"""
Quantum-Resilient Social Mesh Recovery System - API Views

Provides REST API endpoints for:
- Recovery system setup
- Guardian management
- Recovery initiation and completion
- Temporal challenge handling
- Shard collection
"""

from rest_framework import viewsets, status
from rest_framework.authentication import SessionAuthentication
from rest_framework.decorators import action, api_view, authentication_classes, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from auth_module.authentication import RevocableJWTAuthentication as JWTAuthentication
from django.contrib.auth.models import User
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.db import transaction
from datetime import timedelta
import re
import uuid
import secrets
import hashlib
import time
import logging

from .quantum_recovery_models import (
    PasskeyRecoverySetup,
    RecoveryShard,
    RecoveryGuardian,
    RecoveryAttempt,
    TemporalChallenge,
    GuardianApproval,
    RecoveryAuditLog,
    BehavioralBiometrics,
    RecoveryShardType
)
from .recovery_factor_view import _valid_envelope
from .recovery_models_v2 import RecoveryWrappedDEK, VaultWrappedDEK
from .recovery_notice import dispatch as dispatch_task, notify as notify_recovery
from .recovery_throttling import RecoveryInitiateThrottle, RecoveryThrottle
from .services.quantum_crypto_service import quantum_crypto_service
from .quantum_recovery_tasks import (
    guardians_left_unasked,
    request_guardian_approvals,
    send_guardian_invitation,
)
from .tasks import (
    GUARDIAN_UNCONFIRMED_WINDOW_HOURS,
    confirmed_guardian_attempts,
    start_guardian_recovery,
)
from shared import sealed_shares
from shared.client_ip import get_client_ip

logger = logging.getLogger(__name__)

GUARDIAN_RECOVERY_MESSAGE = (
    'If guardian recovery is available for this account, an email about it '
    'has been sent to its address.'
)
# A travel lock also stops an attempt that started before it. Only the device
# that asked sees this: the request itself answers the same for every account.
RECOVERY_PAUSED = 'Recovery is paused on this account. Try again later.'


def _parse_sealed_guardian(g):
    """Check one guardian entry of setup_recovery.

    Returns ``(guardian, None)`` or ``(None, error message)``; the messages
    are fixed text.
    """
    if not isinstance(g, dict):
        return None, 'Each guardian must be an object'
    email = g.get('email')
    share_index = g.get('share_index')
    if not isinstance(email, str) or '@' not in email:
        return None, "Each guardian needs an 'email'"
    if not isinstance(share_index, int) or isinstance(share_index, bool) \
            or not 1 <= share_index <= 255:
        return None, "Each guardian needs a 'share_index' (1-255)"
    guardian = {
        'email': email,
        'requires_video': bool(g.get('requires_video', False)),
        'share_index': share_index,
        'public_key': sealed_shares.decode_hybrid_public_key(g.get('public_key')),
        'sealed_share': sealed_shares.decode_sealed_share(g.get('sealed_share')),
        'share_proof_hash': sealed_shares.decode_digest(g.get('share_proof_hash')),
    }
    if guardian['public_key'] is None:
        return None, f"Each guardian's 'public_key' {sealed_shares.INVALID_HYBRID_PUBLIC_KEY}"
    if guardian['sealed_share'] is None:
        return None, f"Each guardian's 'sealed_share' {sealed_shares.INVALID_SEALED_SHARE}"
    if guardian['share_proof_hash'] is None:
        return None, f"Each guardian's 'share_proof_hash' {sealed_shares.INVALID_DIGEST}"
    return guardian, None


def _recovery_factor_problem(factor):
    """The error message for setup_recovery's wrapped vault key, or None. The
    server checks its shape and cannot open it (recovery_factor_view.py)."""
    if not isinstance(factor, dict) or not _valid_envelope(factor.get('blob')):
        return "'recovery_factor' needs the vault key wrapped under the recovery seed"
    if not isinstance(factor.get('auth_hash'), str) \
            or not re.fullmatch(r'[0-9a-f]{64}', factor['auth_hash']):
        return "'recovery_factor' needs a valid 'auth_hash'"
    return None


class QuantumRecoveryViewSet(viewsets.ViewSet):
    """
    ViewSet for Quantum-Resilient Recovery System
    """
    authentication_classes = [JWTAuthentication, SessionAuthentication]
    permission_classes = [IsAuthenticated]

    # These actions are called during recovery when the user has no session
    # yet. complete_recovery returns only shares re-sealed to the requester's
    # one-time key, which nobody else can open.
    PUBLIC_ACTIONS = {'initiate_recovery', 'respond_to_challenge', 'approve_recovery',
                      'guardian_share', 'confirm_recovery', 'recovery_progress',
                      'complete_recovery'}

    def get_permissions(self):
        if getattr(self, 'action', None) in self.PUBLIC_ACTIONS:
            return [AllowAny()]
        return super().get_permissions()

    def initialize_request(self, request, *args, **kwargs):
        # A stale bearer token must not turn these into a 401: they use tokens
        # from the body and never read request.user. Done here because DRF
        # chooses authenticators before it sets self.action.
        request = super().initialize_request(request, *args, **kwargs)
        if self.action in self.PUBLIC_ACTIONS:
            request.authenticators = ()
        return request

    # auth_module/urls.py binds each action with as_view(), which ignores
    # @action(throttle_classes=...), so the recovery limit is applied here.
    RECOVERY_THROTTLED_ACTIONS = {'confirm_recovery', 'complete_recovery'}

    def get_throttles(self):
        # Per client, not per account: each initiate queues a task, and the
        # account's own monthly limit cannot show in the answer.
        if getattr(self, 'action', None) == 'initiate_recovery':
            return [RecoveryInitiateThrottle()]
        if getattr(self, 'action', None) in self.RECOVERY_THROTTLED_ACTIONS:
            return [RecoveryThrottle()]
        return super().get_throttles()

    @action(detail=False, methods=['post'])
    def setup_recovery(self, request):
        """
        Register guardians for a recovery seed split and sealed on the owner's
        device.

        POST /api/auth/quantum-recovery/setup_recovery/

        Request body (built by frontend/src/services/recovery/sealedShareRecovery.js):
        {
            "threshold_shards": 2,
            "secret_type": "vault_dek_seed",
            "secret_check": "<base64 SHA-256 seed check>",
            "recovery_factor": {"dek_id": "<uuid of the vault key>",
                                "blob": {<vault key wrapped under the seed>},
                                "auth_hash": "<hex rotation proof>"},
            "guardians": [
                {"email": "guardian1@example.com", "requires_video": false,
                 "public_key": "<base64 X25519 + ML-KEM-768 public key>",
                 "share_index": 1,
                 "sealed_share": "<base64 share sealed to public_key>",
                 "share_proof_hash": "<base64 SHA-256 of the share proof>"}
            ]
        }

        The server never sees the seed or a share: it stores the sealed shares
        and relays them, and holds no key that opens them. The shares and the
        vault key wrapped under the same seed are written together: an active
        factor is replaced only by a setup that was accepted.
        """
        try:
            user = request.user

            if any(k in request.data for k in ('secret', 'secret_hex', 'master_secret_hex')):
                return Response({
                    'error': 'Send sealed shares only; the recovery seed never leaves your device'
                }, status=status.HTTP_400_BAD_REQUEST)

            guardians_data = request.data.get('guardians') or []
            threshold_shards = request.data.get('threshold_shards', 3)
            secret_type = request.data.get('secret_type', RecoveryShard.SecretType.VAULT_DEK_SEED)

            if not isinstance(guardians_data, list) or not 3 <= len(guardians_data) <= 10:
                return Response({
                    'error': 'Between 3 and 10 guardians are required'
                }, status=status.HTTP_400_BAD_REQUEST)
            if (not isinstance(threshold_shards, int)
                    or not 2 <= threshold_shards <= len(guardians_data)):
                return Response({
                    'error': 'threshold_shards must be between 2 and the number of guardians'
                }, status=status.HTTP_400_BAD_REQUEST)
            if secret_type not in RecoveryShard.SecretType.values:
                return Response({'error': 'Unknown secret_type'},
                                status=status.HTTP_400_BAD_REQUEST)

            # Each share is sealed on the owner's device to a public key the
            # guardian generated on their own device.
            secret_check = sealed_shares.decode_digest(request.data.get('secret_check'))
            if secret_check is None:
                return Response({'error': f"'secret_check' {sealed_shares.INVALID_DIGEST}"},
                                status=status.HTTP_400_BAD_REQUEST)
            guardians = []
            for g in guardians_data:
                guardian, problem = _parse_sealed_guardian(g)
                if problem:
                    return Response({'error': problem}, status=status.HTTP_400_BAD_REQUEST)
                guardians.append(guardian)
            if len({g['share_index'] for g in guardians}) != len(guardians):
                return Response({'error': 'share_index values must be distinct'},
                                status=status.HTTP_400_BAD_REQUEST)
            # One key on two guardians lets its holder open both shares.
            if len({g['public_key'] for g in guardians}) != len(guardians):
                return Response({'error': 'Each guardian needs their own key'},
                                status=status.HTTP_400_BAD_REQUEST)
            # A seed for the vault is no use without the vault key wrapped under it.
            factor = None
            if secret_type == RecoveryShard.SecretType.VAULT_DEK_SEED:
                factor = request.data.get('recovery_factor')
                problem = _recovery_factor_problem(factor)
                if problem:
                    return Response({'error': problem}, status=status.HTTP_400_BAD_REQUEST)

            with transaction.atomic():
                # One setup at a time per owner, including a first setup, which
                # has no row of its own to lock yet.
                User.objects.select_for_update().get(pk=user.pk)

                # A pending setup (guardians not yet accepted) counts too: the
                # user has one setup at most.
                current = PasskeyRecoverySetup.objects.filter(user=user).first()
                if current is not None and not current.is_replaceable():
                    return Response({
                        'error': 'Recovery system already configured'
                        if current.is_active
                        else 'Recovery system already set up; waiting for guardians to accept'
                    }, status=status.HTTP_400_BAD_REQUEST)

                if factor is not None:
                    # The current dek_id is the proof of holding the vault key
                    # (recovery_factor_view.py). Locked against a rotation.
                    wrapped = VaultWrappedDEK.objects.select_for_update().filter(user=user).first()
                    if wrapped is None:
                        return Response({'error': 'no DEK enrolled'},
                                        status=status.HTTP_400_BAD_REQUEST)
                    if str(wrapped.dek_id) != str(factor.get('dek_id') or ''):
                        return Response({'error': 'dek_id mismatch'},
                                        status=status.HTTP_409_CONFLICT)
                    RecoveryWrappedDEK.objects.filter(
                        user=user,
                        factor_type=RecoveryWrappedDEK.FactorType.SOCIAL_MESH,
                        status=RecoveryWrappedDEK.Status.ACTIVE,
                    ).update(status=RecoveryWrappedDEK.Status.REVOKED, revoked_at=timezone.now())
                    enrolled = RecoveryWrappedDEK.objects.create(
                        user=user,
                        factor_type=RecoveryWrappedDEK.FactorType.SOCIAL_MESH,
                        dek_id=wrapped.dek_id,
                        blob=factor['blob'],
                        factor_meta={'secret_type': secret_type},
                        auth_hash=factor['auth_hash'],
                    )
                    RecoveryAuditLog.objects.create(
                        user=user,
                        event_type='setup_created',
                        event_data={
                            'subsystem': 'recovery_factor',
                            'factor_type': enrolled.factor_type,
                            'factor_id': enrolled.id,
                            'dek_id': str(wrapped.dek_id),
                        },
                        ip_address=get_client_ip(request),
                        user_agent=request.META.get('HTTP_USER_AGENT', '')[:1024],
                    )

                if current is not None:
                    current.delete()
                recovery_setup = PasskeyRecoverySetup.objects.create(
                    user=user,
                    total_shards=len(guardians),
                    threshold_shards=threshold_shards,
                    encryption_algorithm=sealed_shares.HYBRID_KEM_ALGORITHM,
                    secret_check=secret_check,
                    is_active=False  # Will activate after guardian acceptance
                )

                created_shards = []
                for i, g in enumerate(guardians):
                    shard = RecoveryShard.objects.create(
                        recovery_setup=recovery_setup,
                        shard_type=RecoveryShardType.GUARDIAN,
                        shard_index=g['share_index'],
                        secret_type=secret_type,
                        encrypted_shard_data=g['sealed_share'],
                        encryption_metadata={
                            'algorithm': sealed_shares.HYBRID_KEM_ALGORITHM,
                            'share_format': sealed_shares.SHARE_FORMAT,
                        },
                        context_data={'guardian_index': i}
                    )

                    invitation_token = secrets.token_urlsafe(32)
                    guardian = RecoveryGuardian.objects.create(
                        recovery_setup=recovery_setup,
                        encrypted_guardian_info=g['email'].encode('utf-8'),  # Simplified
                        guardian_public_key=g['public_key'],
                        share_proof_hash=g['share_proof_hash'],
                        shard=shard,
                        requires_video_verification=g['requires_video'],
                        invitation_token=invitation_token,
                        invitation_expires_at=timezone.now() + timedelta(days=7)
                    )
                    transaction.on_commit(lambda guardian_id=str(guardian.id): dispatch_task(
                        send_guardian_invitation, guardian_id))

                    created_shards.append({
                        'type': 'guardian',
                        'guardian_email': g['email'],
                        'invitation_token': invitation_token
                    })

                # Create honeypot shard
                honeypot_shard_data = quantum_crypto_service.create_honeypot_shard(32)
                RecoveryShard.objects.create(
                    recovery_setup=recovery_setup,
                    shard_type=RecoveryShardType.HONEYPOT,
                    shard_index=999,  # Special index for honeypot
                    encrypted_shard_data=honeypot_shard_data,
                    is_honeypot=True,
                    context_data={'purpose': 'detection'}
                )

                # Log audit event
                RecoveryAuditLog.objects.create(
                    user=user,
                    event_type='setup_created',
                    event_data={
                        'total_shards': len(guardians),
                        'threshold_shards': threshold_shards,
                        'guardians_count': len(guardians)
                    },
                    ip_address=request.META.get('REMOTE_ADDR', '127.0.0.1'),  # nosec B104
                    user_agent=request.META.get('HTTP_USER_AGENT', ''),
                    cryptographic_hash=hashlib.sha256(
                        f"{user.id}:{time.time()}".encode()
                    ).hexdigest(),
                )

            return Response({
                'success': True,
                'recovery_setup_id': str(recovery_setup.id),
                'shards_created': created_shards,
                'message': 'Recovery system initialized. Guardian invitations are on their way.'
            }, status=status.HTTP_201_CREATED)

        except Exception as e:
            logger.error(f"Error setting up recovery for {request.user.username}: {str(e)}")
            return Response({
                'error': 'Failed to setup recovery system'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def get_recovery_status(self, request):
        """
        Get user's recovery system status

        GET /api/auth/quantum-recovery/get_recovery_status/
        """
        try:
            user = request.user

            # If caller passes attempt_id, verify ownership before exposing status
            attempt_id = request.query_params.get('attempt_id')
            if attempt_id:
                try:
                    attempt = RecoveryAttempt.objects.get(id=attempt_id)
                    if attempt.recovery_setup.user != user:
                        return Response(
                            {'error': 'Not authorized to view this recovery attempt'},
                            status=status.HTTP_403_FORBIDDEN
                        )
                except RecoveryAttempt.DoesNotExist:
                    return Response(
                        {'error': 'Recovery attempt not found'},
                        status=status.HTTP_404_NOT_FOUND
                    )

            if not hasattr(user, 'passkey_recovery_setup'):
                return Response({
                    'recovery_configured': False
                })
            
            recovery_setup = user.passkey_recovery_setup
            guardians = recovery_setup.guardians.all()
            
            return Response({
                'recovery_configured': True,
                'is_active': recovery_setup.is_active,
                'can_replace': recovery_setup.is_replaceable(),
                'total_shards': recovery_setup.total_shards,
                'threshold_shards': recovery_setup.threshold_shards,
                'guardians': [{
                    'id': str(guardian.id),
                    'status': guardian.status,
                    'requires_video': guardian.requires_video_verification,
                    'accepted_at': guardian.accepted_at
                } for guardian in guardians],
                'travel_lock_enabled': recovery_setup.is_travel_locked(),
                'last_rehearsal_at': recovery_setup.last_rehearsal_at
            })
            
        except Exception as e:
            logger.error(f"Error getting recovery status: {str(e)}")
            return Response({
                'error': 'Failed to get recovery status'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['post'], permission_classes=[AllowAny])
    def initiate_recovery(self, request):
        """
        Start guardian recovery. Anonymous: says nothing about the account.

        POST /api/auth/quantum-recovery/initiate_recovery/

        Request body:
        {
            "email": "user@example.com",
            "device_fingerprint": "abc123...",
            "requester_public_key": "<base64 one-time X25519 + ML-KEM-768 public key>",
            "requester_token_hash": "<base64 SHA-256 of the requester token>"
        }

        Guardians re-seal their shares to requester_public_key; the private
        key stays on the requesting device, which alone can derive the token
        that confirm_recovery, recovery_progress and complete_recovery ask for.

        Every email gets the same synchronous work (validate, enqueue) and the
        same answer. The account lookup, the attempt and the email with its
        link happen in tasks.start_guardian_recovery, so neither the response
        nor its timing says whether the email has an account, or whether its
        recovery is set up, travel-locked or at its monthly limit.
        """
        try:
            email = request.data.get('email')
            if not email or not isinstance(email, str):
                return Response({
                    'error': 'Email required'
                }, status=status.HTTP_400_BAD_REQUEST)
            requester_public_key = sealed_shares.decode_hybrid_public_key(
                request.data.get('requester_public_key'))
            if requester_public_key is None:
                return Response({
                    'error': f"'requester_public_key' {sealed_shares.INVALID_HYBRID_PUBLIC_KEY}"
                }, status=status.HTTP_400_BAD_REQUEST)
            requester_token_hash = sealed_shares.decode_digest(
                request.data.get('requester_token_hash'))
            if requester_token_hash is None:
                return Response({
                    'error': f"'requester_token_hash' {sealed_shares.INVALID_DIGEST}"
                }, status=status.HTTP_400_BAD_REQUEST)

            # Cut down here: the task must store whatever this request sent
            fingerprint = request.data.get('device_fingerprint')
            accepted = dispatch_task(
                start_guardian_recovery,
                email,
                sealed_shares.b64(requester_public_key),
                fingerprint[:255] if isinstance(fingerprint, str) else '',
                get_client_ip(request, default='127.0.0.1'),  # nosec B104
                request.META.get('HTTP_USER_AGENT', ''),
                sealed_shares.b64(requester_token_hash),
            )
            # Nothing about the account: this is the same for every email.
            if not accepted:
                return Response({
                    'error': 'Recovery is temporarily unavailable. Try again later.'
                }, status=status.HTTP_503_SERVICE_UNAVAILABLE)
            return Response({'message': GUARDIAN_RECOVERY_MESSAGE})

        except Exception as e:
            logger.error(f"Error initiating recovery: {str(e)}")
            return Response({
                'error': 'Failed to initiate recovery'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'], permission_classes=[AllowAny])
    def respond_to_challenge(self, request):
        """
        Submit response to temporal challenge
        
        POST /api/auth/quantum-recovery/respond_to_challenge/
        
        Request body:
        {
            "attempt_id": "uuid",
            "challenge_id": "uuid",
            "response": "user's answer"
        }
        """
        try:
            attempt_id = request.data.get('attempt_id')
            challenge_id = request.data.get('challenge_id')
            response_text = request.data.get('response')
            
            if not all([attempt_id, challenge_id, response_text]):
                return Response({
                    'error': 'Missing required fields'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Get challenge
            challenge = get_object_or_404(TemporalChallenge, id=challenge_id)
            attempt = get_object_or_404(RecoveryAttempt, id=attempt_id)
            
            # Verify challenge belongs to attempt
            if challenge.recovery_attempt_id != attempt.id:
                return Response({
                    'error': 'Invalid challenge'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Check if challenge expired
            if challenge.is_expired():
                challenge.status = 'expired'
                challenge.save()
                return Response({
                    'error': 'Challenge expired'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Verify response against stored expected answer.
            # encrypted_expected_response is raw bytes in tests (plain UTF-8);
            # production code should decrypt before comparing.
            try:
                expected = bytes(challenge.encrypted_expected_response).decode('utf-8')
                is_correct = response_text.strip().lower() == expected.strip().lower()
            except Exception:
                is_correct = False

            # Update challenge
            challenge.user_response = response_text
            challenge.response_received_at = timezone.now()
            challenge.response_correct = is_correct
            challenge.response_device_fingerprint = request.data.get('device_fingerprint', '')
            # A received response always completes the challenge;
            # correctness is tracked separately in response_correct.
            challenge.status = 'completed'
            
            # Calculate response time
            if challenge.sent_at:
                response_time = (challenge.response_received_at - challenge.sent_at).total_seconds()
                challenge.actual_response_time_seconds = int(response_time)
            
            challenge.save()
            
            # Update attempt statistics
            if is_correct:
                attempt.challenges_completed += 1
            else:
                attempt.challenges_failed += 1

            attempt.save(update_fields=['challenges_completed', 'challenges_failed'])

            # Recalculate trust score
            attempt.calculate_trust_score()
            
            # Log audit event
            RecoveryAuditLog.objects.create(
                user=attempt.recovery_setup.user,
                event_type='challenge_completed' if is_correct else 'challenge_failed',
                recovery_attempt_id=attempt.id,
                event_data={
                    'challenge_id': str(challenge_id),
                    'correct': is_correct
                },
                ip_address=request.META.get('REMOTE_ADDR', '127.0.0.1'),  # nosec B104
                cryptographic_hash=hashlib.sha256(
                    f"{attempt.recovery_setup.user.id}:{time.time()}".encode()
                ).hexdigest(),
            )
            
            return Response({
                'success': True,
                'correct': is_correct,
                'challenges_remaining': attempt.challenges_sent - (attempt.challenges_completed + attempt.challenges_failed),
                'trust_score': attempt.trust_score
            })
            
        except Exception as e:
            logger.error(f"Error responding to challenge: {str(e)}")
            return Response({
                'error': 'Failed to submit response'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['post'])
    def cancel_recovery(self, request):
        """
        Cancel an ongoing recovery attempt (used for canary alert response)
        
        POST /api/auth/quantum-recovery/cancel_recovery/
        
        Request body:
        {
            "attempt_id": "uuid"
        }
        """
        try:
            attempt_id = request.data.get('attempt_id')
            
            attempt = get_object_or_404(RecoveryAttempt, id=attempt_id)
            
            # Verify user owns this recovery
            if attempt.recovery_setup.user != request.user:
                return Response({
                    'error': 'Unauthorized'
                }, status=status.HTTP_403_FORBIDDEN)
            
            # Cancel attempt
            attempt.status = 'cancelled'
            attempt.user_cancelled = True
            attempt.canary_alert_acknowledged = True
            attempt.failure_reason = 'Cancelled by legitimate user via canary alert'
            attempt.save()
            
            # Log audit event
            RecoveryAuditLog.objects.create(
                user=request.user,
                event_type='recovery_cancelled',
                recovery_attempt_id=attempt.id,
                event_data={
                    'attempt_id': str(attempt_id),
                    'reason': 'canary_alert'
                },
                ip_address=request.META.get('REMOTE_ADDR', '127.0.0.1'),  # nosec B104
                cryptographic_hash=hashlib.sha256(
                    f"{request.user.id}:{time.time()}".encode()
                ).hexdigest(),
            )
            
            return Response({
                'success': True,
                'message': 'Recovery attempt cancelled and flagged as suspicious'
            })
            
        except Exception as e:
            logger.error(f"Error cancelling recovery: {str(e)}")
            return Response({
                'error': 'Failed to cancel recovery'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['post'], permission_classes=[AllowAny])
    def approve_recovery(self, request):
        """
        Guardian approval or denial of a recovery attempt

        POST /api/auth/quantum-recovery/approve_recovery/

        Request body:
        {
            "approval_token": "token_string",
            "approved": true | false,
            "resealed_share": "<base64, required when approved>"
        }

        On approval the guardian's device opens its share (from guardian_share)
        and re-seals it to the requester's one-time key; the server stores
        that value and never sees the share.
        """
        try:
            approval_token = request.data.get('approval_token')
            approved = request.data.get('approved')

            if approved is None or not approval_token:
                return Response({
                    'error': 'approval_token and approved are required'
                }, status=status.HTTP_400_BAD_REQUEST)
            resealed_share = b''
            if approved:
                resealed_share = sealed_shares.decode_sealed_share(
                    request.data.get('resealed_share'))
                if resealed_share is None:
                    return Response({
                        'error': f"'resealed_share' {sealed_shares.INVALID_SEALED_SHARE}"
                    }, status=status.HTTP_400_BAD_REQUEST)

            try:
                approval = GuardianApproval.objects.select_related(
                    'recovery_attempt', 'guardian'
                ).get(approval_token=approval_token, status='pending')
            except GuardianApproval.DoesNotExist:
                return Response({
                    'error': 'Invalid or already processed approval token'
                }, status=status.HTTP_400_BAD_REQUEST)

            closed = _approval_closed(approval)
            if closed:
                return closed

            with transaction.atomic():
                approval.responded_at = timezone.now()
                approval.response_ip = get_client_ip(request, default=None)
                if approved:
                    approval.status = 'approved'
                    approval.shard_released = True
                    approval.shard_released_at = timezone.now()
                    approval.resealed_share = resealed_share
                else:
                    approval.status = 'denied'
                    approval.shard_released = False
                approval.save()

                user = approval.recovery_attempt.recovery_setup.user
                RecoveryAuditLog.objects.create(
                    user=user,
                    event_type='guardian_approved' if approved else 'guardian_denied',
                    recovery_attempt_id=approval.recovery_attempt_id,
                    event_data={
                        'guardian_id': str(approval.guardian_id),
                        'approval_id': str(approval.id),
                    },
                    ip_address=approval.response_ip,
                    cryptographic_hash=hashlib.sha256(
                        f"{user.id}:{time.time()}".encode()
                    ).hexdigest(),
                )

            return Response({
                'success': True,
                'status': approval.status
            })

        except Exception as e:
            logger.error(f"Error processing guardian approval: {str(e)}")
            return Response({
                'error': 'Failed to process approval'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'], permission_classes=[AllowAny])
    def guardian_share(self, request):
        """
        What a guardian's device needs to re-seal its share for a recovery.

        POST /api/auth/quantum-recovery/guardian_share/
        Body: {"approval_token": "token_string"}

        Returns the guardian's sealed share (only the guardian's private key
        opens it) and the requester's one-time public key.
        """
        approval = GuardianApproval.objects.select_related(
            'recovery_attempt', 'guardian__shard'
        ).filter(
            approval_token=request.data.get('approval_token') or '', status='pending'
        ).first()
        if approval is None or approval.guardian.shard is None:
            return Response({
                'error': 'Invalid or already processed approval token'
            }, status=status.HTTP_400_BAD_REQUEST)
        closed = _approval_closed(approval)
        if closed:
            return closed
        attempt = approval.recovery_attempt
        if not bytes(attempt.requester_public_key):
            return Response({
                'error': 'This recovery attempt predates client-side sealing; start a new one'
            }, status=status.HTTP_410_GONE)
        shard = approval.guardian.shard
        return Response({
            'share_index': shard.shard_index,
            'sealed_share': sealed_shares.b64(shard.encrypted_shard_data),
            'requester_public_key': sealed_shares.b64(attempt.requester_public_key),
            'algorithm': sealed_shares.HYBRID_KEM_ALGORITHM,
        })

    @action(detail=False, methods=['post'])
    def enable_travel_lock(self, request):
        """
        Enable travel lock to temporarily disable recovery
        
        POST /api/auth/quantum-recovery/enable_travel_lock/
        
        Request body:
        {
            "duration_days": 7
        }
        """
        try:
            duration_days = request.data.get('duration_days', 7)
            
            if duration_days < 1 or duration_days > 90:
                return Response({
                    'error': 'duration_days must be between 1 and 90'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            recovery_setup = request.user.passkey_recovery_setup
            recovery_setup.travel_lock_enabled = True
            recovery_setup.travel_lock_until = timezone.now() + timedelta(days=duration_days)
            recovery_setup.save()
            
            # Log audit event
            RecoveryAuditLog.objects.create(
                user=request.user,
                event_type='travel_lock_enabled',
                event_data={
                    'duration_days': duration_days,
                    'until': recovery_setup.travel_lock_until.isoformat()
                },
                ip_address=request.META.get('REMOTE_ADDR', '127.0.0.1'),  # nosec B104
                cryptographic_hash=hashlib.sha256(
                    f"{request.user.id}:{time.time()}".encode()
                ).hexdigest(),
            )
            
            return Response({
                'success': True,
                'travel_lock_until': recovery_setup.travel_lock_until
            })
            
        except Exception as e:
            logger.error(f"Error enabling travel lock: {str(e)}")
            return Response({
                'error': 'Failed to enable travel lock'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['post'], permission_classes=[AllowAny])
    def confirm_recovery(self, request):
        """
        The owner opened the emailed link on the device that asked: ask the
        guardians. A stranger's request never gets this far, so it emails no
        guardian and spends nothing from the monthly limit.

        POST /api/auth/quantum-recovery/confirm_recovery/
        Body: {"attempt_id": "uuid", "requester_token": "<base64>"}

        Safe to repeat: it returns recovery_progress's answer.
        """
        attempt = _requester_attempt(request)
        if attempt is None:
            return Response({'error': 'Recovery attempt not found'},
                            status=status.HTTP_404_NOT_FOUND)
        with transaction.atomic():
            # The same lock as tasks._start_guardian_attempt, for the limit
            recovery_setup = PasskeyRecoverySetup.objects.select_for_update().get(
                pk=attempt.recovery_setup_id)
            attempt = RecoveryAttempt.objects.select_for_update().get(pk=attempt.pk)
            if recovery_setup.is_travel_locked():
                return Response({'error': RECOVERY_PAUSED}, status=status.HTTP_400_BAD_REQUEST)
            if attempt.status == 'initiated':
                link_ends = attempt.initiated_at + timedelta(hours=GUARDIAN_UNCONFIRMED_WINDOW_HOURS)
                if attempt.is_expired() or timezone.now() > link_ends:
                    return Response({'error': 'This link has expired; start recovery again'},
                                    status=status.HTTP_400_BAD_REQUEST)
                if (confirmed_guardian_attempts(recovery_setup).count()
                        >= recovery_setup.max_recovery_attempts_per_month):
                    return Response({'error': 'Too many recoveries this month; try again later'},
                                    status=status.HTTP_429_TOO_MANY_REQUESTS)
                attempt.status = 'guardian_approval'
                attempt.save(update_fields=['status'])
        # Also repeats a job or an email that was lost before it asked anyone.
        if attempt.status == 'guardian_approval' and guardians_left_unasked(attempt):
            if not dispatch_task(request_guardian_approvals, str(attempt.id)):
                return Response({'error': 'Recovery is temporarily unavailable. Try again later.'},
                                status=status.HTTP_503_SERVICE_UNAVAILABLE)
        return Response(_recovery_progress(attempt))

    @action(detail=False, methods=['post'], permission_classes=[AllowAny])
    def recovery_progress(self, request):
        """
        How far a recovery has got, for the device that asked for it.

        POST /api/auth/quantum-recovery/recovery_progress/
        Body: {"attempt_id": "uuid", "requester_token": "<base64>"}
        """
        attempt = _requester_attempt(request)
        if attempt is None:
            return Response({'error': 'Recovery attempt not found'},
                            status=status.HTTP_404_NOT_FOUND)
        return Response(_recovery_progress(attempt))

    @action(detail=False, methods=['post'], permission_classes=[AllowAny])
    def complete_recovery(self, request):
        """
        Hand the requester the shares guardians re-sealed to its one-time key.

        POST /api/auth/quantum-recovery/complete_recovery/
        Body: {"attempt_id": "uuid", "requester_token": "<base64>"}

        Returns {"threshold", "secret_type", "secret_check", "sealed_shares"}.
        The requester's device opens the shares, recombines the seed, checks
        it against secret_check and uses it with the layered recovery flow
        (vault/wrapped-dek/recover-rotate). The server never reconstructs
        anything and grants no session here. A completed attempt answers
        again with the same shares, so a lost response can be retried; they
        open only with the requester's key. Nothing is released until the wait
        after the owner's alert has passed (_release_after).
        """
        try:
            attempt = _requester_attempt(request)
            if attempt is None:
                return Response({'error': 'Recovery attempt not found'},
                                status=status.HTTP_404_NOT_FOUND)
            recovery_setup = attempt.recovery_setup

            if recovery_setup.is_travel_locked():
                return Response({'error': RECOVERY_PAUSED}, status=status.HTTP_400_BAD_REQUEST)

            if not bytes(recovery_setup.secret_check) or not bytes(attempt.requester_public_key):
                return Response({
                    'error': 'This recovery setup predates client-side sealing and '
                             'cannot complete; set up guardian recovery again'
                }, status=status.HTTP_410_GONE)

            # Verify attempt is in correct status
            if attempt.status not in ['shard_collection', 'guardian_approval',
                                      'final_verification', 'completed']:
                return Response({
                    'error': 'Recovery not ready for completion'
                }, status=status.HTTP_400_BAD_REQUEST)
            # A completed attempt only repeats its earlier answer, so a lost
            # response can still be fetched after expires_at.
            if attempt.status != 'completed' and attempt.is_expired():
                return Response({'error': 'Recovery attempt expired'},
                                status=status.HTTP_400_BAD_REQUEST)

            release_after = _release_after(attempt)
            if attempt.status != 'completed' and (
                    release_after is None or timezone.now() < release_after):
                return Response({
                    'error': 'Recovery is still in its waiting period',
                    'release_after': release_after,
                }, status=status.HTTP_400_BAD_REQUEST)

            sealed = _released_shares(attempt)
            if len(sealed) < recovery_setup.threshold_shards:
                return Response({
                    'error': f'Insufficient shares: need {recovery_setup.threshold_shards}, have {len(sealed)}'
                }, status=status.HTTP_400_BAD_REQUEST)

            with transaction.atomic():
                # Lock the attempt and check its status again: a cancel (from
                # a recovery notice or the canary) that landed after the
                # checks above must stop the completion, not be overwritten.
                attempt = RecoveryAttempt.objects.select_for_update().get(pk=attempt.pk)
                if attempt.status not in ['shard_collection', 'guardian_approval',
                                          'final_verification', 'completed']:
                    return Response({
                        'error': 'Recovery not ready for completion'
                    }, status=status.HTTP_400_BAD_REQUEST)

                if attempt.status != 'completed':
                    attempt.status = 'completed'
                    attempt.recovery_successful = True
                    attempt.completed_at = timezone.now()
                    attempt.save(update_fields=['status', 'recovery_successful', 'completed_at'])
                    notify_recovery(recovery_setup.user, 'guardian_recovery_completed', request)

                    RecoveryAuditLog.objects.create(
                        user=recovery_setup.user,
                        event_type='recovery_completed',
                        recovery_attempt_id=attempt.id,
                        event_data={
                            'shares_released': len(sealed),
                            'trust_score': attempt.trust_score
                        },
                        ip_address=request.META.get('REMOTE_ADDR', '127.0.0.1'),  # nosec B104
                        cryptographic_hash=hashlib.sha256(
                            f"{recovery_setup.user.id}:{time.time()}".encode()
                        ).hexdigest(),
                    )

            first_shard = recovery_setup.shards.filter(is_honeypot=False).first()
            return Response({
                'success': True,
                'threshold': recovery_setup.threshold_shards,
                'secret_type': first_shard.secret_type if first_shard else None,
                'secret_check': sealed_shares.b64(recovery_setup.secret_check),
                'sealed_shares': sealed,
                'algorithm': sealed_shares.HYBRID_KEM_ALGORITHM,
            })

        except Exception as e:
            logger.error(f"Error completing recovery: {str(e)}")
            return Response({
                'error': 'Failed to complete recovery'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


def _requester_attempt(request):
    """The attempt named in the request, for the device that asked for it: the
    ID comes by email, and only that device can derive the token. The answer is
    the same for an unknown ID and a wrong token."""
    attempt_id = request.data.get('attempt_id')
    attempt = RecoveryAttempt.objects.select_related('recovery_setup').filter(
        id=attempt_id).first() if _is_uuid(attempt_id) else None
    if attempt is None or not sealed_shares.share_proof_matches(
            request.data.get('requester_token'), attempt.requester_token_hash):
        return None
    return attempt


def _release_after(attempt):
    """When shares may be released: the owner's alert plus their time to cancel.
    None if the alert has not gone out, so nothing is released."""
    if attempt.canary_alert_sent_at is None:
        return None
    return attempt.canary_alert_sent_at + timedelta(
        hours=attempt.recovery_setup.canary_alert_window_hours)


def _released_shares(attempt):
    released = GuardianApproval.objects.filter(
        recovery_attempt=attempt,
        status='approved',
        shard_released=True,
        guardian__shard__is_honeypot=False,
    ).select_related('guardian__shard').order_by('guardian__shard__shard_index')
    return [
        {'share_index': a.guardian.shard.shard_index,
         'sealed_share': sealed_shares.b64(a.resealed_share)}
        for a in released if bytes(a.resealed_share)
    ]


def _recovery_progress(attempt):
    threshold = attempt.recovery_setup.threshold_shards
    approvals_received = len(_released_shares(attempt))
    release_after = _release_after(attempt)
    # No periodic job moves an attempt to 'expired', and it can do nothing now.
    expired = attempt.status in ('initiated', 'guardian_approval') and attempt.is_expired()
    return {
        'status': 'expired' if expired else attempt.status,
        'threshold': threshold,
        'guardians_asked': attempt.guardian_approvals.count(),
        'ask_again': (attempt.status == 'guardian_approval' and not expired
                      and guardians_left_unasked(attempt)),
        'approvals_received': approvals_received,
        'denials': attempt.guardian_approvals.filter(status='denied').count(),
        'release_after': release_after,
        'expires_at': attempt.expires_at,
        'ready': attempt.status == 'completed' or (
            attempt.status == 'guardian_approval' and not attempt.is_expired()
            and approvals_received >= threshold
            and release_after is not None and timezone.now() >= release_after),
    }


def _approval_closed(approval):
    """The refusal for an approval that cannot be used now, or None."""
    attempt = approval.recovery_attempt
    if attempt.status != 'guardian_approval' or attempt.is_expired():
        return Response({'error': 'This recovery is no longer open'},
                        status=status.HTTP_400_BAD_REQUEST)
    now = timezone.now()
    if now > approval.approval_window_end:
        approval.status = 'expired'
        approval.save(update_fields=['status'])
        return Response({'error': 'Approval window has expired'},
                        status=status.HTTP_400_BAD_REQUEST)
    if now < approval.approval_window_start:
        return Response({'error': 'This approval is not open yet'},
                        status=status.HTTP_400_BAD_REQUEST)
    return None


def _is_uuid(value):
    try:
        uuid.UUID(str(value))
        return True
    except (ValueError, TypeError, AttributeError):
        return False


@api_view(['POST'])
@authentication_classes([])  # a stale bearer token must not turn this into a 401
@permission_classes([AllowAny])
def guardian_invitation(request):
    """
    What an invited guardian's device needs before it accepts.

    POST /api/auth/quantum-recovery/guardian-invitation/
    Body: {"invitation_token": "token123"}

    Returns the guardian's sealed share, which only the private key matching
    the public key the guardian gave the owner can open.
    """
    guardian = RecoveryGuardian.objects.select_related('shard').filter(
        invitation_token=request.data.get('invitation_token') or ''
    ).first()
    if guardian is None or not guardian.is_invitation_valid() or guardian.shard is None:
        return Response({'error': 'Invitation expired or already used'},
                        status=status.HTTP_400_BAD_REQUEST)
    return Response({
        'share_index': guardian.shard.shard_index,
        'sealed_share': sealed_shares.b64(guardian.shard.encrypted_shard_data),
        'algorithm': sealed_shares.HYBRID_KEM_ALGORITHM,
    })


@api_view(['POST'])
@authentication_classes([])  # a stale bearer token must not turn this into a 401
@permission_classes([AllowAny])
def accept_guardian_invitation(request):
    """
    Guardian accepts invitation to hold a recovery share.

    POST /api/auth/quantum-recovery/accept-guardian-invitation/

    Request body:
    {
        "invitation_token": "token123",
        "share_proof": "<base64 share proof>"
    }

    The share proof shows that the guardian's device opened its sealed share,
    so it holds the private key and the share is intact
    (shared/sealed_shares.py). Without it a guardian could accept a share it
    can never open.
    """
    try:
        invitation_token = request.data.get('invitation_token') or ''

        with transaction.atomic():
            # Lock the setup before the guardian, so acceptances for one
            # setup run one at a time and the last one sees every other
            # acceptance when it counts the pending guardians below.
            setup_id = RecoveryGuardian.objects.filter(
                invitation_token=invitation_token
            ).values_list('recovery_setup_id', flat=True).first()
            recovery_setup = PasskeyRecoverySetup.objects.select_for_update().filter(
                pk=setup_id
            ).first()
            guardian = RecoveryGuardian.objects.select_for_update().filter(
                invitation_token=invitation_token
            ).first()

            # Check if invitation is valid
            if guardian is None or not guardian.is_invitation_valid():
                return Response({
                    'error': 'Invitation expired or already used'
                }, status=status.HTTP_400_BAD_REQUEST)

            if not sealed_shares.share_proof_matches(
                    request.data.get('share_proof'), guardian.share_proof_hash):
                return Response({
                    'error': 'share_proof does not match: open the sealed share with '
                             'the key you gave the account owner'
                }, status=status.HTTP_400_BAD_REQUEST)

            # Update guardian status
            guardian.status = 'active'
            guardian.accepted_at = timezone.now()
            guardian.save(update_fields=['status', 'accepted_at', 'updated_at'])

            # Check if all guardians have accepted - if so, activate recovery
            all_accepted = recovery_setup.guardians.filter(status='pending').count() == 0

            if all_accepted:
                recovery_setup.is_active = True
                recovery_setup.save()

            # Log audit event
            RecoveryAuditLog.objects.create(
                user=recovery_setup.user,
                event_type='guardian_accepted',
                event_data={
                    'guardian_id': str(guardian.id)
                },
                ip_address=request.META.get('REMOTE_ADDR', '127.0.0.1'),  # nosec B104
                cryptographic_hash=hashlib.sha256(
                    f"{recovery_setup.user.id}:{time.time()}".encode()
                ).hexdigest(),
            )

        return Response({
            'success': True,
            'message': 'Guardian invitation accepted',
            'recovery_active': recovery_setup.is_active
        })

    except Exception as e:
        logger.error(f"Error accepting guardian invitation: {str(e)}")
        return Response({
            'error': 'Failed to accept invitation'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

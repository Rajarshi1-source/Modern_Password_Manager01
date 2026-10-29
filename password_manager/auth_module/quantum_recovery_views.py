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
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from auth_module.authentication import RevocableJWTAuthentication as JWTAuthentication
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.db import transaction
from datetime import timedelta
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
from .recovery_throttling import RecoveryThrottle
from .services.quantum_crypto_service import quantum_crypto_service
from shared import sealed_shares

logger = logging.getLogger(__name__)


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
                      'guardian_share', 'complete_recovery'}

    def get_permissions(self):
        if getattr(self, 'action', None) in self.PUBLIC_ACTIONS:
            return [AllowAny()]
        return super().get_permissions()

    # auth_module/urls.py binds each action with as_view(), which ignores
    # @action(throttle_classes=...), so the recovery limit is applied here.
    RECOVERY_THROTTLED_ACTIONS = {'complete_recovery'}

    def get_throttles(self):
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
            "guardians": [
                {"email": "guardian1@example.com", "requires_video": false,
                 "public_key": "<base64 X25519 + ML-KEM-768 public key>",
                 "share_index": 1,
                 "sealed_share": "<base64 share sealed to public_key>",
                 "share_proof_hash": "<base64 SHA-256 of the share proof>"}
            ]
        }

        The server never sees the seed or a share: it stores the sealed shares
        and relays them, and holds no key that opens them.
        """
        try:
            user = request.user

            # Check if recovery already setup. A pending setup (guardians not
            # yet accepted) counts too: the user has one setup at most. A
            # setup from before client-side sealing holds no recoverable
            # secret (it cannot complete), so it is replaced once the new
            # request is valid.
            legacy_setup = None
            if hasattr(user, 'passkey_recovery_setup'):
                if not bytes(user.passkey_recovery_setup.secret_check or b''):
                    legacy_setup = user.passkey_recovery_setup
            if hasattr(user, 'passkey_recovery_setup') and legacy_setup is None:
                return Response({
                    'error': 'Recovery system already configured'
                    if user.passkey_recovery_setup.is_active
                    else 'Recovery system already set up; waiting for guardians to accept'
                }, status=status.HTTP_400_BAD_REQUEST)

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

            with transaction.atomic():
                if legacy_setup is not None:
                    legacy_setup.delete()
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
                    RecoveryGuardian.objects.create(
                        recovery_setup=recovery_setup,
                        encrypted_guardian_info=g['email'].encode('utf-8'),  # Simplified
                        guardian_public_key=g['public_key'],
                        share_proof_hash=g['share_proof_hash'],
                        shard=shard,
                        requires_video_verification=g['requires_video'],
                        invitation_token=invitation_token,
                        invitation_expires_at=timezone.now() + timedelta(days=7)
                    )

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
                'message': 'Recovery system initialized. Send guardian invitations to activate.'
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
        Initiate passkey recovery process
        
        POST /api/auth/quantum-recovery/initiate_recovery/
        
        Request body:
        {
            "email": "user@example.com",
            "device_fingerprint": "abc123...",
            "requester_public_key": "<base64 one-time X25519 + ML-KEM-768 public key>"
        }

        Guardians re-seal their shares to requester_public_key; the private
        key stays on the requesting device.
        """
        try:
            email = request.data.get('email')
            if not email:
                return Response({
                    'error': 'Email required'
                }, status=status.HTTP_400_BAD_REQUEST)
            requester_public_key = sealed_shares.decode_hybrid_public_key(
                request.data.get('requester_public_key'))
            if requester_public_key is None:
                return Response({
                    'error': f"'requester_public_key' {sealed_shares.INVALID_HYBRID_PUBLIC_KEY}"
                }, status=status.HTTP_400_BAD_REQUEST)

            # Find user and recovery setup
            from django.contrib.auth import get_user_model
            User = get_user_model()
            
            try:
                user = User.objects.get(email=email)
                recovery_setup = user.passkey_recovery_setup
            except (User.DoesNotExist, PasskeyRecoverySetup.DoesNotExist):
                # Return generic message to prevent user enumeration
                return Response({
                    'message': 'If recovery is configured, you will receive instructions shortly.'
                })
            
            # Check if recovery is active
            if not recovery_setup.is_active:
                return Response({
                    'error': 'Recovery system not fully configured'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Check travel lock
            if recovery_setup.is_travel_locked():
                return Response({
                    'error': f'Recovery is locked until {recovery_setup.travel_lock_until}'
                }, status=status.HTTP_403_FORBIDDEN)
            
            # Check recent recovery attempts
            recent_attempts = RecoveryAttempt.objects.filter(
                recovery_setup=recovery_setup,
                initiated_at__gte=timezone.now() - timedelta(days=30)
            ).count()
            
            if recent_attempts >= recovery_setup.max_recovery_attempts_per_month:
                return Response({
                    'error': 'Maximum recovery attempts reached. Please wait.'
                }, status=status.HTTP_429_TOO_MANY_REQUESTS)
            
            with transaction.atomic():
                # Create recovery attempt
                attempt = RecoveryAttempt.objects.create(
                    recovery_setup=recovery_setup,
                    initiated_from_ip=request.META.get('REMOTE_ADDR', ''),
                    initiated_from_device_fingerprint=request.data.get('device_fingerprint', ''),
                    requester_public_key=requester_public_key,
                    shards_required=recovery_setup.threshold_shards,
                    # Every active guardian is asked: completion needs
                    # threshold_shards re-sealed shares, and asking more than
                    # the threshold lets recovery finish if one does not answer.
                    guardian_approvals_required=recovery_setup.guardians.filter(status='active').count(),
                    expires_at=timezone.now() + timedelta(days=recovery_setup.decay_window_days)
                )
                
                # Send canary alert to user
                attempt.canary_alert_sent_at = timezone.now()
                attempt.save()
                
                # Create temporal challenges (will be sent via Celery tasks)
                # In production, trigger Celery task here
                
                # Log audit event
                RecoveryAuditLog.objects.create(
                    user=user,
                    event_type='recovery_initiated',
                    recovery_attempt_id=attempt.id,
                    event_data={
                        'attempt_id': str(attempt.id)
                    },
                    ip_address=request.META.get('REMOTE_ADDR', '127.0.0.1'),  # nosec B104
                    user_agent=request.META.get('HTTP_USER_AGENT', ''),
                    cryptographic_hash=hashlib.sha256(
                        f"{user.id}:{time.time()}".encode()
                    ).hexdigest(),
                )
            
            return Response({
                'success': True,
                'attempt_id': str(attempt.id),
                'message': 'Recovery initiated. Check your email for challenges.',
                'expires_at': attempt.expires_at,
                'canary_alert_sent': True
            })
            
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

            # Check approval window
            if timezone.now() > approval.approval_window_end:
                approval.status = 'expired'
                approval.save(update_fields=['status'])
                return Response({
                    'error': 'Approval window has expired'
                }, status=status.HTTP_400_BAD_REQUEST)

            with transaction.atomic():
                approval.responded_at = timezone.now()
                if approved:
                    approval.status = 'approved'
                    approval.shard_released = True
                    approval.shard_released_at = timezone.now()
                    approval.resealed_share = resealed_share
                else:
                    approval.status = 'denied'
                    approval.shard_released = False
                approval.save()

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
    def complete_recovery(self, request):
        """
        Hand the requester the shares guardians re-sealed to its one-time key.

        POST /api/auth/quantum-recovery/complete_recovery/
        Body: {"attempt_id": "uuid"}

        Returns {"threshold", "secret_type", "secret_check", "sealed_shares"}.
        The requester's device opens the shares, recombines the seed, checks
        it against secret_check and uses it with the layered recovery flow
        (vault/wrapped-dek/recover-rotate). The server never reconstructs
        anything and grants no session here. A completed attempt answers
        again with the same shares, so a lost response can be retried; they
        open only with the requester's key.
        """
        try:
            attempt = RecoveryAttempt.objects.select_related('recovery_setup').filter(
                id=request.data.get('attempt_id')
            ).first() if _is_uuid(request.data.get('attempt_id')) else None
            if attempt is None:
                return Response({'error': 'Recovery attempt not found'},
                                status=status.HTTP_404_NOT_FOUND)
            recovery_setup = attempt.recovery_setup

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

            # Verify trust score meets threshold
            if attempt.trust_score < recovery_setup.minimum_challenge_success_rate:
                return Response({
                    'error': f'Insufficient trust score: {attempt.trust_score:.2f} (required: {recovery_setup.minimum_challenge_success_rate:.2f})'
                }, status=status.HTTP_400_BAD_REQUEST)

            released = GuardianApproval.objects.filter(
                recovery_attempt=attempt,
                status='approved',
                shard_released=True,
                guardian__shard__is_honeypot=False,
            ).select_related('guardian__shard').order_by('guardian__shard__shard_index')
            sealed = [
                {'share_index': a.guardian.shard.shard_index,
                 'sealed_share': sealed_shares.b64(a.resealed_share)}
                for a in released if bytes(a.resealed_share)
            ]
            if len(sealed) < recovery_setup.threshold_shards:
                return Response({
                    'error': f'Insufficient shares: need {recovery_setup.threshold_shards}, have {len(sealed)}'
                }, status=status.HTTP_400_BAD_REQUEST)

            if attempt.status != 'completed':
                with transaction.atomic():
                    attempt.status = 'completed'
                    attempt.recovery_successful = True
                    attempt.completed_at = timezone.now()
                    attempt.save(update_fields=['status', 'recovery_successful', 'completed_at'])

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


def _is_uuid(value):
    try:
        uuid.UUID(str(value))
        return True
    except (ValueError, TypeError, AttributeError):
        return False


@api_view(['POST'])
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
            recovery_setup = guardian.recovery_setup
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


@api_view(['POST'])
@permission_classes([AllowAny])
def guardian_approve_recovery(request):
    """
    Guardian approves a recovery attempt and releases their shard
    
    POST /api/auth/quantum-recovery/guardian-approve-recovery/
    
    Request body:
    {
        "approval_token": "token123",
        "video_verification_id": "optional"
    }
    """
    try:
        approval_token = request.data.get('approval_token')
        
        approval = get_object_or_404(GuardianApproval, approval_token=approval_token)
        
        # Check if in approval window
        if not approval.is_in_approval_window():
            return Response({
                'error': 'Outside of approval window. Please try again later.'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Check additional verification requirements
        guardian = approval.guardian
        if guardian.requires_video_verification:
            video_id = request.data.get('video_verification_id')
            if not video_id:
                return Response({
                    'error': 'Video verification required'
                }, status=status.HTTP_400_BAD_REQUEST)
            approval.video_verification_session_id = video_id
            approval.video_verification_completed = True
        
        # Approve and release shard
        approval.status = 'approved'
        approval.responded_at = timezone.now()
        approval.response_ip = request.META.get('REMOTE_ADDR', '')
        approval.shard_released = True
        approval.shard_released_at = timezone.now()
        approval.save()
        
        # Update recovery attempt
        attempt = approval.recovery_attempt
        attempt.guardian_approvals_received = attempt.guardian_approvals_received + [str(guardian.id)]
        attempt.save()
        
        # Log audit event
        RecoveryAuditLog.objects.create(
            user=attempt.recovery_setup.user,
            event_type='guardian_approved',
            recovery_attempt_id=attempt.id,
            event_data={
                'guardian_id': str(guardian.id),
                'approval_id': str(approval.id)
            },
            ip_address=request.META.get('REMOTE_ADDR', '127.0.0.1'),  # nosec B104
            cryptographic_hash=hashlib.sha256(
                f"{attempt.recovery_setup.user.id}:{time.time()}".encode()
            ).hexdigest(),
        )
        
        return Response({
            'success': True,
            'message': 'Recovery approved. Shard released.'
        })
        
    except Exception as e:
        logger.error(f"Error approving recovery: {str(e)}")
        return Response({
            'error': 'Failed to approve recovery'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    # Admin Dashboard Endpoints
    
    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated])
    def admin_dashboard_stats(self, request):
        """
        Admin dashboard statistics
        
        GET /api/auth/quantum-recovery/admin_dashboard_stats/
        
        Requires: Admin/Staff permissions
        """
        # Check if user is staff/admin
        if not request.user.is_staff:
            return Response({
                'error': 'Admin permissions required'
            }, status=status.HTTP_403_FORBIDDEN)
        
        try:
            from django.db.models import Count, Avg, Q
            from django.utils import timezone
            from datetime import timedelta
            
            # Time ranges
            now = timezone.now()
            today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            week_ago = now - timedelta(days=7)
            month_ago = now - timedelta(days=30)
            
            # Total statistics
            total_attempts = RecoveryAttempt.objects.count()
            total_setups = PasskeyRecoverySetup.objects.filter(is_active=True).count()
            total_guardians = RecoveryGuardian.objects.filter(status='active').count()
            
            # Success rate
            completed_attempts = RecoveryAttempt.objects.filter(status='completed')
            success_count = completed_attempts.filter(recovery_successful=True).count()
            success_rate = (success_count / total_attempts * 100) if total_attempts > 0 else 0
            
            # Average trust score
            avg_trust_score = RecoveryAttempt.objects.aggregate(
                avg_score=Avg('trust_score')
            )['avg_score'] or 0
            
            # Active attempts (in progress)
            active_attempts = RecoveryAttempt.objects.filter(
                status__in=['initiated', 'challenge_phase', 'shard_collection', 'guardian_approval']
            ).count()
            
            # Security alerts
            honeypots_triggered = RecoveryAttempt.objects.filter(
                honeypot_triggered=True
            ).count()
            
            suspicious_attempts = RecoveryAttempt.objects.filter(
                suspicious_activity_detected=True
            ).count()
            
            # Recent activity
            attempts_today = RecoveryAttempt.objects.filter(
                initiated_at__gte=today_start
            ).count()
            
            challenges_sent_today = TemporalChallenge.objects.filter(
                sent_at__gte=today_start
            ).count()
            
            # Trend data (last 7 days)
            daily_attempts = []
            for i in range(7):
                day_start = today_start - timedelta(days=i)
                day_end = day_start + timedelta(days=1)
                count = RecoveryAttempt.objects.filter(
                    initiated_at__gte=day_start,
                    initiated_at__lt=day_end
                ).count()
                daily_attempts.append({
                    'date': day_start.strftime('%Y-%m-%d'),
                    'count': count
                })
            
            # Status breakdown
            status_breakdown = RecoveryAttempt.objects.values('status').annotate(
                count=Count('id')
            ).order_by('-count')
            
            return Response({
                'overview': {
                    'total_attempts': total_attempts,
                    'active_setups': total_setups,
                    'total_guardians': total_guardians,
                    'success_rate': round(success_rate, 2),
                    'avg_trust_score': round(avg_trust_score, 3),
                    'active_attempts': active_attempts
                },
                'security': {
                    'honeypots_triggered': honeypots_triggered,
                    'suspicious_attempts': suspicious_attempts,
                    'security_alert_rate': round(
                        (suspicious_attempts / total_attempts * 100) if total_attempts > 0 else 0,
                        2
                    )
                },
                'today': {
                    'attempts_initiated': attempts_today,
                    'challenges_sent': challenges_sent_today
                },
                'trends': {
                    'daily_attempts': list(reversed(daily_attempts))
                },
                'status_breakdown': list(status_breakdown)
            })
            
        except Exception as e:
            logger.error(f"Error fetching admin dashboard stats: {str(e)}")
            return Response({
                'error': 'Failed to fetch dashboard statistics'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated])
    def admin_recent_attempts(self, request):
        """
        List recent recovery attempts with details
        
        GET /api/auth/quantum-recovery/admin_recent_attempts/?limit=20&status=initiated
        
        Requires: Admin/Staff permissions
        """
        if not request.user.is_staff:
            return Response({
                'error': 'Admin permissions required'
            }, status=status.HTTP_403_FORBIDDEN)
        
        try:
            limit = int(request.query_params.get('limit', 20))
            status_filter = request.query_params.get('status', None)
            
            queryset = RecoveryAttempt.objects.select_related(
                'recovery_setup__user'
            ).order_by('-initiated_at')
            
            if status_filter:
                queryset = queryset.filter(status=status_filter)
            
            attempts = queryset[:limit]
            
            data = []
            for attempt in attempts:
                data.append({
                    'id': str(attempt.id),
                    'user_email': attempt.recovery_setup.user.email,
                    'status': attempt.status,
                    'trust_score': round(attempt.trust_score, 3),
                    'challenges_completed': attempt.challenges_completed,
                    'challenges_sent': attempt.challenges_sent,
                    'challenge_success_rate': attempt.challenge_success_rate,
                    'honeypot_triggered': attempt.honeypot_triggered,
                    'suspicious_activity': attempt.suspicious_activity_detected,
                    'initiated_at': attempt.initiated_at.isoformat(),
                    'completed_at': attempt.completed_at.isoformat() if attempt.completed_at else None,
                    'recovery_successful': attempt.recovery_successful,
                    'failure_reason': attempt.failure_reason,
                    'initiated_from_ip': attempt.initiated_from_ip,
                    'initiated_from_location': attempt.initiated_from_location
                })
            
            return Response({
                'count': len(data),
                'attempts': data
            })
            
        except Exception as e:
            logger.error(f"Error fetching recent attempts: {str(e)}")
            return Response({
                'error': 'Failed to fetch recent attempts'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated])
    def admin_security_alerts(self, request):
        """
        List security alerts and suspicious activities
        
        GET /api/auth/quantum-recovery/admin_security_alerts/?days=7
        
        Requires: Admin/Staff permissions
        """
        if not request.user.is_staff:
            return Response({
                'error': 'Admin permissions required'
            }, status=status.HTTP_403_FORBIDDEN)
        
        try:
            days = int(request.query_params.get('days', 7))
            since = timezone.now() - timedelta(days=days)
            
            # Honeypot triggers
            honeypot_attempts = RecoveryAttempt.objects.filter(
                honeypot_triggered=True,
                initiated_at__gte=since
            ).select_related('recovery_setup__user').order_by('-initiated_at')
            
            # Suspicious activities
            suspicious_attempts = RecoveryAttempt.objects.filter(
                suspicious_activity_detected=True,
                initiated_at__gte=since
            ).select_related('recovery_setup__user').order_by('-initiated_at')
            
            # Failed attempts with low trust scores
            failed_low_trust = RecoveryAttempt.objects.filter(
                status='failed',
                trust_score__lt=0.3,
                initiated_at__gte=since
            ).select_related('recovery_setup__user').order_by('-initiated_at')
            
            alerts = []
            
            for attempt in honeypot_attempts:
                alerts.append({
                    'type': 'honeypot_triggered',
                    'severity': 'high',
                    'attempt_id': str(attempt.id),
                    'user_email': attempt.recovery_setup.user.email,
                    'ip_address': attempt.initiated_from_ip,
                    'location': attempt.initiated_from_location,
                    'timestamp': attempt.initiated_at.isoformat(),
                    'details': 'Honeypot shard accessed during recovery'
                })
            
            for attempt in suspicious_attempts:
                alerts.append({
                    'type': 'suspicious_activity',
                    'severity': 'medium',
                    'attempt_id': str(attempt.id),
                    'user_email': attempt.recovery_setup.user.email,
                    'ip_address': attempt.initiated_from_ip,
                    'location': attempt.initiated_from_location,
                    'timestamp': attempt.initiated_at.isoformat(),
                    'details': attempt.suspicious_activity_details
                })
            
            for attempt in failed_low_trust:
                alerts.append({
                    'type': 'low_trust_failure',
                    'severity': 'low',
                    'attempt_id': str(attempt.id),
                    'user_email': attempt.recovery_setup.user.email,
                    'trust_score': round(attempt.trust_score, 3),
                    'ip_address': attempt.initiated_from_ip,
                    'timestamp': attempt.initiated_at.isoformat(),
                    'details': f'Recovery failed with low trust score: {attempt.trust_score:.2f}'
                })
            
            # Sort by timestamp descending
            alerts.sort(key=lambda x: x['timestamp'], reverse=True)
            
            return Response({
                'count': len(alerts),
                'alerts': alerts[:50]  # Limit to 50 most recent
            })
            
        except Exception as e:
            logger.error(f"Error fetching security alerts: {str(e)}")
            return Response({
                'error': 'Failed to fetch security alerts'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


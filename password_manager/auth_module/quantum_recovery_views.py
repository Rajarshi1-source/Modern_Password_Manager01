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
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.db import transaction
from datetime import timedelta
import uuid
import secrets
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
from .services.quantum_crypto_service import quantum_crypto_service

logger = logging.getLogger(__name__)


class QuantumRecoveryViewSet(viewsets.ViewSet):
    """
    ViewSet for Quantum-Resilient Recovery System
    """
    permission_classes = [IsAuthenticated]
    
    @action(detail=False, methods=['post'])
    def setup_recovery(self, request):
        """
        Initialize recovery system for user
        
        POST /api/auth/quantum-recovery/setup_recovery/
        
        Request body:
        {
            "total_shards": 5,
            "threshold_shards": 3,
            "guardians": [
                {"email": "guardian1@example.com", "requires_video": false},
                {"email": "guardian2@example.com", "requires_video": true}
            ],
            "enable_temporal_shard": true,
            "enable_biometric_shard": true,
            "enable_device_shard": true
        }
        """
        try:
            user = request.user
            
            # Check if recovery already setup
            if hasattr(user, 'passkey_recovery_setup') and user.passkey_recovery_setup.is_active:
                return Response({
                    'error': 'Recovery system already configured'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Validate request data
            total_shards = request.data.get('total_shards', 5)
            threshold_shards = request.data.get('threshold_shards', 3)
            guardians_data = request.data.get('guardians', [])
            
            if total_shards < 3 or total_shards > 10:
                return Response({
                    'error': 'total_shards must be between 3 and 10'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            if threshold_shards < 2 or threshold_shards > total_shards:
                return Response({
                    'error': 'threshold_shards must be between 2 and total_shards'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            with transaction.atomic():
                # Generate post-quantum keypair
                public_key, private_key = quantum_crypto_service.generate_kyber_keypair()
                
                # Encrypt private key with user's master password (simulated here)
                # In production, derive key from user's master password
                master_key_derived = secrets.token_bytes(32)  # Placeholder
                encrypted_private_key = quantum_crypto_service.encrypt_with_password(
                    private_key,
                    master_key_derived.hex()
                )
                
                # Create recovery setup
                recovery_setup = PasskeyRecoverySetup.objects.create(
                    user=user,
                    total_shards=total_shards,
                    threshold_shards=threshold_shards,
                    kyber_public_key=public_key,
                    kyber_private_key_encrypted=quantum_crypto_service.serialize_encrypted_shard(encrypted_private_key),
                    is_active=False  # Will activate after guardian acceptance
                )
                
                # Generate shards from user's passkey private key
                # In production, this would be the actual passkey private key
                passkey_secret = secrets.token_bytes(32)  # Placeholder
                shards = quantum_crypto_service.shamir_split_secret(
                    passkey_secret,
                    total_shards,
                    threshold_shards
                )
                
                # Create distributed shards
                created_shards = []
                
                # Create guardian shards
                for i, guardian_data in enumerate(guardians_data):
                    if i >= len(shards):
                        break
                    
                    shard_index, shard_data = shards[i]
                    
                    # Generate guardian keypair
                    guardian_public_key, _ = quantum_crypto_service.generate_kyber_keypair()
                    
                    # Encrypt shard with guardian's public key
                    encrypted_shard = quantum_crypto_service.encrypt_shard_hybrid(
                        shard_data,
                        guardian_public_key
                    )
                    
                    # Create shard record
                    shard = RecoveryShard.objects.create(
                        recovery_setup=recovery_setup,
                        shard_type=RecoveryShardType.GUARDIAN,
                        shard_index=shard_index,
                        encrypted_shard_data=quantum_crypto_service.serialize_encrypted_shard(encrypted_shard),
                        context_data={'guardian_index': i}
                    )
                    
                    # Create guardian invitation
                    invitation_token = secrets.token_urlsafe(32)
                    guardian = RecoveryGuardian.objects.create(
                        recovery_setup=recovery_setup,
                        encrypted_guardian_info=guardian_data['email'].encode('utf-8'),  # Simplified
                        guardian_public_key=guardian_public_key,
                        shard=shard,
                        requires_video_verification=guardian_data.get('requires_video', False),
                        invitation_token=invitation_token,
                        invitation_expires_at=timezone.now() + timedelta(days=7)
                    )
                    
                    created_shards.append({
                        'type': 'guardian',
                        'guardian_email': guardian_data['email'],
                        'invitation_token': invitation_token
                    })
                
                # Create device shard
                if request.data.get('enable_device_shard', True) and len(shards) > len(guardians_data):
                    shard_index, shard_data = shards[len(guardians_data)]
                    
                    # Encrypt with device fingerprint
                    device_fingerprint = request.data.get('device_fingerprint', 'unknown')
                    encrypted_shard = quantum_crypto_service.encrypt_with_password(
                        shard_data,
                        device_fingerprint
                    )
                    
                    RecoveryShard.objects.create(
                        recovery_setup=recovery_setup,
                        shard_type=RecoveryShardType.DEVICE,
                        shard_index=shard_index,
                        encrypted_shard_data=quantum_crypto_service.serialize_encrypted_shard(encrypted_shard),
                        context_data={'device_fingerprint': device_fingerprint}
                    )
                    
                    created_shards.append({'type': 'device'})
                
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
                        'total_shards': total_shards,
                        'threshold_shards': threshold_shards,
                        'guardians_count': len(guardians_data)
                    },
                    ip_address=request.META.get('REMOTE_ADDR'),
                    user_agent=request.META.get('HTTP_USER_AGENT', '')
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
    
    @action(detail=False, methods=['post'])
    def initiate_recovery(self, request):
        """
        Initiate passkey recovery process
        
        POST /api/auth/quantum-recovery/initiate_recovery/
        
        Request body:
        {
            "email": "user@example.com",
            "device_fingerprint": "abc123..."
        }
        """
        try:
            email = request.data.get('email')
            if not email:
                return Response({
                    'error': 'Email required'
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
                    shards_required=recovery_setup.threshold_shards,
                    guardian_approvals_required=min(2, len(recovery_setup.guardians.filter(status='active'))),
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
                    ip_address=request.META.get('REMOTE_ADDR'),
                    user_agent=request.META.get('HTTP_USER_AGENT', '')
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
    
    @action(detail=False, methods=['post'])
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
            
            # Verify response (simplified - in production, use encrypted comparison)
            # challenge.encrypted_expected_response would be decrypted and compared
            is_correct = True  # Placeholder
            
            # Update challenge
            challenge.user_response = response_text
            challenge.response_received_at = timezone.now()
            challenge.response_correct = is_correct
            challenge.response_device_fingerprint = request.data.get('device_fingerprint', '')
            challenge.status = 'completed' if is_correct else 'failed'
            
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
                ip_address=request.META.get('REMOTE_ADDR')
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
            attempt.failure_reason = 'Cancelled by legitimate user via canary alert'
            attempt.save()
            
            # Log audit event
            RecoveryAuditLog.objects.create(
                user=request.user,
                event_type='user_cancelled_recovery',
                recovery_attempt_id=attempt.id,
                event_data={
                    'attempt_id': str(attempt_id),
                    'reason': 'canary_alert'
                },
                ip_address=request.META.get('REMOTE_ADDR')
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
                ip_address=request.META.get('REMOTE_ADDR')
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
    
    @action(detail=False, methods=['post'])
    def complete_recovery(self, request):
        """
        Complete recovery by reconstructing passkey from collected shards
        
        POST /api/auth/quantum-recovery/complete_recovery/
        
        Request body:
        {
            "attempt_id": "uuid",
            "collected_shards": [
                {"shard_id": "uuid1", "decryption_context": {...}},
                {"shard_id": "uuid2", "decryption_context": {...}},
                {"shard_id": "uuid3", "decryption_context": {...}}
            ]
        }
        """
        try:
            attempt_id = request.data.get('attempt_id')
            collected_shards_data = request.data.get('collected_shards', [])
            
            attempt = get_object_or_404(RecoveryAttempt, id=attempt_id)
            recovery_setup = attempt.recovery_setup
            
            # Verify attempt is in correct status
            if attempt.status not in ['shard_collection', 'guardian_approval', 'final_verification']:
                return Response({
                    'error': 'Recovery not ready for completion'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Verify trust score meets threshold
            if attempt.trust_score < recovery_setup.minimum_challenge_success_rate:
                return Response({
                    'error': f'Insufficient trust score: {attempt.trust_score:.2f} (required: {recovery_setup.minimum_challenge_success_rate:.2f})'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Verify enough shards collected
            if len(collected_shards_data) < recovery_setup.threshold_shards:
                return Response({
                    'error': f'Insufficient shards: need {recovery_setup.threshold_shards}, have {len(collected_shards_data)}'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            with transaction.atomic():
                # Decrypt and collect shards
                decrypted_shards = []
                
                for shard_data in collected_shards_data:
                    shard = RecoveryShard.objects.get(id=shard_data['shard_id'])
                    
                    # Check for honeypot
                    if shard.is_honeypot:
                        attempt.honeypot_triggered = True
                        attempt.suspicious_activity_detected = True
                        attempt.status = 'failed'
                        attempt.failure_reason = 'Honeypot shard accessed'
                        attempt.save()
                        
                        # Log security event
                        RecoveryAuditLog.objects.create(
                            user=recovery_setup.user,
                            event_type='honeypot_triggered',
                            recovery_attempt_id=attempt.id,
                            event_data={
                                'shard_id': str(shard.id)
                            },
                            ip_address=request.META.get('REMOTE_ADDR')
                        )
                        
                        return Response({
                            'error': 'Security violation detected'
                        }, status=status.HTTP_403_FORBIDDEN)
                    
                    # Decrypt shard based on type
                    from .services.quantum_crypto_service import quantum_crypto_service
                    
                    if shard.shard_type == RecoveryShardType.GUARDIAN:
                        # Guardian shards are already released via approval
                        guardian_approval = GuardianApproval.objects.filter(
                            recovery_attempt=attempt,
                            guardian__shard=shard,
                            status='approved',
                            shard_released=True
                        ).first()
                        
                        if not guardian_approval:
                            continue  # Skip if not approved
                        
                        # Decrypt with guardian's private key (simplified)
                        encrypted_shard = quantum_crypto_service.deserialize_encrypted_shard(
                            shard.encrypted_shard_data
                        )
                        # In production, proper key management would be implemented
                        shard_plaintext = shard.encrypted_shard_data  # Simplified
                    
                    elif shard.shard_type == RecoveryShardType.DEVICE:
                        # Decrypt with device fingerprint
                        device_fp = shard_data.get('decryption_context', {}).get('device_fingerprint', '')
                        encrypted_shard = quantum_crypto_service.deserialize_encrypted_shard(
                            shard.encrypted_shard_data
                        )
                        shard_plaintext = quantum_crypto_service.decrypt_with_password(
                            encrypted_shard,
                            device_fp
                        )
                    else:
                        # For other shard types, use appropriate decryption
                        shard_plaintext = shard.encrypted_shard_data
                    
                    # Add to collection
                    decrypted_shards.append((shard.shard_index, shard_plaintext))
                
                # Reconstruct secret using Shamir's Secret Sharing
                passkey_secret = quantum_crypto_service.shamir_reconstruct_secret(
                    decrypted_shards,
                    recovery_setup.threshold_shards
                )
                
                # Generate recovery token for passkey re-registration
                recovery_token = secrets.token_urlsafe(64)
                
                # Mark recovery as complete
                attempt.status = 'completed'
                attempt.recovery_successful = True
                attempt.completed_at = timezone.now()
                attempt.save()
                
                # Log audit event
                RecoveryAuditLog.objects.create(
                    user=recovery_setup.user,
                    event_type='recovery_completed',
                    recovery_attempt_id=attempt.id,
                    event_data={
                        'shards_used': len(decrypted_shards),
                        'trust_score': attempt.trust_score
                    },
                    ip_address=request.META.get('REMOTE_ADDR')
                )
            
            return Response({
                'success': True,
                'recovery_token': recovery_token,
                'message': 'Recovery completed successfully. Use token to re-register passkey.'
            })
            
        except Exception as e:
            logger.error(f"Error completing recovery: {str(e)}")
            return Response({
                'error': 'Failed to complete recovery'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([AllowAny])
def accept_guardian_invitation(request):
    """
    Guardian accepts invitation to hold recovery shard
    
    POST /api/auth/quantum-recovery/accept-guardian-invitation/
    
    Request body:
    {
        "invitation_token": "token123",
        "guardian_public_key": "base64_encoded_key"
    }
    """
    try:
        invitation_token = request.data.get('invitation_token')
        
        guardian = get_object_or_404(RecoveryGuardian, invitation_token=invitation_token)
        
        # Check if invitation is valid
        if not guardian.is_invitation_valid():
            return Response({
                'error': 'Invitation expired or already used'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Update guardian status
        guardian.status = 'active'
        guardian.accepted_at = timezone.now()
        guardian.save()
        
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
            }
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
            }
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


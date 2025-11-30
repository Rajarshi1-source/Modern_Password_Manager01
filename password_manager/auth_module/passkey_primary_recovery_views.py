"""
Primary Passkey Recovery API Views
Provides endpoints for immediate passkey recovery with automatic fallback to social mesh recovery
"""

from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework import status
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone
import logging
import json

from .passkey_primary_recovery_models import (
    PasskeyRecoveryBackup,
    PasskeyRecoveryAttempt,
    RecoveryKeyRevocation
)
from .services.passkey_primary_recovery_service import PasskeyPrimaryRecoveryService
from .models import UserPasskey
from .recovery_throttling import (
    RecoveryThrottle,
    RecoveryInitiateThrottle,
    RecoveryCompleteThrottle,
    progressive_lockout
)
from .recovery_monitoring import metrics_collector

User = get_user_model()
logger = logging.getLogger(__name__)
recovery_service = PasskeyPrimaryRecoveryService()


def _get_client_ip(request):
    """Extract client IP from request."""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def setup_primary_passkey_recovery(request):
    """
    Set up primary passkey recovery for a specific passkey credential.
    Creates an encrypted backup and returns a recovery key.
    
    Request body:
        - passkey_credential_id: ID of the passkey to back up
        - device_name: Optional name for the device
    
    Response:
        - recovery_key: One-time display of recovery key (24 chars)
        - backup_id: ID of created backup
    """
    user = request.user
    passkey_credential_id = request.data.get('passkey_credential_id')
    device_name = request.data.get('device_name', '')
    
    if not passkey_credential_id:
        return Response(
            {"error": "passkey_credential_id is required"},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        # Find the passkey
        try:
            passkey = UserPasskey.objects.get(
                user=user,
                credential_id=bytes.fromhex(passkey_credential_id)
            )
        except UserPasskey.DoesNotExist:
            return Response(
                {"error": "Passkey not found"},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Check if backup already exists
        existing_backup = PasskeyRecoveryBackup.objects.filter(
            user=user,
            passkey_credential_id=passkey.credential_id,
            is_active=True
        ).first()
        
        if existing_backup:
            return Response(
                {"error": "Active backup already exists for this passkey. Please revoke it first."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        with transaction.atomic():
            # Generate recovery key
            recovery_key = recovery_service.generate_recovery_key()
            recovery_key_hash = recovery_service.hash_recovery_key(recovery_key)
            
            # Prepare credential data to encrypt
            credential_data = {
                'credential_id': passkey.credential_id.hex(),
                'public_key': passkey.public_key.hex(),
                'rp_id': passkey.rp_id,
                'device_type': passkey.device_type or 'unknown',
                'created_at': passkey.created_at.isoformat(),
                'user_id': user.id,
                'username': user.username,
            }
            
            # Generate Kyber keypair
            kyber_public_key, _ = recovery_service.quantum_crypto.generate_kyber_keypair()
            
            # Encrypt credential data
            encrypted_data, encryption_metadata = recovery_service.encrypt_passkey_credential(
                credential_data=credential_data,
                recovery_key=recovery_key,
                user_kyber_public_key=kyber_public_key
            )
            
            # Create backup record
            backup = PasskeyRecoveryBackup.objects.create(
                user=user,
                passkey_credential_id=passkey.credential_id,
                encrypted_credential_data=encrypted_data,
                recovery_key_hash=recovery_key_hash,
                kyber_public_key=kyber_public_key,
                encryption_metadata=encryption_metadata,
                device_name=device_name,
                is_active=True
            )
            
            logger.info(f"Primary passkey recovery backup created for user {user.username}, backup ID: {backup.id}")
            
            return Response({
                "message": "Primary passkey recovery set up successfully",
                "recovery_key": recovery_key,  # ONLY shown once!
                "backup_id": backup.id,
                "device_name": device_name,
                "created_at": backup.created_at.isoformat(),
                "warning": "Save this recovery key in a secure location. It will NOT be shown again!"
            }, status=status.HTTP_201_CREATED)
    
    except Exception as e:
        logger.error(f"Error setting up primary passkey recovery for user {user.username}: {e}", exc_info=True)
        return Response(
            {"error": "Failed to set up recovery. Please try again."},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def list_passkey_recovery_backups(request):
    """
    List all active recovery backups for the current user.
    
    Response:
        - backups: List of backup objects (without sensitive data)
    """
    user = request.user
    
    backups = PasskeyRecoveryBackup.objects.filter(
        user=user,
        is_active=True
    ).order_by('-created_at')
    
    backup_list = []
    for backup in backups:
        backup_list.append({
            'id': backup.id,
            'device_name': backup.device_name,
            'created_at': backup.created_at.isoformat(),
            'last_verified_at': backup.last_verified_at.isoformat() if backup.last_verified_at else None,
            'passkey_credential_id': backup.passkey_credential_id.hex(),
        })
    
    return Response({
        "backups": backup_list,
        "count": len(backup_list)
    }, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([AllowAny])  # Allow unauthenticated for password-less recovery
@throttle_classes([RecoveryInitiateThrottle])
def initiate_primary_passkey_recovery(request):
    """
    Initiate primary passkey recovery using recovery key.
    Step 1: User provides email/username to identify account.
    
    Request body:
        - username_or_email: User's username or email
    
    Response:
        - message: Instructions for next step
        - has_backups: Whether user has active backups
        - backup_count: Number of active backups
    """
    username_or_email = request.data.get('username_or_email')
    
    if not username_or_email:
        return Response(
            {"error": "username_or_email is required"},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        # Find user
        user = User.objects.filter(username=username_or_email).first() or \
               User.objects.filter(email=username_or_email).first()
        
        if not user:
            # Don't reveal if user exists
            logger.warning(f"Recovery initiated for non-existent user: {username_or_email}")
            return Response({
                "message": "If an account exists, you will be prompted for your recovery key.",
                "has_backups": False,
                "backup_count": 0
            }, status=status.HTTP_200_OK)
        
        # Check for active backups
        active_backups = PasskeyRecoveryBackup.objects.filter(
            user=user,
            is_active=True
        )
        
        if not active_backups.exists():
            return Response({
                "message": "No active recovery backups found. Consider social mesh recovery.",
                "has_backups": False,
                "backup_count": 0,
                "fallback_available": True,
                "user_id": user.id  # Needed for fallback
            }, status=status.HTTP_200_OK)
        
        # Create recovery attempt
        ip_address = _get_client_ip(request)
        user_agent = request.META.get('HTTP_USER_AGENT', '')
        
        recovery_attempt = PasskeyRecoveryAttempt.objects.create(
            user=user,
            status='initiated',
            ip_address=ip_address,
            user_agent=user_agent
        )
        
        logger.info(f"Primary passkey recovery initiated for user {user.username}, attempt ID: {recovery_attempt.id}")
        
        return Response({
            "message": "Active backups found. Please provide your recovery key.",
            "has_backups": True,
            "backup_count": active_backups.count(),
            "recovery_attempt_id": recovery_attempt.id,
            "user_id": user.id
        }, status=status.HTTP_200_OK)
    
    except Exception as e:
        logger.error(f"Error initiating primary passkey recovery: {e}", exc_info=True)
        return Response(
            {"error": "An error occurred. Please try again."},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([RecoveryCompleteThrottle])
def complete_primary_passkey_recovery(request):
    """
    Complete primary passkey recovery using recovery key.
    Step 2: User provides recovery key, system decrypts backup.
    
    Request body:
        - recovery_attempt_id: ID from initiate step
        - recovery_key: User's recovery key
        - user_id: User ID from initiate step
    
    Response:
        - passkey_credential: Decrypted passkey credential data
        - message: Success message
    """
    # Check progressive lockout first
    if not progressive_lockout.allow_request(request, None):
        wait_time = getattr(progressive_lockout, 'wait', 0)
        return Response({
            "error": "Too many failed attempts. Please try again later.",
            "retry_after": wait_time
        }, status=status.HTTP_429_TOO_MANY_REQUESTS)
    
    start_time = timezone.now()
    
    recovery_attempt_id = request.data.get('recovery_attempt_id')
    recovery_key = request.data.get('recovery_key')
    user_id = request.data.get('user_id')
    
    if not all([recovery_attempt_id, recovery_key, user_id]):
        return Response(
            {"error": "recovery_attempt_id, recovery_key, and user_id are required"},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        # Find recovery attempt
        try:
            recovery_attempt = PasskeyRecoveryAttempt.objects.get(
                id=recovery_attempt_id,
                user_id=user_id,
                status='initiated'
            )
        except PasskeyRecoveryAttempt.DoesNotExist:
            return Response(
                {"error": "Recovery attempt not found or already processed"},
                status=status.HTTP_404_NOT_FOUND
            )
        
        user = recovery_attempt.user
        
        # Find matching backup by verifying recovery key
        matching_backup = None
        for backup in PasskeyRecoveryBackup.objects.filter(user=user, is_active=True):
            if backup.verify_recovery_key(recovery_key):
                matching_backup = backup
                break
        
        if not matching_backup:
            recovery_attempt.status = 'key_invalid'
            recovery_attempt.failed_at = timezone.now()
            recovery_attempt.failure_reason = 'Invalid recovery key provided'
            recovery_attempt.save()
            
            # Record failure metrics and progressive lockout
            progressive_lockout.record_failure(request, 'invalid_key')
            metrics_collector.record_key_verification(
                user_id=user.id,
                success=False,
                ip_address=_get_client_ip(request)
            )
            
            logger.warning(f"Invalid recovery key for user {user.username}, attempt ID: {recovery_attempt.id}")
            
            return Response({
                "error": "Invalid recovery key",
                "fallback_available": True,
                "message": "Recovery key did not match. Would you like to try social mesh recovery?"
            }, status=status.HTTP_401_UNAUTHORIZED)
        
        # Update recovery attempt
        recovery_attempt.status = 'key_verified'
        recovery_attempt.backup = matching_backup
        recovery_attempt.save()
        
        # Decrypt credential data
        try:
            decrypted_credential = recovery_service.decrypt_passkey_credential(
                encrypted_data=matching_backup.encrypted_credential_data,
                recovery_key=recovery_key,
                encryption_metadata=matching_backup.encryption_metadata
            )
            
            recovery_attempt.status = 'decryption_success'
            recovery_attempt.save()
            
        except Exception as decrypt_error:
            recovery_attempt.status = 'decryption_failed'
            recovery_attempt.failed_at = timezone.now()
            recovery_attempt.failure_reason = str(decrypt_error)
            recovery_attempt.save()
            
            logger.error(f"Decryption failed for user {user.username}: {decrypt_error}", exc_info=True)
            
            return Response({
                "error": "Decryption failed",
                "fallback_available": True,
                "message": "Could not decrypt backup. Would you like to try social mesh recovery?"
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        # Mark recovery as complete
        recovery_attempt.mark_complete()
        
        # Update backup last verified
        matching_backup.last_verified_at = timezone.now()
        matching_backup.save()
        
        # Record success metrics
        duration = (timezone.now() - start_time).total_seconds()
        progressive_lockout.record_success(request)
        metrics_collector.record_key_verification(
            user_id=user.id,
            success=True,
            ip_address=_get_client_ip(request)
        )
        metrics_collector.record_recovery_attempt(
            user_id=user.id,
            attempt_type='primary',
            status='completed',
            duration_seconds=duration
        )
        
        logger.info(f"Primary passkey recovery completed for user {user.username}, attempt ID: {recovery_attempt.id}")
        
        return Response({
            "message": "Passkey recovered successfully!",
            "passkey_credential": decrypted_credential,
            "device_name": matching_backup.device_name,
            "backup_verified": True
        }, status=status.HTTP_200_OK)
    
    except Exception as e:
        logger.error(f"Error completing primary passkey recovery: {e}", exc_info=True)
        return Response(
            {"error": "An error occurred during recovery. Please try again."},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([AllowAny])
def fallback_to_social_mesh_recovery(request):
    """
    Fallback to social mesh recovery if primary recovery fails.
    Links the failed primary attempt to a new social mesh recovery attempt.
    
    Request body:
        - primary_recovery_attempt_id: ID of failed primary recovery attempt
        - user_id: User ID
    
    Response:
        - social_mesh_recovery_attempt_id: ID of new social mesh recovery attempt
        - message: Instructions for social mesh recovery
    """
    primary_attempt_id = request.data.get('primary_recovery_attempt_id')
    user_id = request.data.get('user_id')
    
    if not all([primary_attempt_id, user_id]):
        return Response(
            {"error": "primary_recovery_attempt_id and user_id are required"},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        # Find primary recovery attempt
        try:
            primary_attempt = PasskeyRecoveryAttempt.objects.get(
                id=primary_attempt_id,
                user_id=user_id
            )
        except PasskeyRecoveryAttempt.DoesNotExist:
            return Response(
                {"error": "Primary recovery attempt not found"},
                status=status.HTTP_404_NOT_FOUND
            )
        
        user = primary_attempt.user
        
        # Check if social mesh recovery is set up
        from .quantum_recovery_models import RecoveryTrustShard
        
        active_shards = RecoveryTrustShard.objects.filter(
            user=user,
            is_active=True
        )
        
        if not active_shards.exists():
            return Response({
                "error": "No social mesh recovery set up",
                "message": "You need to set up guardian-based recovery first.",
                "setup_url": "/recovery/setup"
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Import the social mesh recovery initiation view
        from .quantum_recovery_views import initiate_passkey_recovery as initiate_social_mesh
        
        # Create a mock request for social mesh recovery
        # In a real implementation, you'd call the function directly with proper parameters
        
        # For now, just mark primary attempt as fallback initiated
        primary_attempt.initiate_fallback()
        
        logger.info(f"Fallback to social mesh recovery initiated for user {user.username}")
        
        return Response({
            "message": "Fallback to social mesh recovery initiated",
            "instructions": "Temporal challenges will be sent to your guardians. They need to verify their identity to help you recover.",
            "threshold": active_shards.first().threshold,
            "total_guardians": active_shards.count(),
            "estimated_time": "3-7 days",
            "primary_attempt_id": primary_attempt_id,
            "social_mesh_setup": True
        }, status=status.HTTP_200_OK)
    
    except Exception as e:
        logger.error(f"Error initiating fallback to social mesh recovery: {e}", exc_info=True)
        return Response(
            {"error": "Failed to initiate fallback recovery"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def revoke_recovery_backup(request, backup_id):
    """
    Revoke a recovery backup (e.g., if user suspects compromise).
    
    Request body:
        - reason: Optional reason for revocation
        - create_new: Whether to create a new backup immediately
    """
    user = request.user
    reason = request.data.get('reason', '')
    create_new = request.data.get('create_new', False)
    
    try:
        backup = PasskeyRecoveryBackup.objects.get(
            id=backup_id,
            user=user,
            is_active=True
        )
        
        with transaction.atomic():
            # Deactivate backup
            backup.is_active = False
            backup.save()
            
            # Create revocation record
            revocation = RecoveryKeyRevocation.objects.create(
                backup=backup,
                revoked_by=user,
                reason=reason,
                new_backup_created=create_new
            )
            
            logger.info(f"Recovery backup {backup_id} revoked by user {user.username}")
            
            response_data = {
                "message": "Recovery backup revoked successfully",
                "backup_id": backup_id,
                "revoked_at": revocation.revoked_at.isoformat()
            }
            
            if create_new:
                response_data["message"] += " You can now create a new backup."
            
            return Response(response_data, status=status.HTTP_200_OK)
    
    except PasskeyRecoveryBackup.DoesNotExist:
        return Response(
            {"error": "Backup not found or already revoked"},
            status=status.HTTP_404_NOT_FOUND
        )
    except Exception as e:
        logger.error(f"Error revoking recovery backup {backup_id}: {e}", exc_info=True)
        return Response(
            {"error": "Failed to revoke backup"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_recovery_status(request):
    """
    Get overall recovery status for the user.
    Shows both primary and social mesh recovery setup status.
    
    Response:
        - primary_recovery: Status of primary recovery
        - social_mesh_recovery: Status of social mesh recovery
        - recommendations: Suggestions for improving recovery options
    """
    user = request.user
    
    try:
        # Check primary recovery
        active_backups = PasskeyRecoveryBackup.objects.filter(
            user=user,
            is_active=True
        ).count()
        
        # Check social mesh recovery
        from .quantum_recovery_models import RecoveryTrustShard, RecoveryGuardian
        
        active_shards = RecoveryTrustShard.objects.filter(
            user=user,
            is_active=True
        ).count()
        
        accepted_guardians = RecoveryGuardian.objects.filter(
            user=user,
            status='accepted'
        ).count()
        
        # Generate recommendations
        recommendations = []
        if active_backups == 0:
            recommendations.append({
                "type": "primary_recovery",
                "message": "Set up primary passkey recovery for faster account recovery",
                "action": "setup_primary_recovery",
                "priority": "high"
            })
        
        if active_shards == 0:
            recommendations.append({
                "type": "social_mesh_recovery",
                "message": "Set up guardian-based recovery as a backup option",
                "action": "setup_social_mesh_recovery",
                "priority": "medium"
            })
        
        return Response({
            "primary_recovery": {
                "enabled": active_backups > 0,
                "backup_count": active_backups,
                "status": "active" if active_backups > 0 else "not_configured"
            },
            "social_mesh_recovery": {
                "enabled": active_shards > 0,
                "guardian_count": accepted_guardians,
                "shard_count": active_shards,
                "status": "active" if active_shards > 0 else "not_configured"
            },
            "recommendations": recommendations,
            "overall_status": "secure" if (active_backups > 0 or active_shards > 0) else "at_risk"
        }, status=status.HTTP_200_OK)
    
    except Exception as e:
        logger.error(f"Error getting recovery status for user {user.username}: {e}", exc_info=True)
        return Response(
            {"error": "Failed to get recovery status"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


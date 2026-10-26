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
from datetime import timedelta
import base64
import logging
import json
import os
import struct

from cryptography.fernet import Fernet, InvalidToken
from django.utils.crypto import salted_hmac

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
from password_manager.throttling import PasskeyThrottle
from shared.client_ip import get_client_ip
from shared.log_safe import log_safe

User = get_user_model()
logger = logging.getLogger(__name__)
recovery_service = PasskeyPrimaryRecoveryService()


_get_client_ip = get_client_ip

# initiate answers every lookup the same way (OWASP Forgot Password): an
# unknown account, an account without backups and one with backups all get a
# recovery_attempt_id. It is an encrypted (user id, nonce) pair, so a decoy
# (user id 0) is indistinguishable from a real one, and complete/fallback need
# nothing else: no user_id is handed out before the recovery key is proven.
# initiate writes nothing on either path (no timing difference); complete
# creates the attempt row on the token's first use, keyed by its nonce.
ATTEMPT_TOKEN_TTL_SECONDS = 3600
INITIATE_MESSAGE = "If this account has a recovery backup, enter your recovery key to continue."
INVALID_KEY_RESPONSE = {
    "error": "Invalid recovery key",
    "fallback_available": True,
    "message": "Recovery key did not match. Would you like to try social mesh recovery?"
}
FALLBACK_RESPONSE = {
    "message": "If guardian recovery is set up for this account, it has been started.",
    "instructions": "If guardian recovery is set up, temporal challenges will be sent to your guardians. "
                    "They need to verify their identity to help you recover.",
    "estimated_time": "3-7 days"
}


# After a successful recovery the session holds a grant to register one new
# passkey for the recovered account; the registration ceremony itself keeps
# its fido2 state under its own key, as the signed-in registration does.
RECOVERY_REGISTRATION_TTL_SECONDS = 900
RECOVERY_REGISTRATION_GRANT_KEY = 'passkey_recovery_grant'
RECOVERY_REGISTRATION_STATE_KEY = 'passkey_recovery_registration'
RECOVERY_GRANT_INVALID = "Recovery registration expired or invalid. Start recovery again."


def _revoke_lost_passkey(user, credential_id):
    """Delete the lost passkey and deactivate any other backup of it."""
    UserPasskey.objects.filter(user=user, credential_id=credential_id).delete()
    for backup in PasskeyRecoveryBackup.objects.filter(user=user, is_active=True):
        if bytes(backup.passkey_credential_id) == credential_id:
            backup.is_active = False
            backup.save(update_fields=['is_active', 'updated_at'])
            RecoveryKeyRevocation.objects.create(
                backup=backup,
                revoked_by=user,
                reason='Its passkey was revoked by a recovery'
            )


def _recovery_grant_user(request):
    """The account this session may register a recovery passkey for, or None."""
    grant = request.session.get(RECOVERY_REGISTRATION_GRANT_KEY)
    if not isinstance(grant, dict) or grant.get('expires_at', 0) < timezone.now().timestamp():
        return None
    return User.objects.filter(pk=grant.get('user_id'), is_active=True).first()


def _begin_recovery_registration(request, user):
    """Start a WebAuthn registration for ``user``; returns the creation options."""
    from fido2.webauthn import (
        PublicKeyCredentialUserEntity,
        ResidentKeyRequirement,
        UserVerificationRequirement,
    )
    from .passkey_views import AUTHENTICATOR_ATTACHMENT, _descriptor, server

    options, state = server.register_begin(
        user=PublicKeyCredentialUserEntity(
            id=str(user.id).encode(),
            name=user.username,
            display_name=user.email or user.username,
        ),
        credentials=[
            _descriptor(bytes(cid)) for cid in
            UserPasskey.objects.filter(user=user).values_list('credential_id', flat=True)
        ],
        resident_key_requirement=ResidentKeyRequirement.REQUIRED,
        # The recovery key was the first factor; the new passkey must be
        # user-verified so it is a full sign-in factor on its own.
        user_verification=UserVerificationRequirement.REQUIRED,
        authenticator_attachment=AUTHENTICATOR_ATTACHMENT,
    )
    request.session[RECOVERY_REGISTRATION_STATE_KEY] = {'state': state, 'user_id': user.id}
    return dict(options.public_key)


def _attempt_fernet():
    key = salted_hmac('passkey-primary-recovery-attempt', 'fernet-key', algorithm='sha256').digest()
    return Fernet(base64.urlsafe_b64encode(key))


def _attempt_token(user_id):
    payload = struct.pack('>Q', user_id) + os.urandom(16)
    return _attempt_fernet().encrypt(payload).decode('ascii')


def _token_payload(token):
    """(user id, nonce hex) in ``token``; user id 0 is a decoy. None if invalid or expired."""
    try:
        raw = _attempt_fernet().decrypt(str(token).encode('ascii'), ttl=ATTEMPT_TOKEN_TTL_SECONDS)
        if len(raw) != 24:
            return None
        return struct.unpack('>Q', raw[:8])[0], raw[8:].hex()
    except (InvalidToken, UnicodeEncodeError, struct.error, TypeError, ValueError):
        return None


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
        credential_id = bytes.fromhex(passkey_credential_id)
    except (TypeError, ValueError):
        return Response(
            {"error": "passkey_credential_id must be hex"},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        # Find the passkey
        try:
            passkey = UserPasskey.objects.get(
                user=user,
                credential_id=credential_id
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
            
            # Encrypt credential data (generates the backup's Kyber keypair and
            # keeps its private key wrapped under the recovery key)
            encrypted_data, encryption_metadata = recovery_service.encrypt_passkey_credential(
                credential_data=credential_data,
                recovery_key=recovery_key,
            )
            kyber_public_key = base64.b64decode(encryption_metadata['kyber_public_key'])
            
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
            
            logger.info(log_safe(f"Primary passkey recovery backup created for user {user.username}, backup ID: {backup.id}"))
            
            return Response({
                "message": "Primary passkey recovery set up successfully",
                "recovery_key": recovery_key,  # ONLY shown once!
                "backup_id": backup.id,
                "device_name": device_name,
                "created_at": backup.created_at.isoformat(),
                "warning": "Save this recovery key in a secure location. It will NOT be shown again!"
            }, status=status.HTTP_201_CREATED)
    
    except Exception as e:
        logger.error(log_safe(f"Error setting up primary passkey recovery for user {user.username}: {e}"), exc_info=True)
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
    
    Response (the same for every account, existing or not):
        - message: Instructions for next step
        - recovery_attempt_id: Opaque token for complete/fallback
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
        
        # One query on every path; user id 0 never matches a backup
        has_backup = PasskeyRecoveryBackup.objects.filter(
            user_id=user.id if user else 0, is_active=True
        ).exists()
        if not user:
            logger.warning(log_safe(f"Recovery initiated for non-existent user: {username_or_email}"))

        # The same answer, and no write, whether or not the account exists
        # or has backups; the attempt row is created by complete
        return Response({
            "message": INITIATE_MESSAGE,
            "recovery_attempt_id": _attempt_token(user.id if has_backup else 0)
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
    Step 2: User provides recovery key; the backup is consumed, the lost
    passkey is revoked, and a registration of a new passkey begins.
    
    Request body:
        - recovery_attempt_id: Token from initiate step
        - recovery_key: User's recovery key
    
    Response:
        - registration_options: WebAuthn creation options for the new
          passkey; finish with passkey-recovery/register/complete/
        - message: Next step
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

    if not all([recovery_attempt_id, recovery_key]):
        return Response(
            {"error": "recovery_attempt_id and recovery_key are required"},
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        # Find recovery attempt. A decoy, used or expired attempt answers
        # exactly like a wrong key, so complete reveals neither. A wrong key
        # leaves the attempt retryable (key_invalid); progressive_lockout and
        # the completion throttle bound the retries.
        payload = _token_payload(recovery_attempt_id)
        recovery_attempt = None
        if payload and payload[0]:
            token_user_id, nonce = payload
            recovery_attempt, _ = PasskeyRecoveryAttempt.objects.get_or_create(
                token_nonce=nonce,
                defaults={
                    'user_id': token_user_id,
                    'status': 'initiated',
                    'ip_address': _get_client_ip(request),
                    'user_agent': request.META.get('HTTP_USER_AGENT', ''),
                },
            )
            if (recovery_attempt.user_id != token_user_id
                    or recovery_attempt.status not in ('initiated', 'key_invalid')):
                recovery_attempt = None
        if recovery_attempt is None:
            progressive_lockout.record_failure(request, 'invalid_key')
            return Response(INVALID_KEY_RESPONSE, status=status.HTTP_401_UNAUTHORIZED)
        
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
            
            return Response(INVALID_KEY_RESPONSE, status=status.HTTP_401_UNAUTHORIZED)
        
        # A recovery key is single-use (NIST SP 800-63B): the backup it opened
        # is consumed, and the passkey it backed up is revoked, because the
        # user reports it lost (FIDO account recovery: the lost credential
        # must stop working). The conditional update claims the backup, so of
        # two concurrent completions with the same key only one succeeds.
        #
        # The recovery restores access by registering a NEW passkey: the
        # backup holds only the lost passkey's public data, which signs
        # nobody in. The registration options are built inside the same
        # transaction, so if that fails the claim and the revocation roll
        # back and the key can be used again.
        registration_options = None
        try:
            with transaction.atomic():
                claimed = PasskeyRecoveryBackup.objects.filter(
                    pk=matching_backup.pk, is_active=True
                ).update(is_active=False, last_verified_at=timezone.now())
                if claimed:
                    recovery_attempt.backup = matching_backup
                    recovery_attempt.mark_complete()
                    RecoveryKeyRevocation.objects.create(
                        backup=matching_backup,
                        revoked_by=user,
                        reason='Consumed by a successful recovery'
                    )
                    _revoke_lost_passkey(user, bytes(matching_backup.passkey_credential_id))
                    registration_options = _begin_recovery_registration(request, user)
        except Exception:
            request.session.pop(RECOVERY_REGISTRATION_STATE_KEY, None)
            raise
        if not claimed:
            progressive_lockout.record_failure(request, 'invalid_key')
            return Response(INVALID_KEY_RESPONSE, status=status.HTTP_401_UNAUTHORIZED)

        # This session may now run one registration ceremony for this
        # account within RECOVERY_REGISTRATION_TTL_SECONDS.
        request.session[RECOVERY_REGISTRATION_GRANT_KEY] = {
            'user_id': user.id,
            'expires_at': (timezone.now() + timedelta(
                seconds=RECOVERY_REGISTRATION_TTL_SECONDS)).timestamp(),
        }

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
            "message": "Recovery key accepted. Register a new passkey to finish.",
            "registration_options": registration_options,
            "registration_expires_in": RECOVERY_REGISTRATION_TTL_SECONDS,
            "revoked_device_name": matching_backup.device_name,
        }, status=status.HTTP_200_OK)
    
    except Exception as e:
        logger.error(f"Error completing primary passkey recovery: {e}", exc_info=True)
        return Response(
            {"error": "An error occurred during recovery. Please try again."},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([PasskeyThrottle])
def begin_recovery_passkey_registration(request):
    """Start the new-passkey registration again (e.g. after the user
    cancelled the browser prompt) while this session's recovery grant is
    valid."""
    user = _recovery_grant_user(request)
    if user is None:
        return Response({"error": RECOVERY_GRANT_INVALID}, status=status.HTTP_400_BAD_REQUEST)
    try:
        return Response({
            "registration_options": _begin_recovery_registration(request, user),
        }, status=status.HTTP_200_OK)
    except Exception:
        logger.exception("Recovery passkey registration could not start")
        return Response(
            {"error": "An error occurred. Please try again."},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([PasskeyThrottle])
def complete_recovery_passkey_registration(request):
    """Finish registering the new passkey of a recovered account.

    Request body: the WebAuthn attestation response (id, rawId, type,
    response.clientDataJSON, response.attestationObject), plus an optional
    device_type label. Stores only public material, as the signed-in
    registration does, and spends the session's recovery grant.
    """
    from fido2 import cbor
    from .passkey_views import RP_ID, server

    pending = request.session.pop(RECOVERY_REGISTRATION_STATE_KEY, None)
    user = _recovery_grant_user(request)
    if not pending or user is None or pending.get('user_id') != user.id:
        return Response({"error": RECOVERY_GRANT_INVALID}, status=status.HTTP_400_BAD_REQUEST)

    data = request.data
    response = data.get('response') or {}
    payload = {
        'id': data.get('id'),
        'rawId': data.get('rawId'),
        'type': data.get('type', 'public-key'),
        'response': {
            'clientDataJSON': response.get('clientDataJSON'),
            'attestationObject': response.get('attestationObject'),
        },
        'clientExtensionResults': data.get('clientExtensionResults') or {},
    }
    try:
        auth_data = server.register_complete(pending['state'], payload)
    except Exception:
        logger.warning("Recovery passkey registration verification failed", exc_info=True)
        # The grant stays, so the user can begin the registration again.
        return Response({"error": "Passkey verification failed"}, status=status.HTTP_400_BAD_REQUEST)

    credential = auth_data.credential_data
    credential_id = bytes(credential.credential_id)
    device_type = str(data.get('device_type') or 'Unknown Device')[:255]
    with transaction.atomic():
        if UserPasskey.objects.filter(credential_id=credential_id).exists():
            return Response({"error": "This passkey is already registered"},
                            status=status.HTTP_400_BAD_REQUEST)
        passkey = UserPasskey.objects.create(
            user=user,
            credential_id=credential_id,
            public_key=cbor.encode(credential.public_key),
            sign_count=auth_data.counter,
            rp_id=RP_ID,
            device_type=device_type,
        )
    request.session.pop(RECOVERY_REGISTRATION_GRANT_KEY, None)
    logger.info(log_safe(f"Recovery passkey registered for user_id={user.id} (device: {device_type})"))
    return Response({
        "message": "New passkey registered. Sign in with it, then create a new recovery backup.",
        "passkey_id": passkey.id,
        "device_type": device_type,
    }, status=status.HTTP_201_CREATED)


@api_view(['POST'])
@permission_classes([AllowAny])
def fallback_to_social_mesh_recovery(request):
    """
    Fallback to social mesh recovery if primary recovery fails.
    Links the failed primary attempt to a new social mesh recovery attempt.
    
    Request body:
        - primary_recovery_attempt_id: Token of the failed primary recovery attempt
    
    Response (the same for every attempt token that decrypts):
        - message, instructions, estimated_time
    """
    primary_attempt_id = request.data.get('primary_recovery_attempt_id')

    if not primary_attempt_id:
        return Response(
            {"error": "primary_recovery_attempt_id is required"},
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        # Find primary recovery attempt
        payload = _token_payload(primary_attempt_id)
        if payload is None:
            return Response(
                {"error": "Primary recovery attempt not found"},
                status=status.HTTP_404_NOT_FOUND
            )
        # Only an attempt whose recovery key failed may fall back; a fresh
        # attempt stays in primary recovery (and a decoy has no attempt).
        primary_attempt = PasskeyRecoveryAttempt.objects.filter(
            token_nonce=payload[1],
            status__in=('key_invalid', 'decryption_failed')
        ).first()

        from .quantum_recovery_models import RecoveryShard, PasskeyRecoverySetup

        # The answer is the same whether or not the account exists or has
        # guardian recovery set up; guardian details are never returned.
        if primary_attempt is not None and RecoveryShard.objects.filter(
            recovery_setup__in=PasskeyRecoverySetup.objects.filter(
                user=primary_attempt.user, is_active=True
            ),
            is_active=True
        ).exists():
            primary_attempt.initiate_fallback()
            logger.info(f"Fallback to social mesh recovery initiated for user {primary_attempt.user.username}")

        return Response(FALLBACK_RESPONSE, status=status.HTTP_200_OK)
    
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
            
            logger.info(log_safe(f"Recovery backup {backup_id} revoked by user {user.username}"))
            
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
        logger.error(log_safe(f"Error revoking recovery backup {backup_id}: {e}"), exc_info=True)
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
        from .quantum_recovery_models import RecoveryShard, RecoveryGuardian, PasskeyRecoverySetup
        
        active_shards = 0
        accepted_guardians = 0
        try:
            recovery_setup = PasskeyRecoverySetup.objects.get(
                user=user,
                is_active=True
            )
            active_shards = RecoveryShard.objects.filter(
                recovery_setup=recovery_setup,
                is_active=True
            ).count()
            accepted_guardians = RecoveryGuardian.objects.filter(
                recovery_setup=recovery_setup,
                status='active'
            ).count()
        except PasskeyRecoverySetup.DoesNotExist:
            pass
        
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
        logger.error(log_safe(f"Error getting recovery status for user {user.username}: {e}"), exc_info=True)
        return Response(
            {"error": "Failed to get recovery status"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


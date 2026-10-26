import json
import logging
from django.http import JsonResponse
from django.contrib.auth.models import User
from django.contrib.auth import login
from django.utils import timezone
from fido2.webauthn import (
    Aaguid,
    AttestedCredentialData,
    AuthenticationResponse,
    PublicKeyCredentialDescriptor,
    PublicKeyCredentialRpEntity,
    PublicKeyCredentialType,
    PublicKeyCredentialUserEntity,
    ResidentKeyRequirement,
    UserVerificationRequirement,
)
from fido2.cose import CoseKey
from fido2.utils import websafe_encode
from fido2 import cbor
from fido2.server import Fido2Server
from .models import UserPasskey
from django.contrib.auth.decorators import login_required
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken
from password_manager.api_utils import error_response, success_response
from django.conf import settings

# Setup logging
logger = logging.getLogger('auth_module')

# ==============================================================================
# FIDO2 Server Configuration
# ==============================================================================

# Load configuration from Django settings
RP_ID = getattr(settings, 'PASSKEY_RP_ID', 'localhost')
RP_NAME = getattr(settings, 'PASSKEY_RP_NAME', 'Password Manager')
ALLOWED_ORIGINS = getattr(settings, 'PASSKEY_ALLOWED_ORIGINS', [])
TIMEOUT = getattr(settings, 'PASSKEY_TIMEOUT', 300000)
USER_VERIFICATION = getattr(settings, 'PASSKEY_USER_VERIFICATION', 'preferred')
AUTHENTICATOR_ATTACHMENT = getattr(settings, 'PASSKEY_AUTHENTICATOR_ATTACHMENT', 'platform')

# Log configuration
logger.info(f"FIDO2 Server initialized with RP_ID={RP_ID}, RP_NAME={RP_NAME}")
logger.debug(f"Allowed origins: {ALLOWED_ORIGINS}")

# Create Relying Party entity
rp = PublicKeyCredentialRpEntity(id=RP_ID, name=RP_NAME)

# Custom origin validator
def verify_origin_custom(origin):
    """
    Custom origin verification for WebAuthn operations.
    Validates that the origin is in the allowed list.
    """
    if not origin:
        logger.warning("Origin verification failed: No origin provided")
        return False
    
    # In development mode, allow localhost origins
    if settings.DEBUG:
        localhost_origins = [
            'http://localhost:3000',
            'http://127.0.0.1:3000',
            'http://localhost:4173',
            'http://127.0.0.1:4173',
            'http://localhost:8000',
            'http://127.0.0.1:8000',
        ]
        if origin in localhost_origins:
            logger.debug(f"Origin {origin} allowed (development mode)")
            return True
    
    # Check against configured allowed origins
    if origin in ALLOWED_ORIGINS:
        logger.debug(f"Origin {origin} allowed")
        return True
    
    logger.warning(f"Origin verification failed: {origin} not in allowed list")
    return False

# Create FIDO2 server with origin verification enabled
server = Fido2Server(
    rp=rp,
    # None falls back to fido2's own check of the origin against RP_ID.
    verify_origin=verify_origin_custom if (ALLOWED_ORIGINS or settings.DEBUG) else None
)
server.timeout = TIMEOUT

# Import custom throttling classes
from password_manager.throttling import PasskeyThrottle
from shared.log_safe import log_safe

# Session keys holding the fido2 ``state`` between begin and complete. The
# state is the challenge plus the requested user-verification level; it is
# single-use and is popped before anything else in the matching complete.
REGISTRATION_STATE_KEY = 'passkey_registration'
AUTHENTICATION_STATE_KEY = 'passkey_authentication'

# Passkey sign-in only proves who the caller is. Nothing here holds or returns
# vault key material: the server keeps each credential's public key and sign
# count, and the vault stays locked until the client derives its key from the
# master password.

AUTHENTICATION_FAILED = "Authentication failed."


def _authentication_failed():
    """The one answer complete gives for every failure after the session state
    was found -- unknown credential, another account's credential, bad
    signature, counter regression -- so it never says which one it was."""
    return error_response(
        AUTHENTICATION_FAILED,
        status_code=status.HTTP_401_UNAUTHORIZED,
        code="passkey_auth_failed",
    )


def _attested_credential(passkey):
    """Rebuild the fido2 credential from the stored id and COSE public key."""
    return AttestedCredentialData.create(
        Aaguid.NONE,
        bytes(passkey.credential_id),
        CoseKey.parse(cbor.decode(bytes(passkey.public_key))),
    )


def _descriptor(credential_id):
    return PublicKeyCredentialDescriptor(
        type=PublicKeyCredentialType.PUBLIC_KEY, id=credential_id
    )


def _authentication_payload(data):
    """Only the WebAuthn fields fido2 parses, so stray client keys cannot make
    ``AuthenticationResponse.from_dict`` fail differently per account."""
    response = data.get('response') or {}
    payload = {
        'id': data.get('id'),
        'rawId': data.get('rawId'),
        'type': data.get('type', 'public-key'),
        'response': {
            'clientDataJSON': response.get('clientDataJSON'),
            'authenticatorData': response.get('authenticatorData'),
            'signature': response.get('signature'),
        },
        'clientExtensionResults': data.get('clientExtensionResults') or {},
    }
    if response.get('userHandle'):
        payload['response']['userHandle'] = response['userHandle']
    return payload


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@throttle_classes([PasskeyThrottle])
def webauthn_begin_registration(request):
    """Begin registering a passkey for the signed-in user."""
    try:
        user = request.user

        # One passkey per account.
        if UserPasskey.objects.filter(user=user).exists():
            return error_response(
                "User already has a registered passkey",
                status_code=status.HTTP_400_BAD_REQUEST
            )

        user_entity = PublicKeyCredentialUserEntity(
            id=str(user.id).encode(),
            name=user.username,
            display_name=user.email or user.username,
        )

        options, state = server.register_begin(
            user=user_entity,
            credentials=[],
            # Discoverable, so sign-in can start without naming the account.
            resident_key_requirement=ResidentKeyRequirement.REQUIRED,
            user_verification=UserVerificationRequirement.PREFERRED,
            authenticator_attachment=AUTHENTICATOR_ATTACHMENT,
        )

        request.session[REGISTRATION_STATE_KEY] = {'state': state, 'user_id': user.id}

        return success_response(dict(options.public_key))

    except Exception:
        logger.exception("WebAuthn operation failed")
        return error_response("An unexpected error occurred.", status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@throttle_classes([PasskeyThrottle])
def webauthn_complete_registration(request):
    """Complete registering a passkey for the signed-in user."""
    try:
        data = request.data
        pending = request.session.pop(REGISTRATION_STATE_KEY, None)

        # The state must belong to the account that is completing it.
        if not pending or pending.get('user_id') != request.user.id:
            return error_response(
                "Registration session expired or invalid",
                status_code=status.HTTP_400_BAD_REQUEST
            )
        user = request.user

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
            logger.warning("Passkey registration verification failed", exc_info=True)
            return error_response(
                "Passkey verification failed",
                status_code=status.HTTP_400_BAD_REQUEST
            )

        credential = auth_data.credential_data
        credential_id = bytes(credential.credential_id)
        device_type = str(data.get('device_type') or 'Unknown Device')[:255]

        if UserPasskey.objects.filter(credential_id=credential_id).exists():
            return error_response(
                "This passkey is already registered",
                status_code=status.HTTP_400_BAD_REQUEST
            )

        # Only public material is stored: the credential id, the COSE public
        # key (CBOR-encoded) and the authenticator's signature counter.
        passkey = UserPasskey.objects.create(
            user=user,
            credential_id=credential_id,
            public_key=cbor.encode(credential.public_key),
            sign_count=auth_data.counter,
            rp_id=RP_ID,
            device_type=device_type,
        )

        logger.info(log_safe(f"Passkey registered for user_id={user.id} (device: {device_type})"))

        return success_response({
            "success": True,
            "message": "Passkey registered successfully",
            "passkey_id": passkey.id,
            "device_type": device_type
        })

    except Exception:
        logger.exception("Unexpected error during passkey registration")
        return error_response(
            "Registration failed. Please try again.",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([PasskeyThrottle])
def webauthn_begin_authentication(request):
    """Begin passkey sign-in.

    Anonymous sign-in uses discoverable credentials: the answer names no
    account and lists no credential, so it is the same for every caller and
    looks nothing up (any ``email`` sent is ignored). A signed-in caller
    re-authenticating gets its own credential ids, which reveal nothing new.
    """
    try:
        user = request.user if request.user.is_authenticated else None
        credentials = None
        if user is not None:
            credentials = [
                _descriptor(bytes(cid)) for cid in
                UserPasskey.objects.filter(user=user).values_list('credential_id', flat=True)
            ]

        options, state = server.authenticate_begin(
            credentials=credentials,
            user_verification=UserVerificationRequirement.PREFERRED,
        )

        request.session[AUTHENTICATION_STATE_KEY] = {
            'state': state,
            'user_id': user.id if user is not None else None,
        }

        return success_response(dict(options.public_key))

    except Exception:
        logger.exception("WebAuthn operation failed")
        return error_response("An unexpected error occurred.", status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([PasskeyThrottle])
def webauthn_complete_authentication(request):
    """Complete passkey sign-in and issue session and JWT tokens."""
    try:
        pending = request.session.pop(AUTHENTICATION_STATE_KEY, None)
        if not pending:
            return error_response(
                "Authentication session expired or invalid",
                status_code=status.HTTP_400_BAD_REQUEST
            )

        try:
            response = AuthenticationResponse.from_dict(_authentication_payload(request.data))
        except Exception:
            return _authentication_failed()

        # The credential names its account: look it up by id, then require it
        # to belong to the re-authenticating user, if begin was bound to one.
        passkeys = list(
            UserPasskey.objects.select_related('user')
            .filter(credential_id=response.raw_id, user__is_active=True)
        )
        if pending.get('user_id') is not None:
            passkeys = [p for p in passkeys if p.user_id == pending['user_id']]
        credentials = []
        for passkey in passkeys:
            try:
                credentials.append(_attested_credential(passkey))
            except Exception:
                logger.warning("Stored passkey %s could not be parsed", passkey.pk)

        try:
            matched = server.authenticate_complete(pending['state'], credentials, response)
        except Exception:
            return _authentication_failed()

        passkey = next(
            p for p in passkeys if bytes(p.credential_id) == matched.credential_id
        )
        user = passkey.user

        # A discoverable credential returns the user handle set at
        # registration; it must name the credential's own account.
        user_handle = response.response.user_handle
        if user_handle is not None and user_handle != str(user.id).encode():
            return _authentication_failed()

        # Signature counter: authenticators that do not count (synced passkeys)
        # report 0 every time; any other counter must strictly increase. The
        # conditional update keeps two concurrent completes from both passing.
        counter = response.response.authenticator_data.counter
        now = timezone.now()
        if counter == 0 and passkey.sign_count == 0:
            UserPasskey.objects.filter(pk=passkey.pk).update(last_used_at=now)
        else:
            updated = UserPasskey.objects.filter(
                pk=passkey.pk, sign_count__lt=counter
            ).update(sign_count=counter, last_used_at=now)
            if not updated:
                logger.warning("Passkey %s signature counter did not increase", passkey.pk)
                return _authentication_failed()

        logger.info(f"Passkey authentication successful for user_id={user.id}")

        # Log in the user (for session-based auth). Two auth backends are
        # configured, so login() needs to be told which one vouched.
        login(request, user, backend='django.contrib.auth.backends.ModelBackend')

        refresh = RefreshToken.for_user(user)

        return success_response({
            "success": True,
            "message": "Authentication successful",
            "user": {
                "id": user.id,
                "username": user.username,
                "email": user.email
            },
            "tokens": {
                "access": str(refresh.access_token),
                "refresh": str(refresh)
            }
        })

    except Exception:
        logger.exception("Unexpected error during passkey authentication")
        return error_response(
            "Authentication failed. Please try again.",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

# Passkey Management Views
@login_required
def list_passkeys(request):
    """Get all passkeys for the logged-in user"""
    try:
        passkeys_qs = UserPasskey.objects.filter(user=request.user).order_by('-last_used_at')
        
        passkeys_list = []
        for passkey in passkeys_qs:
            passkeys_list.append({
                'id': passkey.id,
                'device_type': passkey.device_type or 'Unknown Device',
                'created_at': passkey.created_at.isoformat(),
                'last_used_at': passkey.last_used_at.isoformat() if passkey.last_used_at else None,
                'credential_id': websafe_encode(bytes(passkey.credential_id)),  # Convert bytes to base64
            })
        
        logger.info(f"Listed {len(passkeys_list)} passkeys for user {request.user.username}")
        
        return JsonResponse({
            'success': True,
            'passkeys': passkeys_list
        })
    except Exception as e:
        logger.error(f"Error listing passkeys for user {request.user.username}: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': 'Failed to retrieve passkeys'
        }, status=500)

@login_required
def delete_passkey(request, passkey_id):
    """Delete a passkey for the logged-in user"""
    if request.method != 'DELETE':
        return JsonResponse({
            'success': False,
            'error': 'This endpoint only accepts DELETE requests'
        }, status=405)
    
    try:
        passkey = UserPasskey.objects.get(id=passkey_id, user=request.user)
        device_type = passkey.device_type
        passkey.delete()
        
        logger.info(log_safe(f"Passkey deleted for user {request.user.username} (device: {device_type})"))
        
        return JsonResponse({
            'success': True,
            'message': 'Passkey deleted successfully'
        })
    except UserPasskey.DoesNotExist:
        logger.warning(log_safe(f"Attempted to delete non-existent passkey {passkey_id} by user {request.user.username}"))
        return JsonResponse({
            'success': False,
            'error': 'Passkey not found'
        }, status=404)
    except Exception as e:
        logger.error(f"Error deleting passkey for user {request.user.username}: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': 'Failed to delete passkey'
        }, status=500)

@login_required
def get_passkey_status(request):
    """Get information about user's passkey status"""
    passkey_count = UserPasskey.objects.filter(user=request.user).count()
    
    # Get the latest used passkey
    latest_passkey = UserPasskey.objects.filter(
        user=request.user, 
        last_used_at__isnull=False
    ).order_by('-last_used_at').first()
    
    return JsonResponse({
        'has_passkeys': passkey_count > 0,
        'passkey_count': passkey_count,
        'latest_use': latest_passkey.last_used_at.isoformat() if latest_passkey else None,
        'latest_device': latest_passkey.device_type if latest_passkey else None
    })

@login_required
def rename_passkey(request, passkey_id):
    """Rename a passkey (update device_type field)"""
    if request.method != 'PUT':
        return JsonResponse({
            'error': 'This endpoint only accepts PUT requests'
        }, status=405)
    
    try:
        data = json.loads(request.body)
        new_name = data.get('name')
        
        if not new_name:
            return JsonResponse({
                'error': 'Name is required'
            }, status=400)
        
        passkey = UserPasskey.objects.get(id=passkey_id, user=request.user)
        passkey.device_type = new_name
        passkey.save()
        
        return JsonResponse({
            'status': 'success',
            'message': 'Passkey renamed successfully'
        })
    except UserPasskey.DoesNotExist:
        return JsonResponse({
            'error': 'Passkey not found'
        }, status=404)
    except json.JSONDecodeError:
        return JsonResponse({
            'error': 'Invalid JSON data'
        }, status=400)

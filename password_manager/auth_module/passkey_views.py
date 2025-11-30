import json
import base64
import secrets
import logging
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.models import User
from django.contrib.auth import login
from django.utils import timezone
from fido2.webauthn import (
    PublicKeyCredentialRpEntity,
    PublicKeyCredentialUserEntity,
    PublicKeyCredentialParameters,
    UserVerificationRequirement
)
from fido2.utils import websafe_decode, websafe_encode
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

# Store challenges in session for security
def store_challenge(request, challenge):
    if 'webauthn_challenges' not in request.session:
        request.session['webauthn_challenges'] = []
    
    request.session['webauthn_challenges'].append(challenge)

def get_and_remove_challenge(request):
    challenges = request.session.get('webauthn_challenges', [])
    if not challenges:
        return None
    
    challenge = challenges.pop(0)
    request.session['webauthn_challenges'] = challenges
    return challenge

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
    verify_origin=verify_origin_custom if (ALLOWED_ORIGINS or settings.DEBUG) else True
)

# Import custom throttling classes
from password_manager.throttling import PasskeyThrottle

@api_view(['POST'])
@throttle_classes([PasskeyThrottle])
def webauthn_begin_registration(request):
    """Begin WebAuthn registration process"""
    try:
        email = request.data.get('email')
        if not email:
            return error_response("Email is required", status_code=status.HTTP_400_BAD_REQUEST)
        
        user = User.objects.filter(email=email).first()
        if not user:
            return error_response("User not found", status_code=status.HTTP_404_NOT_FOUND)
        
        # Check if user already has a passkey
        existing_passkey = UserPasskey.objects.filter(user=user).first()
        if existing_passkey:
            return error_response(
                "User already has a registered passkey",
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        # Create a user entity for the WebAuthn registration
        user_entity = PublicKeyCredentialUserEntity(
            id=str(user.id).encode(),
            name=user.username,
            display_name=user.email
        )
        
        # Generate registration options
        registration_options = server.register_begin(
            user=user_entity,
            credentials=[],
            user_verification=UserVerificationRequirement.PREFERRED,
            authenticator_attachment="platform"
        )
        
        # Store challenge in session
        request.session['registration_challenge'] = websafe_encode(registration_options.challenge)
        request.session['registration_user_id'] = user.id
        
        # Convert to JSON-compatible format
        registration_options_dict = dict(registration_options)
        registration_options_dict['challenge'] = websafe_encode(registration_options.challenge)
        registration_options_dict['user']['id'] = websafe_encode(registration_options_dict['user']['id'])
        
        # Ensure proper format for pubKeyCredParams
        registration_options_dict['pubKeyCredParams'] = [
            {
                'alg': -7,  # ES256
                'type': 'public-key'
            },
            {
                'alg': -257,  # RS256
                'type': 'public-key'
            }
        ]
        
        return success_response(registration_options_dict)
        
    except Exception as e:
        return error_response(str(e), status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
@throttle_classes([PasskeyThrottle])
def webauthn_complete_registration(request):
    """Complete WebAuthn registration process"""
    try:
        # Get data from request
        data = request.data
        
        # Get stored challenge and user ID from session
        challenge = request.session.get('registration_challenge')
        user_id = request.session.get('registration_user_id')
        
        if not challenge or not user_id:
            logger.warning(f"Registration session expired for user_id={user_id}")
            return error_response(
                "Registration session expired or invalid",
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        # Get user from database
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            logger.error(f"User not found: {user_id}")
            return error_response(
                "User not found",
                status_code=status.HTTP_404_NOT_FOUND
            )
        
        # Validate incoming data
        if not all([
            data.get('id'),
            data.get('rawId'),
            data.get('response', {}).get('attestationObject'),
            data.get('response', {}).get('clientDataJSON')
        ]):
            logger.warning(f"Incomplete registration data for user {user.username}")
            return error_response(
                "Incomplete credential data",
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        # Complete registration with origin verification
        try:
            auth_data = server.register_complete(
                challenge=websafe_decode(challenge),
                attestation_object=websafe_decode(data['response']['attestationObject']),
                client_data=websafe_decode(data['response']['clientDataJSON'])
            )
        except ValueError as e:
            logger.error(f"Registration verification failed for user {user.username}: {str(e)}")
            return error_response(
                "Passkey verification failed",
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        # Store credential in database with all required fields
        credential_id = websafe_encode(auth_data.credential_data.credential_id)
        public_key = auth_data.credential_data.public_key
        sign_count = auth_data.sign_count
        device_type = data.get('device_type', 'Unknown Device')
        
        # Check if credential already exists
        if UserPasskey.objects.filter(credential_id=credential_id).exists():
            logger.warning(f"Duplicate credential attempted for user {user.username}")
            return error_response(
                "This passkey is already registered",
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        # Create the passkey record
        # Note: credential_id needs to be stored as bytes for BinaryField
        passkey = UserPasskey.objects.create(
            user=user,
            credential_id=websafe_decode(credential_id),  # Store as bytes
            public_key=public_key,
            sign_count=sign_count,
            rp_id=RP_ID,
            device_type=device_type
            # created_at is set automatically by auto_now_add
        )
        
        logger.info(f"Passkey registered successfully for user {user.username} (device: {device_type})")
        
        # Clear session data
        if 'registration_challenge' in request.session:
            del request.session['registration_challenge']
        if 'registration_user_id' in request.session:
            del request.session['registration_user_id']
        
        return success_response({
            "success": True,
            "message": "Passkey registered successfully",
            "passkey_id": passkey.id,
            "device_type": device_type
        })
        
    except Exception as e:
        logger.error(f"Unexpected error during passkey registration: {str(e)}", exc_info=True)
        return error_response(
            "Registration failed. Please try again.",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(['POST'])
@throttle_classes([PasskeyThrottle])
def webauthn_begin_authentication(request):
    """Begin WebAuthn authentication process"""
    try:
        email = request.data.get('email')
        
        if not email:
            return error_response("Email is required", status_code=status.HTTP_400_BAD_REQUEST)
        
        user = User.objects.filter(email=email).first()
        
        if not user:
            return error_response("User not found", status_code=status.HTTP_404_NOT_FOUND)
        
        # Get user's passkeys
        passkeys = UserPasskey.objects.filter(user=user)
        
        if not passkeys.exists():
            return error_response(
                "No passkeys registered for this user",
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        # Convert credential IDs to allow list
        allow_credentials = [{
            'id': websafe_decode(passkey.credential_id),
            'type': 'public-key',
        } for passkey in passkeys]
        
        # Generate authentication options
        auth_options = server.authenticate_begin(
            credentials=allow_credentials,
            user_verification=UserVerificationRequirement.PREFERRED
        )
        
        # Store challenge in session
        request.session['authentication_challenge'] = websafe_encode(auth_options.challenge)
        request.session['authentication_user_id'] = user.id
        
        # Convert to JSON-compatible format
        auth_options_dict = dict(auth_options)
        auth_options_dict['challenge'] = websafe_encode(auth_options.challenge)
        auth_options_dict['allowCredentials'] = [{
            'id': websafe_encode(cred['id']),
            'type': cred['type'],
        } for cred in auth_options_dict['allowCredentials']]
        
        return success_response(auth_options_dict)
        
    except Exception as e:
        return error_response(str(e), status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
@throttle_classes([PasskeyThrottle])
def webauthn_complete_authentication(request):
    """Complete WebAuthn authentication process"""
    try:
        # Get data from request
        data = request.data
        
        # Get stored challenge and user ID from session
        challenge = request.session.get('authentication_challenge')
        user_id = request.session.get('authentication_user_id')
        
        if not challenge or not user_id:
            logger.warning(f"Authentication session expired for user_id={user_id}")
            return error_response(
                "Authentication session expired or invalid",
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        # Get user from database
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            logger.error(f"User not found: {user_id}")
            return error_response(
                "User not found",
                status_code=status.HTTP_404_NOT_FOUND
            )
        
        # Validate incoming data
        credential_id = data.get('id')
        if not credential_id:
            logger.warning(f"Missing credential ID for user {user.username}")
            return error_response(
                "Missing credential ID",
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        # Find the corresponding passkey
        # credential_id is stored as bytes in BinaryField
        credential_id_bytes = websafe_decode(credential_id)
        passkey = UserPasskey.objects.filter(user=user, credential_id=credential_id_bytes).first()
        
        if not passkey:
            logger.warning(f"Invalid credential attempted for user {user.username}")
            return error_response(
                "Invalid credential",
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        # Validate response data
        if not all([
            data.get('rawId'),
            data.get('response', {}).get('authenticatorData'),
            data.get('response', {}).get('clientDataJSON'),
            data.get('response', {}).get('signature')
        ]):
            logger.warning(f"Incomplete authentication data for user {user.username}")
            return error_response(
                "Incomplete authentication data",
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        # Complete authentication with origin verification
        try:
            auth_data = server.authenticate_complete(
                challenge=websafe_decode(challenge),
                credential_id=websafe_decode(data['rawId']),
                credential_type=data.get('type', 'public-key'),
                authenticator_data=websafe_decode(data['response']['authenticatorData']),
                client_data=websafe_decode(data['response']['clientDataJSON']),
                signature=websafe_decode(data['response']['signature']),
                user_handle=websafe_decode(data['response']['userHandle']) if data.get('response', {}).get('userHandle') else None,
                credential_public_key=passkey.public_key,
                credential_current_sign_count=passkey.sign_count
            )
        except ValueError as e:
            logger.error(f"Authentication verification failed for user {user.username}: {str(e)}")
            return error_response(
                "Authentication failed. Invalid signature.",
                status_code=status.HTTP_401_UNAUTHORIZED
            )
        except Exception as e:
            logger.error(f"Unexpected authentication error for user {user.username}: {str(e)}")
            return error_response(
                "Authentication failed. Please try again.",
                status_code=status.HTTP_401_UNAUTHORIZED
            )
        
        # Verify sign count to prevent replay attacks
        new_sign_count = auth_data.new_sign_count
        if new_sign_count <= passkey.sign_count:
            logger.error(f"Sign count verification failed for user {user.username}. "
                        f"Expected > {passkey.sign_count}, got {new_sign_count}")
            # This could indicate a cloned authenticator or replay attack
            return error_response(
                "Authentication failed. Possible security issue detected.",
                status_code=status.HTTP_401_UNAUTHORIZED
            )
        
        # Update passkey metadata
        passkey.sign_count = new_sign_count
        passkey.last_used_at = timezone.now()
        passkey.save()
        
        logger.info(f"Passkey authentication successful for user {user.username} "
                   f"(device: {passkey.device_type})")
        
        # Log in the user (for session-based auth)
        login(request, user)
        
        # Generate JWT tokens for API access
        refresh = RefreshToken.for_user(user)
        access_token = str(refresh.access_token)
        refresh_token = str(refresh)
        
        # Clear session data
        if 'authentication_challenge' in request.session:
            del request.session['authentication_challenge']
        if 'authentication_user_id' in request.session:
            del request.session['authentication_user_id']
        
        # Return success with tokens
        return success_response({
            "success": True,
            "message": "Authentication successful",
            "user": {
                "id": user.id,
                "username": user.username,
                "email": user.email
            },
            "tokens": {
                "access": access_token,
                "refresh": refresh_token
            }
        })
        
    except Exception as e:
        logger.error(f"Unexpected error during passkey authentication: {str(e)}", exc_info=True)
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
                'credential_id': websafe_encode(passkey.credential_id),  # Convert bytes to base64
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

@csrf_exempt
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
        
        logger.info(f"Passkey deleted for user {request.user.username} (device: {device_type})")
        
        return JsonResponse({
            'success': True,
            'message': 'Passkey deleted successfully'
        })
    except UserPasskey.DoesNotExist:
        logger.warning(f"Attempted to delete non-existent passkey {passkey_id} by user {request.user.username}")
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

@csrf_exempt
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

"""
OpenID Connect (OIDC) Views

Provides REST API endpoints for OIDC authentication:
- Discovery endpoint (.well-known/openid-configuration)
- OIDC provider management
- ID token authentication
- Enterprise SSO support
"""

import logging
import os
from typing import Optional

from django.conf import settings
from django.contrib.auth import get_user_model
from django.http import JsonResponse
from django.shortcuts import redirect
from django.views.decorators.csrf import csrf_exempt
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken

from .services.oidc_service import (
    OIDCError,
    OIDCProviderError,
    OIDCValidationError,
    get_oidc_service,
)

logger = logging.getLogger(__name__)
User = get_user_model()


def get_tokens_for_user(user):
    """Generate JWT tokens for a user"""
    refresh = RefreshToken.for_user(user)
    return {
        'refresh': str(refresh),
        'access': str(refresh.access_token),
    }


# =============================================================================
# OIDC Discovery Endpoints
# =============================================================================

@api_view(['GET'])
@permission_classes([AllowAny])
def oidc_discovery(request):
    """
    OIDC Discovery endpoint (.well-known/openid-configuration)
    
    Returns the server's OIDC configuration for clients to auto-configure.
    This makes your Password Manager an OIDC-aware resource server.
    """
    base_url = request.build_absolute_uri('/').rstrip('/')
    
    discovery_config = {
        'issuer': base_url,
        'authorization_endpoint': f'{base_url}/api/auth/oidc/authorize/',
        'token_endpoint': f'{base_url}/api/auth/oidc/token/',
        'userinfo_endpoint': f'{base_url}/api/auth/oidc/userinfo/',
        'jwks_uri': f'{base_url}/api/auth/oidc/.well-known/jwks.json',
        'registration_endpoint': f'{base_url}/api/auth/register/',
        'scopes_supported': ['openid', 'profile', 'email', 'vault'],
        'response_types_supported': ['code', 'token', 'id_token', 'code token', 'code id_token'],
        'grant_types_supported': ['authorization_code', 'refresh_token'],
        'subject_types_supported': ['public'],
        'id_token_signing_alg_values_supported': ['RS256', 'HS256'],
        'token_endpoint_auth_methods_supported': ['client_secret_basic', 'client_secret_post'],
        'claims_supported': [
            'sub', 'iss', 'aud', 'exp', 'iat', 'nonce',
            'email', 'email_verified', 'name', 'picture', 'locale'
        ],
        'code_challenge_methods_supported': ['S256', 'plain'],
    }
    
    return Response(discovery_config)


@api_view(['GET'])
@permission_classes([AllowAny])
def oidc_jwks(request):
    """
    JSON Web Key Set (JWKS) endpoint
    
    Returns the public keys used to verify JWTs issued by this server.
    """
    # In a production environment, you would generate and store RSA keys
    # For now, we return an empty JWKS since we use symmetric (HS256) signing
    
    jwks = {
        'keys': []
    }
    
    # If RSA keys are configured, add them here
    # Example:
    # jwks['keys'].append({
    #     'kty': 'RSA',
    #     'kid': 'key-id',
    #     'use': 'sig',
    #     'alg': 'RS256',
    #     'n': 'base64url-encoded-modulus',
    #     'e': 'AQAB'
    # })
    
    return Response(jwks)


# =============================================================================
# OIDC Provider Management
# =============================================================================

@api_view(['GET'])
@permission_classes([AllowAny])
def oidc_providers(request):
    """
    List all configured OIDC providers
    
    Returns available enterprise SSO and social login providers.
    """
    oidc_service = get_oidc_service()
    providers = []
    
    for name, provider in oidc_service.providers.items():
        providers.append({
            'name': name,
            'display_name': name.replace('_', ' ').title(),
            'enabled': True,
            'scopes': provider.scopes,
            'supports_oidc': True,
        })
    
    # Also include OAuth-only providers from allauth
    oauth_providers = getattr(settings, 'SOCIALACCOUNT_PROVIDERS', {})
    for provider_name in ['google', 'github', 'apple']:
        if provider_name in oauth_providers:
            provider_config = oauth_providers[provider_name].get('APP', {})
            if provider_config.get('client_id') and provider_name not in [p['name'] for p in providers]:
                providers.append({
                    'name': provider_name,
                    'display_name': provider_name.title(),
                    'enabled': True,
                    'supports_oidc': provider_name in ['google'],  # Only Google supports full OIDC
                })
    
    return Response({
        'success': True,
        'providers': providers,
        'oidc_discovery_url': request.build_absolute_uri('/api/auth/oidc/.well-known/openid-configuration'),
    })


@api_view(['POST'])
@permission_classes([AllowAny])
def oidc_authorize(request):
    """
    Initiate OIDC authorization flow
    
    Body parameters:
    - provider: OIDC provider name (e.g., 'google', 'microsoft', 'okta')
    - redirect_uri: Where to redirect after authentication
    - state: Optional client-provided state
    """
    provider_name = request.data.get('provider')
    redirect_uri = request.data.get('redirect_uri')
    client_state = request.data.get('state')
    
    if not provider_name:
        return Response({
            'success': False,
            'message': 'Provider is required',
            'code': 'missing_provider',
        }, status=status.HTTP_400_BAD_REQUEST)
    
    if not redirect_uri:
        redirect_uri = os.environ.get('FRONTEND_URL', 'http://localhost:3000') + '/auth/callback'
    
    oidc_service = get_oidc_service()
    
    try:
        auth_url, state, nonce = oidc_service.get_authorization_url(
            provider_name=provider_name,
            redirect_uri=request.build_absolute_uri('/api/auth/oidc/callback/'),
            extra_params={'login_hint': request.data.get('login_hint')},
        )
        
        # Store state and nonce for callback validation
        from django.core.cache import cache
        cache.set(f'oidc_state_{state}', {
            'provider': provider_name,
            'redirect_uri': redirect_uri,
            'client_state': client_state,
            'nonce': nonce,
        }, 600)  # 10 minutes
        
        return Response({
            'success': True,
            'authorization_url': auth_url,
            'state': state,
            'nonce': nonce,
        })
        
    except OIDCError as e:
        logger.error(f"OIDC authorize error: {e}")
        return Response({
            'success': False,
            'message': str(e),
            'code': 'oidc_error',
        }, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET', 'POST'])
@permission_classes([AllowAny])
def oidc_callback(request):
    """
    Handle OIDC callback from identity provider
    
    Query/Body parameters:
    - code: Authorization code
    - state: State parameter from authorization request
    - error: Error code (if authentication failed)
    """
    code = request.GET.get('code') or request.data.get('code')
    state = request.GET.get('state') or request.data.get('state')
    error = request.GET.get('error') or request.data.get('error')
    
    frontend_url = os.environ.get('FRONTEND_URL', 'http://localhost:3000')
    
    if error:
        error_description = request.GET.get('error_description', 'Authentication failed')
        logger.error(f"OIDC callback error: {error} - {error_description}")
        return redirect(f"{frontend_url}/auth/callback?error={error}&message={error_description}")
    
    if not code or not state:
        return redirect(f"{frontend_url}/auth/callback?error=invalid_request&message=Missing code or state")
    
    # Retrieve stored state data
    from django.core.cache import cache
    state_data = cache.get(f'oidc_state_{state}')
    
    if not state_data:
        return redirect(f"{frontend_url}/auth/callback?error=invalid_state&message=State expired or invalid")
    
    # Clear state from cache
    cache.delete(f'oidc_state_{state}')
    
    provider_name = state_data['provider']
    redirect_uri = state_data['redirect_uri']
    nonce = state_data['nonce']
    client_state = state_data.get('client_state')
    
    oidc_service = get_oidc_service()
    
    try:
        # Exchange code for tokens
        tokens = oidc_service.exchange_code_for_tokens(
            provider_name=provider_name,
            code=code,
            redirect_uri=request.build_absolute_uri('/api/auth/oidc/callback/'),
        )
        
        id_token = tokens.get('id_token')
        access_token = tokens.get('access_token')
        
        if not id_token:
            raise OIDCError("No ID token received from provider")
        
        # Validate ID token
        claims = oidc_service.validate_id_token(
            provider_name=provider_name,
            id_token=id_token,
            nonce=nonce,
        )
        
        # Extract user info
        user_info = oidc_service.extract_user_info(claims)
        
        # Get additional info from userinfo endpoint if available
        try:
            userinfo_data = oidc_service.get_userinfo(provider_name, access_token)
            user_info.update({
                k: v for k, v in userinfo_data.items()
                if k in ['email', 'name', 'picture'] and v
            })
        except Exception:
            pass  # UserInfo is optional
        
        # Find or create user
        user = _get_or_create_user(user_info, provider_name)
        
        if not user:
            return redirect(f"{frontend_url}/auth/callback?error=user_creation_failed")
        
        # Generate JWT tokens for the user
        jwt_tokens = get_tokens_for_user(user)
        
        logger.info(f"User {user.email} authenticated via OIDC provider {provider_name}")
        
        # Build redirect URL with tokens
        redirect_params = f"token={jwt_tokens['access']}&refresh={jwt_tokens['refresh']}&provider={provider_name}"
        if client_state:
            redirect_params += f"&state={client_state}"
        
        return redirect(f"{redirect_uri}?{redirect_params}")
        
    except OIDCValidationError as e:
        logger.error(f"OIDC token validation error: {e}")
        return redirect(f"{frontend_url}/auth/callback?error=validation_failed&message={str(e)}")
    except OIDCError as e:
        logger.error(f"OIDC callback error: {e}")
        return redirect(f"{frontend_url}/auth/callback?error=oidc_error&message={str(e)}")
    except Exception as e:
        logger.exception(f"Unexpected OIDC callback error: {e}")
        return redirect(f"{frontend_url}/auth/callback?error=server_error")


@api_view(['POST'])
@permission_classes([AllowAny])
def oidc_token(request):
    """
    OIDC Token endpoint
    
    Exchange authorization code for tokens (for clients acting as OIDC Relying Party).
    
    Body parameters:
    - provider: OIDC provider name
    - code: Authorization code
    - redirect_uri: Original redirect URI
    - grant_type: Must be 'authorization_code'
    """
    provider_name = request.data.get('provider')
    code = request.data.get('code')
    redirect_uri = request.data.get('redirect_uri')
    grant_type = request.data.get('grant_type')
    
    if grant_type != 'authorization_code':
        return Response({
            'error': 'unsupported_grant_type',
            'error_description': 'Only authorization_code grant type is supported',
        }, status=status.HTTP_400_BAD_REQUEST)
    
    if not all([provider_name, code, redirect_uri]):
        return Response({
            'error': 'invalid_request',
            'error_description': 'Missing required parameters',
        }, status=status.HTTP_400_BAD_REQUEST)
    
    oidc_service = get_oidc_service()
    
    try:
        tokens = oidc_service.exchange_code_for_tokens(
            provider_name=provider_name,
            code=code,
            redirect_uri=redirect_uri,
        )
        
        return Response(tokens)
        
    except OIDCError as e:
        return Response({
            'error': 'invalid_grant',
            'error_description': str(e),
        }, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def oidc_userinfo(request):
    """
    OIDC UserInfo endpoint
    
    Returns the authenticated user's profile information.
    Requires valid JWT token in Authorization header.
    """
    user = request.user
    
    userinfo = {
        'sub': str(user.id),
        'email': user.email,
        'email_verified': user.is_active,  # Assuming active users have verified email
        'name': user.get_full_name() or user.username,
        'preferred_username': user.username,
        'updated_at': int(user.date_joined.timestamp()) if user.date_joined else None,
    }
    
    # Add additional claims if available
    if hasattr(user, 'first_name') and user.first_name:
        userinfo['given_name'] = user.first_name
    if hasattr(user, 'last_name') and user.last_name:
        userinfo['family_name'] = user.last_name
    
    return Response(userinfo)


@api_view(['POST'])
@permission_classes([AllowAny])
def oidc_validate_token(request):
    """
    Validate an ID token from an OIDC provider
    
    Body parameters:
    - provider: OIDC provider name
    - id_token: The ID token to validate
    - nonce: Expected nonce (optional)
    """
    provider_name = request.data.get('provider')
    id_token = request.data.get('id_token')
    nonce = request.data.get('nonce')
    
    if not provider_name or not id_token:
        return Response({
            'success': False,
            'message': 'Provider and id_token are required',
            'code': 'invalid_request',
        }, status=status.HTTP_400_BAD_REQUEST)
    
    oidc_service = get_oidc_service()
    
    try:
        claims = oidc_service.validate_id_token(
            provider_name=provider_name,
            id_token=id_token,
            nonce=nonce,
            validate_nonce=bool(nonce),
        )
        
        user_info = oidc_service.extract_user_info(claims)
        
        return Response({
            'success': True,
            'valid': True,
            'claims': claims,
            'user_info': user_info,
        })
        
    except OIDCValidationError as e:
        return Response({
            'success': False,
            'valid': False,
            'message': str(e),
            'code': 'validation_failed',
        }, status=status.HTTP_401_UNAUTHORIZED)
    except OIDCError as e:
        return Response({
            'success': False,
            'message': str(e),
            'code': 'oidc_error',
        }, status=status.HTTP_400_BAD_REQUEST)


# =============================================================================
# Helper Functions
# =============================================================================

def _get_or_create_user(user_info: dict, provider_name: str) -> Optional[User]:
    """
    Get existing user or create new one from OIDC claims.
    
    Links OIDC identity to existing user if email matches,
    or creates new user if not found.
    """
    email = user_info.get('email')
    sub = user_info.get('sub')
    
    if not email:
        logger.error("OIDC user info missing email")
        return None
    
    try:
        # Try to find existing user by email
        try:
            user = User.objects.get(email=email)
            logger.info(f"Found existing user {email} for OIDC login")
        except User.DoesNotExist:
            # Create new user
            username = email.split('@')[0]
            base_username = username
            counter = 1
            
            # Ensure unique username
            while User.objects.filter(username=username).exists():
                username = f"{base_username}{counter}"
                counter += 1
            
            user = User.objects.create_user(
                username=username,
                email=email,
                first_name=user_info.get('given_name', ''),
                last_name=user_info.get('family_name', ''),
            )
            
            # Set unusable password since authentication is via OIDC
            user.set_unusable_password()
            user.save()
            
            logger.info(f"Created new user {email} via OIDC provider {provider_name}")
        
        # Link to social account (for tracking)
        try:
            from allauth.socialaccount.models import SocialAccount
            SocialAccount.objects.get_or_create(
                user=user,
                provider=provider_name,
                defaults={
                    'uid': sub,
                    'extra_data': user_info.get('provider_claims', {}),
                }
            )
        except Exception as e:
            logger.warning(f"Could not link social account: {e}")
        
        return user
        
    except Exception as e:
        logger.exception(f"Error getting/creating user from OIDC: {e}")
        return None


"""
OAuth authentication views for Google, GitHub, and Apple login
with Authy fallback mechanism
"""
from django.conf import settings
from django.contrib.auth import login
from django.shortcuts import redirect
from django.http import JsonResponse
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken
from allauth.socialaccount.models import SocialAccount, SocialApp
from allauth.socialaccount.providers.google.views import GoogleOAuth2Adapter
from allauth.socialaccount.providers.github.views import GitHubOAuth2Adapter
from allauth.socialaccount.providers.apple.views import AppleOAuth2Adapter
from dj_rest_auth.registration.views import SocialLoginView, SocialConnectView
from .services.authy_service import authy_service
from django.contrib.auth.models import User
import logging
import os

logger = logging.getLogger(__name__)


def get_tokens_for_user(user):
    """
    Generate JWT tokens for a user
    """
    refresh = RefreshToken.for_user(user)
    return {
        'refresh': str(refresh),
        'access': str(refresh.access_token),
    }


@api_view(['GET'])
@permission_classes([AllowAny])
def oauth_providers(request):
    """
    Get list of configured OAuth providers
    """
    providers = []
    
    # Check if Google OAuth is configured
    if settings.SOCIALACCOUNT_PROVIDERS.get('google', {}).get('APP', {}).get('client_id'):
        providers.append({
            'name': 'google',
            'display_name': 'Google',
            'enabled': True
        })
    
    # Check if GitHub OAuth is configured
    if settings.SOCIALACCOUNT_PROVIDERS.get('github', {}).get('APP', {}).get('client_id'):
        providers.append({
            'name': 'github',
            'display_name': 'GitHub',
            'enabled': True
        })
    
    # Check if Apple OAuth is configured
    if settings.SOCIALACCOUNT_PROVIDERS.get('apple', {}).get('APP', {}).get('client_id'):
        providers.append({
            'name': 'apple',
            'display_name': 'Apple',
            'enabled': True
        })
    
    return Response({
        'success': True,
        'providers': providers
    })


@api_view(['POST'])
@permission_classes([AllowAny])
def oauth_login_url(request):
    """
    Generate OAuth login URL for a provider
    """
    provider = request.data.get('provider')
    
    if not provider:
        return Response({
            'success': False,
            'message': 'Provider is required'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    if provider not in ['google', 'github', 'apple']:
        return Response({
            'success': False,
            'message': 'Invalid provider'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    # Generate the OAuth URL
    frontend_url = os.environ.get('FRONTEND_URL', 'http://localhost:3000')
    backend_url = os.environ.get('BACKEND_URL', 'http://127.0.0.1:8000')
    
    # OAuth URL format: /api/auth/oauth/{provider}/
    oauth_url = f"{backend_url}/api/auth/oauth/{provider}/"
    
    return Response({
        'success': True,
        'url': oauth_url,
        'provider': provider
    })


# Google OAuth Login
class GoogleLogin(SocialLoginView):
    adapter_class = GoogleOAuth2Adapter
    
    def post(self, request, *args, **kwargs):
        """Handle Google OAuth callback"""
        try:
            response = super().post(request, *args, **kwargs)
            
            if response.status_code == 200:
                # Generate JWT tokens
                user = self.user
                tokens = get_tokens_for_user(user)
                
                logger.info(f"User {user.email} logged in successfully with Google")
                
                return Response({
                    'success': True,
                    'message': 'Login successful',
                    'user': {
                        'id': user.id,
                        'email': user.email,
                        'username': user.username,
                    },
                    'tokens': tokens
                }, status=status.HTTP_200_OK)
            
            return response
            
        except Exception as e:
            logger.error(f"Google OAuth error: {str(e)}")
            
            # Try to get user info from the request to enable Authy fallback
            email = request.data.get('email') or request.GET.get('email')
            
            if email:
                # Trigger Authy fallback mechanism
                logger.info(f"OAuth failed for {email}, initiating Authy fallback")
                return Response({
                    'success': False,
                    'message': 'OAuth authentication failed',
                    'error': str(e),
                    'fallback_available': True,
                    'fallback_method': 'authy',
                    'email': email
                }, status=status.HTTP_401_UNAUTHORIZED)
            
            return Response({
                'success': False,
                'message': 'OAuth authentication failed',
                'error': str(e),
                'fallback_available': False
            }, status=status.HTTP_400_BAD_REQUEST)


# GitHub OAuth Login
class GitHubLogin(SocialLoginView):
    adapter_class = GitHubOAuth2Adapter
    
    def post(self, request, *args, **kwargs):
        """Handle GitHub OAuth callback"""
        try:
            response = super().post(request, *args, **kwargs)
            
            if response.status_code == 200:
                # Generate JWT tokens
                user = self.user
                tokens = get_tokens_for_user(user)
                
                logger.info(f"User {user.email} logged in successfully with GitHub")
                
                return Response({
                    'success': True,
                    'message': 'Login successful',
                    'user': {
                        'id': user.id,
                        'email': user.email,
                        'username': user.username,
                    },
                    'tokens': tokens
                }, status=status.HTTP_200_OK)
            
            return response
            
        except Exception as e:
            logger.error(f"GitHub OAuth error: {str(e)}")
            
            # Try to get user info from the request to enable Authy fallback
            email = request.data.get('email') or request.GET.get('email')
            
            if email:
                # Trigger Authy fallback mechanism
                logger.info(f"OAuth failed for {email}, initiating Authy fallback")
                return Response({
                    'success': False,
                    'message': 'OAuth authentication failed',
                    'error': str(e),
                    'fallback_available': True,
                    'fallback_method': 'authy',
                    'email': email
                }, status=status.HTTP_401_UNAUTHORIZED)
            
            return Response({
                'success': False,
                'message': 'OAuth authentication failed',
                'error': str(e),
                'fallback_available': False
            }, status=status.HTTP_400_BAD_REQUEST)


# Apple OAuth Login
class AppleLogin(SocialLoginView):
    adapter_class = AppleOAuth2Adapter
    
    def post(self, request, *args, **kwargs):
        """Handle Apple OAuth callback"""
        try:
            response = super().post(request, *args, **kwargs)
            
            if response.status_code == 200:
                # Generate JWT tokens
                user = self.user
                tokens = get_tokens_for_user(user)
                
                logger.info(f"User {user.email} logged in successfully with Apple")
                
                return Response({
                    'success': True,
                    'message': 'Login successful',
                    'user': {
                        'id': user.id,
                        'email': user.email,
                        'username': user.username,
                    },
                    'tokens': tokens
                }, status=status.HTTP_200_OK)
            
            return response
            
        except Exception as e:
            logger.error(f"Apple OAuth error: {str(e)}")
            
            # Try to get user info from the request to enable Authy fallback
            email = request.data.get('email') or request.GET.get('email')
            
            if email:
                # Trigger Authy fallback mechanism
                logger.info(f"OAuth failed for {email}, initiating Authy fallback")
                return Response({
                    'success': False,
                    'message': 'OAuth authentication failed',
                    'error': str(e),
                    'fallback_available': True,
                    'fallback_method': 'authy',
                    'email': email
                }, status=status.HTTP_401_UNAUTHORIZED)
            
            return Response({
                'success': False,
                'message': 'OAuth authentication failed',
                'error': str(e),
                'fallback_available': False
            }, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
def oauth_callback(request):
    """
    Handle OAuth callback and redirect to frontend with auth token
    """
    provider = request.GET.get('provider')
    error = request.GET.get('error')
    
    frontend_url = os.environ.get('FRONTEND_URL', 'http://localhost:3000')
    
    if error:
        logger.error(f"OAuth error for provider {provider}: {error}")
        return redirect(f"{frontend_url}/login?error=oauth_failed")
    
    # Get the user from the session
    if request.user.is_authenticated:
        tokens = get_tokens_for_user(request.user)
        # Redirect to frontend with token
        return redirect(f"{frontend_url}/auth/callback?token={tokens['access']}&refresh={tokens['refresh']}")
    
    return redirect(f"{frontend_url}/login?error=auth_failed")


@api_view(['POST'])
@permission_classes([AllowAny])
def oauth_fallback_authy(request):
    """
    Initiate Authy fallback when OAuth fails
    """
    email = request.data.get('email')
    phone = request.data.get('phone')
    country_code = request.data.get('country_code', '1')
    
    if not email:
        return Response({
            'success': False,
            'message': 'Email is required for Authy fallback'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        # Check if user exists
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response({
                'success': False,
                'message': 'User not found. Please sign up first.'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Register user with Authy if not already registered
        if phone:
            authy_id = authy_service.register_user(email, phone, country_code)
            
            if not authy_id:
                return Response({
                    'success': False,
                    'message': 'Failed to register with Authy service'
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
            # Store Authy ID in user profile or session
            # (You might want to add this field to your User model)
            request.session['authy_id'] = authy_id
            request.session['pending_user_id'] = user.id
            
            logger.info(f"Authy fallback initiated for user {email}")
            
            return Response({
                'success': True,
                'message': 'Authy verification initiated. Please check your phone.',
                'authy_id': authy_id,
                'requires_verification': True,
                'verification_method': 'sms'
            }, status=status.HTTP_200_OK)
        else:
            return Response({
                'success': False,
                'message': 'Phone number is required for Authy verification'
            }, status=status.HTTP_400_BAD_REQUEST)
            
    except Exception as e:
        logger.error(f"Authy fallback error: {str(e)}")
        return Response({
            'success': False,
            'message': 'Failed to initiate Authy fallback',
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([AllowAny])
def verify_authy_fallback(request):
    """
    Verify Authy code and complete authentication
    """
    authy_id = request.session.get('authy_id') or request.data.get('authy_id')
    token = request.data.get('token')
    
    if not authy_id or not token:
        return Response({
            'success': False,
            'message': 'Authy ID and verification token are required'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        # Verify the token with Authy
        is_valid = authy_service.verify_token(authy_id, token)
        
        if is_valid:
            # Get the pending user
            user_id = request.session.get('pending_user_id')
            if not user_id:
                return Response({
                    'success': False,
                    'message': 'Session expired. Please try again.'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            user = User.objects.get(id=user_id)
            
            # Generate JWT tokens
            tokens = get_tokens_for_user(user)
            
            # Clear session data
            request.session.pop('authy_id', None)
            request.session.pop('pending_user_id', None)
            
            logger.info(f"User {user.email} authenticated via Authy fallback")
            
            return Response({
                'success': True,
                'message': 'Authentication successful',
                'user': {
                    'id': user.id,
                    'email': user.email,
                    'username': user.username,
                },
                'tokens': tokens,
                'auth_method': 'authy_fallback'
            }, status=status.HTTP_200_OK)
        else:
            return Response({
                'success': False,
                'message': 'Invalid verification code'
            }, status=status.HTTP_401_UNAUTHORIZED)
            
    except Exception as e:
        logger.error(f"Authy verification error: {str(e)}")
        return Response({
            'success': False,
            'message': 'Verification failed',
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


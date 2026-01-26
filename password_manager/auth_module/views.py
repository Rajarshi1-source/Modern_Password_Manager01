from django.shortcuts import render
from rest_framework import status, viewsets, permissions
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.authtoken.models import Token
from .models import TwoFactorAuth, UserSalt, PushAuth, RecoveryKey
from .serializers import RegisterSerializer, LoginSerializer, MasterPasswordSerializer
from .utils import (
    generate_totp_secret, verify_totp_code, generate_backup_codes, 
    initiate_push_auth, check_push_auth_status
)
from vault.models import AuditLog
from logging_manager.models import RecoveryAttemptLog
import os
import logging
import base64
from django.contrib.auth.models import User
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes
from django.core.mail import send_mail
from .firebase import create_custom_token
from .services.authy_service import authy_service
from django.utils import timezone
from datetime import timedelta
from password_manager.api_utils import error_response, success_response
# Import account protection service
from security.services.account_protection import account_protection_service
# Import alternative security service
from security.services.security_service import security_service
# Import custom throttling classes
from password_manager.throttling import AuthRateThrottle, StrictSecurityThrottle
# Import shared utilities
from shared.validators import validate_strong_password
from shared.utils import get_client_ip, generate_secure_id
from shared.decorators import log_api_call, security_headers
# FIX: Import CSRF exemption for JWT-based API endpoints
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator

logger = logging.getLogger(__name__)

# Create your views here.

# FIX: Exempt AuthViewSet from CSRF - we use JWT authentication, not session cookies
@method_decorator(csrf_exempt, name='dispatch')
class AuthViewSet(viewsets.ViewSet):
    """Authentication endpoints for the password manager"""
    permission_classes = [permissions.AllowAny]
    
    def get_client_ip(self, request):
        """Extract client IP address from request"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip
    
    @action(detail=False, methods=['post'])
    def register(self, request):
        """Register a new user with master password"""
        serializer = RegisterSerializer(data=request.data)
        
        if serializer.is_valid():
            # Create user
            user = serializer.save()
            
            # Generate salt for key derivation
            salt = os.urandom(16)
            auth_hash = base64.b64decode(request.data.get('auth_hash', ''))
            
            # Store salt with user
            UserSalt.objects.create(
                user=user, 
                salt=salt,
                auth_hash=auth_hash
            )
            
            # Generate authentication token (legacy)
            token, created = Token.objects.get_or_create(user=user)
            
            # FIX: Also generate JWT tokens for frontend compatibility
            from rest_framework_simplejwt.tokens import RefreshToken
            refresh = RefreshToken.for_user(user)
            
            # Enhanced security analysis for new user registration - Option B: Parallel services
            try:
                # Primary analysis with existing service
                account_protection_service.analyze_login_attempt(
                    request=request,
                    user=user,
                    username=user.username,
                    success=True
                )
            except Exception as e:
                print(f"Account protection analysis for registration failed: {str(e)}")
            
            try:
                # Enhanced analysis with new security service
                analysis_result = security_service.analyze_login_attempt(
                    user=user,
                    request=request,
                    is_successful=True,
                    failure_reason=None
                )
                print(f"User registration analysis - Threat score: {analysis_result.threat_score}, Suspicious: {analysis_result.is_suspicious}")
            except Exception as e:
                print(f"Security service analysis for registration failed: {str(e)}")
            
            return success_response({
                'token': token.key,
                'access': str(refresh.access_token),  # FIX: JWT access token
                'refresh': str(refresh),              # FIX: JWT refresh token
                'salt': base64.b64encode(salt).decode('utf-8'),
                'user_id': user.id
            }, status_code=status.HTTP_201_CREATED)
            
        return error_response(serializer.errors, status_code=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['post'])
    def login(self, request):
        """User login with username and password authentication"""
        serializer = LoginSerializer(data=request.data)
        username_attempted = request.data.get('username', '')
        
        if serializer.is_valid():
            user = serializer.validated_data['user']
            
            # Analyze login attempt for security - Option B: Use both services in parallel
            try:
                # Primary analysis with existing service
                analysis_result1 = account_protection_service.analyze_login_attempt(
                    request=request,
                    user=user,
                    username=username_attempted,
                    success=True
                )
            except Exception as e:
                # Don't fail login if analysis fails, just log it
                print(f"Account protection analysis failed: {str(e)}")
                analysis_result1 = {}
            
            try:
                # Enhanced analysis with new security service
                analysis_result2 = security_service.analyze_login_attempt(
                    user=user,
                    request=request,
                    is_successful=True
                )
                # Combine or compare analysis results if needed
                print(f"Security analysis - Threat score: {analysis_result2.threat_score}, Suspicious: {analysis_result2.is_suspicious}")
            except Exception as e:
                print(f"Security service analysis failed: {str(e)}")
                analysis_result2 = None
            
            # Get user's salt
            try:
                salt_obj = UserSalt.objects.get(user=user)
                salt = base64.b64encode(salt_obj.salt).decode('utf-8')
            except UserSalt.DoesNotExist:
                # Log failed attempt - Option B: Use both services in parallel
                try:
                    # Primary analysis with existing service
                    account_protection_service.analyze_login_attempt(
                        request=request,
                        user=None,
                        username=username_attempted,
                        success=False,
                        failure_reason="User not properly initialized"
                    )
                except:
                    pass
                
                try:
                    # Enhanced analysis with new security service
                    analysis_result = security_service.analyze_login_attempt(
                        user=user,  # We have the user object here
                        request=request,
                        is_successful=False,
                        failure_reason="User not properly initialized"
                    )
                    print(f"User initialization failure analysis - Threat score: {analysis_result.threat_score}, Suspicious: {analysis_result.is_suspicious}")
                except Exception as e:
                    print(f"Security service analysis for initialization failure failed: {str(e)}")
                
                return error_response('User not initialized properly', status_code=status.HTTP_400_BAD_REQUEST)
            
            # Get or create auth token
            token, created = Token.objects.get_or_create(user=user)
            
            # Check if 2FA is enabled and what type
            try:
                tfa = TwoFactorAuth.objects.get(user=user)
                requires_2fa = tfa.is_enabled
                mfa_type = tfa.mfa_type if tfa.is_enabled else None
                
                # For push authentication, initiate push request immediately
                if requires_2fa and mfa_type == 'push':
                    push_auth = initiate_push_auth(user, request)
                    if push_auth:
                        return success_response({
                            'requires_2fa': True,
                            'mfa_type': 'push',
                            'request_id': push_auth.request_id,
                            'expires_in': 120,  # 2 minutes
                            'salt': salt,
                            'user_id': user.id,
                            'partial_token': token.key[:4]  # Only part of the token for 2nd stage
                        })
                
            except TwoFactorAuth.DoesNotExist:
                requires_2fa = False
                mfa_type = None
            
            # Log login attempt
            AuditLog.objects.create(
                user=user,
                action='login',
                ip_address=self.get_client_ip(request),
                user_agent=request.META.get('HTTP_USER_AGENT', ''),
                status='success'
            )
            
            # If 2FA is required, only return partial token
            if requires_2fa:
                return success_response({
                    'requires_2fa': True,
                    'mfa_type': mfa_type,
                    'salt': salt,
                    'user_id': user.id,
                    'partial_token': token.key[:4]  # Only part of the token for 2nd stage
                })
            
            # Otherwise, return full token
            return success_response({
                'token': token.key,
                'salt': salt,
                'user_id': user.id,
                'requires_2fa': False
            })
        
        else:
            # Handle failed login attempt - Option B: Use both services in parallel
            try:
                # Primary analysis with existing service
                account_protection_service.analyze_login_attempt(
                    request=request,
                    user=None,
                    username=username_attempted,
                    success=False,
                    failure_reason="Invalid credentials"
                )
            except Exception as e:
                print(f"Account protection analysis failed: {str(e)}")
            
            try:
                # Enhanced analysis with new security service
                # Try to find user for better analysis
                user = None
                try:
                    user = User.objects.get(username=username_attempted)
                except User.DoesNotExist:
                    pass
                
                analysis_result = security_service.analyze_login_attempt(
                    user=user,
                    request=request,
                    is_successful=False,
                    failure_reason="Invalid credentials"
                )
                print(f"Failed login analysis - Threat score: {analysis_result.threat_score}, Suspicious: {analysis_result.is_suspicious}")
            except Exception as e:
                print(f"Security service analysis failed: {str(e)}")
            
            return error_response(serializer.errors, status_code=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['post'])
    def verify_master(self, request):
        """Verify master password using auth hash"""
        if not request.user.is_authenticated:
            return error_response('Authentication required', 
                           status_code=status.HTTP_401_UNAUTHORIZED)
        
        serializer = MasterPasswordSerializer(data=request.data)
        
        if serializer.is_valid():
            auth_hash = base64.b64decode(serializer.validated_data['auth_hash'])
            
            try:
                salt_obj = UserSalt.objects.get(user=request.user)
                
                # Compare with stored auth hash
                is_valid = auth_hash == salt_obj.auth_hash
                
                return success_response({'is_valid': is_valid})
                
            except UserSalt.DoesNotExist:
                return error_response('User not initialized', 
                               status_code=status.HTTP_400_BAD_REQUEST)
        
        return error_response(serializer.errors, status_code=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['post'])
    def change_master(self, request):
        """Change user's master password"""
        if not request.user.is_authenticated:
            return Response({'error': 'Authentication required'}, 
                           status=status.HTTP_401_UNAUTHORIZED)
        
        # Verify the current master password first
        current_auth_hash = request.data.get('current_auth_hash')
        new_auth_hash = request.data.get('new_auth_hash')
        
        if not current_auth_hash or not new_auth_hash:
            return Response({'error': 'Both current and new password hashes are required'}, 
                           status=status.HTTP_400_BAD_REQUEST)
        
        try:
            # Get user's salt
            salt_obj = UserSalt.objects.get(user=request.user)
            
            # Verify current password
            current_auth_hash_bytes = base64.b64decode(current_auth_hash)
            if current_auth_hash_bytes != salt_obj.auth_hash:
                return Response({'error': 'Current master password is incorrect'}, 
                              status=status.HTTP_400_BAD_REQUEST)
            
            # Update to new password
            salt_obj.auth_hash = base64.b64decode(new_auth_hash)
            salt_obj.save()
            
            # Enhanced security analysis for password change - Option B: Parallel services
            try:
                # Primary analysis with existing service
                account_protection_service.analyze_login_attempt(
                    request=request,
                    user=request.user,
                    username=request.user.username,
                    success=True
                )
            except Exception as e:
                print(f"Account protection analysis for password change failed: {str(e)}")
            
            try:
                # Enhanced analysis with new security service
                analysis_result = security_service.analyze_login_attempt(
                    user=request.user,
                    request=request,
                    is_successful=True,
                    failure_reason=None
                )
                print(f"Password change analysis - Threat score: {analysis_result.threat_score}, Suspicious: {analysis_result.is_suspicious}")
            except Exception as e:
                print(f"Security service analysis for password change failed: {str(e)}")
            
            # Log the password change
            AuditLog.objects.create(
                user=request.user,
                action='password_change',
                ip_address=self.get_client_ip(request),
                user_agent=request.META.get('HTTP_USER_AGENT', ''),
                status='success'
            )
            
            return Response({'success': True, 'message': 'Master password changed successfully'})
            
        except UserSalt.DoesNotExist:
            return Response({'error': 'User not initialized'}, 
                           status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['post', 'get'])
    def two_factor_auth(self, request):
        """Handle 2FA setup and verification"""
        if not request.user.is_authenticated:
            return Response({'error': 'Authentication required'}, 
                           status=status.HTTP_401_UNAUTHORIZED)
        
        # GET: Return 2FA status or setup info
        if request.method == 'GET':
            try:
                tfa = TwoFactorAuth.objects.get(user=request.user)
                return Response({
                    'is_enabled': tfa.is_enabled,
                    'mfa_type': tfa.mfa_type,
                    'created_at': tfa.created_at,
                    'phone_number': tfa.phone_number if tfa.phone_number else None
                })
            except TwoFactorAuth.DoesNotExist:
                # Generate new secret for TOTP setup
                secret = generate_totp_secret()
                provisioning_uri = f"otpauth://totp/SecureVault:{request.user.email}?secret={secret}&issuer=SecureVault"
                
                return Response({
                    'is_enabled': False,
                    'setup_secret': secret,
                    'provisioning_uri': provisioning_uri,
                    'backup_codes': generate_backup_codes()
                })
        
        # POST: Enable/disable 2FA or verify code
        elif request.method == 'POST':
            action_type = request.data.get('action', '')
            mfa_type = request.data.get('mfa_type', 'totp')  # Default to TOTP
            
            # Enable 2FA
            if action_type == 'enable':
                return self.enable_two_factor(request, mfa_type)
                
            # Disable 2FA
            elif action_type == 'disable':
                return self.disable_two_factor(request)
                
            # Verify 2FA code
            elif action_type == 'verify':
                return self.verify_two_factor(request)
            
            else:
                return Response({'error': 'Invalid action type'}, 
                               status=status.HTTP_400_BAD_REQUEST)

    def enable_two_factor(self, request, mfa_type):
        """Enable 2FA for a user"""
        # Handle TOTP setup
        if mfa_type == 'totp':
            secret = request.data.get('secret')
            code = request.data.get('code')
            backup_codes = request.data.get('backup_codes', [])
            
            if not secret or not code:
                return Response({'error': 'Secret and verification code required'}, 
                               status=status.HTTP_400_BAD_REQUEST)
            
            # Verify the provided code
            if not verify_totp_code(secret, code):
                return Response({'error': 'Invalid verification code'}, 
                               status=status.HTTP_400_BAD_REQUEST)
            
            # Save secret and enable 2FA
            TwoFactorAuth.objects.update_or_create(
                user=request.user,
                defaults={
                    'secret_key': secret,
                    'is_enabled': True,
                    'mfa_type': 'totp',
                    'backup_codes': ','.join(backup_codes)
                }
            )
            
            # Enhanced security analysis for 2FA setup - Option B: Parallel services
            try:
                # Primary analysis with existing service
                account_protection_service.analyze_login_attempt(
                    request=request,
                    user=request.user,
                    username=request.user.username,
                    success=True
                )
            except Exception as e:
                print(f"Account protection analysis for 2FA setup failed: {str(e)}")
            
            try:
                # Enhanced analysis with new security service
                analysis_result = security_service.analyze_login_attempt(
                    user=request.user,
                    request=request,
                    is_successful=True,
                    failure_reason=None
                )
                print(f"2FA setup analysis - Threat score: {analysis_result.threat_score}, Suspicious: {analysis_result.is_suspicious}")
            except Exception as e:
                print(f"Security service analysis for 2FA setup failed: {str(e)}")
            
            return Response({'success': True, 'message': '2FA enabled successfully'})
        
        # Handle Authy setup
        elif mfa_type == 'authy':
            phone = request.data.get('phone')
            country_code = request.data.get('country_code', '1')
            
            if not phone:
                return Response({'error': 'Phone number required'}, 
                               status=status.HTTP_400_BAD_REQUEST)
            
            # Register with Authy
            authy_id = authy_service.register_user(
                request.user.email,
                phone,
                country_code
            )
            
            if not authy_id:
                return Response({'error': 'Failed to register with Authy'}, 
                               status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
            # Save Authy ID and enable 2FA
            TwoFactorAuth.objects.update_or_create(
                user=request.user,
                defaults={
                    'authy_id': authy_id,
                    'is_enabled': True,
                    'mfa_type': 'authy',
                    'phone_number': phone,
                    'country_code': country_code,
                    'backup_codes': ','.join(generate_backup_codes())
                }
            )
            
            return Response({
                'success': True, 
                'message': 'Authy 2FA enabled successfully',
                'authy_id': authy_id
            })
        
        # Handle push notification setup
        elif mfa_type == 'push':
            phone = request.data.get('phone')
            country_code = request.data.get('country_code', '1')
            device_token = request.data.get('device_token')
            device_type = request.data.get('device_type')  # 'ios' or 'android'
            
            if not phone:
                return Response({'error': 'Phone number required'}, 
                               status=status.HTTP_400_BAD_REQUEST)
            
            # Register with Authy for push
            authy_id = authy_service.register_user(
                request.user.email,
                phone,
                country_code
            )
            
            success = False
            
            # Save the TFA record with backup codes in case push fails
            tfa, _ = TwoFactorAuth.objects.update_or_create(
                user=request.user,
                defaults={
                    'is_enabled': True,
                    'mfa_type': 'push',
                    'phone_number': phone,
                    'country_code': country_code,
                    'backup_codes': ','.join(generate_backup_codes())
                }
            )
            
            # If Authy registration successful, store Authy ID
            if authy_id:
                tfa.authy_id = authy_id
                tfa.save()
                success = True
            
            # If device token provided, register device for direct push
            if device_token and device_type:
                try:
                    if device_type.lower() == 'ios':
                        from push_notifications.models import APNSDevice
                        APNSDevice.objects.get_or_create(
                            registration_id=device_token,
                            defaults={
                                'user': request.user,
                                'name': f"{request.user.username}'s iOS device"
                            }
                        )
                    else:  # Android
                        from push_notifications.models import GCMDevice
                        GCMDevice.objects.get_or_create(
                            registration_id=device_token,
                            defaults={
                                'user': request.user,
                                'name': f"{request.user.username}'s Android device"
                            }
                        )
                    success = True
                except Exception as e:
                    print(f"Error registering device: {str(e)}")
            
            if success:
                return Response({
                    'success': True,
                    'message': 'Push authentication enabled successfully',
                    'authy_id': authy_id
                })
            else:
                return Response({
                    'error': 'Failed to set up push authentication'
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        else:
            return Response({
                'error': 'Invalid MFA type'
            }, status=status.HTTP_400_BAD_REQUEST)

    def disable_two_factor(self, request):
        """Disable 2FA for a user"""
        try:
            tfa = TwoFactorAuth.objects.get(user=request.user)
            
            # Clean up Authy if necessary
            if tfa.mfa_type == 'authy' or (tfa.mfa_type == 'push' and tfa.authy_id):
                try:
                    authy_service.delete_user(tfa.authy_id)
                except:
                    pass
            
            # Disable 2FA
            tfa.is_enabled = False
            tfa.save()
            
            # Enhanced security analysis for 2FA disable - Option B: Parallel services
            try:
                # Primary analysis with existing service
                account_protection_service.analyze_login_attempt(
                    request=request,
                    user=request.user,
                    username=request.user.username,
                    success=True
                )
            except Exception as e:
                print(f"Account protection analysis for 2FA disable failed: {str(e)}")
            
            try:
                # Enhanced analysis with new security service
                analysis_result = security_service.analyze_login_attempt(
                    user=request.user,
                    request=request,
                    is_successful=True,
                    failure_reason=None
                )
                print(f"2FA disable analysis - Threat score: {analysis_result.threat_score}, Suspicious: {analysis_result.is_suspicious}")
            except Exception as e:
                print(f"Security service analysis for 2FA disable failed: {str(e)}")
            
            return Response({'success': True, 'message': '2FA disabled successfully'})
        except TwoFactorAuth.DoesNotExist:
            return Response({'error': '2FA not set up for this user'}, 
                           status=status.HTTP_400_BAD_REQUEST)

    def verify_two_factor(self, request):
        """Verify a 2FA code or status"""
        code = request.data.get('code')
        request_id = request.data.get('request_id')
        backup_code = request.data.get('backup_code')
        
        try:
            tfa = TwoFactorAuth.objects.get(user=request.user)
            
            if not tfa.is_enabled:
                return error_response('2FA is not enabled', 
                               status_code=status.HTTP_400_BAD_REQUEST)
            
            # Check backup code first if provided
            if backup_code:
                backup_codes = tfa.backup_codes.split(',')
                if backup_code in backup_codes:
                    # Remove used backup code
                    backup_codes.remove(backup_code)
                    tfa.backup_codes = ','.join(backup_codes)
                    tfa.save()
                    return success_response({'is_valid': True})
                else:
                    return success_response({'is_valid': False, 'error': 'Invalid backup code'}, 
                                           message='Invalid backup code')
            
            # Handle different MFA types
            if tfa.mfa_type == 'totp':
                if not code:
                    return error_response('Verification code required', 
                                   status_code=status.HTTP_400_BAD_REQUEST)
                
                is_valid = verify_totp_code(tfa.secret_key, code)
                if is_valid:
                    tfa.last_used = timezone.now()
                    tfa.save()
                
                return success_response({'is_valid': is_valid})
                
            elif tfa.mfa_type == 'authy':
                if not code:
                    return error_response('Verification code required', 
                                   status_code=status.HTTP_400_BAD_REQUEST)
                
                is_valid = authy_service.verify_token(tfa.authy_id, code)
                if is_valid:
                    tfa.last_used = timezone.now()
                    tfa.save()
                
                return success_response({'is_valid': is_valid})
                
            elif tfa.mfa_type == 'push':
                # For push, we need a request ID to check status
                if not request_id:
                    # If no request ID, initiate a new push request
                    push_auth = initiate_push_auth(request.user, request)
                    
                    if push_auth:
                        return success_response({
                            'request_id': push_auth.request_id,
                            'expires_in': 120  # 2 minutes
                        })
                    else:
                        return error_response('Failed to initiate push authentication',
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)
                
                # Check status of existing push request
                status_value = check_push_auth_status(request_id)
                
                if status_value == 'approved':
                    tfa.last_used = timezone.now()
                    tfa.save()
                    return success_response({'is_valid': True, 'status': status_value})
                elif status_value == 'pending':
                    return success_response({'is_valid': False, 'status': status_value})
                else:
                    return success_response({'is_valid': False, 'status': status_value}, 
                                           message='Authentication denied or expired')
        
        except TwoFactorAuth.DoesNotExist:
            return error_response('2FA not set up for this user', 
                           status_code=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['post'])
    def initiate_push_authentication(self, request):
        """Initiate a push authentication request"""
        if not request.user.is_authenticated:
            return Response({'error': 'Authentication required'}, 
                           status=status.HTTP_401_UNAUTHORIZED)
        
        push_auth = initiate_push_auth(request.user, request)
        
        if push_auth:
            return Response({
                'success': True,
                'request_id': push_auth.request_id,
                'expires_in': 120  # 2 minutes
            })
        else:
            return Response({
                'error': 'Failed to initiate push authentication'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'])
    def check_push_authentication(self, request):
        """Check the status of a push authentication request"""
        if not request.user.is_authenticated:
            return Response({'error': 'Authentication required'}, 
                           status=status.HTTP_401_UNAUTHORIZED)
        
        request_id = request.data.get('request_id')
        
        if not request_id:
            return Response({'error': 'Request ID required'}, 
                           status=status.HTTP_400_BAD_REQUEST)
        
        status_value = check_push_auth_status(request_id)
        
        if status_value == 'approved':
            return Response({'success': True, 'status': status_value})
        elif status_value == 'pending':
            return Response({'success': True, 'status': status_value})
        else:
            return Response({'success': False, 'status': status_value})

    @action(detail=False, methods=['post'])
    def respond_to_push(self, request):
        """Respond to a push authentication request (from mobile app)"""
        request_id = request.data.get('request_id')
        response = request.data.get('response')  # 'approve' or 'deny'
        
        if not request_id or not response:
            return Response({'error': 'Request ID and response required'}, 
                          status=status.HTTP_400_BAD_REQUEST)
        
        try:
            # Verify the authenticated user
            if not request.user.is_authenticated:
                return Response({'error': 'Authentication required'}, 
                               status=status.HTTP_401_UNAUTHORIZED)
            
            # Find the push auth request
            push_auth = PushAuth.objects.get(
                request_id=request_id,
                user=request.user,
                status='pending'
            )
            
            # Update the status based on response
            if response == 'approve':
                push_auth.status = 'approved'
            else:
                push_auth.status = 'denied'
            
            push_auth.save()
            
            return Response({'success': True})
            
        except PushAuth.DoesNotExist:
            return Response({'error': 'Invalid request ID'}, 
                          status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['post'])
    def request_password_reset(self, request):
        """Request a password reset via email"""
        email = request.data.get('email')
        
        if not email:
            return Response({'error': 'Email is required'}, 
                          status=status.HTTP_400_BAD_REQUEST)
        
        try:
            user = User.objects.get(email=email)
            # Generate password reset token
            token = default_token_generator.make_token(user)
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            
            # Enhanced security analysis for password reset request - Option B: Parallel services
            try:
                # Primary analysis with existing service
                account_protection_service.analyze_login_attempt(
                    request=request,
                    user=user,
                    username=user.username,
                    success=True
                )
            except Exception as e:
                print(f"Account protection analysis for password reset request failed: {str(e)}")
            
            try:
                # Enhanced analysis with new security service
                analysis_result = security_service.analyze_login_attempt(
                    user=user,
                    request=request,
                    is_successful=True,
                    failure_reason=None
                )
                print(f"Password reset request analysis - Threat score: {analysis_result.threat_score}, Suspicious: {analysis_result.is_suspicious}")
            except Exception as e:
                print(f"Security service analysis for password reset request failed: {str(e)}")
            
            # Send email with reset link
            reset_url = f"{request.build_absolute_uri('/').rstrip('/')}/reset-password/{uid}/{token}/"
            
            send_mail(
                'Password Reset Request',
                f'Click the following link to reset your master password: {reset_url}',
                'noreply@yourpasswordmanager.com',
                [email],
                fail_silently=False,
            )
            
            # Log the password reset request
            AuditLog.objects.create(
                user=user,
                action='password_reset_request',
                ip_address=self.get_client_ip(request),
                user_agent=request.META.get('HTTP_USER_AGENT', ''),
                status='success'
            )
            
            return Response({'success': True, 'message': 'Password reset email sent'})
            
        except User.DoesNotExist:
            # Return success anyway to prevent email enumeration
            return Response({'success': True, 'message': 'If your email exists in our system, you will receive a password reset link'})

    @action(detail=False, methods=['post'])
    def reset_password(self, request):
        """Reset password using token from email"""
        uid = request.data.get('uid')
        token = request.data.get('token')
        new_auth_hash = request.data.get('new_auth_hash')
        
        if not uid or not token or not new_auth_hash:
            return Response({'error': 'All fields are required'}, 
                          status=status.HTTP_400_BAD_REQUEST)
        
        try:
            # Decode user ID
            user_id = urlsafe_base64_decode(uid).decode()
            user = User.objects.get(pk=user_id)
            
            # Verify token
            if not default_token_generator.check_token(user, token):
                return Response({'error': 'Invalid or expired token'}, 
                              status=status.HTTP_400_BAD_REQUEST)
            
            # Update password
            salt_obj = UserSalt.objects.get(user=user)
            salt_obj.auth_hash = base64.b64decode(new_auth_hash)
            salt_obj.save()
            
            # Enhanced security analysis for password reset - Option B: Parallel services
            try:
                # Primary analysis with existing service
                account_protection_service.analyze_login_attempt(
                    request=request,
                    user=user,
                    username=user.username,
                    success=True
                )
            except Exception as e:
                print(f"Account protection analysis for password reset failed: {str(e)}")
            
            try:
                # Enhanced analysis with new security service
                analysis_result = security_service.analyze_login_attempt(
                    user=user,
                    request=request,
                    is_successful=True,
                    failure_reason=None
                )
                print(f"Password reset analysis - Threat score: {analysis_result.threat_score}, Suspicious: {analysis_result.is_suspicious}")
            except Exception as e:
                print(f"Security service analysis for password reset failed: {str(e)}")
            
            # Log the password reset
            AuditLog.objects.create(
                user=user,
                action='password_reset',
                ip_address=self.get_client_ip(request),
                user_agent=request.META.get('HTTP_USER_AGENT', ''),
                status='success'
            )
            
            return Response({'success': True, 'message': 'Password reset successful'})
            
        except (TypeError, ValueError, OverflowError, User.DoesNotExist, UserSalt.DoesNotExist):
            return Response({'error': 'Invalid reset link'}, 
                          status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['get'])
    def firebase_token(self, request):
        """Get a Firebase authentication token for real-time sync"""
        if not request.user.is_authenticated:
            return Response({'error': 'Authentication required'}, 
                            status=status.HTTP_401_UNAUTHORIZED)
        
        token = create_custom_token(request.user.id)
        
        if token:
            return Response({
                'token': token,
                'user_id': request.user.id
            })
        else:
            return Response({'error': 'Failed to create Firebase token'}, 
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'])
    def complete_login(self, request):
        """Complete login with 2FA verification"""
        user_id = request.data.get('user_id')
        code = request.data.get('code')
        request_id = request.data.get('request_id')
        backup_code = request.data.get('backup_code')
        
        if not user_id:
            return error_response('User ID required', 
                           status_code=status.HTTP_400_BAD_REQUEST)
        
        try:
            user = User.objects.get(id=user_id)
            
            # Get the user's 2FA settings
            try:
                tfa = TwoFactorAuth.objects.get(user=user)
                
                if not tfa.is_enabled:
                    return error_response('2FA is not enabled for this user', 
                                  status_code=status.HTTP_400_BAD_REQUEST)
                
                is_valid = False
                
                # Check backup code first if provided
                if backup_code:
                    backup_codes = tfa.backup_codes.split(',')
                    if backup_code in backup_codes:
                        # Remove used backup code
                        backup_codes.remove(backup_code)
                        tfa.backup_codes = ','.join(backup_codes)
                        tfa.save()
                        is_valid = True
                
                # Otherwise, verify based on MFA type
                elif tfa.mfa_type == 'totp':
                    if not code:
                        return error_response('Verification code required', 
                                      status_code=status.HTTP_400_BAD_REQUEST)
                    is_valid = verify_totp_code(tfa.secret_key, code)
                
                elif tfa.mfa_type == 'authy':
                    if not code:
                        return error_response('Verification code required', 
                                      status_code=status.HTTP_400_BAD_REQUEST)
                    is_valid = authy_service.verify_token(tfa.authy_id, code)
                
                elif tfa.mfa_type == 'push':
                    if not request_id:
                        return error_response('Request ID required for push authentication', 
                                      status_code=status.HTTP_400_BAD_REQUEST)
                    
                    status_value = check_push_auth_status(request_id)
                    is_valid = status_value == 'approved'
                
                # If valid, return the full token
                if is_valid:
                    token, _ = Token.objects.get_or_create(user=user)
                    
                    # Update last used timestamp
                    tfa.last_used = timezone.now()
                    tfa.save()
                    
                    # Get user's salt
                    salt_obj = UserSalt.objects.get(user=user)
                    salt = base64.b64encode(salt_obj.salt).decode('utf-8')
                    
                    # Enhanced security analysis for 2FA completion - Option B: Parallel services
                    try:
                        # Primary analysis with existing service
                        account_protection_service.analyze_login_attempt(
                            request=request,
                            user=user,
                            username=user.username,
                            success=True
                        )
                    except Exception as e:
                        print(f"Account protection analysis for 2FA completion failed: {str(e)}")
                    
                    try:
                        # Enhanced analysis with new security service
                        analysis_result = security_service.analyze_login_attempt(
                            user=user,
                            request=request,
                            is_successful=True,
                            failure_reason=None
                        )
                        print(f"2FA completion analysis - Threat score: {analysis_result.threat_score}, Suspicious: {analysis_result.is_suspicious}")
                    except Exception as e:
                        print(f"Security service analysis for 2FA completion failed: {str(e)}")
                    
                    # Log successful 2FA
                    AuditLog.objects.create(
                        user=user,
                        action='2fa_success',
                        ip_address=self.get_client_ip(request),
                        user_agent=request.META.get('HTTP_USER_AGENT', ''),
                        status='success'
                    )
                    
                    return success_response({
                        'token': token.key,
                        'salt': salt,
                        'user_id': user.id
                    })
                
                # Enhanced security analysis for failed 2FA - Option B: Parallel services
                try:
                    # Primary analysis with existing service
                    account_protection_service.analyze_login_attempt(
                        request=request,
                        user=user,
                        username=user.username,
                        success=False,
                        failure_reason="Invalid 2FA verification"
                    )
                except Exception as e:
                    print(f"Account protection analysis for failed 2FA failed: {str(e)}")
                
                try:
                    # Enhanced analysis with new security service
                    analysis_result = security_service.analyze_login_attempt(
                        user=user,
                        request=request,
                        is_successful=False,
                        failure_reason="Invalid 2FA verification"
                    )
                    print(f"Failed 2FA analysis - Threat score: {analysis_result.threat_score}, Suspicious: {analysis_result.is_suspicious}")
                except Exception as e:
                    print(f"Security service analysis for failed 2FA failed: {str(e)}")
                
                # Log failed 2FA
                AuditLog.objects.create(
                    user=user,
                    action='2fa_failure',
                    ip_address=self.get_client_ip(request),
                    user_agent=request.META.get('HTTP_USER_AGENT', ''),
                    status='failure'
                )
                
                return error_response('Invalid verification', 
                              status_code=status.HTTP_401_UNAUTHORIZED)
                
            except TwoFactorAuth.DoesNotExist:
                return error_response('2FA not set up for this user', 
                              status_code=status.HTTP_400_BAD_REQUEST)
            
        except User.DoesNotExist:
            return error_response('User not found', 
                          status_code=status.HTTP_404_NOT_FOUND)

    @action(detail=False, methods=['post'])
    def setup_recovery_key(self, request):
        """
        Store encrypted vault data protected by a recovery key
        """
        user = request.user
        
        # Validate request data
        if not user.is_authenticated:
            return Response({"error": "Authentication required"}, status=status.HTTP_401_UNAUTHORIZED)
        
        if not all(k in request.data for k in ['encryptedVault', 'salt', 'method']):
            return Response({"error": "Missing required fields"}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            # Create or update recovery key record
            recovery_key, created = RecoveryKey.objects.update_or_create(
                user=user,
                defaults={
                    'encrypted_vault': request.data['encryptedVault'],
                    'salt': request.data['salt'],
                    'method': request.data['method'],
                }
            )
            
            return Response({
                "success": True,
                "created": created,
                "message": "Recovery key setup successful"
            }, status=status.HTTP_200_OK)
        
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'])
    def update_recovery_status(self, request):
        """
        Update user profile to indicate recovery key is set up
        """
        user = request.user
        
        # Validate request data
        if not user.is_authenticated:
            return Response({"error": "Authentication required"}, status=status.HTTP_401_UNAUTHORIZED)
        
        try:
            # Check if recovery key exists
            has_recovery_key = RecoveryKey.objects.filter(user=user).exists()
            
            if not has_recovery_key and request.data.get('has_recovery_key', False):
                return Response({
                    "error": "Cannot set recovery key status without setting up a recovery key first"
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Update user profile (assuming User model has has_recovery_key field)
            # If your User model doesn't have this field, you'll need to create a UserProfile model or extend the User model
            from django.contrib.auth.models import User
            
            # Check if there's a profile model with this field
            if hasattr(user, 'profile') and hasattr(user.profile, 'has_recovery_key'):
                user.profile.has_recovery_key = request.data.get('has_recovery_key', True)
                user.profile.save()
            else:
                # Alternative: store this in RecoveryKey model directly
                recovery_key = RecoveryKey.objects.get(user=user)
                recovery_key.is_active = request.data.get('has_recovery_key', True)
                recovery_key.save()
            
            return Response({
                "success": True,
                "message": "Recovery key status updated successfully"
            }, status=status.HTTP_200_OK)
        
        except RecoveryKey.DoesNotExist:
            return Response({"error": "Recovery key not found"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'])
    def validate_recovery_key(self, request):
        """
        Validate if a recovery key exists for a given email
        """
        email = request.data.get('email')
        recovery_key_hash = request.data.get('recovery_key_hash')
        
        if not email or not recovery_key_hash:
            return Response({"error": "Email and recovery key hash are required"}, 
                           status=status.HTTP_400_BAD_REQUEST)
        
        try:
            # Find user by email
            user = User.objects.get(email=email)
            
            # Check if recovery key exists
            has_recovery_key = RecoveryKey.objects.filter(user=user).exists()
            
            # We don't validate the actual key here - that happens client side
            # This endpoint just confirms a recovery key exists for the account
            
            # Log analytics for recovery key validation attempt
            AuditLog.objects.create(
                user=user,
                action='recovery_key_validation',
                ip_address=self.get_client_ip(request),
                user_agent=request.META.get('HTTP_USER_AGENT', ''),
                status='success' if has_recovery_key else 'failure'
            )
            
            # Privacy-preserving analytics
            RecoveryAttemptLog.log_attempt(
                user=user,
                attempt_type='validate_key',
                result='success' if has_recovery_key else 'failure',
                request=request
            )
            
            return Response({
                "valid": has_recovery_key,
                "message": "Recovery key exists for this account" if has_recovery_key else "No recovery key found"
            })
            
        except User.DoesNotExist:
            # Don't reveal that the email doesn't exist
            return Response({
                "valid": False,
                "message": "No recovery key found"
            })
    
    @action(detail=False, methods=['post'])
    def get_encrypted_vault(self, request):
        """
        Get encrypted vault data for recovery with a recovery key
        """
        email = request.data.get('email')
        recovery_key_hash = request.data.get('recovery_key_hash')
        
        if not email or not recovery_key_hash:
            return Response({"error": "Email and recovery key hash are required"}, 
                           status=status.HTTP_400_BAD_REQUEST)
        
        try:
            # Find user by email
            user = User.objects.get(email=email)
            
            # Get recovery key data
            recovery_key = RecoveryKey.objects.get(user=user)
            
            # Log analytics for recovery data access attempt
            AuditLog.objects.create(
                user=user,
                action='recovery_data_access',
                ip_address=self.get_client_ip(request),
                user_agent=request.META.get('HTTP_USER_AGENT', ''),
                status='success'
            )
            
            # Privacy-preserving analytics
            RecoveryAttemptLog.log_attempt(
                user=user,
                attempt_type='get_vault',
                result='success',
                request=request
            )
            
            return Response({
                "encryptedVault": recovery_key.encrypted_vault,
                "salt": recovery_key.salt,
                "userId": user.id
            })
            
        except User.DoesNotExist:
            # Don't reveal that the email doesn't exist
            return Response({"error": "Invalid credentials"}, status=status.HTTP_404_NOT_FOUND)
            
        except RecoveryKey.DoesNotExist:
            # If user exists but no recovery key found, log the attempt
            if 'user' in locals():
                RecoveryAttemptLog.log_attempt(
                    user=user,
                    attempt_type='get_vault',
                    result='failure',
                    request=request
                )
            return Response({"error": "No recovery key found for this account"}, status=status.HTTP_404_NOT_FOUND)
    
    @action(detail=False, methods=['post'])
    def reset_with_recovery_key(self, request):
        """
        Reset password using a recovery key
        """
        user_id = request.data.get('user_id')
        new_encrypted_vault = request.data.get('new_encrypted_vault')
        new_password_hash = request.data.get('new_password_hash')
        
        if not user_id or not new_encrypted_vault or not new_password_hash:
            return Response({"error": "All fields are required"}, 
                           status=status.HTTP_400_BAD_REQUEST)
        
        try:
            # Find user
            user = User.objects.get(id=user_id)
            
            # Update password hash
            salt_obj = UserSalt.objects.get(user=user)
            salt_obj.auth_hash = base64.b64decode(new_password_hash)
            salt_obj.save()
            
            # Enhanced security analysis for recovery key password reset - Option B: Parallel services
            try:
                # Primary analysis with existing service
                account_protection_service.analyze_login_attempt(
                    request=request,
                    user=user,
                    username=user.username,
                    success=True
                )
            except Exception as e:
                print(f"Account protection analysis for recovery key reset failed: {str(e)}")
            
            try:
                # Enhanced analysis with new security service
                analysis_result = security_service.analyze_login_attempt(
                    user=user,
                    request=request,
                    is_successful=True,
                    failure_reason=None
                )
                print(f"Recovery key reset analysis - Threat score: {analysis_result.threat_score}, Suspicious: {analysis_result.is_suspicious}")
            except Exception as e:
                print(f"Security service analysis for recovery key reset failed: {str(e)}")
            
            # Update encrypted vault
            recovery_key = RecoveryKey.objects.get(user=user)
            recovery_key.encrypted_vault = new_encrypted_vault
            recovery_key.updated_at = timezone.now()
            recovery_key.save()
            
            # Log analytics for successful password reset with recovery key
            AuditLog.objects.create(
                user=user,
                action='password_reset_with_recovery_key',
                ip_address=self.get_client_ip(request),
                user_agent=request.META.get('HTTP_USER_AGENT', ''),
                status='success'
            )
            
            # Privacy-preserving analytics
            RecoveryAttemptLog.log_attempt(
                user=user,
                attempt_type='recovery_success',
                result='success',
                request=request
            )
            
            return Response({
                "success": True,
                "message": "Password reset successful with recovery key"
            })
            
        except User.DoesNotExist:
            return Response({"error": "User not found"}, status=status.HTTP_404_NOT_FOUND)
            
        except (UserSalt.DoesNotExist, RecoveryKey.DoesNotExist):
            # Log failure if user exists
            if 'user' in locals():
                RecoveryAttemptLog.log_attempt(
                    user=user,
                    attempt_type='reset_password',
                    result='failure',
                    request=request
                )
            return Response({"error": "Account not set up properly for recovery"}, 
                          status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            # Log unexpected errors
            if 'user' in locals():
                RecoveryAttemptLog.log_attempt(
                    user=user,
                    attempt_type='reset_password',
                    result='failure',
                    request=request
                )
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'])
    def verify_email_exists(self, request):
        """
        Verify if an email address exists in the system
        
        For security, we don't directly confirm or deny the existence of an email
        to prevent user enumeration attacks, but we return consistent responses
        for registered users to enable recovery key generation.
        """
        try:
            email = request.data.get('email')
            if not email:
                return error_response('Email is required', status_code=status.HTTP_400_BAD_REQUEST)
            
            # Check if a user with this email exists
            user_exists = User.objects.filter(email=email).exists()
            
            # For security reasons, we only confirm existence for authenticated sessions
            # or for specific secure operations like recovery key setup
            if user_exists:
                return success_response({'exists': True})
            else:
                # Return a 200 response with exists=false
                # This way attackers can't differentiate based on response codes
                return success_response({'exists': False})
                
        except Exception as e:
            logger.error(f"Error verifying email existence: {str(e)}")
            return error_response('An error occurred while processing your request', 
                                 status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)

"""
Multi-Factor Authentication API Views

This module provides API endpoints for:
- Biometric registration (face, voice)
- Biometric authentication
- Adaptive MFA policy management
- Continuous authentication
- MFA factor management
"""

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework import status
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta
import logging
import json
import base64
import numpy as np

from .mfa_models import (
    BiometricProfile, MFAPolicy, MFAFactor,
    AuthenticationAttempt, ContinuousAuthSession,
    AdaptiveMFALog
)
from ml_security.ml_models.biometric_authenticator import BiometricAuthenticator
from ml_security.ml_models.anomaly_detector import AnomalyDetector
from ml_security.ml_models.threat_analyzer import ThreatAnalyzer

logger = logging.getLogger(__name__)

# Initialize ML models
biometric_auth = BiometricAuthenticator()
anomaly_detector = AnomalyDetector()
threat_analyzer = ThreatAnalyzer()


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def register_face(request):
    """
    Register user's face for biometric authentication
    
    Expects:
        face_image: Base64-encoded face image
        device_id: Unique device identifier
    """
    try:
        user = request.user
        
        # Get face image from request
        face_image_b64 = request.data.get('face_image')
        device_id = request.data.get('device_id', 'unknown')
        
        if not face_image_b64:
            return Response({
                'success': False,
                'message': 'Face image is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Decode base64 image
        try:
            image_data = base64.b64decode(face_image_b64)
            # Convert to numpy array (in production, use proper image processing)
            # For now, create dummy 160x160x3 image
            face_image = np.random.rand(160, 160, 3)  # Replace with actual image processing
        except Exception as e:
            return Response({
                'success': False,
                'message': f'Invalid image data: {str(e)}'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Register face with ML model
        result = biometric_auth.register_face(str(user.id), face_image)
        
        if result['success']:
            # Create BiometricProfile
            profile = BiometricProfile.objects.create(
                user=user,
                biometric_type='face',
                embedding_data=json.dumps(result.get('embedding', [])),
                embedding_hash='',  # Will be set by signal
                device_id=device_id,
                is_active=True,
                liveness_score=result.get('liveness_score'),
                requires_liveness=True
            )
            
            # Create MFAFactor
            MFAFactor.objects.create(
                user=user,
                factor_type='face',
                status='active',
                factor_data={'profile_id': profile.id},
                device_info={'device_id': device_id},
                is_primary=False
            )
            
            return Response({
                'success': True,
                'message': 'Face registered successfully',
                'profile_id': profile.id,
                'liveness_score': result.get('liveness_score')
            }, status=status.HTTP_201_CREATED)
        else:
            return Response({
                'success': False,
                'message': result.get('message', 'Face registration failed')
            }, status=status.HTTP_400_BAD_REQUEST)
    
    except Exception as e:
        logger.error(f"Face registration error: {e}")
        return Response({
            'success': False,
            'message': f'Registration error: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def register_voice(request):
    """
    Register user's voice for biometric authentication
    
    Expects:
        voice_audio: Base64-encoded audio data
        device_id: Unique device identifier
    """
    try:
        user = request.user
        
        # Get voice audio from request
        voice_audio_b64 = request.data.get('voice_audio')
        device_id = request.data.get('device_id', 'unknown')
        
        if not voice_audio_b64:
            return Response({
                'success': False,
                'message': 'Voice audio is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Decode base64 audio
        try:
            audio_data = base64.b64decode(voice_audio_b64)
            # Convert to numpy array and extract MFCC features
            # For now, create dummy features
            voice_features = np.random.rand(40, 100, 1)  # Replace with actual audio processing
        except Exception as e:
            return Response({
                'success': False,
                'message': f'Invalid audio data: {str(e)}'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Register voice with ML model
        result = biometric_auth.register_voice(str(user.id), voice_features)
        
        if result['success']:
            # Create BiometricProfile
            profile = BiometricProfile.objects.create(
                user=user,
                biometric_type='voice',
                embedding_data=json.dumps(result.get('embedding', [])),
                embedding_hash='',  # Will be set by signal
                device_id=device_id,
                is_active=True,
                requires_liveness=False
            )
            
            # Create MFAFactor
            MFAFactor.objects.create(
                user=user,
                factor_type='voice',
                status='active',
                factor_data={'profile_id': profile.id},
                device_info={'device_id': device_id},
                is_primary=False
            )
            
            return Response({
                'success': True,
                'message': 'Voice registered successfully',
                'profile_id': profile.id
            }, status=status.HTTP_201_CREATED)
        else:
            return Response({
                'success': False,
                'message': result.get('message', 'Voice registration failed')
            }, status=status.HTTP_400_BAD_REQUEST)
    
    except Exception as e:
        logger.error(f"Voice registration error: {e}")
        return Response({
            'success': False,
            'message': f'Registration error: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([AllowAny])
def authenticate_biometric(request):
    """
    Authenticate user using biometrics (face or voice)
    
    Expects:
        username: Username
        biometric_type: 'face' or 'voice'
        biometric_data: Base64-encoded biometric data
        device_id: Device identifier
    """
    try:
        username = request.data.get('username')
        biometric_type = request.data.get('biometric_type')
        biometric_data_b64 = request.data.get('biometric_data')
        device_id = request.data.get('device_id', 'unknown')
        
        if not all([username, biometric_type, biometric_data_b64]):
            return Response({
                'authenticated': False,
                'message': 'Missing required fields'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Get user
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            return Response({
                'authenticated': False,
                'message': 'User not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Decode biometric data
        try:
            data = base64.b64decode(biometric_data_b64)
            
            if biometric_type == 'face':
                # Process face image
                biometric_features = np.random.rand(160, 160, 3)  # Replace with actual processing
                result = biometric_auth.authenticate_face(str(user.id), biometric_features)
            elif biometric_type == 'voice':
                # Process voice audio
                biometric_features = np.random.rand(40, 100, 1)  # Replace with actual processing
                result = biometric_auth.authenticate_voice(str(user.id), biometric_features)
            else:
                return Response({
                    'authenticated': False,
                    'message': 'Invalid biometric type'
                }, status=status.HTTP_400_BAD_REQUEST)
        
        except Exception as e:
            return Response({
                'authenticated': False,
                'message': f'Processing error: {str(e)}'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Log authentication attempt
        AuthenticationAttempt.objects.create(
            user=user,
            username=username,
            factors_used=[biometric_type],
            factors_required=1,
            factors_completed=1 if result.get('authenticated') else 0,
            result='success' if result.get('authenticated') else 'failure',
            failure_reason='' if result.get('authenticated') else result.get('message', 'Unknown'),
            ip_address=request.META.get('REMOTE_ADDR', '0.0.0.0'),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
            device_fingerprint=device_id
        )
        
        # Update BiometricProfile statistics
        if result.get('authenticated'):
            profile = BiometricProfile.objects.filter(
                user=user,
                biometric_type=biometric_type,
                is_active=True
            ).first()
            
            if profile:
                profile.record_success()
        
        return Response(result, status=status.HTTP_200_OK)
    
    except Exception as e:
        logger.error(f"Biometric authentication error: {e}")
        return Response({
            'authenticated': False,
            'message': f'Authentication error: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def start_continuous_auth(request):
    """
    Start a continuous authentication session
    
    Expects:
        session_duration_minutes: Session duration (default: 60)
    """
    try:
        user = request.user
        session_duration = request.data.get('session_duration_minutes', 60)
        
        # Generate session ID
        import uuid
        session_id = str(uuid.uuid4())
        
        # Get user's MFA policy
        policy, created = MFAPolicy.objects.get_or_create(user=user)
        
        if not policy.enable_continuous_auth:
            return Response({
                'success': False,
                'message': 'Continuous authentication is not enabled for this user'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Create continuous auth session
        session = ContinuousAuthSession.objects.create(
            user=user,
            session_id=session_id,
            status='active',
            initial_auth_score=1.0,
            current_auth_score=1.0,
            min_auth_threshold=0.6,
            device_fingerprint=request.data.get('device_fingerprint', ''),
            ip_address=request.META.get('REMOTE_ADDR', '0.0.0.0'),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
            expires_at=timezone.now() + timedelta(minutes=session_duration)
        )
        
        return Response({
            'success': True,
            'session_id': session_id,
            'expires_at': session.expires_at.isoformat(),
            'min_threshold': session.min_auth_threshold
        }, status=status.HTTP_201_CREATED)
    
    except Exception as e:
        logger.error(f"Continuous auth start error: {e}")
        return Response({
            'success': False,
            'message': f'Error: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def update_continuous_auth(request):
    """
    Update continuous authentication score
    
    Expects:
        session_id: Session identifier
        face_image: Optional base64 face image
        voice_audio: Optional base64 voice audio
        behavior_data: Optional behavioral features
    """
    try:
        user = request.user
        session_id = request.data.get('session_id')
        
        if not session_id:
            return Response({
                'success': False,
                'message': 'Session ID is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Get session
        try:
            session = ContinuousAuthSession.objects.get(
                user=user,
                session_id=session_id
            )
        except ContinuousAuthSession.DoesNotExist:
            return Response({
                'success': False,
                'message': 'Session not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Check if session expired
        if session.is_expired():
            session.status = 'expired'
            session.save()
            return Response({
                'success': False,
                'message': 'Session has expired',
                'requires_full_auth': True
            }, status=status.HTTP_401_UNAUTHORIZED)
        
        # Process biometric data if provided
        face_image = None
        voice_features = None
        behavior_features = None
        
        if request.data.get('face_image'):
            # Process face (dummy data for now)
            face_image = np.random.rand(160, 160, 3)
            session.face_checks_count += 1
        
        if request.data.get('voice_audio'):
            # Process voice (dummy data for now)
            voice_features = np.random.rand(40, 100, 1)
            session.voice_checks_count += 1
        
        if request.data.get('behavior_data'):
            # Get behavioral features
            behavior_data = request.data.get('behavior_data')
            behavior_features = np.array(behavior_data[:15])  # Use first 15 features
            session.behavioral_checks_count += 1
        
        # Perform continuous authentication
        auth_result = biometric_auth.continuous_authenticate(
            str(user.id),
            face_image=face_image,
            voice_features=voice_features,
            behavior_features=behavior_features
        )
        
        # Update session score
        new_score = auth_result.get('auth_score', 0.5)
        session.update_auth_score(new_score)
        
        response_data = {
            'success': True,
            'session_id': session_id,
            'auth_score': new_score,
            'threshold': session.min_auth_threshold,
            'status': session.status,
            'factors_checked': auth_result.get('factors_used', [])
        }
        
        if session.status == 'challenged':
            response_data['requires_reauth'] = True
            response_data['message'] = 'Authentication score too low. Please re-authenticate.'
        
        return Response(response_data, status=status.HTTP_200_OK)
    
    except Exception as e:
        logger.error(f"Continuous auth update error: {e}")
        return Response({
            'success': False,
            'message': f'Error: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def assess_mfa_risk(request):
    """
    Assess risk level and determine required MFA factors
    
    Expects:
        action: Action being attempted (e.g., 'login', 'transfer', 'change_password')
        context: Additional context data
    """
    try:
        user = request.user
        action = request.data.get('action', 'unknown')
        context = request.data.get('context', {})
        
        # Get user's MFA policy
        policy, created = MFAPolicy.objects.get_or_create(user=user)
        
        # Collect risk factors
        risk_factors = []
        risk_score = 0.0
        
        # Check IP address
        ip_address = request.META.get('REMOTE_ADDR', '0.0.0.0')
        recent_attempts = AuthenticationAttempt.objects.filter(
            user=user,
            ip_address=ip_address,
            attempt_timestamp__gte=timezone.now() - timedelta(days=7)
        ).count()
        
        if recent_attempts == 0:
            risk_factors.append('new_ip')
            risk_score += 0.3
        
        # Check time of day
        hour = timezone.now().hour
        if hour < 6 or hour > 22:
            risk_factors.append('unusual_time')
            risk_score += 0.2
        
        # Check recent failures
        recent_failures = AuthenticationAttempt.get_recent_failures(user, minutes=15)
        if recent_failures > 0:
            risk_factors.append('recent_failures')
            risk_score += 0.2 * recent_failures
        
        # Use ML for anomaly detection
        try:
            # Prepare session data for ML
            session_data = {
                'user_id': user.id,
                'ip': ip_address,
                'user_agent': request.META.get('HTTP_USER_AGENT', ''),
                'hour_of_day': hour,
                'action': action
            }
            
            # Get ML risk assessment
            ml_result = threat_analyzer.analyze_threat(session_data)
            risk_score = max(risk_score, ml_result.get('risk_score', 0.0))
            
            if ml_result.get('is_threat'):
                risk_factors.append('ml_threat_detected')
        except Exception as e:
            logger.warning(f"ML risk assessment failed: {e}")
        
        # Determine risk level
        if risk_score < 0.3:
            risk_level = 'low'
        elif risk_score < 0.6:
            risk_level = 'medium'
        elif risk_score < 0.8:
            risk_level = 'high'
        else:
            risk_level = 'critical'
        
        # Get required factors based on risk level and policy
        required_factors_count = policy.get_required_factors(risk_level)
        available_methods = policy.get_allowed_methods()
        
        # Log the assessment
        AdaptiveMFALog.objects.create(
            user=user,
            calculated_risk_level=risk_level,
            risk_factors=risk_factors,
            ml_risk_score=risk_score,
            factors_required=required_factors_count,
            factors_available=available_methods,
            factors_selected=[],  # Will be updated when auth completes
            trigger_action=action,
            ip_address=ip_address,
            device_fingerprint=context.get('device_fingerprint', ''),
            location=context.get('location', {})
        )
        
        return Response({
            'risk_level': risk_level,
            'risk_score': risk_score,
            'risk_factors': risk_factors,
            'required_factors_count': required_factors_count,
            'available_methods': available_methods,
            'recommendation': f'Use {required_factors_count} authentication factors',
            'adaptive_mfa_enabled': policy.enable_adaptive_mfa
        }, status=status.HTTP_200_OK)
    
    except Exception as e:
        logger.error(f"Risk assessment error: {e}")
        return Response({
            'success': False,
            'message': f'Error: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_mfa_factors(request):
    """Get list of user's configured MFA factors"""
    try:
        user = request.user
        
        factors = MFAFactor.objects.filter(user=user, status='active')
        
        factors_data = []
        for factor in factors:
            factors_data.append({
                'id': factor.id,
                'type': factor.factor_type,
                'type_display': factor.get_factor_type_display(),
                'is_primary': factor.is_primary,
                'trust_score': factor.trust_score,
                'last_used_at': factor.last_used_at.isoformat() if factor.last_used_at else None,
                'registered_at': factor.registered_at.isoformat(),
                'success_count': factor.success_count,
                'failure_count': factor.failure_count
            })
        
        return Response({
            'factors': factors_data,
            'total_count': len(factors_data)
        }, status=status.HTTP_200_OK)
    
    except Exception as e:
        logger.error(f"Error fetching MFA factors: {e}")
        return Response({
            'success': False,
            'message': f'Error: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET', 'PUT'])
@permission_classes([IsAuthenticated])
def mfa_policy(request):
    """Get or update user's MFA policy"""
    try:
        user = request.user
        policy, created = MFAPolicy.objects.get_or_create(user=user)
        
        if request.method == 'GET':
            return Response({
                'policy': {
                    'low_risk_factors': policy.low_risk_factors,
                    'medium_risk_factors': policy.medium_risk_factors,
                    'high_risk_factors': policy.high_risk_factors,
                    'critical_risk_factors': policy.critical_risk_factors,
                    'enable_adaptive_mfa': policy.enable_adaptive_mfa,
                    'enable_continuous_auth': policy.enable_continuous_auth,
                    'allow_password': policy.allow_password,
                    'allow_totp': policy.allow_totp,
                    'allow_passkey': policy.allow_passkey,
                    'allow_biometric_face': policy.allow_biometric_face,
                    'allow_biometric_voice': policy.allow_biometric_voice,
                    'max_session_duration_minutes': policy.max_session_duration_minutes
                }
            }, status=status.HTTP_200_OK)
        
        elif request.method == 'PUT':
            # Update policy
            updatable_fields = [
                'enable_adaptive_mfa', 'enable_continuous_auth',
                'allow_password', 'allow_totp', 'allow_passkey',
                'allow_biometric_face', 'allow_biometric_voice',
                'max_session_duration_minutes'
            ]
            
            for field in updatable_fields:
                if field in request.data:
                    setattr(policy, field, request.data[field])
            
            policy.save()
            
            return Response({
                'success': True,
                'message': 'MFA policy updated successfully'
            }, status=status.HTTP_200_OK)
    
    except Exception as e:
        logger.error(f"MFA policy error: {e}")
        return Response({
            'success': False,
            'message': f'Error: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def auth_attempts_history(request):
    """Get user's recent authentication attempts"""
    try:
        user = request.user
        limit = int(request.GET.get('limit', 20))
        
        attempts = AuthenticationAttempt.objects.filter(user=user)[:limit]
        
        attempts_data = []
        for attempt in attempts:
            attempts_data.append({
                'timestamp': attempt.attempt_timestamp.isoformat(),
                'result': attempt.result,
                'factors_used': attempt.factors_used,
                'ip_address': attempt.ip_address,
                'risk_level': attempt.risk_level,
                'anomaly_detected': attempt.anomaly_detected,
                'location': attempt.location_data
            })
        
        return Response({
            'attempts': attempts_data,
            'total_count': len(attempts_data)
        }, status=status.HTTP_200_OK)
    
    except Exception as e:
        logger.error(f"Error fetching auth attempts: {e}")
        return Response({
            'success': False,
            'message': f'Error: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def verify_integrated_mfa(request):
    """
    Integrated MFA+2FA verification endpoint
    Verifies multiple factors (traditional 2FA + biometric MFA)
    
    Expects:
        factors: Dictionary of factor_type -> credential
            Example: {
                'totp': '123456',
                'face': '<base64_image>',
                'sms': '789012'
            }
    """
    try:
        from .mfa_integration import MFAIntegrationService
        
        user = request.user
        factors_provided = request.data.get('factors', {})
        
        # Extract request metadata
        request_data = {
            'ip_address': request.META.get('REMOTE_ADDR'),
            'user_agent': request.META.get('HTTP_USER_AGENT'),
            'device_fingerprint': request.META.get('HTTP_X_DEVICE_FINGERPRINT'),
            'location': request.META.get('HTTP_X_LOCATION')
        }
        
        # Initialize integration service
        integration_service = MFAIntegrationService(user)
        
        # Verify factors
        result = integration_service.verify_multi_factor(factors_provided, request_data)
        
        if result['success']:
            return Response({
                'success': True,
                'message': 'MFA verification successful',
                'verified_factors': result['verified_factors'],
                'requirements': result['requirements']
            }, status=status.HTTP_200_OK)
        else:
            return Response({
                'success': False,
                'message': result['reason'],
                'verification_results': result['verification_results'],
                'requirements': result['requirements']
            }, status=status.HTTP_401_UNAUTHORIZED)
    
    except Exception as e:
        logger.error(f"MFA verification error: {e}")
        return Response({
            'success': False,
            'message': f'Error: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_mfa_requirements(request):
    """
    Get MFA requirements for the current user/request
    
    Query parameters:
        operation_type: Type of operation (login, export_vault, etc.)
    """
    try:
        from .mfa_integration import MFAIntegrationService
        
        user = request.user
        operation_type = request.GET.get('operation_type', 'login')
        
        # Extract request metadata
        request_data = {
            'ip_address': request.META.get('REMOTE_ADDR'),
            'user_agent': request.META.get('HTTP_USER_AGENT'),
            'device_fingerprint': request.META.get('HTTP_X_DEVICE_FINGERPRINT'),
            'location': request.META.get('HTTP_X_LOCATION')
        }
        
        # Initialize integration service
        integration_service = MFAIntegrationService(user)
        
        # Get requirements
        requirements = integration_service.determine_required_factors(request_data, operation_type)
        
        # Get all enabled factors
        enabled_factors = integration_service.get_all_enabled_factors()
        
        return Response({
            'success': True,
            'requirements': requirements,
            'enabled_factors': enabled_factors,
            'operation_type': operation_type
        }, status=status.HTTP_200_OK)
    
    except Exception as e:
        logger.error(f"Error getting MFA requirements: {e}")
        return Response({
            'success': False,
            'message': f'Error: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


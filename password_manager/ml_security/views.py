"""
ML Security API Views

Provides REST API endpoints for all ML-based security features:
- Password strength prediction
- Anomaly detection
- Threat analysis
- Behavior profiling
"""

from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.throttling import UserRateThrottle, AnonRateThrottle
from rest_framework.response import Response
from rest_framework import status
from django.contrib.auth.models import User
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
import logging
import hashlib
import json

from .ml_models import get_model
from .models import (
    PasswordStrengthPrediction,
    UserBehaviorProfile,
    AnomalyDetection,
    ThreatPrediction,
    MLModelMetadata
)
from password_manager.api_utils import success_response, error_response

logger = logging.getLogger(__name__)


class MLSecurityThrottle(UserRateThrottle):
    """Custom throttle for ML security endpoints"""
    rate = '100/hour'


# ============================================================================
# PASSWORD STRENGTH PREDICTION
# ============================================================================

@api_view(['POST'])
@permission_classes([AllowAny])  # Allow for signup flow
@throttle_classes([AnonRateThrottle, MLSecurityThrottle])
def predict_password_strength(request):
    """
    Predict password strength using LSTM model
    
    POST Data:
    {
        "password": "string",
        "save_prediction": boolean (optional, default: false)
    }
    
    Returns:
    {
        "success": true,
        "strength": "strong",
        "confidence": 0.92,
        "features": {...},
        "recommendations": [...]
    }
    """
    try:
        password = request.data.get('password')
        save_prediction = request.data.get('save_prediction', False)
        
        if not password:
            return error_response("Password is required", status_code=status.HTTP_400_BAD_REQUEST)
        
        # Get password strength model
        model = get_model('password_strength')
        if model is None:
            return error_response(
                "Password strength model not available",
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE
            )
        
        # Make prediction
        prediction = model.predict(password)
        
        # Save prediction if requested and user is authenticated
        if save_prediction and request.user.is_authenticated:
            # Create hash of password (for deduplication, not storage)
            password_hash = hashlib.sha256(password.encode()).hexdigest()
            
            PasswordStrengthPrediction.objects.create(
                user=request.user,
                password_hash=password_hash,
                strength=prediction['strength'],
                confidence_score=prediction['confidence'],
                entropy=prediction['features']['entropy'],
                character_diversity=prediction['features']['character_diversity'],
                length=prediction['features']['length'],
                has_numbers=prediction['features']['has_numbers'],
                has_uppercase=prediction['features']['has_uppercase'],
                has_lowercase=prediction['features']['has_lowercase'],
                has_special=prediction['features']['has_special'],
                contains_common_patterns=prediction['features']['contains_common_patterns'],
                guessability_score=prediction['features']['guessability_score']
            )
        
        return success_response(prediction)
    
    except Exception as e:
        logger.error(f"Error in password strength prediction: {str(e)}")
        return error_response(
            "Failed to predict password strength",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@throttle_classes([MLSecurityThrottle])
def get_password_strength_history(request):
    """
    Get user's password strength prediction history
    
    Returns:
    {
        "success": true,
        "predictions": [...]
    }
    """
    try:
        predictions = PasswordStrengthPrediction.objects.filter(
            user=request.user
        ).order_by('-created_at')[:50]
        
        data = [{
            'id': p.id,
            'strength': p.strength,
            'confidence': p.confidence_score,
            'entropy': p.entropy,
            'length': p.length,
            'created_at': p.created_at.isoformat()
        } for p in predictions]
        
        return success_response({'predictions': data})
    
    except Exception as e:
        logger.error(f"Error fetching password history: {str(e)}")
        return error_response("Failed to fetch password history")


# ============================================================================
# ANOMALY DETECTION
# ============================================================================

@api_view(['POST'])
@permission_classes([IsAuthenticated])
@throttle_classes([MLSecurityThrottle])
def detect_session_anomaly(request):
    """
    Detect anomalies in current user session
    
    POST Data:
    {
        "session_data": {
            "session_duration": 300,
            "typing_speed": 45.5,
            "vault_accesses": 5,
            "device_consistency": 0.95,
            "location_consistency": 0.88,
            ...
        }
    }
    
    Returns:
    {
        "success": true,
        "is_anomaly": false,
        "anomaly_score": 0.15,
        "severity": "low",
        "recommended_action": "monitor",
        ...
    }
    """
    try:
        session_data = request.data.get('session_data', {})
        
        # Get anomaly detector model
        detector = get_model('anomaly_detector')
        if detector is None:
            return error_response(
                "Anomaly detector not available",
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE
            )
        
        # Get user behavior profile
        try:
            profile = UserBehaviorProfile.objects.get(user=request.user)
            user_profile = {
                'typical_login_hours': profile.typical_login_hours,
                'typical_login_days': profile.typical_login_days,
                'avg_session_duration': profile.avg_session_duration,
                'common_locations': profile.common_locations,
                'common_ip_ranges': profile.common_ip_ranges,
            }
        except UserBehaviorProfile.DoesNotExist:
            user_profile = None
        
        # Detect anomaly
        result = detector.detect_anomaly(session_data, user_profile)
        
        # Save anomaly if detected
        if result['is_anomaly'] and result['severity'] in ['high', 'critical']:
            # Get client info
            ip_address = request.META.get('REMOTE_ADDR', '')
            user_agent = request.META.get('HTTP_USER_AGENT', '')
            session_id = request.session.session_key or 'unknown'
            
            AnomalyDetection.objects.create(
                user=request.user,
                session_id=session_id,
                anomaly_type=result.get('anomaly_type', 'multiple'),
                severity=result['severity'],
                anomaly_score=result['anomaly_score'],
                confidence=result['confidence'],
                ip_address=ip_address,
                user_agent=user_agent,
                expected_values=user_profile or {},
                actual_values=session_data,
                deviations=result.get('contributing_factors', []),
                action_taken=result['recommended_action']
            )
        
        return success_response(result)
    
    except Exception as e:
        logger.error(f"Error in anomaly detection: {str(e)}")
        return error_response("Failed to detect anomalies")


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@throttle_classes([MLSecurityThrottle])
def get_user_behavior_profile(request):
    """
    Get or create user behavior profile
    
    Returns:
    {
        "success": true,
        "profile": {...}
    }
    """
    try:
        profile, created = UserBehaviorProfile.objects.get_or_create(
            user=request.user
        )
        
        data = {
            'typical_login_hours': profile.typical_login_hours,
            'typical_login_days': profile.typical_login_days,
            'avg_session_duration': profile.avg_session_duration,
            'common_locations': profile.common_locations,
            'common_devices': profile.common_devices,
            'last_trained': profile.last_trained.isoformat() if profile.last_trained else None,
            'samples_used': profile.samples_used,
        }
        
        return success_response({'profile': data, 'created': created})
    
    except Exception as e:
        logger.error(f"Error fetching behavior profile: {str(e)}")
        return error_response("Failed to fetch behavior profile")


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@throttle_classes([MLSecurityThrottle])
def update_behavior_profile(request):
    """
    Update user behavior profile with new session data
    
    POST Data:
    {
        "session_data": {...}
    }
    """
    try:
        session_data = request.data.get('session_data', {})
        
        profile, created = UserBehaviorProfile.objects.get_or_create(
            user=request.user
        )
        
        # Update profile fields based on session data
        # This is a simplified update - in production, you'd use more sophisticated
        # averaging and statistical methods
        
        if 'login_hour' in session_data:
            hours = profile.typical_login_hours or []
            if session_data['login_hour'] not in hours:
                hours.append(session_data['login_hour'])
                profile.typical_login_hours = hours[:24]  # Keep last 24 unique hours
        
        if 'login_day' in session_data:
            days = profile.typical_login_days or []
            if session_data['login_day'] not in days:
                days.append(session_data['login_day'])
                profile.typical_login_days = days[:7]  # Keep last 7 unique days
        
        if 'session_duration' in session_data:
            # Running average
            current_avg = profile.avg_session_duration or 0
            samples = profile.samples_used or 0
            new_avg = (current_avg * samples + session_data['session_duration']) / (samples + 1)
            profile.avg_session_duration = new_avg
        
        profile.samples_used = (profile.samples_used or 0) + 1
        profile.save()
        
        return success_response({'message': 'Profile updated successfully'})
    
    except Exception as e:
        logger.error(f"Error updating behavior profile: {str(e)}")
        return error_response("Failed to update behavior profile")


# ============================================================================
# THREAT ANALYSIS
# ============================================================================

@api_view(['POST'])
@permission_classes([IsAuthenticated])
@throttle_classes([MLSecurityThrottle])
def analyze_threat(request):
    """
    Analyze session for threats using hybrid CNN-LSTM model
    
    POST Data:
    {
        "session_data": {...},
        "behavior_data": {...}
    }
    
    Returns:
    {
        "success": true,
        "threat_detected": false,
        "threat_type": "benign",
        "threat_score": 0.12,
        "risk_level": 12,
        "recommended_action": "allow",
        ...
    }
    """
    try:
        session_data = request.data.get('session_data', {})
        behavior_data = request.data.get('behavior_data', {})
        
        # Get threat analyzer model
        analyzer = get_model('threat_analyzer')
        if analyzer is None:
            return error_response(
                "Threat analyzer not available",
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE
            )
        
        # Analyze threat
        result = analyzer.analyze_threat(
            session_data,
            str(request.user.id),
            behavior_data
        )
        
        # Save threat prediction if significant
        if result['threat_detected'] or result['risk_level'] >= 50:
            ip_address = request.META.get('REMOTE_ADDR', '')
            session_id = request.session.session_key or 'unknown'
            device_fingerprint = request.META.get('HTTP_X_DEVICE_FINGERPRINT', '')
            
            ThreatPrediction.objects.create(
                user=request.user,
                session_id=session_id,
                threat_type=result['threat_type'],
                threat_score=result['threat_score'],
                risk_level=result['risk_level'],
                sequence_features=behavior_data,
                spatial_features=session_data,
                temporal_features=result.get('temporal_analysis', {}),
                cnn_output=result.get('spatial_analysis', {}),
                lstm_output=result.get('temporal_analysis', {}),
                final_prediction={'result': result},
                ip_address=ip_address,
                device_fingerprint=device_fingerprint,
                recommended_action=result['recommended_action']
            )
        
        return success_response(result)
    
    except Exception as e:
        logger.error(f"Error in threat analysis: {str(e)}")
        return error_response("Failed to analyze threat")


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@throttle_classes([MLSecurityThrottle])
def get_threat_history(request):
    """
    Get user's threat prediction history
    
    Query Parameters:
    - limit: Number of records to return (default: 50)
    - severity: Filter by severity (low/medium/high/critical)
    
    Returns:
    {
        "success": true,
        "threats": [...]
    }
    """
    try:
        limit = int(request.query_params.get('limit', 50))
        
        threats = ThreatPrediction.objects.filter(
            user=request.user
        ).order_by('-created_at')[:limit]
        
        data = [{
            'id': t.id,
            'threat_type': t.threat_type,
            'threat_score': t.threat_score,
            'risk_level': t.risk_level,
            'recommended_action': t.recommended_action,
            'created_at': t.created_at.isoformat()
        } for t in threats]
        
        return success_response({'threats': data})
    
    except Exception as e:
        logger.error(f"Error fetching threat history: {str(e)}")
        return error_response("Failed to fetch threat history")


# ============================================================================
# ML MODEL INFORMATION
# ============================================================================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_ml_model_info(request):
    """
    Get information about active ML models
    
    Returns:
    {
        "success": true,
        "models": [...]
    }
    """
    try:
        models = MLModelMetadata.objects.filter(is_active=True)
        
        data = [{
            'model_type': m.model_type,
            'version': m.version,
            'accuracy': m.accuracy,
            'precision': m.precision,
            'recall': m.recall,
            'f1_score': m.f1_score,
            'training_date': m.training_date.isoformat(),
            'training_samples': m.training_samples
        } for m in models]
        
        return success_response({'models': data})
    
    except Exception as e:
        logger.error(f"Error fetching ML model info: {str(e)}")
        return error_response("Failed to fetch ML model information")


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@throttle_classes([MLSecurityThrottle])
def batch_analyze_session(request):
    """
    Perform all ML analyses on a session (password strength, anomaly, threat)
    
    POST Data:
    {
        "password": "string" (optional),
        "session_data": {...},
        "behavior_data": {...}
    }
    
    Returns:
    {
        "success": true,
        "password_strength": {...},
        "anomaly_detection": {...},
        "threat_analysis": {...}
    }
    """
    try:
        result = {}
        
        # Password strength analysis (if provided)
        password = request.data.get('password')
        if password:
            model = get_model('password_strength')
            if model:
                result['password_strength'] = model.predict(password)
        
        # Anomaly detection
        session_data = request.data.get('session_data', {})
        if session_data:
            detector = get_model('anomaly_detector')
            if detector:
                try:
                    profile = UserBehaviorProfile.objects.get(user=request.user)
                    user_profile = {'typical_login_hours': profile.typical_login_hours}
                except UserBehaviorProfile.DoesNotExist:
                    user_profile = None
                
                result['anomaly_detection'] = detector.detect_anomaly(session_data, user_profile)
        
        # Threat analysis
        behavior_data = request.data.get('behavior_data', {})
        if session_data and behavior_data:
            analyzer = get_model('threat_analyzer')
            if analyzer:
                result['threat_analysis'] = analyzer.analyze_threat(
                    session_data,
                    str(request.user.id),
                    behavior_data
                )
        
        return success_response(result)
    
    except Exception as e:
        logger.error(f"Error in batch analysis: {str(e)}")
        return error_response("Failed to perform batch analysis")


# ============================================================================
# FHE-ENHANCED PASSWORD STRENGTH
# ============================================================================

@api_view(['POST'])
@permission_classes([IsAuthenticated])
@throttle_classes([MLSecurityThrottle])
def predict_password_strength_fhe(request):
    """
    Predict password strength using FHE (Fully Homomorphic Encryption).
    
    The password is received encrypted from the client and strength
    is computed on the encrypted data using FHE operations.
    
    POST Data:
    {
        "encrypted_password": [...],  # FHE encrypted password bytes
        "password_length": int,  # Encrypted or plaintext length
        "budget": {
            "max_latency_ms": 1000,
            "min_accuracy": 0.9
        },
        "metadata": {...}  # Additional metadata
    }
    
    Returns:
    {
        "success": true,
        "score": 0.85,
        "tier": "full_fhe",
        "breakdown": {...},
        "recommendations": [...]
    }
    """
    try:
        # Import FHE services
        from fhe_service.services import get_fhe_router, EncryptionTier
        from fhe_service.services.fhe_router import ComputationalBudget, OperationType
        
        encrypted_password = request.data.get('encrypted_password')
        password_length = request.data.get('password_length', 0)
        budget_data = request.data.get('budget', {})
        metadata = request.data.get('metadata', {})
        
        if not encrypted_password:
            return error_response(
                "Encrypted password is required",
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        # Create computational budget
        budget = ComputationalBudget(
            max_latency_ms=budget_data.get('max_latency_ms', 1000),
            max_memory_mb=budget_data.get('max_memory_mb', 512),
            min_accuracy=budget_data.get('min_accuracy', 0.9),
            priority=budget_data.get('priority', 5)
        )
        
        # Get FHE router
        fhe_router = get_fhe_router()
        
        # Determine if password was sent as simulated encryption
        is_simulated = metadata.get('isSimulated', True)
        
        if is_simulated:
            # For simulated encryption, we can use the password length
            # to estimate strength without actual FHE computation
            score = _estimate_strength_from_length(password_length)
            tier = 'hybrid_fhe'
            breakdown = {
                'length_score': min(password_length * 4, 40),
                'complexity_bonus': 10 if password_length >= 12 else 0,
            }
            recommendations = []
            if score < 60:
                recommendations.append('Use a longer password')
                recommendations.append('Add special characters')
        else:
            # Route through actual FHE computation
            tier, result = fhe_router.route_operation(
                OperationType.STRENGTH_CHECK,
                bytes(encrypted_password) if isinstance(encrypted_password, list) else encrypted_password,
                budget,
                metadata
            )
            
            if result.get('success'):
                score = result.get('score', 0)
                breakdown = result.get('breakdown', {})
                recommendations = result.get('recommendations', [])
            else:
                # Fallback to length-based estimation
                score = _estimate_strength_from_length(password_length)
                breakdown = {'fallback': True}
                recommendations = []
        
        return success_response({
            'score': score,
            'tier': tier.name if hasattr(tier, 'name') else str(tier),
            'breakdown': breakdown,
            'recommendations': recommendations,
            'computed_on': 'server',
            'fhe_enabled': not is_simulated,
        })
    
    except ImportError as e:
        logger.warning(f"FHE service not available: {str(e)}")
        # Fallback to length-based estimation
        password_length = request.data.get('password_length', 0)
        return success_response({
            'score': _estimate_strength_from_length(password_length),
            'tier': 'client_only',
            'breakdown': {'fallback': True, 'reason': 'FHE service not available'},
            'recommendations': [],
            'computed_on': 'client_fallback',
            'fhe_enabled': False,
        })
    
    except Exception as e:
        logger.error(f"Error in FHE password strength prediction: {str(e)}")
        return error_response(
            "Failed to predict password strength with FHE",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


def _estimate_strength_from_length(length: int) -> float:
    """Estimate password strength based on length alone (fallback)."""
    if length == 0:
        return 0.0
    
    # Simple length-based scoring
    score = min(length * 5, 50)  # Up to 50 points for length
    
    # Bonus for longer passwords
    if length >= 12:
        score += 20
    if length >= 16:
        score += 15
    if length >= 20:
        score += 15
    
    return min(score, 100.0)
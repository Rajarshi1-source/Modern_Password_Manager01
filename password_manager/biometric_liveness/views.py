"""
Biometric Liveness REST API Views
==================================

REST API endpoints for liveness verification.
"""

import logging
import base64
import numpy as np
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .services import LivenessSessionService
from .models import LivenessProfile, LivenessSession, LivenessSettings

logger = logging.getLogger(__name__)

# Service instance (would use DI in production)
_session_service = None

def get_session_service():
    global _session_service
    if _session_service is None:
        _session_service = LivenessSessionService()
    return _session_service


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def start_session(request):
    """Start a new liveness verification session."""
    try:
        context = request.data.get('context', 'login')
        device_fingerprint = request.data.get('device_fingerprint', '')
        
        service = get_session_service()
        session_info = service.create_session(request.user.id, context)
        
        # Create database record
        LivenessSession.objects.create(
            id=session_info['session_id'],
            user=request.user,
            context=context,
            required_challenges=session_info['challenges'],
            device_fingerprint=device_fingerprint,
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
            ip_address=request.META.get('REMOTE_ADDR'),
        )
        
        return Response(session_info, status=status.HTTP_201_CREATED)
    except Exception as e:
        logger.error(f"Error starting session: {e}")
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def submit_frame(request):
    """Submit a video frame for analysis."""
    try:
        session_id = request.data.get('session_id')
        frame_b64 = request.data.get('frame')
        timestamp_ms = request.data.get('timestamp_ms', 0)
        
        if not session_id or not frame_b64:
            return Response({'error': 'Missing session_id or frame'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Decode base64 frame
        frame_bytes = base64.b64decode(frame_b64)
        frame_array = np.frombuffer(frame_bytes, dtype=np.uint8)
        # Would reshape based on provided dimensions
        
        service = get_session_service()
        result = service.process_frame(session_id, frame_array, timestamp_ms)
        
        if 'error' in result:
            return Response(result, status=status.HTTP_400_BAD_REQUEST)
        
        return Response(result)
    except Exception as e:
        logger.error(f"Error processing frame: {e}")
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_challenge(request):
    """Get current cognitive challenge for session."""
    try:
        session_id = request.query_params.get('session_id')
        if not session_id:
            return Response({'error': 'Missing session_id'}, status=status.HTTP_400_BAD_REQUEST)
        
        service = get_session_service()
        session_status = service.get_session_status(session_id)
        
        if not session_status:
            return Response({'error': 'Session not found'}, status=status.HTTP_404_NOT_FOUND)
        
        return Response({'challenge': session_status.get('current_challenge')})
    except Exception as e:
        logger.error(f"Error getting challenge: {e}")
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def submit_challenge_response(request):
    """Submit response to cognitive challenge."""
    try:
        session_id = request.data.get('session_id')
        response_data = request.data.get('response', {})
        
        if not session_id:
            return Response({'error': 'Missing session_id'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Process challenge response
        # Would validate and store response
        
        return Response({'status': 'received', 'next_challenge': True})
    except Exception as e:
        logger.error(f"Error submitting response: {e}")
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def complete_session(request):
    """Complete session and get final verdict."""
    try:
        session_id = request.data.get('session_id')
        if not session_id:
            return Response({'error': 'Missing session_id'}, status=status.HTTP_400_BAD_REQUEST)
        
        service = get_session_service()
        result = service.complete_session(session_id)
        
        # Update database record
        try:
            session = LivenessSession.objects.get(id=session_id)
            session.status = 'passed' if result.is_verified else 'failed'
            session.overall_liveness_score = result.overall_liveness_score
            session.deepfake_probability = result.deepfake_probability
            session.confidence = result.confidence
            session.micro_expression_score = result.micro_expression_score
            session.gaze_tracking_score = result.gaze_tracking_score
            session.pulse_oximetry_score = result.pulse_oximetry_score
            session.thermal_score = result.thermal_score
            session.total_frames_processed = result.total_frames_processed
            session.save()
        except LivenessSession.DoesNotExist:
            pass
        
        return Response({
            'session_id': result.session_id,
            'is_verified': result.is_verified,
            'liveness_score': result.overall_liveness_score,
            'verdict': result.verdict,
            'confidence': result.confidence,
        })
    except Exception as e:
        logger.error(f"Error completing session: {e}")
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_profile(request):
    """Get user's liveness profile."""
    try:
        profile, created = LivenessProfile.objects.get_or_create(user=request.user)
        return Response({
            'is_calibrated': profile.is_calibrated,
            'calibration_samples': profile.calibration_samples,
            'profile_confidence': profile.profile_confidence,
            'liveness_threshold': profile.liveness_threshold,
            'last_calibration': profile.last_calibration_at.isoformat() if profile.last_calibration_at else None,
        })
    except Exception as e:
        logger.error(f"Error getting profile: {e}")
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET', 'PUT'])
@permission_classes([IsAuthenticated])
def settings_view(request):
    """Get or update liveness settings."""
    try:
        settings_obj, created = LivenessSettings.objects.get_or_create(user=request.user)
        
        if request.method == 'GET':
            return Response({
                'enable_on_login': settings_obj.enable_on_login,
                'enable_on_sensitive_actions': settings_obj.enable_on_sensitive_actions,
                'enable_pulse_detection': settings_obj.enable_pulse_detection,
                'enable_thermal': settings_obj.enable_thermal,
                'challenge_difficulty': settings_obj.challenge_difficulty,
                'extended_time': settings_obj.extended_time,
            })
        else:
            for field in ['enable_on_login', 'enable_on_sensitive_actions', 'enable_pulse_detection', 'enable_thermal', 'extended_time']:
                if field in request.data:
                    setattr(settings_obj, field, request.data[field])
            if 'challenge_difficulty' in request.data:
                settings_obj.challenge_difficulty = request.data['challenge_difficulty']
            settings_obj.save()
            return Response({'status': 'updated'})
    except Exception as e:
        logger.error(f"Error with settings: {e}")
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_history(request):
    """Get verification history."""
    try:
        limit = int(request.query_params.get('limit', 10))
        sessions = LivenessSession.objects.filter(user=request.user).order_by('-created_at')[:limit]
        
        return Response({
            'sessions': [{
                'id': str(s.id),
                'context': s.context,
                'status': s.status,
                'liveness_score': s.overall_liveness_score,
                'created_at': s.created_at.isoformat(),
            } for s in sessions]
        })
    except Exception as e:
        logger.error(f"Error getting history: {e}")
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

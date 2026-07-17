"""
Biometric Liveness REST API Views
==================================

REST API endpoints for liveness verification.
"""

import logging
from functools import lru_cache
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from django.core.exceptions import ValidationError
from django.db import DatabaseError
from django.utils import timezone

from .frame_utils import decode_frame
from .services import LivenessSessionService
from .services.liveness_session_service import (
    SessionCapacityError, GazeChallengeIncompleteError,
)
from .models import LivenessProfile, LivenessSession, LivenessSettings

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def get_session_service():
    return LivenessSessionService()


def persist_session_result(result) -> None:
    """
    Mirror a finalized in-memory verdict onto the LivenessSession row.

    Shared by the REST complete endpoint and the WS consumer. Without it on the
    WS path the row stays pending/in_progress, so the consumer's verify_session
    keeps accepting reconnects to an already-completed session and the user's
    verification history never records the scores.
    """
    try:
        session = LivenessSession.objects.get(id=result.session_id)
    except LivenessSession.DoesNotExist:
        return
    except (DatabaseError, ValidationError, ValueError, TypeError):
        # Same rationale as the guarded save() below: the in-memory session is
        # already terminal, so a transient DB error on lookup must not propagate
        # (500, unretryable) and lose the verdict / deny the client its result.
        logger.exception(
            f"Failed to load liveness row for session {result.session_id}"
        )
        return
    session.status = 'passed' if result.is_verified else 'failed'
    session.completed_at = timezone.now()
    # The nuanced verdict, not just the binary pass/fail: the row's `verdict`
    # field exists precisely to record it, and collapsing SUSPECTED_FAKE and
    # INSUFFICIENT_SIGNAL to the same 'failed' loses why a session failed.
    session.verdict = result.verdict
    session.overall_liveness_score = result.overall_liveness_score
    session.deepfake_probability = result.deepfake_probability
    session.confidence = result.confidence
    session.micro_expression_score = result.micro_expression_score
    session.gaze_tracking_score = result.gaze_tracking_score
    session.pulse_oximetry_score = result.pulse_oximetry_score
    session.thermal_score = result.thermal_score
    session.texture_artifact_score = result.texture_artifact_score
    session.total_frames_processed = result.total_frames_processed
    try:
        session.save()
    except DatabaseError:
        # Best-effort mirror. complete_session() has already flipped the session
        # to its terminal state, so re-completing to retry is impossible; letting
        # this propagate would lose the verdict AND deny the client its result.
        # The in-memory terminal guards still reject further frames/re-scoring.
        logger.exception(
            f"Failed to persist liveness verdict for session {result.session_id}"
        )


def _user_owns_session(request, session_id) -> bool:
    """
    True only if the liveness session belongs to the requesting user.

    The in-memory session store is keyed by an opaque UUID, so the endpoints that
    mutate/finalize a session (frame, challenge response, complete) must confirm
    ownership -- otherwise any authenticated user holding another user's session
    id could inject signal into or finalize that session. Mirrors the WS
    consumer's verify_session.
    """
    if not session_id:
        return False
    try:
        return LivenessSession.objects.filter(id=session_id, user=request.user).exists()
    except (ValidationError, ValueError, TypeError):
        return False


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def start_session(request):
    """Start a new liveness verification session."""
    try:
        context = request.data.get('context', 'login')
        device_fingerprint = request.data.get('device_fingerprint', '')
        
        service = get_session_service()
        session_info = service.create_session(request.user.id, context)

        # Create database record. If it fails, drop the in-memory session so it
        # doesn't hold a live capacity slot until eviction (it would also be
        # unreachable -- ownership checks require the DB row).
        try:
            LivenessSession.objects.create(
                id=session_info['session_id'],
                user=request.user,
                context=context,
                required_challenges=session_info['challenges'],
                device_fingerprint=device_fingerprint,
                user_agent=request.META.get('HTTP_USER_AGENT', ''),
                ip_address=request.META.get('REMOTE_ADDR'),
            )
        except Exception:
            service.discard_session(session_info['session_id'])
            raise

        return Response(session_info, status=status.HTTP_201_CREATED)
    except SessionCapacityError:
        logger.warning("Liveness session capacity reached; rejecting new session")
        return Response({'error': 'capacity_reached'},
                        status=status.HTTP_503_SERVICE_UNAVAILABLE)
    except Exception as e:
        logger.error(f"Error starting session: {e}")
        return Response({'error': 'internal_error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def submit_frame(request):
    """Submit a video frame for analysis."""
    try:
        session_id = request.data.get('session_id')
        frame_b64 = request.data.get('frame')
        timestamp_ms = request.data.get('timestamp_ms', 0)
        try:
            width = int(request.data.get('width', 0) or 0)
            height = int(request.data.get('height', 0) or 0)
        except (TypeError, ValueError):
            return Response({'error': 'Invalid frame dimensions'},
                            status=status.HTTP_400_BAD_REQUEST)

        if not session_id or not frame_b64:
            return Response({'error': 'Missing session_id or frame'}, status=status.HTTP_400_BAD_REQUEST)
        if not _user_owns_session(request, session_id):
            return Response({'error': 'not_found'}, status=status.HTTP_404_NOT_FOUND)

        # Raw RGB/RGBA pixel data from the client canvas; same decode contract as
        # the WS path.
        frame_array, decode_error = decode_frame(frame_b64, width, height)
        if decode_error:
            return Response({'error': decode_error}, status=status.HTTP_400_BAD_REQUEST)

        service = get_session_service()
        result = service.process_frame(session_id, frame_array, timestamp_ms)
        
        if 'error' in result:
            return Response(result, status=status.HTTP_400_BAD_REQUEST)
        
        return Response(result)
    except Exception as e:
        logger.error(f"Error processing frame: {e}")
        return Response({'error': 'internal_error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_challenge(request):
    """Get current cognitive challenge for session."""
    try:
        session_id = request.query_params.get('session_id')
        if not session_id:
            return Response({'error': 'Missing session_id'}, status=status.HTTP_400_BAD_REQUEST)
        if not _user_owns_session(request, session_id):
            return Response({'error': 'not_found'}, status=status.HTTP_404_NOT_FOUND)

        service = get_session_service()
        session_status = service.get_session_status(session_id)
        
        if not session_status:
            return Response({'error': 'Session not found'}, status=status.HTTP_404_NOT_FOUND)
        
        return Response({'challenge': session_status.get('current_challenge')})
    except Exception as e:
        logger.error(f"Error getting challenge: {e}")
        return Response({'error': 'internal_error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def submit_challenge_response(request):
    """Submit response to cognitive challenge."""
    try:
        session_id = request.data.get('session_id')
        response_data = request.data.get('response', {})
        
        if not session_id:
            return Response({'error': 'Missing session_id'}, status=status.HTTP_400_BAD_REQUEST)
        if not _user_owns_session(request, session_id):
            return Response({'error': 'not_found'}, status=status.HTTP_404_NOT_FOUND)

        service = get_session_service()
        result = service.submit_challenge_response(session_id, response_data)
        if 'error' in result:
            return Response(result, status=status.HTTP_400_BAD_REQUEST)
        return Response(result)
    except Exception as e:
        logger.error(f"Error submitting response: {e}")
        return Response({'error': 'internal_error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def complete_session(request):
    """Complete session and get final verdict."""
    try:
        session_id = request.data.get('session_id')
        if not session_id:
            return Response({'error': 'Missing session_id'}, status=status.HTTP_400_BAD_REQUEST)
        if not _user_owns_session(request, session_id):
            return Response({'error': 'not_found'}, status=status.HTTP_404_NOT_FOUND)

        service = get_session_service()
        result = service.complete_session(session_id)

        persist_session_result(result)

        return Response({
            'session_id': result.session_id,
            'is_verified': result.is_verified,
            'liveness_score': result.overall_liveness_score,
            'verdict': result.verdict,
            'confidence': result.confidence,
        })
    except GazeChallengeIncompleteError:
        # Distinct from the terminal errors below: the session is still live, so
        # the client should answer the gaze challenge and retry, not abandon it.
        return Response({'error': 'required_challenge_incomplete', 'retryable': True},
                        status=status.HTTP_409_CONFLICT)
    except ValueError as e:
        # Session not found / already completed / expired -> terminal state error.
        # Do not echo the exception text to the client (CodeQL info-exposure).
        logger.warning(f"Session completion conflict: {e}")
        return Response({'error': 'invalid_session_state'}, status=status.HTTP_409_CONFLICT)
    except Exception as e:
        logger.error(f"Error completing session: {e}")
        return Response({'error': 'internal_error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_capabilities(request):
    """Report which liveness modalities are genuinely operational server-side."""
    try:
        service = get_session_service()
        return Response(service.get_capabilities())
    except Exception:
        # Boundary converts unexpected failures to HTTP 500; keep the traceback.
        logger.exception("Error getting capabilities")
        return Response({'error': 'internal_error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


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
        return Response({'error': 'internal_error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


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
        return Response({'error': 'internal_error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


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
        return Response({'error': 'internal_error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

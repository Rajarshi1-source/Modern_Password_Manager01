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
from django.utils.dateparse import parse_datetime

from .frame_utils import decode_frame
from .services import LivenessSessionService
from .services.liveness_session_service import (
    SessionCapacityError, GazeChallengeIncompleteError, SessionLockError,
)
from .models import LivenessProfile, LivenessSession, LivenessSettings

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def get_session_service():
    return LivenessSessionService()


# Another worker holds this session's (or the create) lock. The lock is held for
# a single fast session operation, so a 1s backoff is the right order of
# magnitude -- long enough not to hot-loop, short enough that a live
# verification does not visibly stall.
_SESSION_BUSY_RETRY_AFTER = '1'


def _session_busy_response():
    """
    Retryable 409 for cross-process lock contention.

    The body flag is what our own client reads, but Retry-After lets generic
    HTTP clients, SDK retry policies and proxies back off on their own instead
    of retrying immediately in a tight loop.
    """
    response = Response({'error': 'session_busy', 'retryable': True},
                        status=status.HTTP_409_CONFLICT)
    response['Retry-After'] = _SESSION_BUSY_RETRY_AFTER
    return response


def _liveness_result_payload(result) -> dict:
    """
    Flatten a SessionResult into the primitive fields the row needs.

    Kept JSON-serializable so the very same write can run inline (persist_session_result)
    or from the Celery retry task (which serializes its args as JSON).
    """
    return {
        'session_id': str(result.session_id),
        'is_verified': bool(result.is_verified),
        # The nuanced verdict, not just the binary pass/fail: the row's `verdict`
        # field exists precisely to record it, and collapsing SUSPECTED_FAKE and
        # INSUFFICIENT_SIGNAL to the same 'failed' loses why a session failed.
        'verdict': result.verdict,
        'overall_liveness_score': result.overall_liveness_score,
        'deepfake_probability': result.deepfake_probability,
        'confidence': result.confidence,
        'micro_expression_score': result.micro_expression_score,
        'gaze_tracking_score': result.gaze_tracking_score,
        'pulse_oximetry_score': result.pulse_oximetry_score,
        'thermal_score': result.thermal_score,
        'texture_artifact_score': result.texture_artifact_score,
        'total_frames_processed': result.total_frames_processed,
        # Carry the REAL completion time so a deferred/retried write records when
        # the session actually completed, not when the write ran (ISO for JSON).
        'completed_at': result.completed_at.isoformat() if result.completed_at is not None else None,
    }


def _completion_time(value):
    """
    Resolve a payload's completion timestamp to an aware datetime.

    Uses the carried real completion time so a deferred/retried persist records
    WHEN the session finished, not the write time -- and so re-applying the same
    payload is truly idempotent. Falls back to now() only when it is missing or
    unparseable.
    """
    if value:
        parsed = parse_datetime(value)
        if parsed is not None:
            return parsed
    return timezone.now()


def apply_liveness_result(payload: dict) -> None:
    """
    Write a finalized verdict onto its LivenessSession row.

    Raises LivenessSession.DoesNotExist / ValidationError (bad id) for PERMANENT
    failures and DatabaseError for TRANSIENT ones -- the caller decides whether to
    retry. Idempotent: re-applying writes the same terminal fields (including the
    carried completion time), so a retry (or a re-completion) can safely run it
    again without drifting completed_at to the write time.
    """
    session = LivenessSession.objects.get(id=payload['session_id'])
    session.status = 'passed' if payload['is_verified'] else 'failed'
    session.completed_at = _completion_time(payload.get('completed_at'))
    session.verdict = payload['verdict']
    session.overall_liveness_score = payload['overall_liveness_score']
    session.deepfake_probability = payload['deepfake_probability']
    session.confidence = payload['confidence']
    session.micro_expression_score = payload['micro_expression_score']
    session.gaze_tracking_score = payload['gaze_tracking_score']
    session.pulse_oximetry_score = payload['pulse_oximetry_score']
    session.thermal_score = payload['thermal_score']
    session.texture_artifact_score = payload['texture_artifact_score']
    session.total_frames_processed = payload['total_frames_processed']
    session.save()


def _record_persist_outbox(payload: dict, reason: str = '') -> None:
    """
    Write a verdict to the DB-backed persist outbox -- the LAST-RESORT net.

    Reached only when the broker retry layer is unavailable (enqueue failed) or
    exhausted its retries. By then the original DatabaseError may have been
    row-level/partial (lock timeout, deadlock on the session row) or a blip
    that has since recovered, so an INSERT into this separate table can still
    succeed; the beat sweeper (tasks.drain_liveness_persist_outbox) then
    re-applies it idempotently. update_or_create keeps ONE row per session
    (re-recording the same frozen verdict must not grow the table) and resets
    attempts/status so a fresh record gets fresh retries. Best-effort: during a
    FULL DB outage this write fails too -- log and return (the client already
    holds its verdict; identical terminal behavior to before this layer
    existed, so the net can only add durability, never a new failure mode).
    """
    try:
        from .models import LivenessPersistOutbox
        LivenessPersistOutbox.objects.update_or_create(
            session_id=payload['session_id'],
            defaults={
                'payload': payload,
                'status': 'pending',
                'attempts': 0,
                'last_error': reason[:500],
            },
        )
        logger.warning(
            f"Recorded liveness verdict for {payload['session_id']} in the persist outbox ({reason})")
    except Exception:
        logger.exception(
            f"Could not record liveness persist-outbox row for {payload.get('session_id')}")


def _enqueue_persist_retry(payload: dict) -> None:
    """
    Hand a verdict to the durable retry queue.

    The queue (Celery broker) is a SEPARATE service from the app DB, so a queued
    verdict survives a transient DB failure and is applied once the DB recovers --
    this is why the PRIMARY durable layer is the broker, not a DB-backed pending
    table (a DB row cannot be written during the very DB outage it would be
    protecting against). If even the enqueue fails (broker unreachable), fall
    through to the DB-backed outbox as the last-resort net -- the original
    DB error may have been partial or already recovered, so that write can
    still land. Never propagate a 500 here: the client already holds its
    verdict, and the in-memory session stays terminal for the retention window.
    """
    try:
        from .tasks import retry_persist_liveness_result
        retry_persist_liveness_result.delay(payload)
    except Exception:
        logger.exception(
            f"Could not enqueue liveness persistence retry for {payload['session_id']}")
        _record_persist_outbox(payload, reason='broker enqueue failed')


def persist_session_result(result) -> None:
    """
    Mirror a finalized in-memory verdict onto the LivenessSession row.

    Shared by the REST complete endpoint and the WS consumer. Without it on the
    WS path the row stays pending/in_progress, so the consumer's verify_session
    keeps accepting reconnects to an already-completed session and the user's
    verification history never records the scores. On a TRANSIENT DB failure the
    write is handed to a durable retry rather than silently dropped -- the verdict
    is not lost, and complete_session is idempotent so re-applying is safe.
    """
    payload = _liveness_result_payload(result)
    try:
        apply_liveness_result(payload)
    except LivenessSession.DoesNotExist:
        # No row to mirror onto (never persisted / already removed). Not retryable.
        return
    except (ValidationError, ValueError, TypeError, KeyError):
        # A malformed/unusable id or payload can never succeed on retry; log and
        # drop. Same non-retryable classification as the Celery retry task.
        logger.exception(
            f"Unusable liveness session id for persistence: {payload.get('session_id')}")
        return
    except DatabaseError:
        # Transient: do NOT lose the verdict. Hand it to the durable retry queue.
        logger.warning(
            f"Deferring liveness verdict persistence for {payload['session_id']} to retry")
        _enqueue_persist_retry(payload)


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


def _owns_in_memory_session(request, session_id, service) -> bool:
    """
    Ownership check for the hot per-frame path, without a DB query.

    submit_frame runs at video-frame rates, so an ORM exists() per frame (see
    _user_owns_session) is sustained database load. create_session stamps the
    owning user_id onto the in-memory session server-side, and a frame can only
    be processed if that session is in THIS worker's store (process_frame keys
    off it), so comparing against the stored user_id is authoritative and exactly
    as strict as the DB check for this path. A session absent from memory (never
    created here / evicted) is treated as not owned -> 404, matching how
    process_frame would reject it.
    """
    if not session_id:
        return False
    owner_id = service.owner_of(session_id)
    return owner_id is not None and owner_id == request.user.id


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
    except SessionLockError:
        # Store busy (could not take the create-lock) -- transient, retry.
        return _session_busy_response()
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

        service = get_session_service()
        # Per-frame ownership is resolved from the in-memory session's stamped
        # user_id (no ORM query at video-frame rates); see _owns_in_memory_session.
        if not _owns_in_memory_session(request, session_id, service):
            return Response({'error': 'not_found'}, status=status.HTTP_404_NOT_FOUND)

        # Raw RGB/RGBA pixel data from the client canvas; same decode contract as
        # the WS path.
        frame_array, decode_error = decode_frame(frame_b64, width, height)
        if decode_error:
            return Response({'error': decode_error}, status=status.HTTP_400_BAD_REQUEST)

        result = service.process_frame(session_id, frame_array, timestamp_ms)
        
        if 'error' in result:
            return Response(result, status=status.HTTP_400_BAD_REQUEST)
        
        return Response(result)
    except SessionLockError:
        return _session_busy_response()
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
            # Mirror complete_session's status semantics: a session-lifecycle
            # conflict (gone / already completed / expired) is 409, while a
            # genuine bad request (unknown or replayed challenge) stays 400.
            conflict = result.pop('state_conflict', False)
            return Response(result, status=status.HTTP_409_CONFLICT if conflict
                            else status.HTTP_400_BAD_REQUEST)
        return Response(result)
    except SessionLockError:
        return _session_busy_response()
    except Exception as e:
        logger.error(f"Error submitting response: {e}")
        return Response({'error': 'internal_error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def submit_hardware_spo2(request):
    """Relay a real BLE pulse-oximeter SpO2 reading into the session (REST).

    Shares the exact server-side path as the WS ``hardware_spo2`` message
    (``submit_hardware_spo2`` -> ``ingest_hardware_spo2``, stamped on the server
    clock). SpO2 is never derived from the webcam; a bad/absent/stale reading is
    dropped, never fabricated. ``accepted`` reports whether the reading currently
    passes both the quality floor and freshness window (not merely that it was
    stored) -- i.e. whether it would actually surface and gate right now.
    """
    try:
        session_id = request.data.get('session_id')
        if not session_id:
            return Response({'error': 'Missing session_id'}, status=status.HTTP_400_BAD_REQUEST)
        if not _user_owns_session(request, session_id):
            return Response({'error': 'not_found'}, status=status.HTTP_404_NOT_FOUND)

        service = get_session_service()
        result = service.submit_hardware_spo2(
            session_id, request.data.get('spo2'), request.data.get('quality', 1.0)
        )
        if 'error' in result:
            # Same status semantics as submit_challenge_response: a session-
            # lifecycle conflict is 409, a genuine bad request stays 400.
            conflict = result.pop('state_conflict', False)
            return Response(result, status=status.HTTP_409_CONFLICT if conflict
                            else status.HTTP_400_BAD_REQUEST)
        return Response(result)
    except SessionLockError:
        return _session_busy_response()
    except Exception as e:
        logger.error(f"Error ingesting hardware SpO2: {e}")
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
    except SessionLockError:
        return _session_busy_response()
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

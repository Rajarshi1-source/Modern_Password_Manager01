"""DRF views for heartbeat_auth.

Keep thin — all decision logic lives in ``services.heartbeat_service``.
"""

from __future__ import annotations

import logging

from django.conf import settings
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .services import heartbeat_service

logger = logging.getLogger(__name__)


def _feature_enabled() -> bool:
    return bool(getattr(settings, 'HEARTBEAT_AUTH_ENABLED', True))


def _disabled_response():
    return Response(
        {'success': False, 'error': 'heartbeat_auth_disabled'},
        status=status.HTTP_503_SERVICE_UNAVAILABLE,
    )


def _validate_features(payload) -> tuple[dict, dict]:
    """Pull (features, extras) out of the request payload."""
    features = payload.get('features') or {}
    if not isinstance(features, dict) or not features:
        raise ValueError('features payload is empty')
    # Extras keep raw R-R intervals off the features dict so the
    # matcher only sees its canonical inputs.
    extras = {
        'rr_intervals': payload.get('rr_intervals') or [],
        'capture_duration_s': payload.get('capture_duration_s'),
        'frame_rate': payload.get('frame_rate'),
    }
    return features, extras


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def enroll(request):
    if not _feature_enabled():
        return _disabled_response()
    try:
        features, extras = _validate_features(request.data)
    except ValueError as exc:
        return Response(
            {'success': False, 'error': 'invalid_payload', 'message': str(exc)},
            status=status.HTTP_400_BAD_REQUEST,
        )

    result = heartbeat_service.enroll_reading(
        user=request.user, features=features, extras=extras, request=request,
    )
    return Response({'success': True, **result})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def verify(request):
    if not _feature_enabled():
        return _disabled_response()
    try:
        features, extras = _validate_features(request.data)
    except ValueError as exc:
        return Response(
            {'success': False, 'error': 'invalid_payload', 'message': str(exc)},
            status=status.HTTP_400_BAD_REQUEST,
        )

    result = heartbeat_service.verify_reading(
        user=request.user, features=features, extras=extras, request=request,
    )
    # On duress the HTTP status stays 200 — the whole point of the
    # anti-coercion path is that it is UI-indistinguishable from a
    # normal success. The response body still flags decision='duress'
    # for server-side consumers that need to know.
    return Response({'success': True, **result})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def profile(request):
    if not _feature_enabled():
        return _disabled_response()
    return Response({'success': True, 'profile': heartbeat_service.get_profile_dict(request.user)})


@api_view(['POST', 'DELETE'])
@permission_classes([IsAuthenticated])
def reset_profile(request):
    if not _feature_enabled():
        return _disabled_response()
    heartbeat_service.reset(request.user)
    return Response({'success': True})

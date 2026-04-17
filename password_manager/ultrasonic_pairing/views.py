"""DRF views for ultrasonic pairing.

Implemented as function-based views in the same style as
``biometric_liveness.views`` for consistency. Each view is thin; all
state-machine logic lives in :mod:`ultrasonic_pairing.services.pairing_service`.
"""

from __future__ import annotations

import logging
import uuid
from typing import Optional

from django.conf import settings
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import PairingSession, PairingStatus
from .serializers import (
    PairingSessionSerializer,
    PairingSessionSummarySerializer,
)
from .services import pairing_service

logger = logging.getLogger(__name__)


def _feature_enabled() -> bool:
    return bool(getattr(settings, 'ULTRASONIC_PAIRING_ENABLED', True))


def _disabled_response():
    return Response(
        {'success': False, 'error': 'ultrasonic_pairing_disabled'},
        status=status.HTTP_503_SERVICE_UNAVAILABLE,
    )


def _request_meta(request):
    ip = request.META.get('HTTP_X_FORWARDED_FOR', '').split(',')[0].strip() \
        or request.META.get('REMOTE_ADDR')
    return ip or None, request.META.get('HTTP_USER_AGENT', '')[:255]


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def initiate_session(request):
    """Create a new pairing session.

    Body:
        {
          "pub_key": "<base64 SEC1 P-256>",
          "purpose": "device_enroll" | "item_share"
        }
    Returns ``{session_id, nonce, expires_at}`` — the caller then
    emits the 6-byte nonce over the ultrasonic channel.
    """
    if not _feature_enabled():
        return _disabled_response()

    pub_key_b64 = request.data.get('pub_key')
    purpose = request.data.get('purpose')
    if not pub_key_b64 or not purpose:
        return Response(
            {'success': False, 'error': 'missing_fields'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        ip, ua = _request_meta(request)
        session, nonce = pairing_service.initiate(
            user=request.user,
            pub_key_b64=pub_key_b64,
            purpose=purpose,
            ip=ip,
            user_agent=ua,
        )
    except pairing_service.PairingError as exc:
        return Response(
            {'success': False, 'error': exc.code, 'message': str(exc)},
            status=status.HTTP_400_BAD_REQUEST,
        )

    return Response({
        'success': True,
        'session_id': str(session.id),
        'nonce': nonce,  # base64
        'expires_at': session.expires_at.isoformat(),
        'purpose': session.purpose,
    }, status=status.HTTP_201_CREATED)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def claim_session(request):
    """Responder claims a nonce heard over the air.

    Body: ``{ "nonce": "<base64 6B>", "pub_key": "<base64 SEC1>" }``
    """
    if not _feature_enabled():
        return _disabled_response()

    nonce_b64 = request.data.get('nonce')
    pub_key_b64 = request.data.get('pub_key')
    if not nonce_b64 or not pub_key_b64:
        return Response(
            {'success': False, 'error': 'missing_fields'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        ip, ua = _request_meta(request)
        session = pairing_service.claim(
            user=request.user,
            nonce_b64=nonce_b64,
            pub_key_b64=pub_key_b64,
            ip=ip,
            user_agent=ua,
        )
    except pairing_service.PairingError as exc:
        return Response(
            {'success': False, 'error': exc.code, 'message': str(exc)},
            status=exc.http_status,
        )

    return Response({
        'success': True,
        'session_id': str(session.id),
        'initiator_pub_key': pairing_service.b64(bytes(session.initiator_pub_key)),
        'purpose': session.purpose,
        'expires_at': session.expires_at.isoformat(),
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def confirm_session(request, session_id: uuid.UUID):
    """Responder confirms the shared secret via SAS HMAC.

    Body: ``{ "sas_hmac": "<base64 32B>" }``
    """
    if not _feature_enabled():
        return _disabled_response()

    sas_b64 = request.data.get('sas_hmac')
    if not sas_b64:
        return Response(
            {'success': False, 'error': 'missing_fields'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        ip, ua = _request_meta(request)
        session = pairing_service.confirm(
            session_id=session_id,
            user=request.user,
            sas_hmac_b64=sas_b64,
            ip=ip,
            user_agent=ua,
        )
    except pairing_service.PairingError as exc:
        return Response(
            {'success': False, 'error': exc.code, 'message': str(exc)},
            status=exc.http_status,
        )

    return Response({
        'success': True,
        'session_id': str(session.id),
        'status': session.status,
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_session(request, session_id: uuid.UUID):
    """Initiator polls to observe responder progress.

    Only the initiator can poll (to avoid session-id enumeration by
    other authenticated users).
    """
    if not _feature_enabled():
        return _disabled_response()

    session = get_object_or_404(PairingSession, id=session_id)
    if session.initiator_id != request.user.id and session.responder_id != request.user.id:
        return Response(
            {'success': False, 'error': 'forbidden'},
            status=status.HTTP_403_FORBIDDEN,
        )

    return Response({
        'success': True,
        'session': PairingSessionSerializer(session, context={
            'viewer_is_initiator': session.initiator_id == request.user.id,
        }).data,
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def share_payload(request, session_id: uuid.UUID):
    """Initiator attaches an encrypted vault-item payload (item_share)."""
    if not _feature_enabled():
        return _disabled_response()

    ct_b64 = request.data.get('ciphertext')
    nonce_b64 = request.data.get('nonce')
    vault_item_id = request.data.get('vault_item_id', '')
    if not ct_b64 or not nonce_b64:
        return Response(
            {'success': False, 'error': 'missing_fields'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        ip, ua = _request_meta(request)
        pairing_service.attach_share_payload(
            session_id=session_id,
            user=request.user,
            ciphertext_b64=ct_b64,
            nonce_b64=nonce_b64,
            vault_item_id=vault_item_id,
            ip=ip,
            user_agent=ua,
        )
    except pairing_service.PairingError as exc:
        return Response(
            {'success': False, 'error': exc.code, 'message': str(exc)},
            status=exc.http_status,
        )
    return Response({'success': True})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def fetch_delivered_payload(request, session_id: uuid.UUID):
    """Responder retrieves the encrypted payload (item_share)."""
    if not _feature_enabled():
        return _disabled_response()

    try:
        ip, ua = _request_meta(request)
        data = pairing_service.fetch_share_payload(
            session_id=session_id,
            user=request.user,
            ip=ip,
            user_agent=ua,
        )
    except pairing_service.PairingError as exc:
        return Response(
            {'success': False, 'error': exc.code, 'message': str(exc)},
            status=exc.http_status,
        )
    return Response({'success': True, **data})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def enroll_device(request, session_id: uuid.UUID):
    """Responder registers as a new device (device_enroll)."""
    if not _feature_enabled():
        return _disabled_response()

    fingerprint = request.data.get('fingerprint') or {}
    try:
        ip, ua = _request_meta(request)
        token_info = pairing_service.enroll_device(
            session_id=session_id,
            user=request.user,
            fingerprint=fingerprint,
            ip=ip,
            user_agent=ua,
        )
    except pairing_service.PairingError as exc:
        return Response(
            {'success': False, 'error': exc.code, 'message': str(exc)},
            status=exc.http_status,
        )
    return Response({'success': True, **token_info})

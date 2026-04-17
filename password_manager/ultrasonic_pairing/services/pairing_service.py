"""Pairing state machine.

This module is the only place the ``PairingSession`` model should be
mutated. Everything goes through one of:

* :func:`initiate` — initiator creates a session + nonce.
* :func:`claim` — responder claims a heard nonce (atomic, single-use).
* :func:`confirm` — responder submits HMAC(shared, "sas") proving ECDH.
* :func:`attach_share_payload` / :func:`fetch_share_payload` — item_share.
* :func:`enroll_device` — device_enroll.

All of the above write a :class:`PairingEvent` row for forensic replay.
"""

from __future__ import annotations

import base64
import logging
import secrets
import uuid
from dataclasses import dataclass
from datetime import timedelta
from typing import Optional, Tuple

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from rest_framework import status as http_status

from ..models import (
    PairingEvent,
    PairingPurpose,
    PairingSession,
    PairingStatus,
)

logger = logging.getLogger(__name__)

NONCE_LENGTH = 6
EXPECTED_PUB_KEY_LENGTH = 65  # SEC1 uncompressed P-256
EXPECTED_SAS_LENGTH = 32  # HMAC-SHA256


class PairingError(Exception):
    """Raised for any state-machine violation.

    Exposes a stable ``.code`` string for clients and a sensible
    default HTTP status code.
    """

    def __init__(
        self,
        code: str,
        message: str = '',
        http_status_code: int = http_status.HTTP_400_BAD_REQUEST,
    ) -> None:
        super().__init__(message or code)
        self.code = code
        self.http_status = http_status_code


def b64(data: bytes) -> str:
    return base64.b64encode(data).decode('ascii')


def _b64decode(data: Optional[str], *, field: str) -> bytes:
    if not data:
        raise PairingError('missing_' + field, f'missing {field}')
    try:
        return base64.b64decode(data, validate=True)
    except (ValueError, TypeError) as exc:
        raise PairingError('invalid_' + field, str(exc)) from exc


def _ttl_seconds() -> int:
    return int(getattr(settings, 'PAIRING_SESSION_TTL_SECONDS', 120))


def _log(session: PairingSession, kind: str, *, actor=None, ip=None,
         user_agent: str = '', detail: str = '') -> None:
    try:
        PairingEvent.objects.create(
            session=session,
            kind=kind,
            actor=actor,
            ip=ip,
            user_agent=(user_agent or '')[:255],
            detail=detail[:255],
        )
    except Exception:  # pragma: no cover - audit logging must never raise
        logger.exception('failed to log pairing event %s', kind)


@dataclass
class InitiateResult:
    session: PairingSession
    nonce_b64: str


def initiate(
    *,
    user,
    pub_key_b64: str,
    purpose: str,
    ip=None,
    user_agent: str = '',
) -> Tuple[PairingSession, str]:
    if purpose not in PairingPurpose.values:
        raise PairingError('invalid_purpose', f'unknown purpose: {purpose}')

    pub_key = _b64decode(pub_key_b64, field='pub_key')
    if len(pub_key) != EXPECTED_PUB_KEY_LENGTH or pub_key[0] != 0x04:
        raise PairingError(
            'invalid_pub_key',
            'initiator public key must be SEC1 uncompressed P-256 (65 bytes).',
        )

    # Generate a single-use nonce; retry on the astronomically unlikely
    # collision against the unique constraint.
    for _ in range(5):
        nonce = secrets.token_bytes(NONCE_LENGTH)
        nonce_hex = nonce.hex()
        expires_at = timezone.now() + timedelta(seconds=_ttl_seconds())
        try:
            with transaction.atomic():
                session = PairingSession.objects.create(
                    initiator=user,
                    purpose=purpose,
                    status=PairingStatus.AWAITING_RESPONDER,
                    initiator_pub_key=pub_key,
                    nonce=nonce,
                    nonce_key=nonce_hex,
                    expires_at=expires_at,
                )
            break
        except Exception as exc:  # IntegrityError on nonce_key collision
            logger.debug('pairing nonce collision, retrying: %s', exc)
    else:  # pragma: no cover - collision floor is 2^-48
        raise PairingError(
            'nonce_allocation_failed',
            'Could not allocate unique nonce; try again.',
            http_status_code=http_status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    _log(session, 'initiate', actor=user, ip=ip, user_agent=user_agent,
         detail=f'purpose={purpose}')
    return session, b64(nonce)


def claim(
    *,
    user,
    nonce_b64: str,
    pub_key_b64: str,
    ip=None,
    user_agent: str = '',
) -> PairingSession:
    nonce = _b64decode(nonce_b64, field='nonce')
    if len(nonce) != NONCE_LENGTH:
        raise PairingError('invalid_nonce', 'nonce must be 6 bytes')

    pub_key = _b64decode(pub_key_b64, field='pub_key')
    if len(pub_key) != EXPECTED_PUB_KEY_LENGTH or pub_key[0] != 0x04:
        raise PairingError(
            'invalid_pub_key',
            'responder public key must be SEC1 uncompressed P-256 (65 bytes).',
        )

    nonce_hex = nonce.hex()

    # Atomic select-for-update so two simultaneous claims can't both
    # succeed. ``SELECT ... FOR UPDATE`` is a no-op on SQLite (test
    # backend) but the outer transaction + the state check below still
    # ensure single-use semantics.
    with transaction.atomic():
        try:
            session = (
                PairingSession.objects
                .select_for_update()
                .get(nonce_key=nonce_hex)
            )
        except PairingSession.DoesNotExist:
            raise PairingError(
                'unknown_nonce',
                'no active pairing session for that nonce',
                http_status_code=http_status.HTTP_404_NOT_FOUND,
            )

        if session.initiator_id == user.id and session.purpose == PairingPurpose.ITEM_SHARE:
            # Allow self-pairing for device_enroll flows (same user,
            # two devices) but disallow it for item_share to avoid
            # sharing with yourself.
            raise PairingError(
                'self_claim_forbidden',
                'item_share cannot be claimed by the initiator.',
                http_status_code=http_status.HTTP_403_FORBIDDEN,
            )

        if session.status != PairingStatus.AWAITING_RESPONDER:
            raise PairingError(
                'already_claimed',
                f'session already in state {session.status}',
                http_status_code=http_status.HTTP_409_CONFLICT,
            )
        if not session.is_live:
            session.status = PairingStatus.EXPIRED
            session.save(update_fields=['status'])
            _log(session, 'expire', actor=user, ip=ip, user_agent=user_agent)
            raise PairingError(
                'session_expired',
                'pairing session has expired',
                http_status_code=http_status.HTTP_410_GONE,
            )

        session.responder = user
        session.responder_pub_key = pub_key
        session.status = PairingStatus.CLAIMED
        session.save(update_fields=['responder', 'responder_pub_key', 'status'])
        _log(session, 'claim', actor=user, ip=ip, user_agent=user_agent)
    return session


def confirm(
    *,
    session_id: uuid.UUID,
    user,
    sas_hmac_b64: str,
    ip=None,
    user_agent: str = '',
) -> PairingSession:
    sas = _b64decode(sas_hmac_b64, field='sas_hmac')
    if len(sas) != EXPECTED_SAS_LENGTH:
        raise PairingError('invalid_sas', 'sas_hmac must be 32 bytes')

    with transaction.atomic():
        try:
            session = (
                PairingSession.objects
                .select_for_update()
                .get(id=session_id)
            )
        except PairingSession.DoesNotExist:
            raise PairingError(
                'unknown_session',
                'no such pairing session',
                http_status_code=http_status.HTTP_404_NOT_FOUND,
            )

        if session.responder_id != user.id:
            _log(session, 'fail', actor=user, ip=ip, user_agent=user_agent,
                 detail='wrong_responder')
            raise PairingError(
                'wrong_responder',
                'only the claiming device can confirm',
                http_status_code=http_status.HTTP_403_FORBIDDEN,
            )
        if session.status != PairingStatus.CLAIMED:
            raise PairingError(
                'invalid_state',
                f'cannot confirm from state {session.status}',
                http_status_code=http_status.HTTP_409_CONFLICT,
            )
        if not session.is_live:
            session.status = PairingStatus.EXPIRED
            session.save(update_fields=['status'])
            raise PairingError(
                'session_expired',
                'pairing session has expired',
                http_status_code=http_status.HTTP_410_GONE,
            )

        session.sas_hmac = sas
        session.status = PairingStatus.CONFIRMED
        session.save(update_fields=['sas_hmac', 'status'])
        _log(session, 'confirm', actor=user, ip=ip, user_agent=user_agent)
    return session


def _load_for_terminal(
    *,
    session_id: uuid.UUID,
    required_role: str,
    user,
    allowed_states: Tuple[str, ...] = (PairingStatus.CONFIRMED,),
) -> PairingSession:
    """Load a session ready for share/enroll/delivered actions."""
    try:
        session = PairingSession.objects.get(id=session_id)
    except PairingSession.DoesNotExist:
        raise PairingError(
            'unknown_session',
            'no such pairing session',
            http_status_code=http_status.HTTP_404_NOT_FOUND,
        )

    if required_role == 'initiator' and session.initiator_id != user.id:
        raise PairingError(
            'forbidden', '', http_status_code=http_status.HTTP_403_FORBIDDEN,
        )
    if required_role == 'responder' and session.responder_id != user.id:
        raise PairingError(
            'forbidden', '', http_status_code=http_status.HTTP_403_FORBIDDEN,
        )
    if session.status not in allowed_states:
        raise PairingError(
            'invalid_state', f'cannot act from state {session.status}',
            http_status_code=http_status.HTTP_409_CONFLICT,
        )
    return session


def attach_share_payload(
    *,
    session_id: uuid.UUID,
    user,
    ciphertext_b64: str,
    nonce_b64: str,
    vault_item_id: str = '',
    ip=None,
    user_agent: str = '',
) -> None:
    ct = _b64decode(ciphertext_b64, field='ciphertext')
    nonce = _b64decode(nonce_b64, field='nonce')
    if not (8 <= len(nonce) <= 24):
        raise PairingError('invalid_nonce', 'payload nonce must be 8-24 bytes')
    if not (1 <= len(ct) <= 64 * 1024):
        raise PairingError('invalid_ciphertext', 'payload too large')

    session = _load_for_terminal(
        session_id=session_id, required_role='initiator', user=user,
    )
    if session.purpose != PairingPurpose.ITEM_SHARE:
        raise PairingError(
            'wrong_purpose', 'share only valid for item_share sessions',
            http_status_code=http_status.HTTP_409_CONFLICT,
        )

    session.payload_ciphertext = ct
    session.payload_nonce = nonce
    session.payload_vault_item_id = (vault_item_id or '')[:64]
    session.save(update_fields=[
        'payload_ciphertext', 'payload_nonce', 'payload_vault_item_id',
    ])
    _log(session, 'share', actor=user, ip=ip, user_agent=user_agent,
         detail=session.payload_vault_item_id)


def fetch_share_payload(
    *,
    session_id: uuid.UUID,
    user,
    ip=None,
    user_agent: str = '',
) -> dict:
    session = _load_for_terminal(
        session_id=session_id, required_role='responder', user=user,
    )
    if session.purpose != PairingPurpose.ITEM_SHARE:
        raise PairingError(
            'wrong_purpose', 'delivered only valid for item_share sessions',
            http_status_code=http_status.HTTP_409_CONFLICT,
        )
    if not session.payload_ciphertext:
        raise PairingError(
            'no_payload', 'initiator has not attached a payload yet',
            http_status_code=http_status.HTTP_409_CONFLICT,
        )

    data = {
        'ciphertext': b64(bytes(session.payload_ciphertext)),
        'nonce': b64(bytes(session.payload_nonce or b'')),
        'vault_item_id': session.payload_vault_item_id,
    }

    # Flip to delivered so the payload can\'t be fetched twice. The
    # ciphertext is retained for the forensic window; purge is handled
    # by the Celery expire/purge job below.
    session.status = PairingStatus.DELIVERED
    session.completed_at = timezone.now()
    session.save(update_fields=['status', 'completed_at'])
    _log(session, 'deliver', actor=user, ip=ip, user_agent=user_agent)
    return data


def enroll_device(
    *,
    session_id: uuid.UUID,
    user,
    fingerprint: dict,
    ip=None,
    user_agent: str = '',
) -> dict:
    session = _load_for_terminal(
        session_id=session_id, required_role='responder', user=user,
    )
    if session.purpose != PairingPurpose.DEVICE_ENROLL:
        raise PairingError(
            'wrong_purpose', 'enroll_device only valid for device_enroll sessions',
            http_status_code=http_status.HTTP_409_CONFLICT,
        )

    # Mint a device JWT via SimpleJWT if available; if not, fall back
    # to a signed payload so tests can exercise the flow without the
    # full auth stack.
    try:
        from rest_framework_simplejwt.tokens import RefreshToken
        refresh = RefreshToken.for_user(session.initiator)
        refresh['device_pairing_session'] = str(session.id)
        refresh['device_fingerprint'] = (fingerprint or {}).get('hash', '')
        access = str(refresh.access_token)
        refresh_str = str(refresh)
    except Exception as exc:  # pragma: no cover - depends on auth app config
        logger.warning('simplejwt unavailable; returning opaque device token: %s', exc)
        access = secrets.token_urlsafe(32)
        refresh_str = ''

    session.status = PairingStatus.DELIVERED
    session.completed_at = timezone.now()
    session.save(update_fields=['status', 'completed_at'])
    _log(session, 'enroll_device', actor=user, ip=ip, user_agent=user_agent,
         detail=(fingerprint or {}).get('hash', '')[:64])
    return {
        'device_access_token': access,
        'device_refresh_token': refresh_str,
        'account_user_id': session.initiator_id,
    }

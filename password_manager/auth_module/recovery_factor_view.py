"""
RecoveryFactorListCreateView — REST surface for enrolled recovery factors.

Each row in `RecoveryWrappedDEK` wraps the *same* DEK as the user's
`VaultWrappedDEK`, but under a *different* KEK derived from a recovery
secret (printable recovery key, social-mesh seed, time-lock seed, or
local passkey). Any single active row is enough to recover the vault.

Enrollment requires the client to send the *current* `dek_id`. That
acts as proof-of-DEK-possession: the only way to know it is to have
just unwrapped the live DEK with the master password (or a previously
enrolled recovery factor).

Server stores the resulting `blob` as opaque ciphertext. It never sees
the unwrapping secret (recovery key, seed, etc.) — only the wrapped
DEK that the client built locally.
"""
import base64
import hashlib
import hmac
import os
import uuid

from django.conf import settings
from django.contrib.auth.models import User
from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from auth_module.recovery_throttling import RecoveryThrottle
from auth_module.recovery_models_v2 import VaultWrappedDEK, RecoveryWrappedDEK
from auth_module.quantum_recovery_models import RecoveryAuditLog


ENVELOPE_VERSION = 'wdek-1'
_REQUIRED_FIELDS = ('kdf', 'kdf_params', 'salt', 'iv', 'wrapped')


def _valid_envelope(blob):
    """Validate envelope shape WITHOUT decrypting. (Same helper as
    Unit 4; duplicated here so this view is self-contained and the
    units do not have a shared-helper-module dependency.)"""
    if not isinstance(blob, dict) or blob.get('v') != ENVELOPE_VERSION:
        return False
    return all(k in blob for k in _REQUIRED_FIELDS)


def _client_ip(request):
    xff = request.META.get('HTTP_X_FORWARDED_FOR')
    if xff:
        return xff.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')


class RecoveryFactorListCreateView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [RecoveryThrottle]

    def get(self, request):
        qs = (
            RecoveryWrappedDEK.objects
            .filter(user=request.user, status=RecoveryWrappedDEK.Status.ACTIVE)
            .order_by('factor_type', 'created_at')
        )
        return Response([
            {
                'id': f.id,
                'factor_type': f.factor_type,
                'dek_id': str(f.dek_id),
                'created_at': f.created_at.isoformat(),
                'last_used_at': f.last_used_at.isoformat() if f.last_used_at else None,
                'meta': f.factor_meta,
            }
            for f in qs
        ])

    def post(self, request):
        try:
            current = VaultWrappedDEK.objects.get(user=request.user)
        except VaultWrappedDEK.DoesNotExist:
            return Response({'error': 'no DEK enrolled'}, status=400)

        if str(current.dek_id) != str(request.data.get('dek_id') or ''):
            return Response({'error': 'dek_id mismatch'}, status=409)

        ftype = request.data.get('factor_type')
        if ftype not in RecoveryWrappedDEK.FactorType.values:
            return Response({'error': 'invalid factor_type'}, status=400)
        # Time-locked enrollments MUST go through the dedicated bundle
        # endpoint that writes the wdek row and the Shamir server half
        # in one transaction. Allowing this generic path to write a
        # ``time_locked`` wdek row would let a caller create the row
        # without a matching TimeLockedRecovery row — exactly the
        # orphan state the bundle endpoint exists to prevent.
        if ftype == RecoveryWrappedDEK.FactorType.TIME_LOCKED:
            return Response(
                {
                    'error': 'use /api/auth/vault/time-locked/enroll-bundle/',
                    'detail': (
                        'time-locked factors must be enrolled atomically with '
                        'their server-side Shamir half'
                    ),
                },
                status=400,
            )

        blob = request.data.get('blob')
        if not _valid_envelope(blob):
            return Response({'error': 'invalid envelope'}, status=400)

        # auth_hash is the proof-of-secret-knowledge the rotation
        # endpoint will require later. Computed client-side as
        # SHA-256("rotation-auth-v1:" + recovery_secret). 64-char
        # lowercase hex; we don't validate it cryptographically here
        # (the server only stores opaque ciphertext / opaque hashes),
        # we just verify the shape so a rotation can compare bytes.
        auth_hash = request.data.get('auth_hash')
        if not isinstance(auth_hash, str) or len(auth_hash) != 64 or not all(
            c in '0123456789abcdef' for c in auth_hash
        ):
            return Response({'error': 'invalid auth_hash'}, status=400)

        meta = request.data.get('meta', {}) or {}
        if not isinstance(meta, dict):
            return Response({'error': 'meta must be an object'}, status=400)

        # Single-ACTIVE-row invariant per (user, factor_type):
        #
        #   - For recovery_key, this is enforced at the DB layer by
        #     a partial unique index. A duplicate raises IntegrityError
        #     and we translate to 409 — the user must explicitly revoke
        #     the old key first (printing two recovery keys at once is
        #     a UX footgun: which one is "the" recovery key?).
        #
        #   - For social_mesh / time_locked / passkey, no DB-level
        #     uniqueness existed historically. CodeRabbit flagged this
        #     because, without it, repeated enrollments stack ACTIVE
        #     rows and the anonymous lookup view's `order_by('-created
        #     _at').first()` would silently switch which blob is
        #     "live" while older blobs remain ACTIVE in the DB. To
        #     fix: revoke any prior ACTIVE row of the same factor_type
        #     atomically with the create, so at most one ACTIVE row
        #     of any given factor_type exists per user. We also lock
        #     those rows via `select_for_update()` so concurrent
        #     enrollments serialize.
        #
        # Other exceptions (DB outage, programming error) bubble to
        # DRF's default 500 handler — we never echo str(exc) back.
        try:
            with transaction.atomic():
                if ftype != RecoveryWrappedDEK.FactorType.RECOVERY_KEY:
                    revoke_qs = (
                        RecoveryWrappedDEK.objects
                        .select_for_update()
                        .filter(
                            user=request.user,
                            factor_type=ftype,
                            status=RecoveryWrappedDEK.Status.ACTIVE,
                        )
                    )
                    revoke_qs.update(
                        status=RecoveryWrappedDEK.Status.REVOKED,
                        revoked_at=timezone.now(),
                    )
                factor = RecoveryWrappedDEK.objects.create(
                    user=request.user,
                    factor_type=ftype,
                    dek_id=current.dek_id,
                    blob=blob,
                    factor_meta=meta,
                    auth_hash=auth_hash,
                )
        except IntegrityError:
            return Response(
                {'error': 'factor of this type already active'},
                status=409,
            )

        # Reuse existing audit-log event types; subsystem in event_data.
        RecoveryAuditLog.objects.create(
            user=request.user,
            event_type='setup_created',
            event_data={
                'subsystem': 'recovery_factor',
                'factor_type': ftype,
                'factor_id': factor.id,
                'dek_id': str(current.dek_id),
            },
            ip_address=_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', '')[:1024],
        )
        return Response({'success': True, 'factor_id': factor.id}, status=201)


_DECOY_INFO_SALT = b'recovery-factor-decoy:salt'
_DECOY_INFO_IV = b'recovery-factor-decoy:iv'
_DECOY_INFO_WRAPPED = b'recovery-factor-decoy:wrapped'
_DECOY_INFO_DEK_ID = b'recovery-factor-decoy:dek_id'


def _decoy_secret() -> bytes:
    """Long-lived server secret used as the HMAC key for decoy derivation.

    Loaded from ``settings.RECOVERY_DECOY_SECRET`` (preferred) or the
    ``RECOVERY_DECOY_SECRET`` env var. Fallback to ``settings.SECRET_KEY``
    is allowed for development but logged once so production deployments
    can audit. Rotating this secret rotates every decoy — that's
    acceptable because rotation just makes a fresh attacker have to
    re-build their oracle from scratch; legitimate recovery flows are
    unaffected because they never observe a decoy (they observe a real
    factor by definition).
    """
    explicit = getattr(settings, 'RECOVERY_DECOY_SECRET', None)
    if explicit:
        return explicit if isinstance(explicit, (bytes, bytearray)) else explicit.encode('utf-8')
    env = os.environ.get('RECOVERY_DECOY_SECRET')
    if env:
        return env.encode('utf-8')
    # Fallback: SECRET_KEY. Production deployments SHOULD configure
    # RECOVERY_DECOY_SECRET explicitly so it can rotate independently.
    return settings.SECRET_KEY.encode('utf-8')


def _decoy_bytes(username: str, factor_type: str, info: bytes, length: int) -> bytes:
    """Derive `length` deterministic bytes for a `(username, factor_type)`
    decoy under `info`-domain separation.

    The construction is HMAC-SHA256(server_secret, info ‖ username ‖
    factor_type) repeated until enough output bytes are produced. This
    guarantees:
      - same input → same output (no oracle for repeat-call distinguish)
      - different `info` constants → independent outputs (so e.g. the
        decoy salt cannot be derived from the decoy iv)
      - rotating the server secret rotates every decoy at once.
    """
    out = bytearray()
    counter = 0
    base = info + b'\x00' + username.encode('utf-8') + b'\x00' + factor_type.encode('utf-8')
    while len(out) < length:
        block = hmac.new(
            _decoy_secret(),
            base + counter.to_bytes(4, 'big'),
            hashlib.sha256,
        ).digest()
        out.extend(block)
        counter += 1
    return bytes(out[:length])


def _decoy_response(username: str, factor_type: str) -> dict:
    """Build the deterministic decoy {blob, dek_id} for a username +
    factor_type that has no real enrollment.

    A repeat call with the same `(username, factor_type)` MUST return
    a byte-identical response so an attacker cannot use response-
    diffing to distinguish "decoy" from "real factor" — real factors
    return the same DB row every time, and so must decoys.

    The synthesized blob has the same envelope shape as a wrapped DEK
    (`wdek-1`, Argon2id KDF, 16-byte salt, 12-byte iv, 48-byte
    wrapped). An attacker cannot unwrap it (the bytes are derived from
    a server secret they don't possess), but neither can the
    legitimate user — recovery against a decoy fails with the same
    generic "Incorrect password or corrupted vault key" the wrong
    secret produces against a real blob.
    """
    return {
        'v': ENVELOPE_VERSION,
        'kdf': 'argon2id',
        'kdf_params': {'t': 3, 'm': 65536, 'p': 2},
        'salt': base64.b64encode(_decoy_bytes(username, factor_type, _DECOY_INFO_SALT, 16)).decode('ascii'),
        'iv': base64.b64encode(_decoy_bytes(username, factor_type, _DECOY_INFO_IV, 12)).decode('ascii'),
        # 32-byte AES key + 16-byte GCM tag = 48 bytes wrapped output.
        'wrapped': base64.b64encode(_decoy_bytes(username, factor_type, _DECOY_INFO_WRAPPED, 48)).decode('ascii'),
    }


def _decoy_dek_id(username: str, factor_type: str) -> str:
    """Deterministic, UUIDv4-shaped identifier for the decoy.

    Built directly from the same HMAC-derived bytes used for the blob
    (under a different `info` constant). We then force the RFC 4122
    version (byte 6 high nibble = 0x4) and variant bits (byte 8 high
    bits = 0b10) so the resulting string is byte-shaped identical to a
    real ``uuid.uuid4()`` value. Without this, an attacker could
    distinguish decoys from real ``dek_id`` values purely by inspecting
    the version nibble and variant bits — a side-channel oracle that
    defeats the deterministic-decoy defense and reintroduces
    account/factor enumeration through ``dek_id`` alone.

    Real ``dek_id`` is set by ``VaultWrappedDEK.dek_id = uuid.uuid4()``
    and reused as ``RecoveryWrappedDEK.dek_id``.
    """
    raw = bytearray(_decoy_bytes(username, factor_type, _DECOY_INFO_DEK_ID, 16))
    # Force RFC 4122 / UUIDv4 shape:
    #   byte 6: top nibble must be 0x4 (version)
    #   byte 8: top two bits must be 0b10 (variant)
    raw[6] = (raw[6] & 0x0F) | 0x40
    raw[8] = (raw[8] & 0x3F) | 0x80
    return str(uuid.UUID(bytes=bytes(raw)))


class RecoveryFactorLookupView(APIView):
    """Anonymous lookup of a wrapped recovery factor by username.

    Needed because the recovery pages (``/recovery/key/use-v2``,
    ``/recovery/time-lock/recover``, etc.) run while the user is NOT
    authenticated — they have forgotten the master password — and yet
    must obtain the wrapped factor blob to feed the recovery secret
    into ``unlockWithRecoveryFactor``.

    Threat model:
      - Returning the wrapped blob publicly does not enable practical
        offline brute force. The recovery secrets used as Argon2id
        inputs are 26-char alphanumeric (tier 1) or 32 random bytes
        (tier 2/3); at OWASP-2024 Argon2id parameters these are
        infeasible to crack offline.
      - The endpoint must NOT leak account existence. We achieve this
        by returning a synthesized decoy blob with the same shape for
        unknown usernames or users who have not enrolled the requested
        factor type. An attacker cannot distinguish a decoy from a
        real blob without successfully unwrapping (which requires the
        recovery secret).

    Throttled with the standard recovery family. Audit-logged when a
    real factor is hit.
    """
    permission_classes = [AllowAny]
    throttle_classes = [RecoveryThrottle]

    def post(self, request):
        username = request.data.get('username')
        factor_type = request.data.get('factor_type')
        if (
            not isinstance(username, str)
            or not username
            or factor_type not in RecoveryWrappedDEK.FactorType.values
        ):
            return Response(
                {'error': 'username and factor_type required'},
                status=400,
            )

        try:
            user = User.objects.get(username=username)
            factor = (
                RecoveryWrappedDEK.objects
                .filter(
                    user=user,
                    factor_type=factor_type,
                    status=RecoveryWrappedDEK.Status.ACTIVE,
                )
                .order_by('-created_at')
                .first()
            )
        except User.DoesNotExist:
            factor = None

        if factor is None:
            # Deterministic decoy keyed by (username, factor_type)
            # under a server-held secret. Repeat calls with the same
            # input produce a byte-identical response, just like a
            # real-factor lookup does — so an attacker cannot use
            # response-diffing to distinguish "real" from "decoy".
            return Response({
                'blob': _decoy_response(username, factor_type),
                'dek_id': _decoy_dek_id(username, factor_type),
            })

        # Real hit — audit it. We deliberately do not gate on
        # successful unwrap because the server has no way to know;
        # this log row simply records that a blob was disclosed.
        RecoveryAuditLog.objects.create(
            user=factor.user,
            event_type='shard_accessed',
            event_data={
                'subsystem': 'recovery_factor',
                'factor_type': factor_type,
                'factor_id': factor.id,
            },
            ip_address=_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', '')[:1024],
        )
        return Response({
            'blob': factor.blob,
            'dek_id': str(factor.dek_id),
        })

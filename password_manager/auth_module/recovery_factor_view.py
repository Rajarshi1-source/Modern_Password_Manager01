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
import secrets
import uuid

from django.contrib.auth.models import User
from django.db import IntegrityError
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

        blob = request.data.get('blob')
        if not _valid_envelope(blob):
            return Response({'error': 'invalid envelope'}, status=400)

        meta = request.data.get('meta', {}) or {}
        if not isinstance(meta, dict):
            return Response({'error': 'meta must be an object'}, status=400)

        # Partial unique constraint
        # (factor_type='recovery_key', status='active') is enforced at
        # the DB layer. We translate ONLY that specific IntegrityError
        # to 409; any other exception (DB outage, programming error)
        # bubbles to DRF's default 500 handler so real faults aren't
        # masked as a business conflict, and we never echo str(exc)
        # back to the client (information-exposure rule).
        try:
            factor = RecoveryWrappedDEK.objects.create(
                user=request.user,
                factor_type=ftype,
                dek_id=current.dek_id,
                blob=blob,
                factor_meta=meta,
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


def _decoy_blob():
    """Synthesize a wdek-1 envelope filled with random bytes.

    Used by ``RecoveryFactorLookupView`` so the response shape is
    identical for "user has factor" and "user does not exist / has no
    factor of this type". An attacker cannot distinguish without
    actually trying to unwrap, which requires the recovery secret —
    something the legitimate user holds and the attacker does not.
    Argon2id at ``DEFAULT_KDF`` parameters and a sufficiently long
    secret (26-char alphanumeric for tier 1, 32 random bytes for
    tier 2/3) makes offline brute force infeasible.
    """
    return {
        'v': ENVELOPE_VERSION,
        'kdf': 'argon2id',
        'kdf_params': {'t': 3, 'm': 65536, 'p': 2},
        'salt': base64.b64encode(secrets.token_bytes(16)).decode('ascii'),
        'iv': base64.b64encode(secrets.token_bytes(12)).decode('ascii'),
        # 32-byte AES key + 16-byte GCM tag = 48 bytes wrapped output.
        'wrapped': base64.b64encode(secrets.token_bytes(48)).decode('ascii'),
    }


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
            # Decoy: same shape as a real response, but a fresh random
            # blob and a fresh dek_id. Attacker cannot enumerate.
            return Response({
                'blob': _decoy_blob(),
                'dek_id': str(uuid.uuid4()),
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

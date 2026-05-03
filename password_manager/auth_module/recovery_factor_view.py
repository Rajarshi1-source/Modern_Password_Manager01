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
from django.db import IntegrityError
from rest_framework.permissions import IsAuthenticated
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

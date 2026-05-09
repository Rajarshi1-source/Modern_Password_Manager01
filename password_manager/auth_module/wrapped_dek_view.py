"""
VaultWrappedDEKView — REST surface for the user's wrapped vault DEK.

Zero-knowledge boundary: the server stores the `blob` field as opaque
ciphertext. It is never decrypted server-side. This view validates only
the envelope shape (`v`, `kdf`, `kdf_params`, `salt`, `iv`, `wrapped`)
and never inspects the `wrapped` payload itself.

PUT semantics:
  - First PUT (no row exists): create the wrapped DEK, mint a stable
    `dek_id` (UUID).
  - Subsequent PUT (master-password rotation): client MUST send the
    existing `dek_id`. Refusing to clobber the DEK identity is what
    protects existing recovery factors (each row in
    `RecoveryWrappedDEK` references the same `dek_id`) from being
    silently orphaned.
"""
from django.contrib.auth.models import User
from django.db import transaction
from django.utils import timezone
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from auth_module.recovery_throttling import (
    RecoveryThrottle,
    RecoveryCompleteThrottle,
)
from auth_module.recovery_models_v2 import VaultWrappedDEK, RecoveryWrappedDEK
from auth_module.quantum_recovery_models import RecoveryAuditLog


# Wrapped-DEK envelope versioning. The client (sessionVaultCryptoV3.js)
# produces this exact shape; bumping the version requires both ends to
# agree.
ENVELOPE_VERSION = 'wdek-1'
_REQUIRED_FIELDS = ('kdf', 'kdf_params', 'salt', 'iv', 'wrapped')


def _valid_envelope(blob):
    """Validate the wrapped-DEK envelope shape WITHOUT decrypting it.

    Server never inspects `blob['wrapped']`. We check only that the
    envelope is the version we know how to store and round-trip.
    """
    if not isinstance(blob, dict) or blob.get('v') != ENVELOPE_VERSION:
        return False
    return all(k in blob for k in _REQUIRED_FIELDS)


def _client_ip(request):
    xff = request.META.get('HTTP_X_FORWARDED_FOR')
    if xff:
        return xff.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')


class VaultWrappedDEKView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [RecoveryThrottle]

    def get(self, request):
        try:
            row = VaultWrappedDEK.objects.get(user=request.user)
        except VaultWrappedDEK.DoesNotExist:
            return Response({'enrolled': False})
        return Response({
            'enrolled': True,
            'blob': row.blob,
            'dek_id': str(row.dek_id),
        })

    def put(self, request):
        blob = request.data.get('blob')
        if not _valid_envelope(blob):
            return Response({'error': 'invalid envelope'}, status=400)

        with transaction.atomic():
            row, created = (
                VaultWrappedDEK.objects
                .select_for_update()
                .get_or_create(user=request.user, defaults={'blob': blob})
            )
            if not created:
                # Master-password rotation. Same DEK, new KEK; client
                # MUST send the existing dek_id to prove DEK possession.
                if str(row.dek_id) != str(request.data.get('dek_id') or ''):
                    return Response({'error': 'dek_id mismatch'}, status=409)
                row.blob = blob
                row.rotated_at = timezone.now()
                row.save(update_fields=['blob', 'rotated_at', 'updated_at'])

        # Audit log: re-use existing event_types from RecoveryAuditLog.
        # `setup_created` / `setup_updated` semantically match enrollment
        # vs rotation; specifics live in event_data. (Adding new event
        # type values would only require updating the choices tuple,
        # not a DB migration, since EVENT_TYPES is form-level only.)
        RecoveryAuditLog.objects.create(
            user=request.user,
            event_type='setup_created' if created else 'setup_updated',
            event_data={
                'subsystem': 'wrapped_dek',
                'dek_id': str(row.dek_id),
                'action': 'enrolled' if created else 'rotated',
            },
            ip_address=_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', '')[:1024],
        )
        return Response({'success': True, 'dek_id': str(row.dek_id)})


class WrappedDEKRecoveryRotateView(APIView):
    """Anonymous rotation of the master-wrapped DEK after a recovery.

    Why this exists: ``VaultWrappedDEKView.put`` is `IsAuthenticated`,
    but the recovery pages (``/recovery/key/use-v2``,
    ``/recovery/time-lock/recover``, etc.) run BEFORE the user is
    authenticated — they can't authenticate normally because they
    forgot the master password. They have just unwrapped the DEK
    locally using a recovery secret, re-wrapped it under a new
    master-password KEK, and now need to PUT the new envelope to the
    server. Without this anonymous endpoint, the rotation would 401
    and the user would still be locked out on next login.

    Request: ``{username, factor_type, dek_id, blob}``

    Authorization model:

      - The endpoint requires the caller to know the user's CURRENT
        ``dek_id``, which is only obtainable via a successful
        ``recovery-factors/lookup/`` (or for an unknown user, via
        coincidence with a decoy — but the decoy ``dek_id`` would
        never match an existing ``VaultWrappedDEK.dek_id``, so the
        write here would be rejected).
      - The caller must also reference an enrolled ``factor_type``
        which actually exists for the user.
      - The throttle (``RecoveryCompleteThrottle``) and the audit log
        cover abuse.

    Trade-off: an attacker who knows ``username`` AND can call lookup
    AND has gotten a real (not decoy) blob can submit a malformed
    new envelope and DESTROY the user's vault by replacing the
    master-wrapped row with one that wraps no actual DEK. They
    cannot EXFILTRATE anything — the wrapped envelope is opaque on
    both old and new sides — so the worst case is temporary DoS,
    which the user can remediate by performing recovery again
    (recovery factors are unaffected by master-row writes). ZK is
    preserved either way.
    """

    permission_classes = [AllowAny]
    throttle_classes = [RecoveryCompleteThrottle]

    def post(self, request):
        import hmac as _hmac

        username = request.data.get('username')
        factor_type = request.data.get('factor_type')
        dek_id_in = request.data.get('dek_id')
        blob = request.data.get('blob')
        # auth_hash is the proof-of-secret-knowledge: SHA-256 of
        # "rotation-auth-v1:" || recovery_secret, set at enrollment
        # and stored on the factor row. The lookup endpoint does NOT
        # disclose this value, so an attacker who only hit lookup has
        # everything *except* this hash and cannot rotate.
        auth_hash_in = request.data.get('auth_hash')

        if (
            not isinstance(username, str)
            or not username
            or factor_type not in RecoveryWrappedDEK.FactorType.values
            or not isinstance(dek_id_in, str)
            or not dek_id_in
            or not isinstance(auth_hash_in, str)
            or len(auth_hash_in) != 64
        ):
            return Response(
                {'error': 'username, factor_type, dek_id, and auth_hash required'},
                status=400,
            )
        if not _valid_envelope(blob):
            return Response({'error': 'invalid envelope'}, status=400)

        # Look up the user. We do NOT leak existence here either —
        # the same generic 'recovery target not found' covers both
        # 'no such user' and 'user exists but no matching factor /
        # mismatched dek_id'. An attacker probing usernames sees a
        # uniform error.
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            return Response({'error': 'recovery target not found'}, status=404)

        with transaction.atomic():
            try:
                wrapped_row = (
                    VaultWrappedDEK.objects
                    .select_for_update()
                    .get(user=user)
                )
            except VaultWrappedDEK.DoesNotExist:
                return Response(
                    {'error': 'recovery target not found'},
                    status=404,
                )

            # Caller must know the EXISTING dek_id. Only a successful
            # recovery-factors/lookup/ surfaces that value to a non-
            # authenticated client, and the server-side decoy path
            # synthesizes a UUIDv4 that won't match any real wrapped
            # DEK row. So this check ties the rotation to a real
            # factor enrollment.
            if str(wrapped_row.dek_id) != dek_id_in:
                return Response(
                    {'error': 'recovery target not found'},
                    status=404,
                )

            # Caller must reference a factor_type that the user
            # actually has enrolled AND must demonstrate possession
            # of the recovery secret via auth_hash. Without the
            # auth_hash check, the rotation endpoint trusts only
            # dek_id, which is freely obtainable from the anonymous
            # lookup endpoint — an attacker could then DoS any
            # vault by submitting a garbage envelope. The auth_hash
            # is computed client-side from the recovery secret, has
            # ≥130 bits of preimage resistance for tier-1 secrets
            # (32^26 alphabet) and ≥256 for tier 2/3, so it cannot
            # be brute-forced offline even on full DB exfiltration.
            #
            # The row is locked with select_for_update() inside the
            # outer transaction so a concurrent revoke / re-enroll
            # cannot race past this read and let an old recovery
            # secret authorize one last rotation.
            factor = (
                RecoveryWrappedDEK.objects
                .select_for_update()
                .filter(
                    user=user,
                    factor_type=factor_type,
                    status=RecoveryWrappedDEK.Status.ACTIVE,
                )
                .order_by('-created_at')
                .first()
            )
            if factor is None:
                return Response(
                    {'error': 'recovery target not found'},
                    status=404,
                )

            # Empty stored auth_hash means the row was created
            # before this field existed (i.e. on a deployment that
            # ran an earlier version of the layered-recovery code).
            # The server has nothing to compare against, so we cannot
            # safely accept the rotation: trusting any submitted
            # auth_hash on a legacy row would let an attacker who
            # only hit lookup take ownership of the rotation by
            # being the first to submit a hash. Instead, surface a
            # distinguishable status so the client can show an
            # actionable message — the user must re-enroll the
            # factor (which writes a real auth_hash) before recovery
            # via this endpoint will work.
            if not factor.auth_hash:
                return Response(
                    {
                        'error': 'recovery factor pre-dates auth_hash',
                        're_enroll_required': True,
                        'detail': (
                            'This recovery factor was enrolled before the '
                            'rotation auth_hash existed. Sign in with your '
                            'master password (or another active recovery '
                            'factor) and re-enroll this factor to refresh it.'
                        ),
                    },
                    status=409,
                )

            # Constant-time comparison so a partial match doesn't
            # leak timing information.
            if not _hmac.compare_digest(
                factor.auth_hash.lower(), auth_hash_in.lower(),
            ):
                return Response(
                    {'error': 'recovery target not found'},
                    status=404,
                )

            wrapped_row.blob = blob
            wrapped_row.rotated_at = timezone.now()
            wrapped_row.save(
                update_fields=['blob', 'rotated_at', 'updated_at'],
            )

            RecoveryAuditLog.objects.create(
                user=user,
                event_type='setup_updated',
                event_data={
                    'subsystem': 'wrapped_dek',
                    'dek_id': str(wrapped_row.dek_id),
                    'action': 'recovery_rotation',
                    'factor_type': factor_type,
                },
                ip_address=_client_ip(request),
                user_agent=request.META.get('HTTP_USER_AGENT', '')[:1024],
            )

        return Response({'success': True, 'dek_id': str(wrapped_row.dek_id)})

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
from django.db import transaction
from django.utils import timezone
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from auth_module.recovery_throttling import RecoveryThrottle
from auth_module.recovery_models_v2 import VaultWrappedDEK
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

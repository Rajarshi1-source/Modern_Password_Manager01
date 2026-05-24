"""Vault backup API.

Zero-knowledge contract
-----------------------
The server NEVER sees the user's key-encrypting-key (KEK) or any material
from which it could be derived. Envelope encryption is performed entirely
client-side: the client derives the KEK from the master password, generates
a random data-encryption key (DEK), wraps the DEK under the KEK, and POSTs
the already-sealed envelope to ``create_backup``. The server stores the
ciphertext verbatim.

On restore, the server returns the stored ciphertext (or a presigned URL to
it for cloud-stored backups). The client unwraps the envelope locally and
either restores items directly or POSTs the decrypted (but still
field-level encrypted) item list back to ``restore`` for batch insert.

This module previously accepted a plaintext ``encryption_key`` field and
ran ``PBKDF2 -> AES-GCM`` on the server. That was a zero-knowledge
violation: a DB dump combined with captured request bodies (or memory
forensics on the server) recovered the master-key material. The endpoint
now refuses such payloads outright; see ``BACKUP_REQUIRE_CLIENT_ENVELOPE``
in settings for the rollout flag.
"""

from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from vault.models.vault_models import EncryptedVaultItem
from vault.models.backup_models import VaultBackup
from vault.serializer import BackupSerializer, VaultItemSerializer
from vault.services.cloud_storage import CloudStorageService
import base64
import json
import logging
from typing import Optional

from password_manager.api_utils import error_response, success_response

logger = logging.getLogger(__name__)

# Placeholder row while payload lives only in object storage (valet-key upload flow).
CLOUD_ONLY_PAYLOAD_META = {'cloud_only': True, 'v': 1}

# Shape of a v1 client-sealed envelope. The server validates that all
# required keys are present and base64-decodable but never inspects the
# wrapped bytes themselves.
ENVELOPE_VERSION_V1 = 'envelope-v1'
_ENVELOPE_REQUIRED_KEYS = (
    'encrypted_data',
    'data_nonce',
    'wrapped_dek',
    'kek_nonce',
)
# AES-GCM constants used only for sanity-checking envelope shape — the
# server does NOT perform any AES operation on backup payloads.
_GCM_NONCE_LEN = 12
_MIN_AESGCM_CT_LEN = 16  # GCM authentication tag length

# Fields that, if present in a stored blob, indicate the client tried
# to smuggle a key-encrypting-key. Used by the cloud-upload validator.
_KEK_FIELD_NAMES = ('encryption_key', 'kek', 'wrapping_key', 'master_key')


def _scan_for_kek_fields(node) -> Optional[str]:
    """Walk a parsed-JSON structure looking for KEK-alias keys.

    Returns the first offending key path found, or ``None`` if the
    structure is clean. Used after a client direct-PUTs to object
    storage to verify the blob doesn't carry a plaintext KEK.
    """
    if isinstance(node, dict):
        for key, value in node.items():
            if key in _KEK_FIELD_NAMES and value not in (None, '', [], {}):
                return key
            nested = _scan_for_kek_fields(value)
            if nested is not None:
                return f"{key}.{nested}" if nested else key
    elif isinstance(node, list):
        for i, item in enumerate(node):
            nested = _scan_for_kek_fields(item)
            if nested is not None:
                return f"[{i}].{nested}" if nested else f"[{i}]"
    return None


def _validate_cloud_blob(blob_text: str) -> str:
    """Validate a backup blob fetched from object storage post-upload.

    Returns ``''`` on success, else a human-readable error message.

    Accepts two shapes:

    1. A v1 envelope (``{"version": "envelope-v1", ...}``) — validated
       by :func:`_validate_envelope`. This is the zero-knowledge path.
    2. A legacy plain-JSON backup (``{"items": [...], ...}``) — checked
       for any KEK-alias field at any depth, since the historical
       create_backup path would dump those into the blob unencrypted.

    The blob MUST be JSON. Opaque/binary uploads are rejected because
    the server cannot tell whether they carry KEK material; clients
    using the valet-key path must base64-encode envelope fields and
    JSON-serialise them, matching the v1 envelope contract.
    """
    if not blob_text:
        return "uploaded blob is empty"
    try:
        parsed = json.loads(blob_text)
    except (json.JSONDecodeError, TypeError, ValueError):
        return (
            "uploaded blob is not valid JSON; the cloud-upload path "
            "requires a JSON-encoded v1 envelope"
        )
    if not isinstance(parsed, dict):
        return "uploaded blob must be a JSON object"
    if parsed.get('version') == ENVELOPE_VERSION_V1:
        # Same validator the synchronous create_backup path uses.
        return _validate_envelope(parsed)
    # Plain-JSON backup: scan recursively for smuggled KEK fields.
    smuggled = _scan_for_kek_fields(parsed)
    if smuggled:
        return (
            f"uploaded blob contains a KEK-alias field ({smuggled}); "
            "the server must not store plaintext key material"
        )
    return ''


# Counter for canary observability. Operators can poll
# ``backup_views._kek_rejection_stats`` (or hook it into Prometheus via
# a dedicated exporter) to watch the legacy-client traffic curve
# approach zero before flipping the enforcement mode to ``strict``.
_kek_rejection_stats = {
    'strict_400': 0,
    'header_400': 0,
    'header_422': 0,
    'off_422': 0,
}


def _resolve_enforcement_mode():
    """Return the effective enforcement mode, normalised + validated.

    Reading at call time (rather than module-import time) means tests can
    flip the setting via ``override_settings``/``self.settings(...)``
    without resetting the import cache.
    """
    mode = getattr(settings, 'BACKUP_ENVELOPE_ENFORCEMENT', None)
    if mode in ('strict', 'header', 'off'):
        return mode
    # Fall back to the legacy boolean for back-compat.
    return 'strict' if getattr(settings, 'BACKUP_REQUIRE_CLIENT_ENVELOPE', True) else 'off'


def _client_claims_v2(request) -> bool:
    """True if the client announced a migrated build via the canary header.

    The header value is opaque: any non-empty string counts. We don't
    pin it to a specific version today so the server doesn't have to
    ship a new build every time a client bumps its envelope-handling
    version.
    """
    header_name = getattr(
        settings,
        'BACKUP_ENVELOPE_CLIENT_VERSION_HEADER',
        'HTTP_X_BACKUP_ENVELOPE_CLIENT_VERSION',
    )
    meta = getattr(request, 'META', {}) or {}
    value = meta.get(header_name, '')
    return bool(value and str(value).strip())


def _reject_plaintext_kek(request):
    """Return a ready-to-send error response if the payload carries an
    ``encryption_key`` field (or any equivalent KEK material), else None.

    Accepting the plaintext KEK on the server defeats the zero-knowledge
    contract the rest of the codebase enforces. We refuse outright. The
    rollout mode (``BACKUP_ENVELOPE_ENFORCEMENT``) controls only the
    response surface — in EVERY mode the server discards the supplied
    KEK without using it.

    Modes
    -----
    ``strict``
        Always 400 ``zero_knowledge_violation``. Default; correct end
        state once all clients have migrated.

    ``header``
        Canary mode. Clients that announce themselves via
        ``X-Backup-Envelope-Client-Version`` get the strict 400 (they
        regressed). Clients without the header are presumed pre-
        migration and get a 422 ``zero_knowledge_violation_deprecated``
        so their UI can surface a clear "update your client" message
        rather than an opaque error.

    ``off``
        Always 422 deprecation. Last-resort rollback switch.
    """
    data = request.data if hasattr(request, 'data') else {}
    rejected_fields = [
        f for f in ('encryption_key', 'kek', 'wrapping_key', 'master_key')
        if data.get(f)
    ]
    if not rejected_fields:
        return None

    mode = _resolve_enforcement_mode()
    user_id = getattr(getattr(request, 'user', None), 'id', '<anon>')
    claims_v2 = _client_claims_v2(request)

    # Decide which response shape to emit.
    if mode == 'strict' or (mode == 'header' and claims_v2):
        bucket = 'strict_400' if mode == 'strict' else 'header_400'
        _kek_rejection_stats[bucket] += 1
        logger.warning(
            "backup KEK rejected (mode=%s, user=%s, claims_v2=%s, "
            "fields=%s): hard 400",
            mode, user_id, claims_v2, rejected_fields,
        )
        return error_response(
            (
                "Plaintext encryption_key is not accepted. Derive the KEK "
                "client-side, wrap the backup envelope locally, and POST "
                "the sealed envelope object instead. See the backup API "
                "documentation for the v1 envelope schema."
            ),
            status_code=status.HTTP_400_BAD_REQUEST,
            code='zero_knowledge_violation',
            details={
                'expected_field': 'envelope',
                'rejected_fields': rejected_fields,
                'enforcement_mode': mode,
                'client_claims_v2': claims_v2,
            },
        )

    # ``header`` mode + no v2 header, OR ``off`` mode: soft 422 so legacy
    # clients can surface an upgrade prompt to the user.
    bucket = 'header_422' if mode == 'header' else 'off_422'
    _kek_rejection_stats[bucket] += 1
    logger.warning(
        "backup KEK deprecated (mode=%s, user=%s, claims_v2=%s, "
        "fields=%s): soft 422 — legacy client still in field",
        mode, user_id, claims_v2, rejected_fields,
    )
    return error_response(
        (
            "Plaintext encryption_key is deprecated and was ignored. "
            "Upgrade the client to send a sealed envelope; this lenient "
            "mode will be removed once the canary rollout completes."
        ),
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        code='zero_knowledge_violation_deprecated',
        details={
            'expected_field': 'envelope',
            'enforcement_mode': mode,
            'client_claims_v2': claims_v2,
            'upgrade_required': True,
        },
    )


def _validate_envelope(envelope) -> str:
    """Return '' if the envelope shape is acceptable, else an error message.

    Validation is structural only — the server cannot (and must not) verify
    that the wrapped bytes decrypt to anything meaningful, because it does
    not hold the KEK. Rejecting malformed envelopes early prevents storing
    garbage that the client would later fail to decrypt with a confusing
    error.
    """
    if not isinstance(envelope, dict):
        return "envelope must be a JSON object"
    # Reject ANY field outside the strict allow-list. Without this an
    # attacker (or a buggy client) could smuggle a plaintext KEK back in
    # via e.g. ``{"envelope": {..., "encryption_key": "<secret>"}}`` and
    # the server would store it verbatim through the "safe" path —
    # silently breaking the zero-knowledge guarantee.
    allowed_keys = {'version', *_ENVELOPE_REQUIRED_KEYS}
    unexpected = sorted(set(envelope) - allowed_keys)
    if unexpected:
        return f"envelope contains unexpected fields: {', '.join(unexpected)}"
    version = envelope.get('version')
    if version != ENVELOPE_VERSION_V1:
        return f"unsupported envelope version: {version!r}"
    for key in _ENVELOPE_REQUIRED_KEYS:
        value = envelope.get(key)
        if not isinstance(value, str) or not value:
            return f"envelope missing required field: {key}"
        try:
            decoded = base64.b64decode(value, validate=True)
        except (ValueError, TypeError, base64.binascii.Error):
            return f"envelope field {key} is not valid base64"
        if key.endswith('_nonce') and len(decoded) != _GCM_NONCE_LEN:
            return f"envelope {key} must be a 12-byte AES-GCM nonce"
        if key in ('encrypted_data', 'wrapped_dek') and len(decoded) < _MIN_AESGCM_CT_LEN:
            return f"envelope {key} is too short to be a valid AES-GCM ciphertext"
    return ''


class BackupViewSet(viewsets.ModelViewSet):
    """API endpoints for vault backups (zero-knowledge)."""
    permission_classes = [IsAuthenticated]
    serializer_class = BackupSerializer

    def get_queryset(self):
        """Return only backups belonging to authenticated user"""
        return VaultBackup.objects.filter(user=self.request.user)

    # ------------------------------------------------------------------
    # Create
    # ------------------------------------------------------------------
    @action(detail=False, methods=['post'])
    def create_backup(self, request):
        """Create a new vault backup.

        Two acceptable payload shapes:

        1. ``{"envelope": {...}, "name": "..."}`` — the client has already
           performed envelope encryption locally. The server stores the
           envelope JSON verbatim.
        2. ``{"name": "..."}`` (no envelope) — store the list of
           field-level-encrypted vault items as plain JSON. Items are
           still individually encrypted client-side; the only thing the
           envelope adds is hiding the list of item IDs from a DB reader.

        ANY payload containing ``encryption_key`` (or other plaintext KEK
        material) is rejected — see ``_reject_plaintext_kek``.
        """
        rejection = _reject_plaintext_kek(request)
        if rejection is not None:
            return rejection

        # Validate envelope (if supplied) BEFORE doing any DB work.
        envelope = request.data.get('envelope')
        is_envelope_encrypted = False
        if envelope is not None:
            err = _validate_envelope(envelope)
            if err:
                return error_response(
                    f"Invalid backup envelope: {err}",
                    status_code=status.HTTP_400_BAD_REQUEST,
                    code='invalid_envelope',
                )
            is_envelope_encrypted = True

        with transaction.atomic():
            vault_items = EncryptedVaultItem.objects.filter(
                user=request.user,
                deleted=False,
            )

            items_data = [
                {
                    'id': str(item.id),
                    'item_id': item.item_id,
                    'item_type': item.item_type,
                    'encrypted_data': item.encrypted_data,
                    'created_at': item.created_at.isoformat(),
                    'updated_at': item.updated_at.isoformat(),
                    'favorite': item.favorite,
                    'tags': item.tags,
                }
                for item in vault_items
            ]

            if is_envelope_encrypted:
                # Client has already sealed the items list. Store the
                # envelope verbatim; the server has no way to inspect it.
                stored_data = json.dumps(envelope)
                # Item count cannot be derived from the ciphertext; record
                # the server-side count for the response only (a UX hint).
                server_item_count = len(items_data)
                logger.info(
                    "Backup created (envelope-v1) for user %s with %d items",
                    request.user.id,
                    server_item_count,
                )
            else:
                backup_data = {
                    'version': '1.0',
                    'created_at': timezone.now().isoformat(),
                    'item_count': len(items_data),
                    'items': items_data,
                }
                stored_data = json.dumps(backup_data)
                server_item_count = len(items_data)

            backup = VaultBackup.objects.create(
                user=request.user,
                name=request.data.get(
                    'name', f"Backup {timezone.now().strftime('%Y-%m-%d %H:%M')}"
                ),
                encrypted_data=stored_data,
                size=len(stored_data),
            )

            cloud_service = CloudStorageService()
            cloud_path = cloud_service.upload_backup(
                request.user.id,
                stored_data,
                str(backup.id),
            )

            if cloud_path:
                backup.cloud_storage_path = cloud_path
                backup.cloud_sync_status = 'synced'
                backup.save()

            return Response({
                'id': backup.id,
                'name': backup.name,
                'created_at': backup.created_at,
                'item_count': server_item_count,
                'size': backup.size,
                'cloud_synced': backup.cloud_sync_status == 'synced',
                'envelope_encrypted': is_envelope_encrypted,
            })

    # ------------------------------------------------------------------
    # Direct cloud-upload (valet-key) flow — unchanged
    # ------------------------------------------------------------------
    @action(detail=False, methods=['post'], url_path='start-cloud-upload')
    def start_cloud_upload(self, request):
        """Create DB row and return a presigned PUT URL.

        The client uploads the already-sealed envelope bytes directly to
        object storage. The server never sees the KEK or the envelope's
        plaintext.
        """
        rejection = _reject_plaintext_kek(request)
        if rejection is not None:
            return rejection

        cloud_service = CloudStorageService()
        if not cloud_service.supports_presigned_urls:
            return error_response(
                'Cloud storage is not configured for presigned URLs '
                '(set CLOUD_STORAGE_BUCKET or AWS_STORAGE_BUCKET_NAME and credentials).',
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        name = request.data.get(
            'name',
            f"Cloud backup {timezone.now().strftime('%Y-%m-%d %H:%M')}",
        )
        with transaction.atomic():
            backup = VaultBackup.objects.create(
                user=request.user,
                name=name,
                encrypted_data=json.dumps(CLOUD_ONLY_PAYLOAD_META),
                size=0,
                cloud_sync_status='pending',
            )
            cloud_path = f'backups/{request.user.id}/{backup.id}'
            backup.cloud_storage_path = cloud_path
            backup.save(update_fields=['cloud_storage_path'])

        presigned = cloud_service.generate_presigned_put_url(
            cloud_path,
            content_type='application/octet-stream',
        )
        if not presigned:
            backup.delete()
            return error_response(
                'Could not generate upload URL',
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        return Response({
            'backup_id': str(backup.id),
            'upload_url': presigned['url'],
            'method': 'PUT',
            'headers': {'Content-Type': 'application/octet-stream'},
            'cloud_path': cloud_path,
            'expires_in': presigned['expires_in'],
            'backend': presigned['backend'],
        })

    @action(detail=True, methods=['post'], url_path='complete-cloud-upload')
    def complete_cloud_upload(self, request, pk=None):
        """Confirm a presigned-upload completed and validate the blob.

        The valet-key path lets the client PUT the backup payload
        directly to object storage, bypassing our request body. That
        means the zero-knowledge checks the synchronous ``create_backup``
        endpoint enforces would otherwise be skipped here — a legacy
        client could PUT a plaintext backup (or smuggle ``encryption_key``
        into the envelope dict) and the server would silently mark it
        synced.

        Before flipping ``cloud_sync_status`` to ``synced`` we therefore
        fetch the uploaded blob, parse it, and run the same KEK-alias
        / envelope-shape validation the in-band path uses. Validation
        failure transitions the row to ``failed`` and returns 400 with
        the specific error so the client can fix and re-upload.
        """
        rejection = _reject_plaintext_kek(request)
        if rejection is not None:
            return rejection

        backup = self.get_object()
        try:
            size = int(request.data.get('size', 0))
        except (TypeError, ValueError):
            size = 0

        if not backup.cloud_storage_path:
            return error_response(
                'Backup has no cloud_storage_path to validate against',
                status_code=status.HTTP_400_BAD_REQUEST,
                code='no_cloud_path',
            )

        cloud_service = CloudStorageService()
        try:
            blob = cloud_service.download_backup(backup.cloud_storage_path)
        except Exception as exc:
            logger.exception("cloud download failed during validation")
            backup.cloud_sync_status = 'failed'
            backup.save(update_fields=['cloud_sync_status'])
            return error_response(
                f'Failed to validate uploaded blob: {exc}',
                status_code=status.HTTP_502_BAD_GATEWAY,
                code='cloud_download_failed',
            )

        if blob is None:
            backup.cloud_sync_status = 'failed'
            backup.save(update_fields=['cloud_sync_status'])
            return error_response(
                'Uploaded object not found in cloud storage',
                status_code=status.HTTP_400_BAD_REQUEST,
                code='cloud_object_missing',
            )
        blob_text = blob.decode('utf-8') if isinstance(blob, bytes) else blob

        validation_error = _validate_cloud_blob(blob_text)
        if validation_error:
            logger.warning(
                "complete_cloud_upload rejected blob for backup %s: %s",
                backup.id, validation_error,
            )
            backup.cloud_sync_status = 'failed'
            backup.save(update_fields=['cloud_sync_status'])
            return error_response(
                validation_error,
                status_code=status.HTTP_400_BAD_REQUEST,
                code='invalid_cloud_blob',
            )

        backup.size = size if size > 0 else len(blob_text)
        backup.cloud_sync_status = 'synced'
        backup.save(update_fields=['size', 'cloud_sync_status'])
        return Response({
            'success': True,
            'backup_id': str(backup.id),
            'size': backup.size,
            'cloud_sync_status': backup.cloud_sync_status,
        })

    @action(detail=True, methods=['get'], url_path='cloud-download-url')
    def cloud_download_url(self, request, pk=None):
        """Return a short-lived presigned GET URL for backups stored in object storage."""
        backup = self.get_object()
        if not backup.cloud_storage_path:
            return error_response(
                'No cloud object for this backup',
                status_code=status.HTTP_404_NOT_FOUND,
            )
        cloud_service = CloudStorageService()
        presigned = cloud_service.generate_presigned_get_url(backup.cloud_storage_path)
        if not presigned:
            return error_response(
                'Could not generate download URL',
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        return Response({
            'download_url': presigned['url'],
            'expires_in': presigned['expires_in'],
            'backend': presigned['backend'],
        })

    # ------------------------------------------------------------------
    # Ciphertext fetch (for client-side decryption of envelope backups)
    # ------------------------------------------------------------------
    @action(detail=True, methods=['get'], url_path='ciphertext')
    def ciphertext(self, request, pk=None):
        """Return the raw stored backup blob so the client can decrypt locally.

        For envelope-encrypted backups, this is the only way to read the
        ciphertext without round-tripping through the cloud presigned URL.
        The response shape is::

            {"format": "envelope-v1" | "plaintext-json", "data": <object>}

        The server attaches NO KEK material and performs NO decryption.
        """
        backup = self.get_object()
        raw_data = backup.encrypted_data

        # Cloud-only stub -> fetch from object storage transparently.
        try:
            stub = json.loads(raw_data) if raw_data else {}
        except (json.JSONDecodeError, TypeError):
            stub = {}
        if (
            stub.get('cloud_only')
            and stub.get('v') == CLOUD_ONLY_PAYLOAD_META['v']
            and backup.cloud_storage_path
        ):
            cloud_service = CloudStorageService()
            blob = cloud_service.download_backup(backup.cloud_storage_path)
            if not blob:
                return error_response(
                    'Failed to download backup from cloud',
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )
            raw_data = (
                blob.decode('utf-8') if isinstance(blob, bytes) else blob
            )

        try:
            parsed = json.loads(raw_data) if raw_data else {}
        except (json.JSONDecodeError, TypeError):
            return error_response(
                'Stored backup is not valid JSON',
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        fmt = (
            'envelope-v1'
            if parsed.get('version') == ENVELOPE_VERSION_V1
            else 'plaintext-json'
        )
        return Response({
            'backup_id': str(backup.id),
            'format': fmt,
            'data': parsed,
        })

    # ------------------------------------------------------------------
    # Restore
    # ------------------------------------------------------------------
    @action(detail=True, methods=['post'])
    def restore(self, request, pk=None):
        """Restore vault items from a backup.

        Modes:

        * **Client-supplied items** (preferred for envelope backups):
          ``{"items": [...]}`` — the client has already decrypted the
          envelope locally and POSTs the (still field-level encrypted)
          item list. The server batch-writes them and never sees plaintext
          KEK material.

        * **Plain-JSON backup** (legacy or items-already-individually
          encrypted): ``{}`` — server reads the stored blob, which must be
          ``{"items": [...]}``, and restores from it.

        * **Envelope backup with no client-supplied items**: returns a
          ``422 envelope_requires_client_decryption`` with the stored
          ciphertext attached so the client can decrypt and re-call. The
          server never attempts to decrypt itself.
        """
        rejection = _reject_plaintext_kek(request)
        if rejection is not None:
            return rejection

        try:
            backup = self.get_object()
        except VaultBackup.DoesNotExist:
            return error_response(
                'Backup not found', status_code=status.HTTP_404_NOT_FOUND,
            )

        with transaction.atomic():
            # Mode 1: client supplied decrypted items directly.
            client_items = request.data.get('items')
            if client_items is not None:
                if not isinstance(client_items, list):
                    return error_response(
                        '"items" must be a list',
                        status_code=status.HTTP_400_BAD_REQUEST,
                        code='invalid_items',
                    )
                return self._restore_from_items(
                    request, backup, client_items,
                )

            # Mode 2/3: try to read the stored blob.
            raw_data = backup.encrypted_data
            try:
                stub = json.loads(raw_data) if raw_data else {}
            except (json.JSONDecodeError, TypeError):
                stub = {}
            if (
                stub.get('cloud_only')
                and stub.get('v') == CLOUD_ONLY_PAYLOAD_META['v']
                and backup.cloud_storage_path
            ):
                cloud_service = CloudStorageService()
                blob = cloud_service.download_backup(backup.cloud_storage_path)
                if not blob:
                    return error_response(
                        'Failed to download backup from cloud',
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    )
                raw_data = (
                    blob.decode('utf-8') if isinstance(blob, bytes) else blob
                )
            elif not raw_data and backup.cloud_storage_path:
                cloud_service = CloudStorageService()
                raw_data = cloud_service.download_backup(
                    backup.cloud_storage_path,
                )
                if not raw_data:
                    return error_response(
                        'Failed to download backup from cloud',
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    )
                if isinstance(raw_data, bytes):
                    raw_data = raw_data.decode('utf-8')

            try:
                parsed = json.loads(raw_data)
            except (json.JSONDecodeError, TypeError):
                return error_response(
                    'Stored backup is not valid JSON',
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )

            # Mode 3: envelope -> tell the client to decrypt locally.
            if parsed.get('version') == ENVELOPE_VERSION_V1:
                return error_response(
                    (
                        'Backup is envelope-encrypted. Decrypt the envelope '
                        'client-side and re-call this endpoint with the '
                        'decrypted items list as "items".'
                    ),
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    code='envelope_requires_client_decryption',
                    details={'envelope': parsed},
                )

            # Mode 2: plain-JSON backup. An empty ``items`` list is a
            # legitimate state — a user can back up an empty vault and
            # later restore it without losing the "this backup exists"
            # signal — so only reject when ``items`` is missing entirely
            # or the wrong shape.
            items = parsed.get('items')
            if items is None or not isinstance(items, list):
                return error_response(
                    'Invalid backup data',
                    status_code=status.HTTP_400_BAD_REQUEST,
                )
            return self._restore_from_items(request, backup, items)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    # Audit-fix H2: hard ceiling on a single restore. Set high enough
    # not to bother power users but low enough that a malicious or
    # buggy backup with ``"items": [{}] * 10_000_000`` is rejected
    # before any DB work happens. Configurable via settings for ops
    # who genuinely need higher.
    MAX_RESTORE_ITEMS = 100_000

    # Required keys on every item in the restore payload. We don't
    # validate the SHAPE of `encrypted_data` (it's an opaque client-
    # sealed envelope) but we DO require the field exists and that
    # `item_id` is present so the update_or_create lookup is well-
    # defined. Strict schema is enforced before any destructive
    # `clear_existing` runs.
    _RESTORE_REQUIRED_KEYS = ('item_id', 'encrypted_data')

    def _validate_restore_payload(self, items):
        """
        Strictly validate the restore payload. Returns ``None`` on
        success or a Response on failure. No DB writes have happened
        at the point this is called.
        """
        from django.conf import settings as _settings
        max_items = int(getattr(
            _settings, 'VAULT_BACKUP_MAX_RESTORE_ITEMS', self.MAX_RESTORE_ITEMS
        ))

        if not isinstance(items, list):
            return error_response(
                message="Restore payload 'items' must be a list.",
                code="invalid_restore_payload",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        if len(items) > max_items:
            return error_response(
                message=(
                    f"Backup too large: {len(items)} items exceeds the "
                    f"server limit of {max_items}. Split the backup or "
                    "raise VAULT_BACKUP_MAX_RESTORE_ITEMS in settings."
                ),
                code="restore_too_large",
                status_code=status.HTTP_400_BAD_REQUEST,
                details={'item_count': len(items), 'limit': max_items},
            )
        # Audit-fix (PR #272 review): track item_id uniqueness during
        # validation. _restore_from_items uses `update_or_create(user,
        # item_id=...)`, so a payload with two entries sharing the
        # same item_id would silently let the second clobber the
        # first — making restore output order-dependent and losing
        # data with no error reported. Reject the whole batch instead.
        seen_item_ids: set = set()
        for idx, item in enumerate(items):
            if not isinstance(item, dict):
                return error_response(
                    message=f"Restore item at index {idx} is not a JSON object.",
                    code="invalid_restore_item",
                    status_code=status.HTTP_400_BAD_REQUEST,
                )
            missing = [k for k in self._RESTORE_REQUIRED_KEYS if not item.get(k)]
            if missing:
                return error_response(
                    message=(
                        f"Restore item at index {idx} is missing required "
                        f"fields: {', '.join(missing)}"
                    ),
                    code="invalid_restore_item",
                    status_code=status.HTTP_400_BAD_REQUEST,
                    details={'index': idx, 'missing': missing},
                )
            item_id = item['item_id']
            if item_id in seen_item_ids:
                return error_response(
                    message=(
                        f"Duplicate item_id in restore payload at index "
                        f"{idx}: {item_id!r}. Each item must have a "
                        "unique item_id; the restore was aborted before "
                        "any DB writes."
                    ),
                    code="duplicate_restore_item_id",
                    status_code=status.HTTP_400_BAD_REQUEST,
                    details={'index': idx, 'item_id': item_id},
                )
            seen_item_ids.add(item_id)
        return None

    def _restore_from_items(self, request, backup, items):
        """
        Batch-write a list of (already field-level encrypted) items.

        Audit-fix H2: the previous version performed ``clear_existing``
        UP FRONT and then looped over arbitrarily-large ``items``. A
        malicious backup with millions of entries OOM-ed the worker
        AFTER the live vault was wiped — leaving the user with
        nothing. We now:
          (1) validate the entire payload (size + per-item schema)
              before touching any DB row;
          (2) run delete + inserts inside a single atomic transaction
              so a mid-loop failure rolls the delete back too.
        """
        validation_error = self._validate_restore_payload(items)
        if validation_error is not None:
            return validation_error

        clear_existing = bool(request.data.get('clear_existing', False))
        restored_count = 0
        try:
            with transaction.atomic():
                if clear_existing:
                    EncryptedVaultItem.objects.filter(user=request.user).delete()

                for item_data in items:
                    item_id = item_data.get('item_id')
                    EncryptedVaultItem.objects.update_or_create(
                        user=request.user,
                        item_id=item_id,
                        defaults={
                            'item_type': item_data.get('item_type', 'password'),
                            'encrypted_data': item_data.get('encrypted_data', ''),
                            'favorite': item_data.get('favorite', False),
                            'tags': item_data.get('tags', []),
                        },
                    )
                    restored_count += 1
        except Exception as exc:
            # Tx already rolled back by atomic() — live vault preserved.
            logger.exception("backup restore failed mid-batch: %s", exc)
            return error_response(
                message="Restore failed; live vault was preserved.",
                code="restore_failed",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        return success_response({
            'success': True,
            'restored_items': restored_count,
            'backup_id': backup.id,
            'backup_name': backup.name,
            'backup_date': backup.created_at,
        })

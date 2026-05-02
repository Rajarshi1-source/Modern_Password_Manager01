from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from django.db import transaction
from django.utils import timezone
from vault.models.vault_models import EncryptedVaultItem
from vault.models.backup_models import VaultBackup
from vault.serializer import BackupSerializer, VaultItemSerializer
from vault.services.cloud_storage import CloudStorageService
import json
import os
import base64
import hashlib
import logging
from password_manager.api_utils import error_response, success_response

logger = logging.getLogger(__name__)

# Placeholder row while payload lives only in object storage (valet-key upload flow).
CLOUD_ONLY_PAYLOAD_META = {'cloud_only': True, 'v': 1}


def _derive_wrapping_key(user_key: str) -> bytes:
    """
    Derive a 256-bit wrapping key from the user-provided key using HKDF-like
    derivation (SHA-256 + salt). The user_key is typically derived client-side
    from the master password.
    """
    salt = b'securevault-backup-envelope-v1'
    return hashlib.pbkdf2_hmac('sha256', user_key.encode('utf-8'), salt, 100_000)


def _envelope_encrypt(plaintext_bytes: bytes, wrapping_key: bytes) -> dict:
    """
    Envelope encryption using AES-256-GCM.

    1. Generate a random Data Encryption Key (DEK)
    2. Encrypt the plaintext with the DEK
    3. Wrap (encrypt) the DEK with the wrapping_key (KEK)
    4. Return all components needed for decryption

    Returns dict with base64-encoded components.
    """
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    # Step 1: Generate random DEK (256-bit)
    dek = os.urandom(32)

    # Step 2: Encrypt data with DEK
    data_nonce = os.urandom(12)  # 96-bit nonce for AES-GCM
    data_cipher = AESGCM(dek)
    encrypted_data = data_cipher.encrypt(data_nonce, plaintext_bytes, None)

    # Step 3: Wrap DEK with KEK (user's wrapping key)
    kek_nonce = os.urandom(12)
    kek_cipher = AESGCM(wrapping_key)
    wrapped_dek = kek_cipher.encrypt(kek_nonce, dek, None)

    return {
        'version': 'envelope-v1',
        'encrypted_data': base64.b64encode(encrypted_data).decode('utf-8'),
        'data_nonce': base64.b64encode(data_nonce).decode('utf-8'),
        'wrapped_dek': base64.b64encode(wrapped_dek).decode('utf-8'),
        'kek_nonce': base64.b64encode(kek_nonce).decode('utf-8'),
    }


def _envelope_decrypt(envelope: dict, wrapping_key: bytes) -> bytes:
    """
    Decrypt envelope-encrypted data.

    1. Unwrap the DEK using the wrapping_key (KEK)
    2. Decrypt the data with the DEK
    """
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    # Decode components
    wrapped_dek = base64.b64decode(envelope['wrapped_dek'])
    kek_nonce = base64.b64decode(envelope['kek_nonce'])
    encrypted_data = base64.b64decode(envelope['encrypted_data'])
    data_nonce = base64.b64decode(envelope['data_nonce'])

    # Step 1: Unwrap DEK
    kek_cipher = AESGCM(wrapping_key)
    dek = kek_cipher.decrypt(kek_nonce, wrapped_dek, None)

    # Step 2: Decrypt data
    data_cipher = AESGCM(dek)
    plaintext = data_cipher.decrypt(data_nonce, encrypted_data, None)

    return plaintext


class BackupViewSet(viewsets.ModelViewSet):
    """API endpoints for vault backups"""
    permission_classes = [IsAuthenticated]
    serializer_class = BackupSerializer
    
    def get_queryset(self):
        """Return only backups belonging to authenticated user"""
        return VaultBackup.objects.filter(user=self.request.user)
    
    @action(detail=False, methods=['post'])
    def create_backup(self, request):
        """Create a new vault backup"""
        with transaction.atomic():
            # Get all vault items
            vault_items = EncryptedVaultItem.objects.filter(
                user=request.user,
                deleted=False
            )
            
            # Serialize items for backup
            items_data = []
            for item in vault_items:
                items_data.append({
                    'id': str(item.id),
                    'item_id': item.item_id,
                    'item_type': item.item_type,
                    'encrypted_data': item.encrypted_data,
                    'created_at': item.created_at.isoformat(),
                    'updated_at': item.updated_at.isoformat(),
                    'favorite': item.favorite,
                    'tags': item.tags
                })
            
            # Create backup package with metadata
            backup_data = {
                'version': '1.0',
                'created_at': timezone.now().isoformat(),
                'item_count': len(items_data),
                'items': items_data
            }
            
            # Convert to JSON bytes
            backup_json = json.dumps(backup_data)
            
            # Envelope encryption: if user provides an encryption_key,
            # wrap the backup with AES-256-GCM envelope encryption.
            user_key = request.data.get('encryption_key')
            is_envelope_encrypted = False
            
            if user_key:
                try:
                    wrapping_key = _derive_wrapping_key(user_key)
                    envelope = _envelope_encrypt(
                        backup_json.encode('utf-8'), wrapping_key
                    )
                    stored_data = json.dumps(envelope)
                    is_envelope_encrypted = True
                    logger.info(
                        f"Backup created with envelope encryption for user {request.user.id}"
                    )
                except Exception as e:
                    logger.error(f"Envelope encryption failed, storing without: {e}")
                    stored_data = backup_json
            else:
                # No user key provided — store as-is (data is already
                # client-side encrypted at the field level)
                stored_data = backup_json
            
            # Create backup in database
            backup = VaultBackup.objects.create(
                user=request.user,
                name=request.data.get('name', f"Backup {timezone.now().strftime('%Y-%m-%d %H:%M')}"),
                encrypted_data=stored_data,
                size=len(stored_data)
            )
            
            # Upload to cloud storage
            cloud_service = CloudStorageService()
            cloud_path = cloud_service.upload_backup(
                request.user.id, 
                stored_data,
                str(backup.id)
            )
            
            if cloud_path:
                backup.cloud_storage_path = cloud_path
                backup.cloud_sync_status = 'synced'
                backup.save()
            
            return Response({
                'id': backup.id,
                'name': backup.name,
                'created_at': backup.created_at,
                'item_count': len(items_data),
                'size': backup.size,
                'cloud_synced': backup.cloud_sync_status == 'synced',
                'envelope_encrypted': is_envelope_encrypted,
            })

    @action(detail=False, methods=['post'], url_path='start-cloud-upload')
    def start_cloud_upload(self, request):
        """
        Valet-key flow: create DB row and return a presigned PUT URL so the client
        uploads encrypted backup bytes directly to object storage.
        """
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
        """Call after a successful PUT of the backup blob to object storage."""
        backup = self.get_object()
        try:
            size = int(request.data.get('size', 0))
        except (TypeError, ValueError):
            size = 0
        backup.size = size
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

    @action(detail=True, methods=['post'])
    def restore(self, request, pk=None):
        """Restore vault from a backup"""
        try:
            backup = self.get_object()
        except VaultBackup.DoesNotExist:
            return error_response('Backup not found', status_code=status.HTTP_404_NOT_FOUND)
        
        with transaction.atomic():
            try:
                raw_data = backup.encrypted_data

                try:
                    stub = json.loads(raw_data) if raw_data else {}
                except json.JSONDecodeError:
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
                        blob.decode('utf-8')
                        if isinstance(blob, bytes)
                        else blob
                    )
                elif not raw_data and backup.cloud_storage_path:
                    cloud_service = CloudStorageService()
                    raw_data = cloud_service.download_backup(backup.cloud_storage_path)
                    if not raw_data:
                        return error_response(
                            'Failed to download backup from cloud',
                            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
                        )
                    if isinstance(raw_data, bytes):
                        raw_data = raw_data.decode('utf-8')

                parsed = json.loads(raw_data)
                
                # Check if this is an envelope-encrypted backup
                if parsed.get('version') == 'envelope-v1':
                    user_key = request.data.get('encryption_key')
                    if not user_key:
                        return error_response(
                            'This backup is envelope-encrypted. '
                            'Please provide the encryption_key used during backup.',
                            status_code=status.HTTP_400_BAD_REQUEST
                        )
                    try:
                        wrapping_key = _derive_wrapping_key(user_key)
                        decrypted_bytes = _envelope_decrypt(parsed, wrapping_key)
                        backup_data = json.loads(decrypted_bytes.decode('utf-8'))
                    except Exception as e:
                        logger.warning(f"Envelope decryption failed: {e}")
                        return error_response(
                            'Decryption failed. Incorrect encryption key or corrupted backup.',
                            status_code=status.HTTP_400_BAD_REQUEST
                        )
                else:
                    backup_data = parsed
                
                if not backup_data.get('items'):
                    return error_response('Invalid backup data', status_code=status.HTTP_400_BAD_REQUEST)
                
                # Clear existing vault items if specified
                if request.data.get('clear_existing', False):
                    EncryptedVaultItem.objects.filter(user=request.user).delete()
                
                # Restore items
                restored_count = 0
                for item_data in backup_data['items']:
                    EncryptedVaultItem.objects.update_or_create(
                        user=request.user,
                        item_id=item_data['item_id'],
                        defaults={
                            'item_type': item_data['item_type'],
                            'encrypted_data': item_data['encrypted_data'],
                            'favorite': item_data.get('favorite', False),
                            'tags': item_data.get('tags', [])
                        }
                    )
                    restored_count += 1
                
                return success_response({
                    'success': True,
                    'restored_items': restored_count,
                    'backup_id': backup.id,
                    'backup_name': backup.name,
                    'backup_date': backup.created_at
                })
                
            except Exception as e:
                return error_response(f'Restore failed: {str(e)}', status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)

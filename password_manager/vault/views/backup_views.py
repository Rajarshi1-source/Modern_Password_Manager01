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
from django.conf import settings
from password_manager.api_utils import error_response, success_response

logger = logging.getLogger(__name__)


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
                
                # Optionally download from cloud if local data is missing
                if not raw_data and backup.cloud_storage_path:
                    cloud_service = CloudStorageService()
                    raw_data = cloud_service.download_backup(backup.cloud_storage_path)
                    if not raw_data:
                        return error_response(
                            'Failed to download backup from cloud',
                            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
                        )
                
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

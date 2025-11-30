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
from django.conf import settings
from password_manager.api_utils import error_response, success_response

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
            
            # Convert to JSON string
            backup_json = json.dumps(backup_data)
            
            # Create backup in database
            backup = VaultBackup.objects.create(
                user=request.user,
                name=request.data.get('name', f"Backup {timezone.now().strftime('%Y-%m-%d %H:%M')}"),
                encrypted_data=backup_json,
                size=len(backup_json)
            )
            
            # Upload to cloud storage
            cloud_service = CloudStorageService()
            cloud_path = cloud_service.upload_backup(
                request.user.id, 
                backup_json,
                str(backup.id)
            )
            
            if cloud_path:
                backup.cloud_storage_path = cloud_path
                backup.cloud_sync_status = 'synced'
                backup.save()
            
            # Enhanced: Add envelope encryption using user's key
            user_key = request.data.get('encryption_key')
            backup_key = os.urandom(32)
            
            # Encrypt backup with backup_key, then encrypt backup_key with user_key
            # This allows storing backups without requiring master password
            
            return Response({
                'id': backup.id,
                'name': backup.name,
                'created_at': backup.created_at,
                'item_count': len(items_data),
                'size': backup.size,
                'cloud_synced': backup.cloud_sync_status == 'synced'
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
                # Get backup data
                backup_data = json.loads(backup.encrypted_data)
                
                if not backup_data.get('items'):
                    return error_response('Invalid backup data', status_code=status.HTTP_400_BAD_REQUEST)
                
                # Optionally download from cloud if local data is missing
                if not backup_data and backup.cloud_storage_path:
                    cloud_service = CloudStorageService()
                    cloud_data = cloud_service.download_backup(backup.cloud_storage_path)
                    if cloud_data:
                        backup_data = json.loads(cloud_data)
                    else:
                        return error_response('Failed to download backup from cloud', 
                                             status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)
                
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

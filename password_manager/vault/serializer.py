from rest_framework import serializers
from vault.models.vault_models import EncryptedVaultItem
from vault.models import UserSalt, AuditLog, DeletedItem, VaultFolder
from django.contrib.auth.models import User
from vault.models.backup_models import VaultBackup
import json

class EncryptedVaultItemSerializer(serializers.ModelSerializer):
    """Serializer for encrypted vault items API"""
    class Meta:
        model = EncryptedVaultItem
        fields = ['id', 'item_id', 'encrypted_data', 'item_type', 'created_at', 'updated_at', 'user']
        read_only_fields = ['id', 'created_at', 'updated_at']

class FolderSerializer(serializers.ModelSerializer):
    """Serializer for vault folders"""
    item_count = serializers.SerializerMethodField()
    
    class Meta:
        model = VaultFolder
        fields = [
            'id',
            'name',
            'description',
            'parent',
            'color',
            'icon',
            'created_at',
            'updated_at',
            'item_count'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'item_count']
        
    def get_item_count(self, obj):
        return obj.items.count()
    
    def create(self, validated_data):
        # Associate with current user
        validated_data['user'] = self.context['request'].user
        return super().create(validated_data)

class _UserScopedFolderPrimaryKeyRelatedField(serializers.PrimaryKeyRelatedField):
    """PrimaryKeyRelatedField for folders, scoped to ``request.user``.

    Scoping the queryset at field-resolution time prevents two leaks:

    1. ``update`` path: a user could PATCH ``folder_id`` to move their item
       into another user's folder (the previous ``create``-only check was
       bypassed on update).
    2. Enumeration: an unfiltered queryset produces a "does not exist"
       validation error for IDs outside the user's scope, letting an attacker
       probe existence of other users' folder IDs via error messages.
    """

    def get_queryset(self):
        request = self.context.get('request')
        if request is None or not getattr(request, 'user', None) or not request.user.is_authenticated:
            return VaultFolder.objects.none()
        return VaultFolder.objects.filter(user=request.user)


class VaultItemSerializer(serializers.ModelSerializer):
    """Serializer for vault items with client-side encryption"""
    folder_id = _UserScopedFolderPrimaryKeyRelatedField(
        source='folder',
        required=False,
        allow_null=True,
    )

    class Meta:
        model = EncryptedVaultItem
        fields = [
            'id',
            'item_id',
            'encrypted_data',
            'item_type',
            'created_at',
            'updated_at',
            'last_used_at',
            'favorite',
            'folder_id',
            'tags'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def create(self, validated_data):
        # Associate with current user. The queryset on ``folder_id`` already
        # guarantees the folder (if supplied) belongs to ``request.user``, so
        # no extra cross-user check is required here.
        validated_data['user'] = self.context['request'].user
        return super().create(validated_data)

class SyncSerializer(serializers.Serializer):
    """Serializer for synchronizing vault items across devices"""
    last_sync = serializers.DateTimeField(required=False)
    items = serializers.ListField(
        child=VaultItemSerializer(), 
        required=False
    )
    deleted_items = serializers.ListField(
        child=serializers.CharField(),
        required=False
    )
    
    class Meta:
        fields = ['last_sync', 'items', 'deleted_items']

class BackupSerializer(serializers.ModelSerializer):
    """Serializer for vault backups"""
    item_count = serializers.SerializerMethodField()
    
    class Meta:
        model = VaultBackup
        fields = [
            'id', 
            'name', 
            'created_at', 
            'size',
            'item_count',
            'cloud_sync_status'
        ]
        read_only_fields = ['id', 'created_at', 'size', 'cloud_sync_status']
    
    def get_item_count(self, obj):
        try:
            backup_data = json.loads(obj.encrypted_data)
            return len(backup_data.get('items', []))
        except:
            return 0


class EmergencyVaultSerializer(serializers.ModelSerializer):
    """
    Restricted serializer for emergency vault access.
    
    Only exposes the minimum fields needed for emergency recovery:
    - item_id and item_type for identification
    - encrypted_data for the actual vault content (still encrypted)
    
    Strips metadata that would leak organizational information:
    - No tags, favorites, folder_id (organizational structure)
    - No timestamps (temporal patterns)
    - No last_used_at (usage patterns)
    """
    class Meta:
        model = EncryptedVaultItem
        fields = [
            'item_id',
            'encrypted_data',
            'item_type',
        ]
        read_only_fields = fields

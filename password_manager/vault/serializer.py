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

class VaultItemSerializer(serializers.ModelSerializer):
    """Serializer for vault items with client-side encryption"""
    folder_id = serializers.PrimaryKeyRelatedField(
        source='folder',
        queryset=VaultFolder.objects.all(),
        required=False,
        allow_null=True
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
        # Associate with current user
        validated_data['user'] = self.context['request'].user
        
        # Validate folder belongs to user if provided
        folder = validated_data.get('folder')
        if folder and folder.user.id != self.context['request'].user.id:
            raise serializers.ValidationError("Folder does not belong to this user")
            
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

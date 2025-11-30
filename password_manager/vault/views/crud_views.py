from rest_framework import viewsets, status, mixins
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from django.db import transaction
from django.utils import timezone
from vault.models.vault_models import EncryptedVaultItem
from vault.models import UserSalt, DeletedItem, AuditLog
from vault.serializer import VaultItemSerializer, SyncSerializer
import json

# Import the standardized response helpers
from .api_views import error_response, success_response

class VaultItemViewSet(viewsets.ModelViewSet):
    """
    Endpoints for vault items with end-to-end encryption
    
    This viewset provides CRUD operations for vault items and includes
    a sync endpoint for cross-device synchronization.
    """
    permission_classes = [IsAuthenticated]
    serializer_class = VaultItemSerializer
    
    def get_queryset(self):
        """Return only items belonging to authenticated user with optimized queries"""
        return EncryptedVaultItem.objects.select_related('user', 'folder').filter(
            user=self.request.user
        )
    
    def list(self, request):
        """List all vault items for the authenticated user with pagination"""
        try:
            queryset = self.get_queryset()
            
            # Optional filtering by item type
            item_type = request.query_params.get('type')
            if item_type:
                queryset = queryset.filter(item_type=item_type)
                
            # Optional filtering by favorites
            favorites = request.query_params.get('favorites')
            if favorites and favorites.lower() == 'true':
                queryset = queryset.filter(favorite=True)
            
            # Add pagination for large datasets
            page = self.paginate_queryset(queryset)
            if page is not None:
                serializer = self.get_serializer(page, many=True)
                return self.get_paginated_response(serializer.data)
            
            serializer = self.get_serializer(queryset, many=True)
            return success_response(
                data={"items": serializer.data},
                message="Items retrieved successfully"
            )
        except Exception as e:
            return error_response(
                message=f"Failed to retrieve items: {str(e)}",
                code="retrieval_error",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def create(self, request):
        """Create a new encrypted vault item"""
        serializer = self.get_serializer(data=request.data)
        
        if not serializer.is_valid():
            return error_response(
                message="Invalid item data provided",
                code="validation_error",
                details=serializer.errors
            )
            
        try:
            # Save the item
            item = serializer.save(user=request.user)
            
            # Log the action
            AuditLog.objects.create(
                user=request.user,
                action='create_item',
                item_type=item.item_type,
                status='success'
            )
            
            return success_response(
                data=serializer.data,
                message="Item created successfully",
                status_code=status.HTTP_201_CREATED
            )
        except Exception as e:
            return error_response(
                message=f"Failed to create item: {str(e)}",
                code="creation_error",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def update(self, request, pk=None):
        """Update an existing vault item"""
        try:
            instance = self.get_queryset().get(pk=pk)
        except EncryptedVaultItem.DoesNotExist:
            return error_response(
                message="Item not found",
                code="item_not_found",
                status_code=status.HTTP_404_NOT_FOUND
            )
            
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        
        if not serializer.is_valid():
            return error_response(
                message="Invalid item data provided",
                code="validation_error",
                details=serializer.errors
            )
            
        try:
            item = serializer.save()
            
            # Log the action
            AuditLog.objects.create(
                user=request.user,
                action='update_item',
                item_type=item.item_type,
                status='success'
            )
            
            return success_response(
                data=serializer.data,
                message="Item updated successfully"
            )
        except Exception as e:
            return error_response(
                message=f"Failed to update item: {str(e)}",
                code="update_error",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def destroy(self, request, pk=None):
        """Delete a vault item"""
        try:
            instance = self.get_queryset().get(pk=pk)
        except EncryptedVaultItem.DoesNotExist:
            return error_response(
                message="Item not found",
                code="item_not_found",
                status_code=status.HTTP_404_NOT_FOUND
            )
            
        try:
            # Store deleted item ID for syncing
            DeletedItem.objects.create(
                user=request.user,
                item_id=instance.item_id,
                deleted_at=timezone.now()
            )
            
            # Delete the item
            instance.delete()
            
            # Log the action
            AuditLog.objects.create(
                user=request.user,
                action='delete_item',
                item_type=instance.item_type,
                status='success'
            )
            
            return success_response(
                message="Item deleted successfully",
                status_code=status.HTTP_204_NO_CONTENT
            )
        except Exception as e:
            return error_response(
                message=f"Failed to delete item: {str(e)}",
                code="deletion_error",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['post'])
    def sync(self, request):
        """
        Synchronize vault items across devices
        
        This endpoint enables bidirectional sync between client and server:
        1. Client sends local changes (items and deletions)
        2. Server processes these changes
        3. Server returns changes that occurred since client's last sync
        
        Request format:
        {
            "last_sync": "2023-01-01T00:00:00Z",  // ISO timestamp of last sync
            "items": [                           // Array of changed items
                { item_id: "uuid", ... }
            ],
            "deleted_items": ["item_id1", ...]   // Array of deleted item IDs
        }
        
        Response format:
        {
            "success": true,
            "message": "Sync completed successfully",
            "items": [...],            // Server-side changes
            "deleted_items": [...],    // Server-side deletions
            "sync_time": "2023..."     // Current server time for next sync
        }
        """
        serializer = SyncSerializer(data=request.data)
        
        if not serializer.is_valid():
            return error_response(
                message="Invalid sync data provided",
                code="validation_error",
                details=serializer.errors
            )
        
        try:
            with transaction.atomic():
                last_sync = serializer.validated_data.get('last_sync')
                client_items = serializer.validated_data.get('items', [])
                deleted_item_ids = serializer.validated_data.get('deleted_items', [])
                
                # Get server-side changes since last_sync
                server_items = self.get_queryset()
                if last_sync:
                    server_items = server_items.filter(updated_at__gt=last_sync)
                
                # Get deleted items since last_sync
                server_deleted = []
                if last_sync:
                    server_deleted = DeletedItem.objects.filter(
                        user=request.user,
                        deleted_at__gt=last_sync
                    ).values_list('item_id', flat=True)
                
                # Process client-side changes
                for item_data in client_items:
                    self._process_sync_item(item_data)
                
                # Process client-side deletions
                if deleted_item_ids:
                    self.get_queryset().filter(item_id__in=deleted_item_ids).delete()
                
                # Return server-side changes
                server_items_serializer = self.get_serializer(server_items, many=True)
                
                return success_response({
                    'items': server_items_serializer.data,
                    'deleted_items': list(server_deleted),
                    'sync_time': timezone.now()
                }, message="Sync completed successfully")
                
        except Exception as e:
            return error_response(
                message=f"Sync failed: {str(e)}",
                code="sync_error",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def _process_sync_item(self, item_data):
        """
        Helper method to process a single item during sync
        Returns the processed item
        """
        item_id = item_data.get('item_id')
        if not item_id:
            return None
            
        try:
            # Update existing item
            existing_item = self.get_queryset().get(item_id=item_id)
            item_serializer = self.get_serializer(
                existing_item, 
                data=item_data, 
                partial=True
            )
            
            if item_serializer.is_valid():
                return item_serializer.save()
                
        except EncryptedVaultItem.DoesNotExist:
            # Create new item
            item_data['user'] = self.request.user.id
            item_serializer = self.get_serializer(data=item_data)
            
            if item_serializer.is_valid():
                return item_serializer.save()
                
        return None

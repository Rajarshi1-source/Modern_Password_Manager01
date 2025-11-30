"""
Shared Folders API Views - Part 2
Member Management, Item Sharing, Activity Logs
"""

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.utils import timezone
from django.db import transaction
from vault.models import (
    SharedFolder,
    SharedFolderMember,
    SharedVaultItem,
    SharedFolderActivity
)
import logging

logger = logging.getLogger(__name__)


@api_view(['PATCH'])
@permission_classes([IsAuthenticated])
def update_member_role(request, folder_id, member_id):
    """
    Update a member's role and permissions
    
    PATCH /api/vault/folders/shared/<folder_id>/members/<member_id>/
    Body: {
        "role": "editor",
        "can_invite": true,
        "can_edit_items": true,
        "can_delete_items": false,
        "can_export": false
    }
    """
    try:
        folder = SharedFolder.objects.get(id=folder_id, is_active=True)
        
        # Only owner or admin can update roles
        is_owner = folder.owner == request.user
        is_admin = False
        
        if not is_owner:
            try:
                requester = SharedFolderMember.objects.get(
                    folder=folder,
                    user=request.user,
                    status='accepted'
                )
                is_admin = requester.role == 'admin'
            except SharedFolderMember.DoesNotExist:
                pass
        
        if not (is_owner or is_admin):
            return Response({
                'error': 'Only owner or admin can update member roles'
            }, status=status.HTTP_403_FORBIDDEN)
        
        member = SharedFolderMember.objects.get(
            id=member_id,
            folder=folder
        )
        
        # Update role and permissions
        if 'role' in request.data:
            member.role = request.data['role']
        if 'can_invite' in request.data:
            member.can_invite = request.data['can_invite']
        if 'can_edit_items' in request.data:
            member.can_edit_items = request.data['can_edit_items']
        if 'can_delete_items' in request.data:
            member.can_delete_items = request.data['can_delete_items']
        if 'can_export' in request.data:
            member.can_export = request.data['can_export']
        
        member.save()
        
        # Log activity
        SharedFolderActivity.objects.create(
            folder=folder,
            activity_type='member_role_changed',
            user=request.user,
            target_user=member.user,
            details={
                'new_role': member.role,
                'can_invite': member.can_invite,
                'can_edit_items': member.can_edit_items,
                'can_delete_items': member.can_delete_items
            },
            ip_address=request.META.get('REMOTE_ADDR')
        )
        
        return Response({
            'message': 'Member role updated successfully'
        }, status=status.HTTP_200_OK)
        
    except (SharedFolder.DoesNotExist, SharedFolderMember.DoesNotExist):
        return Response({
            'error': 'Folder or member not found'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error(f"Error updating member role: {e}")
        return Response({
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def remove_member(request, folder_id, member_id):
    """
    Remove a member from a shared folder
    
    DELETE /api/vault/folders/shared/<folder_id>/members/<member_id>/
    """
    try:
        folder = SharedFolder.objects.get(id=folder_id, is_active=True)
        
        # Check permissions
        is_owner = folder.owner == request.user
        is_admin = False
        
        if not is_owner:
            try:
                requester = SharedFolderMember.objects.get(
                    folder=folder,
                    user=request.user,
                    status='accepted'
                )
                is_admin = requester.role == 'admin'
            except SharedFolderMember.DoesNotExist:
                pass
        
        if not (is_owner or is_admin):
            return Response({
                'error': 'Only owner or admin can remove members'
            }, status=status.HTTP_403_FORBIDDEN)
        
        member = SharedFolderMember.objects.get(
            id=member_id,
            folder=folder
        )
        
        # Revoke access
        member.revoke_access()
        
        # Log activity
        SharedFolderActivity.objects.create(
            folder=folder,
            activity_type='member_removed',
            user=request.user,
            target_user=member.user,
            ip_address=request.META.get('REMOTE_ADDR')
        )
        
        return Response({
            'message': 'Member removed successfully'
        }, status=status.HTTP_200_OK)
        
    except (SharedFolder.DoesNotExist, SharedFolderMember.DoesNotExist):
        return Response({
            'error': 'Folder or member not found'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error(f"Error removing member: {e}")
        return Response({
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def add_item_to_folder(request, folder_id):
    """
    Add a vault item to a shared folder
    
    POST /api/vault/folders/shared/<folder_id>/items/
    Body: {
        "vault_item_id": "uuid",
        "encrypted_data": "base64_encrypted_item_data",
        "encrypted_metadata": "base64_encrypted_metadata"
    }
    """
    try:
        folder = SharedFolder.objects.get(id=folder_id, is_active=True)
        
        # Check permissions
        is_owner = folder.owner == request.user
        can_edit = False
        
        if not is_owner:
            try:
                member = SharedFolderMember.objects.get(
                    folder=folder,
                    user=request.user,
                    status='accepted'
                )
                can_edit = member.can_edit_items or member.role in ['admin', 'editor']
            except SharedFolderMember.DoesNotExist:
                pass
        
        if not (is_owner or can_edit):
            return Response({
                'error': 'You do not have permission to add items'
            }, status=status.HTTP_403_FORBIDDEN)
        
        vault_item_id = request.data.get('vault_item_id')
        
        # Check if item already shared in this folder
        if SharedVaultItem.objects.filter(
            folder=folder,
            vault_item_id=vault_item_id,
            is_active=True
        ).exists():
            return Response({
                'error': 'Item already shared in this folder'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        with transaction.atomic():
            shared_item = SharedVaultItem.objects.create(
                folder=folder,
                vault_item_id=vault_item_id,
                encrypted_folder_key=request.data.get('encrypted_data'),
                encrypted_metadata=request.data.get('encrypted_metadata', ''),
                shared_by=request.user
            )
            
            # Log activity
            SharedFolderActivity.objects.create(
                folder=folder,
                activity_type='item_added',
                user=request.user,
                details={'vault_item_id': vault_item_id},
                ip_address=request.META.get('REMOTE_ADDR')
            )
        
        return Response({
            'message': 'Item added to folder successfully',
            'shared_item_id': str(shared_item.id)
        }, status=status.HTTP_201_CREATED)
        
    except SharedFolder.DoesNotExist:
        return Response({
            'error': 'Folder not found'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error(f"Error adding item to folder: {e}")
        return Response({
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def folder_items(request, folder_id):
    """
    List all items in a shared folder
    
    GET /api/vault/folders/shared/<folder_id>/items/
    """
    try:
        folder = SharedFolder.objects.get(id=folder_id, is_active=True)
        
        # Check access
        is_owner = folder.owner == request.user
        is_member = SharedFolderMember.objects.filter(
            folder=folder,
            user=request.user,
            status='accepted'
        ).exists()
        
        if not (is_owner or is_member):
            return Response({
                'error': 'Access denied'
            }, status=status.HTTP_403_FORBIDDEN)
        
        items = SharedVaultItem.objects.filter(
            folder=folder,
            is_active=True
        ).order_by('-shared_at')
        
        result = []
        for item in items:
            result.append({
                'id': str(item.id),
                'vault_item_id': item.vault_item_id,
                'encrypted_data': item.encrypted_folder_key,
                'encrypted_metadata': item.encrypted_metadata,
                'shared_by': item.shared_by.username if item.shared_by else None,
                'shared_at': item.shared_at
            })
        
        return Response(result, status=status.HTTP_200_OK)
        
    except SharedFolder.DoesNotExist:
        return Response({
            'error': 'Folder not found'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error(f"Error listing folder items: {e}")
        return Response({
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET', 'DELETE'])
@permission_classes([IsAuthenticated])
def folder_item_detail(request, folder_id, item_id):
    """
    Get or remove a specific item from a shared folder
    
    GET    /api/vault/folders/shared/<folder_id>/items/<item_id>/
    DELETE /api/vault/folders/shared/<folder_id>/items/<item_id>/
    """
    try:
        folder = SharedFolder.objects.get(id=folder_id, is_active=True)
        item = SharedVaultItem.objects.get(
            id=item_id,
            folder=folder,
            is_active=True
        )
        
        # Check access
        is_owner = folder.owner == request.user
        can_access = False
        can_delete = False
        
        if not is_owner:
            try:
                member = SharedFolderMember.objects.get(
                    folder=folder,
                    user=request.user,
                    status='accepted'
                )
                can_access = True
                can_delete = member.can_delete_items or member.role in ['admin', 'editor']
            except SharedFolderMember.DoesNotExist:
                pass
        else:
            can_access = True
            can_delete = True
        
        if not can_access:
            return Response({
                'error': 'Access denied'
            }, status=status.HTTP_403_FORBIDDEN)
        
        if request.method == 'GET':
            # Log view activity
            SharedFolderActivity.objects.create(
                folder=folder,
                activity_type='item_viewed',
                user=request.user,
                details={'vault_item_id': item.vault_item_id},
                ip_address=request.META.get('REMOTE_ADDR')
            )
            
            return Response({
                'id': str(item.id),
                'vault_item_id': item.vault_item_id,
                'encrypted_data': item.encrypted_folder_key,
                'encrypted_metadata': item.encrypted_metadata,
                'shared_by': item.shared_by.username if item.shared_by else None,
                'shared_at': item.shared_at
            }, status=status.HTTP_200_OK)
        
        elif request.method == 'DELETE':
            if not can_delete:
                return Response({
                    'error': 'You do not have permission to delete items'
                }, status=status.HTTP_403_FORBIDDEN)
            
            item.is_active = False
            item.save()
            
            # Log activity
            SharedFolderActivity.objects.create(
                folder=folder,
                activity_type='item_removed',
                user=request.user,
                details={'vault_item_id': item.vault_item_id},
                ip_address=request.META.get('REMOTE_ADDR')
            )
            
            return Response({
                'message': 'Item removed from folder successfully'
            }, status=status.HTTP_200_OK)
        
    except (SharedFolder.DoesNotExist, SharedVaultItem.DoesNotExist):
        return Response({
            'error': 'Folder or item not found'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error(f"Error in folder_item_detail: {e}")
        return Response({
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def folder_activity(request, folder_id):
    """
    Get activity log for a shared folder
    
    GET /api/vault/folders/shared/<folder_id>/activity/
    Query params:
        - limit: Number of activities to return (default: 50)
        - offset: Offset for pagination (default: 0)
    """
    try:
        folder = SharedFolder.objects.get(id=folder_id, is_active=True)
        
        # Check access
        is_owner = folder.owner == request.user
        is_member = SharedFolderMember.objects.filter(
            folder=folder,
            user=request.user,
            status='accepted'
        ).exists()
        
        if not (is_owner or is_member):
            return Response({
                'error': 'Access denied'
            }, status=status.HTTP_403_FORBIDDEN)
        
        limit = int(request.GET.get('limit', 50))
        offset = int(request.GET.get('offset', 0))
        
        activities = SharedFolderActivity.objects.filter(
            folder=folder
        ).order_by('-timestamp')[offset:offset+limit]
        
        result = []
        for activity in activities:
            result.append({
                'id': str(activity.id),
                'activity_type': activity.activity_type,
                'user': activity.user.username if activity.user else 'System',
                'target_user': activity.target_user.username if activity.target_user else None,
                'details': activity.details,
                'timestamp': activity.timestamp
            })
        
        return Response(result, status=status.HTTP_200_OK)
        
    except SharedFolder.DoesNotExist:
        return Response({
            'error': 'Folder not found'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error(f"Error getting folder activity: {e}")
        return Response({
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def leave_folder(request, folder_id):
    """
    Leave a shared folder (self-removal)
    
    POST /api/vault/folders/shared/<folder_id>/leave/
    """
    try:
        folder = SharedFolder.objects.get(id=folder_id, is_active=True)
        
        # Owner cannot leave their own folder
        if folder.owner == request.user:
            return Response({
                'error': 'Owner cannot leave their own folder. Delete the folder instead.'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        member = SharedFolderMember.objects.get(
            folder=folder,
            user=request.user,
            status='accepted'
        )
        
        member.revoke_access()
        
        # Log activity
        SharedFolderActivity.objects.create(
            folder=folder,
            activity_type='member_removed',
            user=request.user,
            target_user=request.user,
            details={'self_removed': True},
            ip_address=request.META.get('REMOTE_ADDR')
        )
        
        return Response({
            'message': 'Successfully left folder'
        }, status=status.HTTP_200_OK)
        
    except SharedFolder.DoesNotExist:
        return Response({
            'error': 'Folder not found'
        }, status=status.HTTP_404_NOT_FOUND)
    except SharedFolderMember.DoesNotExist:
        return Response({
            'error': 'You are not a member of this folder'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error(f"Error leaving folder: {e}")
        return Response({
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def rotate_folder_key(request, folder_id):
    """
    Rotate encryption key for a shared folder
    
    POST /api/vault/folders/shared/<folder_id>/rotate-key/
    Body: {
        "new_encrypted_keys": {
            "user_id_1": "encrypted_key_for_user1",
            "user_id_2": "encrypted_key_for_user2"
        },
        "re_encrypted_items": {
            "item_id_1": "re_encrypted_data1",
            "item_id_2": "re_encrypted_data2"
        }
    }
    """
    try:
        folder = SharedFolder.objects.get(id=folder_id, is_active=True)
        
        # Only owner can rotate keys
        if folder.owner != request.user:
            return Response({
                'error': 'Only owner can rotate folder keys'
            }, status=status.HTTP_403_FORBIDDEN)
        
        new_encrypted_keys = request.data.get('new_encrypted_keys', {})
        re_encrypted_items = request.data.get('re_encrypted_items', {})
        
        with transaction.atomic():
            # Update folder keys for all members
            from django.contrib.auth.models import User
            for user_id, encrypted_key in new_encrypted_keys.items():
                try:
                    user = User.objects.get(id=user_id)
                    # Get current key version
                    current_key = SharedFolderKey.objects.filter(
                        folder=folder,
                        user=user
                    ).order_by('-key_version').first()
                    
                    new_version = (current_key.key_version + 1) if current_key else 1
                    
                    SharedFolderKey.objects.create(
                        folder=folder,
                        user=user,
                        encrypted_folder_key=encrypted_key,
                        key_version=new_version,
                        rotated_at=timezone.now()
                    )
                except User.DoesNotExist:
                    logger.warning(f"User {user_id} not found during key rotation")
            
            # Update re-encrypted items
            for item_id, re_encrypted_data in re_encrypted_items.items():
                try:
                    item = SharedVaultItem.objects.get(
                        id=item_id,
                        folder=folder
                    )
                    item.encrypted_folder_key = re_encrypted_data
                    item.save()
                except SharedVaultItem.DoesNotExist:
                    logger.warning(f"Item {item_id} not found during key rotation")
            
            # Log activity
            SharedFolderActivity.objects.create(
                folder=folder,
                activity_type='key_rotated',
                user=request.user,
                details={'keys_updated': len(new_encrypted_keys), 'items_updated': len(re_encrypted_items)},
                ip_address=request.META.get('REMOTE_ADDR')
            )
        
        return Response({
            'message': 'Folder key rotated successfully'
        }, status=status.HTTP_200_OK)
        
    except SharedFolder.DoesNotExist:
        return Response({
            'error': 'Folder not found'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error(f"Error rotating folder key: {e}")
        return Response({
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


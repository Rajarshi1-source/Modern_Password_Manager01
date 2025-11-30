"""
Shared Folders API Views

Implements RESTful API for secure folder sharing with E2EE
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
    SharedFolderKey,
    SharedFolderActivity
)
import secrets
import uuid
import logging

logger = logging.getLogger(__name__)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_shared_folder(request):
    """
    Create a new shared folder
    
    POST /api/vault/folders/shared/
    Body: {
        "name": "Team Passwords",
        "description": "Shared team credentials",
        "require_2fa": false,
        "allow_export": false,
        "encrypted_folder_key": "base64_encrypted_key"
    }
    """
    try:
        with transaction.atomic():
            folder = SharedFolder.objects.create(
                name=request.data.get('name'),
                description=request.data.get('description', ''),
                owner=request.user,
                require_2fa=request.data.get('require_2fa', False),
                allow_export=request.data.get('allow_export', False)
            )
            
            # Store owner's encrypted folder key
            SharedFolderKey.objects.create(
                folder=folder,
                user=request.user,
                encrypted_folder_key=request.data.get('encrypted_folder_key'),
                key_version=1
            )
            
            # Log activity
            SharedFolderActivity.objects.create(
                folder=folder,
                activity_type='created',
                user=request.user,
                details={'name': folder.name},
                ip_address=request.META.get('REMOTE_ADDR'),
                user_agent=request.META.get('HTTP_USER_AGENT', '')
            )
            
            return Response({
                'id': str(folder.id),
                'name': folder.name,
                'description': folder.description,
                'owner': request.user.username,
                'created_at': folder.created_at
            }, status=status.HTTP_201_CREATED)
            
    except Exception as e:
        logger.error(f"Error creating shared folder: {e}")
        return Response({
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def list_shared_folders(request):
    """
    List all shared folders for the current user
    
    GET /api/vault/folders/shared/
    """
    try:
        # Folders owned by user
        owned_folders = SharedFolder.objects.filter(
            owner=request.user,
            is_active=True
        )
        
        # Folders shared with user
        member_folder_ids = SharedFolderMember.objects.filter(
            user=request.user,
            status='accepted'
        ).values_list('folder_id', flat=True)
        
        shared_folders = SharedFolder.objects.filter(
            id__in=member_folder_ids,
            is_active=True
        )
        
        result = []
        
        # Add owned folders
        for folder in owned_folders:
            result.append({
                'id': str(folder.id),
                'name': folder.name,
                'description': folder.description,
                'owner': folder.owner.username,
                'role': 'owner',
                'members_count': folder.get_members_count(),
                'items_count': folder.get_items_count(),
                'created_at': folder.created_at,
                'require_2fa': folder.require_2fa,
                'allow_export': folder.allow_export
            })
        
        # Add shared folders
        for folder in shared_folders:
            member = SharedFolderMember.objects.get(
                folder=folder,
                user=request.user
            )
            result.append({
                'id': str(folder.id),
                'name': folder.name,
                'description': folder.description,
                'owner': folder.owner.username,
                'role': member.role,
                'members_count': folder.get_members_count(),
                'items_count': folder.get_items_count(),
                'created_at': folder.created_at,
                'require_2fa': folder.require_2fa,
                'allow_export': folder.allow_export
            })
        
        return Response(result, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Error listing shared folders: {e}")
        return Response({
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET', 'PATCH', 'DELETE'])
@permission_classes([IsAuthenticated])
def folder_detail(request, folder_id):
    """
    Get, update, or delete a specific shared folder
    
    GET    /api/vault/folders/shared/<folder_id>/
    PATCH  /api/vault/folders/shared/<folder_id>/
    DELETE /api/vault/folders/shared/<folder_id>/
    """
    try:
        folder = SharedFolder.objects.get(id=folder_id, is_active=True)
        
        # Check if user has access
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
        
        if request.method == 'GET':
            # Get encrypted folder key for user
            folder_key = SharedFolderKey.objects.filter(
                folder=folder,
                user=request.user
            ).order_by('-key_version').first()
            
            return Response({
                'id': str(folder.id),
                'name': folder.name,
                'description': folder.description,
                'owner': folder.owner.username,
                'is_owner': is_owner,
                'encrypted_folder_key': folder_key.encrypted_folder_key if folder_key else None,
                'key_version': folder_key.key_version if folder_key else None,
                'require_2fa': folder.require_2fa,
                'allow_export': folder.allow_export,
                'created_at': folder.created_at,
                'updated_at': folder.updated_at
            }, status=status.HTTP_200_OK)
        
        elif request.method == 'PATCH':
            # Only owner can update folder settings
            if not is_owner:
                return Response({
                    'error': 'Only owner can update folder settings'
                }, status=status.HTTP_403_FORBIDDEN)
            
            if 'name' in request.data:
                folder.name = request.data['name']
            if 'description' in request.data:
                folder.description = request.data['description']
            if 'require_2fa' in request.data:
                folder.require_2fa = request.data['require_2fa']
            if 'allow_export' in request.data:
                folder.allow_export = request.data['allow_export']
            
            folder.save()
            
            return Response({
                'message': 'Folder updated successfully',
                'id': str(folder.id)
            }, status=status.HTTP_200_OK)
        
        elif request.method == 'DELETE':
            # Only owner can delete folder
            if not is_owner:
                return Response({
                    'error': 'Only owner can delete folder'
                }, status=status.HTTP_403_FORBIDDEN)
            
            folder.is_active = False
            folder.save()
            
            # Log activity
            SharedFolderActivity.objects.create(
                folder=folder,
                activity_type='deleted',
                user=request.user,
                ip_address=request.META.get('REMOTE_ADDR')
            )
            
            return Response({
                'message': 'Folder deleted successfully'
            }, status=status.HTTP_200_OK)
        
    except SharedFolder.DoesNotExist:
        return Response({
            'error': 'Folder not found'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error(f"Error in folder_detail: {e}")
        return Response({
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def invite_member(request, folder_id):
    """
    Invite a user to a shared folder
    
    POST /api/vault/folders/shared/<folder_id>/invite/
    Body: {
        "email": "user@example.com",
        "role": "editor",
        "can_invite": false,
        "can_edit_items": true,
        "can_delete_items": false,
        "can_export": false,
        "encrypted_folder_key": "base64_encrypted_key_for_invitee"
    }
    """
    try:
        folder = SharedFolder.objects.get(id=folder_id, is_active=True)
        
        # Check permissions
        is_owner = folder.owner == request.user
        can_invite = False
        
        if not is_owner:
            try:
                member = SharedFolderMember.objects.get(
                    folder=folder,
                    user=request.user,
                    status='accepted'
                )
                can_invite = member.can_invite
            except SharedFolderMember.DoesNotExist:
                pass
        
        if not (is_owner or can_invite):
            return Response({
                'error': 'You do not have permission to invite members'
            }, status=status.HTTP_403_FORBIDDEN)
        
        # Get invitee
        from django.contrib.auth.models import User
        email = request.data.get('email')
        try:
            invitee = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response({
                'error': f'User with email {email} not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Check if already a member
        if SharedFolderMember.objects.filter(folder=folder, user=invitee).exists():
            return Response({
                'error': 'User is already a member or has a pending invitation'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Generate invitation token
        invitation_token = secrets.token_urlsafe(32)
        invitation_expires_at = timezone.now() + timezone.timedelta(days=7)
        
        with transaction.atomic():
            # Create membership
            membership = SharedFolderMember.objects.create(
                folder=folder,
                user=invitee,
                role=request.data.get('role', 'viewer'),
                can_invite=request.data.get('can_invite', False),
                can_edit_items=request.data.get('can_edit_items', False),
                can_delete_items=request.data.get('can_delete_items', False),
                can_export=request.data.get('can_export', False),
                status='pending',
                invited_by=request.user,
                invitation_token=invitation_token,
                invitation_expires_at=invitation_expires_at
            )
            
            # Store encrypted folder key for invitee
            SharedFolderKey.objects.create(
                folder=folder,
                user=invitee,
                encrypted_folder_key=request.data.get('encrypted_folder_key'),
                key_version=1
            )
            
            # Log activity
            SharedFolderActivity.objects.create(
                folder=folder,
                activity_type='invitation_sent',
                user=request.user,
                target_user=invitee,
                details={'role': membership.role},
                ip_address=request.META.get('REMOTE_ADDR')
            )
        
        return Response({
            'message': 'Invitation sent successfully',
            'invitation_token': invitation_token,
            'expires_at': invitation_expires_at
        }, status=status.HTTP_201_CREATED)
        
    except SharedFolder.DoesNotExist:
        return Response({
            'error': 'Folder not found'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error(f"Error inviting member: {e}")
        return Response({
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def accept_invitation(request, invitation_token):
    """
    Accept a folder invitation
    
    POST /api/vault/invitations/<token>/accept/
    """
    try:
        membership = SharedFolderMember.objects.get(
            invitation_token=invitation_token,
            user=request.user,
            status='pending'
        )
        
        # Check if invitation expired
        if membership.invitation_expires_at < timezone.now():
            return Response({
                'error': 'Invitation has expired'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        membership.accept_invitation()
        
        # Log activity
        SharedFolderActivity.objects.create(
            folder=membership.folder,
            activity_type='invitation_accepted',
            user=request.user,
            details={'role': membership.role},
            ip_address=request.META.get('REMOTE_ADDR')
        )
        
        return Response({
            'message': 'Invitation accepted successfully',
            'folder_id': str(membership.folder.id),
            'folder_name': membership.folder.name
        }, status=status.HTTP_200_OK)
        
    except SharedFolderMember.DoesNotExist:
        return Response({
            'error': 'Invalid invitation token'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error(f"Error accepting invitation: {e}")
        return Response({
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def decline_invitation(request, invitation_token):
    """
    Decline a folder invitation
    
    POST /api/vault/invitations/<token>/decline/
    """
    try:
        membership = SharedFolderMember.objects.get(
            invitation_token=invitation_token,
            user=request.user,
            status='pending'
        )
        
        membership.decline_invitation()
        
        # Log activity
        SharedFolderActivity.objects.create(
            folder=membership.folder,
            activity_type='invitation_declined',
            user=request.user,
            ip_address=request.META.get('REMOTE_ADDR')
        )
        
        return Response({
            'message': 'Invitation declined'
        }, status=status.HTTP_200_OK)
        
    except SharedFolderMember.DoesNotExist:
        return Response({
            'error': 'Invalid invitation token'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error(f"Error declining invitation: {e}")
        return Response({
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def pending_invitations(request):
    """
    Get all pending invitations for the current user
    
    GET /api/vault/invitations/pending/
    """
    try:
        invitations = SharedFolderMember.objects.filter(
            user=request.user,
            status='pending',
            invitation_expires_at__gt=timezone.now()
        )
        
        result = []
        for inv in invitations:
            result.append({
                'invitation_token': inv.invitation_token,
                'folder_id': str(inv.folder.id),
                'folder_name': inv.folder.name,
                'folder_owner': inv.folder.owner.username,
                'role': inv.role,
                'invited_by': inv.invited_by.username if inv.invited_by else None,
                'invited_at': inv.invited_at,
                'expires_at': inv.invitation_expires_at
            })
        
        return Response(result, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Error getting pending invitations: {e}")
        return Response({
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def folder_members(request, folder_id):
    """
    List all members of a shared folder
    
    GET /api/vault/folders/shared/<folder_id>/members/
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
        
        members = SharedFolderMember.objects.filter(
            folder=folder,
            status='accepted'
        )
        
        result = [{
            'id': 'owner',
            'user': folder.owner.username,
            'email': folder.owner.email,
            'role': 'owner',
            'joined_at': folder.created_at
        }]
        
        for member in members:
            result.append({
                'id': str(member.id),
                'user': member.user.username,
                'email': member.user.email,
                'role': member.role,
                'can_invite': member.can_invite,
                'can_edit_items': member.can_edit_items,
                'can_delete_items': member.can_delete_items,
                'can_export': member.can_export,
                'joined_at': member.accepted_at
            })
        
        return Response(result, status=status.HTTP_200_OK)
        
    except SharedFolder.DoesNotExist:
        return Response({
            'error': 'Folder not found'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error(f"Error listing folder members: {e}")
        return Response({
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# Continue in next message due to length...


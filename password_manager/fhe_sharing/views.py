"""
FHE Sharing API Views

API endpoints for Homomorphic Password Sharing:
- Create, list, detail, revoke shares
- Use autofill tokens
- Manage share groups
- View access logs
- Service status
"""

import logging
from django.contrib.auth.models import User
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from vault.models import EncryptedVaultItem
from .models import HomomorphicShare, ShareGroup
from .serializers import (
    HomomorphicShareSerializer,
    ShareRecipientSerializer,
    CreateShareSerializer,
    UseAutofillSerializer,
    RevokeShareSerializer,
    ShareAccessLogSerializer,
    ShareGroupSerializer,
    CreateShareGroupSerializer,
)
from .services import get_sharing_service

logger = logging.getLogger(__name__)


# ================================================================
# Share CRUD
# ================================================================

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_share(request):
    """
    Create a new homomorphic share.

    POST /api/fhe-sharing/shares/
    {
        "vault_item_id": "uuid",
        "recipient_username": "username",
        "domain_constraints": ["github.com"],
        "expires_at": "2026-04-01T00:00:00Z",
        "max_uses": 100,
        "group_id": "uuid" (optional)
    }
    """
    serializer = CreateShareSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(
            {'error': 'Invalid input', 'details': serializer.errors},
            status=status.HTTP_400_BAD_REQUEST,
        )

    data = serializer.validated_data

    try:
        # Get vault item
        vault_item = EncryptedVaultItem.objects.get(
            id=data['vault_item_id'],
            user=request.user,
        )
    except EncryptedVaultItem.DoesNotExist:
        return Response(
            {'error': 'Vault item not found or not owned by you'},
            status=status.HTTP_404_NOT_FOUND,
        )

    # Get recipient
    try:
        recipient = User.objects.get(username=data['recipient_username'])
    except User.DoesNotExist:
        return Response(
            {'error': f"User '{data['recipient_username']}' not found"},
            status=status.HTTP_404_NOT_FOUND,
        )

    # Get optional group
    group = None
    if data.get('group_id'):
        try:
            group = ShareGroup.objects.get(
                id=data['group_id'],
                owner=request.user,
            )
        except ShareGroup.DoesNotExist:
            return Response(
                {'error': 'Share group not found'},
                status=status.HTTP_404_NOT_FOUND,
            )

    try:
        service = get_sharing_service()
        share = service.create_autofill_share(
            owner=request.user,
            vault_item=vault_item,
            recipient=recipient,
            domain_constraints=data.get('domain_constraints', []),
            expires_at=data.get('expires_at'),
            max_uses=data.get('max_uses'),
            group=group,
            request=request,
        )

        return Response(
            {
                'success': True,
                'message': (
                    f"Password shared with {recipient.username} "
                    f"(autofill only — they cannot see the password)"
                ),
                'share': HomomorphicShareSerializer(share).data,
            },
            status=status.HTTP_201_CREATED,
        )

    except ValueError as e:
        return Response(
            {'error': str(e)},
            status=status.HTTP_400_BAD_REQUEST,
        )
    except PermissionError as e:
        return Response(
            {'error': str(e)},
            status=status.HTTP_403_FORBIDDEN,
        )
    except Exception as e:
        logger.error(f"[FHE Sharing] Create share error: {e}")
        return Response(
            {'error': 'Failed to create share'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def list_shares(request):
    """
    List shares created by the current user.

    GET /api/fhe-sharing/shares/
    Query params:
        include_inactive=true — include revoked/expired shares
    """
    include_inactive = request.query_params.get(
        'include_inactive', ''
    ).lower() == 'true'

    service = get_sharing_service()
    shares = service.list_shares_for_owner(
        request.user, include_inactive=include_inactive
    )

    serializer = HomomorphicShareSerializer(shares, many=True)
    return Response({
        'success': True,
        'count': shares.count(),
        'shares': serializer.data,
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def share_detail(request, share_id):
    """
    Get details of a specific share.

    GET /api/fhe-sharing/shares/<uuid>/
    """
    try:
        share = HomomorphicShare.objects.select_related(
            'owner', 'recipient', 'vault_item', 'group'
        ).get(id=share_id)
    except HomomorphicShare.DoesNotExist:
        return Response(
            {'error': 'Share not found'},
            status=status.HTTP_404_NOT_FOUND,
        )

    # Owner sees full details, recipient sees limited
    if share.owner_id == request.user.id:
        serializer = HomomorphicShareSerializer(share)
    elif share.recipient_id == request.user.id:
        serializer = ShareRecipientSerializer(share)
    else:
        return Response(
            {'error': 'Not authorized to view this share'},
            status=status.HTTP_403_FORBIDDEN,
        )

    return Response({
        'success': True,
        'share': serializer.data,
    })


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def revoke_share(request, share_id):
    """
    Revoke a share.

    DELETE /api/fhe-sharing/shares/<uuid>/
    Body (optional): { "reason": "No longer needed" }
    """
    reason_serializer = RevokeShareSerializer(data=request.data)
    reason_serializer.is_valid(raise_exception=True)

    try:
        service = get_sharing_service()
        share = service.revoke_share(
            share_id=str(share_id),
            revoking_user=request.user,
            reason=reason_serializer.validated_data.get('reason', ''),
            request=request,
        )

        return Response({
            'success': True,
            'message': 'Share revoked successfully',
            'share': HomomorphicShareSerializer(share).data,
        })

    except ValueError as e:
        return Response(
            {'error': str(e)},
            status=status.HTTP_400_BAD_REQUEST,
        )
    except PermissionError as e:
        return Response(
            {'error': str(e)},
            status=status.HTTP_403_FORBIDDEN,
        )
    except Exception as e:
        logger.error(f"[FHE Sharing] Revoke error: {e}")
        return Response(
            {'error': 'Failed to revoke share'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


# ================================================================
# Autofill Usage
# ================================================================

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def use_autofill(request, share_id):
    """
    Use an autofill token to fill a password form field.

    POST /api/fhe-sharing/shares/<uuid>/use/
    {
        "domain": "github.com",
        "form_field_selector": "input[type='password']"
    }
    """
    serializer = UseAutofillSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(
            {'error': 'Invalid input', 'details': serializer.errors},
            status=status.HTTP_400_BAD_REQUEST,
        )

    data = serializer.validated_data

    try:
        service = get_sharing_service()
        result = service.use_autofill_token(
            share_id=str(share_id),
            recipient=request.user,
            domain=data['domain'],
            form_field_selector=data.get(
                'form_field_selector', 'input[type="password"]'
            ),
            request=request,
        )

        return Response({
            'success': True,
            'message': 'Autofill data generated',
            **result,
        })

    except ValueError as e:
        return Response(
            {'error': str(e)},
            status=status.HTTP_400_BAD_REQUEST,
        )
    except PermissionError as e:
        return Response(
            {'error': str(e)},
            status=status.HTTP_403_FORBIDDEN,
        )
    except Exception as e:
        logger.error(f"[FHE Sharing] Autofill error: {e}")
        return Response(
            {'error': 'Failed to use autofill'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


# ================================================================
# Received Shares
# ================================================================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def received_shares(request):
    """
    List shares received by the current user (available for autofill).

    GET /api/fhe-sharing/received/
    """
    service = get_sharing_service()
    shares = service.list_shares_for_recipient(request.user)

    serializer = ShareRecipientSerializer(shares, many=True)
    return Response({
        'success': True,
        'count': shares.count(),
        'shares': serializer.data,
    })


# ================================================================
# Access Logs
# ================================================================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def share_logs(request, share_id):
    """
    Get access logs for a share (owner only).

    GET /api/fhe-sharing/shares/<uuid>/logs/
    """
    try:
        service = get_sharing_service()
        logs = service.get_share_logs(
            share_id=str(share_id),
            user=request.user,
        )

        # Paginate
        page_size = int(request.query_params.get('page_size', 50))
        page = int(request.query_params.get('page', 1))
        offset = (page - 1) * page_size

        total = logs.count()
        page_logs = logs[offset:offset + page_size]

        serializer = ShareAccessLogSerializer(page_logs, many=True)
        return Response({
            'success': True,
            'total': total,
            'page': page,
            'page_size': page_size,
            'logs': serializer.data,
        })

    except ValueError as e:
        return Response(
            {'error': str(e)},
            status=status.HTTP_404_NOT_FOUND,
        )
    except PermissionError as e:
        return Response(
            {'error': str(e)},
            status=status.HTTP_403_FORBIDDEN,
        )


# ================================================================
# Share Groups
# ================================================================

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_group(request):
    """
    Create a new share group.

    POST /api/fhe-sharing/groups/
    {
        "name": "Team GitHub",
        "description": "GitHub team account",
        "vault_item_id": "uuid"
    }
    """
    serializer = CreateShareGroupSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(
            {'error': 'Invalid input', 'details': serializer.errors},
            status=status.HTTP_400_BAD_REQUEST,
        )

    data = serializer.validated_data

    try:
        vault_item = EncryptedVaultItem.objects.get(
            id=data['vault_item_id'],
            user=request.user,
        )
    except EncryptedVaultItem.DoesNotExist:
        return Response(
            {'error': 'Vault item not found'},
            status=status.HTTP_404_NOT_FOUND,
        )

    try:
        service = get_sharing_service()
        group = service.create_share_group(
            owner=request.user,
            vault_item=vault_item,
            name=data['name'],
            description=data.get('description', ''),
        )

        return Response(
            {
                'success': True,
                'message': 'Share group created',
                'group': ShareGroupSerializer(group).data,
            },
            status=status.HTTP_201_CREATED,
        )

    except PermissionError as e:
        return Response(
            {'error': str(e)},
            status=status.HTTP_403_FORBIDDEN,
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def list_groups(request):
    """
    List share groups owned by the current user.

    GET /api/fhe-sharing/groups/
    """
    service = get_sharing_service()
    groups = service.list_share_groups(request.user)

    serializer = ShareGroupSerializer(groups, many=True)
    return Response({
        'success': True,
        'count': groups.count(),
        'groups': serializer.data,
    })


# ================================================================
# Service Status
# ================================================================

@api_view(['GET'])
def sharing_status(request):
    """
    Get FHE sharing service status (public endpoint).

    GET /api/fhe-sharing/status/
    """
    try:
        from .services import get_autofill_circuit_service

        circuit_service = get_autofill_circuit_service()

        return Response({
            'success': True,
            'service': 'fhe_sharing',
            'version': '1.0.0',
            'status': 'operational',
            'features': {
                'homomorphic_sharing': True,
                'domain_binding': True,
                'usage_limits': True,
                'audit_logging': True,
                'share_groups': True,
            },
            'circuit_service': {
                'initialized': circuit_service._initialized,
                'token_version': circuit_service.TOKEN_VERSION,
            },
        })

    except Exception as e:
        logger.error(f"[FHE Sharing] Status error: {e}")
        return Response({
            'success': False,
            'error': str(e),
        })

"""
Email Masking API Views
"""

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.utils import timezone
from .models import EmailAlias, EmailMaskingProvider, EmailAliasActivity
from .services import SimpleLoginService, AnonAddyService
from security.services.crypto_service import CryptoService
import logging

logger = logging.getLogger(__name__)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_alias(request):
    """
    Create a new email alias
    """
    try:
        provider_name = request.data.get('provider', 'simplelogin')
        description = request.data.get('description', '')
        alias_name = request.data.get('name', '')
        vault_item_id = request.data.get('vault_item_id')
        
        # Get user's provider configuration
        try:
            provider_config = EmailMaskingProvider.objects.get(
                user=request.user,
                provider=provider_name,
                is_active=True
            )
        except EmailMaskingProvider.DoesNotExist:
            return Response({
                'error': f'{provider_name} provider not configured'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Check quota
        if not provider_config.can_create_alias():
            return Response({
                'error': 'Monthly alias creation quota exceeded'
            }, status=status.HTTP_429_TOO_MANY_REQUESTS)
        
        # Decrypt API key
        crypto_service = CryptoService()
        api_key = crypto_service.decrypt_data(provider_config.api_key)
        
        # Create alias using appropriate service
        if provider_name == 'simplelogin':
            service = SimpleLoginService(api_key)
            result = service.create_alias(note=description)
            alias_email = result['email']
            provider_alias_id = str(result['id'])
        elif provider_name == 'anonaddy':
            service = AnonAddyService(api_key)
            result = service.create_alias(description=description)
            alias_email = result['email']
            provider_alias_id = result['id']
        else:
            return Response({
                'error': 'Unsupported provider'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Save to database
        alias = EmailAlias.objects.create(
            user=request.user,
            alias_email=alias_email,
            alias_name=alias_name,
            description=description,
            provider=provider_name,
            provider_alias_id=provider_alias_id,
            forwards_to=request.user.email,
            vault_item_id=vault_item_id,
            status='active'
        )
        
        # Log activity
        EmailAliasActivity.objects.create(
            alias=alias,
            activity_type='created',
            details={'created_via': 'api'}
        )
        
        # Update quota
        provider_config.aliases_created_this_month += 1
        provider_config.save()
        
        return Response({
            'id': alias.id,
            'alias_email': alias.alias_email,
            'forwards_to': alias.forwards_to,
            'provider': alias.provider,
            'status': alias.status,
            'created_at': alias.created_at
        }, status=status.HTTP_201_CREATED)
        
    except Exception as e:
        logger.error(f"Error creating email alias: {e}")
        return Response({
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def list_aliases(request):
    """
    Get all email aliases for the current user
    """
    try:
        aliases = EmailAlias.objects.filter(user=request.user).exclude(status='deleted')
        
        result = []
        for alias in aliases:
            result.append({
                'id': alias.id,
                'alias_email': alias.alias_email,
                'alias_name': alias.alias_name,
                'description': alias.description,
                'forwards_to': alias.forwards_to,
                'provider': alias.provider,
                'status': alias.status,
                'emails_received': alias.emails_received,
                'emails_forwarded': alias.emails_forwarded,
                'emails_blocked': alias.emails_blocked,
                'vault_item_id': alias.vault_item_id,
                'created_at': alias.created_at,
                'last_used_at': alias.last_used_at,
                'is_active': alias.is_active()
            })
        
        return Response(result, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Error listing aliases: {e}")
        return Response({
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET', 'PATCH', 'DELETE'])
@permission_classes([IsAuthenticated])
def alias_detail(request, alias_id):
    """
    Get, update, or delete a specific alias
    """
    try:
        alias = EmailAlias.objects.get(id=alias_id, user=request.user)
    except EmailAlias.DoesNotExist:
        return Response({
            'error': 'Alias not found'
        }, status=status.HTTP_404_NOT_FOUND)
    
    if request.method == 'GET':
        return Response({
            'id': alias.id,
            'alias_email': alias.alias_email,
            'alias_name': alias.alias_name,
            'description': alias.description,
            'forwards_to': alias.forwards_to,
            'provider': alias.provider,
            'status': alias.status,
            'emails_received': alias.emails_received,
            'emails_forwarded': alias.emails_forwarded,
            'emails_blocked': alias.emails_blocked,
            'vault_item_id': alias.vault_item_id,
            'created_at': alias.created_at,
            'last_used_at': alias.last_used_at
        }, status=status.HTTP_200_OK)
    
    elif request.method == 'PATCH':
        # Update alias
        alias_name = request.data.get('alias_name')
        description = request.data.get('description')
        
        if alias_name is not None:
            alias.alias_name = alias_name
        if description is not None:
            alias.description = description
        
        alias.save()
        
        return Response({
            'message': 'Alias updated successfully',
            'id': alias.id
        }, status=status.HTTP_200_OK)
    
    elif request.method == 'DELETE':
        # Delete alias from provider and database
        try:
            provider_config = EmailMaskingProvider.objects.get(
                user=request.user,
                provider=alias.provider,
                is_active=True
            )
            
            crypto_service = CryptoService()
            api_key = crypto_service.decrypt_data(provider_config.api_key)
            
            # Delete from provider
            if alias.provider == 'simplelogin':
                service = SimpleLoginService(api_key)
                service.delete_alias(alias.provider_alias_id)
            elif alias.provider == 'anonaddy':
                service = AnonAddyService(api_key)
                service.delete_alias(alias.provider_alias_id)
            
            # Log activity
            EmailAliasActivity.objects.create(
                alias=alias,
                activity_type='deleted',
                details={'deleted_via': 'api'}
            )
            
            # Mark as deleted
            alias.status = 'deleted'
            alias.save()
            
            return Response({
                'message': 'Alias deleted successfully'
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Error deleting alias: {e}")
            return Response({
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def toggle_alias(request, alias_id):
    """
    Enable/disable an alias
    """
    try:
        alias = EmailAlias.objects.get(id=alias_id, user=request.user)
        
        # Toggle status
        new_status = 'disabled' if alias.status == 'active' else 'active'
        
        # Update on provider
        provider_config = EmailMaskingProvider.objects.get(
            user=request.user,
            provider=alias.provider,
            is_active=True
        )
        
        crypto_service = CryptoService()
        api_key = crypto_service.decrypt_data(provider_config.api_key)
        
        if alias.provider == 'simplelogin':
            service = SimpleLoginService(api_key)
            service.toggle_alias(alias.provider_alias_id)
        elif alias.provider == 'anonaddy':
            service = AnonAddyService(api_key)
            if new_status == 'active':
                service.activate_alias(alias.provider_alias_id)
            else:
                service.deactivate_alias(alias.provider_alias_id)
        
        # Update locally
        alias.status = new_status
        alias.save()
        
        # Log activity
        EmailAliasActivity.objects.create(
            alias=alias,
            activity_type='enabled' if new_status == 'active' else 'disabled',
            details={'toggled_via': 'api'}
        )
        
        return Response({
            'message': f'Alias {new_status}',
            'status': new_status
        }, status=status.HTTP_200_OK)
        
    except EmailAlias.DoesNotExist:
        return Response({
            'error': 'Alias not found'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error(f"Error toggling alias: {e}")
        return Response({
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def alias_activity(request, alias_id):
    """
    Get activity log for an alias
    """
    try:
        alias = EmailAlias.objects.get(id=alias_id, user=request.user)
        activities = EmailAliasActivity.objects.filter(alias=alias)[:50]
        
        result = []
        for activity in activities:
            result.append({
                'activity_type': activity.activity_type,
                'sender_email': activity.sender_email,
                'subject': activity.subject,
                'details': activity.details,
                'timestamp': activity.timestamp
            })
        
        return Response(result, status=status.HTTP_200_OK)
        
    except EmailAlias.DoesNotExist:
        return Response({
            'error': 'Alias not found'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error(f"Error fetching alias activity: {e}")
        return Response({
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def configure_provider(request):
    """
    Configure an email masking provider
    """
    try:
        provider = request.data.get('provider')
        api_key = request.data.get('api_key')
        is_default = request.data.get('is_default', False)
        
        if not provider or not api_key:
            return Response({
                'error': 'Provider and API key are required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Encrypt API key
        crypto_service = CryptoService()
        encrypted_api_key = crypto_service.encrypt_data(api_key)
        
        # Verify API key works
        if provider == 'simplelogin':
            service = SimpleLoginService(api_key)
            user_info = service.get_user_info()
        elif provider == 'anonaddy':
            service = AnonAddyService(api_key)
            user_info = service.get_account_details()
        else:
            return Response({
                'error': 'Unsupported provider'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Save configuration
        provider_config, created = EmailMaskingProvider.objects.update_or_create(
            user=request.user,
            provider=provider,
            defaults={
                'api_key': encrypted_api_key,
                'is_active': True,
                'is_default': is_default
            }
        )
        
        return Response({
            'message': f'{provider} configured successfully',
            'provider': provider,
            'is_default': is_default
        }, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Error configuring provider: {e}")
        return Response({
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def list_providers(request):
    """
    Get configured providers for the current user
    """
    try:
        providers = EmailMaskingProvider.objects.filter(user=request.user)
        
        result = []
        for provider in providers:
            result.append({
                'provider': provider.provider,
                'is_active': provider.is_active,
                'is_default': provider.is_default,
                'monthly_quota': provider.monthly_quota,
                'aliases_created_this_month': provider.aliases_created_this_month,
                'created_at': provider.created_at
            })
        
        return Response(result, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Error listing providers: {e}")
        return Response({
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


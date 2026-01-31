"""
Duress Code API Views

REST API endpoints for managing duress codes, decoy vaults,
trusted authorities, and duress events.
"""

import logging
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from security.services.duress_code_service import get_duress_code_service

logger = logging.getLogger(__name__)


# =============================================================================
# Configuration Endpoints
# =============================================================================

@api_view(['GET', 'PUT'])
@permission_classes([IsAuthenticated])
def duress_config(request):
    """
    GET: Get duress configuration for the current user
    PUT: Update duress configuration
    """
    service = get_duress_code_service()
    
    if request.method == 'GET':
        try:
            config = service.get_or_create_config(request.user)
            return Response({
                'success': True,
                'config': {
                    'is_enabled': config.is_enabled,
                    'threat_level_count': config.threat_level_count,
                    'evidence_preservation_enabled': config.evidence_preservation_enabled,
                    'silent_alarm_enabled': config.silent_alarm_enabled,
                    'behavioral_detection_enabled': config.behavioral_detection_enabled,
                    'legal_compliance_mode': config.legal_compliance_mode,
                    'is_enterprise': config.is_enterprise,
                    'auto_refresh_decoy': config.auto_refresh_decoy,
                    'decoy_refresh_interval_days': config.decoy_refresh_interval_days,
                    'last_tested_at': config.last_tested_at.isoformat() if config.last_tested_at else None,
                    'created_at': config.created_at.isoformat(),
                    'updated_at': config.updated_at.isoformat(),
                }
            })
        except Exception as e:
            logger.error(f"Failed to get duress config: {e}")
            return Response({
                'success': False,
                'error': 'Failed to retrieve configuration'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    elif request.method == 'PUT':
        try:
            data = request.data
            config = service.update_config(
                request.user,
                is_enabled=data.get('is_enabled'),
                threat_level_count=data.get('threat_level_count'),
                evidence_preservation_enabled=data.get('evidence_preservation_enabled'),
                silent_alarm_enabled=data.get('silent_alarm_enabled'),
                behavioral_detection_enabled=data.get('behavioral_detection_enabled'),
                auto_refresh_decoy=data.get('auto_refresh_decoy'),
                decoy_refresh_interval_days=data.get('decoy_refresh_interval_days'),
            )
            return Response({
                'success': True,
                'message': 'Configuration updated',
                'config': {
                    'is_enabled': config.is_enabled,
                    'updated_at': config.updated_at.isoformat(),
                }
            })
        except Exception as e:
            logger.error(f"Failed to update duress config: {e}")
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)


# =============================================================================
# Duress Code CRUD Endpoints
# =============================================================================

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def duress_codes_list(request):
    """
    GET: List all duress codes for the current user
    POST: Create a new duress code
    """
    service = get_duress_code_service()
    
    if request.method == 'GET':
        try:
            codes = service.get_user_codes(request.user)
            return Response({
                'success': True,
                'codes': [
                    {
                        'id': str(code.id),
                        'threat_level': code.threat_level,
                        'code_hint': code.code_hint,
                        'is_active': code.is_active,
                        'activation_count': code.activation_count,
                        'last_activated_at': code.last_activated_at.isoformat() if code.last_activated_at else None,
                        'action_config': code.action_config,
                        'created_at': code.created_at.isoformat(),
                    }
                    for code in codes
                ],
                'count': len(codes)
            })
        except Exception as e:
            logger.error(f"Failed to list duress codes: {e}")
            return Response({
                'success': False,
                'error': 'Failed to retrieve codes'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    elif request.method == 'POST':
        try:
            data = request.data
            code = data.get('code')
            threat_level = data.get('threat_level', 'medium')
            code_hint = data.get('code_hint', '')
            action_config = data.get('action_config', {})
            
            if not code:
                return Response({
                    'success': False,
                    'error': 'Duress code is required'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            duress_code = service.create_duress_code(
                user=request.user,
                code=code,
                threat_level=threat_level,
                code_hint=code_hint,
                action_config=action_config
            )
            
            return Response({
                'success': True,
                'message': 'Duress code created successfully',
                'code': {
                    'id': str(duress_code.id),
                    'threat_level': duress_code.threat_level,
                    'code_hint': duress_code.code_hint,
                    'action_config': duress_code.action_config,
                }
            }, status=status.HTTP_201_CREATED)
            
        except ValueError as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Failed to create duress code: {e}")
            return Response({
                'success': False,
                'error': 'Failed to create code'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET', 'PUT', 'DELETE'])
@permission_classes([IsAuthenticated])
def duress_code_detail(request, code_id):
    """
    GET: Get details of a specific duress code
    PUT: Update a duress code
    DELETE: Delete (deactivate) a duress code
    """
    from security.models.duress_models import DuressCode
    
    service = get_duress_code_service()
    
    try:
        duress_code = DuressCode.objects.get(
            id=code_id,
            user=request.user
        )
    except DuressCode.DoesNotExist:
        return Response({
            'success': False,
            'error': 'Duress code not found'
        }, status=status.HTTP_404_NOT_FOUND)
    
    if request.method == 'GET':
        return Response({
            'success': True,
            'code': {
                'id': str(duress_code.id),
                'threat_level': duress_code.threat_level,
                'code_hint': duress_code.code_hint,
                'is_active': duress_code.is_active,
                'activation_count': duress_code.activation_count,
                'last_activated_at': duress_code.last_activated_at.isoformat() if duress_code.last_activated_at else None,
                'action_config': duress_code.action_config,
                'created_at': duress_code.created_at.isoformat(),
                'updated_at': duress_code.updated_at.isoformat(),
            }
        })
    
    elif request.method == 'PUT':
        try:
            data = request.data
            updated = service.update_duress_code(
                duress_code=duress_code,
                new_code=data.get('new_code'),
                threat_level=data.get('threat_level'),
                code_hint=data.get('code_hint'),
                action_config=data.get('action_config')
            )
            return Response({
                'success': True,
                'message': 'Duress code updated',
                'code': {
                    'id': str(updated.id),
                    'threat_level': updated.threat_level,
                    'updated_at': updated.updated_at.isoformat(),
                }
            })
        except ValueError as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)
    
    elif request.method == 'DELETE':
        service.delete_duress_code(duress_code)
        return Response({
            'success': True,
            'message': 'Duress code deactivated'
        })


# =============================================================================
# Decoy Vault Endpoints
# =============================================================================

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def decoy_vault(request):
    """
    GET: Get decoy vault for the current user
    POST: Regenerate decoy vault
    """
    from security.models.duress_models import DecoyVault
    from security.services.decoy_vault_service import get_decoy_vault_service
    
    threat_level = request.query_params.get('threat_level', 'medium')
    
    if request.method == 'GET':
        try:
            decoy = DecoyVault.objects.filter(
                user=request.user,
                threat_level=threat_level
            ).first()
            
            if not decoy:
                return Response({
                    'success': True,
                    'decoy': None,
                    'message': 'No decoy vault exists for this threat level'
                })
            
            return Response({
                'success': True,
                'decoy': {
                    'id': str(decoy.id),
                    'threat_level': decoy.threat_level,
                    'item_count': decoy.item_count,
                    'realism_score': decoy.realism_score,
                    'items': decoy.decoy_items,
                    'folders': decoy.decoy_folders,
                    'last_refreshed': decoy.last_refreshed.isoformat(),
                }
            })
        except Exception as e:
            logger.error(f"Failed to get decoy vault: {e}")
            return Response({
                'success': False,
                'error': 'Failed to retrieve decoy vault'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    elif request.method == 'POST':
        try:
            data = request.data
            threat_level = data.get('threat_level', 'medium')
            
            decoy_service = get_decoy_vault_service()
            decoy_data = decoy_service.generate_realistic_decoy(
                request.user, threat_level
            )
            
            # Update or create
            decoy, created = DecoyVault.objects.update_or_create(
                user=request.user,
                threat_level=threat_level,
                defaults={
                    'decoy_items': decoy_data['items'],
                    'decoy_folders': decoy_data['folders'],
                    'item_count': len(decoy_data['items']),
                    'realism_score': decoy_data.get('realism_score', 0.8),
                }
            )
            
            return Response({
                'success': True,
                'message': 'Decoy vault regenerated',
                'decoy': {
                    'id': str(decoy.id),
                    'item_count': decoy.item_count,
                    'realism_score': decoy.realism_score,
                    'last_refreshed': decoy.last_refreshed.isoformat(),
                }
            })
        except Exception as e:
            logger.error(f"Failed to regenerate decoy vault: {e}")
            return Response({
                'success': False,
                'error': 'Failed to regenerate decoy vault'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# =============================================================================
# Trusted Authority Endpoints
# =============================================================================

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def trusted_authorities_list(request):
    """
    GET: List all trusted authorities
    POST: Add a new trusted authority
    """
    from security.models.duress_models import TrustedAuthority
    
    if request.method == 'GET':
        try:
            authorities = TrustedAuthority.objects.filter(
                user=request.user,
                is_active=True
            )
            return Response({
                'success': True,
                'authorities': [
                    {
                        'id': str(auth.id),
                        'name': auth.name,
                        'authority_type': auth.authority_type,
                        'contact_method': auth.contact_method,
                        'trigger_threat_levels': auth.trigger_threat_levels,
                        'verification_status': auth.verification_status,
                        'delay_seconds': auth.delay_seconds,
                        'notification_count': auth.notification_count,
                        'last_notified_at': auth.last_notified_at.isoformat() if auth.last_notified_at else None,
                        'created_at': auth.created_at.isoformat(),
                    }
                    for auth in authorities
                ]
            })
        except Exception as e:
            logger.error(f"Failed to list authorities: {e}")
            return Response({
                'success': False,
                'error': 'Failed to retrieve authorities'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    elif request.method == 'POST':
        try:
            data = request.data
            
            authority = TrustedAuthority.objects.create(
                user=request.user,
                name=data.get('name'),
                authority_type=data.get('authority_type', 'custom'),
                contact_method=data.get('contact_method', 'email'),
                contact_details=data.get('contact_details', {}),
                trigger_threat_levels=data.get('trigger_threat_levels', ['high', 'critical']),
                delay_seconds=data.get('delay_seconds', 0),
                include_location=data.get('include_location', True),
                include_evidence_link=data.get('include_evidence_link', False),
            )
            
            # TODO: Send verification request
            
            return Response({
                'success': True,
                'message': 'Trusted authority added',
                'authority': {
                    'id': str(authority.id),
                    'name': authority.name,
                    'verification_status': authority.verification_status,
                }
            }, status=status.HTTP_201_CREATED)
        except Exception as e:
            logger.error(f"Failed to add authority: {e}")
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET', 'PUT', 'DELETE'])
@permission_classes([IsAuthenticated])
def trusted_authority_detail(request, authority_id):
    """
    GET: Get authority details
    PUT: Update authority
    DELETE: Remove authority
    """
    from security.models.duress_models import TrustedAuthority
    
    try:
        authority = TrustedAuthority.objects.get(
            id=authority_id,
            user=request.user
        )
    except TrustedAuthority.DoesNotExist:
        return Response({
            'success': False,
            'error': 'Authority not found'
        }, status=status.HTTP_404_NOT_FOUND)
    
    if request.method == 'GET':
        return Response({
            'success': True,
            'authority': {
                'id': str(authority.id),
                'name': authority.name,
                'authority_type': authority.authority_type,
                'contact_method': authority.contact_method,
                'contact_details': authority.contact_details,
                'trigger_threat_levels': authority.trigger_threat_levels,
                'verification_status': authority.verification_status,
                'delay_seconds': authority.delay_seconds,
                'include_location': authority.include_location,
                'include_evidence_link': authority.include_evidence_link,
                'notification_count': authority.notification_count,
                'last_notified_at': authority.last_notified_at.isoformat() if authority.last_notified_at else None,
            }
        })
    
    elif request.method == 'PUT':
        data = request.data
        
        for field in ['name', 'contact_method', 'contact_details', 
                      'trigger_threat_levels', 'delay_seconds',
                      'include_location', 'include_evidence_link']:
            if field in data:
                setattr(authority, field, data[field])
        
        authority.save()
        return Response({
            'success': True,
            'message': 'Authority updated'
        })
    
    elif request.method == 'DELETE':
        authority.is_active = False
        authority.save(update_fields=['is_active'])
        return Response({
            'success': True,
            'message': 'Authority removed'
        })


# =============================================================================
# Duress Event Endpoints
# =============================================================================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def duress_events_list(request):
    """Get duress event history for the current user"""
    from security.models.duress_models import DuressEvent
    
    try:
        limit = int(request.query_params.get('limit', 50))
        events = DuressEvent.objects.filter(
            user=request.user
        ).order_by('-timestamp')[:limit]
        
        return Response({
            'success': True,
            'events': [
                {
                    'id': str(event.id),
                    'event_type': event.event_type,
                    'threat_level': event.threat_level,
                    'ip_address': event.ip_address,
                    'actions_taken': event.actions_taken,
                    'silent_alarm_sent': event.silent_alarm_sent,
                    'evidence_package_id': str(event.evidence_package_id) if event.evidence_package_id else None,
                    'timestamp': event.timestamp.isoformat(),
                }
                for event in events
            ]
        })
    except Exception as e:
        logger.error(f"Failed to list events: {e}")
        return Response({
            'success': False,
            'error': 'Failed to retrieve events'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# =============================================================================
# Evidence Package Endpoints
# =============================================================================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def evidence_package_detail(request, package_id):
    """Get evidence package details"""
    from security.models.duress_models import EvidencePackage
    from security.services.evidence_preservation_service import get_evidence_preservation_service
    
    try:
        package = EvidencePackage.objects.get(
            id=package_id,
            user=request.user
        )
    except EvidencePackage.DoesNotExist:
        return Response({
            'success': False,
            'error': 'Evidence package not found'
        }, status=status.HTTP_404_NOT_FOUND)
    
    return Response({
        'success': True,
        'package': {
            'id': str(package.id),
            'status': package.status,
            'evidence_hash': package.evidence_hash,
            'legal_timestamp': package.legal_timestamp.isoformat() if package.legal_timestamp else None,
            'timestamp_authority': package.timestamp_authority,
            'created_at': package.created_at.isoformat(),
            'sealed_at': package.sealed_at.isoformat() if package.sealed_at else None,
            'custody_log': package.custody_log,
            'summary': {
                'has_behavioral_data': bool(package.behavioral_snapshot),
                'has_device_info': bool(package.device_info),
                'has_network_info': bool(package.network_info),
                'has_geo_location': bool(package.geo_location),
            }
        }
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def evidence_package_export(request, package_id):
    """Export evidence package for legal use"""
    from security.models.duress_models import EvidencePackage
    from security.services.evidence_preservation_service import get_evidence_preservation_service
    
    try:
        package = EvidencePackage.objects.get(
            id=package_id,
            user=request.user
        )
    except EvidencePackage.DoesNotExist:
        return Response({
            'success': False,
            'error': 'Evidence package not found'
        }, status=status.HTTP_404_NOT_FOUND)
    
    service = get_evidence_preservation_service()
    export_data = service.export_for_legal(
        package,
        requesting_user=request.user.username
    )
    
    return Response({
        'success': True,
        'message': 'Evidence package exported',
        'export': export_data
    })


# =============================================================================
# Test Activation Endpoint
# =============================================================================

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def test_duress_activation(request):
    """
    Test duress code activation in safe mode.
    Does not send real alerts or lock vault.
    """
    from security.models.duress_models import DuressCode
    
    service = get_duress_code_service()
    
    try:
        code_id = request.data.get('code_id')
        
        if not code_id:
            return Response({
                'success': False,
                'error': 'code_id is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        duress_code = DuressCode.objects.get(
            id=code_id,
            user=request.user,
            is_active=True
        )
        
        # Build request context
        request_context = {
            'ip_address': request.META.get('REMOTE_ADDR', '0.0.0.0'),
            'user_agent': request.META.get('HTTP_USER_AGENT', ''),
            'device_fingerprint': request.data.get('device_fingerprint', {}),
            'geo_location': request.data.get('geo_location', {}),
            'behavioral_data': request.data.get('behavioral_data', {}),
        }
        
        # Activate in test mode
        result = service.activate_duress_mode(
            user=request.user,
            duress_code=duress_code,
            request_context=request_context,
            is_test=True
        )
        
        # Update last tested timestamp
        config = service.get_or_create_config(request.user)
        from django.utils import timezone
        config.last_tested_at = timezone.now()
        config.save(update_fields=['last_tested_at'])
        
        return Response({
            'success': True,
            'message': 'Test activation completed',
            'result': result
        })
        
    except DuressCode.DoesNotExist:
        return Response({
            'success': False,
            'error': 'Duress code not found'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error(f"Test activation failed: {e}")
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

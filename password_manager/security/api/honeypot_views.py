"""
Honeypot Email API Views
========================

REST API endpoints for honeypot email breach detection system.
Provides CRUD operations for honeypots, breach management,
activity logs, and credential rotation.

@author Password Manager Team
@created 2026-02-01
"""

import json
import logging
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from django.utils import timezone

from ..services.honeypot_service import get_honeypot_service
from ..models import (
    HoneypotConfiguration,
    HoneypotEmail,
    HoneypotActivity,
    HoneypotBreachEvent,
    CredentialRotationLog,
)

logger = logging.getLogger(__name__)


# =============================================================================
# Configuration Endpoints
# =============================================================================

class HoneypotConfigView(APIView):
    """Manage user's honeypot configuration."""
    
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """Get honeypot configuration for current user."""
        service = get_honeypot_service()
        config = service.get_or_create_config(request.user)
        
        return Response({
            'id': str(config.id),
            'is_enabled': config.is_enabled,
            'email_provider': config.email_provider,
            'has_api_key': bool(config.provider_api_key),
            'custom_domain': config.custom_domain,
            'auto_rotate_on_breach': config.auto_rotate_on_breach,
            'require_confirmation': config.require_confirmation,
            'auto_create_on_signup': config.auto_create_on_signup,
            'suggest_honeypot_creation': config.suggest_honeypot_creation,
            'notify_on_any_activity': config.notify_on_any_activity,
            'notify_on_breach': config.notify_on_breach,
            'notification_email': config.notification_email,
            'max_honeypots': config.max_honeypots,
            'honeypot_count': config.honeypot_count,
            'can_create_honeypot': config.can_create_honeypot,
        })
    
    def put(self, request):
        """Update honeypot configuration."""
        service = get_honeypot_service()
        
        try:
            config = service.update_config(request.user, **request.data)
            
            return Response({
                'message': 'Configuration updated successfully',
                'id': str(config.id),
            })
        except Exception as e:
            logger.error(f"Config update failed: {e}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )


# =============================================================================
# Honeypot CRUD Endpoints
# =============================================================================

class HoneypotListCreateView(APIView):
    """List and create honeypot emails."""
    
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """List all honeypots for current user."""
        service = get_honeypot_service()
        
        # Parse query params
        status_filter = request.query_params.get('status')
        include_inactive = request.query_params.get('include_inactive', 'false').lower() == 'true'
        
        honeypots = service.get_user_honeypots(
            request.user,
            status=status_filter,
            include_inactive=include_inactive
        )
        
        return Response({
            'count': len(honeypots),
            'honeypots': [self._serialize_honeypot(h) for h in honeypots]
        })
    
    def post(self, request):
        """Create a new honeypot email."""
        service = get_honeypot_service()
        
        # Validate required fields
        service_name = request.data.get('service_name')
        if not service_name:
            return Response(
                {'error': 'service_name is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            honeypot = service.create_honeypot(
                user=request.user,
                service_name=service_name,
                service_domain=request.data.get('service_domain', ''),
                vault_item_id=request.data.get('vault_item_id'),
                notes=request.data.get('notes', ''),
                tags=request.data.get('tags', [])
            )
            
            return Response({
                'message': 'Honeypot created successfully',
                'honeypot': self._serialize_honeypot(honeypot)
            }, status=status.HTTP_201_CREATED)
            
        except ValueError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.error(f"Honeypot creation failed: {e}")
            return Response(
                {'error': 'Failed to create honeypot'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def _serialize_honeypot(self, honeypot: HoneypotEmail) -> dict:
        """Serialize honeypot to JSON."""
        return {
            'id': str(honeypot.id),
            'honeypot_address': honeypot.honeypot_address,
            'service_name': honeypot.service_name,
            'service_domain': honeypot.service_domain,
            'vault_item_id': str(honeypot.vault_item_id) if honeypot.vault_item_id else None,
            'status': honeypot.status,
            'is_active': honeypot.is_active,
            'total_emails_received': honeypot.total_emails_received,
            'spam_emails_received': honeypot.spam_emails_received,
            'breach_detected': honeypot.breach_detected,
            'breach_detected_at': honeypot.breach_detected_at.isoformat() if honeypot.breach_detected_at else None,
            'breach_confidence': honeypot.breach_confidence,
            'last_activity_at': honeypot.last_activity_at.isoformat() if honeypot.last_activity_at else None,
            'days_active': honeypot.days_active,
            'notes': honeypot.notes,
            'tags': honeypot.tags,
            'created_at': honeypot.created_at.isoformat(),
        }


class HoneypotDetailView(APIView):
    """Get, update, or delete a specific honeypot."""
    
    permission_classes = [IsAuthenticated]
    
    def get(self, request, honeypot_id):
        """Get honeypot details."""
        service = get_honeypot_service()
        honeypot = service.get_honeypot(honeypot_id, request.user)
        
        if not honeypot:
            return Response(
                {'error': 'Honeypot not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Get recent activities
        activities = HoneypotActivity.objects.filter(
            honeypot=honeypot
        ).order_by('-received_at')[:10]
        
        return Response({
            'honeypot': HoneypotListCreateView()._serialize_honeypot(honeypot),
            'recent_activities': [
                {
                    'id': str(a.id),
                    'type': a.activity_type,
                    'sender_domain': a.sender_domain,
                    'is_spam': a.is_spam,
                    'is_breach_indicator': a.is_breach_indicator,
                    'received_at': a.received_at.isoformat(),
                }
                for a in activities
            ]
        })
    
    def patch(self, request, honeypot_id):
        """Update honeypot (notes, tags, etc)."""
        service = get_honeypot_service()
        honeypot = service.get_honeypot(honeypot_id, request.user)
        
        if not honeypot:
            return Response(
                {'error': 'Honeypot not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Update allowed fields
        if 'notes' in request.data:
            honeypot.notes = request.data['notes']
        if 'tags' in request.data:
            honeypot.tags = request.data['tags']
        
        honeypot.save()
        
        return Response({
            'message': 'Honeypot updated',
            'honeypot': HoneypotListCreateView()._serialize_honeypot(honeypot)
        })
    
    def delete(self, request, honeypot_id):
        """Delete (deactivate) a honeypot."""
        service = get_honeypot_service()
        honeypot = service.get_honeypot(honeypot_id, request.user)
        
        if not honeypot:
            return Response(
                {'error': 'Honeypot not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        success = service.delete_honeypot(honeypot)
        
        if success:
            return Response({'message': 'Honeypot deleted'})
        else:
            return Response(
                {'error': 'Failed to delete honeypot'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class HoneypotTestView(APIView):
    """Test a honeypot by checking for activity."""
    
    permission_classes = [IsAuthenticated]
    
    def post(self, request, honeypot_id):
        """Manually check honeypot for activity."""
        service = get_honeypot_service()
        honeypot = service.get_honeypot(honeypot_id, request.user)
        
        if not honeypot:
            return Response(
                {'error': 'Honeypot not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        try:
            activities = service.check_honeypot_for_activity(honeypot)
            
            return Response({
                'message': 'Honeypot checked',
                'new_activities': len(activities),
                'status': honeypot.status,
                'breach_detected': honeypot.breach_detected,
            })
        except Exception as e:
            logger.error(f"Honeypot test failed: {e}")
            return Response(
                {'error': 'Failed to check honeypot'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


# =============================================================================
# Breach Endpoints
# =============================================================================

class BreachListView(APIView):
    """List detected breaches."""
    
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """Get all breach events for user."""
        service = get_honeypot_service()
        
        status_filter = request.query_params.get('status')
        include_resolved = request.query_params.get('include_resolved', 'false').lower() == 'true'
        
        breaches = service.get_user_breaches(
            request.user,
            status=status_filter,
            include_resolved=include_resolved
        )
        
        return Response({
            'count': len(breaches),
            'breaches': [self._serialize_breach(b) for b in breaches]
        })
    
    def _serialize_breach(self, breach: HoneypotBreachEvent) -> dict:
        """Serialize breach event to JSON."""
        return {
            'id': str(breach.id),
            'service_name': breach.service_name,
            'severity': breach.severity,
            'severity_display': breach.get_severity_display(),
            'status': breach.status,
            'status_display': breach.get_status_display(),
            'detected_at': breach.detected_at.isoformat(),
            'confidence_score': breach.confidence_score,
            'credentials_rotated': breach.credentials_rotated,
            'user_acknowledged': breach.user_acknowledged,
            'days_before_public': breach.days_before_public,
            'honeypot_id': str(breach.honeypot.id) if breach.honeypot else None,
        }


class BreachDetailView(APIView):
    """Get breach details and timeline."""
    
    permission_classes = [IsAuthenticated]
    
    def get(self, request, breach_id):
        """Get breach details with timeline."""
        service = get_honeypot_service()
        timeline = service.get_breach_timeline(breach_id, request.user)
        
        if not timeline:
            return Response(
                {'error': 'Breach not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        return Response(timeline)
    
    def patch(self, request, breach_id):
        """Update breach status or acknowledge."""
        try:
            breach = HoneypotBreachEvent.objects.get(
                id=breach_id,
                user=request.user
            )
        except HoneypotBreachEvent.DoesNotExist:
            return Response(
                {'error': 'Breach not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Acknowledge breach
        if request.data.get('acknowledge'):
            breach.user_acknowledged = True
            breach.user_acknowledged_at = timezone.now()
        
        # Add user notes
        if 'user_notes' in request.data:
            breach.user_notes = request.data['user_notes']
        
        # Update status
        if 'status' in request.data:
            allowed_statuses = ['investigating', 'confirmed', 'mitigated', 'resolved', 'false_positive']
            if request.data['status'] in allowed_statuses:
                breach.status = request.data['status']
                if request.data['status'] == 'resolved':
                    breach.resolved_at = timezone.now()
        
        breach.save()
        
        return Response({
            'message': 'Breach updated',
            'status': breach.status,
        })


class BreachRotateView(APIView):
    """Initiate credential rotation for a breach."""
    
    permission_classes = [IsAuthenticated]
    
    def post(self, request, breach_id):
        """Start credential rotation process."""
        service = get_honeypot_service()
        
        try:
            breach = HoneypotBreachEvent.objects.get(
                id=breach_id,
                user=request.user
            )
        except HoneypotBreachEvent.DoesNotExist:
            return Response(
                {'error': 'Breach not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        rotation = service.initiate_credential_rotation(
            breach,
            trigger='manual_user'
        )
        
        return Response({
            'message': 'Credential rotation initiated',
            'rotation_id': str(rotation.id),
            'service_name': rotation.service_name,
            'status': rotation.status,
        }, status=status.HTTP_201_CREATED)


# =============================================================================
# Activity Endpoints
# =============================================================================

class ActivityListView(APIView):
    """List honeypot activity logs."""
    
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """Get activity logs for user's honeypots."""
        honeypot_id = request.query_params.get('honeypot_id')
        limit = int(request.query_params.get('limit', 50))
        
        queryset = HoneypotActivity.objects.filter(
            honeypot__user=request.user
        )
        
        if honeypot_id:
            queryset = queryset.filter(honeypot_id=honeypot_id)
        
        activities = queryset.order_by('-received_at')[:limit]
        
        return Response({
            'count': len(activities),
            'activities': [
                {
                    'id': str(a.id),
                    'honeypot_id': str(a.honeypot_id),
                    'service_name': a.honeypot.service_name,
                    'activity_type': a.activity_type,
                    'activity_type_display': a.get_activity_type_display(),
                    'sender_domain': a.sender_domain,
                    'subject_preview': a.subject_preview,
                    'is_spam': a.is_spam,
                    'spam_score': a.spam_score,
                    'is_breach_indicator': a.is_breach_indicator,
                    'received_at': a.received_at.isoformat(),
                }
                for a in activities
            ]
        })


# =============================================================================
# Webhook Endpoint
# =============================================================================

class HoneypotWebhookView(APIView):
    """Webhook endpoint for email provider callbacks."""
    
    permission_classes = []  # Public endpoint with signature verification
    
    def post(self, request):
        """Process incoming email webhook."""
        service = get_honeypot_service()
        
        # Get provider from header
        provider = request.headers.get('X-Honeypot-Provider', 'unknown')
        
        # Verify webhook signature
        signature = request.headers.get('X-Webhook-Signature', '')
        if not self._verify_signature(request.body, signature, provider):
            logger.warning(f"Invalid webhook signature from {provider}")
            return Response(
                {'error': 'Invalid signature'},
                status=status.HTTP_401_UNAUTHORIZED
            )
        
        try:
            # Parse webhook payload
            data = request.data
            
            honeypot_address = data.get('recipient') or data.get('to')
            sender_address = data.get('sender') or data.get('from')
            subject = data.get('subject', '')
            is_spam = data.get('is_spam', False)
            spam_score = float(data.get('spam_score', 0.0))
            headers = data.get('headers', {})
            
            if not honeypot_address:
                return Response(
                    {'error': 'Missing recipient address'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            activity, breach_detected = service.process_incoming_email(
                honeypot_address=honeypot_address,
                sender_address=sender_address or '',
                subject=subject,
                headers=headers,
                is_spam=is_spam,
                spam_score=spam_score
            )
            
            if activity:
                logger.info(f"Webhook processed: {honeypot_address}")
                return Response({
                    'status': 'processed',
                    'breach_detected': breach_detected,
                })
            else:
                return Response(
                    {'error': 'Unknown honeypot address'},
                    status=status.HTTP_404_NOT_FOUND
                )
                
        except Exception as e:
            logger.error(f"Webhook processing failed: {e}")
            return Response(
                {'error': 'Processing failed'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def _verify_signature(self, payload: bytes, signature: str, provider: str) -> bool:
        """Verify webhook signature based on provider."""
        from django.conf import settings
        import hashlib
        import hmac
        
        secrets = {
            'simplelogin': getattr(settings, 'SIMPLELOGIN_WEBHOOK_SECRET', ''),
            'anonaddy': getattr(settings, 'ANONADDY_WEBHOOK_SECRET', ''),
            'custom': getattr(settings, 'CUSTOM_SMTP_WEBHOOK_SECRET', ''),
        }
        
        secret = secrets.get(provider, '')
        
        # Skip verification in development
        if settings.DEBUG and not secret:
            return True
        
        if not secret:
            return False
        
        expected = hmac.new(
            secret.encode(),
            payload,
            hashlib.sha256
        ).hexdigest()
        
        return hmac.compare_digest(expected, signature)


# =============================================================================
# Bulk Operations
# =============================================================================

class BulkCreateHoneypotsView(APIView):
    """Bulk create honeypots for multiple services."""
    
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        """Create honeypots for multiple services at once."""
        service = get_honeypot_service()
        
        services = request.data.get('services', [])
        if not services:
            return Response(
                {'error': 'services list is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        results = {
            'created': [],
            'failed': [],
        }
        
        for svc in services:
            service_name = svc.get('service_name')
            if not service_name:
                continue
            
            try:
                honeypot = service.create_honeypot(
                    user=request.user,
                    service_name=service_name,
                    service_domain=svc.get('service_domain', ''),
                    vault_item_id=svc.get('vault_item_id'),
                )
                results['created'].append({
                    'service_name': service_name,
                    'honeypot_id': str(honeypot.id),
                    'honeypot_address': honeypot.honeypot_address,
                })
            except Exception as e:
                results['failed'].append({
                    'service_name': service_name,
                    'error': str(e),
                })
        
        return Response({
            'created_count': len(results['created']),
            'failed_count': len(results['failed']),
            'results': results,
        }, status=status.HTTP_201_CREATED)


class CheckAllHoneypotsView(APIView):
    """Check all honeypots for a user."""
    
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        """Trigger activity check on all honeypots."""
        service = get_honeypot_service()
        
        results = service.check_all_honeypots(request.user)
        
        return Response(results)

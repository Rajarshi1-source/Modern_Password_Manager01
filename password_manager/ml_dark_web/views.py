"""
API Views for ML-Powered Dark Web Monitoring
"""

from rest_framework import viewsets, status
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.db.models import Q, Count, Avg
import logging

from .models import (
    BreachSource, MLBreachData, UserCredentialMonitoring,
    MLBreachMatch, DarkWebScrapeLog, BreachPatternAnalysis,
    MLModelMetadata
)
from .tasks import (
    monitor_user_credentials, check_user_against_all_breaches,
    scrape_dark_web_source, scrape_all_active_sources
)
from .ml_services import get_breach_classifier, get_credential_matcher
from vault.models import BreachAlert

logger = logging.getLogger(__name__)
User = get_user_model()


class MLDarkWebViewSet(viewsets.ViewSet):
    """API endpoints for ML-powered dark web monitoring"""
    permission_classes = [IsAuthenticated]
    
    @action(detail=False, methods=['post'])
    def add_credential_monitoring(self, request):
        """
        Add user credentials for monitoring
        
        POST /api/ml-darkweb/add_credential_monitoring/
        Body: {
            "credentials": ["user@example.com", "another@example.com"]
        }
        """
        credentials = request.data.get('credentials', [])
        
        if not credentials or not isinstance(credentials, list):
            return Response(
                {'error': 'Valid credentials list required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            # Add credentials to monitoring system
            result = monitor_user_credentials.delay(
                request.user.id,
                credentials
            )
            
            return Response({
                'success': True,
                'message': f'{len(credentials)} credential(s) added for monitoring',
                'task_id': result.id
            })
        
        except Exception as e:
            logger.error(f"Error adding credentials: {e}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['get'])
    def monitored_credentials(self, request):
        """
        Get user's monitored credentials
        
        GET /api/ml-darkweb/monitored_credentials/
        """
        try:
            credentials = UserCredentialMonitoring.objects.filter(
                user=request.user,
                is_active=True
            ).values('id', 'domain', 'created_at', 'last_checked')
            
            return Response(list(credentials))
        
        except Exception as e:
            logger.error(f"Error fetching monitored credentials: {e}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['delete'])
    def remove_credential_monitoring(self, request):
        """
        Remove credential from monitoring
        
        DELETE /api/ml-darkweb/remove_credential_monitoring/
        Body: {
            "credential_id": 123
        }
        """
        credential_id = request.data.get('credential_id')
        
        if not credential_id:
            return Response(
                {'error': 'credential_id required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            credential = UserCredentialMonitoring.objects.get(
                id=credential_id,
                user=request.user
            )
            credential.is_active = False
            credential.save()
            
            return Response({'success': True, 'message': 'Credential monitoring removed'})
        
        except UserCredentialMonitoring.DoesNotExist:
            return Response(
                {'error': 'Credential not found'},
                status=status.HTTP_404_NOT_FOUND
            )
    
    @action(detail=False, methods=['get'])
    def breach_matches(self, request):
        """
        Get user's breach matches
        
        GET /api/ml-darkweb/breach_matches/
        Query params:
            - resolved: true/false (filter by resolved status)
            - limit: int (number of results)
        """
        try:
            resolved_filter = request.query_params.get('resolved')
            limit = int(request.query_params.get('limit', 50))
            
            matches = MLBreachMatch.objects.filter(
                user=request.user
            ).select_related('breach', 'monitored_credential')
            
            if resolved_filter is not None:
                resolved_bool = resolved_filter.lower() == 'true'
                matches = matches.filter(resolved=resolved_bool)
            
            matches = matches.order_by('-detected_at')[:limit]
            
            result = [{
                'id': match.id,
                'breach_id': match.breach.breach_id,
                'breach_title': match.breach.title,
                'severity': match.breach.severity,
                'similarity_score': match.similarity_score,
                'confidence_score': match.confidence_score,
                'detected_at': match.detected_at,
                'resolved': match.resolved,
                'alert_created': match.alert_created,
                'domain': match.monitored_credential.domain
            } for match in matches]
            
            return Response(result)
        
        except Exception as e:
            logger.error(f"Error fetching breach matches: {e}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['post'])
    def resolve_match(self, request):
        """
        Mark a breach match as resolved
        
        POST /api/ml-darkweb/resolve_match/
        Body: {
            "match_id": 123
        }
        """
        match_id = request.data.get('match_id')
        
        if not match_id:
            return Response(
                {'error': 'match_id required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            match = MLBreachMatch.objects.get(
                id=match_id,
                user=request.user
            )
            match.resolved = True
            match.resolved_at = timezone.now()
            match.save()
            
            return Response({'success': True, 'message': 'Match marked as resolved'})
        
        except MLBreachMatch.DoesNotExist:
            return Response(
                {'error': 'Match not found'},
                status=status.HTTP_404_NOT_FOUND
            )
    
    @action(detail=False, methods=['post'])
    def scan_now(self, request):
        """
        Trigger immediate scan of user's credentials against all breaches
        
        POST /api/ml-darkweb/scan_now/
        """
        try:
            result = check_user_against_all_breaches.delay(request.user.id)
            
            return Response({
                'success': True,
                'message': 'Scan initiated',
                'task_id': result.id
            })
        
        except Exception as e:
            logger.error(f"Error initiating scan: {e}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """
        Get dark web monitoring statistics for user
        
        GET /api/ml-darkweb/statistics/
        """
        try:
            # Get counts
            monitored_count = UserCredentialMonitoring.objects.filter(
                user=request.user,
                is_active=True
            ).count()
            
            matches_count = MLBreachMatch.objects.filter(
                user=request.user,
                resolved=False
            ).count()
            
            total_matches = MLBreachMatch.objects.filter(
                user=request.user
            ).count()
            
            # Get recent activity
            recent_matches = MLBreachMatch.objects.filter(
                user=request.user
            ).order_by('-detected_at')[:5]
            
            recent_activity = [{
                'breach_title': match.breach.title,
                'severity': match.breach.severity,
                'detected_at': match.detected_at
            } for match in recent_matches]
            
            return Response({
                'monitored_credentials': monitored_count,
                'active_matches': matches_count,
                'total_matches': total_matches,
                'recent_activity': recent_activity
            })
        
        except Exception as e:
            logger.error(f"Error fetching statistics: {e}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['get'])
    def breach_details(self, request):
        """
        Get details of a specific breach
        
        GET /api/ml-darkweb/breach_details/?breach_id=BREACH_123
        """
        breach_id = request.query_params.get('breach_id')
        
        if not breach_id:
            return Response(
                {'error': 'breach_id required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            breach = MLBreachData.objects.get(breach_id=breach_id)
            
            # Check if user is affected
            user_match = MLBreachMatch.objects.filter(
                user=request.user,
                breach=breach
            ).first()
            
            result = {
                'breach_id': breach.breach_id,
                'title': breach.title,
                'description': breach.description,
                'severity': breach.severity,
                'confidence_score': breach.confidence_score,
                'detected_at': breach.detected_at,
                'breach_date': breach.breach_date,
                'affected_records': breach.affected_records,
                'exposed_data_types': breach.exposed_data_types,
                'source': breach.source.name,
                'user_affected': user_match is not None,
                'similarity_score': user_match.similarity_score if user_match else None
            }
            
            return Response(result)
        
        except MLBreachData.DoesNotExist:
            return Response(
                {'error': 'Breach not found'},
                status=status.HTTP_404_NOT_FOUND
            )


class MLDarkWebAdminViewSet(viewsets.ViewSet):
    """Admin-only endpoints for managing dark web monitoring"""
    permission_classes = [IsAdminUser]
    
    @action(detail=False, methods=['get'])
    def sources(self, request):
        """Get all breach sources"""
        sources = BreachSource.objects.all().values(
            'id', 'name', 'url', 'source_type', 'is_active',
            'reliability_score', 'last_scraped'
        )
        return Response(list(sources))
    
    @action(detail=False, methods=['post'])
    def add_source(self, request):
        """Add a new breach source"""
        name = request.data.get('name')
        url = request.data.get('url')
        source_type = request.data.get('source_type')
        
        if not all([name, url, source_type]):
            return Response(
                {'error': 'name, url, and source_type required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            source = BreachSource.objects.create(
                name=name,
                url=url,
                source_type=source_type
            )
            
            return Response({
                'success': True,
                'source_id': source.id
            })
        
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['post'])
    def trigger_scrape(self, request):
        """Trigger scraping of specific source or all sources"""
        source_id = request.data.get('source_id')
        
        if source_id:
            # Scrape specific source
            result = scrape_dark_web_source.delay(source_id)
            message = f'Scrape initiated for source {source_id}'
        else:
            # Scrape all sources
            result = scrape_all_active_sources.delay()
            message = 'Scrape initiated for all active sources'
        
        return Response({
            'success': True,
            'message': message,
            'task_id': result.id
        })
    
    @action(detail=False, methods=['get'])
    def scrape_logs(self, request):
        """Get recent scrape logs"""
        limit = int(request.query_params.get('limit', 50))
        
        logs = DarkWebScrapeLog.objects.select_related('source').order_by('-started_at')[:limit]
        
        result = [{
            'id': log.id,
            'source_name': log.source.name,
            'started_at': log.started_at,
            'completed_at': log.completed_at,
            'status': log.status,
            'items_found': log.items_found,
            'breaches_detected': log.breaches_detected,
            'processing_time_seconds': log.processing_time_seconds,
            'error_message': log.error_message
        } for log in logs]
        
        return Response(result)
    
    @action(detail=False, methods=['get'])
    def system_statistics(self, request):
        """Get overall system statistics"""
        try:
            stats = {
                'total_breaches': MLBreachData.objects.count(),
                'active_breaches': MLBreachData.objects.filter(
                    processing_status='matched'
                ).count(),
                'total_matches': MLBreachMatch.objects.count(),
                'unresolved_matches': MLBreachMatch.objects.filter(
                    resolved=False
                ).count(),
                'monitored_users': UserCredentialMonitoring.objects.values('user').distinct().count(),
                'total_monitored_credentials': UserCredentialMonitoring.objects.filter(
                    is_active=True
                ).count(),
                'active_sources': BreachSource.objects.filter(is_active=True).count(),
                'average_confidence': MLBreachData.objects.aggregate(
                    Avg('confidence_score')
                )['confidence_score__avg'] or 0,
                'breaches_by_severity': dict(
                    MLBreachData.objects.values('severity').annotate(
                        count=Count('id')
                    ).values_list('severity', 'count')
                )
            }
            
            return Response(stats)
        
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['get'])
    def model_info(self, request):
        """Get ML model information"""
        try:
            models = MLModelMetadata.objects.filter(is_active=True)
            
            result = [{
                'model_type': model.get_model_type_display(),
                'version': model.version,
                'accuracy': model.accuracy,
                'training_date': model.training_date,
                'last_used': model.last_used
            } for model in models]
            
            return Response(result)
        
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def classify_text(request):
    """
    Classify arbitrary text for breach content (for testing/admin)
    
    POST /api/ml-darkweb/classify-text/
    Body: {
        "text": "Text to classify"
    }
    """
    text = request.data.get('text')
    
    if not text:
        return Response(
            {'error': 'text required'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        classifier = get_breach_classifier()
        result = classifier.classify_breach(text)
        
        return Response(result)
    
    except Exception as e:
        logger.error(f"Error classifying text: {e}")
        return Response(
            {'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def mark_alert_read(request, alert_id):
    """
    Mark a breach alert as read and broadcast update via WebSocket
    
    POST /api/ml-darkweb/mark-alert-read/<alert_id>/
    """
    try:
        alert = BreachAlert.objects.get(id=alert_id, user=request.user)
        alert.is_read = True
        alert.read_at = timezone.now()
        alert.save()
        
        # Broadcast update via WebSocket using Celery
        from .tasks import broadcast_alert_update
        broadcast_alert_update.delay(
            user_id=request.user.id,
            alert_id=alert_id,
            update_type='marked_read',
            additional_data={
                'read_at': alert.read_at.isoformat()
            }
        )
        
        logger.info(f"Alert {alert_id} marked as read by user {request.user.id}")
        
        return Response({
            'success': True,
            'message': 'Alert marked as read',
            'alert_id': alert_id,
            'read_at': alert.read_at
        })
    
    except BreachAlert.DoesNotExist:
        return Response(
            {'error': 'Alert not found or access denied'},
            status=status.HTTP_404_NOT_FOUND
        )
    
    except Exception as e:
        logger.error(f"Error marking alert as read: {e}")
        return Response(
            {'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_breach_alerts(request):
    """
    Get breach alerts for the authenticated user
    
    GET /api/ml-darkweb/breach-alerts/
    Query params:
        - unread: true/false (filter by read status)
        - severity: LOW/MEDIUM/HIGH/CRITICAL
        - limit: int (default: 50)
    """
    try:
        alerts = BreachAlert.objects.filter(user=request.user)
        
        # Apply filters
        unread_filter = request.query_params.get('unread')
        if unread_filter:
            is_unread = unread_filter.lower() == 'true'
            alerts = alerts.filter(is_read=not is_unread)
        
        severity_filter = request.query_params.get('severity')
        if severity_filter:
            alerts = alerts.filter(severity=severity_filter.upper())
        
        # Limit results
        limit = int(request.query_params.get('limit', 50))
        alerts = alerts.order_by('-detected_at')[:limit]
        
        # Serialize
        result = [{
            'id': alert.id,
            'breach_name': alert.breach_name,
            'breach_description': alert.breach_description,
            'severity': alert.severity,
            'detected_at': alert.detected_at,
            'is_read': alert.is_read,
            'read_at': alert.read_at,
            'notified': alert.notified,
            'notification_sent_at': alert.notification_sent_at
        } for alert in alerts]
        
        return Response({
            'success': True,
            'count': len(result),
            'alerts': result
        })
    
    except Exception as e:
        logger.error(f"Error fetching breach alerts: {e}")
        return Response(
            {'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

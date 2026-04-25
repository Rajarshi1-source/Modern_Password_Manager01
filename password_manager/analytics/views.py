"""
Analytics API Views
==================

API endpoints for analytics data collection and reporting.

GDPR Note: IP addresses are anonymized before storage by truncating
to /24 (IPv4) or /48 (IPv6) subnets. This prevents individual
identification while preserving geo-level analytics utility.
"""

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from django.utils import timezone
from django.db.models import Count, Avg, Sum, Q
from django.contrib.auth.models import User
from datetime import timedelta
import json
import logging

logger = logging.getLogger(__name__)


def _anonymize_ip(ip_address: str) -> str:
    """
    Anonymize an IP address for GDPR compliance.
    - IPv4: truncate to /24 subnet (last octet zeroed)
    - IPv6: truncate to /48 subnet (last 80 bits zeroed)
    """
    if not ip_address:
        return None
    
    ip_address = ip_address.strip()
    
    if ':' in ip_address:
        # IPv6 — truncate to /48
        parts = ip_address.split(':')
        # Keep first 3 groups, zero the rest
        anonymized = ':'.join(parts[:3] + ['0'] * (len(parts) - 3))
        return anonymized
    else:
        # IPv4 — truncate to /24
        parts = ip_address.split('.')
        if len(parts) == 4:
            parts[3] = '0'
            return '.'.join(parts)
    
    return ip_address

from .models import (
    AnalyticsEvent,
    UserEngagement,
    Conversion,
    UserSession,
    PerformanceMetric,
    Funnel,
    FunnelCompletion,
    CohortDefinition
)


@api_view(['POST'])
@permission_classes([AllowAny])  # Allow anonymous analytics
def track_events(request):
    """
    Track analytics events in batch (async via Celery).
    
    POST /api/analytics/events/
    Body: {
        "events": [...],
        "engagements": [...],
        "conversions": [...],
        "session": {...},
        "performance": {...}
    }
    
    Rate limited to 30 requests/minute for anonymous users to prevent
    DB flooding attacks.  Actual DB writes are dispatched to a Celery
    task and processed asynchronously.
    """
    from rest_framework.throttling import AnonRateThrottle, ScopedRateThrottle

    # --- Manual throttle enforcement ---
    # We apply a scoped throttle ('analytics_track') here because the
    # view uses @permission_classes([AllowAny]) which skips the default
    # throttle class check for anonymous users in some DRF versions.
    throttle = ScopedRateThrottle()
    throttle.scope = 'analytics_track'
    if not throttle.allow_request(request, None):
        wait = throttle.wait()
        return Response({
            'status': 'error',
            'message': f'Rate limit exceeded. Retry after {int(wait or 60)} seconds.',
        }, status=status.HTTP_429_TOO_MANY_REQUESTS)

    try:
        data = request.data
        
        # Get user ID (or None for anonymous)
        user_id = request.user.id if request.user.is_authenticated else None
        
        # Get and anonymize client IP
        client_ip = request.META.get('HTTP_X_FORWARDED_FOR', '').split(',')[0] or \
                    request.META.get('REMOTE_ADDR')
        anonymized_ip = _anonymize_ip(client_ip)
        
        # Augment data with user agent for session tracking
        data_copy = dict(data)
        data_copy['_user_agent'] = request.META.get('HTTP_USER_AGENT', '')
        
        # Dispatch to Celery for async processing
        from .tasks import process_analytics_batch
        process_analytics_batch.delay(
            data=data_copy,
            user_id=user_id,
            client_ip=anonymized_ip,
        )
        
        return Response({
            'status': 'success',
            'message': 'Analytics data queued for processing',
            'counts': {
                'events': len(data.get('events', [])),
                'engagements': len(data.get('engagements', [])),
                'conversions': len(data.get('conversions', [])),
            }
        }, status=status.HTTP_202_ACCEPTED)
        
    except Exception:
        # Log the full traceback server-side; never echo the
        # exception text back to the client (CodeQL
        # py/stack-trace-exposure).
        logger.exception("Analytics view failed")
        return Response({
            'status': 'error',
            'message': 'An internal error occurred'
        }, status=status.HTTP_400_BAD_REQUEST)


def create_analytics_event(event_data, user, client_ip):
    """Create an analytics event"""
    properties = event_data.get('properties', {})
    metadata = event_data.get('metadata', {})
    user_context = event_data.get('user', {})
    
    AnalyticsEvent.objects.create(
        name=event_data.get('name'),
        category=event_data.get('category', 'general'),
        user=user,
        session_id=properties.get('sessionId', ''),
        properties=properties,
        url=properties.get('url', ''),
        path=properties.get('path', ''),
        referrer=event_data.get('referrer', ''),
        user_agent=metadata.get('userAgent', ''),
        ip_address=_anonymize_ip(client_ip),
        language=metadata.get('language', ''),
        platform=metadata.get('platform', ''),
        timestamp=timezone.now()
    )


def create_user_engagement(engagement_data, user):
    """Create a user engagement metric"""
    properties = engagement_data.get('properties', {})
    
    UserEngagement.objects.create(
        user=user,
        session_id=engagement_data.get('sessionId', ''),
        metric=engagement_data.get('metric'),
        value=engagement_data.get('value', 0),
        properties=properties,
        timestamp=timezone.now()
    )


def create_conversion(conversion_data, user):
    """Create a conversion event"""
    properties = conversion_data.get('properties', {})
    
    Conversion.objects.create(
        user=user,
        session_id=conversion_data.get('sessionId', ''),
        name=conversion_data.get('name'),
        value=conversion_data.get('value', 0),
        properties=properties,
        timestamp=timezone.now()
    )


def update_user_session(session_data, user, client_ip, user_agent):
    """Update or create user session"""
    session_id = session_data.get('sessionId')
    
    if not session_id:
        return
    
    session, created = UserSession.objects.get_or_create(
        session_id=session_id,
        defaults={
            'user': user,
            'user_agent': user_agent,
            'ip_address': _anonymize_ip(client_ip),
            'start_time': timezone.now()
        }
    )
    
    # Update session data
    session.page_views = session_data.get('pageViews', 0)
    session.feature_usage = session_data.get('featureUsage', {})
    session.user_journey = session_data.get('userJourney', [])
    
    if session_data.get('duration'):
        session.duration = session_data.get('duration') // 1000  # Convert to seconds
        session.end_time = session.start_time + timedelta(seconds=session.duration)
    
    # Determine engagement
    session.is_engaged = session.duration > 30 or session.page_views > 1
    session.is_bounce = session.page_views <= 1 and session.duration < 30
    
    session.save()


def create_performance_metrics(performance_data, user, session_id):
    """Create performance metrics"""
    api_times = performance_data.get('apiResponseTimes', [])
    for metric in api_times:
        PerformanceMetric.objects.create(
            user=user,
            session_id=session_id,
            metric_type='api_response',
            metric_name=metric.get('endpoint', ''),
            value=metric.get('duration', 0),
            properties={'status': metric.get('status')},
            timestamp=timezone.now()
        )
    
    user_flow_times = performance_data.get('userFlowTimes', [])
    for metric in user_flow_times:
        PerformanceMetric.objects.create(
            user=user,
            session_id=session_id,
            metric_type='user_flow',
            metric_name=metric.get('flow', ''),
            value=metric.get('duration', 0),
            timestamp=timezone.now()
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_analytics_dashboard(request):
    """
    Get analytics dashboard data
    
    GET /api/analytics/dashboard/
    Query params:
        - period: 'day', 'week', 'month', 'year' (default: 'week')
    """
    try:
        period = request.GET.get('period', 'week')
        
        # Calculate date range
        now = timezone.now()
        if period == 'day':
            start_date = now - timedelta(days=1)
        elif period == 'week':
            start_date = now - timedelta(weeks=1)
        elif period == 'month':
            start_date = now - timedelta(days=30)
        elif period == 'year':
            start_date = now - timedelta(days=365)
        else:
            start_date = now - timedelta(weeks=1)
        
        user = request.user
        
        # Get event counts
        events = AnalyticsEvent.objects.filter(
            user=user,
            timestamp__gte=start_date
        )
        
        # Get session stats
        sessions = UserSession.objects.filter(
            user=user,
            start_time__gte=start_date
        )
        
        # Get conversion stats
        conversions = Conversion.objects.filter(
            user=user,
            timestamp__gte=start_date
        )
        
        # Calculate metrics
        dashboard_data = {
            'period': period,
            'date_range': {
                'start': start_date.isoformat(),
                'end': now.isoformat()
            },
            'events': {
                'total': events.count(),
                'by_category': dict(events.values('category').annotate(count=Count('id')).values_list('category', 'count')),
                'top_events': list(events.values('name').annotate(count=Count('id')).order_by('-count')[:10])
            },
            'sessions': {
                'total': sessions.count(),
                'avg_duration': sessions.aggregate(Avg('duration'))['duration__avg'] or 0,
                'engaged_sessions': sessions.filter(is_engaged=True).count(),
                'bounce_rate': (sessions.filter(is_bounce=True).count() / sessions.count() * 100) if sessions.count() > 0 else 0
            },
            'conversions': {
                'total': conversions.count(),
                'total_value': conversions.aggregate(Sum('value'))['value__sum'] or 0,
                'by_type': list(conversions.values('name').annotate(count=Count('id'), value=Sum('value')).order_by('-count')[:10])
            },
            'engagement': {
                'avg_session_duration': sessions.aggregate(Avg('duration'))['duration__avg'] or 0,
                'avg_page_views': sessions.aggregate(Avg('page_views'))['page_views__avg'] or 0,
                'avg_events_per_session': events.count() / sessions.count() if sessions.count() > 0 else 0
            }
        }
        
        return Response(dashboard_data)
        
    except Exception:
        # Log the full traceback server-side; never echo the
        # exception text back to the client (CodeQL
        # py/stack-trace-exposure).
        logger.exception("Analytics view failed")
        return Response({
            'status': 'error',
            'message': 'An internal error occurred'
        }, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_user_journey(request):
    """
    Get user journey data
    
    GET /api/analytics/journey/
    Query params:
        - session_id: specific session ID (optional)
        - limit: number of sessions to return (default: 10)
    """
    try:
        session_id = request.GET.get('session_id')
        limit = int(request.GET.get('limit', 10))
        
        user = request.user
        
        if session_id:
            # Get specific session
            session = UserSession.objects.get(session_id=session_id, user=user)
            return Response({
                'session': {
                    'session_id': session.session_id,
                    'start_time': session.start_time,
                    'duration': session.duration,
                    'page_views': session.page_views,
                    'journey': session.user_journey,
                    'feature_usage': session.feature_usage
                }
            })
        else:
            # Get recent sessions
            sessions = UserSession.objects.filter(user=user).order_by('-start_time')[:limit]
            
            return Response({
                'sessions': [{
                    'session_id': s.session_id,
                    'start_time': s.start_time,
                    'duration': s.duration,
                    'page_views': s.page_views,
                    'is_engaged': s.is_engaged,
                    'feature_usage': s.feature_usage
                } for s in sessions]
            })
        
    except Exception:
        # Log the full traceback server-side; never echo the
        # exception text back to the client (CodeQL
        # py/stack-trace-exposure).
        logger.exception("Analytics view failed")
        return Response({
            'status': 'error',
            'message': 'An internal error occurred'
        }, status=status.HTTP_400_BAD_REQUEST)


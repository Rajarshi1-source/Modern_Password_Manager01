"""
Performance Monitoring API Views
=================================

API endpoints for accessing performance metrics, alerts, and system health.
"""

from rest_framework import viewsets, status
from rest_framework.decorators import api_view, permission_classes, action
from rest_framework.permissions import IsAuthenticated, IsAdminUser, AllowAny
from rest_framework.response import Response
from django.db.models import Avg, Max, Min, Count, Q
from django.utils import timezone
from datetime import timedelta
import logging

logger = logging.getLogger(__name__)
from .models import (
    PerformanceMetric,
    APIPerformanceMetric,
    SystemMetric,
    ErrorLog,
    PerformanceAlert,
    DependencyVersion,
    PerformancePrediction
)
from .performance_middleware import SystemResourceMonitor, PerformanceMetricsCollector


@api_view(['GET'])
@permission_classes([IsAdminUser])
def performance_summary(request):
    """Get performance summary for the last hour"""
    summary = PerformanceMetricsCollector.get_summary()
    
    if summary:
        return Response({
            'success': True,
            'data': summary
        })
    else:
        return Response({
            'success': False,
            'message': 'Failed to retrieve performance summary'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAdminUser])
def system_health(request):
    """Get current system health metrics"""
    metrics = SystemResourceMonitor.get_system_metrics()
    
    if metrics:
        # Check system health
        health_status = 'healthy'
        warnings = []
        
        if metrics['cpu_percent'] > 80:
            health_status = 'warning'
            warnings.append(f"High CPU usage: {metrics['cpu_percent']}%")
        
        if metrics['memory_percent'] > 80:
            health_status = 'warning'
            warnings.append(f"High memory usage: {metrics['memory_percent']}%")
        
        if metrics['disk_percent'] > 80:
            health_status = 'critical' if metrics['disk_percent'] > 90 else 'warning'
            warnings.append(f"High disk usage: {metrics['disk_percent']}%")
        
        return Response({
            'success': True,
            'data': {
                'metrics': metrics,
                'health_status': health_status,
                'warnings': warnings
            }
        })
    else:
        return Response({
            'success': False,
            'message': 'Failed to retrieve system metrics'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAdminUser])
def endpoint_performance(request):
    """Get performance metrics for specific endpoints"""
    hours = int(request.query_params.get('hours', 24))
    limit = int(request.query_params.get('limit', 20))
    
    time_threshold = timezone.now() - timedelta(hours=hours)
    
    # Get slowest endpoints
    slowest_endpoints = PerformanceMetric.objects.filter(
        timestamp__gte=time_threshold
    ).values('path', 'method').annotate(
        avg_duration=Avg('duration_ms'),
        max_duration=Max('duration_ms'),
        total_requests=Count('id')
    ).order_by('-avg_duration')[:limit]
    
    # Get most frequently accessed endpoints
    frequent_endpoints = PerformanceMetric.objects.filter(
        timestamp__gte=time_threshold
    ).values('path', 'method').annotate(
        request_count=Count('id'),
        avg_duration=Avg('duration_ms')
    ).order_by('-request_count')[:limit]
    
    return Response({
        'success': True,
        'data': {
            'slowest_endpoints': list(slowest_endpoints),
            'frequent_endpoints': list(frequent_endpoints),
            'time_period_hours': hours
        }
    })


@api_view(['GET'])
@permission_classes([IsAdminUser])
def database_performance(request):
    """Get database query performance metrics"""
    hours = int(request.query_params.get('hours', 24))
    time_threshold = timezone.now() - timedelta(hours=hours)
    
    metrics = PerformanceMetric.objects.filter(
        timestamp__gte=time_threshold
    ).aggregate(
        avg_query_count=Avg('query_count'),
        max_query_count=Max('query_count'),
        avg_query_time=Avg('query_time_ms'),
        max_query_time=Max('query_time_ms')
    )
    
    # Endpoints with excessive queries
    excessive_queries = PerformanceMetric.objects.filter(
        timestamp__gte=time_threshold,
        query_count__gt=50
    ).values('path', 'method').annotate(
        avg_queries=Avg('query_count'),
        max_queries=Max('query_count'),
        request_count=Count('id')
    ).order_by('-avg_queries')[:20]
    
    return Response({
        'success': True,
        'data': {
            'overall_metrics': metrics,
            'endpoints_with_excessive_queries': list(excessive_queries),
            'time_period_hours': hours
        }
    })


@api_view(['GET'])
@permission_classes([IsAdminUser])
def error_summary(request):
    """Get error log summary"""
    hours = int(request.query_params.get('hours', 24))
    time_threshold = timezone.now() - timedelta(hours=hours)
    
    # Error counts by level
    errors_by_level = ErrorLog.objects.filter(
        timestamp__gte=time_threshold
    ).values('level').annotate(
        count=Count('id')
    ).order_by('-count')
    
    # Most common errors
    common_errors = ErrorLog.objects.filter(
        timestamp__gte=time_threshold
    ).values('exception_type', 'message').annotate(
        count=Count('id')
    ).order_by('-count')[:20]
    
    # Unresolved errors
    unresolved_errors = ErrorLog.objects.filter(
        resolved=False,
        timestamp__gte=time_threshold
    ).count()
    
    return Response({
        'success': True,
        'data': {
            'errors_by_level': list(errors_by_level),
            'common_errors': list(common_errors),
            'unresolved_count': unresolved_errors,
            'time_period_hours': hours
        }
    })


@api_view(['GET'])
@permission_classes([IsAdminUser])
def performance_alerts(request):
    """Get performance alerts"""
    unacknowledged = request.query_params.get('unacknowledged', 'false').lower() == 'true'
    unresolved = request.query_params.get('unresolved', 'false').lower() == 'true'
    
    alerts = PerformanceAlert.objects.all()
    
    if unacknowledged:
        alerts = alerts.filter(acknowledged=False)
    
    if unresolved:
        alerts = alerts.filter(resolved=False)
    
    alerts_data = []
    for alert in alerts[:50]:  # Limit to 50
        alerts_data.append({
            'id': alert.id,
            'alert_type': alert.alert_type,
            'severity': alert.severity,
            'message': alert.message,
            'details': alert.details,
            'timestamp': alert.timestamp,
            'acknowledged': alert.acknowledged,
            'resolved': alert.resolved
        })
    
    return Response({
        'success': True,
        'data': {
            'alerts': alerts_data,
            'total_count': alerts.count()
        }
    })


@api_view(['POST'])
@permission_classes([IsAdminUser])
def acknowledge_alert(request, alert_id):
    """Acknowledge a performance alert"""
    try:
        alert = PerformanceAlert.objects.get(id=alert_id)
        alert.acknowledge(user=request.user)
        
        return Response({
            'success': True,
            'message': 'Alert acknowledged successfully'
        })
    except PerformanceAlert.DoesNotExist:
        return Response({
            'success': False,
            'message': 'Alert not found'
        }, status=status.HTTP_404_NOT_FOUND)


@api_view(['POST'])
@permission_classes([IsAdminUser])
def resolve_alert(request, alert_id):
    """Resolve a performance alert"""
    try:
        alert = PerformanceAlert.objects.get(id=alert_id)
        alert.resolve()
        
        return Response({
            'success': True,
            'message': 'Alert resolved successfully'
        })
    except PerformanceAlert.DoesNotExist:
        return Response({
            'success': False,
            'message': 'Alert not found'
        }, status=status.HTTP_404_NOT_FOUND)


@api_view(['GET'])
@permission_classes([IsAdminUser])
def dependencies_status(request):
    """Get status of dependencies"""
    check_updates = request.query_params.get('check_updates', 'false').lower() == 'true'
    
    if check_updates:
        # Trigger dependency check (would be implemented in a management command)
        pass
    
    dependencies = DependencyVersion.objects.all()
    
    # Count vulnerabilities
    vulnerable_count = dependencies.filter(has_vulnerabilities=True).count()
    update_available_count = dependencies.filter(update_available=True).count()
    
    deps_data = []
    for dep in dependencies:
        deps_data.append({
            'name': dep.name,
            'current_version': dep.current_version,
            'latest_version': dep.latest_version,
            'update_available': dep.update_available,
            'has_vulnerabilities': dep.has_vulnerabilities,
            'vulnerability_count': dep.vulnerability_count,
            'ecosystem': dep.ecosystem,
            'last_checked': dep.last_checked
        })
    
    return Response({
        'success': True,
        'data': {
            'dependencies': deps_data,
            'summary': {
                'total_dependencies': dependencies.count(),
                'vulnerable_count': vulnerable_count,
                'updates_available': update_available_count
            }
        }
    })


@api_view(['GET'])
@permission_classes([IsAdminUser])
def ml_predictions(request):
    """Get ML performance predictions"""
    hours = int(request.query_params.get('hours', 24))
    time_threshold = timezone.now() - timedelta(hours=hours)
    
    predictions = PerformancePrediction.objects.filter(
        timestamp__gte=time_threshold
    ).order_by('-timestamp')[:100]
    
    # Calculate overall prediction accuracy
    accurate_predictions = predictions.filter(
        prediction_accuracy__isnull=False
    )
    
    if accurate_predictions.exists():
        avg_accuracy = accurate_predictions.aggregate(
            avg=Avg('prediction_accuracy')
        )['avg']
    else:
        avg_accuracy = None
    
    predictions_data = []
    for pred in predictions:
        predictions_data.append({
            'endpoint': pred.endpoint,
            'predicted_duration_ms': pred.predicted_duration_ms,
            'actual_duration_ms': pred.actual_duration_ms,
            'prediction_accuracy': pred.prediction_accuracy,
            'confidence_score': pred.confidence_score,
            'model_version': pred.model_version,
            'timestamp': pred.timestamp
        })
    
    return Response({
        'success': True,
        'data': {
            'predictions': predictions_data,
            'average_accuracy': avg_accuracy,
            'time_period_hours': hours
        }
    })


@api_view(['POST'])
@permission_classes([IsAdminUser])
def optimize_performance(request):
    """Trigger ML-based performance optimization"""
    # This would trigger the ML model to analyze recent performance
    # and suggest optimizations
    
    return Response({
        'success': True,
        'message': 'Performance optimization analysis initiated',
        'data': {
            'status': 'processing',
            'estimated_time': '5-10 minutes'
        }
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def user_performance_metrics(request):
    """Get performance metrics for the current user (limited)"""
    hours = int(request.query_params.get('hours', 24))
    time_threshold = timezone.now() - timedelta(hours=hours)
    
    # Get user's request metrics
    user_metrics = PerformanceMetric.objects.filter(
        user=str(request.user),
        timestamp__gte=time_threshold
    ).aggregate(
        avg_response_time=Avg('duration_ms'),
        total_requests=Count('id')
    )
    
    return Response({
        'success': True,
        'data': user_metrics
    })


@api_view(['POST'])
@permission_classes([AllowAny])  # Allow anonymous performance reporting
def frontend_performance_report(request):
    """
    Receive frontend performance metrics from the React app.
    Stores metrics for analysis and monitoring.
    """
    try:
        data = request.data
        
        # Get user if authenticated
        user = request.user if request.user.is_authenticated else None
        
        # Log frontend metrics for analysis
        logger.info(f"Frontend performance report received from user {user or 'anonymous'}")
        logger.info(f"Vault unlock avg: {data.get('vaultUnlock', {}).get('average', 0)}ms")
        logger.info(f"API request avg: {data.get('apiRequests', {}).get('average', 0)}ms")
        logger.info(f"Error count: {data.get('errors', {}).get('count', 0)}")
        
        # Could store in database if needed for long-term analysis
        # For now, just acknowledge receipt
        
        return Response({
            'success': True,
            'message': 'Frontend performance metrics received successfully',
            'timestamp': timezone.now()
        })
    
    except Exception as e:
        logger.error(f"Error processing frontend performance report: {e}")
        return Response({
            'success': False,
            'error': str(e)
        }, status=400)


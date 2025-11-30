from django.http import JsonResponse
from django.db import connection
from django.core.cache import cache
from django.utils import timezone
from django.conf import settings
import logging

logger = logging.getLogger(__name__)

def health_check(request):
    """
    Health check endpoint for monitoring system status
    """
    health_status = {
        'status': 'healthy',
        'timestamp': timezone.now().isoformat(),
        'version': getattr(settings, 'VERSION', '1.0.0'),
        'checks': {}
    }
    
    # Check database connectivity
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
        health_status['checks']['database'] = 'connected'
    except Exception as e:
        health_status['checks']['database'] = f'error: {str(e)}'
        health_status['status'] = 'unhealthy'
        logger.error(f"Database health check failed: {e}")
    
    # Check cache connectivity
    try:
        cache_key = 'health_check_test'
        cache.set(cache_key, 'test', 10)
        cached_value = cache.get(cache_key)
        if cached_value == 'test':
            health_status['checks']['cache'] = 'connected'
            cache.delete(cache_key)
        else:
            health_status['checks']['cache'] = 'error: cache not working'
            health_status['status'] = 'unhealthy'
    except Exception as e:
        health_status['checks']['cache'] = f'error: {str(e)}'
        health_status['status'] = 'unhealthy'
        logger.error(f"Cache health check failed: {e}")
    
    # Check if we're in debug mode (security check)
    health_status['checks']['debug_mode'] = settings.DEBUG
    if settings.DEBUG and not settings.DEVELOPMENT:
        health_status['checks']['security_warning'] = 'DEBUG is enabled in production'
        logger.warning("DEBUG mode is enabled in production environment")
    
    # Return appropriate HTTP status code
    status_code = 200 if health_status['status'] == 'healthy' else 503
    
    return JsonResponse(health_status, status=status_code)

def readiness_check(request):
    """
    Readiness check endpoint for deployment health
    """
    try:
        # Perform more thorough checks for readiness
        with connection.cursor() as cursor:
            # Check if migrations are applied
            cursor.execute("SELECT COUNT(*) FROM django_migrations")
            migration_count = cursor.fetchone()[0]
            
        if migration_count > 0:
            return JsonResponse({
                'status': 'ready',
                'timestamp': timezone.now().isoformat(),
                'migrations_applied': migration_count
            })
        else:
            return JsonResponse({
                'status': 'not_ready',
                'error': 'No migrations found',
                'timestamp': timezone.now().isoformat()
            }, status=503)
            
    except Exception as e:
        logger.error(f"Readiness check failed: {e}")
        return JsonResponse({
            'status': 'not_ready',
            'error': str(e),
            'timestamp': timezone.now().isoformat()
        }, status=503)

def liveness_check(request):
    """
    Liveness check endpoint for container health
    """
    return JsonResponse({
        'status': 'alive',
        'timestamp': timezone.now().isoformat(),
        'uptime': 'running'
    })

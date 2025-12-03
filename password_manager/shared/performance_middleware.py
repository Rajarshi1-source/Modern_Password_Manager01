"""
Performance Monitoring Middleware
==================================

ASGI-Compatible middleware that tracks and logs performance metrics for all requests,
database queries, and system resources.

Version: 2.0.0 (ASGI-compatible)
"""

import time
import logging
import traceback
from django.db import connection
from django.conf import settings
from django.utils import timezone
from asgiref.sync import iscoroutinefunction, markcoroutinefunction, sync_to_async

logger = logging.getLogger('performance')

# Try to import psutil
try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False
    logger.warning("psutil not available - system metrics will be limited")


class PerformanceMonitoringMiddleware:
    """
    Middleware to track request/response performance metrics.
    ASGI/async compatible.
    """
    
    async_capable = True
    sync_capable = True
    
    def __init__(self, get_response):
        self.get_response = get_response
        if iscoroutinefunction(self.get_response):
            markcoroutinefunction(self)
    
    def __call__(self, request):
        if iscoroutinefunction(self.get_response):
            return self.__acall__(request)
        return self._process_sync(request)
    
    async def __acall__(self, request):
        """Async request handler"""
        self._process_request(request)
        response = await self.get_response(request)
        return self._process_response(request, response)
    
    def _process_sync(self, request):
        """Sync request handler"""
        self._process_request(request)
        response = self.get_response(request)
        return self._process_response(request, response)
    
    def _process_request(self, request):
        """Store request start time"""
        request._performance_start_time = time.time()
        request._performance_query_count = len(connection.queries)
        
        # Track memory usage at request start
        if PSUTIL_AVAILABLE:
            try:
                process = psutil.Process()
                request._performance_memory_start = process.memory_info().rss / 1024 / 1024  # MB
            except Exception:
                request._performance_memory_start = 0
        else:
            request._performance_memory_start = 0
    
    def _process_response(self, request, response):
        """Calculate and log performance metrics"""
        
        # Calculate request duration
        if hasattr(request, '_performance_start_time'):
            duration = time.time() - request._performance_start_time
            
            # Calculate database queries
            query_count = len(connection.queries) - getattr(request, '_performance_query_count', 0)
            
            # Calculate memory usage
            memory_used = 0
            if PSUTIL_AVAILABLE:
                try:
                    process = psutil.Process()
                    memory_end = process.memory_info().rss / 1024 / 1024  # MB
                    memory_used = memory_end - getattr(request, '_performance_memory_start', 0)
                except Exception:
                    pass
            
            # Get query times
            query_time = sum(
                float(q['time']) 
                for q in connection.queries[getattr(request, '_performance_query_count', 0):]
            )
            
            # Log performance metrics
            log_data = {
                'path': request.path,
                'method': request.method,
                'duration_ms': round(duration * 1000, 2),
                'status_code': response.status_code,
                'query_count': query_count,
                'query_time_ms': round(query_time * 1000, 2),
                'memory_mb': round(memory_used, 2),
                'timestamp': timezone.now().isoformat(),
                'user': str(request.user) if hasattr(request, 'user') and request.user.is_authenticated else 'anonymous'
            }
            
            # Add to response headers (for debugging)
            if settings.DEBUG:
                response['X-Request-Duration'] = f"{log_data['duration_ms']}ms"
                response['X-Query-Count'] = str(query_count)
                response['X-Query-Time'] = f"{log_data['query_time_ms']}ms"
            
            # Log performance data
            logger.info(f"Performance: {log_data}")
            
            # Store in database if enabled (run synchronously to avoid issues)
            if getattr(settings, 'STORE_PERFORMANCE_METRICS', False):
                try:
                    from .models import PerformanceMetric
                    PerformanceMetric.objects.create(**log_data)
                except Exception as e:
                    logger.error(f"Failed to store performance metric: {e}")
            
            # Warn about slow requests
            if duration > getattr(settings, 'SLOW_REQUEST_THRESHOLD', 1.0):
                logger.warning(
                    f"SLOW REQUEST: {request.method} {request.path} "
                    f"took {duration:.2f}s with {query_count} queries"
                )
            
            # Warn about excessive queries
            if query_count > getattr(settings, 'QUERY_COUNT_THRESHOLD', 50):
                logger.warning(
                    f"EXCESSIVE QUERIES: {request.method} {request.path} "
                    f"executed {query_count} queries"
                )
        
        return response


class DatabaseQueryMonitoringMiddleware:
    """
    Middleware specifically for detailed database query monitoring.
    ASGI/async compatible.
    """
    
    async_capable = True
    sync_capable = True
    
    def __init__(self, get_response):
        self.get_response = get_response
        if iscoroutinefunction(self.get_response):
            markcoroutinefunction(self)
    
    def __call__(self, request):
        if iscoroutinefunction(self.get_response):
            return self.__acall__(request)
        return self._process_sync(request)
    
    async def __acall__(self, request):
        """Async request handler"""
        request._db_queries = []
        response = await self.get_response(request)
        return self._process_response(request, response)
    
    def _process_sync(self, request):
        """Sync request handler"""
        request._db_queries = []
        response = self.get_response(request)
        return self._process_response(request, response)
    
    def _process_response(self, request, response):
        """Analyze database queries"""
        if settings.DEBUG and hasattr(request, '_db_queries'):
            # Analyze queries for N+1 problems
            query_list = connection.queries
            
            # Group similar queries
            query_patterns = {}
            for query in query_list:
                sql = query.get('sql', '')
                # Simplify query by removing specific values
                pattern = self._normalize_query(sql)
                
                if pattern not in query_patterns:
                    query_patterns[pattern] = []
                query_patterns[pattern].append(query)
            
            # Detect N+1 queries
            for pattern, queries in query_patterns.items():
                if len(queries) > 5:  # More than 5 similar queries
                    logger.warning(
                        f"Potential N+1 query problem: "
                        f"{len(queries)} similar queries in {request.path}"
                    )
        
        return response
    
    @staticmethod
    def _normalize_query(sql):
        """Normalize SQL query for pattern matching"""
        import re
        # Replace specific values with placeholders
        normalized = re.sub(r'\d+', 'N', sql)
        normalized = re.sub(r"'[^']*'", "'?'", normalized)
        normalized = re.sub(r'"[^"]*"', '"?"', normalized)
        return normalized


class APIPerformanceMiddleware:
    """
    Middleware for tracking API endpoint performance specifically.
    ASGI/async compatible.
    """
    
    async_capable = True
    sync_capable = True
    
    def __init__(self, get_response):
        self.get_response = get_response
        if iscoroutinefunction(self.get_response):
            markcoroutinefunction(self)
    
    def __call__(self, request):
        if iscoroutinefunction(self.get_response):
            return self.__acall__(request)
        return self._process_sync(request)
    
    async def __acall__(self, request):
        """Async request handler"""
        self._process_request(request)
        response = await self.get_response(request)
        return self._process_response(request, response)
    
    def _process_sync(self, request):
        """Sync request handler"""
        self._process_request(request)
        response = self.get_response(request)
        return self._process_response(request, response)
    
    def _process_request(self, request):
        """Track API request start"""
        if request.path.startswith('/api/'):
            request._api_start = time.time()
            request._api_endpoint = request.path
    
    def _process_response(self, request, response):
        """Log API performance metrics"""
        if hasattr(request, '_api_start'):
            duration = time.time() - request._api_start
            
            # Log API metrics
            api_log = {
                'endpoint': request._api_endpoint,
                'method': request.method,
                'duration_ms': round(duration * 1000, 2),
                'status': response.status_code,
                'timestamp': timezone.now().isoformat()
            }
            
            logger.info(f"API Performance: {api_log}")
            
            # Store API metrics separately if enabled
            if getattr(settings, 'STORE_API_METRICS', False):
                try:
                    from .models import APIPerformanceMetric
                    APIPerformanceMetric.objects.create(**api_log)
                except Exception as e:
                    logger.error(f"Failed to store API metric: {e}")
        
        return response


class CachePerformanceMiddleware:
    """
    Middleware for tracking cache hit/miss rates.
    ASGI/async compatible.
    """
    
    async_capable = True
    sync_capable = True
    
    def __init__(self, get_response):
        self.get_response = get_response
        if iscoroutinefunction(self.get_response):
            markcoroutinefunction(self)
    
    def __call__(self, request):
        if iscoroutinefunction(self.get_response):
            return self.__acall__(request)
        return self._process_sync(request)
    
    async def __acall__(self, request):
        """Async request handler"""
        request._cache_hits = 0
        request._cache_misses = 0
        response = await self.get_response(request)
        return self._process_response(request, response)
    
    def _process_sync(self, request):
        """Sync request handler"""
        request._cache_hits = 0
        request._cache_misses = 0
        response = self.get_response(request)
        return self._process_response(request, response)
    
    def _process_response(self, request, response):
        """Log cache performance"""
        if hasattr(request, '_cache_hits') and hasattr(request, '_cache_misses'):
            total = request._cache_hits + request._cache_misses
            if total > 0:
                hit_rate = (request._cache_hits / total) * 100
                
                logger.info(
                    f"Cache Performance for {request.path}: "
                    f"{hit_rate:.1f}% hit rate "
                    f"({request._cache_hits} hits, {request._cache_misses} misses)"
                )
        
        return response


class SystemResourceMonitor:
    """
    Monitor system resources (CPU, Memory, Disk)
    """
    
    @staticmethod
    def get_system_metrics():
        """Get current system resource metrics"""
        if not PSUTIL_AVAILABLE:
            return {
                'error': 'psutil not available',
                'timestamp': timezone.now().isoformat()
            }
        
        try:
            cpu_percent = psutil.cpu_percent(interval=0.1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            
            return {
                'cpu_percent': cpu_percent,
                'memory_percent': memory.percent,
                'memory_available_mb': memory.available / 1024 / 1024,
                'disk_percent': disk.percent,
                'disk_free_gb': disk.free / 1024 / 1024 / 1024,
                'timestamp': timezone.now().isoformat()
            }
        except Exception as e:
            logger.error(f"Failed to get system metrics: {e}")
            return None
    
    @staticmethod
    def log_system_metrics():
        """Log current system metrics"""
        metrics = SystemResourceMonitor.get_system_metrics()
        if metrics:
            logger.info(f"System Metrics: {metrics}")
            
            # Warn if resources are low
            if metrics.get('cpu_percent', 0) > 80:
                logger.warning(f"High CPU usage: {metrics['cpu_percent']}%")
            
            if metrics.get('memory_percent', 0) > 80:
                logger.warning(f"High memory usage: {metrics['memory_percent']}%")
            
            if metrics.get('disk_percent', 0) > 80:
                logger.warning(f"High disk usage: {metrics['disk_percent']}%")
        
        return metrics


class PerformanceMetricsCollector:
    """
    Centralized collector for all performance metrics
    """
    
    @staticmethod
    def get_summary():
        """Get performance summary"""
        try:
            from .models import PerformanceMetric, APIPerformanceMetric
            from django.db.models import Avg, Max, Min, Count
            from datetime import timedelta
            from django.utils import timezone
            
            # Last hour metrics
            hour_ago = timezone.now() - timedelta(hours=1)
            
            request_metrics = PerformanceMetric.objects.filter(
                timestamp__gte=hour_ago
            ).aggregate(
                avg_duration=Avg('duration_ms'),
                max_duration=Max('duration_ms'),
                min_duration=Min('duration_ms'),
                total_requests=Count('id'),
                avg_queries=Avg('query_count')
            )
            
            api_metrics = APIPerformanceMetric.objects.filter(
                timestamp__gte=hour_ago
            ).aggregate(
                avg_duration=Avg('duration_ms'),
                max_duration=Max('duration_ms'),
                total_api_calls=Count('id')
            )
            
            system_metrics = SystemResourceMonitor.get_system_metrics()
            
            return {
                'request_metrics': request_metrics,
                'api_metrics': api_metrics,
                'system_metrics': system_metrics,
                'timestamp': timezone.now().isoformat()
            }
        except Exception as e:
            logger.error(f"Failed to get performance summary: {e}")
            return None

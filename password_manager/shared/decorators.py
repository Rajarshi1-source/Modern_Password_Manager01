"""
Custom decorators for the Password Manager application.

This module contains decorators for common functionality like
security checks, caching, logging, and API enhancements.
"""

import functools
import time
import logging
from datetime import datetime, timedelta
from django.core.cache import cache
from django.http import JsonResponse
from django.conf import settings
from django.utils import timezone
from django.contrib.auth.decorators import user_passes_test
from rest_framework.response import Response
from rest_framework import status
from .constants import CACHE_TIMEOUTS
from .utils import get_client_ip, cache_key_for_user

logger = logging.getLogger(__name__)


def require_master_password(view_func):
    """
    Decorator to require master password verification for sensitive operations.
    
    Args:
        view_func: View function to wrap
        
    Returns:
        Wrapped view function
    """
    @functools.wraps(view_func)
    def wrapper(request, *args, **kwargs):
        # Check if master password has been verified recently
        if request.user.is_authenticated:
            cache_key = cache_key_for_user(request.user.id, 'master_verified')
            if cache.get(cache_key):
                return view_func(request, *args, **kwargs)
        
        return JsonResponse({
            'error': 'Master password verification required',
            'code': 'master_password_required'
        }, status=401)
    
    return wrapper


def security_headers(view_func):
    """
    Decorator to add security headers to response.
    
    Args:
        view_func: View function to wrap
        
    Returns:
        Wrapped view function
    """
    @functools.wraps(view_func)
    def wrapper(request, *args, **kwargs):
        response = view_func(request, *args, **kwargs)
        
        # Add security headers
        response['X-Content-Type-Options'] = 'nosniff'
        response['X-Frame-Options'] = 'DENY'
        response['X-XSS-Protection'] = '1; mode=block'
        response['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        
        # Add cache control for sensitive endpoints
        if request.path.startswith('/api/'):
            response['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
            response['Pragma'] = 'no-cache'
        
        return response
    
    return wrapper


def rate_limit(max_requests=10, period=60, key_func=None):
    """
    Simple rate limiting decorator.
    
    Args:
        max_requests (int): Maximum requests allowed
        period (int): Time period in seconds
        key_func (callable): Function to generate cache key
        
    Returns:
        Decorator function
    """
    def decorator(view_func):
        @functools.wraps(view_func)
        def wrapper(request, *args, **kwargs):
            # Generate cache key
            if key_func:
                cache_key = key_func(request)
            else:
                ip = get_client_ip(request)
                cache_key = f"rate_limit:{view_func.__name__}:{ip}"
            
            # Get current request count
            current_requests = cache.get(cache_key, 0)
            
            if current_requests >= max_requests:
                return JsonResponse({
                    'error': 'Rate limit exceeded',
                    'code': 'rate_limited',
                    'retry_after': period
                }, status=429)
            
            # Increment counter
            cache.set(cache_key, current_requests + 1, period)
            
            return view_func(request, *args, **kwargs)
        
        return wrapper
    return decorator


def log_api_call(log_level=logging.INFO):
    """
    Decorator to log API calls.
    
    Args:
        log_level: Logging level to use
        
    Returns:
        Decorator function
    """
    def decorator(view_func):
        @functools.wraps(view_func)
        def wrapper(request, *args, **kwargs):
            start_time = time.time()
            ip = get_client_ip(request)
            
            # Log request
            logger.log(log_level, f"API Call: {request.method} {request.path} from {ip}")
            
            try:
                response = view_func(request, *args, **kwargs)
                
                # Log response
                duration = (time.time() - start_time) * 1000
                status_code = getattr(response, 'status_code', 200)
                logger.log(log_level, 
                    f"API Response: {status_code} for {request.method} {request.path} "
                    f"({duration:.2f}ms)")
                
                return response
                
            except Exception as e:
                duration = (time.time() - start_time) * 1000
                logger.error(
                    f"API Error: {request.method} {request.path} from {ip} "
                    f"({duration:.2f}ms) - {str(e)}"
                )
                raise
        
        return wrapper
    return decorator


def cache_response(timeout=CACHE_TIMEOUTS['MEDIUM'], key_func=None, user_specific=False):
    """
    Decorator to cache view responses.
    
    Args:
        timeout (int): Cache timeout in seconds
        key_func (callable): Function to generate cache key
        user_specific (bool): Whether to make cache user-specific
        
    Returns:
        Decorator function
    """
    def decorator(view_func):
        @functools.wraps(view_func)
        def wrapper(request, *args, **kwargs):
            # Generate cache key
            if key_func:
                cache_key = key_func(request, *args, **kwargs)
            else:
                cache_key = f"view_cache:{view_func.__name__}:{request.path}"
                if user_specific and request.user.is_authenticated:
                    cache_key = cache_key_for_user(request.user.id, cache_key)
                
                # Include query parameters in cache key
                if request.GET:
                    query_string = request.GET.urlencode()
                    cache_key = f"{cache_key}:{hash(query_string)}"
            
            # Try to get cached response
            cached_response = cache.get(cache_key)
            if cached_response is not None:
                logger.debug(f"Cache hit for {cache_key}")
                return cached_response
            
            # Generate response and cache it
            response = view_func(request, *args, **kwargs)
            
            # Only cache successful responses
            if hasattr(response, 'status_code') and response.status_code == 200:
                cache.set(cache_key, response, timeout)
                logger.debug(f"Cached response for {cache_key}")
            
            return response
        
        return wrapper
    return decorator


def require_device_verification(view_func):
    """
    Decorator to require device verification for sensitive operations.
    
    Args:
        view_func: View function to wrap
        
    Returns:
        Wrapped view function
    """
    @functools.wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse({
                'error': 'Authentication required',
                'code': 'authentication_required'
            }, status=401)
        
        # Check if device is verified
        device_fingerprint = request.headers.get('X-Device-Fingerprint')
        if device_fingerprint:
            cache_key = cache_key_for_user(
                request.user.id, 
                f'device_verified:{device_fingerprint}'
            )
            if cache.get(cache_key):
                return view_func(request, *args, **kwargs)
        
        return JsonResponse({
            'error': 'Device verification required',
            'code': 'device_verification_required'
        }, status=403)
    
    return wrapper


def require_2fa(view_func):
    """
    Decorator to require 2FA verification for sensitive operations.
    
    Args:
        view_func: View function to wrap
        
    Returns:
        Wrapped view function
    """
    @functools.wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse({
                'error': 'Authentication required',
                'code': 'authentication_required'
            }, status=401)
        
        # Check if 2FA has been verified recently
        cache_key = cache_key_for_user(request.user.id, '2fa_verified')
        if cache.get(cache_key):
            return view_func(request, *args, **kwargs)
        
        return JsonResponse({
            'error': '2FA verification required',
            'code': '2fa_required'
        }, status=403)
    
    return wrapper


def handle_exceptions(default_message="An error occurred"):
    """
    Decorator to handle exceptions and return standardized error responses.
    
    Args:
        default_message (str): Default error message
        
    Returns:
        Decorator function
    """
    def decorator(view_func):
        @functools.wraps(view_func)
        def wrapper(request, *args, **kwargs):
            try:
                return view_func(request, *args, **kwargs)
            except ValueError as e:
                logger.warning(f"ValueError in {view_func.__name__}: {str(e)}")
                return JsonResponse({
                    'error': str(e),
                    'code': 'validation_error'
                }, status=400)
            except PermissionError as e:
                logger.warning(f"PermissionError in {view_func.__name__}: {str(e)}")
                return JsonResponse({
                    'error': 'Permission denied',
                    'code': 'permission_denied'
                }, status=403)
            except Exception as e:
                logger.error(f"Unexpected error in {view_func.__name__}: {str(e)}")
                return JsonResponse({
                    'error': default_message,
                    'code': 'server_error'
                }, status=500)
        
        return wrapper
    return decorator


def validate_json_request(required_fields=None):
    """
    Decorator to validate JSON request data.
    
    Args:
        required_fields (list): List of required field names
        
    Returns:
        Decorator function
    """
    def decorator(view_func):
        @functools.wraps(view_func)
        def wrapper(request, *args, **kwargs):
            # Check content type
            if request.content_type != 'application/json':
                return JsonResponse({
                    'error': 'Content-Type must be application/json',
                    'code': 'invalid_content_type'
                }, status=400)
            
            # Parse JSON
            try:
                import json
                data = json.loads(request.body)
                request.json = data
            except json.JSONDecodeError:
                return JsonResponse({
                    'error': 'Invalid JSON data',
                    'code': 'invalid_json'
                }, status=400)
            
            # Validate required fields
            if required_fields:
                missing_fields = [
                    field for field in required_fields 
                    if field not in data
                ]
                if missing_fields:
                    return JsonResponse({
                        'error': f'Missing required fields: {", ".join(missing_fields)}',
                        'code': 'missing_fields'
                    }, status=400)
            
            return view_func(request, *args, **kwargs)
        
        return wrapper
    return decorator


def timing_decorator(view_func):
    """
    Decorator to measure and log view execution time.
    
    Args:
        view_func: View function to wrap
        
    Returns:
        Wrapped view function
    """
    @functools.wraps(view_func)
    def wrapper(request, *args, **kwargs):
        start_time = time.time()
        
        response = view_func(request, *args, **kwargs)
        
        end_time = time.time()
        duration = (end_time - start_time) * 1000  # Convert to milliseconds
        
        logger.info(f"View {view_func.__name__} executed in {duration:.2f}ms")
        
        # Add timing header to response
        if hasattr(response, '__setitem__'):
            response['X-Response-Time'] = f"{duration:.2f}ms"
        
        return response
    
    return wrapper

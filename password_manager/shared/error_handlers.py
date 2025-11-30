"""
Centralized Error Handlers
===========================

Global error handling, logging, and reporting for Django application.

Features:
- Custom exception handlers
- Error logging and tracking
- User-friendly error responses
- Error notification system
- Error grouping and deduplication

Author: Password Manager Team
Date: October 2025
"""

import logging
import traceback
import sys
from datetime import datetime
from django.http import JsonResponse
from django.core.exceptions import (
    ValidationError,
    PermissionDenied,
    ObjectDoesNotExist
)
from django.db import DatabaseError
from rest_framework.views import exception_handler as drf_exception_handler
from rest_framework import status
from rest_framework.exceptions import (
    APIException,
    AuthenticationFailed,
    NotAuthenticated,
    MethodNotAllowed,
    NotFound,
    Throttled
)

logger = logging.getLogger(__name__)


# ==============================================================================
# CUSTOM EXCEPTION CLASSES
# ==============================================================================

class ApplicationError(Exception):
    """Base application error"""
    def __init__(self, message, code='app_error', status_code=500, details=None):
        self.message = message
        self.code = code
        self.status_code = status_code
        self.details = details or {}
        super().__init__(self.message)


class BusinessLogicError(ApplicationError):
    """Error in business logic"""
    def __init__(self, message, details=None):
        super().__init__(message, 'business_logic_error', 400, details)


class ResourceNotFoundError(ApplicationError):
    """Resource not found error"""
    def __init__(self, resource_type, resource_id=None):
        message = f"{resource_type} not found"
        if resource_id:
            message += f" (ID: {resource_id})"
        super().__init__(message, 'resource_not_found', 404)


class UnauthorizedError(ApplicationError):
    """Unauthorized access error"""
    def __init__(self, message="Unauthorized access"):
        super().__init__(message, 'unauthorized', 401)


class ForbiddenError(ApplicationError):
    """Forbidden access error"""
    def __init__(self, message="Access forbidden"):
        super().__init__(message, 'forbidden', 403)


class ValidationErrorCustom(ApplicationError):
    """Validation error"""
    def __init__(self, field, message, details=None):
        super().__init__(
            message,
            'validation_error',
            400,
            {'field': field, **(details or {})}
        )


class RateLimitError(ApplicationError):
    """Rate limit exceeded error"""
    def __init__(self, retry_after=None):
        message = "Too many requests. Please try again later."
        details = {'retry_after': retry_after} if retry_after else {}
        super().__init__(message, 'rate_limit_exceeded', 429, details)


# ==============================================================================
# ERROR HANDLER MIDDLEWARE
# ==============================================================================

class ErrorHandlerMiddleware:
    """
    Middleware to catch and handle all unhandled exceptions
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        response = self.get_response(request)
        return response
    
    def process_exception(self, request, exception):
        """Handle exceptions that occur during request processing"""
        
        # Log the exception
        log_error(exception, request)
        
        # Handle different exception types
        if isinstance(exception, ApplicationError):
            return self._handle_application_error(exception)
        elif isinstance(exception, ValidationError):
            return self._handle_validation_error(exception)
        elif isinstance(exception, PermissionDenied):
            return self._handle_permission_denied(exception)
        elif isinstance(exception, ObjectDoesNotExist):
            return self._handle_not_found(exception)
        elif isinstance(exception, DatabaseError):
            return self._handle_database_error(exception)
        else:
            return self._handle_generic_error(exception)
    
    def _handle_application_error(self, exception):
        """Handle custom application errors"""
        return JsonResponse({
            'success': False,
            'error': exception.message,
            'code': exception.code,
            'details': exception.details
        }, status=exception.status_code)
    
    def _handle_validation_error(self, exception):
        """Handle Django validation errors"""
        return JsonResponse({
            'success': False,
            'error': 'Validation failed',
            'code': 'validation_error',
            'details': {'errors': exception.message_dict if hasattr(exception, 'message_dict') else str(exception)}
        }, status=400)
    
    def _handle_permission_denied(self, exception):
        """Handle permission denied errors"""
        return JsonResponse({
            'success': False,
            'error': 'Permission denied',
            'code': 'permission_denied',
            'details': {'message': str(exception)}
        }, status=403)
    
    def _handle_not_found(self, exception):
        """Handle not found errors"""
        return JsonResponse({
            'success': False,
            'error': 'Resource not found',
            'code': 'not_found',
            'details': {'message': str(exception)}
        }, status=404)
    
    def _handle_database_error(self, exception):
        """Handle database errors"""
        logger.error(f"Database error: {exception}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': 'Database error occurred',
            'code': 'database_error',
            'details': {}  # Don't expose database details to clients
        }, status=500)
    
    def _handle_generic_error(self, exception):
        """Handle all other errors"""
        logger.error(f"Unhandled exception: {exception}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': 'An unexpected error occurred',
            'code': 'internal_error',
            'details': {}  # Don't expose internal details to clients
        }, status=500)


# ==============================================================================
# DRF EXCEPTION HANDLER
# ==============================================================================

def custom_exception_handler(exc, context):
    """
    Custom exception handler for Django REST Framework
    """
    
    # Log the exception
    request = context.get('request')
    log_error(exc, request)
    
    # Call DRF's default exception handler first
    response = drf_exception_handler(exc, context)
    
    # If DRF handled it, customize the response
    if response is not None:
        # Standardize the error response format
        custom_response_data = {
            'success': False,
            'error': get_error_message(exc),
            'code': get_error_code(exc),
            'details': response.data if isinstance(response.data, dict) else {'detail': response.data}
        }
        
        response.data = custom_response_data
        return response
    
    # Handle custom application errors
    if isinstance(exc, ApplicationError):
        return JsonResponse({
            'success': False,
            'error': exc.message,
            'code': exc.code,
            'details': exc.details
        }, status=exc.status_code)
    
    # If DRF didn't handle it, return None to let Django handle it
    return None


def get_error_message(exc):
    """Extract user-friendly error message from exception"""
    
    if isinstance(exc, ApplicationError):
        return exc.message
    elif isinstance(exc, ValidationError):
        return 'Validation failed'
    elif isinstance(exc, AuthenticationFailed):
        return 'Authentication failed'
    elif isinstance(exc, NotAuthenticated):
        return 'Authentication required'
    elif isinstance(exc, PermissionDenied):
        return 'Permission denied'
    elif isinstance(exc, NotFound):
        return 'Resource not found'
    elif isinstance(exc, MethodNotAllowed):
        return 'Method not allowed'
    elif isinstance(exc, Throttled):
        return 'Too many requests'
    elif hasattr(exc, 'detail'):
        return str(exc.detail)
    else:
        return str(exc)


def get_error_code(exc):
    """Extract error code from exception"""
    
    if isinstance(exc, ApplicationError):
        return exc.code
    elif isinstance(exc, ValidationError):
        return 'validation_error'
    elif isinstance(exc, AuthenticationFailed):
        return 'authentication_failed'
    elif isinstance(exc, NotAuthenticated):
        return 'not_authenticated'
    elif isinstance(exc, PermissionDenied):
        return 'permission_denied'
    elif isinstance(exc, NotFound):
        return 'not_found'
    elif isinstance(exc, MethodNotAllowed):
        return 'method_not_allowed'
    elif isinstance(exc, Throttled):
        return 'throttled'
    elif hasattr(exc, 'default_code'):
        return exc.default_code
    else:
        return 'error'


# ==============================================================================
# ERROR LOGGING
# ==============================================================================

def log_error(exception, request=None):
    """
    Log error with context information
    """
    
    # Prepare error context
    error_context = {
        'timestamp': datetime.now().isoformat(),
        'exception_type': type(exception).__name__,
        'exception_message': str(exception),
        'traceback': traceback.format_exc(),
    }
    
    # Add request context if available
    if request:
        error_context.update({
            'path': request.path,
            'method': request.method,
            'user': str(request.user) if hasattr(request, 'user') else 'Anonymous',
            'ip_address': get_client_ip(request),
            'user_agent': request.META.get('HTTP_USER_AGENT', 'Unknown'),
        })
    
    # Log to appropriate logger based on severity
    if isinstance(exception, (ValidationError, ValidationErrorCustom)):
        logger.warning(f"Validation error: {exception}", extra=error_context)
    elif isinstance(exception, (UnauthorizedError, ForbiddenError, PermissionDenied)):
        logger.warning(f"Authorization error: {exception}", extra=error_context)
    elif isinstance(exception, (ResourceNotFoundError, ObjectDoesNotExist, NotFound)):
        logger.info(f"Not found error: {exception}", extra=error_context)
    elif isinstance(exception, DatabaseError):
        logger.critical(f"Database error: {exception}", extra=error_context)
    else:
        logger.error(f"Unhandled exception: {exception}", extra=error_context)
    
    # Store in database for tracking (optional)
    try:
        from .models import ErrorLog
        
        ErrorLog.objects.create(
            error_type=error_context['exception_type'],
            error_message=error_context['exception_message'],
            stack_trace=error_context['traceback'],
            request_path=error_context.get('path', ''),
            request_method=error_context.get('method', ''),
            user_id=request.user.id if request and hasattr(request, 'user') and request.user.is_authenticated else None,
            ip_address=error_context.get('ip_address', ''),
            user_agent=error_context.get('user_agent', ''),
            severity=get_error_severity(exception)
        )
    except Exception as e:
        # Don't let error logging break the application
        logger.error(f"Failed to log error to database: {e}")


def get_error_severity(exception):
    """Determine error severity level"""
    
    if isinstance(exception, (ValidationError, ValidationErrorCustom)):
        return 'warning'
    elif isinstance(exception, (UnauthorizedError, ForbiddenError)):
        return 'warning'
    elif isinstance(exception, (ResourceNotFoundError, ObjectDoesNotExist)):
        return 'info'
    elif isinstance(exception, DatabaseError):
        return 'critical'
    elif isinstance(exception, ApplicationError):
        return 'error'
    else:
        return 'error'


def get_client_ip(request):
    """Extract client IP address from request"""
    
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


# ==============================================================================
# ERROR NOTIFICATION
# ==============================================================================

def notify_error(exception, request=None, send_email=False):
    """
    Notify administrators of critical errors
    """
    
    # Only notify for critical errors
    if not isinstance(exception, (DatabaseError, ApplicationError)):
        return
    
    error_message = f"""
    Critical Error Occurred
    
    Exception: {type(exception).__name__}
    Message: {str(exception)}
    
    Request Path: {request.path if request else 'N/A'}
    User: {request.user if request and hasattr(request, 'user') else 'N/A'}
    
    Traceback:
    {traceback.format_exc()}
    """
    
    logger.critical(error_message)
    
    # Send email notification if enabled
    if send_email:
        try:
            from django.core.mail import mail_admins
            mail_admins(
                subject=f'Critical Error: {type(exception).__name__}',
                message=error_message,
                fail_silently=True
            )
        except Exception as e:
            logger.error(f"Failed to send error notification email: {e}")


# ==============================================================================
# UTILITY FUNCTIONS
# ==============================================================================

def safe_execute(func, *args, **kwargs):
    """
    Execute a function and handle any exceptions safely
    """
    
    try:
        return func(*args, **kwargs)
    except Exception as e:
        log_error(e)
        return None


def with_error_handling(func):
    """
    Decorator to add error handling to any function
    """
    
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            log_error(e)
            raise
    
    return wrapper


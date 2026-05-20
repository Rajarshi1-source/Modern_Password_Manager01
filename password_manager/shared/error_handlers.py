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
from django.conf import settings
from django.http import JsonResponse
from django.utils import timezone
from django.core.exceptions import (
    ValidationError,
    PermissionDenied,
    ObjectDoesNotExist
)
from django.db import DatabaseError
from rest_framework.views import exception_handler as drf_exception_handler, set_rollback
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
    Custom DRF exception handler that closes the CodeQL
    `py/stack-trace-exposure` family of alerts (#1133-#1303) without
    leaking exception detail to clients in production.

    Design notes:
    * The DRF default handler is called first and its status code is
      preserved verbatim. We never convert 401 ↔ 403 or 400 ↔ 422 —
      doing so previously broke `test_login_wrong_password_no_cookie`
      in auth_module/tests/test_cookie_auth.py.
    * DRF's `APIException` subclasses carry a curated, safe `.detail`
      attribute (e.g. "Invalid token", or a `{"field": [...]}` dict
      from a ValidationError). Those are returned to the client as-is.
    * For non-DRF unhandled exceptions, the response body contains
      only a constant `code` and a generic `error` message — never
      `str(exc)`. The full exception detail still goes to `logger`
      and to the ErrorLog table for operators.
    * In DEBUG mode the full exception text is included under
      `details` to keep local development ergonomic.
    """

    # Log the exception (best-effort; never let logging break a request).
    # `logger.exception` is called inside an except block, so it picks up
    # the active exception via sys.exc_info() and emits the traceback;
    # passing exc_info=True is redundant but explicit.
    request = context.get('request')
    try:
        log_error(exc, request)
    except Exception:  # pragma: no cover - defensive
        logger.exception(
            "custom_exception_handler: log_error failed", exc_info=True
        )

    # Call DRF's default exception handler first.
    response = drf_exception_handler(exc, context)

    debug_mode = bool(getattr(settings, 'DEBUG', False))

    if response is not None:
        # DRF handled it — keep the status code DRF chose. Only the
        # body is replaced with a standardized shape. `response.data`
        # is the curated `exc.detail`, which is safe to surface.
        safe_details = response.data if isinstance(response.data, dict) else {'detail': response.data}
        custom_response_data = {
            'success': False,
            'error': get_error_message(exc),
            'code': get_error_code(exc),
            'details': safe_details,
        }
        response.data = custom_response_data
        return response

    # Custom application errors carry their own safe message/code.
    # Mark the request transaction for rollback before returning so a
    # 4xx/5xx ApplicationError doesn't leave partial DB writes committed
    # under ATOMIC_REQUESTS=True. DRF's default `exception_handler` does
    # this internally via `set_rollback()` — we replicate it on every
    # branch where we return a response ourselves instead of letting
    # DRF do it.
    if isinstance(exc, ApplicationError):
        set_rollback()
        return JsonResponse({
            'success': False,
            'error': exc.message,
            'code': exc.code,
            'details': exc.details,
        }, status=exc.status_code)

    # Anything else is an *unhandled* exception. Do NOT expose its
    # repr/str to the client — that's exactly what CodeQL flags.
    if debug_mode:
        unhandled_details = {
            'exception_type': type(exc).__name__,
            'exception_message': str(exc),
        }
    else:
        unhandled_details = {}

    # Same rollback caveat as above: ATOMIC_REQUESTS=True would otherwise
    # commit any partial writes from this request because we return a
    # JsonResponse instead of letting the exception propagate.
    set_rollback()
    return JsonResponse({
        'success': False,
        'error': 'An unexpected error occurred',
        'code': 'internal_error',
        'details': unhandled_details,
    }, status=500)


def get_error_message(exc):
    """Extract user-friendly error message from exception.

    The return value is rendered into the response body, so it MUST NOT
    contain stack traces, file paths, credentials, or raw `str(exc)`
    output for non-DRF exceptions (CodeQL py/stack-trace-exposure family).
    DRF's `APIException` subclasses carry curated `.detail` strings that
    are safe to surface; everything else falls back to a constant.
    """

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
    elif isinstance(exc, APIException) and hasattr(exc, 'detail'):
        # DRF APIException subclasses are designed to be client-safe.
        return str(exc.detail)
    else:
        # Unknown / unhandled exception — never leak its str() form.
        return 'An unexpected error occurred'


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
        'timestamp': timezone.now().isoformat(),
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
    
    # Log to appropriate logger based on severity. We pass the exception
    # via `exc_info=` so logging emits the full traceback through the
    # standard formatter — the `extra=error_context` payload alone is
    # NOT rendered by the project's default 'verbose'/'simple' formatters
    # (see password_manager/settings.py LOGGING['formatters']), so an
    # exc_info-less call would silently drop the traceback at stdout/stderr.
    if isinstance(exception, (ValidationError, ValidationErrorCustom)):
        logger.warning("Validation error: %s", exception, extra=error_context, exc_info=exception)
    elif isinstance(exception, (UnauthorizedError, ForbiddenError, PermissionDenied)):
        logger.warning("Authorization error: %s", exception, extra=error_context, exc_info=exception)
    elif isinstance(exception, (ResourceNotFoundError, ObjectDoesNotExist, NotFound)):
        logger.info("Not found error: %s", exception, extra=error_context, exc_info=exception)
    elif isinstance(exception, DatabaseError):
        logger.critical("Database error: %s", exception, extra=error_context, exc_info=exception)
    else:
        logger.error("Unhandled exception: %s", exception, extra=error_context, exc_info=exception)
    
    # Store in database for tracking (best-effort). The ErrorLog model
    # lives in shared.models — the field names below MUST match
    # shared/models.py exactly. A previous version of this function used
    # `error_type`/`error_message`/`stack_trace`/`request_path`/
    # `request_method`/`severity` (which do not exist on the model) and
    # raised IntegrityError on every request, which is why registering
    # this handler in REST_FRAMEWORK had to be reverted. See the comment
    # block in password_manager/password_manager/settings.py.
    try:
        from .models import ErrorLog

        user_obj = None
        if (
            request is not None
            and hasattr(request, 'user')
            and getattr(request.user, 'is_authenticated', False)
        ):
            user_obj = request.user

        ErrorLog.objects.create(
            level=_severity_to_level(get_error_severity(exception)),
            message=error_context['exception_message'],
            exception_type=error_context['exception_type'],
            traceback=error_context['traceback'],
            path=error_context.get('path', '') or '',
            method=error_context.get('method', '') or '',
            user=user_obj,
            user_agent=error_context.get('user_agent', '') or '',
            ip_address=error_context.get('ip_address') or None,
        )
    except Exception as exc_log:
        # Don't let error logging break the application
        logger.warning("Failed to log error to database: %s", exc_log)


# Map the legacy severity strings used by `get_error_severity` onto the
# ErrorLog.level choices ('DEBUG'/'INFO'/'WARNING'/'ERROR'/'CRITICAL').
_SEVERITY_TO_LEVEL = {
    'debug': 'DEBUG',
    'info': 'INFO',
    'warning': 'WARNING',
    'error': 'ERROR',
    'critical': 'CRITICAL',
}


def _severity_to_level(severity: str) -> str:
    return _SEVERITY_TO_LEVEL.get((severity or 'error').lower(), 'ERROR')


def get_error_severity(exception):
    """Determine error severity level used by ErrorLog and the logger.

    The DRF exception classes (`AuthenticationFailed`, `NotAuthenticated`,
    `PermissionDenied`, `Throttled`, `NotFound`, `MethodNotAllowed`) are
    classified explicitly so that routine 401/403/404/405/429 responses
    don't get stored as `ERROR` in ErrorLog and skew operator dashboards.
    """

    if isinstance(exception, (ValidationError, ValidationErrorCustom)):
        return 'warning'
    elif isinstance(
        exception,
        (
            UnauthorizedError,
            ForbiddenError,
            PermissionDenied,
            AuthenticationFailed,
            NotAuthenticated,
            Throttled,
            MethodNotAllowed,
        ),
    ):
        # 401/403/405/429 — client-side problems, not service errors
        return 'warning'
    elif isinstance(exception, (ResourceNotFoundError, ObjectDoesNotExist, NotFound)):
        # 404 — informational, not an error
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


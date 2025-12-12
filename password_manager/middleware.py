"""
ASGI-Compatible Middleware for Password Manager

These middleware classes are designed to work with both WSGI (sync) and ASGI (async)
request handling, making them compatible with Django Channels and Daphne.
"""

from django.conf import settings
from django.http import HttpResponseRedirect, HttpResponseForbidden, HttpResponsePermanentRedirect
from asgiref.sync import iscoroutinefunction, markcoroutinefunction, sync_to_async
import logging
import ipaddress

logger = logging.getLogger(__name__)


# FIX: Middleware to exempt /auth/ and /api/auth/ paths from CSRF
# This is more reliable than view-level decorators for DRF ViewSets
class CSRFExemptAuthMiddleware:
    """Exempt authentication endpoints from CSRF verification.
    
    JWT-based APIs don't need CSRF protection since they use
    Authorization headers instead of cookies for authentication.
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
        self._exempt_csrf_if_auth(request)
        return await self.get_response(request)
    
    def _process_sync(self, request):
        self._exempt_csrf_if_auth(request)
        return self.get_response(request)
    
    def _exempt_csrf_if_auth(self, request):
        """Mark auth requests as CSRF exempt"""
        # Exempt /auth/ and /api/auth/ paths from CSRF
        if request.path.startswith('/auth/') or request.path.startswith('/api/auth/'):
            setattr(request, '_dont_enforce_csrf_checks', True)


class ASGIRedirectFixMiddleware:
    """
    Middleware to fix ASGI redirect compatibility issues.
    
    When Django's CommonMiddleware or other middleware generates an
    HttpResponsePermanentRedirect, it can cause issues with ASGI because
    the ASGI handler may try to await the response incorrectly.
    
    This middleware wraps redirect responses to ensure they work correctly
    in both sync and async contexts.
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
        return self.get_response(request)
    
    async def __acall__(self, request):
        """Async request handler that properly handles redirect responses"""
        try:
            response = await self.get_response(request)
            return response
        except TypeError as e:
            # Catch the "can't be used in 'await' expression" error
            if "await" in str(e):
                logger.warning(f"ASGI redirect fix caught error: {e}")
                # The response was likely a redirect that wasn't properly awaited
                # Try calling get_response synchronously
                from asgiref.sync import sync_to_async
                sync_get_response = sync_to_async(lambda req: self.get_response.__wrapped__(req), thread_sensitive=True)
                return await sync_get_response(request)
            raise


class HttpsRedirectMiddleware:
    """
    Redirect HTTP requests to HTTPS in production.
    
    This middleware is async-compatible and works with both WSGI and ASGI.
    """
    
    async_capable = True
    sync_capable = True
    
    def __init__(self, get_response):
        self.get_response = get_response
        # Check if the get_response is async
        if iscoroutinefunction(self.get_response):
            markcoroutinefunction(self)
    
    def __call__(self, request):
        # Handle both sync and async modes
        if iscoroutinefunction(self.get_response):
            return self.__acall__(request)
        return self._process_request_sync(request)
    
    async def __acall__(self, request):
        """Async request handler"""
        # Check if redirect is needed (only in production)
        redirect_response = self._check_redirect(request)
        if redirect_response:
            return redirect_response
        
        # Call the next middleware/view
        response = await self.get_response(request)
        return response
    
    def _process_request_sync(self, request):
        """Sync request handler"""
        redirect_response = self._check_redirect(request)
        if redirect_response:
            return redirect_response
        return self.get_response(request)
    
    def _check_redirect(self, request):
        """Check if HTTPS redirect is needed"""
        # Only redirect in production (non-DEBUG mode)
        if not request.is_secure() and not settings.DEBUG:
            url = request.build_absolute_uri(request.get_full_path())
            secure_url = url.replace('http://', 'https://')
            return HttpResponseRedirect(secure_url)
        return None


class SecurityHeadersMiddleware:
    """
    Add security headers to all responses.
    
    This middleware is async-compatible and works with both WSGI and ASGI.
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
        response = await self.get_response(request)
        return self._add_security_headers(request, response)
    
    def _process_sync(self, request):
        """Sync request handler"""
        response = self.get_response(request)
        return self._add_security_headers(request, response)
    
    def _add_security_headers(self, request, response):
        """Add security headers to the response"""
        # Content Security Policy - Restrict sources of content
        response['Content-Security-Policy'] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://cdn.jsdelivr.net; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "font-src 'self' https://fonts.gstatic.com; "
            "img-src 'self' data: blob:; "
            "connect-src 'self' ws: wss: https://api.haveibeenpwned.com; "
            "frame-ancestors 'none'; "
            "form-action 'self'"
        )
        
        # Prevent browsers from using MIME sniffing
        response['X-Content-Type-Options'] = 'nosniff'
        
        # Prevent clickjacking
        response['X-Frame-Options'] = 'DENY'
        
        # Enable XSS protection
        response['X-XSS-Protection'] = '1; mode=block'
        
        # HSTS - Force HTTPS (only in production)
        if not settings.DEBUG:
            response['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains; preload'
        
        # Prevent browsers from caching sensitive information
        if request.path.startswith('/api/') or request.path.startswith('/auth/'):
            response['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
            response['Pragma'] = 'no-cache'
            response['Expires'] = '0'
        
        return response


class SecurityMiddleware:
    """
    Middleware to handle security-related tasks for each request.
    
    This middleware is async-compatible and works with both WSGI and ASGI.
    Handles:
    - IP whitelisting (Enterprise feature)
    - Device fingerprint tracking
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
        # Check IP whitelisting
        forbidden_response = self._check_ip_whitelist(request)
        if forbidden_response:
            return forbidden_response
        
        # Get response from next middleware/view
        response = await self.get_response(request)
        
        # Update device timestamp (run in thread pool to avoid blocking)
        await self._update_device_timestamp_async(request)
        
        return response
    
    def _process_sync(self, request):
        """Sync request handler"""
        # Check IP whitelisting
        forbidden_response = self._check_ip_whitelist(request)
        if forbidden_response:
            return forbidden_response
        
        response = self.get_response(request)
        
        # Update device timestamp
        self._update_device_timestamp_sync(request)
        
        return response
    
    def _check_ip_whitelist(self, request):
        """Check if IP whitelisting blocks this request"""
        if getattr(settings, 'IP_WHITELISTING_ENABLED', False) and getattr(settings, 'ALLOWED_IP_RANGES', []):
            client_ip = self._get_client_ip(request)
            if not self._is_ip_allowed(client_ip):
                logger.warning(f"Access denied for IP: {client_ip}")
                return HttpResponseForbidden("Access denied: Your IP address is not authorized.")
        return None
    
    async def _update_device_timestamp_async(self, request):
        """Update device timestamp asynchronously"""
        await sync_to_async(self._update_device_timestamp_sync)(request)
    
    def _update_device_timestamp_sync(self, request):
        """Update device timestamp synchronously"""
        # Skip if user is not authenticated
        if not hasattr(request, 'user') or not request.user.is_authenticated:
            return
        
        # Skip excluded paths
        excluded_paths = ['/api/security/', '/api/login/', '/auth/login/', '/auth/register/']
        path = request.path
        if any(path.startswith(excluded) for excluded in excluded_paths):
            return
        
        # Update device last used timestamp if it's a known device
        device_fingerprint = request.headers.get('X-Device-Fingerprint')
        if device_fingerprint:
            try:
                from security.models import UserDevice
                from django.utils import timezone
                
                device = UserDevice.objects.filter(
                    user=request.user,
                    fingerprint=device_fingerprint
                ).first()
                
                if device:
                    device.last_seen = timezone.now()
                    device.save(update_fields=['last_seen'])
            except Exception as e:
                logger.error(f"Error updating device timestamp: {e}")
    
    def _get_client_ip(self, request):
        """Get the client's IP address from the request"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip
    
    def _is_ip_allowed(self, client_ip):
        """Check if the client IP is in the allowed IP ranges"""
        try:
            client_ip_obj = ipaddress.ip_address(client_ip)
            for ip_range in settings.ALLOWED_IP_RANGES:
                if not ip_range.strip():
                    continue
                try:
                    # Check if it's a network range (e.g., 192.168.1.0/24)
                    if '/' in ip_range:
                        network = ipaddress.ip_network(ip_range.strip(), strict=False)
                        if client_ip_obj in network:
                            return True
                    # Check if it's a single IP address
                    else:
                        allowed_ip = ipaddress.ip_address(ip_range.strip())
                        if client_ip_obj == allowed_ip:
                            return True
                except ValueError as e:
                    logger.error(f"Invalid IP range in settings: {ip_range}, error: {e}")
            return False
        except ValueError as e:
            logger.error(f"Invalid client IP: {client_ip}, error: {e}")
            return False

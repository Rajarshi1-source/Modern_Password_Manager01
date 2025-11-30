"""
Throttling configuration for the Password Manager API.

This module contains custom throttling classes for different types of API operations,
ensuring rate limiting for security-sensitive operations like authentication and
password checking.
"""

from rest_framework.throttling import ScopedRateThrottle, AnonRateThrottle, UserRateThrottle
from rest_framework.throttling import BaseThrottle
from django.core.cache import cache
from django.conf import settings
import time
import logging

logger = logging.getLogger(__name__)


class AuthRateThrottle(ScopedRateThrottle):
    """
    Rate throttling for authentication endpoints.
    Limits login attempts to prevent brute force attacks.
    """
    scope = 'auth'
    
    def get_cache_key(self, request, view):
        """
        Override to include IP address in cache key for better security.
        """
        if request.user and request.user.is_authenticated:
            ident = request.user.pk
        else:
            ident = self.get_ident(request)
        
        return self.cache_format % {
            'scope': self.scope,
            'ident': ident
        }


class PasswordCheckRateThrottle(ScopedRateThrottle):
    """
    Rate throttling for password checking operations.
    Limits password breach checks and validation attempts.
    """
    scope = 'password_check'


class SecurityOperationThrottle(ScopedRateThrottle):
    """
    Rate throttling for security-sensitive operations.
    Limits operations like device registration, 2FA setup, etc.
    """
    scope = 'security'


class PasskeyThrottle(ScopedRateThrottle):
    """
    Rate throttling for WebAuthn/passkey operations.
    Limits passkey registration and authentication attempts.
    """
    scope = 'passkey'


class VaultOperationThrottle(UserRateThrottle):
    """
    Rate throttling for vault operations.
    More lenient throttling for authenticated vault operations.
    """
    scope = 'vault'
    
    def allow_request(self, request, view):
        """
        Override to allow higher rates for authenticated users.
        """
        if request.user and request.user.is_authenticated:
            return super().allow_request(request, view)
        else:
            # Use more restrictive throttling for anonymous users
            self.rate = getattr(settings, 'ANON_VAULT_RATE', '10/hour')
            return super().allow_request(request, view)


class StrictSecurityThrottle(BaseThrottle):
    """
    Very strict throttling for highly sensitive operations.
    Used for operations like account recovery, emergency access, etc.
    """
    RATE_LIMIT = 3  # 3 attempts per hour
    CACHE_TIMEOUT = 3600  # 1 hour
    
    def allow_request(self, request, view):
        """
        Check if request should be allowed based on strict rate limiting.
        """
        cache_key = self.get_cache_key(request)
        current_time = int(time.time())
        
        # Get current attempt count and timestamps
        attempts = cache.get(cache_key, [])
        
        # Filter out attempts older than 1 hour
        recent_attempts = [
            timestamp for timestamp in attempts 
            if current_time - timestamp < self.CACHE_TIMEOUT
        ]
        
        # Check if under rate limit
        if len(recent_attempts) < self.RATE_LIMIT:
            # Add current attempt
            recent_attempts.append(current_time)
            cache.set(cache_key, recent_attempts, self.CACHE_TIMEOUT)
            return True
        
        # Log rate limit exceeded
        logger.warning(
            f"Strict security rate limit exceeded for {self.get_ident(request)} "
            f"on {request.path}"
        )
        return False
    
    def get_cache_key(self, request):
        """
        Generate cache key for rate limiting.
        """
        ident = self.get_ident(request)
        return f"strict_throttle:{ident}:{request.path}"
    
    def get_ident(self, request):
        """
        Get identifier for the request (IP address or user ID).
        """
        if request.user and request.user.is_authenticated:
            return f"user:{request.user.pk}"
        else:
            xff = request.META.get('HTTP_X_FORWARDED_FOR')
            remote_addr = request.META.get('REMOTE_ADDR')
            return xff.split(',')[0].strip() if xff else remote_addr
    
    def wait(self):
        """
        Return the recommended next request time in seconds.
        """
        return self.CACHE_TIMEOUT


# Throttle classes for different security levels
SECURITY_THROTTLES = {
    'low': UserRateThrottle,
    'medium': SecurityOperationThrottle, 
    'high': AuthRateThrottle,
    'critical': StrictSecurityThrottle,
}

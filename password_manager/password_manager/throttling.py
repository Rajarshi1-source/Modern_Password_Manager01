"""
Throttling configuration for the Password Manager API.

This module contains custom throttling classes for different types of API operations,
ensuring rate limiting for security-sensitive operations like authentication and
password checking.
"""

from rest_framework.throttling import ScopedRateThrottle, AnonRateThrottle, UserRateThrottle
from rest_framework.throttling import BaseThrottle, SimpleRateThrottle
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

    def get_rate(self):
        if hasattr(self, '_request_is_anon') and self._request_is_anon:
            return getattr(settings, 'ANON_VAULT_RATE', '10/hour')
        return super().get_rate()

    def allow_request(self, request, view):
        self._request_is_anon = not (request.user and request.user.is_authenticated)
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


class WhatIfSimulationThrottle(ScopedRateThrottle):
    """
    Rate throttling for CPU-intensive what-if simulations.
    """
    scope = 'what_if_simulation'


class DeadDropCollectThrottle(ScopedRateThrottle):
    """
    Rate throttling for dead drop fragment collection.
    Limits per-IP to prevent brute-force attempts.
    """
    scope = 'deaddrop_collect'

    def get_cache_key(self, request, view):
        if request.user and request.user.is_authenticated:
            ident = request.user.pk
        else:
            ident = self.get_ident(request)
        return self.cache_format % {
            'scope': self.scope,
            'ident': ident
        }


def _vouch_resource_ident(request, view):
    """Return the most specific resource identifier available on the
    request, or ``None`` if none can be derived.

    Priority order matches the public social-recovery surface:

      1. ``voucher_id`` from the JSON body (``AttestRequestView``).
      2. ``request_id`` from the URL (``CompleteRequestView``).
      3. ``circle_id`` from the JSON body (``InitiateRecoveryView``).

    Returning ``None`` lets the caller bypass the per-resource bucket
    while still applying the per-IP cap — the right behaviour when the
    payload isn't parseable (malformed JSON) or hasn't been parsed yet.
    """
    try:
        data = getattr(request, 'data', None) or {}
    except Exception:
        # ``request.data`` is lazy; if the parser blows up we don't want
        # to take the throttle down with it. Fall through to IP-only.
        data = {}
    voucher_id = data.get('voucher_id')
    if voucher_id:
        return f"voucher:{voucher_id}"
    kwargs = getattr(view, 'kwargs', None) or {}
    request_id = kwargs.get('request_id')
    if request_id:
        return f"request:{request_id}"
    circle_id = data.get('circle_id') or kwargs.get('circle_id')
    if circle_id:
        return f"circle:{circle_id}"
    return None


class _DynamicRateThrottleMixin:
    """Make ``get_rate`` re-read ``api_settings.DEFAULT_THROTTLE_RATES``
    on every instantiation rather than caching the value at class-import
    time.

    DRF's ``SimpleRateThrottle`` binds the rate dict to a class attribute
    (``THROTTLE_RATES = api_settings.DEFAULT_THROTTLE_RATES``) the moment
    the module is imported. ``override_settings(REST_FRAMEWORK=...)`` in
    tests reloads ``api_settings`` itself but the *class attribute* still
    points at the original dict — so the rate frozen at import wins.
    Reading fresh here lets ``override_settings`` actually take effect.
    """

    def get_rate(self):
        from rest_framework.settings import api_settings
        try:
            return api_settings.DEFAULT_THROTTLE_RATES[self.scope]
        except KeyError as exc:  # pragma: no cover - configuration bug
            msg = (
                f"No default throttle rate set for '{self.scope}' scope; "
                f"add it to REST_FRAMEWORK['DEFAULT_THROTTLE_RATES']."
            )
            raise RuntimeError(msg) from exc


class _VouchPerResourceBucket(_DynamicRateThrottleMixin, SimpleRateThrottle):
    """Per-(voucher|request|circle) token bucket."""

    scope = 'vouch_attestation'

    def get_cache_key(self, request, view):
        ident = _vouch_resource_ident(request, view)
        if ident is None:
            # No identifiable resource -> skip the per-resource bucket;
            # the per-IP bucket alone is responsible for this request.
            return None
        return self.cache_format % {'scope': self.scope, 'ident': ident}


class _VouchPerIPBucket(_DynamicRateThrottleMixin, SimpleRateThrottle):
    """Per-IP token bucket. Caps fan-out from a single host even when
    the attacker rotates ``voucher_id`` values."""

    scope = 'vouch_attestation_ip'

    def get_cache_key(self, request, view):
        return self.cache_format % {
            'scope': self.scope,
            'ident': self.get_ident(request),
        }


class VouchAttestationThrottle(BaseThrottle):
    """Compose per-resource + per-IP buckets for the public social-recovery
    endpoints.

    Two independent buckets:

    * ``vouch_attestation``     — keyed on voucher/request/circle id.
      Stops a single compromised voucher key from flipping a quorum.
    * ``vouch_attestation_ip``  — keyed on client IP. Stops a single
      host from spreading the attack across many voucher ids.

    The request is allowed only if BOTH buckets accept it. A rejection
    in either bucket emits an ``attestation_rate_limited`` audit row so
    operators see when this fires.

    ``BaseThrottle`` (rather than ``ScopedRateThrottle``) is used because
    DRF supports exactly one scope per ``ScopedRateThrottle`` instance;
    we need two distinct rates checked simultaneously.
    """

    def __init__(self):
        self._resource = _VouchPerResourceBucket()
        self._ip = _VouchPerIPBucket()
        self._last_wait = None

    def allow_request(self, request, view):
        ok_resource = self._resource.allow_request(request, view)
        ok_ip = self._ip.allow_request(request, view)
        if ok_resource and ok_ip:
            return True

        # Compute the longer of the two recommended back-offs so ``wait``
        # returns something useful in the ``Retry-After`` header.
        waits = []
        for bucket, ok in ((self._resource, ok_resource), (self._ip, ok_ip)):
            if not ok:
                w = bucket.wait()
                if w is not None:
                    waits.append(w)
        self._last_wait = max(waits) if waits else None

        self._emit_audit_event(request, view, ok_resource, ok_ip)
        return False

    def wait(self):
        return self._last_wait

    @staticmethod
    def _emit_audit_event(request, view, ok_resource, ok_ip):
        """Best-effort audit row. Never raise from a throttle path —
        failing here would 500 the request instead of cleanly 429-ing."""
        try:
            from social_recovery.services.audit_service import record_event
            ip = None
            try:
                ip = _VouchPerIPBucket().get_ident(request)
            except Exception:
                ip = None
            record_event(
                event_type='attestation_rate_limited',
                ip_address=ip,
                user_agent=request.META.get('HTTP_USER_AGENT', '')[:255],
                event_data={
                    'view': view.__class__.__name__,
                    'path': request.path,
                    'bucket_resource_ok': bool(ok_resource),
                    'bucket_ip_ok': bool(ok_ip),
                    'resource_ident': _vouch_resource_ident(request, view),
                },
            )
        except Exception:  # pragma: no cover - audit is best-effort
            logger.exception(
                "failed to record attestation_rate_limited audit row",
            )


class MeshNodePingThrottle(ScopedRateThrottle):
    """Throttle mesh node pings so a compromised device cannot flood the API.

    Keyed per ``(user, node_id)`` so a single compromised node can't bring the
    whole fleet offline, and so legitimate heartbeats from multiple devices
    are not throttled against each other.
    """

    scope = 'mesh_node_ping'

    def get_cache_key(self, request, view):
        user_pk = getattr(request.user, 'pk', None) or self.get_ident(request)
        node_id = (
            view.kwargs.get('node_id') if hasattr(view, 'kwargs') else None
        )
        ident = f"{user_pk}:{node_id}" if node_id else f"{user_pk}"
        return self.cache_format % {'scope': self.scope, 'ident': ident}


# Throttle classes for different security levels
SECURITY_THROTTLES = {
    'low': UserRateThrottle,
    'medium': SecurityOperationThrottle, 
    'high': AuthRateThrottle,
    'critical': StrictSecurityThrottle,
}

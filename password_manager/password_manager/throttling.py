"""
Throttling configuration for the Password Manager API.

This module contains custom throttling classes for different types of API operations,
ensuring rate limiting for security-sensitive operations like authentication and
password checking.

--------------------------------------------------------------------------
Phase G / G1 (2026-05): why these classes use ``SimpleRateThrottle``, not
``ScopedRateThrottle``.

DRF's ``ScopedRateThrottle.allow_request`` reads the throttle scope from
the **view's** ``throttle_scope`` attribute, NOT from the throttle
class:

    def allow_request(self, request, view):
        self.scope = getattr(view, 'throttle_scope', None)
        if not self.scope:
            return True  # <-- short-circuits to ALLOW
        ...

No view in this codebase sets ``throttle_scope``. That means every
``ScopedRateThrottle`` subclass that declares a class-level
``scope = 'foo'`` was historically being silently disabled — DRF
overwrote ``self.scope = None`` on every call, the function returned
``True``, no rate limit ever fired.

This was first surfaced by the Phase F fix for
``HoneypotWebhookThrottle`` (Codex P1 on PR #277). Phase G is the
cleanup pass: every previously-``ScopedRateThrottle`` class with a
class-level ``scope`` is now a ``SimpleRateThrottle`` subclass.
``SimpleRateThrottle.__init__`` reads ``self.scope`` directly,
populates ``self.rate`` / ``num_requests`` / ``duration`` from
``settings.REST_FRAMEWORK['DEFAULT_THROTTLE_RATES'][scope]``, and the
throttle actually runs.

The ``ScopedRateThrottle`` import is kept so future code that
genuinely wants per-view scope assignment (via ``throttle_scope`` on
the view) can still reach for it.
--------------------------------------------------------------------------
"""

from rest_framework.throttling import ScopedRateThrottle, AnonRateThrottle, UserRateThrottle
from rest_framework.throttling import BaseThrottle, SimpleRateThrottle
from django.core.cache import cache
from django.conf import settings
import time
import logging
import uuid
from typing import Optional

logger = logging.getLogger(__name__)


class AuthRateThrottle(SimpleRateThrottle):
    """
    Rate throttling for authentication endpoints.
    Limits login attempts to prevent brute force attacks.

    Phase G / G1: was ``ScopedRateThrottle`` (no-op without
    ``throttle_scope`` on the view — see module docstring).
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


class _UserOrIPCacheKeyMixin:
    """Phase G / G1: shared cache-key strategy for SimpleRateThrottle
    subclasses migrated from ScopedRateThrottle. Key by
    authenticated-user PK when available, fall back to client IP for
    anonymous traffic. ScopedRateThrottle inherited a similar default;
    SimpleRateThrottle requires the implementation to be explicit."""

    def get_cache_key(self, request, view):
        if request.user and request.user.is_authenticated:
            ident = request.user.pk
        else:
            ident = self.get_ident(request)
        return self.cache_format % {'scope': self.scope, 'ident': ident}


class PasswordCheckRateThrottle(_UserOrIPCacheKeyMixin, SimpleRateThrottle):
    """
    Rate throttling for password checking operations.
    Limits password breach checks and validation attempts.

    Phase G / G1: was ``ScopedRateThrottle`` (no-op without
    ``throttle_scope`` on the view — see module docstring).
    """
    scope = 'password_check'


class SecurityOperationThrottle(_UserOrIPCacheKeyMixin, SimpleRateThrottle):
    """
    Rate throttling for security-sensitive operations.
    Limits operations like device registration, 2FA setup, etc.

    Phase G / G1: was ``ScopedRateThrottle`` (no-op without
    ``throttle_scope`` on the view — see module docstring).
    """
    scope = 'security'


class PasskeyThrottle(_UserOrIPCacheKeyMixin, SimpleRateThrottle):
    """
    Rate throttling for WebAuthn/passkey operations.
    Limits passkey registration and authentication attempts.

    Phase G / G1: was ``ScopedRateThrottle`` (no-op without
    ``throttle_scope`` on the view — see module docstring).
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


class WhatIfSimulationThrottle(SimpleRateThrottle):
    """
    Rate throttling for CPU-intensive what-if simulations.

    Phase G / G1: was ``ScopedRateThrottle`` (no-op without
    ``throttle_scope`` on the view — see module docstring).
    """
    scope = 'what_if_simulation'

    def get_cache_key(self, request, view):
        # ``SimpleRateThrottle`` requires get_cache_key to be defined
        # explicitly (no default). Match the convention used by the
        # other classes in this module: per-user when authenticated,
        # per-IP otherwise.
        if request.user and request.user.is_authenticated:
            ident = request.user.pk
        else:
            ident = self.get_ident(request)
        return self.cache_format % {'scope': self.scope, 'ident': ident}


class DeadDropCollectThrottle(SimpleRateThrottle):
    """
    Rate throttling for dead drop fragment collection.
    Limits per-IP to prevent brute-force attempts.

    Phase G / G1: was ``ScopedRateThrottle`` (no-op without
    ``throttle_scope`` on the view — see module docstring).
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


class HoneypotWebhookThrottle(SimpleRateThrottle):
    """Phase F / F4 (2026-05): per-IP rate limit on the honeypot webhook.

    The endpoint is intentionally public (``permission_classes = []``)
    and gated only by an HMAC signature check. That keeps the
    legitimate provider integrations simple but leaves the endpoint
    exposed to two abuse patterns the signature check alone doesn't
    address:

      1. Log flooding — an attacker can hammer the endpoint with
         wrong-signature requests; every miss writes a
         ``logger.warning(f"Invalid webhook signature from {provider}")``
         line and the log file grows unbounded.
      2. Timing-oracle probing — repeated requests at varying rates
         could be used to infer per-request handling cost.

    Per-IP throttle (default 60/min via ``honeypot_webhook`` scope)
    closes both. Real providers fan in from a small set of source
    IPs and rarely exceed a few req/sec; legit traffic stays well
    under the limit.

    PR #277 review (Codex P1): this MUST subclass ``SimpleRateThrottle``
    rather than ``ScopedRateThrottle``. DRF's ``ScopedRateThrottle``
    reads its scope from the VIEW's ``throttle_scope`` attribute, not
    from the throttle class — and the public webhook view (and every
    other view in this codebase) doesn't set that attribute, so the
    scoped variant short-circuits to ``allow_request → True`` and
    the throttle is silently disabled. ``SimpleRateThrottle`` reads
    ``self.scope`` directly from the class, which matches the
    intended semantics.
    """
    scope = 'honeypot_webhook'

    def get_cache_key(self, request, view):
        # Webhook is unauthenticated by design — always key by IP.
        return self.cache_format % {
            'scope': self.scope,
            'ident': self.get_ident(request),
        }


def _coerce_uuid_str(value) -> Optional[str]:
    """Return a canonical UUID string if ``value`` parses as one, else ``None``.

    Treating ``"not-a-uuid"`` as a valid resource key was the original
    bug here: anything truthy was accepted, so the per-resource bucket
    silently absorbed malformed inputs and the documented IP-only
    fallback never triggered. Validating against ``uuid.UUID`` makes
    the fallback reachable.
    """
    if value is None:
        return None
    try:
        return str(uuid.UUID(str(value)))
    except (ValueError, TypeError, AttributeError):
        return None


def _vouch_resource_ident(request, view):
    """Return the most specific resource identifier available on the
    request, or ``None`` if none can be derived.

    Priority order matches the public social-recovery surface:

      1. ``voucher_id`` from the JSON body (``AttestRequestView``).
      2. ``request_id`` from the URL (``CompleteRequestView``).
      3. ``circle_id`` from the JSON body (``InitiateRecoveryView``).

    Returning ``None`` lets the caller bypass the per-resource bucket
    while still applying the per-IP cap — the right behaviour when the
    payload isn't parseable (malformed JSON), hasn't been parsed yet,
    or supplies an identifier the server cannot validate.

    A request that *carries* ``voucher_id`` (the key is present) but
    whose value fails to parse as a UUID drops through to ``None``
    rather than falling back to ``request_id`` — falling back would let
    an attacker pin per-resource quota to whatever string they want
    while still hitting the attest endpoint. ``request_id`` / ``circle_id``
    are only consulted when their respective key was not supplied.
    """
    try:
        data = getattr(request, 'data', None) or {}
    except Exception:
        # ``request.data`` is lazy; if the parser blows up we don't want
        # to take the throttle down with it. Fall through to IP-only.
        data = {}
    kwargs = getattr(view, 'kwargs', None) or {}

    # 1) voucher_id (attestation)
    if 'voucher_id' in data:
        voucher_id = _coerce_uuid_str(data.get('voucher_id'))
        # Present but malformed -> IP-only bucket. We intentionally do NOT
        # fall through to request_id here: an attacker supplying garbage
        # voucher_ids on the attest endpoint should not be able to opt
        # themselves into a different (potentially fresher) resource
        # bucket by doing so.
        if voucher_id is None:
            return None
        return f"voucher:{voucher_id}"

    # 2) request_id (URL kwarg on complete endpoint)
    request_id = _coerce_uuid_str(kwargs.get('request_id'))
    if request_id:
        return f"request:{request_id}"

    # 3) circle_id (body or URL kwarg on initiate endpoint)
    circle_id = _coerce_uuid_str(
        data.get('circle_id') if 'circle_id' in data else kwargs.get('circle_id')
    )
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

        # The composite has rejected the request, but
        # ``SimpleRateThrottle.throttle_success`` already wrote a
        # timestamp into the cache of whichever child returned True.
        # Without a rollback that "ghost hit" persists, so an attacker
        # who is already throttled on one dimension can keep consuming
        # the OTHER dimension's budget — eventually causing unrelated
        # legitimate traffic on that shared dimension to be 429'd.
        # Pop the recorded hit so each bucket only counts requests the
        # composite actually allowed.
        if ok_resource and not ok_ip:
            self._rollback_hit(self._resource)
        elif ok_ip and not ok_resource:
            self._rollback_hit(self._ip)
        # If both children rejected, neither wrote — nothing to undo.

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
    def _rollback_hit(bucket):
        """Undo the timestamp ``SimpleRateThrottle.throttle_success``
        wrote into the cache for ``bucket``.

        Concurrency note: another worker could write to the same key
        between the original ``cache.set`` and this rollback. We accept
        that small race because the alternative (leaving a ghost hit on
        a denied request) is strictly worse — false 429s for unrelated
        traffic on the same bucket. Best-effort by design.
        """
        try:
            key = getattr(bucket, 'key', None)
            history = getattr(bucket, 'history', None)
            if not key or not history:
                return
            # ``throttle_success`` does ``history.insert(0, self.now)`` —
            # the just-recorded hit is at index 0.
            history.pop(0)
            bucket.cache.set(key, history, bucket.duration)
        except Exception:  # pragma: no cover - rollback is best-effort
            logger.exception("failed to roll back composite throttle hit")

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


class MeshNodePingThrottle(SimpleRateThrottle):
    """Throttle mesh node pings so a compromised device cannot flood the API.

    Keyed per ``(user, node_id)`` so a single compromised node can't bring the
    whole fleet offline, and so legitimate heartbeats from multiple devices
    are not throttled against each other.

    Phase G / G1: was ``ScopedRateThrottle`` (no-op without
    ``throttle_scope`` on the view — see module docstring).
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

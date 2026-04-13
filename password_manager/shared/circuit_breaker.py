"""
Circuit Breaker Pattern for External API Resilience
=====================================================

Prevents cascading failures when external services (Claude API, HIBP,
blockchain RPC) go down.  Without a circuit breaker, failing calls retry
indefinitely, tying up Daphne worker threads and exhausting the thread pool.

States:
    CLOSED  — calls pass through; failures are counted.
    OPEN    — calls are immediately rejected with CircuitBreakerOpen.
    HALF_OPEN — one probe call is allowed; success closes, failure re-opens.

Storage:
    Uses the Django 'rate_limiting' cache alias so that state survives
    restarts when Redis is configured (USE_REDIS_CACHE=True).  Falls back
    to locmem in development.

Usage:
    from shared.circuit_breaker import circuit_breaker, CircuitBreakerOpen

    @circuit_breaker(name='claude_api', failure_threshold=5, recovery_timeout=30)
    def call_claude(prompt):
        return anthropic_client.messages.create(...)

    # Or as a context manager:
    cb = CircuitBreaker('hibp_api')
    with cb:
        response = requests.get(...)
"""

import logging
import time
from enum import Enum
from functools import wraps

from django.core.cache import caches

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    CLOSED = 'closed'
    OPEN = 'open'
    HALF_OPEN = 'half_open'


class CircuitBreakerOpen(Exception):
    """Raised when the circuit is open and calls are being rejected."""

    def __init__(self, name: str, recovery_in: float = 0):
        self.name = name
        self.recovery_in = recovery_in
        super().__init__(
            f"Circuit breaker '{name}' is OPEN. "
            f"Service unavailable. Retry in {int(recovery_in)}s."
        )


class CircuitBreaker:
    """
    Thread-safe, cache-backed circuit breaker.

    Args:
        name:               Unique identifier (e.g. 'claude_api').
        failure_threshold:  Consecutive failures before opening the circuit.
        recovery_timeout:   Seconds to wait in OPEN before allowing a probe.
        half_open_max_calls: Max probe calls allowed in HALF_OPEN state.
        cache_alias:        Django cache alias for state storage.
    """

    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: int = 30,
        half_open_max_calls: int = 1,
        cache_alias: str = 'rate_limiting',
    ):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max_calls = half_open_max_calls
        self._cache_alias = cache_alias

    # ---- Cache helpers ----

    @property
    def _cache(self):
        """Lazy cache access — avoids import-time cache initialization."""
        return caches[self._cache_alias]

    def _key(self, suffix: str) -> str:
        return f'circuit_breaker:{self.name}:{suffix}'

    def _get_failure_count(self) -> int:
        return self._cache.get(self._key('failures'), 0)

    def _set_failure_count(self, count: int):
        # TTL = 2x recovery timeout to auto-clean stale keys
        self._cache.set(
            self._key('failures'), count,
            timeout=self.recovery_timeout * 2
        )

    def _get_state(self) -> CircuitState:
        raw = self._cache.get(self._key('state'))
        if raw is None:
            return CircuitState.CLOSED
        try:
            return CircuitState(raw)
        except ValueError:
            return CircuitState.CLOSED

    def _set_state(self, state: CircuitState):
        self._cache.set(
            self._key('state'), state.value,
            timeout=self.recovery_timeout * 3
        )

    def _get_opened_at(self) -> float:
        return self._cache.get(self._key('opened_at'), 0)

    def _set_opened_at(self, timestamp: float):
        self._cache.set(
            self._key('opened_at'), timestamp,
            timeout=self.recovery_timeout * 3
        )

    def _get_half_open_calls(self) -> int:
        return self._cache.get(self._key('half_open_calls'), 0)

    def _incr_half_open_calls(self):
        key = self._key('half_open_calls')
        try:
            self._cache.incr(key)
        except ValueError:
            self._cache.set(key, 1, timeout=self.recovery_timeout)

    # ---- State transitions ----

    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to try a probe call."""
        opened_at = self._get_opened_at()
        return (time.time() - opened_at) >= self.recovery_timeout

    def _transition_to_open(self):
        logger.warning(
            f"Circuit breaker '{self.name}' → OPEN "
            f"(threshold={self.failure_threshold} consecutive failures)"
        )
        self._set_state(CircuitState.OPEN)
        self._set_opened_at(time.time())
        self._cache.set(self._key('half_open_calls'), 0, timeout=self.recovery_timeout)

    def _transition_to_half_open(self):
        logger.info(f"Circuit breaker '{self.name}' → HALF_OPEN (probing)")
        self._set_state(CircuitState.HALF_OPEN)

    def _transition_to_closed(self):
        logger.info(f"Circuit breaker '{self.name}' → CLOSED (recovered)")
        self._set_state(CircuitState.CLOSED)
        self._set_failure_count(0)

    # ---- Core logic ----

    def before_call(self):
        """
        Check circuit state before making the external call.
        Raises CircuitBreakerOpen if calls should be rejected.
        """
        state = self._get_state()

        if state == CircuitState.CLOSED:
            return  # Allow call

        if state == CircuitState.OPEN:
            if self._should_attempt_reset():
                self._transition_to_half_open()
                # Fall through to allow the probe call
            else:
                elapsed = time.time() - self._get_opened_at()
                recovery_in = max(0, self.recovery_timeout - elapsed)
                raise CircuitBreakerOpen(self.name, recovery_in)

        if state == CircuitState.HALF_OPEN:
            if self._get_half_open_calls() >= self.half_open_max_calls:
                raise CircuitBreakerOpen(self.name, self.recovery_timeout)
            self._incr_half_open_calls()

    def on_success(self):
        """Record a successful call."""
        state = self._get_state()
        if state == CircuitState.HALF_OPEN:
            self._transition_to_closed()
        elif state == CircuitState.CLOSED:
            # Reset failure count on success
            self._set_failure_count(0)

    def on_failure(self, exc: Exception = None):
        """Record a failed call."""
        state = self._get_state()

        if state == CircuitState.HALF_OPEN:
            # Probe failed — re-open
            self._transition_to_open()
            return

        if state == CircuitState.CLOSED:
            failures = self._get_failure_count() + 1
            self._set_failure_count(failures)

            if failures >= self.failure_threshold:
                self._transition_to_open()
            else:
                logger.debug(
                    f"Circuit breaker '{self.name}': failure {failures}/"
                    f"{self.failure_threshold}"
                )

    # ---- Context manager ----

    def __enter__(self):
        self.before_call()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:
            self.on_success()
        elif exc_type is not CircuitBreakerOpen:
            self.on_failure(exc_val)
        return False  # Don't suppress the exception

    # ---- Status ----

    def get_status(self) -> dict:
        """Return current circuit breaker status for health checks."""
        state = self._get_state()
        return {
            'name': self.name,
            'state': state.value,
            'failure_count': self._get_failure_count(),
            'failure_threshold': self.failure_threshold,
            'recovery_timeout': self.recovery_timeout,
        }


# ---- Global circuit breaker instances ----

# Pre-configured breakers for known external services.
# Import these directly: `from shared.circuit_breaker import claude_breaker`
claude_breaker = CircuitBreaker(
    name='claude_api',
    failure_threshold=5,
    recovery_timeout=30,
)

hibp_breaker = CircuitBreaker(
    name='hibp_api',
    failure_threshold=5,
    recovery_timeout=60,
)

blockchain_breaker = CircuitBreaker(
    name='blockchain_rpc',
    failure_threshold=5,
    recovery_timeout=60,
)

oidc_breaker = CircuitBreaker(
    name='oidc_discovery',
    failure_threshold=3,
    recovery_timeout=60,
)

noaa_breaker = CircuitBreaker(
    name='noaa_api',
    failure_threshold=5,
    recovery_timeout=120,
)

ipinfo_breaker = CircuitBreaker(
    name='ipinfo_api',
    failure_threshold=5,
    recovery_timeout=60,
)

email_masking_breaker = CircuitBreaker(
    name='email_masking_api',
    failure_threshold=5,
    recovery_timeout=60,
)

quantum_rng_breaker = CircuitBreaker(
    name='quantum_rng_api',
    failure_threshold=3,
    recovery_timeout=120,
)

amadeus_breaker = CircuitBreaker(
    name='amadeus_api',
    failure_threshold=3,
    recovery_timeout=120,
)


def circuit_breaker(
    name: str = None,
    failure_threshold: int = 5,
    recovery_timeout: int = 30,
    **kwargs,
):
    """
    Decorator to wrap a function with a circuit breaker.

    Usage:
        @circuit_breaker(name='my_api')
        def call_api():
            ...
    """
    def decorator(func):
        cb = CircuitBreaker(
            name=name or func.__qualname__,
            failure_threshold=failure_threshold,
            recovery_timeout=recovery_timeout,
            **kwargs,
        )

        @wraps(func)
        def wrapper(*args, **kw):
            cb.before_call()
            try:
                result = func(*args, **kw)
                cb.on_success()
                return result
            except CircuitBreakerOpen:
                raise
            except Exception as e:
                cb.on_failure(e)
                raise

        wrapper.circuit_breaker = cb
        return wrapper

    return decorator

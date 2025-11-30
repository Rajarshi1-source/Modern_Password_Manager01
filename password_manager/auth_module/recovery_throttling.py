"""
Recovery-Specific Rate Limiting and Throttling

Enhanced security throttling for passkey recovery endpoints.
Implements progressive rate limiting with lockout protection.
"""

from rest_framework.throttling import BaseThrottle, SimpleRateThrottle
from django.core.cache import cache
from django.conf import settings
from django.utils import timezone
import hashlib
import logging
import time

logger = logging.getLogger(__name__)


class RecoveryThrottle(SimpleRateThrottle):
    """
    Strict rate limiting for recovery operations.
    
    Recovery operations are high-value targets for attackers.
    We implement:
    - Low request limits
    - Progressive lockout
    - IP-based and user-based tracking
    - Monitoring and alerting
    """
    scope = 'recovery'
    
    # Default rate: 3 attempts per hour
    THROTTLE_RATES = {
        'recovery': '3/hour',
    }
    
    def get_cache_key(self, request, view):
        """Generate cache key based on IP and optional user identifier."""
        if request.user.is_authenticated:
            ident = str(request.user.id)
        else:
            ident = self.get_ident(request)
        
        return f'throttle_recovery_{view.__class__.__name__}_{ident}'
    
    def get_rate(self):
        """Get rate from settings or use default."""
        rate = getattr(settings, 'RECOVERY_THROTTLE_RATE', '3/hour')
        if not hasattr(self, 'THROTTLE_RATES'):
            self.THROTTLE_RATES = {}
        self.THROTTLE_RATES['recovery'] = rate
        return super().get_rate()


class RecoveryInitiateThrottle(SimpleRateThrottle):
    """
    Rate limiting specifically for recovery initiation.
    More permissive than completion throttle.
    """
    scope = 'recovery_initiate'
    
    def get_cache_key(self, request, view):
        ident = self.get_ident(request)
        return f'throttle_recovery_initiate_{ident}'
    
    def get_rate(self):
        return getattr(settings, 'RECOVERY_INITIATE_RATE', '5/hour')


class RecoveryCompleteThrottle(SimpleRateThrottle):
    """
    Strict rate limiting for recovery completion (key verification).
    This is where attackers would try to brute force recovery keys.
    """
    scope = 'recovery_complete'
    
    def get_cache_key(self, request, view):
        ident = self.get_ident(request)
        return f'throttle_recovery_complete_{ident}'
    
    def get_rate(self):
        return getattr(settings, 'RECOVERY_COMPLETE_RATE', '3/hour')


class ProgressiveLockoutThrottle(BaseThrottle):
    """
    Progressive lockout throttle that increases lockout duration
    with each failed attempt.
    
    Lockout progression:
    - 1st-3rd failure: Normal rate limiting
    - 4th-6th failure: 15 minute lockout
    - 7th-10th failure: 1 hour lockout
    - 11th+ failure: 24 hour lockout
    
    Also triggers security alerts after threshold.
    """
    
    LOCKOUT_LEVELS = [
        (3, 0),      # First 3 attempts: no extra lockout
        (6, 900),    # Next 3: 15 minutes
        (10, 3600),  # Next 4: 1 hour
        (float('inf'), 86400),  # Beyond: 24 hours
    ]
    
    ALERT_THRESHOLD = 5  # Trigger security alert after this many failures
    
    def __init__(self):
        self.cache_key_prefix = 'progressive_lockout'
    
    def get_cache_key(self, request):
        """Generate cache key based on IP."""
        ip = self._get_client_ip(request)
        ip_hash = hashlib.sha256(ip.encode()).hexdigest()[:16]
        return f'{self.cache_key_prefix}_{ip_hash}'
    
    def _get_client_ip(self, request):
        """Extract client IP from request."""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR', 'unknown')
        return ip
    
    def allow_request(self, request, view):
        """Check if request is allowed based on lockout status."""
        cache_key = self.get_cache_key(request)
        lockout_data = cache.get(cache_key)
        
        if lockout_data is None:
            return True
        
        failures = lockout_data.get('failures', 0)
        lockout_until = lockout_data.get('lockout_until')
        
        # Check if currently locked out
        if lockout_until and time.time() < lockout_until:
            remaining = int(lockout_until - time.time())
            logger.warning(
                f"Recovery attempt blocked - IP locked out for {remaining}s more. "
                f"Failures: {failures}. IP: {self._get_client_ip(request)}"
            )
            self.wait = remaining
            return False
        
        return True
    
    def record_failure(self, request, reason: str = 'unknown'):
        """Record a failed recovery attempt and potentially trigger lockout."""
        cache_key = self.get_cache_key(request)
        lockout_data = cache.get(cache_key) or {'failures': 0, 'first_failure': time.time()}
        
        lockout_data['failures'] += 1
        lockout_data['last_failure'] = time.time()
        lockout_data['last_reason'] = reason
        
        failures = lockout_data['failures']
        
        # Calculate lockout duration
        lockout_duration = 0
        for threshold, duration in self.LOCKOUT_LEVELS:
            if failures <= threshold:
                lockout_duration = duration
                break
        
        if lockout_duration > 0:
            lockout_data['lockout_until'] = time.time() + lockout_duration
            logger.warning(
                f"Progressive lockout triggered: {failures} failures. "
                f"Locked for {lockout_duration}s. IP: {self._get_client_ip(request)}"
            )
        
        # Trigger security alert if threshold reached
        if failures == self.ALERT_THRESHOLD:
            self._trigger_security_alert(request, failures)
        
        # Store with 24-hour expiry
        cache.set(cache_key, lockout_data, timeout=86400)
        
        return lockout_duration
    
    def record_success(self, request):
        """Record a successful recovery and reset lockout."""
        cache_key = self.get_cache_key(request)
        cache.delete(cache_key)
        logger.info(f"Recovery lockout reset for IP: {self._get_client_ip(request)}")
    
    def _trigger_security_alert(self, request, failures):
        """Trigger security alert for suspicious recovery attempts."""
        ip = self._get_client_ip(request)
        user_agent = request.META.get('HTTP_USER_AGENT', 'unknown')
        
        logger.critical(
            f"SECURITY ALERT: Multiple failed recovery attempts detected. "
            f"IP: {ip}, Failures: {failures}, User-Agent: {user_agent}"
        )
        
        # In production, you would:
        # 1. Send notification to security team
        # 2. Log to SIEM system
        # 3. Consider temporary IP block
        
        # Example: Store alert in database
        try:
            from .quantum_recovery_models import RecoveryAuditLog
            from django.contrib.auth import get_user_model
            User = get_user_model()
            
            # Create audit log entry
            RecoveryAuditLog.objects.create(
                user=None if not request.user.is_authenticated else request.user,
                event_type='suspicious_activity',
                event_data={
                    'type': 'multiple_failed_recovery_attempts',
                    'failures': failures,
                    'threshold': self.ALERT_THRESHOLD,
                    'user_agent': user_agent,
                },
                ip_address=ip,
                user_agent=user_agent,
                cryptographic_hash=hashlib.sha256(
                    f'{ip}:{time.time()}'.encode()
                ).hexdigest()
            )
        except Exception as e:
            logger.error(f"Failed to create security alert audit log: {e}")


# Singleton instance for progressive lockout
progressive_lockout = ProgressiveLockoutThrottle()


def get_throttle_status(request) -> dict:
    """Get current throttle status for a request."""
    ip = request.META.get('REMOTE_ADDR', 'unknown')
    
    # Check progressive lockout
    lockout_key = f'progressive_lockout_{hashlib.sha256(ip.encode()).hexdigest()[:16]}'
    lockout_data = cache.get(lockout_key) or {}
    
    return {
        'ip_hash': hashlib.sha256(ip.encode()).hexdigest()[:16],
        'failures': lockout_data.get('failures', 0),
        'is_locked': bool(
            lockout_data.get('lockout_until') and 
            time.time() < lockout_data.get('lockout_until', 0)
        ),
        'lockout_remaining': max(
            0, 
            int(lockout_data.get('lockout_until', 0) - time.time())
        ) if lockout_data.get('lockout_until') else 0,
        'last_failure': lockout_data.get('last_failure'),
        'first_failure': lockout_data.get('first_failure'),
    }


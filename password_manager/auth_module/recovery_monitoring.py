"""
Recovery System Monitoring and Metrics

Provides comprehensive monitoring, metrics collection, and alerting
for the passkey recovery system.
"""

import logging
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from collections import defaultdict
from django.core.cache import cache
from django.db.models import Count, Avg, Q
from django.utils import timezone
from django.conf import settings

logger = logging.getLogger(__name__)


@dataclass
class RecoveryMetric:
    """Single recovery metric data point."""
    timestamp: datetime
    metric_type: str
    value: float
    metadata: Dict[str, Any] = field(default_factory=dict)


class RecoveryMetricsCollector:
    """
    Collects and aggregates recovery system metrics.
    
    Metrics tracked:
    - Recovery attempt counts (success/failure)
    - Average recovery time
    - Fallback rates (primary -> social mesh)
    - Key verification failure rates
    - Guardian response times
    - Shard collection times
    """
    
    CACHE_PREFIX = 'recovery_metrics'
    METRIC_RETENTION_HOURS = 168  # 7 days
    
    def __init__(self):
        self.metrics_buffer: List[RecoveryMetric] = []
        self.buffer_limit = 100
    
    def record_recovery_attempt(
        self,
        user_id: int,
        attempt_type: str,  # 'primary' or 'social_mesh'
        status: str,  # 'initiated', 'completed', 'failed', 'fallback'
        duration_seconds: Optional[float] = None,
        metadata: Optional[Dict] = None
    ):
        """Record a recovery attempt metric."""
        metric = RecoveryMetric(
            timestamp=timezone.now(),
            metric_type=f'recovery_attempt_{attempt_type}_{status}',
            value=1.0,
            metadata={
                'user_id': user_id,
                'duration_seconds': duration_seconds,
                **(metadata or {})
            }
        )
        self._store_metric(metric)
        
        # Log for monitoring
        logger.info(
            f"Recovery attempt recorded: type={attempt_type}, status={status}, "
            f"user_id={user_id}, duration={duration_seconds}s"
        )
    
    def record_key_verification(
        self,
        user_id: int,
        success: bool,
        ip_address: str
    ):
        """Record a recovery key verification attempt."""
        metric = RecoveryMetric(
            timestamp=timezone.now(),
            metric_type=f'key_verification_{"success" if success else "failure"}',
            value=1.0,
            metadata={
                'user_id': user_id,
                'ip_address': ip_address,
            }
        )
        self._store_metric(metric)
        
        if not success:
            logger.warning(
                f"Key verification failed: user_id={user_id}, ip={ip_address}"
            )
    
    def record_guardian_response(
        self,
        user_id: int,
        guardian_id: str,
        response_time_seconds: float,
        approved: bool
    ):
        """Record a guardian response metric."""
        metric = RecoveryMetric(
            timestamp=timezone.now(),
            metric_type=f'guardian_response_{"approved" if approved else "denied"}',
            value=response_time_seconds,
            metadata={
                'user_id': user_id,
                'guardian_id': guardian_id,
                'approved': approved,
            }
        )
        self._store_metric(metric)
    
    def record_fallback(
        self,
        user_id: int,
        from_type: str,  # 'primary'
        to_type: str,  # 'social_mesh'
        reason: str
    ):
        """Record a recovery fallback event."""
        metric = RecoveryMetric(
            timestamp=timezone.now(),
            metric_type='recovery_fallback',
            value=1.0,
            metadata={
                'user_id': user_id,
                'from_type': from_type,
                'to_type': to_type,
                'reason': reason,
            }
        )
        self._store_metric(metric)
        
        logger.warning(
            f"Recovery fallback: user_id={user_id}, {from_type} -> {to_type}, "
            f"reason={reason}"
        )
    
    def _store_metric(self, metric: RecoveryMetric):
        """Store metric in cache and buffer."""
        self.metrics_buffer.append(metric)
        
        # Flush buffer if limit reached
        if len(self.metrics_buffer) >= self.buffer_limit:
            self._flush_buffer()
        
        # Also store in cache for real-time queries
        cache_key = f'{self.CACHE_PREFIX}:{metric.metric_type}:{metric.timestamp.isoformat()}'
        cache.set(cache_key, metric.__dict__, timeout=self.METRIC_RETENTION_HOURS * 3600)
    
    def _flush_buffer(self):
        """Flush metrics buffer to persistent storage."""
        if not self.metrics_buffer:
            return
        
        # In production, you would write to a time-series database or analytics system
        # For now, we aggregate to cache
        aggregated = defaultdict(list)
        for metric in self.metrics_buffer:
            key = f'{self.CACHE_PREFIX}:aggregated:{metric.metric_type}'
            aggregated[key].append(metric.value)
        
        for key, values in aggregated.items():
            existing = cache.get(key) or []
            existing.extend(values)
            # Keep last 1000 values
            cache.set(key, existing[-1000:], timeout=self.METRIC_RETENTION_HOURS * 3600)
        
        self.metrics_buffer.clear()
    
    def get_metrics_summary(self, hours: int = 24) -> Dict:
        """Get summary of recovery metrics for the specified time period."""
        summary = {
            'period_hours': hours,
            'generated_at': timezone.now().isoformat(),
            'primary_recovery': {
                'total_attempts': 0,
                'successful': 0,
                'failed': 0,
                'avg_duration_seconds': 0,
            },
            'social_mesh_recovery': {
                'total_attempts': 0,
                'successful': 0,
                'failed': 0,
                'avg_guardian_response_time': 0,
            },
            'fallbacks': {
                'count': 0,
                'rate': 0.0,
            },
            'key_verification': {
                'total': 0,
                'success_rate': 0.0,
            },
            'alerts': [],
        }
        
        try:
            from .passkey_primary_recovery_models import PasskeyRecoveryAttempt
            from .quantum_recovery_models import RecoveryAttempt
            
            cutoff = timezone.now() - timedelta(hours=hours)
            
            # Primary recovery stats
            primary_attempts = PasskeyRecoveryAttempt.objects.filter(
                initiated_at__gte=cutoff
            )
            summary['primary_recovery']['total_attempts'] = primary_attempts.count()
            summary['primary_recovery']['successful'] = primary_attempts.filter(
                status='recovery_complete'
            ).count()
            summary['primary_recovery']['failed'] = primary_attempts.filter(
                status__in=['failed', 'key_invalid', 'decryption_failed']
            ).count()
            
            # Social mesh recovery stats
            social_attempts = RecoveryAttempt.objects.filter(
                initiated_at__gte=cutoff
            )
            summary['social_mesh_recovery']['total_attempts'] = social_attempts.count()
            summary['social_mesh_recovery']['successful'] = social_attempts.filter(
                status='completed',
                recovery_successful=True
            ).count()
            summary['social_mesh_recovery']['failed'] = social_attempts.filter(
                status='failed'
            ).count()
            
            # Fallback rate
            fallbacks = primary_attempts.filter(status='fallback_initiated').count()
            summary['fallbacks']['count'] = fallbacks
            if summary['primary_recovery']['total_attempts'] > 0:
                summary['fallbacks']['rate'] = (
                    fallbacks / summary['primary_recovery']['total_attempts']
                ) * 100
            
            # Generate alerts based on metrics
            summary['alerts'] = self._generate_alerts(summary)
            
        except Exception as e:
            logger.error(f"Error generating metrics summary: {e}")
            summary['error'] = str(e)
        
        return summary
    
    def _generate_alerts(self, summary: Dict) -> List[Dict]:
        """Generate alerts based on metrics."""
        alerts = []
        
        # High failure rate alert
        primary = summary['primary_recovery']
        if primary['total_attempts'] > 10:
            failure_rate = (primary['failed'] / primary['total_attempts']) * 100
            if failure_rate > 20:
                alerts.append({
                    'severity': 'warning' if failure_rate < 50 else 'critical',
                    'type': 'high_failure_rate',
                    'message': f'Primary recovery failure rate is {failure_rate:.1f}%',
                    'threshold': 20,
                    'current_value': failure_rate,
                })
        
        # High fallback rate alert
        if summary['fallbacks']['rate'] > 30:
            alerts.append({
                'severity': 'warning',
                'type': 'high_fallback_rate',
                'message': f'Recovery fallback rate is {summary["fallbacks"]["rate"]:.1f}%',
                'threshold': 30,
                'current_value': summary['fallbacks']['rate'],
            })
        
        return alerts


class RecoveryHealthChecker:
    """
    Health checker for the recovery system.
    Monitors system components and dependencies.
    """
    
    def check_health(self) -> Dict:
        """Run all health checks and return status."""
        checks = {
            'database': self._check_database(),
            'cache': self._check_cache(),
            'crypto': self._check_crypto(),
            'celery': self._check_celery(),
            'email': self._check_email(),
        }
        
        overall_status = 'healthy'
        for check_name, check_result in checks.items():
            if check_result['status'] == 'unhealthy':
                overall_status = 'unhealthy'
                break
            elif check_result['status'] == 'degraded' and overall_status == 'healthy':
                overall_status = 'degraded'
        
        return {
            'status': overall_status,
            'timestamp': timezone.now().isoformat(),
            'checks': checks,
        }
    
    def _check_database(self) -> Dict:
        """Check database connectivity."""
        try:
            from django.db import connection
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
            return {'status': 'healthy', 'message': 'Database connection OK'}
        except Exception as e:
            return {'status': 'unhealthy', 'message': str(e)}
    
    def _check_cache(self) -> Dict:
        """Check cache connectivity."""
        try:
            test_key = 'health_check_test'
            cache.set(test_key, 'test', timeout=10)
            result = cache.get(test_key)
            if result == 'test':
                return {'status': 'healthy', 'message': 'Cache connection OK'}
            return {'status': 'degraded', 'message': 'Cache read/write mismatch'}
        except Exception as e:
            return {'status': 'unhealthy', 'message': str(e)}
    
    def _check_crypto(self) -> Dict:
        """Check cryptographic service availability."""
        try:
            from .services.kyber_crypto import get_crypto_status
            status = get_crypto_status()
            
            if status['using_real_pqc']:
                return {
                    'status': 'healthy',
                    'message': f'Using {status["implementation"]} implementation',
                    'details': status
                }
            else:
                return {
                    'status': 'degraded',
                    'message': 'Using simulated cryptography - NOT for production',
                    'details': status
                }
        except Exception as e:
            return {'status': 'unhealthy', 'message': str(e)}
    
    def _check_celery(self) -> Dict:
        """Check Celery worker availability."""
        try:
            from celery import current_app
            inspect = current_app.control.inspect()
            stats = inspect.stats()
            
            if stats:
                worker_count = len(stats)
                return {
                    'status': 'healthy',
                    'message': f'{worker_count} Celery worker(s) running',
                    'workers': list(stats.keys())
                }
            else:
                return {
                    'status': 'degraded',
                    'message': 'No Celery workers detected - async tasks disabled'
                }
        except Exception as e:
            return {
                'status': 'degraded',
                'message': f'Celery check failed: {str(e)}'
            }
    
    def _check_email(self) -> Dict:
        """Check email configuration."""
        try:
            email_backend = settings.EMAIL_BACKEND
            if 'console' in email_backend.lower() or 'dummy' in email_backend.lower():
                return {
                    'status': 'degraded',
                    'message': 'Email using console/dummy backend - not for production'
                }
            return {
                'status': 'healthy',
                'message': 'Email backend configured'
            }
        except Exception as e:
            return {'status': 'unhealthy', 'message': str(e)}


# Global instances
metrics_collector = RecoveryMetricsCollector()
health_checker = RecoveryHealthChecker()


def get_recovery_dashboard_data() -> Dict:
    """Get all data needed for a recovery system dashboard."""
    return {
        'health': health_checker.check_health(),
        'metrics_24h': metrics_collector.get_metrics_summary(24),
        'metrics_7d': metrics_collector.get_metrics_summary(168),
    }


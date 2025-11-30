"""
Kyber Performance Monitoring Service

Comprehensive monitoring for CRYSTALS-Kyber cryptographic operations:
- Operation timing and throughput
- Error tracking
- Cache hit/miss rates
- Algorithm status
- System health

Usage:
    from auth_module.services.kyber_monitor import kyber_monitor
    
    @kyber_monitor.measure_operation('keypair_generation')
    async def generate_keypair():
        ...
    
    metrics = kyber_monitor.get_all_metrics()
"""

import logging
import time
import functools
import asyncio
from typing import Dict, Any, Optional, Callable
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from threading import Lock

from django.conf import settings

logger = logging.getLogger(__name__)


@dataclass
class OperationMetrics:
    """Metrics for a single operation type."""
    count: int = 0
    total_time: float = 0.0
    min_time: float = float('inf')
    max_time: float = 0.0
    errors: int = 0
    last_operation: Optional[datetime] = None
    
    @property
    def avg_time(self) -> float:
        """Average operation time in milliseconds."""
        return (self.total_time / self.count * 1000) if self.count > 0 else 0
    
    @property
    def error_rate(self) -> float:
        """Error rate as percentage."""
        total = self.count + self.errors
        return (self.errors / total * 100) if total > 0 else 0
    
    def record(self, elapsed: float, success: bool = True):
        """Record an operation."""
        self.last_operation = datetime.now()
        
        if success:
            self.count += 1
            self.total_time += elapsed
            self.min_time = min(self.min_time, elapsed)
            self.max_time = max(self.max_time, elapsed)
        else:
            self.errors += 1
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'count': self.count,
            'total_time_ms': self.total_time * 1000,
            'avg_time_ms': self.avg_time,
            'min_time_ms': self.min_time * 1000 if self.min_time != float('inf') else 0,
            'max_time_ms': self.max_time * 1000,
            'errors': self.errors,
            'error_rate': f'{self.error_rate:.2f}%',
            'last_operation': self.last_operation.isoformat() if self.last_operation else None
        }


class KyberPerformanceMonitor:
    """
    Performance monitoring for Kyber cryptographic operations.
    
    Features:
    - Operation timing with decorators
    - Error tracking and alerting
    - Throughput calculation
    - Health status reporting
    """
    
    def __init__(self):
        self._lock = Lock()
        self._operations: Dict[str, OperationMetrics] = defaultdict(OperationMetrics)
        self._start_time = datetime.now()
        
        # Alert thresholds
        self._alert_thresholds = {
            'error_rate': 5.0,  # Alert if error rate > 5%
            'avg_time_ms': 100,  # Alert if avg time > 100ms
            'min_throughput': 10  # Alert if throughput < 10 ops/sec
        }
        
        # Recent errors for debugging
        self._recent_errors: list = []
        self._max_recent_errors = 100
        
        logger.info("KyberPerformanceMonitor initialized")
    
    def measure_operation(self, operation_name: str):
        """
        Decorator to measure operation performance.
        
        Usage:
            @kyber_monitor.measure_operation('keypair_generation')
            def generate_keypair():
                ...
        """
        def decorator(func: Callable):
            @functools.wraps(func)
            def sync_wrapper(*args, **kwargs):
                start_time = time.perf_counter()
                success = True
                try:
                    result = func(*args, **kwargs)
                    return result
                except Exception as e:
                    success = False
                    self._record_error(operation_name, e)
                    raise
                finally:
                    elapsed = time.perf_counter() - start_time
                    self._record_operation(operation_name, elapsed, success)
            
            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs):
                start_time = time.perf_counter()
                success = True
                try:
                    result = await func(*args, **kwargs)
                    return result
                except Exception as e:
                    success = False
                    self._record_error(operation_name, e)
                    raise
                finally:
                    elapsed = time.perf_counter() - start_time
                    self._record_operation(operation_name, elapsed, success)
            
            # Return appropriate wrapper based on function type
            if asyncio.iscoroutinefunction(func):
                return async_wrapper
            return sync_wrapper
        
        return decorator
    
    def _record_operation(self, operation_name: str, elapsed: float, success: bool):
        """Record an operation internally."""
        with self._lock:
            self._operations[operation_name].record(elapsed, success)
    
    def _record_error(self, operation_name: str, error: Exception):
        """Record an error."""
        with self._lock:
            error_info = {
                'operation': operation_name,
                'error_type': type(error).__name__,
                'error_message': str(error),
                'timestamp': datetime.now().isoformat()
            }
            
            self._recent_errors.append(error_info)
            
            # Trim old errors
            if len(self._recent_errors) > self._max_recent_errors:
                self._recent_errors = self._recent_errors[-self._max_recent_errors:]
            
            logger.error(f"Kyber operation error [{operation_name}]: {error}")
    
    def record_manual(
        self, 
        operation_name: str, 
        elapsed: float, 
        success: bool = True
    ):
        """
        Manually record an operation metric.
        
        Args:
            operation_name: Name of the operation
            elapsed: Time elapsed in seconds
            success: Whether operation was successful
        """
        self._record_operation(operation_name, elapsed, success)
    
    def get_operation_metrics(self, operation_name: str) -> Dict[str, Any]:
        """Get metrics for a specific operation."""
        with self._lock:
            if operation_name in self._operations:
                return self._operations[operation_name].to_dict()
            return {}
    
    def get_all_metrics(self) -> Dict[str, Any]:
        """Get all metrics."""
        with self._lock:
            uptime = (datetime.now() - self._start_time).total_seconds()
            
            total_operations = sum(m.count for m in self._operations.values())
            total_errors = sum(m.errors for m in self._operations.values())
            
            return {
                'uptime_seconds': uptime,
                'total_operations': total_operations,
                'total_errors': total_errors,
                'overall_error_rate': f'{(total_errors / max(total_operations + total_errors, 1) * 100):.2f}%',
                'throughput_ops_per_sec': total_operations / max(uptime, 1),
                'operations': {
                    name: metrics.to_dict()
                    for name, metrics in self._operations.items()
                }
            }
    
    def get_health_status(self) -> Dict[str, Any]:
        """
        Get system health status.
        
        Returns:
            Dictionary with health indicators and alerts
        """
        metrics = self.get_all_metrics()
        alerts = []
        status = 'healthy'
        
        # Check overall error rate
        total_ops = metrics['total_operations']
        total_errors = metrics['total_errors']
        
        if total_ops > 0:
            error_rate = total_errors / (total_ops + total_errors) * 100
            
            if error_rate > self._alert_thresholds['error_rate']:
                alerts.append({
                    'type': 'high_error_rate',
                    'message': f'Error rate is {error_rate:.1f}% (threshold: {self._alert_thresholds["error_rate"]}%)',
                    'severity': 'warning'
                })
                status = 'degraded'
        
        # Check individual operation performance
        for op_name, op_metrics in metrics['operations'].items():
            if op_metrics['avg_time_ms'] > self._alert_thresholds['avg_time_ms']:
                alerts.append({
                    'type': 'slow_operation',
                    'message': f'{op_name} avg time is {op_metrics["avg_time_ms"]:.1f}ms',
                    'severity': 'info'
                })
        
        # Check throughput
        if metrics['throughput_ops_per_sec'] < self._alert_thresholds['min_throughput']:
            if total_ops > 100:  # Only alert after sufficient operations
                alerts.append({
                    'type': 'low_throughput',
                    'message': f'Throughput is {metrics["throughput_ops_per_sec"]:.1f} ops/sec',
                    'severity': 'info'
                })
        
        return {
            'status': status,
            'alerts': alerts,
            'alert_count': len(alerts),
            'last_check': datetime.now().isoformat()
        }
    
    def get_recent_errors(self, limit: int = 10) -> list:
        """Get recent errors."""
        with self._lock:
            return self._recent_errors[-limit:]
    
    def reset_metrics(self):
        """Reset all metrics."""
        with self._lock:
            self._operations.clear()
            self._start_time = datetime.now()
            self._recent_errors.clear()
            logger.info("Kyber metrics reset")
    
    def set_alert_threshold(self, threshold_name: str, value: float):
        """Set an alert threshold."""
        if threshold_name in self._alert_thresholds:
            self._alert_thresholds[threshold_name] = value
            logger.info(f"Alert threshold '{threshold_name}' set to {value}")
    
    def get_summary(self) -> str:
        """Get a human-readable summary."""
        metrics = self.get_all_metrics()
        health = self.get_health_status()
        
        lines = [
            "=== Kyber Performance Summary ===",
            f"Status: {health['status'].upper()}",
            f"Uptime: {metrics['uptime_seconds']:.0f}s",
            f"Total Operations: {metrics['total_operations']}",
            f"Total Errors: {metrics['total_errors']}",
            f"Error Rate: {metrics['overall_error_rate']}",
            f"Throughput: {metrics['throughput_ops_per_sec']:.1f} ops/sec",
            "",
            "Operations:",
        ]
        
        for op_name, op_metrics in metrics['operations'].items():
            lines.append(
                f"  - {op_name}: {op_metrics['count']} calls, "
                f"avg {op_metrics['avg_time_ms']:.2f}ms, "
                f"errors: {op_metrics['errors']}"
            )
        
        if health['alerts']:
            lines.append("")
            lines.append("Alerts:")
            for alert in health['alerts']:
                lines.append(f"  [{alert['severity'].upper()}] {alert['message']}")
        
        return "\n".join(lines)


# Global singleton instance
kyber_monitor = KyberPerformanceMonitor()


def get_kyber_monitor() -> KyberPerformanceMonitor:
    """Get the global Kyber monitor instance."""
    return kyber_monitor


# Convenience decorators
def measure_keypair_generation(func):
    """Decorator for keypair generation operations."""
    return kyber_monitor.measure_operation('keypair_generation')(func)


def measure_encryption(func):
    """Decorator for encryption operations."""
    return kyber_monitor.measure_operation('encryption')(func)


def measure_decryption(func):
    """Decorator for decryption operations."""
    return kyber_monitor.measure_operation('decryption')(func)


def measure_ntt(func):
    """Decorator for NTT operations."""
    return kyber_monitor.measure_operation('ntt_transform')(func)


# Context manager for manual timing
class OperationTimer:
    """
    Context manager for timing operations.
    
    Usage:
        with OperationTimer('my_operation') as timer:
            # do work
            pass
        print(f"Took {timer.elapsed}ms")
    """
    
    def __init__(self, operation_name: str, auto_record: bool = True):
        self.operation_name = operation_name
        self.auto_record = auto_record
        self.start_time = None
        self.elapsed = None
        self.success = True
    
    def __enter__(self):
        self.start_time = time.perf_counter()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.elapsed = time.perf_counter() - self.start_time
        self.success = exc_type is None
        
        if self.auto_record:
            kyber_monitor.record_manual(
                self.operation_name, 
                self.elapsed, 
                self.success
            )
        
        return False  # Don't suppress exceptions


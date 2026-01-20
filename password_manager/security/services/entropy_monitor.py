"""
Entropy Monitor
===============

Detects eavesdropping and tampering through entropy analysis.

Uses statistical methods to detect anomalies in shared randomness pools:
- Shannon entropy measurement
- KL divergence between pools
- Chi-squared randomness tests
- Continuous monitoring with alerting

If entropy drops or divergence increases, it indicates potential tampering.
"""

import math
import logging
import hashlib
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
from collections import Counter
import secrets

logger = logging.getLogger(__name__)

# Try to import scipy for advanced statistics
try:
    from scipy import stats
    from scipy.special import kl_div
    import numpy as np
    SCIPY_AVAILABLE = True
except ImportError:
    SCIPY_AVAILABLE = False
    logger.warning("scipy not available - using basic entropy calculations")


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class EntropyMeasurement:
    """Result of entropy measurement."""
    entropy_bits_per_byte: float
    sample_size: int
    measured_at: datetime = field(default_factory=datetime.utcnow)
    is_healthy: bool = True
    warning_message: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'entropy_bits_per_byte': round(self.entropy_bits_per_byte, 4),
            'sample_size': self.sample_size,
            'measured_at': self.measured_at.isoformat(),
            'is_healthy': self.is_healthy,
            'warning_message': self.warning_message,
        }


@dataclass
class AnomalyReport:
    """Report of detected anomalies."""
    has_anomaly: bool
    anomaly_type: Optional[str] = None
    severity: str = 'none'  # none, low, medium, high, critical
    kl_divergence: float = 0.0
    entropy_a: float = 0.0
    entropy_b: float = 0.0
    details: Dict[str, Any] = field(default_factory=dict)
    detected_at: datetime = field(default_factory=datetime.utcnow)
    recommendation: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'has_anomaly': self.has_anomaly,
            'anomaly_type': self.anomaly_type,
            'severity': self.severity,
            'kl_divergence': round(self.kl_divergence, 6),
            'entropy_a': round(self.entropy_a, 4),
            'entropy_b': round(self.entropy_b, 4),
            'details': self.details,
            'detected_at': self.detected_at.isoformat(),
            'recommendation': self.recommendation,
        }


@dataclass
class TamperCheckResult:
    """Result of tamper detection check."""
    is_tampered: bool
    confidence: float  # 0.0 to 1.0
    checks_passed: List[str]
    checks_failed: List[str]
    details: Dict[str, Any] = field(default_factory=dict)


# =============================================================================
# Entropy Monitor
# =============================================================================

class EntropyMonitor:
    """
    Monitors entropy of shared randomness pools to detect eavesdropping.
    
    Key concepts:
    - Ideal random data has ~8 bits of entropy per byte
    - Tampering typically reduces entropy (patterns appear)
    - KL divergence measures how different two distributions are
    - High divergence between paired pools indicates tampering
    
    Thresholds (configurable):
    - Entropy warning: < 7.5 bits/byte
    - Entropy critical: < 7.0 bits/byte
    - KL divergence warning: > 0.1
    - KL divergence critical: > 0.5
    """
    
    # Default thresholds
    DEFAULT_ENTROPY_WARNING = 7.5
    DEFAULT_ENTROPY_CRITICAL = 7.0
    DEFAULT_KL_WARNING = 0.1
    DEFAULT_KL_CRITICAL = 0.5
    
    def __init__(
        self,
        entropy_warning_threshold: float = None,
        entropy_critical_threshold: float = None,
        kl_warning_threshold: float = None,
        kl_critical_threshold: float = None,
    ):
        """
        Initialize entropy monitor with thresholds.
        
        Args:
            entropy_warning_threshold: Entropy level for warning (bits/byte)
            entropy_critical_threshold: Entropy level for critical alert
            kl_warning_threshold: KL divergence for warning
            kl_critical_threshold: KL divergence for critical alert
        """
        self.entropy_warning = entropy_warning_threshold or self.DEFAULT_ENTROPY_WARNING
        self.entropy_critical = entropy_critical_threshold or self.DEFAULT_ENTROPY_CRITICAL
        self.kl_warning = kl_warning_threshold or self.DEFAULT_KL_WARNING
        self.kl_critical = kl_critical_threshold or self.DEFAULT_KL_CRITICAL
        
        self.scipy_available = SCIPY_AVAILABLE
        
        logger.info(f"EntropyMonitor initialized (scipy: {self.scipy_available})")
    
    def measure_pool_entropy(self, pool: bytes) -> EntropyMeasurement:
        """
        Measure the entropy of a randomness pool.
        
        Uses Shannon entropy formula:
        H = -Σ p(x) * log2(p(x))
        
        For ideal random data, H ≈ 8 bits/byte.
        
        Args:
            pool: Bytes to measure
            
        Returns:
            EntropyMeasurement with entropy value and health status
        """
        if not pool or len(pool) < 32:
            return EntropyMeasurement(
                entropy_bits_per_byte=0.0,
                sample_size=len(pool) if pool else 0,
                is_healthy=False,
                warning_message="Pool too small for reliable entropy measurement",
            )
        
        # Count byte frequencies
        byte_counts = Counter(pool)
        total_bytes = len(pool)
        
        # Calculate Shannon entropy
        entropy = 0.0
        for count in byte_counts.values():
            if count > 0:
                probability = count / total_bytes
                entropy -= probability * math.log2(probability)
        
        # Determine health status
        is_healthy = entropy >= self.entropy_warning
        warning = None
        
        if entropy < self.entropy_critical:
            warning = f"CRITICAL: Entropy {entropy:.2f} below threshold {self.entropy_critical}"
            logger.error(warning)
        elif entropy < self.entropy_warning:
            warning = f"WARNING: Entropy {entropy:.2f} below threshold {self.entropy_warning}"
            logger.warning(warning)
        
        return EntropyMeasurement(
            entropy_bits_per_byte=entropy,
            sample_size=total_bytes,
            is_healthy=is_healthy,
            warning_message=warning,
        )
    
    def calculate_divergence(
        self,
        pool_a: bytes,
        pool_b: bytes
    ) -> float:
        """
        Calculate KL divergence between two pools.
        
        KL divergence measures how different distribution P is from Q.
        For identical pools, KL ≈ 0.
        For tampered pools, KL increases significantly.
        
        Args:
            pool_a: First pool bytes
            pool_b: Second pool bytes
            
        Returns:
            KL divergence value (0 = identical, higher = more different)
        """
        if not pool_a or not pool_b:
            return float('inf')
        
        # Get byte frequency distributions
        dist_a = self._get_byte_distribution(pool_a)
        dist_b = self._get_byte_distribution(pool_b)
        
        if self.scipy_available:
            return self._kl_divergence_scipy(dist_a, dist_b)
        else:
            return self._kl_divergence_basic(dist_a, dist_b)
    
    def _get_byte_distribution(self, data: bytes) -> List[float]:
        """Convert bytes to probability distribution over 256 values."""
        counts = Counter(data)
        total = len(data)
        
        # Create distribution for all 256 possible byte values
        # Add small epsilon to avoid log(0)
        epsilon = 1e-10
        distribution = [(counts.get(i, 0) + epsilon) / (total + 256 * epsilon) 
                       for i in range(256)]
        
        return distribution
    
    def _kl_divergence_scipy(
        self,
        p: List[float],
        q: List[float]
    ) -> float:
        """Calculate KL divergence using scipy."""
        p_arr = np.array(p)
        q_arr = np.array(q)
        
        # Symmetric KL divergence (Jensen-Shannon would be even better)
        kl_pq = np.sum(kl_div(p_arr, q_arr))
        kl_qp = np.sum(kl_div(q_arr, p_arr))
        
        return (kl_pq + kl_qp) / 2
    
    def _kl_divergence_basic(
        self,
        p: List[float],
        q: List[float]
    ) -> float:
        """Calculate KL divergence without scipy."""
        divergence = 0.0
        
        for p_i, q_i in zip(p, q):
            if p_i > 0 and q_i > 0:
                divergence += p_i * math.log(p_i / q_i)
        
        return divergence
    
    def detect_anomalies(
        self,
        pool_a: bytes,
        pool_b: bytes
    ) -> AnomalyReport:
        """
        Detect anomalies between two paired pools.
        
        Checks:
        1. Entropy of each pool
        2. KL divergence between pools
        3. Statistical randomness tests
        
        Args:
            pool_a: First device's pool
            pool_b: Second device's pool
            
        Returns:
            AnomalyReport with findings
        """
        anomalies = []
        severity = 'none'
        details = {}
        
        # 1. Measure entropy of each pool
        entropy_a = self.measure_pool_entropy(pool_a)
        entropy_b = self.measure_pool_entropy(pool_b)
        
        details['entropy_a'] = entropy_a.to_dict()
        details['entropy_b'] = entropy_b.to_dict()
        
        # Check entropy thresholds
        for label, measurement in [('pool_a', entropy_a), ('pool_b', entropy_b)]:
            if measurement.entropy_bits_per_byte < self.entropy_critical:
                anomalies.append(f"{label}_low_entropy_critical")
                severity = 'critical'
            elif measurement.entropy_bits_per_byte < self.entropy_warning:
                anomalies.append(f"{label}_low_entropy_warning")
                if severity not in ['critical', 'high']:
                    severity = 'medium'
        
        # 2. Calculate KL divergence
        kl_div_value = self.calculate_divergence(pool_a, pool_b)
        details['kl_divergence'] = kl_div_value
        
        if kl_div_value > self.kl_critical:
            anomalies.append('high_divergence_critical')
            severity = 'critical'
        elif kl_div_value > self.kl_warning:
            anomalies.append('high_divergence_warning')
            if severity not in ['critical', 'high']:
                severity = 'high'
        
        # 3. Additional randomness tests (if scipy available)
        if self.scipy_available:
            chi2_result = self._chi_squared_test(pool_a, pool_b)
            details['chi_squared'] = chi2_result
            
            if chi2_result.get('is_anomalous', False):
                anomalies.append('chi_squared_anomaly')
                if severity not in ['critical']:
                    severity = 'high'
        
        # Build recommendation
        recommendation = self._build_recommendation(anomalies, severity)
        
        has_anomaly = len(anomalies) > 0
        
        if has_anomaly:
            logger.warning(
                f"Entropy anomaly detected: {anomalies}, severity: {severity}"
            )
        
        return AnomalyReport(
            has_anomaly=has_anomaly,
            anomaly_type=','.join(anomalies) if anomalies else None,
            severity=severity,
            kl_divergence=kl_div_value,
            entropy_a=entropy_a.entropy_bits_per_byte,
            entropy_b=entropy_b.entropy_bits_per_byte,
            details=details,
            recommendation=recommendation,
        )
    
    def _chi_squared_test(
        self,
        pool_a: bytes,
        pool_b: bytes
    ) -> Dict[str, Any]:
        """Perform chi-squared test on byte distributions."""
        if not self.scipy_available:
            return {'available': False}
        
        # Get observed frequencies
        counts_a = np.array([Counter(pool_a).get(i, 0) for i in range(256)])
        counts_b = np.array([Counter(pool_b).get(i, 0) for i in range(256)])
        
        # Expected uniform distribution
        expected_a = len(pool_a) / 256
        expected_b = len(pool_b) / 256
        
        # Chi-squared test
        chi2_a, p_value_a = stats.chisquare(counts_a + 1, expected_a + 1)
        chi2_b, p_value_b = stats.chisquare(counts_b + 1, expected_b + 1)
        
        # Very low p-value indicates non-random (anomalous)
        is_anomalous = p_value_a < 0.01 or p_value_b < 0.01
        
        return {
            'available': True,
            'chi2_a': float(chi2_a),
            'chi2_b': float(chi2_b),
            'p_value_a': float(p_value_a),
            'p_value_b': float(p_value_b),
            'is_anomalous': is_anomalous,
        }
    
    def _build_recommendation(
        self,
        anomalies: List[str],
        severity: str
    ) -> str:
        """Build recommendation based on anomalies."""
        if not anomalies:
            return "No action required - pools are healthy"
        
        if severity == 'critical':
            return "IMMEDIATE ACTION: Revoke entanglement and re-establish pairing"
        elif severity == 'high':
            return "Rotate keys immediately and monitor closely"
        elif severity == 'medium':
            return "Schedule key rotation within 24 hours"
        else:
            return "Monitor situation and consider preventive rotation"
    
    def is_tampered(self, pool: bytes) -> TamperCheckResult:
        """
        Check if a pool shows signs of tampering.
        
        Performs multiple tests:
        1. Entropy check
        2. Byte distribution uniformity
        3. Sequential correlation check
        
        Args:
            pool: Pool to check
            
        Returns:
            TamperCheckResult with analysis
        """
        checks_passed = []
        checks_failed = []
        details = {}
        
        # 1. Entropy check
        entropy = self.measure_pool_entropy(pool)
        details['entropy'] = entropy.to_dict()
        
        if entropy.is_healthy:
            checks_passed.append('entropy')
        else:
            checks_failed.append('entropy')
        
        # 2. Distribution uniformity
        uniformity = self._check_uniformity(pool)
        details['uniformity'] = uniformity
        
        if uniformity['is_uniform']:
            checks_passed.append('uniformity')
        else:
            checks_failed.append('uniformity')
        
        # 3. Sequential correlation
        correlation = self._check_sequential_correlation(pool)
        details['correlation'] = correlation
        
        if not correlation['has_correlation']:
            checks_passed.append('no_correlation')
        else:
            checks_failed.append('sequential_correlation')
        
        # Determine tampering probability
        total_checks = len(checks_passed) + len(checks_failed)
        failed_ratio = len(checks_failed) / total_checks if total_checks > 0 else 0
        
        is_tampered = failed_ratio > 0.33  # More than 1/3 checks failed
        confidence = 1.0 - (len(checks_passed) / total_checks) if total_checks > 0 else 0
        
        if is_tampered:
            logger.warning(f"Pool tampering detected with {confidence:.2%} confidence")
        
        return TamperCheckResult(
            is_tampered=is_tampered,
            confidence=confidence,
            checks_passed=checks_passed,
            checks_failed=checks_failed,
            details=details,
        )
    
    def _check_uniformity(self, pool: bytes) -> Dict[str, Any]:
        """Check if byte distribution is approximately uniform."""
        if len(pool) < 256:
            return {'is_uniform': True, 'reason': 'pool_too_small'}
        
        counts = Counter(pool)
        expected = len(pool) / 256
        
        # Check if any byte is significantly over/under-represented
        max_deviation = max(abs(counts.get(i, 0) - expected) for i in range(256))
        max_allowed = expected * 0.5  # 50% deviation threshold
        
        is_uniform = max_deviation < max_allowed
        
        return {
            'is_uniform': is_uniform,
            'max_deviation': max_deviation,
            'max_allowed': max_allowed,
            'unique_bytes': len(counts),
        }
    
    def _check_sequential_correlation(self, pool: bytes) -> Dict[str, Any]:
        """Check for sequential correlation between consecutive bytes."""
        if len(pool) < 100:
            return {'has_correlation': False, 'reason': 'pool_too_small'}
        
        # Count runs of identical bytes
        run_lengths = []
        current_run = 1
        
        for i in range(1, len(pool)):
            if pool[i] == pool[i-1]:
                current_run += 1
            else:
                run_lengths.append(current_run)
                current_run = 1
        run_lengths.append(current_run)
        
        # For random data, runs should be mostly length 1
        long_runs = sum(1 for r in run_lengths if r > 3)
        long_run_ratio = long_runs / len(run_lengths) if run_lengths else 0
        
        # More than 5% long runs suggests correlation
        has_correlation = long_run_ratio > 0.05
        
        return {
            'has_correlation': has_correlation,
            'long_run_count': long_runs,
            'long_run_ratio': long_run_ratio,
            'total_runs': len(run_lengths),
        }
    
    def trigger_alert(
        self,
        pair_id: str,
        anomaly_type: str,
        severity: str
    ) -> None:
        """
        Trigger an alert for detected anomaly.
        
        In production, this would:
        - Create SecurityAlert in database
        - Send push notification to user
        - Log to security audit trail
        - Potentially trigger auto-revocation
        
        Args:
            pair_id: Affected entangled pair ID
            anomaly_type: Type of anomaly detected
            severity: Severity level
        """
        logger.warning(
            f"ENTROPY ALERT: pair={pair_id}, type={anomaly_type}, severity={severity}"
        )
        
        # Import here to avoid circular imports
        try:
            from security.models import EntanglementSyncEvent, EntangledDevicePair
            from django.utils import timezone
            
            pair = EntangledDevicePair.objects.filter(id=pair_id).first()
            if pair:
                EntanglementSyncEvent.objects.create(
                    pair=pair,
                    event_type='anomaly_detected',
                    success=False,
                    details={
                        'anomaly_type': anomaly_type,
                        'severity': severity,
                        'triggered_at': timezone.now().isoformat(),
                    }
                )
                logger.info(f"Created EntanglementSyncEvent for anomaly on pair {pair_id}")
        except Exception as e:
            logger.error(f"Failed to create alert event: {e}")


# =============================================================================
# Singleton Instance
# =============================================================================

entropy_monitor = EntropyMonitor()

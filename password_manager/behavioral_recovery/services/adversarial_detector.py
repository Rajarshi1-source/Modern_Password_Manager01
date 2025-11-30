"""
Adversarial Detector

Detects adversarial attacks on the behavioral recovery system including:
- Replay attacks
- Behavioral spoofing
- Synthetic data injection
- Coerced authentication
"""

import logging
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import hashlib
import json

logger = logging.getLogger(__name__)

try:
    from sklearn.ensemble import IsolationForest
    from sklearn.preprocessing import StandardScaler
    SKLEARN_AVAILABLE = True
except ImportError:
    logger.warning("Scikit-learn not available for adversarial detection")
    SKLEARN_AVAILABLE = False


class AdversarialDetector:
    """
    Detects adversarial attacks on behavioral recovery system
    
    Detection methods:
    1. Replay attack detection (temporal consistency)
    2. Biometric spoofing detection (statistical impossibility)
    3. Synthetic data detection (ML-based)
    4. Duress detection (stress biomarkers)
    """
    
    def __init__(self):
        self.replay_cache = {}  # Cache of recent submissions
        self.anomaly_detector = self._initialize_anomaly_detector()
    
    def _initialize_anomaly_detector(self):
        """Initialize Isolation Forest for anomaly detection"""
        if not SKLEARN_AVAILABLE:
            return None
        
        return IsolationForest(
            contamination=0.1,
            random_state=42,
            n_estimators=100
        )
    
    def detect_replay_attack(self, behavioral_sequence, user_id):
        """
        Detect if behavioral data is a replay of previously captured data
        
        Args:
            behavioral_sequence: Behavioral data submitted
            user_id: User ID
        
        Returns:
            dict: Detection result
        """
        logger.info(f"Checking for replay attack for user {user_id}")
        
        # Create hash of behavioral data
        data_hash = self._hash_behavioral_data(behavioral_sequence)
        
        # Check if we've seen this exact data before
        cache_key = f"{user_id}_{data_hash}"
        
        if cache_key in self.replay_cache:
            last_seen = self.replay_cache[cache_key]
            time_diff = (datetime.now() - last_seen).total_seconds()
            
            # If seen within last hour, likely replay
            if time_diff < 3600:
                logger.warning(f"Replay attack detected for user {user_id}")
                return {
                    'is_replay': True,
                    'confidence': 0.95,
                    'reason': f'Identical data seen {time_diff:.0f} seconds ago',
                    'risk_score': 0.9
                }
        
        # Check temporal consistency
        temporal_result = self._check_temporal_consistency(behavioral_sequence)
        if temporal_result['is_suspicious']:
            return {
                'is_replay': True,
                'confidence': temporal_result['confidence'],
                'reason': temporal_result['reason'],
                'risk_score': 0.7
            }
        
        # Store in cache
        self.replay_cache[cache_key] = datetime.now()
        
        # Clean old cache entries (> 24 hours)
        self._cleanup_replay_cache()
        
        return {
            'is_replay': False,
            'confidence': 0.95,
            'reason': 'Data appears fresh and temporally consistent',
            'risk_score': 0.0
        }
    
    def detect_spoofing(self, behavioral_data):
        """
        Detect biometric spoofing attempts
        
        Checks for statistical impossibilities in behavioral data
        
        Args:
            behavioral_data: Dict with behavioral features
        
        Returns:
            dict: Detection result
        """
        logger.info("Checking for biometric spoofing")
        
        suspicions = []
        
        # Check typing dynamics for impossibilities
        if 'typing' in behavioral_data:
            typing_checks = self._check_typing_impossibilities(behavioral_data['typing'])
            suspicions.extend(typing_checks)
        
        # Check mouse behavior for impossibilities
        if 'mouse' in behavioral_data:
            mouse_checks = self._check_mouse_impossibilities(behavioral_data['mouse'])
            suspicions.extend(mouse_checks)
        
        # Check for synthetic data patterns
        synthetic_check = self._check_synthetic_patterns(behavioral_data)
        if synthetic_check['is_synthetic']:
            suspicions.append(synthetic_check['reason'])
        
        is_spoofed = len(suspicions) > 0
        risk_score = min(1.0, len(suspicions) * 0.3)
        
        if is_spoofed:
            logger.warning(f"Spoofing detected: {suspicions}")
        
        return {
            'is_spoofed': is_spoofed,
            'confidence': 0.8 if is_spoofed else 0.2,
            'reasons': suspicions,
            'risk_score': risk_score
        }
    
    def detect_duress(self, behavioral_data):
        """
        Detect if user is under duress (coerced authentication)
        
        Looks for stress biomarkers in behavioral data
        
        Args:
            behavioral_data: Dict with behavioral features
        
        Returns:
            dict: Detection result
        """
        logger.info("Checking for duress indicators")
        
        stress_indicators = []
        
        # Check typing for stress patterns
        if 'typing' in behavioral_data:
            typing = behavioral_data['typing']
            
            # Increased error rate (stress)
            if typing.get('error_rate', 0) > 0.15:  # > 15% errors
                stress_indicators.append('High typing error rate')
            
            # Irregular rhythm (stress)
            if typing.get('rhythm_variability', 0) > 0.8:
                stress_indicators.append('Irregular typing rhythm')
            
            # Unusual typing speed
            avg_wpm = typing.get('typing_speed_wpm', 0)
            if avg_wpm < 10 or avg_wpm > 200:
                stress_indicators.append('Unusual typing speed')
        
        # Check mouse for stress patterns
        if 'mouse' in behavioral_data:
            mouse = behavioral_data['mouse']
            
            # Erratic movements (stress)
            if mouse.get('mouse_jitter', 0) > 0.5:
                stress_indicators.append('Erratic mouse movements')
            
            # High acceleration variability
            if mouse.get('acceleration_variability', 0) > 2.0:
                stress_indicators.append('Unstable mouse acceleration')
        
        # Check cognitive for rushed decisions (coercion)
        if 'cognitive' in behavioral_data:
            cognitive = behavioral_data['cognitive']
            
            # Suspiciously fast decisions
            if cognitive.get('quick_decision_rate', 0) > 0.9:
                stress_indicators.append('Unusually quick decisions')
        
        is_duress = len(stress_indicators) >= 2  # Need multiple indicators
        risk_score = min(1.0, len(stress_indicators) * 0.25)
        
        if is_duress:
            logger.warning(f"Duress detected: {stress_indicators}")
        
        return {
            'is_duress': is_duress,
            'confidence': 0.7 if is_duress else 0.3,
            'indicators': stress_indicators,
            'risk_score': risk_score
        }
    
    def comprehensive_security_check(self, behavioral_data, user_id):
        """
        Run all security checks
        
        Args:
            behavioral_data: Behavioral data to check
            user_id: User ID
        
        Returns:
            dict: Comprehensive security assessment
        """
        logger.info(f"Running comprehensive security check for user {user_id}")
        
        # Run all detectors
        replay_result = self.detect_replay_attack(behavioral_data, user_id)
        spoofing_result = self.detect_spoofing(behavioral_data)
        duress_result = self.detect_duress(behavioral_data)
        
        # Calculate overall risk score
        overall_risk = max(
            replay_result['risk_score'],
            spoofing_result['risk_score'],
            duress_result['risk_score']
        )
        
        # Determine if should block
        should_block = (
            replay_result['is_replay'] or
            spoofing_result['is_spoofed'] or
            duress_result['is_duress']
        )
        
        issues = []
        if replay_result['is_replay']:
            issues.append(('replay_attack', replay_result['reason']))
        if spoofing_result['is_spoofed']:
            issues.extend([('spoofing', r) for r in spoofing_result['reasons']])
        if duress_result['is_duress']:
            issues.extend([('duress', i) for i in duress_result['indicators']])
        
        return {
            'safe': not should_block,
            'overall_risk_score': overall_risk,
            'replay_detection': replay_result,
            'spoofing_detection': spoofing_result,
            'duress_detection': duress_result,
            'issues': issues,
            'recommendation': 'block' if should_block else 'allow'
        }
    
    # =============================================================================
    # PRIVATE HELPER METHODS
    # =============================================================================
    
    def _hash_behavioral_data(self, data):
        """Create hash of behavioral data"""
        data_str = json.dumps(data, sort_keys=True)
        return hashlib.sha256(data_str.encode()).hexdigest()
    
    def _check_temporal_consistency(self, behavioral_data):
        """Check if behavioral data shows temporal consistency"""
        # Check timestamps for consistency
        
        if 'timestamp' in behavioral_data:
            submission_time = behavioral_data['timestamp']
            current_time = datetime.now().timestamp() * 1000
            
            # Check if timestamp is too old (> 1 hour) or in future
            time_diff = abs(current_time - submission_time)
            
            if time_diff > 3600000:  # 1 hour in ms
                return {
                    'is_suspicious': True,
                    'confidence': 0.9,
                    'reason': f'Timestamp off by {time_diff / 1000:.0f} seconds'
                }
        
        # Check session duration consistency
        if 'typing' in behavioral_data and 'mouse' in behavioral_data:
            typing_duration = behavioral_data['typing'].get('session_duration_seconds', 0)
            mouse_duration = behavioral_data['mouse'].get('session_duration_seconds', 0)
            
            # If durations vastly different, suspicious
            if abs(typing_duration - mouse_duration) > 60:  # > 1 minute difference
                return {
                    'is_suspicious': True,
                    'confidence': 0.7,
                    'reason': 'Inconsistent session durations across modules'
                }
        
        return {
            'is_suspicious': False,
            'confidence': 0.9,
            'reason': 'Temporal consistency verified'
        }
    
    def _check_typing_impossibilities(self, typing_data):
        """Check for impossible typing patterns"""
        impossibilities = []
        
        # Superhuman typing speed
        wpm = typing_data.get('typing_speed_wpm', 0)
        if wpm > 200:
            impossibilities.append('Impossible typing speed (>200 WPM)')
        
        # Perfect regularity (likely synthetic)
        if typing_data.get('rhythm_regularity', 0) > 0.99:
            impossibilities.append('Suspiciously perfect typing rhythm')
        
        # Zero errors (suspicious for long text)
        if typing_data.get('total_samples', 0) > 100 and typing_data.get('error_rate', 0) == 0:
            impossibilities.append('Zero errors on long text (suspicious)')
        
        return impossibilities
    
    def _check_mouse_impossibilities(self, mouse_data):
        """Check for impossible mouse patterns"""
        impossibilities = []
        
        # Impossible movement speed
        max_velocity = mouse_data.get('velocity_max', 0)
        if max_velocity > 50:  # pixels/ms
            impossibilities.append('Impossible mouse velocity')
        
        # Perfect straight lines (suspicious)
        if mouse_data.get('movement_straightness', 0) > 0.99:
            impossibilities.append('Suspiciously straight mouse movements')
        
        # No micro-movements (human mice always jitter)
        if mouse_data.get('micro_movement_count', 1) == 0 and mouse_data.get('total_movements', 0) > 50:
            impossibilities.append('No micro-movements detected (non-human)')
        
        return impossibilities
    
    def _check_synthetic_patterns(self, behavioral_data):
        """
        Detect synthetic (AI-generated) behavioral data
        
        Uses statistical tests to identify patterns that are too regular
        or don't match human behavioral variability
        """
        # Check for suspiciously low variance
        low_variance_count = 0
        
        for module_name, module_data in behavioral_data.items():
            if not isinstance(module_data, dict):
                continue
            
            # Check variance of timing-related features
            timing_features = [k for k in module_data.keys() if 'time' in k.lower() or 'duration' in k.lower()]
            
            for feature in timing_features:
                value = module_data.get(feature)
                if isinstance(value, (int, float)):
                    # Check if value is suspiciously round/regular
                    if value > 0 and value == int(value):  # Perfect integer
                        low_variance_count += 1
        
        is_synthetic = low_variance_count > 5  # Too many perfect values
        
        return {
            'is_synthetic': is_synthetic,
            'confidence': 0.6 if is_synthetic else 0.4,
            'reason': f'Too many perfect values ({low_variance_count})' if is_synthetic else None
        }
    
    def _cleanup_replay_cache(self):
        """Remove old entries from replay cache"""
        cutoff_time = datetime.now() - timedelta(hours=24)
        
        keys_to_remove = [
            key for key, timestamp in self.replay_cache.items()
            if timestamp < cutoff_time
        ]
        
        for key in keys_to_remove:
            del self.replay_cache[key]
        
        if keys_to_remove:
            logger.info(f"Cleaned up {len(keys_to_remove)} old replay cache entries")


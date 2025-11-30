"""
Duress Detector

Specialized module for detecting when a user is under duress or coercion
during the behavioral recovery process
"""

import logging
from typing import Dict, List
import numpy as np

logger = logging.getLogger(__name__)


class DuressDetector:
    """
    Detects stress biomarkers in behavioral data that may indicate
    the user is under duress or coercion
    
    Stress indicators:
    - Erratic typing patterns
    - Trembling mouse movements
    - Rushed decisions
    - Unusual error patterns
    """
    
    # Stress detection thresholds
    THRESHOLDS = {
        'typing_error_rate_high': 0.20,      # > 20% errors
        'typing_rhythm_irregular': 0.85,      # High variability
        'mouse_jitter_high': 0.60,            # Trembling
        'quick_decision_rate_high': 0.90,    # > 90% rushed
        'typing_speed_abnormal_low': 15,      # < 15 WPM
        'typing_speed_abnormal_high': 150,    # > 150 WPM
    }
    
    def __init__(self):
        self.stress_baseline = None
    
    def detect_stress_biomarkers(self, behavioral_data):
        """
        Analyze behavioral data for stress indicators
        
        Args:
            behavioral_data: Dict with typing, mouse, cognitive features
        
        Returns:
            dict: Stress detection results
        """
        logger.info("Analyzing behavioral data for stress biomarkers")
        
        stress_indicators = []
        stress_scores = []
        
        # Analyze typing patterns
        if 'typing' in behavioral_data:
            typing_stress = self._analyze_typing_stress(behavioral_data['typing'])
            stress_indicators.extend(typing_stress['indicators'])
            stress_scores.append(typing_stress['stress_score'])
        
        # Analyze mouse patterns
        if 'mouse' in behavioral_data:
            mouse_stress = self._analyze_mouse_stress(behavioral_data['mouse'])
            stress_indicators.extend(mouse_stress['indicators'])
            stress_scores.append(mouse_stress['stress_score'])
        
        # Analyze cognitive patterns
        if 'cognitive' in behavioral_data:
            cognitive_stress = self._analyze_cognitive_stress(behavioral_data['cognitive'])
            stress_indicators.extend(cognitive_stress['indicators'])
            stress_scores.append(cognitive_stress['stress_score'])
        
        # Overall stress assessment
        overall_stress_score = np.mean(stress_scores) if stress_scores else 0.0
        is_under_duress = overall_stress_score > 0.6 and len(stress_indicators) >= 2
        
        result = {
            'is_under_duress': is_under_duress,
            'stress_score': float(overall_stress_score),
            'confidence': 0.7 if is_under_duress else 0.3,
            'indicators': stress_indicators,
            'recommendation': 'require_additional_verification' if is_under_duress else 'proceed'
        }
        
        if is_under_duress:
            logger.warning(f"Duress detected: {stress_indicators}")
        
        return result
    
    def _analyze_typing_stress(self, typing_data):
        """Analyze typing data for stress indicators"""
        indicators = []
        stress_score = 0.0
        
        # High error rate
        error_rate = typing_data.get('error_rate', 0)
        if error_rate > self.THRESHOLDS['typing_error_rate_high']:
            indicators.append(f'High error rate ({error_rate:.1%})')
            stress_score += 0.3
        
        # Irregular rhythm
        rhythm_var = typing_data.get('rhythm_variability', 0)
        if rhythm_var > self.THRESHOLDS['typing_rhythm_irregular']:
            indicators.append('Irregular typing rhythm')
            stress_score += 0.2
        
        # Abnormal typing speed
        wpm = typing_data.get('typing_speed_wpm', 50)
        if wpm < self.THRESHOLDS['typing_speed_abnormal_low']:
            indicators.append(f'Unusually slow typing ({wpm:.0f} WPM)')
            stress_score += 0.2
        elif wpm > self.THRESHOLDS['typing_speed_abnormal_high']:
            indicators.append(f'Unusually fast typing ({wpm:.0f} WPM)')
            stress_score += 0.2
        
        # Excessive backspace usage (hesitation)
        backspace_freq = typing_data.get('backspace_frequency', 0)
        if backspace_freq > 0.25:  # > 25% backspaces
            indicators.append('Excessive hesitation/corrections')
            stress_score += 0.1
        
        return {
            'indicators': indicators,
            'stress_score': min(stress_score, 1.0)
        }
    
    def _analyze_mouse_stress(self, mouse_data):
        """Analyze mouse data for stress indicators"""
        indicators = []
        stress_score = 0.0
        
        # High jitter (trembling)
        jitter = mouse_data.get('mouse_jitter', 0)
        if jitter > self.THRESHOLDS['mouse_jitter_high']:
            indicators.append('Hand trembling detected')
            stress_score += 0.4
        
        # Erratic movements
        if mouse_data.get('movement_smoothness', 1) < 0.3:
            indicators.append('Erratic mouse movements')
            stress_score += 0.3
        
        # High acceleration variability
        accel_var = mouse_data.get('acceleration_variability', 0)
        if accel_var > 2.0:
            indicators.append('Unstable mouse control')
            stress_score += 0.2
        
        # Excessive pauses
        pause_rate = mouse_data.get('pause_frequency', 0)
        if pause_rate > 0.4:  # > 40% pauses
            indicators.append('Frequent pauses (hesitation)')
            stress_score += 0.1
        
        return {
            'indicators': indicators,
            'stress_score': min(stress_score, 1.0)
        }
    
    def _analyze_cognitive_stress(self, cognitive_data):
        """Analyze cognitive patterns for stress"""
        indicators = []
        stress_score = 0.0
        
        # Rushed decisions
        quick_rate = cognitive_data.get('quick_decision_rate', 0)
        if quick_rate > self.THRESHOLDS['quick_decision_rate_high']:
            indicators.append('Decisions made too quickly')
            stress_score += 0.3
        
        # High interaction count (nervousness)
        interactions = cognitive_data.get('total_interactions', 0)
        session_duration = cognitive_data.get('session_duration_preference', 1)
        if session_duration > 0:
            interaction_rate = interactions / session_duration
            if interaction_rate > 5:  # > 5 interactions per second
                indicators.append('Unusually high interaction rate')
                stress_score += 0.2
        
        # Low focus stability
        focus_stability = cognitive_data.get('focus_stability', 1)
        if focus_stability < 0.3:
            indicators.append('Poor focus stability')
            stress_score += 0.2
        
        return {
            'indicators': indicators,
            'stress_score': min(stress_score, 1.0)
        }


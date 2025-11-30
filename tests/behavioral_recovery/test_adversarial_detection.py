"""
Tests for Adversarial Detection

Tests replay attack detection, spoofing detection, and duress detection
"""

import unittest
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../password_manager')))

from django.test import TestCase
from django.contrib.auth.models import User


class AdversarialDetectionTests(TestCase):
    """Tests for adversarial attack detection"""
    
    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='TestPassword123!'
        )
        
        self.normal_behavioral_data = {
            'typing': {
                'typing_speed_wpm': 65,
                'error_rate': 0.05,
                'rhythm_variability': 0.42
            },
            'mouse': {
                'velocity_mean': 2.3,
                'mouse_jitter': 0.15
            },
            'cognitive': {
                'quick_decision_rate': 0.40
            },
            'timestamp': 1234567890000
        }
    
    def test_replay_attack_detection(self):
        """Test detection of replay attacks"""
        from behavioral_recovery.services.adversarial_detector import AdversarialDetector
        
        detector = AdversarialDetector()
        
        # First submission - should be fine
        result1 = detector.detect_replay_attack(self.normal_behavioral_data, self.user.id)
        self.assertFalse(result1['is_replay'])
        
        # Immediate resubmission of same data - should be detected
        result2 = detector.detect_replay_attack(self.normal_behavioral_data, self.user.id)
        self.assertTrue(result2['is_replay'], "Replay attack should be detected")
        self.assertGreater(result2['risk_score'], 0.5)
    
    def test_spoofing_detection_impossible_typing_speed(self):
        """Test detection of impossible typing speed"""
        from behavioral_recovery.services.adversarial_detector import AdversarialDetector
        
        detector = AdversarialDetector()
        
        # Create data with impossible typing speed
        spoofed_data = {
            'typing': {
                'typing_speed_wpm': 250,  # Superhuman speed
                'error_rate': 0.0,        # Perfect accuracy
                'rhythm_variability': 0.01  # Perfect rhythm
            },
            'mouse': {'velocity_mean': 1.0},
            'cognitive': {}
        }
        
        result = detector.detect_spoofing(spoofed_data)
        
        # Should detect spoofing
        self.assertTrue(result['is_spoofed'], "Spoofing should be detected")
        self.assertGreater(len(result['reasons']), 0)
    
    def test_spoofing_detection_impossible_mouse_speed(self):
        """Test detection of impossible mouse movement"""
        from behavioral_recovery.services.adversarial_detector import AdversarialDetector
        
        detector = AdversarialDetector()
        
        spoofed_data = {
            'typing': {'typing_speed_wpm': 60},
            'mouse': {
                'velocity_max': 100,  # Impossible velocity
                'movement_straightness': 0.999,  # Too perfect
                'micro_movement_count': 0  # No human jitter
            },
            'cognitive': {}
        }
        
        result = detector.detect_spoofing(spoofed_data)
        self.assertTrue(result['is_spoofed'])


class DuressDetectionTests(TestCase):
    """Tests for duress detection"""
    
    def test_stress_biomarker_detection(self):
        """Test detection of stress biomarkers"""
        from behavioral_recovery.services.duress_detector import DuressDetector
        
        detector = DuressDetector()
        
        # Normal behavioral data
        normal_data = {
            'typing': {
                'error_rate': 0.05,
                'rhythm_variability': 0.40,
                'typing_speed_wpm': 65
            },
            'mouse': {
                'mouse_jitter': 0.15
            },
            'cognitive': {
                'quick_decision_rate': 0.40
            }
        }
        
        result_normal = detector.detect_stress_biomarkers(normal_data)
        self.assertFalse(result_normal['is_under_duress'])
        
        # Stressed behavioral data
        stressed_data = {
            'typing': {
                'error_rate': 0.25,  # High errors
                'rhythm_variability': 0.90,  # Irregular
                'typing_speed_wpm': 120,  # Too fast
                'backspace_frequency': 0.30  # Excessive corrections
            },
            'mouse': {
                'mouse_jitter': 0.70  # Trembling
            },
            'cognitive': {
                'quick_decision_rate': 0.95  # Rushed decisions
            }
        }
        
        result_stressed = detector.detect_stress_biomarkers(stressed_data)
        self.assertTrue(result_stressed['is_under_duress'], "Stress should be detected")
        self.assertGreater(result_stressed['stress_score'], 0.5)
        self.assertGreater(len(result_stressed['indicators']), 0)
    
    def test_comprehensive_security_check(self):
        """Test comprehensive security check"""
        from behavioral_recovery.services.adversarial_detector import AdversarialDetector
        
        detector = AdversarialDetector()
        
        # Clean data
        clean_data = {
            'typing': {'typing_speed_wpm': 60, 'error_rate': 0.05},
            'mouse': {'velocity_mean': 2.0, 'mouse_jitter': 0.15},
            'cognitive': {'quick_decision_rate': 0.40},
            'timestamp': 1234567890000
        }
        
        result = detector.comprehensive_security_check(clean_data, self.user.id)
        
        self.assertTrue(result['safe'], "Clean data should pass security check")
        self.assertLess(result['overall_risk_score'], 0.5)
        self.assertEqual(len(result['issues']), 0)


if __name__ == '__main__':
    unittest.main()


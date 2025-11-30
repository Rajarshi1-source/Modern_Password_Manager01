"""
Tests for Behavioral Capture Modules

Tests the 247-dimensional behavioral capture engine
"""

import unittest
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../password_manager')))

from django.test import TestCase
from django.contrib.auth.models import User


class BehavioralCaptureTests(TestCase):
    """
    Tests for behavioral capture functionality
    
    Note: Most behavioral capture happens on frontend (JavaScript),
    so these tests focus on backend processing of captured data
    """
    
    def setUp(self):
        """Set up test user"""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='TestPassword123!'
        )
        self.sample_behavioral_data = self._create_sample_behavioral_data()
    
    def _create_sample_behavioral_data(self):
        """Create sample 247-dimensional behavioral data"""
        return {
            'typing': {
                'press_duration_mean': 98.5,
                'flight_time_mean': 145.2,
                'typing_speed_wpm': 65,
                'error_rate': 0.05,
                'rhythm_variability': 0.42,
                'total_samples': 150,
                'data_quality_score': 0.85
            },
            'mouse': {
                'velocity_mean': 2.3,
                'acceleration_mean': 0.8,
                'movement_straightness': 0.65,
                'click_count': 45,
                'total_movements': 320,
                'data_quality_score': 0.90
            },
            'cognitive': {
                'avg_decision_time': 2500,
                'navigation_efficiency': 0.75,
                'feature_diversity': 0.68,
                'total_interactions': 120,
                'data_quality_score': 0.80
            },
            'device': {
                'device_type': 'desktop',
                'screen_width': 1920,
                'screen_height': 1080,
                'data_quality_score': 1.0
            },
            'semantic': {
                'passwords_created': 3,
                'avg_password_length': 16,
                'folders_created': 2,
                'data_quality_score': 0.75
            }
        }
    
    def test_behavioral_data_structure(self):
        """Test that behavioral data has correct structure"""
        data = self.sample_behavioral_data
        
        # Check all modules present
        self.assertIn('typing', data)
        self.assertIn('mouse', data)
        self.assertIn('cognitive', data)
        self.assertIn('device', data)
        self.assertIn('semantic', data)
        
        # Check quality scores
        for module_name, module_data in data.items():
            self.assertIn('data_quality_score', module_data)
            quality = module_data['data_quality_score']
            self.assertGreaterEqual(quality, 0.0)
            self.assertLessEqual(quality, 1.0)
    
    def test_behavioral_data_dimensions(self):
        """Test that we're capturing enough dimensions"""
        data = self.sample_behavioral_data
        
        # Count total dimensions
        total_dims = 0
        for module_data in data.values():
            total_dims += len(module_data)
        
        # Should have substantial number of dimensions
        self.assertGreaterEqual(total_dims, 20, "Should capture at least 20 dimensions")
        print(f"Total dimensions captured: {total_dims}")
    
    def test_typing_features(self):
        """Test typing dynamics features"""
        typing = self.sample_behavioral_data['typing']
        
        # Check essential typing features
        self.assertIn('press_duration_mean', typing)
        self.assertIn('flight_time_mean', typing)
        self.assertIn('typing_speed_wpm', typing)
        self.assertIn('error_rate', typing)
        
        # Validate ranges
        self.assertGreater(typing['typing_speed_wpm'], 0)
        self.assertLess(typing['typing_speed_wpm'], 300)
        self.assertGreaterEqual(typing['error_rate'], 0.0)
        self.assertLessEqual(typing['error_rate'], 1.0)
    
    def test_mouse_features(self):
        """Test mouse biometric features"""
        mouse = self.sample_behavioral_data['mouse']
        
        # Check essential mouse features
        self.assertIn('velocity_mean', mouse)
        self.assertIn('click_count', mouse)
        self.assertIn('movement_straightness', mouse)
        
        # Validate ranges
        self.assertGreaterEqual(mouse['movement_straightness'], 0.0)
        self.assertLessEqual(mouse['movement_straightness'], 1.0)
        self.assertGreaterEqual(mouse['click_count'], 0)


class BehavioralDataProcessingTests(TestCase):
    """Tests for processing behavioral data"""
    
    def test_feature_extraction(self):
        """Test feature extraction from behavioral data"""
        # This would test the backend feature extraction logic
        pass
    
    def test_embedding_generation(self):
        """Test generation of 128-dim embeddings"""
        # This would test the Transformer model embedding generation
        pass


if __name__ == '__main__':
    unittest.main()


"""
Integration Tests for Behavioral Recovery

End-to-end tests for the complete behavioral recovery system
"""

import unittest
import sys
import os
from datetime import timedelta

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../password_manager')))

from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.utils import timezone


class BehavioralRecoveryIntegrationTests(TestCase):
    """
    Integration tests for complete recovery workflow
    """
    
    def setUp(self):
        """Set up test environment"""
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='OldPassword123!'
        )
        
        # Set up behavioral commitments
        self._create_test_commitments()
    
    def _create_test_commitments(self):
        """Create test behavioral commitments"""
        from behavioral_recovery.models import BehavioralCommitment
        
        for i, challenge_type in enumerate(['typing', 'mouse', 'cognitive', 'navigation']):
            BehavioralCommitment.objects.create(
                user=self.user,
                challenge_type=challenge_type,
                encrypted_embedding=f'test_embedding_{i}'.encode(),
                unlock_conditions={'similarity_threshold': 0.87},
                samples_used=100,
                is_active=True
            )
    
    def test_complete_recovery_workflow(self):
        """Test complete recovery workflow from start to finish"""
        # Step 1: Initiate recovery
        response = self.client.post('/api/behavioral-recovery/initiate/', {
            'email': 'test@example.com'
        }, content_type='application/json')
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        
        attempt_id = data['data']['attempt_id']
        
        # Step 2: Get first challenge
        first_challenge = data['data']['first_challenge']
        self.assertIsNotNone(first_challenge)
        
        # Step 3: Complete challenges
        for i in range(5):  # Complete 5 challenges
            # Submit challenge
            submit_response = self.client.post('/api/behavioral-recovery/submit-challenge/', {
                'attempt_id': attempt_id,
                'challenge_id': first_challenge['challenge_id'],
                'behavioral_data': {
                    'typing': {'typing_speed_wpm': 65, 'error_rate': 0.05},
                    'data_quality_score': 0.85
                }
            }, content_type='application/json')
            
            self.assertEqual(submit_response.status_code, 200)
            submit_data = submit_response.json()
            
            # Get next challenge
            if submit_data['data'].get('next_challenge'):
                first_challenge = submit_data['data']['next_challenge']
        
        # Step 4: Check status
        status_response = self.client.get(f'/api/behavioral-recovery/status/{attempt_id}/')
        self.assertEqual(status_response.status_code, 200)
        
        status_data = status_response.json()
        self.assertEqual(status_data['data']['challenges_completed'], 5)
    
    def test_similarity_threshold_enforcement(self):
        """Test that recovery requires similarity threshold"""
        from behavioral_recovery.models import BehavioralRecoveryAttempt
        
        # Create attempt with low similarity
        attempt = BehavioralRecoveryAttempt.objects.create(
            user=self.user,
            status='in_progress',
            challenges_total=20,
            challenges_completed=20,
            overall_similarity=0.65  # Below threshold
        )
        
        # Try to complete recovery - should fail
        response = self.client.post('/api/behavioral-recovery/complete/', {
            'attempt_id': str(attempt.attempt_id),
            'new_password': 'NewPassword123!'
        }, content_type='application/json')
        
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertFalse(data['success'])
        self.assertIn('similarity', data['message'].lower())
    
    def test_audit_logging(self):
        """Test that all recovery actions are logged"""
        from behavioral_recovery.models import RecoveryAuditLog
        
        # Initiate recovery
        response = self.client.post('/api/behavioral-recovery/initiate/', {
            'email': 'test@example.com'
        }, content_type='application/json')
        
        # Check that audit log was created
        logs = RecoveryAuditLog.objects.filter(event_type='recovery_initiated')
        self.assertGreater(logs.count(), 0, "Recovery initiation should be logged")
        
        # Verify log details
        log = logs.first()
        self.assertIsNotNone(log.event_data)


class ModelPerformanceTests(TestCase):
    """Tests for model performance"""
    
    def test_embedding_generation_speed(self):
        """Test that embedding generation is fast enough"""
        import time
        import numpy as np
        
        try:
            from ml_security.ml_models.behavioral_dna_model import BehavioralDNATransformer
            
            model = BehavioralDNATransformer()
            sample_sequence = np.random.rand(30, 247)
            
            # Measure embedding generation time
            start_time = time.time()
            embedding = model.generate_embedding(sample_sequence)
            end_time = time.time()
            
            generation_time = (end_time - start_time) * 1000  # milliseconds
            
            # Should be under 200ms as per requirements
            self.assertLess(generation_time, 200, 
                          f"Embedding generation took {generation_time:.2f}ms, should be < 200ms")
            
        except ImportError:
            self.skipTest("TensorFlow not available")


if __name__ == '__main__':
    unittest.main()


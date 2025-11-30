"""
Tests for Recovery Flow

Tests the complete behavioral recovery workflow
"""

import unittest
import sys
import os
from datetime import timedelta

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../password_manager')))

from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.utils import timezone
from django.urls import reverse


class RecoveryFlowTests(TestCase):
    """Tests for behavioral recovery flow"""
    
    def setUp(self):
        """Set up test user and client"""
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='TestPassword123!'
        )
        
        # Create behavioral commitments for user
        self._setup_behavioral_commitments()
    
    def _setup_behavioral_commitments(self):
        """Create test behavioral commitments"""
        from behavioral_recovery.models import BehavioralCommitment
        import json
        
        # Create sample commitments
        for challenge_type in ['typing', 'mouse', 'cognitive', 'navigation']:
            BehavioralCommitment.objects.create(
                user=self.user,
                challenge_type=challenge_type,
                encrypted_embedding=b'dummy_encrypted_embedding',
                unlock_conditions={'similarity_threshold': 0.87},
                samples_used=100,
                is_active=True
            )
    
    def test_initiate_recovery(self):
        """Test initiating behavioral recovery"""
        response = self.client.post('/api/behavioral-recovery/initiate/', {
            'email': 'test@example.com'
        }, content_type='application/json')
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        self.assertTrue(data.get('success'))
        self.assertIn('attempt_id', data.get('data', {}))
        self.assertIn('timeline', data.get('data', {}))
        self.assertIn('first_challenge', data.get('data', {}))
    
    def test_initiate_recovery_no_commitments(self):
        """Test initiating recovery for user without commitments"""
        # Create user without commitments
        user2 = User.objects.create_user(
            username='testuser2',
            email='test2@example.com',
            password='TestPassword123!'
        )
        
        response = self.client.post('/api/behavioral-recovery/initiate/', {
            'email': 'test2@example.com'
        }, content_type='application/json')
        
        # Should fail with appropriate message
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertFalse(data.get('success'))
    
    def test_get_recovery_status(self):
        """Test getting recovery attempt status"""
        from behavioral_recovery.models import BehavioralRecoveryAttempt
        
        # Create recovery attempt
        attempt = BehavioralRecoveryAttempt.objects.create(
            user=self.user,
            current_stage='typing_challenge',
            status='in_progress',
            challenges_total=20,
            challenges_completed=5,
            expected_completion_date=timezone.now() + timedelta(days=3)
        )
        
        response = self.client.get(f'/api/behavioral-recovery/status/{attempt.attempt_id}/')
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        self.assertTrue(data.get('success'))
        self.assertEqual(data['data']['challenges_completed'], 5)
        self.assertEqual(data['data']['challenges_total'], 20)
    
    def test_submit_challenge(self):
        """Test submitting a challenge response"""
        from behavioral_recovery.models import BehavioralRecoveryAttempt, BehavioralChallenge
        
        # Create recovery attempt
        attempt = BehavioralRecoveryAttempt.objects.create(
            user=self.user,
            current_stage='typing_challenge',
            status='in_progress',
            challenges_total=20
        )
        
        # Create challenge
        challenge = BehavioralChallenge.objects.create(
            recovery_attempt=attempt,
            challenge_type='typing',
            challenge_data={'sentence': 'Test sentence'}
        )
        
        # Submit challenge response
        response = self.client.post('/api/behavioral-recovery/submit-challenge/', {
            'attempt_id': str(attempt.attempt_id),
            'challenge_id': str(challenge.challenge_id),
            'behavioral_data': self.sample_behavioral_data['typing']
        }, content_type='application/json')
        
        # Should succeed
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data.get('success'))
        
        # Check that challenge was updated
        challenge.refresh_from_db()
        self.assertIsNotNone(challenge.similarity_score)
        self.assertIsNotNone(challenge.completed_at)


class CommitmentTests(TestCase):
    """Tests for behavioral commitments"""
    
    def setUp(self):
        """Set up test user"""
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='TestPassword123!'
        )
        self.client.force_login(self.user)
    
    def test_create_commitments(self):
        """Test creating behavioral commitments"""
        from behavioral_recovery.services import CommitmentService
        
        service = CommitmentService()
        
        behavioral_profile = {
            'typing': {'data': [1, 2, 3]},
            'mouse': {'data': [4, 5, 6]},
            'cognitive': {'data': [7, 8, 9]},
            'combined_embedding': list(range(128))
        }
        
        commitments = service.create_commitments(self.user, behavioral_profile)
        
        # Should create commitments
        self.assertGreater(len(commitments), 0)
        
        # Verify commitments are saved
        from behavioral_recovery.models import BehavioralCommitment
        saved_commitments = BehavioralCommitment.objects.filter(user=self.user)
        self.assertEqual(saved_commitments.count(), len(commitments))
    
    def test_commitment_status_endpoint(self):
        """Test getting commitment status"""
        response = self.client.get('/api/behavioral-recovery/commitments/status/')
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        self.assertTrue(data.get('success'))
        # Initially no commitments
        self.assertFalse(data['data']['has_commitments'])


if __name__ == '__main__':
    unittest.main()


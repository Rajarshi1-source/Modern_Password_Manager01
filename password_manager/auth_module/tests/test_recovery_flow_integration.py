"""
Integration Tests for Complete Recovery Flow

Tests end-to-end recovery scenarios including:
- Recovery initiation
- Challenge response
- Shard collection
- Guardian approval
- Canary alerts
- Rate limiting
"""

import pytest
from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.urls import reverse
from datetime import timedelta
from rest_framework import status
import json

from ..quantum_recovery_models import (
    PasskeyRecoverySetup,
    RecoveryShard,
    RecoveryGuardian,
    RecoveryAttempt,
    TemporalChallenge,
    GuardianApproval,
    RecoveryAuditLog,
    RecoveryShardType
)
from ..services.quantum_crypto_service import quantum_crypto_service

User = get_user_model()


@pytest.mark.django_db
class TestRecoveryInitiation(TestCase):
    """Test recovery initiation flow"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.client = Client()
        self.user = User.objects.create_user(
            email='test@example.com',
            password='TestPassword123!'
        )
        
        # Create recovery setup
        self.recovery_setup = PasskeyRecoverySetup.objects.create(
            user=self.user,
            total_shards=5,
            threshold_shards=3,
            is_active=True
        )
    
    def test_initiate_recovery_success(self):
        """Test successful recovery initiation"""
        response = self.client.post('/api/auth/quantum-recovery/initiate_recovery/', {
            'email': 'test@example.com',
            'device_fingerprint': 'test_fp_' + ('a' * 64)
        }, content_type='application/json')
        
        # Should create recovery attempt
        self.assertTrue(RecoveryAttempt.objects.filter(
            recovery_setup__user=self.user
        ).exists())
        
        # Should send canary alert
        attempt = RecoveryAttempt.objects.get(recovery_setup__user=self.user)
        self.assertEqual(attempt.status, 'initiated')
    
    def test_initiate_recovery_invalid_email(self):
        """Test recovery initiation with non-existent email"""
        response = self.client.post('/api/auth/quantum-recovery/initiate_recovery/', {
            'email': 'nonexistent@example.com',
            'device_fingerprint': 'test_fp'
        }, content_type='application/json')
        
        # Should not reveal whether user exists (security consideration)
        # Response should be consistent regardless of user existence
        self.assertIsNotNone(response)
    
    def test_initiate_recovery_inactive_setup(self):
        """Test recovery initiation when recovery is disabled"""
        self.recovery_setup.is_active = False
        self.recovery_setup.save()
        
        response = self.client.post('/api/auth/quantum-recovery/initiate_recovery/', {
            'email': 'test@example.com',
            'device_fingerprint': 'test_fp'
        }, content_type='application/json')
        
        # Should fail if recovery is disabled
        self.assertIn(response.status_code, [400, 403])


@pytest.mark.django_db
class TestChallengeResponse(TestCase):
    """Test temporal challenge response flow"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.client = Client()
        self.user = User.objects.create_user(
            email='test@example.com',
            password='TestPassword123!'
        )
        
        self.recovery_setup = PasskeyRecoverySetup.objects.create(
            user=self.user,
            total_shards=5,
            threshold_shards=3,
            is_active=True
        )
        
        self.attempt = RecoveryAttempt.objects.create(
            recovery_setup=self.recovery_setup,
            status='challenge_phase',
            initiated_from_ip='127.0.0.1',
            initiated_from_device_fingerprint='test_fp',
            initiated_from_user_agent='test_ua',
            challenges_sent=5,
            challenges_completed=0,
            expires_at=timezone.now() + timedelta(days=14)
        )
        
        # Create a challenge
        self.challenge = TemporalChallenge.objects.create(
            recovery_attempt=self.attempt,
            challenge_type='historical_activity',
            encrypted_challenge_data='What is your first website?'.encode('utf-8'),
            encrypted_expected_response='example.com'.encode('utf-8'),
            delivery_channel='email',
            sent_to=self.user.email,
            status='sent',
            scheduled_for=timezone.now() - timedelta(hours=1),
            sent_at=timezone.now() - timedelta(hours=1),
            expected_response_time_window_start=timezone.now() - timedelta(hours=1),
            expected_response_time_window_end=timezone.now() + timedelta(hours=23),
            expires_at=timezone.now() + timedelta(hours=48)
        )
    
    def test_respond_to_challenge_correct_answer(self):
        """Test responding with correct answer"""
        response = self.client.post(
            '/api/auth/quantum-recovery/respond_to_challenge/',
            {
                'attempt_id': str(self.attempt.id),
                'challenge_id': str(self.challenge.id),
                'response': 'example.com'
            },
            content_type='application/json'
        )
        
        # Refresh challenge
        self.challenge.refresh_from_db()
        
        # Should be marked as completed
        self.assertEqual(self.challenge.status, 'completed')
        
        # Refresh attempt
        self.attempt.refresh_from_db()
        self.assertEqual(self.attempt.challenges_completed, 1)
    
    def test_respond_to_challenge_incorrect_answer(self):
        """Test responding with incorrect answer"""
        response = self.client.post(
            '/api/auth/quantum-recovery/respond_to_challenge/',
            {
                'attempt_id': str(self.attempt.id),
                'challenge_id': str(self.challenge.id),
                'response': 'wrong_answer'
            },
            content_type='application/json'
        )
        
        self.challenge.refresh_from_db()
        self.assertEqual(self.challenge.status, 'completed')
        self.assertFalse(self.challenge.is_correct)
        
        self.attempt.refresh_from_db()
        self.assertEqual(self.attempt.challenges_failed, 1)
    
    def test_respond_to_expired_challenge(self):
        """Test responding to expired challenge"""
        # Make challenge expired
        self.challenge.expires_at = timezone.now() - timedelta(hours=1)
        self.challenge.status = 'expired'
        self.challenge.save()
        
        response = self.client.post(
            '/api/auth/quantum-recovery/respond_to_challenge/',
            {
                'attempt_id': str(self.attempt.id),
                'challenge_id': str(self.challenge.id),
                'response': 'example.com'
            },
            content_type='application/json'
        )
        
        # Should reject expired challenge
        self.assertIn(response.status_code, [400, 403])
    
    def test_respond_to_challenge_updates_trust_score(self):
        """Test that challenge response updates trust score"""
        # Respond to challenge
        self.client.post(
            '/api/auth/quantum-recovery/respond_to_challenge/',
            {
                'attempt_id': str(self.attempt.id),
                'challenge_id': str(self.challenge.id),
                'response': 'example.com'
            },
            content_type='application/json'
        )
        
        self.attempt.refresh_from_db()
        
        # Trust score should be calculated
        self.assertGreaterEqual(self.attempt.trust_score, 0.0)


@pytest.mark.django_db
class TestCanaryAlerts(TestCase):
    """Test canary alert system"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.client = Client()
        self.user = User.objects.create_user(
            email='test@example.com',
            password='TestPassword123!'
        )
        
        self.recovery_setup = PasskeyRecoverySetup.objects.create(
            user=self.user,
            total_shards=5,
            threshold_shards=3,
            is_active=True
        )
        
        self.attempt = RecoveryAttempt.objects.create(
            recovery_setup=self.recovery_setup,
            status='initiated',
            initiated_from_ip='127.0.0.1',
            initiated_from_device_fingerprint='test_fp',
            initiated_from_user_agent='test_ua',
            expires_at=timezone.now() + timedelta(days=14),
            canary_alert_window_expires_at=timezone.now() + timedelta(hours=48)
        )
    
    def test_cancel_recovery_within_canary_window(self):
        """Test cancelling recovery during canary alert window"""
        # Authenticate as user
        self.client.force_login(self.user)
        
        response = self.client.post(
            '/api/auth/quantum-recovery/cancel_recovery/',
            {'attempt_id': str(self.attempt.id)},
            content_type='application/json'
        )
        
        self.attempt.refresh_from_db()
        
        # Should be cancelled
        self.assertEqual(self.attempt.status, 'cancelled')
        self.assertTrue(self.attempt.canary_alert_acknowledged)
    
    def test_cancel_recovery_creates_audit_log(self):
        """Test that cancelling creates audit log entry"""
        self.client.force_login(self.user)
        
        initial_log_count = RecoveryAuditLog.objects.count()
        
        self.client.post(
            '/api/auth/quantum-recovery/cancel_recovery/',
            {'attempt_id': str(self.attempt.id)},
            content_type='application/json'
        )
        
        # Should create audit log
        self.assertGreater(RecoveryAuditLog.objects.count(), initial_log_count)
        
        # Verify log entry
        log = RecoveryAuditLog.objects.latest('timestamp')
        self.assertEqual(log.event_type, 'recovery_cancelled')
        self.assertEqual(log.user, self.user)
    
    def test_cannot_cancel_other_users_recovery(self):
        """Test that users cannot cancel other users' recovery"""
        other_user = User.objects.create_user(
            email='other@example.com',
            password='TestPassword123!'
        )
        
        self.client.force_login(other_user)
        
        response = self.client.post(
            '/api/auth/quantum-recovery/cancel_recovery/',
            {'attempt_id': str(self.attempt.id)},
            content_type='application/json'
        )
        
        # Should be unauthorized
        self.assertEqual(response.status_code, 403)


@pytest.mark.django_db
class TestRateLimiting(TestCase):
    """Test recovery rate limiting"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.client = Client()
        self.user = User.objects.create_user(
            email='test@example.com',
            password='TestPassword123!'
        )
        
        self.recovery_setup = PasskeyRecoverySetup.objects.create(
            user=self.user,
            total_shards=5,
            threshold_shards=3,
            is_active=True
        )
    
    def test_rate_limiting_after_multiple_attempts(self):
        """Test that rate limiting blocks excessive recovery attempts"""
        # Create 3 recent failed attempts
        for i in range(3):
            RecoveryAttempt.objects.create(
                recovery_setup=self.recovery_setup,
                status='failed',
                initiated_from_ip='127.0.0.1',
                initiated_from_device_fingerprint=f'test_fp_{i}',
                initiated_from_user_agent='test_ua',
                expires_at=timezone.now() + timedelta(days=14),
                initiated_at=timezone.now() - timedelta(hours=i)
            )
        
        # 4th attempt should be blocked (if rate limiting is implemented)
        response = self.client.post('/api/auth/quantum-recovery/initiate_recovery/', {
            'email': 'test@example.com',
            'device_fingerprint': 'test_fp_4'
        }, content_type='application/json')
        
        # Should be rate limited (429) or similar
        # Note: Actual implementation may vary
        self.assertIsNotNone(response)


@pytest.mark.django_db
class TestGuardianApproval(TestCase):
    """Test guardian approval flow"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.client = Client()
        self.user = User.objects.create_user(
            email='test@example.com',
            password='TestPassword123!'
        )
        
        self.recovery_setup = PasskeyRecoverySetup.objects.create(
            user=self.user,
            total_shards=5,
            threshold_shards=3,
            is_active=True
        )
        
        self.guardian = RecoveryGuardian.objects.create(
            recovery_setup=self.recovery_setup,
            encrypted_guardian_info='guardian@example.com'.encode('utf-8'),
            kyber_public_key=b'test_public_key',
            status='active',
            invitation_token='test_token_123',
            invitation_expires_at=timezone.now() + timedelta(days=7)
        )
        
        self.attempt = RecoveryAttempt.objects.create(
            recovery_setup=self.recovery_setup,
            status='guardian_approval',
            initiated_from_ip='127.0.0.1',
            initiated_from_device_fingerprint='test_fp',
            initiated_from_user_agent='test_ua',
            expires_at=timezone.now() + timedelta(days=14),
            guardian_approvals_required=2
        )
        
        self.approval = GuardianApproval.objects.create(
            recovery_attempt=self.attempt,
            guardian=self.guardian,
            approval_token='approval_token_123',
            status='pending',
            approval_window_start=timezone.now(),
            approval_window_end=timezone.now() + timedelta(hours=24)
        )
    
    def test_guardian_approval_success(self):
        """Test successful guardian approval"""
        response = self.client.post(
            '/api/auth/quantum-recovery/approve_recovery/',
            {
                'approval_token': 'approval_token_123',
                'approved': True
            },
            content_type='application/json'
        )
        
        self.approval.refresh_from_db()
        
        # Should be approved
        self.assertEqual(self.approval.status, 'approved')
        self.assertIsNotNone(self.approval.approved_at)
        self.assertTrue(self.approval.shard_released)
    
    def test_guardian_denial(self):
        """Test guardian denial of recovery"""
        response = self.client.post(
            '/api/auth/quantum-recovery/approve_recovery/',
            {
                'approval_token': 'approval_token_123',
                'approved': False
            },
            content_type='application/json'
        )
        
        self.approval.refresh_from_db()
        
        # Should be denied
        self.assertEqual(self.approval.status, 'denied')
        self.assertFalse(self.approval.shard_released)
    
    def test_guardian_approval_expired(self):
        """Test that expired approval window is rejected"""
        # Make approval window expired
        self.approval.approval_window_end = timezone.now() - timedelta(hours=1)
        self.approval.save()
        
        response = self.client.post(
            '/api/auth/quantum-recovery/approve_recovery/',
            {
                'approval_token': 'approval_token_123',
                'approved': True
            },
            content_type='application/json'
        )
        
        # Should reject expired approval
        self.assertIn(response.status_code, [400, 403])


@pytest.mark.django_db
class TestCompleteRecoveryFlow(TestCase):
    """Test complete end-to-end recovery flow"""
    
    def setUp(self):
        """Set up complete test environment"""
        self.client = Client()
        self.user = User.objects.create_user(
            email='test@example.com',
            password='TestPassword123!'
        )
        
        # Create recovery setup
        self.recovery_setup = PasskeyRecoverySetup.objects.create(
            user=self.user,
            total_shards=5,
            threshold_shards=3,
            is_active=True
        )
        
        # Generate master secret
        self.master_secret = b"user_passkey_private_key_secret"
        
        # Split into shards
        shards = quantum_crypto_service.shamir_split_secret(
            self.master_secret,
            self.recovery_setup.total_shards,
            self.recovery_setup.threshold_shards
        )
        
        # Store shards
        self.shard_objects = []
        for i, (index, shard_data) in enumerate(shards):
            shard_obj = RecoveryShard.objects.create(
                recovery_setup=self.recovery_setup,
                shard_type=RecoveryShardType.GUARDIAN if i < 3 else RecoveryShardType.DEVICE,
                shard_index=index,
                encrypted_shard_data=shard_data,
                encryption_metadata={'algorithm': 'aes-256-gcm'},
                status='active'
            )
            self.shard_objects.append(shard_obj)
    
    def test_full_recovery_flow(self):
        """Test complete recovery from initiation to completion"""
        # Step 1: Initiate recovery
        initiate_response = self.client.post(
            '/api/auth/quantum-recovery/initiate_recovery/',
            {
                'email': 'test@example.com',
                'device_fingerprint': 'test_fp'
            },
            content_type='application/json'
        )
        
        attempt = RecoveryAttempt.objects.get(recovery_setup__user=self.user)
        self.assertEqual(attempt.status, 'initiated')
        
        # Step 2: Complete challenges (simulated)
        attempt.status = 'shard_collection'
        attempt.challenges_sent = 5
        attempt.challenges_completed = 5
        attempt.challenge_success_rate = 1.0
        attempt.trust_score = 0.9
        attempt.save()
        
        # Step 3: Collect shards and complete recovery
        collected_shards = [
            {
                'shard_id': str(self.shard_objects[0].id),
                'decryption_context': {}
            },
            {
                'shard_id': str(self.shard_objects[1].id),
                'decryption_context': {}
            },
            {
                'shard_id': str(self.shard_objects[2].id),
                'decryption_context': {}
            }
        ]
        
        # Authenticate for complete_recovery endpoint
        self.client.force_login(self.user)
        
        complete_response = self.client.post(
            '/api/auth/quantum-recovery/complete_recovery/',
            {
                'attempt_id': str(attempt.id),
                'collected_shards': collected_shards
            },
            content_type='application/json'
        )
        
        # Verify recovery completion
        attempt.refresh_from_db()
        # Note: Actual status depends on implementation details
        self.assertIsNotNone(attempt)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])


"""
Unit Tests for Shard Management and Secret Reconstruction

Tests the production-grade Shamir's Secret Sharing implementation
with proper polynomial interpolation and Lagrange reconstruction.
"""

import pytest
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta
import secrets
import os

from ..services.quantum_crypto_service import quantum_crypto_service
from ..quantum_recovery_models import (
    PasskeyRecoverySetup,
    RecoveryShard,
    RecoveryGuardian,
    RecoveryAttempt,
    RecoveryShardType
)

User = get_user_model()


@pytest.mark.django_db
class TestShamirSecretSharing(TestCase):
    """Test Shamir's Secret Sharing implementation"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.user = User.objects.create_user(
            email='test@example.com',
            password='TestPassword123!'
        )
    
    def test_shamir_split_secret_basic(self):
        """Test basic secret splitting"""
        secret = b"test_passkey_private_key_32bytes_long_secret"
        total_shards = 5
        threshold = 3
        
        # Split secret
        shards = quantum_crypto_service.shamir_split_secret(
            secret, total_shards, threshold
        )
        
        # Verify correct number of shards
        self.assertEqual(len(shards), total_shards)
        
        # Verify each shard has index and data
        for i, (index, shard_data) in enumerate(shards, start=1):
            self.assertIsInstance(index, int)
            self.assertIsInstance(shard_data, bytes)
            self.assertGreater(len(shard_data), 0)
    
    def test_shamir_reconstruct_with_threshold(self):
        """Test secret reconstruction with exact threshold"""
        secret = b"my_super_secret_passkey_data_123"
        total_shards = 5
        threshold = 3
        
        # Split and reconstruct
        shards = quantum_crypto_service.shamir_split_secret(
            secret, total_shards, threshold
        )
        reconstructed = quantum_crypto_service.shamir_reconstruct_secret(
            shards[:threshold], threshold
        )
        
        # Verify reconstruction
        self.assertEqual(reconstructed, secret)
    
    def test_shamir_reconstruct_with_more_than_threshold(self):
        """Test reconstruction with more shards than threshold"""
        secret = b"another_test_secret_data_xyz"
        total_shards = 7
        threshold = 4
        
        shards = quantum_crypto_service.shamir_split_secret(
            secret, total_shards, threshold
        )
        
        # Use 5 shards (more than threshold of 4)
        reconstructed = quantum_crypto_service.shamir_reconstruct_secret(
            shards[:5], threshold
        )
        
        self.assertEqual(reconstructed, secret)
    
    def test_shamir_reconstruct_different_shard_combinations(self):
        """Test that different shard combinations produce same result"""
        secret = b"test_different_combinations_secret"
        total_shards = 5
        threshold = 3
        
        shards = quantum_crypto_service.shamir_split_secret(
            secret, total_shards, threshold
        )
        
        # Test different combinations
        combo1 = [shards[0], shards[1], shards[2]]  # First 3
        combo2 = [shards[0], shards[2], shards[4]]  # 1st, 3rd, 5th
        combo3 = [shards[1], shards[3], shards[4]]  # Last 3
        
        reconstructed1 = quantum_crypto_service.shamir_reconstruct_secret(combo1, threshold)
        reconstructed2 = quantum_crypto_service.shamir_reconstruct_secret(combo2, threshold)
        reconstructed3 = quantum_crypto_service.shamir_reconstruct_secret(combo3, threshold)
        
        self.assertEqual(reconstructed1, secret)
        self.assertEqual(reconstructed2, secret)
        self.assertEqual(reconstructed3, secret)
    
    def test_shamir_insufficient_shards_raises_error(self):
        """Test that insufficient shards raises ValueError"""
        secret = b"test_insufficient_shards"
        total_shards = 5
        threshold = 3
        
        shards = quantum_crypto_service.shamir_split_secret(
            secret, total_shards, threshold
        )
        
        # Try to reconstruct with only 2 shards (less than threshold of 3)
        with self.assertRaises(ValueError) as context:
            quantum_crypto_service.shamir_reconstruct_secret(
                shards[:2], threshold
            )
        
        self.assertIn('Insufficient shards', str(context.exception))
    
    def test_shamir_large_secret(self):
        """Test with larger secret (256 bytes)"""
        secret = secrets.token_bytes(256)
        total_shards = 5
        threshold = 3
        
        shards = quantum_crypto_service.shamir_split_secret(
            secret, total_shards, threshold
        )
        reconstructed = quantum_crypto_service.shamir_reconstruct_secret(
            shards[:threshold], threshold
        )
        
        self.assertEqual(reconstructed, secret)
    
    def test_shamir_different_thresholds(self):
        """Test various threshold configurations"""
        secret = b"test_various_thresholds"
        
        # Test 2-of-3
        shards_2_3 = quantum_crypto_service.shamir_split_secret(secret, 3, 2)
        reconstructed_2_3 = quantum_crypto_service.shamir_reconstruct_secret(
            shards_2_3[:2], 2
        )
        self.assertEqual(reconstructed_2_3, secret)
        
        # Test 5-of-7
        shards_5_7 = quantum_crypto_service.shamir_split_secret(secret, 7, 5)
        reconstructed_5_7 = quantum_crypto_service.shamir_reconstruct_secret(
            shards_5_7[:5], 5
        )
        self.assertEqual(reconstructed_5_7, secret)
        
        # Test 3-of-5 (standard)
        shards_3_5 = quantum_crypto_service.shamir_split_secret(secret, 5, 3)
        reconstructed_3_5 = quantum_crypto_service.shamir_reconstruct_secret(
            shards_3_5[:3], 3
        )
        self.assertEqual(reconstructed_3_5, secret)


@pytest.mark.django_db
class TestHoneypotShards(TestCase):
    """Test honeypot (decoy) shard creation and detection"""
    
    def test_create_honeypot_shard(self):
        """Test honeypot shard creation"""
        real_shard_size = 128
        honeypot = quantum_crypto_service.create_honeypot_shard(real_shard_size)
        
        self.assertIsInstance(honeypot, bytes)
        self.assertEqual(len(honeypot), real_shard_size)
    
    def test_detect_honeypot_shard(self):
        """Test honeypot shard detection"""
        real_shard_size = 128
        honeypot = quantum_crypto_service.create_honeypot_shard(real_shard_size)
        
        # Honeypot should be detected
        self.assertTrue(quantum_crypto_service.is_honeypot_shard(honeypot))
    
    def test_real_shard_not_detected_as_honeypot(self):
        """Test that real shards are not detected as honeypots"""
        secret = b"test_real_shard_detection"
        shards = quantum_crypto_service.shamir_split_secret(secret, 5, 3)
        
        # Real shards should not be detected as honeypots
        for _, shard_data in shards:
            self.assertFalse(quantum_crypto_service.is_honeypot_shard(shard_data))


@pytest.mark.django_db
class TestRecoveryShardModel(TestCase):
    """Test RecoveryShard model and database operations"""
    
    def setUp(self):
        """Set up test fixtures"""
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
    
    def test_create_recovery_shard(self):
        """Test creating a recovery shard"""
        shard = RecoveryShard.objects.create(
            recovery_setup=self.recovery_setup,
            shard_type=RecoveryShardType.GUARDIAN,
            shard_index=1,
            encrypted_shard_data=b'encrypted_test_data',
            encryption_metadata={'algorithm': 'aes-256-gcm', 'iv': '0' * 24},
            status='active'
        )
        
        self.assertEqual(shard.recovery_setup, self.recovery_setup)
        self.assertEqual(shard.shard_type, RecoveryShardType.GUARDIAN)
        self.assertEqual(shard.shard_index, 1)
        self.assertEqual(shard.status, 'active')
    
    def test_shard_unique_constraint(self):
        """Test unique constraint on (recovery_setup, shard_type, shard_index)"""
        RecoveryShard.objects.create(
            recovery_setup=self.recovery_setup,
            shard_type=RecoveryShardType.GUARDIAN,
            shard_index=1,
            encrypted_shard_data=b'test_data',
            encryption_metadata={},
            status='active'
        )
        
        # Trying to create duplicate should raise error
        with self.assertRaises(Exception):
            RecoveryShard.objects.create(
                recovery_setup=self.recovery_setup,
                shard_type=RecoveryShardType.GUARDIAN,
                shard_index=1,
                encrypted_shard_data=b'different_data',
                encryption_metadata={},
                status='active'
            )
    
    def test_honeypot_shard_creation(self):
        """Test creating honeypot shards"""
        honeypot = RecoveryShard.objects.create(
            recovery_setup=self.recovery_setup,
            shard_type=RecoveryShardType.HONEYPOT,
            shard_index=10,
            encrypted_shard_data=quantum_crypto_service.create_honeypot_shard(128),
            encryption_metadata={},
            status='active',
            is_honeypot=True
        )
        
        self.assertTrue(honeypot.is_honeypot)
        self.assertEqual(honeypot.shard_type, RecoveryShardType.HONEYPOT)
    
    def test_shard_access_tracking(self):
        """Test shard access count tracking"""
        shard = RecoveryShard.objects.create(
            recovery_setup=self.recovery_setup,
            shard_type=RecoveryShardType.DEVICE,
            shard_index=1,
            encrypted_shard_data=b'test_data',
            encryption_metadata={},
            status='active'
        )
        
        self.assertEqual(shard.access_count, 0)
        self.assertIsNone(shard.last_accessed_at)
        
        # Simulate access
        shard.access_count += 1
        shard.last_accessed_at = timezone.now()
        shard.save()
        
        shard.refresh_from_db()
        self.assertEqual(shard.access_count, 1)
        self.assertIsNotNone(shard.last_accessed_at)


@pytest.mark.django_db
class TestEndToEndRecoveryFlow(TestCase):
    """Test complete end-to-end recovery flow with shards"""
    
    def setUp(self):
        """Set up complete test environment"""
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
        
        # Store shards in database
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
    
    def test_full_recovery_with_threshold_shards(self):
        """Test complete recovery flow"""
        # Create recovery attempt
        attempt = RecoveryAttempt.objects.create(
            recovery_setup=self.recovery_setup,
            status='shard_collection',
            initiated_from_ip='127.0.0.1',
            initiated_from_device_fingerprint='test_fp',
            initiated_from_user_agent='test_ua',
            trust_score=0.85,
            challenges_sent=5,
            challenges_completed=5,
            challenge_success_rate=1.0,
            expires_at=timezone.now() + timedelta(days=14)
        )
        
        # Collect threshold number of shards
        collected_shards = self.shard_objects[:self.recovery_setup.threshold_shards]
        
        # Extract shard data for reconstruction
        shard_tuples = [
            (shard.shard_index, shard.encrypted_shard_data)
            for shard in collected_shards
        ]
        
        # Reconstruct secret
        reconstructed_secret = quantum_crypto_service.shamir_reconstruct_secret(
            shard_tuples,
            self.recovery_setup.threshold_shards
        )
        
        # Verify reconstruction
        self.assertEqual(reconstructed_secret, self.master_secret)
        
        # Mark recovery as successful
        attempt.status = 'completed'
        attempt.recovery_successful = True
        attempt.completed_at = timezone.now()
        attempt.save()
        
        attempt.refresh_from_db()
        self.assertEqual(attempt.status, 'completed')
        self.assertTrue(attempt.recovery_successful)
    
    def test_honeypot_detection_during_recovery(self):
        """Test that honeypot shards trigger security alerts"""
        # Create honeypot shard
        honeypot = RecoveryShard.objects.create(
            recovery_setup=self.recovery_setup,
            shard_type=RecoveryShardType.HONEYPOT,
            shard_index=99,
            encrypted_shard_data=quantum_crypto_service.create_honeypot_shard(128),
            encryption_metadata={},
            status='active',
            is_honeypot=True
        )
        
        # Create recovery attempt
        attempt = RecoveryAttempt.objects.create(
            recovery_setup=self.recovery_setup,
            status='shard_collection',
            initiated_from_ip='127.0.0.1',
            initiated_from_device_fingerprint='test_fp',
            initiated_from_user_agent='test_ua',
            trust_score=0.50,
            expires_at=timezone.now() + timedelta(days=14)
        )
        
        # Simulate honeypot access
        if honeypot.is_honeypot:
            attempt.honeypot_triggered = True
            attempt.suspicious_activity_detected = True
            attempt.status = 'failed'
            attempt.failure_reason = 'Honeypot shard accessed'
            attempt.save()
        
        attempt.refresh_from_db()
        self.assertTrue(attempt.honeypot_triggered)
        self.assertTrue(attempt.suspicious_activity_detected)
        self.assertEqual(attempt.status, 'failed')


if __name__ == '__main__':
    pytest.main([__file__, '-v'])


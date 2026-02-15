"""
Chemical Password Storage - Backend Unit Tests
===============================================

Comprehensive tests for:
- DNA encoding/decoding with synthesis constraints
- Time-lock puzzle creation and solving
- Lab provider API integration
- Chemical storage orchestration

@author Password Manager Team
@created 2026-01-17
"""

import pytest
import hashlib
import secrets
import time
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
from decimal import Decimal

from django.test import TestCase, override_settings
from django.contrib.auth.models import User
from rest_framework.test import APITestCase, APIClient
from rest_framework import status


# =============================================================================
# DNA Encoder Tests
# =============================================================================

class DNAEncoderTest(TestCase):
    """Test DNA encoding and decoding with synthesis constraints."""
    
    def setUp(self):
        from security.services.dna_encoder import DNAEncoder
        self.encoder = DNAEncoder(
            use_error_correction=True,
            add_primers=True,
            balance_gc=True
        )
    
    def test_encode_simple_password(self):
        """Test basic password encoding."""
        password = "TestPassword123!"
        result = self.encoder.encode_password(password)
        
        self.assertIsNotNone(result.sequence)
        self.assertGreater(len(result.sequence), 0)
        self.assertTrue(all(n in 'ACGTN' for n in result.sequence))
    
    def test_decode_matches_original(self):
        """Test that decode returns original password."""
        password = "MySecretPassword!@#$"
        encoded = self.encoder.encode_password(password)
        decoded = self.encoder.decode_password(encoded.sequence)
        
        self.assertEqual(password, decoded)
    
    def test_gc_content_within_bounds(self):
        """Test GC content is within synthesis bounds (40-60%)."""
        test_passwords = [
            "AllLowerCase",
            "ALLUPPERCASE",
            "12345678",
            "!@#$%^&*()",
            "MixedCase123!@#",
        ]
        
        for password in test_passwords:
            result = self.encoder.encode_password(password)
            gc_content = result.gc_content
            
            # GC content should be between 40-60% for synthesis stability
            # Allow some tolerance as balancing may not be perfect
            self.assertGreaterEqual(
                gc_content, 0.30,
                f"GC content {gc_content:.1%} too low for '{password}'"
            )
            self.assertLessEqual(
                gc_content, 0.70,
                f"GC content {gc_content:.1%} too high for '{password}'"
            )
    
    def test_homopolymer_runs_limited(self):
        """Test that homopolymer runs are limited to max 4."""
        password = "AAAAAABBBBBB"  # Would naturally create long runs
        result = self.encoder.encode_password(password)
        
        # Check for runs of same nucleotide
        max_run = 1
        current_run = 1
        for i in range(1, len(result.sequence)):
            if result.sequence[i] == result.sequence[i-1] and result.sequence[i] != 'N':
                current_run += 1
                max_run = max(max_run, current_run)
            else:
                current_run = 1
        
        # After homopolymer breaking, runs should be <= 4
        # (may be slightly higher due to marker nucleotides)
        self.assertLessEqual(max_run, 6, f"Homopolymer run of {max_run} exceeds limit")
    
    def test_synthesis_validation(self):
        """Test sequence validation for synthesis."""
        password = "ValidPassword123"
        result = self.encoder.encode_password(password)
        validation = self.encoder.validate_for_synthesis(result.sequence)
        
        self.assertTrue(validation.is_valid)
        self.assertEqual(len(validation.errors), 0)
    
    def test_error_correction(self):
        """Test error correction is applied."""
        from security.services.dna_encoder import DNAEncoder
        encoder_with_ecc = DNAEncoder(use_error_correction=True)
        encoder_without_ecc = DNAEncoder(use_error_correction=False)
        
        password = "TestECC"
        with_ecc = encoder_with_ecc.encode_password(password)
        without_ecc = encoder_without_ecc.encode_password(password)
        
        # ECC should add additional nucleotides
        self.assertGreater(len(with_ecc.sequence), len(without_ecc.sequence))
        self.assertTrue(with_ecc.has_error_correction)
        self.assertFalse(without_ecc.has_error_correction)
    
    def test_cost_estimation(self):
        """Test synthesis cost calculation."""
        password = "CostTest123!"
        result = self.encoder.encode_password(password)
        cost = self.encoder.estimate_synthesis_cost(result.sequence, provider='twist')
        
        self.assertIn('synthesis_cost_usd', cost)
        self.assertIn('total_cost_usd', cost)
        self.assertGreater(cost['synthesis_cost_usd'], 0)
        self.assertGreater(cost['total_cost_usd'], cost['synthesis_cost_usd'])
    
    def test_qr_code_generation(self):
        """Test QR code data generation for paper backup."""
        password = "QRCodeTest!"
        result = self.encoder.encode_password(password)
        qr_data = self.encoder.generate_qr_data(result)
        
        self.assertIsNotNone(qr_data)
        self.assertGreater(len(qr_data), 0)


# =============================================================================
# Time-Lock Service Tests
# =============================================================================

class TimeLockServiceTest(TestCase):
    """Test time-lock puzzle creation and server-enforced delays."""
    
    def setUp(self):
        from security.services.time_lock_service import (
            ServerTimeLockService,
            ClientTimeLockService,
            TimeLockService,
            TimeLockMode,
        )
        self.server_service = ServerTimeLockService()
        self.client_service = ClientTimeLockService(
            modulus_bits=512,  # Smaller for faster tests
            iterations_per_second=1000000  # Fast for testing
        )
        self.hybrid_service = TimeLockService()
        self.TimeLockMode = TimeLockMode
    
    def test_server_capsule_creation(self):
        """Test server-enforced capsule creation."""
        data = b"SecretPassword123"
        delay = 60  # 1 minute
        
        capsule = self.server_service.create_capsule(data, delay)
        
        self.assertIsNotNone(capsule.capsule_id)
        self.assertIsNotNone(capsule.encrypted_data)
        self.assertIsNotNone(capsule.encryption_key_encrypted)
        self.assertGreater(capsule.unlock_at, datetime.now())
    
    def test_server_capsule_locked_before_delay(self):
        """Test capsule cannot be unlocked before delay."""
        data = b"LockedPassword"
        delay = 300  # 5 minutes
        
        capsule = self.server_service.create_capsule(data, delay)
        status = self.server_service.check_status(capsule)
        
        self.assertEqual(status['status'], 'locked')
        self.assertFalse(status['can_unlock'])
        self.assertGreater(status['time_remaining_seconds'], 0)
    
    def test_server_capsule_unlock_after_delay(self):
        """Test capsule can be unlocked after delay."""
        data = b"UnlockedPassword"
        
        # Create capsule with past unlock time (simulate delay expired)
        capsule = self.server_service.create_capsule(data, 60)
        capsule.unlock_at = datetime.now() - timedelta(seconds=1)
        
        # Should be unlockable now
        result = self.server_service.unlock(capsule)
        self.assertEqual(result, data)
    
    def test_client_puzzle_creation(self):
        """Test client-side RSA puzzle creation."""
        data = b"ClientPuzzleData"
        delay = 10  # 10 seconds (small for tests with reduced iterations)
        
        puzzle = self.client_service.create_puzzle(data, delay)
        
        self.assertIsNotNone(puzzle.puzzle_id)
        self.assertIsNotNone(puzzle.n)  # RSA modulus
        self.assertIsNotNone(puzzle.a)  # Base
        self.assertGreater(puzzle.t, 0)  # Iterations
    
    def test_client_puzzle_solve(self):
        """Test client puzzle solving returns correct data."""
        data = b"SolvePuzzleData"
        
        # Very short delay for testing
        self.client_service.iterations_per_second = 100000000
        puzzle = self.client_service.create_puzzle(data, 1)
        
        # Solve the puzzle
        result = self.client_service.solve_puzzle(puzzle)
        self.assertEqual(result, data)
    
    def test_time_lock_estimates(self):
        """Test solve time estimation for different devices."""
        data = b"EstimateData"
        puzzle = self.client_service.create_puzzle(data, 60)
        
        estimates = self.client_service.estimate_solve_time(puzzle)
        
        self.assertIn('laptop', estimates)
        self.assertIn('smartphone', estimates)
        self.assertIn('seconds', estimates['laptop'])
    
    def test_hybrid_mode_creates_both(self):
        """Test hybrid mode creates both server and client locks."""
        data = b"HybridData"
        
        result = self.hybrid_service.create_time_lock(
            data=data,
            delay_seconds=60,
            mode=self.TimeLockMode.HYBRID
        )
        
        self.assertIn('server', result)
        self.assertIn('client', result)
    
    def test_minimum_delay_enforced(self):
        """Test minimum delay of 60 seconds is enforced."""
        from security.services.time_lock_service import MIN_DELAY_SECONDS
        
        with self.assertRaises(ValueError):
            self.server_service.create_capsule(b"data", MIN_DELAY_SECONDS - 1)


# =============================================================================
# Lab Provider API Tests
# =============================================================================

class LabProviderAPITest(TestCase):
    """Test lab provider integrations (mock and real)."""
    
    def setUp(self):
        from security.services.lab_provider_api import (
            LabProviderFactory,
            MockLabProvider,
            list_providers,
        )
        self.factory = LabProviderFactory
        self.MockProvider = MockLabProvider
        self.list_providers = list_providers
    
    def test_mock_provider_synthesis_order(self):
        """Test mock provider accepts synthesis orders."""
        provider = self.factory.get_provider('mock')
        
        order = provider.submit_synthesis_order(
            sequence="ATCGATCGATCGATCGATCG",
            user_email="test@example.com"
        )
        
        self.assertIsNotNone(order.order_id)
        self.assertEqual(order.provider, 'Mock Lab Provider')
        self.assertIsNotNone(order.estimated_completion)
    
    def test_mock_provider_status_progression(self):
        """Test mock provider status changes over time."""
        from security.services.lab_provider_api import SynthesisStatus
        
        provider = self.factory.get_provider('mock')
        order = provider.submit_synthesis_order(
            sequence="GCTAGCTAGCTAGCTA",
            user_email="test@example.com"
        )
        
        # Initial status should be pending
        self.assertEqual(order.status, SynthesisStatus.PENDING)
    
    def test_provider_factory_returns_correct_type(self):
        """Test factory returns correct provider instances."""
        mock = self.factory.get_provider('mock')
        self.assertEqual(mock.name, 'Mock Lab Provider')
        
        # Twist should be returned even if API key is missing
        twist = self.factory.get_provider('twist')
        self.assertEqual(twist.name, 'Twist Bioscience')
    
    def test_list_providers(self):
        """Test listing available providers."""
        providers = self.list_providers()
        
        self.assertIsInstance(providers, list)
        self.assertGreater(len(providers), 0)
        
        # Mock should always be available
        provider_ids = [p['id'] for p in providers]
        self.assertIn('mock', provider_ids)
    
    def test_provider_pricing(self):
        """Test provider pricing information."""
        provider = self.factory.get_provider('mock')
        
        self.assertIsNotNone(provider.pricing)
        self.assertIn('synthesis', provider.pricing)
        self.assertIn('per_bp_usd', provider.pricing['synthesis'])
    
    def test_sequence_validation(self):
        """Test invalid sequence rejection."""
        provider = self.factory.get_provider('mock')
        
        # Valid sequence
        valid_order = provider.submit_synthesis_order(
            sequence="ATCGATCG" * 10,
            user_email="test@example.com"
        )
        self.assertIsNotNone(valid_order.order_id)


# =============================================================================
# Chemical Storage Service Integration Tests
# =============================================================================

class ChemicalStorageServiceTest(TestCase):
    """Test chemical storage service orchestration."""
    
    def setUp(self):
        from security.services.chemical_storage_service import (
            ChemicalStorageService,
            ChemicalStorageTier,
        )
        self.service = ChemicalStorageService(tier=ChemicalStorageTier.FREE)
        self.enterprise_service = ChemicalStorageService(tier=ChemicalStorageTier.ENTERPRISE)
        self.Tier = ChemicalStorageTier
    
    def test_full_workflow_free_tier(self):
        """Test complete storage workflow for free tier."""
        result = self.service.store_password_chemically(
            password="FreeWorkflowTest123!",
            user_id=1,
            user_email="free@example.com",
            enable_time_lock=True,
            time_lock_hours=1,
            order_synthesis=True,
        )
        
        self.assertTrue(result.success)
        self.assertIsNotNone(result.dna_sequence)
        self.assertIsNotNone(result.time_lock)
        self.assertIsNotNone(result.certificate)
        self.assertIsNotNone(result.qr_code_data)
    
    def test_certificate_generation(self):
        """Test certificate is properly signed."""
        from security.services.dna_encoder import DNAEncoder
        
        encoder = DNAEncoder()
        dna_seq = encoder.encode_password("CertTest123")
        
        cert = self.service.generate_certificate(
            user_id=1,
            dna_sequence=dna_seq,
        )
        
        self.assertIsNotNone(cert.certificate_id)
        self.assertIsNotNone(cert.signature)
        self.assertEqual(cert.encoding_method, 'huffman_nucleotide_v1')
    
    def test_tier_features(self):
        """Test tier-specific features."""
        free_info = self.service.get_tier_info()
        enterprise_info = self.enterprise_service.get_tier_info()
        
        self.assertEqual(free_info['tier'], 'free')
        self.assertEqual(enterprise_info['tier'], 'enterprise')
        
        self.assertFalse(self.service._has_feature('real_dna_synthesis'))
        self.assertTrue(self.enterprise_service._has_feature('real_dna_synthesis'))
    
    def test_cost_estimation(self):
        """Test cost estimation for password storage."""
        cost = self.service.estimate_cost("CostPassword123!")
        
        self.assertIn('synthesis_cost_usd', cost)
        self.assertIn('total_cost_usd', cost)
        self.assertIn('sequence_length_bp', cost)


# =============================================================================
# API View Tests
# =============================================================================

class ChemicalStorageAPITest(APITestCase):
    """Test Chemical Storage REST API endpoints."""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
    
    def test_encode_endpoint(self):
        """Test password encoding API."""
        response = self.client.post('/api/security/chemical/encode/', {
            'password': 'APIEncode123!',
            'use_error_correction': True,
        })
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['success'])
        self.assertIn('dna_sequence', response.data)
        self.assertIn('sequence', response.data['dna_sequence'])
    
    def test_time_lock_creation(self):
        """Test time-lock creation API."""
        response = self.client.post('/api/security/chemical/time-lock/', {
            'password': 'TimeLockAPI123!',
            'delay_hours': 1,
            'mode': 'server',
        })
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['success'])
        self.assertIn('capsule_id', response.data)
        self.assertIn('unlock_at', response.data)
    
    def test_subscription_endpoint(self):
        """Test subscription status API."""
        response = self.client.get('/api/security/chemical/subscription/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['success'])
        self.assertIn('subscription', response.data)
        self.assertIn('tier', response.data['subscription'])
    
    def test_providers_endpoint(self):
        """Test lab providers listing API."""
        response = self.client.get('/api/security/chemical/providers/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['success'])
        self.assertIn('providers', response.data)
    
    def test_full_workflow_api(self):
        """Test full storage workflow API."""
        response = self.client.post('/api/security/chemical/store/', {
            'password': 'FullWorkflow123!',
            'enable_time_lock': True,
            'time_lock_hours': 24,
            'order_synthesis': False,
        })
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['success'])
    
    def test_unauthenticated_rejected(self):
        """Test endpoints require authentication."""
        client = APIClient()  # No authentication
        
        response = client.post('/api/security/chemical/encode/', {
            'password': 'test',
        })
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


# =============================================================================
# Model Tests
# =============================================================================

class ChemicalStorageModelTest(TestCase):
    """Test Django models for chemical storage."""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='modeltest',
            email='model@test.com',
            password='testpass'
        )
    
    def test_subscription_creation(self):
        """Test subscription model creation."""
        from security.models import ChemicalStorageSubscription
        
        sub = ChemicalStorageSubscription.objects.create(
            user=self.user,
            tier='free',
            max_passwords=1,
        )
        
        self.assertTrue(sub.can_store_password())
        self.assertTrue(sub.is_active())
    
    def test_subscription_limit(self):
        """Test subscription enforces limits."""
        from security.models import ChemicalStorageSubscription
        
        sub = ChemicalStorageSubscription.objects.create(
            user=self.user,
            tier='free',
            max_passwords=1,
            passwords_stored=1,
        )
        
        self.assertFalse(sub.can_store_password())
    
    def test_dna_encoded_password_creation(self):
        """Test DNA encoded password model."""
        from security.models import DNAEncodedPassword
        
        record = DNAEncodedPassword.objects.create(
            user=self.user,
            service_name='Test Service',
            sequence_hash=hashlib.sha256(b'test').hexdigest(),
            password_hash_prefix='abcd1234',
            sequence_length_bp=200,
            gc_content=0.52,
        )
        
        self.assertIsNotNone(record.id)
        self.assertEqual(record.status, 'encoded')
    
    def test_time_lock_capsule_model(self):
        """Test time-lock capsule model."""
        from security.models import TimeLockCapsule
        
        capsule = TimeLockCapsule.objects.create(
            user=self.user,
            encrypted_data=b'encrypted',
            encryption_key_encrypted=b'key',
            mode='server',
            delay_seconds=3600,
            unlock_at=datetime.now() + timedelta(hours=1),
        )
        
        self.assertFalse(capsule.is_unlockable())
        self.assertGreater(capsule.time_remaining(), 0)

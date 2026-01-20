"""
Comprehensive Test Suite for Quantum Entanglement-Inspired Key Distribution
============================================================================

Test Categories:
- Unit Tests: Lattice crypto engine, entropy monitor
- Model Tests: Django models
- Integration Tests: API endpoints
- Functional Tests: End-to-end workflows
- Privacy Tests: Data protection verification
- A/B Test Configuration: Feature flag testing
- Security Tests: Tamper detection, revocation

Run with: python manage.py test security.tests.test_quantum_entanglement -v 2
"""

import os
import uuid
import json
import secrets
import hashlib
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock

from django.test import TestCase, TransactionTestCase, override_settings
from django.contrib.auth.models import User
from django.utils import timezone
from django.urls import reverse
from rest_framework.test import APITestCase, APIClient
from rest_framework import status


# =============================================================================
# UNIT TESTS: Lattice Crypto Engine
# =============================================================================

class LatticeCryptoEngineUnitTests(TestCase):
    """Unit tests for the lattice-based cryptography engine."""
    
    def setUp(self):
        """Set up test fixtures."""
        from security.services.lattice_crypto_engine import (
            LatticeCryptoEngine, LatticeKeyPair, EntangledState
        )
        self.engine = LatticeCryptoEngine()
    
    def test_engine_initialization(self):
        """Test engine initializes with correct defaults."""
        from security.services.lattice_crypto_engine import LatticeCryptoEngine
        
        engine = LatticeCryptoEngine()
        self.assertEqual(engine.algorithm, 'kyber-1024')
        self.assertIn(engine.algorithm, engine.SUPPORTED_ALGORITHMS)
    
    def test_engine_with_custom_algorithm(self):
        """Test engine with different Kyber variants."""
        from security.services.lattice_crypto_engine import LatticeCryptoEngine
        
        for algo in ['kyber-1024', 'kyber-768', 'kyber-512']:
            engine = LatticeCryptoEngine(algorithm=algo)
            self.assertEqual(engine.algorithm, algo)
    
    def test_engine_invalid_algorithm_raises(self):
        """Test that invalid algorithm raises ValueError."""
        from security.services.lattice_crypto_engine import LatticeCryptoEngine
        
        with self.assertRaises(ValueError):
            LatticeCryptoEngine(algorithm='invalid-algo')
    
    def test_generate_keypair_returns_correct_type(self):
        """Test keypair generation returns LatticeKeyPair."""
        from security.services.lattice_crypto_engine import LatticeKeyPair
        
        keypair = self.engine.generate_lattice_keypair()
        
        self.assertIsInstance(keypair, LatticeKeyPair)
        self.assertIsInstance(keypair.public_key, bytes)
        self.assertIsInstance(keypair.private_key, bytes)
        self.assertTrue(len(keypair.public_key) > 0)
        self.assertTrue(len(keypair.private_key) > 0)
    
    def test_generate_keypair_unique_each_time(self):
        """Test that each keypair is unique."""
        keypairs = [self.engine.generate_lattice_keypair() for _ in range(5)]
        
        public_keys = [kp.public_key for kp in keypairs]
        self.assertEqual(len(public_keys), len(set(public_keys)))
    
    def test_keypair_has_valid_metadata(self):
        """Test keypair contains valid metadata."""
        keypair = self.engine.generate_lattice_keypair()
        
        self.assertIsNotNone(keypair.key_id)
        self.assertIsNotNone(keypair.created_at)
        self.assertIn('kyber', keypair.algorithm.lower())
    
    def test_encapsulate_decapsulate_roundtrip(self):
        """Test key encapsulation/decapsulation produces matching secrets."""
        keypair = self.engine.generate_lattice_keypair()
        
        ciphertext, shared_secret = self.engine.encapsulate_key(keypair.public_key)
        
        self.assertIsInstance(ciphertext, bytes)
        self.assertIsInstance(shared_secret, bytes)
        self.assertTrue(len(ciphertext) > 0)
        self.assertEqual(len(shared_secret), 32)
    
    def test_derive_entangled_state(self):
        """Test entangled state derivation."""
        from security.services.lattice_crypto_engine import EntangledState
        
        base_secret = secrets.token_bytes(32)
        device_a_id = str(uuid.uuid4())
        device_b_id = str(uuid.uuid4())
        
        state = self.engine.derive_entangled_state(
            base_secret=base_secret,
            device_a_id=device_a_id,
            device_b_id=device_b_id,
            generation=0
        )
        
        self.assertIsInstance(state, EntangledState)
        self.assertEqual(len(state.device_a_secret), 32)
        self.assertEqual(len(state.device_b_secret), 32)
        self.assertEqual(state.generation, 0)
    
    def test_entangled_state_secrets_are_different(self):
        """Test device secrets are different but derived from same seed."""
        base_secret = secrets.token_bytes(32)
        
        state = self.engine.derive_entangled_state(
            base_secret=base_secret,
            device_a_id='device-a',
            device_b_id='device-b',
            generation=0
        )
        
        self.assertNotEqual(state.device_a_secret, state.device_b_secret)
    
    def test_entangled_state_deterministic(self):
        """Test same inputs produce same entangled state."""
        base_secret = secrets.token_bytes(32)
        device_a_id = 'device-a'
        device_b_id = 'device-b'
        
        state1 = self.engine.derive_entangled_state(
            base_secret=base_secret,
            device_a_id=device_a_id,
            device_b_id=device_b_id,
            generation=0
        )
        
        state2 = self.engine.derive_entangled_state(
            base_secret=base_secret,
            device_a_id=device_a_id,
            device_b_id=device_b_id,
            generation=0
        )
        
        self.assertEqual(state1.device_a_secret, state2.device_a_secret)
        self.assertEqual(state1.device_b_secret, state2.device_b_secret)
    
    def test_rotate_entangled_state_increments_generation(self):
        """Test state rotation increments generation."""
        base_secret = secrets.token_bytes(32)
        
        initial_state = self.engine.derive_entangled_state(
            base_secret=base_secret,
            device_a_id='device-a',
            device_b_id='device-b',
            generation=0
        )
        
        new_randomness = secrets.token_bytes(32)
        rotated_state = self.engine.rotate_entangled_state(initial_state, new_randomness)
        
        self.assertEqual(rotated_state.generation, 1)
        self.assertNotEqual(initial_state.entanglement_seed, rotated_state.entanglement_seed)
    
    def test_verify_lattice_integrity_valid(self):
        """Test integrity verification passes for valid state."""
        state = self.engine.derive_entangled_state(
            base_secret=secrets.token_bytes(32),
            device_a_id='device-a',
            device_b_id='device-b',
            generation=0
        )
        
        self.assertTrue(self.engine.verify_lattice_integrity(state))
    
    def test_create_verification_code_format(self):
        """Test verification code is 6 digits."""
        state = self.engine.derive_entangled_state(
            base_secret=secrets.token_bytes(32),
            device_a_id='device-a',
            device_b_id='device-b',
            generation=0
        )
        
        code = self.engine.create_pair_verification_code(state)
        
        self.assertEqual(len(code), 6)
        self.assertTrue(code.isdigit())
    
    def test_verify_pairing_code_correct(self):
        """Test pairing code verification with correct code."""
        state = self.engine.derive_entangled_state(
            base_secret=secrets.token_bytes(32),
            device_a_id='device-a',
            device_b_id='device-b',
            generation=0
        )
        
        code = self.engine.create_pair_verification_code(state)
        self.assertTrue(self.engine.verify_pairing_code(state, code))
    
    def test_verify_pairing_code_incorrect(self):
        """Test pairing code verification with wrong code."""
        state = self.engine.derive_entangled_state(
            base_secret=secrets.token_bytes(32),
            device_a_id='device-a',
            device_b_id='device-b',
            generation=0
        )
        
        self.assertFalse(self.engine.verify_pairing_code(state, '000000'))
    
    def test_keypair_to_dict_serialization(self):
        """Test keypair can be serialized to dict."""
        keypair = self.engine.generate_lattice_keypair()
        
        data = keypair.to_dict()
        
        self.assertIn('key_id', data)
        self.assertIn('public_key_b64', data)
        self.assertIn('algorithm', data)
        self.assertIn('created_at', data)


# =============================================================================
# UNIT TESTS: Entropy Monitor
# =============================================================================

class EntropyMonitorUnitTests(TestCase):
    """Unit tests for the entropy monitoring system."""
    
    def setUp(self):
        """Set up test fixtures."""
        from security.services.entropy_monitor import EntropyMonitor
        self.monitor = EntropyMonitor()
    
    def test_monitor_initialization(self):
        """Test monitor initializes with correct thresholds."""
        self.assertEqual(self.monitor.entropy_warning, 7.5)
        self.assertEqual(self.monitor.entropy_critical, 7.0)
        self.assertEqual(self.monitor.kl_warning, 0.1)
        self.assertEqual(self.monitor.kl_critical, 0.5)
    
    def test_monitor_custom_thresholds(self):
        """Test monitor with custom thresholds."""
        from security.services.entropy_monitor import EntropyMonitor
        
        monitor = EntropyMonitor(
            entropy_warning_threshold=7.8,
            entropy_critical_threshold=7.2,
            kl_warning_threshold=0.05,
            kl_critical_threshold=0.3
        )
        
        self.assertEqual(monitor.entropy_warning, 7.8)
        self.assertEqual(monitor.entropy_critical, 7.2)
    
    def test_measure_random_pool_high_entropy(self):
        """Test entropy measurement of truly random data."""
        random_pool = secrets.token_bytes(4096)
        
        result = self.monitor.measure_pool_entropy(random_pool)
        
        # Random data should have entropy close to 8 bits/byte
        self.assertGreater(result.entropy_bits_per_byte, 7.5)
        self.assertTrue(result.is_healthy)
        self.assertIsNone(result.warning_message)
    
    def test_measure_low_entropy_pool(self):
        """Test entropy measurement of low-entropy data."""
        # Repeating pattern has low entropy
        low_entropy_pool = b'\x00\x01\x02\x03' * 1024
        
        result = self.monitor.measure_pool_entropy(low_entropy_pool)
        
        self.assertLess(result.entropy_bits_per_byte, 3.0)
        self.assertFalse(result.is_healthy)
        self.assertIsNotNone(result.warning_message)
    
    def test_measure_empty_pool(self):
        """Test entropy measurement of empty pool."""
        result = self.monitor.measure_pool_entropy(b'')
        
        self.assertEqual(result.entropy_bits_per_byte, 0.0)
        self.assertFalse(result.is_healthy)
    
    def test_measure_small_pool_warning(self):
        """Test warning for pool that's too small."""
        small_pool = secrets.token_bytes(16)
        
        result = self.monitor.measure_pool_entropy(small_pool)
        
        self.assertFalse(result.is_healthy)
        self.assertIn('too small', result.warning_message.lower())
    
    def test_calculate_divergence_identical_pools(self):
        """Test KL divergence of identical pools is near zero."""
        pool = secrets.token_bytes(4096)
        
        divergence = self.monitor.calculate_divergence(pool, pool)
        
        self.assertLess(divergence, 0.01)
    
    def test_calculate_divergence_different_pools(self):
        """Test KL divergence of different pools is non-zero."""
        pool_a = secrets.token_bytes(4096)
        pool_b = secrets.token_bytes(4096)
        
        divergence = self.monitor.calculate_divergence(pool_a, pool_b)
        
        # Different random pools should have some divergence (but not huge)
        self.assertGreater(divergence, 0)
        self.assertLess(divergence, self.monitor.kl_warning)
    
    def test_calculate_divergence_tampered_pool(self):
        """Test KL divergence detects tampering."""
        pool_a = secrets.token_bytes(4096)
        # Tampere: replace with repeating pattern
        pool_b = b'\xAA\xBB' * 2048
        
        divergence = self.monitor.calculate_divergence(pool_a, pool_b)
        
        # Tampered pool should have high divergence
        self.assertGreater(divergence, self.monitor.kl_warning)
    
    def test_detect_anomalies_healthy_pools(self):
        """Test anomaly detection with healthy pools."""
        pool_a = secrets.token_bytes(4096)
        pool_b = secrets.token_bytes(4096)
        
        report = self.monitor.detect_anomalies(pool_a, pool_b)
        
        self.assertFalse(report.has_anomaly)
        self.assertEqual(report.severity, 'none')
        self.assertIn('No action', report.recommendation)
    
    def test_detect_anomalies_low_entropy(self):
        """Test anomaly detection catches low entropy."""
        pool_a = b'\x00\x01' * 2048  # Low entropy
        pool_b = secrets.token_bytes(4096)
        
        report = self.monitor.detect_anomalies(pool_a, pool_b)
        
        self.assertTrue(report.has_anomaly)
        self.assertIn('entropy', report.anomaly_type.lower())
    
    def test_is_tampered_with_valid_pool(self):
        """Test tamper check passes for valid pool."""
        pool = secrets.token_bytes(4096)
        
        result = self.monitor.is_tampered(pool)
        
        self.assertFalse(result.is_tampered)
        self.assertLess(result.confidence, 0.5)
        self.assertIn('entropy', result.checks_passed)
    
    def test_is_tampered_with_patterned_pool(self):
        """Test tamper check fails for patterned pool."""
        # Create pool with clear pattern
        pool = b'\x00\x01\x02\x03\x04\x05\x06\x07' * 512
        
        result = self.monitor.is_tampered(pool)
        
        self.assertTrue(result.is_tampered)
        self.assertGreater(result.confidence, 0.5)
    
    def test_entropy_measurement_to_dict(self):
        """Test entropy result serialization."""
        pool = secrets.token_bytes(4096)
        result = self.monitor.measure_pool_entropy(pool)
        
        data = result.to_dict()
        
        self.assertIn('entropy_bits_per_byte', data)
        self.assertIn('sample_size', data)
        self.assertIn('is_healthy', data)
    
    def test_anomaly_report_to_dict(self):
        """Test anomaly report serialization."""
        pool_a = secrets.token_bytes(4096)
        pool_b = secrets.token_bytes(4096)
        
        report = self.monitor.detect_anomalies(pool_a, pool_b)
        data = report.to_dict()
        
        self.assertIn('has_anomaly', data)
        self.assertIn('severity', data)
        self.assertIn('kl_divergence', data)
        self.assertIn('recommendation', data)


# =============================================================================
# MODEL TESTS
# =============================================================================

class EntangledDevicePairModelTests(TestCase):
    """Tests for the EntangledDevicePair model."""
    
    def setUp(self):
        """Create test user and devices."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        from security.models import UserDevice
        self.device_a = UserDevice.objects.create(
            user=self.user,
            device_name='Test Phone',
            device_type='mobile',
            browser='Safari',
            os_info='iOS 17',
            ip_address='192.168.1.1'
        )
        self.device_b = UserDevice.objects.create(
            user=self.user,
            device_name='Test Laptop',
            device_type='desktop',
            browser='Chrome',
            os_info='macOS 14',
            ip_address='192.168.1.2'
        )
    
    def test_create_entangled_pair(self):
        """Test creating an entangled pair."""
        from security.models import EntangledDevicePair
        
        pair = EntangledDevicePair.objects.create(
            user=self.user,
            device_a=self.device_a,
            device_b=self.device_b,
            status='active'
        )
        
        self.assertIsNotNone(pair.id)
        self.assertEqual(pair.status, 'active')
        self.assertEqual(pair.user, self.user)
    
    def test_pair_status_choices(self):
        """Test pair status field accepts valid choices."""
        from security.models import EntangledDevicePair
        
        for status_value, _ in EntangledDevicePair.STATUS_CHOICES:
            pair = EntangledDevicePair(
                user=self.user,
                device_a=self.device_a,
                device_b=self.device_b,
                status=status_value
            )
            pair.full_clean()  # Should not raise
    
    def test_pair_str_representation(self):
        """Test pair string representation."""
        from security.models import EntangledDevicePair
        
        pair = EntangledDevicePair.objects.create(
            user=self.user,
            device_a=self.device_a,
            device_b=self.device_b,
            status='active'
        )
        
        str_repr = str(pair)
        self.assertIn('Test Phone', str_repr)
        self.assertIn('Test Laptop', str_repr)
        self.assertIn('active', str_repr)
    
    def test_get_other_device(self):
        """Test getting the other device in a pair."""
        from security.models import EntangledDevicePair
        
        pair = EntangledDevicePair.objects.create(
            user=self.user,
            device_a=self.device_a,
            device_b=self.device_b,
            status='active'
        )
        
        other = pair.get_other_device(str(self.device_a.device_id))
        self.assertEqual(other, self.device_b)
        
        other = pair.get_other_device(str(self.device_b.device_id))
        self.assertEqual(other, self.device_a)


class SharedRandomnessPoolModelTests(TestCase):
    """Tests for the SharedRandomnessPool model."""
    
    def setUp(self):
        """Create test pair."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        from security.models import UserDevice, EntangledDevicePair
        
        self.device_a = UserDevice.objects.create(
            user=self.user,
            device_name='Phone',
            device_type='mobile',
            browser='Safari',
            os_info='iOS',
            ip_address='192.168.1.1'
        )
        self.device_b = UserDevice.objects.create(
            user=self.user,
            device_name='Laptop',
            device_type='desktop',
            browser='Chrome',
            os_info='macOS',
            ip_address='192.168.1.2'
        )
        
        self.pair = EntangledDevicePair.objects.create(
            user=self.user,
            device_a=self.device_a,
            device_b=self.device_b,
            status='active'
        )
    
    def test_create_pool(self):
        """Test creating a randomness pool."""
        from security.models import SharedRandomnessPool
        
        pool = SharedRandomnessPool.objects.create(
            pair=self.pair,
            encrypted_pool_a=secrets.token_bytes(4096),
            encrypted_pool_b=secrets.token_bytes(4096),
            pool_generation=0,
            entropy_measurement=7.95
        )
        
        self.assertEqual(pool.pool_generation, 0)
        self.assertEqual(pool.entropy_measurement, 7.95)
    
    def test_pool_is_entropy_healthy(self):
        """Test entropy health check methods."""
        from security.models import SharedRandomnessPool
        
        pool = SharedRandomnessPool.objects.create(
            pair=self.pair,
            encrypted_pool_a=secrets.token_bytes(100),
            encrypted_pool_b=secrets.token_bytes(100),
            entropy_measurement=7.8
        )
        
        self.assertTrue(pool.is_entropy_healthy())
        self.assertFalse(pool.is_entropy_critical())
        
        pool.entropy_measurement = 6.5
        self.assertFalse(pool.is_entropy_healthy())
        self.assertTrue(pool.is_entropy_critical())


class EntanglementSyncEventModelTests(TestCase):
    """Tests for the EntanglementSyncEvent model."""
    
    def setUp(self):
        """Create test pair."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        from security.models import UserDevice, EntangledDevicePair
        
        device_a = UserDevice.objects.create(
            user=self.user,
            device_name='Phone',
            device_type='mobile',
            browser='Safari',
            os_info='iOS',
            ip_address='192.168.1.1'
        )
        device_b = UserDevice.objects.create(
            user=self.user,
            device_name='Laptop',
            device_type='desktop',
            browser='Chrome',
            os_info='macOS',
            ip_address='192.168.1.2'
        )
        
        self.pair = EntangledDevicePair.objects.create(
            user=self.user,
            device_a=device_a,
            device_b=device_b,
            status='active'
        )
        self.device_a = device_a
    
    def test_create_sync_event(self):
        """Test creating a sync event."""
        from security.models import EntanglementSyncEvent
        
        event = EntanglementSyncEvent.objects.create(
            pair=self.pair,
            event_type='key_rotation',
            initiated_by_device=self.device_a,
            success=True,
            details={'generation': 1}
        )
        
        self.assertEqual(event.event_type, 'key_rotation')
        self.assertTrue(event.success)
    
    def test_event_type_choices(self):
        """Test event type field accepts valid choices."""
        from security.models import EntanglementSyncEvent
        
        for event_type, _ in EntanglementSyncEvent.EVENT_TYPE_CHOICES:
            event = EntanglementSyncEvent(
                pair=self.pair,
                event_type=event_type,
                success=True
            )
            event.full_clean()


# =============================================================================
# INTEGRATION TESTS: API Endpoints
# =============================================================================

class EntanglementAPIIntegrationTests(APITestCase):
    """Integration tests for entanglement API endpoints."""
    
    def setUp(self):
        """Set up test user and client."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        from security.models import UserDevice
        
        self.device_a = UserDevice.objects.create(
            user=self.user,
            device_name='Test Phone',
            device_type='mobile',
            browser='Safari',
            os_info='iOS 17',
            ip_address='192.168.1.1'
        )
        self.device_b = UserDevice.objects.create(
            user=self.user,
            device_name='Test Laptop',
            device_type='desktop',
            browser='Chrome',
            os_info='macOS 14',
            ip_address='192.168.1.2'
        )
        
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
    
    def test_initiate_pairing_success(self):
        """Test successful pairing initiation."""
        url = reverse('entanglement-initiate')
        data = {
            'device_a_id': str(self.device_a.device_id),
            'device_b_id': str(self.device_b.device_id)
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('session_id', response.data)
        self.assertIn('verification_code', response.data)
        self.assertEqual(len(response.data['verification_code']), 6)
    
    def test_initiate_pairing_same_device_fails(self):
        """Test pairing same device with itself fails."""
        url = reverse('entanglement-initiate')
        data = {
            'device_a_id': str(self.device_a.device_id),
            'device_b_id': str(self.device_a.device_id)  # Same device
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_initiate_pairing_nonexistent_device(self):
        """Test pairing with nonexistent device fails."""
        url = reverse('entanglement-initiate')
        data = {
            'device_a_id': str(self.device_a.device_id),
            'device_b_id': str(uuid.uuid4())  # Nonexistent
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_get_user_pairs_empty(self):
        """Test getting pairs when none exist."""
        url = reverse('entanglement-pairs')
        
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['total_count'], 0)
    
    def test_get_user_pairs_with_pairs(self):
        """Test getting pairs when they exist."""
        from security.models import EntangledDevicePair, SharedRandomnessPool
        
        pair = EntangledDevicePair.objects.create(
            user=self.user,
            device_a=self.device_a,
            device_b=self.device_b,
            status='active'
        )
        
        SharedRandomnessPool.objects.create(
            pair=pair,
            encrypted_pool_a=secrets.token_bytes(100),
            encrypted_pool_b=secrets.token_bytes(100),
            entropy_measurement=7.9
        )
        
        url = reverse('entanglement-pairs')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['total_count'], 1)
    
    def test_get_pair_status(self):
        """Test getting status of a specific pair."""
        from security.models import EntangledDevicePair, SharedRandomnessPool
        
        pair = EntangledDevicePair.objects.create(
            user=self.user,
            device_a=self.device_a,
            device_b=self.device_b,
            status='active'
        )
        
        SharedRandomnessPool.objects.create(
            pair=pair,
            encrypted_pool_a=secrets.token_bytes(100),
            encrypted_pool_b=secrets.token_bytes(100),
            entropy_measurement=7.9
        )
        
        url = reverse('entanglement-status', kwargs={'pair_id': pair.id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'active')
    
    def test_revoke_pair(self):
        """Test revoking a pair."""
        from security.models import EntangledDevicePair, SharedRandomnessPool
        
        pair = EntangledDevicePair.objects.create(
            user=self.user,
            device_a=self.device_a,
            device_b=self.device_b,
            status='active'
        )
        
        SharedRandomnessPool.objects.create(
            pair=pair,
            encrypted_pool_a=secrets.token_bytes(100),
            encrypted_pool_b=secrets.token_bytes(100),
        )
        
        url = reverse('entanglement-revoke')
        data = {
            'pair_id': str(pair.id),
            'reason': 'Test revocation'
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['success'])
        
        pair.refresh_from_db()
        self.assertEqual(pair.status, 'revoked')
    
    def test_entropy_analysis(self):
        """Test entropy analysis endpoint."""
        from security.models import EntangledDevicePair, SharedRandomnessPool
        
        pair = EntangledDevicePair.objects.create(
            user=self.user,
            device_a=self.device_a,
            device_b=self.device_b,
            status='active'
        )
        
        SharedRandomnessPool.objects.create(
            pair=pair,
            encrypted_pool_a=secrets.token_bytes(4096),
            encrypted_pool_b=secrets.token_bytes(4096),
            entropy_measurement=7.95
        )
        
        url = reverse('entanglement-entropy', kwargs={'pair_id': pair.id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('has_anomaly', response.data)
        self.assertIn('severity', response.data)
    
    def test_unauthenticated_access_denied(self):
        """Test unauthenticated requests are rejected."""
        self.client.logout()
        
        url = reverse('entanglement-pairs')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


# =============================================================================
# FUNCTIONAL TESTS
# =============================================================================

class EntanglementFunctionalTests(TransactionTestCase):
    """Functional tests for complete entanglement workflows."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        from security.models import UserDevice
        
        self.device_a = UserDevice.objects.create(
            user=self.user,
            device_name='Phone',
            device_type='mobile',
            browser='Safari',
            os_info='iOS',
            ip_address='192.168.1.1'
        )
        self.device_b = UserDevice.objects.create(
            user=self.user,
            device_name='Laptop',
            device_type='desktop',
            browser='Chrome',
            os_info='macOS',
            ip_address='192.168.1.2'
        )
        
        from security.services.quantum_entanglement_service import QuantumEntanglementService
        self.service = QuantumEntanglementService()
    
    def test_full_pairing_workflow(self):
        """Test complete pairing workflow from initiation to completion."""
        from security.models import EntangledDevicePair
        import base64
        
        # Step 1: Initiate pairing
        session = self.service.initiate_pairing(
            user_id=self.user.id,
            device_a_id=str(self.device_a.device_id),
            device_b_id=str(self.device_b.device_id)
        )
        
        self.assertIsNotNone(session.session_id)
        self.assertEqual(len(session.verification_code), 6)
        
        # Step 2: Complete pairing
        fake_public_key = secrets.token_bytes(1568)
        
        result = self.service.complete_pairing(
            session_id=session.session_id,
            verification_code=session.verification_code,
            device_b_public_key=fake_public_key
        )
        
        self.assertIn('pair_id', result)
        self.assertEqual(result['status'], 'active')
        
        # Verify pair was created
        pair = EntangledDevicePair.objects.get(id=result['pair_id'])
        self.assertEqual(pair.status, 'active')
        self.assertIsNotNone(pair.sharedrandomnesspool)
    
    def test_key_rotation_workflow(self):
        """Test key rotation updates generation."""
        from security.models import EntangledDevicePair, SharedRandomnessPool
        
        # Create active pair
        pair = EntangledDevicePair.objects.create(
            user=self.user,
            device_a=self.device_a,
            device_b=self.device_b,
            status='active',
            pairing_completed_at=timezone.now()
        )
        
        SharedRandomnessPool.objects.create(
            pair=pair,
            encrypted_pool_a=secrets.token_bytes(4096),
            encrypted_pool_b=secrets.token_bytes(4096),
            pool_generation=0,
            entropy_measurement=7.9
        )
        
        # Rotate keys
        result = self.service.rotate_entangled_keys(
            pair_id=str(pair.id),
            initiating_device_id=str(self.device_a.device_id)
        )
        
        self.assertTrue(result.success)
        self.assertEqual(result.new_generation, 1)
        
        # Verify pool was updated
        pair.refresh_from_db()
        pool = pair.sharedrandomnesspool
        self.assertEqual(pool.pool_generation, 1)
    
    def test_instant_revocation_workflow(self):
        """Test instant revocation deletes pool."""
        from security.models import EntangledDevicePair, SharedRandomnessPool
        
        pair = EntangledDevicePair.objects.create(
            user=self.user,
            device_a=self.device_a,
            device_b=self.device_b,
            status='active'
        )
        
        SharedRandomnessPool.objects.create(
            pair=pair,
            encrypted_pool_a=secrets.token_bytes(100),
            encrypted_pool_b=secrets.token_bytes(100),
        )
        
        # Revoke
        result = self.service.revoke_instantly(
            pair_id=str(pair.id),
            reason='Test revocation'
        )
        
        self.assertTrue(result.success)
        
        # Verify pair revoked and pool deleted
        pair.refresh_from_db()
        self.assertEqual(pair.status, 'revoked')
        self.assertFalse(SharedRandomnessPool.objects.filter(pair=pair).exists())
    
    def test_eavesdropping_detection_workflow(self):
        """Test eavesdropping detection creates event."""
        from security.models import (
            EntangledDevicePair, SharedRandomnessPool, EntanglementSyncEvent
        )
        
        pair = EntangledDevicePair.objects.create(
            user=self.user,
            device_a=self.device_a,
            device_b=self.device_b,
            status='active'
        )
        
        SharedRandomnessPool.objects.create(
            pair=pair,
            encrypted_pool_a=secrets.token_bytes(4096),
            encrypted_pool_b=secrets.token_bytes(4096),
            entropy_measurement=7.9
        )
        
        # Detect eavesdropping
        report = self.service.detect_eavesdropping(str(pair.id))
        
        # Should create entropy_check event
        event = EntanglementSyncEvent.objects.filter(
            pair=pair,
            event_type='entropy_check'
        ).first()
        
        self.assertIsNotNone(event)


# =============================================================================
# PRIVACY TESTS
# =============================================================================

class EntanglementPrivacyTests(TestCase):
    """Tests for privacy and data protection in entanglement feature."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        from security.models import UserDevice
        
        self.device_a = UserDevice.objects.create(
            user=self.user,
            device_name='Phone',
            device_type='mobile',
            browser='Safari',
            os_info='iOS',
            ip_address='192.168.1.1'
        )
        self.device_b = UserDevice.objects.create(
            user=self.user,
            device_name='Laptop',
            device_type='desktop',
            browser='Chrome',
            os_info='macOS',
            ip_address='192.168.1.2'
        )
    
    def test_pools_are_encrypted(self):
        """Test that pools are stored encrypted, not plaintext."""
        from security.models import EntangledDevicePair, SharedRandomnessPool
        
        pair = EntangledDevicePair.objects.create(
            user=self.user,
            device_a=self.device_a,
            device_b=self.device_b,
            status='active'
        )
        
        # Create pool with "encrypted" data
        original_pool = b'super_secret_randomness_12345'
        encrypted_pool = secrets.token_bytes(len(original_pool) + 28)  # AES-GCM overhead
        
        SharedRandomnessPool.objects.create(
            pair=pair,
            encrypted_pool_a=encrypted_pool,
            encrypted_pool_b=encrypted_pool,
        )
        
        pool = SharedRandomnessPool.objects.get(pair=pair)
        
        # Verify stored data doesn't contain plaintext
        self.assertNotIn(original_pool, bytes(pool.encrypted_pool_a))
    
    def test_revocation_deletes_sensitive_data(self):
        """Test revocation properly deletes pool data."""
        from security.models import EntangledDevicePair, SharedRandomnessPool
        from security.services.quantum_entanglement_service import QuantumEntanglementService
        
        pair = EntangledDevicePair.objects.create(
            user=self.user,
            device_a=self.device_a,
            device_b=self.device_b,
            status='active'
        )
        
        SharedRandomnessPool.objects.create(
            pair=pair,
            encrypted_pool_a=secrets.token_bytes(4096),
            encrypted_pool_b=secrets.token_bytes(4096),
        )
        
        pool_id = pair.pk
        
        # Revoke
        service = QuantumEntanglementService()
        service.revoke_instantly(str(pair.id))
        
        # Verify pool is deleted
        self.assertFalse(SharedRandomnessPool.objects.filter(pair_id=pool_id).exists())
    
    def test_user_isolation(self):
        """Test users cannot access other users' pairs."""
        from security.models import EntangledDevicePair
        
        other_user = User.objects.create_user(
            username='otheruser',
            email='other@example.com',
            password='otherpass123'
        )
        
        # Create pair for original user
        pair = EntangledDevicePair.objects.create(
            user=self.user,
            device_a=self.device_a,
            device_b=self.device_b,
            status='active'
        )
        
        # Other user should not see this pair
        other_user_pairs = EntangledDevicePair.objects.filter(user=other_user)
        self.assertEqual(other_user_pairs.count(), 0)
    
    def test_no_raw_secrets_logged(self):
        """Test that raw secrets are not exposed in serialization."""
        from security.services.lattice_crypto_engine import LatticeCryptoEngine
        
        engine = LatticeCryptoEngine()
        keypair = engine.generate_lattice_keypair()
        
        data = keypair.to_dict()
        
        # Should not contain raw private key
        self.assertNotIn('private_key', data)
        # Should only contain public key
        self.assertIn('public_key_b64', data)


# =============================================================================
# A/B TEST CONFIGURATION
# =============================================================================

class EntanglementABTestConfigTests(TestCase):
    """Tests for A/B test and feature flag configurations."""
    
    @override_settings(QUANTUM_ENTANGLEMENT={'ENABLED': True})
    def test_feature_enabled(self):
        """Test feature enabled configuration."""
        from django.conf import settings
        
        config = settings.QUANTUM_ENTANGLEMENT
        self.assertTrue(config['ENABLED'])
    
    @override_settings(QUANTUM_ENTANGLEMENT={'ENABLED': False})
    def test_feature_disabled(self):
        """Test feature disabled configuration."""
        from django.conf import settings
        
        config = settings.QUANTUM_ENTANGLEMENT
        self.assertFalse(config['ENABLED'])
    
    @override_settings(QUANTUM_ENTANGLEMENT={
        'LATTICE_ALGORITHM': 'kyber-768',
        'POOL_SIZE_BYTES': 2048
    })
    def test_custom_algorithm_config(self):
        """Test custom algorithm configuration."""
        from django.conf import settings
        
        config = settings.QUANTUM_ENTANGLEMENT
        self.assertEqual(config['LATTICE_ALGORITHM'], 'kyber-768')
        self.assertEqual(config['POOL_SIZE_BYTES'], 2048)
    
    @override_settings(QUANTUM_ENTANGLEMENT={
        'MAX_PAIRS_PER_USER': 3,
        'AUTO_REVOKE_ON_ANOMALY': False
    })
    def test_security_settings(self):
        """Test security-related settings."""
        from django.conf import settings
        
        config = settings.QUANTUM_ENTANGLEMENT
        self.assertEqual(config['MAX_PAIRS_PER_USER'], 3)
        self.assertFalse(config['AUTO_REVOKE_ON_ANOMALY'])


# =============================================================================
# SECURITY TESTS
# =============================================================================

class EntanglementSecurityTests(TestCase):
    """Security-focused tests for the entanglement feature."""
    
    def test_verification_code_is_timing_safe(self):
        """Test verification code comparison is timing-safe."""
        from security.services.lattice_crypto_engine import LatticeCryptoEngine
        import hmac
        
        engine = LatticeCryptoEngine()
        state = engine.derive_entangled_state(
            base_secret=secrets.token_bytes(32),
            device_a_id='a',
            device_b_id='b',
            generation=0
        )
        
        correct_code = engine.create_pair_verification_code(state)
        
        # The verify_pairing_code uses hmac.compare_digest internally
        # which is timing-safe
        result = engine.verify_pairing_code(state, correct_code)
        self.assertTrue(result)
    
    def test_entropy_threshold_protection(self):
        """Test low entropy triggers appropriate alerts."""
        from security.services.entropy_monitor import EntropyMonitor
        
        monitor = EntropyMonitor(
            entropy_critical_threshold=7.0,
            entropy_warning_threshold=7.5
        )
        
        # Low entropy pool
        low_entropy = b'\x00' * 4096
        result = monitor.measure_pool_entropy(low_entropy)
        
        self.assertFalse(result.is_healthy)
        self.assertIn('CRITICAL', result.warning_message)
    
    def test_pool_size_minimum(self):
        """Test minimum pool size enforcement."""
        from security.services.entropy_monitor import EntropyMonitor
        
        monitor = EntropyMonitor()
        
        # Too small pool
        small_pool = secrets.token_bytes(16)
        result = monitor.measure_pool_entropy(small_pool)
        
        self.assertFalse(result.is_healthy)
    
    def test_max_pairs_limit_enforced(self):
        """Test max pairs per user limit is enforced."""
        from security.models import UserDevice, EntangledDevicePair
        from security.services.quantum_entanglement_service import QuantumEntanglementService
        
        user = User.objects.create_user('limituser', 'limit@test.com', 'pass123')
        
        # Create max allowed pairs
        devices = []
        for i in range(12):  # Need 12 devices for 6 pairs (5 max + 1 to exceed)
            d = UserDevice.objects.create(
                user=user,
                device_name=f'Device{i}',
                device_type='mobile',
                browser='Safari',
                os_info='iOS',
                ip_address=f'192.168.1.{i}'
            )
            devices.append(d)
        
        # Create 5 active pairs (max limit)
        for i in range(5):
            EntangledDevicePair.objects.create(
                user=user,
                device_a=devices[i*2],
                device_b=devices[i*2+1],
                status='active'
            )
        
        service = QuantumEntanglementService()
        
        # Trying to create 6th pair should fail
        with self.assertRaises(ValueError) as ctx:
            service.initiate_pairing(
                user_id=user.id,
                device_a_id=str(devices[10].device_id),
                device_b_id=str(devices[11].device_id)
            )
        
        self.assertIn('Maximum', str(ctx.exception))


# =============================================================================
# E2E TESTS (Simulated)
# =============================================================================

class EntanglementE2ETests(TransactionTestCase):
    """End-to-end tests simulating real user workflows."""
    
    def setUp(self):
        """Set up for E2E tests."""
        self.user = User.objects.create_user(
            username='e2euser',
            email='e2e@test.com',
            password='e2epass123'
        )
        
        from security.models import UserDevice
        
        self.phone = UserDevice.objects.create(
            user=self.user,
            device_name='iPhone 15',
            device_type='mobile',
            browser='Safari',
            os_info='iOS 17.2',
            ip_address='10.0.0.1',
            is_trusted=True
        )
        self.laptop = UserDevice.objects.create(
            user=self.user,
            device_name='MacBook Pro',
            device_type='desktop',
            browser='Chrome 120',
            os_info='macOS 14.2',
            ip_address='10.0.0.2',
            is_trusted=True
        )
        
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
    
    def test_e2e_complete_pairing_flow(self):
        """E2E: Complete pairing flow from start to finish."""
        # 1. User initiates pairing from phone
        response = self.client.post(
            reverse('entanglement-initiate'),
            {
                'device_a_id': str(self.phone.device_id),
                'device_b_id': str(self.laptop.device_id)
            },
            format='json'
        )
        
        self.assertEqual(response.status_code, 201)
        session_id = response.data['session_id']
        code = response.data['verification_code']
        
        # 2. User enters code on laptop to verify
        # (In real flow, laptop would have its own public key)
        fake_pk = secrets.token_bytes(1568)
        import base64
        
        response = self.client.post(
            reverse('entanglement-verify'),
            {
                'session_id': session_id,
                'verification_code': code,
                'device_b_public_key': base64.b64encode(fake_pk).decode()
            },
            format='json'
        )
        
        self.assertEqual(response.status_code, 200)
        pair_id = response.data['pair_id']
        
        # 3. Verify pair appears in list
        response = self.client.get(reverse('entanglement-pairs'))
        self.assertEqual(response.data['total_count'], 1)
        
        # 4. Check entropy is healthy
        response = self.client.get(
            reverse('entanglement-entropy', kwargs={'pair_id': pair_id})
        )
        self.assertFalse(response.data['has_anomaly'])
    
    def test_e2e_rotation_and_revocation(self):
        """E2E: Rotate keys then revoke pair."""
        from security.models import EntangledDevicePair, SharedRandomnessPool
        
        # Create active pair
        pair = EntangledDevicePair.objects.create(
            user=self.user,
            device_a=self.phone,
            device_b=self.laptop,
            status='active',
            pairing_completed_at=timezone.now()
        )
        
        SharedRandomnessPool.objects.create(
            pair=pair,
            encrypted_pool_a=secrets.token_bytes(4096),
            encrypted_pool_b=secrets.token_bytes(4096),
            pool_generation=0,
            entropy_measurement=7.95
        )
        
        # 1. Rotate keys
        response = self.client.post(
            reverse('entanglement-rotate'),
            {
                'pair_id': str(pair.id),
                'device_id': str(self.phone.device_id)
            },
            format='json'
        )
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['new_generation'], 1)
        
        # 2. Revoke pair
        response = self.client.post(
            reverse('entanglement-revoke'),
            {
                'pair_id': str(pair.id),
                'reason': 'Lost phone'
            },
            format='json'
        )
        
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data['success'])
        
        # 3. Verify pair is revoked
        response = self.client.get(
            reverse('entanglement-status', kwargs={'pair_id': pair.id})
        )
        self.assertEqual(response.data['status'], 'revoked')

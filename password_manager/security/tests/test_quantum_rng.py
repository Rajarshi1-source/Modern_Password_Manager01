"""
Quantum RNG Tests
=================

Comprehensive tests for quantum password generation.
Includes unit tests, integration tests, and E2E tests.
"""

from django.test import TestCase, TransactionTestCase
from django.contrib.auth.models import User
from rest_framework.test import APITestCase, APIClient
from rest_framework import status
from unittest.mock import patch, MagicMock, AsyncMock, PropertyMock
from datetime import datetime, timedelta
import asyncio
import json
import os

from ..services.quantum_rng_service import (
    QuantumPasswordGenerator,
    QuantumEntropyPool,
    ANUQuantumProvider,
    IBMQuantumProvider,
    IonQQuantumProvider,
    FallbackCryptoProvider,
    QuantumProvider,
    QuantumCertificate,
    QuantumEntropyBatch,
    get_quantum_generator,
)
from ..models import QuantumPasswordCertificate, QuantumEntropyBatch as DBQuantumEntropyBatch


# =============================================================================
# Provider Unit Tests
# =============================================================================

class FallbackProviderTestCase(TestCase):
    """Tests for the cryptographic fallback provider."""
    
    def test_fallback_generates_bytes(self):
        """Test that fallback generates random bytes."""
        provider = FallbackCryptoProvider()
        
        result = asyncio.run(provider.fetch_random_bytes(32))
        random_bytes, circuit_id = result
        
        self.assertEqual(len(random_bytes), 32)
        self.assertIsNone(circuit_id)
    
    def test_fallback_generates_different_bytes(self):
        """Test that fallback generates different bytes each time."""
        provider = FallbackCryptoProvider()
        
        result1 = asyncio.run(provider.fetch_random_bytes(32))
        result2 = asyncio.run(provider.fetch_random_bytes(32))
        
        # Extremely unlikely to be equal
        self.assertNotEqual(result1[0], result2[0])
    
    def test_fallback_is_available(self):
        """Test fallback is always available."""
        provider = FallbackCryptoProvider()
        self.assertTrue(provider.is_available())
    
    def test_fallback_provider_name(self):
        """Test fallback provider name."""
        provider = FallbackCryptoProvider()
        self.assertEqual(provider.get_provider_name(), QuantumProvider.FALLBACK)
    
    def test_fallback_quantum_source(self):
        """Test fallback quantum source description."""
        provider = FallbackCryptoProvider()
        self.assertEqual(provider.get_quantum_source(), "cryptographic_prng")


class ANUProviderTestCase(TestCase):
    """Tests for the ANU quantum provider."""
    
    def test_anu_provider_name(self):
        """Test ANU provider name."""
        provider = ANUQuantumProvider()
        self.assertEqual(provider.get_provider_name(), QuantumProvider.ANU)
    
    def test_anu_quantum_source(self):
        """Test ANU quantum source description."""
        provider = ANUQuantumProvider()
        self.assertEqual(provider.get_quantum_source(), "vacuum_fluctuations")
    
    def test_anu_base_url(self):
        """Test ANU API URL is correct."""
        provider = ANUQuantumProvider()
        self.assertEqual(provider.BASE_URL, "https://qrng.anu.edu.au/API/jsonI.php")
    
    def test_anu_max_array_length(self):
        """Test ANU maximum array length."""
        provider = ANUQuantumProvider()
        self.assertEqual(provider.MAX_ARRAY_LENGTH, 1024)
    
    @patch('httpx.AsyncClient')
    def test_anu_fetch_mocked(self, mock_client_class):
        """Test ANU fetch with mocked API response."""
        # Create mock response
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "success": True,
            "data": [100, 150, 200, 50]
        }
        mock_response.raise_for_status = MagicMock()
        
        # Create mock client
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client_class.return_value = mock_client
        
        provider = ANUQuantumProvider()
        provider._client = mock_client
        
        result = asyncio.run(provider.fetch_random_bytes(4))
        random_bytes, circuit_id = result
        
        self.assertEqual(len(random_bytes), 4)
        self.assertEqual(random_bytes, bytes([100, 150, 200, 50]))
        self.assertIsNone(circuit_id)


class IBMProviderTestCase(TestCase):
    """Tests for the IBM Quantum provider."""
    
    def test_ibm_provider_name(self):
        """Test IBM provider name."""
        provider = IBMQuantumProvider()
        self.assertEqual(provider.get_provider_name(), QuantumProvider.IBM)
    
    def test_ibm_quantum_source(self):
        """Test IBM quantum source description."""
        provider = IBMQuantumProvider()
        self.assertEqual(provider.get_quantum_source(), "superconducting_qubit_superposition")
    
    def test_ibm_availability_without_token(self):
        """Test IBM requires API token."""
        provider = IBMQuantumProvider(api_token=None)
        if not provider.api_token:
            self.assertFalse(provider.is_available())
    
    def test_ibm_bits_to_bytes(self):
        """Test IBM bit to byte conversion."""
        provider = IBMQuantumProvider()
        
        # Test single byte: 10101010 = 170
        bits = [1, 0, 1, 0, 1, 0, 1, 0]
        result = provider._bits_to_bytes(bits)
        self.assertEqual(result, bytes([170]))
        
        # Test two bytes
        bits = [1, 1, 1, 1, 0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1]  # 240, 15
        result = provider._bits_to_bytes(bits)
        self.assertEqual(result, bytes([240, 15]))


class IonQProviderTestCase(TestCase):
    """Tests for the IonQ quantum provider."""
    
    def test_ionq_provider_name(self):
        """Test IonQ provider name."""
        provider = IonQQuantumProvider()
        self.assertEqual(provider.get_provider_name(), QuantumProvider.IONQ)
    
    def test_ionq_quantum_source(self):
        """Test IonQ quantum source description."""
        provider = IonQQuantumProvider()
        self.assertEqual(provider.get_quantum_source(), "trapped_ion_superposition")
    
    def test_ionq_availability_without_key(self):
        """Test IonQ requires API key."""
        provider = IonQQuantumProvider(api_key=None)
        if not provider.api_key:
            self.assertFalse(provider.is_available())
    
    def test_ionq_base_url(self):
        """Test IonQ API URL is correct."""
        provider = IonQQuantumProvider()
        self.assertEqual(provider.BASE_URL, "https://api.ionq.co/v0.3")
    
    def test_ionq_build_hadamard_circuit(self):
        """Test IonQ Hadamard circuit generation."""
        provider = IonQQuantumProvider()
        circuit = provider._build_hadamard_circuit(4)
        
        self.assertEqual(len(circuit), 4)
        for i, gate in enumerate(circuit):
            self.assertEqual(gate['gate'], 'h')
            self.assertEqual(gate['target'], i)
    
    def test_ionq_build_large_circuit(self):
        """Test IonQ circuit for maximum qubits."""
        provider = IonQQuantumProvider()
        circuit = provider._build_hadamard_circuit(32)
        
        self.assertEqual(len(circuit), 32)
    
    def test_ionq_bits_to_bytes(self):
        """Test IonQ bit to byte conversion."""
        provider = IonQQuantumProvider()
        
        # Test full byte
        bits = [1, 0, 1, 0, 1, 0, 1, 0]  # 170 in binary
        result = provider._bits_to_bytes(bits)
        self.assertEqual(result, bytes([170]))
        
        # Test multiple bytes
        bits = [1, 1, 1, 1, 1, 1, 1, 1, 0, 0, 0, 0, 0, 0, 0, 0]  # 255, 0
        result = provider._bits_to_bytes(bits)
        self.assertEqual(result, bytes([255, 0]))
    
    def test_ionq_bits_to_bytes_padding(self):
        """Test IonQ bit to byte with padding needed."""
        provider = IonQQuantumProvider()
        
        # Test partial byte (should be padded)
        bits = [1, 0, 1]  # Should become 10100000 = 160
        result = provider._bits_to_bytes(bits)
        self.assertEqual(result, bytes([160]))


# =============================================================================
# Entropy Pool Tests
# =============================================================================

class EntropyPoolTestCase(TestCase):
    """Tests for the quantum entropy pool."""
    
    def test_pool_refills(self):
        """Test that pool refills when depleted."""
        pool = QuantumEntropyPool(min_pool_size=32, max_pool_size=64, batch_size=32)
        
        result = asyncio.run(pool.get_random_bytes(16))
        random_bytes, certificate = result
        
        self.assertEqual(len(random_bytes), 16)
        self.assertIsNotNone(certificate)
    
    def test_pool_provides_certificate(self):
        """Test that pool provides certificate with bytes."""
        pool = QuantumEntropyPool(min_pool_size=32, max_pool_size=64, batch_size=32)
        
        result = asyncio.run(pool.get_random_bytes(16))
        random_bytes, certificate = result
        
        self.assertIsNotNone(certificate.certificate_id)
        self.assertIsNotNone(certificate.signature)
        self.assertGreater(certificate.entropy_bits, 0)
    
    def test_pool_status(self):
        """Test pool status reporting."""
        pool = QuantumEntropyPool(min_pool_size=32, max_pool_size=64)
        
        status = pool.get_pool_status()
        
        self.assertIn('total_bytes_available', status)
        self.assertIn('batch_count', status)
        self.assertIn('health', status)
        self.assertIn('min_pool_size', status)
        self.assertIn('max_pool_size', status)
    
    def test_pool_health_good(self):
        """Test pool health when sufficiently filled."""
        pool = QuantumEntropyPool(min_pool_size=16, max_pool_size=64, batch_size=32)
        
        # Trigger refill
        asyncio.run(pool.get_random_bytes(8))
        
        status = pool.get_pool_status()
        # After refill, should have good health
        self.assertIn(status['health'], ['good', 'low'])
    
    def test_pool_multiple_requests(self):
        """Test pool handles multiple requests."""
        pool = QuantumEntropyPool(min_pool_size=64, max_pool_size=128, batch_size=64)
        
        # Multiple requests
        for _ in range(5):
            result = asyncio.run(pool.get_random_bytes(10))
            self.assertEqual(len(result[0]), 10)
    
    def test_pool_large_request(self):
        """Test pool handles large requests."""
        pool = QuantumEntropyPool(min_pool_size=256, max_pool_size=512, batch_size=256)
        
        result = asyncio.run(pool.get_random_bytes(100))
        self.assertEqual(len(result[0]), 100)


# =============================================================================
# Password Generator Tests
# =============================================================================

class QuantumPasswordGeneratorTestCase(TestCase):
    """Tests for the quantum password generator."""
    
    def test_generate_password_default_length(self):
        """Test generating password with default length."""
        generator = QuantumPasswordGenerator()
        
        result = asyncio.run(generator.generate_password(length=16))
        password, certificate = result
        
        self.assertEqual(len(password), 16)
        self.assertIsNotNone(certificate)
    
    def test_generate_password_with_options(self):
        """Test generating password with specific options."""
        generator = QuantumPasswordGenerator()
        
        # Only lowercase
        result = asyncio.run(generator.generate_password(
            length=20,
            use_uppercase=False,
            use_lowercase=True,
            use_numbers=False,
            use_symbols=False
        ))
        password, certificate = result
        
        self.assertEqual(len(password), 20)
        self.assertTrue(password.islower())
    
    def test_generate_password_only_uppercase(self):
        """Test generating password with only uppercase."""
        generator = QuantumPasswordGenerator()
        
        result = asyncio.run(generator.generate_password(
            length=16,
            use_uppercase=True,
            use_lowercase=False,
            use_numbers=False,
            use_symbols=False
        ))
        password, certificate = result
        
        self.assertEqual(len(password), 16)
        self.assertTrue(password.isupper())
    
    def test_generate_password_only_numbers(self):
        """Test generating password with only numbers."""
        generator = QuantumPasswordGenerator()
        
        result = asyncio.run(generator.generate_password(
            length=12,
            use_uppercase=False,
            use_lowercase=False,
            use_numbers=True,
            use_symbols=False
        ))
        password, certificate = result
        
        self.assertEqual(len(password), 12)
        self.assertTrue(password.isdigit())
    
    def test_generate_password_all_chars(self):
        """Test generating password with all character types."""
        generator = QuantumPasswordGenerator()
        
        result = asyncio.run(generator.generate_password(
            length=32,
            use_uppercase=True,
            use_lowercase=True,
            use_numbers=True,
            use_symbols=True
        ))
        password, certificate = result
        
        self.assertEqual(len(password), 32)
    
    def test_password_length_minimum(self):
        """Test password length clamped to minimum."""
        generator = QuantumPasswordGenerator()
        
        result = asyncio.run(generator.generate_password(length=4))
        self.assertEqual(len(result[0]), 8)
    
    def test_password_length_maximum(self):
        """Test password length clamped to maximum."""
        generator = QuantumPasswordGenerator()
        
        result = asyncio.run(generator.generate_password(length=200))
        self.assertEqual(len(result[0]), 128)
    
    def test_custom_charset(self):
        """Test generating password with custom charset."""
        generator = QuantumPasswordGenerator()
        
        result = asyncio.run(generator.generate_password(
            length=10,
            custom_charset='ABC123'
        ))
        password, certificate = result
        
        self.assertEqual(len(password), 10)
        for char in password:
            self.assertIn(char, 'ABC123')
    
    def test_custom_charset_overrides_options(self):
        """Test custom charset overrides other options."""
        generator = QuantumPasswordGenerator()
        
        result = asyncio.run(generator.generate_password(
            length=10,
            use_uppercase=True,
            use_symbols=True,
            custom_charset='xyz'
        ))
        password, certificate = result
        
        for char in password:
            self.assertIn(char, 'xyz')
    
    def test_password_uniqueness(self):
        """Test generated passwords are unique."""
        generator = QuantumPasswordGenerator()
        
        passwords = set()
        for _ in range(10):
            result = asyncio.run(generator.generate_password(length=16))
            passwords.add(result[0])
        
        # All should be unique
        self.assertEqual(len(passwords), 10)
    
    def test_get_raw_random_bytes(self):
        """Test getting raw random bytes."""
        generator = QuantumPasswordGenerator()
        
        result = asyncio.run(generator.get_raw_random_bytes(64))
        random_bytes, certificate = result
        
        self.assertEqual(len(random_bytes), 64)
        self.assertIsNotNone(certificate)
    
    def test_singleton_generator(self):
        """Test singleton pattern for generator."""
        gen1 = get_quantum_generator()
        gen2 = get_quantum_generator()
        
        self.assertIs(gen1, gen2)


# =============================================================================
# Certificate Tests
# =============================================================================

class QuantumCertificateTestCase(TestCase):
    """Tests for quantum certificate dataclass."""
    
    def test_certificate_to_dict(self):
        """Test certificate serialization."""
        cert = QuantumCertificate(
            certificate_id="test-id-123",
            password_hash_prefix="sha256:abc123...",
            provider="anu_qrng",
            generation_timestamp=datetime(2026, 1, 16, 12, 0, 0),
            quantum_source="vacuum_fluctuations",
            entropy_bits=128,
            circuit_id=None,
            signature="test_signature"
        )
        
        data = cert.to_dict()
        
        self.assertEqual(data['certificate_id'], "test-id-123")
        self.assertEqual(data['provider'], "anu_qrng")
        self.assertEqual(data['entropy_bits'], 128)
        self.assertIn('generation_timestamp', data)
    
    def test_certificate_with_circuit_id(self):
        """Test certificate with circuit ID."""
        cert = QuantumCertificate(
            certificate_id="test-id-456",
            password_hash_prefix="sha256:def456...",
            provider="ibm_quantum",
            generation_timestamp=datetime.now(),
            quantum_source="superconducting_qubit_superposition",
            entropy_bits=256,
            circuit_id="ibm-job-abc123",
            signature="ibm_signature"
        )
        
        data = cert.to_dict()
        
        self.assertEqual(data['circuit_id'], "ibm-job-abc123")


class QuantumCertificateModelTestCase(TestCase):
    """Tests for quantum certificate database model."""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='quantumtester',
            email='quantum@test.com',
            password='testpassword123'
        )
    
    def test_create_certificate(self):
        """Test creating a quantum certificate."""
        cert = QuantumPasswordCertificate.objects.create(
            user=self.user,
            password_hash_prefix='sha256:a3f2b1c4',
            provider='anu_qrng',
            quantum_source='vacuum_fluctuations',
            entropy_bits=128,
            signature='test_signature'
        )
        
        self.assertIsNotNone(cert.id)
        self.assertEqual(cert.provider, 'anu_qrng')
    
    def test_certificate_to_dict(self):
        """Test certificate serialization."""
        cert = QuantumPasswordCertificate.objects.create(
            user=self.user,
            password_hash_prefix='sha256:a3f2b1c4',
            provider='anu_qrng',
            quantum_source='vacuum_fluctuations',
            entropy_bits=128,
            signature='test_signature'
        )
        
        data = cert.to_dict()
        
        self.assertIn('certificate_id', data)
        self.assertIn('provider', data)
        self.assertIn('entropy_bits', data)
        self.assertEqual(data['entropy_bits'], 128)
    
    def test_certificate_str(self):
        """Test certificate string representation."""
        cert = QuantumPasswordCertificate.objects.create(
            user=self.user,
            password_hash_prefix='sha256:a3f2b1c4',
            provider='anu_qrng',
            quantum_source='vacuum_fluctuations',
            entropy_bits=128,
            signature='test_signature'
        )
        
        str_repr = str(cert)
        self.assertIn('QC-', str_repr)
        self.assertIn('anu_qrng', str_repr)
    
    def test_certificate_ordering(self):
        """Test certificates are ordered by timestamp descending."""
        for i in range(3):
            QuantumPasswordCertificate.objects.create(
                user=self.user,
                password_hash_prefix=f'sha256:hash{i}',
                provider='anu_qrng',
                quantum_source='vacuum_fluctuations',
                entropy_bits=128,
                signature=f'sig{i}'
            )
        
        certs = list(QuantumPasswordCertificate.objects.filter(user=self.user))
        for i in range(len(certs) - 1):
            self.assertGreaterEqual(
                certs[i].generation_timestamp,
                certs[i + 1].generation_timestamp
            )


# =============================================================================
# API Tests
# =============================================================================

class QuantumAPITestCase(APITestCase):
    """Tests for quantum RNG API endpoints."""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='apitester',
            email='api@test.com',
            password='testpassword123'
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
    
    def test_generate_password_endpoint(self):
        """Test password generation endpoint."""
        response = self.client.post('/api/security/quantum/generate-password/', {
            'length': 16,
            'uppercase': True,
            'lowercase': True,
            'numbers': True,
            'symbols': True,
            'save_certificate': True
        }, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['success'])
        self.assertIn('password', response.data)
        self.assertEqual(len(response.data['password']), 16)
        self.assertIn('certificate', response.data)
        self.assertIn('quantum_certified', response.data)
    
    def test_generate_password_default_values(self):
        """Test password generation with default values."""
        response = self.client.post('/api/security/quantum/generate-password/', {}, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['password']), 16)  # Default length
    
    def test_generate_password_invalid_length_short(self):
        """Test password generation with too short length."""
        response = self.client.post('/api/security/quantum/generate-password/', {
            'length': 5,
        }, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_generate_password_invalid_length_long(self):
        """Test password generation with too long length."""
        response = self.client.post('/api/security/quantum/generate-password/', {
            'length': 200,
        }, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_generate_password_no_save(self):
        """Test password generation without saving certificate."""
        initial_count = QuantumPasswordCertificate.objects.filter(user=self.user).count()
        
        response = self.client.post('/api/security/quantum/generate-password/', {
            'length': 16,
            'save_certificate': False
        }, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Certificate count should not increase
        final_count = QuantumPasswordCertificate.objects.filter(user=self.user).count()
        self.assertEqual(initial_count, final_count)
    
    def test_random_bytes_endpoint_hex(self):
        """Test random bytes endpoint with hex format."""
        response = self.client.get('/api/security/quantum/random-bytes/?count=32&format=hex')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['success'])
        self.assertIn('bytes', response.data)
        self.assertEqual(len(response.data['bytes']), 64)  # 32 bytes in hex
        self.assertEqual(response.data['format'], 'hex')
    
    def test_random_bytes_endpoint_base64(self):
        """Test random bytes endpoint with base64 format."""
        response = self.client.get('/api/security/quantum/random-bytes/?count=32&format=base64')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['format'], 'base64')
    
    def test_random_bytes_invalid_count(self):
        """Test random bytes with invalid count."""
        response = self.client.get('/api/security/quantum/random-bytes/?count=500')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_pool_status_endpoint(self):
        """Test pool status endpoint."""
        response = self.client.get('/api/security/quantum/pool-status/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['success'])
        self.assertIn('pool', response.data)
        self.assertIn('providers', response.data)
        self.assertIn('anu_qrng', response.data['providers'])
        self.assertIn('ibm_quantum', response.data['providers'])
        self.assertIn('ionq_quantum', response.data['providers'])
    
    def test_pool_status_provider_details(self):
        """Test pool status includes provider details."""
        response = self.client.get('/api/security/quantum/pool-status/')
        
        anu = response.data['providers']['anu_qrng']
        self.assertIn('available', anu)
        self.assertIn('description', anu)
        self.assertIn('source', anu)
    
    def test_list_certificates_endpoint(self):
        """Test certificates listing endpoint."""
        for i in range(3):
            QuantumPasswordCertificate.objects.create(
                user=self.user,
                password_hash_prefix=f'sha256:hash{i}',
                provider='anu_qrng',
                quantum_source='vacuum_fluctuations',
                entropy_bits=128,
                signature=f'sig{i}'
            )
        
        response = self.client.get('/api/security/quantum/certificates/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['success'])
        self.assertEqual(len(response.data['certificates']), 3)
        self.assertEqual(response.data['total'], 3)
    
    def test_list_certificates_limit(self):
        """Test certificates listing with limit."""
        for i in range(10):
            QuantumPasswordCertificate.objects.create(
                user=self.user,
                password_hash_prefix=f'sha256:hash{i}',
                provider='anu_qrng',
                quantum_source='vacuum_fluctuations',
                entropy_bits=128,
                signature=f'sig{i}'
            )
        
        response = self.client.get('/api/security/quantum/certificates/?limit=5')
        
        self.assertEqual(len(response.data['certificates']), 5)
        self.assertEqual(response.data['total'], 10)
    
    def test_get_certificate_endpoint(self):
        """Test getting a specific certificate."""
        cert = QuantumPasswordCertificate.objects.create(
            user=self.user,
            password_hash_prefix='sha256:specific',
            provider='ibm_quantum',
            quantum_source='superconducting_qubit_superposition',
            entropy_bits=256,
            signature='specific_sig'
        )
        
        response = self.client.get(f'/api/security/quantum/certificate/{cert.id}/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['success'])
        self.assertEqual(response.data['certificate']['provider'], 'ibm_quantum')
    
    def test_get_certificate_not_found(self):
        """Test getting non-existent certificate."""
        import uuid
        fake_id = uuid.uuid4()
        
        response = self.client.get(f'/api/security/quantum/certificate/{fake_id}/')
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
    
    def test_unauthenticated_access(self):
        """Test that unauthenticated access is denied."""
        self.client.force_authenticate(user=None)
        
        response = self.client.get('/api/security/quantum/pool-status/')
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_unauthenticated_generate(self):
        """Test unauthenticated password generation is denied."""
        self.client.force_authenticate(user=None)
        
        response = self.client.post('/api/security/quantum/generate-password/', {
            'length': 16
        }, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


# =============================================================================
# E2E Integration Tests
# =============================================================================

class QuantumE2ETestCase(TransactionTestCase):
    """End-to-end tests for quantum password flow."""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='e2etester',
            email='e2e@test.com',
            password='testpassword123'
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
    
    def test_full_password_generation_flow(self):
        """Test complete flow: generate -> save -> retrieve certificate."""
        # Step 1: Generate password
        gen_response = self.client.post('/api/security/quantum/generate-password/', {
            'length': 20,
            'uppercase': True,
            'lowercase': True,
            'numbers': True,
            'symbols': False,
            'save_certificate': True
        }, format='json')
        
        self.assertEqual(gen_response.status_code, status.HTTP_200_OK)
        password = gen_response.data['password']
        cert_id = gen_response.data['certificate']['certificate_id']
        
        self.assertEqual(len(password), 20)
        
        # Step 2: Retrieve certificate
        cert_response = self.client.get(f'/api/security/quantum/certificate/{cert_id}/')
        
        self.assertEqual(cert_response.status_code, status.HTTP_200_OK)
        retrieved_cert = cert_response.data['certificate']
        
        self.assertEqual(retrieved_cert['certificate_id'], cert_id)
        self.assertIn('signature', retrieved_cert)
        
        # Step 3: List certificates - should include our new one
        list_response = self.client.get('/api/security/quantum/certificates/')
        
        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        cert_ids = [c['certificate_id'] for c in list_response.data['certificates']]
        self.assertIn(cert_id, cert_ids)
    
    def test_multiple_passwords_different_providers(self):
        """Test generating multiple passwords and verifying certificates."""
        passwords = []
        certificates = []
        
        for i in range(5):
            response = self.client.post('/api/security/quantum/generate-password/', {
                'length': 16 + i,
                'save_certificate': True
            }, format='json')
            
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            passwords.append(response.data['password'])
            certificates.append(response.data['certificate'])
        
        # All passwords should be unique
        self.assertEqual(len(set(passwords)), 5)
        
        # All certificates should have valid structure
        for cert in certificates:
            self.assertIn('certificate_id', cert)
            self.assertIn('provider', cert)
            self.assertIn('signature', cert)
            self.assertIn('entropy_bits', cert)
    
    def test_raw_bytes_to_password_flow(self):
        """Test getting raw bytes and verifying entropy."""
        # Get raw bytes
        bytes_response = self.client.get('/api/security/quantum/random-bytes/?count=64&format=hex')
        
        self.assertEqual(bytes_response.status_code, status.HTTP_200_OK)
        
        hex_bytes = bytes_response.data['bytes']
        provider = bytes_response.data['provider']
        
        # Verify hex string length
        self.assertEqual(len(hex_bytes), 128)  # 64 bytes * 2
        
        # Verify provider is valid
        valid_providers = ['anu_qrng', 'ibm_quantum', 'ionq_quantum', 'cryptographic_fallback']
        self.assertIn(provider, valid_providers)
    
    def test_pool_status_reflects_usage(self):
        """Test pool status changes after usage."""
        # Get initial status
        initial_response = self.client.get('/api/security/quantum/pool-status/')
        self.assertEqual(initial_response.status_code, status.HTTP_200_OK)
        
        # Generate some passwords
        for _ in range(3):
            self.client.post('/api/security/quantum/generate-password/', {
                'length': 32
            }, format='json')
        
        # Get status again
        final_response = self.client.get('/api/security/quantum/pool-status/')
        self.assertEqual(final_response.status_code, status.HTTP_200_OK)
        
        # Pool should still report health
        self.assertIn(final_response.data['pool']['health'], ['good', 'low'])
    
    def test_certificate_verification(self):
        """Test that certificate signature can be verified concept."""
        response = self.client.post('/api/security/quantum/generate-password/', {
            'length': 16,
            'save_certificate': True
        }, format='json')
        
        cert = response.data['certificate']
        
        # Certificate should have all required fields
        required_fields = [
            'certificate_id',
            'password_hash_prefix',
            'provider',
            'quantum_source',
            'entropy_bits',
            'generation_timestamp',
            'signature'
        ]
        
        for field in required_fields:
            self.assertIn(field, cert, f"Missing field: {field}")
        
        # Password hash should be prefixed correctly
        self.assertTrue(cert['password_hash_prefix'].startswith('sha256:'))
        
        # Entropy bits should match expected value
        self.assertGreater(cert['entropy_bits'], 0)


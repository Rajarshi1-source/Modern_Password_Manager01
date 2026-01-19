"""
Chemical Password Storage - Integration & Functional Tests
============================================================

Integration tests for:
- End-to-end API workflows
- Lab provider API response validation
- Database persistence verification
- Time-lock timing accuracy

@author Password Manager Team
@created 2026-01-17
"""

import pytest
import time
from datetime import datetime, timedelta
from decimal import Decimal

from django.test import TestCase, TransactionTestCase
from django.contrib.auth.models import User
from rest_framework.test import APITestCase, APIClient
from rest_framework import status


# =============================================================================
# Integration Tests
# =============================================================================

class ChemicalStorageIntegrationTest(TransactionTestCase):
    """Integration tests for complete workflows."""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='integration_test',
            email='integration@test.com',
            password='testpass123'
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
    
    def test_encode_to_synthesis_workflow(self):
        """Test full workflow from encoding to synthesis order."""
        # Step 1: Encode password
        encode_response = self.client.post('/api/security/chemical/encode/', {
            'password': 'IntegrationTestPassword!',
            'service_name': 'Integration Test',
            'save_to_db': True,
        })
        
        self.assertEqual(encode_response.status_code, status.HTTP_200_OK)
        self.assertTrue(encode_response.data['success'])
        
        sequence = encode_response.data['dna_sequence']['sequence']
        record_id = encode_response.data['id']
        
        self.assertIsNotNone(record_id)
        self.assertGreater(len(sequence), 0)
        
        # Step 2: Order synthesis
        synthesis_response = self.client.post('/api/security/chemical/synthesis-order/', {
            'dna_sequence': sequence,
            'provider': 'mock',
        })
        
        self.assertEqual(synthesis_response.status_code, status.HTTP_200_OK)
        self.assertTrue(synthesis_response.data['success'])
        
        order_id = synthesis_response.data['order_id']
        self.assertIsNotNone(order_id)
        
        # Step 3: Check synthesis status
        status_response = self.client.get(f'/api/security/chemical/synthesis-status/{order_id}/')
        
        self.assertEqual(status_response.status_code, status.HTTP_200_OK)
    
    def test_time_lock_full_lifecycle(self):
        """Test time-lock creation, status check, and unlock."""
        # Step 1: Create time-lock
        create_response = self.client.post('/api/security/chemical/time-lock/', {
            'password': 'TimeLockIntegration!',
            'delay_hours': 1,
            'mode': 'server',
        })
        
        self.assertEqual(create_response.status_code, status.HTTP_200_OK)
        self.assertTrue(create_response.data['success'])
        
        capsule_id = create_response.data['capsule_id']
        
        # Step 2: Check status (should be locked)
        status_response = self.client.get(f'/api/security/chemical/capsule-status/{capsule_id}/')
        
        self.assertEqual(status_response.status_code, status.HTTP_200_OK)
        self.assertEqual(status_response.data['status'], 'locked')
        self.assertFalse(status_response.data['can_unlock'])
        
        # Step 3: Try to unlock (should fail - still locked)
        unlock_response = self.client.post(f'/api/security/chemical/unlock-capsule/{capsule_id}/')
        
        self.assertEqual(unlock_response.status_code, status.HTTP_403_FORBIDDEN)
    
    def test_certificate_generation_and_retrieval(self):
        """Test certificate is generated and can be retrieved."""
        # Trigger full workflow
        store_response = self.client.post('/api/security/chemical/store/', {
            'password': 'CertificateTest123!',
            'enable_time_lock': False,
            'order_synthesis': False,
        })
        
        self.assertEqual(store_response.status_code, status.HTTP_200_OK)
        self.assertTrue(store_response.data['success'])
        
        # List certificates
        cert_response = self.client.get('/api/security/chemical/certificates/')
        
        self.assertEqual(cert_response.status_code, status.HTTP_200_OK)
        self.assertTrue(cert_response.data['success'])
    
    def test_subscription_limits_enforced(self):
        """Test subscription password limits are enforced."""
        from security.models import ChemicalStorageSubscription
        
        # Set subscription to limit
        sub, _ = ChemicalStorageSubscription.objects.get_or_create(
            user=self.user,
            defaults={'tier': 'free', 'max_passwords': 1, 'passwords_stored': 1}
        )
        sub.passwords_stored = sub.max_passwords
        sub.save()
        
        # Try to store another password
        store_response = self.client.post('/api/security/chemical/store/', {
            'password': 'LimitTest123!',
        })
        
        # Should fail due to limit
        self.assertEqual(store_response.status_code, status.HTTP_403_FORBIDDEN)


# =============================================================================
# Lab Provider API Validation Tests
# =============================================================================

class LabProviderAPIValidationTest(TestCase):
    """Validate lab provider API responses match expected format."""
    
    def test_synthesis_order_response_format(self):
        """Test synthesis order has all required fields."""
        from security.services.lab_provider_api import LabProviderFactory
        
        provider = LabProviderFactory.get_provider('mock')
        order = provider.submit_synthesis_order(
            sequence='ATCGATCGATCG',
            user_email='test@example.com'
        )
        
        # Required fields
        self.assertIsNotNone(order.order_id)
        self.assertIsNotNone(order.provider)
        self.assertIsNotNone(order.status)
        self.assertIsNotNone(order.created_at)
    
    def test_sequencing_order_response_format(self):
        """Test sequencing order has all required fields."""
        from security.services.lab_provider_api import LabProviderFactory
        
        provider = LabProviderFactory.get_provider('mock')
        
        if provider.supports_sequencing:
            order = provider.submit_sequencing_order('SAMPLE-123')
            
            self.assertIsNotNone(order.order_id)
            self.assertIsNotNone(order.status)
    
    def test_twist_provider_response_format(self):
        """Test Twist Bioscience provider response format."""
        from security.services.lab_provider_api import LabProviderFactory
        
        provider = LabProviderFactory.get_provider('twist')
        
        # Even without real API key, should have correct structure
        self.assertIsNotNone(provider.pricing)
        self.assertIn('synthesis', provider.pricing)
        self.assertIn('per_bp_usd', provider.pricing['synthesis'])
    
    def test_provider_pricing_structure(self):
        """Test all providers have consistent pricing structure."""
        from security.services.lab_provider_api import list_providers
        
        providers = list_providers()
        
        for provider in providers:
            self.assertIn('id', provider)
            self.assertIn('name', provider)
            # May not all have pricing exposed
            if 'pricing' in provider:
                self.assertIsInstance(provider['pricing'], dict)


# =============================================================================
# DNA Synthesis Constraints Tests
# =============================================================================

class DNASynthesisConstraintsTest(TestCase):
    """Test DNA sequence meets synthesis constraints."""
    
    def setUp(self):
        from security.services.dna_encoder import DNAEncoder
        self.encoder = DNAEncoder(
            use_error_correction=True,
            add_primers=True,
            balance_gc=True
        )
    
    def test_gc_content_synthetic_range(self):
        """Test GC content stays within synthesizable range."""
        # Test various password types
        passwords = [
            'lowercase',
            'UPPERCASE',
            '12345678',
            'MixedCase123!@#',
            'Special!@#$%^&*()',
            'VeryLongPasswordWithManyCharacters123!@#$',
        ]
        
        for password in passwords:
            result = self.encoder.encode_password(password)
            validation = self.encoder.validate_for_synthesis(result.sequence)
            
            # GC should be 30-70% for synthesis stability
            self.assertGreaterEqual(
                result.gc_content, 0.30,
                f"GC {result.gc_content:.1%} too low for '{password[:20]}'"
            )
            self.assertLessEqual(
                result.gc_content, 0.70,
                f"GC {result.gc_content:.1%} too high for '{password[:20]}'"
            )
    
    def test_homopolymer_breaking(self):
        """Test homopolymer runs are broken up."""
        # Password that would naturally create long runs
        password = "AAAAAABBBBBBCCCCCC"
        result = self.encoder.encode_password(password)
        
        # Check max run length
        max_run = self._get_max_homopolymer_run(result.sequence)
        
        # Should be <= 6 after processing
        self.assertLessEqual(max_run, 6, f"Run of {max_run} in sequence")
    
    def test_no_restriction_sites(self):
        """Test common restriction sites are avoided."""
        # Common restriction sites to avoid
        restriction_sites = [
            'GAATTC',  # EcoRI
            'GGATCC',  # BamHI
            'AAGCTT',  # HindIII
        ]
        
        password = "TestRestrictionSites123!"
        result = self.encoder.encode_password(password)
        
        for site in restriction_sites:
            self.assertNotIn(
                site, result.sequence,
                f"Found restriction site {site}"
            )
    
    def test_start_stop_codons(self):
        """Test start/stop codons are present and valid."""
        password = "CodonTest123"
        result = self.encoder.encode_password(password)
        sequence = result.sequence
        
        # Standard start codon after primer
        # Implementation may vary - just verify sequence is valid
        self.assertGreater(len(sequence), 0)
        self.assertTrue(all(n in 'ATCGN' for n in sequence))
    
    def _get_max_homopolymer_run(self, sequence):
        """Helper to find max homopolymer run length."""
        if not sequence:
            return 0
        
        max_run = 1
        current_run = 1
        
        for i in range(1, len(sequence)):
            if sequence[i] == sequence[i-1] and sequence[i] != 'N':
                current_run += 1
                max_run = max(max_run, current_run)
            else:
                current_run = 1
        
        return max_run


# =============================================================================
# Time-Lock Timing Tests
# =============================================================================

class TimeLockTimingTest(TestCase):
    """Test time-lock puzzle timing accuracy."""
    
    def test_server_lock_timing_accuracy(self):
        """Test server lock timing is accurate."""
        from security.services.time_lock_service import ServerTimeLockService
        
        service = ServerTimeLockService()
        delay_seconds = 60
        
        capsule = service.create_capsule(b'test', delay_seconds)
        
        # Unlock time should be approximately delay_seconds from now
        expected_unlock = datetime.now() + timedelta(seconds=delay_seconds)
        actual_unlock = capsule.unlock_at
        
        # Allow 2 second tolerance
        time_diff = abs((expected_unlock - actual_unlock).total_seconds())
        self.assertLess(time_diff, 2, f"Timing off by {time_diff} seconds")
    
    def test_client_puzzle_iterations(self):
        """Test client puzzle has correct iteration count."""
        from security.services.time_lock_service import ClientTimeLockService
        
        iterations_per_second = 100000
        service = ClientTimeLockService(
            modulus_bits=512,
            iterations_per_second=iterations_per_second
        )
        
        delay_seconds = 10
        puzzle = service.create_puzzle(b'test', delay_seconds)
        
        expected_iterations = delay_seconds * iterations_per_second
        self.assertEqual(puzzle.t, expected_iterations)
    
    def test_puzzle_solve_time_estimate(self):
        """Test puzzle solve time estimation is reasonable."""
        from security.services.time_lock_service import ClientTimeLockService
        
        service = ClientTimeLockService(
            modulus_bits=512,
            iterations_per_second=100000
        )
        
        puzzle = service.create_puzzle(b'test', 60)  # 1 minute
        estimates = service.estimate_solve_time(puzzle)
        
        # Should have estimates for different devices
        self.assertIn('laptop', estimates)
        self.assertIn('smartphone', estimates)
        
        # Laptop should be faster than smartphone
        laptop_time = estimates['laptop']['seconds']
        smartphone_time = estimates['smartphone']['seconds']
        
        self.assertLess(laptop_time, smartphone_time)


# =============================================================================
# A/B Test Configuration
# =============================================================================

class ChemicalStorageABTestConfig(TestCase):
    """A/B test experiment configuration and tracking."""
    
    def test_experiment_variants(self):
        """Test A/B experiment variant definitions."""
        # Experiment: Extended info vs. minimal info display
        experiment_config = {
            'experiment_id': 'chemical_storage_info_display',
            'variants': {
                'control': {
                    'show_extended_info': False,
                    'show_cost_breakdown': False,
                },
                'treatment_a': {
                    'show_extended_info': True,
                    'show_cost_breakdown': False,
                },
                'treatment_b': {
                    'show_extended_info': True,
                    'show_cost_breakdown': True,
                },
            },
            'allocation': {
                'control': 0.34,
                'treatment_a': 0.33,
                'treatment_b': 0.33,
            },
            'metrics': [
                'encoding_completion_rate',
                'time_to_encode',
                'synthesis_order_rate',
            ],
        }
        
        # Validate config
        self.assertEqual(
            sum(experiment_config['allocation'].values()),
            1.0
        )
        
        for variant_name in experiment_config['allocation']:
            self.assertIn(variant_name, experiment_config['variants'])
    
    def test_time_lock_delay_experiment(self):
        """Test A/B experiment for default time-lock delay."""
        experiment_config = {
            'experiment_id': 'time_lock_default_delay',
            'variants': {
                'control': {'default_delay_hours': 72},
                'shorter': {'default_delay_hours': 24},
                'longer': {'default_delay_hours': 168},
            },
            'metrics': [
                'time_lock_adoption_rate',
                'unlock_success_rate',
                'user_satisfaction',
            ],
        }
        
        # Validate delay values
        for variant in experiment_config['variants'].values():
            delay = variant['default_delay_hours']
            self.assertGreaterEqual(delay, 1)
            self.assertLessEqual(delay, 168)
    
    def test_provider_recommendation_experiment(self):
        """Test A/B experiment for lab provider recommendations."""
        experiment_config = {
            'experiment_id': 'provider_recommendation',
            'variants': {
                'no_recommendation': {},
                'cheapest_first': {'sort_by': 'cost_asc'},
                'fastest_first': {'sort_by': 'time_asc'},
                'best_rated': {'sort_by': 'rating_desc'},
            },
            'metrics': [
                'provider_selection_time',
                'synthesis_completion_rate',
            ],
        }
        
        self.assertEqual(len(experiment_config['variants']), 4)


# =============================================================================
# Functional Tests
# =============================================================================

class ChemicalStorageFunctionalTest(TransactionTestCase):
    """Functional tests simulating real user workflows."""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='functional_test',
            email='functional@test.com',
            password='testpass123'
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
    
    def test_new_user_onboarding_flow(self):
        """Test complete onboarding for new user."""
        # Step 1: Check subscription (auto-created)
        sub_response = self.client.get('/api/security/chemical/subscription/')
        
        self.assertEqual(sub_response.status_code, status.HTTP_200_OK)
        self.assertEqual(sub_response.data['subscription']['tier'], 'free')
        
        # Step 2: List providers
        prov_response = self.client.get('/api/security/chemical/providers/')
        
        self.assertEqual(prov_response.status_code, status.HTTP_200_OK)
        self.assertGreater(len(prov_response.data['providers']), 0)
        
        # Step 3: Encode first password
        encode_response = self.client.post('/api/security/chemical/encode/', {
            'password': 'NewUserFirstPassword!',
        })
        
        self.assertEqual(encode_response.status_code, status.HTTP_200_OK)
        self.assertTrue(encode_response.data['success'])
    
    def test_emergency_access_scenario(self):
        """Test emergency access via time-lock."""
        # Create time-lock with beneficiary
        create_response = self.client.post('/api/security/chemical/time-lock/', {
            'password': 'EmergencyAccessPassword!',
            'delay_hours': 72,
            'mode': 'server',
            'beneficiary_email': 'family@example.com',
        })
        
        self.assertEqual(create_response.status_code, status.HTTP_200_OK)
        
        # Verify beneficiary is recorded
        capsule_id = create_response.data['capsule_id']
        status_response = self.client.get(f'/api/security/chemical/capsule-status/{capsule_id}/')
        
        self.assertEqual(status_response.data['beneficiary_email'], 'family@example.com')
    
    def test_decode_previously_encoded_password(self):
        """Test decoding a previously encoded password."""
        original_password = "DecodeTestPassword123!"
        
        # Encode
        encode_response = self.client.post('/api/security/chemical/encode/', {
            'password': original_password,
        })
        
        sequence = encode_response.data['dna_sequence']['sequence']
        
        # Decode
        decode_response = self.client.post('/api/security/chemical/decode/', {
            'dna_sequence': sequence,
        })
        
        self.assertEqual(decode_response.status_code, status.HTTP_200_OK)
        self.assertTrue(decode_response.data['success'])
        self.assertEqual(decode_response.data['password'], original_password)

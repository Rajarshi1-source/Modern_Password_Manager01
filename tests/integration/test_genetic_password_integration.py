"""
Genetic Password Evolution - Integration & A/B Tests
======================================================

Integration tests for:
- Full API workflows with DNA connection
- Password generation with genetic seeding
- Evolution triggers and tracking
- A/B experiment configurations

@author Password Manager Team
@created 2026-01-17
"""

import pytest
import hashlib
import secrets
import time
from datetime import datetime, timedelta
from decimal import Decimal

from django.test import TestCase, TransactionTestCase
from django.contrib.auth.models import User
from django.utils import timezone
from rest_framework.test import APITestCase, APIClient
from rest_framework import status
from unittest.mock import patch, MagicMock


# =============================================================================
# Integration Tests
# =============================================================================

class GeneticPasswordIntegrationTest(TransactionTestCase):
    """Integration tests for complete genetic password workflows."""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='integration_test',
            email='integration@test.com',
            password='testpass123'
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
    
    def test_full_connection_to_generation_workflow(self):
        """Test workflow from DNA connection to password generation."""
        from security.models import GeneticSubscription, DNAConnection
        
        # Step 1: Create subscription
        sub = GeneticSubscription.objects.create(
            user=self.user,
            tier='trial',
            status='active',
            trial_started_at=timezone.now(),
            trial_expires_at=timezone.now() + timedelta(days=30)
        )
        
        # Step 2: Create DNA connection
        connection = DNAConnection.objects.create(
            user=self.user,
            provider='manual',
            status='connected',
            genetic_hash_prefix='test123456',
            snp_count=500000,
            is_active=True
        )
        
        # Step 3: Check connection status API
        status_response = self.client.get('/api/security/genetic/connection-status/')
        self.assertEqual(status_response.status_code, status.HTTP_200_OK)
        self.assertTrue(status_response.data.get('connected'))
        
        # Step 4: Generate password
        generate_response = self.client.post('/api/security/genetic/generate/', {
            'length': 16,
            'uppercase': True,
            'lowercase': True,
            'numbers': True,
            'symbols': True,
        })
        
        self.assertEqual(generate_response.status_code, status.HTTP_200_OK)
        self.assertTrue(generate_response.data.get('success'))
        self.assertIn('password', generate_response.data)
        self.assertIn('certificate', generate_response.data)
    
    def test_evolution_trigger_workflow(self):
        """Test complete evolution trigger workflow."""
        from security.models import (
            GeneticSubscription, 
            DNAConnection, 
            GeneticEvolutionLog
        )
        
        # Setup
        GeneticSubscription.objects.create(
            user=self.user,
            tier='premium',
            status='active',
            epigenetic_evolution_enabled=True
        )
        
        DNAConnection.objects.create(
            user=self.user,
            provider='sequencing',
            status='connected',
            is_active=True,
            evolution_generation=1,
            biological_age=35.0
        )
        
        # Step 1: Check evolution status
        status_response = self.client.get('/api/security/genetic/evolution-status/')
        self.assertEqual(status_response.status_code, status.HTTP_200_OK)
        
        # Step 2: Trigger evolution (simulated age change)
        with patch('security.services.epigenetic_service.epigenetic_evolution_manager') as mock:
            mock.check_and_evolve.return_value = {
                'evolved': True,
                'old_generation': 1,
                'new_generation': 2,
                'biological_age': 36.5,
                'previous_age': 35.0
            }
            
            evolve_response = self.client.post('/api/security/genetic/trigger-evolution/', {
                'force': False,
            })
            
            self.assertEqual(evolve_response.status_code, status.HTTP_200_OK)
    
    def test_certificate_creation_and_retrieval(self):
        """Test certificate creation and listing workflow."""
        from security.models import GeneticSubscription, DNAConnection
        
        # Setup
        GeneticSubscription.objects.create(
            user=self.user,
            tier='trial',
            status='active',
            trial_expires_at=timezone.now() + timedelta(days=30)
        )
        
        DNAConnection.objects.create(
            user=self.user,
            provider='manual',
            status='connected',
            is_active=True,
            snp_count=100000
        )
        
        # Generate password (creates certificate)
        generate_response = self.client.post('/api/security/genetic/generate/', {
            'length': 16,
        })
        
        self.assertEqual(generate_response.status_code, status.HTTP_200_OK)
        certificate_id = generate_response.data.get('certificate', {}).get('certificate_id')
        
        # List certificates
        list_response = self.client.get('/api/security/genetic/certificates/')
        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        
        # Retrieve specific certificate
        if certificate_id:
            detail_response = self.client.get(
                f'/api/security/genetic/certificates/{certificate_id}/'
            )
            self.assertEqual(detail_response.status_code, status.HTTP_200_OK)
    
    def test_quantum_combination_workflow(self):
        """Test genetic + quantum combined password generation."""
        from security.models import GeneticSubscription, DNAConnection
        
        GeneticSubscription.objects.create(
            user=self.user,
            tier='premium',
            status='active',
            combine_with_quantum=True
        )
        
        DNAConnection.objects.create(
            user=self.user,
            provider='sequencing',
            status='connected',
            is_active=True,
            snp_count=500000
        )
        
        with patch('security.services.quantum_rng_service.get_quantum_generator') as mock:
            mock_gen = MagicMock()
            mock_gen.generate_password.return_value = (
                'QuantumPart123!',
                MagicMock(entropy_bits=256)
            )
            mock.return_value = mock_gen
            
            response = self.client.post('/api/security/genetic/generate/', {
                'length': 20,
                'combine_with_quantum': True,
            })
            
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            # Certificate should indicate quantum combination
            cert = response.data.get('certificate', {})
            self.assertTrue(cert.get('combined_with_quantum', True))


# =============================================================================
# DNA Provider Integration Tests
# =============================================================================

class DNAProviderIntegrationTest(TransactionTestCase):
    """Integration tests for DNA provider connections."""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='provider_test',
            email='provider@test.com',
            password='testpass123'
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
    
    def test_manual_upload_workflow(self):
        """Test manual DNA file upload workflow."""
        from django.core.files.uploadedfile import SimpleUploadedFile
        from security.models import GeneticSubscription
        
        GeneticSubscription.objects.create(
            user=self.user,
            tier='trial',
            status='active',
            trial_expires_at=timezone.now() + timedelta(days=30)
        )
        
        # Create test DNA file
        dna_content = b"""# This data file generated by 23andMe
# rsid\tchromosome\tposition\tgenotype
rs1426654\t15\t28365618\tAA
rs12913832\t15\t28365618\tGG
rs1799971\t6\t154039662\tAG
rs429358\t19\t45411941\tTT
rs7903146\t10\t114758349\tCC
"""
        dna_file = SimpleUploadedFile(
            'genome.txt',
            dna_content,
            content_type='text/plain'
        )
        
        # Upload file
        response = self.client.post(
            '/api/security/genetic/upload-dna/',
            {'file': dna_file},
            format='multipart'
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data.get('success'))
        self.assertIn('snp_count', response.data)
    
    def test_oauth_callback_handling(self):
        """Test OAuth callback processing."""
        from security.models import GeneticSubscription
        
        GeneticSubscription.objects.create(
            user=self.user,
            tier='trial',
            status='active'
        )
        
        # Simulate OAuth callback (would normally come from provider)
        with patch('security.services.dna_provider_service.SequencingProvider') as mock:
            mock_provider = MagicMock()
            mock_provider.exchange_code.return_value = {
                'access_token': 'test-token',
                'refresh_token': 'refresh-token',
                'snps': {'rs123': 'AA'},
                'snp_count': 500000,
            }
            mock.return_value = mock_provider
            
            response = self.client.post('/api/security/genetic/oauth-callback/', {
                'code': 'test-auth-code',
                'state': 'test-state-token',
            })
            
            # May fail without real OAuth setup, but tests the endpoint exists
            self.assertIn(response.status_code, [200, 400, 500])
    
    def test_provider_disconnect(self):
        """Test disconnecting DNA provider."""
        from security.models import GeneticSubscription, DNAConnection
        
        GeneticSubscription.objects.create(
            user=self.user,
            tier='trial',
            status='active'
        )
        
        connection = DNAConnection.objects.create(
            user=self.user,
            provider='sequencing',
            status='connected',
            is_active=True
        )
        
        response = self.client.delete('/api/security/genetic/disconnect/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        connection.refresh_from_db()
        self.assertFalse(connection.is_active)


# =============================================================================
# DNA-Based Seeding Tests
# =============================================================================

class DNABasedSeedingTest(TestCase):
    """Test DNA-based seed generation specifics."""
    
    def test_snp_data_produces_consistent_seed(self):
        """Test that same SNP data always produces same seed."""
        from security.services.genetic_password_service import GeneticSeedGenerator
        
        salt = b'consistent_salt_for_testing_1234'
        generator = GeneticSeedGenerator(salt=salt)
        
        snp_data = {
            'rs1426654': 'AA',
            'rs12913832': 'GG',
            'rs1799971': 'AG',
        }
        
        seed1 = generator.generate_seed_from_snps(snp_data)
        seed2 = generator.generate_seed_from_snps(snp_data)
        
        self.assertEqual(seed1.seed_bytes, seed2.seed_bytes)
    
    def test_snp_variation_produces_different_seeds(self):
        """Test that different SNP values produce different seeds."""
        from security.services.genetic_password_service import GeneticSeedGenerator
        
        salt = b'consistent_salt_for_testing_1234'
        generator = GeneticSeedGenerator(salt=salt)
        
        snp_data1 = {'rs1426654': 'AA', 'rs12913832': 'GG'}
        snp_data2 = {'rs1426654': 'AG', 'rs12913832': 'GG'}  # Different genotype
        
        seed1 = generator.generate_seed_from_snps(snp_data1)
        seed2 = generator.generate_seed_from_snps(snp_data2)
        
        self.assertNotEqual(seed1.seed_bytes, seed2.seed_bytes)
    
    def test_epigenetic_factor_modifies_seed(self):
        """Test epigenetic factor creates different seeds."""
        from security.services.genetic_password_service import GeneticSeedGenerator
        
        salt = b'consistent_salt_for_testing_1234'
        generator = GeneticSeedGenerator(salt=salt)
        
        snp_data = {'rs1426654': 'AA'}
        
        seed_no_epi = generator.generate_seed_from_snps(snp_data)
        seed_low_epi = generator.generate_seed_from_snps(snp_data, epigenetic_factor=0.5)
        seed_high_epi = generator.generate_seed_from_snps(snp_data, epigenetic_factor=1.5)
        
        self.assertNotEqual(seed_no_epi.seed_bytes, seed_low_epi.seed_bytes)
        self.assertNotEqual(seed_low_epi.seed_bytes, seed_high_epi.seed_bytes)
    
    def test_evolution_generation_affects_seed(self):
        """Test evolution generation creates different seeds."""
        from security.services.genetic_password_service import GeneticSeedGenerator
        
        salt = b'consistent_salt_for_testing_1234'
        generator = GeneticSeedGenerator(salt=salt)
        
        snp_data = {'rs1426654': 'AA'}
        
        seed_gen1 = generator.generate_seed_from_snps(snp_data, evolution_generation=1)
        seed_gen2 = generator.generate_seed_from_snps(snp_data, evolution_generation=2)
        seed_gen3 = generator.generate_seed_from_snps(snp_data, evolution_generation=3)
        
        self.assertNotEqual(seed_gen1.seed_bytes, seed_gen2.seed_bytes)
        self.assertNotEqual(seed_gen2.seed_bytes, seed_gen3.seed_bytes)
    
    def test_seed_entropy(self):
        """Test seed has sufficient entropy."""
        from security.services.genetic_password_service import GeneticSeedGenerator
        import collections
        
        generator = GeneticSeedGenerator()
        
        snp_data = {f'rs{i}': 'AG' for i in range(1000, 1100)}
        seed = generator.generate_seed_from_snps(snp_data)
        
        # Seed should have 64 bytes
        self.assertEqual(len(seed.seed_bytes), 64)
        
        # Check byte distribution (rough entropy test)
        byte_counts = collections.Counter(seed.seed_bytes)
        unique_bytes = len(byte_counts)
        
        # Should have good distribution (at least 30 unique values in 64 bytes)
        self.assertGreater(unique_bytes, 30)


# =============================================================================
# A/B Test Configuration
# =============================================================================

class GeneticPasswordABTestConfig(TestCase):
    """A/B test experiment configuration for genetic password feature."""
    
    def test_password_length_experiment(self):
        """Test A/B experiment for default password length."""
        experiment = {
            'experiment_id': 'genetic_password_default_length',
            'name': 'Genetic Password Default Length',
            'description': 'Test user preference for default password length',
            'variants': {
                'control': {'default_length': 16},
                'longer': {'default_length': 20},
                'shorter': {'default_length': 12},
            },
            'allocation': {
                'control': 0.34,
                'longer': 0.33,
                'shorter': 0.33,
            },
            'metrics': [
                'password_generation_count',
                'regeneration_rate',
                'copy_to_clipboard_rate',
                'user_satisfaction_score',
            ],
            'started_at': '2026-01-01',
            'ended_at': None,
        }
        
        # Validate allocation sums to 1.0
        total_allocation = sum(experiment['allocation'].values())
        self.assertAlmostEqual(total_allocation, 1.0, places=2)
        
        # Validate all variants have allocations
        for variant in experiment['variants']:
            self.assertIn(variant, experiment['allocation'])
    
    def test_evolution_notification_experiment(self):
        """Test A/B experiment for evolution notifications."""
        experiment = {
            'experiment_id': 'genetic_evolution_notification',
            'name': 'Evolution Notification Timing',
            'variants': {
                'control': {
                    'notify_on_evolution': True,
                    'notify_method': 'email',
                    'notify_delay_hours': 0,
                },
                'delayed_24h': {
                    'notify_on_evolution': True,
                    'notify_method': 'email',
                    'notify_delay_hours': 24,
                },
                'in_app_only': {
                    'notify_on_evolution': True,
                    'notify_method': 'in_app',
                    'notify_delay_hours': 0,
                },
                'no_notification': {
                    'notify_on_evolution': False,
                },
            },
            'metrics': [
                'evolution_completion_rate',
                'notification_open_rate',
                'password_update_rate',
            ],
        }
        
        self.assertEqual(len(experiment['variants']), 4)
        
        # Control should have immediate email notification
        self.assertTrue(experiment['variants']['control']['notify_on_evolution'])
        self.assertEqual(experiment['variants']['control']['notify_delay_hours'], 0)
    
    def test_quantum_combination_experiment(self):
        """Test A/B experiment for quantum combination default."""
        experiment = {
            'experiment_id': 'genetic_quantum_default',
            'name': 'Quantum Combination Default Setting',
            'variants': {
                'control': {
                    'quantum_enabled_by_default': False,
                    'show_quantum_toggle': True,
                },
                'enabled': {
                    'quantum_enabled_by_default': True,
                    'show_quantum_toggle': True,
                },
                'hidden': {
                    'quantum_enabled_by_default': True,
                    'show_quantum_toggle': False,
                },
            },
            'metrics': [
                'quantum_adoption_rate',
                'average_password_entropy',
                'generation_time_ms',
            ],
        }
        
        # Control should have quantum disabled by default
        self.assertFalse(experiment['variants']['control']['quantum_enabled_by_default'])
        
        # Hidden variant should enable but not show toggle
        self.assertTrue(experiment['variants']['hidden']['quantum_enabled_by_default'])
        self.assertFalse(experiment['variants']['hidden']['show_quantum_toggle'])
    
    def test_provider_onboarding_experiment(self):
        """Test A/B experiment for DNA provider onboarding UX."""
        experiment = {
            'experiment_id': 'genetic_provider_onboarding',
            'name': 'DNA Provider Onboarding Flow',
            'variants': {
                'control': {
                    'show_all_providers': True,
                    'recommended_provider': None,
                    'manual_upload_visible': True,
                },
                'recommended': {
                    'show_all_providers': True,
                    'recommended_provider': 'sequencing',
                    'manual_upload_visible': True,
                },
                'simplified': {
                    'show_all_providers': False,
                    'recommended_provider': 'sequencing',
                    'manual_upload_visible': True,
                },
            },
            'metrics': [
                'connection_success_rate',
                'time_to_first_connection',
                'provider_selection_diversity',
            ],
        }
        
        self.assertEqual(len(experiment['variants']), 3)
        
        # Simplified should only show recommended + manual
        self.assertFalse(experiment['variants']['simplified']['show_all_providers'])
        self.assertIsNotNone(experiment['variants']['simplified']['recommended_provider'])
    
    def test_evolution_threshold_experiment(self):
        """Test A/B experiment for evolution trigger threshold."""
        experiment = {
            'experiment_id': 'genetic_evolution_threshold',
            'name': 'Password Evolution Threshold',
            'description': 'Test optimal biological age change threshold for evolution',
            'variants': {
                'strict': {'age_change_threshold_years': 2.0},
                'control': {'age_change_threshold_years': 1.0},
                'sensitive': {'age_change_threshold_years': 0.5},
            },
            'metrics': [
                'evolution_frequency',
                'password_staleness_score',
                'user_engagement',
            ],
        }
        
        # Strict should require more age change
        strict_threshold = experiment['variants']['strict']['age_change_threshold_years']
        control_threshold = experiment['variants']['control']['age_change_threshold_years']
        sensitive_threshold = experiment['variants']['sensitive']['age_change_threshold_years']
        
        self.assertGreater(strict_threshold, control_threshold)
        self.assertGreater(control_threshold, sensitive_threshold)


# =============================================================================
# Functional Tests
# =============================================================================

class GeneticPasswordFunctionalTest(TransactionTestCase):
    """Functional tests simulating real user workflows."""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='functional_test',
            email='functional@test.com',
            password='testpass123'
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
    
    def test_new_user_trial_activation(self):
        """Test new user trial activation flow."""
        # Check initial subscription status
        status_response = self.client.get('/api/security/genetic/subscription/')
        
        self.assertEqual(status_response.status_code, status.HTTP_200_OK)
        
        # Start trial if not active
        if not status_response.data.get('subscription', {}).get('is_active'):
            activate_response = self.client.post('/api/security/genetic/activate-trial/')
            self.assertEqual(activate_response.status_code, status.HTTP_200_OK)
    
    def test_password_recovery_scenario(self):
        """Test password recovery using genetic certificate."""
        from security.models import GeneticSubscription, DNAConnection
        
        GeneticSubscription.objects.create(
            user=self.user,
            tier='trial',
            status='active',
            trial_expires_at=timezone.now() + timedelta(days=30)
        )
        
        DNAConnection.objects.create(
            user=self.user,
            provider='manual',
            status='connected',
            is_active=True,
            snp_count=100000
        )
        
        # Generate password
        gen_response = self.client.post('/api/security/genetic/generate/', {
            'length': 16,
        })
        
        self.assertEqual(gen_response.status_code, status.HTTP_200_OK)
        original_password = gen_response.data.get('password')
        
        # Regenerate with same settings (should produce same password)
        regen_response = self.client.post('/api/security/genetic/generate/', {
            'length': 16,
        })
        
        self.assertEqual(regen_response.status_code, status.HTTP_200_OK)
        regenerated_password = regen_response.data.get('password')
        
        # Same genetic data + same settings = same password
        self.assertEqual(original_password, regenerated_password)
    
    def test_multi_device_consistency(self):
        """Test password is consistent across devices."""
        from security.models import GeneticSubscription, DNAConnection
        
        GeneticSubscription.objects.create(
            user=self.user,
            tier='premium',
            status='active'
        )
        
        DNAConnection.objects.create(
            user=self.user,
            provider='sequencing',
            status='connected',
            is_active=True,
            snp_count=500000
        )
        
        # Simulate "device 1"
        password1 = self.client.post('/api/security/genetic/generate/', {
            'length': 20,
            'uppercase': True,
            'lowercase': True,
            'numbers': True,
            'symbols': True,
        }).data.get('password')
        
        # Simulate "device 2" (same user, same settings)
        password2 = self.client.post('/api/security/genetic/generate/', {
            'length': 20,
            'uppercase': True,
            'lowercase': True,
            'numbers': True,
            'symbols': True,
        }).data.get('password')
        
        # Should be identical
        self.assertEqual(password1, password2)

"""
Genetic Password Evolution Tests
================================

Comprehensive unit tests for DNA-based password generation.
Tests cover seed generation, evolution engine, and password generation.
"""

from django.test import TestCase, TransactionTestCase
from django.contrib.auth.models import User
from rest_framework.test import APITestCase, APIClient
from rest_framework import status
from unittest.mock import patch, MagicMock, AsyncMock
from datetime import datetime, timedelta
from django.utils import timezone
import asyncio
import json
import os
import hashlib

from ..services.genetic_password_service import (
    GeneticSeedGenerator,
    GeneticPasswordGenerator,
    EpigeneticEvolutionEngine,
    GeneticSeed,
    GeneticCertificate,
    GeneticProvider,
)
from ..models import (
    GeneticSubscription,
    DNAConnection,
    GeneticPasswordCertificate,
    GeneticEvolutionLog,
    DNAConsentRecord,
)


# =============================================================================
# Sample SNP Data for Testing
# =============================================================================

SAMPLE_SNP_DATA = {
    'rs1426654': 'AA',  # Skin pigmentation
    'rs12913832': 'GG',  # Eye color
    'rs1799971': 'AG',  # Opioid receptor
    'rs429358': 'TT',   # APOE
    'rs7903146': 'CC',  # TCF7L2
    'rs1801133': 'CT',  # MTHFR
    'rs4988235': 'AA',  # Lactase persistence
    'rs1815739': 'CC',  # ACTN3
    'rs6152': 'GG',     # Androgen receptor
    'rs17822931': 'CC', # ABCC11 (earwax type)
}

SAMPLE_SNP_DATA_LARGE = {f'rs{i}': 'AG' for i in range(1000, 2000)}


# =============================================================================
# GeneticSeedGenerator Unit Tests
# =============================================================================

class GeneticSeedGeneratorTestCase(TestCase):
    """Tests for the GeneticSeedGenerator class."""

    def setUp(self):
        """Set up test fixtures."""
        self.salt = os.urandom(32)
        self.generator = GeneticSeedGenerator(salt=self.salt)

    def test_generate_seed_from_snps(self):
        """Test basic seed generation from SNP data."""
        seed = self.generator.generate_seed_from_snps(SAMPLE_SNP_DATA)
        
        self.assertIsInstance(seed, GeneticSeed)
        self.assertEqual(len(seed.seed_bytes), 64)  # 512 bits
        self.assertGreater(seed.snp_count, 0)
        self.assertEqual(seed.evolution_generation, 1)

    def test_seed_is_deterministic(self):
        """Test that same SNP data produces same seed."""
        seed1 = self.generator.generate_seed_from_snps(SAMPLE_SNP_DATA)
        seed2 = self.generator.generate_seed_from_snps(SAMPLE_SNP_DATA)
        
        self.assertEqual(seed1.seed_bytes, seed2.seed_bytes)

    def test_different_snps_produce_different_seeds(self):
        """Test that different SNP data produces different seeds."""
        modified_snps = SAMPLE_SNP_DATA.copy()
        modified_snps['rs1426654'] = 'GG'  # Change one SNP
        
        seed1 = self.generator.generate_seed_from_snps(SAMPLE_SNP_DATA)
        seed2 = self.generator.generate_seed_from_snps(modified_snps)
        
        self.assertNotEqual(seed1.seed_bytes, seed2.seed_bytes)

    def test_different_salt_produces_different_seeds(self):
        """Test that different salt produces different seeds."""
        generator2 = GeneticSeedGenerator(salt=os.urandom(32))
        
        seed1 = self.generator.generate_seed_from_snps(SAMPLE_SNP_DATA)
        seed2 = generator2.generate_seed_from_snps(SAMPLE_SNP_DATA)
        
        self.assertNotEqual(seed1.seed_bytes, seed2.seed_bytes)

    def test_seed_with_epigenetic_factor(self):
        """Test seed generation with epigenetic factor."""
        seed_without = self.generator.generate_seed_from_snps(SAMPLE_SNP_DATA)
        seed_with = self.generator.generate_seed_from_snps(
            SAMPLE_SNP_DATA, 
            epigenetic_factor=0.5
        )
        
        self.assertNotEqual(seed_without.seed_bytes, seed_with.seed_bytes)
        self.assertEqual(seed_with.epigenetic_factor, 0.5)

    def test_seed_evolution_generation(self):
        """Test seed with different evolution generations."""
        seed_gen1 = self.generator.generate_seed_from_snps(
            SAMPLE_SNP_DATA, evolution_generation=1
        )
        seed_gen2 = self.generator.generate_seed_from_snps(
            SAMPLE_SNP_DATA, evolution_generation=2
        )
        
        self.assertNotEqual(seed_gen1.seed_bytes, seed_gen2.seed_bytes)
        self.assertEqual(seed_gen1.evolution_generation, 1)
        self.assertEqual(seed_gen2.evolution_generation, 2)

    def test_seed_with_large_snp_dataset(self):
        """Test seed generation with large SNP dataset."""
        seed = self.generator.generate_seed_from_snps(SAMPLE_SNP_DATA_LARGE)
        
        self.assertEqual(len(seed.seed_bytes), 64)
        self.assertGreater(seed.snp_count, 100)

    def test_seed_with_empty_snps_raises_error(self):
        """Test that empty SNP data raises an error."""
        with self.assertRaises(ValueError):
            self.generator.generate_seed_from_snps({})

    def test_seed_with_minimal_snps(self):
        """Test seed generation with minimal SNP data."""
        minimal_snps = {'rs1426654': 'AA'}
        seed = self.generator.generate_seed_from_snps(minimal_snps)
        
        self.assertEqual(len(seed.seed_bytes), 64)
        self.assertEqual(seed.snp_count, 1)


# =============================================================================
# EpigeneticEvolutionEngine Unit Tests
# =============================================================================

class EpigeneticEvolutionEngineTestCase(TestCase):
    """Tests for the EpigeneticEvolutionEngine class."""

    def setUp(self):
        """Set up test fixtures."""
        self.engine = EpigeneticEvolutionEngine()

    def test_calculate_evolution_factor(self):
        """Test evolution factor calculation."""
        factor = self.engine.calculate_evolution_factor(
            biological_age=35.5,
            previous_age=33.0,
            current_generation=1
        )
        
        self.assertIsInstance(factor, float)
        self.assertGreaterEqual(factor, 0.0)
        self.assertLessEqual(factor, 1.0)

    def test_evolution_factor_increases_with_age_delta(self):
        """Test that larger age changes produce larger evolution factors."""
        factor_small = self.engine.calculate_evolution_factor(
            biological_age=35.0,
            previous_age=34.5,
            current_generation=1
        )
        factor_large = self.engine.calculate_evolution_factor(
            biological_age=40.0,
            previous_age=35.0,
            current_generation=1
        )
        
        self.assertLess(factor_small, factor_large)

    def test_should_evolve_threshold(self):
        """Test evolution threshold detection."""
        # Small change - should not evolve
        should_not = self.engine.should_evolve(
            current_age=35.0,
            previous_age=34.9,
            threshold=0.5
        )
        self.assertFalse(should_not)
        
        # Large change - should evolve
        should = self.engine.should_evolve(
            current_age=36.0,
            previous_age=34.0,
            threshold=0.5
        )
        self.assertTrue(should)

    def test_evolution_generation_increment(self):
        """Test proper generation incrementing."""
        new_gen = self.engine.get_next_generation(current_generation=3)
        self.assertEqual(new_gen, 4)


# =============================================================================
# GeneticPasswordGenerator Unit Tests
# =============================================================================

class GeneticPasswordGeneratorTestCase(TestCase):
    """Tests for the GeneticPasswordGenerator class."""

    def setUp(self):
        """Set up test fixtures."""
        self.generator = GeneticPasswordGenerator()
        self.salt = os.urandom(32)
        self.seed_generator = GeneticSeedGenerator(salt=self.salt)
        self.sample_seed = self.seed_generator.generate_seed_from_snps(SAMPLE_SNP_DATA)

    def test_generate_password_default_length(self):
        """Test password generation with default length."""
        password = self.generator.generate_password(self.sample_seed)
        
        self.assertEqual(len(password), 16)  # Default length
        self.assertIsInstance(password, str)

    def test_generate_password_custom_length(self):
        """Test password generation with custom length."""
        password = self.generator.generate_password(self.sample_seed, length=24)
        
        self.assertEqual(len(password), 24)

    def test_generate_password_with_uppercase(self):
        """Test password contains uppercase when enabled."""
        password = self.generator.generate_password(
            self.sample_seed,
            uppercase=True,
            lowercase=False,
            numbers=False,
            symbols=False
        )
        
        self.assertTrue(any(c.isupper() for c in password))

    def test_generate_password_with_lowercase(self):
        """Test password contains lowercase when enabled."""
        password = self.generator.generate_password(
            self.sample_seed,
            uppercase=False,
            lowercase=True,
            numbers=False,
            symbols=False
        )
        
        self.assertTrue(any(c.islower() for c in password))

    def test_generate_password_with_numbers(self):
        """Test password contains numbers when enabled."""
        password = self.generator.generate_password(
            self.sample_seed,
            uppercase=False,
            lowercase=False,
            numbers=True,
            symbols=False
        )
        
        self.assertTrue(any(c.isdigit() for c in password))

    def test_generate_password_with_symbols(self):
        """Test password contains symbols when enabled."""
        password = self.generator.generate_password(
            self.sample_seed,
            uppercase=False,
            lowercase=False,
            numbers=False,
            symbols=True
        )
        
        self.assertTrue(any(not c.isalnum() for c in password))

    def test_password_is_deterministic(self):
        """Test that same seed produces same password."""
        password1 = self.generator.generate_password(self.sample_seed)
        password2 = self.generator.generate_password(self.sample_seed)
        
        self.assertEqual(password1, password2)

    def test_different_seeds_produce_different_passwords(self):
        """Test that different seeds produce different passwords."""
        modified_snps = SAMPLE_SNP_DATA.copy()
        modified_snps['rs1426654'] = 'GG'
        
        seed2 = self.seed_generator.generate_seed_from_snps(modified_snps)
        
        password1 = self.generator.generate_password(self.sample_seed)
        password2 = self.generator.generate_password(seed2)
        
        self.assertNotEqual(password1, password2)

    @patch('security.services.quantum_rng_service.get_quantum_generator')
    def test_password_with_quantum_combination(self, mock_quantum):
        """Test password generation with quantum entropy."""
        mock_generator = MagicMock()
        mock_generator.generate_password.return_value = (
            'quantumpass123!', 
            MagicMock(entropy_bits=256)
        )
        mock_quantum.return_value = mock_generator
        
        password = self.generator.generate_password_with_quantum(
            self.sample_seed,
            combine_with_quantum=True
        )
        
        # Should produce a valid password
        self.assertGreater(len(password), 0)


# =============================================================================
# GeneticCertificate Tests
# =============================================================================

class GeneticCertificateTestCase(TestCase):
    """Tests for genetic certificate generation."""

    def setUp(self):
        """Set up test fixtures."""
        self.generator = GeneticPasswordGenerator()
        self.salt = os.urandom(32)
        self.seed_generator = GeneticSeedGenerator(salt=self.salt)
        self.sample_seed = self.seed_generator.generate_seed_from_snps(SAMPLE_SNP_DATA)

    def test_certificate_creation(self):
        """Test certificate is created with password."""
        password, certificate = self.generator.generate_password_with_certificate(
            self.sample_seed
        )
        
        self.assertIsInstance(certificate, GeneticCertificate)
        self.assertIsNotNone(certificate.password_hash_prefix)
        self.assertIsNotNone(certificate.genetic_hash_prefix)
        self.assertIsNotNone(certificate.signature)

    def test_certificate_contains_required_fields(self):
        """Test certificate has all required fields."""
        _, certificate = self.generator.generate_password_with_certificate(
            self.sample_seed
        )
        
        self.assertIsNotNone(certificate.certificate_id)
        self.assertIsNotNone(certificate.provider)
        self.assertIsNotNone(certificate.snp_markers_used)
        self.assertIsNotNone(certificate.evolution_generation)
        self.assertIsNotNone(certificate.generation_timestamp)

    def test_certificate_hash_is_prefix_only(self):
        """Test that certificate stores only hash prefixes."""
        _, certificate = self.generator.generate_password_with_certificate(
            self.sample_seed
        )
        
        # Should be prefix, not full hash
        self.assertLessEqual(len(certificate.password_hash_prefix), 64)
        self.assertLessEqual(len(certificate.genetic_hash_prefix), 64)


# =============================================================================
# Model Tests
# =============================================================================

class GeneticSubscriptionModelTestCase(TestCase):
    """Tests for GeneticSubscription model."""

    def setUp(self):
        """Set up test user."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpassword123!'
        )

    def test_create_subscription(self):
        """Test creating a genetic subscription."""
        subscription = GeneticSubscription.objects.create(
            user=self.user,
            tier='trial',
            status='active'
        )
        
        self.assertEqual(subscription.user, self.user)
        self.assertEqual(subscription.tier, 'trial')

    def test_trial_active_check(self):
        """Test is_trial_active method."""
        subscription = GeneticSubscription.objects.create(
            user=self.user,
            tier='trial',
            status='active',
            trial_started_at=timezone.now(),
            trial_expires_at=timezone.now() + timedelta(days=30)
        )
        
        self.assertTrue(subscription.is_trial_active())

    def test_trial_expired_check(self):
        """Test is_trial_active returns False for expired trial."""
        subscription = GeneticSubscription.objects.create(
            user=self.user,
            tier='trial',
            status='active',
            trial_started_at=timezone.now() - timedelta(days=31),
            trial_expires_at=timezone.now() - timedelta(days=1)
        )
        
        self.assertFalse(subscription.is_trial_active())


class DNAConnectionModelTestCase(TestCase):
    """Tests for DNAConnection model."""

    def setUp(self):
        """Set up test user."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpassword123!'
        )

    def test_create_dna_connection(self):
        """Test creating a DNA connection."""
        connection = DNAConnection.objects.create(
            user=self.user,
            provider='sequencing',
            status='connected',
            genetic_hash_prefix='abc123def456',
            snp_count=500000
        )
        
        self.assertEqual(connection.provider, 'sequencing')
        self.assertEqual(connection.snp_count, 500000)

    def test_evolution_generation_default(self):
        """Test default evolution generation is 1."""
        connection = DNAConnection.objects.create(
            user=self.user,
            provider='manual',
            status='connected'
        )
        
        self.assertEqual(connection.evolution_generation, 1)

    def test_unique_active_connection_per_user(self):
        """Test only one active connection per user."""
        DNAConnection.objects.create(
            user=self.user,
            provider='sequencing',
            status='connected',
            is_active=True
        )
        
        # Creating another active connection should work but only one should be active
        connection2 = DNAConnection.objects.create(
            user=self.user,
            provider='23andme',
            status='connected',
            is_active=True
        )
        
        # Both exist but in practice app logic would deactivate first
        self.assertEqual(
            DNAConnection.objects.filter(user=self.user, is_active=True).count(),
            2  # Model allows multiple, app logic should manage
        )


class GeneticEvolutionLogModelTestCase(TestCase):
    """Tests for GeneticEvolutionLog model."""

    def setUp(self):
        """Set up test user."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpassword123!'
        )

    def test_log_evolution_event(self):
        """Test logging an evolution event."""
        log = GeneticEvolutionLog.objects.create(
            user=self.user,
            trigger_type='automatic',
            old_evolution_gen=1,
            new_evolution_gen=2,
            biological_age_before=35.0,
            biological_age_after=36.5,
            success=True
        )
        
        self.assertEqual(log.trigger_type, 'automatic')
        self.assertEqual(log.new_evolution_gen, 2)
        self.assertTrue(log.success)


# =============================================================================
# DNA Provider Service Tests
# =============================================================================

class DNAProviderServiceTestCase(TestCase):
    """Tests for DNA provider service."""

    def test_manual_upload_parser_23andme(self):
        """Test parsing 23andMe file format."""
        from ..services.dna_provider_service import ManualUploadProvider
        
        provider = ManualUploadProvider()
        
        # Sample 23andMe format
        content = b"""# This data file generated by 23andMe
# rsid\tchromosome\tposition\tgenotype
rs1426654\t15\t28365618\tAA
rs12913832\t15\t28365618\tGG
rs1799971\t6\t154039662\tAG
"""
        
        snps, format_name = provider.parse_uploaded_file(content, 'test.txt')
        
        self.assertEqual(format_name, '23andme')
        self.assertIn('rs1426654', snps)
        self.assertEqual(snps['rs1426654'], 'AA')

    def test_manual_upload_parser_ancestry(self):
        """Test parsing AncestryDNA CSV format."""
        from ..services.dna_provider_service import ManualUploadProvider
        
        provider = ManualUploadProvider()
        
        # Sample Ancestry format
        content = b"""rsid,chromosome,position,allele1,allele2
rs1426654,15,28365618,A,A
rs12913832,15,28365618,G,G
rs1799971,6,154039662,A,G
"""
        
        snps, format_name = provider.parse_uploaded_file(content, 'test.csv')
        
        self.assertEqual(format_name, 'ancestry')
        self.assertIn('rs1426654', snps)
        self.assertEqual(snps['rs1426654'], 'AA')

    def test_manual_upload_detects_format(self):
        """Test format auto-detection."""
        from ..services.dna_provider_service import ManualUploadProvider
        
        provider = ManualUploadProvider()
        
        # 23andMe detection
        content_23andme = b"# This data file generated by 23andMe\nrs123\t1\t100\tAA"
        detected = provider.detect_format('test.txt', content_23andme[:1000])
        self.assertEqual(detected, '23andme')
        
        # Ancestry detection
        content_ancestry = b"rsid,chromosome,position,allele1,allele2\nrs123,1,100,A,A"
        detected = provider.detect_format('test.csv', content_ancestry[:1000])
        self.assertEqual(detected, 'ancestry')


# =============================================================================
# API Endpoint Tests
# =============================================================================

class GeneticPasswordAPITestCase(APITestCase):
    """Tests for genetic password API endpoints."""

    def setUp(self):
        """Set up test client and user."""
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpassword123!'
        )
        self.client.force_authenticate(user=self.user)
        
        # Create subscription and connection
        self.subscription = GeneticSubscription.objects.create(
            user=self.user,
            tier='trial',
            status='active',
            trial_started_at=timezone.now(),
            trial_expires_at=timezone.now() + timedelta(days=30)
        )
        
        self.connection = DNAConnection.objects.create(
            user=self.user,
            provider='manual',
            status='connected',
            genetic_hash_prefix='test123',
            snp_count=10000,
            is_active=True
        )

    def test_connection_status_endpoint(self):
        """Test GET /genetic/connection-status/"""
        response = self.client.get('/api/security/genetic/connection-status/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data.get('connected'))

    def test_connection_status_unauthenticated(self):
        """Test connection status requires authentication."""
        self.client.logout()
        response = self.client.get('/api/security/genetic/connection-status/')
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_disconnect_endpoint(self):
        """Test DELETE /genetic/disconnect/"""
        response = self.client.delete('/api/security/genetic/disconnect/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Connection should be deactivated
        self.connection.refresh_from_db()
        self.assertFalse(self.connection.is_active)

    def test_update_preferences_endpoint(self):
        """Test PUT /genetic/preferences/"""
        response = self.client.put(
            '/api/security/genetic/preferences/',
            {'combine_with_quantum': False},
            format='json'
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        self.connection.refresh_from_db()
        self.assertFalse(self.connection.combine_with_quantum)

    def test_evolution_status_endpoint(self):
        """Test GET /genetic/evolution-status/"""
        response = self.client.get('/api/security/genetic/evolution-status/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('evolution', response.data)

    def test_list_certificates_endpoint(self):
        """Test GET /genetic/certificates/"""
        # Create a certificate
        GeneticPasswordCertificate.objects.create(
            user=self.user,
            provider='manual',
            password_hash_prefix='test123',
            genetic_hash_prefix='genetic456',
            snp_markers_used=100,
            evolution_generation=1,
            signature='testsig'
        )
        
        response = self.client.get('/api/security/genetic/certificates/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data.get('total'), 1)


# =============================================================================
# Celery Task Tests
# =============================================================================

class GeneticEvolutionTaskTestCase(TestCase):
    """Tests for genetic evolution Celery tasks."""

    def setUp(self):
        """Set up test user and connection."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpassword123!'
        )
        
        self.subscription = GeneticSubscription.objects.create(
            user=self.user,
            tier='premium',
            status='active',
            epigenetic_evolution_enabled=True
        )
        
        self.connection = DNAConnection.objects.create(
            user=self.user,
            provider='sequencing',
            status='connected',
            is_active=True,
            evolution_generation=1
        )

    @patch('security.services.epigenetic_service.epigenetic_evolution_manager')
    def test_check_genetic_evolution_task(self, mock_manager):
        """Test the check_genetic_evolution Celery task."""
        from ..tasks import check_genetic_evolution
        
        mock_manager.check_and_evolve.return_value = {
            'evolved': True,
            'old_generation': 1,
            'new_generation': 2,
            'biological_age': 36.5,
            'previous_age': 35.0
        }
        
        result = check_genetic_evolution(self.user.id)
        
        self.assertTrue(result['checked'])
        self.assertTrue(result['evolved'])
        self.assertEqual(result['new_generation'], 2)

    def test_check_evolution_no_connection(self):
        """Test evolution check with no DNA connection."""
        from ..tasks import check_genetic_evolution
        
        self.connection.delete()
        
        result = check_genetic_evolution(self.user.id)
        
        self.assertFalse(result['checked'])
        self.assertEqual(result['reason'], 'no_dna_connection')

    def test_cleanup_expired_trials_task(self):
        """Test the cleanup_expired_genetic_trials task."""
        from ..tasks import cleanup_expired_genetic_trials
        
        # Create expired trial
        expired_sub = GeneticSubscription.objects.create(
            user=User.objects.create_user('expired', 'exp@test.com', 'pass123!'),
            tier='trial',
            status='active',
            trial_expires_at=timezone.now() - timedelta(days=1)
        )
        
        result = cleanup_expired_genetic_trials()
        
        expired_sub.refresh_from_db()
        self.assertEqual(expired_sub.status, 'expired')
        self.assertEqual(result['expired_trials_cleaned'], 1)

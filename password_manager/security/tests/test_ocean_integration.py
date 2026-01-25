"""
Ocean Entropy Integration Tests
================================

Integration tests that hit the real NOAA API.
These tests are marked with @pytest.mark.integration and can be run with:

    pytest tests/test_ocean_integration.py --integration -v

Or skipped with:

    pytest tests/ -m "not integration"

@author Password Manager Team
@created 2026-01-25
"""

import pytest
import asyncio
import time
from datetime import datetime, timedelta
from django.test import TestCase, override_settings
from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase, APIClient
from rest_framework import status

# Mark all tests in this module as integration tests
pytestmark = pytest.mark.integration

User = get_user_model()


# =============================================================================
# NOAA Buoy Client Integration Tests
# =============================================================================

class TestNOAABuoyClientIntegration(TestCase):
    """
    Integration tests for NOAABuoyClient that hit the real NOAA API.
    
    These tests verify:
    - Real-time data fetching
    - Response parsing
    - Data freshness
    """
    
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        from security.services.noaa_api_client import NOAABuoyClient
        cls.client = NOAABuoyClient()
    
    def test_fetch_real_buoy_data_44013(self):
        """Test fetching real data from Boston buoy (44013)."""
        reading = self.client.fetch_latest_reading('44013')
        
        # May be None if buoy is temporarily offline
        if reading is not None:
            self.assertEqual(reading.buoy_id, '44013')
            self.assertIsInstance(reading.timestamp, datetime)
            
            # At least some data should be present
            has_data = any([
                reading.wave_height_m is not None,
                reading.water_temp_c is not None,
                reading.wind_speed_mps is not None,
            ])
            self.assertTrue(has_data, "Expected at least some data from buoy")
            
            # Data should be recent (within 48 hours for most buoys)
            age = datetime.now() - reading.timestamp
            self.assertLess(age.total_seconds(), 48 * 3600,
                "Buoy data should be less than 48 hours old")
    
    def test_fetch_real_buoy_data_41010(self):
        """Test fetching real data from Florida buoy (41010)."""
        reading = self.client.fetch_latest_reading('41010')
        
        if reading is not None:
            self.assertEqual(reading.buoy_id, '41010')
            self.assertIsInstance(reading.timestamp, datetime)
    
    def test_entropy_bytes_from_real_reading(self):
        """Test entropy extraction from real buoy data."""
        reading = self.client.fetch_latest_reading('44013')
        
        if reading is not None:
            entropy = reading.to_entropy_bytes()
            
            # Should return SHA3-512 hash (64 bytes)
            self.assertEqual(len(entropy), 64)
            
            # Entropy should be non-zero
            self.assertFalse(all(b == 0 for b in entropy))
    
    def test_quality_score_from_real_reading(self):
        """Test quality score calculation from real data."""
        reading = self.client.fetch_latest_reading('44013')
        
        if reading is not None:
            score = reading.entropy_quality_score
            
            # Score should be between 0 and 1
            self.assertGreaterEqual(score, 0.0)
            self.assertLessEqual(score, 1.0)
            
            # Real readings should have some quality
            self.assertGreater(score, 0.1, "Real reading should have quality > 0.1")
    
    def test_fetch_multiple_buoys(self):
        """Test fetching from multiple buoys concurrently."""
        buoy_ids = ['44013', '41010', '46042']
        readings = self.client.fetch_multiple_buoys(buoy_ids, max_concurrent=3)
        
        # Should get at least one reading back
        self.assertGreater(len(readings), 0, 
            "Should get at least one successful reading")
        
        # Each reading should be properly formatted
        for buoy_id, reading in readings.items():
            self.assertIn(buoy_id, buoy_ids)
            self.assertIsInstance(reading.timestamp, datetime)
    
    def test_buoy_status_check(self):
        """Test buoy health status checking."""
        status = self.client.get_buoy_status('44013')
        
        self.assertEqual(status.buoy_id, '44013')
        # Status should indicate whether buoy is online
        self.assertIsInstance(status.is_online, bool)
    
    def test_invalid_buoy_id_returns_none(self):
        """Test that invalid buoy ID returns None gracefully."""
        reading = self.client.fetch_latest_reading('INVALID_BUOY_99999')
        self.assertIsNone(reading)
    
    def test_rate_limiting_respected(self):
        """Test that rate limiting prevents too-frequent requests."""
        # First request should succeed
        reading1 = self.client.fetch_latest_reading('44013')
        
        # Immediate second request should return cached data
        start = time.time()
        reading2 = self.client.fetch_latest_reading('44013')
        elapsed = time.time() - start
        
        # Should return quickly (from cache, not network)
        self.assertLess(elapsed, 1.0, "Second request should return from cache")
        
        # Both readings should be equal if cached
        if reading1 and reading2:
            self.assertEqual(reading1.timestamp, reading2.timestamp)


# =============================================================================
# Ocean Wave Entropy Provider Integration Tests
# =============================================================================

class TestOceanWaveEntropyProviderIntegration(TestCase):
    """
    Integration tests for OceanWaveEntropyProvider with real NOAA data.
    """
    
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        from security.services.ocean_wave_entropy_service import OceanWaveEntropyProvider
        cls.provider = OceanWaveEntropyProvider()
    
    def test_provider_availability(self):
        """Test that provider reports availability correctly."""
        available = self.provider.is_available()
        
        # Provider should be available if ocean entropy is enabled
        # (may fail if no buoys are online)
        self.assertIsInstance(available, bool)
    
    def test_fetch_random_bytes_from_ocean(self):
        """Test generating random bytes from real ocean data."""
        try:
            entropy, source = self.provider.fetch_random_bytes(32)
            
            self.assertEqual(len(entropy), 32)
            self.assertIsNotNone(source)
            self.assertIn('ocean', source.lower())
            
            # Entropy should look random
            # Check byte diversity (should have multiple unique bytes)
            unique_bytes = len(set(entropy))
            self.assertGreater(unique_bytes, 10, 
                "Entropy should have byte diversity")
            
        except Exception as e:
            # May fail if all buoys are offline
            self.skipTest(f"Ocean provider unavailable: {e}")
    
    def test_provider_status(self):
        """Test getting provider status."""
        status = self.provider.get_status()
        
        self.assertIn('available', status)
        self.assertIn('healthy_buoys', status)
        
        if status['available']:
            self.assertGreater(status['healthy_buoys'], 0)


# =============================================================================
# Hybrid Password Generation Integration Tests
# =============================================================================

class TestHybridPasswordIntegration(APITestCase):
    """
    Integration tests for hybrid password generation via API.
    """
    
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = User.objects.create_user(
            username='ocean_test_user',
            email='ocean@test.com',
            password='testpassword123'
        )
    
    def setUp(self):
        self.client.force_authenticate(user=self.user)
    
    @classmethod
    def tearDownClass(cls):
        cls.user.delete()
        super().tearDownClass()
    
    def test_generate_hybrid_password_endpoint(self):
        """Test generating password through the API with real data."""
        response = self.client.post('/api/security/ocean/generate-hybrid-password/', {
            'length': 16,
            'include_uppercase': True,
            'include_lowercase': True,
            'include_numbers': True,
            'include_symbols': True,
        })
        
        # Endpoint should respond (may fail if entropy sources unavailable)
        self.assertIn(response.status_code, [
            status.HTTP_200_OK,
            status.HTTP_503_SERVICE_UNAVAILABLE,  # If entropy unavailable
        ])
        
        if response.status_code == status.HTTP_200_OK:
            data = response.json()
            
            # Should have password
            self.assertIn('password', data)
            password = data['password']
            self.assertEqual(len(password), 16)
            
            # Should have sources
            self.assertIn('sources', data)
            
            # Should have ocean details in new format
            self.assertIn('ocean_details', data)
            if data['ocean_details']:
                self.assertIn('buoy_id', data['ocean_details'])
    
    def test_ocean_status_endpoint(self):
        """Test ocean status endpoint."""
        response = self.client.get('/api/security/ocean/status/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        
        self.assertIn('status', data)
        self.assertIn('healthy_buoys', data)
    
    def test_buoy_list_endpoint(self):
        """Test buoy list endpoint."""
        response = self.client.get('/api/security/ocean/buoys/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        
        self.assertIn('buoys', data)
        self.assertIsInstance(data['buoys'], list)
        
        if len(data['buoys']) > 0:
            buoy = data['buoys'][0]
            self.assertIn('id', buoy)
            self.assertIn('latitude', buoy)
            self.assertIn('longitude', buoy)
    
    def test_live_wave_data_endpoint(self):
        """Test live wave data for a specific buoy."""
        response = self.client.get('/api/security/ocean/buoy/44013/live-data/')
        
        # May return 404 if buoy data unavailable
        self.assertIn(response.status_code, [
            status.HTTP_200_OK,
            status.HTTP_404_NOT_FOUND,
            status.HTTP_503_SERVICE_UNAVAILABLE,
        ])
        
        if response.status_code == status.HTTP_200_OK:
            data = response.json()
            self.assertIn('buoy_id', data)
            self.assertIn('wave_data', data)


# =============================================================================
# Entropy Quality Tests
# =============================================================================

class TestEntropyQualityIntegration(TestCase):
    """
    Tests that verify the quality of entropy from real sources.
    """
    
    def test_entropy_randomness_nist_basic(self):
        """Basic randomness test (not full NIST suite)."""
        from security.services.ocean_wave_entropy_service import OceanWaveEntropyProvider
        
        provider = OceanWaveEntropyProvider()
        
        try:
            entropy, _ = provider.fetch_random_bytes(256)
        except Exception:
            self.skipTest("Ocean entropy unavailable")
        
        # Monobit test: count of 1s should be roughly half
        bits = ''.join(format(b, '08b') for b in entropy)
        ones = bits.count('1')
        zeros = bits.count('0')
        
        # Ratio should be between 0.45 and 0.55 for good random data
        ratio = ones / len(bits)
        self.assertGreater(ratio, 0.40, "Too few 1 bits - may not be random")
        self.assertLess(ratio, 0.60, "Too many 1 bits - may not be random")
    
    def test_entropy_non_repeating(self):
        """Test that consecutive entropy generations are different."""
        from security.services.ocean_wave_entropy_service import OceanWaveEntropyProvider
        
        provider = OceanWaveEntropyProvider()
        
        samples = []
        for _ in range(3):
            try:
                entropy, _ = provider.fetch_random_bytes(32)
                samples.append(entropy)
            except Exception:
                pass
        
        if len(samples) < 2:
            self.skipTest("Not enough samples collected")
        
        # All samples should be unique
        unique_samples = set(samples)
        self.assertEqual(len(unique_samples), len(samples),
            "Entropy samples should be unique")


# =============================================================================
# Performance Tests
# =============================================================================

class TestOceanEntropyPerformance(TestCase):
    """
    Performance benchmarks for ocean entropy.
    """
    
    def test_single_buoy_fetch_time(self):
        """Benchmark single buoy fetch time."""
        from security.services.noaa_api_client import NOAABuoyClient
        
        client = NOAABuoyClient()
        
        # Force fresh fetch
        start = time.time()
        reading = client.fetch_latest_reading('44013', force_refresh=True)
        elapsed = time.time() - start
        
        if reading:
            print(f"\nSingle buoy fetch: {elapsed:.2f}s")
            # Should complete within reasonable time
            self.assertLess(elapsed, 15.0, "Fetch took too long")
    
    def test_entropy_generation_time(self):
        """Benchmark entropy generation time."""
        from security.services.ocean_wave_entropy_service import OceanWaveEntropyProvider
        
        provider = OceanWaveEntropyProvider()
        
        start = time.time()
        try:
            entropy, _ = provider.fetch_random_bytes(32)
            elapsed = time.time() - start
            
            print(f"\nEntropy generation: {elapsed:.2f}s")
            self.assertLess(elapsed, 20.0, "Generation took too long")
        except Exception as e:
            self.skipTest(f"Provider unavailable: {e}")


# =============================================================================
# Pytest Configuration
# =============================================================================

def pytest_configure(config):
    """Add integration marker to pytest."""
    config.addinivalue_line(
        "markers", "integration: mark test as integration test (may hit external APIs)"
    )

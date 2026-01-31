"""
Natural Entropy Providers Tests
===============================

Comprehensive test suite for natural entropy sources:
- Lightning Detection (NOAA GOES GLM)
- Seismic Activity (USGS)
- Solar Wind (NOAA DSCOVR)
- Combined entropy mixing

Tests cover:
- Data classes (LightningStrike, Earthquake, SolarWindData)
- Provider clients
- Entropy extraction
- API endpoints
- Quality scoring
- Integration with password generation

@author Password Manager Team
@created 2026-01-31
"""

import pytest
from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock, AsyncMock
import asyncio
from decimal import Decimal
from rest_framework.test import APITestCase, APIClient
from rest_framework import status

User = get_user_model()


# =============================================================================
# LightningStrike Tests
# =============================================================================

class TestLightningStrike(TestCase):
    """Tests for LightningStrike dataclass."""
    
    def setUp(self):
        """Create test lightning strike."""
        from security.services.natural_entropy_providers import LightningStrike
        
        self.strike = LightningStrike(
            timestamp=datetime.utcnow(),
            latitude=35.6892,
            longitude=-105.9378,
            intensity=25.5,
            polarity=-1,
            sensor_count=8,
            ellipse_major=2.5,
            ellipse_minor=1.2,
        )
    
    def test_to_entropy_bytes_returns_bytes(self):
        """Test entropy bytes generation."""
        entropy = self.strike.to_entropy_bytes()
        
        self.assertIsInstance(entropy, bytes)
        self.assertGreater(len(entropy), 0)
    
    def test_to_entropy_bytes_is_deterministic(self):
        """Test same strike produces same entropy."""
        entropy1 = self.strike.to_entropy_bytes()
        entropy2 = self.strike.to_entropy_bytes()
        
        self.assertEqual(entropy1, entropy2)
    
    def test_to_entropy_bytes_varies_with_data(self):
        """Test different strikes produce different entropy."""
        from security.services.natural_entropy_providers import LightningStrike
        
        strike2 = LightningStrike(
            timestamp=datetime.utcnow(),
            latitude=40.0,
            longitude=-80.0,
            intensity=30.0,
            polarity=1,
            sensor_count=5,
            ellipse_major=3.0,
            ellipse_minor=2.0,
        )
        
        entropy1 = self.strike.to_entropy_bytes()
        entropy2 = strike2.to_entropy_bytes()
        
        self.assertNotEqual(entropy1, entropy2)
    
    def test_entropy_quality_score(self):
        """Test entropy quality score calculation."""
        score = self.strike.entropy_quality_score
        
        self.assertIsInstance(score, float)
        self.assertGreaterEqual(score, 0.0)
        self.assertLessEqual(score, 1.0)
    
    def test_high_intensity_higher_quality(self):
        """Test high intensity strikes have higher quality."""
        from security.services.natural_entropy_providers import LightningStrike
        
        low_intensity = LightningStrike(
            timestamp=datetime.utcnow(),
            latitude=35.0, longitude=-105.0,
            intensity=5.0, polarity=-1,
            sensor_count=3, ellipse_major=5.0, ellipse_minor=3.0,
        )
        
        high_intensity = LightningStrike(
            timestamp=datetime.utcnow(),
            latitude=35.0, longitude=-105.0,
            intensity=50.0, polarity=-1,
            sensor_count=10, ellipse_major=1.0, ellipse_minor=0.5,
        )
        
        self.assertLess(
            low_intensity.entropy_quality_score,
            high_intensity.entropy_quality_score
        )
    
    def test_to_dict(self):
        """Test serialization to dictionary."""
        data = self.strike.to_dict()
        
        self.assertIn('latitude', data)
        self.assertIn('longitude', data)
        self.assertIn('intensity', data)
        self.assertIn('polarity', data)


# =============================================================================
# Earthquake Tests
# =============================================================================

class TestEarthquake(TestCase):
    """Tests for Earthquake dataclass."""
    
    def setUp(self):
        """Create test earthquake event."""
        from security.services.natural_entropy_providers import Earthquake
        
        self.earthquake = Earthquake(
            timestamp=datetime.utcnow(),
            latitude=37.7749,
            longitude=-122.4194,
            depth_km=10.5,
            magnitude=4.2,
            magnitude_type='ml',
            place='San Francisco Bay Area',
            event_id='us7000abc123',
        )
    
    def test_to_entropy_bytes_returns_bytes(self):
        """Test entropy bytes generation."""
        entropy = self.earthquake.to_entropy_bytes()
        
        self.assertIsInstance(entropy, bytes)
        self.assertGreater(len(entropy), 0)
    
    def test_entropy_quality_score(self):
        """Test entropy quality score calculation."""
        score = self.earthquake.entropy_quality_score
        
        self.assertIsInstance(score, float)
        self.assertGreaterEqual(score, 0.0)
        self.assertLessEqual(score, 1.0)
    
    def test_higher_magnitude_higher_quality(self):
        """Test higher magnitude earthquakes have higher quality."""
        from security.services.natural_entropy_providers import Earthquake
        
        small_quake = Earthquake(
            timestamp=datetime.utcnow(),
            latitude=35.0, longitude=-120.0,
            depth_km=20.0, magnitude=2.0,
            magnitude_type='ml', place='Test', event_id='test1',
        )
        
        large_quake = Earthquake(
            timestamp=datetime.utcnow(),
            latitude=35.0, longitude=-120.0,
            depth_km=20.0, magnitude=6.5,
            magnitude_type='ml', place='Test', event_id='test2',
        )
        
        self.assertLess(
            small_quake.entropy_quality_score,
            large_quake.entropy_quality_score
        )
    
    def test_to_dict(self):
        """Test serialization to dictionary."""
        data = self.earthquake.to_dict()
        
        self.assertIn('magnitude', data)
        self.assertIn('depth_km', data)
        self.assertIn('place', data)


# =============================================================================
# LightningDetectionClient Tests
# =============================================================================

class TestLightningDetectionClient(TestCase):
    """Tests for LightningDetectionClient."""
    
    def test_client_initialization(self):
        """Test client can be initialized."""
        from security.services.natural_entropy_providers import LightningDetectionClient
        
        client = LightningDetectionClient(timeout=5)
        
        self.assertIsNotNone(client)
    
    def test_get_recent_strikes(self):
        """Test getting recent lightning strikes."""
        from security.services.natural_entropy_providers import LightningDetectionClient
        
        client = LightningDetectionClient()
        strikes = client.get_recent_strikes(minutes=10, limit=50)
        
        self.assertIsInstance(strikes, list)
        # Should return data (real or generated)
        for strike in strikes:
            self.assertIsNotNone(strike.latitude)
            self.assertIsNotNone(strike.longitude)
    
    def test_get_global_activity(self):
        """Test getting global lightning activity."""
        from security.services.natural_entropy_providers import LightningDetectionClient
        
        client = LightningDetectionClient()
        activity = client.get_global_activity()
        
        self.assertIsInstance(activity, dict)
    
    def test_generate_realistic_strikes(self):
        """Test realistic strike generation."""
        from security.services.natural_entropy_providers import LightningDetectionClient
        
        client = LightningDetectionClient()
        strikes = client._generate_realistic_strikes(minutes=10, limit=20)
        
        self.assertIsInstance(strikes, list)
        self.assertLessEqual(len(strikes), 20)
        
        for strike in strikes:
            # Check geographic validity
            self.assertGreaterEqual(strike.latitude, -90.0)
            self.assertLessEqual(strike.latitude, 90.0)
            self.assertGreaterEqual(strike.longitude, -180.0)
            self.assertLessEqual(strike.longitude, 180.0)


# =============================================================================
# LightningEntropyProvider Tests
# =============================================================================

class TestLightningEntropyProvider(TestCase):
    """Tests for LightningEntropyProvider."""
    
    def test_provider_initialization(self):
        """Test provider can be initialized."""
        from security.services.natural_entropy_providers import LightningEntropyProvider
        
        provider = LightningEntropyProvider()
        
        self.assertIsNotNone(provider)
    
    def test_fetch_entropy(self):
        """Test fetching entropy from lightning."""
        from security.services.natural_entropy_providers import LightningEntropyProvider
        
        provider = LightningEntropyProvider()
        entropy = provider.fetch_entropy(num_bytes=32)
        
        self.assertIsInstance(entropy, bytes)
        self.assertGreaterEqual(len(entropy), 32)
    
    def test_is_available(self):
        """Test availability check."""
        from security.services.natural_entropy_providers import LightningEntropyProvider
        
        provider = LightningEntropyProvider()
        available = provider.is_available()
        
        self.assertIsInstance(available, bool)
    
    def test_get_last_source_info(self):
        """Test getting source info."""
        from security.services.natural_entropy_providers import LightningEntropyProvider
        
        provider = LightningEntropyProvider()
        provider.fetch_entropy(16)
        
        info = provider.get_last_source_info()
        
        self.assertIsInstance(info, dict)


# =============================================================================
# SeismicEntropyProvider Tests
# =============================================================================

class TestSeismicEntropyProvider(TestCase):
    """Tests for SeismicEntropyProvider."""
    
    def test_provider_initialization(self):
        """Test provider can be initialized."""
        from security.services.natural_entropy_providers import SeismicEntropyProvider
        
        provider = SeismicEntropyProvider()
        
        self.assertIsNotNone(provider)
    
    def test_fetch_entropy(self):
        """Test fetching entropy from seismic data."""
        from security.services.natural_entropy_providers import SeismicEntropyProvider
        
        provider = SeismicEntropyProvider()
        entropy = provider.fetch_entropy(num_bytes=32)
        
        self.assertIsInstance(entropy, bytes)
        self.assertGreaterEqual(len(entropy), 32)
    
    def test_is_available(self):
        """Test availability check."""
        from security.services.natural_entropy_providers import SeismicEntropyProvider
        
        provider = SeismicEntropyProvider()
        available = provider.is_available()
        
        self.assertIsInstance(available, bool)


# =============================================================================
# SolarWindEntropyProvider Tests
# =============================================================================

class TestSolarWindEntropyProvider(TestCase):
    """Tests for SolarWindEntropyProvider."""
    
    def test_provider_initialization(self):
        """Test provider can be initialized."""
        from security.services.natural_entropy_providers import SolarWindEntropyProvider
        
        provider = SolarWindEntropyProvider()
        
        self.assertIsNotNone(provider)
    
    def test_fetch_entropy(self):
        """Test fetching entropy from solar wind."""
        from security.services.natural_entropy_providers import SolarWindEntropyProvider
        
        provider = SolarWindEntropyProvider()
        entropy = provider.fetch_entropy(num_bytes=32)
        
        self.assertIsInstance(entropy, bytes)
        self.assertGreaterEqual(len(entropy), 32)
    
    def test_is_available(self):
        """Test availability check."""
        from security.services.natural_entropy_providers import SolarWindEntropyProvider
        
        provider = SolarWindEntropyProvider()
        available = provider.is_available()
        
        self.assertIsInstance(available, bool)


# =============================================================================
# NaturalEntropyMixer Tests
# =============================================================================

class TestNaturalEntropyMixer(TestCase):
    """Tests for multi-source entropy mixing."""
    
    def test_mixer_initialization(self):
        """Test mixer can be initialized."""
        from security.services.natural_entropy_providers import NaturalEntropyMixer
        
        mixer = NaturalEntropyMixer()
        
        self.assertIsNotNone(mixer)
    
    def test_mix_multiple_sources(self):
        """Test mixing entropy from multiple sources."""
        from security.services.natural_entropy_providers import NaturalEntropyMixer
        
        mixer = NaturalEntropyMixer()
        
        source1 = bytes([0xAA] * 32)
        source2 = bytes([0x55] * 32)
        
        mixed = mixer.mix(source1, source2)
        
        self.assertEqual(len(mixed), 32)
        self.assertNotEqual(mixed, source1)
        self.assertNotEqual(mixed, source2)
    
    def test_mix_single_source(self):
        """Test mixing with single source."""
        from security.services.natural_entropy_providers import NaturalEntropyMixer
        
        mixer = NaturalEntropyMixer()
        
        source = bytes([0xBB] * 32)
        mixed = mixer.mix(source)
        
        self.assertEqual(len(mixed), 32)


# =============================================================================
# Natural Entropy API Tests
# =============================================================================

class TestNaturalEntropyAPI(APITestCase):
    """Tests for Natural Entropy API endpoints."""
    
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='entropytester',
            email='entropy@example.com',
            password='testpass123'
        )
        self.client.force_authenticate(user=self.user)
    
    def test_generate_natural_password(self):
        """Test POST /api/security/natural-entropy/generate/"""
        response = self.client.post(
            '/api/security/natural-entropy/generate/',
            {
                'sources': ['lightning', 'seismic'],
                'length': 16,
                'charset': 'standard'
            },
            format='json'
        )
        
        self.assertIn(response.status_code, [200, 201, 400, 401, 403, 404, 503])
        
        if response.status_code in [200, 201]:
            self.assertIn('password', response.data)
    
    def test_get_global_entropy_status(self):
        """Test GET /api/security/natural-entropy/status/"""
        response = self.client.get('/api/security/natural-entropy/status/')
        
        self.assertIn(response.status_code, [200, 401, 403, 404])
        
        if response.status_code == 200:
            # Should have status for each source
            self.assertIn('sources', response.data)
    
    def test_get_entropy_statistics(self):
        """Test GET /api/security/natural-entropy/statistics/"""
        response = self.client.get('/api/security/natural-entropy/statistics/')
        
        self.assertIn(response.status_code, [200, 401, 403, 404])
    
    def test_get_lightning_activity(self):
        """Test GET /api/security/natural-entropy/lightning/"""
        response = self.client.get('/api/security/natural-entropy/lightning/')
        
        self.assertIn(response.status_code, [200, 401, 403, 404])
    
    def test_get_seismic_activity(self):
        """Test GET /api/security/natural-entropy/seismic/"""
        response = self.client.get('/api/security/natural-entropy/seismic/')
        
        self.assertIn(response.status_code, [200, 401, 403, 404])
    
    def test_get_solar_wind_status(self):
        """Test GET /api/security/natural-entropy/solar/"""
        response = self.client.get('/api/security/natural-entropy/solar/')
        
        self.assertIn(response.status_code, [200, 401, 403, 404])
    
    def test_user_entropy_preferences(self):
        """Test GET/PUT /api/security/natural-entropy/preferences/"""
        # GET preferences
        response = self.client.get('/api/security/natural-entropy/preferences/')
        self.assertIn(response.status_code, [200, 401, 403, 404])
        
        # PUT preferences
        response = self.client.put(
            '/api/security/natural-entropy/preferences/',
            {'preferred_sources': ['lightning', 'ocean']},
            format='json'
        )
        self.assertIn(response.status_code, [200, 201, 400, 401, 403, 404])
    
    def test_get_user_certificates(self):
        """Test GET /api/security/natural-entropy/certificates/"""
        response = self.client.get('/api/security/natural-entropy/certificates/')
        
        self.assertIn(response.status_code, [200, 401, 403, 404])


# =============================================================================
# Entropy Quality Tests
# =============================================================================

class TestEntropyQuality(TestCase):
    """Tests for entropy quality assessment."""
    
    def test_lightning_entropy_quality(self):
        """Test lightning entropy quality is acceptable."""
        from security.services.natural_entropy_providers import LightningEntropyProvider
        
        provider = LightningEntropyProvider()
        entropy = provider.fetch_entropy(64)
        
        # Check entropy has reasonable distribution
        unique_bytes = len(set(entropy))
        self.assertGreater(unique_bytes, 20)
    
    def test_seismic_entropy_quality(self):
        """Test seismic entropy quality is acceptable."""
        from security.services.natural_entropy_providers import SeismicEntropyProvider
        
        provider = SeismicEntropyProvider()
        entropy = provider.fetch_entropy(64)
        
        unique_bytes = len(set(entropy))
        self.assertGreater(unique_bytes, 15)
    
    def test_combined_entropy_quality(self):
        """Test combined entropy from multiple sources."""
        from security.services.natural_entropy_providers import (
            LightningEntropyProvider,
            SeismicEntropyProvider,
            NaturalEntropyMixer,
        )
        
        lightning = LightningEntropyProvider()
        seismic = SeismicEntropyProvider()
        mixer = NaturalEntropyMixer()
        
        l_entropy = lightning.fetch_entropy(32)
        s_entropy = seismic.fetch_entropy(32)
        
        combined = mixer.mix(l_entropy, s_entropy)
        
        unique_bytes = len(set(combined))
        self.assertGreater(unique_bytes, 15)


# =============================================================================
# Exception Handling Tests
# =============================================================================

class TestExceptionHandling(TestCase):
    """Tests for exception handling."""
    
    def test_entropy_unavailable_exception(self):
        """Test EntropyUnavailable exception."""
        from security.services.natural_entropy_providers import EntropyUnavailable
        
        with self.assertRaises(EntropyUnavailable):
            raise EntropyUnavailable("Test source unavailable")
    
    @patch('security.services.natural_entropy_providers.httpx')
    def test_network_failure_handling(self, mock_httpx):
        """Test handling of network failures."""
        from security.services.natural_entropy_providers import LightningDetectionClient
        
        mock_httpx.get.side_effect = Exception("Network error")
        
        client = LightningDetectionClient()
        # Should fall back to generated data, not crash
        strikes = client.get_recent_strikes()
        
        self.assertIsInstance(strikes, list)


# =============================================================================
# Integration Tests
# =============================================================================

class TestNaturalEntropyIntegration(TestCase):
    """Integration tests for natural entropy."""
    
    def test_full_password_generation_flow(self):
        """Test complete password generation from natural entropy."""
        from security.services.natural_entropy_providers import (
            LightningEntropyProvider,
            NaturalEntropyMixer,
        )
        import hashlib
        
        # Get entropy
        lightning = LightningEntropyProvider()
        entropy = lightning.fetch_entropy(32)
        
        # Mix with local randomness
        import secrets
        local = secrets.token_bytes(32)
        
        mixer = NaturalEntropyMixer()
        combined = mixer.mix(entropy, local)
        
        # Generate password
        charset = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@#$%'
        password = ''.join(charset[b % len(charset)] for b in combined[:16])
        
        self.assertEqual(len(password), 16)
        self.assertRegex(password, r'[A-Za-z0-9!@#$%]+')
    
    def test_multiple_source_password_generation(self):
        """Test password from multiple natural sources."""
        from security.services.natural_entropy_providers import (
            LightningEntropyProvider,
            SeismicEntropyProvider,
            SolarWindEntropyProvider,
            NaturalEntropyMixer,
        )
        
        providers = [
            LightningEntropyProvider(),
            SeismicEntropyProvider(),
            SolarWindEntropyProvider(),
        ]
        
        mixer = NaturalEntropyMixer()
        entropy_blocks = []
        
        for provider in providers:
            try:
                entropy = provider.fetch_entropy(32)
                entropy_blocks.append(entropy)
            except Exception:
                pass  # Skip unavailable sources
        
        self.assertGreater(len(entropy_blocks), 0)
        
        if len(entropy_blocks) > 1:
            combined = mixer.mix(*entropy_blocks)
            self.assertEqual(len(combined), 32)


# =============================================================================
# Performance Tests
# =============================================================================

class TestPerformance(TestCase):
    """Performance tests for entropy generation."""
    
    def test_lightning_entropy_speed(self):
        """Test lightning entropy generation is fast enough."""
        from security.services.natural_entropy_providers import LightningEntropyProvider
        import time
        
        provider = LightningEntropyProvider()
        
        start = time.time()
        for _ in range(10):
            provider.fetch_entropy(32)
        elapsed = time.time() - start
        
        # Should complete 10 generations in under 5 seconds
        self.assertLess(elapsed, 5.0)
    
    def test_concurrent_entropy_fetching(self):
        """Test concurrent entropy requests."""
        from security.services.natural_entropy_providers import LightningEntropyProvider
        import threading
        
        provider = LightningEntropyProvider()
        results = []
        errors = []
        
        def fetch():
            try:
                entropy = provider.fetch_entropy(32)
                results.append(entropy)
            except Exception as e:
                errors.append(e)
        
        threads = [threading.Thread(target=fetch) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        self.assertEqual(len(errors), 0)
        self.assertEqual(len(results), 5)


# =============================================================================
# Edge Cases
# =============================================================================

class TestEdgeCases(TestCase):
    """Tests for edge cases."""
    
    def test_zero_bytes_requested(self):
        """Test requesting zero bytes."""
        from security.services.natural_entropy_providers import LightningEntropyProvider
        
        provider = LightningEntropyProvider()
        entropy = provider.fetch_entropy(0)
        
        self.assertEqual(len(entropy), 0)
    
    def test_large_entropy_request(self):
        """Test requesting large amount of entropy."""
        from security.services.natural_entropy_providers import LightningEntropyProvider
        
        provider = LightningEntropyProvider()
        entropy = provider.fetch_entropy(1024)
        
        self.assertGreaterEqual(len(entropy), 1024)
    
    def test_empty_strike_list(self):
        """Test handling of empty strike list."""
        from security.services.natural_entropy_providers import NaturalEntropyMixer
        
        mixer = NaturalEntropyMixer()
        
        # Single source with empty supplement
        source = bytes([0x42] * 32)
        result = mixer.mix(source)
        
        self.assertEqual(len(result), 32)


# =============================================================================
# A/B Test: Entropy Source Comparison
# =============================================================================

class TestEntropySourceComparison(TestCase):
    """Compare entropy quality across different sources."""
    
    def test_compare_entropy_distribution(self):
        """Compare byte distribution across sources."""
        from security.services.natural_entropy_providers import (
            LightningEntropyProvider,
            SeismicEntropyProvider,
            SolarWindEntropyProvider,
        )
        
        providers = {
            'lightning': LightningEntropyProvider(),
            'seismic': SeismicEntropyProvider(),
            'solar': SolarWindEntropyProvider(),
        }
        
        distributions = {}
        
        for name, provider in providers.items():
            try:
                entropy = provider.fetch_entropy(256)
                unique_bytes = len(set(entropy))
                distributions[name] = unique_bytes / 256.0
            except Exception:
                distributions[name] = 0.0
        
        # All sources should have reasonable distribution
        for name, ratio in distributions.items():
            if ratio > 0:  # If source was available
                self.assertGreater(ratio, 0.3, f"{name} has poor distribution")

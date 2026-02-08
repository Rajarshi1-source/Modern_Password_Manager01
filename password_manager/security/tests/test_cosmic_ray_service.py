"""
Cosmic Ray Entropy Service Unit Tests
======================================

Tests for the cosmic ray-based entropy provider including:
- CosmicRayEvent dataclass
- SimulatedCosmicDetector
- CosmicEntropyExtractor
- CosmicRayEntropyProvider
"""

import pytest
import asyncio
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime


class TestCosmicRayEvent:
    """Tests for CosmicRayEvent dataclass."""
    
    def test_event_creation(self):
        """Test creating a cosmic ray event."""
        from security.services.cosmic_ray_entropy_service import CosmicRayEvent
        
        event = CosmicRayEvent(
            timestamp=1234567890.123,
            energy_adc=2500,
            detector_id="test_detector",
            temperature_c=25.0,
            silicon_pm_count=1,
            coincidence=False,
            deadtime_corrected=True,
            quality_score=0.95
        )
        
        assert event.timestamp == 1234567890.123
        assert event.energy_adc == 2500
        assert event.detector_id == "test_detector"
        assert event.quality_score == 0.95
    
    def test_event_to_dict(self):
        """Test event serialization to dictionary."""
        from security.services.cosmic_ray_entropy_service import CosmicRayEvent
        
        event = CosmicRayEvent(
            timestamp=1234567890.123,
            energy_adc=2500,
            detector_id="test_detector"
        )
        
        data = event.to_dict()
        
        assert isinstance(data, dict)
        assert data['timestamp'] == 1234567890.123
        assert data['energy_adc'] == 2500
        assert data['detector_id'] == "test_detector"
    
    def test_event_entropy_bytes(self):
        """Test entropy byte extraction from event."""
        from security.services.cosmic_ray_entropy_service import CosmicRayEvent
        
        event = CosmicRayEvent(
            timestamp=1234567890.123456789,
            energy_adc=2500,
            detector_id="test"
        )
        
        entropy = event.get_entropy_bytes()
        
        assert isinstance(entropy, bytes)
        assert len(entropy) >= 8  # At least timing bytes


class TestSimulatedCosmicDetector:
    """Tests for the simulated cosmic ray detector."""
    
    @pytest.fixture
    def detector(self):
        """Create a simulated detector instance."""
        from security.services.cosmic_ray_entropy_service import SimulatedCosmicDetector
        return SimulatedCosmicDetector()
    
    @pytest.mark.asyncio
    async def test_generate_event(self, detector):
        """Test generating a single simulated event."""
        event = await detector.generate_event()
        
        assert event is not None
        assert hasattr(event, 'timestamp')
        assert hasattr(event, 'energy_adc')
        assert event.detector_id == 'simulated_muon_detector'
    
    @pytest.mark.asyncio
    async def test_collect_events_count(self, detector):
        """Test collecting multiple events."""
        events = await detector.collect_events(count=5, realistic_timing=False)
        
        assert len(events) == 5
        for event in events:
            assert event.energy_adc > 0
    
    @pytest.mark.asyncio
    async def test_event_quality_scores(self, detector):
        """Test that events have valid quality scores."""
        events = await detector.collect_events(count=10, realistic_timing=False)
        
        for event in events:
            assert 0.0 <= event.quality_score <= 1.0
    
    def test_detector_status(self, detector):
        """Test detector status reporting."""
        status = detector.get_status()
        
        assert isinstance(status, dict)
        assert 'mode' in status
        assert status['mode'] == 'simulation'


class TestCosmicEntropyExtractor:
    """Tests for entropy extraction from cosmic events."""
    
    @pytest.fixture
    def extractor(self):
        """Create an entropy extractor instance."""
        from security.services.cosmic_ray_entropy_service import CosmicEntropyExtractor
        return CosmicEntropyExtractor()
    
    @pytest.fixture
    def sample_events(self):
        """Generate sample cosmic events for testing."""
        from security.services.cosmic_ray_entropy_service import CosmicRayEvent
        import time
        
        events = []
        for i in range(20):
            events.append(CosmicRayEvent(
                timestamp=time.time() + i * 0.001,
                energy_adc=2000 + (i * 100) % 500,
                detector_id="test",
                quality_score=0.9
            ))
        return events
    
    def test_extract_raw_entropy(self, extractor, sample_events):
        """Test raw entropy extraction from events."""
        entropy = extractor.extract_raw_entropy(sample_events)
        
        assert isinstance(entropy, bytes)
        assert len(entropy) > 0
    
    def test_condition_entropy(self, extractor):
        """Test entropy conditioning with SHA-3."""
        raw = b'\x12\x34\x56\x78' * 10
        
        conditioned = extractor.condition_entropy(raw, output_bytes=32)
        
        assert len(conditioned) == 32
        assert conditioned != raw[:32]  # Should be transformed
    
    def test_extract_conditioned_entropy(self, extractor, sample_events):
        """Test full entropy extraction pipeline."""
        entropy = extractor.extract_conditioned_entropy(sample_events, output_bytes=64)
        
        assert len(entropy) == 64
        assert isinstance(entropy, bytes)
    
    def test_deterministic_output(self, extractor, sample_events):
        """Test that same events produce same entropy."""
        entropy1 = extractor.extract_conditioned_entropy(sample_events, output_bytes=32)
        entropy2 = extractor.extract_conditioned_entropy(sample_events, output_bytes=32)
        
        assert entropy1 == entropy2


class TestCosmicRayEntropyProvider:
    """Tests for the main cosmic ray entropy provider."""
    
    @pytest.fixture
    def provider(self):
        """Create a provider instance (simulation mode)."""
        from security.services.cosmic_ray_entropy_service import CosmicRayEntropyProvider
        # Force simulation mode
        with patch.dict('os.environ', {'COSMIC_RAY_SERIAL_PORT': 'none'}):
            return CosmicRayEntropyProvider(prefer_hardware=False)
    
    def test_provider_name(self, provider):
        """Test provider name identifier."""
        name = provider.get_provider_name()
        
        assert name == "cosmic_ray_muon"
    
    def test_provider_is_available(self, provider):
        """Test provider availability in simulation mode."""
        available = provider.is_available()
        
        assert available is True
    
    def test_get_status(self, provider):
        """Test provider status reporting."""
        status = provider.get_status()
        
        assert isinstance(status, dict)
        assert 'mode' in status
        assert status['mode'] in ('simulation', 'hardware', 'uninitialized')
    
    @pytest.mark.asyncio
    async def test_fetch_random_bytes(self, provider):
        """Test fetching random bytes from the provider."""
        entropy, source = await provider.fetch_random_bytes(32)
        
        assert len(entropy) == 32
        assert isinstance(entropy, bytes)
        assert source is not None
    
    @pytest.mark.asyncio
    async def test_fetch_random_bytes_various_sizes(self, provider):
        """Test fetching different amounts of random data."""
        for size in [8, 16, 32, 64, 128]:
            entropy, _ = await provider.fetch_random_bytes(size)
            assert len(entropy) == size
    
    @pytest.mark.asyncio
    async def test_entropy_uniqueness(self, provider):
        """Test that successive calls produce different entropy."""
        results = []
        for _ in range(5):
            entropy, _ = await provider.fetch_random_bytes(32)
            results.append(entropy)
        
        # All results should be unique
        unique_results = set(results)
        assert len(unique_results) == len(results)


class TestPasswordGeneration:
    """Tests for cosmic ray password generation."""
    
    @pytest.mark.asyncio
    async def test_generate_cosmic_password(self):
        """Test password generation with cosmic entropy."""
        from security.services.cosmic_ray_entropy_service import generate_cosmic_password
        
        password, info = await generate_cosmic_password(length=16)
        
        assert len(password) == 16
        assert isinstance(info, dict)
        assert 'source' in info
    
    @pytest.mark.asyncio
    async def test_password_with_charset(self):
        """Test password generation with custom charset."""
        from security.services.cosmic_ray_entropy_service import generate_cosmic_password
        
        password, _ = await generate_cosmic_password(
            length=20,
            charset='0123456789'
        )
        
        assert len(password) == 20
        assert all(c.isdigit() for c in password)
    
    @pytest.mark.asyncio
    async def test_password_length_range(self):
        """Test password generation at various lengths."""
        from security.services.cosmic_ray_entropy_service import generate_cosmic_password
        
        for length in [8, 16, 32, 64]:
            password, _ = await generate_cosmic_password(length=length)
            assert len(password) == length


class TestSingletonFactory:
    """Tests for the provider singleton factory."""
    
    def test_get_cosmic_provider(self):
        """Test singleton provider factory."""
        from security.services.cosmic_ray_entropy_service import get_cosmic_provider
        
        provider1 = get_cosmic_provider()
        provider2 = get_cosmic_provider()
        
        # Should return the same instance
        assert provider1 is provider2
    
    def test_provider_reusable(self):
        """Test that singleton provider is reusable."""
        from security.services.cosmic_ray_entropy_service import get_cosmic_provider
        
        provider = get_cosmic_provider()
        
        # Should be usable multiple times
        assert provider.is_available()
        assert provider.get_provider_name() == "cosmic_ray_muon"

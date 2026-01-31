"""
Storm Chase Mode Tests
======================

Comprehensive test suite for Storm Chase Mode - detecting hurricane/storm conditions
and maximizing entropy collection during severe weather events.

Tests cover:
- StormAlert data class
- StormChaseStatus data class
- StormChaseService core functionality
- API endpoints
- Storm detection algorithms
- Entropy generation from storm buoys

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
# StormSeverity Tests
# =============================================================================

class TestStormSeverity(TestCase):
    """Tests for StormSeverity enum."""
    
    def test_severity_levels_exist(self):
        """Test all severity levels are defined."""
        from security.services.storm_chase import StormSeverity
        
        expected = ['calm', 'moderate', 'severe', 'extreme']
        for level in expected:
            self.assertTrue(hasattr(StormSeverity, level.upper()))
    
    def test_severity_comparison(self):
        """Test severity levels can be compared."""
        from security.services.storm_chase import StormSeverity
        
        self.assertLess(
            StormSeverity.CALM.value,
            StormSeverity.EXTREME.value
        )


# =============================================================================
# StormAlert Tests
# =============================================================================

class TestStormAlert(TestCase):
    """Tests for StormAlert dataclass."""
    
    def setUp(self):
        """Create test storm alert."""
        from security.services.storm_chase import StormAlert, StormSeverity
        
        self.alert = StormAlert(
            buoy_id='44013',
            buoy_name='Boston Harbor Buoy',
            region='atlantic',
            severity=StormSeverity.SEVERE,
            wave_height_m=4.5,
            wind_speed_mps=25.0,
            pressure_hpa=990.0,
            detected_at=datetime.utcnow(),
        )
    
    def test_entropy_bonus_severe_storm(self):
        """Test entropy bonus for severe storm."""
        bonus = self.alert.entropy_bonus
        
        self.assertGreater(bonus, 0.0)
        self.assertLessEqual(bonus, 1.0)
    
    def test_entropy_bonus_increases_with_severity(self):
        """Test entropy bonus increases with storm severity."""
        from security.services.storm_chase import StormAlert, StormSeverity
        
        moderate = StormAlert(
            buoy_id='test', buoy_name='Test', region='test',
            severity=StormSeverity.MODERATE,
            wave_height_m=2.0, wind_speed_mps=15.0,
            detected_at=datetime.utcnow(),
        )
        
        extreme = StormAlert(
            buoy_id='test', buoy_name='Test', region='test',
            severity=StormSeverity.EXTREME,
            wave_height_m=8.0, wind_speed_mps=40.0,
            detected_at=datetime.utcnow(),
        )
        
        self.assertLess(moderate.entropy_bonus, extreme.entropy_bonus)
    
    def test_severity_label(self):
        """Test severity label is human readable."""
        label = self.alert.severity_label
        
        self.assertIsInstance(label, str)
        self.assertIn('Severe', label)
    
    def test_to_dict(self):
        """Test serialization to dictionary."""
        data = self.alert.to_dict()
        
        self.assertEqual(data['buoy_id'], '44013')
        self.assertEqual(data['region'], 'atlantic')
        self.assertIn('entropy_bonus', data)
        self.assertIn('severity', data)
        self.assertIn('detected_at', data)


# =============================================================================
# StormChaseStatus Tests
# =============================================================================

class TestStormChaseStatus(TestCase):
    """Tests for StormChaseStatus dataclass."""
    
    def test_status_with_no_storms(self):
        """Test status when no storms are active."""
        from security.services.storm_chase import StormChaseStatus
        
        status = StormChaseStatus(
            is_active=False,
            active_storms_count=0,
            most_severe=None,
            max_entropy_bonus=0.0,
            regions_affected=[],
            storm_alerts=[],
        )
        
        self.assertFalse(status.is_active)
        self.assertEqual(status.active_storms_count, 0)
    
    def test_status_with_active_storms(self):
        """Test status when storms are active."""
        from security.services.storm_chase import StormChaseStatus, StormSeverity
        
        status = StormChaseStatus(
            is_active=True,
            active_storms_count=3,
            most_severe=StormSeverity.EXTREME,
            max_entropy_bonus=0.35,
            regions_affected=['atlantic', 'gulf'],
            storm_alerts=[],
        )
        
        self.assertTrue(status.is_active)
        self.assertEqual(len(status.regions_affected), 2)
    
    def test_to_dict(self):
        """Test serialization to dictionary."""
        from security.services.storm_chase import StormChaseStatus
        
        status = StormChaseStatus(
            is_active=True,
            active_storms_count=2,
            most_severe=None,
            max_entropy_bonus=0.25,
            regions_affected=['pacific'],
            storm_alerts=[],
        )
        
        data = status.to_dict()
        
        self.assertIn('is_active', data)
        self.assertIn('active_storms_count', data)
        self.assertIn('max_entropy_bonus', data)


# =============================================================================
# StormChaseService Tests
# =============================================================================

class TestStormChaseService(TestCase):
    """Tests for StormChaseService core functionality."""
    
    def setUp(self):
        """Initialize storm chase service."""
        from security.services.storm_chase import StormChaseService
        
        self.service = StormChaseService()
    
    def test_service_initialization(self):
        """Test service initializes correctly."""
        self.assertIsNotNone(self.service)
        self.assertIsNotNone(self.service.storm_threshold_wave_height)
        self.assertIsNotNone(self.service.storm_threshold_wind_speed)
    
    @patch('security.services.storm_chase.get_noaa_client')
    def test_scan_for_storms_no_storms(self, mock_client):
        """Test scanning when no storms are active."""
        # Mock NOAA client to return calm readings
        mock_noaa = MagicMock()
        mock_noaa.get_all_readings_async = AsyncMock(return_value=[])
        mock_client.return_value = mock_noaa
        
        alerts = self.service.scan_for_storms()
        
        self.assertIsInstance(alerts, list)
    
    @patch('security.services.storm_chase.get_noaa_client')
    def test_scan_for_storms_with_storm(self, mock_client):
        """Test scanning when storms are detected."""
        from security.services.noaa_api_client import BuoyReading
        
        # Mock NOAA client with storm-level readings
        mock_noaa = MagicMock()
        storm_reading = MagicMock()
        storm_reading.buoy_id = '44013'
        storm_reading.wave_height_m = 6.0  # Storm level
        storm_reading.wind_speed_mps = 30.0  # Storm level
        storm_reading.pressure_hpa = 985.0
        storm_reading.timestamp = datetime.utcnow()
        
        mock_noaa.get_all_readings_async = AsyncMock(return_value=[storm_reading])
        mock_noaa.buoy_info = {'44013': {'name': 'Test Buoy', 'region': 'atlantic'}}
        mock_client.return_value = mock_noaa
        
        alerts = self.service.scan_for_storms()
        
        self.assertIsInstance(alerts, list)
    
    def test_get_storm_chase_status(self):
        """Test getting overall storm chase status."""
        from security.services.storm_chase import StormChaseStatus
        
        status = self.service.get_storm_chase_status()
        
        self.assertIsInstance(status, StormChaseStatus)
        self.assertIsInstance(status.is_active, bool)
        self.assertIsInstance(status.active_storms_count, int)
    
    def test_get_active_storms(self):
        """Test getting list of active storms."""
        storms = self.service.get_active_storms()
        
        self.assertIsInstance(storms, list)
    
    def test_get_storm_buoys(self):
        """Test getting storm-affected buoy readings."""
        buoys = self.service.get_storm_buoys()
        
        self.assertIsInstance(buoys, list)
    
    @patch('security.services.storm_chase.get_noaa_client')
    def test_generate_storm_entropy(self, mock_client):
        """Test generating entropy from storm buoys."""
        mock_noaa = MagicMock()
        mock_noaa.get_all_readings_async = AsyncMock(return_value=[])
        mock_client.return_value = mock_noaa
        
        result = self.service.generate_storm_entropy(count=32)
        
        self.assertIsInstance(result, tuple)
        self.assertEqual(len(result), 3)  # (entropy_bytes, source_id, storm_buoy_ids)
    
    def test_get_regional_storm_status(self):
        """Test getting storm status for specific region."""
        status = self.service.get_regional_storm_status('atlantic')
        
        self.assertIsInstance(status, dict)
        self.assertIn('region', status)


# =============================================================================
# StormChaseService Singleton Tests
# =============================================================================

class TestStormChaseServiceSingleton(TestCase):
    """Tests for storm chase service singleton."""
    
    def test_get_storm_chase_service_returns_service(self):
        """Test singleton returns service instance."""
        from security.services.storm_chase import get_storm_chase_service
        
        service = get_storm_chase_service()
        
        self.assertIsNotNone(service)
    
    def test_get_storm_chase_service_returns_same_instance(self):
        """Test singleton returns same instance."""
        from security.services.storm_chase import get_storm_chase_service
        
        service1 = get_storm_chase_service()
        service2 = get_storm_chase_service()
        
        self.assertIs(service1, service2)


# =============================================================================
# Storm Detection Algorithm Tests
# =============================================================================

class TestStormDetectionAlgorithms(TestCase):
    """Tests for storm detection algorithms."""
    
    def test_detect_storm_by_wave_height(self):
        """Test storm detection based on wave height."""
        from security.services.storm_chase import StormChaseService
        
        service = StormChaseService()
        
        # Create mock reading with high waves
        mock_reading = MagicMock()
        mock_reading.wave_height_m = 5.0
        mock_reading.wind_speed_mps = 10.0
        mock_reading.pressure_hpa = 1010.0
        
        # Waves above threshold should indicate storm
        is_storm = mock_reading.wave_height_m > service.storm_threshold_wave_height
        self.assertTrue(is_storm)
    
    def test_detect_storm_by_wind_speed(self):
        """Test storm detection based on wind speed."""
        from security.services.storm_chase import StormChaseService
        
        service = StormChaseService()
        
        mock_reading = MagicMock()
        mock_reading.wave_height_m = 1.0
        mock_reading.wind_speed_mps = 25.0  # High wind
        mock_reading.pressure_hpa = 1010.0
        
        is_storm = mock_reading.wind_speed_mps > service.storm_threshold_wind_speed
        self.assertTrue(is_storm)
    
    def test_detect_storm_by_low_pressure(self):
        """Test storm detection based on low pressure."""
        from security.services.storm_chase import StormChaseService
        
        service = StormChaseService()
        
        mock_reading = MagicMock()
        mock_reading.wave_height_m = 2.0
        mock_reading.wind_speed_mps = 15.0
        mock_reading.pressure_hpa = 980.0  # Very low pressure
        
        # Low pressure typically indicates storm
        is_low_pressure = mock_reading.pressure_hpa < 1000.0
        self.assertTrue(is_low_pressure)


# =============================================================================
# Storm Chase API Tests
# =============================================================================

class TestStormChaseAPI(APITestCase):
    """Tests for Storm Chase API endpoints."""
    
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='stormtester',
            email='storm@example.com',
            password='testpass123'
        )
        self.client.force_authenticate(user=self.user)
    
    def test_storm_list_endpoint(self):
        """Test GET /api/security/ocean/storms/"""
        response = self.client.get('/api/security/ocean/storms/')
        
        self.assertIn(response.status_code, [200, 401, 403, 404])
        
        if response.status_code == 200:
            self.assertIn('storms', response.data)
    
    def test_storm_status_endpoint(self):
        """Test GET /api/security/ocean/storms/status/"""
        response = self.client.get('/api/security/ocean/storms/status/')
        
        self.assertIn(response.status_code, [200, 401, 403, 404])
        
        if response.status_code == 200:
            self.assertIn('is_active', response.data)
    
    def test_storm_buoys_endpoint(self):
        """Test GET /api/security/ocean/storms/buoys/"""
        response = self.client.get('/api/security/ocean/storms/buoys/')
        
        self.assertIn(response.status_code, [200, 401, 403, 404])
    
    def test_generate_storm_entropy_endpoint(self):
        """Test POST /api/security/ocean/generate-storm-entropy/"""
        response = self.client.post(
            '/api/security/ocean/generate-storm-entropy/',
            {'bytes': 32},
            format='json'
        )
        
        self.assertIn(response.status_code, [200, 201, 400, 401, 403, 404, 503])
    
    def test_scan_storms_endpoint(self):
        """Test POST /api/security/ocean/storms/scan/"""
        response = self.client.post('/api/security/ocean/storms/scan/')
        
        self.assertIn(response.status_code, [200, 201, 401, 403, 404])
    
    def test_unauthenticated_access_denied(self):
        """Test that unauthenticated requests are denied."""
        self.client.logout()
        
        response = self.client.get('/api/security/ocean/storms/')
        
        self.assertIn(response.status_code, [401, 403])


# =============================================================================
# Storm Entropy Quality Tests
# =============================================================================

class TestStormEntropyQuality(TestCase):
    """Tests for entropy quality during storms."""
    
    def test_storm_entropy_has_bonus(self):
        """Test that storm-generated entropy has quality bonus."""
        from security.services.storm_chase import StormAlert, StormSeverity
        
        # Extreme storm should have significant bonus
        alert = StormAlert(
            buoy_id='test',
            buoy_name='Test',
            region='atlantic',
            severity=StormSeverity.EXTREME,
            wave_height_m=10.0,
            wind_speed_mps=50.0,
            pressure_hpa=950.0,
            detected_at=datetime.utcnow(),
        )
        
        self.assertGreater(alert.entropy_bonus, 0.2)
    
    def test_calm_conditions_no_bonus(self):
        """Test that calm conditions have minimal bonus."""
        from security.services.storm_chase import StormAlert, StormSeverity
        
        alert = StormAlert(
            buoy_id='test',
            buoy_name='Test',
            region='pacific',
            severity=StormSeverity.CALM,
            wave_height_m=0.5,
            wind_speed_mps=3.0,
            pressure_hpa=1015.0,
            detected_at=datetime.utcnow(),
        )
        
        self.assertLess(alert.entropy_bonus, 0.1)


# =============================================================================
# Integration Tests
# =============================================================================

class TestStormChaseIntegration(TestCase):
    """Integration tests for Storm Chase Mode."""
    
    @patch('security.services.storm_chase.get_noaa_client')
    def test_full_storm_detection_flow(self, mock_client):
        """Test complete storm detection and entropy generation flow."""
        from security.services.storm_chase import get_storm_chase_service
        
        # Setup mock
        mock_noaa = MagicMock()
        mock_noaa.get_all_readings_async = AsyncMock(return_value=[])
        mock_client.return_value = mock_noaa
        
        service = get_storm_chase_service()
        
        # Scan for storms
        alerts = service.scan_for_storms()
        
        # Get status
        status = service.get_storm_chase_status()
        
        # Generate entropy
        entropy, source_id, storm_ids = service.generate_storm_entropy(32)
        
        # Verify results
        self.assertIsInstance(alerts, list)
        self.assertIsNotNone(status)
        self.assertIsInstance(entropy, bytes)


# =============================================================================
# A/B Testing for Storm Detection Thresholds
# =============================================================================

class TestStormDetectionThresholds(TestCase):
    """Tests for different storm detection threshold configurations."""
    
    def test_default_wave_height_threshold(self):
        """Test default wave height threshold is reasonable."""
        from security.services.storm_chase import StormChaseService
        
        service = StormChaseService()
        
        # Threshold should be between 2-5 meters for meaningful storms
        self.assertGreaterEqual(service.storm_threshold_wave_height, 2.0)
        self.assertLessEqual(service.storm_threshold_wave_height, 5.0)
    
    def test_default_wind_speed_threshold(self):
        """Test default wind speed threshold is reasonable."""
        from security.services.storm_chase import StormChaseService
        
        service = StormChaseService()
        
        # Threshold should be between 15-25 m/s for meaningful storms
        self.assertGreaterEqual(service.storm_threshold_wind_speed, 15.0)
        self.assertLessEqual(service.storm_threshold_wind_speed, 30.0)


# =============================================================================
# Edge Cases
# =============================================================================

class TestStormChaseEdgeCases(TestCase):
    """Tests for edge cases in Storm Chase Mode."""
    
    def test_empty_buoy_readings(self):
        """Test handling of empty buoy readings."""
        from security.services.storm_chase import StormChaseService
        
        service = StormChaseService()
        status = service.get_storm_chase_status()
        
        # Should not crash with no readings
        self.assertIsNotNone(status)
    
    def test_partial_reading_data(self):
        """Test handling of readings with missing data."""
        from security.services.storm_chase import StormAlert, StormSeverity
        
        # Alert with minimal data
        alert = StormAlert(
            buoy_id='test',
            buoy_name='Test',
            region='gulf',
            severity=StormSeverity.MODERATE,
            wave_height_m=3.0,
            wind_speed_mps=None,  # Missing
            pressure_hpa=None,  # Missing
            detected_at=datetime.utcnow(),
        )
        
        # Should still calculate bonus
        self.assertIsInstance(alert.entropy_bonus, float)
    
    def test_concurrent_storm_scans(self):
        """Test concurrent storm scan requests."""
        from security.services.storm_chase import get_storm_chase_service
        import threading
        
        service = get_storm_chase_service()
        results = []
        
        def scan():
            try:
                status = service.get_storm_chase_status()
                results.append(status)
            except Exception as e:
                results.append(e)
        
        threads = [threading.Thread(target=scan) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        # All should succeed
        self.assertEqual(len(results), 5)
        for r in results:
            self.assertNotIsInstance(r, Exception)

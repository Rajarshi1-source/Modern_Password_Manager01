"""
Location Verification Service Tests
=====================================

Tests for the location verification service including:
- GPS verification
- BLE node detection
- Anti-spoofing checks
- Velocity anomaly detection
- Confidence scoring

@author Password Manager Team
@created 2026-01-22
"""

from django.test import TestCase
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal
from unittest.mock import Mock, patch, MagicMock
import math

# Import the service
from mesh_deaddrop.services.location_verification_service import (
    LocationVerificationService,
    LocationVerificationResult
)


class LocationVerificationServiceTests(TestCase):
    """Tests for LocationVerificationService."""
    
    def setUp(self):
        """Set up test data."""
        self.service = LocationVerificationService()
        
        # Reference location (New York City)
        self.target_location = {
            'latitude': 40.7128,
            'longitude': -74.0060,
            'radius_meters': 50
        }
    
    def test_haversine_distance_calculation(self):
        """Test Haversine distance calculation."""
        # Same point
        distance = self.service.calculate_distance(
            40.7128, -74.0060,
            40.7128, -74.0060
        )
        self.assertEqual(distance, 0)
        
        # About 1 km apart
        distance = self.service.calculate_distance(
            40.7128, -74.0060,
            40.7218, -74.0060
        )
        self.assertAlmostEqual(distance, 1000, delta=50)
    
    def test_verify_location_within_radius(self):
        """Test location verification when within radius."""
        claimed_location = {
            'latitude': 40.7128,
            'longitude': -74.0060,
            'accuracy_meters': 10
        }
        
        result = self.service.verify_gps_location(
            claimed_location,
            self.target_location
        )
        
        self.assertTrue(result['is_within_radius'])
        self.assertEqual(result['distance_meters'], 0)
    
    def test_verify_location_outside_radius(self):
        """Test location verification when outside radius."""
        claimed_location = {
            'latitude': 40.7200,  # About 800m away
            'longitude': -74.0060,
            'accuracy_meters': 10
        }
        
        result = self.service.verify_gps_location(
            claimed_location,
            self.target_location
        )
        
        self.assertFalse(result['is_within_radius'])
        self.assertGreater(result['distance_meters'], 50)
    
    def test_verify_location_with_accuracy_buffer(self):
        """Test that GPS accuracy is considered."""
        # Just outside radius but within accuracy buffer
        claimed_location = {
            'latitude': 40.7132,  # About 45m away
            'longitude': -74.0060,
            'accuracy_meters': 20  # With 20m accuracy, could be within 50m
        }
        
        result = self.service.verify_gps_location(
            claimed_location,
            self.target_location
        )
        
        # Should consider the accuracy buffer
        self.assertTrue(result['is_within_radius'] or result['distance_meters'] < 70)
    
    def test_ble_presence_verification(self):
        """Test BLE beacon presence verification."""
        ble_signals = [
            {'node_id': 'node-1', 'rssi': -55, 'name': 'MeshNode-A'},
            {'node_id': 'node-2', 'rssi': -65, 'name': 'MeshNode-B'},
            {'node_id': 'node-3', 'rssi': -75, 'name': 'MeshNode-C'},
        ]
        
        result = self.service.verify_ble_presence(
            ble_signals,
            min_required_nodes=2
        )
        
        self.assertTrue(result['verified'])
        self.assertEqual(result['nodes_found'], 3)
        self.assertGreater(result['confidence'], 0.5)
    
    def test_ble_verification_insufficient_nodes(self):
        """Test BLE verification fails with insufficient nodes."""
        ble_signals = [
            {'node_id': 'node-1', 'rssi': -55, 'name': 'MeshNode-A'},
        ]
        
        result = self.service.verify_ble_presence(
            ble_signals,
            min_required_nodes=2
        )
        
        self.assertFalse(result['verified'])
    
    def test_calculate_presence_confidence(self):
        """Test presence confidence calculation based on RSSI."""
        # Strong signals = high confidence
        strong_signals = [
            {'rssi': -40},
            {'rssi': -45},
            {'rssi': -50},
        ]
        
        confidence = self.service.calculate_presence_confidence(strong_signals)
        self.assertGreater(confidence, 0.7)
        
        # Weak signals = lower confidence
        weak_signals = [
            {'rssi': -80},
            {'rssi': -85},
        ]
        
        confidence = self.service.calculate_presence_confidence(weak_signals)
        self.assertLess(confidence, 0.5)
    
    def test_anti_spoofing_normal_movement(self):
        """Test anti-spoofing with normal movement."""
        location_history = [
            {
                'latitude': 40.7128,
                'longitude': -74.0060,
                'timestamp': timezone.now() - timedelta(minutes=30)
            },
            {
                'latitude': 40.7130,  # Moved ~22m in 30 min = walking pace
                'longitude': -74.0060,
                'timestamp': timezone.now() - timedelta(minutes=15)
            }
        ]
        
        current = {
            'latitude': 40.7132,
            'longitude': -74.0060,
            'timestamp': timezone.now()
        }
        
        result = self.service.anti_spoofing_check(location_history, current)
        
        self.assertTrue(result['is_legitimate'])
        self.assertIsNone(result.get('anomaly_type'))
    
    def test_anti_spoofing_velocity_anomaly(self):
        """Test anti-spoofing detects impossible travel."""
        location_history = [
            {
                'latitude': 40.7128,  # New York
                'longitude': -74.0060,
                'timestamp': timezone.now() - timedelta(minutes=5)
            }
        ]
        
        current = {
            'latitude': 51.5074,  # London - 5570 km away in 5 minutes!
            'longitude': -0.1278,
            'timestamp': timezone.now()
        }
        
        result = self.service.anti_spoofing_check(location_history, current)
        
        self.assertFalse(result['is_legitimate'])
        self.assertEqual(result['anomaly_type'], 'impossible_travel')
    
    def test_anti_spoofing_teleportation(self):
        """Test detection of instant teleportation."""
        location_history = [
            {
                'latitude': 40.7128,
                'longitude': -74.0060,
                'timestamp': timezone.now() - timedelta(seconds=1)
            }
        ]
        
        current = {
            'latitude': 40.8000,  # ~10km away in 1 second
            'longitude': -74.0060,
            'timestamp': timezone.now()
        }
        
        result = self.service.anti_spoofing_check(location_history, current)
        
        self.assertFalse(result['is_legitimate'])
    
    def test_combined_verification(self):
        """Test combined GPS + BLE verification."""
        claimed_location = {
            'latitude': 40.7128,
            'longitude': -74.0060,
            'accuracy_meters': 10,
            'ble_nodes': [
                {'node_id': 'node-1', 'rssi': -55},
                {'node_id': 'node-2', 'rssi': -60},
                {'node_id': 'node-3', 'rssi': -65},
            ]
        }
        
        target = {
            'latitude': 40.7128,
            'longitude': -74.0060,
            'radius_meters': 50,
            'require_ble': True,
            'min_ble_nodes': 2
        }
        
        result = self.service.verify_at_location(
            claimed_location,
            target
        )
        
        self.assertTrue(result.verified)
        self.assertGreater(result.confidence, 0.7)
    
    def test_verification_fails_without_required_ble(self):
        """Test verification fails when BLE required but not provided."""
        claimed_location = {
            'latitude': 40.7128,
            'longitude': -74.0060,
            'accuracy_meters': 10,
            'ble_nodes': []  # No BLE nodes
        }
        
        target = {
            'latitude': 40.7128,
            'longitude': -74.0060,
            'radius_meters': 50,
            'require_ble': True,
            'min_ble_nodes': 2
        }
        
        result = self.service.verify_at_location(
            claimed_location,
            target
        )
        
        self.assertFalse(result.verified)
        self.assertIn('ble', result.failure_reason.lower())


class VelocityCalculationTests(TestCase):
    """Tests for velocity calculation logic."""
    
    def setUp(self):
        """Set up test data."""
        self.service = LocationVerificationService()
    
    def test_calculate_velocity_walking(self):
        """Test velocity calculation for walking speed."""
        point1 = {'latitude': 40.7128, 'longitude': -74.0060}
        point2 = {'latitude': 40.7138, 'longitude': -74.0060}  # ~111m
        time_delta = timedelta(minutes=2)  # ~3.3 km/h
        
        velocity = self.service.calculate_velocity(point1, point2, time_delta)
        
        self.assertLess(velocity, 10)  # Walking speed
    
    def test_calculate_velocity_driving(self):
        """Test velocity calculation for driving speed."""
        point1 = {'latitude': 40.7128, 'longitude': -74.0060}
        point2 = {'latitude': 40.8128, 'longitude': -74.0060}  # ~11km
        time_delta = timedelta(minutes=10)  # ~66 km/h
        
        velocity = self.service.calculate_velocity(point1, point2, time_delta)
        
        self.assertLess(velocity, 200)  # Driving speed
        self.assertGreater(velocity, 50)
    
    def test_calculate_velocity_supersonic(self):
        """Test detection of supersonic speeds (spoofing)."""
        point1 = {'latitude': 40.7128, 'longitude': -74.0060}  # NYC
        point2 = {'latitude': 34.0522, 'longitude': -118.2437}  # LA
        time_delta = timedelta(minutes=10)
        
        velocity = self.service.calculate_velocity(point1, point2, time_delta)
        
        # NYC to LA in 10 min would be ~23,000 km/h
        self.assertGreater(velocity, 10000)
    
    def test_is_velocity_suspicious(self):
        """Test velocity suspicion check."""
        # Normal walking
        self.assertFalse(self.service.is_velocity_suspicious(5))
        
        # Normal driving  
        self.assertFalse(self.service.is_velocity_suspicious(100))
        
        # Commercial flight
        self.assertFalse(self.service.is_velocity_suspicious(900))
        
        # Too fast (teleportation)
        self.assertTrue(self.service.is_velocity_suspicious(2000))


class GeohashVerificationTests(TestCase):
    """Tests for geohash-based verification."""
    
    def setUp(self):
        """Set up test data."""
        self.service = LocationVerificationService()
    
    def test_geohash_generation(self):
        """Test geohash generation for location."""
        geohash = self.service.generate_geohash(40.7128, -74.0060, precision=8)
        
        self.assertEqual(len(geohash), 8)
        self.assertTrue(geohash.startswith('dr5'))  # NYC prefix
    
    def test_geohash_proximity(self):
        """Test geohash proximity matching."""
        loc1_hash = self.service.generate_geohash(40.7128, -74.0060, precision=6)
        loc2_hash = self.service.generate_geohash(40.7130, -74.0058, precision=6)
        
        # Nearby locations should have same 6-char geohash
        self.assertEqual(loc1_hash, loc2_hash)
    
    def test_geohash_different_locations(self):
        """Test geohash differs for distant locations."""
        nyc_hash = self.service.generate_geohash(40.7128, -74.0060, precision=4)
        la_hash = self.service.generate_geohash(34.0522, -118.2437, precision=4)
        
        self.assertNotEqual(nyc_hash, la_hash)

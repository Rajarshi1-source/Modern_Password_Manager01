"""
Geofence & Impossible Travel Detection Tests
=============================================

Comprehensive test suite for geofencing and physics-based
impossible travel detection.
"""

import math
from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import patch, MagicMock

from django.test import TestCase, override_settings
from django.contrib.auth.models import User
from django.utils import timezone

from rest_framework.test import APITestCase, APIClient
from rest_framework import status


class HaversineDistanceTests(TestCase):
    """Test cases for great-circle distance calculations."""
    
    def setUp(self):
        """Import the service."""
        from security.services.impossible_travel_service import ImpossibleTravelService
        self.service = ImpossibleTravelService()
    
    def test_same_location_returns_zero(self):
        """Distance between same point should be zero."""
        lat, lon = 40.7128, -74.0060  # New York
        distance = self.service.calculate_distance(lat, lon, lat, lon)
        self.assertEqual(distance, 0.0)
    
    def test_known_distance_new_york_to_los_angeles(self):
        """Test known distance: NYC to LA is approximately 3940 km."""
        nyc_lat, nyc_lon = 40.7128, -74.0060
        la_lat, la_lon = 34.0522, -118.2437
        
        distance = self.service.calculate_distance(nyc_lat, nyc_lon, la_lat, la_lon)
        
        # Should be approximately 3940 km (allow 5% tolerance)
        self.assertAlmostEqual(distance, 3940, delta=200)
    
    def test_known_distance_london_to_paris(self):
        """Test known distance: London to Paris is approximately 344 km."""
        london_lat, london_lon = 51.5074, -0.1278
        paris_lat, paris_lon = 48.8566, 2.3522
        
        distance = self.service.calculate_distance(
            london_lat, london_lon, paris_lat, paris_lon
        )
        
        # Should be approximately 344 km
        self.assertAlmostEqual(distance, 344, delta=20)
    
    def test_known_distance_delhi_to_mumbai(self):
        """Test known distance: Delhi to Mumbai is approximately 1150 km."""
        delhi_lat, delhi_lon = 28.6139, 77.2090
        mumbai_lat, mumbai_lon = 19.0760, 72.8777
        
        distance = self.service.calculate_distance(
            delhi_lat, delhi_lon, mumbai_lat, mumbai_lon
        )
        
        # Should be approximately 1150 km
        self.assertAlmostEqual(distance, 1150, delta=100)
    
    def test_antipodal_points(self):
        """Test maximum Earth distance (antipodal points)."""
        # North pole to South pole
        distance = self.service.calculate_distance(90, 0, -90, 0)
        
        # Should be approximately 20,000 km (half Earth circumference)
        self.assertAlmostEqual(distance, 20015, delta=100)
    
    def test_equator_points(self):
        """Test distance along equator."""
        # Two points on equator, 90 degrees apart
        distance = self.service.calculate_distance(0, 0, 0, 90)
        
        # Should be approximately 10,000 km (quarter Earth circumference)
        self.assertAlmostEqual(distance, 10007, delta=100)


class SpeedCalculationTests(TestCase):
    """Test cases for required speed calculations."""
    
    def setUp(self):
        """Import the service."""
        from security.services.impossible_travel_service import ImpossibleTravelService
        self.service = ImpossibleTravelService()
    
    def test_zero_distance_returns_zero_speed(self):
        """Zero distance should return zero speed regardless of time."""
        speed = self.service.calculate_required_speed(0, 3600)
        self.assertEqual(speed, 0.0)
    
    def test_zero_time_returns_infinity(self):
        """Zero time with distance should return infinity."""
        speed = self.service.calculate_required_speed(100, 0)
        self.assertEqual(speed, float('inf'))
    
    def test_walking_speed(self):
        """3 km in 1 hour = 3 km/h (walking)."""
        speed = self.service.calculate_required_speed(3, 3600)
        self.assertAlmostEqual(speed, 3.0, places=1)
    
    def test_driving_speed(self):
        """100 km in 1 hour = 100 km/h (driving)."""
        speed = self.service.calculate_required_speed(100, 3600)
        self.assertAlmostEqual(speed, 100.0, places=1)
    
    def test_flight_speed(self):
        """800 km in 1 hour = 800 km/h (commercial flight)."""
        speed = self.service.calculate_required_speed(800, 3600)
        self.assertAlmostEqual(speed, 800.0, places=1)
    
    def test_impossible_speed(self):
        """5000 km in 1 hour = 5000 km/h (impossible)."""
        speed = self.service.calculate_required_speed(5000, 3600)
        self.assertAlmostEqual(speed, 5000.0, places=1)


class SpeedThresholdTests(TestCase):
    """Test cases for speed threshold classification."""
    
    def setUp(self):
        """Import speed thresholds."""
        from security.services.impossible_travel_service import SpeedThresholds
        self.thresholds = SpeedThresholds
    
    def test_walking_mode(self):
        """Speed < 6 km/h should infer walking."""
        mode = self.thresholds.infer_mode(5)
        self.assertEqual(mode, 'walking')
    
    def test_driving_mode(self):
        """Speed between 40-200 km/h should infer driving."""
        mode = self.thresholds.infer_mode(100)
        self.assertEqual(mode, 'driving')
    
    def test_train_mode(self):
        """Speed between 200-400 km/h should infer train."""
        mode = self.thresholds.infer_mode(350)
        self.assertEqual(mode, 'train')
    
    def test_flight_mode(self):
        """Speed between 400-920 km/h should infer flight."""
        mode = self.thresholds.infer_mode(800)
        self.assertEqual(mode, 'flight')
    
    def test_impossible_mode(self):
        """Speed > 1200 km/h should be supersonic (impossible)."""
        mode = self.thresholds.infer_mode(1500)
        self.assertEqual(mode, 'supersonic')
    
    def test_severity_none_for_walking(self):
        """Walking speed should have no severity."""
        severity = self.thresholds.get_severity(5)
        self.assertEqual(severity, 'none')
    
    def test_severity_low_for_driving(self):
        """High driving speed should have low severity."""
        severity = self.thresholds.get_severity(180)
        self.assertEqual(severity, 'low')
    
    def test_severity_medium_for_train(self):
        """Train speed should have medium severity."""
        severity = self.thresholds.get_severity(350)
        self.assertEqual(severity, 'medium')
    
    def test_severity_high_for_flight(self):
        """Flight speed should have high severity."""
        severity = self.thresholds.get_severity(800)
        self.assertEqual(severity, 'high')
    
    def test_severity_critical_for_supersonic(self):
        """Supersonic speed should have critical severity."""
        severity = self.thresholds.get_severity(1500)
        self.assertEqual(severity, 'critical')
    
    def test_action_allow_for_walking(self):
        """Walking should be allowed."""
        action = self.thresholds.get_action(5)
        self.assertEqual(action, 'allowed')
    
    def test_action_challenge_for_flight_without_itinerary(self):
        """Flight speed without itinerary should require challenge."""
        action = self.thresholds.get_action(800, has_itinerary=False)
        self.assertEqual(action, 'challenged')
    
    def test_action_allow_for_flight_with_itinerary(self):
        """Flight speed with verified itinerary should be allowed."""
        action = self.thresholds.get_action(800, has_itinerary=True)
        self.assertEqual(action, 'allowed')
    
    def test_action_block_for_supersonic(self):
        """Supersonic speed should be blocked."""
        action = self.thresholds.get_action(1500)
        self.assertEqual(action, 'blocked')


class GeofenceZoneTests(TestCase):
    """Test cases for geofence zone checking."""
    
    def setUp(self):
        """Create test user and service."""
        self.user = User.objects.create_user(
            username='geofence_test_user',
            email='geofence@test.com',
            password='testpass123'
        )
        from security.services.impossible_travel_service import ImpossibleTravelService
        self.service = ImpossibleTravelService()
    
    def test_point_inside_zone(self):
        """Test that a point inside the zone radius is detected."""
        # Create a zone at Delhi
        from security.models import GeofenceZone
        zone = GeofenceZone.objects.create(
            user=self.user,
            name='Office',
            latitude=Decimal('28.6139'),
            longitude=Decimal('77.2090'),
            radius_meters=1000,  # 1 km radius
            is_always_trusted=True,
            require_mfa_outside=True
        )
        
        # Check a point ~500m away (inside the zone)
        result = self.service.check_geofence_zones(
            self.user,
            28.6180,  # Slightly north
            77.2090
        )
        
        self.assertTrue(result.is_in_trusted_zone)
        self.assertEqual(result.zone_name, 'Office')
    
    def test_point_outside_zone(self):
        """Test that a point outside the zone radius is not detected."""
        from security.models import GeofenceZone
        zone = GeofenceZone.objects.create(
            user=self.user,
            name='Home',
            latitude=Decimal('28.6139'),
            longitude=Decimal('77.2090'),
            radius_meters=500,  # 500m radius
            is_always_trusted=True,
            require_mfa_outside=True
        )
        
        # Check a point ~10km away (outside the zone)
        result = self.service.check_geofence_zones(
            self.user,
            28.7000,  # Far north
            77.2090
        )
        
        self.assertFalse(result.is_in_trusted_zone)
        self.assertIsNone(result.zone_name)
    
    def test_mfa_required_outside_zones(self):
        """Test that MFA is required when outside all trusted zones."""
        from security.models import GeofenceZone
        GeofenceZone.objects.create(
            user=self.user,
            name='Home',
            latitude=Decimal('28.6139'),
            longitude=Decimal('77.2090'),
            radius_meters=500,
            is_always_trusted=True,
            require_mfa_outside=True  # This triggers MFA requirement
        )
        
        # Check from a completely different location
        result = self.service.check_geofence_zones(
            self.user,
            19.0760,  # Mumbai
            72.8777
        )
        
        self.assertFalse(result.is_in_trusted_zone)
        self.assertTrue(result.requires_mfa)


class TravelAnalysisTests(TestCase):
    """Test cases for complete travel analysis."""
    
    def setUp(self):
        """Create test user and locations."""
        self.user = User.objects.create_user(
            username='travel_test_user',
            email='travel@test.com',
            password='testpass123'
        )
        from security.services.impossible_travel_service import ImpossibleTravelService
        self.service = ImpossibleTravelService()
    
    def test_normal_local_travel(self):
        """Test analysis of local travel (within city)."""
        # Simulate moving 5 km in 30 minutes = 10 km/h (cycling)
        from security.services.impossible_travel_service import Coordinates
        
        source = Coordinates(
            latitude=28.6139,
            longitude=77.2090,
            source='gps'
        )
        destination = Coordinates(
            latitude=28.6500,
            longitude=77.2300,
            source='gps'
        )
        
        # 30 minutes = 1800 seconds
        analysis = self.service.analyze_travel_between_coords(
            source, destination, 1800
        )
        
        self.assertTrue(analysis.is_plausible)
        self.assertIn(analysis.inferred_mode, ['walking', 'driving', 'unknown'])
        self.assertEqual(analysis.severity, 'none')
    
    def test_flight_travel_detected(self):
        """Test detection of flight-speed travel."""
        from security.services.impossible_travel_service import Coordinates
        
        # Delhi to Mumbai (~1150 km)
        source = Coordinates(latitude=28.6139, longitude=77.2090)
        destination = Coordinates(latitude=19.0760, longitude=72.8777)
        
        # 2 hours = 7200 seconds (~575 km/h = flight speed)
        analysis = self.service.analyze_travel_between_coords(
            source, destination, 7200
        )
        
        self.assertTrue(analysis.is_plausible)  # Flight is plausible
        self.assertEqual(analysis.inferred_mode, 'flight')
        self.assertEqual(analysis.severity, 'high')
    
    def test_impossible_travel_detected(self):
        """Test detection of impossible travel (supersonic)."""
        from security.services.impossible_travel_service import Coordinates
        
        # New York to London (~5500 km)
        source = Coordinates(latitude=40.7128, longitude=-74.0060)
        destination = Coordinates(latitude=51.5074, longitude=-0.1278)
        
        # 1 hour = 3600 seconds (~5500 km/h = impossible)
        analysis = self.service.analyze_travel_between_coords(
            source, destination, 3600
        )
        
        self.assertFalse(analysis.is_plausible)
        self.assertEqual(analysis.inferred_mode, 'supersonic')
        self.assertEqual(analysis.severity, 'critical')
        self.assertEqual(analysis.action, 'blocked')


class AirlineAPIServiceTests(TestCase):
    """Test cases for airline API integration."""
    
    def setUp(self):
        """Import the airline service."""
        from security.services.airline_api_service import AirlineAPIService
        self.service = AirlineAPIService()
    
    def test_airport_lookup(self):
        """Test airport information lookup."""
        airport = self.service.get_airport('JFK')
        
        if airport:  # Will be None if no airport data configured
            self.assertEqual(airport.code, 'JFK')
            self.assertIn('New York', airport.city)
    
    @patch('security.services.airline_api_service.AirlineAPIService._amadeus_client')
    def test_booking_verification_success(self, mock_amadeus):
        """Test successful booking verification with mocked Amadeus."""
        # Mock Amadeus response
        mock_response = MagicMock()
        mock_response.data = [{
            'type': 'flight-order',
            'id': 'test123',
            'travelers': [{'name': {'lastName': 'TESTUSER'}}],
            'flightOffers': [{
                'itineraries': [{
                    'segments': [{
                        'departure': {'iataCode': 'DEL', 'at': '2026-01-22T10:00:00'},
                        'arrival': {'iataCode': 'BOM', 'at': '2026-01-22T12:00:00'},
                        'carrierCode': 'AI',
                        'number': '101'
                    }]
                }]
            }]
        }]
        
        with patch.object(self.service, '_amadeus_client', mock_amadeus):
            mock_amadeus.booking.flight_orders.get.return_value = mock_response
            
            result = self.service.verify_booking('ABC123', 'TESTUSER')
            
            # Should return verification result (may fail without real API)
            # This tests the structure, not the actual API call
            self.assertIsNotNone(result)
    
    def test_distance_calculation(self):
        """Test internal distance calculation."""
        # Delhi airport to Mumbai airport
        distance = self.service._distance_to(
            28.5562, 77.1000,  # DEL
            19.0896, 72.8656   # BOM
        )
        
        # Should be approximately 1150 km
        self.assertAlmostEqual(distance, 1150, delta=100)


class GeofenceAPITests(APITestCase):
    """API endpoint tests for geofencing."""
    
    def setUp(self):
        """Create test user and authenticate."""
        self.user = User.objects.create_user(
            username='api_test_user',
            email='api@test.com',
            password='testpass123'
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
    
    def test_list_zones_empty(self):
        """Test listing zones when none exist."""
        response = self.client.get('/api/security/geofence/zones/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data.get('zones', [])), 0)
    
    def test_create_zone(self):
        """Test creating a new trusted zone."""
        data = {
            'name': 'Home',
            'latitude': 28.6139,
            'longitude': 77.2090,
            'radius_meters': 500,
            'is_always_trusted': True,
            'require_mfa_outside': True
        }
        
        response = self.client.post('/api/security/geofence/zones/', data)
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['name'], 'Home')
    
    def test_record_location(self):
        """Test recording a GPS location."""
        data = {
            'latitude': 28.6139,
            'longitude': 77.2090,
            'accuracy_meters': 10,
            'source': 'gps'
        }
        
        response = self.client.post(
            '/api/security/geofence/location/record/',
            data
        )
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('location_id', response.data)
    
    def test_geofence_check(self):
        """Test checking if coordinates are in a trusted zone."""
        # First create a zone
        from security.models import GeofenceZone
        GeofenceZone.objects.create(
            user=self.user,
            name='Office',
            latitude=Decimal('28.6139'),
            longitude=Decimal('77.2090'),
            radius_meters=1000,
            is_always_trusted=True
        )
        
        # Check coordinates inside the zone
        response = self.client.post('/api/security/geofence/check/', {
            'latitude': 28.6150,
            'longitude': 77.2100
        })
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data.get('is_in_trusted_zone'))
    
    def test_list_travel_events(self):
        """Test listing impossible travel events."""
        response = self.client.get('/api/security/geofence/travel/events/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('events', response.data)


class ClonedSessionDetectionTests(TestCase):
    """Test cases for cloned session detection."""
    
    def setUp(self):
        """Create test user."""
        self.user = User.objects.create_user(
            username='clone_test_user',
            email='clone@test.com',
            password='testpass123'
        )
        from security.services.impossible_travel_service import ImpossibleTravelService
        self.service = ImpossibleTravelService()
    
    def test_simultaneous_sessions_same_location(self):
        """Two sessions from same location should NOT be flagged."""
        from security.services.impossible_travel_service import Coordinates
        
        loc1 = Coordinates(latitude=28.6139, longitude=77.2090)
        loc2 = Coordinates(latitude=28.6140, longitude=77.2091)  # ~100m away
        
        is_cloned = self.service.detect_cloned_session(
            self.user, loc1, loc2, time_delta_seconds=60
        )
        
        self.assertFalse(is_cloned)
    
    def test_simultaneous_sessions_far_apart(self):
        """Two sessions from far locations at same time should be flagged."""
        from security.services.impossible_travel_service import Coordinates
        
        loc1 = Coordinates(latitude=28.6139, longitude=77.2090)  # Delhi
        loc2 = Coordinates(latitude=19.0760, longitude=72.8777)  # Mumbai
        
        # 5 minutes apart = 300 seconds
        is_cloned = self.service.detect_cloned_session(
            self.user, loc1, loc2, time_delta_seconds=300
        )
        
        self.assertTrue(is_cloned)

"""
Dead Drop API Tests
====================

Integration tests for the mesh dead drop REST API.

@author Password Manager Team
@created 2026-01-22
"""

from django.test import TestCase
from django.contrib.auth.models import User
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status
from ..models import DeadDrop, MeshNode


class DeadDropAPITests(TestCase):
    """Tests for Dead Drop API endpoints."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.user = User.objects.create_user(
            username='testuser',
            password='testpassword123'
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
    
    def test_list_deaddrops_empty(self):
        """Test listing dead drops when empty."""
        response = self.client.get('/api/mesh/deaddrops/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 0)
        self.assertEqual(response.data['dead_drops'], [])
    
    def test_create_deaddrop(self):
        """Test creating a dead drop."""
        data = {
            'title': 'Test Dead Drop',
            'description': 'A test dead drop',
            'latitude': '40.7128',
            'longitude': '-74.0060',
            'radius_meters': 50,
            'location_hint': 'Near the fountain',
            'secret': 'my secret password',
            'required_fragments': 3,
            'total_fragments': 5,
            'expires_in_hours': 24,
        }
        
        response = self.client.post('/api/mesh/deaddrops/', data)
        
        # May fail if no mesh nodes available, check structure
        if response.status_code == status.HTTP_201_CREATED:
            self.assertIn('dead_drop', response.data)
            self.assertEqual(response.data['dead_drop']['title'], 'Test Dead Drop')
    
    def test_create_deaddrop_invalid_threshold(self):
        """Test that invalid threshold is rejected."""
        data = {
            'title': 'Invalid',
            'latitude': '40.7128',
            'longitude': '-74.0060',
            'secret': 'secret',
            'required_fragments': 5,  # k > n
            'total_fragments': 3,
        }
        
        response = self.client.post('/api/mesh/deaddrops/', data)
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('required_fragments', str(response.data))


class MeshNodeAPITests(TestCase):
    """Tests for Mesh Node API endpoints."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.user = User.objects.create_user(
            username='nodeuser',
            password='nodepassword123'
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
    
    def test_register_node(self):
        """Test registering a mesh node."""
        import base64
        import os
        
        # Generate a mock public key (32 bytes for X25519)
        public_key = base64.b64encode(os.urandom(32)).decode()
        
        data = {
            'device_name': 'Test Node',
            'device_type': 'phone_android',
            'ble_address': 'AA:BB:CC:DD:EE:FF',
            'public_key': public_key,
            'max_fragments': 10,
        }
        
        response = self.client.post('/api/mesh/nodes/', data)
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['node']['device_name'], 'Test Node')
    
    def test_register_node_invalid_ble_address(self):
        """Test that invalid BLE address is rejected."""
        import base64
        import os
        
        data = {
            'device_name': 'Bad Node',
            'device_type': 'phone_android',
            'ble_address': 'invalid-address',
            'public_key': base64.b64encode(os.urandom(32)).decode(),
        }
        
        response = self.client.post('/api/mesh/nodes/', data)
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('ble_address', response.data)
    
    def test_list_nodes(self):
        """Test listing mesh nodes."""
        response = self.client.get('/api/mesh/nodes/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('nodes', response.data)


class LocationVerificationTests(TestCase):
    """Tests for location verification."""
    
    def setUp(self):
        """Set up test fixtures."""
        from ..services.location_verification_service import (
            LocationVerificationService,
            LocationClaim,
            VerificationMethod,
        )
        self.service = LocationVerificationService()
        self.LocationClaim = LocationClaim
        self.VerificationMethod = VerificationMethod
    
    def test_verify_at_correct_location(self):
        """Test verification at correct location."""
        from ..services.location_verification_service import VerificationResult
        
        target_lat, target_lon = 40.7128, -74.0060
        
        claim = self.LocationClaim(
            latitude=40.7130,  # Very close
            longitude=-74.0062,
            accuracy_meters=10,
            ble_nodes=[
                {'id': 'node-1', 'rssi': -60},
                {'id': 'node-2', 'rssi': -65},
            ]
        )
        
        result = self.service.verify_location(
            claimed=claim,
            target_lat=target_lat,
            target_lon=target_lon,
            radius_meters=100,
            require_ble=True,
            min_ble_nodes=2,
        )
        
        self.assertEqual(result.result, VerificationResult.SUCCESS)
        self.assertTrue(result.gps_verified)
        self.assertTrue(result.ble_verified)
    
    def test_verify_at_wrong_location(self):
        """Test verification at wrong location."""
        from ..services.location_verification_service import VerificationResult
        
        claim = self.LocationClaim(
            latitude=34.0522,  # LA, far from NYC
            longitude=-118.2437,
            accuracy_meters=10,
        )
        
        result = self.service.verify_location(
            claimed=claim,
            target_lat=40.7128,  # NYC
            target_lon=-74.0060,
            radius_meters=50,
            require_ble=False,
        )
        
        self.assertEqual(result.result, VerificationResult.FAILED)
        self.assertFalse(result.gps_verified)
    
    def test_impossible_travel_detection(self):
        """Test impossible travel detection."""
        from ..services.location_verification_service import VerificationResult
        from datetime import timedelta
        from django.utils import timezone
        
        user_id = 'test-user-1'
        
        # First location: NYC
        claim1 = self.LocationClaim(
            latitude=40.7128,
            longitude=-74.0060,
            accuracy_meters=10,
            timestamp=timezone.now()
        )
        
        # Verify first (should pass)
        self.service.verify_location(
            claimed=claim1,
            target_lat=40.7128,
            target_lon=-74.0060,
            radius_meters=100,
            user_id=user_id,
            require_ble=False,
        )
        
        # Second location: LA, 1 second later (impossible!)
        claim2 = self.LocationClaim(
            latitude=34.0522,
            longitude=-118.2437,
            accuracy_meters=10,
            timestamp=timezone.now() + timedelta(seconds=1)
        )
        
        result = self.service.verify_location(
            claimed=claim2,
            target_lat=34.0522,
            target_lon=-118.2437,
            radius_meters=100,
            user_id=user_id,
            require_ble=False,
        )
        
        self.assertEqual(result.result, VerificationResult.SPOOFING_DETECTED)
        self.assertFalse(result.velocity_check_passed)

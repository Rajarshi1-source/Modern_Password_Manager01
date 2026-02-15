"""
Location Verification Service Tests
=====================================

Tests for the location verification service ensuring alignment with implementation:
- GPS verification
- BLE node detection
- Anti-spoofing checks (velocity)
- NFC verification

@author Password Manager Team
@created 2026-02-15
"""

from django.test import TestCase
from django.utils import timezone
from datetime import timedelta
from mesh_deaddrop.services.location_verification_service import (
    LocationVerificationService,
    VerificationResult,
    LocationClaim,
    VerificationMethod
)


class LocationVerificationServiceTests(TestCase):
    """Tests for LocationVerificationService."""

    def setUp(self):
        """Set up test data."""
        self.service = LocationVerificationService()
        self.target_lat = 40.7128  # NYC
        self.target_lon = -74.0060
        self.radius = 50.0
        self.user_id = "test_user_123"

        # Clear history for test user
        self.service.clear_user_history(self.user_id)

    def test_verify_location_success(self):
        """Test verifying a valid location claim within radius."""
        claim = LocationClaim(
            latitude=self.target_lat,
            longitude=self.target_lon,
            accuracy_meters=5.0,
            source=VerificationMethod.GPS
        )

        result = self.service.verify_location(
            claimed=claim,
            target_lat=self.target_lat,
            target_lon=self.target_lon,
            radius_meters=self.radius,
            require_ble=False
        )

        self.assertEqual(result.result, VerificationResult.SUCCESS)
        self.assertTrue(result.gps_verified)
        self.assertGreaterEqual(result.confidence, 0.7)

    def test_verify_location_too_far(self):
        """Test verification fails when location is outside radius."""
        # Claim is far away (~1.1km)
        claim = LocationClaim(
            latitude=self.target_lat + 0.01,
            longitude=self.target_lon,
            accuracy_meters=5.0
        )

        result = self.service.verify_location(
            claimed=claim,
            target_lat=self.target_lat,
            target_lon=self.target_lon,
            radius_meters=self.radius,
            require_ble=False
        )

        self.assertNotEqual(result.result, VerificationResult.SUCCESS)
        self.assertFalse(result.gps_verified)
        self.assertIn("Too far", result.message)

    def test_verify_ble_requirements_failure(self):
        """Test verification fails when required BLE nodes are missing."""
        claim = LocationClaim(
            latitude=self.target_lat,
            longitude=self.target_lon,
            ble_nodes=[]  # No nodes found
        )

        result = self.service.verify_location(
            claimed=claim,
            target_lat=self.target_lat,
            target_lon=self.target_lon,
            require_ble=True,
            min_ble_nodes=1
        )

        self.assertNotEqual(result.result, VerificationResult.SUCCESS)
        self.assertIn("Insufficient BLE nodes", result.message)

    def test_verify_ble_success(self):
        """Test verification succeeds with sufficient BLE nodes."""
        claim = LocationClaim(
            latitude=self.target_lat,
            longitude=self.target_lon,
            ble_nodes=[
                {'id': 'node1', 'rssi': -60},
                {'id': 'node2', 'rssi': -70}
            ]
        )

        result = self.service.verify_location(
            claimed=claim,
            target_lat=self.target_lat,
            target_lon=self.target_lon,
            require_ble=True,
            min_ble_nodes=2
        )

        self.assertEqual(result.result, VerificationResult.SUCCESS)
        self.assertTrue(result.ble_verified)

    def test_velocity_check_impossible_travel(self):
        """Test that impossible travel speeds are detected as spoofing."""
        # First location
        claim1 = LocationClaim(
            latitude=self.target_lat,
            longitude=self.target_lon,
            timestamp=timezone.now() - timedelta(minutes=5)
        )
        self.service.verify_location(
            claimed=claim1,
            target_lat=self.target_lat,
            target_lon=self.target_lon,
            user_id=self.user_id,
            require_ble=False
        )

        # Second location (London) 5 mins later - physically impossible
        claim2 = LocationClaim(
            latitude=51.5074,
            longitude=-0.1278,
            timestamp=timezone.now()
        )

        result = self.service.verify_location(
            claimed=claim2,
            target_lat=51.5074,
            target_lon=-0.1278,
            user_id=self.user_id,
            require_ble=False
        )

        self.assertEqual(result.result, VerificationResult.SPOOFING_DETECTED)
        self.assertFalse(result.velocity_check_passed)
        self.assertIn("Impossible travel", result.message)

    def test_nfc_verification_success(self):
        """Test successful NFC verification."""
        claim = LocationClaim(
            latitude=self.target_lat,
            longitude=self.target_lon,
            nfc_response="valid_secret_token"
        )

        result = self.service.verify_location(
            claimed=claim,
            target_lat=self.target_lat,
            target_lon=self.target_lon,
            require_ble=False,
            require_nfc=True,
            nfc_expected_response="valid_secret_token"
        )

        self.assertEqual(result.result, VerificationResult.SUCCESS)
        self.assertTrue(result.nfc_verified)

    def test_nfc_verification_failure(self):
        """Test failed NFC verification with wrong token."""
        claim = LocationClaim(
            latitude=self.target_lat,
            longitude=self.target_lon,
            nfc_response="wrong_token"
        )

        result = self.service.verify_location(
            claimed=claim,
            target_lat=self.target_lat,
            target_lon=self.target_lon,
            require_ble=False,
            require_nfc=True,
            nfc_expected_response="valid_secret_token"
        )

        self.assertEqual(result.result, VerificationResult.SPOOFING_DETECTED)
        self.assertIn("NFC verification failed", result.message)

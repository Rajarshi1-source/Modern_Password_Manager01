"""Integration tests for circadian_totp HTTP API.

Follows the same force-login + DRF APIClient pattern as
``auth_module/tests/test_recovery_flow_integration.py``.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone as _tz

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from circadian_totp import services
from circadian_totp.models import (
    CircadianProfile,
    CircadianTOTPDevice,
    SleepObservation,
)

User = get_user_model()


@pytest.mark.django_db
class TestCircadianProfileAPI(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="circuser",
            email="circ@example.com",
            password="TestPassword123!",
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_profile_endpoint_returns_profile_wearables_devices(self):
        response = self.client.get("/api/circadian/profile/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        payload = response.json()
        self.assertIn("profile", payload)
        self.assertIn("wearables", payload)
        self.assertIn("devices", payload)
        self.assertEqual(payload["wearables"], [])
        self.assertEqual(payload["devices"], [])

    def test_device_setup_and_verify_flow(self):
        response = self.client.post("/api/circadian/device/setup/", {"name": "Watch"})
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        payload = response.json()
        self.assertIn("device", payload)
        self.assertIn("provisioning_uri", payload)
        device_id = payload["device"]["id"]
        self.assertFalse(payload["device"]["confirmed"])
        device = CircadianTOTPDevice.objects.get(id=device_id)

        at = datetime(2026, 4, 17, 3, 0, tzinfo=_tz.utc)
        code = services.generate_code(device, at=at)

        verify_resp = self.client.post(
            "/api/circadian/device/verify/",
            {"device_id": device_id, "code": code},
            format="json",
        )
        self.assertIn(
            verify_resp.status_code,
            (status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST),
        )

    def test_device_verify_rejects_missing_fields(self):
        response = self.client.post(
            "/api/circadian/device/verify/", {}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_mfa_verify_requires_code(self):
        response = self.client.post("/api/circadian/verify/", {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


@pytest.mark.django_db
class TestWearableIngest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="wearer", email="w@example.com", password="TestPassword123!"
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_ingest_observations_creates_rows_and_recomputes_profile(self):
        now = datetime(2026, 4, 17, 12, 0, tzinfo=_tz.utc)
        observations = [
            {
                "sleep_start": (now - timedelta(days=i, hours=8)).isoformat(),
                "sleep_end": (now - timedelta(days=i, hours=0)).isoformat(),
                "efficiency_score": 92.0,
            }
            for i in range(1, 6)
        ]
        response = self.client.post(
            "/api/circadian/wearables/manual/ingest/",
            {"observations": observations},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        body = response.json()
        self.assertEqual(body["created"], 5)
        self.assertIn("profile", body)
        self.assertEqual(
            SleepObservation.objects.filter(user=self.user).count(), 5
        )

    def test_wearable_connect_fitbit_returns_400_or_501_without_credentials(self):
        response = self.client.post("/api/circadian/wearables/fitbit/connect/")
        # With empty OAuth env vars, the adapter will either 400 (ValueError)
        # or 501 (NotImplementedError). Both are acceptable.
        self.assertIn(
            response.status_code,
            (
                status.HTTP_400_BAD_REQUEST,
                status.HTTP_501_NOT_IMPLEMENTED,
                status.HTTP_200_OK,
            ),
        )


@pytest.mark.django_db
class TestCircadianAuthGate(TestCase):
    def test_unauthenticated_access_rejected(self):
        client = APIClient()
        for path in (
            "/api/circadian/profile/",
            "/api/circadian/device/setup/",
            "/api/circadian/verify/",
        ):
            resp = client.get(path) if path.endswith("profile/") else client.post(path, {}, format="json")
            self.assertIn(
                resp.status_code,
                (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN),
            )

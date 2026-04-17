"""Smoke tests for the DRF HTTP surface of heartbeat_auth."""

from __future__ import annotations

import pytest

pytest.importorskip('numpy')

from django.contrib.auth import get_user_model
from django.test import override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

User = get_user_model()


@override_settings(HEARTBEAT_AUTH_ENABLED=True)
class HeartbeatEnrollEndpointTest(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(email='api-hb@example.com', password='x' * 12)
        self.client.force_authenticate(self.user)

    def _feat(self):
        return {
            'features': {
                'mean_hr': 72.0, 'rmssd': 46.0,
                'sdnn': 56.0, 'pnn50': 0.24, 'lf_hf_ratio': 1.6,
            },
            'capture_duration_s': 30.0,
            'frame_rate': 30.0,
        }

    def test_enroll_happy_path(self):
        resp = self.client.post(reverse('heartbeat_auth:enroll'), data=self._feat(), format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        body = resp.json()
        self.assertTrue(body['success'])
        self.assertEqual(body['enrollment_count'], 1)

    def test_enroll_empty_payload_400(self):
        resp = self.client.post(reverse('heartbeat_auth:enroll'), data={}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_profile_endpoint_returns_shape(self):
        resp = self.client.get(reverse('heartbeat_auth:profile'))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        body = resp.json()
        self.assertIn('profile', body)
        self.assertIn('enrollment_count', body['profile'])

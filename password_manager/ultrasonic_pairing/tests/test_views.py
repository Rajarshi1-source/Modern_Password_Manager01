"""Smoke tests for the DRF HTTP surface of ultrasonic_pairing."""

from __future__ import annotations

import base64
import os

from django.contrib.auth import get_user_model
from django.test import override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from ultrasonic_pairing.models import PairingPurpose

User = get_user_model()


def _fake_pub() -> str:
    return base64.b64encode(b'\x04' + os.urandom(64)).decode()


@override_settings(ULTRASONIC_PAIRING_ENABLED=True, PAIRING_SESSION_TTL_SECONDS=120)
class ApiInitiateTest(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(email='api@example.com', password='x' * 12)
        self.client.force_authenticate(self.user)

    def test_initiate_happy_path(self):
        resp = self.client.post(
            reverse('ultrasonic_pairing:initiate'),
            data={'pub_key': _fake_pub(), 'purpose': PairingPurpose.ITEM_SHARE},
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        body = resp.json()
        self.assertTrue(body['success'])
        self.assertIn('session_id', body)
        self.assertIn('nonce', body)

    def test_initiate_missing_fields_400(self):
        resp = self.client.post(
            reverse('ultrasonic_pairing:initiate'),
            data={},
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_initiate_bad_pub_key_400(self):
        resp = self.client.post(
            reverse('ultrasonic_pairing:initiate'),
            data={
                'pub_key': base64.b64encode(b'short').decode(),
                'purpose': PairingPurpose.ITEM_SHARE,
            },
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(resp.json()['error'], 'invalid_pub_key')

"""End-to-end tests for the HRV -> duress-bridge -> decoy-vault path."""

from __future__ import annotations

from unittest import mock

import pytest

pytest.importorskip('numpy')

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from heartbeat_auth.models import (
    HeartbeatProfile,
    HeartbeatSession,
    ProfileStatus,
    SessionStatus,
)
from heartbeat_auth.services import heartbeat_service

User = get_user_model()


class _FakeRequest:
    def __init__(self):
        self.META = {'REMOTE_ADDR': '127.0.0.1', 'HTTP_USER_AGENT': 'test'}


def _base_profile(user):
    return HeartbeatProfile.objects.create(
        user=user,
        status=ProfileStatus.ENROLLED,
        baseline_mean=[70.0, 45.0, 55.0, 0.25, 1.5],
        baseline_cov=[
            [9.0, 0, 0, 0, 0],
            [0, 9.0, 0, 0, 0],
            [0, 0, 9.0, 0, 0],
            [0, 0, 0, 0.01, 0],
            [0, 0, 0, 0, 0.25],
        ],
        baseline_rmssd=45.0,
        baseline_sdnn=8.0,
        baseline_mean_hr=70.0,
        match_threshold=0.3,  # loose so near-baseline still matches
    )


@override_settings(HEARTBEAT_AUTH_ENABLED=True, HEARTBEAT_DURESS_ENABLED=True)
class HeartbeatDuressBridgeTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email='duress@example.com', password='x' * 12)
        _base_profile(self.user)

    def _calm(self):
        return {
            'mean_hr': 70.0, 'rmssd': 45.0,
            'sdnn': 55.0, 'pnn50': 0.25, 'lf_hf_ratio': 1.5,
        }

    def _stressed(self):
        return {
            'mean_hr': 95.0, 'rmssd': 25.0,
            'sdnn': 55.0, 'pnn50': 0.05, 'lf_hf_ratio': 4.5,
        }

    def test_calm_reading_allows(self):
        result = heartbeat_service.verify_reading(
            user=self.user, features=self._calm(), request=_FakeRequest(),
        )
        self.assertEqual(result['decision'], 'allow')
        self.assertFalse(result['duress'])
        self.assertIsNone(result['decoy_vault'])

    def test_duress_reading_returns_decoy_from_bridge(self):
        decoy = {'items': [{'site': 'decoy.example', 'username': 'u', 'password': 'x'}]}
        with mock.patch(
            'heartbeat_auth.services.duress_bridge.maybe_activate_duress',
            return_value=decoy,
        ) as mock_bridge:
            result = heartbeat_service.verify_reading(
                user=self.user, features=self._stressed(), request=_FakeRequest(),
            )
        self.assertEqual(result['decision'], 'duress')
        self.assertTrue(result['duress'])
        self.assertEqual(result['decoy_vault'], decoy)
        mock_bridge.assert_called_once()
        session = HeartbeatSession.objects.get(id=result['session_id'])
        self.assertEqual(session.status, SessionStatus.DURESS)
        self.assertTrue(session.duress_detected)

    @override_settings(HEARTBEAT_DURESS_ENABLED=False)
    def test_duress_flag_off_never_returns_decoy(self):
        # With the subordinate flag disabled, even a stress signature
        # routes through the normal allow/deny gate.
        result = heartbeat_service.verify_reading(
            user=self.user, features=self._stressed(), request=_FakeRequest(),
        )
        self.assertNotEqual(result['decision'], 'duress')
        self.assertIsNone(result['decoy_vault'])

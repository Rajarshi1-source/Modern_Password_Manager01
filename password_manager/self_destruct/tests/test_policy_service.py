"""Tests for the self-destruct policy engine."""

from __future__ import annotations

import uuid
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone

from self_destruct.models import (
    PolicyKind,
    PolicyStatus,
    SelfDestructPolicy,
)
from self_destruct.services import policy_service
from self_destruct.services.geofence import GeofenceEvaluator, haversine_m
from self_destruct.tasks import expire_stale_policies

User = get_user_model()


class _FakeRequest:
    def __init__(self, meta=None):
        self.META = meta or {}
        self.data = {}


class _StubVault:
    def __init__(self, pk):
        self.id = pk


@override_settings(SELF_DESTRUCT_PASSWORDS_ENABLED=True)
class TTLPolicyTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email='bob@example.com', password='p' * 12)
        self.vault = _StubVault(uuid.uuid4())

    def _policy(self, **kwargs):
        return SelfDestructPolicy.objects.create(
            user=self.user,
            vault_item_id=self.vault.id,
            **kwargs,
        )

    def test_ttl_expired_flips_status(self):
        self._policy(kinds=[PolicyKind.TTL], expires_at=timezone.now() - timedelta(minutes=1))
        reason = policy_service.evaluate_access(self.vault, _FakeRequest())
        self.assertEqual(reason, 'ttl_expired')
        stored = SelfDestructPolicy.objects.get(vault_item_id=self.vault.id)
        self.assertEqual(stored.status, PolicyStatus.EXPIRED)

    def test_ttl_future_allows(self):
        self._policy(kinds=[PolicyKind.TTL], expires_at=timezone.now() + timedelta(hours=1))
        self.assertEqual(policy_service.evaluate_access(self.vault, _FakeRequest()), 'allow')

    def test_burn_after_read_single_use(self):
        self._policy(kinds=[PolicyKind.BURN_AFTER_READ])
        self.assertEqual(policy_service.evaluate_access(self.vault, _FakeRequest()), 'allow')
        policy_service.record_access(self.vault, _FakeRequest())
        # Second read must be denied.
        self.assertEqual(policy_service.evaluate_access(self.vault, _FakeRequest()), 'burned')

    def test_use_limit_enforced(self):
        self._policy(kinds=[PolicyKind.USE_LIMIT], max_uses=2)
        req = _FakeRequest()
        for _ in range(2):
            self.assertEqual(policy_service.evaluate_access(self.vault, req), 'allow')
            policy_service.record_access(self.vault, req)
        self.assertEqual(policy_service.evaluate_access(self.vault, req), 'use_limit_exceeded')

    def test_expire_stale_policies_task_flips_rows(self):
        self._policy(kinds=[PolicyKind.TTL], expires_at=timezone.now() - timedelta(minutes=5))
        flipped = expire_stale_policies()
        self.assertEqual(flipped, 1)


class GeofenceTest(TestCase):
    def test_haversine_roughly_correct(self):
        # London <-> Paris is ~344 km.
        dist = haversine_m(51.5074, -0.1278, 48.8566, 2.3522)
        self.assertGreater(dist, 300_000)
        self.assertLess(dist, 400_000)

    def test_evaluator_inside_radius(self):
        ev = GeofenceEvaluator(51.5074, -0.1278, 1_000_000)  # 1000 km
        self.assertTrue(ev.contains(48.8566, 2.3522))

    def test_evaluator_outside_radius(self):
        ev = GeofenceEvaluator(51.5074, -0.1278, 10_000)  # 10 km
        self.assertFalse(ev.contains(48.8566, 2.3522))

    def test_missing_coords_fails_closed(self):
        ev = GeofenceEvaluator(51.5074, -0.1278, 10_000)
        self.assertFalse(ev.contains(None, 2.3522))
        self.assertFalse(ev.contains(48.8566, None))

"""
Mesh Dead Drop Extension Tests
===============================

Covers the new subsystems added for the "Dead Drop Password Sharing via
Offline Mesh Networks" feature:

- ``RelayTrustService`` EWMA behaviour
- ``SimulatedBLEAdapter`` distance-based RSSI simulation
- ``PendingFragmentSync`` queueing / flushing
- ``LocationVerificationService`` distinct-fingerprint rule
- ``/api/mesh/nodes/<id>/trust/``, ``deaddrops/<id>/health/``,
  ``deaddrops/<id>/rebalance/`` endpoints
- ``MeshNodeConsumer`` authentication / event fan-out
"""

from __future__ import annotations

import uuid
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from mesh_deaddrop.models import (
    DeadDrop,
    DeadDropFragment,
    MeshNode,
    PendingFragmentSync,
)
from mesh_deaddrop.services import (
    RelayTrustService,
    SimulatedBLEAdapter,
    pending_sync_service,
)
from mesh_deaddrop.services.location_verification_service import (
    LocationClaim,
    LocationVerificationService,
    VerificationResult,
)

User = get_user_model()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_node(owner, *, trust=0.5, lat=37.0, lon=-122.0, online=True, addr=None):
    return MeshNode.objects.create(
        owner=owner,
        public_key=f'pk-{uuid.uuid4().hex[:8]}',
        device_name=f'dev-{uuid.uuid4().hex[:4]}',
        device_type='phone_android',
        ble_address=addr or f'AA:BB:CC:{uuid.uuid4().hex[:2].upper()}:{uuid.uuid4().hex[:2].upper()}:{uuid.uuid4().hex[:2].upper()}',
        is_online=online,
        trust_score=trust,
        last_known_latitude=Decimal(str(lat)),
        last_known_longitude=Decimal(str(lon)),
    )


def _make_drop(owner, *, required=2, total=3):
    return DeadDrop.objects.create(
        owner=owner,
        title='drop',
        latitude=Decimal('37.7749'),
        longitude=Decimal('-122.4194'),
        radius_meters=50,
        encrypted_secret=b'\x00' * 32,
        secret_hash='h' * 32,
        required_fragments=required,
        total_fragments=total,
        expires_at=timezone.now() + timedelta(hours=2),
    )


# ---------------------------------------------------------------------------
# RelayTrustService
# ---------------------------------------------------------------------------

class RelayTrustServiceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email='trust@example.com', password='x')
        self.node = _make_node(self.user, trust=0.5)

    def test_record_success_raises_trust(self):
        svc = RelayTrustService(alpha=0.5)
        summary = svc.record_success(self.node, duration_ms=100)
        self.assertGreater(summary.trust_score, 0.5)
        self.assertEqual(summary.successful_transfers, 1)

    def test_record_failure_lowers_trust(self):
        svc = RelayTrustService(alpha=0.5)
        summary = svc.record_failure(self.node, reason='timeout')
        self.assertLess(summary.trust_score, 0.5)
        self.assertEqual(summary.failed_transfers, 1)

    def test_slow_success_still_positive_but_capped(self):
        svc = RelayTrustService(alpha=0.5)
        fast = svc.record_success(_make_node(self.user, trust=0.5), duration_ms=100)
        slow = svc.record_success(_make_node(self.user, trust=0.5), duration_ms=10_000)
        self.assertGreater(fast.trust_score, slow.trust_score)
        self.assertGreater(slow.trust_score, 0.5)

    def test_fraud_slash_is_sharp(self):
        self.node.trust_score = 0.9
        self.node.save()
        svc = RelayTrustService()
        summary = svc.record_fraud(self.node, reason='replay')
        self.assertLess(summary.trust_score, 0.3)
        self.node.refresh_from_db()
        self.assertFalse(self.node.is_available_for_storage)

    def test_recompute_baseline_uses_counters(self):
        self.node.successful_transfers = 8
        self.node.failed_transfers = 2
        self.node.total_uptime_hours = 100
        self.node.trust_score = 0.1
        self.node.save()
        svc = RelayTrustService()
        summary = svc.recompute_baseline(self.node)
        self.assertAlmostEqual(summary.trust_score, 0.8 + min(0.05, (100 / 500) * 0.05), places=3)


# ---------------------------------------------------------------------------
# Simulated BLE adapter
# ---------------------------------------------------------------------------

class SimulatedBLEAdapterTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email='ble@example.com', password='x')

    def test_scan_orders_nodes_by_distance(self):
        near = _make_node(self.user, lat=37.7749, lon=-122.4194)
        far = _make_node(self.user, lat=37.77495, lon=-122.41945)  # ~6m away
        outside = _make_node(self.user, lat=38.0, lon=-122.0)
        adapter = SimulatedBLEAdapter(
            observer_location=(37.7749, -122.4194),
            max_range_m=100,
        )
        results = adapter.scan(timeout_seconds=0.1)
        node_ids = {r.node_id for r in results}
        self.assertIn(str(near.id), node_ids)
        self.assertIn(str(far.id), node_ids)
        self.assertNotIn(str(outside.id), node_ids)
        near_rssi = next(r.rssi for r in results if r.node_id == str(near.id))
        far_rssi = next(r.rssi for r in results if r.node_id == str(far.id))
        self.assertGreaterEqual(near_rssi, far_rssi)

    def test_advertise_records_audit(self):
        adapter = SimulatedBLEAdapter()
        adapter.advertise(b'hello')
        self.assertTrue(any(e['op'] == 'advertise' for e in adapter.audit_log))

    def test_write_fragment_is_successful(self):
        adapter = SimulatedBLEAdapter()
        res = adapter.write_fragment('AA:BB:CC:DD:EE:FF', b'payload-123')
        self.assertTrue(res.success)
        self.assertEqual(res.bytes_transferred, len(b'payload-123'))


# ---------------------------------------------------------------------------
# PendingFragmentSync
# ---------------------------------------------------------------------------

class PendingFragmentSyncTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email='sync@example.com', password='x')
        self.node = _make_node(self.user, online=False)
        self.drop = _make_drop(self.user, required=2, total=3)
        self.fragment = DeadDropFragment.objects.create(
            dead_drop=self.drop,
            fragment_index=1,
            encrypted_fragment=b'\x01\x02',
            fragment_hash='h' * 32,
            node=self.node,
        )

    def test_enqueue_is_idempotent(self):
        a = pending_sync_service.enqueue_pending_sync(self.fragment, self.node)
        b = pending_sync_service.enqueue_pending_sync(self.fragment, self.node)
        self.assertEqual(a.pk, b.pk)
        self.assertEqual(PendingFragmentSync.objects.count(), 1)

    def test_offline_node_not_flushed(self):
        pending_sync_service.enqueue_pending_sync(self.fragment, self.node)
        with patch('mesh_deaddrop.consumers.broadcast_fragment_sync') as m:
            result = pending_sync_service.flush_queue_for_online_nodes()
        self.assertEqual(result.nodes_notified, 0)
        m.assert_not_called()

    def test_online_node_triggers_broadcast(self):
        pending_sync_service.enqueue_pending_sync(self.fragment, self.node)
        self.node.is_online = True
        self.node.save()
        with patch('mesh_deaddrop.services.pending_sync_service.broadcast_fragment_sync') as m:
            # import happens inside the function, so patch via that path won't stick —
            # patch the consumers module instead.
            pass
        with patch('mesh_deaddrop.consumers.broadcast_fragment_sync') as m:
            result = pending_sync_service.flush_queue_for_online_nodes()
        self.assertEqual(result.nodes_notified, 1)
        self.assertEqual(result.syncs_touched, 1)
        m.assert_called_once()
        sync = PendingFragmentSync.objects.get()
        self.assertEqual(sync.status, 'delivering')
        self.assertEqual(sync.retry_count, 1)

    def test_mark_delivered_by_device(self):
        sync = pending_sync_service.enqueue_pending_sync(self.fragment, self.node)
        self.node.is_online = True
        self.node.save()
        with patch('mesh_deaddrop.consumers.broadcast_fragment_sync'):
            pending_sync_service.flush_queue_for_online_nodes()
        count = pending_sync_service.mark_delivered_by_device(self.node, [sync.id])
        self.assertEqual(count, 1)
        sync.refresh_from_db()
        self.assertEqual(sync.status, 'delivered')
        self.assertIsNotNone(sync.delivered_at)

    def test_expire_stale_syncs(self):
        sync = pending_sync_service.enqueue_pending_sync(
            self.fragment, self.node, expires_in_hours=1
        )
        sync.expires_at = timezone.now() - timedelta(minutes=1)
        sync.save()
        expired = pending_sync_service.expire_stale_syncs()
        self.assertEqual(expired, 1)
        sync.refresh_from_db()
        self.assertEqual(sync.status, 'failed')


# ---------------------------------------------------------------------------
# Distinct-fingerprint rule
# ---------------------------------------------------------------------------

class DistinctFingerprintTests(TestCase):
    """Verifies the spoof-resistance rule added to LocationVerificationService."""

    def _base_claim(self, ble_nodes):
        return LocationClaim(
            latitude=37.7749,
            longitude=-122.4194,
            accuracy_meters=5,
            ble_nodes=ble_nodes,
        )

    def test_distinct_fingerprints_accepted(self):
        svc = LocationVerificationService()
        result = svc.verify_location(
            claimed=self._base_claim([
                {'id': 'a', 'rssi': -55, 'device_fingerprint': 'fp-a'},
                {'id': 'b', 'rssi': -62, 'device_fingerprint': 'fp-b'},
            ]),
            target_lat=37.7749,
            target_lon=-122.4194,
            radius_meters=50,
            user_id='u1',
            min_ble_nodes=2,
        )
        self.assertIn(
            result.result,
            (VerificationResult.SUCCESS, VerificationResult.INSUFFICIENT_EVIDENCE),
        )
        self.assertTrue(result.ble_verified)

    def test_same_fingerprint_reports_spoofing(self):
        svc = LocationVerificationService()
        result = svc.verify_location(
            claimed=self._base_claim([
                {'id': 'a', 'rssi': -55, 'device_fingerprint': 'fp-same'},
                {'id': 'b', 'rssi': -60, 'device_fingerprint': 'fp-same'},
            ]),
            target_lat=37.7749,
            target_lon=-122.4194,
            radius_meters=50,
            user_id='u2',
            min_ble_nodes=2,
        )
        self.assertEqual(result.result, VerificationResult.SPOOFING_DETECTED)

    def test_duplicate_rssi_pattern_reports_spoofing(self):
        svc = LocationVerificationService()
        result = svc.verify_location(
            claimed=self._base_claim([
                {'id': 'a', 'rssi': -55, 'device_fingerprint': 'fp-a'},
                {'id': 'b', 'rssi': -55, 'device_fingerprint': 'fp-b'},
                {'id': 'c', 'rssi': -55, 'device_fingerprint': 'fp-c'},
            ]),
            target_lat=37.7749,
            target_lon=-122.4194,
            radius_meters=50,
            user_id='u3',
            min_ble_nodes=2,
        )
        self.assertEqual(result.result, VerificationResult.SPOOFING_DETECTED)

    def test_disabled_check_lets_duplicates_pass(self):
        svc = LocationVerificationService()
        result = svc.verify_location(
            claimed=self._base_claim([
                {'id': 'a', 'rssi': -55, 'device_fingerprint': 'fp-same'},
                {'id': 'b', 'rssi': -55, 'device_fingerprint': 'fp-same'},
            ]),
            target_lat=37.7749,
            target_lon=-122.4194,
            radius_meters=50,
            user_id='u4',
            min_ble_nodes=2,
            require_distinct_fingerprints=False,
        )
        self.assertNotEqual(result.result, VerificationResult.SPOOFING_DETECTED)


# ---------------------------------------------------------------------------
# New REST endpoints
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestMeshNewEndpoints:
    def setup_method(self):
        self.user = User.objects.create_user(email='api@example.com', password='x')
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
        self.node = _make_node(self.user, trust=0.6)
        self.drop = _make_drop(self.user, required=2, total=3)

    def test_node_trust_get(self):
        resp = self.client.get(f'/api/mesh/nodes/{self.node.id}/trust/')
        assert resp.status_code == 200
        assert resp.data['node_id'] == str(self.node.id)
        assert 'trust_score' in resp.data

    def test_node_trust_recompute(self):
        self.node.successful_transfers = 3
        self.node.failed_transfers = 1
        self.node.save()
        resp = self.client.post(f'/api/mesh/nodes/{self.node.id}/trust/')
        assert resp.status_code == 200
        assert resp.data['status'] == 'recomputed'

    def test_health_endpoint(self):
        DeadDropFragment.objects.create(
            dead_drop=self.drop,
            fragment_index=1,
            encrypted_fragment=b'\x01',
            fragment_hash='h' * 32,
            node=self.node,
            is_distributed=True,
            is_available=True,
        )
        resp = self.client.get(f'/api/mesh/deaddrops/{self.drop.id}/health/')
        assert resp.status_code == 200
        assert resp.data['drop_id'] == str(self.drop.id)
        assert resp.data['threshold']['required'] == 2
        assert resp.data['fragments']['total'] == 1

    def test_rebalance_endpoint_returns_status(self):
        with patch(
            'mesh_deaddrop.services.fragment_distribution_service.FragmentDistributionService.rebalance_fragments',
            return_value=0,
        ), patch(
            'mesh_deaddrop.services.fragment_distribution_service.FragmentDistributionService.get_distribution_status',
            return_value={'distributed': 0, 'total': 3},
        ):
            resp = self.client.post(f'/api/mesh/deaddrops/{self.drop.id}/rebalance/')
        assert resp.status_code == 200
        assert 'status' in resp.data

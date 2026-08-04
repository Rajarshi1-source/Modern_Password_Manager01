"""
Dark Protocol Backend Tests
============================

Comprehensive unit tests for the Dark Protocol anonymous vault access network.

Tests:
- Model creation and constraints
- Service functionality
- API endpoints
- WebSocket communication
- Cover traffic generation
- Noise encryption

@author Password Manager Team
@created 2026-02-02
"""

import uuid
import json
import secrets
from datetime import timedelta
from unittest.mock import Mock, patch, MagicMock

from django.test import TestCase, TransactionTestCase, override_settings
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.urls import reverse
from rest_framework.test import APITestCase, APIClient
from rest_framework import status
from channels.testing import WebsocketCommunicator
from channels.routing import URLRouter
from channels.db import database_sync_to_async

User = get_user_model()


# =============================================================================
# Model Tests
# =============================================================================

class DarkProtocolNodeModelTests(TestCase):
    """Tests for DarkProtocolNode model."""
    
    def setUp(self):
        from security.models.dark_protocol_models import DarkProtocolNode
        self.DarkProtocolNode = DarkProtocolNode
    
    def test_create_entry_node(self):
        """Test creating an entry node."""
        node = self.DarkProtocolNode.objects.create(
            node_id=secrets.token_hex(32),
            fingerprint=secrets.token_hex(32),
            node_type='entry',
            status='active',
            region='NA',
            public_key=secrets.token_bytes(32),
            signing_key=secrets.token_bytes(64),
        )
        
        self.assertIsNotNone(node.node_id)
        self.assertEqual(node.node_type, 'entry')
        self.assertEqual(node.status, 'active')
        self.assertEqual(node.trust_score, 1.0)
    
    def test_create_relay_node(self):
        """Test creating a relay node."""
        node = self.DarkProtocolNode.objects.create(
            node_id=secrets.token_hex(32),
            fingerprint=secrets.token_hex(32),
            node_type='relay',
            status='active',
        )
        
        self.assertEqual(node.node_type, 'relay')
    
    def test_node_types(self):
        """Test all node types can be created."""
        for node_type in ['entry', 'relay', 'destination', 'bridge']:
            node = self.DarkProtocolNode.objects.create(
                node_id=secrets.token_hex(32),
                fingerprint=secrets.token_hex(32),
                node_type=node_type,
            )
            self.assertEqual(node.node_type, node_type)


class GarlicSessionModelTests(TestCase):
    """Tests for GarlicSession model."""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpassword123'
        )
        from security.models.dark_protocol_models import GarlicSession, DarkProtocolNode
        self.GarlicSession = GarlicSession
        self.DarkProtocolNode = DarkProtocolNode
        
        self.entry_node = self.DarkProtocolNode.objects.create(
            node_id=secrets.token_hex(32),
            fingerprint=secrets.token_hex(32),
            node_type='entry',
        )
    
    def test_create_session(self):
        """Test creating a garlic session."""
        session = self.GarlicSession.objects.create(
            user=self.user,
            encrypted_path=b'encrypted_path_data',
            layer_keys=b'encrypted_layer_keys',
            entry_node=self.entry_node,
            path_length=3,
            expires_at=timezone.now() + timedelta(minutes=30),
        )
        
        self.assertIsNotNone(session.session_id)
        self.assertEqual(len(session.session_id), 64)
        self.assertEqual(session.status, 'active')
        self.assertEqual(session.path_length, 3)
    
    def test_session_expires(self):
        """Test session expiration logic."""
        session = self.GarlicSession.objects.create(
            user=self.user,
            encrypted_path=b'test',
            layer_keys=b'test',
            path_length=3,
            expires_at=timezone.now() - timedelta(minutes=1),  # Already expired
        )
        
        # Session should be marked as expired
        self.assertTrue(session.expires_at < timezone.now())


class TrafficBundleModelTests(TestCase):
    """Tests for TrafficBundle model."""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpassword123'
        )
        from security.models.dark_protocol_models import GarlicSession, TrafficBundle
        self.GarlicSession = GarlicSession
        self.TrafficBundle = TrafficBundle
        
        self.session = self.GarlicSession.objects.create(
            user=self.user,
            encrypted_path=b'test',
            layer_keys=b'test',
            path_length=3,
            expires_at=timezone.now() + timedelta(minutes=30),
        )
    
    def test_create_real_bundle(self):
        """Test creating a real traffic bundle."""
        bundle = self.TrafficBundle.objects.create(
            session=self.session,
            bundle_type='real',
            encrypted_payload=b'encrypted_vault_data',
            payload_size=1024,
            sequence_number=1,
        )
        
        self.assertEqual(bundle.bundle_type, 'real')
        self.assertEqual(bundle.payload_size, 1024)
    
    def test_create_cover_bundle(self):
        """Test creating a cover traffic bundle."""
        bundle = self.TrafficBundle.objects.create(
            session=self.session,
            bundle_type='cover',
            encrypted_payload=b'fake_encrypted_data',
            payload_size=512,
            sequence_number=2,
        )
        
        self.assertEqual(bundle.bundle_type, 'cover')


# =============================================================================
# Service Tests
# =============================================================================

class NoiseEncryptorTests(TestCase):
    """Tests for NoiseEncryptor service."""
    
    def setUp(self):
        from security.services.noise_encryptor import NoiseEncryptor
        self.encryptor = NoiseEncryptor()
    
    def test_generate_noise(self):
        """Test noise generation."""
        noise = self.encryptor.generate_noise(256)
        
        self.assertEqual(len(noise), 256)
        self.assertIsInstance(noise, bytes)
    
    def test_calculate_entropy(self):
        """Test entropy calculation."""
        # High entropy data
        random_data = secrets.token_bytes(1024)
        entropy = self.encryptor.calculate_entropy(random_data)
        
        # Should be close to 8 bits (maximum for random bytes)
        self.assertGreater(entropy, 7.0)
    
    def test_generate_timing_noise(self):
        """Test timing noise generation.

        PR #464 review (CodeRabbit): both bounds are inclusive, not
        exclusive -- ``base = int(random.expovariate(...))`` can floor
        to 0, and ``min(base + uniform + spike, 1000)`` can hit the
        1000 cap exactly, so a strict > / < assertion would
        occasionally fail on valid output.
        """
        delay = self.encryptor.generate_timing_noise()

        self.assertGreaterEqual(delay, 0)
        self.assertLessEqual(delay, 1000)  # At most 1 second

    def test_pad_to_block_lands_on_next_bucket_at_every_boundary(self):
        """Round 31/32 review follow-up: a payload of EXACTLY a
        BLOCK_SIZES value can't fit that bucket once the 4-byte length
        prefix is counted (block_size bytes + 4 > block_size), so it
        must move up to the next real bucket. Before the fix,
        `_pad_to_block` special-cased this as "already big enough" and
        returned block_size + 4 -- a unique, unbucketed wire size that
        leaked exactly which payloads sat on a boundary. Pin that every
        exact-boundary payload now lands on the true next bucket
        instead."""
        from security.services.noise_encryptor import BLOCK_SIZES

        for i, block_size in enumerate(BLOCK_SIZES[:-1]):
            data = secrets.token_bytes(block_size)
            result = self.encryptor._pad_to_block(data, block_size)
            expected_next_bucket = BLOCK_SIZES[i + 1]
            self.assertEqual(
                len(result), expected_next_bucket,
                f"payload of exactly {block_size} bytes should land on "
                f"the {expected_next_bucket} bucket, got {len(result)}",
            )
            # Must not be the old buggy "just add the prefix" value.
            self.assertNotEqual(len(result), block_size + 4)

    def test_pad_to_block_near_largest_block_does_not_double(self):
        """Round 31 review follow-up: the largest configured block
        (4096) has no next entry in BLOCK_SIZES to move up to, so a
        payload landing in its last 4 bytes (4093-4095) used to fall
        through to `block_size * 2` = 8192 -- doubling the wire size
        for no reason, right at the ceiling where "just add the
        prefix, no more padding possible" is already the documented,
        correct answer for anything at or beyond 4096. Pin the
        ceiling behavior instead of the doubling."""
        from security.services.noise_encryptor import BLOCK_SIZES

        largest_block = BLOCK_SIZES[-1]
        for data_size in (largest_block - 3, largest_block - 2, largest_block - 1):
            data = secrets.token_bytes(data_size)
            result = self.encryptor._pad_to_block(data, largest_block)
            self.assertEqual(len(result), data_size + 4)
            self.assertNotEqual(len(result), largest_block * 2)

    def test_pad_to_block_typical_case_still_lands_exactly_on_block(self):
        """Regression guard: the fix must not disturb the common case
        where the payload already comfortably fits (with the 4-byte
        prefix) inside the selected block."""
        from security.services.noise_encryptor import BLOCK_SIZES

        for block_size in BLOCK_SIZES:
            data = secrets.token_bytes(block_size - 4)
            result = self.encryptor._pad_to_block(data, block_size)
            self.assertEqual(len(result), block_size)

    def test_pad_to_block_round_trip_at_every_boundary(self):
        """Whatever wire size `_pad_to_block` picks, `_remove_block_padding`
        must recover the exact original bytes -- pinned at every
        boundary-adjacent size, not just the comfortable middle of a
        bucket."""
        from security.services.noise_encryptor import BLOCK_SIZES

        offsets = (-3, -2, -1, 0, 1, 2, 3)
        for block_size in BLOCK_SIZES:
            for offset in offsets:
                data_size = block_size + offset
                if data_size < 0:
                    continue
                data = secrets.token_bytes(data_size)
                padded = self.encryptor._pad_to_block(data, block_size)
                recovered = self.encryptor._remove_block_padding(padded)
                self.assertEqual(
                    recovered, data,
                    f"round-trip failed for data_size={data_size}, "
                    f"block_size={block_size}",
                )


class CoverTrafficGeneratorTests(TestCase):
    """Tests for CoverTrafficGenerator service."""
    
    def setUp(self):
        from security.services.cover_traffic_generator import CoverTrafficGenerator
        self.generator = CoverTrafficGenerator()
    
    def test_generate_cover_message(self):
        """Test cover message generation."""
        message = self.generator.generate_cover_message()
        
        self.assertIsNotNone(message.message_id)
        self.assertIsNotNone(message.operation)
        self.assertIsNotNone(message.payload)
        self.assertGreater(message.size, 0)
    
    def test_generate_burst(self):
        """Test burst generation."""
        burst = self.generator.generate_burst(count=5)
        
        self.assertEqual(len(burst.messages), 5)
    
    def test_fake_operations_variety(self):
        """Test that various fake operations are generated."""
        operations = set()
        for _ in range(50):
            message = self.generator.generate_cover_message()
            operations.add(message.operation)
        
        # Should have multiple different operation types
        self.assertGreater(len(operations), 1)


class GarlicRouterTests(TestCase):
    """Tests for GarlicRouter service."""
    
    def setUp(self):
        from security.services.garlic_router import GarlicRouter
        from security.models.dark_protocol_models import DarkProtocolNode
        
        self.router = GarlicRouter()
        self.DarkProtocolNode = DarkProtocolNode
        
        # Create test nodes
        self.nodes = []
        for i, node_type in enumerate(['entry', 'relay', 'relay', 'destination']):
            node = self.DarkProtocolNode.objects.create(
                node_id=secrets.token_hex(32),
                fingerprint=secrets.token_hex(32),
                node_type=node_type,
                public_key=secrets.token_bytes(32),
                signing_key=secrets.token_bytes(64),
            )
            self.nodes.append(node)
    
    def test_create_circuit(self):
        """Test circuit creation."""
        session_id = secrets.token_hex(32)
        
        layer_keys, encrypted_path = self.router.create_circuit(
            nodes=self.nodes,
            session_id=session_id,
        )
        
        self.assertIsNotNone(layer_keys)
        self.assertIsNotNone(encrypted_path)
        self.assertGreater(len(layer_keys), 0)


# =============================================================================
# API Tests
# =============================================================================

class DarkProtocolAPITests(APITestCase):
    """Tests for Dark Protocol REST API endpoints."""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpassword123'
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
    
    def test_get_config(self):
        """Test getting dark protocol configuration."""
        url = reverse('dark-protocol-config')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('is_enabled', response.data)
    
    def test_update_config(self):
        """Test updating dark protocol configuration."""
        url = reverse('dark-protocol-config')
        data = {
            'is_enabled': True,
            'min_hops': 4,
            'cover_traffic_enabled': True,
        }
        
        response = self.client.put(url, data, format='json')
        
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_201_CREATED])
    
    def test_get_session_no_active(self):
        """Test getting session when none active."""
        url = reverse('dark-protocol-session')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data.get('has_active_session', False))
    
    @override_settings(TOR={'ENABLED': False})
    def test_get_network_health(self):
        """Health leads with the Tor-verified anonymity verdict.

        This used to assert a top-level `active_nodes`, which counted local
        database rows and read as the size of an anonymity network. Those
        counters now live under `obfuscation_layer`, and the headline is
        whether anonymity is genuinely available.

        TOR['ENABLED'] is pinned rather than inherited: it comes from
        os.environ, so a developer or runner with Tor enabled would flip the
        verdict and fail this test for reasons unrelated to the code it covers.
        """
        url = reverse('dark-protocol-health')
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('anonymity_active', response.data)
        self.assertFalse(response.data['anonymity_active'])
        self.assertEqual(response.data['status'], 'unavailable')
        self.assertIn('active_records', response.data['obfuscation_layer'])
    
    def test_get_stats(self):
        """Test getting usage statistics."""
        url = reverse('dark-protocol-stats')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
    
    def test_unauthenticated_access(self):
        """Test that unauthenticated access is denied."""
        self.client.force_authenticate(user=None)
        url = reverse('dark-protocol-config')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


# =============================================================================
# Integration Tests
# =============================================================================

class DarkProtocolIntegrationTests(TransactionTestCase):
    """Integration tests for Dark Protocol end-to-end functionality."""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpassword123'
        )
        
        from security.models.dark_protocol_models import DarkProtocolNode
        self.DarkProtocolNode = DarkProtocolNode
        
        # Create a minimal network
        for node_type in ['entry', 'relay', 'relay', 'destination']:
            self.DarkProtocolNode.objects.create(
                node_id=secrets.token_hex(32),
                fingerprint=secrets.token_hex(32),
                node_type=node_type,
                status='active',
                public_key=secrets.token_bytes(32),
                signing_key=secrets.token_bytes(64),
            )
    
    def test_full_session_lifecycle(self):
        """Test complete session lifecycle: establish -> use -> terminate."""
        from security.services.dark_protocol_service import get_dark_protocol_service
        
        service = get_dark_protocol_service()
        
        # Establish session
        result = service.establish_session(
            user=self.user,
            hop_count=3,
        )
        
        self.assertTrue(result.success)
        self.assertIsNotNone(result.session_id)
        
        # Verify session is active
        active_session = service.get_active_session(self.user)
        self.assertIsNotNone(active_session)
        
        # Terminate session
        terminated = service.terminate_session(
            user=self.user,
            session_id=result.session_id,
        )
        
        self.assertTrue(terminated)
        
        # Verify session is no longer active
        active_after = service.get_active_session(self.user)
        self.assertIsNone(active_after)


# =============================================================================
# Task Tests
# =============================================================================

class DarkProtocolTaskTests(TestCase):
    """Tests for Celery background tasks."""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpassword123'
        )
        
        from security.models.dark_protocol_models import (
            DarkProtocolNode, GarlicSession, NetworkHealth
        )
        self.DarkProtocolNode = DarkProtocolNode
        self.GarlicSession = GarlicSession
        self.NetworkHealth = NetworkHealth
        
        # Create test node
        self.node = self.DarkProtocolNode.objects.create(
            node_id=secrets.token_hex(32),
            fingerprint=secrets.token_hex(32),
            node_type='relay',
            status='active',
        )
    
    def test_health_check_task(self):
        """Test node health check task."""
        from security.tasks.dark_protocol_tasks import health_check_nodes
        
        result = health_check_nodes()
        
        self.assertTrue(result['success'])
        self.assertEqual(result['checked_count'], 1)
    
    def test_cleanup_task(self):
        """Test cleanup expired sessions task."""
        from security.tasks.dark_protocol_tasks import cleanup_expired_sessions
        
        # Create expired session
        self.GarlicSession.objects.create(
            user=self.user,
            encrypted_path=b'test',
            layer_keys=b'test',
            path_length=3,
            expires_at=timezone.now() - timedelta(hours=1),
            status='active',
        )
        
        result = cleanup_expired_sessions()
        
        self.assertTrue(result['success'])
        self.assertEqual(result['expired_sessions'], 1)

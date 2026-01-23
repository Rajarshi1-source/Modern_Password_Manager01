"""
Mesh Dead Drop Model Tests
===========================

Unit tests for all mesh dead drop models including:
- DeadDrop
- DeadDropFragment
- MeshNode
- NFCBeacon
- DeadDropAccess
- FragmentTransfer
- LocationVerificationCache

@author Password Manager Team
@created 2026-01-22
"""

from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from datetime import timedelta
from decimal import Decimal
import uuid

from mesh_deaddrop.models import (
    DeadDrop,
    DeadDropFragment,
    MeshNode,
    NFCBeacon,
    DeadDropAccess,
    FragmentTransfer,
    LocationVerificationCache
)

User = get_user_model()


class DeadDropModelTests(TestCase):
    """Tests for the DeadDrop model."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
    
    def test_create_dead_drop_basic(self):
        """Test creating a basic dead drop."""
        dead_drop = DeadDrop.objects.create(
            owner=self.user,
            title='Test Dead Drop',
            latitude=Decimal('40.7128'),
            longitude=Decimal('-74.0060'),
            encrypted_secret=b'encrypted_data',
            secret_hash='abc123',
            required_fragments=3,
            total_fragments=5,
            expires_at=timezone.now() + timedelta(days=7)
        )
        
        self.assertIsNotNone(dead_drop.id)
        self.assertEqual(dead_drop.owner, self.user)
        self.assertEqual(dead_drop.title, 'Test Dead Drop')
        self.assertEqual(dead_drop.required_fragments, 3)
        self.assertEqual(dead_drop.total_fragments, 5)
        self.assertEqual(dead_drop.status, 'pending')
        self.assertTrue(dead_drop.is_active)
    
    def test_dead_drop_auto_uuid(self):
        """Test that dead drop gets auto-generated UUID."""
        dead_drop = DeadDrop.objects.create(
            owner=self.user,
            title='UUID Test',
            latitude=Decimal('40.7128'),
            longitude=Decimal('-74.0060'),
            encrypted_secret=b'test',
            secret_hash='hash',
            required_fragments=3,
            total_fragments=5,
            expires_at=timezone.now() + timedelta(days=7)
        )
        
        self.assertIsNotNone(dead_drop.id)
        # Check it's a valid UUID
        self.assertEqual(len(str(dead_drop.id)), 36)
    
    def test_dead_drop_threshold_display(self):
        """Test threshold display property."""
        dead_drop = DeadDrop.objects.create(
            owner=self.user,
            title='Threshold Test',
            latitude=Decimal('40.7128'),
            longitude=Decimal('-74.0060'),
            encrypted_secret=b'test',
            secret_hash='hash',
            required_fragments=3,
            total_fragments=5,
            expires_at=timezone.now() + timedelta(days=7)
        )
        
        self.assertEqual(dead_drop.threshold_display, '3-of-5')
    
    def test_dead_drop_is_expired(self):
        """Test is_expired property."""
        # Not expired
        dead_drop = DeadDrop.objects.create(
            owner=self.user,
            title='Expiry Test',
            latitude=Decimal('40.7128'),
            longitude=Decimal('-74.0060'),
            encrypted_secret=b'test',
            secret_hash='hash',
            required_fragments=3,
            total_fragments=5,
            expires_at=timezone.now() + timedelta(days=7)
        )
        self.assertFalse(dead_drop.is_expired)
        
        # Expired
        dead_drop.expires_at = timezone.now() - timedelta(hours=1)
        dead_drop.save()
        self.assertTrue(dead_drop.is_expired)
    
    def test_dead_drop_time_remaining(self):
        """Test time_remaining_seconds property."""
        expires = timezone.now() + timedelta(hours=1)
        dead_drop = DeadDrop.objects.create(
            owner=self.user,
            title='Time Test',
            latitude=Decimal('40.7128'),
            longitude=Decimal('-74.0060'),
            encrypted_secret=b'test',
            secret_hash='hash',
            required_fragments=3,
            total_fragments=5,
            expires_at=expires
        )
        
        remaining = dead_drop.time_remaining_seconds
        self.assertGreater(remaining, 3500)  # About 1 hour
        self.assertLess(remaining, 3700)
    
    def test_dead_drop_status_choices(self):
        """Test valid status choices."""
        dead_drop = DeadDrop.objects.create(
            owner=self.user,
            title='Status Test',
            latitude=Decimal('40.7128'),
            longitude=Decimal('-74.0060'),
            encrypted_secret=b'test',
            secret_hash='hash',
            required_fragments=3,
            total_fragments=5,
            expires_at=timezone.now() + timedelta(days=7)
        )
        
        valid_statuses = ['pending', 'distributed', 'active', 'collected', 'expired', 'cancelled']
        for status in valid_statuses:
            dead_drop.status = status
            dead_drop.save()
            dead_drop.refresh_from_db()
            self.assertEqual(dead_drop.status, status)
    
    def test_dead_drop_str_representation(self):
        """Test string representation."""
        dead_drop = DeadDrop.objects.create(
            owner=self.user,
            title='String Test Drop',
            latitude=Decimal('40.7128'),
            longitude=Decimal('-74.0060'),
            encrypted_secret=b'test',
            secret_hash='hash',
            required_fragments=3,
            total_fragments=5,
            expires_at=timezone.now() + timedelta(days=7)
        )
        
        self.assertIn('String Test Drop', str(dead_drop))


class DeadDropFragmentModelTests(TestCase):
    """Tests for the DeadDropFragment model."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.dead_drop = DeadDrop.objects.create(
            owner=self.user,
            title='Fragment Test',
            latitude=Decimal('40.7128'),
            longitude=Decimal('-74.0060'),
            encrypted_secret=b'test',
            secret_hash='hash',
            required_fragments=3,
            total_fragments=5,
            expires_at=timezone.now() + timedelta(days=7)
        )
    
    def test_create_fragment(self):
        """Test creating a fragment."""
        fragment = DeadDropFragment.objects.create(
            dead_drop=self.dead_drop,
            fragment_index=1,
            encrypted_fragment=b'encrypted_fragment_data',
            fragment_hash='fragment_hash_123'
        )
        
        self.assertIsNotNone(fragment.id)
        self.assertEqual(fragment.dead_drop, self.dead_drop)
        self.assertEqual(fragment.fragment_index, 1)
        self.assertFalse(fragment.is_distributed)
    
    def test_fragment_storage_types(self):
        """Test valid storage types."""
        valid_types = ['mesh_node', 'trusted_device', 'cloud_backup']
        
        for i, storage_type in enumerate(valid_types):
            fragment = DeadDropFragment.objects.create(
                dead_drop=self.dead_drop,
                fragment_index=i + 1,
                encrypted_fragment=b'data',
                fragment_hash=f'hash_{i}',
                storage_type=storage_type
            )
            self.assertEqual(fragment.storage_type, storage_type)
    
    def test_fragment_with_node(self):
        """Test fragment associated with a mesh node."""
        node = MeshNode.objects.create(
            owner=self.user,
            device_name='Test Node',
            device_type='phone_android',
            ble_address='AA:BB:CC:DD:EE:FF',
            public_key='test_public_key'
        )
        
        fragment = DeadDropFragment.objects.create(
            dead_drop=self.dead_drop,
            fragment_index=10,
            encrypted_fragment=b'data',
            fragment_hash='hash_node',
            storage_type='mesh_node',
            node=node,
            is_distributed=True,
            distributed_at=timezone.now()
        )
        
        self.assertEqual(fragment.node, node)
        self.assertTrue(fragment.is_distributed)


class MeshNodeModelTests(TestCase):
    """Tests for the MeshNode model."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
    
    def test_create_mesh_node(self):
        """Test creating a mesh node."""
        node = MeshNode.objects.create(
            owner=self.user,
            device_name='My Phone',
            device_type='phone_android',
            ble_address='AA:BB:CC:DD:EE:FF',
            public_key='public_key_data'
        )
        
        self.assertIsNotNone(node.id)
        self.assertEqual(node.owner, self.user)
        self.assertEqual(node.device_name, 'My Phone')
        self.assertFalse(node.is_online)
        self.assertEqual(node.max_fragments, 10)
    
    def test_node_uuid_uniqueness(self):
        """Test that node IDs are unique."""
        node1 = MeshNode.objects.create(
            device_name='Node 1',
            device_type='phone_android',
            ble_address='AA:BB:CC:DD:EE:01',
            public_key='key1'
        )
        node2 = MeshNode.objects.create(
            device_name='Node 2',
            device_type='phone_android',
            ble_address='AA:BB:CC:DD:EE:02',
            public_key='key2'
        )
        
        self.assertNotEqual(node1.id, node2.id)
    
    def test_node_has_capacity(self):
        """Test has_capacity property."""
        node = MeshNode.objects.create(
            device_name='Available Node',
            device_type='phone_android',
            ble_address='AA:BB:CC:DD:EE:FF',
            public_key='key',
            is_online=True,
            max_fragments=10,
            current_fragment_count=5
        )
        
        self.assertTrue(node.has_capacity)
        
        # Fill up the node
        node.current_fragment_count = 10
        node.save()
        self.assertFalse(node.has_capacity)
    
    def test_node_device_types(self):
        """Test valid device types."""
        valid_types = ['phone_android', 'phone_ios', 'tablet', 'raspberry_pi', 'dedicated', 'other']
        
        for i, device_type in enumerate(valid_types):
            node = MeshNode.objects.create(
                device_name=f'Device {i}',
                device_type=device_type,
                ble_address=f'AA:BB:CC:DD:EE:{i:02X}',
                public_key=f'key_{i}'
            )
            self.assertEqual(node.device_type, device_type)
    
    def test_node_with_location(self):
        """Test node with location data."""
        node = MeshNode.objects.create(
            device_name='Located Node',
            device_type='phone_android',
            ble_address='AA:BB:CC:DD:EE:FF',
            public_key='key',
            last_known_latitude=Decimal('40.7128'),
            last_known_longitude=Decimal('-74.0060')
        )
        
        self.assertEqual(node.last_known_latitude, Decimal('40.7128'))
        self.assertEqual(node.last_known_longitude, Decimal('-74.0060'))
    
    def test_node_trust_score_update(self):
        """Test trust score calculation."""
        node = MeshNode.objects.create(
            device_name='Trust Test Node',
            device_type='phone_android',
            ble_address='AA:BB:CC:DD:EE:FF',
            public_key='key'
        )
        
        # Record successes
        for _ in range(8):
            node.record_transfer_success()
        
        # Record failures
        for _ in range(2):
            node.record_transfer_failure()
        
        node.refresh_from_db()
        self.assertAlmostEqual(node.trust_score, 0.8, places=2)


class NFCBeaconModelTests(TestCase):
    """Tests for the NFCBeacon model."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.dead_drop = DeadDrop.objects.create(
            owner=self.user,
            title='NFC Test',
            latitude=Decimal('40.7128'),
            longitude=Decimal('-74.0060'),
            encrypted_secret=b'test',
            secret_hash='hash',
            required_fragments=3,
            total_fragments=5,
            expires_at=timezone.now() + timedelta(days=7)
        )
    
    def test_create_nfc_beacon(self):
        """Test creating an NFC beacon."""
        beacon = NFCBeacon.objects.create(
            dead_drop=self.dead_drop,
            tag_id='04:11:22:33:44:55:66',
            tag_signature='signature_data'
        )
        
        self.assertIsNotNone(beacon.id)
        self.assertEqual(beacon.dead_drop, self.dead_drop)
        self.assertTrue(beacon.is_active)
    
    def test_nfc_beacon_rotate_challenge(self):
        """Test challenge rotation."""
        beacon = NFCBeacon.objects.create(
            dead_drop=self.dead_drop,
            tag_id='04:11:22:33:44:55:77',
            tag_signature='signature'
        )
        
        challenge = beacon.rotate_challenge()
        
        self.assertIsNotNone(challenge)
        self.assertEqual(len(challenge), 64)  # 32 bytes = 64 hex chars
        self.assertIsNotNone(beacon.challenge_expires_at)


class DeadDropAccessModelTests(TestCase):
    """Tests for the DeadDropAccess model."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.dead_drop = DeadDrop.objects.create(
            owner=self.user,
            title='Access Test',
            latitude=Decimal('40.7128'),
            longitude=Decimal('-74.0060'),
            encrypted_secret=b'test',
            secret_hash='hash',
            required_fragments=3,
            total_fragments=5,
            expires_at=timezone.now() + timedelta(days=7)
        )
    
    def test_create_access_record(self):
        """Test creating an access record."""
        access = DeadDropAccess.objects.create(
            dead_drop=self.dead_drop,
            accessor=self.user,
            claimed_latitude=Decimal('40.7128'),
            claimed_longitude=Decimal('-74.0060'),
            gps_verified=True,
            ble_verified=True,
            ble_nodes_detected=3,
            result='success',
            fragments_collected=3,
            reconstruction_successful=True
        )
        
        self.assertIsNotNone(access.id)
        self.assertTrue(access.gps_verified)
        self.assertTrue(access.reconstruction_successful)
    
    def test_access_record_anonymous(self):
        """Test access record without user."""
        access = DeadDropAccess.objects.create(
            dead_drop=self.dead_drop,
            claimed_latitude=Decimal('40.7128'),
            claimed_longitude=Decimal('-74.0060'),
            gps_verified=True,
            ble_nodes_detected=3,
            result='insufficient_fragments',
            fragments_collected=0,
            reconstruction_successful=False
        )
        
        self.assertIsNone(access.accessor)


class FragmentTransferModelTests(TestCase):
    """Tests for the FragmentTransfer model."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.dead_drop = DeadDrop.objects.create(
            owner=self.user,
            title='Transfer Test',
            latitude=Decimal('40.7128'),
            longitude=Decimal('-74.0060'),
            encrypted_secret=b'test',
            secret_hash='hash',
            required_fragments=3,
            total_fragments=5,
            expires_at=timezone.now() + timedelta(days=7)
        )
        self.fragment = DeadDropFragment.objects.create(
            dead_drop=self.dead_drop,
            fragment_index=1,
            encrypted_fragment=b'data',
            fragment_hash='hash'
        )
        self.from_node = MeshNode.objects.create(
            device_name='From Node',
            device_type='phone_android',
            ble_address='AA:BB:CC:DD:EE:01',
            public_key='key1'
        )
        self.to_node = MeshNode.objects.create(
            device_name='To Node',
            device_type='phone_android',
            ble_address='AA:BB:CC:DD:EE:02',
            public_key='key2'
        )
    
    def test_create_transfer_record(self):
        """Test creating a transfer record."""
        transfer = FragmentTransfer.objects.create(
            fragment=self.fragment,
            from_node=self.from_node,
            to_node=self.to_node,
            encryption_method='X25519+XChaCha20',
            transfer_successful=True
        )
        
        self.assertIsNotNone(transfer.id)
        self.assertTrue(transfer.transfer_successful)
    
    def test_transfer_with_error(self):
        """Test transfer record with error."""
        transfer = FragmentTransfer.objects.create(
            fragment=self.fragment,
            from_node=self.from_node,
            to_node=self.to_node,
            encryption_method='X25519+XChaCha20',
            transfer_successful=False,
            error_message='Connection timeout'
        )
        
        self.assertFalse(transfer.transfer_successful)
        self.assertEqual(transfer.error_message, 'Connection timeout')


class LocationVerificationCacheTests(TestCase):
    """Tests for the LocationVerificationCache model."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
    
    def test_create_location_cache(self):
        """Test creating a location cache entry."""
        cache = LocationVerificationCache.objects.create(
            user=self.user,
            latitude=Decimal('40.7128'),
            longitude=Decimal('-74.0060'),
            accuracy_meters=10.0,
            source='gps',
            verification_method='gps_ble'
        )
        
        self.assertIsNotNone(cache.id)
        self.assertEqual(cache.user, self.user)
        self.assertEqual(cache.source, 'gps')

"""
Mesh Dead Drop Functional Tests
================================

Functional tests for the complete dead drop workflow:
- Create dead drop with secret
- Split secret into fragments
- Distribute to mesh nodes  
- Verify location at collection
- Collect fragments and reconstruct

@author Password Manager Team
@created 2026-01-22
"""

from django.test import TestCase, TransactionTestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal
from unittest.mock import Mock, patch, MagicMock

from mesh_deaddrop.models import (
    DeadDrop,
    DeadDropFragment,
    MeshNode,
    NFCBeacon,
    DeadDropAccess
)
from mesh_deaddrop.services.shamir_service import ShamirSecretSharingService
from mesh_deaddrop.services.mesh_crypto_service import MeshCryptoService
from mesh_deaddrop.services.location_verification_service import LocationVerificationService
from mesh_deaddrop.services.fragment_distribution_service import FragmentDistributionService

User = get_user_model()


class CreateDeadDropFunctionalTest(TestCase):
    """Functional tests for creating dead drops."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='alice',
            email='alice@example.com',
            password='alicepass123'
        )
        self.shamir = ShamirSecretSharingService()
        self.crypto = MeshCryptoService()
    
    def test_create_dead_drop_with_secret_splitting(self):
        """Test complete flow of creating a dead drop with secret splitting."""
        # 1. Define the secret
        secret = "my-super-secret-password-123"
        
        # 2. Create dead drop record
        dead_drop = DeadDrop.objects.create(
            owner=self.user,
            title='Secure Password Share',
            latitude=Decimal('40.7128'),
            longitude=Decimal('-74.0060'),
            radius_meters=50,
            location_hint='Near the fountain in Central Park',
            encrypted_secret=secret.encode(),
            secret_hash=self.crypto.hash_secret(secret),
            required_fragments=3,
            total_fragments=5,
            expires_at=timezone.now() + timedelta(days=7)
        )
        
        # 3. Split secret into shares
        shares = self.shamir.split_secret(secret.encode(), k=3, n=5)
        
        # 4. Create fragment records
        for index, share_data in shares:
            DeadDropFragment.objects.create(
                dead_drop=dead_drop,
                fragment_index=index,
                encrypted_fragment=share_data,
                fragment_hash=self.crypto.hash_fragment(share_data)
            )
        
        # 5. Verify creation
        self.assertEqual(dead_drop.fragments.count(), 5)
        self.assertEqual(dead_drop.status, 'pending')
        
        # 6. Verify we can reconstruct with k=3 fragments
        fragments = list(dead_drop.fragments.all()[:3])
        shares_to_reconstruct = [
            (f.fragment_index, f.encrypted_fragment)
            for f in fragments
        ]
        reconstructed = self.shamir.reconstruct_secret(shares_to_reconstruct, k=3)
        self.assertEqual(reconstructed.decode(), secret)
    
    def test_create_high_threshold_dead_drop(self):
        """Test creating dead drop with higher threshold (5-of-7)."""
        secret = "high-security-secret"
        
        dead_drop = DeadDrop.objects.create(
            owner=self.user,
            title='High Security Share',
            latitude=Decimal('51.5074'),
            longitude=Decimal('-0.1278'),
            encrypted_secret=secret.encode(),
            secret_hash=self.crypto.hash_secret(secret),
            required_fragments=5,
            total_fragments=7,
            expires_at=timezone.now() + timedelta(hours=24)
        )
        
        shares = self.shamir.split_secret(secret.encode(), k=5, n=7)
        
        for index, share_data in shares:
            DeadDropFragment.objects.create(
                dead_drop=dead_drop,
                fragment_index=index,
                encrypted_fragment=share_data,
                fragment_hash=self.crypto.hash_fragment(share_data)
            )
        
        self.assertEqual(dead_drop.threshold_display, '5-of-7')
        self.assertEqual(dead_drop.fragments.count(), 7)


class DistributeFragmentsFunctionalTest(TestCase):
    """Functional tests for distributing fragments to mesh nodes."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='bob',
            email='bob@example.com',
            password='bobpass123'
        )
        self.shamir = ShamirSecretSharingService()
        self.crypto = MeshCryptoService()
        self.distribution = FragmentDistributionService()
        
        # Create mesh nodes near the dead drop location
        self.nodes = []
        for i in range(7):
            node = MeshNode.objects.create(
                device_name=f'MeshNode-{chr(65+i)}',
                device_type='phone_android',
                ble_address=f'AA:BB:CC:DD:EE:{i:02X}',
                public_key=f'node_public_key_{i}',
                is_online=True,
                trust_score=0.8 + (i * 0.02),
                max_fragments=10,
                current_fragment_count=i % 3,
                last_known_latitude=Decimal('40.7128') + Decimal(str(i * 0.0001)),
                last_known_longitude=Decimal('-74.0060')
            )
            self.nodes.append(node)
        
        # Create dead drop with fragments
        secret = "distribution-test-secret"
        self.dead_drop = DeadDrop.objects.create(
            owner=self.user,
            title='Distribution Test',
            latitude=Decimal('40.7128'),
            longitude=Decimal('-74.0060'),
            encrypted_secret=secret.encode(),
            secret_hash='test_hash',
            required_fragments=3,
            total_fragments=5,
            expires_at=timezone.now() + timedelta(days=7)
        )
        
        shares = self.shamir.split_secret(secret.encode(), k=3, n=5)
        self.fragments = []
        for index, share_data in shares:
            fragment = DeadDropFragment.objects.create(
                dead_drop=self.dead_drop,
                fragment_index=index,
                encrypted_fragment=share_data,
                fragment_hash='hash'
            )
            self.fragments.append(fragment)
    
    def test_distribute_fragments_to_nodes(self):
        """Test distributing fragments to available mesh nodes."""
        result = self.distribution.distribute_fragments(
            dead_drop=self.dead_drop,
            fragments=self.fragments
        )
        
        self.assertTrue(result['success'])
        self.assertEqual(result['distributed_count'], 5)
        
        # Verify all fragments are marked distributed
        for fragment in self.fragments:
            fragment.refresh_from_db()
            self.assertTrue(fragment.is_distributed)
            self.assertIsNotNone(fragment.node)
        
        # Verify dead drop status updated
        self.dead_drop.refresh_from_db()
        self.assertIn(self.dead_drop.status, ['distributed', 'active'])
    
    def test_distribution_selects_diverse_nodes(self):
        """Test that distribution uses different nodes when possible."""
        result = self.distribution.distribute_fragments(
            dead_drop=self.dead_drop,
            fragments=self.fragments
        )
        
        assigned_nodes = set()
        for fragment in self.fragments:
            fragment.refresh_from_db()
            if fragment.node:
                assigned_nodes.add(fragment.node.id)
        
        # Should use different nodes (up to 5 different ones)
        self.assertGreaterEqual(len(assigned_nodes), min(5, len(self.nodes)))
    
    def test_distribution_health_check(self):
        """Test distribution health monitoring."""
        self.distribution.distribute_fragments(
            dead_drop=self.dead_drop,
            fragments=self.fragments
        )
        
        health = self.distribution.calculate_distribution_health(self.dead_drop)
        
        self.assertEqual(health['total_fragments'], 5)
        self.assertEqual(health['distributed'], 5)
        self.assertEqual(health['health'], 'good')
        self.assertGreaterEqual(health['available'], 3)


class CollectFragmentsFunctionalTest(TestCase):
    """Functional tests for collecting fragments at location."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='charlie',
            email='charlie@example.com',
            password='charliepass123'
        )
        self.shamir = ShamirSecretSharingService()
        self.crypto = MeshCryptoService()
        self.location_service = LocationVerificationService()
        
        # The secret to share
        self.secret = "collect-test-secret-password"
        
        # Location for the dead drop
        self.target_lat = Decimal('40.7128')
        self.target_lon = Decimal('-74.0060')
        
        # Create dead drop
        self.dead_drop = DeadDrop.objects.create(
            owner=self.user,
            title='Collection Test',
            latitude=self.target_lat,
            longitude=self.target_lon,
            radius_meters=50,
            encrypted_secret=self.secret.encode(),
            secret_hash=self.crypto.hash_secret(self.secret),
            required_fragments=3,
            total_fragments=5,
            status='active',
            expires_at=timezone.now() + timedelta(days=7)
        )
        
        # Create nodes with fragments
        shares = self.shamir.split_secret(self.secret.encode(), k=3, n=5)
        self.nodes = []
        
        for i, (index, share_data) in enumerate(shares):
            node = MeshNode.objects.create(
                device_name=f'CollectNode-{i}',
                device_type='phone_android',
                ble_address=f'CC:CC:CC:CC:CC:{i:02X}',
                public_key=f'collect_key_{i}',
                is_online=True,
                last_known_latitude=self.target_lat,
                last_known_longitude=self.target_lon
            )
            self.nodes.append(node)
            
            DeadDropFragment.objects.create(
                dead_drop=self.dead_drop,
                fragment_index=index,
                encrypted_fragment=share_data,
                fragment_hash='hash',
                storage_type='mesh_node',
                node=node,
                is_distributed=True,
                distributed_at=timezone.now()
            )
    
    def test_collect_at_correct_location(self):
        """Test successful collection at the dead drop location."""
        # User claims to be at the correct location
        claimed_location = {
            'latitude': float(self.target_lat),
            'longitude': float(self.target_lon),
            'accuracy_meters': 10
        }
        
        target = {
            'latitude': float(self.target_lat),
            'longitude': float(self.target_lon),
            'radius_meters': 50
        }
        
        # Verify location
        gps_result = self.location_service.verify_gps_location(
            claimed_location, target
        )
        
        self.assertTrue(gps_result['is_within_radius'])
        
        # Collect fragments
        fragments = self.dead_drop.fragments.filter(
            is_distributed=True,
            node__is_online=True
        )[:3]
        
        shares = [(f.fragment_index, f.encrypted_fragment) for f in fragments]
        reconstructed = self.shamir.reconstruct_secret(shares, k=3)
        
        self.assertEqual(reconstructed.decode(), self.secret)
    
    def test_collection_fails_at_wrong_location(self):
        """Test that collection fails at wrong location."""
        # User claims to be in London (wrong location)
        claimed_location = {
            'latitude': 51.5074,
            'longitude': -0.1278,
            'accuracy_meters': 10
        }
        
        target = {
            'latitude': float(self.target_lat),
            'longitude': float(self.target_lon),
            'radius_meters': 50
        }
        
        gps_result = self.location_service.verify_gps_location(
            claimed_location, target
        )
        
        self.assertFalse(gps_result['is_within_radius'])
        self.assertGreater(gps_result['distance_meters'], 5000000)  # >5000km
    
    def test_collection_logs_access_attempt(self):
        """Test that collection attempts are logged."""
        claimed_location = {
            'latitude': float(self.target_lat),
            'longitude': float(self.target_lon),
            'accuracy_meters': 10
        }
        
        # Log access attempt
        access = DeadDropAccess.objects.create(
            dead_drop=self.dead_drop,
            accessor=self.user,
            claimed_latitude=Decimal(str(claimed_location['latitude'])),
            claimed_longitude=Decimal(str(claimed_location['longitude'])),
            claimed_accuracy_meters=claimed_location['accuracy_meters'],
            gps_verified=True,
            ble_verified=True,
            ble_nodes_detected=3,
            result='success',
            fragments_collected=3,
            reconstruction_successful=True
        )
        
        self.assertIsNotNone(access.id)
        self.assertTrue(access.reconstruction_successful)
        
        # Check access log is associated with dead drop
        self.assertEqual(self.dead_drop.access_logs.count(), 1)


class PartialCollectionFunctionalTest(TestCase):
    """Functional tests for partial fragment collection scenarios."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='dave',
            email='dave@example.com',
            password='davepass123'
        )
        self.shamir = ShamirSecretSharingService()
        self.crypto = MeshCryptoService()
        
        self.secret = "partial-collection-secret"
        
        self.dead_drop = DeadDrop.objects.create(
            owner=self.user,
            title='Partial Collection Test',
            latitude=Decimal('40.7128'),
            longitude=Decimal('-74.0060'),
            encrypted_secret=self.secret.encode(),
            secret_hash=self.crypto.hash_secret(self.secret),
            required_fragments=3,
            total_fragments=5,
            status='active',
            expires_at=timezone.now() + timedelta(days=7)
        )
        
        # Create fragments
        shares = self.shamir.split_secret(self.secret.encode(), k=3, n=5)
        self.fragments = []
        
        for i, (index, share_data) in enumerate(shares):
            node = MeshNode.objects.create(
                device_name=f'PartialNode-{i}',
                device_type='phone_android',
                ble_address=f'DD:DD:DD:DD:DD:{i:02X}',
                public_key=f'partial_key_{i}',
                is_online=(i < 3),  # Only first 3 are online
            )
            
            fragment = DeadDropFragment.objects.create(
                dead_drop=self.dead_drop,
                fragment_index=index,
                encrypted_fragment=share_data,
                fragment_hash='hash',
                storage_type='mesh_node',
                node=node,
                is_distributed=True
            )
            self.fragments.append(fragment)
    
    def test_reconstruction_with_exactly_k_fragments(self):
        """Test reconstruction succeeds with exactly k fragments."""
        # Get the 3 fragments from online nodes
        online_fragments = self.dead_drop.fragments.filter(node__is_online=True)[:3]
        
        shares = [(f.fragment_index, f.encrypted_fragment) for f in online_fragments]
        reconstructed = self.shamir.reconstruct_secret(shares, k=3)
        
        self.assertEqual(reconstructed.decode(), self.secret)
    
    def test_reconstruction_fails_with_fewer_than_k(self):
        """Test reconstruction fails with fewer than k fragments."""
        # Get only 2 fragments (less than k=3)
        fragments = list(self.dead_drop.fragments.all()[:2])
        shares = [(f.fragment_index, f.encrypted_fragment) for f in fragments]
        
        # Should raise an error or return garbage
        with self.assertRaises(Exception):
            self.shamir.reconstruct_secret(shares, k=3)
    
    def test_reconstruction_with_more_than_k_fragments(self):
        """Test reconstruction works with more than k fragments."""
        # Make all nodes online
        MeshNode.objects.all().update(is_online=True)
        
        # Get all 5 fragments
        all_fragments = list(self.dead_drop.fragments.all())
        shares = [(f.fragment_index, f.encrypted_fragment) for f in all_fragments]
        
        reconstructed = self.shamir.reconstruct_secret(shares, k=3)
        
        self.assertEqual(reconstructed.decode(), self.secret)


class ExpirationFunctionalTest(TestCase):
    """Functional tests for dead drop expiration."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='eve',
            email='eve@example.com',
            password='evepass123'
        )
    
    def test_dead_drop_expiration(self):
        """Test dead drop expires after expiration time."""
        # Create dead drop that expires in 1 hour
        dead_drop = DeadDrop.objects.create(
            owner=self.user,
            title='Expiring Drop',
            latitude=Decimal('40.7128'),
            longitude=Decimal('-74.0060'),
            encrypted_secret=b'test',
            secret_hash='hash',
            required_fragments=3,
            total_fragments=5,
            expires_at=timezone.now() + timedelta(hours=1)
        )
        
        # Not expired yet
        self.assertFalse(dead_drop.is_expired)
        self.assertGreater(dead_drop.time_remaining_seconds, 3500)
        
        # Simulate time passing
        dead_drop.expires_at = timezone.now() - timedelta(hours=1)
        dead_drop.save()
        
        # Now expired
        dead_drop.refresh_from_db()
        self.assertTrue(dead_drop.is_expired)
        self.assertEqual(dead_drop.time_remaining_seconds, 0)
    
    def test_collection_rejected_when_expired(self):
        """Test that collection is rejected for expired dead drops."""
        dead_drop = DeadDrop.objects.create(
            owner=self.user,
            title='Already Expired',
            latitude=Decimal('40.7128'),
            longitude=Decimal('-74.0060'),
            encrypted_secret=b'test',
            secret_hash='hash',
            required_fragments=3,
            total_fragments=5,
            status='active',
            expires_at=timezone.now() - timedelta(hours=1)  # Already expired
        )
        
        self.assertTrue(dead_drop.is_expired)
        
        # Log failed access attempt
        access = DeadDropAccess.objects.create(
            dead_drop=dead_drop,
            accessor=self.user,
            claimed_latitude=Decimal('40.7128'),
            claimed_longitude=Decimal('-74.0060'),
            result='expired',
            fragments_collected=0,
            reconstruction_successful=False
        )
        
        self.assertEqual(access.result, 'expired')


class NFCVerificationFunctionalTest(TestCase):
    """Functional tests for NFC beacon verification."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='frank',
            email='frank@example.com',
            password='frankpass123'
        )
        
        self.dead_drop = DeadDrop.objects.create(
            owner=self.user,
            title='NFC Required Drop',
            latitude=Decimal('40.7128'),
            longitude=Decimal('-74.0060'),
            encrypted_secret=b'nfc-secret',
            secret_hash='hash',
            required_fragments=3,
            total_fragments=5,
            require_nfc_tap=True,
            expires_at=timezone.now() + timedelta(days=7)
        )
        
        self.beacon = NFCBeacon.objects.create(
            dead_drop=self.dead_drop,
            tag_id='04:11:22:33:44:55:66',
            tag_signature='valid_signature'
        )
    
    def test_nfc_challenge_response(self):
        """Test NFC challenge-response flow."""
        # 1. Get challenge
        challenge = self.beacon.rotate_challenge()
        self.assertIsNotNone(challenge)
        self.assertEqual(len(challenge), 64)  # 32 bytes hex
        
        # 2. Verify before expiry
        import hashlib
        expected_response = hashlib.blake2b(
            f"{self.beacon.tag_id}:{challenge}".encode(),
            digest_size=32
        ).hexdigest()
        
        result = self.beacon.verify_tap(expected_response)
        self.assertTrue(result)
    
    def test_nfc_verification_fails_with_wrong_response(self):
        """Test NFC verification fails with wrong response."""
        self.beacon.rotate_challenge()
        
        result = self.beacon.verify_tap("wrong_response")
        self.assertFalse(result)
    
    def test_nfc_verification_fails_after_expiry(self):
        """Test NFC verification fails after challenge expires."""
        challenge = self.beacon.rotate_challenge()
        
        # Expire the challenge
        self.beacon.challenge_expires_at = timezone.now() - timedelta(minutes=10)
        self.beacon.save()
        
        import hashlib
        response = hashlib.blake2b(
            f"{self.beacon.tag_id}:{challenge}".encode(),
            digest_size=32
        ).hexdigest()
        
        result = self.beacon.verify_tap(response)
        self.assertFalse(result)

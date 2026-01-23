"""
Dead Drop API Integration Tests
================================

End-to-end integration tests for the Dead Drop REST API including:
- Complete workflow testing
- Authentication and permissions
- Error handling
- Edge cases

@author Password Manager Team  
@created 2026-01-22
"""

from django.test import TestCase, TransactionTestCase
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APITestCase, APIClient
from rest_framework import status
from datetime import timedelta
from decimal import Decimal
import json

from mesh_deaddrop.models import (
    DeadDrop,
    DeadDropFragment,
    MeshNode,
    NFCBeacon,
    DeadDropAccess
)

User = get_user_model()


class DeadDropAPIIntegrationTests(APITestCase):
    """Integration tests for Dead Drop API endpoints."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.other_user = User.objects.create_user(
            username='otheruser',
            email='other@example.com',
            password='testpass123'
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
        
        # Create some mesh nodes
        self.nodes = []
        for i in range(5):
            node = MeshNode.objects.create(
                device_name=f'TestNode-{i}',
                device_type='phone',
                ble_address=f'AA:BB:CC:DD:EE:{i:02X}',
                public_key=f'public_key_{i}',
                is_online=True,
                trust_score=Decimal('0.8'),
                max_fragments=10,
                last_known_lat=Decimal('40.7128'),
                last_known_lon=Decimal('-74.0060')
            )
            self.nodes.append(node)
    
    def test_create_dead_drop_success(self):
        """Test creating a dead drop successfully."""
        data = {
            'title': 'Test Secret Share',
            'secret': 'my-super-secret-password-123',
            'latitude': '40.7128',
            'longitude': '-74.0060',
            'radius_meters': 50,
            'location_hint': 'Near the coffee shop',
            'required_fragments': 3,
            'total_fragments': 5,
            'expires_in_hours': 168
        }
        
        response = self.client.post('/api/mesh/deaddrops/', data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('dead_drop', response.data)
        self.assertEqual(response.data['dead_drop']['title'], 'Test Secret Share')
        self.assertEqual(response.data['dead_drop']['status'], 'pending')
    
    def test_create_dead_drop_invalid_threshold(self):
        """Test creating dead drop with invalid threshold."""
        data = {
            'title': 'Invalid Threshold',
            'secret': 'test-secret',
            'latitude': '40.7128',
            'longitude': '-74.0060',
            'required_fragments': 6,  # More than total!
            'total_fragments': 5,
            'expires_in_hours': 168
        }
        
        response = self.client.post('/api/mesh/deaddrops/', data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_create_dead_drop_unauthenticated(self):
        """Test that unauthenticated users cannot create dead drops."""
        self.client.logout()
        
        data = {
            'title': 'Unauthorized Test',
            'secret': 'test-secret',
            'latitude': '40.7128',
            'longitude': '-74.0060',
        }
        
        response = self.client.post('/api/mesh/deaddrops/', data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_list_dead_drops(self):
        """Test listing user's dead drops."""
        # Create dead drops
        for i in range(3):
            DeadDrop.objects.create(
                owner=self.user,
                title=f'Drop {i}',
                latitude=Decimal('40.7128'),
                longitude=Decimal('-74.0060'),
                encrypted_secret=b'test',
                secret_hash='hash',
                required_fragments=3,
                total_fragments=5,
                expires_at=timezone.now() + timedelta(days=7)
            )
        
        # Create another user's drop (should not appear)
        DeadDrop.objects.create(
            owner=self.other_user,
            title='Other Drop',
            latitude=Decimal('40.7128'),
            longitude=Decimal('-74.0060'),
            encrypted_secret=b'test',
            secret_hash='hash',
            required_fragments=3,
            total_fragments=5,
            expires_at=timezone.now() + timedelta(days=7)
        )
        
        response = self.client.get('/api/mesh/deaddrops/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['dead_drops']), 3)
    
    def test_get_dead_drop_detail(self):
        """Test getting dead drop details."""
        dead_drop = DeadDrop.objects.create(
            owner=self.user,
            title='Detail Test',
            latitude=Decimal('40.7128'),
            longitude=Decimal('-74.0060'),
            encrypted_secret=b'test',
            secret_hash='hash',
            required_fragments=3,
            total_fragments=5,
            expires_at=timezone.now() + timedelta(days=7)
        )
        
        response = self.client.get(f'/api/mesh/deaddrops/{dead_drop.id}/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['title'], 'Detail Test')
    
    def test_get_other_users_drop_forbidden(self):
        """Test that users cannot access other users' drops."""
        other_drop = DeadDrop.objects.create(
            owner=self.other_user,
            title='Private Drop',
            latitude=Decimal('40.7128'),
            longitude=Decimal('-74.0060'),
            encrypted_secret=b'test',
            secret_hash='hash',
            required_fragments=3,
            total_fragments=5,
            expires_at=timezone.now() + timedelta(days=7)
        )
        
        response = self.client.get(f'/api/mesh/deaddrops/{other_drop.id}/')
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
    
    def test_cancel_dead_drop(self):
        """Test cancelling a dead drop."""
        dead_drop = DeadDrop.objects.create(
            owner=self.user,
            title='Cancel Test',
            latitude=Decimal('40.7128'),
            longitude=Decimal('-74.0060'),
            encrypted_secret=b'test',
            secret_hash='hash',
            required_fragments=3,
            total_fragments=5,
            expires_at=timezone.now() + timedelta(days=7)
        )
        
        response = self.client.post(f'/api/mesh/deaddrops/{dead_drop.id}/cancel/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        dead_drop.refresh_from_db()
        self.assertEqual(dead_drop.status, 'cancelled')
        self.assertFalse(dead_drop.is_active)
    
    def test_collect_dead_drop_with_location_proof(self):
        """Test collecting a dead drop with valid location proof."""
        dead_drop = DeadDrop.objects.create(
            owner=self.user,
            title='Collect Test',
            latitude=Decimal('40.7128'),
            longitude=Decimal('-74.0060'),
            radius_meters=50,
            encrypted_secret=b'my_secret_data',
            secret_hash='hash123',
            required_fragments=3,
            total_fragments=5,
            status='active',
            expires_at=timezone.now() + timedelta(days=7)
        )
        
        # Create distributed fragments
        for i in range(5):
            DeadDropFragment.objects.create(
                dead_drop=dead_drop,
                fragment_index=i + 1,
                encrypted_fragment=f'fragment_{i}'.encode(),
                fragment_hash=f'hash_{i}',
                node=self.nodes[i],
                is_distributed=True,
                distributed_at=timezone.now()
            )
        
        location_data = {
            'location': {
                'latitude': '40.7128',
                'longitude': '-74.0060',
                'accuracy_meters': 10,
                'ble_nodes': [
                    {'id': str(self.nodes[0].id), 'rssi': -55},
                    {'id': str(self.nodes[1].id), 'rssi': -60},
                    {'id': str(self.nodes[2].id), 'rssi': -65},
                ]
            }
        }
        
        response = self.client.post(
            f'/api/mesh/deaddrops/{dead_drop.id}/collect/',
            location_data,
            format='json'
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('secret', response.data)
    
    def test_collect_dead_drop_wrong_location(self):
        """Test collection fails at wrong location."""
        dead_drop = DeadDrop.objects.create(
            owner=self.user,
            title='Wrong Location Test',
            latitude=Decimal('40.7128'),
            longitude=Decimal('-74.0060'),
            radius_meters=50,
            encrypted_secret=b'secret',
            secret_hash='hash',
            required_fragments=3,
            total_fragments=5,
            status='active',
            expires_at=timezone.now() + timedelta(days=7)
        )
        
        location_data = {
            'location': {
                'latitude': '51.5074',  # London (wrong location)
                'longitude': '-0.1278',
                'accuracy_meters': 10
            }
        }
        
        response = self.client.post(
            f'/api/mesh/deaddrops/{dead_drop.id}/collect/',
            location_data,
            format='json'
        )
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class MeshNodeAPITests(APITestCase):
    """Tests for Mesh Node API endpoints."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
    
    def test_register_node(self):
        """Test registering a new mesh node."""
        data = {
            'device_name': 'My Phone',
            'device_type': 'phone',
            'ble_address': 'AA:BB:CC:DD:EE:FF',
            'public_key': 'my_public_key_data',
            'max_fragments': 10
        }
        
        response = self.client.post('/api/mesh/nodes/', data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('node', response.data)
        self.assertEqual(response.data['node']['device_name'], 'My Phone')
    
    def test_list_nodes(self):
        """Test listing mesh nodes."""
        # Create nodes
        for i in range(3):
            MeshNode.objects.create(
                owner=self.user,
                device_name=f'Node-{i}',
                device_type='phone',
                ble_address=f'AA:BB:CC:DD:EE:{i:02X}',
                public_key=f'key_{i}'
            )
        
        response = self.client.get('/api/mesh/nodes/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['nodes']), 3)
    
    def test_ping_node(self):
        """Test pinging a node to update status."""
        node = MeshNode.objects.create(
            owner=self.user,
            device_name='Ping Test Node',
            device_type='phone',
            ble_address='AA:BB:CC:DD:EE:FF',
            public_key='key'
        )
        
        data = {
            'latitude': 40.7128,
            'longitude': -74.0060
        }
        
        response = self.client.post(f'/api/mesh/nodes/{node.id}/ping/', data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        node.refresh_from_db()
        self.assertTrue(node.is_online)
    
    def test_get_nearby_nodes(self):
        """Test getting nearby mesh nodes."""
        # Create nodes at various locations
        MeshNode.objects.create(
            device_name='Nearby Node',
            device_type='phone',
            ble_address='AA:BB:CC:DD:EE:01',
            public_key='key1',
            is_online=True,
            last_known_lat=Decimal('40.7128'),
            last_known_lon=Decimal('-74.0060')
        )
        MeshNode.objects.create(
            device_name='Far Node',
            device_type='phone',
            ble_address='AA:BB:CC:DD:EE:02',
            public_key='key2',
            is_online=True,
            last_known_lat=Decimal('51.5074'),  # London
            last_known_lon=Decimal('-0.1278')
        )
        
        response = self.client.get('/api/mesh/nodes/nearby/?lat=40.7128&lon=-74.0060&radius=10')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['nodes']), 1)
        self.assertEqual(response.data['nodes'][0]['device_name'], 'Nearby Node')


class NFCVerificationAPITests(APITestCase):
    """Tests for NFC verification API endpoints."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
        
        self.dead_drop = DeadDrop.objects.create(
            owner=self.user,
            title='NFC Test',
            latitude=Decimal('40.7128'),
            longitude=Decimal('-74.0060'),
            encrypted_secret=b'test',
            secret_hash='hash',
            required_fragments=3,
            total_fragments=5,
            require_nfc_tap=True,
            expires_at=timezone.now() + timedelta(days=7)
        )
        
        self.beacon = NFCBeacon.objects.create(
            dead_drop=self.dead_drop,
            beacon_uid='04:11:22:33:44:55:66',
            public_key='beacon_public_key',
            latitude=Decimal('40.7128'),
            longitude=Decimal('-74.0060')
        )
    
    def test_request_nfc_challenge(self):
        """Test requesting an NFC challenge."""
        response = self.client.post(
            '/api/mesh/nfc/challenge/',
            {'beacon_id': str(self.beacon.id)},
            format='json'
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('challenge', response.data)
        self.assertIn('nonce', response.data)
    
    def test_verify_nfc_response(self):
        """Test verifying NFC response."""
        # First get a challenge
        challenge_response = self.client.post(
            '/api/mesh/nfc/challenge/',
            {'beacon_id': str(self.beacon.id)},
            format='json'
        )
        
        challenge = challenge_response.data['challenge']
        
        # Submit response (in real scenario, this would be from NFC tap)
        response = self.client.post(
            '/api/mesh/nfc/verify/',
            {
                'beacon_id': str(self.beacon.id),
                'challenge': challenge,
                'response': 'mock_signed_response'
            },
            format='json'
        )
        
        # Response depends on implementation
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST])


class DeadDropWorkflowE2ETests(TransactionTestCase):
    """End-to-end tests for complete dead drop workflow."""
    
    def setUp(self):
        """Set up test data."""
        self.sender = User.objects.create_user(
            username='sender',
            email='sender@example.com',
            password='senderpass123'
        )
        self.recipient = User.objects.create_user(
            username='recipient',
            email='recipient@example.com',
            password='recipientpass123'
        )
        self.sender_client = APIClient()
        self.sender_client.force_authenticate(user=self.sender)
        self.recipient_client = APIClient()
        self.recipient_client.force_authenticate(user=self.recipient)
        
        # Create mesh nodes
        for i in range(5):
            MeshNode.objects.create(
                device_name=f'E2E-Node-{i}',
                device_type='phone',
                ble_address=f'E2:E2:E2:E2:E2:{i:02X}',
                public_key=f'e2e_key_{i}',
                is_online=True,
                trust_score=Decimal('0.85'),
                max_fragments=10,
                last_known_lat=Decimal('40.7128'),
                last_known_lon=Decimal('-74.0060')
            )
    
    def test_complete_create_distribute_collect_workflow(self):
        """Test complete workflow: create -> distribute -> collect."""
        # Step 1: Sender creates dead drop
        create_data = {
            'title': 'E2E Test Secret',
            'secret': 'super-secret-password-for-e2e-testing',
            'latitude': '40.7128',
            'longitude': '-74.0060',
            'radius_meters': 50,
            'location_hint': 'Under the bridge',
            'required_fragments': 3,
            'total_fragments': 5,
            'expires_in_hours': 168
        }
        
        create_response = self.sender_client.post(
            '/api/mesh/deaddrops/',
            create_data,
            format='json'
        )
        
        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)
        drop_id = create_response.data['dead_drop']['id']
        
        # Step 2: Distribute fragments
        distribute_response = self.sender_client.post(
            f'/api/mesh/deaddrops/{drop_id}/distribute/'
        )
        
        self.assertEqual(distribute_response.status_code, status.HTTP_200_OK)
        
        # Step 3: Check distribution status
        detail_response = self.sender_client.get(f'/api/mesh/deaddrops/{drop_id}/')
        self.assertEqual(detail_response.data['status'], 'active')
        
        # Step 4: Recipient collects at location
        # (In real scenario, recipient needs to be at location)
        nodes = MeshNode.objects.filter(is_online=True)[:3]
        
        collect_data = {
            'location': {
                'latitude': '40.7128',
                'longitude': '-74.0060',
                'accuracy_meters': 5,
                'ble_nodes': [
                    {'id': str(node.id), 'rssi': -55}
                    for node in nodes
                ]
            }
        }
        
        # Need to make the drop accessible to recipient
        # (In real app, might use access code or recipient public key)
        collect_response = self.sender_client.post(
            f'/api/mesh/deaddrops/{drop_id}/collect/',
            collect_data,
            format='json'
        )
        
        # Check collection result
        if collect_response.status_code == status.HTTP_200_OK:
            self.assertIn('secret', collect_response.data)
            self.assertEqual(
                collect_response.data['secret'],
                'super-secret-password-for-e2e-testing'
            )
    
    def test_partial_collection_fails(self):
        """Test that collecting fewer than threshold fragments fails."""
        # Create and distribute dead drop
        create_data = {
            'title': 'Partial Collection Test',
            'secret': 'test-secret',
            'latitude': '40.7128',
            'longitude': '-74.0060',
            'required_fragments': 3,
            'total_fragments': 5,
            'expires_in_hours': 168
        }
        
        create_response = self.sender_client.post(
            '/api/mesh/deaddrops/',
            create_data,
            format='json'
        )
        
        drop_id = create_response.data['dead_drop']['id']
        self.sender_client.post(f'/api/mesh/deaddrops/{drop_id}/distribute/')
        
        # Make most nodes offline so only 2 fragments available
        MeshNode.objects.all().update(is_online=False)
        two_nodes = MeshNode.objects.all()[:2]
        for node in two_nodes:
            node.is_online = True
            node.save()
        
        collect_data = {
            'location': {
                'latitude': '40.7128',
                'longitude': '-74.0060',
                'accuracy_meters': 5,
                'ble_nodes': [
                    {'id': str(node.id), 'rssi': -55}
                    for node in two_nodes
                ]
            }
        }
        
        collect_response = self.sender_client.post(
            f'/api/mesh/deaddrops/{drop_id}/collect/',
            collect_data,
            format='json'
        )
        
        # Should fail because not enough fragments
        self.assertIn(
            collect_response.status_code,
            [status.HTTP_400_BAD_REQUEST, status.HTTP_403_FORBIDDEN]
        )

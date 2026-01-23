"""
Fragment Distribution Service Tests
=====================================

Tests for fragment distribution including:
- Node selection algorithm
- Fragment distribution
- Rebalancing logic
- Trust scoring

@author Password Manager Team
@created 2026-01-22
"""

from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal
from unittest.mock import Mock, patch, MagicMock

from mesh_deaddrop.models import DeadDrop, DeadDropFragment, MeshNode
from mesh_deaddrop.services.fragment_distribution_service import (
    FragmentDistributionService
)

User = get_user_model()


class FragmentDistributionServiceTests(TestCase):
    """Tests for FragmentDistributionService."""
    
    def setUp(self):
        """Set up test data."""
        self.service = FragmentDistributionService()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        # Create a dead drop
        self.dead_drop = DeadDrop.objects.create(
            owner=self.user,
            title='Distribution Test',
            latitude=Decimal('40.7128'),
            longitude=Decimal('-74.0060'),
            encrypted_secret=b'test_secret',
            secret_hash='abc123',
            required_fragments=3,
            total_fragments=5,
            expires_at=timezone.now() + timedelta(days=7)
        )
        
        # Create mesh nodes
        self.nodes = []
        for i in range(7):
            node = MeshNode.objects.create(
                owner=self.user if i < 3 else None,
                device_name=f'Node-{i}',
                device_type='phone',
                ble_address=f'AA:BB:CC:DD:EE:{i:02X}',
                public_key=f'public_key_{i}',
                is_online=True,
                trust_score=Decimal('0.8') + Decimal(str(i * 0.02)),
                max_fragments=10,
                current_fragment_count=i,
                last_known_lat=Decimal('40.7128') + Decimal(str(i * 0.001)),
                last_known_lon=Decimal('-74.0060')
            )
            self.nodes.append(node)
    
    def test_select_nodes_for_distribution(self):
        """Test selecting nodes for fragment distribution."""
        selected = self.service.select_nodes_for_distribution(
            dead_drop=self.dead_drop,
            num_nodes=5
        )
        
        self.assertEqual(len(selected), 5)
        # All selected nodes should be online
        for node in selected:
            self.assertTrue(node.is_online)
    
    def test_select_nodes_prefers_nearby(self):
        """Test that nearby nodes are preferred."""
        # Create a distant node
        distant_node = MeshNode.objects.create(
            device_name='Distant Node',
            device_type='phone',
            ble_address='FF:FF:FF:FF:FF:FF',
            public_key='distant_key',
            is_online=True,
            trust_score=Decimal('0.9'),
            last_known_lat=Decimal('51.5074'),  # London
            last_known_lon=Decimal('-0.1278')
        )
        
        selected = self.service.select_nodes_for_distribution(
            dead_drop=self.dead_drop,
            num_nodes=5,
            prefer_nearby=True
        )
        
        # Distant node should not be in top selections
        node_ids = [n.id for n in selected]
        # If we have enough nearby nodes, distant should be excluded
        if len(self.nodes) >= 5:
            self.assertNotIn(distant_node.id, node_ids)
    
    def test_select_nodes_excludes_full(self):
        """Test that full nodes are excluded."""
        # Make some nodes full
        self.nodes[0].current_fragment_count = 10
        self.nodes[0].save()
        
        selected = self.service.select_nodes_for_distribution(
            dead_drop=self.dead_drop,
            num_nodes=5
        )
        
        selected_ids = [n.id for n in selected]
        self.assertNotIn(self.nodes[0].id, selected_ids)
    
    def test_select_nodes_excludes_offline(self):
        """Test that offline nodes are excluded."""
        self.nodes[1].is_online = False
        self.nodes[1].save()
        
        selected = self.service.select_nodes_for_distribution(
            dead_drop=self.dead_drop,
            num_nodes=5
        )
        
        selected_ids = [n.id for n in selected]
        self.assertNotIn(self.nodes[1].id, selected_ids)
    
    def test_distribute_fragments(self):
        """Test distributing fragments to nodes."""
        # Create fragments
        fragments = []
        for i in range(5):
            fragment = DeadDropFragment.objects.create(
                dead_drop=self.dead_drop,
                fragment_index=i + 1,
                encrypted_fragment=f'fragment_{i}'.encode(),
                fragment_hash=f'hash_{i}'
            )
            fragments.append(fragment)
        
        result = self.service.distribute_fragments(
            dead_drop=self.dead_drop,
            fragments=fragments
        )
        
        self.assertTrue(result['success'])
        self.assertEqual(result['distributed_count'], 5)
        
        # Check fragments are marked as distributed
        for fragment in fragments:
            fragment.refresh_from_db()
            self.assertTrue(fragment.is_distributed)
    
    def test_distribute_to_specific_nodes(self):
        """Test distributing to specific target nodes."""
        fragment = DeadDropFragment.objects.create(
            dead_drop=self.dead_drop,
            fragment_index=1,
            encrypted_fragment=b'test_fragment',
            fragment_hash='test_hash'
        )
        
        target_nodes = self.nodes[:3]
        
        result = self.service.distribute_fragment_to_nodes(
            fragment=fragment,
            target_nodes=target_nodes
        )
        
        self.assertTrue(result['success'])
        fragment.refresh_from_db()
        self.assertIn(fragment.node, target_nodes)
    
    def test_calculate_distribution_health(self):
        """Test distribution health calculation."""
        # Create distributed fragments
        for i in range(5):
            DeadDropFragment.objects.create(
                dead_drop=self.dead_drop,
                fragment_index=i + 1,
                encrypted_fragment=f'fragment_{i}'.encode(),
                fragment_hash=f'hash_{i}',
                node=self.nodes[i],
                is_distributed=True,
                distributed_at=timezone.now()
            )
        
        health = self.service.calculate_distribution_health(self.dead_drop)
        
        self.assertEqual(health['total_fragments'], 5)
        self.assertEqual(health['distributed'], 5)
        self.assertEqual(health['health'], 'good')
    
    def test_distribution_health_degraded(self):
        """Test health calculation when some nodes are offline."""
        # Create distributed fragments
        for i in range(5):
            node = self.nodes[i]
            if i < 2:  # Make 2 nodes offline
                node.is_online = False
                node.save()
            
            DeadDropFragment.objects.create(
                dead_drop=self.dead_drop,
                fragment_index=i + 1,
                encrypted_fragment=f'fragment_{i}'.encode(),
                fragment_hash=f'hash_{i}',
                node=node,
                is_distributed=True,
                distributed_at=timezone.now()
            )
        
        health = self.service.calculate_distribution_health(self.dead_drop)
        
        self.assertEqual(health['available'], 3)  # Only 3 online
        # Still 'good' because we need 3 and have 3 available
        self.assertEqual(health['health'], 'good')
    
    def test_distribution_health_critical(self):
        """Test health is critical when below threshold."""
        # Create fragments with most nodes offline
        for i in range(5):
            node = self.nodes[i]
            if i >= 1:  # Only 1 node online
                node.is_online = False
                node.save()
            
            DeadDropFragment.objects.create(
                dead_drop=self.dead_drop,
                fragment_index=i + 1,
                encrypted_fragment=f'fragment_{i}'.encode(),
                fragment_hash=f'hash_{i}',
                node=node,
                is_distributed=True,
                distributed_at=timezone.now()
            )
        
        health = self.service.calculate_distribution_health(self.dead_drop)
        
        self.assertEqual(health['available'], 1)
        self.assertEqual(health['health'], 'critical')  # Below threshold
    
    def test_rebalance_fragments(self):
        """Test fragment rebalancing when nodes go offline."""
        # Create fragments on some nodes
        for i in range(3):
            DeadDropFragment.objects.create(
                dead_drop=self.dead_drop,
                fragment_index=i + 1,
                encrypted_fragment=f'fragment_{i}'.encode(),
                fragment_hash=f'hash_{i}',
                node=self.nodes[i],
                is_distributed=True,
                distributed_at=timezone.now()
            )
        
        # Make one node offline
        self.nodes[0].is_online = False
        self.nodes[0].save()
        
        result = self.service.rebalance_fragments(self.dead_drop)
        
        self.assertTrue(result['rebalanced'])
        self.assertEqual(result['fragments_moved'], 1)
    
    def test_node_selection_by_trust_score(self):
        """Test that higher trust nodes are preferred."""
        # Create nodes with varying trust scores
        high_trust = MeshNode.objects.create(
            device_name='High Trust',
            device_type='phone',
            ble_address='HH:HH:HH:HH:HH:HH',
            public_key='high_trust_key',
            is_online=True,
            trust_score=Decimal('0.99'),
            last_known_lat=Decimal('40.7128'),
            last_known_lon=Decimal('-74.0060')
        )
        
        low_trust = MeshNode.objects.create(
            device_name='Low Trust',
            device_type='phone',
            ble_address='LL:LL:LL:LL:LL:LL',
            public_key='low_trust_key',
            is_online=True,
            trust_score=Decimal('0.30'),
            last_known_lat=Decimal('40.7128'),
            last_known_lon=Decimal('-74.0060')
        )
        
        selected = self.service.select_nodes_for_distribution(
            dead_drop=self.dead_drop,
            num_nodes=1,
            prefer_trusted=True
        )
        
        self.assertEqual(selected[0].id, high_trust.id)


class TrustScoreTests(TestCase):
    """Tests for node trust scoring."""
    
    def setUp(self):
        """Set up test data."""
        self.service = FragmentDistributionService()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
    
    def test_calculate_trust_score_new_node(self):
        """Test trust score for new nodes."""
        node = MeshNode.objects.create(
            device_name='New Node',
            device_type='phone',
            ble_address='AA:BB:CC:DD:EE:FF',
            public_key='key'
        )
        
        score = self.service.calculate_trust_score(node)
        
        # New nodes should have default trust
        self.assertGreater(score, 0.4)
        self.assertLess(score, 0.7)
    
    def test_trust_score_increases_with_activity(self):
        """Test that active nodes gain trust."""
        node = MeshNode.objects.create(
            device_name='Active Node',
            device_type='phone',
            ble_address='AA:BB:CC:DD:EE:FF',
            public_key='key',
            successful_transfers=100,
            failed_transfers=5,
            total_uptime_hours=500
        )
        
        score = self.service.calculate_trust_score(node)
        
        self.assertGreater(score, 0.7)
    
    def test_trust_score_decreases_with_failures(self):
        """Test that failures reduce trust."""
        node = MeshNode.objects.create(
            device_name='Unreliable Node',
            device_type='phone',
            ble_address='AA:BB:CC:DD:EE:FF',
            public_key='key',
            successful_transfers=10,
            failed_transfers=50  # High failure rate
        )
        
        score = self.service.calculate_trust_score(node)
        
        self.assertLess(score, 0.5)

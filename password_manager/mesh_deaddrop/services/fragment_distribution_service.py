"""
Fragment Distribution Service
==============================

Manages the distribution of secret fragments across mesh nodes:
- Node selection strategy (reliability, location, capacity)
- Fragment distribution with redundancy
- Fragment collection coordination
- Reconstruction verification

Strategies:
- Priority: Reliability-first, locality-first, random
- Redundancy: Store fragments on multiple nodes
- Rebalancing: Move fragments when nodes go offline

@author Password Manager Team
@created 2026-01-22
"""

import random
from typing import List, Dict, Optional, Set
from dataclasses import dataclass
from enum import Enum

from django.db import transaction
from django.utils import timezone

from ..models import DeadDrop, DeadDropFragment, MeshNode, FragmentTransfer
from .shamir_service import ShamirSecretSharingService, Share
from .mesh_crypto_service import MeshCryptoService


class DistributionStrategy(Enum):
    """Fragment distribution strategies."""
    RELIABILITY_FIRST = 'reliability'  # Prefer high-trust nodes
    LOCALITY_FIRST = 'locality'        # Prefer nearby nodes
    RANDOM = 'random'                   # Random selection
    BALANCED = 'balanced'               # Mix of factors


@dataclass
class DistributionPlan:
    """Plan for distributing fragments to nodes."""
    fragment_id: str
    target_node: MeshNode
    backup_nodes: List[MeshNode]
    priority: int


@dataclass
class DistributionResult:
    """Result of a distribution operation."""
    success: bool
    fragments_distributed: int
    fragments_failed: int
    node_assignments: Dict[str, str]  # fragment_id -> node_id
    errors: List[str]


@dataclass
class CollectionResult:
    """Result of fragment collection."""
    success: bool
    fragments_collected: int
    fragments_needed: int
    reconstructed_secret: Optional[bytes]
    errors: List[str]


class FragmentDistributionService:
    """
    Manages fragment distribution across mesh network.
    
    Usage:
        service = FragmentDistributionService()
        
        # Create and distribute dead drop
        result = service.create_and_distribute(
            owner=user,
            secret=b"sensitive data",
            latitude=40.7128,
            longitude=-74.0060,
            k=3, n=5
        )
        
        # Collect fragments
        collection = service.collect_fragments(
            dead_drop=drop,
            accessor=user,
            visible_nodes=[node1, node2, node3]
        )
    """
    
    def __init__(self):
        """Initialize the distribution service."""
        self.shamir = ShamirSecretSharingService()
        self.crypto = MeshCryptoService()
    
    def create_and_distribute(
        self,
        owner,
        title: str,
        secret: bytes,
        latitude: float,
        longitude: float,
        k: int = 3,
        n: int = 5,
        expires_in_hours: int = 168,
        radius_meters: int = 50,
        strategy: DistributionStrategy = DistributionStrategy.BALANCED,
        require_ble: bool = True,
        require_nfc: bool = False
    ) -> tuple:
        """
        Create a dead drop and distribute fragments to mesh nodes.
        
        Args:
            owner: User creating the dead drop
            title: Title for the dead drop
            secret: Secret data to protect
            latitude: Target latitude
            longitude: Target longitude
            k: Threshold (minimum fragments needed)
            n: Total fragments to create
            expires_in_hours: Expiration time
            radius_meters: Geofence radius
            strategy: Node selection strategy
            require_ble: Require BLE verification
            require_nfc: Require NFC verification
            
        Returns:
            Tuple of (DeadDrop, DistributionResult)
        """
        # Split secret using Shamir
        split_result = self.shamir.split_secret(secret, k, n)
        
        # Encrypt the full secret for verification
        encrypted_secret = self.crypto.encrypt_for_node(
            secret,
            self.crypto.generate_mesh_keypair().public_key
        )
        
        # Create the dead drop
        with transaction.atomic():
            dead_drop = DeadDrop.objects.create(
                owner=owner,
                title=title,
                latitude=latitude,
                longitude=longitude,
                radius_meters=radius_meters,
                encrypted_secret=self.crypto.serialize_payload(encrypted_secret),
                secret_hash=split_result.original_hash,
                required_fragments=k,
                total_fragments=n,
                expires_at=timezone.now() + timezone.timedelta(hours=expires_in_hours),
                require_ble_verification=require_ble,
                require_nfc_tap=require_nfc,
                status='pending'
            )
            
            # Create fragment records
            fragments = []
            for share in split_result.shares:
                fragment = DeadDropFragment.objects.create(
                    dead_drop=dead_drop,
                    fragment_index=share.index,
                    encrypted_fragment=share.value,
                    fragment_hash=self.crypto.hash_secret(share.value),
                    storage_type='mesh_node',
                    is_distributed=False
                )
                fragments.append(fragment)
        
        # Select nodes and distribute
        distribution_result = self._distribute_to_nodes(
            dead_drop,
            fragments,
            latitude,
            longitude,
            strategy
        )
        
        # Update dead drop status
        if distribution_result.success:
            dead_drop.status = 'active'
        else:
            dead_drop.status = 'distributed' if distribution_result.fragments_distributed > 0 else 'pending'
        dead_drop.save()
        
        return dead_drop, distribution_result
    
    def _distribute_to_nodes(
        self,
        dead_drop: DeadDrop,
        fragments: List[DeadDropFragment],
        target_lat: float,
        target_lon: float,
        strategy: DistributionStrategy
    ) -> DistributionResult:
        """
        Distribute fragments to mesh nodes.
        
        Args:
            dead_drop: The dead drop being distributed
            fragments: Fragments to distribute
            target_lat: Target latitude
            target_lon: Target longitude
            strategy: Selection strategy
            
        Returns:
            DistributionResult
        """
        # Get available nodes
        available_nodes = MeshNode.objects.filter(
            is_online=True,
            is_available_for_storage=True
        ).exclude(
            current_fragment_count__gte=models.F('max_fragments')
        )
        
        if available_nodes.count() < len(fragments):
            # Not enough nodes - some fragments will be stored locally
            pass
        
        # Score and rank nodes
        scored_nodes = self._score_nodes(
            list(available_nodes),
            target_lat,
            target_lon,
            strategy
        )
        
        # Assign fragments to nodes
        result = DistributionResult(
            success=True,
            fragments_distributed=0,
            fragments_failed=0,
            node_assignments={},
            errors=[]
        )
        
        for i, fragment in enumerate(fragments):
            if i < len(scored_nodes):
                target_node = scored_nodes[i]
                
                try:
                    self._assign_fragment_to_node(fragment, target_node)
                    result.fragments_distributed += 1
                    result.node_assignments[str(fragment.id)] = str(target_node.id)
                except Exception as e:
                    result.fragments_failed += 1
                    result.errors.append(f"Failed to assign fragment {i}: {e}")
            else:
                # Store locally as fallback
                fragment.storage_type = 'self'
                fragment.is_distributed = True
                fragment.distributed_at = timezone.now()
                fragment.save()
                result.fragments_distributed += 1
        
        result.success = result.fragments_failed == 0
        return result
    
    def _score_nodes(
        self,
        nodes: List[MeshNode],
        target_lat: float,
        target_lon: float,
        strategy: DistributionStrategy
    ) -> List[MeshNode]:
        """
        Score and rank nodes based on strategy.
        
        Returns:
            Sorted list of nodes (best first)
        """
        import math
        
        scored = []
        
        for node in nodes:
            score = 0.0
            
            # Calculate distance if location available
            distance = float('inf')
            if node.last_known_latitude and node.last_known_longitude:
                lat1 = math.radians(float(target_lat))
                lat2 = math.radians(float(node.last_known_latitude))
                dlon = math.radians(float(node.last_known_longitude) - float(target_lon))
                
                # Simplified distance calculation
                distance = math.sqrt((lat2 - lat1)**2 + (dlon * math.cos(lat1))**2) * 111000  # meters
            
            if strategy == DistributionStrategy.RELIABILITY_FIRST:
                score = node.trust_score * 100
            elif strategy == DistributionStrategy.LOCALITY_FIRST:
                score = max(0, 100 - distance / 100)  # Closer = higher score
            elif strategy == DistributionStrategy.RANDOM:
                score = random.random() * 100
            else:  # BALANCED
                score = (node.trust_score * 50) + max(0, 50 - distance / 200)
            
            # Bonus for available capacity
            capacity_ratio = 1 - (node.current_fragment_count / node.max_fragments)
            score += capacity_ratio * 10
            
            scored.append((score, node))
        
        # Sort by score (descending)
        scored.sort(key=lambda x: x[0], reverse=True)
        
        return [node for score, node in scored]
    
    def _assign_fragment_to_node(
        self,
        fragment: DeadDropFragment,
        node: MeshNode
    ):
        """
        Assign a fragment to a specific node.
        
        Encrypts fragment for the node and updates records.
        """
        # Encrypt fragment for this node
        encrypted = self.crypto.encrypt_for_node(
            fragment.encrypted_fragment,
            node.public_key.encode() if isinstance(node.public_key, str) else node.public_key
        )
        
        # Update fragment
        fragment.node = node
        fragment.node_public_key = node.public_key
        fragment.encrypted_fragment = self.crypto.serialize_payload(encrypted)
        fragment.is_distributed = True
        fragment.distributed_at = timezone.now()
        fragment.save()
        
        # Update node capacity
        node.current_fragment_count += 1
        node.save()
        
        # Log transfer
        FragmentTransfer.objects.create(
            fragment=fragment,
            from_node=None,  # From creator
            to_node=node,
            transfer_successful=True,
            bytes_transferred=len(fragment.encrypted_fragment)
        )
    
    def collect_fragments(
        self,
        dead_drop: DeadDrop,
        accessor,
        visible_node_ids: List[str],
        node_private_keys: Dict[str, bytes] = None
    ) -> CollectionResult:
        """
        Collect fragments from visible mesh nodes.
        
        Args:
            dead_drop: The dead drop to collect from
            accessor: User attempting collection
            visible_node_ids: UUIDs of nodes currently visible via BLE
            node_private_keys: Optional private keys for decryption (for testing)
            
        Returns:
            CollectionResult
        """
        result = CollectionResult(
            success=False,
            fragments_collected=0,
            fragments_needed=dead_drop.required_fragments,
            reconstructed_secret=None,
            errors=[]
        )
        
        # Get fragments stored on visible nodes
        visible_fragments = DeadDropFragment.objects.filter(
            dead_drop=dead_drop,
            node__id__in=visible_node_ids,
            is_available=True
        )
        
        collected_shares = []
        
        for fragment in visible_fragments:
            try:
                # In real implementation, this would request from BLE
                # For now, assume fragment is available
                share = Share(
                    index=fragment.fragment_index,
                    value=fragment.encrypted_fragment
                )
                collected_shares.append(share)
                
                # Mark as collected
                fragment.is_collected = True
                fragment.collected_at = timezone.now()
                fragment.collected_by = accessor
                fragment.save()
                
                result.fragments_collected += 1
                
            except Exception as e:
                result.errors.append(f"Failed to collect fragment {fragment.fragment_index}: {e}")
        
        # Check if we have enough fragments
        if result.fragments_collected >= dead_drop.required_fragments:
            try:
                # Reconstruct secret
                secret = self.shamir.reconstruct_secret(
                    collected_shares[:dead_drop.required_fragments],
                    expected_hash=dead_drop.secret_hash
                )
                result.reconstructed_secret = secret
                result.success = True
                
                # Mark dead drop as collected
                dead_drop.mark_collected(accessor)
                
            except Exception as e:
                result.errors.append(f"Reconstruction failed: {e}")
        else:
            result.errors.append(
                f"Insufficient fragments: {result.fragments_collected}/{dead_drop.required_fragments}"
            )
        
        return result
    
    def get_distribution_status(self, dead_drop: DeadDrop) -> Dict:
        """
        Get current distribution status of a dead drop.
        
        Returns:
            Dict with status information
        """
        fragments = dead_drop.fragments.all()
        
        distributed_count = fragments.filter(is_distributed=True).count()
        available_count = fragments.filter(is_available=True).count()
        collected_count = fragments.filter(is_collected=True).count()
        
        nodes_used = fragments.filter(node__isnull=False).values_list('node_id', flat=True).distinct()
        online_nodes = MeshNode.objects.filter(id__in=nodes_used, is_online=True).count()
        
        return {
            'total_fragments': dead_drop.total_fragments,
            'required_fragments': dead_drop.required_fragments,
            'distributed': distributed_count,
            'available': available_count,
            'collected': collected_count,
            'nodes_used': len(nodes_used),
            'nodes_online': online_nodes,
            'health': 'good' if available_count >= dead_drop.required_fragments else 'degraded',
            'status': dead_drop.status
        }
    
    def rebalance_fragments(self, dead_drop: DeadDrop) -> int:
        """
        Rebalance fragments when nodes go offline.
        
        Moves fragments from offline nodes to online ones.
        
        Returns:
            Number of fragments rebalanced
        """
        # Find fragments on offline nodes
        orphaned = DeadDropFragment.objects.filter(
            dead_drop=dead_drop,
            node__is_online=False,
            is_collected=False
        )
        
        if not orphaned.exists():
            return 0
        
        # Find available nodes
        available_nodes = list(MeshNode.objects.filter(
            is_online=True,
            is_available_for_storage=True
        ).exclude(
            current_fragment_count__gte=models.F('max_fragments')
        ))
        
        rebalanced = 0
        
        for fragment in orphaned:
            if available_nodes:
                target = random.choice(available_nodes)
                
                try:
                    old_node = fragment.node
                    self._assign_fragment_to_node(fragment, target)
                    
                    # Update old node count
                    if old_node:
                        old_node.current_fragment_count = max(0, old_node.current_fragment_count - 1)
                        old_node.save()
                    
                    rebalanced += 1
                except Exception:
                    pass
        
        return rebalanced


# Import models here to avoid circular imports
from django.db import models

# Module-level instance
fragment_distribution_service = FragmentDistributionService()

"""
Dark Protocol Service
=====================

Core orchestrator for the anonymous vault access network.

Provides:
- Session establishment with multi-layer encryption
- Path selection and rotation
- Traffic bundling (real + decoy operations)
- Censorship detection and circumvention

@author Password Manager Team
@created 2026-02-02
"""

import secrets
import logging
import hashlib
from datetime import timedelta
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass, field
from django.conf import settings
from django.utils import timezone
from django.db import transaction

from ..models.dark_protocol_models import (
    DarkProtocolNode,
    GarlicSession,
    CoverTrafficPattern,
    RoutingPath,
    TrafficBundle,
    NetworkHealth,
    DarkProtocolConfig,
)

logger = logging.getLogger(__name__)


# =============================================================================
# Configuration
# =============================================================================

def get_dark_protocol_config() -> Dict[str, Any]:
    """Get dark protocol configuration from settings."""
    return getattr(settings, 'DARK_PROTOCOL', {
        'ENABLED': True,
        'DEFAULT_HOP_COUNT': 3,
        'MAX_HOP_COUNT': 5,
        'SESSION_TIMEOUT_MINUTES': 30,
        'PATH_ROTATION_MINUTES': 5,
        'COVER_TRAFFIC_ENABLED': True,
        'COVER_TRAFFIC_RATE': 0.5,
        'MIN_NODE_TRUST_SCORE': 0.3,
        'USE_BRIDGE_NODES': False,
    })


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class SessionEstablishResult:
    """Result of establishing a garlic session."""
    success: bool
    session_id: Optional[str] = None
    session: Optional[GarlicSession] = None
    error_message: Optional[str] = None
    path_length: int = 0
    estimated_latency_ms: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'success': self.success,
            'session_id': self.session_id,
            'error_message': self.error_message,
            'path_length': self.path_length,
            'estimated_latency_ms': self.estimated_latency_ms,
        }


@dataclass
class EncryptedBundle:
    """An encrypted traffic bundle ready for transmission."""
    bundle_id: str
    encrypted_data: bytes
    layers: int
    size: int
    is_cover: bool = False
    sequence: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'bundle_id': self.bundle_id,
            'size': self.size,
            'layers': self.layers,
            'is_cover': self.is_cover,
            'sequence': self.sequence,
        }


@dataclass
class VaultOperationResult:
    """Result of a proxied vault operation."""
    success: bool
    operation_id: str
    response_data: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    latency_ms: int = 0
    path_used: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'success': self.success,
            'operation_id': self.operation_id,
            'response_data': self.response_data,
            'error_message': self.error_message,
            'latency_ms': self.latency_ms,
        }


# =============================================================================
# Dark Protocol Service
# =============================================================================

class DarkProtocolService:
    """
    Core service for the Dark Protocol anonymous vault access network.
    
    Orchestrates:
    - Session establishment with garlic routing
    - Path selection and rotation
    - Traffic bundling
    - Vault operation proxying
    """
    
    def __init__(self):
        self.config = get_dark_protocol_config()
        self._garlic_router = None
        self._noise_encryptor = None
        self._cover_generator = None
    
    @property
    def garlic_router(self):
        """Lazy load garlic router."""
        if self._garlic_router is None:
            from .garlic_router import GarlicRouter
            self._garlic_router = GarlicRouter()
        return self._garlic_router
    
    @property
    def noise_encryptor(self):
        """Lazy load noise encryptor."""
        if self._noise_encryptor is None:
            from .noise_encryptor import NoiseEncryptor
            self._noise_encryptor = NoiseEncryptor()
        return self._noise_encryptor
    
    @property
    def cover_generator(self):
        """Lazy load cover traffic generator."""
        if self._cover_generator is None:
            from .cover_traffic_generator import CoverTrafficGenerator
            self._cover_generator = CoverTrafficGenerator()
        return self._cover_generator
    
    # =========================================================================
    # Configuration Management
    # =========================================================================
    
    def get_or_create_config(self, user) -> DarkProtocolConfig:
        """Get or create user's dark protocol configuration."""
        config, created = DarkProtocolConfig.objects.get_or_create(
            user=user,
            defaults={
                'is_enabled': False,
                'cover_traffic_enabled': True,
                'cover_traffic_intensity': 0.5,
            }
        )
        if created:
            logger.info(f"Created dark protocol config for user {user.id}")
        return config
    
    def update_config(self, user, **kwargs) -> DarkProtocolConfig:
        """Update user's dark protocol configuration."""
        config = self.get_or_create_config(user)
        
        allowed_fields = [
            'is_enabled', 'auto_enable_on_threat', 'preferred_regions',
            'min_hops', 'max_hops', 'cover_traffic_enabled',
            'cover_traffic_intensity', 'session_timeout_minutes',
            'auto_path_rotation', 'path_rotation_interval_minutes',
            'use_bridge_nodes', 'require_verified_nodes',
        ]
        
        for field, value in kwargs.items():
            if field in allowed_fields:
                setattr(config, field, value)
        
        config.save()
        logger.info(f"Updated dark protocol config for user {user.id}")
        return config
    
    # =========================================================================
    # Session Management
    # =========================================================================
    
    def establish_session(
        self,
        user,
        hop_count: int = None,
        preferred_regions: List[str] = None,
    ) -> SessionEstablishResult:
        """
        Establish a new garlic routing session.
        
        Args:
            user: The user establishing the session
            hop_count: Number of hops (default from config)
            preferred_regions: Preferred geographic regions for nodes
            
        Returns:
            SessionEstablishResult with session details
        """
        try:
            config = self.get_or_create_config(user)
            
            # Determine hop count
            if hop_count is None:
                hop_count = config.min_hops
            hop_count = max(config.min_hops, min(hop_count, config.max_hops))
            
            # Get preferred regions
            if preferred_regions is None:
                preferred_regions = config.preferred_regions or []
            
            # Select nodes for path
            nodes = self._select_path_nodes(
                hop_count=hop_count,
                preferred_regions=preferred_regions,
                require_verified=config.require_verified_nodes,
                use_bridges=config.use_bridge_nodes,
            )
            
            if len(nodes) < hop_count:
                return SessionEstablishResult(
                    success=False,
                    error_message=f"Insufficient nodes available (found {len(nodes)}, need {hop_count})"
                )
            
            # Create session with garlic router
            session_id = secrets.token_hex(32)
            layer_keys, encrypted_path = self.garlic_router.create_circuit(
                nodes=nodes,
                session_id=session_id,
            )
            
            # Calculate estimated latency
            estimated_latency = sum(
                NetworkHealth.objects.filter(
                    node=node, is_reachable=True
                ).order_by('-checked_at').first().latency_ms or 50
                for node in nodes
            )
            
            # Create session record
            with transaction.atomic():
                session = GarlicSession.objects.create(
                    session_id=session_id,
                    user=user,
                    status='active',
                    encrypted_path=encrypted_path,
                    path_length=len(nodes),
                    layer_keys=layer_keys,
                    entry_node=nodes[0],
                    expires_at=timezone.now() + timedelta(
                        minutes=config.session_timeout_minutes
                    ),
                    is_verified=True,
                )
                
                # Update node circuit counts
                for node in nodes:
                    node.current_circuits += 1
                    node.save(update_fields=['current_circuits'])
            
            logger.info(
                f"Established dark protocol session {session_id[:8]}... "
                f"for user {user.id} with {len(nodes)} hops"
            )
            
            return SessionEstablishResult(
                success=True,
                session_id=session_id,
                session=session,
                path_length=len(nodes),
                estimated_latency_ms=estimated_latency,
            )
            
        except Exception as e:
            logger.error(f"Failed to establish session: {e}")
            return SessionEstablishResult(
                success=False,
                error_message=str(e)
            )
    
    def terminate_session(self, session_id: str, user) -> bool:
        """
        Terminate a garlic routing session.
        
        Args:
            session_id: The session to terminate
            user: The session owner
            
        Returns:
            True if terminated successfully
        """
        try:
            session = GarlicSession.objects.get(
                session_id=session_id,
                user=user,
            )
            
            if session.entry_node:
                session.entry_node.current_circuits = max(
                    0, session.entry_node.current_circuits - 1
                )
                session.entry_node.save(update_fields=['current_circuits'])
            
            session.status = 'terminated'
            session.save(update_fields=['status'])
            
            # Clean up associated paths
            RoutingPath.objects.filter(
                user=user,
                entry_node=session.entry_node,
                is_active=True,
            ).update(is_active=False)
            
            logger.info(f"Terminated session {session_id[:8]}...")
            return True
            
        except GarlicSession.DoesNotExist:
            logger.warning(f"Session {session_id[:8]}... not found")
            return False
        except Exception as e:
            logger.error(f"Error terminating session: {e}")
            return False
    
    def get_active_session(self, user) -> Optional[GarlicSession]:
        """Get user's active session if one exists."""
        return GarlicSession.objects.filter(
            user=user,
            status='active',
            expires_at__gt=timezone.now(),
        ).first()
    
    # =========================================================================
    # Path Management
    # =========================================================================
    
    def _select_path_nodes(
        self,
        hop_count: int,
        preferred_regions: List[str],
        require_verified: bool = True,
        use_bridges: bool = False,
    ) -> List[DarkProtocolNode]:
        """
        Select nodes for a routing path.
        
        Nodes are selected to maximize anonymity:
        - Different regions for each hop
        - High trust scores
        - Low current load
        - Good uptime
        """
        # Base query for available nodes
        nodes_qs = DarkProtocolNode.objects.filter(
            status='active',
            last_seen_at__gt=timezone.now() - timedelta(minutes=5),
        )
        
        if require_verified:
            nodes_qs = nodes_qs.filter(trust_score__gte=self.config.get('MIN_NODE_TRUST_SCORE', 0.3))
        
        # Select entry node (prefer bridges if enabled)
        if use_bridges:
            entry_candidates = nodes_qs.filter(node_type='bridge')
            if not entry_candidates.exists():
                entry_candidates = nodes_qs.filter(node_type='entry')
        else:
            entry_candidates = nodes_qs.filter(node_type='entry')
        
        # Apply region preference for entry
        if preferred_regions:
            preferred_entry = entry_candidates.filter(region__in=preferred_regions)
            if preferred_entry.exists():
                entry_candidates = preferred_entry
        
        entry_node = entry_candidates.order_by(
            '-trust_score', '-uptime_percentage', 'current_circuits'
        ).first()
        
        if not entry_node:
            return []
        
        selected_nodes = [entry_node]
        used_regions = {entry_node.region}
        
        # Select relay nodes
        for i in range(hop_count - 2):
            relay_candidates = nodes_qs.filter(
                node_type='relay'
            ).exclude(
                id__in=[n.id for n in selected_nodes]
            ).exclude(
                region__in=used_regions  # Different region for diversity
            )
            
            relay = relay_candidates.order_by(
                '-trust_score', '-uptime_percentage', 'current_circuits'
            ).first()
            
            if not relay:
                # Fallback: allow same region if necessary
                relay = nodes_qs.filter(
                    node_type='relay'
                ).exclude(
                    id__in=[n.id for n in selected_nodes]
                ).order_by(
                    '-trust_score', '-uptime_percentage'
                ).first()
            
            if relay:
                selected_nodes.append(relay)
                used_regions.add(relay.region)
        
        # Select destination node
        dest_candidates = nodes_qs.filter(
            node_type='destination'
        ).exclude(
            id__in=[n.id for n in selected_nodes]
        )
        
        destination = dest_candidates.order_by(
            '-trust_score', '-uptime_percentage', 'current_circuits'
        ).first()
        
        if destination:
            selected_nodes.append(destination)
        
        return selected_nodes
    
    def rotate_path(self, user) -> Optional[RoutingPath]:
        """
        Rotate the user's routing path for additional security.
        
        Creates a new path and marks old paths as inactive.
        """
        try:
            config = self.get_or_create_config(user)
            
            # Select new nodes
            nodes = self._select_path_nodes(
                hop_count=config.min_hops,
                preferred_regions=config.preferred_regions or [],
                require_verified=config.require_verified_nodes,
                use_bridges=config.use_bridge_nodes,
            )
            
            if not nodes:
                logger.warning(f"No nodes available for path rotation for user {user.id}")
                return None
            
            # Create encrypted path data
            path_data = self.garlic_router.create_path_data(nodes)
            
            with transaction.atomic():
                # Deactivate old paths
                RoutingPath.objects.filter(
                    user=user, is_active=True
                ).update(is_active=False, is_primary=False)
                
                # Create new path
                path = RoutingPath.objects.create(
                    user=user,
                    encrypted_path_data=path_data,
                    hop_count=len(nodes),
                    entry_node=nodes[0],
                    is_active=True,
                    is_primary=True,
                    expires_at=timezone.now() + timedelta(
                        minutes=config.path_rotation_interval_minutes
                    ),
                )
            
            logger.info(f"Rotated path for user {user.id}: {path.path_id[:8]}...")
            return path
            
        except Exception as e:
            logger.error(f"Path rotation failed: {e}")
            return None
    
    # =========================================================================
    # Traffic Operations
    # =========================================================================
    
    def proxy_vault_operation(
        self,
        user,
        operation: str,
        payload: Dict[str, Any],
        session_id: str = None,
    ) -> VaultOperationResult:
        """
        Proxy a vault operation through the dark protocol network.
        
        Args:
            user: The user performing the operation
            operation: The vault operation type
            payload: The operation payload
            session_id: Optional session ID (uses active session if not provided)
            
        Returns:
            VaultOperationResult with response data
        """
        operation_id = secrets.token_hex(16)
        start_time = timezone.now()
        
        try:
            # Get or establish session
            if session_id:
                session = GarlicSession.objects.get(
                    session_id=session_id,
                    user=user,
                    status='active',
                )
            else:
                session = self.get_active_session(user)
                if not session:
                    result = self.establish_session(user)
                    if not result.success:
                        return VaultOperationResult(
                            success=False,
                            operation_id=operation_id,
                            error_message=result.error_message,
                        )
                    session = result.session
            
            # Bundle the operation
            bundle = self._create_operation_bundle(
                session=session,
                operation=operation,
                payload=payload,
            )
            
            # Apply noise encryption
            noisy_bundle = self.noise_encryptor.apply_noise(bundle)
            
            # Send through garlic router
            response = self.garlic_router.send_bundle(
                session=session,
                bundle=noisy_bundle,
            )
            
            # Update session statistics
            session.bytes_sent += len(noisy_bundle.encrypted_data)
            session.messages_sent += 1
            session.save(update_fields=['bytes_sent', 'messages_sent', 'last_activity_at'])
            
            # Calculate latency
            latency_ms = int((timezone.now() - start_time).total_seconds() * 1000)
            
            return VaultOperationResult(
                success=True,
                operation_id=operation_id,
                response_data=response,
                latency_ms=latency_ms,
                path_used=session.session_id[:8],
            )
            
        except GarlicSession.DoesNotExist:
            return VaultOperationResult(
                success=False,
                operation_id=operation_id,
                error_message="Session not found or expired",
            )
        except Exception as e:
            logger.error(f"Vault operation proxy failed: {e}")
            return VaultOperationResult(
                success=False,
                operation_id=operation_id,
                error_message=str(e),
            )
    
    def _create_operation_bundle(
        self,
        session: GarlicSession,
        operation: str,
        payload: Dict[str, Any],
    ) -> TrafficBundle:
        """Create an encrypted traffic bundle for an operation."""
        import json
        
        # Serialize payload
        payload_bytes = json.dumps({
            'op': operation,
            'data': payload,
            'ts': timezone.now().isoformat(),
        }).encode()
        
        # Encrypt with garlic layers
        encrypted = self.garlic_router.encrypt_payload(
            session=session,
            payload=payload_bytes,
        )
        
        # Get next sequence number
        last_bundle = TrafficBundle.objects.filter(
            session=session
        ).order_by('-sequence_number').first()
        
        sequence = (last_bundle.sequence_number + 1) if last_bundle else 1
        
        # Create bundle
        bundle = TrafficBundle.objects.create(
            session=session,
            bundle_type='real',
            encrypted_payload=encrypted,
            payload_size=len(encrypted),
            sequence_number=sequence,
        )
        
        return bundle
    
    # =========================================================================
    # Network Health
    # =========================================================================
    
    def get_network_status(self) -> Dict[str, Any]:
        """Get overall network health status."""
        now = timezone.now()
        five_min_ago = now - timedelta(minutes=5)
        
        total_nodes = DarkProtocolNode.objects.count()
        active_nodes = DarkProtocolNode.objects.filter(
            status='active',
            last_seen_at__gt=five_min_ago,
        ).count()
        
        # Calculate average metrics
        recent_health = NetworkHealth.objects.filter(
            checked_at__gt=five_min_ago,
            is_reachable=True,
        )
        
        avg_latency = 0
        if recent_health.exists():
            avg_latency = sum(h.latency_ms for h in recent_health) / recent_health.count()
        
        # Get node distribution by type
        node_types = {}
        for node_type, _ in DarkProtocolNode.NODE_TYPE_CHOICES if hasattr(DarkProtocolNode, 'NODE_TYPE_CHOICES') else []:
            node_types[node_type] = DarkProtocolNode.objects.filter(
                node_type=node_type, status='active'
            ).count()
        
        return {
            'total_nodes': total_nodes,
            'active_nodes': active_nodes,
            'health_percentage': (active_nodes / total_nodes * 100) if total_nodes > 0 else 0,
            'average_latency_ms': int(avg_latency),
            'node_distribution': node_types,
            'checked_at': now.isoformat(),
        }
    
    def get_available_nodes(self, node_type: str = None) -> List[Dict[str, Any]]:
        """Get list of available nodes."""
        nodes_qs = DarkProtocolNode.objects.filter(
            status='active',
            last_seen_at__gt=timezone.now() - timedelta(minutes=5),
        )
        
        if node_type:
            nodes_qs = nodes_qs.filter(node_type=node_type)
        
        return [
            {
                'node_id': node.node_id,
                'type': node.node_type,
                'region': node.region,
                'trust_score': node.trust_score,
                'load_percentage': node.load_percentage,
                'is_available': node.is_available,
            }
            for node in nodes_qs.order_by('-trust_score')[:50]
        ]


# =============================================================================
# Service Singleton
# =============================================================================

_dark_protocol_service = None


def get_dark_protocol_service() -> DarkProtocolService:
    """Get the dark protocol service singleton."""
    global _dark_protocol_service
    if _dark_protocol_service is None:
        _dark_protocol_service = DarkProtocolService()
    return _dark_protocol_service

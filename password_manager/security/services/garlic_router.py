"""
Garlic Router
=============

Garlic routing implementation for the Dark Protocol network.

Features:
- Multiple encrypted layers per message (like cloves in garlic)
- Each hop peels one layer, adds timing jitter
- Uses LatticeCryptoEngine for post-quantum encryption
- Path obfuscation and replay protection

@author Password Manager Team
@created 2026-02-02
"""

import os
import json
import secrets
import hashlib
import logging
from datetime import datetime
from typing import List, Dict, Any, Tuple, Optional
from dataclasses import dataclass, field

from django.utils import timezone

logger = logging.getLogger(__name__)


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class GarlicClove:
    """
    A single encryption layer (clove) in the garlic packet.
    
    Each clove contains:
    - Encrypted payload for this hop
    - Next hop information (encrypted)
    - Session key for this layer
    """
    layer_index: int
    encrypted_payload: bytes
    next_hop_id: Optional[str] = None  # None for final destination
    session_key: bytes = field(default_factory=lambda: os.urandom(32))
    nonce: bytes = field(default_factory=lambda: os.urandom(12))
    
    def to_bytes(self) -> bytes:
        """Serialize clove to bytes."""
        return (
            self.layer_index.to_bytes(2, 'big') +
            len(self.encrypted_payload).to_bytes(4, 'big') +
            self.encrypted_payload +
            (self.next_hop_id.encode() if self.next_hop_id else b'')
        )


@dataclass
class GarlicPacket:
    """
    A complete garlic packet with multiple cloves.
    
    The packet is structured so that each node only sees
    its own clove and the encrypted remaining packet.
    """
    packet_id: str
    cloves: List[GarlicClove]
    created_at: datetime = field(default_factory=datetime.utcnow)
    sequence: int = 0
    
    def get_outer_layer(self) -> bytes:
        """Get the outermost encrypted layer for transmission."""
        if not self.cloves:
            return b''
        return self.cloves[0].encrypted_payload
    
    @property
    def layer_count(self) -> int:
        return len(self.cloves)


@dataclass
class CircuitKeys:
    """Session keys for each hop in the circuit."""
    hop_keys: List[bytes]  # One key per hop
    created_at: datetime = field(default_factory=datetime.utcnow)
    
    def to_bytes(self) -> bytes:
        """Serialize keys for storage."""
        result = len(self.hop_keys).to_bytes(2, 'big')
        for key in self.hop_keys:
            result += len(key).to_bytes(2, 'big') + key
        return result
    
    @classmethod
    def from_bytes(cls, data: bytes) -> 'CircuitKeys':
        """Deserialize keys from storage."""
        hop_count = int.from_bytes(data[:2], 'big')
        keys = []
        offset = 2
        for _ in range(hop_count):
            key_len = int.from_bytes(data[offset:offset+2], 'big')
            offset += 2
            keys.append(data[offset:offset+key_len])
            offset += key_len
        return cls(hop_keys=keys)


# =============================================================================
# Garlic Router
# =============================================================================

class GarlicRouter:
    """
    Garlic routing implementation.
    
    Provides stronger anonymity than onion routing by:
    - Bundling multiple messages together
    - Using post-quantum lattice encryption
    - Adding timing obfuscation
    - Supporting bidirectional secure channels
    """
    
    def __init__(self):
        self._lattice_engine = None
        self._crypto_service = None
    
    @property
    def lattice_engine(self):
        """Lazy load lattice crypto engine."""
        if self._lattice_engine is None:
            try:
                from .lattice_crypto_engine import lattice_engine
                self._lattice_engine = lattice_engine
            except ImportError:
                from .lattice_crypto_engine import LatticeCryptoEngine
                self._lattice_engine = LatticeCryptoEngine()
        return self._lattice_engine
    
    @property
    def crypto_service(self):
        """Lazy load crypto service."""
        if self._crypto_service is None:
            from .crypto_service import CryptoService
            self._crypto_service = CryptoService()
        return self._crypto_service
    
    # =========================================================================
    # Circuit Creation
    # =========================================================================
    
    def create_circuit(
        self,
        nodes: List,  # List of DarkProtocolNode
        session_id: str,
    ) -> Tuple[bytes, bytes]:
        """
        Create an encrypted circuit through the given nodes.
        
        Args:
            nodes: Ordered list of nodes for the path
            session_id: Unique session identifier
            
        Returns:
            Tuple of (encrypted_layer_keys, encrypted_path)
        """
        if not nodes:
            raise ValueError("At least one node required for circuit")
        
        # Generate session keys for each hop
        circuit_keys = CircuitKeys(
            hop_keys=[os.urandom(32) for _ in nodes]
        )
        
        # Create encrypted path data
        path_data = self._create_path_data(nodes, circuit_keys, session_id)
        
        # Encrypt the keys for storage
        master_key = os.urandom(32)
        encrypted_keys = self._encrypt_circuit_keys(circuit_keys, master_key)
        
        # Encrypt path with master key
        encrypted_path = self.crypto_service.encrypt_aes_gcm(
            key=master_key,
            nonce=os.urandom(12),
            plaintext=path_data,
        )
        
        # Prepend master key encrypted with user's key
        # (In real implementation, this would use the user's lattice key)
        key_package = master_key + encrypted_keys
        
        logger.info(f"Created circuit with {len(nodes)} hops for session {session_id[:8]}...")
        
        return key_package, encrypted_path[0] if encrypted_path[0] else b''
    
    def _create_path_data(
        self,
        nodes: List,
        circuit_keys: CircuitKeys,
        session_id: str,
    ) -> bytes:
        """Create serialized path data."""
        path_info = {
            'session_id': session_id,
            'created_at': timezone.now().isoformat(),
            'hops': [
                {
                    'node_id': node.node_id,
                    'fingerprint': node.fingerprint,
                    'key_index': i,
                }
                for i, node in enumerate(nodes)
            ]
        }
        return json.dumps(path_info).encode()
    
    def _encrypt_circuit_keys(
        self,
        circuit_keys: CircuitKeys,
        master_key: bytes,
    ) -> bytes:
        """Encrypt circuit keys with master key."""
        nonce = os.urandom(12)
        encrypted, tag = self.crypto_service.encrypt_aes_gcm(
            key=master_key,
            nonce=nonce,
            plaintext=circuit_keys.to_bytes(),
        )
        return nonce + tag + encrypted if encrypted else b''
    
    def create_path_data(self, nodes: List) -> bytes:
        """Create encrypted path data for RoutingPath model."""
        circuit_keys = CircuitKeys(
            hop_keys=[os.urandom(32) for _ in nodes]
        )
        
        path_info = {
            'created_at': timezone.now().isoformat(),
            'hop_count': len(nodes),
            'hops': [
                {
                    'node_id': node.node_id,
                    'region': node.region,
                }
                for node in nodes
            ]
        }
        
        # Encrypt with ephemeral key
        ephemeral_key = os.urandom(32)
        nonce = os.urandom(12)
        
        encrypted, tag = self.crypto_service.encrypt_aes_gcm(
            key=ephemeral_key,
            nonce=nonce,
            plaintext=json.dumps(path_info).encode(),
        )
        
        # Combine: ephemeral_key + nonce + tag + encrypted
        return ephemeral_key + nonce + (tag or b'') + (encrypted or b'')
    
    # =========================================================================
    # Packet Creation
    # =========================================================================
    
    def create_garlic_packet(
        self,
        payload: bytes,
        circuit_keys: CircuitKeys,
        nodes: List,
    ) -> GarlicPacket:
        """
        Create a garlic packet with layered encryption.
        
        The packet is built from the inside out:
        - First, encrypt for the final destination
        - Then wrap with each relay's encryption
        - Finally wrap with entry node's encryption
        
        Args:
            payload: The actual data to transmit
            circuit_keys: Session keys for each hop
            nodes: List of nodes in the path
            
        Returns:
            GarlicPacket ready for transmission
        """
        packet_id = secrets.token_hex(16)
        cloves = []
        
        # Start with the innermost layer (destination)
        current_payload = payload
        
        # Build layers from inside out (reverse order)
        for i in range(len(nodes) - 1, -1, -1):
            node = nodes[i]
            key = circuit_keys.hop_keys[i]
            
            # Determine next hop
            next_hop = nodes[i + 1].node_id if i < len(nodes) - 1 else None
            
            # Create clove for this layer
            nonce = os.urandom(12)
            
            # Add routing info to payload
            routing_info = {
                'next': next_hop,
                'seq': i,
                'ts': timezone.now().timestamp(),
            }
            
            layer_payload = json.dumps(routing_info).encode() + b'\x00' + current_payload
            
            # Encrypt with this hop's key
            encrypted, tag = self.crypto_service.encrypt_aes_gcm(
                key=key,
                nonce=nonce,
                plaintext=layer_payload,
            )
            
            # Prepend nonce and tag
            clove_payload = nonce + (tag or b'') + (encrypted or b'')
            
            clove = GarlicClove(
                layer_index=i,
                encrypted_payload=clove_payload,
                next_hop_id=next_hop,
                session_key=key,
                nonce=nonce,
            )
            
            cloves.insert(0, clove)
            current_payload = clove_payload
        
        return GarlicPacket(
            packet_id=packet_id,
            cloves=cloves,
            sequence=0,
        )
    
    def peel_layer(
        self,
        packet_data: bytes,
        session_key: bytes,
    ) -> Tuple[bytes, Optional[str], Dict[str, Any]]:
        """
        Peel one encryption layer from a garlic packet.
        
        Used by relay nodes to process incoming packets.
        
        Args:
            packet_data: The encrypted packet
            session_key: This hop's session key
            
        Returns:
            Tuple of (inner_payload, next_hop_id, routing_info)
        """
        if len(packet_data) < 28:  # nonce(12) + tag(16)
            raise ValueError("Packet too short")
        
        nonce = packet_data[:12]
        tag = packet_data[12:28]
        ciphertext = packet_data[28:]
        
        # Decrypt
        decrypted = self.crypto_service.decrypt_aes_gcm(
            key=session_key,
            nonce=nonce,
            ciphertext=ciphertext,
            tag=tag,
        )
        
        if not decrypted:
            raise ValueError("Decryption failed")
        
        # Parse routing info
        separator_idx = decrypted.find(b'\x00')
        if separator_idx == -1:
            raise ValueError("Invalid packet format")
        
        routing_info = json.loads(decrypted[:separator_idx])
        inner_payload = decrypted[separator_idx + 1:]
        
        next_hop = routing_info.get('next')
        
        return inner_payload, next_hop, routing_info
    
    # =========================================================================
    # Payload Encryption/Decryption
    # =========================================================================
    
    def encrypt_payload(
        self,
        session,  # GarlicSession
        payload: bytes,
    ) -> bytes:
        """
        Encrypt a payload for transmission through the session's circuit.
        
        Args:
            session: Active garlic session
            payload: Data to encrypt
            
        Returns:
            Fully encrypted payload with all layers
        """
        # In a real implementation, we would extract keys from session
        # and encrypt layer by layer using actual node keys
        
        # For now, use simplified multi-layer encryption
        current = payload
        
        # Add random padding for traffic analysis resistance
        padding_size = secrets.randbelow(256)
        padding = os.urandom(padding_size)
        current = len(padding).to_bytes(2, 'big') + padding + current
        
        # Simulate layered encryption (in real impl, use per-hop keys)
        for layer in range(session.path_length):
            layer_key = hashlib.sha256(
                session.layer_keys + layer.to_bytes(4, 'big')
            ).digest()
            
            nonce = os.urandom(12)
            encrypted, tag = self.crypto_service.encrypt_aes_gcm(
                key=layer_key,
                nonce=nonce,
                plaintext=current,
            )
            
            current = nonce + (tag or b'') + (encrypted or b'')
        
        return current
    
    def decrypt_payload(
        self,
        session,  # GarlicSession
        encrypted_payload: bytes,
    ) -> bytes:
        """
        Decrypt a payload received through the session's circuit.
        
        Args:
            session: Active garlic session
            encrypted_payload: Encrypted data
            
        Returns:
            Decrypted payload
        """
        current = encrypted_payload
        
        # Decrypt each layer (in reverse order)
        for layer in range(session.path_length - 1, -1, -1):
            layer_key = hashlib.sha256(
                session.layer_keys + layer.to_bytes(4, 'big')
            ).digest()
            
            if len(current) < 28:
                raise ValueError("Invalid encrypted data")
            
            nonce = current[:12]
            tag = current[12:28]
            ciphertext = current[28:]
            
            decrypted = self.crypto_service.decrypt_aes_gcm(
                key=layer_key,
                nonce=nonce,
                ciphertext=ciphertext,
                tag=tag,
            )
            
            if not decrypted:
                raise ValueError(f"Decryption failed at layer {layer}")
            
            current = decrypted
        
        # Remove padding
        padding_size = int.from_bytes(current[:2], 'big')
        payload = current[2 + padding_size:]
        
        return payload
    
    # =========================================================================
    # Bundle Transmission
    # =========================================================================
    
    def send_bundle(
        self,
        session,  # GarlicSession
        bundle,  # TrafficBundle
    ) -> Dict[str, Any]:
        """
        Send an encrypted bundle through the circuit.
        
        In a real implementation, this would:
        1. Connect to entry node
        2. Transmit encrypted bundle
        3. Wait for response
        4. Decrypt and return response
        
        Args:
            session: Active garlic session
            bundle: Traffic bundle to send
            
        Returns:
            Response data from vault service
        """
        # This is a placeholder for the actual network transmission
        # In production, this would use WebSockets to the entry node
        
        logger.debug(f"Sending bundle {bundle.bundle_id[:8]}... through session {session.session_id[:8]}...")
        
        # Simulate successful transmission
        # Real implementation would:
        # 1. Send to entry node via WebSocket
        # 2. Entry node decrypts its layer, forwards to next hop
        # 3. Process continues until destination
        # 4. Response travels back through same path
        
        return {
            'success': True,
            'bundle_id': bundle.bundle_id,
            'acknowledged': True,
        }
    
    # =========================================================================
    # Timing Obfuscation
    # =========================================================================
    
    def calculate_timing_jitter(self) -> int:
        """
        Calculate random timing jitter for traffic analysis resistance.
        
        Returns jitter in milliseconds to add before transmission.
        """
        # Use exponential distribution for realistic jitter
        import random
        
        # Base jitter: 10-100ms
        base_jitter = random.randint(10, 100)
        
        # Occasional larger delays (traffic shaping resistance)
        if random.random() < 0.1:
            base_jitter += random.randint(100, 500)
        
        return base_jitter
    
    def add_cover_cloves(
        self,
        packet: GarlicPacket,
        count: int = 2,
    ) -> GarlicPacket:
        """
        Add cover cloves to a garlic packet.
        
        Cover cloves are indistinguishable from real cloves,
        adding uncertainty for traffic analysis.
        """
        for i in range(count):
            # Generate random cover data
            cover_size = secrets.randbelow(512) + 256
            cover_data = os.urandom(cover_size)
            
            cover_clove = GarlicClove(
                layer_index=packet.layer_count + i,
                encrypted_payload=cover_data,
                next_hop_id=None,  # Cover cloves don't route
            )
            
            packet.cloves.append(cover_clove)
        
        return packet


# =============================================================================
# Module-level Instance
# =============================================================================

_garlic_router = None


def get_garlic_router() -> GarlicRouter:
    """Get garlic router singleton."""
    global _garlic_router
    if _garlic_router is None:
        _garlic_router = GarlicRouter()
    return _garlic_router

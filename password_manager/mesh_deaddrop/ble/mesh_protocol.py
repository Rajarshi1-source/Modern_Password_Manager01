"""
BLE Mesh Protocol Implementation
=================================

Implements the mesh networking protocol for dead drop fragment distribution.
Based on Bluetooth Mesh standard with custom extensions for:
- Fragment storage and retrieval
- Anonymous node discovery
- Encrypted payload transmission
- Location challenges

Protocol Overview:
- Uses BLE advertising for node discovery
- GATT for reliable fragment transfer
- Custom MTU negotiation for large fragments
- End-to-end encryption (X25519 + XChaCha20)

@author Password Manager Team
@created 2026-01-22
"""

import struct
import uuid
import hashlib
import secrets
from enum import IntEnum
from typing import Optional, Tuple, List, Dict, Any
from dataclasses import dataclass, field
from datetime import datetime

from django.utils import timezone


# =============================================================================
# Protocol Constants
# =============================================================================

# BLE UUIDs for mesh service
MESH_SERVICE_UUID = "0000dead-0000-1000-8000-00805f9b34fb"
FRAGMENT_CHAR_UUID = "0000f001-0000-1000-8000-00805f9b34fb"
COMMAND_CHAR_UUID = "0000f002-0000-1000-8000-00805f9b34fb"
STATUS_CHAR_UUID = "0000f003-0000-1000-8000-00805f9b34fb"

# Protocol version
PROTOCOL_VERSION = 1

# Message size limits
MAX_MESSAGE_SIZE = 512
MAX_FRAGMENT_SIZE = 4096
MAX_PAYLOAD_SIZE = MAX_MESSAGE_SIZE - 32  # Header overhead

# Timeouts (seconds)
MESSAGE_TIMEOUT = 30
TRANSFER_TIMEOUT = 120
NODE_TIMEOUT = 600  # 10 minutes


# =============================================================================
# Message Types
# =============================================================================

class MeshMessageType(IntEnum):
    """Types of messages in the mesh protocol."""
    
    # Node discovery
    NODE_ANNOUNCE = 0x01      # Announce node availability
    NODE_QUERY = 0x02         # Query for nearby nodes
    NODE_RESPONSE = 0x03      # Response to query
    
    # Fragment operations
    FRAGMENT_STORE = 0x10     # Request to store a fragment
    FRAGMENT_STORE_ACK = 0x11 # Acknowledge fragment stored
    FRAGMENT_REQUEST = 0x12   # Request a fragment
    FRAGMENT_RESPONSE = 0x13  # Fragment data response
    FRAGMENT_DELETE = 0x14    # Request to delete fragment
    
    # Location verification
    LOCATION_CHALLENGE = 0x20   # Challenge for location proof
    LOCATION_RESPONSE = 0x21    # Response to location challenge
    PRESENCE_PROOF = 0x22       # Proof of physical presence
    
    # Status & control
    PING = 0x30              # Keepalive ping
    PONG = 0x31              # Ping response
    ERROR = 0xE0             # Error message
    
    # Transfer control
    TRANSFER_START = 0x40    # Start large transfer
    TRANSFER_CHUNK = 0x41    # Transfer chunk
    TRANSFER_END = 0x42      # End transfer
    TRANSFER_ACK = 0x43      # Acknowledge chunk


class MeshErrorCode(IntEnum):
    """Error codes for mesh protocol."""
    
    SUCCESS = 0x00
    INVALID_MESSAGE = 0x01
    UNKNOWN_DROP = 0x02
    FRAGMENT_NOT_FOUND = 0x03
    STORAGE_FULL = 0x04
    LOCATION_FAILED = 0x05
    ENCRYPTION_ERROR = 0x06
    TIMEOUT = 0x07
    NOT_AUTHORIZED = 0x08
    RATE_LIMITED = 0x09
    INTERNAL_ERROR = 0xFF


# =============================================================================
# Message Data Structures
# =============================================================================

@dataclass
class MeshMessageHeader:
    """Header for all mesh messages."""
    
    version: int = PROTOCOL_VERSION
    message_type: MeshMessageType = MeshMessageType.PING
    message_id: bytes = field(default_factory=lambda: secrets.token_bytes(8))
    timestamp: int = field(default_factory=lambda: int(timezone.now().timestamp()))
    payload_length: int = 0
    
    def to_bytes(self) -> bytes:
        """Serialize header to bytes."""
        return struct.pack(
            '<BBQIH',
            self.version,
            self.message_type,
            int.from_bytes(self.message_id[:8], 'little'),
            self.timestamp,
            self.payload_length
        )
    
    @classmethod
    def from_bytes(cls, data: bytes) -> 'MeshMessageHeader':
        """Deserialize header from bytes."""
        version, msg_type, msg_id, timestamp, payload_len = struct.unpack('<BBQIH', data[:16])
        return cls(
            version=version,
            message_type=MeshMessageType(msg_type),
            message_id=msg_id.to_bytes(8, 'little'),
            timestamp=timestamp,
            payload_length=payload_len
        )
    
    @staticmethod
    def size() -> int:
        return 16


@dataclass
class MeshMessage:
    """Complete mesh message with header and payload."""
    
    header: MeshMessageHeader
    payload: bytes = b''
    signature: bytes = b''  # Optional HMAC signature
    
    def to_bytes(self) -> bytes:
        """Serialize message to bytes."""
        self.header.payload_length = len(self.payload)
        data = self.header.to_bytes() + self.payload
        if self.signature:
            data += self.signature
        return data
    
    @classmethod
    def from_bytes(cls, data: bytes) -> 'MeshMessage':
        """Deserialize message from bytes."""
        header = MeshMessageHeader.from_bytes(data[:16])
        payload_end = 16 + header.payload_length
        payload = data[16:payload_end]
        signature = data[payload_end:] if len(data) > payload_end else b''
        return cls(header=header, payload=payload, signature=signature)


@dataclass
class NodeAnnounce:
    """Node announcement payload."""
    
    node_id: bytes  # 16 bytes UUID
    public_key: bytes  # 32 bytes X25519
    capabilities: int  # Bitfield of capabilities
    available_slots: int
    rssi_hint: int  # Signal strength hint
    
    CAP_STORAGE = 0x01  # Can store fragments
    CAP_RELAY = 0x02    # Can relay messages
    CAP_NFC = 0x04      # Has NFC capability
    
    def to_bytes(self) -> bytes:
        return struct.pack('<16s32sBBb',
            self.node_id,
            self.public_key,
            self.capabilities,
            self.available_slots,
            self.rssi_hint
        )
    
    @classmethod
    def from_bytes(cls, data: bytes) -> 'NodeAnnounce':
        node_id, pub_key, caps, slots, rssi = struct.unpack('<16s32sBBb', data[:52])
        return cls(
            node_id=node_id,
            public_key=pub_key,
            capabilities=caps,
            available_slots=slots,
            rssi_hint=rssi
        )


@dataclass
class FragmentStoreRequest:
    """Request to store a fragment on a node."""
    
    drop_id: bytes  # 16 bytes UUID
    fragment_index: int
    fragment_hash: bytes  # 32 bytes BLAKE3
    encrypted_fragment: bytes
    ttl_hours: int  # Time to live
    
    def to_bytes(self) -> bytes:
        header = struct.pack('<16sB32sH',
            self.drop_id,
            self.fragment_index,
            self.fragment_hash,
            self.ttl_hours
        )
        length = struct.pack('<I', len(self.encrypted_fragment))
        return header + length + self.encrypted_fragment
    
    @classmethod
    def from_bytes(cls, data: bytes) -> 'FragmentStoreRequest':
        drop_id, idx, frag_hash, ttl = struct.unpack('<16sB32sH', data[:51])
        frag_len = struct.unpack('<I', data[51:55])[0]
        fragment = data[55:55+frag_len]
        return cls(
            drop_id=drop_id,
            fragment_index=idx,
            fragment_hash=frag_hash,
            encrypted_fragment=fragment,
            ttl_hours=ttl
        )


@dataclass
class FragmentRequest:
    """Request to retrieve a fragment."""
    
    drop_id: bytes  # 16 bytes UUID
    fragment_index: int
    requester_public_key: bytes  # 32 bytes
    location_proof: Optional[bytes] = None  # Optional proof of location
    
    def to_bytes(self) -> bytes:
        data = struct.pack('<16sB32s',
            self.drop_id,
            self.fragment_index,
            self.requester_public_key
        )
        if self.location_proof:
            data += struct.pack('<H', len(self.location_proof))
            data += self.location_proof
        else:
            data += struct.pack('<H', 0)
        return data
    
    @classmethod
    def from_bytes(cls, data: bytes) -> 'FragmentRequest':
        drop_id, idx, pub_key = struct.unpack('<16sB32s', data[:49])
        proof_len = struct.unpack('<H', data[49:51])[0]
        proof = data[51:51+proof_len] if proof_len > 0 else None
        return cls(
            drop_id=drop_id,
            fragment_index=idx,
            requester_public_key=pub_key,
            location_proof=proof
        )


@dataclass
class LocationChallenge:
    """Challenge for location verification."""
    
    challenge_id: bytes  # 16 bytes
    node_id: bytes  # 16 bytes
    nonce: bytes  # 32 bytes random
    timestamp: int
    required_ble_nodes: List[bytes]  # List of node IDs that must be visible
    
    def to_bytes(self) -> bytes:
        header = struct.pack('<16s16s32sIB',
            self.challenge_id,
            self.node_id,
            self.nonce,
            self.timestamp,
            len(self.required_ble_nodes)
        )
        nodes = b''.join(self.required_ble_nodes)
        return header + nodes
    
    @classmethod
    def from_bytes(cls, data: bytes) -> 'LocationChallenge':
        challenge_id, node_id, nonce, ts, num_nodes = struct.unpack('<16s16s32sIB', data[:69])
        nodes = []
        offset = 69
        for _ in range(num_nodes):
            nodes.append(data[offset:offset+16])
            offset += 16
        return cls(
            challenge_id=challenge_id,
            node_id=node_id,
            nonce=nonce,
            timestamp=ts,
            required_ble_nodes=nodes
        )


# =============================================================================
# Mesh Protocol Handler
# =============================================================================

class MeshProtocol:
    """
    Handler for mesh network protocol operations.
    
    Usage:
        protocol = MeshProtocol()
        
        # Create announcement
        announce = protocol.create_node_announce(node_id, public_key, slots=5)
        
        # Parse incoming message
        message = protocol.parse_message(raw_data)
        
        # Handle fragment request
        response = protocol.handle_fragment_request(request, stored_fragments)
    """
    
    def __init__(self):
        """Initialize protocol handler."""
        self.pending_challenges: Dict[bytes, LocationChallenge] = {}
        self.message_cache: Dict[bytes, datetime] = {}  # For dedup
    
    # =========================================================================
    # Message Creation
    # =========================================================================
    
    def create_node_announce(
        self,
        node_id: bytes,
        public_key: bytes,
        available_slots: int = 10,
        capabilities: int = NodeAnnounce.CAP_STORAGE | NodeAnnounce.CAP_RELAY,
        rssi_hint: int = -50
    ) -> MeshMessage:
        """Create a node announcement message."""
        announce = NodeAnnounce(
            node_id=node_id,
            public_key=public_key,
            capabilities=capabilities,
            available_slots=available_slots,
            rssi_hint=rssi_hint
        )
        
        header = MeshMessageHeader(message_type=MeshMessageType.NODE_ANNOUNCE)
        return MeshMessage(header=header, payload=announce.to_bytes())
    
    def create_fragment_store_request(
        self,
        drop_id: bytes,
        fragment_index: int,
        encrypted_fragment: bytes,
        ttl_hours: int = 168
    ) -> MeshMessage:
        """Create a fragment storage request message."""
        fragment_hash = hashlib.blake2b(encrypted_fragment, digest_size=32).digest()
        
        request = FragmentStoreRequest(
            drop_id=drop_id,
            fragment_index=fragment_index,
            fragment_hash=fragment_hash,
            encrypted_fragment=encrypted_fragment,
            ttl_hours=ttl_hours
        )
        
        header = MeshMessageHeader(message_type=MeshMessageType.FRAGMENT_STORE)
        return MeshMessage(header=header, payload=request.to_bytes())
    
    def create_fragment_request(
        self,
        drop_id: bytes,
        fragment_index: int,
        requester_public_key: bytes,
        location_proof: Optional[bytes] = None
    ) -> MeshMessage:
        """Create a fragment retrieval request message."""
        request = FragmentRequest(
            drop_id=drop_id,
            fragment_index=fragment_index,
            requester_public_key=requester_public_key,
            location_proof=location_proof
        )
        
        header = MeshMessageHeader(message_type=MeshMessageType.FRAGMENT_REQUEST)
        return MeshMessage(header=header, payload=request.to_bytes())
    
    def create_location_challenge(
        self,
        node_id: bytes,
        required_ble_nodes: List[bytes] = None
    ) -> MeshMessage:
        """Create a location verification challenge."""
        challenge = LocationChallenge(
            challenge_id=secrets.token_bytes(16),
            node_id=node_id,
            nonce=secrets.token_bytes(32),
            timestamp=int(timezone.now().timestamp()),
            required_ble_nodes=required_ble_nodes or []
        )
        
        # Cache challenge for later verification
        self.pending_challenges[challenge.challenge_id] = challenge
        
        header = MeshMessageHeader(message_type=MeshMessageType.LOCATION_CHALLENGE)
        return MeshMessage(header=header, payload=challenge.to_bytes())
    
    def create_ping(self) -> MeshMessage:
        """Create a ping message."""
        header = MeshMessageHeader(message_type=MeshMessageType.PING)
        return MeshMessage(header=header, payload=b'')
    
    def create_pong(self, ping_id: bytes) -> MeshMessage:
        """Create a pong response."""
        header = MeshMessageHeader(message_type=MeshMessageType.PONG)
        return MeshMessage(header=header, payload=ping_id)
    
    def create_error(self, error_code: MeshErrorCode, message: str = '') -> MeshMessage:
        """Create an error message."""
        payload = struct.pack('<B', error_code) + message.encode()[:255]
        header = MeshMessageHeader(message_type=MeshMessageType.ERROR)
        return MeshMessage(header=header, payload=payload)
    
    # =========================================================================
    # Message Parsing
    # =========================================================================
    
    def parse_message(self, data: bytes) -> Optional[MeshMessage]:
        """
        Parse raw bytes into a mesh message.
        
        Args:
            data: Raw bytes received
            
        Returns:
            MeshMessage or None if invalid
        """
        if len(data) < MeshMessageHeader.size():
            return None
        
        try:
            message = MeshMessage.from_bytes(data)
            
            # Validate version
            if message.header.version != PROTOCOL_VERSION:
                return None
            
            # Check message age (reject old messages)
            age = int(timezone.now().timestamp()) - message.header.timestamp
            if abs(age) > MESSAGE_TIMEOUT:
                return None
            
            # Deduplicate
            msg_id = message.header.message_id
            if msg_id in self.message_cache:
                return None
            self.message_cache[msg_id] = timezone.now()
            
            # Clean old cache entries
            self._cleanup_cache()
            
            return message
        except Exception:
            return None
    
    def parse_node_announce(self, message: MeshMessage) -> Optional[NodeAnnounce]:
        """Parse a node announcement from message."""
        if message.header.message_type != MeshMessageType.NODE_ANNOUNCE:
            return None
        return NodeAnnounce.from_bytes(message.payload)
    
    def parse_fragment_store_request(self, message: MeshMessage) -> Optional[FragmentStoreRequest]:
        """Parse a fragment store request from message."""
        if message.header.message_type != MeshMessageType.FRAGMENT_STORE:
            return None
        return FragmentStoreRequest.from_bytes(message.payload)
    
    def parse_fragment_request(self, message: MeshMessage) -> Optional[FragmentRequest]:
        """Parse a fragment request from message."""
        if message.header.message_type != MeshMessageType.FRAGMENT_REQUEST:
            return None
        return FragmentRequest.from_bytes(message.payload)
    
    # =========================================================================
    # Message Handling
    # =========================================================================
    
    def handle_fragment_store(
        self,
        request: FragmentStoreRequest,
        storage_callback
    ) -> MeshMessage:
        """
        Handle a fragment storage request.
        
        Args:
            request: The storage request
            storage_callback: Function to actually store the fragment
            
        Returns:
            Acknowledgement or error message
        """
        try:
            # Verify fragment hash
            computed_hash = hashlib.blake2b(request.encrypted_fragment, digest_size=32).digest()
            if computed_hash != request.fragment_hash:
                return self.create_error(MeshErrorCode.ENCRYPTION_ERROR, "Hash mismatch")
            
            # Attempt storage
            success = storage_callback(
                drop_id=request.drop_id,
                fragment_index=request.fragment_index,
                fragment_data=request.encrypted_fragment,
                ttl_hours=request.ttl_hours
            )
            
            if success:
                header = MeshMessageHeader(message_type=MeshMessageType.FRAGMENT_STORE_ACK)
                ack_payload = struct.pack('<16sB', request.drop_id, request.fragment_index)
                return MeshMessage(header=header, payload=ack_payload)
            else:
                return self.create_error(MeshErrorCode.STORAGE_FULL, "No storage available")
                
        except Exception as e:
            return self.create_error(MeshErrorCode.INTERNAL_ERROR, str(e)[:100])
    
    def handle_fragment_request(
        self,
        request: FragmentRequest,
        retrieve_callback,
        verify_location: bool = True
    ) -> MeshMessage:
        """
        Handle a fragment retrieval request.
        
        Args:
            request: The retrieval request
            retrieve_callback: Function to retrieve fragment
            verify_location: Whether to verify location proof
            
        Returns:
            Fragment data or error message
        """
        try:
            # Optionally verify location proof
            if verify_location and request.location_proof:
                if not self._verify_location_proof(request.location_proof):
                    return self.create_error(MeshErrorCode.LOCATION_FAILED, "Location verification failed")
            
            # Retrieve fragment
            fragment_data = retrieve_callback(
                drop_id=request.drop_id,
                fragment_index=request.fragment_index
            )
            
            if fragment_data is None:
                return self.create_error(MeshErrorCode.FRAGMENT_NOT_FOUND, "Fragment not found")
            
            # Build response
            header = MeshMessageHeader(message_type=MeshMessageType.FRAGMENT_RESPONSE)
            payload = struct.pack('<16sB', request.drop_id, request.fragment_index)
            payload += struct.pack('<I', len(fragment_data))
            payload += fragment_data
            
            return MeshMessage(header=header, payload=payload)
            
        except Exception as e:
            return self.create_error(MeshErrorCode.INTERNAL_ERROR, str(e)[:100])
    
    def verify_location_response(
        self,
        challenge_id: bytes,
        response: bytes,
        visible_nodes: List[bytes]
    ) -> bool:
        """
        Verify a location challenge response.
        
        Args:
            challenge_id: ID of the challenge
            response: Response signature
            visible_nodes: List of BLE node IDs that were visible
            
        Returns:
            True if location is verified
        """
        challenge = self.pending_challenges.get(challenge_id)
        if not challenge:
            return False
        
        # Check if required nodes are visible
        required_set = set(n.hex() for n in challenge.required_ble_nodes)
        visible_set = set(n.hex() for n in visible_nodes)
        
        if not required_set.issubset(visible_set):
            return False
        
        # Verify response signature
        expected = hashlib.blake2b(
            challenge.nonce + b''.join(sorted(visible_nodes)),
            digest_size=32
        ).digest()
        
        if response != expected:
            return False
        
        # Remove used challenge
        del self.pending_challenges[challenge_id]
        
        return True
    
    def _verify_location_proof(self, proof: bytes) -> bool:
        """Verify a location proof blob."""
        # Extract and verify proof components
        try:
            # Proof format: challenge_id (16) + signature (32) + visible_count (1) + visible_nodes (16 each)
            if len(proof) < 49:
                return False
            
            challenge_id = proof[:16]
            signature = proof[16:48]
            visible_count = proof[48]
            visible_nodes = []
            
            offset = 49
            for _ in range(visible_count):
                visible_nodes.append(proof[offset:offset+16])
                offset += 16
            
            return self.verify_location_response(challenge_id, signature, visible_nodes)
        except Exception:
            return False
    
    def _cleanup_cache(self):
        """Remove old entries from message cache."""
        now = timezone.now()
        old_keys = [
            k for k, v in self.message_cache.items()
            if (now - v).total_seconds() > MESSAGE_TIMEOUT
        ]
        for k in old_keys:
            del self.message_cache[k]
        
        # Also cleanup old challenges
        old_challenges = [
            k for k, v in self.pending_challenges.items()
            if int(now.timestamp()) - v.timestamp > MESSAGE_TIMEOUT
        ]
        for k in old_challenges:
            del self.pending_challenges[k]


# =============================================================================
# Module Instance
# =============================================================================

mesh_protocol = MeshProtocol()

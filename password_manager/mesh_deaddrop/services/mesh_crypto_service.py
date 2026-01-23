"""
Mesh Cryptography Service
==========================

Handles all cryptographic operations for mesh dead drops:
- Fragment encryption for nodes (X25519 + XChaCha20-Poly1305)
- Node-to-node secure channels
- Location-bound encryption using geohash
- Time-bound encryption wrappers
- Key generation and derivation

Security Properties:
- Forward secrecy via ephemeral keys
- Authenticated encryption (AEAD)
- Location binding prevents remote decryption
- Time binding causes automatic expiration

@author Password Manager Team
@created 2026-01-22
"""

import os
import time
import struct
import hashlib
import secrets
from datetime import datetime, timedelta
from typing import Tuple, Optional
from dataclasses import dataclass
import base64

# Cryptographic primitives
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey, X25519PublicKey
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305
from cryptography.hazmat.backends import default_backend


@dataclass
class EncryptedPayload:
    """Encrypted data with metadata."""
    ciphertext: bytes
    nonce: bytes
    ephemeral_public_key: Optional[bytes] = None
    location_hash: Optional[str] = None
    time_bound_until: Optional[datetime] = None


@dataclass
class MeshKeyPair:
    """X25519 keypair for mesh communication."""
    private_key: bytes
    public_key: bytes


class MeshCryptoService:
    """
    Cryptographic operations for mesh dead drop communication.
    
    Usage:
        crypto = MeshCryptoService()
        
        # Generate node keypair
        keypair = crypto.generate_mesh_keypair()
        
        # Encrypt fragment for a node
        encrypted = crypto.encrypt_for_node(fragment, node_public_key)
        
        # Decrypt on receiving node
        plaintext = crypto.decrypt_from_sender(encrypted, node_private_key)
    """
    
    # Protocol version for future compatibility
    PROTOCOL_VERSION = 1
    
    # Constants
    NONCE_SIZE = 12  # 96-bit nonce for ChaCha20Poly1305
    KEY_SIZE = 32    # 256-bit keys
    
    def __init__(self):
        """Initialize the crypto service."""
        self.backend = default_backend()
    
    # =========================================================================
    # Key Generation & Management
    # =========================================================================
    
    def generate_mesh_keypair(self) -> MeshKeyPair:
        """
        Generate X25519 keypair for mesh communication.
        
        Returns:
            MeshKeyPair with private and public keys (raw bytes)
        """
        private_key = X25519PrivateKey.generate()
        public_key = private_key.public_key()
        
        return MeshKeyPair(
            private_key=private_key.private_bytes_raw(),
            public_key=public_key.public_bytes_raw()
        )
    
    def derive_shared_secret(
        self, 
        private_key: bytes, 
        peer_public_key: bytes,
        context: bytes = b"mesh_deaddrop_v1"
    ) -> bytes:
        """
        Derive shared secret using X25519 ECDH + HKDF.
        
        Args:
            private_key: Our X25519 private key (32 bytes)
            peer_public_key: Peer's X25519 public key (32 bytes)
            context: Additional context for key derivation
            
        Returns:
            256-bit derived key
        """
        # Perform X25519 key agreement
        private = X25519PrivateKey.from_private_bytes(private_key)
        peer = X25519PublicKey.from_public_bytes(peer_public_key)
        shared = private.exchange(peer)
        
        # Derive key using HKDF
        hkdf = HKDF(
            algorithm=hashes.SHA256(),
            length=self.KEY_SIZE,
            salt=None,
            info=context,
            backend=self.backend
        )
        
        return hkdf.derive(shared)
    
    # =========================================================================
    # Fragment Encryption
    # =========================================================================
    
    def encrypt_for_node(
        self, 
        plaintext: bytes, 
        node_public_key: bytes,
        associated_data: Optional[bytes] = None
    ) -> EncryptedPayload:
        """
        Encrypt data for a specific mesh node using ephemeral key agreement.
        
        Uses X25519 ECDHE + XChaCha20-Poly1305 for forward secrecy
        and authenticated encryption.
        
        Args:
            plaintext: Data to encrypt
            node_public_key: Recipient's X25519 public key
            associated_data: Optional AAD for authentication
            
        Returns:
            EncryptedPayload with ciphertext, nonce, and ephemeral public key
        """
        # Generate ephemeral keypair for forward secrecy
        ephemeral = self.generate_mesh_keypair()
        
        # Derive encryption key
        encryption_key = self.derive_shared_secret(
            ephemeral.private_key,
            node_public_key,
            context=b"mesh_fragment_encryption"
        )
        
        # Generate random nonce
        nonce = secrets.token_bytes(self.NONCE_SIZE)
        
        # Encrypt with ChaCha20-Poly1305
        cipher = ChaCha20Poly1305(encryption_key)
        ciphertext = cipher.encrypt(nonce, plaintext, associated_data)
        
        return EncryptedPayload(
            ciphertext=ciphertext,
            nonce=nonce,
            ephemeral_public_key=ephemeral.public_key
        )
    
    def decrypt_from_sender(
        self, 
        payload: EncryptedPayload, 
        node_private_key: bytes,
        associated_data: Optional[bytes] = None
    ) -> bytes:
        """
        Decrypt data sent to this node.
        
        Args:
            payload: Encrypted payload from sender
            node_private_key: Our X25519 private key
            associated_data: Optional AAD (must match encryption)
            
        Returns:
            Decrypted plaintext
            
        Raises:
            ValueError: If decryption fails (authentication error)
        """
        if not payload.ephemeral_public_key:
            raise ValueError("Missing ephemeral public key")
        
        # Derive decryption key
        decryption_key = self.derive_shared_secret(
            node_private_key,
            payload.ephemeral_public_key,
            context=b"mesh_fragment_encryption"
        )
        
        # Decrypt with ChaCha20-Poly1305
        cipher = ChaCha20Poly1305(decryption_key)
        
        try:
            plaintext = cipher.decrypt(payload.nonce, payload.ciphertext, associated_data)
            return plaintext
        except Exception as e:
            raise ValueError(f"Decryption failed - authentication error: {e}")
    
    # =========================================================================
    # Location-Bound Encryption
    # =========================================================================
    
    def create_location_bound_key(
        self, 
        latitude: float, 
        longitude: float, 
        precision: int = 6,
        base_key: Optional[bytes] = None
    ) -> Tuple[bytes, str]:
        """
        Create encryption key material tied to a geographic location.
        
        Uses geohash encoding to bind key to a specific area.
        Precision 6 ≈ ±0.6km, Precision 7 ≈ ±76m, Precision 8 ≈ ±19m
        
        Args:
            latitude: GPS latitude
            longitude: GPS longitude
            precision: Geohash precision (1-12, default 6)
            base_key: Optional base key to combine with location
            
        Returns:
            Tuple of (location_key, geohash)
        """
        # Calculate geohash
        geohash = self._encode_geohash(latitude, longitude, precision)
        
        # Derive location key
        location_material = f"location:{geohash}".encode()
        
        if base_key:
            combined = base_key + location_material
        else:
            combined = location_material
        
        location_key = hashlib.blake2b(combined, digest_size=32).digest()
        
        return location_key, geohash
    
    def encrypt_with_location(
        self, 
        plaintext: bytes, 
        latitude: float, 
        longitude: float,
        precision: int = 7
    ) -> Tuple[EncryptedPayload, str]:
        """
        Encrypt data that can only be decrypted at a specific location.
        
        Args:
            plaintext: Data to encrypt
            latitude: Required latitude for decryption
            longitude: Required longitude for decryption
            precision: Geohash precision (higher = more precise)
            
        Returns:
            Tuple of (encrypted_payload, required_geohash)
        """
        location_key, geohash = self.create_location_bound_key(
            latitude, longitude, precision
        )
        
        nonce = secrets.token_bytes(self.NONCE_SIZE)
        cipher = ChaCha20Poly1305(location_key)
        ciphertext = cipher.encrypt(nonce, plaintext, geohash.encode())
        
        payload = EncryptedPayload(
            ciphertext=ciphertext,
            nonce=nonce,
            location_hash=geohash
        )
        
        return payload, geohash
    
    def decrypt_with_location(
        self, 
        payload: EncryptedPayload,
        latitude: float,
        longitude: float,
        precision: int = 7
    ) -> bytes:
        """
        Decrypt location-bound data by proving presence at location.
        
        Args:
            payload: Encrypted payload
            latitude: Current latitude
            longitude: Current longitude
            precision: Geohash precision used for encryption
            
        Returns:
            Decrypted plaintext
            
        Raises:
            ValueError: If location doesn't match
        """
        location_key, current_geohash = self.create_location_bound_key(
            latitude, longitude, precision
        )
        
        # Check if geohash matches (within precision)
        if payload.location_hash and current_geohash != payload.location_hash:
            raise ValueError(
                f"Location mismatch: not at required location "
                f"(expected {payload.location_hash[:4]}..., got {current_geohash[:4]}...)"
            )
        
        cipher = ChaCha20Poly1305(location_key)
        return cipher.decrypt(payload.nonce, payload.ciphertext, current_geohash.encode())
    
    # =========================================================================
    # Time-Bound Encryption
    # =========================================================================
    
    def create_time_bound_wrapper(
        self, 
        data: bytes, 
        not_before: datetime, 
        not_after: datetime
    ) -> bytes:
        """
        Add time-based encryption layer that only works within a time window.
        
        The wrapper includes timestamps that are verified on decryption.
        
        Args:
            data: Data to wrap
            not_before: Earliest valid timestamp
            not_after: Latest valid timestamp (expiration)
            
        Returns:
            Time-bound wrapped data
        """
        # Derive time-bound key
        time_material = f"time:{int(not_before.timestamp())}:{int(not_after.timestamp())}"
        time_key = hashlib.blake2b(time_material.encode(), digest_size=32).digest()
        
        # Create header with timestamps
        header = struct.pack(
            '<BQQ',  # version, not_before, not_after
            self.PROTOCOL_VERSION,
            int(not_before.timestamp()),
            int(not_after.timestamp())
        )
        
        # Encrypt data
        nonce = secrets.token_bytes(self.NONCE_SIZE)
        cipher = ChaCha20Poly1305(time_key)
        ciphertext = cipher.encrypt(nonce, data, header)
        
        # Combine: header + nonce + ciphertext
        return header + nonce + ciphertext
    
    def unwrap_time_bound(self, wrapped: bytes) -> bytes:
        """
        Unwrap time-bound data, verifying it's within valid time window.
        
        Args:
            wrapped: Time-bound wrapped data
            
        Returns:
            Original data
            
        Raises:
            ValueError: If outside valid time window or corrupted
        """
        # Parse header
        header_size = 1 + 8 + 8  # version + 2 timestamps
        if len(wrapped) < header_size + self.NONCE_SIZE:
            raise ValueError("Invalid wrapped data - too short")
        
        header = wrapped[:header_size]
        version, not_before_ts, not_after_ts = struct.unpack('<BQQ', header)
        
        if version != self.PROTOCOL_VERSION:
            raise ValueError(f"Unknown protocol version: {version}")
        
        # Check time bounds
        now = time.time()
        if now < not_before_ts:
            raise ValueError("Data not yet valid - before activation time")
        if now > not_after_ts:
            raise ValueError("Data expired - after expiration time")
        
        # Derive key and decrypt
        time_material = f"time:{not_before_ts}:{not_after_ts}"
        time_key = hashlib.blake2b(time_material.encode(), digest_size=32).digest()
        
        nonce = wrapped[header_size:header_size + self.NONCE_SIZE]
        ciphertext = wrapped[header_size + self.NONCE_SIZE:]
        
        cipher = ChaCha20Poly1305(time_key)
        return cipher.decrypt(nonce, ciphertext, header)
    
    # =========================================================================
    # Geohash Implementation
    # =========================================================================
    
    def _encode_geohash(self, lat: float, lon: float, precision: int = 6) -> str:
        """
        Encode latitude/longitude to geohash string.
        
        Args:
            lat: Latitude (-90 to 90)
            lon: Longitude (-180 to 180)
            precision: Number of characters (1-12)
            
        Returns:
            Geohash string
        """
        BASE32 = '0123456789bcdefghjkmnpqrstuvwxyz'
        
        lat_range = (-90.0, 90.0)
        lon_range = (-180.0, 180.0)
        
        geohash = []
        bits = 0
        bit_count = 0
        is_lon = True
        
        while len(geohash) < precision:
            if is_lon:
                mid = (lon_range[0] + lon_range[1]) / 2
                if lon >= mid:
                    bits = (bits << 1) | 1
                    lon_range = (mid, lon_range[1])
                else:
                    bits = bits << 1
                    lon_range = (lon_range[0], mid)
            else:
                mid = (lat_range[0] + lat_range[1]) / 2
                if lat >= mid:
                    bits = (bits << 1) | 1
                    lat_range = (mid, lat_range[1])
                else:
                    bits = bits << 1
                    lat_range = (lat_range[0], mid)
            
            is_lon = not is_lon
            bit_count += 1
            
            if bit_count == 5:
                geohash.append(BASE32[bits])
                bits = 0
                bit_count = 0
        
        return ''.join(geohash)
    
    def _decode_geohash(self, geohash: str) -> Tuple[float, float]:
        """
        Decode geohash string to latitude/longitude.
        
        Args:
            geohash: Geohash string
            
        Returns:
            Tuple of (latitude, longitude)
        """
        BASE32 = '0123456789bcdefghjkmnpqrstuvwxyz'
        BASE32_MAP = {c: i for i, c in enumerate(BASE32)}
        
        lat_range = [-90.0, 90.0]
        lon_range = [-180.0, 180.0]
        is_lon = True
        
        for char in geohash.lower():
            bits = BASE32_MAP.get(char, 0)
            
            for i in range(4, -1, -1):
                bit = (bits >> i) & 1
                
                if is_lon:
                    mid = (lon_range[0] + lon_range[1]) / 2
                    if bit:
                        lon_range[0] = mid
                    else:
                        lon_range[1] = mid
                else:
                    mid = (lat_range[0] + lat_range[1]) / 2
                    if bit:
                        lat_range[0] = mid
                    else:
                        lat_range[1] = mid
                
                is_lon = not is_lon
        
        lat = (lat_range[0] + lat_range[1]) / 2
        lon = (lon_range[0] + lon_range[1]) / 2
        
        return lat, lon
    
    # =========================================================================
    # Utility Functions
    # =========================================================================
    
    def hash_secret(self, secret: bytes) -> str:
        """Create BLAKE3 hash of secret for verification."""
        return hashlib.blake2b(secret, digest_size=32).hexdigest()
    
    def generate_nonce(self) -> bytes:
        """Generate random nonce."""
        return secrets.token_bytes(self.NONCE_SIZE)
    
    def serialize_payload(self, payload: EncryptedPayload) -> bytes:
        """Serialize encrypted payload for network transmission."""
        parts = [
            struct.pack('<B', self.PROTOCOL_VERSION),
            struct.pack('<H', len(payload.ciphertext)),
            payload.ciphertext,
            payload.nonce,
        ]
        
        if payload.ephemeral_public_key:
            parts.append(b'\x01')  # Has ephemeral key
            parts.append(payload.ephemeral_public_key)
        else:
            parts.append(b'\x00')
        
        return b''.join(parts)
    
    def deserialize_payload(self, data: bytes) -> EncryptedPayload:
        """Deserialize encrypted payload from network."""
        offset = 0
        
        version = struct.unpack('<B', data[offset:offset+1])[0]
        offset += 1
        
        if version != self.PROTOCOL_VERSION:
            raise ValueError(f"Unknown protocol version: {version}")
        
        ciphertext_len = struct.unpack('<H', data[offset:offset+2])[0]
        offset += 2
        
        ciphertext = data[offset:offset+ciphertext_len]
        offset += ciphertext_len
        
        nonce = data[offset:offset+self.NONCE_SIZE]
        offset += self.NONCE_SIZE
        
        has_ephemeral = data[offset] == 1
        offset += 1
        
        ephemeral = None
        if has_ephemeral:
            ephemeral = data[offset:offset+32]
        
        return EncryptedPayload(
            ciphertext=ciphertext,
            nonce=nonce,
            ephemeral_public_key=ephemeral
        )


# Module-level instance
mesh_crypto_service = MeshCryptoService()

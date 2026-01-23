"""
Mesh Crypto Service Tests
==========================

Unit tests for mesh cryptography operations.

@author Password Manager Team
@created 2026-01-22
"""

from datetime import datetime, timedelta
from django.test import TestCase
from django.utils import timezone
from ..services.mesh_crypto_service import MeshCryptoService


class MeshCryptoTests(TestCase):
    """Tests for mesh cryptography."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.crypto = MeshCryptoService()
    
    def test_generate_keypair(self):
        """Test keypair generation."""
        keypair = self.crypto.generate_mesh_keypair()
        
        self.assertEqual(len(keypair.private_key), 32)
        self.assertEqual(len(keypair.public_key), 32)
    
    def test_keypairs_are_unique(self):
        """Test that keypairs are unique."""
        kp1 = self.crypto.generate_mesh_keypair()
        kp2 = self.crypto.generate_mesh_keypair()
        
        self.assertNotEqual(kp1.private_key, kp2.private_key)
        self.assertNotEqual(kp1.public_key, kp2.public_key)
    
    def test_encrypt_for_node(self):
        """Test encryption for a specific node."""
        node_keypair = self.crypto.generate_mesh_keypair()
        plaintext = b"secret message for node"
        
        encrypted = self.crypto.encrypt_for_node(plaintext, node_keypair.public_key)
        
        self.assertIsNotNone(encrypted.ciphertext)
        self.assertIsNotNone(encrypted.nonce)
        self.assertIsNotNone(encrypted.ephemeral_public_key)
        self.assertNotEqual(encrypted.ciphertext, plaintext)
    
    def test_decrypt_from_sender(self):
        """Test decryption of node-encrypted message."""
        node_keypair = self.crypto.generate_mesh_keypair()
        plaintext = b"decrypt me"
        
        encrypted = self.crypto.encrypt_for_node(plaintext, node_keypair.public_key)
        decrypted = self.crypto.decrypt_from_sender(encrypted, node_keypair.private_key)
        
        self.assertEqual(decrypted, plaintext)
    
    def test_decrypt_with_wrong_key_fails(self):
        """Test that decryption with wrong key fails."""
        node1 = self.crypto.generate_mesh_keypair()
        node2 = self.crypto.generate_mesh_keypair()
        
        encrypted = self.crypto.encrypt_for_node(b"secret", node1.public_key)
        
        with self.assertRaises(ValueError):
            self.crypto.decrypt_from_sender(encrypted, node2.private_key)
    
    def test_authenticated_encryption(self):
        """Test AEAD with associated data."""
        node = self.crypto.generate_mesh_keypair()
        plaintext = b"authenticated message"
        aad = b"additional authenticated data"
        
        encrypted = self.crypto.encrypt_for_node(plaintext, node.public_key, aad)
        decrypted = self.crypto.decrypt_from_sender(encrypted, node.private_key, aad)
        
        self.assertEqual(decrypted, plaintext)
    
    def test_aead_fails_with_wrong_aad(self):
        """Test that wrong AAD causes decryption failure."""
        node = self.crypto.generate_mesh_keypair()
        encrypted = self.crypto.encrypt_for_node(
            b"message", 
            node.public_key, 
            b"correct aad"
        )
        
        with self.assertRaises(ValueError):
            self.crypto.decrypt_from_sender(encrypted, node.private_key, b"wrong aad")
    
    def test_location_bound_key(self):
        """Test location-bound key generation."""
        lat, lon = 40.7128, -74.0060  # NYC
        
        key1, geohash1 = self.crypto.create_location_bound_key(lat, lon, precision=6)
        key2, geohash2 = self.crypto.create_location_bound_key(lat, lon, precision=6)
        
        # Same location should give same key
        self.assertEqual(key1, key2)
        self.assertEqual(geohash1, geohash2)
        self.assertEqual(len(key1), 32)
    
    def test_different_locations_different_keys(self):
        """Test that different locations produce different keys."""
        key1, _ = self.crypto.create_location_bound_key(40.7128, -74.0060, precision=6)
        key2, _ = self.crypto.create_location_bound_key(34.0522, -118.2437, precision=6)  # LA
        
        self.assertNotEqual(key1, key2)
    
    def test_location_bound_encryption(self):
        """Test location-bound encryption and decryption."""
        lat, lon = 40.7128, -74.0060
        plaintext = b"location secret"
        
        encrypted, geohash = self.crypto.encrypt_with_location(plaintext, lat, lon, precision=7)
        
        # Decrypt at same location
        decrypted = self.crypto.decrypt_with_location(encrypted, lat, lon, precision=7)
        self.assertEqual(decrypted, plaintext)
    
    def test_location_bound_fails_at_wrong_location(self):
        """Test that decryption fails at wrong location."""
        encrypted, _ = self.crypto.encrypt_with_location(
            b"secret", 40.7128, -74.0060, precision=7
        )
        
        # Try to decrypt at different location
        with self.assertRaises(ValueError):
            self.crypto.decrypt_with_location(encrypted, 34.0522, -118.2437, precision=7)
    
    def test_time_bound_wrapper(self):
        """Test time-bound encryption wrapper."""
        plaintext = b"time-limited secret"
        not_before = timezone.now()
        not_after = timezone.now() + timedelta(hours=1)
        
        wrapped = self.crypto.create_time_bound_wrapper(plaintext, not_before, not_after)
        
        # Should be able to unwrap within valid window
        unwrapped = self.crypto.unwrap_time_bound(wrapped)
        self.assertEqual(unwrapped, plaintext)
    
    def test_time_bound_expired_fails(self):
        """Test that expired time-bound data fails."""
        plaintext = b"expired secret"
        not_before = timezone.now() - timedelta(hours=2)
        not_after = timezone.now() - timedelta(hours=1)  # Already expired
        
        wrapped = self.crypto.create_time_bound_wrapper(plaintext, not_before, not_after)
        
        with self.assertRaises(ValueError) as ctx:
            self.crypto.unwrap_time_bound(wrapped)
        
        self.assertIn("expired", str(ctx.exception).lower())
    
    def test_geohash_encoding(self):
        """Test geohash encoding."""
        # NYC
        geohash = self.crypto._encode_geohash(40.7128, -74.0060, precision=6)
        self.assertEqual(len(geohash), 6)
        
        # Different precisions
        for precision in [4, 6, 8]:
            gh = self.crypto._encode_geohash(40.7128, -74.0060, precision=precision)
            self.assertEqual(len(gh), precision)
    
    def test_geohash_decoding(self):
        """Test geohash decoding."""
        lat, lon = 40.7128, -74.0060
        geohash = self.crypto._encode_geohash(lat, lon, precision=8)
        
        decoded_lat, decoded_lon = self.crypto._decode_geohash(geohash)
        
        # Should be close (within precision)
        self.assertAlmostEqual(lat, decoded_lat, places=3)
        self.assertAlmostEqual(lon, decoded_lon, places=3)
    
    def test_nearby_locations_same_geohash(self):
        """Test that nearby locations have same geohash prefix."""
        # Two points very close together
        gh1 = self.crypto._encode_geohash(40.7128, -74.0060, precision=6)
        gh2 = self.crypto._encode_geohash(40.7129, -74.0061, precision=6)
        
        self.assertEqual(gh1, gh2)
    
    def test_hash_secret(self):
        """Test secret hashing."""
        secret = b"hash me"
        hash1 = self.crypto.hash_secret(secret)
        hash2 = self.crypto.hash_secret(secret)
        
        self.assertEqual(hash1, hash2)
        self.assertEqual(len(hash1), 64)  # BLAKE2b-256 produces 32 bytes = 64 hex chars
    
    def test_serialize_deserialize_payload(self):
        """Test payload serialization."""
        node = self.crypto.generate_mesh_keypair()
        encrypted = self.crypto.encrypt_for_node(b"serialize me", node.public_key)
        
        serialized = self.crypto.serialize_payload(encrypted)
        deserialized = self.crypto.deserialize_payload(serialized)
        
        self.assertEqual(encrypted.ciphertext, deserialized.ciphertext)
        self.assertEqual(encrypted.nonce, deserialized.nonce)
        self.assertEqual(encrypted.ephemeral_public_key, deserialized.ephemeral_public_key)

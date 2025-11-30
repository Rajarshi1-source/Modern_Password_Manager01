"""
ECCService - Backend Elliptic Curve Cryptography Service

Implements dual ECC curves for hybrid key exchange:
- Curve25519 (X25519): Modern, fast, side-channel resistant
- P-384 (secp384r1): NIST standard, enterprise trusted

This provides defense-in-depth: both curves must be compromised
for the system to be vulnerable.
"""

import os
import base64
import logging
from cryptography.hazmat.primitives.asymmetric import x25519, ec
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.backends import default_backend

logger = logging.getLogger(__name__)


class ECCService:
    """Service for elliptic curve cryptography operations"""
    
    CURVE25519_KEY_SIZE = 32  # bytes
    P384_KEY_SIZE = 48  # bytes (384 bits)
    
    def __init__(self):
        self.backend = default_backend()
    
    def generate_curve25519_keypair(self):
        """
        Generate Curve25519 (X25519) keypair
        
        Returns:
            dict: { 'private_key': X25519PrivateKey, 'public_key': bytes }
        """
        try:
            private_key = x25519.X25519PrivateKey.generate()
            public_key = private_key.public_key()
            
            # Serialize public key to bytes
            public_key_bytes = public_key.public_bytes(
                encoding=serialization.Encoding.Raw,
                format=serialization.PublicFormat.Raw
            )
            
            return {
                'private_key': private_key,
                'public_key': public_key_bytes,
                'curve': 'Curve25519'
            }
        except Exception as e:
            logger.error(f'Failed to generate Curve25519 keypair: {e}')
            raise ValueError('Curve25519 key generation failed')
    
    def generate_p384_keypair(self):
        """
        Generate P-384 (secp384r1) keypair
        
        Returns:
            dict: { 'private_key': EllipticCurvePrivateKey, 'public_key': bytes }
        """
        try:
            private_key = ec.generate_private_key(
                ec.SECP384R1(),
                backend=self.backend
            )
            public_key = private_key.public_key()
            
            # Serialize public key to uncompressed format
            public_key_bytes = public_key.public_bytes(
                encoding=serialization.Encoding.X962,
                format=serialization.PublicFormat.UncompressedPoint
            )
            
            return {
                'private_key': private_key,
                'public_key': public_key_bytes,
                'curve': 'P-384'
            }
        except Exception as e:
            logger.error(f'Failed to generate P-384 keypair: {e}')
            raise ValueError('P-384 key generation failed')
    
    def generate_hybrid_keypair(self):
        """
        Generate hybrid keypair (both Curve25519 and P-384)
        
        Returns:
            dict: Contains both keypairs
        """
        try:
            curve25519_pair = self.generate_curve25519_keypair()
            p384_pair = self.generate_p384_keypair()
            
            return {
                'curve25519': curve25519_pair,
                'p384': p384_pair,
                'type': 'hybrid-ecdh',
                'version': 2
            }
        except Exception as e:
            logger.error(f'Failed to generate hybrid keypair: {e}')
            raise ValueError('Hybrid keypair generation failed')
    
    def perform_curve25519_ecdh(self, private_key, peer_public_key_bytes):
        """
        Perform Curve25519 ECDH
        
        Args:
            private_key: X25519PrivateKey object
            peer_public_key_bytes: bytes of peer's public key
            
        Returns:
            bytes: Shared secret
        """
        try:
            # Deserialize peer's public key
            peer_public_key = x25519.X25519PublicKey.from_public_bytes(
                peer_public_key_bytes
            )
            
            # Perform ECDH
            shared_secret = private_key.exchange(peer_public_key)
            
            return shared_secret
        except Exception as e:
            logger.error(f'Curve25519 ECDH failed: {e}')
            raise ValueError('Curve25519 ECDH failed')
    
    def perform_p384_ecdh(self, private_key, peer_public_key_bytes):
        """
        Perform P-384 ECDH
        
        Args:
            private_key: EllipticCurvePrivateKey object
            peer_public_key_bytes: bytes of peer's public key
            
        Returns:
            bytes: Shared secret
        """
        try:
            # Deserialize peer's public key
            peer_public_key = ec.EllipticCurvePublicKey.from_encoded_point(
                ec.SECP384R1(),
                peer_public_key_bytes
            )
            
            # Perform ECDH
            shared_secret = private_key.exchange(
                ec.ECDH(),
                peer_public_key
            )
            
            return shared_secret
        except Exception as e:
            logger.error(f'P-384 ECDH failed: {e}')
            raise ValueError('P-384 ECDH failed')
    
    def perform_hybrid_ecdh(self, our_keys, peer_public_keys):
        """
        Perform hybrid ECDH with both curves
        
        Args:
            our_keys: dict with curve25519 and p384 private keys
            peer_public_keys: dict with curve25519 and p384 public key bytes
            
        Returns:
            dict: { 'curve25519_secret': bytes, 'p384_secret': bytes }
        """
        try:
            # Perform ECDH with Curve25519
            secret1 = self.perform_curve25519_ecdh(
                our_keys['curve25519']['private_key'],
                peer_public_keys['curve25519']
            )
            
            # Perform ECDH with P-384
            secret2 = self.perform_p384_ecdh(
                our_keys['p384']['private_key'],
                peer_public_keys['p384']
            )
            
            return {
                'curve25519_secret': secret1,
                'p384_secret': secret2
            }
        except Exception as e:
            logger.error(f'Hybrid ECDH failed: {e}')
            raise ValueError('Hybrid ECDH failed')
    
    def derive_key_from_hybrid_secret(self, secret1, secret2, salt, info=b'hybrid-ecdh-v2'):
        """
        Derive final key from hybrid ECDH secrets using HKDF
        
        Args:
            secret1: bytes - Curve25519 shared secret
            secret2: bytes - P-384 shared secret
            salt: bytes - Salt for HKDF
            info: bytes - Context information
            
        Returns:
            bytes: Derived key (32 bytes for AES-256)
        """
        try:
            # Concatenate both secrets
            combined_secret = secret1 + secret2
            
            # Use HKDF to derive final key
            hkdf = HKDF(
                algorithm=hashes.SHA256(),
                length=32,  # 32 bytes for AES-256
                salt=salt,
                info=info,
                backend=self.backend
            )
            
            derived_key = hkdf.derive(combined_secret)
            
            return derived_key
        except Exception as e:
            logger.error(f'Hybrid key derivation failed: {e}')
            raise ValueError('Hybrid key derivation failed')
    
    def wrap_key(self, key_to_wrap, peer_public_keys):
        """
        Wrap a key using hybrid ECDH
        Used for encrypting vault keys for cross-device sync
        
        Args:
            key_to_wrap: bytes - The key to encrypt
            peer_public_keys: dict - Peer's public keys
            
        Returns:
            dict: Wrapped key and our public keys
        """
        try:
            # Generate ephemeral keypair
            our_keys = self.generate_hybrid_keypair()
            
            # Perform hybrid ECDH
            secrets = self.perform_hybrid_ecdh(our_keys, peer_public_keys)
            
            # Derive encryption key
            salt = os.urandom(32)
            wrap_key = self.derive_key_from_hybrid_secret(
                secrets['curve25519_secret'],
                secrets['p384_secret'],
                salt,
                b'key-wrap-v2'
            )
            
            # Encrypt the key using AES-GCM
            aesgcm = AESGCM(wrap_key)
            iv = os.urandom(12)
            encrypted_key = aesgcm.encrypt(iv, key_to_wrap, None)
            
            return {
                'encrypted_key': encrypted_key,
                'iv': iv,
                'salt': salt,
                'public_keys': {
                    'curve25519': our_keys['curve25519']['public_key'],
                    'p384': our_keys['p384']['public_key']
                },
                'version': 2
            }
        except Exception as e:
            logger.error(f'Key wrapping failed: {e}')
            raise ValueError('Failed to wrap key with hybrid ECDH')
    
    def unwrap_key(self, wrapped_data, our_private_keys):
        """
        Unwrap a key using hybrid ECDH
        
        Args:
            wrapped_data: dict - Wrapped key data
            our_private_keys: dict - Our private keys
            
        Returns:
            bytes: Unwrapped key
        """
        try:
            # Perform hybrid ECDH
            secrets = self.perform_hybrid_ecdh(
                our_private_keys,
                wrapped_data['public_keys']
            )
            
            # Derive decryption key
            unwrap_key = self.derive_key_from_hybrid_secret(
                secrets['curve25519_secret'],
                secrets['p384_secret'],
                wrapped_data['salt'],
                b'key-wrap-v2'
            )
            
            # Decrypt the key using AES-GCM
            aesgcm = AESGCM(unwrap_key)
            decrypted_key = aesgcm.decrypt(
                wrapped_data['iv'],
                wrapped_data['encrypted_key'],
                None
            )
            
            return decrypted_key
        except Exception as e:
            logger.error(f'Key unwrapping failed: {e}')
            raise ValueError('Failed to unwrap key with hybrid ECDH')
    
    def export_public_keys(self, keys):
        """
        Export public keys for transmission
        
        Args:
            keys: dict - Keypair object
            
        Returns:
            dict: Base64-encoded public keys
        """
        return {
            'curve25519': base64.b64encode(keys['curve25519']['public_key']).decode('utf-8'),
            'p384': base64.b64encode(keys['p384']['public_key']).decode('utf-8'),
            'version': 2
        }
    
    def import_public_keys(self, encoded_keys):
        """
        Import public keys from Base64
        
        Args:
            encoded_keys: dict - Base64-encoded public keys
            
        Returns:
            dict: bytes public keys
        """
        return {
            'curve25519': base64.b64decode(encoded_keys['curve25519']),
            'p384': base64.b64decode(encoded_keys['p384'])
        }
    
    def serialize_private_key(self, private_key, password=None):
        """
        Serialize private key for storage
        
        Args:
            private_key: Private key object
            password: Optional password for encryption
            
        Returns:
            bytes: Serialized private key
        """
        try:
            encryption = serialization.BestAvailableEncryption(password) if password else serialization.NoEncryption()
            
            if isinstance(private_key, x25519.X25519PrivateKey):
                return private_key.private_bytes(
                    encoding=serialization.Encoding.Raw,
                    format=serialization.PrivateFormat.Raw,
                    encryption_algorithm=encryption
                )
            else:
                return private_key.private_bytes(
                    encoding=serialization.Encoding.PEM,
                    format=serialization.PrivateFormat.PKCS8,
                    encryption_algorithm=encryption
                )
        except Exception as e:
            logger.error(f'Failed to serialize private key: {e}')
            raise ValueError('Private key serialization failed')


# Singleton instance
ecc_service = ECCService()


"""
Production Post-Quantum Cryptography Service

Implements CRYSTALS-Kyber-768 (NIST-approved) for quantum-resistant encryption
of behavioral embeddings using hybrid Kyber + AES approach.
"""

import os
import base64
import logging
import json
from typing import Tuple, Dict, Optional

logger = logging.getLogger(__name__)

# Try to import liboqs for production Kyber implementation
try:
    from oqs import KEM
    LIBOQS_AVAILABLE = True
    logger.info("liboqs-python available - using production Kyber-768")
except ImportError:
    LIBOQS_AVAILABLE = False
    logger.warning("liboqs-python not available - using fallback encryption")

# Import for AES-GCM
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.backends import default_backend


class QuantumCryptoService:
    """
    Production quantum-resistant encryption using CRYSTALS-Kyber-768
    
    Hybrid approach for maximum security:
    1. Kyber-768 for key encapsulation (post-quantum resistant)
    2. AES-256-GCM for data encryption (classical, proven)
    
    Key Sizes (Kyber-768 / NIST Level 3):
    - Public key: 1184 bytes
    - Private key: 2400 bytes
    - Ciphertext: 1088 bytes
    - Shared secret: 32 bytes
    """
    
    ALGORITHM = 'Kyber768'  # NIST Level 3 security (equivalent to AES-192)
    PUBLIC_KEY_SIZE = 1184
    PRIVATE_KEY_SIZE = 2400
    CIPHERTEXT_SIZE = 1088
    SHARED_SECRET_SIZE = 32
    
    def __init__(self):
        """Initialize Kyber KEM"""
        if LIBOQS_AVAILABLE:
            try:
                self.kem = KEM(self.ALGORITHM)
                self.backend = default_backend()
                logger.info(f"Initialized production {self.ALGORITHM} KEM")
            except Exception as e:
                logger.error(f"Failed to initialize Kyber: {e}")
                raise
        else:
            logger.warning("Using fallback encryption (not quantum-resistant)")
            self.backend = default_backend()
    
    def generate_keypair(self) -> Tuple[bytes, bytes]:
        """
        Generate CRYSTALS-Kyber-768 keypair
        
        Returns:
            Tuple of (public_key, private_key) as bytes
        """
        if LIBOQS_AVAILABLE:
            try:
                # Generate Kyber keypair
                public_key = self.kem.generate_keypair()
                private_key = self.kem.export_secret_key()
                
                logger.debug(f"Generated Kyber-768 keypair: pub={len(public_key)}B, priv={len(private_key)}B")
                return public_key, private_key
                
            except Exception as e:
                logger.error(f"Kyber keypair generation failed: {e}")
                raise
        else:
            # Fallback: generate random keys (not quantum-resistant)
            return self._fallback_generate_keypair()
    
    def encrypt_behavioral_embedding(self, embedding: list, public_key: bytes) -> Dict:
        """
        Encrypt behavioral embedding using hybrid Kyber + AES-256-GCM
        
        Process:
        1. Kyber encapsulation: Generate shared secret using public key
        2. AES-256-GCM: Encrypt embedding with shared secret
        3. Return: Kyber ciphertext + AES ciphertext
        
        Args:
            embedding: 128-dimensional behavioral DNA array
            public_key: Kyber-768 public key (1184 bytes)
        
        Returns:
            Dict with:
            - kyber_ciphertext: Base64-encoded Kyber ciphertext
            - aes_ciphertext: Base64-encoded AES ciphertext
            - nonce: Base64-encoded nonce (12 bytes)
            - algorithm: Encryption algorithm identifier
        """
        if LIBOQS_AVAILABLE:
            try:
                # Step 1: Kyber encapsulation
                kyber_ciphertext, shared_secret = self.kem.encap_secret(public_key)
                
                logger.debug(f"Kyber encapsulation: ct={len(kyber_ciphertext)}B, ss={len(shared_secret)}B")
                
            except Exception as e:
                logger.error(f"Kyber encapsulation failed: {e}")
                raise
        else:
            # Fallback encryption
            return self._fallback_encrypt(embedding, public_key)
        
        # Step 2: AES-256-GCM encryption with shared secret
        try:
            # Use first 32 bytes of shared secret as AES key
            aesgcm = AESGCM(shared_secret[:32])
            
            # Generate random nonce
            nonce = os.urandom(12)
            
            # Convert embedding to bytes
            embedding_json = json.dumps(embedding)
            embedding_bytes = embedding_json.encode('utf-8')
            
            # Encrypt with AES-GCM (includes authentication tag)
            aes_ciphertext = aesgcm.encrypt(nonce, embedding_bytes, None)
            
            logger.debug(f"AES-GCM encryption: {len(aes_ciphertext)}B")
            
            # Return encrypted data
            return {
                'kyber_ciphertext': base64.b64encode(kyber_ciphertext).decode('utf-8'),
                'aes_ciphertext': base64.b64encode(aes_ciphertext).decode('utf-8'),
                'nonce': base64.b64encode(nonce).decode('utf-8'),
                'algorithm': 'kyber768-aes256gcm',
                'version': '1.0'
            }
            
        except Exception as e:
            logger.error(f"AES-GCM encryption failed: {e}")
            raise
    
    def decrypt_behavioral_embedding(self, encrypted_data: Dict, private_key: bytes) -> list:
        """
        Decrypt behavioral embedding using hybrid Kyber + AES-256-GCM
        
        Process:
        1. Kyber decapsulation: Recover shared secret using private key
        2. AES-256-GCM: Decrypt embedding with shared secret
        
        Args:
            encrypted_data: Dict with kyber_ciphertext, aes_ciphertext, nonce
            private_key: Kyber-768 private key (2400 bytes)
        
        Returns:
            128-dimensional behavioral DNA array
        """
        if LIBOQS_AVAILABLE:
            try:
                # Step 1: Kyber decapsulation
                kyber_ciphertext = base64.b64decode(encrypted_data['kyber_ciphertext'])
                shared_secret = self.kem.decap_secret(kyber_ciphertext)
                
                logger.debug(f"Kyber decapsulation successful: ss={len(shared_secret)}B")
                
            except Exception as e:
                logger.error(f"Kyber decapsulation failed: {e}")
                raise
        else:
            # Fallback decryption
            return self._fallback_decrypt(encrypted_data, private_key)
        
        # Step 2: AES-256-GCM decryption
        try:
            # Use shared secret as AES key
            aesgcm = AESGCM(shared_secret[:32])
            
            # Decode nonce and ciphertext
            nonce = base64.b64decode(encrypted_data['nonce'])
            aes_ciphertext = base64.b64decode(encrypted_data['aes_ciphertext'])
            
            # Decrypt (also verifies authentication tag)
            embedding_bytes = aesgcm.decrypt(nonce, aes_ciphertext, None)
            
            # Convert back to array
            embedding_json = embedding_bytes.decode('utf-8')
            embedding = json.loads(embedding_json)
            
            logger.debug(f"AES-GCM decryption successful: embedding_dim={len(embedding)}")
            
            return embedding
            
        except Exception as e:
            logger.error(f"AES-GCM decryption failed: {e}")
            raise
    
    def is_quantum_protected(self, encrypted_data: Dict) -> bool:
        """
        Check if data is quantum-protected
        
        Args:
            encrypted_data: Encrypted data dict
        
        Returns:
            True if using Kyber encryption
        """
        algorithm = encrypted_data.get('algorithm', '')
        return algorithm.startswith('kyber')
    
    # ============================================================================
    # FALLBACK METHODS (when liboqs not available)
    # ============================================================================
    
    def _fallback_generate_keypair(self) -> Tuple[bytes, bytes]:
        """
        Fallback keypair generation using classical crypto
        
        NOTE: This is NOT quantum-resistant! Only for development/testing.
        """
        logger.warning("Using fallback keypair generation - NOT QUANTUM-RESISTANT")
        
        # Generate random keys matching Kyber sizes for compatibility
        public_key = os.urandom(self.PUBLIC_KEY_SIZE)
        private_key = os.urandom(self.PRIVATE_KEY_SIZE)
        
        return public_key, private_key
    
    def _fallback_encrypt(self, embedding: list, public_key: bytes) -> Dict:
        """
        Fallback encryption (classical AES only)
        
        NOTE: This is NOT quantum-resistant!
        """
        logger.warning("Using fallback encryption - NOT QUANTUM-RESISTANT")
        
        # Use public_key hash as AES key (deterministic shared secret)
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.kdf.hkdf import HKDF
        
        # Derive AES key from public key
        hkdf = HKDF(
            algorithm=hashes.SHA256(),
            length=32,
            salt=None,
            info=b'behavioral-embedding',
            backend=self.backend
        )
        aes_key = hkdf.derive(public_key)
        
        # Encrypt with AES-GCM
        aesgcm = AESGCM(aes_key)
        nonce = os.urandom(12)
        
        embedding_json = json.dumps(embedding)
        embedding_bytes = embedding_json.encode('utf-8')
        
        aes_ciphertext = aesgcm.encrypt(nonce, embedding_bytes, None)
        
        # Return in same format as Kyber encryption
        return {
            'kyber_ciphertext': base64.b64encode(b'fallback').decode('utf-8'),
            'aes_ciphertext': base64.b64encode(aes_ciphertext).decode('utf-8'),
            'nonce': base64.b64encode(nonce).decode('utf-8'),
            'algorithm': 'fallback-aes256gcm',
            'version': '1.0-fallback'
        }
    
    def _fallback_decrypt(self, encrypted_data: Dict, private_key: bytes) -> list:
        """
        Fallback decryption (classical AES only)
        
        NOTE: This is NOT quantum-resistant!
        """
        logger.warning("Using fallback decryption - NOT QUANTUM-RESISTANT")
        
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.kdf.hkdf import HKDF
        
        # Reconstruct AES key from private key
        # In fallback mode, we derive from private key
        hkdf = HKDF(
            algorithm=hashes.SHA256(),
            length=32,
            salt=None,
            info=b'behavioral-embedding',
            backend=self.backend
        )
        aes_key = hkdf.derive(private_key[:32])  # Use first 32 bytes
        
        # Decrypt with AES-GCM
        aesgcm = AESGCM(aes_key)
        nonce = base64.b64decode(encrypted_data['nonce'])
        aes_ciphertext = base64.b64decode(encrypted_data['aes_ciphertext'])
        
        embedding_bytes = aesgcm.decrypt(nonce, aes_ciphertext, None)
        embedding_json = embedding_bytes.decode('utf-8')
        embedding = json.loads(embedding_json)
        
        return embedding
    
    # ============================================================================
    # UTILITY METHODS
    # ============================================================================
    
    def get_algorithm_info(self) -> Dict:
        """
        Get information about the cryptographic algorithm
        
        Returns:
            Dict with algorithm details
        """
        return {
            'algorithm': self.ALGORITHM if LIBOQS_AVAILABLE else 'Fallback-AES',
            'quantum_resistant': LIBOQS_AVAILABLE,
            'public_key_size': self.PUBLIC_KEY_SIZE,
            'private_key_size': self.PRIVATE_KEY_SIZE,
            'ciphertext_size': self.CIPHERTEXT_SIZE,
            'shared_secret_size': self.SHARED_SECRET_SIZE,
            'security_level': 'NIST Level 3 (192-bit equivalent)' if LIBOQS_AVAILABLE else 'Classical (256-bit)',
            'liboqs_available': LIBOQS_AVAILABLE
        }
    
    def validate_key_sizes(self, public_key: bytes, private_key: bytes) -> bool:
        """
        Validate that keys are correct sizes
        
        Args:
            public_key: Public key bytes
            private_key: Private key bytes
        
        Returns:
            True if sizes are correct
        """
        if len(public_key) != self.PUBLIC_KEY_SIZE:
            logger.error(f"Invalid public key size: {len(public_key)} (expected {self.PUBLIC_KEY_SIZE})")
            return False
        
        if len(private_key) != self.PRIVATE_KEY_SIZE:
            logger.error(f"Invalid private key size: {len(private_key)} (expected {self.PRIVATE_KEY_SIZE})")
            return False
        
        return True


# Singleton instance for reuse
_global_quantum_crypto = None

def get_quantum_crypto_service():
    """Get or create global QuantumCryptoService instance"""
    global _global_quantum_crypto
    
    if _global_quantum_crypto is None:
        _global_quantum_crypto = QuantumCryptoService()
    
    return _global_quantum_crypto


"""
Post-Quantum Cryptography Service

Implements CRYSTALS-Kyber (lattice-based) encryption for quantum-resistant security.
Falls back to hybrid encryption (Kyber + AES-GCM) for maximum security.
"""

import os
import base64
import hashlib
from typing import Tuple, Dict, Optional
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.backends import default_backend
import json


class QuantumCryptoService:
    """
    Service for quantum-resistant encryption using hybrid approach:
    1. CRYSTALS-Kyber for key encapsulation (post-quantum)
    2. AES-256-GCM for data encryption (classical but proven)
    
    Note: This is a placeholder implementation. For production, use actual
    CRYSTALS-Kyber library (e.g., liboqs-python or pqcrypto)
    """
    
    # Key sizes for CRYSTALS-Kyber-768 (NIST Level 3)
    PUBLIC_KEY_SIZE = 1184
    PRIVATE_KEY_SIZE = 2400
    CIPHERTEXT_SIZE = 1088
    SHARED_SECRET_SIZE = 32
    
    def __init__(self):
        self.backend = default_backend()
    
    def generate_kyber_keypair(self) -> Tuple[bytes, bytes]:
        """
        Generate CRYSTALS-Kyber-768 keypair
        
        Returns:
            (public_key, private_key): Post-quantum key pair
        
        Note: This is a simulation for demonstration. In production, use:
        from pqcrypto.kem.kyber768 import generate_keypair
        public_key, private_key = generate_keypair()
        """
        # Simulated keypair generation (replace with actual Kyber implementation)
        public_key = os.urandom(self.PUBLIC_KEY_SIZE)
        private_key = os.urandom(self.PRIVATE_KEY_SIZE)
        
        return public_key, private_key
    
    def kyber_encapsulate(self, public_key: bytes) -> Tuple[bytes, bytes]:
        """
        Encapsulate a shared secret using recipient's public key
        
        Args:
            public_key: Recipient's Kyber public key
        
        Returns:
            (ciphertext, shared_secret): Encapsulated shared secret and the secret itself
        
        Note: In production, use:
        from pqcrypto.kem.kyber768 import encrypt
        ciphertext, shared_secret = encrypt(public_key)
        """
        # Simulated encapsulation (replace with actual Kyber)
        ciphertext = os.urandom(self.CIPHERTEXT_SIZE)
        shared_secret = os.urandom(self.SHARED_SECRET_SIZE)
        
        return ciphertext, shared_secret
    
    def kyber_decapsulate(self, ciphertext: bytes, private_key: bytes) -> bytes:
        """
        Decapsulate shared secret using private key
        
        Args:
            ciphertext: Kyber ciphertext
            private_key: Recipient's Kyber private key
        
        Returns:
            shared_secret: Decapsulated shared secret
        
        Note: In production, use:
        from pqcrypto.kem.kyber768 import decrypt
        shared_secret = decrypt(ciphertext, private_key)
        """
        # Simulated decapsulation (replace with actual Kyber)
        shared_secret = os.urandom(self.SHARED_SECRET_SIZE)
        
        return shared_secret
    
    def encrypt_shard_hybrid(
        self,
        shard_data: bytes,
        public_key: bytes
    ) -> Dict[str, bytes]:
        """
        Encrypt a recovery shard using hybrid post-quantum encryption
        
        Process:
        1. Generate ephemeral Kyber shared secret
        2. Derive AES key from shared secret
        3. Encrypt shard data with AES-GCM
        4. Return ciphertext and Kyber encapsulation
        
        Args:
            shard_data: Raw shard bytes
            public_key: Recipient's Kyber public key
        
        Returns:
            Dictionary with encrypted data, ciphertext, nonce
        """
        # Step 1: Kyber key encapsulation
        kyber_ciphertext, shared_secret = self.kyber_encapsulate(public_key)
        
        # Step 2: Derive AES key from shared secret using HKDF
        aes_key = self._derive_aes_key_from_secret(shared_secret)
        
        # Step 3: Encrypt shard with AES-GCM
        aesgcm = AESGCM(aes_key)
        nonce = os.urandom(12)  # 96-bit nonce for GCM
        ciphertext = aesgcm.encrypt(nonce, shard_data, None)
        
        return {
            'kyber_ciphertext': kyber_ciphertext,
            'aes_ciphertext': ciphertext,
            'nonce': nonce,
            'algorithm': 'Kyber-768-AES-256-GCM',
            'version': '1.0'
        }
    
    def decrypt_shard_hybrid(
        self,
        encrypted_shard: Dict[str, bytes],
        private_key: bytes
    ) -> bytes:
        """
        Decrypt a recovery shard using hybrid post-quantum decryption
        
        Args:
            encrypted_shard: Dictionary from encrypt_shard_hybrid
            private_key: Recipient's Kyber private key
        
        Returns:
            Decrypted shard data
        """
        # Step 1: Kyber key decapsulation
        kyber_ciphertext = encrypted_shard['kyber_ciphertext']
        shared_secret = self.kyber_decapsulate(kyber_ciphertext, private_key)
        
        # Step 2: Derive AES key from shared secret
        aes_key = self._derive_aes_key_from_secret(shared_secret)
        
        # Step 3: Decrypt shard with AES-GCM
        aesgcm = AESGCM(aes_key)
        nonce = encrypted_shard['nonce']
        ciphertext = encrypted_shard['aes_ciphertext']
        
        plaintext = aesgcm.decrypt(nonce, ciphertext, None)
        
        return plaintext
    
    def _derive_aes_key_from_secret(self, shared_secret: bytes) -> bytes:
        """
        Derive AES-256 key from Kyber shared secret using HKDF
        
        Args:
            shared_secret: 32-byte Kyber shared secret
        
        Returns:
            32-byte AES key
        """
        # Use SHA-256 based HKDF
        from cryptography.hazmat.primitives.kdf.hkdf import HKDF
        
        hkdf = HKDF(
            algorithm=hashes.SHA256(),
            length=32,  # AES-256 key
            salt=None,
            info=b'quantum-resistant-recovery-shard-encryption',
            backend=self.backend
        )
        
        return hkdf.derive(shared_secret)
    
    def shamir_split_secret(
        self,
        secret: bytes,
        total_shards: int,
        threshold: int
    ) -> list:
        """
        Split secret into Shamir's Secret Sharing shards using proper polynomial interpolation
        
        Args:
            secret: Secret to split (e.g., passkey private key)
            total_shards: Total number of shards to create (n)
            threshold: Minimum shards needed to reconstruct (k)
        
        Returns:
            List of shard tuples (index, shard_bytes)
        """
        from secretsharing import PlaintextToHexSecretSharer
        
        # Convert bytes to hex string for secretsharing library
        secret_hex = secret.hex()
        
        # Split using proper Shamir's Secret Sharing with polynomial interpolation
        shard_strings = PlaintextToHexSecretSharer.split_secret(
            secret_hex,
            threshold,
            total_shards
        )
        
        # Convert back to (index, bytes) tuples
        result = []
        for i, shard_string in enumerate(shard_strings, start=1):
            # Each shard string is in format "index-hexdata"
            # We need to extract just the hex data and convert to bytes
            shard_bytes = shard_string.encode('utf-8')
            result.append((i, shard_bytes))
        
        return result
    
    def shamir_reconstruct_secret(
        self,
        shards: list,
        threshold: int
    ) -> bytes:
        """
        Reconstruct secret from Shamir shards using Lagrange interpolation
        
        Args:
            shards: List of tuples (index, shard_bytes)
            threshold: Minimum shards needed (k)
        
        Returns:
            Reconstructed secret
        """
        from secretsharing import PlaintextToHexSecretSharer
        
        if len(shards) < threshold:
            raise ValueError(f"Insufficient shards: need {threshold}, have {len(shards)}")
        
        # Convert (index, bytes) tuples back to shard strings
        shard_strings = []
        for index, shard_bytes in shards[:threshold]:
            shard_string = shard_bytes.decode('utf-8')
            shard_strings.append(shard_string)
        
        # Reconstruct using proper Shamir's Secret Sharing with Lagrange interpolation
        secret_hex = PlaintextToHexSecretSharer.recover_secret(shard_strings)
        
        # Convert hex string back to bytes
        secret = bytes.fromhex(secret_hex)
        
        return secret
    
    def create_honeypot_shard(self, real_shard_size: int) -> bytes:
        """
        Create a convincing honeypot (decoy) shard that looks legitimate
        but triggers alerts when accessed
        
        Args:
            real_shard_size: Size of real shards for matching
        
        Returns:
            Fake shard data
        """
        # Generate random data that looks like an encrypted shard
        fake_shard = os.urandom(real_shard_size)
        
        # Add a special marker that can be detected server-side
        # In production, use a more sophisticated approach
        marker = hashlib.sha256(b'HONEYPOT_MARKER').digest()[:8]
        fake_shard = marker + fake_shard[8:]
        
        return fake_shard
    
    def is_honeypot_shard(self, shard_data: bytes) -> bool:
        """
        Check if a shard is a honeypot
        
        Args:
            shard_data: Shard to check
        
        Returns:
            True if honeypot, False otherwise
        """
        if len(shard_data) < 8:
            return False
        
        expected_marker = hashlib.sha256(b'HONEYPOT_MARKER').digest()[:8]
        return shard_data[:8] == expected_marker
    
    def encrypt_with_password(
        self,
        data: bytes,
        password: str,
        salt: Optional[bytes] = None
    ) -> Dict[str, bytes]:
        """
        Encrypt data using password-based encryption (for temporal shards)
        Uses Scrypt KDF + AES-GCM
        
        Args:
            data: Data to encrypt
            password: User password
            salt: Optional salt (generated if not provided)
        
        Returns:
            Dictionary with encrypted data and metadata
        """
        if salt is None:
            salt = os.urandom(32)
        
        # Derive key using Scrypt (memory-hard KDF)
        kdf = Scrypt(
            salt=salt,
            length=32,
            n=2**16,  # CPU/memory cost
            r=8,      # Block size
            p=1,      # Parallelization
            backend=self.backend
        )
        key = kdf.derive(password.encode('utf-8'))
        
        # Encrypt with AES-GCM
        aesgcm = AESGCM(key)
        nonce = os.urandom(12)
        ciphertext = aesgcm.encrypt(nonce, data, None)
        
        return {
            'ciphertext': ciphertext,
            'salt': salt,
            'nonce': nonce,
            'algorithm': 'Scrypt-AES-256-GCM',
            'version': '1.0'
        }
    
    def decrypt_with_password(
        self,
        encrypted_data: Dict[str, bytes],
        password: str
    ) -> bytes:
        """
        Decrypt password-encrypted data
        
        Args:
            encrypted_data: Dictionary from encrypt_with_password
            password: User password
        
        Returns:
            Decrypted data
        """
        salt = encrypted_data['salt']
        nonce = encrypted_data['nonce']
        ciphertext = encrypted_data['ciphertext']
        
        # Derive key using Scrypt
        kdf = Scrypt(
            salt=salt,
            length=32,
            n=2**16,
            r=8,
            p=1,
            backend=self.backend
        )
        key = kdf.derive(password.encode('utf-8'))
        
        # Decrypt with AES-GCM
        aesgcm = AESGCM(key)
        plaintext = aesgcm.decrypt(nonce, ciphertext, None)
        
        return plaintext
    
    def serialize_encrypted_shard(self, encrypted_shard: Dict[str, bytes]) -> bytes:
        """
        Serialize encrypted shard dict to bytes for database storage
        
        Args:
            encrypted_shard: Dictionary from encrypt_shard_hybrid
        
        Returns:
            Serialized bytes
        """
        # Convert dict to JSON-serializable format
        serializable = {
            'kyber_ciphertext': base64.b64encode(encrypted_shard['kyber_ciphertext']).decode('utf-8'),
            'aes_ciphertext': base64.b64encode(encrypted_shard['aes_ciphertext']).decode('utf-8'),
            'nonce': base64.b64encode(encrypted_shard['nonce']).decode('utf-8'),
            'algorithm': encrypted_shard['algorithm'],
            'version': encrypted_shard['version']
        }
        
        return json.dumps(serializable).encode('utf-8')
    
    def deserialize_encrypted_shard(self, serialized_shard: bytes) -> Dict[str, bytes]:
        """
        Deserialize encrypted shard from database
        
        Args:
            serialized_shard: Bytes from database
        
        Returns:
            Dictionary suitable for decrypt_shard_hybrid
        """
        data = json.loads(serialized_shard.decode('utf-8'))
        
        return {
            'kyber_ciphertext': base64.b64decode(data['kyber_ciphertext']),
            'aes_ciphertext': base64.b64decode(data['aes_ciphertext']),
            'nonce': base64.b64decode(data['nonce']),
            'algorithm': data['algorithm'],
            'version': data['version']
        }


# Global instance
quantum_crypto_service = QuantumCryptoService()


class Kyber:
    """
    Static wrapper class for Kyber key encapsulation mechanism.
    Provides a simple interface for Kyber operations using the global QuantumCryptoService.
    """
    
    @staticmethod
    def encapsulate(public_key: bytes) -> Tuple[bytes, bytes]:
        """
        Encapsulate a shared secret using a public key.
        
        Args:
            public_key: Kyber public key (bytes)
            
        Returns:
            Tuple of (ciphertext, shared_secret)
        """
        return quantum_crypto_service.kyber_encapsulate(public_key)
    
    @staticmethod
    def decapsulate(private_key: bytes, ciphertext: bytes) -> bytes:
        """
        Decapsulate a shared secret using a private key.
        
        Args:
            private_key: Kyber private key (bytes)
            ciphertext: Kyber ciphertext (bytes)
            
        Returns:
            Shared secret (bytes)
        """
        return quantum_crypto_service.kyber_decapsulate(ciphertext, private_key)
    
    @staticmethod
    def generate_keypair() -> Tuple[bytes, bytes]:
        """
        Generate a new Kyber keypair.
        
        Returns:
            Tuple of (public_key, private_key)
        """
        return quantum_crypto_service.generate_kyber_keypair()


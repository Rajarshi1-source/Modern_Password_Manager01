"""
Post-Quantum Cryptography Service

Hybrid ML-KEM-768 (FIPS 203) + AES-256-GCM encryption for recovery shards,
plus Shamir splitting and password-based helpers. The KEM itself is delegated
to ``auth_module.services.kyber_crypto.ProductionKyber``. Shards written before
the ML-KEM migration used round-3 Kyber768 and still decrypt: every shard
records its KEM in 'algorithm', and decapsulation takes the KEM explicitly.
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

from auth_module.services.kyber_crypto import (
    DEFAULT_KEM,
    KYBER_768,
    ML_KEM_768,
    ProductionKyber,
)

# encrypt_shard_hybrid's 'algorithm' labels, one per KEM. The Kyber768 label
# is the one every shard written before the ML-KEM migration carries.
SHARD_ALGORITHMS = {
    'ML-KEM-768-AES-256-GCM': ML_KEM_768,
    'Kyber-768-AES-256-GCM': KYBER_768,
}
_SHARD_LABELS = {kem: label for label, kem in SHARD_ALGORITHMS.items()}


class QuantumCryptoService:
    """
    Service for quantum-resistant encryption using hybrid approach:
    1. ML-KEM-768 for key encapsulation (post-quantum)
    2. AES-256-GCM for data encryption (classical but proven)

    The KEM is ``kyber_crypto.ProductionKyber`` (liboqs ``ML-KEM-768``, or the
    legacy ``Kyber768`` for data that records it). Its
    simulated fallback is refused unless QUANTUM_CRYPTO['ALLOW_SIMULATION']
    is True. Until F13 (docs/pqc-hybrid-architecture-review.md) this class
    returned fresh ``os.urandom`` bytes from all three KEM methods in every
    environment, so nothing it encrypted could ever be decrypted.
    """

    # Key sizes for ML-KEM-768 (NIST Level 3; same as Kyber768)
    PUBLIC_KEY_SIZE = ProductionKyber.PUBLIC_KEY_SIZE
    PRIVATE_KEY_SIZE = ProductionKyber.PRIVATE_KEY_SIZE
    CIPHERTEXT_SIZE = ProductionKyber.CIPHERTEXT_SIZE
    SHARED_SECRET_SIZE = ProductionKyber.SHARED_SECRET_SIZE

    def __init__(self):
        self.backend = default_backend()

    @staticmethod
    def _kem(kem: str = DEFAULT_KEM) -> ProductionKyber:
        # Built per call rather than once: ProductionKyber picks its
        # implementation when constructed, and the module-level instance
        # below is created at import time.
        return ProductionKyber(algorithm=kem)

    def generate_kyber_keypair(self, kem: str = DEFAULT_KEM) -> Tuple[bytes, bytes]:
        """
        Generate a post-quantum keypair (ML-KEM-768 by default)

        Returns:
            (public_key, private_key): Post-quantum key pair
        """
        return self._kem(kem).generate_keypair()

    def kyber_encapsulate(self, public_key: bytes, kem: str = DEFAULT_KEM) -> Tuple[bytes, bytes]:
        """
        Encapsulate a shared secret using recipient's public key

        Args:
            public_key: Recipient's public key
            kem: The KEM public_key belongs to

        Returns:
            (ciphertext, shared_secret): Encapsulated shared secret and the secret itself
        """
        return self._kem(kem).encapsulate(public_key)

    def kyber_decapsulate(self, ciphertext: bytes, private_key: bytes, *, kem: str) -> bytes:
        """
        Decapsulate shared secret using private key

        Args:
            ciphertext: KEM ciphertext
            private_key: Recipient's private key (the one matching the
                public key the ciphertext was encapsulated to)
            kem: The KEM the stored artefact records. Required, with no
                default: decapsulating with the wrong KEM returns a wrong
                secret instead of raising.

        Returns:
            shared_secret: Decapsulated shared secret
        """
        return self._kem(kem).decapsulate(ciphertext, private_key)

    def encrypt_shard_hybrid(
        self,
        shard_data: bytes,
        public_key: bytes,
        kem: str = DEFAULT_KEM,
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
        # Step 1: KEM key encapsulation
        kyber_ciphertext, shared_secret = self.kyber_encapsulate(public_key, kem)
        
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
            'algorithm': _SHARD_LABELS[kem],
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
        # Step 1: KEM decapsulation, with the KEM the shard records
        label = encrypted_shard.get('algorithm')
        if label not in SHARD_ALGORITHMS:
            raise ValueError(f"Unsupported recovery shard algorithm {label!r}")
        kyber_ciphertext = encrypted_shard['kyber_ciphertext']
        shared_secret = self.kyber_decapsulate(
            kyber_ciphertext, private_key, kem=SHARD_ALGORITHMS[label]
        )
        
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
        from auth_module.services.shamir_py3 import ShamirSecretSharer

        # Convert bytes to hex string for secret sharing
        secret_hex = secret.hex()

        # Split using Shamir's Secret Sharing with polynomial interpolation
        shard_strings = ShamirSecretSharer.split_secret(
            secret_hex,
            threshold,
            total_shards,
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
        from auth_module.services.shamir_py3 import ShamirSecretSharer

        if len(shards) < threshold:
            raise ValueError(f"Insufficient shards: need {threshold}, have {len(shards)}")

        # Convert (index, bytes) tuples back to shard strings
        shard_strings = []
        for index, shard_bytes in shards[:threshold]:
            shard_string = shard_bytes.decode('utf-8')
            shard_strings.append(shard_string)

        # Reconstruct using Shamir's Secret Sharing with Lagrange interpolation
        secret_hex = ShamirSecretSharer.recover_secret(shard_strings)
        
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
    
    # Binary fields of the dicts encrypt_shard_hybrid and encrypt_with_password
    # return; every other field (algorithm, version) is stored as is.
    _BINARY_SHARD_FIELDS = ('kyber_ciphertext', 'aes_ciphertext', 'ciphertext', 'salt', 'nonce')

    def serialize_encrypted_shard(self, encrypted_shard: Dict[str, bytes]) -> bytes:
        """
        Serialize an encrypted dict to bytes for database storage

        Args:
            encrypted_shard: Dictionary from encrypt_shard_hybrid or
                encrypt_with_password

        Returns:
            Serialized bytes
        """
        serializable = {
            key: base64.b64encode(value).decode('utf-8')
            if key in self._BINARY_SHARD_FIELDS else value
            for key, value in encrypted_shard.items()
        }

        return json.dumps(serializable).encode('utf-8')

    def deserialize_encrypted_shard(self, serialized_shard: bytes) -> Dict[str, bytes]:
        """
        Deserialize an encrypted dict from database

        Args:
            serialized_shard: Bytes from database

        Returns:
            Dictionary suitable for decrypt_shard_hybrid or decrypt_with_password
        """
        data = json.loads(bytes(serialized_shard).decode('utf-8'))

        return {
            key: base64.b64decode(value) if key in self._BINARY_SHARD_FIELDS else value
            for key, value in data.items()
        }


# Global instance
quantum_crypto_service = QuantumCryptoService()


class Kyber:
    """
    Static wrapper class for Kyber key encapsulation mechanism.
    Provides a simple interface for Kyber operations using the global QuantumCryptoService.
    """
    
    @staticmethod
    def encapsulate(public_key: bytes, kem: str = DEFAULT_KEM) -> Tuple[bytes, bytes]:
        """
        Encapsulate a shared secret using a public key of the KEM ``kem``.

        Returns:
            Tuple of (ciphertext, shared_secret)
        """
        return quantum_crypto_service.kyber_encapsulate(public_key, kem)

    @staticmethod
    def decapsulate(private_key: bytes, ciphertext: bytes, *, kem: str) -> bytes:
        """
        Decapsulate a shared secret using a private key.

        ``kem`` is the KEM the stored artefact records; there is no default.

        Returns:
            Shared secret (bytes)
        """
        return quantum_crypto_service.kyber_decapsulate(ciphertext, private_key, kem=kem)

    @staticmethod
    def generate_keypair(kem: str = DEFAULT_KEM) -> Tuple[bytes, bytes]:
        """
        Generate a new post-quantum keypair (ML-KEM-768 by default).

        Returns:
            Tuple of (public_key, private_key)
        """
        return quantum_crypto_service.generate_kyber_keypair(kem)

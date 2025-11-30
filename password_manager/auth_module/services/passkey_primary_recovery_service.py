"""
Primary Passkey Recovery Service
Handles encryption/decryption of passkey credentials using Kyber + AES-GCM
"""

import secrets
import hashlib
import base64
import json
import logging
from typing import Dict, Tuple, Optional

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.exceptions import InvalidTag

from ..services.quantum_crypto_service import QuantumCryptoService, Kyber

logger = logging.getLogger(__name__)


class PasskeyPrimaryRecoveryService:
    """
    Service for managing primary passkey recovery with Kyber + AES-GCM encryption.
    """
    
    def __init__(self):
        self.quantum_crypto = QuantumCryptoService()
        self.recovery_key_length = 24  # Characters in recovery key
        self.charset = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'  # Avoid ambiguous characters
    
    def generate_recovery_key(self) -> str:
        """
        Generate a cryptographically secure recovery key.
        Returns a 24-character key formatted as XXXX-XXXX-XXXX-XXXX-XXXX-XXXX.
        """
        random_values = secrets.token_bytes(self.recovery_key_length)
        key_chars = [self.charset[b % len(self.charset)] for b in random_values]
        key = ''.join(key_chars)
        
        # Format with hyphens for readability
        formatted_key = '-'.join([key[i:i+4] for i in range(0, len(key), 4)])
        
        logger.info("Generated new recovery key")
        return formatted_key
    
    def hash_recovery_key(self, recovery_key: str) -> str:
        """Generate SHA-256 hash of recovery key for storage."""
        # Remove hyphens and normalize
        clean_key = recovery_key.replace('-', '').upper()
        key_hash = hashlib.sha256(clean_key.encode()).hexdigest()
        return key_hash
    
    def verify_recovery_key(self, recovery_key: str, stored_hash: str) -> bool:
        """Verify if recovery key matches stored hash."""
        computed_hash = self.hash_recovery_key(recovery_key)
        return computed_hash == stored_hash
    
    def encrypt_passkey_credential(
        self,
        credential_data: Dict,
        recovery_key: str,
        user_kyber_public_key: Optional[bytes] = None
    ) -> Tuple[bytes, Dict]:
        """
        Encrypt passkey credential data using hybrid Kyber + AES-GCM encryption.
        
        Args:
            credential_data: Dictionary containing passkey credential details
            recovery_key: User's recovery key
            user_kyber_public_key: Optional Kyber public key (generated if not provided)
        
        Returns:
            Tuple of (encrypted_data, encryption_metadata)
        """
        try:
            # Generate Kyber keypair if not provided
            if user_kyber_public_key is None:
                user_kyber_public_key, user_kyber_private_key = self.quantum_crypto.generate_kyber_keypair()
            else:
                # In practice, the private key would be derived from the recovery key
                # For this implementation, we'll use a deterministic approach
                user_kyber_private_key = self._derive_kyber_private_key_from_recovery_key(recovery_key)
            
            # Serialize credential data
            credential_json = json.dumps(credential_data).encode('utf-8')
            
            # Generate salt for key derivation
            salt = secrets.token_bytes(32)
            
            # Derive master encryption key from recovery key
            master_key = self._derive_master_key_from_recovery_key(recovery_key, salt)
            master_key_hash = hashlib.sha256(master_key).digest()
            
            # Use Kyber to establish a shared secret
            kyber_ciphertext, kyber_shared_secret = Kyber.encapsulate(user_kyber_public_key)
            
            # Combine master key with Kyber shared secret for additional security
            combined_key_material = master_key + kyber_shared_secret
            
            # Derive AES key using HKDF
            hkdf_salt = secrets.token_bytes(16)
            hkdf = HKDF(
                algorithm=hashes.SHA256(),
                length=32,  # 256-bit AES key
                salt=hkdf_salt,
                info=b'passkey-primary-recovery-v1',
                backend=default_backend()
            )
            aes_key = hkdf.derive(combined_key_material)
            
            # Encrypt with AES-256-GCM
            iv = secrets.token_bytes(12)  # 96-bit IV for GCM
            cipher = Cipher(algorithms.AES(aes_key), modes.GCM(iv), backend=default_backend())
            encryptor = cipher.encryptor()
            
            # Add additional authenticated data
            aad = master_key_hash + user_kyber_public_key[:32]  # Bind to both keys
            encryptor.authenticate_additional_data(aad)
            
            ciphertext = encryptor.update(credential_json) + encryptor.finalize()
            tag = encryptor.tag
            
            # Prepare encryption metadata
            encryption_metadata = {
                'version': 1,
                'algorithm': 'kyber768-aes256-gcm',
                'salt': base64.b64encode(salt).decode('utf-8'),
                'hkdf_salt': base64.b64encode(hkdf_salt).decode('utf-8'),
                'iv': base64.b64encode(iv).decode('utf-8'),
                'tag': base64.b64encode(tag).decode('utf-8'),
                'kyber_ciphertext': base64.b64encode(kyber_ciphertext).decode('utf-8'),
                'kyber_public_key': base64.b64encode(user_kyber_public_key).decode('utf-8'),
                'timestamp': int(secrets.randbits(64))  # Random timestamp for uniqueness
            }
            
            logger.info("Successfully encrypted passkey credential with Kyber + AES-GCM")
            return ciphertext, encryption_metadata
            
        except Exception as e:
            logger.error(f"Error encrypting passkey credential: {e}", exc_info=True)
            raise ValueError(f"Encryption failed: {str(e)}")
    
    def decrypt_passkey_credential(
        self,
        encrypted_data: bytes,
        recovery_key: str,
        encryption_metadata: Dict
    ) -> Dict:
        """
        Decrypt passkey credential data using the recovery key.
        
        Args:
            encrypted_data: Encrypted credential data
            recovery_key: User's recovery key
            encryption_metadata: Metadata needed for decryption
        
        Returns:
            Dictionary containing decrypted credential data
        """
        try:
            # Extract metadata
            salt = base64.b64decode(encryption_metadata['salt'])
            hkdf_salt = base64.b64decode(encryption_metadata['hkdf_salt'])
            iv = base64.b64decode(encryption_metadata['iv'])
            tag = base64.b64decode(encryption_metadata['tag'])
            kyber_ciphertext = base64.b64decode(encryption_metadata['kyber_ciphertext'])
            kyber_public_key = base64.b64decode(encryption_metadata['kyber_public_key'])
            
            # Derive master key from recovery key
            master_key = self._derive_master_key_from_recovery_key(recovery_key, salt)
            master_key_hash = hashlib.sha256(master_key).digest()
            
            # Derive Kyber private key from recovery key
            kyber_private_key = self._derive_kyber_private_key_from_recovery_key(recovery_key)
            
            # Decapsulate Kyber shared secret
            kyber_shared_secret = Kyber.decapsulate(kyber_private_key, kyber_ciphertext)
            
            # Combine keys
            combined_key_material = master_key + kyber_shared_secret
            
            # Derive AES key using HKDF
            hkdf = HKDF(
                algorithm=hashes.SHA256(),
                length=32,
                salt=hkdf_salt,
                info=b'passkey-primary-recovery-v1',
                backend=default_backend()
            )
            aes_key = hkdf.derive(combined_key_material)
            
            # Decrypt with AES-256-GCM
            cipher = Cipher(algorithms.AES(aes_key), modes.GCM(iv, tag), backend=default_backend())
            decryptor = cipher.decryptor()
            
            # Verify AAD
            aad = master_key_hash + kyber_public_key[:32]
            decryptor.authenticate_additional_data(aad)
            
            plaintext = decryptor.update(encrypted_data) + decryptor.finalize()
            
            # Deserialize credential data
            credential_data = json.loads(plaintext.decode('utf-8'))
            
            logger.info("Successfully decrypted passkey credential")
            return credential_data
            
        except InvalidTag:
            logger.error("Decryption failed: Invalid authentication tag (wrong key or tampered data)")
            raise ValueError("Invalid recovery key or tampered data")
        except Exception as e:
            logger.error(f"Error decrypting passkey credential: {e}", exc_info=True)
            raise ValueError(f"Decryption failed: {str(e)}")
    
    def _derive_master_key_from_recovery_key(self, recovery_key: str, salt: bytes) -> bytes:
        """Derive a master encryption key from the recovery key using Argon2id."""
        try:
            import argon2
            
            # Remove hyphens and normalize
            clean_key = recovery_key.replace('-', '').upper()
            
            # Use Argon2id for key derivation (resistant to side-channel attacks)
            hasher = argon2.PasswordHasher(
                time_cost=3,        # Iterations
                memory_cost=65536,  # 64 MB
                parallelism=4,      # Threads
                hash_len=32,        # 256-bit key
                salt_len=32
            )
            
            # Derive key
            derived = hasher.hash(clean_key, salt=salt)
            # Extract raw hash (32 bytes)
            key = derived.encode('utf-8')[-32:]
            
            return key
            
        except ImportError:
            # Fallback to PBKDF2 if argon2 not available
            logger.warning("Argon2 not available, falling back to PBKDF2")
            from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
            
            clean_key = recovery_key.replace('-', '').upper().encode('utf-8')
            
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=salt,
                iterations=100000,
                backend=default_backend()
            )
            return kdf.derive(clean_key)
    
    def _derive_kyber_private_key_from_recovery_key(self, recovery_key: str) -> bytes:
        """
        Derive a deterministic Kyber private key from the recovery key.
        This is a simplified approach for the demo.
        In production, this would use proper key derivation.
        """
        clean_key = recovery_key.replace('-', '').upper().encode('utf-8')
        # Use HKDF to derive a 32-byte seed for Kyber key generation
        hkdf = HKDF(
            algorithm=hashes.SHA256(),
            length=32,
            salt=b'kyber-private-key-derivation',
            info=b'passkey-recovery-v1',
            backend=default_backend()
        )
        seed = hkdf.derive(clean_key)
        
        # For the simulation, return the seed as the "private key"
        # In a real Kyber implementation, this seed would be used to deterministically
        # generate the actual Kyber private key
        return seed
    
    def verify_backup_integrity(
        self,
        encrypted_data: bytes,
        recovery_key: str,
        encryption_metadata: Dict
    ) -> bool:
        """
        Verify that a backup can be decrypted without actually decrypting it fully.
        Uses a quick check mechanism.
        """
        try:
            # Try to decrypt
            self.decrypt_passkey_credential(encrypted_data, recovery_key, encryption_metadata)
            return True
        except Exception as e:
            logger.warning(f"Backup integrity check failed: {e}")
            return False


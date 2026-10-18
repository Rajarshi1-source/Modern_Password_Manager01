"""
Primary Passkey Recovery Service
Handles encryption/decryption of passkey credentials using Kyber + AES-GCM
"""

import secrets
import hashlib
import hmac
import base64
import json
import logging
from typing import Dict, Tuple, Optional

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.exceptions import InvalidTag
from django.core.exceptions import ImproperlyConfigured

from ..services.kyber_crypto import (
    DEFAULT_KEM,
    KYBER_768,
    SUPPORTED_KEMS,
)
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
        return hmac.compare_digest(computed_hash, stored_hash or '')
    
    # Bump when the blob layout changes.
    #   1: before F13. Never stored the private key, and encapsulated with a
    #      KEM that returned random bytes: no version-1 blob can be decrypted.
    #   2: round-3 Kyber768, implied by the version (v2 was only ever written
    #      with Kyber768). Still decrypts; no longer written.
    #   3: records its KEM in metadata['kem'] (ML-KEM-768 for new backups),
    #      and binds that name into the private-key wrap AAD.
    BLOB_VERSION = 3
    LEGACY_BLOB_VERSIONS = {2: KYBER_768}
    _SK_WRAP_INFO = b'passkey-primary-recovery-kyber-sk-wrap-v2'

    def encrypt_passkey_credential(
        self,
        credential_data: Dict,
        recovery_key: str,
    ) -> Tuple[bytes, Dict]:
        """
        Encrypt passkey credential data using hybrid Kyber + AES-GCM encryption.

        A fresh ML-KEM-768 keypair is generated per backup. Its private key
        is stored in the metadata, AES-GCM-wrapped under a key derived from
        the recovery key, so decryption uses exactly the private key that
        matches the stored public key. (liboqs 0.16 can derive an ML-KEM
        keypair from a seed, but Kyber768, pqcrypto and the simulation
        cannot, so the blob keeps the wrapped key rather than depend on it.)

        Args:
            credential_data: Dictionary containing passkey credential details
            recovery_key: User's recovery key

        Returns:
            Tuple of (encrypted_data, encryption_metadata). The Kyber public
            key is in encryption_metadata['kyber_public_key'] (base64).
        """
        kem = DEFAULT_KEM
        try:
            user_kyber_public_key, user_kyber_private_key = (
                self.quantum_crypto.generate_kyber_keypair(kem)
            )

            # Serialize credential data
            credential_json = json.dumps(credential_data).encode('utf-8')

            # Generate salt for key derivation
            salt = secrets.token_bytes(32)

            # Derive master encryption key from recovery key
            master_key = self._derive_master_key_from_recovery_key(recovery_key, salt)
            master_key_hash = hashlib.sha256(master_key).digest()

            # Keep the Kyber private key, wrapped under the recovery key
            sk_iv = secrets.token_bytes(12)
            wrapped_private_key = AESGCM(self._derive_sk_wrap_key(master_key)).encrypt(
                sk_iv,
                user_kyber_private_key,
                self._sk_wrap_aad(user_kyber_public_key, kem, self.BLOB_VERSION),
            )

            # Use the KEM to establish a shared secret
            kyber_ciphertext, kyber_shared_secret = Kyber.encapsulate(user_kyber_public_key, kem)

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
                'version': self.BLOB_VERSION,
                'kem': kem,
                'algorithm': f'{kem.lower()}-aes256-gcm',
                'salt': base64.b64encode(salt).decode('utf-8'),
                'hkdf_salt': base64.b64encode(hkdf_salt).decode('utf-8'),
                'iv': base64.b64encode(iv).decode('utf-8'),
                'tag': base64.b64encode(tag).decode('utf-8'),
                'kyber_ciphertext': base64.b64encode(kyber_ciphertext).decode('utf-8'),
                'kyber_public_key': base64.b64encode(user_kyber_public_key).decode('utf-8'),
                'kyber_private_key_wrapped': base64.b64encode(wrapped_private_key).decode('utf-8'),
                'kyber_private_key_iv': base64.b64encode(sk_iv).decode('utf-8'),
                'timestamp': int(secrets.randbits(64))  # Random timestamp for uniqueness
            }

            logger.info("Successfully encrypted passkey credential with Kyber + AES-GCM")
            return ciphertext, encryption_metadata

        except ImproperlyConfigured:
            # Simulated KEM refused (F7): a deployment error, not bad input.
            raise
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
        version = encryption_metadata.get('version')
        kem = self._blob_kem(version, encryption_metadata)

        try:
            # Extract metadata
            salt = base64.b64decode(encryption_metadata['salt'])
            hkdf_salt = base64.b64decode(encryption_metadata['hkdf_salt'])
            iv = base64.b64decode(encryption_metadata['iv'])
            tag = base64.b64decode(encryption_metadata['tag'])
            kyber_ciphertext = base64.b64decode(encryption_metadata['kyber_ciphertext'])
            kyber_public_key = base64.b64decode(encryption_metadata['kyber_public_key'])
            wrapped_private_key = base64.b64decode(encryption_metadata['kyber_private_key_wrapped'])
            sk_iv = base64.b64decode(encryption_metadata['kyber_private_key_iv'])

            # Derive master key from recovery key
            master_key = self._derive_master_key_from_recovery_key(recovery_key, salt)
            master_key_hash = hashlib.sha256(master_key).digest()

            # Unwrap the Kyber private key that matches the stored public key
            kyber_private_key = AESGCM(self._derive_sk_wrap_key(master_key)).decrypt(
                sk_iv,
                wrapped_private_key,
                self._sk_wrap_aad(kyber_public_key, kem, version),
            )

            # Decapsulate with the KEM the blob was written with
            kyber_shared_secret = Kyber.decapsulate(kyber_private_key, kyber_ciphertext, kem=kem)

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
        except ImproperlyConfigured:
            raise
        except Exception as e:
            logger.error(f"Error decrypting passkey credential: {e}", exc_info=True)
            raise ValueError(f"Decryption failed: {str(e)}")

    @classmethod
    def _derive_sk_wrap_key(cls, master_key: bytes) -> bytes:
        """Key that wraps the Kyber private key; separate from the data key."""
        return HKDF(
            algorithm=hashes.SHA256(),
            length=32,
            salt=None,
            info=cls._SK_WRAP_INFO,
            backend=default_backend()
        ).derive(master_key)

    @classmethod
    def _blob_kem(cls, version, encryption_metadata: Dict) -> str:
        """
        The KEM a blob was written with, or ValueError if it cannot be opened.

        Version 2 implies Kyber768. Version 3 records its KEM, which must be
        one this backend can run; it is never inferred from key sizes.
        """
        if not isinstance(version, (int, type(None))) or isinstance(version, bool):
            raise ValueError(f"Unsupported recovery backup version: {version!r}")
        if version in cls.LEGACY_BLOB_VERSIONS:
            return cls.LEGACY_BLOB_VERSIONS[version]
        if version == cls.BLOB_VERSION:
            kem = encryption_metadata.get('kem')
            if kem not in SUPPORTED_KEMS:
                raise ValueError(f"Unsupported recovery backup KEM: {kem!r}")
            return kem
        # Only missing/older versions are the pre-fix blobs; a newer one
        # must not be called undecryptable and revoked.
        if version is None or version < min(cls.LEGACY_BLOB_VERSIONS):
            raise ValueError(
                "This recovery backup predates the Kyber fix and was never "
                "decryptable. Revoke it and create a new backup."
            )
        raise ValueError(f"Unsupported recovery backup version: {version!r}")

    @staticmethod
    def _sk_wrap_aad(kyber_public_key: bytes, kem: str, version: int) -> bytes:
        # Bind the wrapped private key to its public key, so a swapped
        # public key in the metadata fails here instead of at decapsulation.
        # From version 3 the KEM name is bound too: a blob relabelled to
        # another KEM fails to unwrap instead of decapsulating to a wrong
        # secret. Version 2 keeps its original AAD (it was only Kyber768).
        pk_hash = hashlib.sha256(kyber_public_key).digest()
        if version == 2:
            return b'kyber768-sk|' + pk_hash
        return b'passkey-primary-sk|' + kem.encode('ascii') + b'|' + pk_hash

    def _derive_master_key_from_recovery_key(self, recovery_key: str, salt: bytes) -> bytes:
        """
        Derive a 32-byte master key from the recovery key with Argon2id.

        Uses the raw-hash API. The previous code called
        ``PasswordHasher.hash(..., salt=)``, which argon2-cffi 21.3.0 (the
        pinned version) does not accept, so every backup failed to encrypt;
        it also took the last 32 characters of the encoded hash string rather
        than the raw hash. No PBKDF2 fallback: a different KDF in another
        environment would silently derive a key that cannot open the backup.
        """
        from argon2.low_level import Type, hash_secret_raw

        clean_key = recovery_key.replace('-', '').upper().encode('utf-8')
        return hash_secret_raw(
            secret=clean_key,
            salt=salt,
            time_cost=3,         # Iterations
            memory_cost=65536,   # 64 MiB
            parallelism=4,
            hash_len=32,         # 256-bit key
            type=Type.ID,
        )

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


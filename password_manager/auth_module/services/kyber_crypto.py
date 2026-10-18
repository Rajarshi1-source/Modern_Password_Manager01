"""
Production-Ready Post-Quantum KEM Integration (FIPS 203 ML-KEM-768)

This module provides real post-quantum cryptography using ML-KEM-768
(FIPS 203). Round-3 Kyber768 is kept only to decrypt data written before the
ML-KEM migration: see ``KYBER_768`` below.
Without liboqs (or pqcrypto) it can fall back to a simulated KEM, but only
when QUANTUM_CRYPTO['ALLOW_SIMULATION'] is True; otherwise every operation
raises ImproperlyConfigured.

Security Level: NIST Level 3 (ML-KEM-768)

Note: In local development without Docker, the code uses simulated Kyber.
      In production (Docker), liboqs is compiled and installed for real PQC.
"""

import os
import logging
import hashlib
import base64
import importlib
from typing import Tuple, Optional
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.backends import default_backend

logger = logging.getLogger(__name__)

# Track if warnings have been shown (to avoid spam during startup)
_warnings_shown = {'liboqs': False, 'pqcrypto': False, 'simulation': False}

# Check if we're in development mode
_DEBUG_MODE = os.environ.get('DEBUG', 'True').lower() == 'true'
_IN_DOCKER = os.path.exists('/.dockerenv') or os.environ.get('DOCKER_CONTAINER', False)
_SUPPRESS_CRYPTO_WARNINGS = _DEBUG_MODE and not _IN_DOCKER

# KEM names, spelled as liboqs spells them.
#
# FIPS 203 ML-KEM-768 and round-3 Kyber768 have the same sizes (public key
# 1184, secret key 2400, ciphertext 1088, shared secret 32 bytes) but are NOT
# interoperable: FIPS 203 changed the key derivation and implicit rejection.
# Decapsulating with the wrong one does not raise; it returns an unrelated
# (implicit-rejection) secret. So every stored artefact records which KEM it
# used, decryption dispatches on that record, and nothing infers the KEM from
# key or ciphertext sizes.
ML_KEM_768 = 'ML-KEM-768'
# Legacy: everything this backend wrote before the ML-KEM migration. It still
# decapsulates (and encapsulates to an existing Kyber768 public key), but no
# new Kyber768 keypair is generated.
KYBER_768 = 'Kyber768'
DEFAULT_KEM = ML_KEM_768
SUPPORTED_KEMS = (ML_KEM_768, KYBER_768)
LEGACY_KEMS = (KYBER_768,)

# HybridKyberEncryption's 'algorithm' labels, one per KEM.
HYBRID_ALGORITHMS = {
    'ML-KEM-768-AES256-GCM': ML_KEM_768,
    'Kyber768-AES256-GCM': KYBER_768,
}


def require_supported_kem(kem: str) -> str:
    """Return ``kem`` if this module supports it, else raise ValueError."""
    if kem not in SUPPORTED_KEMS:
        raise ValueError(
            f"Unsupported KEM {kem!r}; expected one of {', '.join(SUPPORTED_KEMS)}"
        )
    return kem


def hybrid_algorithm_for_kem(kem: str) -> str:
    """The HybridKyberEncryption 'algorithm' label recorded for ``kem``."""
    return f"{require_supported_kem(kem)}-AES256-GCM"


def kem_for_hybrid_algorithm(label: Optional[str]) -> str:
    """
    The KEM a HybridKyberEncryption blob was written with.

    A blob without a label is legacy Kyber768: before the ML-KEM migration
    Kyber768 was the only KEM, and the decrypt endpoint never forwarded the
    label the encrypt endpoint returned. An unknown label is refused, not
    guessed.
    """
    if not label:
        return KYBER_768
    try:
        return HYBRID_ALGORITHMS[label]
    except KeyError:
        raise ValueError(f"Unsupported hybrid encryption algorithm {label!r}") from None


# Try to import liboqs for the real KEMs
LIBOQS_AVAILABLE = False
oqs = None

try:
    import oqs as oqs_lib
    oqs = oqs_lib
    LIBOQS_AVAILABLE = True
    logger.info("liboqs-python loaded - using real ML-KEM-768")
except (ImportError, Exception, SystemExit):
    if not _warnings_shown['liboqs'] and not _SUPPRESS_CRYPTO_WARNINGS:
        _warnings_shown['liboqs'] = True
        if not _DEBUG_MODE:
            logger.warning("[WARNING] liboqs-python not available - using simulated Kyber (NOT for production)")

# Try pqcrypto as alternative. Current pqcrypto releases ship ml_kem_768 and
# no kyber768; older ones are the reverse. Keep whichever is present.
PQCRYPTO_AVAILABLE = False
_PQCRYPTO_KEMS = {}

if not LIBOQS_AVAILABLE:
    for _kem_name, _module_name in ((ML_KEM_768, 'ml_kem_768'), (KYBER_768, 'kyber768')):
        try:
            _PQCRYPTO_KEMS[_kem_name] = importlib.import_module(f'pqcrypto.kem.{_module_name}')
        except ImportError:
            pass
    PQCRYPTO_AVAILABLE = bool(_PQCRYPTO_KEMS)
    if PQCRYPTO_AVAILABLE:
        logger.info("pqcrypto loaded - KEMs: %s", ', '.join(_PQCRYPTO_KEMS))
    elif not _warnings_shown['pqcrypto'] and not _SUPPRESS_CRYPTO_WARNINGS:
        _warnings_shown['pqcrypto'] = True
        if not _DEBUG_MODE:
            logger.warning("[WARNING] pqcrypto not available - using simulated Kyber (NOT for production)")


def _require_simulation_allowed() -> None:
    """
    Refuse the simulated KEM unless QUANTUM_CRYPTO['ALLOW_SIMULATION'] is True.

    Checked per operation rather than at construction, because the module-level
    instances below are built at import time. Same switch as LatticeCryptoEngine:
    True for DEBUG, tests and passive management commands; False when serving
    in production (settings/base.py). Missing means False (fail closed).
    """
    from django.conf import settings
    if not getattr(settings, 'QUANTUM_CRYPTO', {}).get('ALLOW_SIMULATION', False):
        from django.core.exceptions import ImproperlyConfigured
        raise ImproperlyConfigured(
            "Refusing simulated Kyber: neither liboqs nor pqcrypto is available "
            "and QUANTUM_CRYPTO['ALLOW_SIMULATION'] is False. The simulation is "
            "NOT post-quantum (or even a real KEM) and must never run in production."
        )


class ProductionKyber:
    """
    Production-ready post-quantum KEM (ML-KEM-768 by default).
    Uses liboqs-python or pqcrypto for real post-quantum cryptography.
    Falls back to simulation only in development mode.

    One instance runs one KEM (``algorithm``). Decrypting a stored artefact
    must use the KEM that artefact records, not the default.
    """

    # Key sizes for ML-KEM-768 and Kyber768 (NIST Level 3; identical)
    PUBLIC_KEY_SIZE = 1184
    PRIVATE_KEY_SIZE = 2400
    CIPHERTEXT_SIZE = 1088
    SHARED_SECRET_SIZE = 32

    def __init__(self, allow_simulation: bool = True, algorithm: str = DEFAULT_KEM):
        """
        Initialize the KEM implementation.

        Args:
            allow_simulation: If True, allows falling back to simulation.
                             Set to False in production to enforce real PQC.
            algorithm: ML_KEM_768 (default) or the legacy KYBER_768.
        """
        self.allow_simulation = allow_simulation
        self.algorithm = require_supported_kem(algorithm)
        self.backend = default_backend()

        # Determine which implementation to use
        if LIBOQS_AVAILABLE:
            self.implementation = 'liboqs'
            logger.debug("Using liboqs implementation of %s", self.algorithm)
        elif PQCRYPTO_AVAILABLE:
            self.implementation = 'pqcrypto'
            logger.debug("Using pqcrypto implementation of %s", self.algorithm)
        elif allow_simulation:
            self.implementation = 'simulation'
            if not _warnings_shown['simulation'] and not _SUPPRESS_CRYPTO_WARNINGS:
                _warnings_shown['simulation'] = True
                if not _DEBUG_MODE:
                    logger.warning("Using SIMULATED Kyber - NOT SECURE FOR PRODUCTION")
        else:
            raise RuntimeError(
                "No post-quantum cryptography library available. "
                "Please install liboqs-python or pqcrypto: "
                "pip install liboqs-python or pip install pqcrypto"
            )

    @property
    def is_real_pqc(self) -> bool:
        """Check if using real post-quantum cryptography."""
        return self.implementation in ('liboqs', 'pqcrypto')

    def generate_keypair(self) -> Tuple[bytes, bytes]:
        """
        Generate a keypair for this instance's KEM.

        Returns:
            (public_key, private_key): Post-quantum key pair

        Raises:
            ValueError: for a legacy KEM (Kyber768). Existing Kyber768 data
                still decrypts, but no new Kyber768 keys are made.
        """
        if self.algorithm in LEGACY_KEMS:
            raise ValueError(
                f"{self.algorithm} is kept for decrypting existing data only; "
                f"generate new keys with {DEFAULT_KEM}."
            )
        if self.implementation == 'liboqs':
            return self._generate_keypair_liboqs()
        elif self.implementation == 'pqcrypto':
            return self._generate_keypair_pqcrypto()
        else:
            _require_simulation_allowed()
            return self._generate_keypair_simulation()

    def encapsulate(self, public_key: bytes) -> Tuple[bytes, bytes]:
        """
        Encapsulate a shared secret using recipient's public key.

        Args:
            public_key: Recipient's public key, for this instance's KEM

        Returns:
            (ciphertext, shared_secret): Encapsulated key and shared secret
        """
        if self.implementation == 'liboqs':
            return self._encapsulate_liboqs(public_key)
        elif self.implementation == 'pqcrypto':
            return self._encapsulate_pqcrypto(public_key)
        else:
            _require_simulation_allowed()
            return self._encapsulate_simulation(public_key)

    def decapsulate(self, ciphertext: bytes, private_key: bytes) -> bytes:
        """
        Decapsulate shared secret using private key.

        Args:
            ciphertext: KEM ciphertext
            private_key: Recipient's private key, for this instance's KEM

        Returns:
            shared_secret: Decapsulated shared secret
        """
        if self.implementation == 'liboqs':
            return self._decapsulate_liboqs(ciphertext, private_key)
        elif self.implementation == 'pqcrypto':
            return self._decapsulate_pqcrypto(ciphertext, private_key)
        else:
            _require_simulation_allowed()
            return self._decapsulate_simulation(ciphertext, private_key)

    # ==================== liboqs Implementation ====================

    # Always via `with`: liboqs-python's KeyEncapsulation has no __del__
    # (checked at 0.10.0 and 0.16.0.1), so only free() (called by __exit__)
    # cleanses its native secret-key buffer and releases the native OQS_KEM.
    # The bytes returned to callers are Python copies and are not cleansed.

    def _generate_keypair_liboqs(self) -> Tuple[bytes, bytes]:
        """Generate keypair using liboqs."""
        with oqs.KeyEncapsulation(self.algorithm) as kem:
            public_key = kem.generate_keypair()
            private_key = kem.export_secret_key()
        return public_key, private_key

    def _encapsulate_liboqs(self, public_key: bytes) -> Tuple[bytes, bytes]:
        """Encapsulate using liboqs."""
        with oqs.KeyEncapsulation(self.algorithm) as kem:
            ciphertext, shared_secret = kem.encap_secret(public_key)
        return ciphertext, shared_secret

    def _decapsulate_liboqs(self, ciphertext: bytes, private_key: bytes) -> bytes:
        """Decapsulate using liboqs."""
        with oqs.KeyEncapsulation(self.algorithm, private_key) as kem:
            shared_secret = kem.decap_secret(ciphertext)
        return shared_secret

    # ==================== pqcrypto Implementation ====================

    def _pqcrypto_kem(self):
        try:
            return _PQCRYPTO_KEMS[self.algorithm]
        except KeyError:
            raise RuntimeError(
                f"The installed pqcrypto has no {self.algorithm} "
                f"(it provides: {', '.join(_PQCRYPTO_KEMS) or 'none'})."
            ) from None

    def _generate_keypair_pqcrypto(self) -> Tuple[bytes, bytes]:
        """Generate keypair using pqcrypto."""
        public_key, private_key = self._pqcrypto_kem().generate_keypair()
        return public_key, private_key

    def _encapsulate_pqcrypto(self, public_key: bytes) -> Tuple[bytes, bytes]:
        """Encapsulate using pqcrypto."""
        ciphertext, shared_secret = self._pqcrypto_kem().encrypt(public_key)
        return ciphertext, shared_secret

    def _decapsulate_pqcrypto(self, ciphertext: bytes, private_key: bytes) -> bytes:
        """Decapsulate using pqcrypto."""
        shared_secret = self._pqcrypto_kem().decrypt(private_key, ciphertext)
        return shared_secret

    # ==================== Simulation Implementation ====================
    # WARNING: Only for development/testing - NOT SECURE
    #
    # Laid out like a real ML-KEM-768 / Kyber768 secret key
    # (indcpa_sk || pk || H(pk) || z), so decapsulation can recover the public
    # key from the private key and reproduce the encapsulated secret. Anyone
    # holding the PUBLIC key can compute the shared secret too: this is a
    # functional stand-in that lets round trips work in DEBUG and tests, not a
    # KEM. The secret also depends on the KEM name, so, as with the real KEMs,
    # decapsulating with the wrong one yields an unrelated secret.

    _SIM_PK_OFFSET = 1152
    _SIM_TAGS = {
        KYBER_768: b'simulated-kyber768|',
        ML_KEM_768: b'simulated-ml-kem-768|',
    }

    def _generate_keypair_simulation(self) -> Tuple[bytes, bytes]:
        """
        SIMULATION ONLY - Generate fake keypair.
        WARNING: Not cryptographically secure!
        """
        logger.debug("SIMULATION: Generating fake Kyber keypair")
        public_key = os.urandom(self.PUBLIC_KEY_SIZE)
        private_key = (
            os.urandom(self._SIM_PK_OFFSET)
            + public_key
            + hashlib.sha256(public_key).digest()
            + os.urandom(32)
        )
        return public_key, private_key

    def _simulated_secret(self, public_key: bytes, ciphertext: bytes) -> bytes:
        return hashlib.sha256(self._SIM_TAGS[self.algorithm] + public_key + ciphertext).digest()

    def _encapsulate_simulation(self, public_key: bytes) -> Tuple[bytes, bytes]:
        """
        SIMULATION ONLY - Generate fake encapsulation.
        WARNING: Not cryptographically secure!
        """
        logger.debug("SIMULATION: Generating fake encapsulation")
        ciphertext = os.urandom(self.CIPHERTEXT_SIZE)
        return ciphertext, self._simulated_secret(public_key, ciphertext)

    def _decapsulate_simulation(self, ciphertext: bytes, private_key: bytes) -> bytes:
        """
        SIMULATION ONLY - Recompute the secret from the embedded public key.
        WARNING: Not cryptographically secure!
        """
        logger.debug("SIMULATION: Returning simulated shared secret")
        public_key = private_key[self._SIM_PK_OFFSET:self._SIM_PK_OFFSET + self.PUBLIC_KEY_SIZE]
        return self._simulated_secret(public_key, ciphertext)


class HybridKyberEncryption:
    """
    Hybrid encryption using a post-quantum KEM (ML-KEM-768) + AES-256-GCM.

    Each blob records its KEM in 'algorithm' (HYBRID_ALGORITHMS), and
    decrypt() uses the KEM the blob names.

    This provides:
    1. Post-quantum security from ML-KEM
    2. Proven symmetric encryption from AES-GCM
    3. Forward secrecy through ephemeral keys
    """

    def __init__(self, allow_simulation: bool = True):
        self.allow_simulation = allow_simulation
        self.kyber = ProductionKyber(allow_simulation=allow_simulation)
        self.backend = default_backend()

    def _kem(self, kem: str) -> ProductionKyber:
        if kem == self.kyber.algorithm:
            return self.kyber
        return ProductionKyber(allow_simulation=self.allow_simulation, algorithm=kem)

    @property
    def is_real_pqc(self) -> bool:
        """Check if using real post-quantum cryptography."""
        return self.kyber.is_real_pqc

    def encrypt(
        self,
        plaintext: bytes,
        recipient_public_key: bytes,
        associated_data: Optional[bytes] = None,
        kem: str = DEFAULT_KEM,
    ) -> dict:
        """
        Encrypt data using hybrid KEM + AES-GCM encryption.

        Args:
            plaintext: Data to encrypt
            recipient_public_key: Recipient's public key
            associated_data: Optional AAD for AEAD encryption
            kem: The KEM of recipient_public_key. It must match the key:
                encapsulating to a Kyber768 key with ML-KEM-768 "works" and
                produces a blob the matching private key cannot open.

        Returns:
            Dictionary containing all encrypted components
        """
        # Step 1: KEM encapsulation
        kyber_ciphertext, shared_secret = self._kem(kem).encapsulate(recipient_public_key)

        # Step 2: Derive AES key using HKDF
        hkdf = HKDF(
            algorithm=hashes.SHA256(),
            length=32,  # AES-256
            salt=None,
            info=b'kyber-hybrid-encryption-v1',
            backend=self.backend
        )
        aes_key = hkdf.derive(shared_secret)

        # Step 3: Encrypt with AES-256-GCM
        aesgcm = AESGCM(aes_key)
        nonce = os.urandom(12)  # 96-bit nonce
        ciphertext = aesgcm.encrypt(nonce, plaintext, associated_data)

        return {
            'kyber_ciphertext': base64.b64encode(kyber_ciphertext).decode('utf-8'),
            'aes_ciphertext': base64.b64encode(ciphertext).decode('utf-8'),
            'nonce': base64.b64encode(nonce).decode('utf-8'),
            'aad_hash': hashlib.sha256(associated_data).hexdigest() if associated_data else None,
            'algorithm': hybrid_algorithm_for_kem(kem),
            'version': '2.0',
            'is_real_pqc': self.is_real_pqc
        }

    def decrypt(
        self,
        encrypted_data: dict,
        private_key: bytes,
        associated_data: Optional[bytes] = None
    ) -> bytes:
        """
        Decrypt data using hybrid KEM + AES-GCM decryption.

        Args:
            encrypted_data: Dictionary from encrypt(). Its 'algorithm' picks
                the KEM (kem_for_hybrid_algorithm).
            private_key: Recipient's private key
            associated_data: Optional AAD (must match encryption)

        Returns:
            Decrypted plaintext
        """
        kem = kem_for_hybrid_algorithm(encrypted_data.get('algorithm'))

        # Extract components
        kyber_ciphertext = base64.b64decode(encrypted_data['kyber_ciphertext'])
        aes_ciphertext = base64.b64decode(encrypted_data['aes_ciphertext'])
        nonce = base64.b64decode(encrypted_data['nonce'])

        # Verify AAD hash if provided
        if encrypted_data.get('aad_hash') and associated_data:
            expected_hash = hashlib.sha256(associated_data).hexdigest()
            if encrypted_data['aad_hash'] != expected_hash:
                raise ValueError("Associated data hash mismatch")

        # Step 1: KEM decapsulation, with the KEM the blob was written with
        shared_secret = self._kem(kem).decapsulate(kyber_ciphertext, private_key)

        # Step 2: Derive AES key using HKDF
        hkdf = HKDF(
            algorithm=hashes.SHA256(),
            length=32,
            salt=None,
            info=b'kyber-hybrid-encryption-v1',
            backend=self.backend
        )
        aes_key = hkdf.derive(shared_secret)

        # Step 3: Decrypt with AES-256-GCM
        aesgcm = AESGCM(aes_key)
        plaintext = aesgcm.decrypt(nonce, aes_ciphertext, associated_data)

        return plaintext


# Global instances for convenience
production_kyber = ProductionKyber(allow_simulation=True)
hybrid_encryption = HybridKyberEncryption(allow_simulation=True)


def get_crypto_status() -> dict:
    """Get status of cryptographic implementations."""
    return {
        'liboqs_available': LIBOQS_AVAILABLE,
        'pqcrypto_available': PQCRYPTO_AVAILABLE,
        'using_real_pqc': production_kyber.is_real_pqc,
        'implementation': production_kyber.implementation,
        'algorithm': production_kyber.algorithm,
        'legacy_decrypt_only': list(LEGACY_KEMS),
        'security_level': 'NIST Level 3',
        'warnings': [] if production_kyber.is_real_pqc else [
            'Using SIMULATED post-quantum cryptography',
            'NOT SECURE FOR PRODUCTION USE',
            'Install liboqs-python or pqcrypto for real PQC'
        ]
    }

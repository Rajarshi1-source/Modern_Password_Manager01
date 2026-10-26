"""
Wire formats for recovery shares sealed on the client.

Guardian recovery (``auth_module.quantum_recovery_views``) and social recovery
(``social_recovery``) both split the recovery seed on the owner's device and
seal each share to a guardian's hybrid X25519 + ML-KEM-768 public key there
(``frontend/src/services/quantum/hybridKem.js``). The server stores and relays
these values; it never holds a key that opens them, so it only checks their
shape here.

Hybrid public key (base64): ``x25519_public (32) || ml_kem_768_ek (1184)``.

Sealed share (base64)::

    version 0x01 (1) || x25519_ephemeral (32) || ml_kem_768_ct (1088)
        || nonce (12) || AES-256-GCM ciphertext and tag

    key = HKDF-SHA256(ikm = ss_mlkem || ss_x25519, salt = "",
                      info = "pwm-hybrid-kem-v1" || ml_kem_ct || x25519_ephemeral
                             || recipient_x25519 || SHA-256(recipient_ml_kem_ek))

Share proof: the share holder proves it can open its sealed share (and so
holds the private key) with ``HMAC-SHA256(share, "pwm-recovery-share-proof-v1|"
|| SHA-256(hybrid public key))``. The owner sends SHA-256 of that proof at
setup; the server compares digests and never sees the share.

Seed check: ``SHA-256("pwm-recovery-seed-check-v1|" || seed)``, sent at setup
and returned at completion so the requester's device can tell a correct
reconstruction from a wrong one. The seed is 32 random bytes, so the digest
does not help a guess.
"""

import base64
import binascii
import hashlib
import hmac

from auth_module.services.kyber_crypto import ml_kem_768_public_key_is_valid

HYBRID_KEM_ALGORITHM = 'X25519MLKEM768-HKDF-SHA256-AES256GCM-v1'
SHARE_FORMAT = 'gf256-shamir-v1'

X25519_PUBLIC_KEY_SIZE = 32
ML_KEM_768_PUBLIC_KEY_SIZE = 1184
ML_KEM_768_CIPHERTEXT_SIZE = 1088
HYBRID_PUBLIC_KEY_SIZE = X25519_PUBLIC_KEY_SIZE + ML_KEM_768_PUBLIC_KEY_SIZE

SEALED_SHARE_VERSION = 1
_SEALED_HEADER_SIZE = 1 + X25519_PUBLIC_KEY_SIZE + ML_KEM_768_CIPHERTEXT_SIZE + 12
_GCM_TAG_SIZE = 16
# A share is one index byte plus the 32-byte seed's share; leave room for a
# longer secret but refuse blobs that are clearly not a share.
_MAX_SHARE_PLAINTEXT = 512

DIGEST_SIZE = 32


# What a caller tells the client when a decoder returns None. Fixed text
# (no exception message reaches a response).
INVALID_HYBRID_PUBLIC_KEY = (
    f'must be a base64 X25519 + ML-KEM-768 public key ({HYBRID_PUBLIC_KEY_SIZE} bytes) '
    "from the holder's own device")
INVALID_SEALED_SHARE = f'must be a base64 sealed share ({HYBRID_KEM_ALGORITHM})'
INVALID_DIGEST = f'must be a base64 {DIGEST_SIZE}-byte SHA-256 digest'


def _b64(value):
    if not isinstance(value, str) or not value:
        return None
    try:
        return base64.b64decode(value, validate=True)
    except (binascii.Error, ValueError):
        return None


def decode_hybrid_public_key(value):
    """The raw client hybrid public key, or None if ``value`` is not one."""
    raw = _b64(value)
    if (raw is None or len(raw) != HYBRID_PUBLIC_KEY_SIZE
            or not any(raw[:X25519_PUBLIC_KEY_SIZE])
            or not ml_kem_768_public_key_is_valid(raw[X25519_PUBLIC_KEY_SIZE:])):
        return None
    return raw


def decode_sealed_share(value):
    """The raw sealed share, or None if ``value`` does not have its shape."""
    raw = _b64(value)
    if raw is None or raw[:1] != bytes([SEALED_SHARE_VERSION]):
        return None
    body = len(raw) - _SEALED_HEADER_SIZE
    if not _GCM_TAG_SIZE < body <= _GCM_TAG_SIZE + _MAX_SHARE_PLAINTEXT:
        return None
    return raw


def decode_digest(value):
    """The raw SHA-256 digest, or None."""
    raw = _b64(value)
    return raw if raw is not None and len(raw) == DIGEST_SIZE else None


def share_proof_matches(proof_b64, stored_proof_hash) -> bool:
    """True if SHA-256 of the presented share proof is the stored digest."""
    stored = bytes(stored_proof_hash or b'')
    proof = _b64(proof_b64)
    if len(stored) != DIGEST_SIZE or proof is None:
        return False
    return hmac.compare_digest(hashlib.sha256(proof).digest(), stored)


def b64(raw) -> str:
    return base64.b64encode(bytes(raw)).decode('ascii')

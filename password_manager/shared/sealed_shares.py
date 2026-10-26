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


def _b64(value, field):
    if not isinstance(value, str) or not value:
        raise ValueError(f"'{field}' must be a base64 string")
    try:
        return base64.b64decode(value, validate=True)
    except (binascii.Error, ValueError):
        raise ValueError(f"'{field}' is not valid base64")


def decode_hybrid_public_key(value, field='public_key') -> bytes:
    """Decode and check a client hybrid public key; raise ValueError."""
    raw = _b64(value, field)
    if len(raw) != HYBRID_PUBLIC_KEY_SIZE:
        raise ValueError(
            f"'{field}' must be an X25519 + ML-KEM-768 public key "
            f"({HYBRID_PUBLIC_KEY_SIZE} bytes)")
    if not any(raw[:X25519_PUBLIC_KEY_SIZE]):
        raise ValueError(f"'{field}' has an all-zero X25519 key")
    if not ml_kem_768_public_key_is_valid(raw[X25519_PUBLIC_KEY_SIZE:]):
        raise ValueError(f"'{field}' has an invalid ML-KEM-768 key")
    return raw


def decode_sealed_share(value, field='sealed_share') -> bytes:
    """Decode and check the shape of a sealed share; raise ValueError."""
    raw = _b64(value, field)
    body = len(raw) - _SEALED_HEADER_SIZE
    if raw[:1] != bytes([SEALED_SHARE_VERSION]) or not (
            _GCM_TAG_SIZE < body <= _GCM_TAG_SIZE + _MAX_SHARE_PLAINTEXT):
        raise ValueError(f"'{field}' is not a sealed share ({HYBRID_KEM_ALGORITHM})")
    return raw


def decode_digest(value, field) -> bytes:
    """Decode a base64 SHA-256 digest; raise ValueError."""
    raw = _b64(value, field)
    if len(raw) != DIGEST_SIZE:
        raise ValueError(f"'{field}' must be a {DIGEST_SIZE}-byte digest")
    return raw


def share_proof_matches(proof_b64, stored_proof_hash) -> bool:
    """True if SHA-256 of the presented share proof is the stored digest."""
    stored = bytes(stored_proof_hash or b'')
    if len(stored) != DIGEST_SIZE:
        return False
    try:
        proof = _b64(proof_b64, 'share_proof')
    except ValueError:
        return False
    return hmac.compare_digest(hashlib.sha256(proof).digest(), stored)


def b64(raw) -> str:
    return base64.b64encode(bytes(raw)).decode('ascii')

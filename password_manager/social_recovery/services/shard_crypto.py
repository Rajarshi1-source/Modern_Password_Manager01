"""Authenticated encryption of Shamir shards to a voucher's public key.

Replaces the prior "encrypt with SHA-256(public_key)" construction (which was
effectively unencrypted: anyone with the voucher's published Ed25519 public key
could recompute the key) with a proper X25519-wrap-to-recipient scheme.

Construction
------------
Each shard is sealed with ephemeral-static X25519 + HKDF-SHA256 + AES-256-GCM:

    1. Derive the recipient's X25519 public key from their Ed25519 public key
       via the standard birational map (y -> u = (1+y)/(1-y) mod p).
    2. Generate a fresh ephemeral X25519 keypair for this shard.
    3. shared = ECDH(ephemeral_priv, recipient_x25519_pub).
    4. kek = HKDF-SHA256(shared, info = domain || ephemeral_pub || recipient).
    5. Encrypt shard with AES-256-GCM under ``kek`` with a random 96-bit nonce.

Ciphertext layout (bytes): ``version (1) || eph_pub (32) || nonce (12) || ct``

The recipient decrypts by converting their Ed25519 private seed to an X25519
private scalar (SHA-512 clamp) and running the same ECDH + HKDF.

This gives forward secrecy for the symmetric key (ephemeral senders) and
prevents trivial DB-leak decryption: an attacker who only reads the database
still needs the voucher's Ed25519 *private* key to unwrap the shard.
"""
from __future__ import annotations

import hashlib
import secrets as _secrets

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric.x25519 import (
    X25519PrivateKey,
    X25519PublicKey,
)
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    PublicFormat,
)


SHARD_CRYPTO_VERSION = 2
SHARE_ENCRYPTION_ALGORITHM = "x25519-hkdf-sha256-aesgcm-v2"
_HKDF_INFO_PREFIX = b"pwm-social-recovery-v2|shard-wrap"
_AAD_PREFIX = b"pwm-social-recovery-v2"

_P25519 = (1 << 255) - 19


def _ed25519_pub_to_x25519(ed_pub: bytes) -> bytes:
    """Convert an Ed25519 public key to its X25519 counterpart (u-coordinate).

    Uses the birational map ``u = (1 + y) / (1 - y) mod p`` where ``y`` is the
    y-coordinate of the decoded Edwards point (ignoring the sign bit).
    """
    if len(ed_pub) != 32:
        raise ValueError("Ed25519 public key must be 32 bytes")
    y = int.from_bytes(ed_pub, "little") & ((1 << 255) - 1)
    denom = (1 - y) % _P25519
    if denom == 0:
        raise ValueError("invalid Ed25519 public key for X25519 conversion")
    u = ((1 + y) * pow(denom, _P25519 - 2, _P25519)) % _P25519
    return u.to_bytes(32, "little")


def ed25519_priv_to_x25519(ed_priv_seed: bytes) -> bytes:
    """Derive an X25519 private scalar from an Ed25519 32-byte private seed."""
    if len(ed_priv_seed) != 32:
        raise ValueError("Ed25519 private seed must be 32 bytes")
    h = bytearray(hashlib.sha512(ed_priv_seed).digest()[:32])
    h[0] &= 248
    h[31] &= 127
    h[31] |= 64
    return bytes(h)


def _derive_kek(shared: bytes, eph_pub: bytes, recipient_x25519_pub: bytes,
                recipient_label: bytes) -> bytes:
    return HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=None,
        info=_HKDF_INFO_PREFIX + b"|" + eph_pub + b"|" + recipient_x25519_pub
             + b"|" + recipient_label,
    ).derive(shared)


def encrypt_shard(share: str, ed25519_public_key_multibase: str,
                  decoded_ed25519_pub: bytes) -> bytes:
    """Seal ``share`` to the voucher's Ed25519 public key.

    ``decoded_ed25519_pub`` is the raw 32-byte key; ``ed25519_public_key_multibase``
    is the ``z...`` identifier used as AAD so ciphertexts cannot be transplanted
    between recipients without detection.
    """
    recipient_x = _ed25519_pub_to_x25519(decoded_ed25519_pub)
    recipient_pub = X25519PublicKey.from_public_bytes(recipient_x)
    ephemeral = X25519PrivateKey.generate()
    ephemeral_pub_bytes = ephemeral.public_key().public_bytes(
        Encoding.Raw, PublicFormat.Raw
    )
    shared = ephemeral.exchange(recipient_pub)
    kek = _derive_kek(
        shared, ephemeral_pub_bytes, recipient_x,
        ed25519_public_key_multibase.encode("utf-8"),
    )
    nonce = _secrets.token_bytes(12)
    aad = _AAD_PREFIX + b"|" + ed25519_public_key_multibase.encode("utf-8")
    ciphertext = AESGCM(kek).encrypt(nonce, share.encode("utf-8"), aad)
    return bytes([SHARD_CRYPTO_VERSION]) + ephemeral_pub_bytes + nonce + ciphertext


def decrypt_shard(blob: bytes, ed25519_public_key_multibase: str,
                  ed25519_private_seed: bytes) -> str:
    """Reverse :func:`encrypt_shard` using the voucher's Ed25519 private seed."""
    blob = bytes(blob)
    if not blob or blob[0] != SHARD_CRYPTO_VERSION:
        raise ValueError("unsupported shard ciphertext version")
    if len(blob) < 1 + 32 + 12 + 16:
        raise ValueError("shard ciphertext truncated")
    eph_pub = blob[1:33]
    nonce = blob[33:45]
    ct = blob[45:]

    x_priv_bytes = ed25519_priv_to_x25519(ed25519_private_seed)
    x_priv = X25519PrivateKey.from_private_bytes(x_priv_bytes)
    shared = x_priv.exchange(X25519PublicKey.from_public_bytes(eph_pub))

    recipient_x = x_priv.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
    kek = _derive_kek(
        shared, eph_pub, recipient_x,
        ed25519_public_key_multibase.encode("utf-8"),
    )
    aad = _AAD_PREFIX + b"|" + ed25519_public_key_multibase.encode("utf-8")
    pt = AESGCM(kek).decrypt(nonce, ct, aad)
    return pt.decode("utf-8")

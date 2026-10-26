"""Well-formed client values for recovery tests (shared/sealed_shares.py).

The server never opens a sealed share, so random bytes in the right layout
stand in for what the client's hybridKem.js produces.
"""
import base64
import hashlib
import os
import secrets

from shared.sealed_shares import ML_KEM_768_CIPHERTEXT_SIZE, SEALED_SHARE_VERSION


def ml_kem_768_public_key(bad_coefficient=False):
    """768 12-bit coefficients below q = 3329 (FIPS 203 ByteEncode_12) and a
    32-byte seed."""
    coefficients = [secrets.randbelow(3329) for _ in range(768)]
    if bad_coefficient:
        coefficients[5] = 3329
    out = bytearray()
    for a, b in zip(coefficients[0::2], coefficients[1::2]):
        out += bytes((a & 0xFF, a >> 8 | (b & 0x0F) << 4, b >> 4))
    return bytes(out) + os.urandom(32)


def b64(raw):
    return base64.b64encode(raw).decode('ascii')


def hybrid_public_key():
    return b64(os.urandom(32) + ml_kem_768_public_key())


def sealed_share(plaintext_len=33):
    return b64(bytes([SEALED_SHARE_VERSION]) + os.urandom(32 + ML_KEM_768_CIPHERTEXT_SIZE + 12)
               + os.urandom(plaintext_len + 16))


def share_proof():
    """Return ``(proof_b64, proof_hash_b64)``."""
    proof = os.urandom(32)
    return b64(proof), b64(hashlib.sha256(proof).digest())


def seed_check():
    return b64(os.urandom(32))

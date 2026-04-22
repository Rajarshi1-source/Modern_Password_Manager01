"""
Pedersen commitment + Schnorr proof of equality (Chaum-Pedersen) on secp256k1.

Commitment:
    C = m*G + r*H
    where G = secp256k1 base point, H = hash_to_point("pwm-zkp-v1|H-generator"),
    m = password-derived scalar, r = blinding factor.

Equality proof (prove c1 and c2 commit to the same m without revealing m):
    D     = c1 - c2 = (r1 - r2) * H
    Prover knows δ = r1 - r2.
    k   ← random scalar ∈ [1, n-1]
    T   = k * H
    c   = H_sha256("pwm-zkp-v1|eq-challenge" || enc(c1) || enc(c2) || enc(T)) mod n
    s   = k + c*δ (mod n)
    proof = (enc(T), s_bytes_be32)

Verify: s*H == T + c*D
"""

from __future__ import annotations

import secrets
from typing import Tuple

from . import secp256k1 as ec

DOMAIN_EQUALITY_CHALLENGE = b"pwm-zkp-v1|eq-challenge"


def commit(m_scalar: int, r_scalar: int) -> ec.Point:
    """Return the Pedersen commitment ``m*G + r*H`` as a ``Point``."""
    return ec.point_add(
        ec.point_mul(m_scalar % ec.N, ec.G),
        ec.point_mul(r_scalar % ec.N, ec.H),
    )


def prove_equality(
    c1: ec.Point,
    c2: ec.Point,
    r1: int,
    r2: int,
) -> Tuple[bytes, bytes]:
    """
    Produce a Schnorr proof that c1 and c2 commit to the same scalar.

    Returns ``(T_bytes_33, s_bytes_32)`` — both canonical big-endian encodings.
    ``c1`` and ``c2`` must already be computed from the same m with the caller's
    private r1/r2 (which the prover supplies here).
    """
    delta = (r1 - r2) % ec.N
    # secrets.randbelow(n-1) returns [0, n-2]; add 1 to get [1, n-1].
    k = secrets.randbelow(ec.N - 1) + 1
    T = ec.point_mul(k, ec.H)
    c = ec.hash_to_scalar(
        DOMAIN_EQUALITY_CHALLENGE,
        ec.encode_point(c1),
        ec.encode_point(c2),
        ec.encode_point(T),
    )
    s = (k + c * delta) % ec.N
    return ec.encode_point(T), s.to_bytes(32, "big")


def verify_equality(
    c1_bytes: bytes,
    c2_bytes: bytes,
    proof_T_bytes: bytes,
    proof_s_bytes: bytes,
) -> bool:
    """
    Verify a Schnorr equality proof. Returns False on ANY decoding or range
    failure so callers never have to catch exceptions from malformed input.
    """
    try:
        c1 = ec.decode_point(c1_bytes)
        c2 = ec.decode_point(c2_bytes)
        T = ec.decode_point(proof_T_bytes)
        if not isinstance(proof_s_bytes, (bytes, bytearray, memoryview)):
            return False
        proof_s_bytes = bytes(proof_s_bytes)
        if len(proof_s_bytes) != 32:
            return False
        s = int.from_bytes(proof_s_bytes, "big")
        if s == 0 or s >= ec.N:
            return False
        c = ec.hash_to_scalar(
            DOMAIN_EQUALITY_CHALLENGE,
            c1_bytes,
            c2_bytes,
            proof_T_bytes,
        )
        D = ec.point_add(c1, ec.point_neg(c2))
        lhs = ec.point_mul(s, ec.H)
        rhs = ec.point_add(T, ec.point_mul(c, D))
        if lhs.is_infinity() or rhs.is_infinity():
            # A valid proof never produces infinity: lhs = sH with s ∈ [1, n-1]
            # and H of full order, rhs = T + cD likewise. Accepting the
            # "both infinity" branch would let a forged proof over D=0
            # (identical commitments or C with C) verify trivially.
            return False
        return lhs.x == rhs.x and lhs.y == rhs.y
    except (ValueError, TypeError, OverflowError):
        return False

"""
Minimal pure-Python secp256k1 point arithmetic for the ZK proof verifier.

This module is intentionally self-contained so the backend does not depend on
``coincurve`` or any native ECC library. All inputs to public verification
functions are untrusted bytes received from clients; every decode path
validates that the resulting point lies on the curve.

Timing:
    The arithmetic below is NOT constant-time. This is acceptable because the
    backend only ever performs *verification* using public data (stored
    commitments + client-submitted proof bytes). Secret scalars never leave
    the client. For a client-side implementation we use ``@noble/curves`` which
    is constant-time.

Transcript / hash-to-curve compatibility:
    ``hash_to_point`` and ``hash_to_scalar`` MUST stay byte-for-byte
    compatible with the JavaScript implementation in
    ``frontend/src/services/zkProof/commitmentSchnorrProvider.js``.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Iterable, Union

# secp256k1 parameters (SEC2)
P: int = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEFFFFFC2F
N: int = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141
A: int = 0
B: int = 7
GX: int = 0x79BE667EF9DCBBAC55A06295CE870B07029BFCDB2DCE28D959F2815B16F81798
GY: int = 0x483ADA7726A3C4655DA4FBFC0E1108A8FD17B448A68554199C47D08FFB10D4B8


@dataclass(frozen=True)
class Point:
    """Affine point on secp256k1. ``x is None`` denotes the point at infinity."""

    x: Union[int, None]
    y: Union[int, None]

    def is_infinity(self) -> bool:
        return self.x is None


INF = Point(None, None)
G = Point(GX, GY)


def _modinv(a: int, m: int) -> int:
    # Python 3.8+ supports pow(a, -1, m); use it for simplicity.
    return pow(a, -1, m)


def is_on_curve(pt: Point) -> bool:
    if pt.is_infinity():
        return True
    x, y = pt.x, pt.y
    # y^2 == x^3 + 7 (mod P)  (a = 0 on secp256k1)
    return (y * y - (x * x * x + B)) % P == 0


def point_add(p1: Point, p2: Point) -> Point:
    if p1.is_infinity():
        return p2
    if p2.is_infinity():
        return p1
    if p1.x == p2.x:
        if (p1.y + p2.y) % P == 0:
            return INF
        # p1 == p2 → doubling
        slope = (3 * p1.x * p1.x) * _modinv(2 * p1.y % P, P) % P
    else:
        slope = (p2.y - p1.y) * _modinv((p2.x - p1.x) % P, P) % P
    x3 = (slope * slope - p1.x - p2.x) % P
    y3 = (slope * (p1.x - x3) - p1.y) % P
    return Point(x3, y3)


def point_neg(pt: Point) -> Point:
    if pt.is_infinity():
        return pt
    return Point(pt.x, (-pt.y) % P)


def point_mul(k: int, pt: Point) -> Point:
    k = k % N
    if k == 0 or pt.is_infinity():
        return INF
    result = INF
    addend = pt
    while k:
        if k & 1:
            result = point_add(result, addend)
        addend = point_add(addend, addend)
        k >>= 1
    return result


def encode_point(pt: Point) -> bytes:
    """SEC1 compressed encoding (33 bytes)."""
    if pt.is_infinity():
        raise ValueError("Cannot encode point at infinity")
    prefix = 0x02 if pt.y % 2 == 0 else 0x03
    return bytes([prefix]) + pt.x.to_bytes(32, "big")


def decode_point(data: bytes) -> Point:
    """Parse a SEC1 compressed point. Raises ``ValueError`` on any malformed input."""
    if not isinstance(data, (bytes, bytearray, memoryview)):
        raise TypeError("decode_point expects bytes-like")
    data = bytes(data)
    if len(data) != 33:
        raise ValueError("Expected 33-byte compressed secp256k1 point")
    prefix = data[0]
    if prefix not in (0x02, 0x03):
        raise ValueError("Invalid compression prefix")
    x = int.from_bytes(data[1:], "big")
    if not (0 < x < P):
        raise ValueError("x coordinate out of field range")
    # y^2 = x^3 + 7 (mod P)
    y_sq = (pow(x, 3, P) + B) % P
    # secp256k1 P ≡ 3 (mod 4) so y = y_sq^((P+1)/4) mod P is a square root
    y = pow(y_sq, (P + 1) // 4, P)
    if (y * y) % P != y_sq:
        raise ValueError("Point not on curve (no square root)")
    if (y % 2 == 0) != (prefix == 0x02):
        y = P - y
    pt = Point(x, y)
    if not is_on_curve(pt):
        raise ValueError("Point not on curve")
    return pt


def _feed(h: "hashlib._Hash", parts: Iterable[Union[bytes, str]]) -> None:
    for part in parts:
        if isinstance(part, str):
            h.update(part.encode("utf-8"))
        elif isinstance(part, (bytes, bytearray, memoryview)):
            h.update(bytes(part))
        else:
            raise TypeError(f"Cannot feed {type(part)!r} into transcript hash")


def hash_to_scalar(*parts: Union[bytes, str]) -> int:
    """Fiat-Shamir challenge: SHA-256 over concatenated parts, reduced mod N."""
    h = hashlib.sha256()
    _feed(h, parts)
    return int.from_bytes(h.digest(), "big") % N


def hash_to_point(seed: bytes) -> Point:
    """
    Deterministic hash-to-curve via SHA-256 try-and-increment.

    Canonicalises the returned y-coordinate to be even so this function
    produces the same point across languages without parity ambiguity.
    """
    counter = 0
    while counter < (1 << 32):
        digest = hashlib.sha256(seed + counter.to_bytes(4, "big")).digest()
        x = int.from_bytes(digest, "big") % P
        if x == 0:
            counter += 1
            continue
        y_sq = (pow(x, 3, P) + B) % P
        y = pow(y_sq, (P + 1) // 4, P)
        if (y * y) % P == y_sq and y != 0:
            if y % 2 == 1:
                y = P - y
            return Point(x, y)
        counter += 1
    raise RuntimeError("hash_to_point failed to find a point in 2^32 attempts")


# Nothing-up-my-sleeve second generator. Its discrete log relative to G is
# computationally intractable because it was produced by hashing a public
# domain string — nobody, including us, chose a scalar.
H_SEED = b"pwm-zkp-v1|H-generator"
H = hash_to_point(H_SEED)

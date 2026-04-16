"""
HiddenVaultBlob v1 - encode / decode.

Implements the container format documented in ``SPEC.md``.

Design notes
------------

* Both slots are ALWAYS written. The slot whose password was not
  provided (or was not provided at all) is filled with a ciphertext
  under a freshly generated random key that is immediately discarded.
  An adversary therefore cannot tell whether the user configured one
  vault or two, and cannot decrypt the "throwaway" slot with any
  password.
* The total blob size is fixed by the tier - no part of the blob
  leaks plaintext length.
* Argon2id is used as the KDF with parameters baked into the header,
  so future migrations can bump parameters while old blobs stay
  decryptable.
* Both slots are ALWAYS attempted during decode - keeping decode
  timing roughly constant-time with respect to "which slot was
  correct".

The module exposes two public entry points:

* :func:`encode` - random nonces, salts, and padding. Production path.
* :func:`encode_deterministic` - seeds all randomness from a
  user-supplied ``rng_seed`` so byte-for-byte equality can be asserted
  in cross-language tests. **Not for production use.**
"""

from __future__ import annotations

import hashlib
import os
import struct
from dataclasses import dataclass
from typing import Optional, Tuple

from argon2.low_level import Type, hash_secret_raw
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MAGIC = b"HVBLOBv1"                 # 8 bytes
VERSION = 0x01                       # 1 byte
SLOT_COUNT = 2                       # 1 byte in header
KDF_ID_ARGON2ID = 0x01

DEFAULT_KDF_TIME_COST = 3
DEFAULT_KDF_MEMORY_KIB = 65536  # 64 MiB
DEFAULT_KDF_PARALLELISM = 1

OUTER_SALT_LEN = 16
NONCE_LEN = 12
GCM_TAG_LEN = 16
KEY_LEN = 32

HEADER_FIXED_LEN = 8 + 1 + 1 + 1 + 1 + 4 + 4 + 4 + OUTER_SALT_LEN + 2
# magic(8) + version(1) + slot_count(1) + tier(1) + kdf_id(1)
# + kdf_time(4) + kdf_mem(4) + kdf_par(4) + outer_salt(16) + slot_len(2)
# = 42 bytes

SLOT_FRAME_MAGIC = b"HVS1"           # 4 bytes
SLOT_FRAME_HEADER_LEN = 4 + 4        # magic(4) + length(4)

DOMAIN_TAG_PREFIX = b"HVBLOBv1/slot"  # 13 bytes; + 1 byte index = 14 bytes


# ---------------------------------------------------------------------------
# Tiers
# ---------------------------------------------------------------------------


class TIERS:
    """Supported container sizes (encoded as a single byte in the header)."""

    TIER0_32K = 0
    TIER1_128K = 1
    TIER2_1M = 2


_TIER_TOTAL_BYTES = {
    TIERS.TIER0_32K: 32 * 1024,
    TIERS.TIER1_128K: 128 * 1024,
    TIERS.TIER2_1M: 1024 * 1024,
}

_TIER_SLOT_PAYLOAD_LEN = {
    TIERS.TIER0_32K: 16000,
    TIERS.TIER1_128K: 60000,
    TIERS.TIER2_1M: 490000,
}


def tier_bytes(tier: int) -> int:
    """Return the fixed total byte size of a tier."""
    try:
        return _TIER_TOTAL_BYTES[tier]
    except KeyError as exc:
        raise ValueError(f"Unknown tier: {tier}") from exc


def slot_payload_len(tier: int) -> int:
    """Return the ciphertext+tag length K reserved per slot in a tier."""
    try:
        return _TIER_SLOT_PAYLOAD_LEN[tier]
    except KeyError as exc:
        raise ValueError(f"Unknown tier: {tier}") from exc


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class HiddenVaultError(Exception):
    """Base class for all hidden-vault envelope errors."""


class WrongPasswordError(HiddenVaultError):
    """Neither slot decrypted successfully with the supplied password."""


class MalformedBlobError(HiddenVaultError):
    """The blob header is invalid, too short, or carries an unsupported version."""


class PayloadTooLargeError(HiddenVaultError):
    """The plaintext payload does not fit in the requested tier's slot."""


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _derive_slot_key(
    password: str,
    outer_salt: bytes,
    slot_index: int,
    kdf_time: int,
    kdf_mem_kib: int,
    kdf_par: int,
) -> bytes:
    """Argon2id KDF, domain-separated per slot index."""
    if slot_index not in (0, 1):
        raise ValueError("slot_index must be 0 or 1")
    domain_tag = DOMAIN_TAG_PREFIX + bytes([slot_index])
    salt = outer_salt + domain_tag  # 16 + 14 = 30 bytes
    pwd = password.encode("utf-8") if isinstance(password, str) else password
    return hash_secret_raw(
        secret=pwd,
        salt=salt,
        time_cost=kdf_time,
        memory_cost=kdf_mem_kib,
        parallelism=kdf_par,
        hash_len=KEY_LEN,
        type=Type.ID,
    )


def _frame_plaintext(payload: bytes, slot_ct_len: int) -> bytes:
    """Wrap payload in the HVS1 slot frame, zero-padded to fit."""
    if not isinstance(payload, (bytes, bytearray)):
        raise TypeError("payload must be bytes")
    body_len = slot_ct_len - GCM_TAG_LEN  # plaintext length for AES-GCM
    if len(payload) + SLOT_FRAME_HEADER_LEN > body_len:
        raise PayloadTooLargeError(
            f"Payload ({len(payload)}B) does not fit in slot body "
            f"({body_len - SLOT_FRAME_HEADER_LEN}B available)."
        )
    frame = SLOT_FRAME_MAGIC + struct.pack("<I", len(payload)) + bytes(payload)
    frame += b"\x00" * (body_len - len(frame))
    assert len(frame) == body_len
    return frame


def _unframe_plaintext(frame: bytes) -> Optional[bytes]:
    """Undo :func:`_frame_plaintext`; returns None if the frame is invalid."""
    if len(frame) < SLOT_FRAME_HEADER_LEN or frame[:4] != SLOT_FRAME_MAGIC:
        return None
    length = struct.unpack("<I", frame[4:8])[0]
    if length > len(frame) - SLOT_FRAME_HEADER_LEN:
        return None
    return bytes(frame[8 : 8 + length])


@dataclass
class _ParsedHeader:
    version: int
    slot_count: int
    tier: int
    kdf_id: int
    kdf_time: int
    kdf_mem: int
    kdf_par: int
    outer_salt: bytes
    slot_ct_len: int


def _parse_header(blob: bytes) -> _ParsedHeader:
    if len(blob) < HEADER_FIXED_LEN:
        raise MalformedBlobError("blob shorter than header length")
    if blob[:8] != MAGIC:
        raise MalformedBlobError("bad magic")
    version = blob[8]
    if version != VERSION:
        raise MalformedBlobError(f"unsupported version: {version}")
    slot_count = blob[9]
    if slot_count != SLOT_COUNT:
        raise MalformedBlobError(f"unsupported slot count: {slot_count}")
    tier = blob[10]
    if tier not in _TIER_TOTAL_BYTES:
        raise MalformedBlobError(f"unknown tier: {tier}")
    kdf_id = blob[11]
    if kdf_id != KDF_ID_ARGON2ID:
        raise MalformedBlobError(f"unsupported kdf id: {kdf_id}")
    (kdf_time,) = struct.unpack_from("<I", blob, 12)
    (kdf_mem,) = struct.unpack_from("<I", blob, 16)
    (kdf_par,) = struct.unpack_from("<I", blob, 20)
    outer_salt = bytes(blob[24 : 24 + OUTER_SALT_LEN])
    (slot_ct_len,) = struct.unpack_from("<H", blob, 40)
    expected_ct_len = _TIER_SLOT_PAYLOAD_LEN[tier]
    if slot_ct_len != expected_ct_len:
        raise MalformedBlobError(
            f"slot_ct_len={slot_ct_len} does not match tier expectation={expected_ct_len}"
        )
    expected_total = _TIER_TOTAL_BYTES[tier]
    if len(blob) != expected_total:
        raise MalformedBlobError(
            f"blob length {len(blob)} != tier total {expected_total}"
        )
    return _ParsedHeader(
        version=version,
        slot_count=slot_count,
        tier=tier,
        kdf_id=kdf_id,
        kdf_time=kdf_time,
        kdf_mem=kdf_mem,
        kdf_par=kdf_par,
        outer_salt=outer_salt,
        slot_ct_len=slot_ct_len,
    )


def _slot_offsets(slot_ct_len: int) -> Tuple[int, int, int, int]:
    """Return (slot0_nonce_off, slot0_ct_off, slot1_nonce_off, slot1_ct_off)."""
    s0_nonce = HEADER_FIXED_LEN
    s0_ct = s0_nonce + NONCE_LEN
    s1_nonce = s0_ct + slot_ct_len
    s1_ct = s1_nonce + NONCE_LEN
    return s0_nonce, s0_ct, s1_nonce, s1_ct


# ---------------------------------------------------------------------------
# Deterministic RNG for tests
# ---------------------------------------------------------------------------


class _DeterministicRng:
    """SHAKE-256-backed counter PRNG for test vectors only."""

    def __init__(self, seed: bytes, domain: bytes = b"hv-rng") -> None:
        self._seed = hashlib.sha256(domain + b"/" + seed).digest()
        self._counter = 0
        self._buffer = b""

    def _refill(self, n: int) -> None:
        while len(self._buffer) < n:
            blk = hashlib.sha256(
                self._seed + self._counter.to_bytes(8, "little")
            ).digest()
            self._buffer += blk
            self._counter += 1

    def randbytes(self, n: int) -> bytes:
        self._refill(n)
        out, self._buffer = self._buffer[:n], self._buffer[n:]
        return out


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def _encode_core(
    *,
    real_password: Optional[str],
    real_payload: Optional[bytes],
    decoy_password: Optional[str],
    decoy_payload: Optional[bytes],
    tier: int,
    kdf_time: int,
    kdf_mem_kib: int,
    kdf_par: int,
    rng,  # has .randbytes(n)
) -> bytes:
    # --- validate ---
    if real_password is None and decoy_password is None:
        raise ValueError("At least one of real_password / decoy_password is required.")
    total_bytes = tier_bytes(tier)
    ct_len = slot_payload_len(tier)

    real_payload = real_payload or b""
    decoy_payload = decoy_payload or b""

    # --- build header ---
    outer_salt = rng.randbytes(OUTER_SALT_LEN)
    header = (
        MAGIC
        + bytes([VERSION, SLOT_COUNT, tier, KDF_ID_ARGON2ID])
        + struct.pack("<I", kdf_time)
        + struct.pack("<I", kdf_mem_kib)
        + struct.pack("<I", kdf_par)
        + outer_salt
        + struct.pack("<H", ct_len)
    )
    assert len(header) == HEADER_FIXED_LEN

    # --- derive slot keys. Unused slot gets a freshly-generated random
    # key that we immediately discard, making the two slots byte-wise
    # indistinguishable. ---
    def _key_for(password: Optional[str], slot_index: int) -> bytes:
        if password is None:
            return rng.randbytes(KEY_LEN)
        return _derive_slot_key(
            password,
            outer_salt,
            slot_index,
            kdf_time,
            kdf_mem_kib,
            kdf_par,
        )

    # Caller semantics: slot 0 = the slot for the "real" password when
    # both are supplied, slot 1 = decoy. This is opaque to the decoder,
    # which only knows which slot decrypted successfully.
    key0 = _key_for(real_password, 0)
    key1 = _key_for(decoy_password, 1)

    plaintext0 = _frame_plaintext(real_payload, ct_len)
    plaintext1 = _frame_plaintext(decoy_payload, ct_len)

    nonce0 = rng.randbytes(NONCE_LEN)
    nonce1 = rng.randbytes(NONCE_LEN)

    ct0 = AESGCM(key0).encrypt(nonce0, plaintext0, associated_data=None)
    ct1 = AESGCM(key1).encrypt(nonce1, plaintext1, associated_data=None)
    assert len(ct0) == ct_len and len(ct1) == ct_len

    # --- pad to tier size with random bytes ---
    assembled = header + nonce0 + ct0 + nonce1 + ct1
    pad_len = total_bytes - len(assembled)
    if pad_len < 0:
        raise RuntimeError(
            f"Internal error: assembled length {len(assembled)} exceeds tier total {total_bytes}"
        )
    pad = rng.randbytes(pad_len)
    blob = assembled + pad
    assert len(blob) == total_bytes
    return blob


class _OsRng:
    @staticmethod
    def randbytes(n: int) -> bytes:
        return os.urandom(n)


def encode(
    *,
    real_password: Optional[str] = None,
    real_payload: Optional[bytes] = None,
    decoy_password: Optional[str] = None,
    decoy_payload: Optional[bytes] = None,
    tier: int = TIERS.TIER0_32K,
    kdf_time: int = DEFAULT_KDF_TIME_COST,
    kdf_mem_kib: int = DEFAULT_KDF_MEMORY_KIB,
    kdf_par: int = DEFAULT_KDF_PARALLELISM,
) -> bytes:
    """
    Produce a HiddenVaultBlob v1.

    At least one of ``real_password`` / ``decoy_password`` must be
    provided. The "unused" slot is filled with ciphertext under a
    discarded random key, so the blob bytes are indistinguishable
    between "one real + one decoy" and "one real + one garbage".

    The returned blob is always exactly :func:`tier_bytes` bytes long.
    """
    return _encode_core(
        real_password=real_password,
        real_payload=real_payload,
        decoy_password=decoy_password,
        decoy_payload=decoy_payload,
        tier=tier,
        kdf_time=kdf_time,
        kdf_mem_kib=kdf_mem_kib,
        kdf_par=kdf_par,
        rng=_OsRng(),
    )


def encode_deterministic(
    *,
    rng_seed: bytes,
    real_password: Optional[str] = None,
    real_payload: Optional[bytes] = None,
    decoy_password: Optional[str] = None,
    decoy_payload: Optional[bytes] = None,
    tier: int = TIERS.TIER0_32K,
    kdf_time: int = DEFAULT_KDF_TIME_COST,
    kdf_mem_kib: int = DEFAULT_KDF_MEMORY_KIB,
    kdf_par: int = DEFAULT_KDF_PARALLELISM,
) -> bytes:
    """
    Deterministic variant of :func:`encode` for cross-language tests.

    All randomness (outer salt, nonces, padding, and the throwaway
    "unused slot" key) is derived from ``rng_seed`` via SHA-256 CTR.
    **Do not use in production.**
    """
    if not rng_seed or len(rng_seed) < 16:
        raise ValueError("rng_seed must be >= 16 bytes")
    rng = _DeterministicRng(rng_seed)
    return _encode_core(
        real_password=real_password,
        real_payload=real_payload,
        decoy_password=decoy_password,
        decoy_payload=decoy_payload,
        tier=tier,
        kdf_time=kdf_time,
        kdf_mem_kib=kdf_mem_kib,
        kdf_par=kdf_par,
        rng=rng,
    )


@dataclass
class DecodeResult:
    slot_index: int
    payload: bytes


def decode(blob: bytes, password: str) -> DecodeResult:
    """
    Try to unlock ``blob`` with ``password``.

    Returns ``DecodeResult(slot_index, payload)`` or raises
    :class:`WrongPasswordError`. The caller is expected to treat slot
    semantics (real vs decoy) as application-level policy - the
    primitive only reports which slot decrypted.
    """
    if not isinstance(password, str):
        raise TypeError("password must be a string")
    header = _parse_header(blob)
    s0_nonce_off, s0_ct_off, s1_nonce_off, s1_ct_off = _slot_offsets(header.slot_ct_len)

    nonce0 = bytes(blob[s0_nonce_off : s0_nonce_off + NONCE_LEN])
    ct0 = bytes(blob[s0_ct_off : s0_ct_off + header.slot_ct_len])
    nonce1 = bytes(blob[s1_nonce_off : s1_nonce_off + NONCE_LEN])
    ct1 = bytes(blob[s1_ct_off : s1_ct_off + header.slot_ct_len])

    # Try both slots. Keep timing roughly equalised: always derive both
    # keys and always attempt both decryptions.
    k0 = _derive_slot_key(
        password, header.outer_salt, 0, header.kdf_time, header.kdf_mem, header.kdf_par
    )
    k1 = _derive_slot_key(
        password, header.outer_salt, 1, header.kdf_time, header.kdf_mem, header.kdf_par
    )

    winning_slot = None
    winning_payload: Optional[bytes] = None

    for idx, key, nonce, ct in ((0, k0, nonce0, ct0), (1, k1, nonce1, ct1)):
        try:
            frame = AESGCM(key).decrypt(nonce, ct, associated_data=None)
        except Exception:  # InvalidTag and similar
            continue
        payload = _unframe_plaintext(frame)
        if payload is None:
            continue
        if winning_slot is None:
            winning_slot = idx
            winning_payload = payload

    if winning_slot is None or winning_payload is None:
        raise WrongPasswordError("No slot decrypted successfully with the supplied password.")
    return DecodeResult(slot_index=winning_slot, payload=winning_payload)

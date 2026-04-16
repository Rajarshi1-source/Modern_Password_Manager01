"""
Pytest suite for :mod:`hidden_vault.envelope`.

The tests validate the cross-language invariants from
``hidden_vault/SPEC.md`` and enforce the core plausible-deniability
properties: fixed blob size, slot symmetry, wrong-password rejection,
and resistance to trivial slot-identification attacks.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from hidden_vault.envelope import (
    DEFAULT_KDF_MEMORY_KIB,
    DEFAULT_KDF_PARALLELISM,
    DEFAULT_KDF_TIME_COST,
    TIERS,
    HiddenVaultError,
    MalformedBlobError,
    PayloadTooLargeError,
    WrongPasswordError,
    decode,
    encode,
    encode_deterministic,
    slot_payload_len,
    tier_bytes,
)


# Light Argon2id parameters for tests so the suite runs in < a few
# seconds. Production callers must use the defaults.
FAST_KDF = dict(kdf_time=1, kdf_mem_kib=8, kdf_par=1)

VECTORS_PATH = Path(__file__).parent / "vectors.json"


# ---------------------------------------------------------------------------
# Core invariants
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("tier", [TIERS.TIER0_32K, TIERS.TIER1_128K])
def test_encode_produces_fixed_tier_size(tier):
    blob = encode(
        real_password="alpha",
        real_payload=b'{"items":[{"n":"a"}]}',
        decoy_password="beta",
        decoy_payload=b'{"items":[{"n":"b"}]}',
        tier=tier,
        **FAST_KDF,
    )
    assert len(blob) == tier_bytes(tier)


def test_roundtrip_both_slots():
    real = b"real-vault-content-42"
    decoy = b"decoy-vault-bait-99"
    blob = encode(
        real_password="rpw",
        real_payload=real,
        decoy_password="dpw",
        decoy_payload=decoy,
        tier=TIERS.TIER0_32K,
        **FAST_KDF,
    )

    r = decode(blob, "rpw")
    d = decode(blob, "dpw")

    assert r.payload == real
    assert d.payload == decoy
    assert r.slot_index != d.slot_index


def test_wrong_password_raises():
    blob = encode(
        real_password="rpw",
        real_payload=b"x" * 64,
        decoy_password="dpw",
        decoy_payload=b"y" * 64,
        tier=TIERS.TIER0_32K,
        **FAST_KDF,
    )
    with pytest.raises(WrongPasswordError):
        decode(blob, "totally-wrong")


def test_single_slot_configured_blob_still_fixed_size_and_decoy_password_fails():
    blob = encode(
        real_password="only-real",
        real_payload=b"real-only",
        # No decoy password -> slot 1 has throwaway random key.
        tier=TIERS.TIER0_32K,
        **FAST_KDF,
    )
    assert len(blob) == tier_bytes(TIERS.TIER0_32K)
    r = decode(blob, "only-real")
    assert r.payload == b"real-only"
    with pytest.raises(WrongPasswordError):
        decode(blob, "anything-else")


def test_blob_bytes_do_not_distinguish_single_vs_double_config():
    """
    A blob with only a real slot must be indistinguishable (at the
    level of simple statistics / fixed-layout inspection) from a blob
    with both slots configured. This is weaker than a real
    indistinguishability proof but catches accidental layout leaks.
    """
    blob_single = encode(
        real_password="rpw",
        real_payload=b"real",
        tier=TIERS.TIER0_32K,
        **FAST_KDF,
    )
    blob_double = encode(
        real_password="rpw",
        real_payload=b"real",
        decoy_password="dpw",
        decoy_payload=b"decoy",
        tier=TIERS.TIER0_32K,
        **FAST_KDF,
    )
    assert len(blob_single) == len(blob_double)
    # Header version + slot_count + tier must match byte-for-byte.
    assert blob_single[:12] == blob_double[:12]


def test_payload_too_large_raises_payload_too_large():
    overflow = b"x" * (slot_payload_len(TIERS.TIER0_32K))  # > body (no tag)
    with pytest.raises(PayloadTooLargeError):
        encode(
            real_password="pw",
            real_payload=overflow,
            tier=TIERS.TIER0_32K,
            **FAST_KDF,
        )


def test_requires_at_least_one_password():
    with pytest.raises(ValueError):
        encode(tier=TIERS.TIER0_32K, **FAST_KDF)


def test_truncated_blob_is_malformed():
    blob = encode(
        real_password="rpw",
        real_payload=b"x",
        tier=TIERS.TIER0_32K,
        **FAST_KDF,
    )
    with pytest.raises(MalformedBlobError):
        decode(blob[:10], "rpw")


def test_corrupted_header_magic_rejected():
    blob = bytearray(
        encode(
            real_password="rpw",
            real_payload=b"x",
            tier=TIERS.TIER0_32K,
            **FAST_KDF,
        )
    )
    blob[0] = ord("X")
    with pytest.raises(MalformedBlobError):
        decode(bytes(blob), "rpw")


def test_independent_slot_decryption():
    """
    Flipping a byte inside slot 1 must not affect slot 0's ability to
    decrypt, proving the slots are cryptographically independent.
    """
    blob = bytearray(
        encode(
            real_password="rpw",
            real_payload=b"real-42",
            decoy_password="dpw",
            decoy_payload=b"decoy-99",
            tier=TIERS.TIER0_32K,
            **FAST_KDF,
        )
    )
    # Corrupt somewhere inside slot 1's ciphertext region.
    ct0_len = slot_payload_len(TIERS.TIER0_32K)
    slot1_ct_off = 42 + 12 + ct0_len + 12  # header + nonce0 + ct0 + nonce1
    blob[slot1_ct_off + 50] ^= 0xFF
    r = decode(bytes(blob), "rpw")
    assert r.payload == b"real-42"
    with pytest.raises(WrongPasswordError):
        decode(bytes(blob), "dpw")


def test_decode_slot_indices_are_independent_of_password_order():
    """
    Encoding the same vault first as (real=A, decoy=B) and then as
    (real=B, decoy=A) must assign password A to slot 0 and slot 1
    respectively - proving slot_index is a property of encoding, not
    of the password itself.
    """
    a, b = "pw-a", "pw-b"
    pa, pb = b"AAA", b"BBB"
    blob1 = encode(
        real_password=a, real_payload=pa,
        decoy_password=b, decoy_payload=pb,
        tier=TIERS.TIER0_32K, **FAST_KDF,
    )
    blob2 = encode(
        real_password=b, real_payload=pb,
        decoy_password=a, decoy_payload=pa,
        tier=TIERS.TIER0_32K, **FAST_KDF,
    )
    assert decode(blob1, a).slot_index == 0
    assert decode(blob2, a).slot_index == 1


# ---------------------------------------------------------------------------
# Deterministic encoder (for cross-language byte-equal tests)
# ---------------------------------------------------------------------------


def test_deterministic_encoder_is_reproducible():
    seed = b"\xde" * 16
    kwargs = dict(
        rng_seed=seed,
        real_password="rpw",
        real_payload=b"real",
        decoy_password="dpw",
        decoy_payload=b"decoy",
        tier=TIERS.TIER0_32K,
        **FAST_KDF,
    )
    b1 = encode_deterministic(**kwargs)
    b2 = encode_deterministic(**kwargs)
    assert b1 == b2
    r = decode(b1, "rpw")
    d = decode(b1, "dpw")
    assert r.payload == b"real"
    assert d.payload == b"decoy"


def test_deterministic_encoder_requires_seed():
    with pytest.raises(ValueError):
        encode_deterministic(
            rng_seed=b"short",
            real_password="a", real_payload=b"a",
            tier=TIERS.TIER0_32K,
        )


# ---------------------------------------------------------------------------
# Vector file sanity
# ---------------------------------------------------------------------------


def test_vectors_file_present_and_well_formed():
    """
    vectors.json is consumed by the JS/extension/mobile suites for
    parity. We only verify it parses and has the expected shape here.
    """
    data = json.loads(VECTORS_PATH.read_text(encoding="utf-8"))
    assert data["spec"] == "HiddenVaultBlob v1"
    assert isinstance(data["cases"], list) and data["cases"]
    for case in data["cases"]:
        assert "id" in case
        assert "tier" in case
        assert case["tier_bytes"] == tier_bytes(case["tier"])
        assert case["slot_payload_len"] == slot_payload_len(case["tier"])


def test_vectors_file_roundtrip_in_python():
    data = json.loads(VECTORS_PATH.read_text(encoding="utf-8"))
    for case in data["cases"]:
        if case["tier"] != TIERS.TIER0_32K:
            # Skip the 128KiB unicode case in the fast suite.
            continue
        real_pw = case["real_password"]
        decoy_pw = case.get("decoy_password")
        real_payload = case["real_payload_utf8"].encode("utf-8")
        decoy_payload = (
            case["decoy_payload_utf8"].encode("utf-8")
            if case.get("decoy_payload_utf8")
            else None
        )
        blob = encode(
            real_password=real_pw,
            real_payload=real_payload,
            decoy_password=decoy_pw,
            decoy_payload=decoy_payload,
            tier=case["tier"],
            **FAST_KDF,
        )
        assert len(blob) == case["tier_bytes"]
        r = decode(blob, real_pw)
        assert r.payload == real_payload
        if decoy_pw is not None and decoy_payload is not None:
            d = decode(blob, decoy_pw)
            assert d.payload == decoy_payload
            assert r.slot_index != d.slot_index

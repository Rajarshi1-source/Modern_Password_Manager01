"""
Unit tests for the Pedersen + Schnorr equality proof primitives.

Run with:
    cd password_manager && pytest zk_proofs/tests/ -q
"""

from __future__ import annotations

import secrets

import pytest

from zk_proofs.crypto import schnorr
from zk_proofs.crypto import secp256k1 as ec
from zk_proofs.providers import get_provider


def _rand_scalar() -> int:
    """Uniformly random scalar in [1, n-1]."""
    return secrets.randbelow(ec.N - 1) + 1


class TestSecp256k1:
    def test_generator_is_on_curve(self):
        assert ec.is_on_curve(ec.G)

    def test_h_generator_is_on_curve(self):
        assert ec.is_on_curve(ec.H)
        # H must not equal G (different generator)
        assert ec.H.x != ec.G.x

    def test_hash_to_point_is_deterministic(self):
        a = ec.hash_to_point(b"pwm-zkp-v1|H-generator")
        b = ec.hash_to_point(b"pwm-zkp-v1|H-generator")
        assert a.x == b.x and a.y == b.y

    def test_hash_to_point_even_y(self):
        # Canonicalised to even y so frontend/backend match bit-for-bit.
        assert ec.H.y % 2 == 0

    def test_double_matches_add(self):
        doubled = ec.point_mul(2, ec.G)
        added = ec.point_add(ec.G, ec.G)
        assert doubled.x == added.x and doubled.y == added.y

    def test_encode_decode_roundtrip(self):
        k = _rand_scalar()
        pt = ec.point_mul(k, ec.G)
        data = ec.encode_point(pt)
        assert len(data) == 33
        back = ec.decode_point(data)
        assert pt.x == back.x and pt.y == back.y

    def test_decode_rejects_wrong_length(self):
        with pytest.raises(ValueError):
            ec.decode_point(b"\x02" + b"\x00" * 31)
        with pytest.raises(ValueError):
            ec.decode_point(b"\x02" + b"\x00" * 33)

    def test_decode_rejects_bad_prefix(self):
        with pytest.raises(ValueError):
            ec.decode_point(b"\x04" + b"\x00" * 32)

    def test_decode_rejects_x_out_of_range(self):
        # x == 0 produces y_sq = 7; 7 is non-residue mod P so this should fail
        # decoding (Fermat check).
        with pytest.raises(ValueError):
            ec.decode_point(b"\x02" + (ec.P - 1).to_bytes(32, "big"))


class TestSchnorrEquality:
    def test_completeness_honest_prover_accepted(self):
        m = _rand_scalar()
        r1, r2 = _rand_scalar(), _rand_scalar()
        c1 = schnorr.commit(m, r1)
        c2 = schnorr.commit(m, r2)
        T, s = schnorr.prove_equality(c1, c2, r1, r2)
        assert schnorr.verify_equality(
            ec.encode_point(c1), ec.encode_point(c2), T, s
        )

    def test_soundness_different_values_rejected(self):
        m1 = _rand_scalar()
        m2 = (m1 + 1) % ec.N
        r1, r2 = _rand_scalar(), _rand_scalar()
        c1 = schnorr.commit(m1, r1)
        c2 = schnorr.commit(m2, r2)
        T, s = schnorr.prove_equality(c1, c2, r1, r2)
        assert not schnorr.verify_equality(
            ec.encode_point(c1), ec.encode_point(c2), T, s
        )

    def test_tampered_s_rejected(self):
        m = _rand_scalar()
        r1, r2 = _rand_scalar(), _rand_scalar()
        c1 = schnorr.commit(m, r1)
        c2 = schnorr.commit(m, r2)
        T, s = schnorr.prove_equality(c1, c2, r1, r2)
        tampered = ((int.from_bytes(s, "big") + 1) % ec.N).to_bytes(32, "big")
        assert not schnorr.verify_equality(
            ec.encode_point(c1), ec.encode_point(c2), T, tampered
        )

    def test_tampered_T_rejected(self):
        m = _rand_scalar()
        r1, r2 = _rand_scalar(), _rand_scalar()
        c1 = schnorr.commit(m, r1)
        c2 = schnorr.commit(m, r2)
        T, s = schnorr.prove_equality(c1, c2, r1, r2)
        # Replace T with a random point.
        bogus_T = ec.encode_point(ec.point_mul(_rand_scalar(), ec.H))
        assert not schnorr.verify_equality(
            ec.encode_point(c1), ec.encode_point(c2), bogus_T, s
        )

    def test_proof_bound_to_transcript(self):
        """A proof for (c1,c2) must not verify against (c1,c3)."""
        m = _rand_scalar()
        r1, r2, r3 = _rand_scalar(), _rand_scalar(), _rand_scalar()
        c1 = schnorr.commit(m, r1)
        c2 = schnorr.commit(m, r2)
        c3 = schnorr.commit(m, r3)
        T, s = schnorr.prove_equality(c1, c2, r1, r2)
        # (c1, c3) is a valid same-value pair but proof was for (c1, c2).
        # The challenge c is a hash of the transcript, so reusing T,s here
        # must fail with overwhelming probability.
        assert not schnorr.verify_equality(
            ec.encode_point(c1), ec.encode_point(c3), T, s
        )

    def test_zero_s_rejected(self):
        m = _rand_scalar()
        r1, r2 = _rand_scalar(), _rand_scalar()
        c1 = schnorr.commit(m, r1)
        c2 = schnorr.commit(m, r2)
        T, _ = schnorr.prove_equality(c1, c2, r1, r2)
        assert not schnorr.verify_equality(
            ec.encode_point(c1), ec.encode_point(c2), T, b"\x00" * 32
        )

    def test_s_equal_to_n_rejected(self):
        m = _rand_scalar()
        r1, r2 = _rand_scalar(), _rand_scalar()
        c1 = schnorr.commit(m, r1)
        c2 = schnorr.commit(m, r2)
        T, _ = schnorr.prove_equality(c1, c2, r1, r2)
        assert not schnorr.verify_equality(
            ec.encode_point(c1), ec.encode_point(c2), T, ec.N.to_bytes(32, "big")
        )

    def test_swapped_commitments_distinct_proofs(self):
        """Proof for (c1,c2) should also verify for (c2,c1) with recomputed proof."""
        m = _rand_scalar()
        r1, r2 = _rand_scalar(), _rand_scalar()
        c1 = schnorr.commit(m, r1)
        c2 = schnorr.commit(m, r2)
        T_ab, s_ab = schnorr.prove_equality(c1, c2, r1, r2)
        T_ba, s_ba = schnorr.prove_equality(c2, c1, r2, r1)
        assert schnorr.verify_equality(
            ec.encode_point(c1), ec.encode_point(c2), T_ab, s_ab
        )
        assert schnorr.verify_equality(
            ec.encode_point(c2), ec.encode_point(c1), T_ba, s_ba
        )
        # A proof for (c1,c2) must NOT verify for (c2,c1) because the
        # transcript ordering is different.
        assert not schnorr.verify_equality(
            ec.encode_point(c2), ec.encode_point(c1), T_ab, s_ab
        )


class TestProviderRegistry:
    def test_default_provider_round_trip(self):
        provider = get_provider()
        m = _rand_scalar()
        r1, r2 = _rand_scalar(), _rand_scalar()
        c1 = schnorr.commit(m, r1)
        c2 = schnorr.commit(m, r2)
        T, s = schnorr.prove_equality(c1, c2, r1, r2)
        assert provider.verify_equality(
            ec.encode_point(c1), ec.encode_point(c2), T, s
        )
        assert provider.commitment_size() == 33
        assert provider.proof_T_size() == 33
        assert provider.proof_s_size() == 32

    def test_provider_rejects_bad_commitment(self):
        provider = get_provider()
        assert not provider.is_valid_commitment(b"\x04" + b"\x00" * 32)
        assert not provider.is_valid_commitment(b"")

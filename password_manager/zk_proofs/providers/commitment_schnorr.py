"""Concrete provider: Pedersen commitments + Schnorr equality proofs on secp256k1."""

from __future__ import annotations

from ..crypto import schnorr, secp256k1 as ec
from .base import ZKProofProvider


class CommitmentSchnorrProvider(ZKProofProvider):
    scheme = "commitment-schnorr-v1"

    def is_valid_commitment(self, data: bytes) -> bool:
        try:
            ec.decode_point(data)
            return True
        except (ValueError, TypeError):
            return False

    def commitment_size(self) -> int:
        return 33

    def proof_T_size(self) -> int:
        return 33

    def proof_s_size(self) -> int:
        return 32

    def verify_equality(
        self,
        c_a: bytes,
        c_b: bytes,
        proof_T: bytes,
        proof_s: bytes,
    ) -> bool:
        return schnorr.verify_equality(c_a, c_b, proof_T, proof_s)

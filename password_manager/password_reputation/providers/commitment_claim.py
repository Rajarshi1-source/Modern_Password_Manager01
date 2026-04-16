"""
commitment-claim-v1 provider.

Design tradeoff: this v1 provider is **not** a real zero-knowledge proof of
password entropy. A real zk-SNARK circuit for "entropy(password) >= N" is out
of scope for this phase; producing one requires a trusted setup and a
substantial frontend bundle (~1-2MB of proving key). Instead, v1:

  * Accepts a Pedersen commitment to the secret (same primitive the
    ``zk_proofs`` app already exposes) so the server never sees the plaintext.
  * Accepts an ``claimed_entropy_bits`` value in a bounded range.
  * Requires a ``binding_hash`` that ties ``(commitment || claim || user_id)``
    together. This prevents a client from blindly re-using someone else's
    commitment with a different claim, and — together with server-side rate
    limits and "slash on breach" enforcement — gives meaningful game-theoretic
    incentives while keeping the upgrade path clean.

When a real SNARK provider is added later, the interface (``verify_and_score``
+ Pedersen commitment blob) stays identical, so stored proofs continue to be
auditable even after cutting over.

Reward curve (baseline, before any per-user cap applied by the service layer):

    score_delta  = claimed_entropy_bits  (clamped to [MIN_ENTROPY_BITS,
                                          MAX_ENTROPY_BITS])
    tokens_delta = score_delta * TOKENS_PER_BIT
"""

from __future__ import annotations

import hashlib
from typing import Any, Dict

from zk_proofs.crypto import secp256k1 as ec

from .base import ReputationProofProvider, VerificationResult


# Entropy policy — tuned conservatively so a "random 12-char mixed" password
# (~78 bits) lands in the middle of the reward curve. Intentionally rejects
# trivially-small claims and caps large claims to prevent gaming.
MIN_ENTROPY_BITS = 40
MAX_ENTROPY_BITS = 128
TOKENS_PER_BIT = 10

# Binding hash domain separation tag (must match the frontend).
BINDING_DOMAIN = b"pwm-reputation-v1|binding"


def _binding_hash(commitment: bytes, claimed_bits: int, user_id: int) -> bytes:
    h = hashlib.sha256()
    h.update(BINDING_DOMAIN)
    h.update(len(commitment).to_bytes(4, "big"))
    h.update(commitment)
    h.update(int(claimed_bits).to_bytes(4, "big"))
    h.update(int(user_id).to_bytes(8, "big", signed=False))
    return h.digest()


class CommitmentClaimV1Provider(ReputationProofProvider):
    scheme = "commitment-claim-v1"
    commitment_size_bytes = 33  # SEC1 compressed point (matches zk_proofs)

    def is_valid_commitment(self, blob: bytes) -> bool:
        if not isinstance(blob, (bytes, bytearray, memoryview)):
            return False
        if len(bytes(blob)) != self.commitment_size_bytes:
            return False
        try:
            ec.decode_point(bytes(blob))
            return True
        except Exception:
            return False

    def verify_and_score(
        self,
        *,
        commitment: bytes,
        claimed_entropy_bits: int,
        payload: Dict[str, Any],
    ) -> VerificationResult:
        user_id = payload.get("user_id")
        binding_hash = payload.get("binding_hash")

        if user_id is None:
            return VerificationResult(False, claimed_entropy_bits, 0, 0, "Missing user binding.")
        if not isinstance(binding_hash, (bytes, bytearray)) or len(bytes(binding_hash)) != 32:
            return VerificationResult(
                False, claimed_entropy_bits, 0, 0,
                "Missing or malformed binding_hash (expected 32 bytes SHA-256).",
            )
        if not self.is_valid_commitment(commitment):
            return VerificationResult(
                False, claimed_entropy_bits, 0, 0,
                "Commitment is not a valid point for commitment-claim-v1.",
            )
        if claimed_entropy_bits < MIN_ENTROPY_BITS:
            return VerificationResult(
                False, claimed_entropy_bits, 0, 0,
                f"Claimed entropy {claimed_entropy_bits} bits below minimum {MIN_ENTROPY_BITS} bits.",
            )

        expected_binding = _binding_hash(bytes(commitment), claimed_entropy_bits, int(user_id))
        if expected_binding != bytes(binding_hash):
            return VerificationResult(
                False, claimed_entropy_bits, 0, 0,
                "Binding hash mismatch — commitment and claim are not bound to this user.",
            )

        clamped = min(claimed_entropy_bits, MAX_ENTROPY_BITS)
        tokens = clamped * TOKENS_PER_BIT
        return VerificationResult(
            accepted=True,
            claimed_entropy_bits=clamped,
            score_delta=clamped,
            tokens_delta=tokens,
            error="",
            provider_meta={"clamped_from": claimed_entropy_bits, "clamped_to": clamped},
        )


# Exported for frontend parity + tests.
compute_binding_hash = _binding_hash

"""Abstract interface for reputation proof providers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass(frozen=True)
class VerificationResult:
    """Structured outcome returned by provider.verify_and_score.

    score_delta / tokens_delta are advisory — the reputation service layer may
    clamp them based on per-user caps, cooldowns, or configured maxima.
    """

    accepted: bool
    claimed_entropy_bits: int
    score_delta: int
    tokens_delta: int
    error: str = ""
    provider_meta: Optional[Dict[str, Any]] = None


class ReputationProofProvider(ABC):
    """Protocol every reputation scheme must implement."""

    scheme: str
    commitment_size_bytes: int  # length of the binary commitment blob

    @abstractmethod
    def is_valid_commitment(self, blob: bytes) -> bool:
        """True iff ``blob`` decodes as a valid commitment for this scheme."""

    @abstractmethod
    def verify_and_score(
        self,
        *,
        commitment: bytes,
        claimed_entropy_bits: int,
        payload: Dict[str, Any],
    ) -> VerificationResult:
        """Validate the proof and compute the baseline reward.

        Providers should reject payloads they cannot interpret (wrong shape,
        below minimum entropy threshold, malformed aux fields, etc.) and
        return ``VerificationResult(accepted=False, …)`` with a human-readable
        ``error`` string.
        """

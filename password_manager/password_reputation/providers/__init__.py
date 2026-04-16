"""
Pluggable Reputation Proof provider registry.

A "reputation proof" demonstrates that a user knows a secret meeting some
entropy threshold. v1 uses a Pedersen commitment + a bounded entropy claim
(``commitment-claim-v1``); a future provider can plug in a real zk-SNARK
circuit that proves ``entropy(password) >= threshold`` without any claimed
bits and register here.

``verify_and_score`` returns a ``VerificationResult`` describing whether the
proof was accepted and, if so, how much score / how many tokens to mint.
Rate-limiting, cooldowns, and cap logic are enforced in ``services.py``;
providers only speak about the cryptographic payload.
"""

from __future__ import annotations

from .base import ReputationProofProvider, VerificationResult
from .commitment_claim import CommitmentClaimV1Provider

DEFAULT_SCHEME = CommitmentClaimV1Provider.scheme

_REGISTRY = {p.scheme: p for p in [CommitmentClaimV1Provider()]}


def get_provider(scheme: str = DEFAULT_SCHEME) -> ReputationProofProvider:
    if scheme not in _REGISTRY:
        raise ValueError(f"Unknown reputation scheme: {scheme!r}")
    return _REGISTRY[scheme]


def available_schemes() -> list:
    return sorted(_REGISTRY.keys())


__all__ = [
    "ReputationProofProvider",
    "VerificationResult",
    "CommitmentClaimV1Provider",
    "DEFAULT_SCHEME",
    "get_provider",
    "available_schemes",
]

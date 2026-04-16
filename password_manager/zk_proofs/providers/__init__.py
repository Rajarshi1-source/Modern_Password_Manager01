"""
Pluggable ZK proof provider registry.

To add a future backend (e.g. Groth16/PLONK), implement ``ZKProofProvider`` in
a sibling module and register an instance here. Callers use ``get_provider``
with the ``scheme`` string stored on a ``ZKCommitment`` row.
"""

from .base import ZKProofProvider
from .commitment_schnorr import CommitmentSchnorrProvider

DEFAULT_SCHEME = CommitmentSchnorrProvider.scheme

_REGISTRY = {p.scheme: p for p in [CommitmentSchnorrProvider()]}


def get_provider(scheme: str = DEFAULT_SCHEME) -> ZKProofProvider:
    if scheme not in _REGISTRY:
        raise ValueError(f"Unknown ZK scheme: {scheme!r}")
    return _REGISTRY[scheme]


def available_schemes() -> list:
    return sorted(_REGISTRY.keys())


__all__ = [
    "ZKProofProvider",
    "CommitmentSchnorrProvider",
    "DEFAULT_SCHEME",
    "get_provider",
    "available_schemes",
]

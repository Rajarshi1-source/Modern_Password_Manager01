"""
Pluggable on-chain anchor adapters.

Default (Phase 2a): ``NullAnchor`` — records a deterministic "skipped" batch
without any RPC call. Configured via ``settings.PASSWORD_REPUTATION`` or env
var ``REPUTATION_ANCHOR_ADAPTER``.

Phase 2b registers ``ArbitrumAnchor``, which delegates the actual submission
to the already-wired ``blockchain.services.blockchain_anchor_service`` and
calls ``CommitmentRegistry.anchorCommitment(merkleRoot, batchSize, signature)``.
"""

from __future__ import annotations

import logging
import os

from django.conf import settings

from .base import AnchorAdapter, AnchorResult
from .null_anchor import NullAnchor

logger = logging.getLogger(__name__)

# Populated lazily so importing this module never hard-requires web3/eth.
_REGISTRY: dict[str, AnchorAdapter] = {NullAnchor.name: NullAnchor()}


def _try_register_arbitrum() -> None:
    """Import ArbitrumAnchor on demand so Phase 2a works without web3."""
    try:
        from .arbitrum_anchor import ArbitrumAnchor
    except ImportError as exc:  # pragma: no cover - only matters when web3 missing
        logger.info("ArbitrumAnchor unavailable (%s); sticking with NullAnchor.", exc)
        return
    adapter = ArbitrumAnchor()
    _REGISTRY[adapter.name] = adapter


def configured_adapter_name() -> str:
    """Resolve the configured adapter name from settings / env."""
    config = getattr(settings, "PASSWORD_REPUTATION", {}) or {}
    name = (
        config.get("ANCHOR_ADAPTER")
        or os.environ.get("REPUTATION_ANCHOR_ADAPTER")
        or NullAnchor.name
    )
    return str(name).lower()


def get_adapter(name: str | None = None) -> AnchorAdapter:
    resolved = (name or configured_adapter_name()).lower()
    if resolved == "arbitrum" and "arbitrum" not in _REGISTRY:
        _try_register_arbitrum()
    if resolved not in _REGISTRY:
        logger.warning(
            "Unknown anchor adapter %r — falling back to NullAnchor.", resolved,
        )
        return _REGISTRY[NullAnchor.name]
    return _REGISTRY[resolved]


def available_adapters() -> list[str]:
    # Probe for Arbitrum so admin/debug surfaces list it when available.
    if "arbitrum" not in _REGISTRY:
        _try_register_arbitrum()
    return sorted(_REGISTRY.keys())


__all__ = [
    "AnchorAdapter",
    "AnchorResult",
    "NullAnchor",
    "get_adapter",
    "available_adapters",
    "configured_adapter_name",
]

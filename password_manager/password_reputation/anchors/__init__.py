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
    adapter_key: str = (name or configured_adapter_name()).lower()
    if adapter_key == "arbitrum" and "arbitrum" not in _REGISTRY:
        _try_register_arbitrum()
    if adapter_key not in _REGISTRY:
        # Log a constant string only — never include `adapter_key` or any
        # value derived from it. CodeQL's clear-text-logging dataflow tracks
        # the `name` parameter all the way to any logger call site, so the
        # diagnostic value of including the token isn't worth the false-
        # positive churn. Operators can grep the registry or set
        # PASSWORD_REPUTATION/REPUTATION_ANCHOR_ADAPTER to debug.
        logger.warning("Unknown anchor adapter configured; falling back to NullAnchor.")
        return _REGISTRY[NullAnchor.name]
    return _REGISTRY[adapter_key]


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

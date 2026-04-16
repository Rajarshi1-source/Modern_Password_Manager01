"""NullAnchor — no-op adapter used in Phase 2a and in tests."""

from __future__ import annotations

from .base import AnchorAdapter, AnchorResult


class NullAnchor(AnchorAdapter):
    """Records a deterministic "skipped" batch without talking to any chain.

    Useful for:
      * Phase 2a: ship the reputation backend before wiring up Arbitrum.
      * Dev / test environments where a real chain is unavailable.
      * Feature-flagging anchoring off without code changes.
    """

    name = "null"

    def is_enabled(self) -> bool:
        return True

    def submit_batch(self, *, merkle_root_hex: str, batch_size: int) -> AnchorResult:
        return AnchorResult(
            status="skipped",
            tx_hash="",
            block_number=None,
            network="null",
            error="",
        )

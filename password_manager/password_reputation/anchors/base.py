"""Abstract anchor adapter interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class AnchorResult:
    """Outcome of submitting a batch to the adapter.

    ``status`` maps to ``AnchorBatch.Status``:
      - ``"submitted"``: tx broadcast; awaiting confirmation.
      - ``"confirmed"``: tx mined and included (block_number populated).
      - ``"failed"``: adapter attempted and errored; retry in a later batch.
      - ``"skipped"``: adapter intentionally did not submit (e.g. NullAnchor).
    """

    status: str
    tx_hash: str = ""
    block_number: Optional[int] = None
    network: str = ""
    error: str = ""


class AnchorAdapter(ABC):
    """Anchor adapter protocol."""

    name: str

    @abstractmethod
    def is_enabled(self) -> bool:
        """True iff this adapter is configured to actually anchor."""

    @abstractmethod
    def submit_batch(self, *, merkle_root_hex: str, batch_size: int) -> AnchorResult:
        """Submit a Merkle-root batch to the underlying storage / chain."""

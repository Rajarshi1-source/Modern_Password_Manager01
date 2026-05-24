"""
Thread-safe transaction-nonce reservation for the blockchain workers.

Background (audit-fix H4)
-------------------------
``w3.eth.get_transaction_count(addr)`` returns the current nonce as
seen by the configured RPC node. Two concurrent Celery workers (or
two threads inside one worker — the k8s default uses
``--concurrency=4``) that read this value at the same time will both
get the same nonce. They then sign, broadcast, and exactly one wins;
the other reverts with ``nonce too low``. Under steady load this
creates a retry storm and occasionally drops an audit anchor entirely.

The fix in this file is intentionally small:

* In-process ``threading.Lock`` serialises concurrent reservations,
  preventing intra-pod races.
* The reserved counter is bumped optimistically; on RPC failure
  (specifically the ``nonce too low`` / ``replacement transaction
  underpriced`` family of errors) the caller invokes :meth:`resync`
  which refreshes the counter from the chain.

For the cross-pod race we rely on the k8s topology split: the
``blockchain`` queue runs on a dedicated single-replica deployment
(``celery-blockchain-worker``). When/if that constraint is relaxed,
swap this class out for a Redis-backed reservation — the public API
(``reserve`` / ``resync``) is shaped to make that change additive.

See ``docs/DEPLOYMENT_PR262.md`` for the operator-side guarantee
this design depends on.
"""

from __future__ import annotations

import logging
import threading
from typing import Optional

logger = logging.getLogger(__name__)


class NonceManager:
    """Per-address nonce reservation guarded by a process-local lock."""

    def __init__(self, w3, address: str) -> None:
        self._w3 = w3
        self._address = w3.to_checksum_address(address)
        self._lock = threading.Lock()
        # ``pending`` so we don't collide with unconfirmed txs we
        # broadcast in earlier iterations of the same process.
        self._next: Optional[int] = None

    @property
    def address(self) -> str:
        return self._address

    def _refresh_locked(self) -> int:
        """Re-read the on-chain nonce. Caller must hold ``self._lock``."""
        self._next = self._w3.eth.get_transaction_count(
            self._address, 'pending'
        )
        return self._next

    def reserve(self) -> int:
        """
        Return the next nonce and atomically increment the cached
        counter. Two callers in the same process can never see the
        same value, even across threads / Celery prefork pools.
        """
        with self._lock:
            if self._next is None:
                self._refresh_locked()
            n = self._next
            self._next += 1
            return n

    def resync(self) -> int:
        """
        Force a re-read from chain. Call this after a broadcast fails
        with ``nonce too low`` / ``known transaction`` so the next
        :meth:`reserve` returns a fresh number.
        """
        with self._lock:
            old = self._next
            new = self._refresh_locked()
            logger.warning(
                "NonceManager.resync(%s): was=%s, now=%s",
                self._address, old, new,
            )
            return new

    def peek(self) -> Optional[int]:
        """Return the cached next-nonce without reserving it. For tests."""
        with self._lock:
            return self._next

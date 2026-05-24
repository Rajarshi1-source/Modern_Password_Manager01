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

Design
------
* In-process ``threading.Lock`` serialises concurrent reservations,
  preventing intra-pod races.
* Reservations use a **lease/commit/release** API (audit-fix from
  PR #272 review). The cached counter is advanced when a nonce is
  leased, but the caller MUST call :meth:`Lease.commit` after a
  successful ``send_raw_transaction``, or :meth:`Lease.release` on
  any failure between lease and broadcast (build / sign / send).
  Release rolls the counter back to the smallest non-released value
  so a later transaction doesn't sit behind a permanent gap.

* For the cross-pod race we rely on the k8s topology split: the
  ``blockchain`` queue runs on a dedicated single-replica deployment
  (``celery-blockchain-worker``). When/if that constraint is relaxed,
  swap this class out for a Redis-backed reservation — the public
  API (``lease`` / ``commit`` / ``release`` / ``resync``) is shaped
  to make that change additive.

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
        # Released nonces that haven't been recommitted yet. Tracked
        # so we never hand the same number out twice when a caller
        # fails mid-broadcast and we have to roll back.
        self._released: set[int] = set()

    @property
    def address(self) -> str:
        return self._address

    def _refresh_locked(self) -> int:
        """Re-read the on-chain nonce. Caller must hold ``self._lock``."""
        self._next = self._w3.eth.get_transaction_count(
            self._address, 'pending'
        )
        # Any cached released nonces below the new floor are obsolete.
        self._released = {n for n in self._released if n >= self._next}
        return self._next

    def lease(self) -> 'NonceLease':
        """
        Return a :class:`NonceLease` holding the next nonce. The cached
        counter is advanced now; the lease MUST be either ``commit``-ed
        (after a successful broadcast) or ``release``-d (on any failure
        before broadcast) before the worker moves on. Failing to do
        either creates a permanent in-memory gap.
        """
        with self._lock:
            if self._next is None:
                self._refresh_locked()

            # Prefer a previously-released slot before advancing the
            # high-water mark — keeps the counter dense and avoids
            # ever-growing _released sets under repeated failures.
            if self._released:
                n = min(self._released)
                self._released.remove(n)
            else:
                n = self._next
                self._next += 1
            return NonceLease(self, n)

    def reserve(self) -> int:
        """
        Back-compat alias for callers that just want a raw nonce and
        will handle commit/release out-of-band. New code should use
        :meth:`lease` so the manager can roll the counter back on
        failure.
        """
        return self.lease().value

    def resync(self) -> int:
        """
        Force a re-read from chain. Call this after a broadcast fails
        with ``nonce too low`` / ``known transaction`` so the next
        :meth:`lease` returns a fresh number.
        """
        with self._lock:
            old = self._next
            new = self._refresh_locked()
            logger.warning(
                "NonceManager.resync(%s): was=%s, now=%s",
                self._address, old, new,
            )
            return new

    def _on_release(self, n: int) -> None:
        """Internal hook used by :class:`NonceLease` on rollback."""
        with self._lock:
            # If the released nonce is the top of the cache, just step
            # _next back. Otherwise stash it so the next lease can
            # reuse it before allocating a fresh slot.
            if self._next is not None and n == self._next - 1:
                self._next -= 1
            else:
                self._released.add(n)
            logger.debug(
                "NonceManager.release(%s): nonce=%s, next=%s, released=%s",
                self._address, n, self._next, sorted(self._released),
            )

    def peek(self) -> Optional[int]:
        """Return the cached next-nonce without reserving it. For tests."""
        with self._lock:
            return self._next


class NonceLease:
    """
    Lease handle for a single nonce reservation.

    Lifecycle: ``lease()`` → either ``commit()`` (broadcast succeeded
    and the chain consumed this nonce) or ``release()`` (broadcast
    failed; roll the counter back). ``commit`` and ``release`` are
    idempotent; calling either twice is a no-op.
    """

    __slots__ = ('_manager', 'value', '_settled')

    def __init__(self, manager: 'NonceManager', value: int) -> None:
        self._manager = manager
        self.value = value
        self._settled = False

    def commit(self) -> None:
        """Mark the leased nonce as actually consumed by chain."""
        self._settled = True

    def release(self) -> None:
        """Roll the leased nonce back into the manager's free pool."""
        if not self._settled:
            self._settled = True
            self._manager._on_release(self.value)

    def __enter__(self) -> 'NonceLease':
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        # Default: if the caller exits the `with` block without
        # explicitly committing, treat it as a failure and roll back.
        if not self._settled:
            self.release()
        return False  # don't suppress exceptions

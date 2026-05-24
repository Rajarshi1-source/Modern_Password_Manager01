"""
Blockchain failure-classification taxonomy.

Audit-fix M10 (2026-05)
-----------------------
The circuit-breaker used to count every exception its protected call
raised toward the failure threshold. That conflated two very different
populations:

* **Transient infra failures** — RPC down, HTTP 5xx from the node,
  socket timeout, ``nonce too low`` race. These genuinely indicate
  the underlying provider is unhealthy and the breaker SHOULD open
  to stop the retry storm.
* **Deterministic contract reverts** — a user attempting to unlock a
  TimeLockedVault before its time, a multi-sig that hasn't reached
  threshold, an oracle still inside its grace window. The on-chain
  call cleanly reverted because the on-chain condition wasn't met;
  the RPC is perfectly healthy and the next user with a different
  vault should succeed. The breaker MUST NOT open on these.

The previous bare ``blockchain_breaker.on_failure(e)`` flow treated
both as failures, so a single user trying to unlock a not-yet-ready
vault could ripple through the threshold and DoS the entire
blockchain anchoring pipeline for the recovery_timeout window.

Callers are now expected to wrap raw web3.py / eth_account exceptions
into one of the classes below, and ``shared.circuit_breaker.CircuitBreaker.
on_failure`` skips the counter increment for ``BlockchainContractRevert``.
"""

from __future__ import annotations


class BlockchainError(Exception):
    """Base class — never raise this directly."""


class BlockchainTransient(BlockchainError):
    """
    Underlying infra is unhealthy. Counts toward the circuit breaker.

    Typical causes:
      * RPC node returning 5xx
      * Provider socket timeout / connection refused
      * `nonce too low` / `replacement transaction underpriced`
      * `insufficient funds for gas`
    """


class BlockchainContractRevert(BlockchainError):
    """
    The on-chain call reverted deterministically because the contract
    said no (`require(...)` failed, custom error emitted, condition
    not met). The infra is fine and another caller may succeed; do
    NOT open the breaker.

    Typical causes:
      * `Conditions not met` from TimeLockedVault.unlockVault
      * `Already anchored` from VaultAuditLog
      * `Unauthorized signer` from CommitmentRegistry
    """


# ---------------------------------------------------------------------------
# Helper: best-effort classification of a raw web3.py / eth_utils exception.
# Used by call sites that don't know up-front which class to raise.
# ---------------------------------------------------------------------------

_REVERT_MARKERS = (
    'execution reverted',
    'require(...)',
    'custom error',
    'not authorized',
    'unauthorized',
    'conditions not met',
    'switch not triggered',
    'already anchored',
    'invalid signature',
    'invalid batch size',
    'cannot remove last',
    'renounce disabled',
    'use releaseescrow()',
    'use triggerdeadmansswitch()',
)


def classify(exc: Exception) -> BlockchainError:
    """
    Map a raw exception to the right ``BlockchainError`` subclass.

    Conservative: anything that isn't unambiguously a deterministic
    revert is treated as transient (opens the breaker). False
    positives here just mean a brief retry pause — much safer than
    misclassifying a real outage as "user error" and never opening.
    """
    if isinstance(exc, BlockchainError):
        return exc
    msg = str(exc).lower()
    for marker in _REVERT_MARKERS:
        if marker in msg:
            return BlockchainContractRevert(str(exc))
    return BlockchainTransient(str(exc))

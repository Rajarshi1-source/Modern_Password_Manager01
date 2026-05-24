"""On-chain anchoring via the existing :mod:`blockchain` app.

We store ``sha256(vc_jwt)`` as the anchor commitment so the credential
contents never leave our database even when anchored publicly.

Audit-fix M6 (2026-05): the previous implementation imported a
``BlockchainCommitment`` model that **does not exist** in the
``blockchain`` app (only ``BlockchainAnchor``, ``MerkleProof``, and
``PendingCommitment`` are defined there). The ``except Exception``
swallowed the resulting ``ImportError`` and the entire
``anchor_commitment`` call silently no-op'd — meaning every VC
issuance that was supposed to be on-chain anchored just wasn't.

The integration path needs real product work (deciding how a VC
anchor maps to ``PendingCommitment``'s ``BehavioralCommitment`` FK,
or introducing a separate VC-specific model). Until that lands, this
function returns ``None`` deliberately and logs an explicit warning
so anyone enabling the feature flag sees the gap immediately.

We narrow the exception to ``ImportError`` so any future caller that
breaks transitive imports (circular, missing dep) gets a loud
failure instead of being papered over.
"""

from __future__ import annotations

import hashlib
import logging
from typing import Optional

from django.conf import settings

logger = logging.getLogger(__name__)


def anchor_commitment(vc_jwt: str, vc_id: str) -> Optional[str]:
    if not getattr(settings, "VC_CHAIN_ANCHOR_ENABLED", False):
        return None

    # The digest itself is still useful as an audit log artifact even
    # when the on-chain anchor is unimplemented. Compute and log it so
    # the operator has the value to manually paste into a backfill
    # script once the proper integration ships.
    digest = hashlib.sha256(vc_jwt.encode("utf-8")).hexdigest()

    try:
        # We import to surface ImportError loudly (so the operator
        # notices the blockchain app is genuinely unavailable) but the
        # anchoring itself is intentionally a no-op pending real
        # integration. See the module docstring.
        from blockchain.tasks import anchor_pending_commitments  # noqa: F401
    except ImportError:
        logger.warning(
            "VC_CHAIN_ANCHOR_ENABLED=True but the `blockchain` app is "
            "not importable; skipping anchor for vc_id=%s",
            vc_id,
        )
        return None

    logger.warning(
        "VC chain-anchor is a planned feature, not yet wired to a "
        "concrete model. vc_id=%s digest=%s — value computed but "
        "NOT persisted on-chain. Track this gap in the project's "
        "issue list before enabling VC_CHAIN_ANCHOR_ENABLED in prod.",
        vc_id, digest,
    )
    return None

"""On-chain anchoring via the existing :mod:`blockchain` app.

We store ``sha256(vc_jwt)`` as the anchor commitment so the credential
contents never leave our database even when anchored publicly.
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
    digest = hashlib.sha256(vc_jwt.encode("utf-8")).hexdigest()
    try:
        from blockchain.tasks import anchor_pending_commitments  # type: ignore
        from blockchain.models import BlockchainCommitment  # type: ignore
    except Exception:
        logger.debug("blockchain app not available; skipping anchor")
        return None

    try:
        commitment = BlockchainCommitment.objects.create(
            commitment_hash=digest,
            metadata={"source": "vc", "vc_id": str(vc_id)},
        )
        # Schedule the on-chain post; the task drains the queue.
        try:
            anchor_pending_commitments.delay()
        except Exception:
            logger.debug("Celery not running; commitment queued synchronously")
        return str(commitment.pk)
    except Exception:
        logger.exception("chain_anchor failed")
        return None

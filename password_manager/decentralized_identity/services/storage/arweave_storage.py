"""Arweave storage backend.

If the ``arweave-python-client`` dependency isn't installed, or an
``ARWEAVE_WALLET_JSON`` env var isn't provided, the backend logs a debug
message and returns ``None`` rather than raising - callers treat this as
"chain anchoring disabled".
"""

from __future__ import annotations

import json
import logging
from typing import Optional

from django.conf import settings

logger = logging.getLogger(__name__)


def upload_to_arweave(payload: dict, vc_id: str) -> Optional[str]:
    wallet_json = getattr(settings, "ARWEAVE_WALLET_JSON", "")
    if not wallet_json:
        return None
    try:
        from arweave.arweave_lib import Wallet, Transaction  # type: ignore
    except Exception:
        logger.debug("arweave-python-client not available; skipping")
        return None

    try:
        wallet = Wallet.from_data(json.loads(wallet_json))
        tx = Transaction(wallet, data=json.dumps(payload).encode("utf-8"))
        tx.add_tag("Content-Type", "application/json")
        tx.add_tag("App-Name", "SecureVault-VC")
        tx.add_tag("VC-Id", str(vc_id))
        tx.sign()
        tx.send()
        return tx.id
    except Exception:
        logger.exception("Arweave upload raised")
        return None

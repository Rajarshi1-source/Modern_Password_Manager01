"""IPFS storage via Pinata (primary) with Web3.Storage as fallback."""

from __future__ import annotations

import json
import logging
from typing import Optional

from django.conf import settings

logger = logging.getLogger(__name__)


PINATA_ENDPOINT = "https://api.pinata.cloud/pinning/pinJSONToIPFS"
WEB3_STORAGE_ENDPOINT = "https://api.web3.storage/upload"


def upload_to_ipfs(payload: dict, vc_id: str) -> Optional[str]:
    """Pin a JSON payload to IPFS and return its CID."""
    jwt = getattr(settings, "PINATA_JWT", "")
    if jwt:
        try:
            import requests

            resp = requests.post(
                PINATA_ENDPOINT,
                headers={
                    "Authorization": f"Bearer {jwt}",
                    "Content-Type": "application/json",
                },
                data=json.dumps(
                    {
                        "pinataMetadata": {"name": f"vc-{vc_id}"},
                        "pinataContent": payload,
                    }
                ),
                timeout=15,
            )
            if resp.status_code < 400:
                return resp.json().get("IpfsHash")
            logger.warning("Pinata pin failed: %s", resp.text)
        except Exception:
            logger.exception("Pinata upload raised")

    token = getattr(settings, "WEB3_STORAGE_TOKEN", "")
    if token:
        try:
            import requests

            resp = requests.post(
                WEB3_STORAGE_ENDPOINT,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
                data=json.dumps(payload),
                timeout=15,
            )
            if resp.status_code < 400:
                return resp.json().get("cid")
            logger.warning("Web3.Storage upload failed: %s", resp.text)
        except Exception:
            logger.exception("Web3.Storage upload raised")
    return None

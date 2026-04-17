"""Apple Health adapter.

Apple Health does not expose a server-side OAuth API. The iOS/macOS client is
expected to POST HealthKit sleep samples to the ``wearable_ingest`` endpoint.
This adapter therefore implements the data-path half of the protocol only.
"""

from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Tuple

from .base import BaseAdapter


class AppleHealthAdapter(BaseAdapter):
    provider_key = "apple_health"
    requires_oauth = False

    def authorize_url(self, user) -> Tuple[str, str]:
        raise NotImplementedError(
            "Apple Health does not support server-side OAuth. "
            "Use the mobile client to push observations to the ingest endpoint."
        )

    def exchange_code(self, user, code: str, state: str) -> Dict:
        raise NotImplementedError(
            "Apple Health uses push ingestion; there is no code to exchange."
        )

    def fetch_sleep(self, link, start: datetime, end: datetime) -> List[Dict]:
        return []

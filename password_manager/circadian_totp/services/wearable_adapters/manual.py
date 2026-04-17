"""Manual / self-reported sleep adapter.

Provides a pure ingest path for users without wearables.
"""

from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Tuple

from .base import BaseAdapter


class ManualAdapter(BaseAdapter):
    provider_key = "manual"
    requires_oauth = False

    def authorize_url(self, user) -> Tuple[str, str]:
        raise NotImplementedError("Manual provider does not use OAuth.")

    def exchange_code(self, user, code: str, state: str) -> Dict:
        raise NotImplementedError("Manual provider does not use OAuth.")

    def fetch_sleep(self, link, start: datetime, end: datetime) -> List[Dict]:
        return []

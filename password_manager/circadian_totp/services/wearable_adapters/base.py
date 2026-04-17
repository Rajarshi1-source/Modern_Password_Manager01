"""Abstract base class for wearable provider adapters."""

from __future__ import annotations

import secrets
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Dict, List, Tuple


class BaseAdapter(ABC):
    """Interface every wearable adapter must implement.

    The workflow is:
      1. ``authorize_url(user)`` returns the OAuth consent URL + a CSRF state.
      2. The browser redirects back to our callback with a `code`.
      3. ``exchange_code(user, code, state)`` returns token material which the
         service layer persists (encrypted) in a ``WearableLink`` row.
      4. ``refresh(link)`` produces a fresh access token when a pull is made.
      5. ``fetch_sleep(link, start, end)`` returns a list of observations
         ready for ``ingest_sleep_observations``.
    """

    provider_key: str = ""
    requires_oauth: bool = True

    # ---- OAuth lifecycle --------------------------------------------------

    @abstractmethod
    def authorize_url(self, user) -> Tuple[str, str]:
        """Return ``(consent_url, state)``.

        May raise :class:`NotImplementedError` if the provider only supports
        push ingestion (e.g., Apple Health).
        """

    @abstractmethod
    def exchange_code(self, user, code: str, state: str) -> Dict:
        """Exchange the one-time ``code`` for access + refresh tokens."""

    def refresh(self, link) -> Dict:  # pragma: no cover - provider specific
        """Return refreshed token material or an empty dict if not needed."""
        return {}

    # ---- Data pull --------------------------------------------------------

    @abstractmethod
    def fetch_sleep(self, link, start: datetime, end: datetime) -> List[Dict]:
        """Return a list of ``{sleep_start, sleep_end, efficiency_score}``."""

    # ---- Helpers ----------------------------------------------------------

    @staticmethod
    def generate_state() -> str:
        return secrets.token_urlsafe(24)

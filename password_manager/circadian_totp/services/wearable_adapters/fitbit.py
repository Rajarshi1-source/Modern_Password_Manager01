"""Fitbit Web API adapter.

Docs: https://dev.fitbit.com/build/reference/web-api/
This is the primary live provider. When ``FITBIT_CLIENT_ID`` is not set the
adapter short-circuits with a clear error so tests can still import cleanly.
"""

from __future__ import annotations

import base64
import logging
from datetime import datetime, timedelta, timezone as _tz
from typing import Dict, List, Tuple
from urllib.parse import urlencode

from django.conf import settings
from django.utils import timezone as djtz

from .base import BaseAdapter

logger = logging.getLogger(__name__)


FITBIT_AUTH_URL = "https://www.fitbit.com/oauth2/authorize"
FITBIT_TOKEN_URL = "https://api.fitbit.com/oauth2/token"
FITBIT_API = "https://api.fitbit.com"
FITBIT_SCOPES = "sleep profile"


class FitbitAdapter(BaseAdapter):
    provider_key = "fitbit"
    requires_oauth = True

    # ---- Helpers ----------------------------------------------------------

    def _config(self) -> Tuple[str, str, str]:
        client_id = getattr(settings, "FITBIT_CLIENT_ID", "")
        client_secret = getattr(settings, "FITBIT_CLIENT_SECRET", "")
        redirect_uri = getattr(settings, "FITBIT_REDIRECT_URI", "")
        if not client_id or not client_secret:
            raise ValueError(
                "Fitbit OAuth is not configured: "
                "set FITBIT_CLIENT_ID + FITBIT_CLIENT_SECRET"
            )
        return client_id, client_secret, redirect_uri

    def _basic_auth_header(self) -> str:
        client_id, client_secret, _ = self._config()
        token = base64.b64encode(
            f"{client_id}:{client_secret}".encode("utf-8")
        ).decode("ascii")
        return f"Basic {token}"

    # ---- OAuth ------------------------------------------------------------

    def authorize_url(self, user):
        client_id, _, redirect_uri = self._config()
        state = self.generate_state()
        params = {
            "response_type": "code",
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "scope": FITBIT_SCOPES,
            "state": state,
            "expires_in": 604800,
        }
        return f"{FITBIT_AUTH_URL}?{urlencode(params)}", state

    def exchange_code(self, user, code: str, state: str) -> Dict:
        import requests  # deferred import so the module remains import-safe

        _, _, redirect_uri = self._config()
        resp = requests.post(
            FITBIT_TOKEN_URL,
            headers={
                "Authorization": self._basic_auth_header(),
                "Content-Type": "application/x-www-form-urlencoded",
            },
            data={
                "grant_type": "authorization_code",
                "redirect_uri": redirect_uri,
                "code": code,
            },
            timeout=15,
        )
        if resp.status_code >= 400:
            logger.warning("Fitbit token exchange failed: %s", resp.text)
            raise ValueError("Fitbit token exchange failed")
        payload = resp.json()
        expires_at = djtz.now() + timedelta(seconds=int(payload.get("expires_in", 0)))
        return {
            "access_token": payload.get("access_token", ""),
            "refresh_token": payload.get("refresh_token", ""),
            "scope": payload.get("scope", ""),
            "token_type": payload.get("token_type", "Bearer"),
            "expires_at": expires_at,
            "user_id": payload.get("user_id", ""),
        }

    def refresh(self, link) -> Dict:
        import requests

        from ...crypto_utils import decrypt_string

        refresh_token = decrypt_string(link.oauth_refresh_token_encrypted)
        if not refresh_token:
            raise ValueError("No refresh token stored for this Fitbit link")
        resp = requests.post(
            FITBIT_TOKEN_URL,
            headers={
                "Authorization": self._basic_auth_header(),
                "Content-Type": "application/x-www-form-urlencoded",
            },
            data={
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
            },
            timeout=15,
        )
        if resp.status_code >= 400:
            logger.warning("Fitbit refresh failed: %s", resp.text)
            raise ValueError("Fitbit token refresh failed")
        payload = resp.json()
        expires_at = djtz.now() + timedelta(seconds=int(payload.get("expires_in", 0)))
        return {
            "access_token": payload.get("access_token", ""),
            "refresh_token": payload.get("refresh_token", ""),
            "scope": payload.get("scope", ""),
            "token_type": payload.get("token_type", "Bearer"),
            "expires_at": expires_at,
        }

    # ---- Data pull --------------------------------------------------------

    def fetch_sleep(self, link, start: datetime, end: datetime) -> List[Dict]:
        import requests

        from ...crypto_utils import decrypt_string

        access = decrypt_string(link.oauth_access_token_encrypted)
        if not access:
            raise ValueError("No access token stored for this Fitbit link")
        url = (
            f"{FITBIT_API}/1.2/user/-/sleep/date/"
            f"{start.date().isoformat()}/{end.date().isoformat()}.json"
        )
        resp = requests.get(
            url,
            headers={"Authorization": f"Bearer {access}"},
            timeout=15,
        )
        if resp.status_code == 401:
            raise ValueError("Fitbit access token expired")
        if resp.status_code >= 400:
            logger.warning("Fitbit sleep fetch failed: %s", resp.text)
            raise ValueError("Fitbit sleep fetch failed")
        data = resp.json().get("sleep", []) or []
        out: List[Dict] = []
        for entry in data:
            try:
                start_dt = datetime.fromisoformat(entry["startTime"]).astimezone(_tz.utc)
                end_dt = datetime.fromisoformat(entry["endTime"]).astimezone(_tz.utc)
                out.append(
                    {
                        "sleep_start": start_dt,
                        "sleep_end": end_dt,
                        "efficiency_score": float(entry.get("efficiency") or 0) / 100.0
                        if entry.get("efficiency")
                        else None,
                    }
                )
            except (KeyError, ValueError):
                logger.debug("Skipping malformed Fitbit sleep entry: %s", entry)
        return out

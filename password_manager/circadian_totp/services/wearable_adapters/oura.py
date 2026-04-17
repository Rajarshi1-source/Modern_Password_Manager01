"""Oura adapter.

Oura has a first-class OAuth2 API (see https://cloud.ouraring.com/docs/api).
When ``OURA_CLIENT_ID`` is not configured the adapter will raise so callers
can fall back to manual ingestion.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone as _tz
from typing import Dict, List, Tuple
from urllib.parse import urlencode

from django.conf import settings
from django.utils import timezone as djtz

from .base import BaseAdapter

logger = logging.getLogger(__name__)


OURA_AUTH_URL = "https://cloud.ouraring.com/oauth/authorize"
OURA_TOKEN_URL = "https://api.ouraring.com/oauth/token"
OURA_API = "https://api.ouraring.com"
OURA_SCOPES = "email personal daily"


class OuraAdapter(BaseAdapter):
    provider_key = "oura"
    requires_oauth = True

    def _config(self) -> Tuple[str, str, str]:
        client_id = getattr(settings, "OURA_CLIENT_ID", "")
        client_secret = getattr(settings, "OURA_CLIENT_SECRET", "")
        redirect_uri = getattr(settings, "OURA_REDIRECT_URI", "")
        if not client_id or not client_secret:
            raise ValueError(
                "Oura OAuth is not configured: set OURA_CLIENT_ID + OURA_CLIENT_SECRET"
            )
        return client_id, client_secret, redirect_uri

    def authorize_url(self, user):
        client_id, _, redirect_uri = self._config()
        state = self.generate_state()
        params = {
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": OURA_SCOPES,
            "state": state,
        }
        return f"{OURA_AUTH_URL}?{urlencode(params)}", state

    def exchange_code(self, user, code: str, state: str) -> Dict:
        import requests

        client_id, client_secret, redirect_uri = self._config()
        resp = requests.post(
            OURA_TOKEN_URL,
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": redirect_uri,
                "client_id": client_id,
                "client_secret": client_secret,
            },
            timeout=15,
        )
        if resp.status_code >= 400:
            logger.warning("Oura token exchange failed: %s", resp.text)
            raise ValueError("Oura token exchange failed")
        payload = resp.json()
        expires_at = djtz.now() + timedelta(seconds=int(payload.get("expires_in", 0)))
        return {
            "access_token": payload.get("access_token", ""),
            "refresh_token": payload.get("refresh_token", ""),
            "scope": payload.get("scope", OURA_SCOPES),
            "token_type": payload.get("token_type", "Bearer"),
            "expires_at": expires_at,
        }

    def fetch_sleep(self, link, start: datetime, end: datetime) -> List[Dict]:
        import requests

        from ...crypto_utils import decrypt_string

        access = decrypt_string(link.oauth_access_token_encrypted)
        if not access:
            raise ValueError("No access token for Oura link")
        url = (
            f"{OURA_API}/v2/usercollection/sleep"
            f"?start_date={start.date().isoformat()}"
            f"&end_date={end.date().isoformat()}"
        )
        resp = requests.get(
            url, headers={"Authorization": f"Bearer {access}"}, timeout=15
        )
        if resp.status_code >= 400:
            raise ValueError("Oura sleep fetch failed")
        out: List[Dict] = []
        for e in resp.json().get("data", []) or []:
            try:
                s = datetime.fromisoformat(e["bedtime_start"]).astimezone(_tz.utc)
                t = datetime.fromisoformat(e["bedtime_end"]).astimezone(_tz.utc)
                out.append(
                    {
                        "sleep_start": s,
                        "sleep_end": t,
                        "efficiency_score": (float(e.get("efficiency")) / 100.0)
                        if e.get("efficiency")
                        else None,
                    }
                )
            except (KeyError, ValueError):
                continue
        return out

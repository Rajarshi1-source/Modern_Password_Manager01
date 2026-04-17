"""Google Fit adapter (v1 stub).

Google Fit uses the Google OAuth 2.0 flow. The adapter below constructs the
authorize URL and performs the token exchange when credentials are present;
sleep data is pulled from the Users.sessions endpoint.
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


GFIT_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GFIT_TOKEN_URL = "https://oauth2.googleapis.com/token"
GFIT_API = "https://www.googleapis.com/fitness/v1"
GFIT_SCOPES = (
    "https://www.googleapis.com/auth/fitness.sleep.read "
    "https://www.googleapis.com/auth/fitness.activity.read"
)


class GoogleFitAdapter(BaseAdapter):
    provider_key = "google_fit"
    requires_oauth = True

    def _config(self) -> Tuple[str, str, str]:
        client_id = getattr(settings, "GOOGLE_FIT_CLIENT_ID", "")
        client_secret = getattr(settings, "GOOGLE_FIT_CLIENT_SECRET", "")
        redirect_uri = getattr(settings, "GOOGLE_FIT_REDIRECT_URI", "")
        if not client_id or not client_secret:
            raise ValueError("Google Fit OAuth is not configured")
        return client_id, client_secret, redirect_uri

    def authorize_url(self, user):
        client_id, _, redirect_uri = self._config()
        state = self.generate_state()
        params = {
            "response_type": "code",
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "scope": GFIT_SCOPES,
            "access_type": "offline",
            "prompt": "consent",
            "state": state,
        }
        return f"{GFIT_AUTH_URL}?{urlencode(params)}", state

    def exchange_code(self, user, code: str, state: str) -> Dict:
        import requests

        client_id, client_secret, redirect_uri = self._config()
        resp = requests.post(
            GFIT_TOKEN_URL,
            data={
                "code": code,
                "client_id": client_id,
                "client_secret": client_secret,
                "redirect_uri": redirect_uri,
                "grant_type": "authorization_code",
            },
            timeout=15,
        )
        if resp.status_code >= 400:
            logger.warning("Google Fit token exchange failed: %s", resp.text)
            raise ValueError("Google Fit token exchange failed")
        payload = resp.json()
        expires_at = djtz.now() + timedelta(seconds=int(payload.get("expires_in", 0)))
        return {
            "access_token": payload.get("access_token", ""),
            "refresh_token": payload.get("refresh_token", ""),
            "scope": payload.get("scope", GFIT_SCOPES),
            "token_type": payload.get("token_type", "Bearer"),
            "expires_at": expires_at,
        }

    def fetch_sleep(self, link, start: datetime, end: datetime) -> List[Dict]:
        import requests

        from ...crypto_utils import decrypt_string

        access = decrypt_string(link.oauth_access_token_encrypted)
        if not access:
            raise ValueError("No access token for Google Fit link")
        # Google Fit encodes sleep as Session activityType 72.
        start_ms = int(start.timestamp() * 1000)
        end_ms = int(end.timestamp() * 1000)
        url = (
            f"{GFIT_API}/users/me/sessions?"
            f"startTime={start.isoformat()}&endTime={end.isoformat()}"
            f"&activityType=72"
        )
        resp = requests.get(
            url, headers={"Authorization": f"Bearer {access}"}, timeout=15
        )
        if resp.status_code >= 400:
            raise ValueError("Google Fit sleep fetch failed")
        out: List[Dict] = []
        for session in resp.json().get("session", []) or []:
            try:
                s = datetime.fromtimestamp(
                    int(session["startTimeMillis"]) / 1000, tz=_tz.utc
                )
                e = datetime.fromtimestamp(
                    int(session["endTimeMillis"]) / 1000, tz=_tz.utc
                )
                out.append(
                    {
                        "sleep_start": s,
                        "sleep_end": e,
                        "efficiency_score": None,
                    }
                )
            except (KeyError, ValueError):
                continue
        return out

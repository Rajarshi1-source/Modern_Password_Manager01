import os
import hashlib
import logging
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Dict, Optional, Tuple
from urllib.parse import quote

import requests

from shared.circuit_breaker import hibp_breaker, CircuitBreakerOpen

logger = logging.getLogger(__name__)

# HIBP API endpoints
HIBP_API_URL = "https://haveibeenpwned.com/api/v3"
HIBP_PASSWORD_API_URL = "https://api.pwnedpasswords.com/range"
HIBP_EMAIL_API_URL = f"{HIBP_API_URL}/breachedaccount"
# SHA-1 is REQUIRED by the HIBP API protocol — do NOT change this.
# HIBP's database contains SHA-1 hashes. Substituting SHA-3 or SHA-512
# would cause all passwords to return "not breached" (silent false negatives).
# SHA-1's weaknesses (collision attacks) are irrelevant here — this hash
# is used only as a k-anonymity lookup key, never for authentication or storage.
# Snapshot at import; email breach checks use os.environ at request time (see get_breached_sites_for_email).
HIBP_API_KEY = os.environ.get("HIBP_API_KEY", "")

_PWNED_HEADERS = {
    "User-Agent": "SecureVault-PasswordManager/1.0 (k-anonymity check)",
    "Add-Padding": "true",
}

_HIBP_REQUEST_TIMEOUT = 10
_HIBP_429_MAX_RETRIES = 3

# Returned by check_password_prefix on timeout/HTTP error — not a mapping; do not treat as {}.
_BREACH_UNKNOWN = object()


def _retry_after_seconds(header: str | None, default: int = 2) -> int:
    """Parse Retry-After as seconds or HTTP-date (RFC 7231)."""
    if not header or not str(header).strip():
        return default
    header = str(header).strip()
    try:
        secs = int(header)
        return max(secs, 0) or default
    except ValueError:
        pass
    try:
        when = parsedate_to_datetime(header)
        if when is None:
            return default
        if when.tzinfo is None:
            when = when.replace(tzinfo=timezone.utc)
        delay = (when - datetime.now(when.tzinfo)).total_seconds()
        return max(int(delay), 0) or default
    except (TypeError, ValueError, OverflowError):
        return default


def _sha1_hex(password: str) -> str:
    """
    SHA-1 hash a password for HIBP lookup.

    SHA-1 is mandated by the HIBP k-anonymity API — this is intentional.
    Do NOT replace with SHA-3 or SHA-512.
    """
    return (
        hashlib.sha1(password.encode("utf-8"), usedforsecurity=False)
        .hexdigest()
        .upper()
    )


def hash_password(password: str) -> str:
    """Backward-compatible name for _sha1_hex (HIBP k-anonymity protocol)."""
    return _sha1_hex(password)


def check_password_prefix(prefix: str) -> Dict[str, int] | object:
    """
    Query HIBP range API with a 5-char SHA-1 prefix (k-anonymity model).
    The full password hash is never sent over the network.

    Args:
        prefix: First 5 hex characters of the SHA-1 hash.

    Returns:
        Dict mapping uppercase hash suffixes to breach counts (may be empty if API
        returns no lines for this prefix). On timeout or request failure, returns
        ``_BREACH_UNKNOWN`` — callers must not treat that like an empty dict.
    """
    if not prefix or len(prefix) != 5 or not all(
        c in "0123456789ABCDEFabcdef" for c in prefix
    ):
        raise ValueError(f"Prefix must be exactly 5 hex characters, got: {prefix!r}")

    try:
        hibp_breaker.before_call()

        response = requests.get(
            f"{HIBP_PASSWORD_API_URL}/{prefix.upper()}",
            headers=_PWNED_HEADERS,
            timeout=_HIBP_REQUEST_TIMEOUT,
        )
        response.raise_for_status()

        result = {}
        for line in response.text.splitlines():
            if ":" not in line:
                continue
            suffix, _, count_str = line.partition(":")
            try:
                result[suffix.strip().upper()] = int(count_str.strip())
            except ValueError:
                logger.warning("Unexpected HIBP line format: %r", line)

        hibp_breaker.on_success()
        return result

    except CircuitBreakerOpen:
        logger.warning("HIBP circuit breaker is OPEN — skipping breach check")
        return _BREACH_UNKNOWN
    except requests.exceptions.Timeout:
        hibp_breaker.on_failure()
        logger.error("HIBP API timed out for prefix %s***", prefix[:2])
        return _BREACH_UNKNOWN
    except requests.exceptions.RequestException as e:
        hibp_breaker.on_failure(e)
        logger.error("HIBP request failed: %s", e)
        return _BREACH_UNKNOWN


def is_password_breached(password_or_hash: str) -> Tuple[Optional[bool], int]:
    """
    Check if a password appears in known data breaches (k-anonymity).

    Accepts either a 40-character SHA-1 hex hash (as sent by the client API)
    or a plaintext password (hashed locally before any network call).

    Args:
        password_or_hash: SHA-1 hex hash or plaintext password.

    Returns:
        (is_breached, breach_count). ``is_breached`` is None if the check could not
        be completed (service unavailable); count is 0 in that case. Otherwise
        count is 0 if not breached.
    """
    if not password_or_hash:
        raise ValueError("Password or hash must not be empty")

    if len(password_or_hash) == 40 and all(
        c in "0123456789abcdefABCDEF" for c in password_or_hash
    ):
        full_hash = password_or_hash.upper()
    else:
        full_hash = _sha1_hex(password_or_hash)

    prefix = full_hash[:5]
    suffix = full_hash[5:]

    breach_data = check_password_prefix(prefix)
    if breach_data is _BREACH_UNKNOWN:
        return None, 0
    count = breach_data.get(suffix, 0)
    return count > 0, count


def get_breached_sites_for_email(
    email: str, include_unverified: bool = False
) -> list:
    """
    Check if an email address appears in any known data breaches.

    Requires a valid HIBP_API_KEY environment variable (v3 API mandate).

    Args:
        email: Email address to check.
        include_unverified: Whether to include unverified breaches.

    Returns:
        List of breach objects, or empty list if none found, skipped, or on error.
    """
    if not email or "@" not in email:
        raise ValueError("Invalid email address")

    # Read at call time so keys loaded after import (e.g. Django / dotenv) still work.
    api_key = os.environ.get("HIBP_API_KEY", "")
    if not api_key:
        logger.error(
            "HIBP_API_KEY is not set. Email breach checks require a paid API key "
            "(https://haveibeenpwned.com/API/Key). Skipping check."
        )
        return []

    account = email.strip()
    # HIBP: account in path must be URL-encoded.
    breached_url = f"{HIBP_EMAIL_API_URL}/{quote(account, safe='')}"
    headers = {
        "User-Agent": "SecureVault-PasswordManager/1.0",
        "hibp-api-key": api_key,
    }
    params = {
        "truncateResponse": "false",
        "includeUnverified": "true" if include_unverified else "false",
    }

    for attempt in range(_HIBP_429_MAX_RETRIES + 1):
        try:
            response = requests.get(
                breached_url,
                headers=headers,
                params=params,
                timeout=_HIBP_REQUEST_TIMEOUT,
            )

            if response.status_code == 404:
                return []

            if response.status_code == 429:
                if attempt >= _HIBP_429_MAX_RETRIES:
                    logger.error(
                        "HIBP rate limited after %d retries for email check",
                        _HIBP_429_MAX_RETRIES,
                    )
                    return []
                retry_after = _retry_after_seconds(
                    response.headers.get("Retry-After"), default=2
                )
                logger.warning("HIBP rate limited. Retry after %ds.", retry_after)
                time.sleep(retry_after)
                continue

            if response.status_code == 401:
                logger.error("HIBP API key is invalid or expired.")
                return []

            response.raise_for_status()
            try:
                return response.json()
            except ValueError as e:
                logger.error("HIBP returned invalid JSON: %s", e)
                return []

        except requests.exceptions.Timeout:
            logger.error(
                "HIBP email check timed out for domain %s",
                email.split("@", 1)[-1],
            )
            return []
        except requests.exceptions.RequestException as e:
            logger.error("HIBP email request failed: %s", e)
            return []

    return []

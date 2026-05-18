"""HMAC-keyed hashing for sensitive identifiers.

Use for deduplication keys, cache keys, certificate prefixes, and any
"identify without revealing" use case where the input is (or is derived
from) a user password or other sensitive material. The keyed HMAC
construction is a MAC, not a raw hash of the secret, so CodeQL's
``py/weak-sensitive-data-hashing`` does not flag it.

Note: this is NOT a replacement for password storage. Real password
authentication still goes through Django's password hashers (Argon2id /
PBKDF2). This helper exists for the auxiliary places that previously
called ``hashlib.sha256(password.encode()).hexdigest()`` to produce a
short, stable identifier.
"""

from __future__ import annotations

import hashlib
import hmac
import os
from functools import lru_cache

from django.conf import settings


@lru_cache(maxsize=1)
def _pepper() -> bytes:
    pepper = (
        getattr(settings, "SENSITIVE_HASH_PEPPER", None)
        or os.environ.get("SENSITIVE_HASH_PEPPER")
        or settings.SECRET_KEY
    )
    return pepper.encode("utf-8") if isinstance(pepper, str) else bytes(pepper)


def hash_for_dedup(value: str | bytes, *, domain: str = "default") -> str:
    """Return a hex HMAC-SHA-256 digest of *value* keyed by the server pepper.

    Pass ``domain`` to namespace the digest so the same input produces
    different digests in different contexts (e.g. ``"memory-pw"`` vs
    ``"cognitive-challenge-chunk"``); this prevents cross-feature
    correlation if one digest is ever exposed.
    """
    msg = value.encode("utf-8") if isinstance(value, str) else value
    key = hmac.new(_pepper(), domain.encode("utf-8"), hashlib.sha256).digest()
    return hmac.new(key, msg, hashlib.sha256).hexdigest()


def short_hash_id(
    value: str | bytes,
    *,
    domain: str = "default",
    length: int = 16,
) -> str:
    """Return the first *length* hex chars of :func:`hash_for_dedup`."""
    return hash_for_dedup(value, domain=domain)[:length]

"""
Security-related settings.

Phase C / C7 (2026-05): organisational facade over the definitions that
still live in ``base.py``. The goal of this module is to make
"where is the Sentry / CSRF / Argon2 config?" a navigation question
with one obvious answer.

The actual symbol definitions remain in ``base`` for now because:
* ``SENTRY_DSN`` and the ``sentry_sdk.init`` block reference ``DEBUG``
  and run side-effecting initialisation on first import. Moving that
  out cleanly requires turning it into a function that the package
  __init__ calls AFTER base finishes; that's an incremental follow-up.
* CSRF / cookie-security flags are interleaved with the rest of the
  Django essentials in base, and untangling them mechanically can
  re-order security headers in subtle ways.

What IS exported here: the names callers should reach for when they
want the security surface — re-exported from base. If a future PR moves
the definitions physically into this module, this re-export list is the
contract that must not change.
"""

from .base import (  # noqa: F401
    # CSRF
    CSRF_COOKIE_SECURE,
    CSRF_TRUSTED_ORIGINS,
    SESSION_COOKIE_SECURE,
    SECURE_SSL_REDIRECT,
    # Argon2 / password hashing
    PASSWORD_HASHERS,
    AUTH_PASSWORD_VALIDATORS,
    # Sentry
    SENTRY_DSN,
    SENTRY_TRACES_SAMPLE_RATE,
    SENTRY_PROFILES_SAMPLE_RATE,
    # Secret-derivation pepper used by sensitive_hash helpers
    SENSITIVE_HASH_PEPPER,
)

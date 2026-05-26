"""
Sentry payload scrubbing — secret redaction primitives.

Phase E / E1 (2026-05): extracted from the inline definitions in
``settings/base.py`` so the scrubber can be unit-tested without
standing up a live ``sentry_sdk.init``. The settings module imports
these helpers and passes ``before_send`` into ``sentry_sdk.init``;
behaviour is byte-identical to the previous inline implementation,
plus the breadcrumbs branch added in this same phase.

Why this exists in its own module:
  * The inline scrubber lived inside ``if SENTRY_DSN:`` which made it
    unreachable from a test that did not set ``SENTRY_DSN`` first.
  * Setting ``SENTRY_DSN`` in tests triggered ``sentry_sdk.init`` and
    its network connect, which is the wrong thing for a unit test.
  * Extracting keeps the scrubber pure (no side effects, no Sentry
    SDK import) so a test can call ``scrub_event({...})`` directly.

What gets scrubbed:
  * Top-level ``event['extra' | 'contexts' | 'tags' | 'request']``
    dicts — keys matching ``SENSITIVE_KEY_PATTERNS`` are replaced
    with ``<redacted>``; 40+ hex-char ``0x...`` blobs are replaced
    with ``0x<redacted>``.
  * ``event['exception']['values'][*]['stacktrace']['frames'][*]['vars']``
    — Python frame locals captured by Sentry on exception.
  * ``event['logentry']['message' | 'formatted']`` and ``params`` —
    log lines that reach Sentry via ``LoggingIntegration``.
  * ``event['message']`` — top-level free-text.
  * ``event['breadcrumbs']['values'][*]`` — pre-error trail (added
    Phase E / E1; previously skipped, which let ``logger.info`` lines
    bypass scrubbing entirely if they fired before the failing call).

The matcher is intentionally substring-case-insensitive on the key
name (e.g. ``my_api_key`` matches ``API_KEY``). The cost is occasional
over-redaction of benign field names; the gain is catching every
variant of ``*_token``, ``*_secret``, ``*_password`` without an
explicit list.
"""

from __future__ import annotations

import re


# Env-var names known to hold secrets. Match is exact uppercase.
SENSITIVE_ENV_NAMES = (
    'BLOCKCHAIN_PRIVATE_KEY',
    'JWT_SECRET_KEY', 'JWT_PRIVATE_KEY',
    'SECRET_KEY',
    'DATABASE_PASSWORD', 'DB_PASSWORD', 'DB_REPLICA_PASSWORD',
    'POSTGRES_PASSWORD',
    'REDIS_PASSWORD',
    'EMAIL_HOST_PASSWORD', 'TWILIO_AUTH_TOKEN',
    'DNA_TOKEN_ENCRYPTION_KEY', 'DNA_TOKEN_LEGACY_KEY',
)


# Substring patterns matched case-insensitively against any dict key.
# Phase E / E1: added ``TOKEN`` + ``VERIFICATION`` for catch-all
# coverage of verification_token / id_token / session_token / etc.
SENSITIVE_KEY_PATTERNS = (
    'PASSWORD', 'SECRET', 'PRIVATE_KEY', 'SIGNING_KEY',
    'CERTIFICATE_KEY', 'API_KEY', 'AUTH_TOKEN',
    'ACCESS_TOKEN', 'REFRESH_TOKEN', 'CREDENTIALS',
    'TOKEN', 'VERIFICATION',
)


# Match anything that looks like an Ethereum address (40 hex) or a
# private key / hash (64 hex). 40-char lower bound avoids false hits
# on ordinary 32-bit hex IDs.
_HEX_BLOB = re.compile(r'0x[0-9a-fA-F]{40,}')


def is_sensitive_key(key_str) -> bool:
    """Return True if the key looks like it holds a secret value."""
    if not isinstance(key_str, str):
        return False
    upper = key_str.upper()
    if upper in SENSITIVE_ENV_NAMES:
        return True
    return any(pat in upper for pat in SENSITIVE_KEY_PATTERNS)


def scrub_str(s):
    """Redact 0x-prefixed hex blobs from a string. Passthrough otherwise."""
    if not isinstance(s, str):
        return s
    return _HEX_BLOB.sub('0x<redacted>', s)


def scrub_mapping(mapping):
    """Deep-redact a mapping. Sensitive keys → ``<redacted>``; values
    recursed into dicts/lists; strings have hex blobs scrubbed."""
    if not isinstance(mapping, dict):
        return mapping
    out = {}
    for k, v in mapping.items():
        if is_sensitive_key(k):
            out[k] = '<redacted>'
        elif isinstance(v, dict):
            out[k] = scrub_mapping(v)
        elif isinstance(v, list):
            out[k] = [
                scrub_mapping(x) if isinstance(x, dict) else scrub_str(x)
                for x in v
            ]
        else:
            out[k] = scrub_str(v)
    return out


def scrub_event(event):
    """``before_send`` body — mutates and returns ``event`` in place.

    NEVER raises; any internal exception causes the (partially-
    scrubbed) event to be returned as-is, because losing telemetry
    is preferable to losing the application.
    """
    try:
        for bag in ('extra', 'contexts', 'tags', 'request'):
            if bag in event:
                event[bag] = scrub_mapping(event[bag])

        # Stack-frame locals may capture the private key on init.
        for ex in event.get('exception', {}).get('values', []) or []:
            stacktrace = ex.get('stacktrace') or {}
            for frame in stacktrace.get('frames', []) or []:
                if 'vars' in frame:
                    frame['vars'] = scrub_mapping(frame['vars'])

        # Logger-rendered records (sentry_sdk.integrations.logging).
        logentry = event.get('logentry')
        if isinstance(logentry, dict):
            for key in ('message', 'formatted'):
                val = logentry.get(key)
                if isinstance(val, str):
                    logentry[key] = scrub_str(val)
            params = logentry.get('params')
            if isinstance(params, dict):
                logentry['params'] = scrub_mapping(params)
            elif isinstance(params, (list, tuple)):
                logentry['params'] = [
                    scrub_mapping(p) if isinstance(p, dict) else scrub_str(p)
                    for p in params
                ]
            event['logentry'] = logentry

        if isinstance(event.get('message'), str):
            event['message'] = scrub_str(event['message'])

        # Phase E / E1: breadcrumbs.
        breadcrumbs = event.get('breadcrumbs') or {}
        if isinstance(breadcrumbs, dict):
            for crumb in breadcrumbs.get('values') or []:
                if not isinstance(crumb, dict):
                    continue
                if isinstance(crumb.get('message'), str):
                    crumb['message'] = scrub_str(crumb['message'])
                if isinstance(crumb.get('data'), dict):
                    crumb['data'] = scrub_mapping(crumb['data'])
    except Exception:
        return event
    return event

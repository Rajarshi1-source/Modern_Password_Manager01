"""
Short-lived, single-use WebSocket authentication tickets.

The browser authenticates a normal REST request with its long-lived auth token
(sent in the ``Authorization`` header — never a URL), exchanges it for a ticket,
and then opens the WebSocket with ``?ticket=<ticket>``. This keeps the long-lived
token out of ``ws://`` URLs, and therefore out of server access logs and browser
history. Tickets expire quickly and are consumed on first use by the WS auth
middleware.

Tickets live in Django's *default* cache. In production that is Redis
(``USE_REDIS_CACHE=True``), which is shared across the HTTP (gunicorn) and
WebSocket (daphne) processes — required so a ticket minted by the REST endpoint
can be consumed by the ASGI middleware. With locmem (dev/tests, single process)
it also works.
"""

import secrets

from django.core.cache import cache

_CACHE_PREFIX = 'ws_ticket:'
# Just long enough for the browser to open the socket after fetching a ticket;
# short enough that a leaked ticket is near-useless.
TTL_SECONDS = 30


def issue_ticket(user_id):
    """Mint a single-use ticket bound to ``user_id``; return the opaque ticket."""
    ticket = secrets.token_urlsafe(32)
    cache.set(f'{_CACHE_PREFIX}{ticket}', user_id, TTL_SECONDS)
    return ticket


def consume_ticket(ticket):
    """Return the bound ``user_id`` and invalidate the ticket (single-use).

    Returns ``None`` if the ticket is missing, malformed, already used, or
    expired — so the caller can fall back to denying the connection.
    """
    if not ticket:
        return None
    key = f'{_CACHE_PREFIX}{ticket}'
    user_id = cache.get(key)
    if user_id is None:
        return None
    # Single-use via an atomic claim: cache.delete() (Redis DEL) is atomic and
    # returns truthy only for the caller that actually removed the key, so two
    # concurrent handshakes replaying one ticket cannot both authenticate.
    if not cache.delete(key):
        return None
    return user_id

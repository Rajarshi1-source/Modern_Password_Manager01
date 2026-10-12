"""
The one place that decides a request's client IP.

``X-Forwarded-For`` is a list each proxy appends to, so its LEFTMOST entry is
whatever the client sent and proves nothing. Only the entries added by
proxies we run can be trusted, and those are at the right-hand end. With
``TRUSTED_PROXY_COUNT = N`` the client is the N-th entry from the right; with
0 (the default) the header is ignored and ``REMOTE_ADDR`` is used.

This mirrors DRF's ``get_ident`` with ``NUM_PROXIES`` (settings set both from
the same value), so DRF throttle buckets and every other IP check agree.
Finding F14 in docs/pqc-hybrid-architecture-review.md.
"""

from typing import Optional

from django.conf import settings


def trusted_proxy_count() -> int:
    return max(int(getattr(settings, 'TRUSTED_PROXY_COUNT', 0) or 0), 0)


def get_client_ip(request, default: Optional[str] = None) -> Optional[str]:
    """Return the client IP for ``request``, or ``default`` if there is none."""
    remote_addr = request.META.get('REMOTE_ADDR') or None
    count = trusted_proxy_count()
    xff = request.META.get('HTTP_X_FORWARDED_FOR')
    if count and xff:
        addrs = xff.split(',')
        client = addrs[-min(count, len(addrs))].strip()
        if client:
            return client
    return remote_addr or default

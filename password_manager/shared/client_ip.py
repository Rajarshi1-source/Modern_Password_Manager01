"""
The one place that decides a request's client IP.

``X-Forwarded-For`` is a list each proxy appends to, so its LEFTMOST entry is
whatever the client sent and proves nothing. Only the entries added by
proxies we run can be trusted, and those are at the right-hand end. With
``TRUSTED_PROXY_COUNT = N`` the client is the N-th entry from the right; with
0 (the default) the header is ignored and ``REMOTE_ADDR`` is used.

``TRUSTED_PROXY_CIDRS`` (optional) additionally requires the direct peer
(``REMOTE_ADDR``) to be one of our proxies before the header is read at all,
so a caller that reaches Django without going through them cannot choose its
address. Empty means "any peer", which is only safe when the network allows
nothing but the proxies to connect (k8s/network-policy.yaml allow-backend).

This mirrors DRF's ``get_ident`` with ``NUM_PROXIES`` (settings set both from
the same value), so DRF throttle buckets and every other IP check agree.
Finding F14 in docs/pqc-hybrid-architecture-review.md.
"""

import ipaddress
from typing import Optional

from asgiref.sync import iscoroutinefunction, markcoroutinefunction
from django.conf import settings


def trusted_proxy_count() -> int:
    """Number of our proxies that append to X-Forwarded-For (0 = ignore it)."""
    return max(int(getattr(settings, 'TRUSTED_PROXY_COUNT', 0) or 0), 0)


def _peer_is_trusted_proxy(remote_addr: Optional[str]) -> bool:
    cidrs = getattr(settings, 'TRUSTED_PROXY_CIDRS', ()) or ()
    if not cidrs:
        return True
    try:
        peer = ipaddress.ip_address(remote_addr or '')
    except ValueError:
        return False
    return any(peer in ipaddress.ip_network(c, strict=False) for c in cidrs)


def get_client_ip(request, default: Optional[str] = None) -> Optional[str]:
    """Return the client IP for ``request``, or ``default`` if there is none."""
    remote_addr = request.META.get('REMOTE_ADDR') or None
    count = trusted_proxy_count()
    xff = request.META.get('HTTP_X_FORWARDED_FOR')
    if count and xff and _peer_is_trusted_proxy(remote_addr):
        addrs = xff.split(',')
        client = addrs[-min(count, len(addrs))].strip()
        # A misconfigured or bypassed proxy can leave junk here; callers store
        # it in GenericIPAddressFields and parse it with ipaddress.
        try:
            return str(ipaddress.ip_address(client))
        except ValueError:
            pass
    return remote_addr or default


class ForwardedForPeerMiddleware:
    """Drop X-Forwarded-For unless the direct peer is in TRUSTED_PROXY_CIDRS.

    Runs first, so DRF's throttles (which read the header via NUM_PROXIES)
    and get_client_ip() see the same thing. A no-op when the setting is empty.
    """

    async_capable = True
    sync_capable = True

    def __init__(self, get_response):
        self.get_response = get_response
        if iscoroutinefunction(get_response):
            markcoroutinefunction(self)

    @staticmethod
    def _strip(request):
        if 'HTTP_X_FORWARDED_FOR' in request.META and not _peer_is_trusted_proxy(
            request.META.get('REMOTE_ADDR')
        ):
            del request.META['HTTP_X_FORWARDED_FOR']

    def __call__(self, request):
        self._strip(request)
        if iscoroutinefunction(self):
            return self.__acall__(request)
        return self.get_response(request)

    async def __acall__(self, request):
        return await self.get_response(request)

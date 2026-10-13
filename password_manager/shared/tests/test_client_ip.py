"""
F14 (docs/pqc-hybrid-architecture-review.md): the client IP must not come from
the client-controlled leftmost X-Forwarded-For entry.

Every test sends a spoofed leftmost hop. A proxy we run appends the real
client, so with TRUSTED_PROXY_COUNT=1 the real client is the rightmost entry.
"""

from django.http import HttpResponse
from django.test import RequestFactory, SimpleTestCase, override_settings
from rest_framework.settings import api_settings
from rest_framework.throttling import SimpleRateThrottle

from auth_module.recovery_throttling import ProgressiveLockoutThrottle
from middleware import SecurityMiddleware
from shared.client_ip import ForwardedForPeerMiddleware, get_client_ip

PROXY = '10.0.0.5'          # REMOTE_ADDR: the proxy's own address
REAL_CLIENT = '198.51.100.7'
ALLOWLISTED = '203.0.113.10'


def request_via_proxy(spoofed_hop, real_client=REAL_CLIENT):
    return RequestFactory().get(
        '/', REMOTE_ADDR=PROXY,
        HTTP_X_FORWARDED_FOR=f'{spoofed_hop}, {real_client}',
    )


class GetClientIpTests(SimpleTestCase):
    @override_settings(TRUSTED_PROXY_COUNT=1)
    def test_one_proxy_takes_the_rightmost_entry(self):
        self.assertEqual(get_client_ip(request_via_proxy('1.2.3.4')), REAL_CLIENT)

    @override_settings(TRUSTED_PROXY_COUNT=2)
    def test_two_proxies_take_the_second_from_the_right(self):
        request = RequestFactory().get(
            '/', REMOTE_ADDR=PROXY, HTTP_X_FORWARDED_FOR=f'1.2.3.4, {REAL_CLIENT}, 10.0.0.9',
        )
        self.assertEqual(get_client_ip(request), REAL_CLIENT)

    @override_settings(TRUSTED_PROXY_COUNT=1)
    def test_non_ip_entry_falls_back_to_remote_addr(self):
        request = RequestFactory().get('/', REMOTE_ADDR=PROXY, HTTP_X_FORWARDED_FOR='1.2.3.4, not-an-ip')
        self.assertEqual(get_client_ip(request), PROXY)

    @override_settings(TRUSTED_PROXY_COUNT=0)
    def test_no_trusted_proxy_ignores_the_header(self):
        self.assertEqual(get_client_ip(request_via_proxy('1.2.3.4')), PROXY)

    @override_settings(TRUSTED_PROXY_COUNT=1)
    def test_missing_header_falls_back_to_remote_addr(self):
        self.assertEqual(get_client_ip(RequestFactory().get('/', REMOTE_ADDR=PROXY)), PROXY)

    @override_settings(TRUSTED_PROXY_COUNT=1)
    def test_default_when_nothing_is_known(self):
        request = RequestFactory().get('/')
        request.META.pop('REMOTE_ADDR', None)
        self.assertEqual(get_client_ip(request, default='unknown'), 'unknown')


@override_settings(TRUSTED_PROXY_COUNT=1)
class RecoveryLockoutKeyTests(SimpleTestCase):
    def test_spoofed_leftmost_hop_does_not_change_the_lockout_bucket(self):
        throttle = ProgressiveLockoutThrottle()
        keys = {
            throttle.get_cache_key(request_via_proxy(spoof))
            for spoof in ('1.1.1.1', '2.2.2.2', '9.9.9.9')
        }
        self.assertEqual(len(keys), 1)

    def test_different_real_clients_get_different_buckets(self):
        throttle = ProgressiveLockoutThrottle()
        self.assertNotEqual(
            throttle.get_cache_key(request_via_proxy('1.1.1.1', '198.51.100.1')),
            throttle.get_cache_key(request_via_proxy('1.1.1.1', '198.51.100.2')),
        )


@override_settings(
    TRUSTED_PROXY_COUNT=1,
    IP_WHITELISTING_ENABLED=True,
    ALLOWED_IP_RANGES={ALLOWLISTED},
)
class IpAllowlistTests(SimpleTestCase):
    def _status(self, request):
        middleware = SecurityMiddleware(lambda r: HttpResponse('ok'))
        return middleware(request).status_code

    def test_spoofed_allowlisted_leftmost_hop_is_refused(self):
        self.assertEqual(self._status(request_via_proxy(ALLOWLISTED)), 403)

    def test_allowlisted_real_client_is_admitted(self):
        self.assertEqual(self._status(request_via_proxy('1.2.3.4', ALLOWLISTED)), 200)


class DrfNumProxiesTests(SimpleTestCase):
    def test_settings_set_num_proxies_from_trusted_proxy_count(self):
        from django.conf import settings
        self.assertEqual(api_settings.NUM_PROXIES, settings.TRUSTED_PROXY_COUNT)

    def test_drf_and_helper_agree(self):
        request = request_via_proxy('1.2.3.4')
        with override_settings(TRUSTED_PROXY_COUNT=1, REST_FRAMEWORK={'NUM_PROXIES': 1}):
            self.assertEqual(SimpleRateThrottle.get_ident(None, request), get_client_ip(request))


@override_settings(TRUSTED_PROXY_COUNT=1, TRUSTED_PROXY_CIDRS=['10.0.0.0/24'])
class TrustedProxyCidrTests(SimpleTestCase):
    """With TRUSTED_PROXY_CIDRS set, only our proxies may supply the header."""

    def direct_request(self, peer='203.0.113.99'):
        return RequestFactory().get('/', REMOTE_ADDR=peer, HTTP_X_FORWARDED_FOR=ALLOWLISTED)

    def test_header_from_a_proxy_in_range_is_used(self):
        self.assertEqual(get_client_ip(request_via_proxy('1.2.3.4')), REAL_CLIENT)

    def test_header_from_any_other_peer_is_ignored(self):
        self.assertEqual(get_client_ip(self.direct_request()), '203.0.113.99')

    def test_middleware_strips_it_so_drf_agrees(self):
        request = self.direct_request()
        seen = {}
        ForwardedForPeerMiddleware(lambda r: seen.setdefault('meta', dict(r.META)))(request)
        self.assertNotIn('HTTP_X_FORWARDED_FOR', seen['meta'])
        with override_settings(REST_FRAMEWORK={'NUM_PROXIES': 1}):
            self.assertEqual(SimpleRateThrottle.get_ident(None, request), '203.0.113.99')

    def test_middleware_keeps_it_from_a_trusted_proxy(self):
        request = request_via_proxy('1.2.3.4')
        ForwardedForPeerMiddleware(lambda r: None)(request)
        self.assertIn('HTTP_X_FORWARDED_FOR', request.META)

    def test_spoofed_allowlisted_address_is_refused_from_a_direct_peer(self):
        with override_settings(IP_WHITELISTING_ENABLED=True, ALLOWED_IP_RANGES={ALLOWLISTED}):
            middleware = SecurityMiddleware(lambda r: HttpResponse('ok'))
            self.assertEqual(middleware(self.direct_request()).status_code, 403)

"""
Audit Group D (2026-05): AccountProtectionService hardening.

Covers:
  * #12 — device id is HMAC-keyed with SENSITIVE_HASH_PEPPER (not a bare
    SHA-256 of spoofable headers).
  * #13 — is_ip_blacklisted supports CIDR ranges, not just exact strings.
"""

import hashlib
import hmac
from unittest import mock

from django.test import TestCase, override_settings

from security.services.account_protection import AccountProtectionService
from security.services.security_service import SecurityService


class _FakeRequest:
    def __init__(self, user_agent=''):
        self.META = {'HTTP_USER_AGENT': user_agent}


class DeviceIdHmacTests(TestCase):
    """#12: device id must be keyed with SENSITIVE_HASH_PEPPER."""

    def setUp(self):
        self.service = AccountProtectionService()
        self.device_info = {
            'ip_address': '203.0.113.7',
            'browser': 'Firefox',
            'os': 'Linux',
        }
        self.request = _FakeRequest('Mozilla/5.0 ...')

    @override_settings(SENSITIVE_HASH_PEPPER='unit-test-pepper')
    def test_device_id_is_hmac_not_bare_sha256(self):
        device_string = "Mozilla/5.0 ..._203.0.113.7_Firefox_Linux"
        bare = hashlib.sha256(device_string.encode()).hexdigest()[:32]
        keyed = hmac.new(
            b'unit-test-pepper', device_string.encode(), hashlib.sha256
        ).hexdigest()[:32]

        result = self.service.generate_device_id(self.device_info, self.request)
        self.assertEqual(result, keyed)
        self.assertNotEqual(result, bare)

    @override_settings(SENSITIVE_HASH_PEPPER='pepper-A')
    def test_device_id_depends_on_pepper(self):
        with_a = self.service.generate_device_id(self.device_info, self.request)
        with override_settings(SENSITIVE_HASH_PEPPER='pepper-B'):
            with_b = self.service.generate_device_id(self.device_info, self.request)
        # Different server pepper => different id for identical headers,
        # so the id can't be reproduced off-server.
        self.assertNotEqual(with_a, with_b)


class BlacklistCidrTests(TestCase):
    """#13: is_ip_blacklisted must honor CIDR ranges."""

    def setUp(self):
        self.service = AccountProtectionService()

    @override_settings(BLACKLISTED_IP_NETS=[])
    def test_empty_blacklist_allows_everything(self):
        self.assertFalse(self.service.is_ip_blacklisted('10.1.2.3'))

    def test_cidr_range_matches_member_ip(self):
        import ipaddress
        nets = [ipaddress.ip_network('10.0.0.0/8')]
        with override_settings(BLACKLISTED_IP_NETS=nets):
            self.assertTrue(self.service.is_ip_blacklisted('10.5.6.7'))
            self.assertFalse(self.service.is_ip_blacklisted('11.0.0.1'))

    def test_single_ip_still_matches_exactly(self):
        import ipaddress
        nets = [ipaddress.ip_network('192.168.1.5')]  # parses as /32
        with override_settings(BLACKLISTED_IP_NETS=nets):
            self.assertTrue(self.service.is_ip_blacklisted('192.168.1.5'))
            self.assertFalse(self.service.is_ip_blacklisted('192.168.1.6'))

    def test_ipv6_cidr_range_matches_member_ip(self):
        import ipaddress
        nets = [ipaddress.ip_network('2001:db8::/32')]
        with override_settings(BLACKLISTED_IP_NETS=nets):
            self.assertTrue(self.service.is_ip_blacklisted('2001:db8::1234'))
            self.assertFalse(self.service.is_ip_blacklisted('2001:db9::1'))

    def test_security_service_path_is_cidr_aware_too(self):
        # PR #286 review: SecurityService._is_ip_blacklisted (the
        # suspicious-login scoring path) must honor CIDR the same way, so
        # the two implementations don't drift apart again.
        import ipaddress
        sec = SecurityService()
        nets = [ipaddress.ip_network('10.0.0.0/8')]
        with override_settings(BLACKLISTED_IP_NETS=nets):
            self.assertTrue(sec._is_ip_blacklisted('10.5.6.7'))
            self.assertFalse(sec._is_ip_blacklisted('11.0.0.1'))
            self.assertFalse(sec._is_ip_blacklisted('not-an-ip'))

    def test_malformed_ip_returns_false(self):
        import ipaddress
        nets = [ipaddress.ip_network('10.0.0.0/8')]
        with override_settings(BLACKLISTED_IP_NETS=nets):
            self.assertFalse(self.service.is_ip_blacklisted('not-an-ip'))


class BlacklistedIpsParsingTests(TestCase):
    """#13 follow-up: BLACKLISTED_IPS parsing must fail closed.

    A value fat-fingered as a Python set/list literal (e.g. env line
    ``BLACKLISTED_IPS={'1.2.3.4'}``) used to split into garbage tokens that
    ip_network() rejected, silently leaving BLACKLISTED_IP_NETS empty — a
    fail-open misconfig. The parser now strips stray braces/quotes so the
    intended entries survive.
    """

    @staticmethod
    def _parse():
        from password_manager.settings.base import _parse_blacklisted_ips
        return _parse_blacklisted_ips

    def test_set_literal_value_still_parses(self):
        self.assertEqual(
            self._parse()("{'192.168.1.100', '10.0.0.5'}"),
            {'192.168.1.100', '10.0.0.5'},
        )

    def test_plain_comma_separated_list(self):
        self.assertEqual(
            self._parse()('192.168.1.100,10.0.0.5'),
            {'192.168.1.100', '10.0.0.5'},
        )

    def test_cidr_and_surrounding_whitespace(self):
        self.assertEqual(
            self._parse()(' 10.0.0.0/8 , 192.168.1.5 '),
            {'10.0.0.0/8', '192.168.1.5'},
        )

    def test_empty_value_is_empty_set(self):
        self.assertEqual(self._parse()(''), set())

    def test_embedded_newlines_are_stripped(self):
        # A multi-line .env value can leave \r/\n on tokens; strip them so the
        # entries still parse instead of being dropped at ip_network().
        self.assertEqual(
            self._parse()('192.168.1.100,\n10.0.0.5\r\n'),
            {'192.168.1.100', '10.0.0.5'},
        )

    def test_alternate_separators(self):
        # Semicolon- or newline-only separation (no commas) is tolerated so an
        # accidental .env format doesn't collapse into one unparseable token.
        self.assertEqual(
            self._parse()('192.168.1.100;10.0.0.5'),
            {'192.168.1.100', '10.0.0.5'},
        )
        self.assertEqual(
            self._parse()('192.168.1.100\n10.0.0.5'),
            {'192.168.1.100', '10.0.0.5'},
        )

    def test_parsed_set_literal_builds_usable_networks(self):
        # End-to-end: the cleaned tokens must feed ip_network() so the
        # blacklist is actually populated instead of failing open.
        import ipaddress
        tokens = self._parse()("{'192.168.1.100', '10.0.0.5'}")
        nets = [ipaddress.ip_network(t, strict=False) for t in tokens]
        self.assertEqual(len(nets), 2)
        self.assertTrue(any(ipaddress.ip_address('192.168.1.100') in n for n in nets))
        self.assertTrue(any(ipaddress.ip_address('10.0.0.5') in n for n in nets))

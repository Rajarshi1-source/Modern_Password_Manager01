"""
Dark Protocol — Tor transport and capability gating
====================================================

These tests pin the property the whole feature rests on: Dark Protocol reports
anonymity, and serves anonymous vault operations, ONLY when a live Tor daemon
says an onion service is published and the request actually arrived over it.

Everything is driven through a fake stem controller rather than a real Tor
daemon, because the thing under test is our gating logic, not Tor. The fake
answers the same three control-port queries the real one does, so a test that
passes here is a test of the code path a real daemon would take.

@author Password Manager Team
"""

from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from security.services import tor_service as tor_module
from security.services.dark_protocol_service import DarkProtocolService
from security.services.tor_service import TorService, get_tor_service

User = get_user_model()


# =============================================================================
# Test doubles
# =============================================================================

class _FakeController:
    """Stands in for stem's Controller.

    Only the four queries `TorService` actually issues are implemented. Each
    can be made to raise, because "the control port answered with an error" is
    a real state that must fail closed rather than propagate.
    """

    def __init__(
        self,
        bootstrap='NOTICE BOOTSTRAP PROGRESS=100 TAG=done SUMMARY="Done"',
        circuit_established='1',
        hidden_service_dirs=('/var/lib/tor/hidden_service',),
        onions_current='',
        circuits=(),
        raise_on=(),
        auth_error=False,
    ):
        self.bootstrap = bootstrap
        self.circuit_established = circuit_established
        self.hidden_service_dirs = list(hidden_service_dirs)
        self.onions_current = onions_current
        self.circuits = list(circuits)
        self.raise_on = set(raise_on)
        self.auth_error = auth_error
        self.closed = False
        self.authenticated = False

    def set_socket_timeout(self, timeout):
        self.timeout = timeout

    def authenticate(self, password=None):
        if self.auth_error:
            raise RuntimeError('authentication failed')
        self.authenticated = True

    def get_info(self, key):
        if key in self.raise_on:
            raise RuntimeError(f'control port error for {key}')
        if key == 'status/bootstrap-phase':
            return self.bootstrap
        if key == 'status/circuit-established':
            return self.circuit_established
        if key == 'onions/current':
            return self.onions_current
        raise KeyError(key)

    def get_conf(self, key, multiple=False):
        if key in self.raise_on:
            raise RuntimeError(f'control port error for {key}')
        if key == 'HiddenServiceDir':
            return self.hidden_service_dirs if multiple else (
                self.hidden_service_dirs[0] if self.hidden_service_dirs else ''
            )
        raise KeyError(key)

    def get_circuits(self):
        if 'circuits' in self.raise_on:
            raise RuntimeError('control port error for circuits')
        return self.circuits

    def close(self):
        self.closed = True


class _FakeCircuit:
    def __init__(self, circuit_id='1', status='BUILT', path=(), purpose='HS_CLIENT_REND'):
        self.id = circuit_id
        self.status = status
        self.path = list(path)
        self.purpose = purpose


ONION = 'a' * 56 + '.onion'
OTHER_ONION = 'b' * 56 + '.onion'

# Stands in for the Tor daemon's address. Requests that claim onion ingress
# must come from it, so the API tests below present it as REMOTE_ADDR.
TRUSTED_PEER = '10.1.2.3'

TOR_SETTINGS = {
    'ENABLED': True,
    'CONTROL_HOST': '127.0.0.1',
    'CONTROL_PORT': 9051,
    'CONTROL_PASSWORD': 'secret',
    'ONION_HOSTNAME': ONION,
    'ONION_INGRESS_PORT': 8443,
    # Required: an empty peer list fails closed, so the shared settings pin a
    # peer that the request helpers below present as REMOTE_ADDR.
    'ONION_INGRESS_TRUSTED_PEERS': TRUSTED_PEER,
    # No caching between assertions: each test drives a distinct daemon state
    # and must observe it, not a previous test's answer.
    'CAPABILITY_TTL_SECONDS': 0,
}


def _tor_settings(**overrides):
    merged = dict(TOR_SETTINGS)
    merged.update(overrides)
    return merged


class _TorTestMixin:
    """Gives each test a clean TorService with a fake controller."""

    def _service(self, controller=None, **_kwargs):
        service = TorService()
        controller = controller if controller is not None else _FakeController()
        patcher = patch.object(TorService, '_open_controller', return_value=controller)
        patcher.start()
        self.addCleanup(patcher.stop)
        # `_probe` returns early when stem is absent, before it ever calls
        # `_open_controller`, so the import flag has to be satisfied too or
        # these tests would pass for the wrong reason on a box without stem.
        stem_patcher = patch.object(tor_module, '_StemController', object())
        stem_patcher.start()
        self.addCleanup(stem_patcher.stop)
        self.controller = controller
        return service


# =============================================================================
# Capability probing
# =============================================================================

class TorCapabilityTests(_TorTestMixin, TestCase):
    """The capability answer must track the daemon, and fail closed otherwise."""

    @override_settings(TOR=_tor_settings())
    def test_fully_bootstrapped_onion_is_active(self):
        capability = self._service().get_capability()

        self.assertTrue(capability.anonymity_active)
        self.assertEqual(capability.onion_address, ONION)
        self.assertIsNone(capability.reason)
        self.assertEqual(capability.bootstrap_progress, 100)

    @override_settings(TOR={'ENABLED': False})
    def test_disabled_is_not_configured(self):
        """With Tor off, nothing is probed and nothing is claimed."""
        capability = TorService().get_capability()

        self.assertFalse(capability.anonymity_active)
        self.assertEqual(capability.reason, 'not_configured')

    @override_settings(TOR=_tor_settings())
    def test_partial_bootstrap_is_not_active(self):
        controller = _FakeController(bootstrap='NOTICE BOOTSTRAP PROGRESS=45 TAG=conn')
        capability = self._service(controller).get_capability()

        self.assertFalse(capability.anonymity_active)
        self.assertEqual(capability.reason, 'not_bootstrapped')
        self.assertEqual(capability.bootstrap_progress, 45)

    @override_settings(TOR=_tor_settings())
    def test_out_of_range_bootstrap_is_rejected_not_clamped(self):
        """An uninterpretable progress value must not become "bootstrapped".

        This used to clamp, so 101 became 100 and granted the capability —
        turning an answer we cannot interpret into the most permissive one it
        could have meant.
        """
        controller = _FakeController(bootstrap='NOTICE BOOTSTRAP PROGRESS=101 TAG=done')
        capability = self._service(controller).get_capability()

        self.assertEqual(capability.bootstrap_progress, 0)
        self.assertFalse(capability.bootstrapped)
        self.assertFalse(capability.anonymity_active)

    @override_settings(TOR=_tor_settings(CAPABILITY_TTL_SECONDS=300))
    def test_probe_invalidated_mid_flight_does_not_repopulate_the_cache(self):
        """A probe that started before reset_cache() must not publish after it.

        Probes run outside the lock so a wedged daemon cannot serialise the
        request pool; the cost is that an in-flight answer can land after an
        invalidation and silently restore state that was deliberately cleared.
        """
        service = self._service()

        # Invalidate while the probe is "in flight", from inside the probe.
        original_probe = service._probe

        def _probe_then_invalidate(config):
            result = original_probe(config)
            service.reset_cache()
            return result

        with patch.object(service, '_probe', side_effect=_probe_then_invalidate):
            capability = service.get_capability()

        # The caller still gets what the probe actually read...
        self.assertTrue(capability.anonymity_active)
        # ...but the cleared cache stays cleared.
        self.assertIsNone(service._cached)

    @override_settings(TOR=_tor_settings())
    def test_no_circuit_is_not_active(self):
        controller = _FakeController(circuit_established='0')
        capability = self._service(controller).get_capability()

        self.assertFalse(capability.anonymity_active)
        self.assertEqual(capability.reason, 'no_circuit')

    @override_settings(TOR=_tor_settings())
    def test_no_hidden_service_configured_is_not_published(self):
        """Tor can be perfectly healthy and still not be serving our onion."""
        controller = _FakeController(hidden_service_dirs=(), onions_current='')
        capability = self._service(controller).get_capability()

        self.assertFalse(capability.anonymity_active)
        self.assertEqual(capability.reason, 'onion_not_published')

    @override_settings(TOR=_tor_settings())
    def test_unreachable_controller_fails_closed(self):
        service = TorService()
        with patch.object(TorService, '_open_controller', return_value=None), \
                patch.object(tor_module, '_StemController', object()):
            capability = service.get_capability()

        self.assertFalse(capability.anonymity_active)
        self.assertEqual(capability.reason, 'controller_unreachable')

    @override_settings(TOR=_tor_settings())
    def test_control_port_errors_fail_closed_rather_than_raising(self):
        """A daemon that answers with errors must not 500 the request."""
        controller = _FakeController(raise_on={'status/bootstrap-phase'})
        capability = self._service(controller).get_capability()

        self.assertFalse(capability.anonymity_active)
        self.assertEqual(capability.bootstrap_progress, 0)
        self.assertEqual(capability.reason, 'not_bootstrapped')

    @override_settings(TOR=_tor_settings(ONION_HOSTNAME='not-a-valid-onion'))
    def test_malformed_onion_address_is_discarded(self):
        """A junk address must never be advertised as reachable.

        A truncated read of a hostname file is a realistic input, and echoing
        it to clients would send them somewhere that does not exist while the
        UI claimed anonymity was available.
        """
        capability = self._service().get_capability()

        self.assertIsNone(capability.onion_address)
        self.assertFalse(capability.anonymity_active)
        self.assertEqual(capability.reason, 'no_onion_address')

    @override_settings(TOR=_tor_settings())
    def test_stale_configured_hostname_conflicting_with_tor_is_rejected(self):
        """A configured address wins over discovery, so it must not go stale.

        If ONION_HOSTNAME is left pointing at an address Tor no longer serves,
        advertising it as active sends clients somewhere that does not answer
        while the UI reports available. When both sources exist they must agree.
        """
        controller = _FakeController(
            hidden_service_dirs=(),
            onions_current=OTHER_ONION.replace('.onion', ''),
        )
        capability = self._service(controller).get_capability()

        self.assertFalse(capability.anonymity_active)
        self.assertEqual(capability.reason, 'onion_address_mismatch')
        self.assertIsNone(capability.onion_address)

    @override_settings(TOR=_tor_settings(ONION_HOSTNAME='', CAPABILITY_TTL_SECONDS=0))
    def test_ephemeral_onion_from_control_port_is_accepted(self):
        """Onions created over the control port carry no .onion suffix."""
        controller = _FakeController(
            hidden_service_dirs=(),
            onions_current='a' * 56,
        )
        capability = self._service(controller).get_capability()

        self.assertEqual(capability.onion_address, ONION)
        self.assertTrue(capability.anonymity_active)

    @override_settings(TOR=_tor_settings(CAPABILITY_TTL_SECONDS=300))
    def test_cache_is_dropped_by_force_refresh(self):
        service = self._service()
        self.assertTrue(service.get_capability().anonymity_active)

        # The daemon goes down underneath us.
        self.controller.circuit_established = '0'
        self.assertTrue(service.get_capability().anonymity_active, 'cached answer expected')
        self.assertFalse(service.get_capability(force_refresh=True).anonymity_active)


class TorCircuitRelayTests(_TorTestMixin, TestCase):
    """Relay reporting must describe live circuits, or nothing at all."""

    @override_settings(TOR=_tor_settings())
    def test_built_circuit_relays_are_reported_with_positions(self):
        controller = _FakeController(circuits=[
            _FakeCircuit(circuit_id='7', path=[
                ('AAAAFINGERPRINT1', 'guardrelay'),
                ('BBBBFINGERPRINT2', 'middlerelay'),
                ('CCCCFINGERPRINT3', 'rendrelay'),
            ]),
        ])
        relays = self._service(controller).get_circuit_relays()

        self.assertEqual([r['position'] for r in relays], ['guard', 'middle', 'rendezvous'])
        self.assertEqual(relays[0]['nickname'], 'guardrelay')
        # Fingerprints are truncated so a screenshot cannot fingerprint the circuit.
        self.assertEqual(relays[0]['fingerprint'], 'AAAAFING')

    @override_settings(TOR=_tor_settings())
    def test_unbuilt_circuits_are_excluded(self):
        """A circuit still being extended carries no traffic, so it is not reported."""
        controller = _FakeController(circuits=[
            _FakeCircuit(circuit_id='8', status='EXTENDED', path=[('F', 'half')]),
        ])
        self.assertEqual(self._service(controller).get_circuit_relays(), [])

    @override_settings(TOR={'ENABLED': False})
    def test_relays_are_empty_when_tor_is_disabled(self):
        """The honest answer with no Tor is an empty list, never invented rows."""
        self.assertEqual(TorService().get_circuit_relays(), [])

    @override_settings(TOR=_tor_settings())
    def test_no_relay_is_ever_labelled_exit(self):
        """'No exit node' is a real property of onion circuits; keep it true."""
        controller = _FakeController(circuits=[
            _FakeCircuit(path=[('A', 'one'), ('B', 'two'), ('C', 'three'), ('D', 'four')]),
        ])
        positions = {r['position'] for r in self._service(controller).get_circuit_relays()}

        self.assertNotIn('exit', positions)
        self.assertEqual(positions, {'guard', 'middle', 'rendezvous'})


# =============================================================================
# Loopback self-check
# =============================================================================

class OnionSelfCheckTests(_TorTestMixin, TestCase):
    """The self-check is the only end-to-end proof the descriptor is published.

    /health/?verify=1 exposes it to staff, so its fail-closed reasons are
    pinned here the same way the capability answers are.
    """

    @override_settings(TOR=_tor_settings())
    def test_socks_proxies_use_socks5h_so_the_onion_resolves_inside_tor(self):
        """socks5h, not socks5: the 'h' is what makes .onion resolvable.

        With plain socks5 the local resolver would be asked for the .onion,
        fail, and leak the lookup.
        """
        proxies = self._service().socks_proxies()

        self.assertEqual(proxies['http'], 'socks5h://127.0.0.1:9050')
        self.assertEqual(proxies['https'], 'socks5h://127.0.0.1:9050')

    @override_settings(TOR={'ENABLED': False})
    def test_socks_proxies_absent_when_disabled(self):
        self.assertIsNone(TorService().socks_proxies())

    @override_settings(TOR={'ENABLED': False})
    def test_self_check_not_configured(self):
        result = TorService().check_onion_reachable()

        self.assertFalse(result.reachable)
        self.assertEqual(result.reason, 'not_configured')

    @override_settings(TOR=_tor_settings(SOCKS_PORT=0))
    def test_self_check_without_socks_configured(self):
        result = self._service().check_onion_reachable()

        self.assertFalse(result.reachable)
        self.assertEqual(result.reason, 'socks_not_configured')

    @override_settings(TOR=_tor_settings(ONION_HOSTNAME='', ONION_HOSTNAME_FILE=''))
    def test_self_check_without_an_address(self):
        controller = _FakeController(hidden_service_dirs=(), onions_current='')
        result = self._service(controller).check_onion_reachable()

        self.assertFalse(result.reachable)
        self.assertEqual(result.reason, 'no_onion_address')

    @override_settings(TOR=_tor_settings())
    def test_rendezvous_failure_is_unreachable(self):
        service = self._service()
        with patch('requests.get', side_effect=OSError('no route to host')):
            result = service.check_onion_reachable()

        self.assertFalse(result.reachable)
        self.assertEqual(result.reason, 'unreachable')

    @override_settings(TOR=_tor_settings())
    def test_any_http_status_counts_as_reachable(self):
        """A 404 still proves the rendezvous completed and our service answered.

        The check is about reachability, not about the endpoint's response.
        """
        service = self._service()
        response = MagicMock(status_code=404)
        response.__enter__ = lambda self_: self_
        response.__exit__ = lambda self_, *exc: False

        with patch('requests.get', return_value=response) as get:
            result = service.check_onion_reachable()

        self.assertTrue(result.reachable)
        self.assertEqual(result.status_code, 404)
        # The body must never be downloaded: `timeout` bounds each socket
        # operation, not the transfer, so a slow-drip response would otherwise
        # stall the probe.
        self.assertTrue(get.call_args.kwargs['stream'])

    @override_settings(TOR=_tor_settings(SELF_CHECK_TTL_SECONDS=300))
    def test_self_check_result_is_cached(self):
        service = self._service()
        response = MagicMock(status_code=200)
        response.__enter__ = lambda self_: self_
        response.__exit__ = lambda self_, *exc: False

        with patch('requests.get', return_value=response) as get:
            service.check_onion_reachable()
            service.check_onion_reachable()
            self.assertEqual(get.call_count, 1, 'second call should hit the cache')

            service.reset_cache()
            service.check_onion_reachable()
            self.assertEqual(get.call_count, 2, 'reset_cache must force a re-probe')


# =============================================================================
# Onion ingress detection
# =============================================================================

class OnionIngressTests(_TorTestMixin, TestCase):
    """Only a request that really came through the onion counts as anonymous."""

    def _request(self, port=8443, host=ONION, peer=TRUSTED_PEER):
        class _Request:
            def __init__(self, port, host, peer):
                self._port = port
                self._host = host
                self.META = {
                    'SERVER_PORT': str(port),
                    'HTTP_HOST': host,
                    'REMOTE_ADDR': peer,
                }

            def get_port(self):
                return str(self._port)

            def get_host(self):
                return self._host

        return _Request(port, host, peer)

    @override_settings(TOR=_tor_settings())
    def test_request_on_ingress_port_with_onion_host_is_anonymous(self):
        service = self._service()
        self.assertTrue(service.request_is_onion_ingress(self._request()))

    @override_settings(TOR=_tor_settings())
    def test_clearnet_port_is_not_anonymous(self):
        """The port is the load-bearing check: it is a network fact.

        A client that sets the onion Host header on a clearnet connection must
        not be able to talk its way into an anonymous verdict.
        """
        service = self._service()
        self.assertFalse(service.request_is_onion_ingress(self._request(port=8000)))

    @override_settings(TOR=_tor_settings())
    def test_wrong_host_on_ingress_port_is_not_anonymous(self):
        service = self._service()
        self.assertFalse(service.request_is_onion_ingress(self._request(host=OTHER_ONION)))

    @override_settings(TOR=_tor_settings(ONION_INGRESS_PORT=0))
    def test_without_a_configured_ingress_port_nothing_is_anonymous(self):
        """With no way to tell onion traffic apart, we must not guess."""
        service = self._service()
        self.assertFalse(service.request_is_onion_ingress(self._request()))

    @override_settings(TOR=_tor_settings())
    def test_ingress_requires_a_live_capability(self):
        """Right port, right host, dead Tor: still not anonymous."""
        controller = _FakeController(circuit_established='0')
        service = self._service(controller)
        self.assertFalse(service.request_is_onion_ingress(self._request()))

    @override_settings(TOR=_tor_settings())
    def test_trusted_peer_on_ingress_port_is_anonymous(self):
        service = self._service()
        self.assertTrue(service.request_is_onion_ingress(self._request(peer=TRUSTED_PEER)))

    @override_settings(TOR=_tor_settings(ONION_INGRESS_TRUSTED_PEERS=''))
    def test_unconfigured_trusted_peers_fails_closed(self):
        """No configured peer list means nothing has been verified.

        Treating "unset" as "trust everyone" would let a deployment that
        forgot this setting report connections as anonymous without checking
        anything — the middle state this feature must not have.
        """
        service = self._service()
        self.assertFalse(service.request_is_onion_ingress(self._request()))

    @override_settings(TOR=_tor_settings())
    def test_untrusted_peer_is_not_anonymous(self):
        """A sibling container on the same network is not the Tor daemon.

        The ingress port has no published host mapping, but docker-compose
        puts every service on one bridge network, so a compromised sibling can
        still reach it and present the onion Host. Without this check that
        request would be reported as anonymous.
        """
        service = self._service()
        self.assertFalse(service.request_is_onion_ingress(self._request(peer='10.9.9.9')))

    @override_settings(TOR=_tor_settings())
    def test_missing_peer_address_is_not_anonymous(self):
        """No REMOTE_ADDR means no evidence, which must not read as trusted."""
        service = self._service()
        request = self._request()
        del request.META['REMOTE_ADDR']
        self.assertFalse(service.request_is_onion_ingress(request))

    @override_settings(TOR=_tor_settings(ONION_INGRESS_TRUSTED_PEERS='no-such-host.invalid'))
    def test_unresolvable_trusted_peer_rejects(self):
        """A name that will not resolve is not evidence the peer is Tor."""
        service = self._service()
        self.assertFalse(service.request_is_onion_ingress(self._request()))

    @override_settings(TOR=_tor_settings())
    def test_disallowed_host_is_not_anonymous(self):
        """get_host() raises DisallowedHost for a Host outside ALLOWED_HOSTS."""
        class _BadHostRequest:
            META = {'SERVER_PORT': '8443'}

            def get_port(self):
                return '8443'

            def get_host(self):
                raise Exception('DisallowedHost')

        service = self._service()
        self.assertFalse(service.request_is_onion_ingress(_BadHostRequest()))


# =============================================================================
# API gating
# =============================================================================

class DarkProtocolCapabilityApiTests(_TorTestMixin, APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='torapi', email='torapi@example.com', password='pw-for-tests-123',
        )
        self.client.force_authenticate(user=self.user)
        get_tor_service().reset_cache()
        # DRF throttles are cache-backed and keyed per user, so counts survive
        # between tests and leak into whatever runs next. Clearing on both
        # sides keeps this class from throttling its own later cases or the
        # other dark-protocol module's.
        cache.clear()
        self.addCleanup(cache.clear)

    def _bearer(self):
        """Authorization header for the inner-dispatch tests.

        `force_authenticate` short-circuits DRF's authenticators, so it
        authenticates the OUTER request only. The internally dispatched vault
        request re-authenticates from the forwarded header, which is exactly
        what a real client sends — so these tests use a genuine token rather
        than a shortcut that would leave the real path untested.
        """
        refresh = RefreshToken.for_user(self.user)
        return f'Bearer {refresh.access_token}'

    @override_settings(TOR=_tor_settings())
    def test_capabilities_report_available_but_this_connection_is_not(self):
        """The two answers are independent, and both are reported.

        A deployment can have a perfectly live onion service while the request
        asking about it came in over clearnet. Conflating those is exactly how
        a UI ends up claiming protection a user does not have, so the endpoint
        reports deployment capability and per-connection anonymity separately.
        """
        with patch.object(TorService, '_open_controller', return_value=_FakeController()), \
                patch.object(tor_module, '_StemController', object()):
            get_tor_service().reset_cache()
            response = self.client.get(reverse('dark-protocol-capabilities'))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['anonymity']['available'])
        self.assertEqual(response.data['anonymity']['onion_address'], ONION)
        # The test client does not arrive on the onion ingress port.
        self.assertFalse(response.data['anonymity']['current_connection_is_anonymous'])
        self.assertFalse(response.data['vault_proxy']['available'])

    @override_settings(TOR={'ENABLED': False})
    def test_capabilities_report_unavailable_without_tor(self):
        response = self.client.get(reverse('dark-protocol-capabilities'))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data['anonymity']['available'])
        self.assertEqual(response.data['anonymity']['reason'], 'not_configured')
        self.assertFalse(response.data['vault_proxy']['available'])
        self.assertIsNone(response.data['anonymity']['onion_address'])

    @override_settings(TOR={'ENABLED': False})
    def test_health_reports_unavailable_without_tor(self):
        response = self.client.get(reverse('dark-protocol-health'))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data['anonymity_active'])
        self.assertEqual(response.data['status'], 'unavailable')

    @override_settings(TOR={'ENABLED': False})
    def test_self_check_is_not_run_for_non_staff(self):
        """?verify=1 blocks a worker for up to a minute; keep it to operators."""
        with patch.object(TorService, 'check_onion_reachable') as check:
            response = self.client.get(reverse('dark-protocol-health'), {'verify': '1'})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertNotIn('self_check', response.data)
        check.assert_not_called()

    @override_settings(TOR={'ENABLED': False})
    def test_self_check_runs_for_staff(self):
        self.user.is_staff = True
        self.user.save(update_fields=['is_staff'])

        response = self.client.get(reverse('dark-protocol-health'), {'verify': '1'})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('self_check', response.data)

    @override_settings(TOR={'ENABLED': False})
    def test_nodes_are_empty_without_tor(self):
        """No fabricated topology: with no circuit there are no relays."""
        response = self.client.get(reverse('dark-protocol-nodes'))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['nodes'], [])
        self.assertFalse(response.data['anonymity_active'])

    @override_settings(TOR={'ENABLED': False})
    def test_vault_proxy_refuses_when_tor_is_down(self):
        """The critical regression: this used to answer success with fake data."""
        response = self.client.post(
            reverse('dark-protocol-vault-proxy'),
            {'operation': 'vault_list', 'payload': {}},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
        self.assertEqual(response.data['error_code'], 'tor_unavailable')

    @override_settings(TOR=_tor_settings())
    def test_vault_proxy_refuses_a_clearnet_request(self):
        """Tor is healthy, but this request did not come through the onion."""
        with patch.object(TorService, '_open_controller', return_value=_FakeController()), \
                patch.object(tor_module, '_StemController', object()):
            get_tor_service().reset_cache()
            response = self.client.post(
                reverse('dark-protocol-vault-proxy'),
                {'operation': 'vault_list', 'payload': {}},
                format='json',
            )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.data['error_code'], 'clearnet_ingress_refused')
        # The refusal is actionable: it says where anonymous access lives.
        self.assertEqual(response.data['onion_address'], ONION)

    @override_settings(TOR={'ENABLED': False})
    def test_vault_proxy_rejects_a_non_dict_payload(self):
        response = self.client.post(
            reverse('dark-protocol-vault-proxy'),
            {'operation': 'vault_list', 'payload': None},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data['error_code'], 'invalid_payload')

    @override_settings(TOR=_tor_settings(), ALLOWED_HOSTS=['testserver', ONION])
    def test_onion_request_is_dispatched_to_the_real_vault(self):
        """The happy path: an onion request gets REAL vault data.

        This is the other half of the refusal tests and matters just as much.
        The old implementation returned `{'success': True, 'acknowledged':
        True}` from the garlic router without touching the vault, so a green
        result proved nothing. Here the response has to come back through the
        genuine vault view, which is why the assertion is on vault-shaped data
        rather than on a success flag.
        """
        with patch.object(TorService, '_open_controller', return_value=_FakeController()), \
                patch.object(tor_module, '_StemController', object()):
            get_tor_service().reset_cache()
            response = self.client.post(
                reverse('dark-protocol-vault-proxy'),
                {'operation': 'vault_list', 'payload': {}},
                format='json',
                # Arriving on the onion ingress port with the onion Host is
                # what the server treats as proof of anonymous ingress.
                SERVER_PORT='8443',
                HTTP_HOST=ONION,
                HTTP_AUTHORIZATION=self._bearer(),
                REMOTE_ADDR=TRUSTED_PEER,
            )

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertTrue(response.data['success'])

        # Assert on the DISPATCHED payload, not the envelope around it. An
        # earlier version of this test checked `assertNotIn('acknowledged',
        # response.data)`, which inspected the outer envelope and therefore
        # passed even when the dispatcher was mutated to return a fabricated
        # `{'acknowledged': True}` — the exact regression it existed to catch.
        # These keys come from the vault list view's own response contract and
        # cannot be produced by an invented acknowledgement.
        inner = response.data['data']
        self.assertIsInstance(inner, dict)
        self.assertIn('items', inner)
        self.assertEqual(inner.get('message'), 'Items retrieved successfully')
        self.assertNotIn('acknowledged', inner)

    @override_settings(TOR=_tor_settings(), ALLOWED_HOSTS=['testserver', ONION])
    def test_search_term_reaches_the_vault_view(self):
        """The search view reads `q` from request.GET, so it must be dispatched
        as a query parameter. Sending it as a JSON body silently produced an
        empty query and results that looked like "no matches"."""
        with patch.object(TorService, '_open_controller', return_value=_FakeController()), \
                patch.object(tor_module, '_StemController', object()):
            get_tor_service().reset_cache()
            response = self.client.post(
                reverse('dark-protocol-vault-proxy'),
                {'operation': 'vault_search', 'payload': {'q': 'example-term'}},
                format='json',
                SERVER_PORT='8443',
                HTTP_HOST=ONION,
                HTTP_AUTHORIZATION=self._bearer(),
                REMOTE_ADDR=TRUSTED_PEER,
            )

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        # The view echoes the term it actually received.
        self.assertEqual(response.data['data']['query'], 'example-term')

    @override_settings(TOR=_tor_settings(), ALLOWED_HOSTS=['testserver', ONION])
    def test_envelope_keeps_a_body_when_the_vault_answers_204(self):
        """The envelope is always 200, with the vault's status as a field.

        vault_delete dispatches to the vault's destroy(), which answers 204 No
        Content. Echoing that status would produce a 204 carrying an envelope
        body — a contradiction, and clients (including response.json() in
        darkProtocolService) read 204 as "no body" and would see nothing.
        """
        with patch.object(TorService, '_open_controller', return_value=_FakeController()), \
                patch.object(tor_module, '_StemController', object()), \
                patch.object(
                    DarkProtocolService, '_dispatch_vault_operation',
                    return_value=(204, None),
                ):
            get_tor_service().reset_cache()
            response = self.client.post(
                reverse('dark-protocol-vault-proxy'),
                {'operation': 'vault_delete', 'payload': {'id': 'abc'}},
                format='json',
                SERVER_PORT='8443',
                HTTP_HOST=ONION,
                HTTP_AUTHORIZATION=self._bearer(),
                REMOTE_ADDR=TRUSTED_PEER,
            )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['success'])
        # The vault's own status is preserved, just not as the envelope's.
        self.assertEqual(response.data['status_code'], 204)

    @override_settings(TOR=_tor_settings(), ALLOWED_HOSTS=['testserver', ONION])
    def test_onion_request_with_unknown_operation_is_rejected(self):
        """The operation map is fixed, so this endpoint cannot be aimed anywhere."""
        with patch.object(TorService, '_open_controller', return_value=_FakeController()), \
                patch.object(tor_module, '_StemController', object()):
            get_tor_service().reset_cache()
            response = self.client.post(
                reverse('dark-protocol-vault-proxy'),
                {'operation': 'dark_protocol_vault_proxy', 'payload': {}},
                format='json',
                SERVER_PORT='8443',
                HTTP_HOST=ONION,
                HTTP_AUTHORIZATION=self._bearer(),
                REMOTE_ADDR=TRUSTED_PEER,
            )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data['error_code'], 'unsupported_operation')

    @override_settings(TOR=_tor_settings(), ALLOWED_HOSTS=['testserver', ONION])
    def test_detail_operation_without_an_id_is_a_client_error(self):
        with patch.object(TorService, '_open_controller', return_value=_FakeController()), \
                patch.object(tor_module, '_StemController', object()):
            get_tor_service().reset_cache()
            response = self.client.post(
                reverse('dark-protocol-vault-proxy'),
                {'operation': 'vault_get', 'payload': {}},
                format='json',
                SERVER_PORT='8443',
                HTTP_HOST=ONION,
                HTTP_AUTHORIZATION=self._bearer(),
                REMOTE_ADDR=TRUSTED_PEER,
            )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data['error_code'], 'invalid_payload')

    @override_settings(TOR={'ENABLED': False})
    def test_onion_ping_is_hidden_from_clearnet(self):
        """The unauthenticated self-check target must not answer on clearnet."""
        self.client.force_authenticate(user=None)
        response = self.client.get(reverse('dark-protocol-ping'))

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

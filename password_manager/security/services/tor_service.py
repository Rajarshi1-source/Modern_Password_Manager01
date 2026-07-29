"""
Tor Service - the real anonymity capability behind Dark Protocol
================================================================

Dark Protocol's anonymity claim reduces to exactly one property, and this
module is the only place allowed to decide whether that property holds:

    the backend is published as a Tor v3 onion service, and the request we are
    serving arrived over that onion service.

What that genuinely buys, stated precisely so the UI can repeat it:

  * The circuit terminates INSIDE the Tor network at the onion service, so
    there is no exit node and no clearnet hop between client and backend.
  * The backend never sees the client's IP address - the connection is handed
    to it by the local Tor daemon.

What it does NOT buy (nothing in the product may claim these):

  * It is not "stronger than Tor" - it IS Tor. The garlic/noise/cover-traffic
    layer in this package rides on top of a Tor circuit as traffic-analysis
    padding; it is defence in depth, not the anonymity primitive.
  * It does not defeat a global passive adversary, and it does not protect a
    user who authenticates with an account that identifies them.

Fail-closed contract
--------------------
Every probe in this module degrades to "capability absent, with a reason".
A control-port timeout, an unparsable answer, a missing hostname file and a
Tor daemon that is not running are all the SAME externally visible outcome:
``anonymity_active`` is False and Dark Protocol reports Unavailable. There is
no code path that reports the capability as present without having read a live
answer from the Tor control port in this process, within the cache TTL.
"""

import logging
import re
import time
from dataclasses import dataclass, replace
from pathlib import Path
from threading import Lock
from typing import Any, Dict, List, Optional

from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)


# =============================================================================
# Optional dependency
# =============================================================================
# stem is the Tor control-port library. It is declared in requirements, but the
# import stays optional so that a deployment without a Tor daemon (and without
# the library) starts normally and simply reports the capability as absent -
# the same fail-closed outcome as a Tor daemon that is down.
try:  # pragma: no cover - exercised by the import-failure path in tests
    from stem.control import Controller as _StemController
    _STEM_IMPORT_ERROR = None
except Exception as exc:  # pragma: no cover - depends on the environment
    _StemController = None
    _STEM_IMPORT_ERROR = str(exc)


# `PROGRESS=100` is the only part of the bootstrap line we act on. Tor emits
# e.g. 'NOTICE BOOTSTRAP PROGRESS=100 TAG=done SUMMARY="Done"'.
_BOOTSTRAP_PROGRESS_RE = re.compile(r"PROGRESS=(\d+)")

# v3 onion addresses are 56 base32 characters + '.onion'. Validating the shape
# matters because the address is echoed to clients and used as the expected
# Host header: a junk value read from a half-written hostname file must not be
# presented as a working address.
_V3_ONION_RE = re.compile(r"^[a-z2-7]{56}\.onion$")


def _default_config() -> Dict[str, Any]:
    """Settings defaults. Absent configuration means the capability is absent."""
    return {
        'ENABLED': False,
        'CONTROL_HOST': '127.0.0.1',
        'CONTROL_PORT': 9051,
        'CONTROL_SOCKET': '',
        'CONTROL_PASSWORD': '',
        'SOCKS_HOST': '127.0.0.1',
        'SOCKS_PORT': 9050,
        'ONION_HOSTNAME': '',
        'ONION_HOSTNAME_FILE': '',
        'ONION_INGRESS_PORT': 0,
        'ONION_INGRESS_TRUSTED_PEERS': '',
        'CAPABILITY_TTL_SECONDS': 15,
        'CONTROL_TIMEOUT_SECONDS': 5,
        'SELF_CHECK_PATH': '/api/security/dark-protocol/ping/',
        'SELF_CHECK_TIMEOUT_SECONDS': 60,
        'SELF_CHECK_TTL_SECONDS': 300,
    }


def get_tor_config() -> Dict[str, Any]:
    """Merge ``settings.TOR`` over the defaults.

    Read per call rather than cached on the instance so that
    ``override_settings`` in tests, and a settings reload in a worker, take
    effect without rebuilding the singleton.
    """
    config = _default_config()
    config.update(getattr(settings, 'TOR', {}) or {})
    return config


# =============================================================================
# Capability
# =============================================================================

@dataclass(frozen=True)
class TorCapability:
    """A point-in-time answer about whether real Tor anonymity is available.

    Every field is either read from the live control port or False. ``reason``
    carries the first thing that was missing, for operators and for the UI's
    Unavailable state; it is a fixed machine-readable token, never an exception
    string, so it cannot leak a control password or a filesystem path.
    """

    configured: bool = False
    controller_reachable: bool = False
    bootstrapped: bool = False
    circuit_established: bool = False
    onion_published: bool = False
    onion_address: Optional[str] = None
    bootstrap_progress: int = 0
    reason: Optional[str] = 'not_configured'
    checked_at: Optional[str] = None

    @property
    def anonymity_active(self) -> bool:
        """True only when every link in the chain was verified live.

        Deliberately an AND over all of them: a bootstrapped Tor with no
        published onion still means clients cannot reach us anonymously, and a
        published onion on a Tor that has not bootstrapped cannot carry
        traffic. Either way the honest answer is "not active".
        """
        return (
            self.configured
            and self.controller_reachable
            and self.bootstrapped
            and self.circuit_established
            and self.onion_published
            and bool(self.onion_address)
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            'anonymity_active': self.anonymity_active,
            'configured': self.configured,
            'controller_reachable': self.controller_reachable,
            'bootstrapped': self.bootstrapped,
            'bootstrap_progress': self.bootstrap_progress,
            'circuit_established': self.circuit_established,
            'onion_published': self.onion_published,
            'onion_address': self.onion_address,
            'reason': self.reason,
            'checked_at': self.checked_at,
        }


@dataclass(frozen=True)
class OnionReachability:
    """Result of the end-to-end loopback self-check through the SOCKS proxy."""

    reachable: bool = False
    status_code: Optional[int] = None
    latency_ms: Optional[int] = None
    reason: Optional[str] = 'not_checked'
    checked_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            'reachable': self.reachable,
            'status_code': self.status_code,
            'latency_ms': self.latency_ms,
            'reason': self.reason,
            'checked_at': self.checked_at,
        }


# =============================================================================
# Service
# =============================================================================

class TorService:
    """Reads live Tor state over the control port. Never guesses."""

    def __init__(self):
        self._lock = Lock()
        self._cached: Optional[TorCapability] = None
        # time.monotonic, not wall clock: a clock step backwards must not be
        # able to extend the life of a cached "active" answer.
        self._cached_at: float = 0.0
        self._cached_reach: Optional[OnionReachability] = None
        self._cached_reach_at: float = 0.0
        self._cached_relays: Optional[List[Dict[str, Any]]] = None
        self._cached_relays_at: float = 0.0
        # Bumped by reset_cache(). Probes run outside the lock, so a probe
        # that started before an invalidation must not publish its (now stale)
        # answer afterwards — it would repopulate a cache that was
        # deliberately cleared, or overwrite a newer result with an older one.
        self._generation: int = 0

    # -------------------------------------------------------------------
    # Control-port probing
    # -------------------------------------------------------------------

    def _open_controller(self, config: Dict[str, Any]):
        """Open and authenticate a control connection, or return None.

        Returns None rather than raising: every caller's correct response to a
        failure here is the same fail-closed capability answer.
        """
        if _StemController is None:
            return None

        timeout = _positive_number(config.get('CONTROL_TIMEOUT_SECONDS'), 5)
        socket_path = str(config.get('CONTROL_SOCKET') or '')

        try:
            if socket_path:
                controller = _StemController.from_socket_file(path=socket_path)
            else:
                controller = _StemController.from_port(
                    address=str(config.get('CONTROL_HOST') or '127.0.0.1'),
                    port=int(config.get('CONTROL_PORT') or 9051),
                )
        except Exception as exc:
            logger.warning("Tor control connection failed: %s", type(exc).__name__)
            return None

        try:
            # Bound every subsequent GETINFO. Without this a wedged daemon
            # would hang the request thread that triggered the probe.
            controller.set_socket_timeout(timeout)
        except Exception:  # pragma: no cover - stem always provides this
            pass

        try:
            password = config.get('CONTROL_PASSWORD') or None
            controller.authenticate(password=password)
        except Exception as exc:
            # Never log the exception body: stem includes the attempted
            # authentication method and can echo configuration detail.
            logger.warning("Tor control authentication failed: %s", type(exc).__name__)
            _close_quietly(controller)
            return None

        return controller

    def _probe(self, config: Dict[str, Any]) -> TorCapability:
        """One full capability probe against the live daemon."""
        now = timezone.now().isoformat()

        if _StemController is None:
            return TorCapability(
                configured=True,
                reason='stem_unavailable',
                checked_at=now,
            )

        controller = self._open_controller(config)
        if controller is None:
            return TorCapability(
                configured=True,
                reason='controller_unreachable',
                checked_at=now,
            )

        try:
            progress = self._read_bootstrap_progress(controller)
            bootstrapped = progress >= 100
            circuit = self._read_circuit_established(controller)
            address = self._resolve_onion_address(config, controller)
            # "Published" is asserted only when Tor itself reports a hidden
            # service configured AND we hold a well-formed address for it.
            # The definitive end-to-end proof is check_onion_reachable(),
            # which actually connects to the address through Tor.
            published = bool(address) and self._hidden_service_configured(controller)

            # A configured ONION_HOSTNAME wins over discovery, so a stale value
            # left in configuration would be advertised as live while Tor
            # actually serves a different address - clients would be sent
            # somewhere that does not answer, with the UI reporting available.
            # When both sources exist they must agree; when only one does there
            # is nothing to cross-check and the single source stands.
            if published and self._address_conflicts(config, controller, address):
                return replace(
                    TorCapability(
                        configured=True,
                        controller_reachable=True,
                        bootstrapped=bootstrapped,
                        bootstrap_progress=progress,
                        circuit_established=circuit,
                        onion_address=None,
                        checked_at=now,
                    ),
                    reason='onion_address_mismatch',
                )

            capability = TorCapability(
                configured=True,
                controller_reachable=True,
                bootstrapped=bootstrapped,
                bootstrap_progress=progress,
                circuit_established=circuit,
                onion_published=published,
                onion_address=address,
                checked_at=now,
            )
            return replace(capability, reason=_first_missing(capability))
        except Exception:
            # A probe must never propagate into the request that triggered it.
            logger.exception("Tor capability probe failed")
            return TorCapability(
                configured=True,
                controller_reachable=True,
                reason='probe_failed',
                checked_at=now,
            )
        finally:
            _close_quietly(controller)

    def _read_bootstrap_progress(self, controller) -> int:
        """Bootstrap percentage, or 0 when it cannot be read or parsed."""
        try:
            line = controller.get_info('status/bootstrap-phase')
        except Exception:
            return 0
        match = _BOOTSTRAP_PROGRESS_RE.search(str(line or ''))
        if not match:
            return 0
        try:
            progress = int(match.group(1))
        except (TypeError, ValueError):
            return 0
        # REJECT out of range, do not clamp. This previously clamped, so a
        # value of 101 became 100 and thereby granted "bootstrapped" — while
        # the comment beside it said an out-of-range value is a parse we do
        # not understand. Clamping turned an answer we cannot interpret into
        # the most permissive one it could have meant; 0 is the reading
        # consistent with this module's fail-closed contract.
        # (The regex matches \d+, so a negative can never appear here.)
        if not 0 <= progress <= 100:
            return 0
        return progress

    def _read_circuit_established(self, controller) -> bool:
        """Tor's own answer to "can I currently build/use circuits?"."""
        try:
            value = controller.get_info('status/circuit-established')
        except Exception:
            return False
        return str(value or '').strip() == '1'

    def _hidden_service_configured(self, controller) -> bool:
        """True when this Tor instance actually serves a hidden service.

        Covers both provisioning styles: a torrc ``HiddenServiceDir`` (how the
        compose/k8s deployment publishes the backend) and an ephemeral onion
        created over the control port (``onions/current``).
        """
        try:
            dirs = controller.get_conf('HiddenServiceDir', multiple=True)
            if any(str(d).strip() for d in (dirs or [])):
                return True
        except Exception:
            pass

        try:
            current = controller.get_info('onions/current')
        except Exception:
            return False
        return bool(str(current or '').strip())

    def _resolve_onion_address(self, config: Dict[str, Any], controller) -> Optional[str]:
        """Resolve our .onion address from configuration, file, or control port.

        Order is deliberate: an explicitly configured address wins (it is what
        operators publish), then the hostname file Tor writes, then an
        ephemeral onion from the control port. Any candidate that is not a
        well-formed v3 address is discarded rather than surfaced - a truncated
        read of a hostname file must not become an advertised address.
        """
        explicit = str(config.get('ONION_HOSTNAME') or '').strip()
        candidate = _valid_onion(explicit)
        if candidate:
            return candidate

        hostname_file = str(config.get('ONION_HOSTNAME_FILE') or '').strip()
        if hostname_file:
            try:
                raw = Path(hostname_file).read_text(encoding='utf-8')
            except OSError as exc:
                logger.warning("Onion hostname file unreadable: %s", type(exc).__name__)
            else:
                candidate = _valid_onion(raw)
                if candidate:
                    return candidate

        try:
            current = controller.get_info('onions/current')
        except Exception:
            return None
        for line in str(current or '').splitlines():
            service = line.strip()
            if not service:
                continue
            # onions/current lists service IDs without the .onion suffix.
            candidate = _valid_onion(service if service.endswith('.onion') else f'{service}.onion')
            if candidate:
                return candidate
        return None

    def _address_conflicts(self, config: Dict[str, Any], controller, address: str) -> bool:
        """True when a configured hostname disagrees with what Tor serves.

        Only meaningful when ONION_HOSTNAME is set AND this process can also
        discover an address (a readable hostname file, or an ephemeral onion on
        the control port). Kubernetes backend pods have neither, so there is
        nothing to compare and this correctly returns False rather than
        inventing a conflict.
        """
        if not _valid_onion(config.get('ONION_HOSTNAME')):
            return False

        discovered = self._resolve_onion_address(
            {**config, 'ONION_HOSTNAME': ''}, controller
        )
        return bool(discovered) and discovered != address

    # -------------------------------------------------------------------
    # Public capability API
    # -------------------------------------------------------------------

    def get_capability(self, force_refresh: bool = False) -> TorCapability:
        """Current capability, cached for ``CAPABILITY_TTL_SECONDS``.

        The cache exists so a dashboard poll does not open a control
        connection per widget. It can only ever shorten the life of a stale
        answer, never extend it: an expired entry is discarded and re-probed,
        and a failed re-probe returns the fail-closed answer rather than the
        previous successful one.
        """
        config = get_tor_config()
        if not config.get('ENABLED'):
            return TorCapability(
                configured=False,
                reason='not_configured',
                checked_at=timezone.now().isoformat(),
            )

        ttl = _positive_number(config.get('CAPABILITY_TTL_SECONDS'), 15)
        with self._lock:
            fresh = (
                self._cached is not None
                and (time.monotonic() - self._cached_at) < ttl
            )
            if fresh and not force_refresh:
                return self._cached
            generation = self._generation

        # Probe OUTSIDE the lock. request_is_onion_ingress sits on the vault
        # request path, so holding the lock across a control-port round trip
        # would queue every request thread behind one wedged daemon. Two
        # threads racing a cache miss may both probe; a duplicate read-only
        # GETINFO is far cheaper than serialising the request pool.
        capability = self._probe(config)
        with self._lock:
            # Publish only if nothing invalidated the cache while we probed.
            # The caller still receives what this probe actually read.
            if generation == self._generation:
                self._cached = capability
                self._cached_at = time.monotonic()
        return capability

    def get_circuit_relays(self) -> List[Dict[str, Any]]:
        """Relays of the currently built circuits, read live from Tor.

        Returns [] when Tor is unavailable. This replaced a table of
        database rows that described relays which never existed; an empty
        list is the honest answer when there is no live circuit to describe.
        """
        config = get_tor_config()
        if not config.get('ENABLED') or _StemController is None:
            return []

        # Cached on the same TTL as the capability probe. /nodes/ and /health/
        # are both polled by the dashboard, and without this each poll opened
        # and authenticated a fresh control connection per widget.
        ttl = _positive_number(config.get('CAPABILITY_TTL_SECONDS'), 15)
        with self._lock:
            if (
                self._cached_relays is not None
                and (time.monotonic() - self._cached_relays_at) < ttl
            ):
                return list(self._cached_relays)
            generation = self._generation

        controller = self._open_controller(config)
        if controller is None:
            return []

        try:
            circuits = controller.get_circuits()
        except Exception:
            logger.exception("Failed to read Tor circuits")
            return []
        finally:
            _close_quietly(controller)

        relays: List[Dict[str, Any]] = []
        for circuit in circuits or []:
            status = str(getattr(circuit, 'status', '') or '')
            if status.upper() != 'BUILT':
                # Only describe circuits that are actually usable.
                continue
            path = list(getattr(circuit, 'path', None) or [])
            for index, hop in enumerate(path):
                fingerprint, nickname = _unpack_hop(hop)
                if not fingerprint and not nickname:
                    continue
                relays.append({
                    'circuit_id': str(getattr(circuit, 'id', '') or ''),
                    'position': _hop_position(index, len(path)),
                    'nickname': nickname or None,
                    # Fingerprints are public directory data, but the full
                    # value fingerprints the circuit in logs and screenshots;
                    # the prefix is enough to correlate with the consensus.
                    'fingerprint': (fingerprint[:8] if fingerprint else None),
                    'purpose': str(getattr(circuit, 'purpose', '') or '').lower() or None,
                })

        with self._lock:
            # Same generation guard as the other caches: a read that started
            # before reset_cache() must not repopulate it.
            if generation == self._generation:
                self._cached_relays = list(relays)
                self._cached_relays_at = time.monotonic()
        return relays

    # -------------------------------------------------------------------
    # Onion ingress
    # -------------------------------------------------------------------

    def request_is_onion_ingress(self, request) -> bool:
        """True when THIS request arrived over our onion service.

        Three conditions must hold, and none of them is client-supplied:

        1. The request was served on ``ONION_INGRESS_PORT`` — a port with no
           published host mapping, so it is unreachable from outside the
           deployment.
        2. The peer address is one of ``ONION_INGRESS_TRUSTED_PEERS``, when
           configured. Condition 1 alone is NOT exclusivity: docker-compose
           puts every service on one bridge network, so a sibling container
           can reach 8443 directly and present the onion Host. This check is
           what makes "only the Tor daemon can produce onion ingress" true
           there. In Kubernetes the NetworkPolicy in k8s/tor.yaml enforces the
           same restriction at the network layer, where pod IPs are dynamic
           and cannot be listed here.
        3. The Host header equals our published onion address, which is what a
           client reaching the onion sends.

        A header such as ``X-Onion-Ingress`` is deliberately NOT trusted:
        anything a client can set, a clearnet client can set too, and the
        entire point of this check is that "anonymous" is never displayed for
        a connection that is not.
        """
        config = get_tor_config()
        if not config.get('ENABLED'):
            return False

        ingress_port = _positive_number(config.get('ONION_INGRESS_PORT'), 0)
        if not ingress_port:
            # No dedicated ingress port configured means we have no way to
            # distinguish onion traffic, so we must not claim any request is.
            return False

        served_port = _request_port(request)
        if served_port != int(ingress_port):
            return False

        if not self._peer_is_trusted(config, request):
            return False

        capability = self.get_capability()
        if not capability.anonymity_active or not capability.onion_address:
            return False

        host = _request_host(request)
        return bool(host) and host == capability.onion_address

    def _peer_is_trusted(self, config: Dict[str, Any], request) -> bool:
        """Whether the connecting peer may produce onion ingress.

        Entries may be IP addresses or hostnames. A hostname is resolved at
        check time, which is what makes this workable on both platforms:
        docker-compose service names resolve to the container address, and a
        Kubernetes HEADLESS service resolves to the current pod IPs (a normal
        ClusterIP would not — the source address of the traffic is the pod's,
        not the service's).

        An empty list FAILS CLOSED. Treating "nothing configured" as "trust
        every caller" would mean a deployment that forgot this setting reports
        connections as anonymous without having verified anything, which is
        precisely the middle state this feature must not have. A NetworkPolicy
        is a good second layer but cannot be observed from here, so it is not
        a substitute for checking.
        """
        raw = str(config.get('ONION_INGRESS_TRUSTED_PEERS') or '').strip()
        if not raw:
            return False

        peer = str((getattr(request, 'META', None) or {}).get('REMOTE_ADDR') or '').strip()
        if not peer:
            return False

        import socket

        for entry in raw.split(','):
            candidate = entry.strip()
            if not candidate:
                continue
            if candidate == peer:
                return True
            if _is_ip_literal(candidate):
                # An IP entry that did not match above cannot match after
                # resolution either, so skip the resolver entirely: a
                # deployment configured with IPs never performs a lookup on
                # this path.
                continue
            # DELIBERATELY NOT CACHED. Caching hostname->IP here would remove
            # this lookup from the request path, but container and pod IPs are
            # recycled: after the Tor daemon restarts, a cached address can be
            # reassigned to a DIFFERENT workload, which would then be accepted
            # as the Tor daemon. That is a fail-open, and a slower check is
            # strictly better than one that can be wrong. Configure IP entries
            # (above) if the resolution cost matters.
            try:
                # Resolve every address the name maps to: a compose service can
                # answer on more than one, and matching only the first would
                # reject legitimate ingress.
                infos = socket.getaddrinfo(candidate, None)
            except OSError:
                continue
            if any(info[4][0] == peer for info in infos):
                return True
        return False

    # -------------------------------------------------------------------
    # End-to-end self check
    # -------------------------------------------------------------------

    def socks_proxies(self) -> Optional[Dict[str, str]]:
        """requests-style proxy map pointing at the Tor SOCKS port.

        ``socks5h`` (not ``socks5``) is required: the ``h`` makes the proxy
        resolve the hostname, and a .onion address has no meaning to any other
        resolver. With plain ``socks5`` the local resolver would be asked for
        the .onion, fail, and - worse - leak the lookup.
        """
        config = get_tor_config()
        if not config.get('ENABLED'):
            return None
        host = str(config.get('SOCKS_HOST') or '').strip()
        port = _positive_number(config.get('SOCKS_PORT'), 0)
        if not host or not port:
            return None
        url = f'socks5h://{host}:{int(port)}'
        return {'http': url, 'https': url}

    def check_onion_reachable(self, force_refresh: bool = False) -> OnionReachability:
        """Fetch our own .onion through Tor: end-to-end proof it is published.

        This is the only check that proves the descriptor is in the hash ring
        and the service accepts connections, because it performs the same
        rendezvous a real client performs. It is also SLOW (a cold descriptor
        fetch can take tens of seconds), so it is cached for
        ``SELF_CHECK_TTL_SECONDS`` and is never run inline on an ordinary
        request path - only on explicit demand or from the periodic task.
        """
        config = get_tor_config()
        now = timezone.now().isoformat()

        if not config.get('ENABLED'):
            return OnionReachability(reason='not_configured', checked_at=now)

        ttl = _positive_number(config.get('SELF_CHECK_TTL_SECONDS'), 300)
        with self._lock:
            fresh = (
                self._cached_reach is not None
                and (time.monotonic() - self._cached_reach_at) < ttl
            )
            if fresh and not force_refresh:
                return self._cached_reach
            generation = self._generation

        result = self._probe_reachability(config, now)
        with self._lock:
            # Same generation guard as get_capability: this probe is slow
            # (a cold rendezvous takes tens of seconds), so the window in
            # which an invalidation can land underneath it is much wider.
            if generation == self._generation:
                self._cached_reach = result
                self._cached_reach_at = time.monotonic()
        return result

    def _probe_reachability(self, config: Dict[str, Any], now: str) -> OnionReachability:
        capability = self.get_capability()
        if not capability.onion_address:
            return OnionReachability(reason='no_onion_address', checked_at=now)

        proxies = self.socks_proxies()
        if not proxies:
            return OnionReachability(reason='socks_not_configured', checked_at=now)

        try:
            import requests  # local import: only the self-check needs it
        except Exception:
            return OnionReachability(reason='requests_unavailable', checked_at=now)

        path = str(config.get('SELF_CHECK_PATH') or '/')
        if not path.startswith('/'):
            path = f'/{path}'
        url = f'http://{capability.onion_address}{path}'
        timeout = _positive_number(config.get('SELF_CHECK_TIMEOUT_SECONDS'), 60)

        started = time.monotonic()
        try:
            # http:// is correct here and https:// would be wrong: the request
            # goes to a .onion over the Tor SOCKS proxy, and Tor encrypts that
            # circuit end to end with the service's own keys. There is no
            # clearnet hop for TLS to protect, and onion services do not
            # normally hold CA-issued certificates.
            # The suppression must sit immediately above the line the scanner
            # REPORTS, and for this rule that is the `url` ARGUMENT, not the
            # call line — hence the comment inside the parentheses. Two earlier
            # placements (above the rationale, then above the call) both failed
            # for this reason.
            #
            # stream=True in a context manager: this check only reads the
            # status line, and `timeout` bounds each socket operation rather
            # than the whole transfer, so downloading the body would let a
            # slow-drip or oversized response stall the probe indefinitely.
            # The connection is closed on exit without consuming the body.
            with requests.get(
                # nosemgrep: python.lang.security.audit.insecure-transport.requests.request-with-http.request-with-http
                url,
                proxies=proxies,
                timeout=timeout,
                allow_redirects=False,
                stream=True,
            ) as response:
                status_code = int(getattr(response, 'status_code', 0) or 0)
        except Exception as exc:
            # PySocks raises on a missing/refused proxy; requests raises on
            # rendezvous failure. Both mean "not reachable through Tor".
            logger.warning("Onion self-check failed: %s", type(exc).__name__)
            return OnionReachability(reason='unreachable', checked_at=now)

        latency_ms = int((time.monotonic() - started) * 1000)
        # ANY HTTP status proves the rendezvous completed and our own service
        # answered; the check is about reachability, not about the endpoint's
        # response. A 404 still means the onion is published and serving.
        return OnionReachability(
            reachable=True,
            status_code=status_code,
            latency_ms=latency_ms,
            reason=None,
            checked_at=now,
        )

    def reset_cache(self) -> None:
        """Drop cached probes. Used by tests and by config-change handling."""
        with self._lock:
            self._cached = None
            self._cached_at = 0.0
            self._cached_reach = None
            self._cached_reach_at = 0.0
            self._cached_relays = None
            self._cached_relays_at = 0.0
            # Any probe already in flight now belongs to the previous
            # generation and will be discarded rather than repopulating the
            # cache we just cleared.
            self._generation += 1


# =============================================================================
# Helpers
# =============================================================================

def _first_missing(capability: TorCapability) -> Optional[str]:
    """The first unmet precondition, as a stable machine-readable token."""
    if not capability.controller_reachable:
        return 'controller_unreachable'
    if not capability.bootstrapped:
        return 'not_bootstrapped'
    if not capability.circuit_established:
        return 'no_circuit'
    if not capability.onion_address:
        return 'no_onion_address'
    if not capability.onion_published:
        return 'onion_not_published'
    return None


def _is_ip_literal(value: str) -> bool:
    """True when the string is already an IP address, so no lookup is needed."""
    import ipaddress

    try:
        ipaddress.ip_address(value)
    except ValueError:
        return False
    return True


def _valid_onion(value: Any) -> Optional[str]:
    """Normalise and validate a v3 onion address, or return None."""
    text = str(value or '').strip().lower()
    if not text:
        return None
    # A hostname file may carry trailing whitespace/newlines; anything else
    # (multiple tokens, a URL, a partial write) fails the shape check below.
    text = text.split()[0] if text.split() else ''
    return text if _V3_ONION_RE.match(text) else None


def _positive_number(value: Any, default: float) -> float:
    """Coerce a configured number, falling back on anything unusable.

    Configuration arrives from environment variables, so a non-numeric or
    negative value is a realistic input. It must not become a zero timeout (no
    timeout at all in some clients) or a negative TTL (a permanently stale
    cache), so both fall back to the caller's default.
    """
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    if number != number or number in (float('inf'), float('-inf')):
        # NaN compares False against every bound, so it would slip past a
        # range check instead of tripping it. Reject explicitly.
        return default
    if number < 0:
        return default
    return number


def _request_port(request) -> Optional[int]:
    """The TCP port this process actually served the request on, or None.

    Reads SERVER_PORT directly rather than calling ``request.get_port()``:
    get_port() returns the X-Forwarded-Port header when USE_X_FORWARDED_PORT
    is enabled, and this value is the network FACT the onion-ingress check
    rests on. Sourcing it from a client-settable header would let a request
    name its own ingress port, and would silently do so the day an unrelated
    setting is turned on. (Same reason SECURE_PROXY_SSL_HEADER is disabled on
    the onion listener.)
    """
    port = (getattr(request, 'META', None) or {}).get('SERVER_PORT')
    try:
        return int(str(port).strip())
    except (TypeError, ValueError):
        return None


def _request_host(request) -> Optional[str]:
    """The Host header without its port, lowercased, or None."""
    try:
        host = request.get_host()
    except Exception:
        # get_host() raises DisallowedHost when the Host header is not in
        # ALLOWED_HOSTS. That is not an onion request by definition.
        return None
    host = str(host or '').strip().lower()
    if not host:
        return None
    return host.rsplit(':', 1)[0] if ':' in host else host


def _unpack_hop(hop: Any) -> tuple:
    """Split stem's (fingerprint, nickname) hop tuple defensively."""
    try:
        fingerprint, nickname = hop
    except (TypeError, ValueError):
        return ('', '')
    return (str(fingerprint or ''), str(nickname or ''))


def _hop_position(index: int, length: int) -> str:
    """Name a hop by its position in the circuit.

    Onion-service circuits have no exit: the last hop is a rendezvous point,
    which is precisely why 'no exit node' is a true statement about this
    deployment. Naming the final hop 'exit' would contradict that, so the
    positions used here are guard / middle / rendezvous.
    """
    if index == 0:
        return 'guard'
    if index == length - 1:
        return 'rendezvous'
    return 'middle'


def _close_quietly(controller) -> None:
    if controller is None:
        return
    try:
        controller.close()
    except Exception:  # pragma: no cover - close failures are not actionable
        pass


# =============================================================================
# Singleton
# =============================================================================

_tor_service: Optional[TorService] = None
_tor_service_lock = Lock()


def get_tor_service() -> TorService:
    """Process-wide TorService. Its only mutable state is the probe cache."""
    global _tor_service
    if _tor_service is None:
        with _tor_service_lock:
            if _tor_service is None:
                _tor_service = TorService()
    return _tor_service

"""
Dark Protocol Service
=====================

Core orchestrator for anonymous vault access.

Where the anonymity actually comes from
---------------------------------------
From Tor, and only from Tor. The backend is published as a v3 onion service
(see `tor_service.py`); a client that reaches it over that onion gets a circuit
that terminates inside the Tor network - no exit node - and the backend never
learns the client's IP. `tor_service` verifies that live, and this module
refuses to act anonymously when it cannot.

The garlic bundling, noise encryption and cover traffic in this package are an
obfuscation layer that rides ON TOP of that circuit: padding and traffic shape
for traffic-analysis resistance. They run inside a single Django deployment and
are NOT an anonymity network on their own - the "nodes" they route between are
rows in this database, not peers on a wire. Nothing here may report anonymity
on the strength of that layer alone.

@author Password Manager Team
@created 2026-02-02
"""

import io
import json
import secrets
import logging
import hashlib
import sys
from datetime import timedelta
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass, field
from urllib.parse import urlencode
from django.conf import settings
from django.urls import NoReverseMatch, resolve, reverse
from django.utils import timezone
from django.db import transaction

from ..models.dark_protocol_models import (
    DarkProtocolNode,
    GarlicSession,
    CoverTrafficPattern,
    RoutingPath,
    TrafficBundle,
    NetworkHealth,
    DarkProtocolConfig,
)

logger = logging.getLogger(__name__)


# =============================================================================
# Configuration
# =============================================================================

def get_dark_protocol_config() -> Dict[str, Any]:
    """Get dark protocol configuration from settings."""
    return getattr(settings, 'DARK_PROTOCOL', {
        'ENABLED': True,
        'DEFAULT_HOP_COUNT': 3,
        'MAX_HOP_COUNT': 5,
        'SESSION_TIMEOUT_MINUTES': 30,
        'PATH_ROTATION_MINUTES': 5,
        'COVER_TRAFFIC_ENABLED': True,
        'COVER_TRAFFIC_RATE': 0.5,
        'MIN_NODE_TRUST_SCORE': 0.3,
        'USE_BRIDGE_NODES': False,
    })


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class SessionEstablishResult:
    """Result of establishing a garlic session."""
    success: bool
    session_id: Optional[str] = None
    session: Optional[GarlicSession] = None
    error_message: Optional[str] = None
    path_length: int = 0
    estimated_latency_ms: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'success': self.success,
            'session_id': self.session_id,
            'error_message': self.error_message,
            'path_length': self.path_length,
            'estimated_latency_ms': self.estimated_latency_ms,
        }


@dataclass
class EncryptedBundle:
    """An encrypted traffic bundle ready for transmission."""
    bundle_id: str
    encrypted_data: bytes
    layers: int
    size: int
    is_cover: bool = False
    sequence: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'bundle_id': self.bundle_id,
            'size': self.size,
            'layers': self.layers,
            'is_cover': self.is_cover,
            'sequence': self.sequence,
        }


@dataclass
class VaultOperationResult:
    """Result of a vault operation executed under a verified anonymous ingress.

    ``error_code`` is a stable machine-readable token that the API layer maps
    to an HTTP status and the UI maps to a message. It exists because the
    refusal reasons are meaningfully different to a caller - "Tor is down" is
    an outage, "you came over clearnet" is a routing mistake the client can fix
    by using the .onion address - and because an exception string must never be
    the thing a client parses.
    """
    success: bool
    operation_id: str
    response_data: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    error_code: Optional[str] = None
    latency_ms: int = 0
    path_used: Optional[str] = None
    status_code: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            'success': self.success,
            'operation_id': self.operation_id,
            'response_data': self.response_data,
            'error_message': self.error_message,
            'error_code': self.error_code,
            'latency_ms': self.latency_ms,
        }


# =============================================================================
# Vault operation routing
# =============================================================================
# A FIXED map from the operation names this endpoint accepts to the real vault
# API. It is fixed on purpose: the caller never supplies a path, so this
# endpoint cannot be pointed at an arbitrary internal URL, and it cannot be
# pointed back at itself.
#
# Operations are dispatched to the genuine vault views, so ownership scoping,
# permissions, serializer validation and audit logging are the vault's own -
# there is no second implementation of vault access here to drift out of sync.

VAULT_OPERATION_ROUTES: Dict[str, Dict[str, Any]] = {
    'vault_list': {'method': 'GET', 'route': 'api-vault-list'},
    'vault_get': {'method': 'GET', 'route': 'api-vault-detail', 'needs_id': True},
    'vault_create': {'method': 'POST', 'route': 'api-vault-list'},
    # PATCH, not PUT: callers send the fields they are changing. The vault's
    # update() validates with partial=False under PUT, so a partial payload
    # would fail validation on fields the caller never intended to touch.
    'vault_update': {'method': 'PATCH', 'route': 'api-vault-detail', 'needs_id': True},
    'vault_delete': {'method': 'DELETE', 'route': 'api-vault-detail', 'needs_id': True},
    # GET, not POST: the search view reads its term from request.GET only, so
    # a JSON body would arrive as an empty query and silently return nothing.
    'vault_search': {'method': 'GET', 'route': 'vault-search'},
    'vault_sync': {'method': 'POST', 'route': 'vault-sync'},
}


# =============================================================================
# Dark Protocol Service
# =============================================================================

class DarkProtocolService:
    """
    Core service for the Dark Protocol anonymous vault access network.
    
    Orchestrates:
    - Session establishment with garlic routing
    - Path selection and rotation
    - Traffic bundling
    - Vault operation proxying
    """
    
    def __init__(self):
        self.config = get_dark_protocol_config()
        self._garlic_router = None
        self._noise_encryptor = None
        self._cover_generator = None
    
    @property
    def garlic_router(self):
        """Lazy load garlic router."""
        if self._garlic_router is None:
            from .garlic_router import GarlicRouter
            self._garlic_router = GarlicRouter()
        return self._garlic_router
    
    @property
    def noise_encryptor(self):
        """Lazy load noise encryptor."""
        if self._noise_encryptor is None:
            from .noise_encryptor import NoiseEncryptor
            self._noise_encryptor = NoiseEncryptor()
        return self._noise_encryptor
    
    @property
    def cover_generator(self):
        """Lazy load cover traffic generator."""
        if self._cover_generator is None:
            from .cover_traffic_generator import CoverTrafficGenerator
            self._cover_generator = CoverTrafficGenerator()
        return self._cover_generator

    @property
    def tor(self):
        """The Tor capability layer - the only source of the anonymity verdict."""
        from .tor_service import get_tor_service
        return get_tor_service()

    # =========================================================================
    # Capability Reporting
    # =========================================================================

    def get_capabilities(self, request=None) -> Dict[str, Any]:
        """Report what Dark Protocol can genuinely do right now.

        Mirrors the liveness capability model: a property is advertised only
        when the capability behind it is present and verified, and the claims
        are written so they can be repeated verbatim in the UI without
        overstating anything.

        ``request`` is optional so operators can query the deployment-level
        capability; when supplied, the answer also says whether THIS connection
        is anonymous, which is the only thing that governs vault access.
        """
        capability = self.tor.get_capability()
        dark_config = get_dark_protocol_config()
        onion_ingress = bool(request is not None and self.tor.request_is_onion_ingress(request))

        return {
            'anonymity': {
                'transport': 'tor_v3_onion',
                'available': capability.anonymity_active,
                'reason': capability.reason,
                'onion_address': capability.onion_address if capability.anonymity_active else None,
                'current_connection_is_anonymous': onion_ingress,
                'details': capability.to_dict(),
            },
            # Obfuscation is configuration, not capability: these run in-process
            # and are honest about being padding rather than anonymity.
            'obfuscation': {
                'cover_traffic': {
                    'enabled': bool(dark_config.get('COVER_TRAFFIC_ENABLED')),
                    'gates_anonymity': False,
                    'note': 'Padding and traffic shaping over the Tor circuit; '
                            'raises the cost of traffic analysis. Not anonymity '
                            'on its own.',
                },
                'garlic_bundling': {
                    'enabled': True,
                    'gates_anonymity': False,
                    'note': 'Multi-layer encryption and bundling applied within '
                            'this deployment. The relays it names are local '
                            'records, not independent peers.',
                },
            },
            'vault_proxy': {
                'available': capability.anonymity_active and onion_ingress,
                'requires': 'onion_ingress',
                'note': 'Vault operations are served anonymously only for '
                        'requests that arrived over the onion service.',
            },
            'claims': [
                'Vault access over the Tor network as a v3 onion service.',
                'No exit node: the circuit terminates inside Tor at this service.',
                'The server does not learn the client IP address of onion connections.',
                'Cover traffic and padding add traffic-analysis resistance.',
            ],
            'limitations': [
                'Does not defeat an adversary observing the whole network.',
                'An authenticated account still identifies the user to this service.',
                'Anonymity applies to connections over the onion address only.',
            ],
        }

    # =========================================================================
    # Configuration Management
    # =========================================================================
    
    def get_or_create_config(self, user) -> DarkProtocolConfig:
        """Get or create user's dark protocol configuration."""
        config, created = DarkProtocolConfig.objects.get_or_create(
            user=user,
            defaults={
                'is_enabled': False,
                'cover_traffic_enabled': True,
                'cover_traffic_intensity': 0.5,
            }
        )
        if created:
            logger.info(f"Created dark protocol config for user {user.id}")
        return config
    
    def update_config(self, user, **kwargs) -> DarkProtocolConfig:
        """Update user's dark protocol configuration."""
        config = self.get_or_create_config(user)
        
        allowed_fields = [
            'is_enabled', 'auto_enable_on_threat', 'preferred_regions',
            'min_hops', 'max_hops', 'cover_traffic_enabled',
            'cover_traffic_intensity', 'session_timeout_minutes',
            'auto_path_rotation', 'path_rotation_interval_minutes',
            'use_bridge_nodes', 'require_verified_nodes',
        ]
        
        for field, value in kwargs.items():
            if field in allowed_fields:
                setattr(config, field, value)
        
        config.save()
        logger.info(f"Updated dark protocol config for user {user.id}")
        return config
    
    # =========================================================================
    # Session Management
    # =========================================================================
    
    def establish_session(
        self,
        user,
        hop_count: int = None,
        preferred_regions: List[str] = None,
    ) -> SessionEstablishResult:
        """
        Establish a new garlic routing session.
        
        Args:
            user: The user establishing the session
            hop_count: Number of hops (default from config)
            preferred_regions: Preferred geographic regions for nodes
            
        Returns:
            SessionEstablishResult with session details
        """
        try:
            config = self.get_or_create_config(user)
            
            # Determine hop count
            if hop_count is None:
                hop_count = config.min_hops
            hop_count = max(config.min_hops, min(hop_count, config.max_hops))
            
            # Get preferred regions
            if preferred_regions is None:
                preferred_regions = config.preferred_regions or []
            
            # Select nodes for path
            nodes = self._select_path_nodes(
                hop_count=hop_count,
                preferred_regions=preferred_regions,
                require_verified=config.require_verified_nodes,
                use_bridges=config.use_bridge_nodes,
            )
            
            if len(nodes) < hop_count:
                return SessionEstablishResult(
                    success=False,
                    error_message=f"Insufficient nodes available (found {len(nodes)}, need {hop_count})"
                )
            
            # Create session with garlic router
            session_id = secrets.token_hex(32)
            layer_keys, encrypted_path = self.garlic_router.create_circuit(
                nodes=nodes,
                session_id=session_id,
            )
            
            # Calculate estimated latency
            def _node_latency(node):
                health = (
                    NetworkHealth.objects.filter(node=node, is_reachable=True)
                    .order_by('-checked_at')
                    .first()
                )
                return (health.latency_ms if health else None) or 50
            estimated_latency = sum(_node_latency(node) for node in nodes)
            
            # Create session record
            with transaction.atomic():
                session = GarlicSession.objects.create(
                    session_id=session_id,
                    user=user,
                    status='active',
                    encrypted_path=encrypted_path,
                    path_length=len(nodes),
                    layer_keys=layer_keys,
                    entry_node=nodes[0],
                    expires_at=timezone.now() + timedelta(
                        minutes=config.session_timeout_minutes
                    ),
                    is_verified=True,
                )
                
                # Update node circuit counts atomically
                from django.db.models import F
                for node in nodes:
                    type(node).objects.filter(pk=node.pk).update(
                        current_circuits=F('current_circuits') + 1
                    )
            
            logger.info(
                f"Established dark protocol session {session_id[:8]}... "
                f"for user {user.id} with {len(nodes)} hops"
            )
            
            return SessionEstablishResult(
                success=True,
                session_id=session_id,
                session=session,
                path_length=len(nodes),
                estimated_latency_ms=estimated_latency,
            )
            
        except Exception as e:
            logger.error(f"Failed to establish session: {e}")
            return SessionEstablishResult(
                success=False,
                error_message=str(e)
            )
    
    def terminate_session(self, session_id: str, user) -> bool:
        """
        Terminate a garlic routing session.
        
        Args:
            session_id: The session to terminate
            user: The session owner
            
        Returns:
            True if terminated successfully
        """
        try:
            session = GarlicSession.objects.get(
                session_id=session_id,
                user=user,
            )
            
            if session.entry_node:
                session.entry_node.current_circuits = max(
                    0, session.entry_node.current_circuits - 1
                )
                session.entry_node.save(update_fields=['current_circuits'])
            
            session.status = 'terminated'
            session.save(update_fields=['status'])
            
            # Clean up associated paths
            RoutingPath.objects.filter(
                user=user,
                entry_node=session.entry_node,
                is_active=True,
            ).update(is_active=False)
            
            logger.info(f"Terminated session {session_id[:8]}...")
            return True
            
        except GarlicSession.DoesNotExist:
            logger.warning(f"Session {session_id[:8]}... not found")
            return False
        except Exception as e:
            logger.error(f"Error terminating session: {e}")
            return False
    
    def get_active_session(self, user) -> Optional[GarlicSession]:
        """Get user's active session if one exists."""
        return GarlicSession.objects.filter(
            user=user,
            status='active',
            expires_at__gt=timezone.now(),
        ).first()
    
    # =========================================================================
    # Path Management
    # =========================================================================
    
    def _select_path_nodes(
        self,
        hop_count: int,
        preferred_regions: List[str],
        require_verified: bool = True,
        use_bridges: bool = False,
    ) -> List[DarkProtocolNode]:
        """
        Select nodes for a routing path.
        
        Nodes are selected to maximize anonymity:
        - Different regions for each hop
        - High trust scores
        - Low current load
        - Good uptime
        """
        # Base query for available nodes
        nodes_qs = DarkProtocolNode.objects.filter(
            status='active',
            last_seen_at__gt=timezone.now() - timedelta(minutes=5),
        )
        
        if require_verified:
            nodes_qs = nodes_qs.filter(trust_score__gte=self.config.get('MIN_NODE_TRUST_SCORE', 0.3))
        
        # Select entry node (prefer bridges if enabled)
        if use_bridges:
            entry_candidates = nodes_qs.filter(node_type='bridge')
            if not entry_candidates.exists():
                entry_candidates = nodes_qs.filter(node_type='entry')
        else:
            entry_candidates = nodes_qs.filter(node_type='entry')
        
        # Apply region preference for entry
        if preferred_regions:
            preferred_entry = entry_candidates.filter(region__in=preferred_regions)
            if preferred_entry.exists():
                entry_candidates = preferred_entry
        
        entry_node = entry_candidates.order_by(
            '-trust_score', '-uptime_percentage', 'current_circuits'
        ).first()
        
        if not entry_node:
            return []
        
        selected_nodes = [entry_node]
        used_regions = {entry_node.region}
        
        # Select relay nodes
        for i in range(hop_count - 2):
            relay_candidates = nodes_qs.filter(
                node_type='relay'
            ).exclude(
                id__in=[n.id for n in selected_nodes]
            ).exclude(
                region__in=used_regions  # Different region for diversity
            )
            
            relay = relay_candidates.order_by(
                '-trust_score', '-uptime_percentage', 'current_circuits'
            ).first()
            
            if not relay:
                # Fallback: allow same region if necessary
                relay = nodes_qs.filter(
                    node_type='relay'
                ).exclude(
                    id__in=[n.id for n in selected_nodes]
                ).order_by(
                    '-trust_score', '-uptime_percentage'
                ).first()
            
            if relay:
                selected_nodes.append(relay)
                used_regions.add(relay.region)
        
        # Select destination node
        dest_candidates = nodes_qs.filter(
            node_type='destination'
        ).exclude(
            id__in=[n.id for n in selected_nodes]
        )
        
        destination = dest_candidates.order_by(
            '-trust_score', '-uptime_percentage', 'current_circuits'
        ).first()
        
        if destination:
            selected_nodes.append(destination)
        
        return selected_nodes
    
    def rotate_path(self, user) -> Optional[RoutingPath]:
        """
        Rotate the user's routing path for additional security.
        
        Creates a new path and marks old paths as inactive.
        """
        try:
            config = self.get_or_create_config(user)
            
            # Select new nodes
            nodes = self._select_path_nodes(
                hop_count=config.min_hops,
                preferred_regions=config.preferred_regions or [],
                require_verified=config.require_verified_nodes,
                use_bridges=config.use_bridge_nodes,
            )
            
            if not nodes:
                logger.warning(f"No nodes available for path rotation for user {user.id}")
                return None
            
            # Create encrypted path data
            path_data = self.garlic_router.create_path_data(nodes)
            
            with transaction.atomic():
                # Deactivate old paths
                RoutingPath.objects.filter(
                    user=user, is_active=True
                ).update(is_active=False, is_primary=False)
                
                # Create new path
                path = RoutingPath.objects.create(
                    user=user,
                    encrypted_path_data=path_data,
                    hop_count=len(nodes),
                    entry_node=nodes[0],
                    is_active=True,
                    is_primary=True,
                    expires_at=timezone.now() + timedelta(
                        minutes=config.path_rotation_interval_minutes
                    ),
                )
            
            logger.info(f"Rotated path for user {user.id}: {path.path_id[:8]}...")
            return path
            
        except Exception as e:
            logger.error(f"Path rotation failed: {e}")
            return None
    
    # =========================================================================
    # Traffic Operations
    # =========================================================================
    
    def proxy_vault_operation(
        self,
        user,
        operation: str,
        payload: Dict[str, Any],
        session_id: str = None,
        request=None,
    ) -> VaultOperationResult:
        """
        Execute a vault operation for a client that reached us anonymously.

        This used to bundle the operation, "send" it through the garlic router
        and return an acknowledgement the router invented - the operation never
        travelled anywhere and no vault data was ever touched. That is removed.

        What replaces it is the honest version of the same promise:

        1. Refuse unless Tor is live and our onion service is published.
        2. Refuse unless THIS request arrived over that onion service. The
           anonymity is a property of how the client reached us, so a clearnet
           request cannot be made anonymous by anything done after it arrives -
           and it is never silently served as though it were.
        3. Otherwise dispatch to the real vault API and return real data.

        There is deliberately no fallback between 2 and 3: a client that wants
        anonymous vault access must use the .onion address, which the refusal
        hands back to it.

        Args:
            user: The user performing the operation
            operation: The vault operation name (see VAULT_OPERATION_ROUTES)
            payload: The operation payload, forwarded to the vault view
            session_id: Optional garlic session, used for traffic accounting
            request: The inbound request; required, as the ingress check is
                the entire basis for calling this operation anonymous

        Returns:
            VaultOperationResult with real vault data, or a refusal.
        """
        operation_id = secrets.token_hex(16)
        start_time = timezone.now()

        capability = self.tor.get_capability()
        if not capability.anonymity_active:
            return VaultOperationResult(
                success=False,
                operation_id=operation_id,
                error_code='tor_unavailable',
                error_message=(
                    'Anonymous vault access is unavailable: '
                    f'{capability.reason or "tor_unavailable"}'
                ),
            )

        if request is None or not self.tor.request_is_onion_ingress(request):
            return VaultOperationResult(
                success=False,
                operation_id=operation_id,
                error_code='clearnet_ingress_refused',
                error_message=(
                    'This request did not arrive over the onion service, so it '
                    'is not anonymous. Reach the vault over the .onion address '
                    'to use anonymous access.'
                ),
            )

        route = VAULT_OPERATION_ROUTES.get(operation)
        if route is None:
            return VaultOperationResult(
                success=False,
                operation_id=operation_id,
                error_code='unsupported_operation',
                error_message=f'Unsupported operation: {operation}',
            )

        try:
            status_code, data = self._dispatch_vault_operation(request, route, payload or {})
        except ValueError as exc:
            # A malformed payload (e.g. a detail operation with no id) is the
            # caller's error, so it must not surface as an internal failure.
            return VaultOperationResult(
                success=False,
                operation_id=operation_id,
                error_code='invalid_payload',
                error_message=str(exc),
            )
        except NoReverseMatch:
            # The vault URL names moved. Surfacing this as a refusal rather
            # than a 500 keeps the failure legible, and it is a deploy-time
            # defect that the routing test pins.
            logger.exception("Vault route missing for operation %s", operation)
            return VaultOperationResult(
                success=False,
                operation_id=operation_id,
                error_code='route_unavailable',
                error_message='Vault route unavailable',
            )
        except Exception:
            logger.exception("Anonymous vault operation failed: %s", operation)
            return VaultOperationResult(
                success=False,
                operation_id=operation_id,
                error_code='operation_failed',
                error_message='Vault operation failed',
            )

        latency_ms = int((timezone.now() - start_time).total_seconds() * 1000)
        self._record_operation_traffic(user, session_id, payload)

        return VaultOperationResult(
            success=200 <= status_code < 300,
            operation_id=operation_id,
            response_data=data,
            status_code=status_code,
            error_code=None if 200 <= status_code < 300 else 'vault_error',
            latency_ms=latency_ms,
        )

    def _dispatch_vault_operation(
        self,
        request,
        route: Dict[str, Any],
        payload: Dict[str, Any],
    ) -> Tuple[int, Any]:
        """Call the real vault view in-process and return (status, data).

        The inner request is built from the outer one so the vault view
        authenticates and authorises exactly as it would for a direct call.

        How the inner request authenticates, precisely: this project's
        DEFAULT_AUTHENTICATION_CLASSES contains only JWTAuthentication, so the
        load-bearing mechanism is the ``Authorization`` header, which is
        carried over with the rest of META. The vault view therefore verifies
        the caller's token itself rather than trusting anything decided here.
        ``inner.user`` is set as well so that a deployment which re-enables
        SessionAuthentication continues to resolve the same user; it is inert
        under the current configuration.

        Two properties make the dispatch safe:

        * The path comes from VAULT_OPERATION_ROUTES via ``reverse()``, never
          from the caller, so this cannot be aimed at an arbitrary URL.
        * The outer request has already passed authentication, permissions and
          CSRF in the normal middleware stack; the inner one is a continuation
          of it, not a new entry point, which is why CSRF is not re-enforced on
          it (re-enforcing would reject token-authenticated callers that never
          carry a CSRF cookie).
        """
        method = route['method']
        if route.get('needs_id'):
            item_id = payload.get('id') or payload.get('item_id')
            if not item_id:
                raise ValueError('id is required for this operation')
            path = reverse(route['route'], args=[str(item_id)])
        else:
            path = reverse(route['route'])

        body = b''
        query = ''
        if method in ('GET', 'DELETE'):
            # Only scalars survive into the query string; a nested structure
            # has no unambiguous encoding, so dropping it is better than
            # silently flattening it into something the view misreads.
            query = urlencode({
                # Booleans are lowercased: urlencode would render Python's
                # True as "True", which DRF's BooleanField does not accept and
                # a plain truthiness test reads as true even for "False".
                key: ('true' if value is True else 'false' if value is False else value)
                for key, value in payload.items()
                if isinstance(value, (str, int, float, bool))
            })
        else:
            body = json.dumps(payload).encode('utf-8')

        environ = {
            key: value for key, value in request.META.items()
            if not key.startswith('wsgi.')
        }
        environ.update({
            'REQUEST_METHOD': method,
            'PATH_INFO': path,
            'QUERY_STRING': query,
            'CONTENT_TYPE': 'application/json',
            'CONTENT_LENGTH': str(len(body)),
            'wsgi.input': io.BytesIO(body),
            'wsgi.errors': sys.stderr,
            'wsgi.version': (1, 0),
            'wsgi.multithread': True,
            'wsgi.multiprocess': True,
            'wsgi.run_once': False,
            'wsgi.url_scheme': getattr(request, 'scheme', 'http'),
        })

        from django.core.handlers.wsgi import WSGIRequest

        inner = WSGIRequest(environ)
        inner.user = getattr(request, 'user', None)
        session = getattr(request, 'session', None)
        if session is not None:
            inner.session = session
        inner._dont_enforce_csrf_checks = True

        match = resolve(path)
        response = match.func(inner, *match.args, **match.kwargs)

        if hasattr(response, 'render') and not getattr(response, 'is_rendered', True):
            response.render()

        status_code = int(getattr(response, 'status_code', 500))
        if hasattr(response, 'data'):
            return status_code, response.data
        # A plain HttpResponse (e.g. a redirect) has no .data. Return the body
        # only when it parses as JSON; raw bytes are not something the client
        # of this endpoint can use.
        try:
            return status_code, json.loads(response.content.decode('utf-8'))
        except Exception:
            return status_code, None

    def _record_operation_traffic(
        self,
        user,
        session_id: Optional[str],
        payload: Dict[str, Any],
    ) -> None:
        """Update garlic-session counters for an operation that really ran.

        Accounting only. It feeds the cover-traffic layer's shaping and the
        stats panel; it does not transport anything and no longer stands in
        for a transport. Failures here must not fail the vault operation that
        already succeeded.
        """
        if not session_id:
            return
        try:
            # F() expressions: two concurrent operations on one session would
            # otherwise both read the same bytes_sent and one increment would
            # be lost. Also avoids fetching the row just to add to it.
            from django.db.models import F

            size = len(json.dumps(payload or {}).encode('utf-8'))
            GarlicSession.objects.filter(
                session_id=session_id, user=user, status='active'
            ).update(
                bytes_sent=F('bytes_sent') + size,
                messages_sent=F('messages_sent') + 1,
                last_activity_at=timezone.now(),
            )
        except Exception:
            logger.exception("Failed to record dark protocol traffic accounting")
    
    def _create_operation_bundle(
        self,
        session: GarlicSession,
        operation: str,
        payload: Dict[str, Any],
    ) -> TrafficBundle:
        """Create an encrypted traffic bundle for an operation."""
        import json
        
        # Serialize payload
        payload_bytes = json.dumps({
            'op': operation,
            'data': payload,
            'ts': timezone.now().isoformat(),
        }).encode()
        
        # Encrypt with garlic layers
        encrypted = self.garlic_router.encrypt_payload(
            session=session,
            payload=payload_bytes,
        )
        
        # Get next sequence number
        last_bundle = TrafficBundle.objects.filter(
            session=session
        ).order_by('-sequence_number').first()
        
        sequence = (last_bundle.sequence_number + 1) if last_bundle else 1
        
        # Create bundle
        bundle = TrafficBundle.objects.create(
            session=session,
            bundle_type='real',
            encrypted_payload=encrypted,
            payload_size=len(encrypted),
            sequence_number=sequence,
        )
        
        return bundle
    
    # =========================================================================
    # Network Health
    # =========================================================================
    
    def get_network_status(self) -> Dict[str, Any]:
        """Report network status, led by whether anonymity is actually active.

        ``anonymity_active`` is the headline and it comes from Tor alone. The
        local relay counts that follow describe the in-process obfuscation
        layer and are reported under their own key so they cannot be mistaken
        for - or rendered as - the health of an anonymity network.
        """
        now = timezone.now()
        five_min_ago = now - timedelta(minutes=5)
        capability = self.tor.get_capability()

        relays = self.tor.get_circuit_relays() if capability.anonymity_active else []
        circuits = len({relay['circuit_id'] for relay in relays if relay.get('circuit_id')})

        # Local obfuscation-layer records. Kept, clearly labelled, because the
        # cover-traffic scheduler reads them; they describe rows in this
        # database, not peers reachable over a network.
        total_nodes = DarkProtocolNode.objects.count()
        active_nodes = DarkProtocolNode.objects.filter(
            status='active',
            last_seen_at__gt=five_min_ago,
        ).count()

        recent_health = NetworkHealth.objects.filter(
            checked_at__gt=five_min_ago,
            is_reachable=True,
        )
        avg_latency = 0
        if recent_health.exists():
            avg_latency = sum(h.latency_ms for h in recent_health) / recent_health.count()

        return {
            'anonymity_active': capability.anonymity_active,
            'transport': 'tor_v3_onion',
            'status': 'active' if capability.anonymity_active else 'unavailable',
            'reason': capability.reason,
            'onion_address': capability.onion_address if capability.anonymity_active else None,
            'tor': capability.to_dict(),
            'circuits': {
                'built': circuits,
                'relays': len(relays),
            },
            'obfuscation_layer': {
                'local_records': total_nodes,
                'active_records': active_nodes,
                'average_latency_ms': int(avg_latency),
                'note': 'In-process cover-traffic layer. Not an anonymity network.',
            },
            'checked_at': now.isoformat(),
        }

    def get_available_nodes(self, node_type: str = None) -> List[Dict[str, Any]]:
        """Relays of the live Tor circuits carrying this deployment's traffic.

        This used to return rows from ``DarkProtocolNode``, which described
        relays that did not exist anywhere - a fabricated network topology
        rendered as though it were real infrastructure. It now returns what Tor
        reports, and an empty list when there is no live circuit to describe.

        ``node_type`` filters by circuit position ('guard', 'middle',
        'rendezvous'). There is no 'exit' position: onion-service circuits end
        at a rendezvous point inside Tor, which is what makes "no exit node" a
        true statement about this deployment rather than a slogan.
        """
        relays = self.tor.get_circuit_relays()
        if node_type:
            wanted = str(node_type).strip().lower()
            relays = [relay for relay in relays if relay.get('position') == wanted]
        return relays


# =============================================================================
# Service Singleton
# =============================================================================

_dark_protocol_service = None


def get_dark_protocol_service() -> DarkProtocolService:
    """Get the dark protocol service singleton."""
    global _dark_protocol_service
    if _dark_protocol_service is None:
        _dark_protocol_service = DarkProtocolService()
    return _dark_protocol_service


# =============================================================================
# Relay Node Mode
# =============================================================================

def run_relay_node():
    """
    Run as a Dark Protocol relay node.
    
    This function is called when running in Docker relay mode.
    It starts the relay services and health check endpoint.
    """
    import os
    import time
    import threading
    from http.server import HTTPServer, BaseHTTPRequestHandler
    
    node_type = os.environ.get('DARK_PROTOCOL_NODE_TYPE', 'relay')
    region = os.environ.get('DARK_PROTOCOL_REGION', 'local')
    public_address = os.environ.get('DARK_PROTOCOL_PUBLIC_ADDRESS', '')
    max_circuits = int(os.environ.get('DARK_PROTOCOL_MAX_CIRCUITS', '1000'))
    
    logger.info(f"Starting Dark Protocol relay node ({node_type}) in region {region}")
    
    # Register this node
    node_id = secrets.token_hex(32)
    fingerprint = secrets.token_hex(32)
    
    try:
        node, created = DarkProtocolNode.objects.get_or_create(
            fingerprint=fingerprint,
            defaults={
                'node_id': node_id,
                'node_type': node_type,
                'status': 'active',
                'region': region,
                'public_key': secrets.token_bytes(32),
                'signing_key': secrets.token_bytes(64),
                'ip_address': public_address or '127.0.0.1',  # nosec B104
                'port': 9090,
                'max_circuits': max_circuits,
            }
        )
        
        if created:
            logger.info(f"Registered new node: {node_id[:16]}...")
        else:
            node.status = 'active'
            node.save(update_fields=['status', 'last_seen_at'])
            logger.info(f"Reactivated existing node: {node.node_id[:16]}...")
        
    except Exception as e:
        logger.error(f"Failed to register node: {e}")
        return
    
    # Health check handler
    class HealthHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == '/health':
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                response = {
                    'status': 'healthy',
                    'node_id': node_id[:16],
                    'node_type': node_type,
                    'region': region,
                    'circuits': node.current_circuits if node else 0,
                    'max_circuits': max_circuits,
                }
                import json
                self.wfile.write(json.dumps(response).encode())
            elif self.path == '/metrics':
                self.send_response(200)
                self.send_header('Content-type', 'text/plain')
                self.end_headers()
                metrics = (
                    f"# HELP dark_protocol_circuits Current active circuits\n"
                    f"# TYPE dark_protocol_circuits gauge\n"
                    f"dark_protocol_circuits {node.current_circuits if node else 0}\n"
                    f"# HELP dark_protocol_uptime_ratio Node uptime percentage\n"
                    f"# TYPE dark_protocol_uptime_ratio gauge\n"
                    f"dark_protocol_uptime_ratio {node.uptime_percentage if node else 0}\n"
                )
                self.wfile.write(metrics.encode())
            else:
                self.send_response(404)
                self.end_headers()
        
        def log_message(self, format, *args):
            pass  # Suppress access logs
    
    # Start health check server in background
    def start_health_server():
        health_server = HTTPServer(('127.0.0.1', 9091), HealthHandler)
        logger.info("Health check server started on port 9091")
        health_server.serve_forever()
    
    health_thread = threading.Thread(target=start_health_server, daemon=True)
    health_thread.start()
    
    # Main relay loop - heartbeat and circuit handling
    logger.info(f"Relay node {node_id[:16]}... is now accepting circuits on port 9090")
    
    heartbeat_interval = 30  # seconds
    
    try:
        while True:
            # Update heartbeat
            try:
                DarkProtocolNode.objects.filter(node_id=node_id).update(
                    last_seen_at=timezone.now(),
                )
            except Exception as e:
                logger.warning(f"Heartbeat update failed: {e}")
            
            # Sleep until next heartbeat
            time.sleep(heartbeat_interval)
            
    except KeyboardInterrupt:
        logger.info("Relay node shutting down...")
        
        # Mark node as inactive
        try:
            DarkProtocolNode.objects.filter(node_id=node_id).update(
                status='maintenance'
            )
        except Exception:
            pass
        
        logger.info("Relay node stopped")

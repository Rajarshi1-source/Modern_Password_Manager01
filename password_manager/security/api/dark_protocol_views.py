"""
Dark Protocol API Views
=======================

REST API endpoints for the Dark Protocol anonymous vault access network.

Endpoints:
- /config/: User configuration (GET/PUT)
- /session/: Establish garlic session (POST)
- /nodes/: Available network nodes (GET)
- /route/: Request anonymous route (POST)
- /health/: Network health status (GET)
- /vault-proxy/: Proxied vault operations (POST)

@author Password Manager Team
@created 2026-02-02
"""

import logging
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.throttling import AnonRateThrottle, UserRateThrottle

from django.utils import timezone

from ..models.dark_protocol_models import (
    GarlicSession,
    DarkProtocolConfig,
    RoutingPath,
)
from ..services.dark_protocol_service import get_dark_protocol_service
from ..services.tor_service import get_tor_service

logger = logging.getLogger(__name__)


# =============================================================================
# Throttling
# =============================================================================

class DarkProtocolRateThrottle(UserRateThrottle):
    """Rate limiting for dark protocol endpoints."""
    rate = '100/minute'


class DarkProtocolSessionThrottle(UserRateThrottle):
    """Stricter throttling for session establishment."""
    rate = '10/minute'


class DarkProtocolPingThrottle(AnonRateThrottle):
    """Own bucket for the unauthenticated onion ping.

    The ping is the only AllowAny view here, so under the shared user-scoped
    throttle its requests were keyed by the Tor daemon's IP — the same key every
    other anonymous Dark Protocol request would use. Isolating it keeps an
    operator diagnostic from consuming a bucket real traffic needs, and vice
    versa.

    Note this is NOT about the self-check misreporting: check_onion_reachable()
    treats ANY HTTP status as proof the rendezvous completed, so even a 429
    correctly reads as reachable.
    """
    scope = 'dark_protocol_ping'
    rate = '120/minute'


# =============================================================================
# Configuration View
# =============================================================================

class DarkProtocolConfigView(APIView):
    """
    User's dark protocol configuration.
    
    GET: Retrieve current configuration
    PUT: Update configuration
    """
    permission_classes = [IsAuthenticated]
    throttle_classes = [DarkProtocolRateThrottle]
    
    def get(self, request):
        """Get user's dark protocol configuration."""
        service = get_dark_protocol_service()
        config = service.get_or_create_config(request.user)
        
        return Response({
            'is_enabled': config.is_enabled,
            'auto_enable_on_threat': config.auto_enable_on_threat,
            'preferred_regions': config.preferred_regions,
            'min_hops': config.min_hops,
            'max_hops': config.max_hops,
            'cover_traffic_enabled': config.cover_traffic_enabled,
            'cover_traffic_intensity': config.cover_traffic_intensity,
            'session_timeout_minutes': config.session_timeout_minutes,
            'auto_path_rotation': config.auto_path_rotation,
            'path_rotation_interval_minutes': config.path_rotation_interval_minutes,
            'use_bridge_nodes': config.use_bridge_nodes,
            'require_verified_nodes': config.require_verified_nodes,
            'created_at': config.created_at.isoformat(),
            'updated_at': config.updated_at.isoformat(),
        })
    
    def put(self, request):
        """Update user's dark protocol configuration."""
        service = get_dark_protocol_service()
        
        allowed_fields = [
            'is_enabled', 'auto_enable_on_threat', 'preferred_regions',
            'min_hops', 'max_hops', 'cover_traffic_enabled',
            'cover_traffic_intensity', 'session_timeout_minutes',
            'auto_path_rotation', 'path_rotation_interval_minutes',
            'use_bridge_nodes', 'require_verified_nodes',
        ]
        
        update_data = {
            k: v for k, v in request.data.items()
            if k in allowed_fields
        }
        
        # Validate hop counts
        if 'min_hops' in update_data:
            if not 2 <= update_data['min_hops'] <= 7:
                return Response(
                    {'error': 'min_hops must be between 2 and 7'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        if 'max_hops' in update_data:
            if not 2 <= update_data['max_hops'] <= 7:
                return Response(
                    {'error': 'max_hops must be between 2 and 7'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        # Validate intensity
        if 'cover_traffic_intensity' in update_data:
            intensity = update_data['cover_traffic_intensity']
            if not 0.0 <= intensity <= 1.0:
                return Response(
                    {'error': 'cover_traffic_intensity must be between 0.0 and 1.0'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        config = service.update_config(request.user, **update_data)
        
        logger.info(f"Updated dark protocol config for user {request.user.id}")
        
        return Response({
            'message': 'Configuration updated',
            'is_enabled': config.is_enabled,
            'updated_at': config.updated_at.isoformat(),
        })


# =============================================================================
# Session View
# =============================================================================

class DarkProtocolSessionView(APIView):
    """
    Garlic routing session management.
    
    GET: Get active session info
    POST: Establish new session
    DELETE: Terminate session
    """
    permission_classes = [IsAuthenticated]
    throttle_classes = [DarkProtocolSessionThrottle]
    
    def get(self, request):
        """Get user's active session."""
        service = get_dark_protocol_service()
        session = service.get_active_session(request.user)
        
        if not session:
            return Response({
                'has_active_session': False,
            })
        
        return Response({
            'has_active_session': True,
            'session_id': session.session_id,
            'status': session.status,
            'path_length': session.path_length,
            'created_at': session.created_at.isoformat(),
            'expires_at': session.expires_at.isoformat(),
            'bytes_sent': session.bytes_sent,
            'bytes_received': session.bytes_received,
            'messages_sent': session.messages_sent,
            'messages_received': session.messages_received,
            'is_verified': session.is_verified,
        })
    
    def post(self, request):
        """Establish a new garlic routing session."""
        service = get_dark_protocol_service()
        
        # Check for existing active session
        existing = service.get_active_session(request.user)
        if existing:
            return Response({
                'message': 'Active session already exists',
                'session_id': existing.session_id,
                'expires_at': existing.expires_at.isoformat(),
            }, status=status.HTTP_409_CONFLICT)
        
        # Get parameters
        hop_count = request.data.get('hop_count')
        preferred_regions = request.data.get('preferred_regions')
        
        # Establish session
        result = service.establish_session(
            user=request.user,
            hop_count=hop_count,
            preferred_regions=preferred_regions,
        )
        
        if not result.success:
            return Response({
                'error': result.error_message,
            }, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        
        logger.info(f"Established dark protocol session for user {request.user.id}")
        
        return Response({
            'message': 'Session established',
            'session_id': result.session_id,
            'path_length': result.path_length,
            'estimated_latency_ms': result.estimated_latency_ms,
        }, status=status.HTTP_201_CREATED)
    
    def delete(self, request):
        """Terminate active session."""
        session_id = request.data.get('session_id')
        
        if not session_id:
            # Terminate any active session
            service = get_dark_protocol_service()
            session = service.get_active_session(request.user)
            if session:
                session_id = session.session_id
            else:
                return Response({
                    'message': 'No active session to terminate',
                })
        
        service = get_dark_protocol_service()
        success = service.terminate_session(session_id, request.user)
        
        if success:
            return Response({
                'message': 'Session terminated',
                'session_id': session_id,
            })
        else:
            return Response({
                'error': 'Failed to terminate session',
            }, status=status.HTTP_400_BAD_REQUEST)


# =============================================================================
# Nodes View
# =============================================================================

class DarkProtocolNodesView(APIView):
    """
    Relays of the live Tor circuits.

    GET: List circuit relays (filtered by position if specified)

    Previously this listed ``DarkProtocolNode`` rows - a table of relays that
    existed only in the database. It now reports what Tor reports, and an empty
    list with a reason when there is no live circuit.
    """
    permission_classes = [IsAuthenticated]
    throttle_classes = [DarkProtocolRateThrottle]

    def get(self, request):
        """Get the relays currently carrying this deployment's Tor circuits."""
        node_type = request.query_params.get('type')

        service = get_dark_protocol_service()
        capability = service.tor.get_capability()
        nodes = service.get_available_nodes(node_type=node_type)

        # Distribution over real circuit positions. Onion-service circuits have
        # no exit hop, so 'exit' is deliberately absent from this breakdown.
        distribution = {'guard': 0, 'middle': 0, 'rendezvous': 0}
        for node in nodes:
            position = node.get('position')
            if position in distribution:
                distribution[position] += 1

        return Response({
            'nodes': nodes,
            'total_count': len(nodes),
            'distribution': distribution,
            'anonymity_active': capability.anonymity_active,
            'reason': capability.reason,
        })


# =============================================================================
# Route View
# =============================================================================

class DarkProtocolRouteView(APIView):
    """
    Anonymous routing path management.
    
    GET: Get user's active routes
    POST: Request new route
    """
    permission_classes = [IsAuthenticated]
    throttle_classes = [DarkProtocolRateThrottle]
    
    def get(self, request):
        """Get user's active routing paths."""
        paths = RoutingPath.objects.filter(
            user=request.user,
            is_active=True,
            expires_at__gt=timezone.now(),
        )
        
        return Response({
            'paths': [
                {
                    'path_id': path.path_id,
                    'hop_count': path.hop_count,
                    'estimated_latency_ms': path.estimated_latency_ms,
                    'is_primary': path.is_primary,
                    'created_at': path.created_at.isoformat(),
                    'expires_at': path.expires_at.isoformat(),
                    'times_used': path.times_used,
                    'reliability': path.reliability,
                }
                for path in paths
            ],
            'count': paths.count(),
        })
    
    def post(self, request):
        """Request a new routing path."""
        service = get_dark_protocol_service()
        
        path = service.rotate_path(request.user)
        
        if not path:
            return Response({
                'error': 'Unable to create routing path',
            }, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        
        return Response({
            'message': 'Route created',
            'path_id': path.path_id,
            'hop_count': path.hop_count,
            'expires_at': path.expires_at.isoformat(),
        }, status=status.HTTP_201_CREATED)


# =============================================================================
# Health View
# =============================================================================

class DarkProtocolHealthView(APIView):
    """
    Anonymity transport health.

    GET: Report whether anonymous access is actually available.

    "Active" here means Tor is bootstrapped, has a live circuit, and our onion
    descriptor is published - all verified against the running daemon. Anything
    less reports Unavailable with a reason. It never reports active on the
    strength of the in-process cover-traffic layer.

    ``?verify=1`` additionally performs the loopback self-check, fetching our
    own .onion through the Tor SOCKS proxy. That is the end-to-end proof the
    service is reachable, and it is opt-in because a cold descriptor fetch can
    take tens of seconds.

    The self-check is restricted to staff: it blocks a request worker for up
    to SELF_CHECK_TIMEOUT_SECONDS, and the result is cached, so letting any
    authenticated user force a cache miss would hand them a cheap way to tie
    up workers. It is an operator diagnostic, not user-facing data.
    """
    permission_classes = [IsAuthenticated]
    throttle_classes = [DarkProtocolRateThrottle]

    def get(self, request):
        """Get anonymity transport health."""
        service = get_dark_protocol_service()
        health_status = service.get_network_status()

        wants_verify = str(request.query_params.get('verify', '')).lower() in ('1', 'true', 'yes')
        if wants_verify and getattr(request.user, 'is_staff', False):
            health_status['self_check'] = service.tor.check_onion_reachable().to_dict()

        return Response(health_status)


# =============================================================================
# Capabilities View
# =============================================================================

class DarkProtocolCapabilitiesView(APIView):
    """
    What Dark Protocol can genuinely do right now.

    GET: Capability report for the client to gate its UI on.

    The client renders anonymity features only when this says the capability is
    present, so that a deployment without Tor shows Unavailable rather than a
    dashboard implying protection that is not there.
    """
    permission_classes = [IsAuthenticated]
    throttle_classes = [DarkProtocolRateThrottle]

    def get(self, request):
        try:
            service = get_dark_protocol_service()
            return Response(service.get_capabilities(request=request))
        except Exception:
            # Keep the traceback; a capability probe failing is an operational
            # signal, and the client must not receive an exception string.
            logger.exception("Error getting dark protocol capabilities")
            return Response(
                {'error': 'internal_error'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


# =============================================================================
# Onion Ping View
# =============================================================================

class DarkProtocolOnionPingView(APIView):
    """
    Reachability target for the onion loopback self-check.

    Unauthenticated by necessity: the self-check runs as the deployment, not as
    a user. It answers ONLY on the onion ingress and 404s everywhere else, so
    it adds no clearnet surface and cannot be used to fingerprint the
    deployment from the open internet.
    """
    permission_classes = [AllowAny]
    throttle_classes = [DarkProtocolPingThrottle]

    def get(self, request):
        if not get_tor_service().request_is_onion_ingress(request):
            return Response(status=status.HTTP_404_NOT_FOUND)
        return Response({'ok': True})


# =============================================================================
# Vault Proxy View
# =============================================================================

class DarkProtocolVaultProxyView(APIView):
    """
    Vault operations executed under a verified anonymous ingress.

    POST: Execute a vault operation, but only for a request that actually
    arrived over the onion service.

    There is no clearnet fallback. If Tor is down, or the request came in over
    clearnet, this refuses and says so - it does not serve the operation while
    letting the client believe it was anonymous.
    """
    permission_classes = [IsAuthenticated]
    throttle_classes = [DarkProtocolRateThrottle]

    # Refusal reasons map to distinct statuses so a client can tell an outage
    # from a routing mistake it can fix by using the .onion address.
    ERROR_STATUS = {
        'tor_unavailable': status.HTTP_503_SERVICE_UNAVAILABLE,
        'clearnet_ingress_refused': status.HTTP_403_FORBIDDEN,
        'unsupported_operation': status.HTTP_400_BAD_REQUEST,
        'invalid_payload': status.HTTP_400_BAD_REQUEST,
        'route_unavailable': status.HTTP_503_SERVICE_UNAVAILABLE,
        'operation_failed': status.HTTP_500_INTERNAL_SERVER_ERROR,
    }

    def post(self, request):
        """Execute a vault operation over the anonymous ingress."""
        if not isinstance(request.data, dict):
            # A top-level JSON array or scalar has no .get(), which would
            # otherwise surface as an AttributeError -> 500 instead of the
            # 400 a malformed client request should get.
            return Response({
                'error': 'Request body must be an object',
                'error_code': 'invalid_payload',
            }, status=status.HTTP_400_BAD_REQUEST)

        operation = request.data.get('operation')
        payload = request.data.get('payload', {})
        session_id = request.data.get('session_id')

        if not operation:
            return Response({
                'error': 'Operation is required',
                'error_code': 'operation_required',
            }, status=status.HTTP_400_BAD_REQUEST)

        if not isinstance(payload, dict):
            # An explicit `"payload": null` or a list would otherwise reach the
            # dispatcher and fail deeper, away from the input that caused it.
            return Response({
                'error': 'payload must be an object',
                'error_code': 'invalid_payload',
            }, status=status.HTTP_400_BAD_REQUEST)

        service = get_dark_protocol_service()
        result = service.proxy_vault_operation(
            user=request.user,
            operation=operation,
            payload=payload,
            session_id=session_id,
            request=request,
        )

        if not result.success:
            body = {
                'error': result.error_message,
                'error_code': result.error_code,
                'operation_id': result.operation_id,
            }
            if result.error_code == 'clearnet_ingress_refused':
                # Hand back where anonymous access actually lives, so the
                # refusal is actionable rather than just a wall.
                capability = service.tor.get_capability()
                body['onion_address'] = capability.onion_address
            if result.error_code == 'vault_error':
                # The vault view answered with an error; pass its own status
                # and body through rather than relabelling it.
                return Response({
                    'success': False,
                    'error_code': 'vault_error',
                    'operation_id': result.operation_id,
                    'data': result.response_data,
                }, status=result.status_code or status.HTTP_400_BAD_REQUEST)
            return Response(
                body,
                status=self.ERROR_STATUS.get(
                    result.error_code, status.HTTP_500_INTERNAL_SERVER_ERROR
                ),
            )

        # Always 200 for the envelope, with the vault's own status as a field.
        # Echoing the inner status broke vault_delete: the vault's destroy()
        # answers 204 No Content, and a 204 carrying an envelope body is a
        # contradiction — clients (including response.json() in
        # darkProtocolService) read 204 as "no body" and would see nothing.
        return Response({
            'success': True,
            'operation_id': result.operation_id,
            'status_code': result.status_code,
            'data': result.response_data,
            'latency_ms': result.latency_ms,
        })


# =============================================================================
# Statistics View
# =============================================================================

class DarkProtocolStatsView(APIView):
    """
    User's dark protocol usage statistics.
    
    GET: Get usage statistics
    """
    permission_classes = [IsAuthenticated]
    throttle_classes = [DarkProtocolRateThrottle]
    
    def get(self, request):
        """Get user's dark protocol statistics."""
        user = request.user
        
        # Session stats
        total_sessions = GarlicSession.objects.filter(user=user).count()
        active_sessions = GarlicSession.objects.filter(
            user=user, status='active', expires_at__gt=timezone.now()
        ).count()
        
        # Traffic stats
        from django.db.models import Sum
        traffic = GarlicSession.objects.filter(user=user).aggregate(
            total_sent=Sum('bytes_sent'),
            total_received=Sum('bytes_received'),
            total_messages=Sum('messages_sent'),
        )
        
        # Path stats
        total_paths = RoutingPath.objects.filter(user=user).count()
        active_paths = RoutingPath.objects.filter(
            user=user, is_active=True, expires_at__gt=timezone.now()
        ).count()
        
        return Response({
            'sessions': {
                'total': total_sessions,
                'active': active_sessions,
            },
            'traffic': {
                'bytes_sent': traffic['total_sent'] or 0,
                'bytes_received': traffic['total_received'] or 0,
                'messages_sent': traffic['total_messages'] or 0,
            },
            'paths': {
                'total_created': total_paths,
                'currently_active': active_paths,
            },
        })

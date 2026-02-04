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
from rest_framework.permissions import IsAuthenticated
from rest_framework.throttling import UserRateThrottle

from django.db import transaction
from django.utils import timezone

from ..models.dark_protocol_models import (
    DarkProtocolNode,
    GarlicSession,
    DarkProtocolConfig,
    RoutingPath,
    NetworkHealth,
)
from ..services.dark_protocol_service import get_dark_protocol_service

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
    Available network nodes.
    
    GET: List available nodes (filtered by type if specified)
    """
    permission_classes = [IsAuthenticated]
    throttle_classes = [DarkProtocolRateThrottle]
    
    def get(self, request):
        """Get available network nodes."""
        node_type = request.query_params.get('type')
        
        service = get_dark_protocol_service()
        nodes = service.get_available_nodes(node_type=node_type)
        
        # Get node distribution
        distribution = {}
        for nt, _ in [('entry', 'Entry'), ('relay', 'Relay'), ('destination', 'Destination'), ('bridge', 'Bridge')]:
            distribution[nt] = DarkProtocolNode.objects.filter(
                node_type=nt, status='active'
            ).count()
        
        return Response({
            'nodes': nodes,
            'total_count': len(nodes),
            'distribution': distribution,
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
    Network health status.
    
    GET: Get overall network health and metrics
    """
    permission_classes = [IsAuthenticated]
    throttle_classes = [DarkProtocolRateThrottle]
    
    def get(self, request):
        """Get network health status."""
        service = get_dark_protocol_service()
        health_status = service.get_network_status()
        
        # Get recent health checks
        recent_checks = NetworkHealth.objects.filter(
            checked_at__gte=timezone.now() - timezone.timedelta(minutes=5)
        ).select_related('node')
        
        reachable = recent_checks.filter(is_reachable=True).count()
        total_checks = recent_checks.count()
        
        return Response({
            **health_status,
            'recent_checks': {
                'total': total_checks,
                'reachable': reachable,
                'reachability_rate': reachable / total_checks if total_checks > 0 else 0,
            },
        })


# =============================================================================
# Vault Proxy View
# =============================================================================

class DarkProtocolVaultProxyView(APIView):
    """
    Proxied vault operations through dark protocol.
    
    POST: Execute vault operation through anonymous network
    """
    permission_classes = [IsAuthenticated]
    throttle_classes = [DarkProtocolRateThrottle]
    
    def post(self, request):
        """Execute a vault operation through dark protocol."""
        operation = request.data.get('operation')
        payload = request.data.get('payload', {})
        session_id = request.data.get('session_id')
        
        if not operation:
            return Response({
                'error': 'Operation is required',
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Validate operation
        valid_operations = [
            'vault_list', 'vault_get', 'vault_create', 'vault_update',
            'vault_delete', 'vault_search', 'vault_sync',
        ]
        
        if operation not in valid_operations:
            return Response({
                'error': f'Invalid operation. Valid: {", ".join(valid_operations)}',
            }, status=status.HTTP_400_BAD_REQUEST)
        
        service = get_dark_protocol_service()
        result = service.proxy_vault_operation(
            user=request.user,
            operation=operation,
            payload=payload,
            session_id=session_id,
        )
        
        if not result.success:
            return Response({
                'error': result.error_message,
                'operation_id': result.operation_id,
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        return Response({
            'success': True,
            'operation_id': result.operation_id,
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

"""
Dead Drop API Views
====================

REST API endpoints for mesh dead drop operations.

Endpoints:
- /api/mesh/deaddrops/ - List/create dead drops
- /api/mesh/deaddrops/<id>/ - Detail/delete dead drop
- /api/mesh/deaddrops/<id>/collect/ - Collect fragments
- /api/mesh/deaddrops/<id>/cancel/ - Cancel dead drop
- /api/mesh/nodes/ - List/register mesh nodes
- /api/mesh/nodes/<id>/ - Node detail/update
- /api/mesh/nodes/nearby/ - Find nearby nodes
- /api/mesh/nfc/challenge/ - Get NFC challenge
- /api/mesh/nfc/verify/ - Verify NFC response

@author Password Manager Team
@created 2026-01-22
"""

from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from django.db import transaction
from django.utils import timezone

from ..models import (
    DeadDrop,
    DeadDropFragment,
    MeshNode,
    NFCBeacon,
    DeadDropAccess,
)
from ..serializers import (
    DeadDropSerializer,
    DeadDropCreateSerializer,
    DeadDropDetailSerializer,
    MeshNodeSerializer,
    MeshNodeRegisterSerializer,
    LocationClaimSerializer,
    CollectFragmentsSerializer,
    DistributionStatusSerializer,
    NFCChallengeSerializer,
    NFCVerifySerializer,
)
from ..services import (
    FragmentDistributionService,
    LocationVerificationService,
    MeshCryptoService,
)
from ..services.location_verification_service import (
    LocationClaim,
    VerificationMethod,
    VerificationResult,
)


# =============================================================================
# Dead Drop Views
# =============================================================================

class DeadDropListView(APIView):
    """
    List user's dead drops or create a new one.
    
    GET: List all dead drops owned by current user
    POST: Create a new dead drop with secret
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """List dead drops."""
        dead_drops = DeadDrop.objects.filter(owner=request.user).order_by('-created_at')
        
        # Optional filtering
        status_filter = request.query_params.get('status')
        if status_filter:
            dead_drops = dead_drops.filter(status=status_filter)
        
        active_only = request.query_params.get('active')
        if active_only == 'true':
            dead_drops = dead_drops.filter(is_active=True)
        
        serializer = DeadDropSerializer(dead_drops, many=True)
        return Response({
            'count': dead_drops.count(),
            'dead_drops': serializer.data
        })
    
    def post(self, request):
        """Create a new dead drop."""
        serializer = DeadDropCreateSerializer(
            data=request.data,
            context={'request': request}
        )
        
        if serializer.is_valid():
            dead_drop = serializer.save()
            return Response({
                'message': 'Dead drop created successfully',
                'dead_drop': DeadDropDetailSerializer(dead_drop).data
            }, status=status.HTTP_201_CREATED)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class DeadDropDetailView(APIView):
    """
    Get, update, or delete a specific dead drop.
    
    GET: Get dead drop details including distribution status
    DELETE: Cancel and delete dead drop
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request, drop_id):
        """Get dead drop details."""
        dead_drop = get_object_or_404(DeadDrop, id=drop_id, owner=request.user)
        serializer = DeadDropDetailSerializer(dead_drop)
        return Response(serializer.data)
    
    def delete(self, request, drop_id):
        """Cancel and delete dead drop."""
        dead_drop = get_object_or_404(DeadDrop, id=drop_id, owner=request.user)
        
        if dead_drop.status == 'collected':
            return Response({
                'error': 'Cannot delete an already collected dead drop'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Mark as cancelled and deactivate
        dead_drop.status = 'cancelled'
        dead_drop.is_active = False
        dead_drop.save()
        
        # Mark all fragments as unavailable
        dead_drop.fragments.update(is_available=False)
        
        return Response({
            'message': 'Dead drop cancelled successfully'
        })


class DeadDropDistributeView(APIView):
    """
    Redistribute fragments for a dead drop.
    
    POST: Trigger redistribution to mesh nodes
    """
    permission_classes = [IsAuthenticated]
    
    def post(self, request, drop_id):
        """Redistribute fragments."""
        dead_drop = get_object_or_404(DeadDrop, id=drop_id, owner=request.user)
        
        if dead_drop.status in ['collected', 'cancelled']:
            return Response({
                'error': f'Cannot redistribute {dead_drop.status} dead drop'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        service = FragmentDistributionService()
        rebalanced = service.rebalance_fragments(dead_drop)
        
        return Response({
            'message': f'Rebalanced {rebalanced} fragments',
            'status': service.get_distribution_status(dead_drop)
        })


class DeadDropCollectView(APIView):
    """
    Collect fragments from a dead drop.
    
    POST: Attempt to collect fragments at current location
    """
    permission_classes = [IsAuthenticated]
    
    def post(self, request, drop_id):
        """Collect fragments."""
        dead_drop = get_object_or_404(DeadDrop, id=drop_id)
        
        # Validate request
        serializer = CollectFragmentsSerializer(data={
            'dead_drop_id': str(drop_id),
            'location': request.data.get('location', {}),
            'access_code': request.data.get('access_code', '')
        })
        
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        location_data = serializer.validated_data['location']
        
        # Check access code if required
        if dead_drop.access_code_hash:
            import hashlib
            provided_code = serializer.validated_data.get('access_code', '')
            code_hash = hashlib.blake2b(provided_code.encode(), digest_size=32).hexdigest()
            if code_hash != dead_drop.access_code_hash:
                self._log_access(dead_drop, request, location_data, 'access_code_wrong', 0)
                return Response({
                    'error': 'Invalid access code'
                }, status=status.HTTP_403_FORBIDDEN)
        
        # Verify location
        location_service = LocationVerificationService()
        location_claim = LocationClaim(
            latitude=float(location_data['latitude']),
            longitude=float(location_data['longitude']),
            accuracy_meters=float(location_data.get('accuracy_meters', 10)),
            ble_nodes=location_data.get('ble_nodes', []),
            wifi_fingerprint=location_data.get('wifi_fingerprint'),
            nfc_response=location_data.get('nfc_response'),
        )
        
        # Get required BLE node IDs
        required_nodes = list(
            dead_drop.fragments.filter(node__isnull=False)
            .values_list('node_id', flat=True)
        )
        
        verification = location_service.verify_location(
            claimed=location_claim,
            target_lat=float(dead_drop.latitude),
            target_lon=float(dead_drop.longitude),
            radius_meters=dead_drop.radius_meters,
            user_id=str(request.user.id),
            require_ble=dead_drop.require_ble_verification,
            require_nfc=dead_drop.require_nfc_tap,
            min_ble_nodes=dead_drop.min_ble_nodes_required,
        )
        
        # Handle verification failure
        if verification.result == VerificationResult.SPOOFING_DETECTED:
            self._log_access(dead_drop, request, location_data, 'spoofing_detected', 0)
            return Response({
                'error': 'GPS spoofing detected',
                'details': verification.message
            }, status=status.HTTP_403_FORBIDDEN)
        
        if verification.result != VerificationResult.SUCCESS:
            result_code = 'location_failed'
            if not verification.ble_verified:
                result_code = 'ble_failed'
            if dead_drop.require_nfc_tap and not verification.nfc_verified:
                result_code = 'nfc_failed'
            
            self._log_access(dead_drop, request, location_data, result_code, 0)
            return Response({
                'error': 'Location verification failed',
                'details': verification.message,
                'confidence': verification.confidence,
                'gps_verified': verification.gps_verified,
                'ble_verified': verification.ble_verified,
                'nfc_verified': verification.nfc_verified,
            }, status=status.HTTP_403_FORBIDDEN)
        
        # Collect fragments
        distribution_service = FragmentDistributionService()
        visible_node_ids = [n.get('id') for n in location_data.get('ble_nodes', [])]
        
        collection = distribution_service.collect_fragments(
            dead_drop=dead_drop,
            accessor=request.user,
            visible_node_ids=visible_node_ids
        )
        
        # Log access attempt
        result_code = 'success' if collection.success else 'insufficient_fragments'
        self._log_access(
            dead_drop, request, location_data, result_code,
            collection.fragments_collected,
            verification
        )
        
        if collection.success:
            return Response({
                'message': 'Secret reconstructed successfully',
                'secret': collection.reconstructed_secret.decode() if collection.reconstructed_secret else None,
                'fragments_collected': collection.fragments_collected,
            })
        else:
            return Response({
                'error': 'Failed to collect enough fragments',
                'fragments_collected': collection.fragments_collected,
                'fragments_needed': collection.fragments_needed,
                'errors': collection.errors
            }, status=status.HTTP_400_BAD_REQUEST)
    
    def _log_access(self, dead_drop, request, location_data, result, fragments_collected, verification=None):
        """Log access attempt."""
        DeadDropAccess.objects.create(
            dead_drop=dead_drop,
            accessor=request.user,
            claimed_latitude=location_data['latitude'],
            claimed_longitude=location_data['longitude'],
            claimed_accuracy_meters=location_data.get('accuracy_meters'),
            gps_verified=verification.gps_verified if verification else False,
            ble_verified=verification.ble_verified if verification else False,
            nfc_verified=verification.nfc_verified if verification else False,
            ble_nodes_detected=len(location_data.get('ble_nodes', [])),
            ble_node_ids=[n.get('id') for n in location_data.get('ble_nodes', [])],
            velocity_check_passed=verification.velocity_check_passed if verification else True,
            result=result,
            fragments_collected=fragments_collected,
            reconstruction_successful=(result == 'success'),
            access_ip=self._get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', '')[:500],
        )
    
    def _get_client_ip(self, request):
        """Get client IP address."""
        x_forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded:
            return x_forwarded.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR')


class DeadDropCancelView(APIView):
    """Cancel a dead drop."""
    permission_classes = [IsAuthenticated]
    
    def post(self, request, drop_id):
        """Cancel dead drop."""
        dead_drop = get_object_or_404(DeadDrop, id=drop_id, owner=request.user)
        
        if dead_drop.status == 'collected':
            return Response({
                'error': 'Cannot cancel collected dead drop'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        dead_drop.status = 'cancelled'
        dead_drop.is_active = False
        dead_drop.save()
        
        # Invalidate fragments
        dead_drop.fragments.update(is_available=False)
        
        return Response({
            'message': 'Dead drop cancelled'
        })


# =============================================================================
# Mesh Node Views
# =============================================================================

class MeshNodeListView(APIView):
    """
    List mesh nodes or register a new one.
    
    GET: List user's mesh nodes
    POST: Register a new mesh node
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """List nodes."""
        nodes = MeshNode.objects.filter(owner=request.user).order_by('-last_seen')
        serializer = MeshNodeSerializer(nodes, many=True)
        return Response({
            'count': nodes.count(),
            'nodes': serializer.data
        })
    
    def post(self, request):
        """Register a new node."""
        serializer = MeshNodeRegisterSerializer(
            data=request.data,
            context={'request': request}
        )
        
        if serializer.is_valid():
            node = serializer.save()
            return Response({
                'message': 'Node registered successfully',
                'node': MeshNodeSerializer(node).data
            }, status=status.HTTP_201_CREATED)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class MeshNodeDetailView(APIView):
    """
    Get, update, or delete a mesh node.
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request, node_id):
        """Get node details."""
        node = get_object_or_404(MeshNode, id=node_id, owner=request.user)
        serializer = MeshNodeSerializer(node)
        return Response(serializer.data)
    
    def patch(self, request, node_id):
        """Update node."""
        node = get_object_or_404(MeshNode, id=node_id, owner=request.user)
        
        # Only allow certain fields to be updated
        allowed_fields = ['device_name', 'is_available_for_storage', 'max_fragments']
        update_data = {k: v for k, v in request.data.items() if k in allowed_fields}
        
        for key, value in update_data.items():
            setattr(node, key, value)
        node.save()
        
        return Response(MeshNodeSerializer(node).data)
    
    def delete(self, request, node_id):
        """Unregister node."""
        node = get_object_or_404(MeshNode, id=node_id, owner=request.user)
        
        # Check for active fragments
        active_fragments = node.stored_fragments.filter(is_collected=False).count()
        if active_fragments > 0:
            return Response({
                'error': f'Node has {active_fragments} active fragments. Rebalance first.'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        node.delete()
        return Response({'message': 'Node unregistered'})


class NearbyNodesView(APIView):
    """
    Find nearby mesh nodes.
    
    GET: Find nodes near a location
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """Find nearby nodes."""
        lat = request.query_params.get('lat')
        lon = request.query_params.get('lon')
        radius_km = float(request.query_params.get('radius', 10))
        
        if not lat or not lon:
            return Response({
                'error': 'lat and lon parameters required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        lat = float(lat)
        lon = float(lon)
        
        # Simple bounding box filter (not accurate for large areas)
        # 1 degree ≈ 111km
        delta = radius_km / 111
        
        nodes = MeshNode.objects.filter(
            is_online=True,
            is_available_for_storage=True,
            last_known_latitude__range=(lat - delta, lat + delta),
            last_known_longitude__range=(lon - delta, lon + delta),
        ).exclude(owner=request.user)
        
        serializer = MeshNodeSerializer(nodes, many=True)
        return Response({
            'count': nodes.count(),
            'nodes': serializer.data
        })


class NodePingView(APIView):
    """
    Update node online status.
    
    POST: Ping to indicate node is online
    """
    permission_classes = [IsAuthenticated]
    
    def post(self, request, node_id):
        """Ping node."""
        node = get_object_or_404(MeshNode, id=node_id, owner=request.user)
        
        node.is_online = True
        node.last_seen = timezone.now()
        
        # Update location if provided
        lat = request.data.get('latitude')
        lon = request.data.get('longitude')
        if lat and lon:
            node.update_location(float(lat), float(lon))
        else:
            node.save()
        
        return Response({'status': 'ok'})


# =============================================================================
# NFC Beacon Views
# =============================================================================

class NFCChallengeView(APIView):
    """
    Get NFC challenge for verification.
    """
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        """Get NFC challenge."""
        serializer = NFCChallengeSerializer(data=request.data)
        
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        beacon = get_object_or_404(NFCBeacon, id=serializer.validated_data['beacon_id'])
        challenge = beacon.rotate_challenge()
        
        return Response({
            'challenge': challenge,
            'expires_at': beacon.challenge_expires_at
        })


class NFCVerifyView(APIView):
    """
    Verify NFC tap response.
    """
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        """Verify NFC response."""
        serializer = NFCVerifySerializer(data=request.data)
        
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        beacon = get_object_or_404(NFCBeacon, id=serializer.validated_data['beacon_id'])
        
        if beacon.verify_tap(serializer.validated_data['response']):
            beacon.last_tapped = timezone.now()
            beacon.tap_count += 1
            beacon.save()
            
            return Response({
                'verified': True,
                'message': 'NFC verification successful'
            })
        else:
            return Response({
                'verified': False,
                'error': 'Invalid NFC response'
            }, status=status.HTTP_403_FORBIDDEN)

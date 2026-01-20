"""
Entanglement API Views
======================

REST API endpoints for quantum entanglement-inspired key distribution.

Endpoints:
- POST /initiate/ - Start device pairing
- POST /verify/ - Complete pairing with verification code
- POST /sync/ - Synchronize keys
- POST /rotate/ - Rotate entangled keys
- GET /status/<pair_id>/ - Get pair status
- GET /entropy/<pair_id>/ - Get entropy analysis
- POST /revoke/ - Instant revocation
- DELETE /<pair_id>/ - Delete pairing
- GET /pairs/ - List user's pairs
"""

import base64
import logging

from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404

from security.models import EntangledDevicePair, UserDevice
from security.services.quantum_entanglement_service import (
    QuantumEntanglementService,
    quantum_entanglement_service,
)
from security.serializers.entanglement_serializers import (
    InitiatePairingSerializer,
    PairingSessionSerializer,
    VerifyPairingSerializer,
    PairingCompleteSerializer,
    SyncRequestSerializer,
    SyncResultSerializer,
    RotateKeysSerializer,
    EntropyAnalysisSerializer,
    RevokeRequestSerializer,
    RevocationResultSerializer,
    EntangledDevicePairSerializer,
    PairStatusSerializer,
    UserPairsListSerializer,
)

logger = logging.getLogger(__name__)


class InitiatePairingView(APIView):
    """Initiate device pairing process."""
    
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        """
        Start pairing between two devices.
        
        Returns session ID and verification code to display on both devices.
        """
        serializer = InitiatePairingSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        try:
            session = quantum_entanglement_service.initiate_pairing(
                user_id=request.user.id,
                device_a_id=str(serializer.validated_data['device_a_id']),
                device_b_id=str(serializer.validated_data['device_b_id']),
            )
            
            response_serializer = PairingSessionSerializer(session.to_dict())
            return Response(response_serializer.data, status=status.HTTP_201_CREATED)
            
        except ValueError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.error(f"Pairing initiation failed: {e}")
            return Response(
                {'error': 'Failed to initiate pairing'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class VerifyPairingView(APIView):
    """Verify and complete device pairing."""
    
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        """
        Complete pairing after verification code confirmation.
        
        Requires device B's lattice public key.
        """
        serializer = VerifyPairingSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        try:
            # Decode public key from base64
            public_key_bytes = base64.b64decode(
                serializer.validated_data['device_b_public_key']
            )
            
            result = quantum_entanglement_service.complete_pairing(
                session_id=serializer.validated_data['session_id'],
                verification_code=serializer.validated_data['verification_code'],
                device_b_public_key=public_key_bytes,
            )
            
            return Response(result, status=status.HTTP_200_OK)
            
        except ValueError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.error(f"Pairing verification failed: {e}")
            return Response(
                {'error': 'Failed to complete pairing'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class SyncKeysView(APIView):
    """Synchronize keys between paired devices."""
    
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        """
        Sync keys and get current pool state.
        """
        serializer = SyncRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        result = quantum_entanglement_service.synchronize_keys(
            pair_id=str(serializer.validated_data['pair_id']),
            requesting_device_id=str(serializer.validated_data['device_id']),
        )
        
        response_serializer = SyncResultSerializer(result.to_dict())
        
        if result.success:
            return Response(response_serializer.data, status=status.HTTP_200_OK)
        else:
            return Response(
                response_serializer.data,
                status=status.HTTP_400_BAD_REQUEST
            )


class RotateKeysView(APIView):
    """Rotate entangled keys with fresh randomness."""
    
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        """
        Rotate keys to new generation.
        """
        serializer = RotateKeysSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        result = quantum_entanglement_service.rotate_entangled_keys(
            pair_id=str(serializer.validated_data['pair_id']),
            initiating_device_id=str(serializer.validated_data['device_id']),
        )
        
        response_serializer = SyncResultSerializer(result.to_dict())
        
        if result.success:
            return Response(response_serializer.data, status=status.HTTP_200_OK)
        else:
            return Response(
                response_serializer.data,
                status=status.HTTP_400_BAD_REQUEST
            )


class PairStatusView(APIView):
    """Get status of an entangled pair."""
    
    permission_classes = [IsAuthenticated]
    
    def get(self, request, pair_id):
        """
        Get detailed status of an entangled pair.
        """
        # Verify ownership
        pair = get_object_or_404(
            EntangledDevicePair,
            id=pair_id,
            user=request.user
        )
        
        pair_status = quantum_entanglement_service.get_pair_status(str(pair_id))
        
        if pair_status:
            serializer = PairStatusSerializer(pair_status.to_dict())
            return Response(serializer.data, status=status.HTTP_200_OK)
        else:
            return Response(
                {'error': 'Pair not found'},
                status=status.HTTP_404_NOT_FOUND
            )


class EntropyAnalysisView(APIView):
    """Get entropy analysis for eavesdropping detection."""
    
    permission_classes = [IsAuthenticated]
    
    def get(self, request, pair_id):
        """
        Analyze entropy and check for anomalies.
        """
        # Verify ownership
        pair = get_object_or_404(
            EntangledDevicePair,
            id=pair_id,
            user=request.user
        )
        
        report = quantum_entanglement_service.detect_eavesdropping(str(pair_id))
        
        serializer = EntropyAnalysisSerializer(report.to_dict())
        return Response(serializer.data, status=status.HTTP_200_OK)


class RevokeView(APIView):
    """Instantly revoke an entangled pair."""
    
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        """
        Revoke pairing immediately.
        
        Used when a device is compromised or user suspects tampering.
        """
        serializer = RevokeRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        # Verify ownership
        pair = get_object_or_404(
            EntangledDevicePair,
            id=serializer.validated_data['pair_id'],
            user=request.user
        )
        
        result = quantum_entanglement_service.revoke_instantly(
            pair_id=str(serializer.validated_data['pair_id']),
            compromised_device_id=str(serializer.validated_data.get('compromised_device_id', '')),
            reason=serializer.validated_data.get('reason', 'Manual revocation'),
        )
        
        response_serializer = RevocationResultSerializer(result.to_dict())
        return Response(response_serializer.data, status=status.HTTP_200_OK)


class DeletePairView(APIView):
    """Delete an entangled pair."""
    
    permission_classes = [IsAuthenticated]
    
    def delete(self, request, pair_id):
        """
        Delete a pairing (must be revoked first or pending).
        """
        pair = get_object_or_404(
            EntangledDevicePair,
            id=pair_id,
            user=request.user
        )
        
        if pair.status == 'active':
            return Response(
                {'error': 'Cannot delete active pair. Revoke first.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        pair.delete()
        
        return Response(
            {'message': 'Pair deleted successfully'},
            status=status.HTTP_200_OK
        )


class UserPairsView(APIView):
    """List all entangled pairs for user."""
    
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """
        Get all user's entangled pairs.
        """
        pairs = quantum_entanglement_service.get_user_pairs(request.user.id)
        
        config = quantum_entanglement_service.config
        max_pairs = config.get('MAX_PAIRS_PER_USER', 5)
        
        data = {
            'pairs': [p.to_dict() for p in pairs],
            'total_count': len(pairs),
            'max_allowed': max_pairs,
        }
        
        serializer = UserPairsListSerializer(data)
        return Response(serializer.data, status=status.HTTP_200_OK)


class PairDetailView(APIView):
    """Get full details of an entangled pair."""
    
    permission_classes = [IsAuthenticated]
    
    def get(self, request, pair_id):
        """
        Get complete pair information including pool and events.
        """
        pair = get_object_or_404(
            EntangledDevicePair.objects.select_related(
                'device_a', 'device_b', 'sharedrandomnesspool'
            ).prefetch_related('sync_events'),
            id=pair_id,
            user=request.user
        )
        
        serializer = EntangledDevicePairSerializer(pair)
        return Response(serializer.data, status=status.HTTP_200_OK)

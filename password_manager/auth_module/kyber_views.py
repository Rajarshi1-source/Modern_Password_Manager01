"""
Django views for the post-quantum KEM API.

The server-side keypair, encrypt, decrypt and batch endpoints are retired
(410, see server_side_kem_retired). What remains:

    GET    /api/kyber/status/             - Algorithm and backend status
    GET    /api/kyber/public-key/         - The user's stored public key
    DELETE /api/kyber/keypair/invalidate/ - Deactivate the user's keypair
    GET    /api/kyber/metrics/            - Performance metrics (staff only)
    POST   /api/kyber/metrics/reset/      - Reset metrics (staff only)
"""

import base64
import logging

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from .models import KyberKeyPair
from .services.parallel_kyber import get_parallel_kyber
from .services.kyber_cache import get_kyber_cache
from .services.kyber_crypto import get_crypto_status
from .services.optimized_ntt import get_optimized_ntt

logger = logging.getLogger(__name__)


# =============================================================================
# API VIEWS
# =============================================================================

# Server-side KEM endpoints (keypair, keypair/batch, encrypt, decrypt,
# batch/encrypt) are retired and routed to ``server_side_kem_retired``
# (auth_module/urls.py). They broke the zero-knowledge model: the server
# generated and stored users' KEM private keys unwrapped, took vault plaintext
# and even a client's private key in the request, and decrypted on its own
# side. They were also never reachable: each is an ``async def`` under DRF's
# ``@api_view``, which does not await coroutines, so every call returned 500.
# No client calls them, and their implementations (and the server-held
# private-key column they wrote) are deleted. Post-quantum protection for
# vault data belongs on the client.
SERVER_SIDE_KEM_RETIRED_MESSAGE = (
    "Server-side KEM operations are retired: the server must not hold users' "
    "private keys or see plaintext. Use client-side encryption."
)


@api_view(['GET', 'POST', 'DELETE'])
@permission_classes([IsAuthenticated])
def server_side_kem_retired(request):
    return Response(
        {'status': 'error', 'code': 'server_side_kem_retired',
         'message': SERVER_SIDE_KEM_RETIRED_MESSAGE},
        status=status.HTTP_410_GONE,
    )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_kyber_status(request):
    """
    Get Kyber cryptography status.
    
    Response:
        {
            "status": "success",
            "crypto_status": {
                "liboqs_available": true,
                "using_real_pqc": true,
                "algorithm": "ML-KEM-768",
                ...
            },
            "user_keypair": {
                "has_keypair": true,
                "key_version": 1,
                ...
            }
        }
    """
    try:
        user = request.user
        crypto_status = get_crypto_status()
        
        # Get user's keypair info
        keypair = KyberKeyPair.objects.filter(
            user=user, 
            is_active=True
        ).order_by('-key_version').first()
        
        user_keypair = None
        if keypair:
            user_keypair = {
                'has_keypair': True,
                'key_version': keypair.key_version,
                'algorithm': keypair.algorithm,
                'public_key_size': len(keypair.public_key),
                'created_at': keypair.created_at.isoformat(),
                'encryption_count': keypair.encryption_count,
                'decryption_count': keypair.decryption_count
            }
        else:
            user_keypair = {'has_keypair': False}
        
        return Response({
            'status': 'success',
            'crypto_status': crypto_status,
            'user_keypair': user_keypair
        })
        
    except Exception as e:
        logger.error(f"Status error: {e}")
        return Response({
            'status': 'error',
            'message': 'internal_error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAdminUser])  # global metrics: staff only
def get_kyber_metrics(request):
    """
    Get Kyber performance metrics.
    
    Response:
        {
            "status": "success",
            "parallel_metrics": {...},
            "cache_metrics": {...},
            "ntt_metrics": {...}
        }
    """
    try:
        kyber_ops = get_parallel_kyber()
        cache_manager = get_kyber_cache()
        ntt = get_optimized_ntt()
        
        return Response({
            'status': 'success',
            'parallel_metrics': kyber_ops.get_metrics(),
            'cache_metrics': cache_manager.get_metrics(),
            'ntt_metrics': ntt.get_metrics()
        })
        
    except Exception as e:
        logger.error(f"Metrics error: {e}")
        return Response({
            'status': 'error',
            'message': 'internal_error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAdminUser])  # global metrics: staff only
def reset_kyber_metrics(request):
    """Reset all Kyber performance metrics."""
    try:
        kyber_ops = get_parallel_kyber()
        cache_manager = get_kyber_cache()
        ntt = get_optimized_ntt()
        
        kyber_ops.reset_metrics()
        cache_manager.reset_metrics()
        ntt.reset_metrics()
        
        return Response({
            'status': 'success',
            'message': 'All metrics reset'
        })
        
    except Exception as e:
        logger.error(f"Metrics reset error: {e}")
        return Response({
            'status': 'error',
            'message': 'internal_error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_user_public_key(request):
    """
    Get the authenticated user's public key.
    
    Response:
        {
            "status": "success",
            "public_key": "base64...",
            "key_version": 1,
            "algorithm": "ML-KEM-768"
        }
    """
    try:
        user = request.user
        
        # Check cache first
        cache_manager = get_kyber_cache()
        cached = cache_manager.get_cached_public_key_entry(user.id)

        if cached:
            cached_key, cached_algorithm = cached
            keypair = KyberKeyPair.objects.filter(
                user=user,
                is_active=True
            ).order_by('-key_version').first()

            return Response({
                'status': 'success',
                'public_key': base64.b64encode(cached_key).decode('utf-8'),
                'key_version': keypair.key_version if keypair else 0,
                'algorithm': cached_algorithm,
                'cached': True
            })
        
        # Get from database
        keypair = KyberKeyPair.objects.filter(
            user=user, 
            is_active=True
        ).order_by('-key_version').first()
        
        if not keypair:
            return Response({
                'status': 'error',
                'message': 'No keypair found. Generate a keypair first.'
            }, status=status.HTTP_404_NOT_FOUND)
        
        public_key = bytes(keypair.public_key)
        cache_manager.cache_public_key(user.id, public_key, algorithm=keypair.algorithm)

        return Response({
            'status': 'success',
            'public_key': base64.b64encode(public_key).decode('utf-8'),
            'key_version': keypair.key_version,
            'algorithm': keypair.algorithm,
            'cached': False
        })
        
    except Exception as e:
        logger.error(f"Get public key error: {e}")
        return Response({
            'status': 'error',
            'message': 'internal_error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def invalidate_keypair(request):
    """
    Invalidate (deactivate) user's current keypair.
    
    This is typically done before generating a new keypair.
    """
    try:
        user = request.user
        
        # Deactivate all active keypairs
        updated = KyberKeyPair.objects.filter(
            user=user, 
            is_active=True
        ).update(is_active=False)
        
        # Clear cache
        cache_manager = get_kyber_cache()
        cache_manager.invalidate_public_key(user.id)
        
        return Response({
            'status': 'success',
            'message': f'Invalidated {updated} keypair(s)',
            'deactivated_count': updated
        })
        
    except Exception as e:
        logger.error(f"Invalidate keypair error: {e}")
        return Response({
            'status': 'error',
            'message': 'internal_error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


"""
Async Django Views for CRYSTALS-Kyber API

Provides REST API endpoints for Kyber cryptographic operations:
- Keypair generation
- Encryption/Decryption
- Batch operations
- Metrics and status

All views use async/await for maximum performance with ASGI.

Usage:
    POST /api/kyber/keypair/      - Generate new keypair
    POST /api/kyber/encrypt/      - Encrypt data
    POST /api/kyber/decrypt/      - Decrypt data
    POST /api/kyber/batch/        - Batch operations
    GET  /api/kyber/status/       - Get algorithm status
    GET  /api/kyber/metrics/      - Get performance metrics
"""

import asyncio
import base64
import json
import logging
import time
from typing import Optional

from django.http import JsonResponse
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.utils import timezone

from asgiref.sync import sync_to_async

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from .models import KyberKeyPair, KyberEncryptedPassword, KyberSession
from .services.parallel_kyber import ParallelKyberOperations, get_parallel_kyber
from .services.kyber_cache import KyberCacheManager, get_kyber_cache
from .services.kyber_crypto import get_crypto_status, production_kyber
from .services.optimized_ntt import get_optimized_ntt
from django.db.models import Max

logger = logging.getLogger(__name__)


# =============================================================================
# ASYNC UTILITY FUNCTIONS
# =============================================================================

@sync_to_async
def get_user_keypair(user, version: int = None, create_if_missing: bool = False):
    """
    Get user's Kyber keypair from database.
    
    Args:
        user: Django User instance
        version: Specific key version (default: latest active)
        create_if_missing: Create new keypair if none exists
        
    Returns:
        KyberKeyPair instance or None
    """
    try:
        query = KyberKeyPair.objects.filter(user=user, is_active=True)
        
        if version:
            query = query.filter(key_version=version)
        
        keypair = query.order_by('-key_version').first()
        
        if keypair is None and create_if_missing:
            # Generate new keypair
            kyber_ops = get_parallel_kyber()
            new_keypair = kyber_ops.generate_keypair()
            
            # Get next version number
            max_version = KyberKeyPair.objects.filter(user=user).aggregate(
                max_ver=Max('key_version')
            )['max_ver'] or 0
            
            keypair = KyberKeyPair.objects.create(
                user=user,
                public_key=base64.b64decode(new_keypair['public_key']),
                private_key=base64.b64decode(new_keypair['private_key']),
                key_version=max_version + 1,
                algorithm='Kyber768',
                security_level=3
            )
            
            logger.info(f"Created new Kyber keypair v{keypair.key_version} for {user.username}")
        
        return keypair
        
    except Exception as e:
        logger.error(f"Error getting user keypair: {e}")
        return None


@sync_to_async
def store_keypair_db(user, public_key: bytes, private_key: bytes):
    """Store keypair in database."""
    try:
        # Get next version
        from django.db.models import Max
        max_version = KyberKeyPair.objects.filter(user=user).aggregate(
            max_ver=Max('key_version')
        )['max_ver'] or 0
        
        # Deactivate old keypairs
        KyberKeyPair.objects.filter(user=user, is_active=True).update(is_active=False)
        
        # Create new keypair
        keypair = KyberKeyPair.objects.create(
            user=user,
            public_key=public_key,
            private_key=private_key,
            key_version=max_version + 1,
            is_active=True
        )
        
        return keypair
        
    except Exception as e:
        logger.error(f"Error storing keypair: {e}")
        raise


@sync_to_async
def store_encrypted_password_db(
    user,
    service_name: str,
    username: str,
    encrypted_data: dict,
    keypair_id=None,
    url: str = None
):
    """Store encrypted password in database."""
    try:
        password_entry = KyberEncryptedPassword.objects.create(
            user=user,
            keypair_id=keypair_id,
            service_name=service_name,
            username=username,
            url=url,
            kyber_ciphertext=base64.b64decode(encrypted_data['kyber_ciphertext']),
            aes_ciphertext=base64.b64decode(encrypted_data['aes_ciphertext']),
            nonce=base64.b64decode(encrypted_data['nonce']),
            algorithm=encrypted_data.get('algorithm', 'Kyber768-AES256-GCM'),
            encryption_version=int(encrypted_data.get('version', '1').split('.')[0])
        )
        
        return password_entry
        
    except Exception as e:
        logger.error(f"Error storing encrypted password: {e}")
        raise


# =============================================================================
# API VIEWS
# =============================================================================

@api_view(['POST'])
@permission_classes([IsAuthenticated])
async def generate_keypair_view(request):
    """
    Generate a new Kyber keypair for the authenticated user.
    
    Request Body (optional):
        {
            "algorithm": "Kyber768",  // Kyber512, Kyber768, Kyber1024
            "store": true,            // Store in database
            "cache": true             // Cache public key
        }
    
    Response:
        {
            "status": "success",
            "public_key": "base64...",
            "public_key_size": 1184,
            "key_version": 1,
            "algorithm": "Kyber768",
            "is_quantum_resistant": true,
            "generation_time_ms": 2.5
        }
    """
    start_time = time.perf_counter()
    
    try:
        user = request.user
        data = request.data
        
        store_in_db = data.get('store', True)
        cache_key = data.get('cache', True)
        algorithm = data.get('algorithm', 'Kyber768')
        
        # Check cache first
        cache_manager = get_kyber_cache()
        cached_key = cache_manager.get_cached_public_key(user.id)
        
        if cached_key and not data.get('force_new', False):
            return Response({
                'status': 'success',
                'public_key': base64.b64encode(cached_key).decode('utf-8'),
                'public_key_size': len(cached_key),
                'cached': True,
                'message': 'Returned cached public key'
            })
        
        # Generate new keypair
        kyber_ops = get_parallel_kyber()
        keypair = kyber_ops.generate_keypair()
        
        public_key_bytes = base64.b64decode(keypair['public_key'])
        private_key_bytes = base64.b64decode(keypair['private_key'])
        
        key_version = 1
        
        # Store in database
        if store_in_db:
            db_keypair = await store_keypair_db(user, public_key_bytes, private_key_bytes)
            key_version = db_keypair.key_version
        
        # Cache public key
        if cache_key:
            cache_manager.cache_public_key(user.id, public_key_bytes)
        
        elapsed = time.perf_counter() - start_time
        
        return Response({
            'status': 'success',
            'public_key': keypair['public_key'],
            'public_key_size': keypair['public_key_size'],
            'key_version': key_version,
            'algorithm': algorithm,
            'is_quantum_resistant': keypair['is_real_pqc'],
            'generation_time_ms': elapsed * 1000,
            'cached': False
        })
        
    except Exception as e:
        logger.error(f"Keypair generation error: {e}")
        return Response({
            'status': 'error',
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
async def encrypt_view(request):
    """
    Encrypt data using Kyber hybrid encryption.
    
    Request Body:
        {
            "plaintext": "string or base64",
            "public_key": "base64...",  // Optional, uses user's key if not provided
            "associated_data": "base64...",  // Optional AAD
            "encode_plaintext": true  // If plaintext is string, encode to bytes
        }
    
    Response:
        {
            "status": "success",
            "kyber_ciphertext": "base64...",
            "aes_ciphertext": "base64...",
            "nonce": "base64...",
            "algorithm": "Kyber768-AES256-GCM",
            "encryption_time_ms": 1.2
        }
    """
    start_time = time.perf_counter()
    
    try:
        user = request.user
        data = request.data
        
        # Get plaintext
        plaintext = data.get('plaintext')
        if not plaintext:
            return Response({
                'status': 'error',
                'message': 'plaintext is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Encode plaintext if string
        if data.get('encode_plaintext', True) and isinstance(plaintext, str):
            plaintext_bytes = plaintext.encode('utf-8')
        else:
            plaintext_bytes = base64.b64decode(plaintext)
        
        # Get public key
        public_key_b64 = data.get('public_key')
        
        if public_key_b64:
            public_key = base64.b64decode(public_key_b64)
        else:
            # Use user's cached or stored key
            cache_manager = get_kyber_cache()
            public_key = cache_manager.get_cached_public_key(user.id)
            
            if not public_key:
                # Get from database
                keypair = await get_user_keypair(user, create_if_missing=True)
                if keypair:
                    public_key = bytes(keypair.public_key)
                    cache_manager.cache_public_key(user.id, public_key)
                else:
                    return Response({
                        'status': 'error',
                        'message': 'No public key available. Generate a keypair first.'
                    }, status=status.HTTP_400_BAD_REQUEST)
        
        # Get AAD if provided
        aad = None
        if data.get('associated_data'):
            aad = base64.b64decode(data['associated_data'])
        
        # Encrypt
        kyber_ops = get_parallel_kyber()
        encrypted = kyber_ops.encrypt_data(plaintext_bytes, public_key, aad)
        
        elapsed = time.perf_counter() - start_time
        
        return Response({
            'status': 'success',
            **encrypted,
            'encryption_time_ms': elapsed * 1000
        })
        
    except Exception as e:
        logger.error(f"Encryption error: {e}")
        return Response({
            'status': 'error',
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
async def decrypt_view(request):
    """
    Decrypt data using Kyber hybrid decryption.
    
    Request Body:
        {
            "kyber_ciphertext": "base64...",
            "aes_ciphertext": "base64...",
            "nonce": "base64...",
            "private_key": "base64...",  // Optional, uses user's key if not provided
            "associated_data": "base64...",  // Optional AAD
            "decode_plaintext": true  // Return plaintext as string
        }
    
    Response:
        {
            "status": "success",
            "plaintext": "decrypted string or base64",
            "decryption_time_ms": 1.5
        }
    """
    start_time = time.perf_counter()
    
    try:
        user = request.user
        data = request.data
        
        # Validate required fields
        required_fields = ['kyber_ciphertext', 'aes_ciphertext', 'nonce']
        for field in required_fields:
            if field not in data:
                return Response({
                    'status': 'error',
                    'message': f'{field} is required'
                }, status=status.HTTP_400_BAD_REQUEST)
        
        # Get private key
        private_key_b64 = data.get('private_key')
        
        if private_key_b64:
            private_key = base64.b64decode(private_key_b64)
        else:
            # Get from database
            keypair = await get_user_keypair(user)
            if keypair:
                private_key = bytes(keypair.private_key)
            else:
                return Response({
                    'status': 'error',
                    'message': 'No private key available'
                }, status=status.HTTP_400_BAD_REQUEST)
        
        # Get AAD if provided
        aad = None
        if data.get('associated_data'):
            aad = base64.b64decode(data['associated_data'])
        
        # Prepare encrypted data dict
        encrypted_data = {
            'kyber_ciphertext': data['kyber_ciphertext'],
            'aes_ciphertext': data['aes_ciphertext'],
            'nonce': data['nonce'],
            'aad_hash': data.get('aad_hash')
        }
        
        # Decrypt
        kyber_ops = get_parallel_kyber()
        plaintext_bytes = kyber_ops.decrypt_data(encrypted_data, private_key, aad)
        
        # Decode if requested
        if data.get('decode_plaintext', True):
            try:
                plaintext = plaintext_bytes.decode('utf-8')
            except UnicodeDecodeError:
                plaintext = base64.b64encode(plaintext_bytes).decode('utf-8')
        else:
            plaintext = base64.b64encode(plaintext_bytes).decode('utf-8')
        
        elapsed = time.perf_counter() - start_time
        
        return Response({
            'status': 'success',
            'plaintext': plaintext,
            'decryption_time_ms': elapsed * 1000
        })
        
    except Exception as e:
        logger.error(f"Decryption error: {e}")
        return Response({
            'status': 'error',
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
async def batch_encrypt_view(request):
    """
    Batch encrypt multiple items.
    
    Request Body:
        {
            "items": [
                {
                    "plaintext": "...",
                    "service_name": "Google",
                    "username": "user@example.com"
                },
                ...
            ],
            "store": true  // Store in database
        }
    
    Response:
        {
            "status": "success",
            "results": [...],
            "total_items": 10,
            "successful": 10,
            "failed": 0,
            "total_time_ms": 15.5
        }
    """
    start_time = time.perf_counter()
    
    try:
        user = request.user
        data = request.data
        
        items = data.get('items', [])
        store_in_db = data.get('store', True)
        
        if not items:
            return Response({
                'status': 'error',
                'message': 'items array is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Get user's public key
        cache_manager = get_kyber_cache()
        public_key = cache_manager.get_cached_public_key(user.id)
        
        if not public_key:
            keypair = await get_user_keypair(user, create_if_missing=True)
            if keypair:
                public_key = bytes(keypair.public_key)
                cache_manager.cache_public_key(user.id, public_key)
            else:
                return Response({
                    'status': 'error',
                    'message': 'No public key available'
                }, status=status.HTTP_400_BAD_REQUEST)
        
        # Prepare batch data
        public_keys = [public_key] * len(items)
        messages = [item['plaintext'].encode('utf-8') for item in items]
        
        # Batch encrypt
        kyber_ops = get_parallel_kyber()
        encrypted_results = await kyber_ops.batch_encrypt(public_keys, messages)
        
        # Store in database if requested
        if store_in_db:
            keypair = await get_user_keypair(user)
            for i, (item, encrypted) in enumerate(zip(items, encrypted_results)):
                if 'error' not in encrypted:
                    try:
                        await store_encrypted_password_db(
                            user=user,
                            service_name=item.get('service_name', f'Item {i}'),
                            username=item.get('username', ''),
                            encrypted_data=encrypted,
                            keypair_id=keypair.id if keypair else None,
                            url=item.get('url')
                        )
                    except Exception as e:
                        logger.error(f"Error storing item {i}: {e}")
        
        elapsed = time.perf_counter() - start_time
        
        successful = sum(1 for r in encrypted_results if 'error' not in r)
        
        return Response({
            'status': 'success',
            'results': encrypted_results,
            'total_items': len(items),
            'successful': successful,
            'failed': len(items) - successful,
            'total_time_ms': elapsed * 1000,
            'avg_time_per_item_ms': (elapsed * 1000) / len(items)
        })
        
    except Exception as e:
        logger.error(f"Batch encryption error: {e}")
        return Response({
            'status': 'error',
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
async def batch_keygen_view(request):
    """
    Generate multiple keypairs in parallel.
    
    Request Body:
        {
            "count": 5,
            "algorithm": "Kyber768"
        }
    
    Response:
        {
            "status": "success",
            "keypairs": [...],
            "count": 5,
            "total_time_ms": 10.5
        }
    """
    start_time = time.perf_counter()
    
    try:
        data = request.data
        count = min(data.get('count', 1), 100)  # Limit to 100
        
        kyber_ops = get_parallel_kyber()
        keypairs = await kyber_ops.parallel_keygen(count)
        
        # Remove private keys from response (security)
        public_keypairs = [
            {
                'public_key': kp['public_key'],
                'public_key_size': kp['public_key_size'],
                'timestamp': kp['timestamp'],
                'is_real_pqc': kp['is_real_pqc']
            }
            for kp in keypairs
        ]
        
        elapsed = time.perf_counter() - start_time
        
        return Response({
            'status': 'success',
            'keypairs': public_keypairs,
            'count': len(keypairs),
            'total_time_ms': elapsed * 1000,
            'avg_time_per_key_ms': (elapsed * 1000) / count
        })
        
    except Exception as e:
        logger.error(f"Batch keygen error: {e}")
        return Response({
            'status': 'error',
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


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
                "algorithm": "Kyber768",
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
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
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
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
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
            'message': str(e)
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
            "algorithm": "Kyber768"
        }
    """
    try:
        user = request.user
        
        # Check cache first
        cache_manager = get_kyber_cache()
        cached_key = cache_manager.get_cached_public_key(user.id)
        
        if cached_key:
            keypair = KyberKeyPair.objects.filter(
                user=user, 
                is_active=True
            ).order_by('-key_version').first()
            
            return Response({
                'status': 'success',
                'public_key': base64.b64encode(cached_key).decode('utf-8'),
                'key_version': keypair.key_version if keypair else 0,
                'algorithm': keypair.algorithm if keypair else 'Kyber768',
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
        cache_manager.cache_public_key(user.id, public_key)
        
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
            'message': str(e)
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
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


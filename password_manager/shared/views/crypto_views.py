"""
Cryptography API Views

Provides endpoints for client-side encryption key management
and server-side encryption utilities
"""

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from shared.crypto import (
    XChaCha20EncryptionService,
    derive_key_from_password,
    derive_key_from_master_key,
    EncryptionError,
    DecryptionError
)
import base64
import logging

logger = logging.getLogger(__name__)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def generate_encryption_key(request):
    """
    Generate a new XChaCha20-Poly1305 encryption key
    
    POST /api/crypto/generate-key/
    Returns:
        {
            "key": "base64_encoded_key",
            "algorithm": "XChaCha20-Poly1305",
            "key_size": 32
        }
    """
    try:
        key = XChaCha20EncryptionService.generate_key()
        
        return Response({
            'key': base64.b64encode(key).decode('utf-8'),
            'algorithm': 'XChaCha20-Poly1305',
            'key_size': len(key)
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Key generation failed: {e}")
        return Response({
            'error': 'Failed to generate encryption key'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def derive_key(request):
    """
    Derive encryption key from password or master key
    
    POST /api/crypto/derive-key/
    Body:
        {
            "method": "password" | "master_key",
            "password": "user_password",  // for password method
            "salt": "base64_salt",        // for password method
            "iterations": 100000,          // optional, for password method
            "master_key": "base64_key",    // for master_key method
            "context": "folder_id_123",    // for master_key method
            "key_id": "optional_id"        // for master_key method
        }
    """
    try:
        method = request.data.get('method')
        
        if method == 'password':
            password = request.data.get('password')
            salt = base64.b64decode(request.data.get('salt'))
            iterations = request.data.get('iterations', 100000)
            
            if not password or not salt:
                return Response({
                    'error': 'Password and salt are required'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            derived_key = derive_key_from_password(password, salt, iterations)
            
        elif method == 'master_key':
            master_key = base64.b64decode(request.data.get('master_key'))
            context = request.data.get('context')
            key_id = request.data.get('key_id')
            
            if not master_key or not context:
                return Response({
                    'error': 'Master key and context are required'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            derived_key = derive_key_from_master_key(master_key, context, key_id)
            
        else:
            return Response({
                'error': 'Invalid derivation method'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        return Response({
            'derived_key': base64.b64encode(derived_key).decode('utf-8'),
            'algorithm': 'XChaCha20-Poly1305',
            'method': method
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Key derivation failed: {e}")
        return Response({
            'error': f'Failed to derive key: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def test_encryption(request):
    """
    Test encryption/decryption with XChaCha20-Poly1305
    Useful for client-side validation
    
    POST /api/crypto/test/
    Body:
        {
            "operation": "encrypt" | "decrypt",
            "key": "base64_encoded_key",
            "data": "data_to_encrypt" | {"ciphertext": "...", "nonce": "..."},
            "associated_data": "optional_aad"
        }
    """
    try:
        operation = request.data.get('operation')
        key = base64.b64decode(request.data.get('key'))
        data = request.data.get('data')
        associated_data = request.data.get('associated_data')
        
        service = XChaCha20EncryptionService(key)
        
        if operation == 'encrypt':
            result = service.encrypt(data, associated_data)
            return Response({
                'result': result,
                'operation': 'encrypt'
            }, status=status.HTTP_200_OK)
            
        elif operation == 'decrypt':
            plaintext = service.decrypt(data, associated_data)
            return Response({
                'result': plaintext.decode('utf-8') if isinstance(plaintext, bytes) else plaintext,
                'operation': 'decrypt'
            }, status=status.HTTP_200_OK)
            
        else:
            return Response({
                'error': 'Invalid operation'
            }, status=status.HTTP_400_BAD_REQUEST)
        
    except (EncryptionError, DecryptionError) as e:
        return Response({
            'error': str(e)
        }, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        logger.error(f"Encryption test failed: {e}")
        return Response({
            'error': f'Test failed: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_crypto_info(request):
    """
    Get information about available cryptography features
    
    GET /api/crypto/info/
    """
    return Response({
        'algorithms': {
            'xchacha20_poly1305': {
                'name': 'XChaCha20-Poly1305',
                'type': 'AEAD',
                'key_size': 32,
                'nonce_size': 24,
                'tag_size': 16,
                'features': [
                    'Extended nonce (192-bit)',
                    'Authenticated encryption',
                    'Associated data support',
                    'Stream encryption support'
                ]
            }
        },
        'key_derivation': {
            'pbkdf2': {
                'name': 'PBKDF2-HMAC-SHA256',
                'recommended_iterations': 100000,
                'salt_size': 16
            },
            'hkdf': {
                'name': 'HKDF-SHA256',
                'context_required': True
            }
        },
        'supported_operations': [
            'generate_key',
            'derive_key',
            'encrypt',
            'decrypt',
            'stream_encrypt',
            'stream_decrypt'
        ]
    }, status=status.HTTP_200_OK)


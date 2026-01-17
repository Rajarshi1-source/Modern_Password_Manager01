"""
Quantum RNG API Views
=====================

REST API endpoints for quantum password generation.

Endpoints:
- POST /api/security/quantum/generate-password/  - Generate quantum-certified password
- GET  /api/security/quantum/random-bytes/       - Get raw quantum random bytes
- GET  /api/security/quantum/certificate/{id}/   - Get quantum certificate
- GET  /api/security/quantum/pool-status/        - Check entropy pool health
- GET  /api/security/quantum/certificates/       - List user's certificates
"""

import logging
import base64
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from asgiref.sync import async_to_sync

from ..services.quantum_rng_service import (
    get_quantum_generator,
    QuantumPasswordGenerator,
)
from ..models import QuantumPasswordCertificate

logger = logging.getLogger(__name__)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def generate_quantum_password(request):
    """
    Generate a quantum-certified password.
    
    POST Data:
    {
        "length": 16,              # Password length (8-128)
        "uppercase": true,         # Include uppercase letters
        "lowercase": true,         # Include lowercase letters  
        "numbers": true,           # Include digits
        "symbols": true,           # Include special characters
        "custom_charset": null,    # Optional custom character set
        "save_certificate": true   # Save certificate to database
    }
    
    Returns:
    {
        "success": true,
        "password": "xK9!mP2@nL5#",
        "certificate": {
            "certificate_id": "QC-2026-01-16-...",
            "provider": "anu_qrng",
            "quantum_source": "vacuum_fluctuations",
            "entropy_bits": 128,
            ...
        }
    }
    """
    try:
        data = request.data
        
        # Extract parameters with defaults
        length = data.get('length', 16)
        use_uppercase = data.get('uppercase', True)
        use_lowercase = data.get('lowercase', True)
        use_numbers = data.get('numbers', True)
        use_symbols = data.get('symbols', True)
        custom_charset = data.get('custom_charset')
        save_certificate = data.get('save_certificate', True)
        
        # Validate length
        if not 8 <= length <= 128:
            return Response({
                'success': False,
                'error': 'Password length must be between 8 and 128'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Get quantum generator
        generator = get_quantum_generator()
        
        # Generate password (async to sync wrapper)
        password, certificate = async_to_sync(generator.generate_password)(
            length=length,
            use_uppercase=use_uppercase,
            use_lowercase=use_lowercase,
            use_numbers=use_numbers,
            use_symbols=use_symbols,
            custom_charset=custom_charset
        )
        
        # Save certificate to database
        certificate_data = certificate.to_dict()
        if save_certificate:
            db_cert = QuantumPasswordCertificate.objects.create(
                user=request.user,
                password_hash_prefix=certificate.password_hash_prefix,
                provider=certificate.provider,
                quantum_source=certificate.quantum_source,
                entropy_bits=certificate.entropy_bits,
                circuit_id=certificate.circuit_id,
                signature=certificate.signature
            )
            certificate_data['certificate_id'] = str(db_cert.id)
        
        logger.info(
            f"Generated quantum password for user {request.user.id} "
            f"using {certificate.provider}"
        )
        
        return Response({
            'success': True,
            'password': password,
            'certificate': certificate_data,
            'quantum_certified': certificate.provider != 'cryptographic_fallback'
        })
        
    except Exception as e:
        logger.error(f"Quantum password generation failed: {e}")
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_random_bytes(request):
    """
    Get raw quantum random bytes.
    
    Query Parameters:
    - count: Number of bytes (1-256, default: 32)
    - format: 'hex' or 'base64' (default: 'hex')
    
    Returns:
    {
        "success": true,
        "bytes": "a3f2b1c4d5e6...",
        "format": "hex",
        "count": 32,
        "provider": "anu_qrng"
    }
    """
    try:
        count = int(request.query_params.get('count', 32))
        output_format = request.query_params.get('format', 'hex')
        
        # Validate count
        if not 1 <= count <= 256:
            return Response({
                'success': False,
                'error': 'Count must be between 1 and 256'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Get random bytes
        generator = get_quantum_generator()
        random_bytes, certificate = async_to_sync(generator.get_raw_random_bytes)(count)
        
        # Format output
        if output_format == 'base64':
            bytes_str = base64.b64encode(random_bytes).decode()
        else:
            bytes_str = random_bytes.hex()
        
        return Response({
            'success': True,
            'bytes': bytes_str,
            'format': output_format,
            'count': count,
            'provider': certificate.provider
        })
        
    except Exception as e:
        logger.error(f"Random bytes generation failed: {e}")
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_certificate(request, certificate_id):
    """
    Get a quantum certificate by ID.
    
    Returns:
    {
        "success": true,
        "certificate": {
            "certificate_id": "...",
            "provider": "anu_qrng",
            ...
        }
    }
    """
    try:
        certificate = QuantumPasswordCertificate.objects.get(
            id=certificate_id,
            user=request.user
        )
        
        return Response({
            'success': True,
            'certificate': certificate.to_dict()
        })
        
    except QuantumPasswordCertificate.DoesNotExist:
        return Response({
            'success': False,
            'error': 'Certificate not found'
        }, status=status.HTTP_404_NOT_FOUND)
        
    except Exception as e:
        logger.error(f"Certificate retrieval failed: {e}")
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def list_certificates(request):
    """
    List user's quantum certificates.
    
    Query Parameters:
    - limit: Number of certificates to return (default: 20)
    
    Returns:
    {
        "success": true,
        "certificates": [...],
        "total": 45
    }
    """
    try:
        limit = int(request.query_params.get('limit', 20))
        limit = min(limit, 100)  # Max 100
        
        certificates = QuantumPasswordCertificate.objects.filter(
            user=request.user
        )[:limit]
        
        total = QuantumPasswordCertificate.objects.filter(
            user=request.user
        ).count()
        
        return Response({
            'success': True,
            'certificates': [cert.to_dict() for cert in certificates],
            'total': total
        })
        
    except Exception as e:
        logger.error(f"Certificate listing failed: {e}")
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_pool_status(request):
    """
    Get quantum entropy pool status.
    
    Returns:
    {
        "success": true,
        "pool": {
            "total_bytes_available": 2048,
            "batch_count": 4,
            "health": "good",
            "min_pool_size": 1024,
            "max_pool_size": 4096
        },
        "providers": {
            "anu_qrng": {"available": true, "description": "ANU Quantum RNG"},
            "ibm_quantum": {"available": false, "description": "IBM Quantum"},
            "ionq_quantum": {"available": false, "description": "IonQ Quantum"}
        }
    }
    """
    try:
        generator = get_quantum_generator()
        pool_status = generator.get_pool_status()
        
        # Provider availability
        providers = {
            'anu_qrng': {
                'available': True,  # ANU is always available (no auth needed)
                'description': 'Australian National University QRNG',
                'source': 'Quantum vacuum fluctuations'
            },
            'ibm_quantum': {
                'available': bool(__import__('os').environ.get('IBM_QUANTUM_TOKEN')),
                'description': 'IBM Quantum Computing',
                'source': 'Superconducting qubit superposition'
            },
            'ionq_quantum': {
                'available': bool(__import__('os').environ.get('IONQ_API_KEY')),
                'description': 'IonQ Trapped Ion Quantum',
                'source': 'Trapped ion qubit superposition'
            }
        }
        
        return Response({
            'success': True,
            'pool': pool_status,
            'providers': providers
        })
        
    except Exception as e:
        logger.error(f"Pool status check failed: {e}")
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

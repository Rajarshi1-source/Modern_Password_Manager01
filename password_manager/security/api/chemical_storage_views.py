"""
Chemical Storage API Views
==========================

REST API endpoints for chemical password storage feature.

Endpoints:
- POST /encode/              - Encode password to DNA
- POST /decode/              - Decode DNA to password  
- POST /time-lock/           - Create time-lock capsule
- GET  /capsule-status/{id}/ - Check capsule status
- POST /synthesis-order/     - Order DNA synthesis
- POST /sequencing-request/  - Request password retrieval
- GET  /certificates/        - List certificates
- GET  /subscription/        - Get subscription status
- POST /store/               - Full storage workflow

@author Password Manager Team
@created 2026-01-17
"""

import logging
import hashlib
from datetime import datetime, timedelta

from django.utils import timezone
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from ..models import (
    ChemicalStorageSubscription,
    DNAEncodedPassword,
    TimeLockCapsule,
    ChemicalStorageCertificate,
)
from ..services.chemical_storage_service import (
    ChemicalStorageService,
    ChemicalStorageTier,
    get_chemical_storage_service,
)
from ..services.dna_encoder import DNAEncoder, dna_encoder
from ..services.time_lock_service import TimeLockMode, time_lock_service
from ..services.lab_provider_api import LabProviderFactory, list_providers

logger = logging.getLogger(__name__)


# =============================================================================
# Helper Functions
# =============================================================================

def get_user_subscription(user):
    """Get or create user's chemical storage subscription."""
    subscription, created = ChemicalStorageSubscription.objects.get_or_create(
        user=user,
        defaults={
            'tier': 'free',
            'status': 'active',
            'max_passwords': 1,
        }
    )
    return subscription


def get_service_for_user(user):
    """Get chemical storage service based on user's tier."""
    subscription = get_user_subscription(user)
    tier = ChemicalStorageTier(subscription.tier)
    return ChemicalStorageService(tier=tier)


# =============================================================================
# DNA Encoding Endpoints
# =============================================================================

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def encode_password_to_dna(request):
    """
    Encode a password to DNA sequence.
    
    Request:
        {
            "password": "MySecretPassword123!",
            "service_name": "Gmail Account",
            "use_error_correction": true,
            "save_to_db": false
        }
    
    Response:
        {
            "success": true,
            "dna_sequence": {
                "sequence": "ATCGATCG...",
                "sequence_length": 200,
                "gc_content": 0.52,
                "checksum": "abc123..."
            },
            "validation": {
                "is_valid": true,
                "warnings": []
            },
            "cost_estimate": {
                "synthesis_cost_usd": 14.00
            },
            "id": null
        }
    """
    try:
        password = request.data.get('password')
        service_name = request.data.get('service_name', '')
        save_to_db = request.data.get('save_to_db', False)
        
        if not password:
            return Response(
                {'success': False, 'error': 'Password is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        use_ecc = request.data.get('use_error_correction', True)
        
        # Get service for user
        service = get_service_for_user(request.user)
        
        # Encode password
        dna_sequence, validation = service.encode_password_to_dna(
            password=password,
            use_error_correction=use_ecc
        )
        
        # Get cost estimate
        cost_estimate = service.estimate_cost(password)
        
        # Optionally save to database
        record_id = None
        if save_to_db:
            subscription = get_user_subscription(request.user)
            if subscription.can_store_password():
                dna_password = DNAEncodedPassword.objects.create(
                    user=request.user,
                    service_name=service_name,
                    sequence_hash=hashlib.sha256(dna_sequence.sequence.encode()).hexdigest(),
                    password_hash_prefix=hashlib.sha256(password.encode()).hexdigest()[:16],
                    sequence_length_bp=len(dna_sequence.sequence),
                    gc_content=dna_sequence.gc_content,
                    has_error_correction=use_ecc,
                    status='encoded',
                    synthesis_cost_usd=cost_estimate.get('total_cost_usd', 0),
                )
                record_id = str(dna_password.id)
                subscription.passwords_stored += 1
                subscription.save()
        
        return Response({
            'success': True,
            'dna_sequence': dna_sequence.to_dict(),
            'validation': {
                'is_valid': validation.is_valid,
                'gc_content': validation.gc_content,
                'max_homopolymer': validation.max_homopolymer,
                'errors': validation.errors,
                'warnings': validation.warnings,
            },
            'cost_estimate': cost_estimate,
            'id': record_id,
            'sequence': dna_sequence.sequence,  # Direct access for compatibility
            'cost': cost_estimate,  # Alias for compatibility
        })
        
    except Exception as e:
        logger.error(f"DNA encoding failed: {e}")
        return Response(
            {'success': False, 'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def decode_dna_to_password(request):
    """
    Decode a DNA sequence back to password.
    
    Request:
        {
            "dna_sequence": "ATCGATCG..."
        }
    
    Response:
        {
            "success": true,
            "password": "MySecretPassword123!"
        }
    """
    try:
        dna_sequence = request.data.get('dna_sequence')
        if not dna_sequence:
            return Response(
                {'success': False, 'error': 'DNA sequence is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        service = get_service_for_user(request.user)
        password = service.decode_dna_to_password(dna_sequence)
        
        return Response({
            'success': True,
            'password': password,
        })
        
    except ValueError as e:
        return Response(
            {'success': False, 'error': str(e)},
            status=status.HTTP_400_BAD_REQUEST
        )
    except Exception as e:
        logger.error(f"DNA decoding failed: {e}")
        return Response(
            {'success': False, 'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


# =============================================================================
# Time-Lock Endpoints
# =============================================================================

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_time_lock(request):
    """
    Create a time-lock capsule for delayed password access.
    
    Request:
        {
            "password": "MySecretPassword123!",
            "delay_hours": 72,
            "mode": "server",  // "server", "client", or "hybrid"
            "beneficiary_email": "family@example.com"
        }
    
    Response:
        {
            "success": true,
            "capsule_id": "uuid...",
            "unlock_at": "2026-01-20T18:00:00Z",
            "mode": "server"
        }
    """
    try:
        password = request.data.get('password')
        delay_hours = request.data.get('delay_hours', 72)
        mode_str = request.data.get('mode', 'server')
        beneficiary_email = request.data.get('beneficiary_email')
        
        if not password:
            return Response(
                {'success': False, 'error': 'Password is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Validate delay
        if delay_hours < 1:
            return Response(
                {'success': False, 'error': 'Delay must be at least 1 hour'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        mode = TimeLockMode(mode_str)
        service = get_service_for_user(request.user)
        
        # Create time-lock
        time_lock = service.create_time_lock(
            password=password,
            delay_hours=delay_hours,
            mode=mode,
            beneficiary_email=beneficiary_email,
        )
        
        # Save to database
        capsule = TimeLockCapsule.objects.create(
            user=request.user,
            encrypted_data=time_lock.encrypted_data,
            encryption_key_encrypted=time_lock.encryption_key_encrypted,
            mode=mode_str,
            delay_seconds=delay_hours * 3600,
            unlock_at=time_lock.unlock_at,
            beneficiary_email=beneficiary_email,
        )
        
        return Response({
            'success': True,
            'capsule_id': str(capsule.id),
            'unlock_at': capsule.unlock_at.isoformat(),
            'mode': mode_str,
            'time_remaining_seconds': capsule.time_remaining(),
        })
        
    except ValueError as e:
        return Response(
            {'success': False, 'error': str(e)},
            status=status.HTTP_400_BAD_REQUEST
        )
    except Exception as e:
        logger.error(f"Time-lock creation failed: {e}")
        return Response(
            {'success': False, 'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_capsule_status(request, capsule_id):
    """
    Get status of a time-lock capsule.
    
    Response:
        {
            "success": true,
            "capsule_id": "uuid...",
            "status": "locked",
            "can_unlock": false,
            "time_remaining_seconds": 172800,
            "unlock_at": "2026-01-20T18:00:00Z"
        }
    """
    try:
        capsule = TimeLockCapsule.objects.get(
            id=capsule_id,
            user=request.user
        )
        
        return Response({
            'success': True,
            'capsule_id': str(capsule.id),
            'status': capsule.status,
            'can_unlock': capsule.is_unlockable(),
            'time_remaining_seconds': capsule.time_remaining(),
            'unlock_at': capsule.unlock_at.isoformat(),
            'mode': capsule.mode,
            'beneficiary_email': capsule.beneficiary_email,
        })
        
    except TimeLockCapsule.DoesNotExist:
        return Response(
            {'success': False, 'error': 'Capsule not found'},
            status=status.HTTP_404_NOT_FOUND
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def unlock_capsule(request, capsule_id):
    """
    Unlock a time-lock capsule and retrieve password.
    
    Response:
        {
            "success": true,
            "password": "MySecretPassword123!"
        }
    """
    try:
        capsule = TimeLockCapsule.objects.get(
            id=capsule_id,
            user=request.user
        )
        
        if not capsule.is_unlockable():
            return Response({
                'success': False,
                'error': f'Capsule still locked. {capsule.time_remaining()} seconds remaining.',
                'time_remaining_seconds': capsule.time_remaining(),
            }, status=status.HTTP_403_FORBIDDEN)
        
        # Reconstruct the ServerTimeLockCapsule from DB record
        from ..services.time_lock_service import ServerTimeLockCapsule
        
        server_capsule = ServerTimeLockCapsule(
            capsule_id=str(capsule.id),
            encrypted_data=bytes(capsule.encrypted_data),
            encryption_key_encrypted=bytes(capsule.encryption_key_encrypted),
            unlock_at=capsule.unlock_at,
        )
        
        service = get_service_for_user(request.user)
        password = service.unlock_time_lock(server_capsule)
        
        # Update capsule status
        capsule.status = 'unlocked'
        capsule.unlocked_at = timezone.now()
        capsule.save()
        
        return Response({
            'success': True,
            'password': password,
        })
        
    except TimeLockCapsule.DoesNotExist:
        return Response(
            {'success': False, 'error': 'Capsule not found'},
            status=status.HTTP_404_NOT_FOUND
        )
    except ValueError as e:
        return Response(
            {'success': False, 'error': str(e)},
            status=status.HTTP_400_BAD_REQUEST
        )


# =============================================================================
# Synthesis/Lab Endpoints
# =============================================================================

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def order_synthesis(request):
    """
    Order DNA synthesis from lab.
    
    Request:
        {
            "dna_sequence": "ATCGATCG...",
            "provider": "twist"  // or "mock", "idt", "genscript"
        }
    
    Response:
        {
            "success": true,
            "order_id": "TWIST-ABC123",
            "status": "pending",
            "cost_usd": 145.00,
            "estimated_completion": "2026-01-27T18:00:00Z"
        }
    """
    try:
        dna_sequence_str = request.data.get('dna_sequence')
        provider_name = request.data.get('provider', 'mock')
        
        if not dna_sequence_str:
            return Response(
                {'success': False, 'error': 'DNA sequence is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check subscription
        subscription = get_user_subscription(request.user)
        if not subscription.can_store_password():
            return Response({
                'success': False,
                'error': 'Password storage limit reached. Upgrade to enterprise.',
                'stored': subscription.passwords_stored,
                'max': subscription.max_passwords,
            }, status=status.HTTP_403_FORBIDDEN)
        
        # Get lab provider
        provider = LabProviderFactory.get_provider(provider_name)
        
        if not provider.supports_synthesis:
            return Response({
                'success': False,
                'error': f'{provider.name} does not support DNA synthesis',
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Submit order
        order = provider.submit_synthesis_order(
            sequence=dna_sequence_str,
            user_email=request.user.email,
        )
        
        # Save to database
        dna_password = DNAEncodedPassword.objects.create(
            user=request.user,
            sequence_hash=hashlib.sha256(dna_sequence_str.encode()).hexdigest(),
            password_hash_prefix='',  # Not storing actual password hash
            sequence_length_bp=len(dna_sequence_str),
            gc_content=dna_encoder._calculate_gc_content(dna_sequence_str),
            status='synthesis_pending',
            synthesis_order_id=order.order_id,
            synthesis_provider=order.provider,
            synthesis_cost_usd=order.cost_usd,
        )
        
        # Update subscription count
        subscription.passwords_stored += 1
        subscription.save()
        
        return Response({
            'success': True,
            'order_id': order.order_id,
            'status': order.status.value,
            'cost_usd': order.cost_usd,
            'estimated_completion': order.estimated_completion.isoformat() if order.estimated_completion else None,
            'dna_password_id': str(dna_password.id),
        })
        
    except Exception as e:
        logger.error(f"Synthesis order failed: {e}")
        return Response(
            {'success': False, 'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def check_synthesis_status(request, order_id):
    """Check status of DNA synthesis order."""
    try:
        dna_password = DNAEncodedPassword.objects.get(
            synthesis_order_id=order_id,
            user=request.user
        )
        
        # Get updated status from provider
        provider_name = dna_password.synthesis_provider or 'mock'
        provider = LabProviderFactory.get_provider(provider_name)
        
        try:
            order = provider.check_synthesis_status(order_id)
            
            # Update database
            dna_password.status = order.status.value
            if order.storage_location:
                dna_password.storage_location = order.storage_location
                dna_password.physical_sample_id = order.order_id
            dna_password.save()
            
        except NotImplementedError:
            # Real API not implemented yet
            pass
        
        return Response({
            'success': True,
            'order_id': order_id,
            'status': dna_password.status,
            'storage_location': dna_password.storage_location,
        })
        
    except DNAEncodedPassword.DoesNotExist:
        return Response(
            {'success': False, 'error': 'Order not found'},
            status=status.HTTP_404_NOT_FOUND
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def request_sequencing(request):
    """
    Request DNA sequencing for password retrieval.
    
    Request:
        {
            "sample_id": "SAMPLE-ABC123"
        }
    """
    try:
        sample_id = request.data.get('sample_id')
        
        if not sample_id:
            return Response(
                {'success': False, 'error': 'Sample ID is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        service = get_service_for_user(request.user)
        order = service.request_password_retrieval(sample_id)
        
        return Response({
            'success': True,
            'order_id': order.order_id,
            'status': order.status.value,
            'estimated_completion': order.estimated_completion.isoformat() if order.estimated_completion else None,
        })
        
    except Exception as e:
        logger.error(f"Sequencing request failed: {e}")
        return Response(
            {'success': False, 'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


# =============================================================================
# Certificate Endpoints
# =============================================================================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def list_certificates(request):
    """List user's chemical storage certificates."""
    try:
        certificates = ChemicalStorageCertificate.objects.filter(
            user=request.user
        ).order_by('-created_at')[:50]
        
        return Response({
            'success': True,
            'certificates': [cert.to_dict() for cert in certificates],
            'count': certificates.count(),
        })
        
    except Exception as e:
        logger.error(f"Certificate listing failed: {e}")
        return Response(
            {'success': False, 'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_certificate(request, certificate_id):
    """Get a specific certificate."""
    try:
        certificate = ChemicalStorageCertificate.objects.get(
            id=certificate_id,
            user=request.user
        )
        
        return Response({
            'success': True,
            'certificate': certificate.to_dict(),
        })
        
    except ChemicalStorageCertificate.DoesNotExist:
        return Response(
            {'success': False, 'error': 'Certificate not found'},
            status=status.HTTP_404_NOT_FOUND
        )


# =============================================================================
# Subscription Endpoints
# =============================================================================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_subscription(request):
    """Get user's chemical storage subscription."""
    try:
        subscription = get_user_subscription(request.user)
        
        return Response({
            'success': True,
            'subscription': {
                'tier': subscription.tier,
                'status': subscription.status,
                'is_active': subscription.is_active(),
                'max_passwords': subscription.max_passwords,
                'passwords_stored': subscription.passwords_stored,
                'can_store_more': subscription.can_store_password(),
                'lab_provider': subscription.lab_provider,
                'features': {
                    'real_synthesis': subscription.real_synthesis_enabled,
                    'physical_storage': subscription.physical_storage_enabled,
                    'time_lock': subscription.time_lock_enabled,
                },
                'expires_at': subscription.expires_at.isoformat() if subscription.expires_at else None,
            },
        })
        
    except Exception as e:
        logger.error(f"Subscription fetch failed: {e}")
        return Response(
            {'success': False, 'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


# =============================================================================
# Full Workflow Endpoint
# =============================================================================

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def store_password_chemically(request):
    """
    Complete workflow to store password chemically.
    
    Request:
        {
            "password": "MySecretPassword123!",
            "enable_time_lock": true,
            "time_lock_hours": 72,
            "order_synthesis": false
        }
    
    Response:
        {
            "success": true,
            "dna_sequence": {...},
            "time_lock": {...},
            "certificate": {...},
            "qr_code_data": "base64..."
        }
    """
    try:
        password = request.data.get('password')
        enable_time_lock = request.data.get('enable_time_lock', False)
        time_lock_hours = request.data.get('time_lock_hours', 72)
        order_synthesis = request.data.get('order_synthesis', False)
        
        if not password:
            return Response(
                {'success': False, 'error': 'Password is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check subscription limits
        subscription = get_user_subscription(request.user)
        if not subscription.can_store_password():
            return Response({
                'success': False,
                'error': 'Storage limit reached',
            }, status=status.HTTP_403_FORBIDDEN)
        
        # Get service
        service = get_service_for_user(request.user)
        
        # Execute full workflow
        result = service.store_password_chemically(
            password=password,
            user_id=request.user.id,
            user_email=request.user.email,
            enable_time_lock=enable_time_lock,
            time_lock_hours=time_lock_hours,
            order_synthesis=order_synthesis,
        )
        
        if not result.success:
            return Response({
                'success': False,
                'error': result.error,
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Save certificate to database
        if result.certificate:
            ChemicalStorageCertificate.objects.create(
                user=request.user,
                sequence_hash=result.certificate.sequence_hash,
                encoding_method=result.certificate.encoding_method,
                error_correction_level=result.certificate.error_correction_level,
                time_lock_enabled=result.certificate.time_lock_enabled,
                time_lock_mode=result.certificate.time_lock_mode,
                signature=result.certificate.signature,
            )
        
        return Response(result.to_dict())
        
    except Exception as e:
        logger.error(f"Chemical storage workflow failed: {e}")
        return Response(
            {'success': False, 'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


# =============================================================================
# Provider Info Endpoint
# =============================================================================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def list_lab_providers(request):
    """List available lab providers and pricing."""
    try:
        providers = list_providers()
        
        return Response({
            'success': True,
            'providers': providers,
        })
        
    except Exception as e:
        logger.error(f"Provider listing failed: {e}")
        return Response(
            {'success': False, 'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

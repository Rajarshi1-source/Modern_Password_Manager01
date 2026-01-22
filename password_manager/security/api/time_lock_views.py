"""
Time-Lock Encryption API Views
===============================

API endpoints for time-lock capsules, password wills, and escrows.
"""

import logging
from datetime import timedelta

from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.contrib.auth.models import User
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from ..models import (
    TimeLockCapsule, CapsuleBeneficiary, VDFProof,
    PasswordWill, EscrowAgreement
)
from ..serializers.time_lock_serializers import (
    TimeLockCapsuleSerializer, CapsuleCreateSerializer,
    BeneficiarySerializer, BeneficiaryCreateSerializer,
    VDFProofSerializer, VDFVerifySerializer,
    PasswordWillSerializer, PasswordWillCreateSerializer,
    EscrowAgreementSerializer, EscrowCreateSerializer,
    CapsuleStatusSerializer, UnlockCapsuleSerializer
)
from ..services.time_lock_service import time_lock_service, TimeLockMode
from ..services.vdf_service import vdf_service, VDFParams, VDFOutput

logger = logging.getLogger(__name__)


# =============================================================================
# Capsule CRUD
# =============================================================================

class CapsuleListView(APIView):
    """List and create time-lock capsules."""
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """List user's capsules."""
        capsule_type = request.query_params.get('type')
        status_filter = request.query_params.get('status')
        
        capsules = TimeLockCapsule.objects.filter(
            owner=request.user
        ).order_by('-created_at')
        
        if capsule_type:
            capsules = capsules.filter(capsule_type=capsule_type)
        if status_filter:
            capsules = capsules.filter(status=status_filter)
        
        serializer = TimeLockCapsuleSerializer(capsules, many=True)
        
        return Response({
            'capsules': serializer.data,
            'total_count': capsules.count(),
            'locked_count': capsules.filter(status='locked').count(),
            'unlocked_count': capsules.filter(status='unlocked').count()
        })
    
    def post(self, request):
        """Create a new time-lock capsule."""
        serializer = CapsuleCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        data = serializer.validated_data
        
        # Create time-lock using service
        mode = TimeLockMode(data['mode'])
        secret_bytes = data['secret_data'].encode('utf-8')
        
        lock_result = time_lock_service.create_time_lock(
            data=secret_bytes,
            delay_seconds=data['delay_seconds'],
            mode=mode
        )
        
        # Create database record
        capsule = TimeLockCapsule.objects.create(
            owner=request.user,
            title=data['title'],
            description=data.get('description', ''),
            mode=data['mode'],
            capsule_type=data['capsule_type'],
            delay_seconds=data['delay_seconds'],
            unlock_at=timezone.now() + timedelta(seconds=data['delay_seconds']),
            encrypted_data=lock_result.encrypted_data if hasattr(lock_result, 'encrypted_data') else b'',
            encryption_key_encrypted=lock_result.encryption_key_encrypted if hasattr(lock_result, 'encryption_key_encrypted') else b'',
            puzzle_n=str(lock_result.n) if hasattr(lock_result, 'n') else '',
            puzzle_a=str(lock_result.a) if hasattr(lock_result, 'a') else '',
            puzzle_t=lock_result.t if hasattr(lock_result, 't') else None,
        )
        
        # Add beneficiaries if provided
        for ben_data in data.get('beneficiaries', []):
            CapsuleBeneficiary.objects.create(
                capsule=capsule,
                email=ben_data.get('email'),
                name=ben_data.get('name', ''),
                relationship=ben_data.get('relationship', ''),
                access_level=ben_data.get('access_level', 'view'),
            )
        
        return Response(
            TimeLockCapsuleSerializer(capsule).data,
            status=status.HTTP_201_CREATED
        )


class CapsuleDetailView(APIView):
    """Manage individual capsules."""
    permission_classes = [IsAuthenticated]
    
    def get(self, request, capsule_id):
        """Get capsule details."""
        capsule = get_object_or_404(
            TimeLockCapsule,
            id=capsule_id,
            owner=request.user
        )
        return Response(TimeLockCapsuleSerializer(capsule).data)
    
    def delete(self, request, capsule_id):
        """Cancel/delete a capsule."""
        capsule = get_object_or_404(
            TimeLockCapsule,
            id=capsule_id,
            owner=request.user
        )
        
        if capsule.status == 'unlocked':
            return Response(
                {'error': 'Cannot delete unlocked capsule'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        capsule.cancel()
        
        return Response({'success': True, 'status': 'cancelled'})


class CapsuleStatusView(APIView):
    """Check capsule unlock status."""
    permission_classes = [IsAuthenticated]
    
    def get(self, request, capsule_id):
        """Get current status and time remaining."""
        capsule = get_object_or_404(
            TimeLockCapsule,
            id=capsule_id,
            owner=request.user
        )
        
        return Response({
            'capsule_id': str(capsule.id),
            'status': capsule.status,
            'time_remaining_seconds': capsule.time_remaining_seconds,
            'can_unlock': capsule.is_ready_to_unlock,
            'unlock_at': capsule.unlock_at.isoformat()
        })


class UnlockCapsuleView(APIView):
    """Unlock a capsule and retrieve the secret."""
    permission_classes = [IsAuthenticated]
    
    def post(self, request, capsule_id):
        """Attempt to unlock a capsule."""
        capsule = get_object_or_404(
            TimeLockCapsule,
            id=capsule_id,
            owner=request.user
        )
        
        if capsule.status == 'cancelled':
            return Response(
                {'error': 'Capsule has been cancelled'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if capsule.status == 'unlocked':
            return Response(
                {'error': 'Capsule already unlocked'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if not capsule.is_ready_to_unlock:
            return Response({
                'error': 'Capsule is still locked',
                'time_remaining_seconds': capsule.time_remaining_seconds,
                'unlock_at': capsule.unlock_at.isoformat()
            }, status=status.HTTP_403_FORBIDDEN)
        
        # For client mode, verify VDF proof
        if capsule.mode in ['client', 'hybrid']:
            serializer = UnlockCapsuleSerializer(data=request.data)
            if not serializer.is_valid():
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            
            vdf_output = serializer.validated_data.get('vdf_output')
            vdf_proof = serializer.validated_data.get('vdf_proof')
            
            if vdf_output and vdf_proof and capsule.puzzle_n:
                # Verify VDF
                params = VDFParams(
                    modulus=int(capsule.puzzle_n),
                    challenge=int(capsule.puzzle_a),
                    iterations=capsule.puzzle_t
                )
                output = VDFOutput(
                    output=int(vdf_output),
                    proof=int(vdf_proof),
                    iterations=capsule.puzzle_t,
                    computation_time=0
                )
                verification = vdf_service.verify(params, output)
                
                if not verification.is_valid:
                    return Response(
                        {'error': 'VDF verification failed'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
        
        # Unlock the capsule
        try:
            # Decrypt data using service
            from ..services.time_lock_service import ServerTimeLockCapsule
            
            # Mark as unlocked
            capsule.status = 'unlocked'
            capsule.opened_at = timezone.now()
            capsule.save()
            
            # Notify beneficiaries
            for beneficiary in capsule.beneficiaries.all():
                beneficiary.notified_at = timezone.now()
                beneficiary.save()
            
            return Response({
                'success': True,
                'capsule_id': str(capsule.id),
                'status': 'unlocked',
                'unlocked_at': capsule.opened_at.isoformat(),
                # In production, return decrypted data
                'message': 'Capsule unlocked successfully'
            })
            
        except Exception as e:
            logger.error(f"Unlock failed: {e}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class CancelCapsuleView(APIView):
    """Cancel a capsule before unlock."""
    permission_classes = [IsAuthenticated]
    
    def post(self, request, capsule_id):
        """Cancel a capsule."""
        capsule = get_object_or_404(
            TimeLockCapsule,
            id=capsule_id,
            owner=request.user
        )
        
        if capsule.status != 'locked':
            return Response(
                {'error': f'Cannot cancel capsule with status: {capsule.status}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        capsule.cancel()
        
        return Response({
            'success': True,
            'capsule_id': str(capsule.id),
            'status': 'cancelled'
        })


# =============================================================================
# Beneficiaries
# =============================================================================

class BeneficiaryListView(APIView):
    """Manage capsule beneficiaries."""
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """List all beneficiaries for user's capsules."""
        beneficiaries = CapsuleBeneficiary.objects.filter(
            capsule__owner=request.user
        ).select_related('capsule')
        
        serializer = BeneficiarySerializer(beneficiaries, many=True)
        
        return Response({
            'beneficiaries': serializer.data,
            'total_count': beneficiaries.count()
        })
    
    def post(self, request):
        """Add a beneficiary to a capsule."""
        serializer = BeneficiaryCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        data = serializer.validated_data
        
        capsule = get_object_or_404(
            TimeLockCapsule,
            id=data['capsule_id'],
            owner=request.user
        )
        
        beneficiary = CapsuleBeneficiary.objects.create(
            capsule=capsule,
            email=data['email'],
            name=data['name'],
            relationship=data.get('relationship', ''),
            access_level=data['access_level'],
            requires_verification=data['requires_verification'],
        )
        
        return Response(
            BeneficiarySerializer(beneficiary).data,
            status=status.HTTP_201_CREATED
        )


class BeneficiaryDetailView(APIView):
    """Manage individual beneficiaries."""
    permission_classes = [IsAuthenticated]
    
    def delete(self, request, beneficiary_id):
        """Remove a beneficiary."""
        beneficiary = get_object_or_404(
            CapsuleBeneficiary,
            id=beneficiary_id,
            capsule__owner=request.user
        )
        
        beneficiary.delete()
        
        return Response({'success': True})


# =============================================================================
# Password Wills
# =============================================================================

class PasswordWillListView(APIView):
    """Manage password wills."""
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """List user's password wills."""
        wills = PasswordWill.objects.filter(
            owner=request.user
        ).select_related('capsule').order_by('-created_at')
        
        serializer = PasswordWillSerializer(wills, many=True)
        
        active_count = wills.filter(is_active=True, is_triggered=False).count()
        
        return Response({
            'wills': serializer.data,
            'total_count': wills.count(),
            'active_count': active_count
        })
    
    def post(self, request):
        """Create a new password will."""
        serializer = PasswordWillCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        data = serializer.validated_data
        
        # Calculate delay based on trigger type
        if data['trigger_type'] == 'inactivity':
            delay_seconds = data['inactivity_days'] * 86400
        elif data['trigger_type'] == 'date':
            delay_seconds = int((data['target_date'] - timezone.now()).total_seconds())
        else:
            delay_seconds = 86400 * 365  # Manual: 1 year max
        
        # Create capsule first
        secret_bytes = data['secret_data'].encode('utf-8')
        
        lock_result = time_lock_service.create_time_lock(
            data=secret_bytes,
            delay_seconds=delay_seconds,
            mode=TimeLockMode.SERVER
        )
        
        capsule = TimeLockCapsule.objects.create(
            owner=request.user,
            title=data['title'],
            description=data.get('description', ''),
            mode='server',
            capsule_type='will',
            delay_seconds=delay_seconds,
            unlock_at=timezone.now() + timedelta(seconds=delay_seconds),
            encrypted_data=lock_result.encrypted_data if hasattr(lock_result, 'encrypted_data') else b'',
            encryption_key_encrypted=lock_result.encryption_key_encrypted if hasattr(lock_result, 'encryption_key_encrypted') else b'',
        )
        
        # Add beneficiaries
        for ben_data in data['beneficiaries']:
            CapsuleBeneficiary.objects.create(
                capsule=capsule,
                email=ben_data.get('email'),
                name=ben_data.get('name', ''),
                relationship=ben_data.get('relationship', ''),
                access_level=ben_data.get('access_level', 'full'),
            )
        
        # Create will
        will = PasswordWill.objects.create(
            owner=request.user,
            capsule=capsule,
            trigger_type=data['trigger_type'],
            inactivity_days=data.get('inactivity_days'),
            target_date=data.get('target_date'),
            check_in_reminder_days=data.get('check_in_reminder_days', 7),
            notes=data.get('notes', '')
        )
        
        return Response(
            PasswordWillSerializer(will).data,
            status=status.HTTP_201_CREATED
        )


class PasswordWillCheckInView(APIView):
    """Check in to reset dead man's switch."""
    permission_classes = [IsAuthenticated]
    
    def post(self, request, will_id):
        """Record a check-in."""
        will = get_object_or_404(
            PasswordWill,
            id=will_id,
            owner=request.user
        )
        
        if not will.is_active:
            return Response(
                {'error': 'Will is not active'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if will.is_triggered:
            return Response(
                {'error': 'Will has already been triggered'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        will.check_in()
        
        return Response({
            'success': True,
            'last_check_in': will.last_check_in.isoformat(),
            'days_until_trigger': will.days_until_trigger
        })


# =============================================================================
# Escrow Agreements
# =============================================================================

class EscrowListView(APIView):
    """Manage escrow agreements."""
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """List user's escrow agreements."""
        # Escrows where user is owner or party
        escrows = EscrowAgreement.objects.filter(
            capsule__owner=request.user
        ).select_related('capsule').order_by('-created_at')
        
        party_escrows = EscrowAgreement.objects.filter(
            parties=request.user
        ).exclude(capsule__owner=request.user)
        
        serializer = EscrowAgreementSerializer(escrows, many=True)
        party_serializer = EscrowAgreementSerializer(party_escrows, many=True)
        
        return Response({
            'owned_escrows': serializer.data,
            'party_escrows': party_serializer.data
        })
    
    def post(self, request):
        """Create a new escrow agreement."""
        serializer = EscrowCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        data = serializer.validated_data
        
        # Calculate delay
        if data.get('unlock_date'):
            delay_seconds = int((data['unlock_date'] - timezone.now()).total_seconds())
        else:
            delay_seconds = 86400 * 30  # Default 30 days
        
        # Create capsule
        secret_bytes = data['secret_data'].encode('utf-8')
        
        lock_result = time_lock_service.create_time_lock(
            data=secret_bytes,
            delay_seconds=delay_seconds,
            mode=TimeLockMode.SERVER
        )
        
        capsule = TimeLockCapsule.objects.create(
            owner=request.user,
            title=data['title'],
            description=data.get('description', ''),
            mode='server',
            capsule_type='escrow',
            delay_seconds=delay_seconds,
            unlock_at=data.get('unlock_date') or (timezone.now() + timedelta(days=30)),
            encrypted_data=lock_result.encrypted_data if hasattr(lock_result, 'encrypted_data') else b'',
            encryption_key_encrypted=lock_result.encryption_key_encrypted if hasattr(lock_result, 'encryption_key_encrypted') else b'',
        )
        
        # Create escrow
        escrow = EscrowAgreement.objects.create(
            capsule=capsule,
            title=data['title'],
            description=data.get('description', ''),
            release_condition=data['release_condition'],
            approval_deadline=data.get('approval_deadline'),
            dispute_resolution_email=data.get('dispute_resolution_email', ''),
        )
        
        # Add parties
        for email in data['party_emails']:
            user = User.objects.filter(email=email).first()
            if user:
                escrow.parties.add(user)
        
        return Response(
            EscrowAgreementSerializer(escrow).data,
            status=status.HTTP_201_CREATED
        )


class EscrowApproveView(APIView):
    """Approve an escrow release."""
    permission_classes = [IsAuthenticated]
    
    def post(self, request, escrow_id):
        """Record approval from a party."""
        escrow = get_object_or_404(
            EscrowAgreement,
            id=escrow_id,
            parties=request.user
        )
        
        if escrow.is_released:
            return Response(
                {'error': 'Escrow already released'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        escrow.approve(request.user.id)
        
        # Check if can release now
        if escrow.can_release:
            escrow.release()
            return Response({
                'success': True,
                'approved': True,
                'released': True,
                'message': 'All conditions met - escrow released'
            })
        
        return Response({
            'success': True,
            'approved': True,
            'released': False,
            'approval_count': escrow.approval_count,
            'total_parties': escrow.total_parties
        })


# =============================================================================
# VDF Verification
# =============================================================================

class VDFVerifyView(APIView):
    """Verify a VDF proof."""
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        """Verify a VDF computation."""
        serializer = VDFVerifySerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        data = serializer.validated_data
        
        capsule = get_object_or_404(
            TimeLockCapsule,
            id=data['capsule_id'],
            owner=request.user
        )
        
        # Build VDF params and output
        params = VDFParams(
            modulus=int(data['modulus']),
            challenge=int(data['challenge']),
            iterations=data['iterations']
        )
        output = VDFOutput(
            output=int(data['output']),
            proof=int(data['proof']),
            iterations=data['iterations'],
            computation_time=0
        )
        
        # Verify
        verification = vdf_service.verify(params, output)
        
        # Store proof if valid
        if verification.is_valid:
            VDFProof.objects.create(
                capsule=capsule,
                challenge=data['challenge'],
                output=data['output'],
                proof=data['proof'],
                modulus=data['modulus'],
                iterations=data['iterations'],
                verified=True,
                verification_time_ms=verification.verification_time_ms,
                computation_time_seconds=0
            )
        
        return Response({
            'is_valid': verification.is_valid,
            'verification_time_ms': verification.verification_time_ms,
            'error_message': verification.error_message
        })

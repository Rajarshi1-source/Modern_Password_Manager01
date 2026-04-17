"""
Smart Contract Vault API Views
================================

REST API endpoints for managing smart contract vaults,
conditions, multi-sig approvals, DAO voting, escrow, and more.
"""

import logging
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.response import Response
from django.shortcuts import get_object_or_404

from smart_contracts.models.vault import SmartContractVault, VaultStatus
from smart_contracts.serializers import (
    SmartContractVaultSerializer,
    SmartContractVaultCreateSerializer,
    SmartContractVaultDetailSerializer,
    VaultConditionResultSerializer,
    MultiSigGroupSerializer,
    DAOProposalSerializer,
    DAOVoteCreateSerializer,
    EscrowAgreementSerializer,
    InheritancePlanSerializer,
)
from smart_contracts.services.vault_service import VaultService
from smart_contracts.services.condition_engine import ConditionEngine
from smart_contracts.services.oracle_service import OracleService

logger = logging.getLogger(__name__)


# =============================================================================
# Configuration
# =============================================================================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def smart_contract_config(request):
    """Get smart contract feature configuration."""
    service = VaultService()
    return Response(service.get_config())


# =============================================================================
# Vault CRUD
# =============================================================================

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def vault_list(request):
    """List user's vaults or create a new vault."""
    if request.method == 'GET':
        vaults = SmartContractVault.objects.filter(user=request.user)

        # Optional filters
        condition_type = request.query_params.get('condition_type')
        vault_status = request.query_params.get('status')
        if condition_type:
            vaults = vaults.filter(condition_type=condition_type)
        if vault_status:
            vaults = vaults.filter(status=vault_status)

        serializer = SmartContractVaultSerializer(vaults, many=True)
        return Response(serializer.data)

    # POST: Create a new vault
    create_serializer = SmartContractVaultCreateSerializer(data=request.data)
    create_serializer.is_valid(raise_exception=True)

    service = VaultService()
    try:
        vault = service.create_vault(request.user, create_serializer.validated_data)
        result_serializer = SmartContractVaultDetailSerializer(vault)
        return Response(result_serializer.data, status=status.HTTP_201_CREATED)
    except Exception as e:
        logger.error(f"Vault creation failed: {e}")
        return Response(
            {'error': str(e)},
            status=status.HTTP_400_BAD_REQUEST
        )


@api_view(['GET', 'DELETE'])
@permission_classes([IsAuthenticated])
def vault_detail(request, vault_id):
    """Get vault details or delete (cancel) a vault."""
    vault = get_object_or_404(SmartContractVault, id=vault_id, user=request.user)

    if request.method == 'GET':
        serializer = SmartContractVaultDetailSerializer(vault)
        return Response(serializer.data)

    # DELETE: Cancel the vault
    service = VaultService()
    try:
        result = service.cancel_vault(vault, request.user)
        return Response(result)
    except (ValueError, PermissionError) as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


# =============================================================================
# Condition Evaluation
# =============================================================================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def vault_conditions(request, vault_id):
    """Get condition evaluation details for a vault."""
    vault = get_object_or_404(SmartContractVault, id=vault_id, user=request.user)
    engine = ConditionEngine()

    verify_onchain = request.query_params.get('verify_onchain', 'false').lower() == 'true'
    result = engine.evaluate(vault, verify_onchain=verify_onchain)

    serializer = VaultConditionResultSerializer(result)
    return Response(serializer.data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def vault_unlock(request, vault_id):
    """Attempt to unlock a vault by evaluating its conditions (dry-run)."""
    vault = get_object_or_404(SmartContractVault, id=vault_id, user=request.user)
    service = VaultService()

    try:
        result = service.attempt_unlock(vault, request.user)
        if result['unlocked']:
            return Response(result)
        else:
            return Response(result, status=status.HTTP_403_FORBIDDEN)
    except ValueError as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def vault_reveal(request, vault_id):
    """
    Reveal a vault's encrypted password.

    Evaluates conditions, flips DB state, enqueues the VaultAuditLog
    anchor as a Celery task, and returns the ciphertext. The frontend
    decrypts locally with the user's master key.
    """
    vault = get_object_or_404(SmartContractVault, id=vault_id, user=request.user)
    service = VaultService()
    try:
        result = service.reveal_password(vault, request.user)
    except ValueError as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
    except PermissionError as e:
        return Response({'error': str(e)}, status=status.HTTP_403_FORBIDDEN)

    if not result.get('unlocked'):
        return Response(result, status=status.HTTP_403_FORBIDDEN)
    return Response(result)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def vault_receipt(request, vault_id):
    """Return the current on-chain receipt state for a revealed vault."""
    vault = get_object_or_404(SmartContractVault, id=vault_id, user=request.user)
    service = VaultService()
    return Response(service.get_receipt(vault))


# =============================================================================
# Dead Man's Switch
# =============================================================================

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def vault_check_in(request, vault_id):
    """Dead man's switch check-in."""
    vault = get_object_or_404(SmartContractVault, id=vault_id, user=request.user)
    service = VaultService()

    try:
        result = service.check_in(vault, request.user)
        return Response(result)
    except (ValueError, PermissionError) as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


# =============================================================================
# Multi-Sig
# =============================================================================

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def multi_sig_approve(request, vault_id):
    """Multi-sig approval from an authorized signer."""
    vault = get_object_or_404(SmartContractVault, id=vault_id)
    service = VaultService()

    try:
        result = service.approve_multi_sig(vault, request.user)
        return Response(result)
    except (ValueError, PermissionError) as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def multi_sig_status(request, vault_id):
    """Get multi-sig group status."""
    vault = get_object_or_404(SmartContractVault, id=vault_id)
    try:
        group = vault.multi_sig_group
        serializer = MultiSigGroupSerializer(group)
        return Response(serializer.data)
    except Exception:
        return Response({'error': 'No multi-sig group found'}, status=status.HTTP_404_NOT_FOUND)


# =============================================================================
# DAO Voting
# =============================================================================

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def dao_vote(request, vault_id):
    """Cast a DAO vote on a vault proposal."""
    vault = get_object_or_404(SmartContractVault, id=vault_id)
    vote_serializer = DAOVoteCreateSerializer(data=request.data)
    vote_serializer.is_valid(raise_exception=True)

    service = VaultService()
    try:
        result = service.cast_vote(vault, request.user, vote_serializer.validated_data['approve'])
        return Response(result)
    except (ValueError, PermissionError) as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def dao_results(request, vault_id):
    """Get DAO voting results."""
    vault = get_object_or_404(SmartContractVault, id=vault_id)
    try:
        proposal = vault.dao_proposal
        serializer = DAOProposalSerializer(proposal)
        return Response(serializer.data)
    except Exception:
        return Response({'error': 'No DAO proposal found'}, status=status.HTTP_404_NOT_FOUND)


# =============================================================================
# Escrow
# =============================================================================

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def escrow_release(request, vault_id):
    """Release an escrow vault (arbitrator only)."""
    vault = get_object_or_404(SmartContractVault, id=vault_id)
    service = VaultService()

    try:
        result = service.release_escrow(vault, request.user)
        return Response(result)
    except (ValueError, PermissionError) as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def escrow_status(request, vault_id):
    """Get escrow agreement status."""
    vault = get_object_or_404(SmartContractVault, id=vault_id)
    try:
        escrow = vault.escrow_agreement
        serializer = EscrowAgreementSerializer(escrow)
        return Response(serializer.data)
    except Exception:
        return Response({'error': 'No escrow agreement found'}, status=status.HTTP_404_NOT_FOUND)


# =============================================================================
# Inheritance
# =============================================================================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def inheritance_status(request, vault_id):
    """Get inheritance plan status."""
    vault = get_object_or_404(SmartContractVault, id=vault_id, user=request.user)
    try:
        plan = vault.inheritance_plan
        serializer = InheritancePlanSerializer(plan)
        return Response(serializer.data)
    except Exception:
        return Response({'error': 'No inheritance plan found'}, status=status.HTTP_404_NOT_FOUND)


# =============================================================================
# Oracle
# =============================================================================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def oracle_price(request):
    """Get current ETH/USD oracle price."""
    oracle = OracleService()
    price = oracle.get_eth_usd_price()

    if price is not None:
        return Response({
            'pair': 'ETH/USD',
            'price': price,
            'cached': True,
        })
    else:
        return Response(
            {'error': 'Oracle price unavailable', 'pair': 'ETH/USD'},
            status=status.HTTP_503_SERVICE_UNAVAILABLE
        )

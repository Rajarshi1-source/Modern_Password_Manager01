"""
Blockchain API Views

REST API endpoints for blockchain verification and anchoring
"""

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404
from django.contrib.auth.models import User
from django.conf import settings

from .models import BlockchainAnchor, PendingCommitment, MerkleProof
from .services.blockchain_anchor_service import BlockchainAnchorService
from behavioral_recovery.models import BehavioralCommitment

import logging

logger = logging.getLogger(__name__)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def verify_commitment(request, commitment_id):
    """
    Verify a behavioral commitment on the blockchain
    
    GET /api/blockchain/verify-commitment/<commitment_id>/
    
    Returns:
        {
            "verified": true,
            "commitment_id": "uuid",
            "commitment_hash": "0x...",
            "merkle_root": "0x...",
            "merkle_proof": [...],
            "blockchain_anchor": {
                "tx_hash": "0x...",
                "block_number": 12345,
                "timestamp": "2025-11-23T...",
                "network": "testnet"
            },
            "arbiscan_url": "https://sepolia.arbiscan.io/tx/0x..."
        }
    """
    try:
        # Get commitment
        commitment = get_object_or_404(
            BehavioralCommitment,
            commitment_id=commitment_id,
            user=request.user
        )
        
        # Check if blockchain anchoring is enabled
        if not settings.BLOCKCHAIN_ANCHORING.get('ENABLED', False):
            return Response({
                'error': 'Blockchain anchoring is not enabled',
                'verified': False
            }, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        
        # Check if commitment has been anchored
        if not commitment.blockchain_anchored:
            # Check if it's pending
            pending = PendingCommitment.objects.filter(
                commitment_id=commitment.commitment_id,
                anchored=False
            ).first()
            
            if pending:
                return Response({
                    'verified': False,
                    'status': 'pending',
                    'message': 'Commitment is queued for blockchain anchoring',
                    'pending_since': pending.created_at,
                    'commitment_id': str(commitment.commitment_id)
                })
            else:
                return Response({
                    'verified': False,
                    'status': 'not_anchored',
                    'message': 'Commitment has not been anchored to blockchain yet',
                    'commitment_id': str(commitment.commitment_id)
                })
        
        # Get Merkle proof
        merkle_proof = MerkleProof.objects.filter(
            commitment=commitment
        ).first()
        
        if not merkle_proof:
            return Response({
                'error': 'Merkle proof not found',
                'verified': False
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Get blockchain anchor
        blockchain_anchor = merkle_proof.blockchain_anchor
        
        # Verify proof locally
        service = BlockchainAnchorService()
        is_valid_local = service.verify_proof_locally(
            merkle_root=merkle_proof.merkle_root,
            leaf_hash=merkle_proof.commitment_hash,
            proof=merkle_proof.proof
        )
        
        # Optionally verify on-chain (more expensive but authoritative)
        is_valid_onchain = None
        if request.GET.get('verify_onchain', 'false').lower() == 'true':
            try:
                is_valid_onchain = service.verify_proof_on_chain(
                    merkle_root=merkle_proof.merkle_root,
                    leaf_hash=merkle_proof.commitment_hash,
                    proof=merkle_proof.proof
                )
            except Exception as e:
                logger.error(f"On-chain verification failed: {e}")
        
        # Build Arbiscan URL
        network = blockchain_anchor.network
        arbiscan_base = "https://sepolia.arbiscan.io" if network == "testnet" else "https://arbiscan.io"
        arbiscan_url = f"{arbiscan_base}/tx/{blockchain_anchor.tx_hash}"
        
        return Response({
            'verified': is_valid_local,
            'verified_onchain': is_valid_onchain,
            'commitment_id': str(commitment.commitment_id),
            'commitment_hash': merkle_proof.commitment_hash,
            'merkle_root': merkle_proof.merkle_root,
            'merkle_proof': merkle_proof.proof,
            'leaf_index': merkle_proof.leaf_index,
            'blockchain_anchor': {
                'tx_hash': blockchain_anchor.tx_hash,
                'block_number': blockchain_anchor.block_number,
                'timestamp': blockchain_anchor.timestamp,
                'network': blockchain_anchor.network,
                'batch_size': blockchain_anchor.batch_size
            },
            'arbiscan_url': arbiscan_url,
            'created_at': commitment.creation_timestamp
        })
        
    except Exception as e:
        logger.exception(f"Error verifying commitment {commitment_id}: {e}")
        return Response({
            'error': str(e),
            'verified': False
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def anchor_status(request):
    """
    Get blockchain anchoring status
    
    GET /api/blockchain/anchor-status/
    
    Returns:
        {
            "enabled": true,
            "network": "testnet",
            "contract_address": "0x...",
            "pending_count": 42,
            "total_anchored": 1000,
            "last_anchor": {
                "timestamp": "2025-11-23T...",
                "batch_size": 1000,
                "tx_hash": "0x..."
            },
            "next_anchor_estimated": "2025-11-24T02:00:00Z"
        }
    """
    try:
        blockchain_config = settings.BLOCKCHAIN_ANCHORING
        
        if not blockchain_config.get('ENABLED', False):
            return Response({
                'enabled': False,
                'message': 'Blockchain anchoring is not enabled'
            })
        
        # Get pending count
        pending_count = PendingCommitment.objects.filter(anchored=False).count()
        
        # Get total anchored commitments (across all anchors)
        total_anchored = sum(
            anchor.batch_size for anchor in BlockchainAnchor.objects.all()
        )
        
        # Get last anchor
        last_anchor = BlockchainAnchor.objects.order_by('-timestamp').first()
        last_anchor_data = None
        if last_anchor:
            last_anchor_data = {
                'timestamp': last_anchor.timestamp,
                'batch_size': last_anchor.batch_size,
                'tx_hash': last_anchor.tx_hash,
                'merkle_root': last_anchor.merkle_root
            }
        
        # Estimate next anchor (daily at 2 AM UTC)
        from datetime import datetime, timedelta
        import pytz
        
        now = datetime.now(pytz.UTC)
        next_anchor = now.replace(hour=2, minute=0, second=0, microsecond=0)
        if now.hour >= 2:
            next_anchor += timedelta(days=1)
        
        return Response({
            'enabled': True,
            'network': blockchain_config.get('NETWORK'),
            'contract_address': blockchain_config.get('CONTRACT_ADDRESS'),
            'rpc_url': blockchain_config.get('RPC_URL'),
            'batch_size': blockchain_config.get('BATCH_SIZE'),
            'batch_interval_hours': blockchain_config.get('BATCH_INTERVAL_HOURS'),
            'pending_count': pending_count,
            'total_anchored': total_anchored,
            'last_anchor': last_anchor_data,
            'next_anchor_estimated': next_anchor.isoformat()
        })
        
    except Exception as e:
        logger.exception(f"Error getting anchor status: {e}")
        return Response({
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAdminUser])
def trigger_anchor(request):
    """
    Manually trigger blockchain anchoring (admin only)
    
    POST /api/blockchain/trigger-anchor/
    
    Body: {} (empty or with options)
    
    Returns:
        {
            "success": true,
            "message": "Anchored 42 commitments",
            "tx_hash": "0x...",
            "merkle_root": "0x...",
            "batch_size": 42,
            "arbiscan_url": "https://sepolia.arbiscan.io/tx/0x..."
        }
    """
    try:
        # Check if blockchain anchoring is enabled
        if not settings.BLOCKCHAIN_ANCHORING.get('ENABLED', False):
            return Response({
                'error': 'Blockchain anchoring is not enabled'
            }, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        
        # Check if there are pending commitments
        pending_count = PendingCommitment.objects.filter(anchored=False).count()
        
        if pending_count == 0:
            return Response({
                'success': False,
                'message': 'No pending commitments to anchor'
            })
        
        # Initialize service and anchor
        service = BlockchainAnchorService()
        result = service.anchor_pending_batch()
        
        if result['success']:
            # Build Arbiscan URL
            network = settings.BLOCKCHAIN_ANCHORING.get('NETWORK')
            arbiscan_base = "https://sepolia.arbiscan.io" if network == "testnet" else "https://arbiscan.io"
            arbiscan_url = f"{arbiscan_base}/tx/{result['tx_hash']}"
            
            return Response({
                'success': True,
                'message': f"Anchored {result['anchored_count']} commitments",
                'tx_hash': result['tx_hash'],
                'merkle_root': result['merkle_root'],
                'batch_size': result['anchored_count'],
                'block_number': result.get('block_number'),
                'arbiscan_url': arbiscan_url
            })
        else:
            return Response({
                'success': False,
                'error': result.get('error', 'Unknown error')
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
    except Exception as e:
        logger.exception(f"Error triggering anchor: {e}")
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def user_commitments(request):
    """
    Get all blockchain-anchored commitments for the current user
    
    GET /api/blockchain/user-commitments/
    
    Query params:
        - anchored_only: true/false (default: false)
    
    Returns:
        {
            "commitments": [
                {
                    "commitment_id": "uuid",
                    "created_at": "2025-11-23T...",
                    "blockchain_anchored": true,
                    "blockchain_hash": "0x...",
                    "challenge_type": "typing",
                    "is_quantum_protected": true
                },
                ...
            ],
            "total_count": 5,
            "anchored_count": 3,
            "pending_count": 2
        }
    """
    try:
        anchored_only = request.GET.get('anchored_only', 'false').lower() == 'true'
        
        # Get user's commitments
        commitments_qs = BehavioralCommitment.objects.filter(
            user=request.user,
            is_active=True
        )
        
        if anchored_only:
            commitments_qs = commitments_qs.filter(blockchain_anchored=True)
        
        commitments_qs = commitments_qs.order_by('-creation_timestamp')
        
        # Build response
        commitments_data = []
        for commitment in commitments_qs:
            data = {
                'commitment_id': str(commitment.commitment_id),
                'created_at': commitment.creation_timestamp,
                'blockchain_anchored': commitment.blockchain_anchored,
                'blockchain_hash': commitment.blockchain_hash,
                'challenge_type': commitment.challenge_type,
                'is_quantum_protected': commitment.is_quantum_protected,
                'encryption_algorithm': commitment.encryption_algorithm
            }
            
            # Add anchor details if anchored
            if commitment.blockchain_anchored:
                data['blockchain_anchored_at'] = commitment.blockchain_anchored_at
                
                # Get Merkle proof if exists
                merkle_proof = MerkleProof.objects.filter(commitment=commitment).first()
                if merkle_proof:
                    data['merkle_root'] = merkle_proof.merkle_root
                    data['tx_hash'] = merkle_proof.blockchain_anchor.tx_hash
            
            commitments_data.append(data)
        
        # Calculate counts
        total_count = commitments_qs.count()
        anchored_count = commitments_qs.filter(blockchain_anchored=True).count()
        pending_count = PendingCommitment.objects.filter(
            user=request.user,
            anchored=False
        ).count()
        
        return Response({
            'commitments': commitments_data,
            'total_count': total_count,
            'anchored_count': anchored_count,
            'pending_count': pending_count
        })
        
    except Exception as e:
        logger.exception(f"Error getting user commitments: {e}")
        return Response({
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

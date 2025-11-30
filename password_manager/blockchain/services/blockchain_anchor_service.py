"""
Blockchain Anchor Service for submitting commitment batches to Arbitrum
"""

import logging
import os
from typing import Dict, List, Optional
from web3 import Web3
from eth_account import Account
from django.conf import settings
from django.utils import timezone
from django.db import transaction

from ..models import BlockchainAnchor, MerkleProof, PendingCommitment
from .merkle_tree_builder import MerkleTreeBuilder, create_commitment_hash

logger = logging.getLogger(__name__)


class BlockchainAnchorService:
    """
    Singleton service for anchoring behavioral commitments to Arbitrum blockchain
    Implements Merkle tree batching for cost efficiency
    """
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self.config = getattr(settings, 'BLOCKCHAIN_ANCHORING', {})
        self.enabled = self.config.get('ENABLED', False)
        
        if not self.enabled:
            logger.info("Blockchain anchoring is disabled")
            self._initialized = True
            return
        
        # Initialize Web3 connection
        self.network = self.config.get('NETWORK', 'testnet')
        self.rpc_url = self.config.get('RPC_URL')
        self.contract_address = self.config.get('CONTRACT_ADDRESS')
        self.batch_size = self.config.get('BATCH_SIZE', 1000)
        
        if not self.rpc_url:
            logger.warning("BLOCKCHAIN_ANCHORING.RPC_URL not configured")
            self._initialized = True
            return
        
        try:
            self.w3 = Web3(Web3.HTTPProvider(self.rpc_url))
            if self.w3.is_connected():
                logger.info(f"Connected to Arbitrum {self.network}: {self.rpc_url}")
            else:
                logger.error(f"Failed to connect to Arbitrum {self.network}")
        except Exception as e:
            logger.error(f"Error connecting to Arbitrum: {e}")
            self.w3 = None
        
        # Load contract ABI (simplified for now - will be loaded from file)
        self.contract_abi = self._get_contract_abi()
        
        # Load private key for signing
        self.private_key = os.environ.get('BLOCKCHAIN_PRIVATE_KEY')
        if self.private_key:
            self.account = Account.from_key(self.private_key)
            logger.info(f"Blockchain deployer account: {self.account.address}")
        else:
            logger.warning("BLOCKCHAIN_PRIVATE_KEY not set - anchoring will not work")
            self.account = None
        
        self.pending_commitments = []
        self._initialized = True
    
    def _get_contract_abi(self) -> List[Dict]:
        """Get the CommitmentRegistry contract ABI"""
        # Simplified ABI with just the functions we need
        return [
            {
                "inputs": [
                    {"internalType": "bytes32", "name": "merkleRoot", "type": "bytes32"},
                    {"internalType": "uint256", "name": "batchSize", "type": "uint256"},
                    {"internalType": "bytes", "name": "signature", "type": "bytes"}
                ],
                "name": "anchorCommitment",
                "outputs": [],
                "stateMutability": "nonpayable",
                "type": "function"
            },
            {
                "inputs": [
                    {"internalType": "bytes32", "name": "merkleRoot", "type": "bytes32"},
                    {"internalType": "bytes32", "name": "leafHash", "type": "bytes32"},
                    {"internalType": "bytes32[]", "name": "proof", "type": "bytes32[]"}
                ],
                "name": "verifyCommitment",
                "outputs": [{"internalType": "bool", "name": "", "type": "bool"}],
                "stateMutability": "view",
                "type": "function"
            },
            {
                "inputs": [{"internalType": "bytes32", "name": "merkleRoot", "type": "bytes32"}],
                "name": "getCommitment",
                "outputs": [
                    {
                        "components": [
                            {"internalType": "bytes32", "name": "merkleRoot", "type": "bytes32"},
                            {"internalType": "uint256", "name": "timestamp", "type": "uint256"},
                            {"internalType": "uint256", "name": "batchSize", "type": "uint256"},
                            {"internalType": "address", "name": "submitter", "type": "address"},
                            {"internalType": "bool", "name": "exists", "type": "bool"}
                        ],
                        "internalType": "struct CommitmentRegistry.Commitment",
                        "name": "",
                        "type": "tuple"
                    }
                ],
                "stateMutability": "view",
                "type": "function"
            }
        ]
    
    def add_commitment(self, user_id: int, commitment_id: int, encrypted_data: str) -> str:
        """
        Add a behavioral commitment to pending batch
        
        Args:
            user_id: User ID
            commitment_id: BehavioralCommitment ID
            encrypted_data: Encrypted embedding data
        
        Returns:
            Commitment hash (hex string)
        """
        if not self.enabled:
            logger.debug("Blockchain anchoring disabled, skipping")
            return None
        
        # Create commitment hash
        commitment_hash = create_commitment_hash(str(commitment_id), encrypted_data)
        
        # Store in pending commitments table
        try:
            from behavioral_recovery.models import BehavioralCommitment
            commitment_obj = BehavioralCommitment.objects.get(id=commitment_id)
            
            pending = PendingCommitment.objects.create(
                user_id=user_id,
                commitment=commitment_obj,
                commitment_hash=commitment_hash
            )
            
            logger.info(f"Added commitment {commitment_hash[:10]}... to pending batch")
            
            # Check if we should auto-anchor
            pending_count = PendingCommitment.objects.filter(is_anchored=False).count()
            if pending_count >= self.batch_size:
                logger.info(f"Batch size reached ({pending_count}), triggering anchor")
                self.anchor_pending_batch()
            
            return commitment_hash
        
        except Exception as e:
            logger.error(f"Error adding commitment to pending batch: {e}")
            return commitment_hash
    
    @transaction.atomic
    def anchor_pending_batch(self) -> Optional[str]:
        """
        Anchor all pending commitments to blockchain
        
        Returns:
            Transaction hash or None if failed
        """
        if not self.enabled or not self.w3 or not self.account:
            logger.warning("Blockchain anchoring not properly configured")
            return None
        
        # Get all pending commitments
        pending = list(PendingCommitment.objects.filter(
            is_anchored=False
        ).select_related('user', 'commitment').order_by('created_at'))
        
        if not pending:
            logger.info("No pending commitments to anchor")
            return None
        
        logger.info(f"Anchoring batch of {len(pending)} commitments")
        
        try:
            # Build Merkle tree
            commitment_dicts = [
                {'commitment_hash': p.commitment_hash}
                for p in pending
            ]
            tree = MerkleTreeBuilder.build_from_commitments(commitment_dicts)
            merkle_root = tree.get_root_hex()
            
            logger.info(f"Built Merkle tree with root: {merkle_root}")
            
            # Sign the commitment
            message_hash = Web3.solidity_keccak(
                ['bytes32', 'uint256'],
                [bytes.fromhex(merkle_root[2:]), len(pending)]
            )
            signature = self.account.sign_message_hash(message_hash)
            
            # Submit to blockchain
            contract = self.w3.eth.contract(
                address=self.contract_address,
                abi=self.contract_abi
            )
            
            # Build transaction
            nonce = self.w3.eth.get_transaction_count(self.account.address)
            
            tx = contract.functions.anchorCommitment(
                bytes.fromhex(merkle_root[2:]),
                len(pending),
                signature.signature
            ).build_transaction({
                'from': self.account.address,
                'nonce': nonce,
                'gas': 500000,  # Estimate, will be calculated
                'gasPrice': self.w3.eth.gas_price,
            })
            
            # Sign and send transaction
            signed_tx = self.w3.eth.account.sign_transaction(tx, self.private_key)
            tx_hash = self.w3.eth.send_raw_transaction(signed_tx.raw_transaction)
            tx_hash_hex = self.w3.to_hex(tx_hash)
            
            logger.info(f"Transaction sent: {tx_hash_hex}")
            
            # Wait for receipt
            receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=300)
            
            if receipt['status'] == 1:
                logger.info(f"Transaction confirmed in block {receipt['blockNumber']}")
                
                # Save to database
                anchor = BlockchainAnchor.objects.create(
                    merkle_root=merkle_root,
                    tx_hash=tx_hash_hex,
                    block_number=receipt['blockNumber'],
                    batch_size=len(pending),
                    network=self.network,
                    gas_used=receipt['gasUsed'],
                    gas_price_wei=tx['gasPrice']
                )
                
                # Create Merkle proofs for each commitment
                for i, pending_commitment in enumerate(pending):
                    proof = tree.get_proof_hex(i)
                    
                    MerkleProof.objects.create(
                        user=pending_commitment.user,
                        commitment=pending_commitment.commitment,
                        commitment_hash=pending_commitment.commitment_hash,
                        merkle_root=merkle_root,
                        proof=proof,
                        leaf_index=i,
                        blockchain_anchor=anchor
                    )
                    
                    # Mark as anchored
                    pending_commitment.is_anchored = True
                    pending_commitment.save()
                
                logger.info(f"Successfully anchored {len(pending)} commitments")
                return tx_hash_hex
            
            else:
                logger.error(f"Transaction failed: {receipt}")
                return None
        
        except Exception as e:
            logger.error(f"Error anchoring batch: {e}", exc_info=True)
            return None
    
    def verify_commitment_on_chain(self, commitment_hash: str) -> bool:
        """
        Verify a commitment exists on the blockchain
        
        Args:
            commitment_hash: Commitment hash to verify
        
        Returns:
            bool: True if verified on-chain
        """
        if not self.enabled or not self.w3:
            return False
        
        try:
            # Get Merkle proof from database
            proof_obj = MerkleProof.objects.filter(
                commitment_hash=commitment_hash
            ).select_related('blockchain_anchor').first()
            
            if not proof_obj:
                logger.warning(f"No Merkle proof found for {commitment_hash}")
                return False
            
            # Call contract verification
            contract = self.w3.eth.contract(
                address=self.contract_address,
                abi=self.contract_abi
            )
            
            merkle_root = bytes.fromhex(proof_obj.merkle_root[2:])
            leaf_hash = bytes.fromhex(commitment_hash)
            proof = [bytes.fromhex(p[2:]) for p in proof_obj.proof]
            
            is_valid = contract.functions.verifyCommitment(
                merkle_root,
                leaf_hash,
                proof
            ).call()
            
            logger.info(f"On-chain verification for {commitment_hash[:10]}...: {is_valid}")
            return is_valid
        
        except Exception as e:
            logger.error(f"Error verifying commitment on-chain: {e}")
            return False
    
    def get_pending_count(self) -> int:
        """Get count of pending (not yet anchored) commitments"""
        return PendingCommitment.objects.filter(is_anchored=False).count()
    
    def get_stats(self) -> Dict:
        """Get blockchain anchoring statistics"""
        return {
            'enabled': self.enabled,
            'network': self.network,
            'pending_count': self.get_pending_count(),
            'total_anchors': BlockchainAnchor.objects.count(),
            'total_proofs': MerkleProof.objects.count(),
            'batch_size': self.batch_size,
        }


# Singleton instance
def get_blockchain_anchor_service() -> BlockchainAnchorService:
    """Get the singleton BlockchainAnchorService instance"""
    return BlockchainAnchorService()


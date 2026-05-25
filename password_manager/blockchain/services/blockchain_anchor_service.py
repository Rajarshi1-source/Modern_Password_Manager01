"""
Blockchain Anchor Service for submitting commitment batches to Arbitrum
"""

import logging
import os
import threading
from typing import Dict, List, Optional
from web3 import Web3
from eth_account.messages import encode_defunct
from django.conf import settings
from django.utils import timezone
from django.db import transaction

from ..models import BlockchainAnchor, MerkleProof, PendingCommitment
from .exceptions import classify
from .key_provider import get_key_provider
from .merkle_tree_builder import MerkleTreeBuilder, create_commitment_hash
from shared.circuit_breaker import blockchain_breaker, CircuitBreakerOpen

logger = logging.getLogger(__name__)


class BlockchainAnchorService:
    """
    Singleton service for anchoring behavioral commitments to Arbitrum blockchain
    Implements Merkle tree batching for cost efficiency
    """
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        with cls._lock:
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
        
        # Load signing key via the KeyProvider abstraction. Defaults to
        # EnvKeyProvider (reads BLOCKCHAIN_PRIVATE_KEY); switch to
        # KmsKeyProvider in production by setting
        # BLOCKCHAIN_KEY_PROVIDER='kms' + BLOCKCHAIN_KMS_KEY_ID. See
        # blockchain/services/key_provider.py for the C7 follow-up design.
        self.key_provider = get_key_provider()
        if self.key_provider.is_available:
            logger.debug(
                "Blockchain signer ready: address=%s, provider=%s",
                self.key_provider.address, self.key_provider.provider_kind,
            )
        else:
            logger.warning(
                "Blockchain signer unavailable (provider=%s); anchoring "
                "will not work until the key is configured.",
                self.key_provider.provider_kind,
            )

        # PR #262 cutover safety check (runs once at singleton init):
        # if the configured CONTRACT_ADDRESS is set but the address has
        # no on-chain bytecode, the operator likely deployed the new
        # Django code but forgot to redeploy the contract (or kept the
        # pre-PR-262 address in env). Log a loud warning at boot so the
        # ops team sees it BEFORE the first anchor batch silently fails.
        if self.w3 and self.contract_address:
            try:
                code = self.w3.eth.get_code(
                    Web3.to_checksum_address(self.contract_address)
                )
                if not code or len(code) <= 2:
                    logger.error(
                        "CommitmentRegistry address %s has NO on-chain "
                        "bytecode. Anchoring will revert until a contract "
                        "is deployed and the env var updated. See "
                        "docs/DEPLOYMENT_PR262.md.",
                        self.contract_address,
                    )
            except Exception as exc:
                logger.debug(
                    "Skipping CommitmentRegistry bytecode preflight: %s",
                    exc,
                )

        self.pending_commitments = []

        # Audit-fix H4 + PR #272 review (CodeRabbit major): the nonce
        # manager + its protective lock are created eagerly here so two
        # concurrent `anchor_pending_batch` callers can't race on the
        # lock construction itself (`hasattr` is not atomic).
        # `__init__` runs under the singleton lock so this assignment
        # happens exactly once for the process.
        import threading as _threading
        self._nonce_manager = None
        self._nonce_manager_lock = _threading.Lock()

        self._initialized = True
    
    def _get_contract_abi(self) -> List[Dict]:
        """Get the CommitmentRegistry contract ABI (post-audit)."""
        return [
            # anchorCommitment — now permissionless at the tx level; the
            # signature must recover to an address in `authorizedSigners`.
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
            # verifyCommitment — view (was non-view + event emit before C2 fix).
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
            # authorizedSigners(address) -> bool — exposed for operator tooling.
            {
                "inputs": [{"internalType": "address", "name": "", "type": "address"}],
                "name": "authorizedSigners",
                "outputs": [{"internalType": "bool", "name": "", "type": "bool"}],
                "stateMutability": "view",
                "type": "function"
            },
            # addAuthorizedSigner / removeAuthorizedSigner — owner only.
            {
                "inputs": [{"internalType": "address", "name": "signer", "type": "address"}],
                "name": "addAuthorizedSigner",
                "outputs": [],
                "stateMutability": "nonpayable",
                "type": "function"
            },
            {
                "inputs": [{"internalType": "address", "name": "signer", "type": "address"}],
                "name": "removeAuthorizedSigner",
                "outputs": [],
                "stateMutability": "nonpayable",
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
    
    def add_commitment(
        self,
        user_id: int,
        commitment_id: int,
        encrypted_data: str,
        auto_anchor: bool = True,
    ) -> Optional[str]:
        """
        Add a behavioral commitment to the pending batch.

        Args:
            user_id: User ID
            commitment_id: BehavioralCommitment ID
            encrypted_data: Encrypted embedding data
            auto_anchor: When True (default) and the batch threshold is
                reached, trigger ``anchor_pending_batch()`` immediately.
                The rehash management command passes False so it can
                stage all new rows before any anchoring happens — otherwise
                the anchorer can see legacy and replacement rows together
                and anchor a mixed batch.

        Returns:
            The commitment hash (hex string) iff the PendingCommitment row
            was successfully persisted. ``None`` if the feature is
            disabled or the DB insert failed — previously the helper
            returned the computed hash even on insert failure, which let
            callers like the rehash command silently treat a failed
            enqueue as success and delete the original row. Tightened per
            CodeRabbit review of PR #262.
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

            # Check if we should auto-anchor.
            if auto_anchor:
                pending_count = PendingCommitment.objects.filter(is_anchored=False).count()
                if pending_count >= self.batch_size:
                    logger.info(f"Batch size reached ({pending_count}), triggering anchor")
                    self.anchor_pending_batch()

            return commitment_hash

        except Exception as e:
            logger.error(
                "Error adding commitment to pending batch: %s "
                "(commitment_id=%s); returning None so the caller treats "
                "this as a failed enqueue.",
                e, commitment_id,
            )
            return None
    
    @transaction.atomic
    def anchor_pending_batch(self) -> Optional[str]:
        """
        Anchor all pending commitments to blockchain
        
        Returns:
            Transaction hash or None if failed
        """
        if not self.enabled or not self.w3 or not self.key_provider.is_available:
            logger.warning("Blockchain anchoring not properly configured")
            return None
        signer_address = self.key_provider.address

        try:
            blockchain_breaker.before_call()
        except CircuitBreakerOpen as e:
            logger.warning(f"Blockchain circuit breaker OPEN: {e}")
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
            
            # Sign the commitment. The on-chain contract binds the
            # signed payload to (chainId, contract address) so a
            # signature minted for one deployment can't be replayed on
            # another. Match its `abi.encode(block.chainid, address(this),
            # merkleRoot, batchSize)` exactly — added per CodeRabbit
            # review of PR #262.
            chain_id = self.w3.eth.chain_id
            contract_addr = Web3.to_checksum_address(self.contract_address)
            message_hash = Web3.solidity_keccak(
                ['uint256', 'address', 'bytes32', 'uint256'],
                [chain_id, contract_addr, bytes.fromhex(merkle_root[2:]), len(pending)]
            )
            msg = encode_defunct(primitive=message_hash)
            signature = self.key_provider.sign_message(msg)
            
            # Submit to blockchain
            contract = self.w3.eth.contract(
                address=self.contract_address,
                abi=self.contract_abi
            )

            # Preflight: confirm our signer is still authorized on the
            # contract before paying gas to send a tx that would just
            # revert. Catches the "owner rotated us out" case loudly
            # instead of leaving anchoring quietly broken. Added per
            # CodeRabbit review of PR #262.
            try:
                if not contract.functions.authorizedSigners(
                    signer_address
                ).call():
                    logger.error(
                        "Blockchain signer %s is not in CommitmentRegistry."
                        "authorizedSigners; refusing to broadcast. Have the "
                        "registry owner call addAuthorizedSigner() and retry.",
                        signer_address,
                    )
                    # Audit-fix M10 + PR #273 review: a deterministic
                    # "unauthorized signer" outcome is a contract-revert
                    # equivalent, not infra. Wrap through `classify()`
                    # so the breaker doesn't trip on it.
                    blockchain_breaker.on_failure(
                        classify(PermissionError("unauthorized signer"))
                    )
                    return None
            except Exception as e:
                # Fail closed: if we can't verify the signer is still
                # authorized, don't burn gas on an anchorCommitment() that
                # might just revert (and tie up the on-chain nonce). The
                # circuit breaker takes the failure so the retry path
                # recovers when the read becomes healthy again. Tightened
                # per CodeRabbit review of PR #262.
                logger.error(
                    "authorizedSigners preflight call failed: %s; refusing "
                    "to broadcast until signer authorization can be confirmed.",
                    e,
                )
                blockchain_breaker.on_failure(classify(e))
                return None

            # Audit-fix H4 + PR #272 review: thread-safe nonce
            # reservation with double-checked lazy init under the
            # `_nonce_manager_lock` created in __init__. Before the
            # lock, two concurrent `anchor_pending_batch` callers
            # could both observe `_nonce_manager is None` and
            # construct separate managers, each seeded from the same
            # on-chain pending nonce — the exact race H4 was
            # supposed to fix.
            if self._nonce_manager is None:
                with self._nonce_manager_lock:
                    if self._nonce_manager is None:
                        from smart_contracts.services.nonce_manager import NonceManager
                        self._nonce_manager = NonceManager(self.w3, signer_address)

            # Lease the nonce (PR #272 review). If anything between
            # here and a successful send_raw_transaction raises, the
            # lease's __exit__ releases the nonce so the next batch
            # doesn't sit behind a permanent gap.
            lease = self._nonce_manager.lease()
            try:
                tx = contract.functions.anchorCommitment(
                    bytes.fromhex(merkle_root[2:]),
                    len(pending),
                    signature.signature
                ).build_transaction({
                    'from': signer_address,
                    'nonce': lease.value,
                    'gas': 500000,  # Estimate, will be calculated
                    'gasPrice': self.w3.eth.gas_price,
                })

                # Sign and send transaction via the KeyProvider so the
                # raw private bytes don't need to be in scope here.
                raw_tx = self.key_provider.sign_transaction(tx, self.w3)
                try:
                    tx_hash = self.w3.eth.send_raw_transaction(raw_tx)
                except Exception as send_err:
                    msg = str(send_err).lower()
                    if 'nonce' in msg or 'replacement' in msg:
                        self._nonce_manager.resync()
                    raise
                # Broadcast succeeded — chain has consumed this nonce
                # regardless of what wait_for_receipt or DB writes do
                # below. Commit so the lease is settled.
                lease.commit()
            except Exception:
                # Release the lease back to the pool so the next batch
                # can reuse the slot.
                lease.release()
                raise
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
                blockchain_breaker.on_success()
                return tx_hash_hex
            
            else:
                # Receipt says status=0 → the tx was mined but reverted.
                # Capture enough context for the breaker's failure log:
                # the tx hash is the most useful pointer for after-the-
                # fact triage. The "reverted" message routes the wrapped
                # RuntimeError through `classify()` as
                # `BlockchainContractRevert`, so the breaker won't trip
                # on per-user condition mismatches (the M10 invariant).
                logger.error(f"Transaction failed: {receipt}")
                blockchain_breaker.on_failure(
                    classify(RuntimeError(
                        "Anchor transaction reverted "
                        f"(tx_hash={receipt.get('transactionHash')}, "
                        f"block={receipt.get('blockNumber')})"
                    ))
                )
                return None

        except Exception as e:
            # Audit-fix M10: classify before passing to the breaker so
            # deterministic contract reverts don't count toward the
            # failure threshold.
            blockchain_breaker.on_failure(classify(e))
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
    
    def verify_proof_locally(self, merkle_root: str, leaf_hash: str, proof: list) -> bool:
        """
        Verify a Merkle proof locally without an on-chain call.

        Uses :meth:`MerkleTreeBuilder.hash_pair` so the local and on-chain
        verification paths are guaranteed to use the same keccak256
        sorted-pair construction.
        """
        try:
            computed = bytes.fromhex(leaf_hash.replace('0x', ''))
            for sibling_hex in proof:
                sibling = bytes.fromhex(sibling_hex.replace('0x', ''))
                computed = MerkleTreeBuilder.hash_pair(computed, sibling)

            expected = bytes.fromhex(merkle_root.replace('0x', ''))
            return computed == expected
        except Exception as e:
            logger.error(f"Error verifying proof locally: {e}")
            return False

    def verify_proof_on_chain(self, merkle_root: str, leaf_hash: str, proof: list) -> bool:
        """
        Verify a Merkle proof on-chain via the smart contract.

        Returns a plain bool for backward compatibility. ``False`` here
        is OVERLOADED: it can mean "feature disabled", "genuine
        mismatch", OR "RPC error". Callers that need to distinguish
        those cases (e.g. the ``verify_random_proofs`` Celery task,
        which would otherwise raise false Sentry alerts on transient
        RPC outages) must use ``verify_proof_on_chain_status`` below.
        """
        return self.verify_proof_on_chain_status(
            merkle_root, leaf_hash, proof,
        ) == 'ok'

    def verify_proof_on_chain_status(
        self, merkle_root: str, leaf_hash: str, proof: list,
    ) -> str:
        """
        Structured variant of ``verify_proof_on_chain``.

        Returns one of:
            'ok'         — contract confirmed the proof.
            'mismatch'   — contract returned False; data divergence.
            'rpc_error'  — RPC/transport/decoding failure; transient,
                           do NOT treat as a mismatch alert.
            'disabled'   — feature flag off or web3 unavailable.

        Added per CodeRabbit + Codex review of PR #274: the previous
        bool API caused the verifier Celery task to fire false
        mismatch alerts whenever the RPC blipped, since both real
        mismatches and connection errors collapsed to ``False``.
        """
        if not self.enabled or not self.w3:
            return 'disabled'
        try:
            contract = self.w3.eth.contract(
                address=self.contract_address,
                abi=self.contract_abi,
            )
            root_bytes = bytes.fromhex(merkle_root.replace('0x', ''))
            leaf_bytes = bytes.fromhex(leaf_hash.replace('0x', ''))
            proof_bytes = [bytes.fromhex(p.replace('0x', '')) for p in proof]
            result = contract.functions.verifyCommitment(
                root_bytes, leaf_bytes, proof_bytes
            ).call()
            return 'ok' if bool(result) else 'mismatch'
        except Exception as e:
            # Includes RPC connection errors, JSON-RPC decode failures,
            # contract-not-found-at-address reverts. Callers should
            # treat this as a transient-error retry signal, not a data
            # divergence alert.
            logger.error(f"Error verifying proof on-chain: {e}")
            return 'rpc_error'

    def verify_anchor_on_chain(self, merkle_root: str, tx_hash: str = None) -> bool:
        """
        Verify that a given merkle_root was anchored on the blockchain.
        """
        if not self.enabled or not self.w3:
            return False
        try:
            contract = self.w3.eth.contract(
                address=self.contract_address,
                abi=self.contract_abi,
            )
            root_bytes = bytes.fromhex(merkle_root.replace('0x', ''))
            result = contract.functions.getCommitment(root_bytes).call()
            return result[-1]  # 'exists' flag
        except Exception as e:
            logger.error(f"Error verifying anchor on-chain: {e}")
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


"""
ArbitrumAnchor (Phase 2b).

Reuses the already-wired ``blockchain.services.blockchain_anchor_service``
Web3 connection + deployer key + contract ABI to submit a reputation-batch
Merkle root to the existing ``CommitmentRegistry.anchorCommitment`` contract.
The contract is content-agnostic: it treats ``(merkleRoot, batchSize, signature)``
as opaque data, so reusing it for reputation batches is deliberate — it gives
us tamper-evident anchoring without deploying a second contract.

Design notes:
  * This adapter intentionally does NOT import any behavioral_recovery models
    or the ``add_commitment`` / ``anchor_pending_batch`` flows of the
    behavioral service; it only borrows the ``Web3`` client, the deployer
    account, and the contract ABI/address.
  * If ``BLOCKCHAIN_ANCHORING`` is disabled (e.g. in CI), the adapter
    gracefully returns a ``skipped`` result so the reputation event pipeline
    keeps making forward progress.
  * The per-submission signature uses ``EIP-191 personal_sign`` exactly like
    the behavioral service, so the deployed contract's signature check
    (if any) continues to validate.
"""

from __future__ import annotations

import logging

from .base import AnchorAdapter, AnchorResult

logger = logging.getLogger(__name__)


class ArbitrumAnchor(AnchorAdapter):
    """Submits reputation Merkle roots to the CommitmentRegistry contract."""

    name = "arbitrum"

    def __init__(self) -> None:
        # Defer import so missing web3 / eth_account does not break Phase 2a.
        from blockchain.services.blockchain_anchor_service import (
            BlockchainAnchorService,
        )

        self._service = BlockchainAnchorService()

    def is_enabled(self) -> bool:
        svc = self._service
        return bool(getattr(svc, "enabled", False) and svc.w3 and svc.account)

    def submit_batch(self, *, merkle_root_hex: str, batch_size: int) -> AnchorResult:
        svc = self._service
        if not self.is_enabled():
            return AnchorResult(
                status="skipped",
                network=getattr(svc, "network", "arbitrum"),
                error="BlockchainAnchorService is disabled or not configured.",
            )

        # The behavioral service's anchor_pending_batch is tied to its own
        # pending-commitments table. We only want to submit OUR merkle root,
        # so we call the contract directly using the behavioral service's
        # Web3 client + signer. This keeps the two anchoring pipelines fully
        # independent while sharing the same deployer key + RPC.
        try:
            from eth_account.messages import encode_defunct
            from web3 import Web3

            if merkle_root_hex.startswith("0x"):
                root_bytes = bytes.fromhex(merkle_root_hex[2:])
            else:
                root_bytes = bytes.fromhex(merkle_root_hex)
            if len(root_bytes) != 32:
                return AnchorResult(
                    status="failed",
                    error=f"Merkle root must be 32 bytes, got {len(root_bytes)}.",
                )

            message_hash = Web3.solidity_keccak(
                ["bytes32", "uint256"],
                [root_bytes, int(batch_size)],
            )
            signed_msg = svc.account.sign_message(encode_defunct(primitive=message_hash))

            contract = svc.w3.eth.contract(
                address=svc.contract_address,
                abi=svc.contract_abi,
            )
            nonce = svc.w3.eth.get_transaction_count(svc.account.address)
            tx = contract.functions.anchorCommitment(
                root_bytes,
                int(batch_size),
                signed_msg.signature,
            ).build_transaction(
                {
                    "from": svc.account.address,
                    "nonce": nonce,
                    "gas": 500_000,
                    "gasPrice": svc.w3.eth.gas_price,
                }
            )
            signed_tx = svc.w3.eth.account.sign_transaction(tx, svc.private_key)
            raw_tx = (
                getattr(signed_tx, "raw_transaction", None)
                or getattr(signed_tx, "rawTransaction", None)
            )
            tx_hash = svc.w3.eth.send_raw_transaction(raw_tx)
            tx_hash_hex = svc.w3.to_hex(tx_hash)
            logger.info("Reputation batch submitted: %s (size=%s)", tx_hash_hex, batch_size)

            # Best-effort wait for confirmation; on timeout we return "submitted"
            # and let a reconciliation job upgrade the status later.
            try:
                receipt = svc.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=60)
                if receipt.get("status") == 1:
                    return AnchorResult(
                        status="confirmed",
                        tx_hash=tx_hash_hex,
                        block_number=receipt.get("blockNumber"),
                        network=svc.network,
                    )
                return AnchorResult(
                    status="failed",
                    tx_hash=tx_hash_hex,
                    network=svc.network,
                    error=f"Tx reverted in block {receipt.get('blockNumber')}",
                )
            except Exception as wait_exc:  # noqa: BLE001
                logger.warning("Timed out waiting for reputation anchor: %s", wait_exc)
                return AnchorResult(
                    status="submitted",
                    tx_hash=tx_hash_hex,
                    network=svc.network,
                )
        except Exception as exc:  # noqa: BLE001
            logger.exception("ArbitrumAnchor submit_batch failed")
            return AnchorResult(
                status="failed",
                network=getattr(svc, "network", "arbitrum"),
                error=str(exc)[:256],
            )

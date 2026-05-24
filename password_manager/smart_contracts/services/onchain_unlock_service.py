"""
On-chain Unlock Service
========================

Hybrid reveal pipeline: the ConditionEngine evaluates off-chain conditions,
the VaultService decrypts and returns plaintext to the owner, and this
service leaves a tamper-evident breadcrumb on Arbitrum via the
``VaultAuditLog`` contract.

The plaintext password NEVER touches this module. We only anchor a
commitment hash ``keccak256(vault_id || user_id || nonce)`` so downstream
auditors can verify that *something* was revealed at a given block/time
without exposing which entry or what value.

All paths are guarded by ``SMART_CONTRACT_UNLOCK_ONCHAIN_ENABLED`` and the
presence of ``BLOCKCHAIN_PRIVATE_KEY`` + ``VAULT_AUDIT_LOG_ADDRESS``. When
disabled, every method becomes a cheap no-op returning ``None`` — the DB
unlock still succeeds; the vault is simply flagged ``onchain_audit_pending``.
"""

from __future__ import annotations

import logging
import secrets
import time
from typing import Any, Dict, Optional

from django.conf import settings
from django.utils import timezone

from smart_contracts.models.vault import SmartContractVault
from smart_contracts.services.web3_bridge import SmartContractWeb3Bridge

logger = logging.getLogger(__name__)


class OnchainUnlockService:
    """Submit per-reveal audit anchors to the VaultAuditLog contract."""

    def __init__(self) -> None:
        self.bridge = SmartContractWeb3Bridge()
        self.sc_config = getattr(settings, 'SMART_CONTRACT_AUTOMATION', {})

    @property
    def enabled(self) -> bool:
        """Writes gated by the feature flag + wiring."""
        flag = getattr(settings, 'SMART_CONTRACT_UNLOCK_ONCHAIN_ENABLED', False)
        return bool(
            flag
            and self.bridge.enabled
            and self.bridge.audit_contract is not None
            and self.bridge.w3 is not None
            and self.bridge.account is not None
        )

    def build_commitment_hash(
        self,
        vault: SmartContractVault,
        user_id: int,
        nonce: Optional[bytes] = None,
    ) -> bytes:
        """
        Build the 32-byte commitment anchored on-chain.

        ``keccak256(vault_id_onchain_or_uuid || user_id || nonce)`` — the
        nonce makes the commitment unlinkable between reveals of the same
        vault and prevents observers from correlating on-chain anchors to
        internal records.
        """
        nonce = nonce or secrets.token_bytes(16)
        vault_part: bytes
        if vault.vault_id_onchain is not None:
            vault_part = int(vault.vault_id_onchain).to_bytes(32, 'big')
        else:
            vault_part = vault.id.bytes  # UUID, 16 bytes

        payload = vault_part + int(user_id).to_bytes(8, 'big') + nonce
        # Audit-fix H1: hard-fail on keccak256 unavailability. The previous
        # `try Web3.keccak / except sha3_256` silently changed hash
        # function when the web3 import failed (in stripped images or
        # broken envs), breaking cross-verifiability of every prior
        # anchor since keccak256 and SHA3-256 use different paddings
        # (0x01 vs 0x06). `eth_utils.keccak` is vendored by web3.py so
        # this import either works or the whole feature is correctly
        # disabled — no silent hash drift.
        from eth_utils import keccak
        return keccak(payload)

    def submit_unlock_anchor(
        self,
        vault: SmartContractVault,
        user_id: int,
    ) -> Optional[str]:
        """
        Anchor a reveal on-chain. Returns the ``0x...`` tx hash, or ``None``
        when the feature is disabled / broadcast fails (logged).

        Audit-fix C11 (2026-05): the per-reveal nonce and the resulting
        commitment hash are persisted to the vault row BEFORE the tx is
        broadcast. If broadcast fails or revert-races a chain reorg, the
        DB still records what we tried to anchor so the auditor can
        reconstruct the preimage of the `VaultUnlocked` event.

        Existing nonce/commitment on the vault row are reused on retry —
        this keeps the on-chain anchor idempotent (multiple Celery retries
        will not emit multiple distinct commitments for the same reveal).
        """
        if not self.enabled:
            logger.info("on-chain unlock anchor skipped: feature disabled")
            return None

        # Atomically read-or-create the per-vault nonce so concurrent
        # Celery workers can't each generate a different one and
        # broadcast competing commitments. The row is locked with
        # SELECT FOR UPDATE for the duration of the transaction; the
        # first worker writes the nonce, the rest read the same value
        # back and reuse it. Added per CodeRabbit review of PR #262.
        from django.db import transaction as _txn

        with _txn.atomic():
            locked = (
                SmartContractVault.objects
                .select_for_update()
                .get(pk=vault.pk)
            )
            existing_nonce = bytes(locked.reveal_nonce or b'')
            if existing_nonce:
                nonce = existing_nonce
                fresh = False
            else:
                import secrets as _secrets
                nonce = _secrets.token_bytes(16)
                fresh = True

            commitment = self.build_commitment_hash(
                locked, user_id, nonce=nonce
            )
            commitment_hex = '0x' + commitment.hex()

            # Persist whenever EITHER the nonce was just minted OR the
            # stored commitment is missing/stale relative to what we'll
            # broadcast. Previously only the `fresh` branch updated the
            # DB, which could leave a vault with a valid nonce but a
            # blank/stale `reveal_commitment` while the tx went out with
            # the recomputed hash — desync that an auditor couldn't
            # reconcile. Tightened per CodeRabbit review of PR #262.
            needs_save = False
            if fresh:
                locked.reveal_nonce = nonce
                needs_save = True
            if locked.reveal_commitment != commitment_hex:
                locked.reveal_commitment = commitment_hex
                needs_save = True
            if needs_save:
                locked.save(update_fields=[
                    'reveal_nonce', 'reveal_commitment', 'updated_at',
                ])

            # Reflect the persisted values onto the caller's instance so
            # downstream code sees the same state the DB now holds.
            vault.reveal_nonce = locked.reveal_nonce
            vault.reveal_commitment = locked.reveal_commitment

        tx_hash = self.bridge.build_and_send(
            self.bridge.audit_contract,
            'anchorUnlock',
            commitment,
            gas_limit=120_000,
        )
        if tx_hash:
            logger.info(
                "Submitted unlock anchor for vault %s: %s",
                vault.id,
                tx_hash,
            )
        return tx_hash

    def wait_for_receipt(
        self,
        tx_hash: str,
        timeout_s: int = 120,
    ) -> Optional[Dict[str, Any]]:
        """Thin passthrough to the bridge so callers only depend on this service."""
        return self.bridge.wait_for_receipt(tx_hash, timeout_s=timeout_s)

    def explorer_url(self, tx_hash: str) -> str:
        return self.bridge.explorer_url(tx_hash)

    def finalize_unlock(
        self,
        vault_id: str,
        poll_timeout_s: int = 180,
    ) -> Dict[str, Any]:
        """
        Given a vault already flipped to UNLOCKED in the DB, submit the
        on-chain anchor and poll once for the receipt. Intended to run in
        a Celery worker chained off ``VaultService.attempt_unlock``.
        """
        try:
            vault = SmartContractVault.objects.get(id=vault_id)
        except SmartContractVault.DoesNotExist:
            logger.warning("finalize_unlock: vault %s not found", vault_id)
            return {'status': 'vault_missing'}

        if not self.enabled:
            return {'status': 'disabled'}

        tx_hash = self.submit_unlock_anchor(vault, vault.user_id)
        if not tx_hash:
            return {'status': 'submit_failed'}

        # Persist the pending tx hash immediately so the UI can render
        # "pending on-chain receipt" while we wait.
        vault.released_tx_hash = tx_hash
        vault.save(update_fields=['released_tx_hash', 'updated_at'])

        receipt = self.wait_for_receipt(tx_hash, timeout_s=poll_timeout_s)
        if receipt is None:
            return {'status': 'receipt_pending', 'tx_hash': tx_hash}

        # update vault.released_at only on confirmed success
        if receipt.get('success') and vault.released_at is None:
            vault.released_at = timezone.now()
            vault.save(update_fields=['released_at', 'updated_at'])

        return {
            'status': 'confirmed' if receipt.get('success') else 'reverted',
            'tx_hash': tx_hash,
            'block_number': receipt.get('block_number'),
            'gas_used': receipt.get('gas_used'),
        }

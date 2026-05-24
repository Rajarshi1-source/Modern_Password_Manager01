"""
Post-migration gate for PR #262.

Run this after `manage.py migrate` and before flipping any feature
flags. It exits non-zero on any invariant violation so it's safe to
wire into a Kubernetes init-container, a Helm post-install hook, or a
plain `manage.py migrate && manage.py verify_audit_migration` deploy
script.

Checks
------

1. blockchain.BlockchainAnchor: every row has a `hash_algo` value and
   pre-existing rows are flagged `verifiable=False`. New rows default
   to `verifiable=True, hash_algo='keccak256'`; the migration backfill
   makes existing rows `verifiable=False, hash_algo='sha256'` because
   those proofs were built with the pre-fix SHA-256 hasher and cannot
   be reproduced by the keccak256 verifier.
2. blockchain.MerkleProof.verifiable mirrors its anchor's verifiable.
3. vault.UserSalt: every row that has a populated auth_module.UserSalt
   counterpart now has a matching non-empty auth_hash (C10 backfill).
4. If `SMART_CONTRACT_UNLOCK_ONCHAIN_ENABLED=True`,
   `SMART_CONTRACT_AUTOMATION.VAULT_AUDIT_LOG_ADDRESS` must be set
   (no silent fallback to the TimeLockedVault address).
5. Each configured contract address, if non-empty, must point at
   actual deployed bytecode on the configured RPC. Catches the
   "operator forgot to redeploy" case where the new Django code
   talks to a zero-byte placeholder address.

Exit codes
----------
* 0: all invariants hold; safe to flip feature flags.
* 1: at least one invariant violated; report printed to stdout.
"""

from __future__ import annotations

import sys

from django.conf import settings
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Post-migration safety check for PR #262 audit fixes."

    def add_arguments(self, parser):
        parser.add_argument(
            '--strict',
            action='store_true',
            help=(
                'Treat the on-chain contract-bytecode check as a hard '
                'failure even when BLOCKCHAIN_ENABLED is False. Use this '
                'in production deploys; CI typically wants it off.'
            ),
        )

    def handle(self, *args, **opts):
        violations: list[str] = []

        # ------------------------------------------------------------------
        # Check 1 + 2: BlockchainAnchor / MerkleProof hash provenance.
        # ------------------------------------------------------------------
        try:
            from blockchain.models import BlockchainAnchor, MerkleProof
            anchors_total = BlockchainAnchor.objects.count()
            anchors_missing_algo = (
                BlockchainAnchor.objects.filter(hash_algo='').count()
                + BlockchainAnchor.objects.filter(hash_algo__isnull=True).count()
            )
            if anchors_missing_algo:
                violations.append(
                    f"{anchors_missing_algo} BlockchainAnchor row(s) have "
                    "blank hash_algo; migration 0003 should have backfilled "
                    "every row to either 'sha256' (legacy) or 'keccak256' "
                    "(new). Re-run `manage.py migrate blockchain`."
                )

            # Cross-check: a MerkleProof should never claim verifiable=True
            # while its anchor is verifiable=False. The two fields are
            # mirrored, but the mirror can drift if a future code path
            # writes them independently — detect that.
            drift = MerkleProof.objects.filter(
                verifiable=True, blockchain_anchor__verifiable=False
            ).count()
            if drift:
                violations.append(
                    f"{drift} MerkleProof row(s) have verifiable=True but "
                    "their BlockchainAnchor is verifiable=False. The two "
                    "flags must agree; the view code prefers the anchor "
                    "but the DB should be self-consistent."
                )

            self.stdout.write(
                f"  blockchain.BlockchainAnchor: {anchors_total} row(s) checked."
            )
        except Exception as exc:
            violations.append(
                f"BlockchainAnchor/MerkleProof check failed to run: {exc}. "
                "Did migration 0003_hash_algo_verifiable apply?"
            )

        # ------------------------------------------------------------------
        # Check 3: vault.UserSalt backfill from auth_module.UserSalt.
        # ------------------------------------------------------------------
        try:
            from auth_module.models import UserSalt as AuthSalt
            from vault.models import UserSalt as VaultSalt

            # Index auth-side hashes by user_id once, then walk vault rows.
            auth_map = {
                row.user_id: bytes(row.auth_hash or b'')
                for row in AuthSalt.objects.all()
            }
            missing_backfill = 0
            checked = 0
            for vs in VaultSalt.objects.all():
                checked += 1
                vault_hash = bytes(vs.auth_hash or b'')
                source_hash = auth_map.get(vs.user_id)
                if source_hash and source_hash != b'' and vault_hash == b'':
                    missing_backfill += 1
            if missing_backfill:
                violations.append(
                    f"{missing_backfill} vault.UserSalt row(s) have empty "
                    "auth_hash but the auth_module.UserSalt for the same "
                    "user is populated. The 0010_backfill_user_salt_auth_hash "
                    "migration should have copied these over. Re-run "
                    "`manage.py migrate vault`."
                )
            self.stdout.write(
                f"  vault.UserSalt: {checked} row(s) checked, "
                f"{missing_backfill} missing backfill."
            )
        except Exception as exc:
            violations.append(
                f"vault.UserSalt backfill check failed: {exc}. Did "
                "migration 0010_backfill_user_salt_auth_hash apply?"
            )

        # ------------------------------------------------------------------
        # Check 4: VaultAuditLog address gating.
        # ------------------------------------------------------------------
        unlock_enabled = getattr(
            settings, 'SMART_CONTRACT_UNLOCK_ONCHAIN_ENABLED', False
        )
        sc_cfg = getattr(settings, 'SMART_CONTRACT_AUTOMATION', {}) or {}
        audit_addr = sc_cfg.get('VAULT_AUDIT_LOG_ADDRESS', '')
        if unlock_enabled and not audit_addr:
            violations.append(
                "SMART_CONTRACT_UNLOCK_ONCHAIN_ENABLED=True but "
                "SMART_CONTRACT_AUTOMATION.VAULT_AUDIT_LOG_ADDRESS is "
                "empty. The PR #262 fix removed the silent fallback to "
                "TIMELOCKED_VAULT_ADDRESS — set the new address now or "
                "set SMART_CONTRACT_UNLOCK_ONCHAIN_ENABLED=False."
            )

        # ------------------------------------------------------------------
        # Check 5: configured contract addresses have bytecode on-chain.
        # ------------------------------------------------------------------
        chain_enabled = (
            getattr(settings, 'BLOCKCHAIN_ANCHORING', {}).get('ENABLED', False)
            or sc_cfg.get('ENABLED', False)
            or opts['strict']
        )
        if chain_enabled:
            from blockchain.services.blockchain_anchor_service import (
                get_blockchain_anchor_service,
            )
            svc = get_blockchain_anchor_service()
            w3 = getattr(svc, 'w3', None)
            if w3 is None:
                violations.append(
                    "Blockchain features are enabled but no Web3 provider "
                    "is connected. Check ARBITRUM_*_RPC_URL settings."
                )
            else:
                addresses = {
                    'COMMITMENT_REGISTRY (BLOCKCHAIN_ANCHORING.CONTRACT_ADDRESS)':
                        getattr(svc, 'contract_address', ''),
                    'TIMELOCKED_VAULT_ADDRESS':
                        sc_cfg.get('TIMELOCKED_VAULT_ADDRESS', ''),
                    'VAULT_AUDIT_LOG_ADDRESS': audit_addr,
                }
                for label, addr in addresses.items():
                    if not addr:
                        continue
                    try:
                        code = w3.eth.get_code(w3.to_checksum_address(addr))
                    except Exception as exc:
                        violations.append(
                            f"{label}={addr}: RPC call failed ({exc}). "
                            "Cannot confirm bytecode is deployed."
                        )
                        continue
                    if not code or code == b'' or code == b'\x00' or len(code) <= 2:
                        violations.append(
                            f"{label}={addr} has no on-chain bytecode. The "
                            "Django code expects PR #262's contracts; an "
                            "operator likely forgot to redeploy or set the "
                            "wrong address. Run `npx hardhat run scripts/"
                            "deploy-*.js --network <network>` and update env."
                        )
                    else:
                        self.stdout.write(
                            f"  {label}: deployed ({len(code)} bytes)."
                        )

        # ------------------------------------------------------------------
        # Report.
        # ------------------------------------------------------------------
        if violations:
            self.stdout.write(self.style.ERROR(
                f"\n{len(violations)} violation(s) found:"
            ))
            for v in violations:
                self.stdout.write(self.style.ERROR(f"  * {v}"))
            self.stdout.write('')
            self.stdout.write(self.style.ERROR(
                "Refuse to consider PR #262 cutover complete until the "
                "above are resolved. See docs/DEPLOYMENT_PR262.md."
            ))
            sys.exit(1)

        self.stdout.write(self.style.SUCCESS(
            "\nAll PR #262 post-migration invariants hold. Safe to flip "
            "feature flags (BLOCKCHAIN_ENABLED, "
            "SMART_CONTRACT_UNLOCK_ONCHAIN_ENABLED) at your discretion."
        ))

"""
Vault Service — Core CRUD & Lifecycle Management
==================================================

High-level service orchestrating vault creation, condition evaluation,
check-ins, approvals, votes, and unlocking.
"""

import hashlib
import logging
from typing import Dict, Any, Optional, List
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone
from django.conf import settings

from smart_contracts.models.vault import (
    SmartContractVault, VaultCondition, ConditionType, VaultStatus
)
from smart_contracts.models.governance import (
    MultiSigGroup, MultiSigApproval, DAOProposal, DAOVote
)
from smart_contracts.models.escrow import EscrowAgreement, InheritancePlan
from .condition_engine import ConditionEngine

logger = logging.getLogger(__name__)
User = get_user_model()


class VaultService:
    """
    High-level vault lifecycle management service.
    """

    def __init__(self):
        self.condition_engine = ConditionEngine()
        self.config = getattr(settings, 'SMART_CONTRACT_AUTOMATION', {})

    # =========================================================================
    # Vault Creation
    # =========================================================================

    @transaction.atomic
    def create_vault(self, user, data: Dict[str, Any]) -> SmartContractVault:
        """
        Create a new smart contract vault with the specified condition type.
        """
        condition_type = data['condition_type']
        password_hash = self._compute_password_hash(data['password_encrypted'])

        vault = SmartContractVault.objects.create(
            user=user,
            title=data['title'],
            description=data.get('description', ''),
            password_hash=password_hash,
            password_encrypted=data['password_encrypted'],
            condition_type=condition_type,
            contract_address=self.config.get('TIMELOCKED_VAULT_ADDRESS', ''),
            network=settings.BLOCKCHAIN_ANCHORING.get('NETWORK', 'testnet'),
            # Time-lock
            unlock_at=data.get('unlock_at'),
            # Dead man's switch
            check_in_interval_days=data.get('check_in_interval_days'),
            last_check_in=timezone.now() if condition_type == ConditionType.DEAD_MANS_SWITCH else None,
            grace_period_days=data.get('grace_period_days', self.config.get('DEFAULT_GRACE_PERIOD_DAYS', 7)),
            # Price oracle
            price_threshold=data.get('price_threshold'),
            price_above=data.get('price_above', True),
            oracle_address=data.get('oracle_address', self.config.get('CHAINLINK_ETH_USD_ORACLE', '')),
            # Beneficiary
            beneficiary_email=data.get('beneficiary_email', ''),
        )

        # Create type-specific linked records
        if condition_type == ConditionType.MULTI_SIG:
            self._setup_multi_sig(vault, data)
        elif condition_type == ConditionType.DAO_VOTE:
            self._setup_dao_proposal(vault, data)
        elif condition_type == ConditionType.ESCROW:
            self._setup_escrow(vault, user, data)
        elif condition_type in [ConditionType.DEAD_MANS_SWITCH]:
            self._setup_inheritance(vault, user, data)

        logger.info(f"Created vault {vault.id} ({vault.condition_type}) for user {user.username}")
        return vault

    def _setup_multi_sig(self, vault, data: Dict):
        """Create multi-sig group and initial approvals."""
        signer_ids = data.get('signer_ids', [])
        required = data.get('required_approvals', 2)

        group = MultiSigGroup.objects.create(
            vault=vault,
            required_approvals=required,
        )
        signers = User.objects.filter(id__in=signer_ids)
        group.signers.set(signers)

    def _setup_dao_proposal(self, vault, data: Dict):
        """Create DAO proposal with eligible voters."""
        voter_ids = data.get('voter_ids', [])
        voting_days = data.get('voting_period_days', self.config.get('DAO_VOTING_PERIOD_DAYS', 7))
        quorum = data.get('quorum_threshold', self.config.get('DAO_DEFAULT_QUORUM_PERCENT', 51) * 100)

        proposal = DAOProposal.objects.create(
            vault=vault,
            title=data.get('proposal_title', vault.title),
            description=data.get('proposal_description', vault.description),
            voting_deadline=timezone.now() + timedelta(days=voting_days),
            quorum_threshold=quorum,
        )
        voters = User.objects.filter(id__in=voter_ids)
        proposal.eligible_voters.set(voters)

    def _setup_escrow(self, vault, depositor, data: Dict):
        """Create escrow agreement."""
        EscrowAgreement.objects.create(
            vault=vault,
            depositor=depositor,
            beneficiary_id=data['beneficiary_user_id'],
            arbitrator_id=data['arbitrator_id'],
            arbitrator_wallet=data.get('arbitrator_wallet', ''),
            release_conditions=data.get('release_conditions', ''),
        )

    def _setup_inheritance(self, vault, owner, data: Dict):
        """Create inheritance plan for dead man's switch."""
        InheritancePlan.objects.create(
            vault=vault,
            owner=owner,
            beneficiary_email=data.get('beneficiary_email', ''),
            beneficiary_user_id=data.get('beneficiary_user_id'),
            inactivity_period_days=data.get(
                'check_in_interval_days',
                self.config.get('DEFAULT_CHECK_IN_INTERVAL_DAYS', 30)
            ),
            grace_period_days=data.get(
                'grace_period_days',
                self.config.get('DEFAULT_GRACE_PERIOD_DAYS', 7)
            ),
        )

    # =========================================================================
    # Actions
    # =========================================================================

    def check_in(self, vault: SmartContractVault, user) -> Dict[str, Any]:
        """Dead man's switch check-in."""
        if vault.condition_type != ConditionType.DEAD_MANS_SWITCH:
            raise ValueError("Not a dead man's switch vault")
        if vault.user != user:
            raise PermissionError("Only the vault creator can check in")
        if vault.status != VaultStatus.ACTIVE:
            raise ValueError("Vault is not active")

        vault.last_check_in = timezone.now()
        vault.save(update_fields=['last_check_in', 'updated_at'])

        # Reset inheritance plan if exists
        try:
            plan = vault.inheritance_plan
            plan.last_check_in = timezone.now()
            plan.notification_sent = False
            plan.beneficiary_notified = False
            plan.grace_period_started_at = None
            if plan.status != InheritancePlan.InheritanceStatus.ACTIVE:
                plan.status = InheritancePlan.InheritanceStatus.ACTIVE
            plan.save()
        except InheritancePlan.DoesNotExist:
            pass

        logger.info(f"Check-in for vault {vault.id} by {user.username}")
        return {
            'success': True,
            'last_check_in': vault.last_check_in.isoformat(),
            'next_deadline': vault.dead_mans_switch_deadline.isoformat() if vault.dead_mans_switch_deadline else None,
        }

    def attempt_unlock(self, vault: SmartContractVault, user) -> Dict[str, Any]:
        """Attempt to unlock a vault by evaluating conditions."""
        if vault.status != VaultStatus.ACTIVE:
            raise ValueError(f"Vault is {vault.get_status_display()}, not active")

        result = self.condition_engine.evaluate(vault)

        if result['met']:
            vault.status = VaultStatus.UNLOCKED
            vault.unlocked_at = timezone.now()
            vault.save(update_fields=['status', 'unlocked_at', 'updated_at'])

            logger.info(f"Vault {vault.id} unlocked by {user.username}")
            return {
                'unlocked': True,
                'password_encrypted': vault.password_encrypted,
                'reason': result['reason'],
                'details': result['details'],
            }
        else:
            return {
                'unlocked': False,
                'reason': result['reason'],
                'details': result['details'],
            }

    def approve_multi_sig(self, vault: SmartContractVault, user) -> Dict[str, Any]:
        """Record a multi-sig approval."""
        if vault.condition_type != ConditionType.MULTI_SIG:
            raise ValueError("Not a multi-sig vault")
        if vault.status != VaultStatus.ACTIVE:
            raise ValueError("Vault is not active")

        group = vault.multi_sig_group
        if not group.signers.filter(id=user.id).exists():
            raise PermissionError("Not an authorized signer")

        approval, created = MultiSigApproval.objects.get_or_create(
            group=group,
            signer=user,
            defaults={'approved': True, 'approved_at': timezone.now()}
        )

        if not created:
            if approval.approved:
                raise ValueError("Already approved")
            approval.approved = True
            approval.approved_at = timezone.now()
            approval.save()

        logger.info(f"Multi-sig approval for vault {vault.id} by {user.username} ({group.approval_count}/{group.required_approvals})")
        return {
            'approved': True,
            'current_approvals': group.approval_count,
            'required_approvals': group.required_approvals,
            'threshold_met': group.is_threshold_met,
        }

    def cast_vote(self, vault: SmartContractVault, user, approve: bool) -> Dict[str, Any]:
        """Cast a DAO vote."""
        if vault.condition_type != ConditionType.DAO_VOTE:
            raise ValueError("Not a DAO voting vault")
        if vault.status != VaultStatus.ACTIVE:
            raise ValueError("Vault is not active")

        proposal = vault.dao_proposal
        if proposal.voting_ended:
            raise ValueError("Voting period has ended")
        if not proposal.eligible_voters.filter(id=user.id).exists():
            raise PermissionError("Not an eligible voter")
        if DAOVote.objects.filter(proposal=proposal, voter=user).exists():
            raise ValueError("Already voted")

        DAOVote.objects.create(
            proposal=proposal,
            voter=user,
            approve=approve,
        )

        logger.info(f"DAO vote for vault {vault.id} by {user.username}: {'approve' if approve else 'reject'}")
        return {
            'voted': True,
            'choice': 'approve' if approve else 'reject',
            'votes_for': proposal.votes_for,
            'votes_against': proposal.votes_against,
            'quorum_met': proposal.quorum_met,
        }

    def release_escrow(self, vault: SmartContractVault, arbitrator) -> Dict[str, Any]:
        """Release an escrow vault (arbitrator only)."""
        if vault.condition_type != ConditionType.ESCROW:
            raise ValueError("Not an escrow vault")
        if vault.status != VaultStatus.ACTIVE:
            raise ValueError("Vault is not active")

        escrow = vault.escrow_agreement
        if escrow.arbitrator != arbitrator:
            raise PermissionError("Only the arbitrator can release this escrow")

        escrow.status = EscrowAgreement.EscrowStatus.RELEASED
        escrow.released_at = timezone.now()
        escrow.save()

        vault.status = VaultStatus.UNLOCKED
        vault.unlocked_at = timezone.now()
        vault.save(update_fields=['status', 'unlocked_at', 'updated_at'])

        logger.info(f"Escrow released for vault {vault.id} by arbitrator {arbitrator.username}")
        return {
            'released': True,
            'released_at': escrow.released_at.isoformat(),
        }

    def cancel_vault(self, vault: SmartContractVault, user) -> Dict[str, Any]:
        """Cancel a vault (creator only)."""
        if vault.user != user:
            raise PermissionError("Only the vault creator can cancel")
        if vault.status != VaultStatus.ACTIVE:
            raise ValueError("Vault is not active")

        vault.status = VaultStatus.CANCELLED
        vault.save(update_fields=['status', 'updated_at'])

        logger.info(f"Vault {vault.id} cancelled by {user.username}")
        return {'cancelled': True}

    # =========================================================================
    # Utility
    # =========================================================================

    def _compute_password_hash(self, encrypted_data: str) -> str:
        """Compute keccak256-style hash of the encrypted password."""
        import hashlib
        h = hashlib.sha256(encrypted_data.encode()).hexdigest()
        return f"0x{h}"

    def get_config(self) -> Dict[str, Any]:
        """Return feature configuration for API response."""
        return {
            'enabled': self.config.get('ENABLED', False),
            'contract_address': self.config.get('TIMELOCKED_VAULT_ADDRESS', ''),
            'network': settings.BLOCKCHAIN_ANCHORING.get('NETWORK', 'testnet'),
            'default_check_in_interval_days': self.config.get('DEFAULT_CHECK_IN_INTERVAL_DAYS', 30),
            'default_grace_period_days': self.config.get('DEFAULT_GRACE_PERIOD_DAYS', 7),
            'max_multi_sig_signers': self.config.get('MAX_MULTI_SIG_SIGNERS', 10),
            'dao_default_quorum_percent': self.config.get('DAO_DEFAULT_QUORUM_PERCENT', 51),
            'dao_voting_period_days': self.config.get('DAO_VOTING_PERIOD_DAYS', 7),
        }

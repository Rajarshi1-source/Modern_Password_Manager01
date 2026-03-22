"""
Condition Engine
=================

Evaluates vault conditions server-side (with optional on-chain verification).
Supports all condition types: time-lock, dead man's switch, multi-sig,
DAO voting, price oracle, and escrow.
"""

import logging
from datetime import datetime
from typing import Dict, Any, Optional
from django.utils import timezone
from django.conf import settings

logger = logging.getLogger(__name__)


class ConditionEngine:
    """
    Pure-Python condition evaluator that checks all vault conditions locally.
    Can optionally verify results on-chain for authoritative confirmation.
    """

    def evaluate(self, vault, verify_onchain: bool = False) -> Dict[str, Any]:
        """
        Evaluate a vault's unlock conditions.

        Args:
            vault: SmartContractVault instance
            verify_onchain: If True, also verify on-chain (more authoritative)

        Returns:
            {
                'met': bool,
                'reason': str,
                'details': {...},
                'onchain_verified': bool | None,
            }
        """
        from smart_contracts.models.vault import ConditionType

        evaluators = {
            ConditionType.TIME_LOCK: self._evaluate_time_lock,
            ConditionType.DEAD_MANS_SWITCH: self._evaluate_dead_mans_switch,
            ConditionType.MULTI_SIG: self._evaluate_multi_sig,
            ConditionType.DAO_VOTE: self._evaluate_dao_vote,
            ConditionType.PRICE_ORACLE: self._evaluate_price_oracle,
            ConditionType.ESCROW: self._evaluate_escrow,
        }

        evaluator = evaluators.get(vault.condition_type)
        if not evaluator:
            return {
                'met': False,
                'reason': f'Unknown condition type: {vault.condition_type}',
                'details': {},
                'onchain_verified': None,
            }

        result = evaluator(vault)

        # Optional on-chain verification
        if verify_onchain and vault.vault_id_onchain:
            from .web3_bridge import SmartContractWeb3Bridge
            bridge = SmartContractWeb3Bridge()
            onchain_result = bridge.check_condition_onchain(vault.vault_id_onchain)
            result['onchain_verified'] = onchain_result
        else:
            result['onchain_verified'] = None

        return result

    def _evaluate_time_lock(self, vault) -> Dict[str, Any]:
        """Evaluate time-lock condition."""
        now = timezone.now()
        if not vault.unlock_at:
            return {
                'met': False,
                'reason': 'No unlock time configured',
                'details': {},
            }

        is_met = now >= vault.unlock_at
        remaining = max(0, (vault.unlock_at - now).total_seconds())

        return {
            'met': is_met,
            'reason': 'Time lock expired' if is_met else f'{int(remaining)} seconds remaining',
            'details': {
                'unlock_at': vault.unlock_at.isoformat(),
                'time_remaining_seconds': int(remaining),
            },
        }

    def _evaluate_dead_mans_switch(self, vault) -> Dict[str, Any]:
        """Evaluate dead man's switch condition."""
        now = timezone.now()

        if not vault.last_check_in or not vault.check_in_interval_days:
            return {
                'met': False,
                'reason': 'Dead man\'s switch not configured',
                'details': {},
            }

        deadline = vault.dead_mans_switch_deadline
        if not deadline:
            return {'met': False, 'reason': 'Cannot compute deadline', 'details': {}}

        is_triggered = now > deadline
        remaining = max(0, (deadline - now).total_seconds())

        return {
            'met': is_triggered,
            'reason': 'Dead man\'s switch triggered' if is_triggered else f'{int(remaining)}s until trigger',
            'details': {
                'last_check_in': vault.last_check_in.isoformat(),
                'check_in_interval_days': vault.check_in_interval_days,
                'grace_period_days': vault.grace_period_days,
                'deadline': deadline.isoformat(),
                'time_remaining_seconds': int(remaining),
                'is_triggered': is_triggered,
            },
        }

    def _evaluate_multi_sig(self, vault) -> Dict[str, Any]:
        """Evaluate multi-sig condition."""
        try:
            group = vault.multi_sig_group
        except Exception:
            return {'met': False, 'reason': 'Multi-sig group not configured', 'details': {}}

        is_met = group.is_threshold_met

        return {
            'met': is_met,
            'reason': (
                f'Threshold met ({group.approval_count}/{group.required_approvals})'
                if is_met else
                f'{group.approval_count}/{group.required_approvals} approvals'
            ),
            'details': {
                'required_approvals': group.required_approvals,
                'current_approvals': group.approval_count,
                'total_signers': group.total_signers,
            },
        }

    def _evaluate_dao_vote(self, vault) -> Dict[str, Any]:
        """Evaluate DAO voting condition."""
        try:
            proposal = vault.dao_proposal
        except Exception:
            return {'met': False, 'reason': 'DAO proposal not configured', 'details': {}}

        is_met = proposal.quorum_met

        return {
            'met': is_met,
            'reason': (
                'DAO vote approved' if is_met else
                'Voting in progress' if not proposal.voting_ended else
                'Quorum not met'
            ),
            'details': {
                'votes_for': proposal.votes_for,
                'votes_against': proposal.votes_against,
                'total_eligible': proposal.total_eligible,
                'quorum_threshold_bps': proposal.quorum_threshold,
                'voting_ended': proposal.voting_ended,
                'voting_deadline': proposal.voting_deadline.isoformat(),
            },
        }

    def _evaluate_price_oracle(self, vault) -> Dict[str, Any]:
        """Evaluate price oracle condition."""
        from .oracle_service import OracleService
        oracle = OracleService()

        current_price = oracle.get_eth_usd_price()
        if current_price is None:
            return {
                'met': False,
                'reason': 'Oracle price unavailable',
                'details': {'oracle_address': vault.oracle_address},
            }

        threshold = float(vault.price_threshold) if vault.price_threshold else 0
        if vault.price_above:
            is_met = current_price > threshold
        else:
            is_met = current_price < threshold

        return {
            'met': is_met,
            'reason': (
                f'Price condition met (${current_price:,.2f} {">" if vault.price_above else "<"} ${threshold:,.2f})'
                if is_met else
                f'Price ${current_price:,.2f}, need {">" if vault.price_above else "<"} ${threshold:,.2f}'
            ),
            'details': {
                'current_price': current_price,
                'threshold': threshold,
                'direction': 'above' if vault.price_above else 'below',
            },
        }

    def _evaluate_escrow(self, vault) -> Dict[str, Any]:
        """Evaluate escrow condition (arbitrator-dependent)."""
        try:
            escrow = vault.escrow_agreement
        except Exception:
            return {'met': False, 'reason': 'Escrow agreement not configured', 'details': {}}

        from smart_contracts.models.escrow import EscrowAgreement
        is_released = escrow.status == EscrowAgreement.EscrowStatus.RELEASED

        return {
            'met': is_released,
            'reason': 'Escrow released by arbitrator' if is_released else 'Awaiting arbitrator release',
            'details': {
                'arbitrator': escrow.arbitrator.username,
                'status': escrow.get_status_display(),
                'released_at': escrow.released_at.isoformat() if escrow.released_at else None,
            },
        }

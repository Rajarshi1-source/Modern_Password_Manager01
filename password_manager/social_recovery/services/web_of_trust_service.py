"""Quorum evaluation for a :class:`SocialRecoveryRequest`."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from ..models import SocialRecoveryRequest, VouchAttestation


@dataclass
class QuorumResult:
    approve_count: int
    deny_count: int
    total_weight: int
    total_stake: int
    satisfies_count: bool
    satisfies_weight: bool
    satisfies_stake: bool
    satisfies_reputation: bool

    @property
    def quorum_met(self) -> bool:
        return (
            self.satisfies_count
            and self.satisfies_weight
            and self.satisfies_stake
            and self.satisfies_reputation
        )


def _voucher_reputation(user) -> int:
    if user is None:
        return 0
    try:
        from password_reputation.models import ReputationAccount

        account = ReputationAccount.objects.filter(user=user).first()
        return int(getattr(account, "score", 0) or 0)
    except Exception:  # pragma: no cover - reputation schema optional
        return 0


def evaluate_quorum(request: SocialRecoveryRequest) -> QuorumResult:
    """Evaluate whether the current approvals satisfy the circle rules."""
    circle = request.circle
    attestations: Iterable[VouchAttestation] = request.attestations.all()

    approve_count = 0
    deny_count = 0
    total_weight = 0
    total_stake = 0
    reputations_ok = True

    for att in attestations:
        if att.decision == "approve":
            approve_count += 1
            total_weight += int(att.voucher.vouch_weight or 0)
            total_stake += int(att.stake_committed or 0)
            if circle.min_voucher_reputation:
                if _voucher_reputation(att.voucher.user) < circle.min_voucher_reputation:
                    reputations_ok = False
        elif att.decision == "deny":
            deny_count += 1

    satisfies_count = approve_count >= circle.threshold
    # For weight we require at least one "weight unit" per threshold share, so
    # that low-weight vouchers can't trivially satisfy a high-threshold
    # circle.
    satisfies_weight = total_weight >= circle.threshold
    satisfies_stake = total_stake >= int(circle.min_total_stake or 0)

    return QuorumResult(
        approve_count=approve_count,
        deny_count=deny_count,
        total_weight=total_weight,
        total_stake=total_stake,
        satisfies_count=satisfies_count,
        satisfies_weight=satisfies_weight,
        satisfies_stake=satisfies_stake,
        satisfies_reputation=reputations_ok,
    )

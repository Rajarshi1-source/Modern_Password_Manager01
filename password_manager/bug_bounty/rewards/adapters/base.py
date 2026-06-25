"""
Payout adapter interface for bounty rewards.

A reward is a recorded *obligation* (see ``models.Reward``). Turning that
obligation into an actual disbursement is intentionally **not** built into this
product: integrating a real payment processor pulls in KYC, fraud, PCI and tax
liability that a zero-knowledge password manager has no business owning.

Instead, ``pay_reward`` (in ``services.triage_service``) resolves a
``BasePayoutAdapter`` by name and calls :meth:`~BasePayoutAdapter.pay`. The only
adapter shipped is :class:`ManualPayoutAdapter`, which moves no money — it just
records that the reward was settled off-platform. Real rails (Phase 3) plug in
here by registering another adapter; nothing else changes.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PayoutResult:
    """Outcome of an adapter's :meth:`BasePayoutAdapter.pay` call."""

    reference: str          # external/off-platform reference for the settlement
    detail: str = ''        # human-readable note for audit/UI


class BasePayoutAdapter:
    """Interface a payout backend must implement. No money moves in the base."""

    name: str = 'base'

    def pay(self, reward) -> PayoutResult:
        """Disburse ``reward`` and return a :class:`PayoutResult`.

        Implementations must be idempotent-friendly: ``pay_reward`` only calls
        this for a reward in the ``owed`` state and persists the result.
        """
        raise NotImplementedError


class ManualPayoutAdapter(BasePayoutAdapter):
    """Default adapter — records a manual/off-platform settlement.

    This moves **no** money. It exists so the reward ledger can be marked
    ``paid`` after an owner pays a researcher through some external channel
    (bank transfer, gift card, etc.), keeping the product out of the payment
    business entirely.
    """

    name = 'manual'

    def pay(self, reward) -> PayoutResult:
        return PayoutResult(
            reference=f'manual:{reward.id}',
            detail='Recorded as settled off-platform; no payment processed in-product.',
        )

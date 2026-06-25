"""Reward disbursement layer for the bounty program.

Rewards are recorded obligations; *paying* one is delegated to a pluggable
payout adapter. No payment processor is bundled — see ``adapters`` for the
interface and the no-money default (``ManualPayoutAdapter``).
"""

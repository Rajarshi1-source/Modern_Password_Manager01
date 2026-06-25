"""
Triage state machine + reward ledger for the bounty program (Phase 2).

This module owns every *transition* of a ``Submission`` and the lifecycle of its
``Reward``. The valid moves are:

    new → triaging → accepted | duplicate | rejected
    accepted → resolved → rewarded

``duplicate``, ``rejected`` and ``rewarded`` are terminal. Reaching ``rewarded``
is special: it must create a ``Reward`` obligation, so it goes through
:func:`issue_reward` rather than the generic :func:`apply_transition`.

Authorization (only the program owner may triage) is enforced by the API layer.
These functions assume the caller has already checked it and focus purely on
keeping the state machine and the reward ledger consistent.
"""

from __future__ import annotations

from django.db import IntegrityError, transaction
from django.utils import timezone

from ..models import Reward, RewardStatus, Submission, SubmissionStatus
from ..rewards.adapters import get_payout_adapter

# Allowed submission transitions. REWARDED is intentionally absent from the
# generic map — it is only reachable via issue_reward(), which also creates the
# Reward row. RESOLVED therefore lists no generic successor here.
ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    SubmissionStatus.NEW: {SubmissionStatus.TRIAGING},
    SubmissionStatus.TRIAGING: {
        SubmissionStatus.ACCEPTED,
        SubmissionStatus.DUPLICATE,
        SubmissionStatus.REJECTED,
    },
    SubmissionStatus.ACCEPTED: {SubmissionStatus.RESOLVED},
    SubmissionStatus.RESOLVED: set(),
    SubmissionStatus.DUPLICATE: set(),
    SubmissionStatus.REJECTED: set(),
    SubmissionStatus.REWARDED: set(),
}


class InvalidTransition(Exception):
    """Raised when a requested submission/reward transition is not permitted."""


def apply_transition(submission, to_status, *, severity_assigned='', note='') -> Submission:
    """Validate and apply a generic state-machine transition.

    Does not handle the move to ``rewarded`` (use :func:`issue_reward`). Returns
    the updated submission; raises :class:`InvalidTransition` for an illegal move.
    """
    if to_status == SubmissionStatus.REWARDED:
        raise InvalidTransition(
            'Rewarding a submission must go through the reward action so a '
            'reward record is created.'
        )
    allowed = ALLOWED_TRANSITIONS.get(submission.status, set())
    if to_status not in allowed:
        raise InvalidTransition(
            f'Cannot move a submission from "{submission.status}" to "{to_status}".'
        )

    update_fields = ['status', 'updated_at']
    submission.status = to_status
    if severity_assigned:
        submission.severity_assigned = severity_assigned
        update_fields.append('severity_assigned')
    if note:
        submission.triage_note = note
        update_fields.append('triage_note')
    submission.save(update_fields=update_fields)
    return submission


def issue_reward(submission, *, amount, currency='USD', adapter='manual', note='') -> Reward:
    """Record a reward obligation and move the submission to ``rewarded``.

    No money moves here: the ``Reward`` is created in the ``owed`` state.
    Disbursement is a separate, adapter-mediated step (:func:`pay_reward`).
    A submission must be ``resolved`` first, and can only be rewarded once
    (enforced by the one-to-one ``Reward`` relation).
    """
    if submission.status != SubmissionStatus.RESOLVED:
        raise InvalidTransition(
            f'A submission must be resolved before it can be rewarded '
            f'(currently "{submission.status}").'
        )
    if hasattr(submission, 'reward'):
        raise InvalidTransition('This submission has already been rewarded.')

    try:
        with transaction.atomic():
            reward = Reward.objects.create(
                submission=submission,
                amount=amount,
                currency=currency,
                adapter=adapter,
            )
            submission.status = SubmissionStatus.REWARDED
            update_fields = ['status', 'updated_at']
            if note:
                submission.triage_note = note
                update_fields.append('triage_note')
            submission.save(update_fields=update_fields)
    except IntegrityError as exc:
        # A concurrent issue_reward for the same submission lost the race on the
        # one-to-one constraint — surface the contract error (→ 400), not a 500.
        raise InvalidTransition('This submission has already been rewarded.') from exc
    return reward


def pay_reward(reward) -> Reward:
    """Settle an ``owed`` reward through its payout adapter.

    The bundled ``manual`` adapter moves no money — it only records an
    off-platform reference. Raises :class:`InvalidTransition` unless the reward
    is currently ``owed``.
    """
    if reward.status != RewardStatus.OWED:
        raise InvalidTransition(
            f'Only an owed reward can be paid (currently "{reward.status}").'
        )
    adapter = get_payout_adapter(reward.adapter)
    result = adapter.pay(reward)
    reward.status = RewardStatus.PAID
    reward.payout_ref = result.reference
    reward.paid_at = timezone.now()
    reward.save(update_fields=['status', 'payout_ref', 'paid_at', 'updated_at'])
    return reward


def void_reward(reward) -> Reward:
    """Void an obligation that will not be paid. A ``paid`` reward cannot be voided."""
    if reward.status == RewardStatus.PAID:
        raise InvalidTransition('A paid reward cannot be voided.')
    reward.status = RewardStatus.VOID
    reward.save(update_fields=['status', 'updated_at'])
    return reward

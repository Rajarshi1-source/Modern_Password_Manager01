"""Stake accounting on top of ``password_reputation``.

This app does not run an on-chain escrow. Stake is represented as a
``ReputationEvent`` delta with ``event_type = EVENT_BONUS`` when committed
and reversed through ``slash()`` or a positive bonus on release. All
reputation mutation still flows through ``password_reputation.services`` so
the existing Merkle anchor + cap logic keeps working.
"""
from __future__ import annotations

from typing import Optional

from django.db import transaction

from password_reputation.models import ReputationAccount, ReputationEvent


SCHEME_ID = "social-vouch-v1"


def _ensure_account(user) -> ReputationAccount:
    account, _ = ReputationAccount.objects.get_or_create(user=user)
    return account


@transaction.atomic
def commit_stake(*, user, amount: int, request_id: str) -> ReputationEvent:
    """Record a stake commitment as a ``score_delta`` of 0 + note.

    We intentionally do NOT deduct from the ``score`` column because the
    reputation model treats score monotonically-plus-slash. Commitments are
    tracked as audit rows referenced by ``request_id`` in the ``note`` field
    and are later matched by ``release_stake`` or ``slash_stake``.
    """
    if amount < 0:
        raise ValueError("stake amount must be non-negative")
    account = _ensure_account(user)
    event = ReputationEvent.objects.create(
        user=user,
        event_type=ReputationEvent.EVENT_BONUS,
        score_delta=0,
        tokens_delta=0,
        note=f"{SCHEME_ID}|commit|{request_id}|{amount}"[:256],
        leaf_hash=b"\x00" * 32,
        anchor_status=ReputationEvent.ANCHOR_STATUS_PENDING,
    )
    # Touch the account to keep updated_at fresh.
    account.save(update_fields=["updated_at"])
    return event


@transaction.atomic
def release_stake(*, user, amount: int, request_id: str) -> ReputationEvent:
    """Mark a previously committed stake as released without penalty."""
    event = ReputationEvent.objects.create(
        user=user,
        event_type=ReputationEvent.EVENT_BONUS,
        score_delta=0,
        tokens_delta=0,
        note=f"{SCHEME_ID}|release|{request_id}|{amount}"[:256],
        leaf_hash=b"\x00" * 32,
        anchor_status=ReputationEvent.ANCHOR_STATUS_PENDING,
    )
    return event


@transaction.atomic
def slash_stake(
    *, user, amount: int, request_id: str, reason: str = "fraudulent_vouch"
) -> ReputationEvent:
    """Slash a voucher's reputation for a fraudulent attestation.

    Let errors from ``password_reputation.services.slash`` propagate. The
    previous implementation swallowed them and wrote a bogus ``EVENT_SLASH``
    row with ``leaf_hash = 0`` and ``anchor_status = PENDING``. That row
    never made it into the Merkle anchor, so a caller would see a
    return value indicating success while the voucher's reputation was
    not actually penalised — silently turning a failing slash into a
    no-op. Failing loudly forces the caller (a transaction in
    ``recovery_completion_service`` or an admin action) to retry or
    escalate instead of continuing on a false-positive result.
    """
    # Delegate the actual score hit to password_reputation.services.slash so
    # the existing merkle/anchor flushing is invoked.
    from password_reputation.services import slash

    return slash(
        user=user,
        score_penalty=max(1, int(amount)),
        reason=f"{SCHEME_ID}|{reason}|{request_id}",
    )


def get_current_score(user) -> int:
    account = _ensure_account(user)
    return int(account.score or 0)


def aggregate_committed_stake(request_id: str) -> int:
    """Sum of ``commit_stake`` amounts for a given request id."""
    total = 0
    prefix = f"{SCHEME_ID}|commit|{request_id}|"
    for note in ReputationEvent.objects.filter(
        note__startswith=prefix
    ).values_list("note", flat=True):
        try:
            total += int(note.rsplit("|", 1)[-1])
        except ValueError:  # pragma: no cover - defensive
            continue
    return total

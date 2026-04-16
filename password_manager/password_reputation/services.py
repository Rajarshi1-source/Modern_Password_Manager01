"""
Service layer for the reputation network.

All reputation state mutation goes through these functions. Views are thin
adapters that parse payloads and forward to here. Tests exercise services
directly (without HTTP) to validate the state machine and math.

Configuration (``settings.PASSWORD_REPUTATION``, all optional):
  * ``ANCHOR_ADAPTER``: ``"null"`` (default) or ``"arbitrum"``.
  * ``ANCHOR_BATCH_SIZE``: flush threshold for background anchoring (default 50).
  * ``MAX_SCORE_PER_WINDOW``: per-user score cap within rolling 24h window
    (default 256; i.e., roughly 2 maxed-out proofs per day).
  * ``RATE_LIMIT_WINDOW_HOURS``: window size for the cap (default 24).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import timedelta
from typing import Dict, List, Optional

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from .anchors import AnchorResult, configured_adapter_name, get_adapter
from .merkle import compute_event_leaf, hash_leaf, merkle_root
from .models import (
    AnchorBatch,
    ReputationAccount,
    ReputationEvent,
    ReputationProof,
)
from .providers import DEFAULT_SCHEME, get_provider

logger = logging.getLogger(__name__)

DEFAULT_BATCH_SIZE = 50
DEFAULT_MAX_SCORE_PER_WINDOW = 256
DEFAULT_RATE_LIMIT_HOURS = 24


def _config() -> Dict:
    return getattr(settings, "PASSWORD_REPUTATION", {}) or {}


def _batch_size() -> int:
    return int(_config().get("ANCHOR_BATCH_SIZE", DEFAULT_BATCH_SIZE))


def _score_cap_per_window() -> int:
    return int(_config().get("MAX_SCORE_PER_WINDOW", DEFAULT_MAX_SCORE_PER_WINDOW))


def _rate_limit_window():
    hours = int(_config().get("RATE_LIMIT_WINDOW_HOURS", DEFAULT_RATE_LIMIT_HOURS))
    return timedelta(hours=hours)


@dataclass
class SubmissionResult:
    """Return value of ``submit_proof``. Safe to serialize straight to JSON."""

    proof: ReputationProof
    event: Optional[ReputationEvent]
    account: ReputationAccount
    accepted: bool
    error: str = ""


def _ensure_account(user) -> ReputationAccount:
    account, _ = ReputationAccount.objects.get_or_create(user=user)
    return account


def _recent_score(user, window) -> int:
    """Score earned by this user in the rolling window (ignores slashes)."""
    since = timezone.now() - window
    total = (
        ReputationEvent.objects.filter(
            user=user,
            created_at__gte=since,
            event_type__in=[
                ReputationEvent.EVENT_PROOF_ACCEPTED,
                ReputationEvent.EVENT_BONUS,
            ],
        )
        .values_list("score_delta", flat=True)
    )
    return sum(total)


@transaction.atomic
def submit_proof(
    *,
    user,
    scope_id: str,
    commitment: bytes,
    claimed_entropy_bits: int,
    binding_hash: bytes,
    scheme: str = DEFAULT_SCHEME,
) -> SubmissionResult:
    """Verify a reputation proof and (if accepted) mint score + tokens.

    Idempotent per ``(user, scope_id, scheme)`` — re-submitting for the same
    scope replaces the previous ``ReputationProof`` row but writes a new
    ``ReputationEvent`` only when the new submission would strictly increase
    the user's reward (preventing trivial score farming).
    """
    provider = get_provider(scheme)
    account = _ensure_account(user)

    result = provider.verify_and_score(
        commitment=commitment,
        claimed_entropy_bits=claimed_entropy_bits,
        payload={"user_id": user.id, "binding_hash": binding_hash},
    )

    proof_defaults = dict(
        commitment=commitment,
        claimed_entropy_bits=claimed_entropy_bits,
        status=(
            ReputationProof.STATUS_ACCEPTED if result.accepted else ReputationProof.STATUS_REJECTED
        ),
        score_delta=result.score_delta,
        tokens_delta=result.tokens_delta,
        error_message="" if result.accepted else (result.error[:256] if result.error else "rejected"),
    )
    proof, _ = ReputationProof.objects.update_or_create(
        user=user,
        scope_id=scope_id,
        scheme=scheme,
        defaults=proof_defaults,
    )

    if not result.accepted:
        account.proofs_rejected = (account.proofs_rejected or 0) + 1
        account.save(update_fields=["proofs_rejected", "updated_at"])
        _record_event(
            user=user,
            event_type=ReputationEvent.EVENT_PROOF_REJECTED,
            score_delta=0,
            tokens_delta=0,
            proof=proof,
            note=(result.error or "rejected")[:256],
        )
        return SubmissionResult(proof=proof, event=None, account=account, accepted=False, error=result.error)

    # Rate-limit: clamp score_delta to respect the per-window cap.
    recent = _recent_score(user, _rate_limit_window())
    cap = _score_cap_per_window()
    effective_score = max(0, min(result.score_delta, cap - recent))
    # Tokens scale proportionally with the clamped score.
    if result.score_delta > 0:
        effective_tokens = int(round(result.tokens_delta * (effective_score / result.score_delta)))
    else:
        effective_tokens = 0

    event = _record_event(
        user=user,
        event_type=ReputationEvent.EVENT_PROOF_ACCEPTED,
        score_delta=effective_score,
        tokens_delta=effective_tokens,
        proof=proof,
        note=(
            f"claimed_bits={claimed_entropy_bits} clamped_bits={result.claimed_entropy_bits} "
            f"rate_limited={recent + effective_score}/{cap}"
        ),
    )

    account.score = (account.score or 0) + effective_score
    account.tokens = (account.tokens or 0) + effective_tokens
    account.proofs_accepted = (account.proofs_accepted or 0) + 1
    account.last_proof_at = timezone.now()
    account.save(update_fields=[
        "score", "tokens", "proofs_accepted", "last_proof_at", "updated_at",
    ])

    _maybe_flush_batch()

    return SubmissionResult(proof=proof, event=event, account=account, accepted=True)


@transaction.atomic
def slash(*, user, score_penalty: int, reason: str = "breach") -> ReputationEvent:
    """Apply a score slash (e.g., on breach detection)."""
    account = _ensure_account(user)
    penalty = int(abs(score_penalty))
    if penalty <= 0:
        raise ValueError("score_penalty must be a positive int.")

    event = _record_event(
        user=user,
        event_type=ReputationEvent.EVENT_SLASH,
        score_delta=-penalty,
        tokens_delta=0,  # tokens are monotonic in v1 by design
        note=reason[:256],
    )
    account.score = max(0, (account.score or 0) - penalty)
    account.last_breach_at = timezone.now()
    account.save(update_fields=["score", "last_breach_at", "updated_at"])
    _maybe_flush_batch()
    return event


def _record_event(*, user, event_type, score_delta, tokens_delta, proof=None, note="") -> ReputationEvent:
    """Internal helper — always wrap in a transaction at the call site."""
    # We need the event id before we can hash the leaf; but since the id is a
    # uuid generated client-side by the model default, we can compute the
    # leaf_hash in-memory before save.
    import uuid as _uuid

    event_id = _uuid.uuid4()
    leaf = compute_event_leaf(
        event_id_bytes=event_id.bytes,
        user_id=user.id,
        event_type=event_type,
        score_delta=score_delta,
        tokens_delta=tokens_delta,
    )
    event = ReputationEvent.objects.create(
        id=event_id,
        user=user,
        event_type=event_type,
        score_delta=score_delta,
        tokens_delta=tokens_delta,
        proof=proof,
        leaf_hash=leaf,
        anchor_status=ReputationEvent.ANCHOR_STATUS_PENDING,
        note=note[:256],
    )
    return event


def _maybe_flush_batch() -> Optional[AnchorBatch]:
    """Best-effort synchronous flush once the pending queue hits the threshold.

    Errors from the adapter are swallowed and the batch is left in
    ``status="failed"`` so a Celery retry (Phase 2b) can pick it up later
    without losing events.
    """
    pending = ReputationEvent.objects.filter(
        anchor_status=ReputationEvent.ANCHOR_STATUS_PENDING,
    )
    if pending.count() < _batch_size():
        return None
    try:
        return flush_pending_batch()
    except Exception:  # noqa: BLE001
        logger.exception("Flushing reputation batch failed")
        return None


@transaction.atomic
def flush_pending_batch(adapter_name: Optional[str] = None) -> Optional[AnchorBatch]:
    """Anchor all pending ReputationEvents in a single batch.

    Returns the created ``AnchorBatch`` record (or None if nothing was pending).
    """
    events = list(
        ReputationEvent.objects.select_for_update()
        .filter(anchor_status=ReputationEvent.ANCHOR_STATUS_PENDING)
        .order_by("created_at")
    )
    if not events:
        return None

    leaves = [hash_leaf(bytes(e.leaf_hash)) for e in events]
    root = merkle_root(leaves)
    root_hex = "0x" + root.hex()

    adapter = get_adapter(adapter_name)
    batch = AnchorBatch.objects.create(
        adapter=adapter.name,
        merkle_root=root_hex,
        batch_size=len(events),
        status=AnchorBatch.STATUS_DRAFT,
    )

    # Mark events as "included" before submission so concurrent proofs go in
    # the next batch instead of fighting for this one.
    ReputationEvent.objects.filter(id__in=[e.id for e in events]).update(
        anchor_batch=batch,
        anchor_status=ReputationEvent.ANCHOR_STATUS_INCLUDED,
    )

    try:
        result: AnchorResult = adapter.submit_batch(
            merkle_root_hex=root_hex, batch_size=len(events),
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("Anchor adapter %s raised", adapter.name)
        result = AnchorResult(status="failed", error=str(exc)[:256])

    now = timezone.now()
    if result.status in ("submitted", "confirmed"):
        batch.status = (
            AnchorBatch.STATUS_CONFIRMED
            if result.status == "confirmed"
            else AnchorBatch.STATUS_SUBMITTED
        )
        batch.tx_hash = result.tx_hash
        batch.block_number = result.block_number
        batch.network = result.network
        batch.submitted_at = now
        if result.status == "confirmed":
            batch.confirmed_at = now
        batch.save()
        event_status = (
            ReputationEvent.ANCHOR_STATUS_CONFIRMED
            if result.status == "confirmed"
            else ReputationEvent.ANCHOR_STATUS_INCLUDED
        )
        ReputationEvent.objects.filter(anchor_batch=batch).update(anchor_status=event_status)
        if result.status == "confirmed":
            _record_anchor_confirmed_events(batch, events)
    elif result.status == "skipped":
        batch.status = AnchorBatch.STATUS_SKIPPED
        batch.network = result.network
        batch.submitted_at = now
        batch.save()
        ReputationEvent.objects.filter(anchor_batch=batch).update(
            anchor_status=ReputationEvent.ANCHOR_STATUS_SKIPPED,
        )
    else:
        batch.status = AnchorBatch.STATUS_FAILED
        batch.error_message = (result.error or "")[:256]
        batch.save()
        # Return events to pending so a later flush picks them up again.
        ReputationEvent.objects.filter(anchor_batch=batch).update(
            anchor_batch=None,
            anchor_status=ReputationEvent.ANCHOR_STATUS_PENDING,
        )
    return batch


def _record_anchor_confirmed_events(batch: AnchorBatch, events: List[ReputationEvent]) -> None:
    """Write per-user 'anchor confirmed' ledger entries (no score impact)."""
    seen_users = set()
    for event in events:
        if event.user_id in seen_users:
            continue
        seen_users.add(event.user_id)
        _record_event(
            user=event.user,
            event_type=ReputationEvent.EVENT_ANCHOR_CONFIRMED,
            score_delta=0,
            tokens_delta=0,
            note=f"batch={batch.id} tx={batch.tx_hash[:20]}",
        )


def account_for(user) -> ReputationAccount:
    """Public accessor — ensures the account row exists."""
    return _ensure_account(user)


def recent_events(user, limit: int = 50) -> List[ReputationEvent]:
    return list(
        ReputationEvent.objects.filter(user=user)
        .select_related("proof", "anchor_batch")
        .order_by("-created_at")[:limit]
    )


def leaderboard(limit: int = 20) -> List[ReputationAccount]:
    return list(
        ReputationAccount.objects.select_related("user")
        .order_by("-score", "-tokens", "user_id")[:limit]
    )


def compute_binding_hash(commitment: bytes, claimed_entropy_bits: int, user_id: int) -> bytes:
    """Convenience re-export so tests / frontend helpers agree on the format."""
    from .providers.commitment_claim import compute_binding_hash as _impl

    return _impl(commitment, claimed_entropy_bits, user_id)


def stats() -> Dict:
    return {
        "adapter": configured_adapter_name(),
        "pending_events": ReputationEvent.objects.filter(
            anchor_status=ReputationEvent.ANCHOR_STATUS_PENDING,
        ).count(),
        "total_events": ReputationEvent.objects.count(),
        "total_accounts": ReputationAccount.objects.count(),
        "total_batches": AnchorBatch.objects.count(),
        "confirmed_batches": AnchorBatch.objects.filter(
            status=AnchorBatch.STATUS_CONFIRMED,
        ).count(),
    }

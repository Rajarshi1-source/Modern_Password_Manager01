"""
Decentralized Password Reputation Network — data model.

Phase 2a ships the backend end-to-end with a no-op on-chain adapter
(``NullAnchor``) so the reputation mechanics can be exercised without ever
touching an RPC. Phase 2b swaps the configured adapter for an
``ArbitrumAnchor`` that delegates to the already-deployed
``CommitmentRegistry.anchorCommitment`` contract on the project's Arbitrum
Sepolia deployment.

Model overview:
  * ``ReputationAccount`` — one row per user; tracks current score, tokens,
    and aggregate lifecycle counters. Rebuilt from the event log if it ever
    drifts.
  * ``ReputationProof`` — a submitted proof that the user knows a secret
    whose entropy meets a claimed threshold. Pluggable via ``scheme``
    (today: ``commitment-claim-v1``; tomorrow: a real zk-SNARK).
  * ``ReputationEvent`` — append-only log of every reputation change
    (``earned``, ``bonus``, ``slashed``, ``anchor_confirmed``). The merkle
    leaf anchored on-chain is deterministic per event.
  * ``AnchorBatch`` — a batch of events rolled into a Merkle root and
    anchored via the configured ``AnchorAdapter``. Stores the adapter name,
    submitted root, tx hash (if any), and block number (if confirmed).
"""

from __future__ import annotations

import uuid

from django.conf import settings
from django.db import models


class ReputationAccount(models.Model):
    """Rolling per-user reputation summary."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        primary_key=True,
        related_name="reputation_account",
    )
    score = models.IntegerField(
        default=0,
        help_text="Current reputation score. Incremented on accepted proofs, slashed on breach.",
    )
    tokens = models.BigIntegerField(
        default=0,
        help_text="Total reputation tokens minted to this user (monotonically non-decreasing).",
    )
    proofs_accepted = models.PositiveIntegerField(default=0)
    proofs_rejected = models.PositiveIntegerField(default=0)
    last_proof_at = models.DateTimeField(null=True, blank=True)
    last_breach_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Reputation account"
        verbose_name_plural = "Reputation accounts"

    def __str__(self) -> str:  # pragma: no cover
        return f"ReputationAccount(user={self.user_id}, score={self.score}, tokens={self.tokens})"


class ReputationProof(models.Model):
    """A single proof submission."""

    SCHEME_COMMITMENT_CLAIM_V1 = "commitment-claim-v1"
    SCHEME_CHOICES = [
        (SCHEME_COMMITMENT_CLAIM_V1, "Commitment + entropy claim (v1)"),
    ]

    STATUS_ACCEPTED = "accepted"
    STATUS_REJECTED = "rejected"
    STATUS_CHOICES = [
        (STATUS_ACCEPTED, "Accepted"),
        (STATUS_REJECTED, "Rejected"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="reputation_proofs",
    )
    scheme = models.CharField(
        max_length=48,
        choices=SCHEME_CHOICES,
        default=SCHEME_COMMITMENT_CLAIM_V1,
    )
    scope_id = models.CharField(
        max_length=128,
        help_text="Opaque identifier for the password the proof is about (e.g. vault item ID).",
    )
    commitment = models.BinaryField(
        help_text="Provider-specific commitment payload.",
    )
    claimed_entropy_bits = models.PositiveIntegerField(
        help_text="Entropy threshold the proof claims the secret meets.",
    )
    status = models.CharField(max_length=16, choices=STATUS_CHOICES)
    score_delta = models.IntegerField(default=0)
    tokens_delta = models.BigIntegerField(default=0)
    error_message = models.CharField(max_length=256, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            # One accepted proof per (user, scope_id) — re-submitting with a
            # stronger claim supersedes via update_or_create in the service.
            models.UniqueConstraint(
                fields=["user", "scope_id", "scheme"],
                name="pw_reputation_proof_unique_scope",
            ),
        ]
        indexes = [
            models.Index(
                fields=["user", "-created_at"],
                name="pw_rep_proof_user_created_idx",
            ),
            models.Index(
                fields=["status", "-created_at"],
                name="pw_rep_proof_status_idx",
            ),
        ]
        verbose_name = "Reputation proof"
        verbose_name_plural = "Reputation proofs"

    def __str__(self) -> str:  # pragma: no cover
        return f"ReputationProof({self.id}, {self.status}, +{self.score_delta})"


class ReputationEvent(models.Model):
    """Append-only reputation ledger."""

    EVENT_PROOF_ACCEPTED = "proof_accepted"
    EVENT_PROOF_REJECTED = "proof_rejected"
    EVENT_BONUS = "bonus"
    EVENT_SLASH = "slash"
    EVENT_ANCHOR_CONFIRMED = "anchor_confirmed"
    EVENT_CHOICES = [
        (EVENT_PROOF_ACCEPTED, "Proof accepted"),
        (EVENT_PROOF_REJECTED, "Proof rejected"),
        (EVENT_BONUS, "Bonus"),
        (EVENT_SLASH, "Slash"),
        (EVENT_ANCHOR_CONFIRMED, "Anchor confirmed"),
    ]

    ANCHOR_STATUS_PENDING = "pending"
    ANCHOR_STATUS_INCLUDED = "included"
    ANCHOR_STATUS_CONFIRMED = "confirmed"
    ANCHOR_STATUS_FAILED = "failed"
    ANCHOR_STATUS_SKIPPED = "skipped"
    ANCHOR_STATUS_CHOICES = [
        (ANCHOR_STATUS_PENDING, "Pending"),
        (ANCHOR_STATUS_INCLUDED, "Included in batch"),
        (ANCHOR_STATUS_CONFIRMED, "Confirmed on-chain"),
        (ANCHOR_STATUS_FAILED, "Anchoring failed"),
        (ANCHOR_STATUS_SKIPPED, "Adapter skipped"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="reputation_events",
    )
    event_type = models.CharField(max_length=32, choices=EVENT_CHOICES)
    score_delta = models.IntegerField(default=0)
    tokens_delta = models.BigIntegerField(default=0)
    proof = models.ForeignKey(
        ReputationProof,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="events",
    )
    leaf_hash = models.BinaryField(
        help_text="SHA-256 leaf committed in the merkle batch (32 bytes).",
    )
    anchor_batch = models.ForeignKey(
        "AnchorBatch",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="events",
    )
    anchor_status = models.CharField(
        max_length=16,
        choices=ANCHOR_STATUS_CHOICES,
        default=ANCHOR_STATUS_PENDING,
    )
    note = models.CharField(max_length=256, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(
                fields=["user", "-created_at"],
                name="pw_rep_evt_user_created_idx",
            ),
            models.Index(
                fields=["anchor_status", "created_at"],
                name="pw_rep_evt_anchor_st_idx",
            ),
        ]
        verbose_name = "Reputation event"
        verbose_name_plural = "Reputation events"

    def __str__(self) -> str:  # pragma: no cover
        return f"ReputationEvent({self.id}, {self.event_type}, user={self.user_id})"


class AnchorBatch(models.Model):
    """Merkle batch roll-up submitted (or queued) to the on-chain registry."""

    STATUS_DRAFT = "draft"
    STATUS_SUBMITTED = "submitted"
    STATUS_CONFIRMED = "confirmed"
    STATUS_FAILED = "failed"
    STATUS_SKIPPED = "skipped"
    STATUS_CHOICES = [
        (STATUS_DRAFT, "Draft"),
        (STATUS_SUBMITTED, "Submitted"),
        (STATUS_CONFIRMED, "Confirmed"),
        (STATUS_FAILED, "Failed"),
        (STATUS_SKIPPED, "Skipped (null adapter)"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    adapter = models.CharField(
        max_length=32,
        help_text="Name of the AnchorAdapter that handled (or will handle) this batch.",
    )
    merkle_root = models.CharField(
        max_length=66,
        help_text="0x-prefixed hex string of the 32-byte Merkle root.",
    )
    batch_size = models.PositiveIntegerField()
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=STATUS_DRAFT)
    tx_hash = models.CharField(max_length=80, blank=True, default="")
    block_number = models.BigIntegerField(null=True, blank=True)
    network = models.CharField(max_length=32, blank=True, default="")
    error_message = models.CharField(max_length=256, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["-created_at"], name="pw_rep_batch_created_idx"),
            models.Index(fields=["status"], name="pw_rep_batch_status_idx"),
        ]
        verbose_name = "Anchor batch"
        verbose_name_plural = "Anchor batches"

    def __str__(self) -> str:  # pragma: no cover
        return f"AnchorBatch({self.id}, {self.status}, size={self.batch_size})"

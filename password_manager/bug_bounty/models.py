"""
Bug Bounty — Vault Self-Pentest models (Phase 1).

The self-pentest harness runs a battery of non-destructive, read-only checks
against the *requesting user's own* security posture and records the result as a
``SelfTestRun`` plus a deduplicated set of ``Finding`` rows.

Privacy: a Finding NEVER stores plaintext secrets. ``evidence`` holds only
metadata/counts the underlying security services already expose (e.g. number of
unresolved breach matches), and every row is owned by exactly one user.

Phase 2 adds the external-researcher bounty program on top of the same app:
``BountyProgram`` (an owner-defined program), ``Submission`` (a researcher's
report moving through a triage state machine), and ``Reward`` (a recorded payout
obligation). No money moves in-product — disbursement goes through a pluggable
adapter interface only (see ``rewards/adapters``). Researchers test the app's
defined attack surface; they never receive access to any user's vault data.
"""

from __future__ import annotations

import uuid
from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone


class Severity(models.TextChoices):
    INFO = 'info', 'Info'
    LOW = 'low', 'Low'
    MEDIUM = 'medium', 'Medium'
    HIGH = 'high', 'High'
    CRITICAL = 'critical', 'Critical'


class RunTrigger(models.TextChoices):
    MANUAL = 'manual', 'Manual'
    SCHEDULED = 'scheduled', 'Scheduled'


class RunStatus(models.TextChoices):
    RUNNING = 'running', 'Running'
    COMPLETED = 'completed', 'Completed'
    FAILED = 'failed', 'Failed'


class FindingStatus(models.TextChoices):
    OPEN = 'open', 'Open'
    ACKNOWLEDGED = 'acknowledged', 'Acknowledged'
    RESOLVED = 'resolved', 'Resolved'
    FALSE_POSITIVE = 'false_positive', 'False positive'


class SelfTestRun(models.Model):
    """One execution of the self-pentest harness for a single user."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='bug_bounty_runs',
    )
    trigger = models.CharField(
        max_length=16, choices=RunTrigger.choices, default=RunTrigger.MANUAL,
    )
    status = models.CharField(
        max_length=16, choices=RunStatus.choices, default=RunStatus.RUNNING,
    )
    # Counts by severity plus a 'total', e.g. {"high": 1, "total": 1, ...}.
    summary = models.JSONField(default=dict, blank=True)
    started_at = models.DateTimeField(default=timezone.now)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'bug_bounty_self_test_runs'
        ordering = ['-started_at']
        indexes = [models.Index(fields=['user', '-started_at'])]

    def __str__(self) -> str:
        return f'SelfTestRun<{self.user_id} {self.status} {self.started_at:%Y-%m-%d}>'


class Finding(models.Model):
    """
    A single posture issue surfaced by a check. Deduplicated per
    (user, check_id, fingerprint) so re-runs update the existing row rather than
    piling up duplicates.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='bug_bounty_findings',
    )
    run = models.ForeignKey(
        SelfTestRun,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='findings',
        help_text='The most recent run that re-surfaced this finding.',
    )
    check_id = models.CharField(max_length=64, db_index=True)
    title = models.CharField(max_length=255)
    severity = models.CharField(
        max_length=16, choices=Severity.choices, default=Severity.INFO,
    )
    status = models.CharField(
        max_length=16, choices=FindingStatus.choices, default=FindingStatus.OPEN,
    )
    remediation = models.TextField(blank=True, default='')
    # Metadata only — never plaintext secrets.
    evidence = models.JSONField(default=dict, blank=True)
    fingerprint = models.CharField(
        max_length=128,
        help_text='Stable identity of the logical issue, for dedup across runs.',
    )
    first_seen = models.DateTimeField(default=timezone.now)
    last_seen = models.DateTimeField(default=timezone.now)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'bug_bounty_findings'
        ordering = ['-last_seen']
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'check_id', 'fingerprint'],
                name='uniq_finding_user_check_fingerprint',
            ),
        ]
        indexes = [models.Index(fields=['user', 'status', 'severity'])]

    def save(self, *args, **kwargs):
        # Enforce the status/resolved_at invariant on every write path (admin,
        # API, service) — not just the API view: a closed finding has a
        # resolved_at, an open/acknowledged one does not.
        closed = self.status in (FindingStatus.RESOLVED, FindingStatus.FALSE_POSITIVE)
        desired = (self.resolved_at or timezone.now()) if closed else None
        if desired != self.resolved_at:
            self.resolved_at = desired
            update_fields = kwargs.get('update_fields')
            if update_fields is not None:
                kwargs['update_fields'] = set(update_fields) | {'resolved_at'}
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f'Finding<{self.check_id} {self.severity} {self.status}>'


# --------------------------------------------------------------------------- #
# Phase 2 — external-researcher bounty program
# --------------------------------------------------------------------------- #


class ProgramStatus(models.TextChoices):
    DRAFT = 'draft', 'Draft'
    ACTIVE = 'active', 'Active'
    PAUSED = 'paused', 'Paused'
    CLOSED = 'closed', 'Closed'


class SubmissionStatus(models.TextChoices):
    NEW = 'new', 'New'
    TRIAGING = 'triaging', 'Triaging'
    ACCEPTED = 'accepted', 'Accepted'
    DUPLICATE = 'duplicate', 'Duplicate'
    REJECTED = 'rejected', 'Rejected'
    RESOLVED = 'resolved', 'Resolved'
    REWARDED = 'rewarded', 'Rewarded'


class RewardStatus(models.TextChoices):
    OWED = 'owed', 'Owed'
    PAID = 'paid', 'Paid'
    VOID = 'void', 'Void'


class BountyProgram(models.Model):
    """An owner-defined bug-bounty program for the app's attack surface.

    Scope, policy, and reward tiers are published so researchers know what is in
    scope and what a valid report earns. A program only accepts submissions while
    ``ACTIVE``. Researchers test the defined surface (APIs/auth) — never any
    user's vault contents.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='bug_bounty_programs',
    )
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True, default='')
    # In-scope targets, e.g. ["api/vault/", "auth login flow"]. App surface only.
    scope = models.JSONField(default=list, blank=True)
    # Disclosure policy / rules of engagement (free text).
    policy = models.TextField(blank=True, default='')
    # Suggested reward per severity, e.g. {"high": 200, "critical": 500}.
    reward_tiers = models.JSONField(default=dict, blank=True)
    status = models.CharField(
        max_length=16, choices=ProgramStatus.choices, default=ProgramStatus.DRAFT,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'bug_bounty_programs'
        ordering = ['-created_at']
        indexes = [models.Index(fields=['owner', 'status'])]

    def __str__(self) -> str:
        return f'BountyProgram<{self.title} {self.status}>'


class Submission(models.Model):
    """A researcher's report against a program, moving through triage.

    State machine (enforced in ``services.triage_service``):

        new → triaging → accepted | duplicate | rejected
        accepted → resolved → rewarded

    ``duplicate``, ``rejected`` and ``rewarded`` are terminal. The researcher
    claims a severity; the owner assigns the authoritative one during triage.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    program = models.ForeignKey(
        BountyProgram,
        on_delete=models.CASCADE,
        related_name='submissions',
    )
    researcher = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='bug_bounty_submissions',
    )
    title = models.CharField(max_length=255)
    description = models.TextField()
    severity_claimed = models.CharField(
        max_length=16, choices=Severity.choices, default=Severity.MEDIUM,
    )
    # Empty until the owner triages; '' means "not yet assigned".
    severity_assigned = models.CharField(
        max_length=16, choices=Severity.choices, blank=True, default='',
    )
    status = models.CharField(
        max_length=16, choices=SubmissionStatus.choices,
        default=SubmissionStatus.NEW, db_index=True,
    )
    # The owner's note attached to the most recent triage transition.
    triage_note = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'bug_bounty_submissions'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['program', 'status']),
            models.Index(fields=['researcher', 'status']),
        ]

    def __str__(self) -> str:
        return f'Submission<{self.title} {self.status}>'


class Reward(models.Model):
    """A recorded payout obligation for a rewarded submission.

    This is an *obligation ledger entry*, not a payment. No payment processor is
    integrated (KYC/PCI/tax liability are out of scope). Disbursement is handled
    by a pluggable adapter (see ``rewards/adapters``); the default ``manual``
    adapter merely records an off-platform reference and moves no money.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    submission = models.OneToOneField(
        Submission,
        on_delete=models.CASCADE,
        related_name='reward',
    )
    amount = models.DecimalField(
        max_digits=12, decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
    )
    currency = models.CharField(max_length=3, default='USD')
    status = models.CharField(
        max_length=16, choices=RewardStatus.choices, default=RewardStatus.OWED,
    )
    # Which payout adapter is responsible for disbursing this reward.
    adapter = models.CharField(max_length=64, default='manual')
    # External/off-platform reference recorded once the adapter "pays".
    payout_ref = models.CharField(max_length=255, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    paid_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'bug_bounty_rewards'
        ordering = ['-created_at']

    def __str__(self) -> str:
        return f'Reward<{self.amount} {self.currency} {self.status}>'

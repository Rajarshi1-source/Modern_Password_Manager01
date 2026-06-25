"""
Bug Bounty — Vault Self-Pentest models (Phase 1).

The self-pentest harness runs a battery of non-destructive, read-only checks
against the *requesting user's own* security posture and records the result as a
``SelfTestRun`` plus a deduplicated set of ``Finding`` rows.

Privacy: a Finding NEVER stores plaintext secrets. ``evidence`` holds only
metadata/counts the underlying security services already expose (e.g. number of
unresolved breach matches), and every row is owned by exactly one user.

Phase 2 (BountyProgram / Submission / Reward — external researchers) is a
separate follow-up and intentionally not modelled here.
"""

from __future__ import annotations

import uuid

from django.conf import settings
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

    def __str__(self) -> str:
        return f'Finding<{self.check_id} {self.severity} {self.status}>'

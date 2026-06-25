"""
Self-pentest orchestration.

Runs every registered check against a user, records a ``SelfTestRun``, and
upserts the results into deduplicated ``Finding`` rows. This is the only place
that persists — checks themselves are pure, read-only probes.
"""

from __future__ import annotations

import logging

from django.db import transaction
from django.utils import timezone

from ..checks import CHECK_REGISTRY
from ..models import (
    Finding,
    FindingStatus,
    RunStatus,
    RunTrigger,
    SelfTestRun,
    Severity,
)

logger = logging.getLogger(__name__)

SEVERITY_ORDER = {
    Severity.INFO: 0,
    Severity.LOW: 1,
    Severity.MEDIUM: 2,
    Severity.HIGH: 3,
    Severity.CRITICAL: 4,
}


def run_self_test(user, trigger=RunTrigger.MANUAL, checks=None):
    """Execute the harness for ``user`` and return the completed ``SelfTestRun``.

    A failing check is logged and skipped — one broken probe never fails the run.
    """
    registry = CHECK_REGISTRY if checks is None else checks
    run = SelfTestRun.objects.create(user=user, trigger=trigger, status=RunStatus.RUNNING)

    results = []
    for check in registry:
        try:
            results.extend(check.run(user) or [])
        except Exception:
            logger.exception(
                'bug_bounty check %s failed for user %s',
                getattr(check, 'check_id', '?'), getattr(user, 'pk', '?'),
            )

    results.sort(key=lambda r: SEVERITY_ORDER.get(r.severity, 0), reverse=True)

    with transaction.atomic():
        for result in results:
            _upsert_finding(user, run, result)
        run.status = RunStatus.COMPLETED
        run.completed_at = timezone.now()
        run.summary = _summarise(results)
        run.save(update_fields=['status', 'completed_at', 'summary'])

    return run


def _summarise(results) -> dict:
    counts = {sev.value: 0 for sev in Severity}
    for result in results:
        counts[result.severity] = counts.get(result.severity, 0) + 1
    counts['total'] = len(results)
    return counts


def _upsert_finding(user, run, result):
    """Create or update the Finding for this (user, check_id, fingerprint)."""
    now = timezone.now()
    finding, created = Finding.objects.update_or_create(
        user=user,
        check_id=result.check_id,
        fingerprint=result.fingerprint,
        defaults={
            'run': run,
            'title': result.title,
            'severity': result.severity,
            'remediation': result.remediation,
            'evidence': result.evidence,
            'last_seen': now,
        },
    )
    if not created and finding.status in (FindingStatus.RESOLVED, FindingStatus.FALSE_POSITIVE):
        # The issue re-fired after being closed — reopen it.
        finding.status = FindingStatus.OPEN
        finding.resolved_at = None
        finding.save(update_fields=['status', 'resolved_at'])
    return finding

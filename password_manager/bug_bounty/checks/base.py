"""
Check framework for the vault self-pentest harness.

A check is a small, **read-only, non-destructive** probe of one aspect of the
user's security posture. It reuses an existing security service/model as its
signal source (via a lazy import so the bug_bounty app stays decoupled and
loads even if a dependency is unavailable) and returns zero or more
``FindingResult`` objects describing what it found.

Checks contain no persistence logic — ``self_test_service`` turns the returned
results into deduplicated ``Finding`` rows.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class FindingResult:
    """A check's verdict for one logical issue (not yet persisted)."""

    check_id: str
    title: str
    severity: str          # one of models.Severity values
    remediation: str
    fingerprint: str       # stable per logical issue → dedup across runs
    evidence: dict = field(default_factory=dict)  # metadata only, no secrets


class BaseCheck:
    """Base class for posture checks. Subclasses implement ``run``."""

    check_id: str = ''
    title: str = ''

    def run(self, user) -> list[FindingResult]:
        """Return findings for ``user``. Must be read-only and never raise on
        a missing/degraded signal — return ``[]`` instead."""
        raise NotImplementedError

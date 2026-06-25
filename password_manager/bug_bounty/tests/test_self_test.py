"""
Tests for the Bug Bounty vault self-pentest (Phase 1).

Covers:
  * per-check logic (signals mocked so tests are deterministic / decoupled)
  * the orchestration service (aggregation, dedup/upsert, failure isolation, reopen)
  * a real end-to-end run exercising the actual check registry (import-safety +
    graceful degradation)
  * the API (ownership scoping, on-demand run, finding status transitions)
"""

from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

import bug_bounty.services.self_test_service as svc
from bug_bounty.checks.base import FindingResult
from bug_bounty.checks.breach_exposure import BreachExposureCheck
from bug_bounty.checks.missing_mfa import MissingMFACheck
from bug_bounty.models import Finding, FindingStatus, RunStatus
from bug_bounty.services.self_test_service import run_self_test

User = get_user_model()


@pytest.fixture
def user(db):
    return User.objects.create_user(
        username='alice', email='alice@example.com', password='pw-aaa-12345',
    )


class _StubCheck:
    """A check returning a fixed list of FindingResults."""

    check_id = 'stub'

    def __init__(self, results):
        self._results = results

    def run(self, _user):
        return list(self._results)


def _result(check_id='c1', severity='high', fingerprint='fp1'):
    return FindingResult(
        check_id=check_id, title='t', severity=severity,
        remediation='fix', fingerprint=fingerprint, evidence={'n': 1},
    )


# --------------------------------------------------------------------------- #
# Check logic (signals mocked)
# --------------------------------------------------------------------------- #

def test_missing_mfa_fires_when_no_device(monkeypatch, user):
    check = MissingMFACheck()
    monkeypatch.setattr(check, '_has_mfa', lambda _u: False)
    results = check.run(user)
    assert [r.check_id for r in results] == ['mfa_disabled']
    assert results[0].severity == 'high'


def test_missing_mfa_silent_when_enabled_or_unknown(monkeypatch, user):
    check = MissingMFACheck()
    monkeypatch.setattr(check, '_has_mfa', lambda _u: True)
    assert check.run(user) == []
    monkeypatch.setattr(check, '_has_mfa', lambda _u: None)  # signal unavailable
    assert check.run(user) == []


def test_breach_exposure_severity_and_evidence(monkeypatch, user):
    check = BreachExposureCheck()
    monkeypatch.setattr(check, '_collect', lambda _u: (3, True))   # severe present
    res = check.run(user)
    assert res[0].severity == 'critical'
    assert res[0].evidence == {'unresolved_matches': 3, 'severe_breach_present': True}

    monkeypatch.setattr(check, '_collect', lambda _u: (1, False))  # only low/medium
    assert check.run(user)[0].severity == 'high'

    monkeypatch.setattr(check, '_collect', lambda _u: (0, False))
    assert check.run(user) == []
    monkeypatch.setattr(check, '_collect', lambda _u: None)  # unavailable
    assert check.run(user) == []


# --------------------------------------------------------------------------- #
# Orchestration service
# --------------------------------------------------------------------------- #

def test_service_records_run_and_creates_finding(user):
    run = run_self_test(user, checks=[_StubCheck([_result()])])
    assert run.status == RunStatus.COMPLETED
    assert run.completed_at is not None
    assert run.summary['high'] == 1
    assert run.summary['total'] == 1
    assert Finding.objects.filter(user=user, check_id='c1').count() == 1


def test_service_dedups_on_rerun(user):
    stub = _StubCheck([_result()])
    run_self_test(user, checks=[stub])
    run_self_test(user, checks=[stub])
    # Same (user, check_id, fingerprint) → upserted, never duplicated.
    assert Finding.objects.filter(user=user, check_id='c1').count() == 1


def test_service_isolates_a_failing_check(user):
    class Boom:
        check_id = 'boom'

        def run(self, _user):
            raise RuntimeError('nope')

    run = run_self_test(user, checks=[Boom(), _StubCheck([_result()])])
    assert run.status == RunStatus.COMPLETED
    assert Finding.objects.filter(user=user).count() == 1


def test_resolved_finding_reopens_when_it_refires(user):
    stub = _StubCheck([_result()])
    run_self_test(user, checks=[stub])
    finding = Finding.objects.get(user=user, check_id='c1')
    finding.status = FindingStatus.RESOLVED
    finding.save(update_fields=['status'])

    run_self_test(user, checks=[stub])
    finding.refresh_from_db()
    assert finding.status == FindingStatus.OPEN
    assert finding.resolved_at is None


def test_real_registry_run_is_import_safe(user):
    """Import-safety / graceful-degradation contract: the real registry runs
    without raising and the run completes. No specific finding is asserted —
    each check legitimately degrades to a no-op when its optional signal is
    absent (the MFA-positive path is covered by the _has_mfa unit tests).
    """
    run = run_self_test(user)  # real CHECK_REGISTRY
    assert run.status == RunStatus.COMPLETED
    assert run.completed_at is not None
    assert 'total' in run.summary


def test_service_dedupes_duplicate_fingerprints_in_summary(user):
    dup = _StubCheck([_result(fingerprint='same'), _result(fingerprint='same')])
    run = run_self_test(user, checks=[dup])
    assert run.summary['total'] == 1
    assert Finding.objects.filter(user=user, check_id='c1').count() == 1


def test_evidence_is_sanitized_before_persisting(user):
    leaky = _StubCheck([FindingResult(
        check_id='c1', title='t', severity='low', remediation='fix',
        fingerprint='fp1',
        evidence={'count': 2, 'nested': {'secret': 'p@ss'}, 'blob': ['x'] * 100},
    )])
    run_self_test(user, checks=[leaky])
    finding = Finding.objects.get(user=user, check_id='c1')
    assert finding.evidence == {'count': 2}  # nested dict + list dropped


def test_model_enforces_resolved_at_invariant(user):
    """resolved_at bookkeeping holds on direct (non-API) writes too."""
    finding = Finding.objects.create(
        user=user, check_id='c1', title='t', severity='high', fingerprint='fp',
    )
    assert finding.resolved_at is None
    finding.status = FindingStatus.RESOLVED
    finding.save()
    finding.refresh_from_db()
    assert finding.resolved_at is not None
    finding.status = FindingStatus.OPEN
    finding.save()
    finding.refresh_from_db()
    assert finding.resolved_at is None


# --------------------------------------------------------------------------- #
# API
# --------------------------------------------------------------------------- #

@pytest.fixture
def auth_client(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def test_run_endpoint_returns_completed_run(monkeypatch, auth_client):
    monkeypatch.setattr(svc, 'CHECK_REGISTRY', [_StubCheck([_result()])])
    resp = auth_client.post('/api/bug-bounty/self-test/run/')
    assert resp.status_code == 201
    assert resp.data['latest_run']['status'] == 'completed'
    assert len(resp.data['findings']) == 1


def test_findings_are_owner_scoped(user):
    other = User.objects.create_user(username='bob', password='pw-bbb-12345')
    Finding.objects.create(
        user=other, check_id='c1', title='t', severity='high', fingerprint='fp',
    )
    client = APIClient()
    client.force_authenticate(user=user)
    resp = client.get('/api/bug-bounty/findings/')
    assert resp.status_code == 200
    data = resp.data
    items = data['results'] if isinstance(data, dict) and 'results' in data else data
    assert list(items) == []  # no cross-user leakage


def test_patch_finding_status_marks_resolved(auth_client, user):
    finding = Finding.objects.create(
        user=user, check_id='c1', title='t', severity='high', fingerprint='fp',
    )
    resp = auth_client.patch(
        f'/api/bug-bounty/findings/{finding.id}/',
        {'status': 'resolved'}, format='json',
    )
    assert resp.status_code == 200
    finding.refresh_from_db()
    assert finding.status == FindingStatus.RESOLVED
    assert finding.resolved_at is not None


def test_empty_patch_does_not_clear_resolved_at(auth_client, user):
    finding = Finding.objects.create(
        user=user, check_id='c1', title='t', severity='high', fingerprint='fp',
        status=FindingStatus.RESOLVED,
    )
    finding.refresh_from_db()
    assert finding.resolved_at is not None  # set by Finding.save() on create

    resp = auth_client.patch(f'/api/bug-bounty/findings/{finding.id}/', {}, format='json')

    assert resp.status_code == 200
    finding.refresh_from_db()
    assert finding.resolved_at is not None  # an empty PATCH must not erase it

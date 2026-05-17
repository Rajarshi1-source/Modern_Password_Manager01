"""
Tests for the periodic ``check_compromised_passwords`` Celery beat task.

The schedule entry in ``password_manager/celery.py`` ("check-data-breaches",
every 6 hours) points at ``ml_dark_web.tasks.check_compromised_passwords``;
prior to this PR no such task existed, so beat silently ``KeyError``'d on
every fire. These tests verify the new task dispatches only the rows it
should and respects its bounded-dispatch contract.

We mock ``match_credentials_against_breach.delay`` so the tests don't need
a running Celery worker and don't end up actually loading the BERT /
Siamese network ML models.
"""
from datetime import timedelta
from unittest.mock import patch

import pytest
from django.utils import timezone

from ml_dark_web.models import BreachSource, MLBreachData
from ml_dark_web.tasks import check_compromised_passwords


@pytest.fixture
def source(db):
    """Minimal BreachSource so MLBreachData rows have a valid FK."""
    return BreachSource.objects.create(
        name='test-source',
        source_type='paste',
        url='https://example.invalid/test-source',
        is_active=True,
    )


def _make_breach(source, *, status: str, age_minutes: int, breach_id: str) -> MLBreachData:
    """Create an MLBreachData row and force its detected_at past auto_now_add.

    ``detected_at`` has ``auto_now_add=True``, so we can't pass it to
    ``create()``. We update it after the fact via a queryset ``.update()``
    (which bypasses ``auto_now_add``) so the test can simulate rows that
    have aged in the database.
    """
    breach = MLBreachData.objects.create(
        breach_id=breach_id,
        title='test breach',
        description='test description',
        source=source,
        severity='LOW',
        confidence_score=0.5,
        raw_content='',
        processing_status=status,
    )
    if age_minutes:
        MLBreachData.objects.filter(pk=breach.pk).update(
            detected_at=timezone.now() - timedelta(minutes=age_minutes),
        )
        breach.refresh_from_db()
    return breach


@pytest.mark.django_db
class TestCheckCompromisedPasswords:
    """Beat-driven periodic sweep that re-drives stuck matching jobs."""

    def test_no_breaches_returns_zero(self):
        """Empty backlog yields a clean zero-result, no dispatch."""
        with patch('ml_dark_web.tasks.match_credentials_against_breach.delay') as m:
            result = check_compromised_passwords()
        assert result == {
            'success': True,
            'dispatched': 0,
            'pending': 0,
            'stuck': 0,
        }
        m.assert_not_called()

    def test_dispatches_pending_breaches(self, source):
        """Every 'pending' row should be dispatched, regardless of age."""
        b1 = _make_breach(source, status='pending', age_minutes=1, breach_id='p1')
        b2 = _make_breach(source, status='pending', age_minutes=120, breach_id='p2')
        with patch('ml_dark_web.tasks.match_credentials_against_breach.delay') as m:
            result = check_compromised_passwords()
        assert result['success'] is True
        assert result['dispatched'] == 2
        assert result['pending'] == 2
        assert result['stuck'] == 0
        dispatched_ids = {call.args[0] for call in m.call_args_list}
        assert dispatched_ids == {b1.pk, b2.pk}

    def test_dispatches_stuck_analyzing_only_when_aged(self, source):
        """An 'analyzing' row counts as stuck only past the threshold.

        The default ``stale_analyzing_minutes`` is 30. A row aged 5
        minutes must NOT be dispatched (a worker is probably still
        chewing on it); a row aged 60 minutes must be.
        """
        recent = _make_breach(source, status='analyzing', age_minutes=5, breach_id='a-recent')
        stuck = _make_breach(source, status='analyzing', age_minutes=60, breach_id='a-stuck')
        with patch('ml_dark_web.tasks.match_credentials_against_breach.delay') as m:
            result = check_compromised_passwords()
        assert result['dispatched'] == 1
        assert result['stuck'] == 1
        assert result['pending'] == 0
        dispatched_ids = {call.args[0] for call in m.call_args_list}
        assert dispatched_ids == {stuck.pk}
        assert recent.pk not in dispatched_ids

    def test_ignores_terminal_states(self, source):
        """matched / completed / failed rows must never be re-dispatched."""
        for term_status in ('matched', 'completed', 'failed'):
            _make_breach(
                source,
                status=term_status,
                age_minutes=180,
                breach_id=f'done-{term_status}',
            )
        with patch('ml_dark_web.tasks.match_credentials_against_breach.delay') as m:
            result = check_compromised_passwords()
        assert result == {
            'success': True,
            'dispatched': 0,
            'pending': 0,
            'stuck': 0,
        }
        m.assert_not_called()

    def test_respects_max_dispatch_cap(self, source):
        """A surge of pending rows must not trigger an unbounded dispatch storm.

        The cap defaults to 200 but is parametrised so a test can use a
        small bound; we use 3 here to keep the test fast.
        """
        for i in range(5):
            _make_breach(source, status='pending', age_minutes=1, breach_id=f'surge-{i}')
        with patch('ml_dark_web.tasks.match_credentials_against_breach.delay') as m:
            result = check_compromised_passwords(max_dispatch=3)
        assert result['dispatched'] == 3
        assert result['pending'] == 3
        assert m.call_count == 3

    def test_oldest_first_ordering(self, source):
        """When capped, the oldest rows are processed first.

        This makes the sweep eventually-consistent: each tick chips
        away at the oldest backlog instead of repeatedly re-processing
        the newest rows while older ones starve.
        """
        old = _make_breach(source, status='pending', age_minutes=180, breach_id='old')
        new = _make_breach(source, status='pending', age_minutes=1, breach_id='new')
        with patch('ml_dark_web.tasks.match_credentials_against_breach.delay') as m:
            check_compromised_passwords(max_dispatch=1)
        assert m.call_count == 1
        dispatched_id = m.call_args_list[0].args[0]
        assert dispatched_id == old.pk
        assert dispatched_id != new.pk

    def test_swallows_unexpected_errors(self, source, monkeypatch):
        """The sweep must never crash beat — failures return success=False."""
        _make_breach(source, status='pending', age_minutes=1, breach_id='boom')

        def explode(_breach_id):
            raise RuntimeError('matcher backend offline')

        monkeypatch.setattr(
            'ml_dark_web.tasks.match_credentials_against_breach.delay',
            explode,
        )
        result = check_compromised_passwords()
        assert result['success'] is False
        assert 'matcher backend offline' in result['error']

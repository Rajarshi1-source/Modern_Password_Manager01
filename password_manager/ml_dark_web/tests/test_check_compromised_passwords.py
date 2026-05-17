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


def _refresh_status(breach: MLBreachData) -> str:
    """Convenience: refetch the row and return its processing_status."""
    return MLBreachData.objects.values_list(
        'processing_status', flat=True,
    ).get(pk=breach.pk)


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
        breach = _make_breach(source, status='pending', age_minutes=1, breach_id='boom')

        def explode(_breach_id):
            raise RuntimeError('matcher backend offline')

        monkeypatch.setattr(
            'ml_dark_web.tasks.match_credentials_against_breach.delay',
            explode,
        )
        result = check_compromised_passwords()
        assert result['success'] is False
        assert 'matcher backend offline' in result['error']
        # CodeRabbit major on PR #244 follow-up: the claim must be
        # REVERTED when the broker publish fails. Otherwise the
        # row sits as 'analyzing' until staleness recapture
        # (~stale_analyzing_minutes), wasting a whole tick interval.
        assert _refresh_status(breach) == 'pending', (
            'failed dispatch must revert pending → analyzing claim'
        )

    # ------------------------------------------------------------------
    # Tests added in response to PR #244 review feedback.
    # ------------------------------------------------------------------

    @pytest.mark.parametrize('bad_value', [-1, -30, -200])
    def test_rejects_negative_stale_analyzing_minutes(self, bad_value):
        """CodeRabbit major on PR #244: validate input bounds.

        A negative staleness window would push the cutoff into the
        future and silently re-dispatch every ``analyzing`` row on
        each tick. Reject up-front.
        """
        with patch('ml_dark_web.tasks.match_credentials_against_breach.delay') as m:
            result = check_compromised_passwords(stale_analyzing_minutes=bad_value)
        assert result['success'] is False
        assert 'stale_analyzing_minutes' in result['error']
        m.assert_not_called()

    @pytest.mark.parametrize('bad_value', [-1, -100])
    def test_rejects_negative_max_dispatch(self, bad_value):
        """CodeRabbit major on PR #244: validate input bounds.

        Negative ``max_dispatch`` makes the queryset slice
        ``[:negative]`` skip the safety cap entirely on some ORMs.
        Reject up-front instead of producing surprising behaviour.
        """
        with patch('ml_dark_web.tasks.match_credentials_against_breach.delay') as m:
            result = check_compromised_passwords(max_dispatch=bad_value)
        assert result['success'] is False
        assert 'max_dispatch' in result['error']
        m.assert_not_called()

    def test_zero_max_dispatch_is_a_clean_no_op(self, source):
        """``max_dispatch=0`` is a valid "disable this tick" signal."""
        _make_breach(source, status='pending', age_minutes=1, breach_id='pending-quiet')
        with patch('ml_dark_web.tasks.match_credentials_against_breach.delay') as m:
            result = check_compromised_passwords(max_dispatch=0)
        assert result == {
            'success': True,
            'dispatched': 0,
            'pending': 0,
            'stuck': 0,
        }
        m.assert_not_called()

    def test_pending_row_is_atomically_claimed_before_dispatch(self, source):
        """Codex P1 on PR #244: dispatch must atomically claim the row.

        After a successful dispatch the row's status must be
        ``analyzing`` so a subsequent sweep can't double-dispatch.
        """
        breach = _make_breach(source, status='pending', age_minutes=1, breach_id='claim-me')
        with patch('ml_dark_web.tasks.match_credentials_against_breach.delay') as m:
            result = check_compromised_passwords()
        assert result['dispatched'] == 1
        m.assert_called_once_with(breach.pk)
        # The claim happened — row is no longer pending.
        assert _refresh_status(breach) == 'analyzing'

    def test_lost_claim_race_skips_dispatch(self, source):
        """Codex P1 on PR #244: simulate a row whose status flips
        between the candidate-select and the claim UPDATE.

        We do that by having ``.delay`` flip the *next* candidate's
        status during the first dispatch. The candidate select has
        already happened, so the second loop iteration must observe
        the changed status via the claim precondition and skip.
        """
        first = _make_breach(source, status='pending', age_minutes=2, breach_id='first')
        second = _make_breach(source, status='pending', age_minutes=1, breach_id='second')

        def flip_second(_breach_id):
            # Simulate a concurrent worker completing the second row
            # while we're mid-loop. The claim precondition for the
            # second row will now fail (status != 'pending') so we
            # must NOT dispatch it.
            MLBreachData.objects.filter(pk=second.pk).update(processing_status='completed')

        with patch(
            'ml_dark_web.tasks.match_credentials_against_breach.delay',
            side_effect=flip_second,
        ) as m:
            result = check_compromised_passwords()

        # Two candidates were SELECTED (pending=2), but only one was
        # successfully CLAIMED + dispatched. The other lost the race.
        assert result['pending'] == 2
        assert result['dispatched'] == 1
        assert m.call_count == 1
        dispatched_id = m.call_args_list[0].args[0]
        assert dispatched_id == first.pk
        # Second row keeps the status the racing worker set; not analyzing.
        assert _refresh_status(second) == 'completed'

    def test_stuck_analyzing_claim_respects_staleness_at_claim_time(self, source):
        """Codex P1 on PR #244: the stuck-analyzing claim must re-
        verify the staleness gate at UPDATE time.

        We exercise the race by having the dispatch of the FIRST
        stuck row freshen the SECOND row's ``detected_at`` (simulating
        a concurrent worker finally re-touching it). The second row
        passed the initial candidate select but its claim must fail
        because the staleness precondition now matches at "now".
        """
        # Two stuck rows ordered by detected_at; processed first → second.
        stuck_first = _make_breach(
            source, status='analyzing', age_minutes=120, breach_id='stuck-first',
        )
        stuck_second = _make_breach(
            source, status='analyzing', age_minutes=60, breach_id='stuck-second',
        )

        def freshen_second(_breach_id):
            # When we dispatch stuck_first, simulate a concurrent
            # worker freshly touching stuck_second so its detected_at
            # is now well WITHIN the staleness threshold.
            MLBreachData.objects.filter(pk=stuck_second.pk).update(
                detected_at=timezone.now(),
            )

        with patch(
            'ml_dark_web.tasks.match_credentials_against_breach.delay',
            side_effect=freshen_second,
        ) as m:
            result = check_compromised_passwords()

        # stuck_first wins its claim (still old at claim time) and
        # dispatches. stuck_second's claim fails because the freshen
        # side-effect ran before our loop reached it — so its
        # detected_at__lt=cutoff precondition now misses.
        dispatched_ids = {call.args[0] for call in m.call_args_list}
        assert stuck_first.pk in dispatched_ids
        assert stuck_second.pk not in dispatched_ids
        assert result['dispatched'] == 1
        assert result['stuck'] == 2  # both made it into the candidate select

    def test_claim_bumps_processed_at_out_of_stale_window(self, source):
        """Codex P2 on PR #244 follow-up: a stuck-row claim must move
        ``processed_at`` to "now" so the next sweep tick does NOT
        re-dispatch the same row before staleness recapture.

        Without this bump, a single matcher pass that runs longer
        than the beat interval would be dispatched on every tick.
        """
        stuck = _make_breach(
            source, status='analyzing', age_minutes=60, breach_id='stuck-bump',
        )
        # processed_at starts NULL on a freshly-created MLBreachData
        # row — the closeout path is what writes it.
        stuck.refresh_from_db()
        assert stuck.processed_at is None

        with patch('ml_dark_web.tasks.match_credentials_against_breach.delay') as m:
            check_compromised_passwords()
        assert m.call_count == 1

        stuck.refresh_from_db()
        cutoff = timezone.now() - timedelta(minutes=30)
        assert stuck.processed_at is not None, (
            'claim must write processed_at so subsequent sweeps know '
            'the row was recently touched'
        )
        assert stuck.processed_at > cutoff, (
            'claim must bump processed_at well past the staleness cutoff'
        )

    def test_subsequent_sweep_does_not_re_dispatch_recently_claimed(self, source):
        """Codex P2 on PR #244 follow-up (end-to-end): once a sweep
        claims a stuck row, an immediate second sweep must not
        re-dispatch it. The processed_at bump on claim is what
        guarantees this.
        """
        _make_breach(
            source, status='analyzing', age_minutes=60, breach_id='claim-once',
        )

        with patch('ml_dark_web.tasks.match_credentials_against_breach.delay') as m1:
            check_compromised_passwords()
        assert m1.call_count == 1

        # Second sweep, immediately after — processed_at is fresh
        # (well within the staleness window), so the stuck filter
        # excludes the row entirely.
        with patch('ml_dark_web.tasks.match_credentials_against_breach.delay') as m2:
            result = check_compromised_passwords()
        assert m2.call_count == 0
        assert result['stuck'] == 0
        assert result['dispatched'] == 0


@pytest.mark.django_db
class TestMatcherIdempotenceWhenReDispatched:
    """Codex P1 on PR #244: a re-run of ``match_credentials_against_breach``
    that finds zero NEW matches must NOT regress a prior ``matched``
    status to ``completed`` with ``affected_records=0``.

    We exercise the small no-identifiers helper path that doesn't
    require the heavy ML stack: a breach with no extracted
    credentials and no extracted emails. That path used to overwrite
    status unconditionally; this test pins the matcher to PR-#244's
    decision matrix.
    """

    def test_matched_status_preserved_on_zero_new_matches(self, source, monkeypatch):
        """Direct exercise of the post-loop decision matrix.

        We inject a fake `get_credential_matcher` into sys.modules so
        the real ml_services module (which loads torch+transformers)
        never imports. The fake matcher returns zero matches, which
        is exactly the duplicate-run scenario.
        """
        import sys
        import types
        from ml_dark_web.models import UserCredentialMonitoring
        # Use get_user_model so a project AUTH_USER_MODEL override
        # still hits the right table. CodeRabbit nit on PR #244.
        from django.contrib.auth import get_user_model
        User = get_user_model()

        # Build a breach that already has a successful match recorded.
        breach = MLBreachData.objects.create(
            breach_id='prior-matched',
            title='prior',
            description='prior',
            source=source,
            severity='HIGH',
            confidence_score=0.9,
            raw_content='',
            processing_status='matched',
            affected_records=5,
            extracted_credentials=['hashed-cred-1'],
            extracted_emails=[],
        )

        # The credential matcher will be loaded via deferred import
        # inside the task body. Pre-populate sys.modules with a fake
        # so torch / transformers never get touched.
        fake_module = types.ModuleType('ml_dark_web.ml_services')

        class _FakeMatcher:
            def find_matches(self, _email_hash, _identifiers):
                return []  # zero NEW matches — the regression scenario
            def hash_credential(self, _credential):
                return 'hash'
            def get_embedding(self, _hash):
                import numpy as np
                return np.zeros(8, dtype=np.float32)

        fake_module.get_credential_matcher = lambda: _FakeMatcher()
        fake_module.get_breach_classifier = lambda: None
        monkeypatch.setitem(sys.modules, 'ml_dark_web.ml_services', fake_module)

        # Need at least one UserCredentialMonitoring row so the matcher
        # loop actually executes (otherwise the loop body never runs
        # and the decision matrix is exercised with matches_found=0
        # for a trivially-correct reason).
        user = User.objects.create_user(username='prior-victim', password='x')
        UserCredentialMonitoring.objects.create(
            user=user,
            email_hash='hashed-cred-1',
            domain='example.invalid',
            is_active=True,
        )

        # match_credentials_against_breach is a bound Celery task
        # (@shared_task(bind=True)) so calling it directly would treat
        # `breach.id` as `self`. `.apply()` runs the underlying
        # function synchronously and passes a real bound task instance
        # in as `self`. We read the return payload off the result.
        from ml_dark_web.tasks import match_credentials_against_breach
        async_result = match_credentials_against_breach.apply(args=[breach.id])
        result = async_result.get()
        assert result['success'] is True
        assert result['matches'] == 0

        # The critical assertion: prior 'matched' state survives.
        breach.refresh_from_db()
        assert breach.processing_status == 'matched', (
            'duplicate scan must not regress matched → completed'
        )
        assert breach.affected_records == 5, (
            'duplicate scan must not zero out a real prior match count'
        )

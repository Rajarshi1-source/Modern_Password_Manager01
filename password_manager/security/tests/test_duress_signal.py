"""
Tests for zero-knowledge duress signalling.

These cover the half of "Plausible Deniability Vault" that lives on the server.
The other half -- deciding WHICH vault to open -- is deliberately absent from
the backend entirely: it happens client-side via `hiddenVaultEnvelope.decode()`
so the master password never reaches this process. The most important
assertions here are therefore negative ones: that the endpoint reveals nothing,
and that no password is involved anywhere in the flow.
"""

import base64
import secrets
from unittest import mock

from django.contrib.auth.models import User
from django.core.cache import caches
from django.test import TestCase, TransactionTestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from security.models import DuressCode, DuressEvent, DuressSignal
from security.services.duress_code_service import get_duress_code_service


def make_token():
    """A well-formed signal token: base64 of 32 random bytes (44 chars)."""
    return base64.b64encode(secrets.token_bytes(32)).decode('ascii')


class DuressSignalModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='duress-user',
            email='duress@example.com',
            password='test-password-not-a-secret',  # noqa: S106
        )

    def test_hash_token_is_stable_and_not_reversible(self):
        token = make_token()

        self.assertEqual(
            DuressSignal.hash_token(token),
            DuressSignal.hash_token(token),
        )
        self.assertNotIn(token, DuressSignal.hash_token(token))
        self.assertEqual(len(DuressSignal.hash_token(token)), 64)

    def test_str_does_not_leak_the_hash(self):
        """__str__ lands in admin pages, logs and error reports."""
        token = make_token()
        signal = DuressSignal.objects.create(
            user=self.user, token_hash=DuressSignal.hash_token(token),
        )

        self.assertNotIn(signal.token_hash, str(signal))


class DuressSignalServiceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='duress-user',
            email='duress@example.com',
            password='test-password-not-a-secret',  # noqa: S106
        )
        self.service = get_duress_code_service()
        self.context = {'ip_address': '203.0.113.10', 'user_agent': 'test-agent'}

    def test_register_stores_only_the_hash(self):
        token = make_token()

        signal = self.service.register_signal_token(self.user, token)

        self.assertEqual(signal.token_hash, DuressSignal.hash_token(token))
        # The raw token must appear in no column.
        self.assertFalse(
            DuressSignal.objects.filter(token_hash=token).exists()
        )

    def test_registering_again_deactivates_the_previous_token(self):
        """A user re-running duress setup must not leave a live stale token."""
        first = self.service.register_signal_token(self.user, make_token())
        second = self.service.register_signal_token(self.user, make_token())

        first.refresh_from_db()
        second.refresh_from_db()
        self.assertFalse(first.is_active)
        self.assertTrue(second.is_active)

    def test_consume_unlock_signal_always_enqueues_identically(self):
        """The core regression test for round 2 of the timing fix.

        Round 1 moved the ACTIVATION work (evidence packages, decoy vaults,
        SilentAlarmService's blocking SMTP/webhook I/O) into a Celery task,
        but `consume_unlock_signal` still ran the digest-comparison loop on
        the request thread and called `.delay()` ONLY on a match.
        `Task.delay()` synchronously publishes to the broker before
        returning -- real network I/O -- so whether that publish happened at
        all was itself a smaller but real, still match-dependent timing
        signal.

        This asserts the round-2 fix structurally: for both a token that
        will turn out to match and one that will not, `consume_unlock_signal`
        does the exact same thing -- one `.delay()` call, identical argument
        shape, no synchronous DB query for existing signals at all. The
        matching itself no longer happens here, so there is nothing left on
        this call whose cost could vary with the outcome.
        """
        matching_token = make_token()
        self.service.register_signal_token(self.user, matching_token)
        non_matching_token = make_token()

        with mock.patch(
            'security.tasks.duress_tasks.activate_duress_signal_task.apply_async'
        ) as mock_apply_async:
            self.service.consume_unlock_signal(
                self.user, matching_token, self.context,
            )
            self.service.consume_unlock_signal(
                self.user, non_matching_token, self.context,
            )

        self.assertEqual(mock_apply_async.call_count, 2)
        first_call, second_call = mock_apply_async.call_args_list
        self.assertEqual(
            first_call.kwargs['kwargs'],
            {'user_id': self.user.id, 'signal': matching_token, 'request_context': self.context},
        )
        self.assertEqual(
            second_call.kwargs['kwargs'],
            {'user_id': self.user.id, 'signal': non_matching_token, 'request_context': self.context},
        )
        # Neither call touched the database -- no DuressSignal query, no
        # DuressEvent. Matching (and everything downstream of it) is now
        # exclusively the enqueued task's job.
        self.assertEqual(DuressEvent.objects.count(), 0)

    def test_matching_signal_never_calls_activate_duress_mode_inline(self):
        """Direct guard against the round-1 timing regression: `activate_duress_mode`
        (the entry point into evidence packages, decoy vaults, and
        SilentAlarmService's blocking SMTP/webhook calls) must not be called
        from the request thread at all."""
        token = make_token()
        self.service.register_signal_token(self.user, token)

        with mock.patch.object(
            self.service, 'activate_duress_mode'
        ) as mock_activate:
            self.service.consume_unlock_signal(self.user, token, self.context)

        mock_activate.assert_not_called()

    def test_consume_unlock_signal_returns_none(self):
        """The return value no longer means "matched" -- matching moved to
        the task, so nothing on the request thread can know the outcome. A
        caller checking a truthy/falsy return for match status would be
        silently wrong; pin the contract as None rather than leave it
        implicit."""
        result = self.service.consume_unlock_signal(
            self.user, make_token(), self.context,
        )

        self.assertIsNone(result)


class RegisterSignalTokenConcurrencyTests(TransactionTestCase):
    """`register_signal_token` must hold "one active signal per user" under
    real concurrent registration, not just sequential calls.

    Deactivate-then-create is not atomic against a second writer on its own:
    two transactions can both run their `.filter(is_active=True).update(...)`
    before either commits its `.create()`, so under READ COMMITTED neither
    sees the other's new row and both insert an active signal. A sequential
    test cannot observe this -- it needs real interleaving, hence
    `TransactionTestCase` + real threads rather than mocking the ORM.
    """

    def setUp(self):
        self.user = User.objects.create_user(
            username='race-user',
            email='race@example.com',
            password='test-password-not-a-secret',  # noqa: S106
        )

    def test_concurrent_registrations_leave_exactly_one_active_signal(self):
        from concurrent.futures import ThreadPoolExecutor
        import threading

        from django.db import connection, connections

        if connection.vendor == 'sqlite':
            # Same reasoning as ArmCeilingConcurrencyTests
            # (test_adaptive_policy_bandit.py) and EntangledDevicePairConcurrentInsertTests
            # (test_quantum_entanglement.py): SQLite serializes writers at the
            # file level rather than row-locking, so concurrent threads hit
            # "database is locked" regardless of whether select_for_update()
            # is correct. Real interleaving needs real MVCC row locks; this
            # runs against Postgres in CI.
            self.skipTest(
                "select_for_update() row-locking needs real MVCC. SQLite "
                "serializes writers at the file level instead, so concurrent "
                "threads fail with 'database is locked' independent of the "
                "fix under test. Runs against Postgres in CI."
            )

        n_threads = 8
        start_gate = threading.Event()
        errors = []
        errors_lock = threading.Lock()

        def worker(i):
            service = get_duress_code_service()
            try:
                if not start_gate.wait(timeout=5):
                    raise RuntimeError('start gate never opened')
                service.register_signal_token(self.user, make_token())
            except Exception as exc:  # noqa: BLE001 - surfaced on the main thread below
                with errors_lock:
                    errors.append(exc)
            finally:
                # Per-thread connections leak unless closed explicitly.
                connections.close_all()

        with ThreadPoolExecutor(max_workers=n_threads) as executor:
            futures = [executor.submit(worker, i) for i in range(n_threads)]
            start_gate.set()
            for f in futures:
                f.result(timeout=10)

        self.assertEqual(errors, [], f"worker threads failed: {errors}")
        self.assertEqual(
            DuressSignal.objects.filter(user=self.user, is_active=True).count(),
            1,
            "concurrent registrations left more than one active signal -- "
            "the alarm token a coerced user's client releases would no "
            "longer be the only thing being checked",
        )


class DuressSignalActivationTaskTests(TestCase):
    """The work `consume_unlock_signal` now defers to Celery.

    Run via `.apply()`, which executes the task body synchronously in-process
    -- no broker/worker needed. The task is plain (not `bind=True`; see its
    own docstring for why), so `.apply()` calls it directly with no `self`.
    """

    def setUp(self):
        self.user = User.objects.create_user(
            username='duress-user',
            email='duress@example.com',
            password='test-password-not-a-secret',  # noqa: S106
        )
        self.service = get_duress_code_service()
        self.context = {'ip_address': '203.0.113.10', 'user_agent': 'test-agent'}

    def _run(self, user, signal):
        from security.tasks.duress_tasks import activate_duress_signal_task

        activate_duress_signal_task.apply(
            kwargs={
                'user_id': user.id,
                'signal': signal,
                'request_context': self.context,
            },
        )

    def test_fires_and_counts(self):
        token = make_token()
        signal = self.service.register_signal_token(self.user, token)

        self._run(self.user, token)

        signal.refresh_from_db()
        self.assertEqual(signal.trigger_count, 1)
        self.assertIsNotNone(signal.last_triggered_at)

    def test_does_not_deactivate_after_firing(self):
        """Sustained coercion means repeated unlocks; silently disarming the
        alarm after the first would defeat the feature."""
        token = make_token()
        signal = self.service.register_signal_token(self.user, token)

        self._run(self.user, token)
        self._run(self.user, token)

        signal.refresh_from_db()
        self.assertTrue(signal.is_active)
        self.assertEqual(signal.trigger_count, 2)

    def test_concurrent_deactivation_between_match_and_trigger_update_does_not_fire(self):
        """TOCTOU guard: `register_signal_token` can deactivate this exact
        signal (its deactivate-then-create pattern) between the match loop's
        read, above, and the trigger-count update that follows it -- the two
        hold no lock in common. Simulates that race deterministically: the
        signal is still `is_active=True` when the match loop reads it, but a
        `filter(pk=...).update(is_active=False)` runs (standing in for the
        concurrent `register_signal_token` call) between that read and the
        task's own trigger-count update."""
        token = make_token()
        signal = self.service.register_signal_token(self.user, token)

        real_filter = DuressSignal.objects.filter

        def filter_with_race(*args, **kwargs):
            queryset = real_filter(*args, **kwargs)
            if kwargs.get('pk') == signal.pk:
                real_filter(pk=signal.pk).update(is_active=False)
            return queryset

        with mock.patch.object(
            DuressSignal.objects, 'filter', side_effect=filter_with_race,
        ):
            self._run(self.user, token)

        signal.refresh_from_db()
        self.assertFalse(signal.is_active)
        self.assertEqual(signal.trigger_count, 0)
        self.assertIsNone(signal.last_triggered_at)
        self.assertEqual(DuressEvent.objects.count(), 0)

    def test_non_matching_signal_does_nothing(self):
        """The matching decision itself now lives here, not on the request
        thread -- this is the only place left where "does nothing" can be
        verified for a token that was never registered."""
        self.service.register_signal_token(self.user, make_token())

        self._run(self.user, make_token())

        self.assertEqual(DuressEvent.objects.count(), 0)

    def test_deactivated_token_does_not_fire(self):
        """The is_active flag is only meaningful if the task honours it."""
        old_token = make_token()
        old_signal = self.service.register_signal_token(self.user, old_token)
        self.service.register_signal_token(self.user, make_token())

        self._run(self.user, old_token)

        old_signal.refresh_from_db()
        self.assertEqual(old_signal.trigger_count, 0)
        self.assertEqual(DuressEvent.objects.count(), 0)

    def test_another_users_token_never_matches(self):
        token = make_token()
        self.service.register_signal_token(self.user, token)
        other = User.objects.create_user(
            username='other-user',
            email='other@example.com',
            password='test-password-not-a-secret',  # noqa: S106
        )

        self._run(other, token)

        self.assertEqual(DuressEvent.objects.count(), 0)

    def test_missing_user_does_not_raise(self):
        """The user can vanish between request and task execution (deleted
        account, race in tests); must not crash the worker."""
        from security.tasks.duress_tasks import activate_duress_signal_task

        activate_duress_signal_task.apply(
            kwargs={
                'user_id': 0,
                'signal': make_token(),
                'request_context': self.context,
            },
        )  # no exception

    def test_activation_failure_does_not_raise(self):
        """The docstring's "never raises back to the caller" contract,
        actually enforced: activate_duress_mode does real DB writes, decoy
        generation, and (when enabled) SMTP/webhook alerts, any of which can
        fail. This task has no retry, so an uncaught exception here would
        just fail the task outright -- exactly what the try/except around
        the activation call exists to prevent."""
        token = make_token()
        self.service.register_signal_token(self.user, token)

        with mock.patch.object(
            self.service, 'activate_duress_mode',
            side_effect=RuntimeError('SMTP relay unreachable'),
        ):
            self._run(self.user, token)  # no exception

    def test_no_configured_code_still_records_an_event(self):
        """The alarm must not be silently swallowed."""
        token = make_token()
        self.service.register_signal_token(self.user, token)

        self._run(self.user, token)

        event = DuressEvent.objects.get(user=self.user)
        self.assertEqual(event.event_type, 'code_activated')
        self.assertEqual(event.ip_address, '203.0.113.10')

    def test_fallback_picks_highest_severity_code_not_alphabetical(self):
        """`order_by('-threat_level')` on a CharField would rank
        medium > low > high > critical -- the mildest response for the worst
        situation. Severity must be ranked explicitly."""
        token = make_token()
        self.service.register_signal_token(self.user, token)
        for level in ('low', 'medium', 'critical', 'high'):
            DuressCode.objects.create(
                user=self.user,
                code_hash=f'hash-{level}',
                threat_level=level,
                is_active=True,
            )

        self._run(self.user, token)

        event = DuressEvent.objects.filter(user=self.user).first()
        self.assertEqual(event.threat_level, 'critical')

    def test_prefers_the_signal_linked_code_over_severity_fallback(self):
        """When a signal was registered with an explicit duress_code, that
        code wins even if a higher-severity one also exists."""
        low_code = DuressCode.objects.create(
            user=self.user, code_hash='hash-low', threat_level='low', is_active=True,
        )
        DuressCode.objects.create(
            user=self.user, code_hash='hash-critical', threat_level='critical',
            is_active=True,
        )
        token = make_token()
        self.service.register_signal_token(
            self.user, token, duress_code=low_code,
        )

        self._run(self.user, token)

        event = DuressEvent.objects.filter(user=self.user).first()
        self.assertEqual(event.threat_level, 'low')


class DuressSignalAPITests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='duress-user',
            email='duress@example.com',
            password='test-password-not-a-secret',  # noqa: S106
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
        self.register_url = reverse('duress-signal-register')
        self.report_url = reverse('duress-signal-report')
        # Same isolation fix as DuressSignalReportRateLimitTests.setUp: the
        # 'rate_limiting' cache is process-wide and outlives the per-test
        # transaction rollback, so a counter left by an earlier test class
        # reusing this test's auto-incremented user PK would make
        # _within_report_budget silently skip the enqueue here -- silent
        # because the endpoint still answers 204 either way, so the only
        # visible symptom is an exact-call-count assertion (e.g.
        # mock_delay.assert_called_once()) failing for a reason unrelated to
        # what it's actually testing.
        caches['rate_limiting'].clear()

    def test_register_accepts_well_formed_token(self):
        response = self.client.post(
            self.register_url, {'token': make_token()}, format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(DuressSignal.objects.filter(user=self.user).exists())

    def test_register_rejects_wrong_length_token(self):
        response = self.client.post(
            self.register_url, {'token': 'too-short'}, format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_report_returns_204_on_match(self):
        token = make_token()
        get_duress_code_service().register_signal_token(self.user, token)

        response = self.client.post(
            self.report_url, {'signal': token}, format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

    def test_report_returns_identical_response_whether_or_not_it_matches(self):
        """The core indistinguishability property.

        A coercer holding the user's session can call this endpoint at will.
        Match, no-match, malformed, and no-signal-configured must be
        byte-identical, or they gain an oracle for whether the password they
        extracted was the real one.
        """
        token = make_token()
        get_duress_code_service().register_signal_token(self.user, token)

        matching = self.client.post(
            self.report_url, {'signal': token}, format='json',
        )
        non_matching = self.client.post(
            self.report_url, {'signal': make_token()}, format='json',
        )
        malformed = self.client.post(
            self.report_url, {'signal': 'nope'}, format='json',
        )
        missing = self.client.post(self.report_url, {}, format='json')

        for response in (matching, non_matching, malformed, missing):
            self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
            self.assertEqual(response.content, b'')

    def test_report_is_204_even_for_user_with_no_signal_configured(self):
        """Must not reveal that duress is unconfigured."""
        response = self.client.post(
            self.report_url, {'signal': make_token()}, format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(response.content, b'')

    def test_endpoints_require_authentication(self):
        anon = APIClient()

        self.assertIn(
            anon.post(self.report_url, {'signal': make_token()}, format='json').status_code,
            (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN),
        )
        self.assertIn(
            anon.post(self.register_url, {'token': make_token()}, format='json').status_code,
            (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN),
        )

    def test_no_password_field_is_accepted_anywhere_in_this_flow(self):
        """ZK contract guard.

        Neither endpoint may grow a password/master_password parameter. If one
        ever does, the decision has moved server-side and the invariant in
        docs/adaptive-password-zk-remediation-plan.md §1 is broken.

        Posts the ACTUALLY REGISTERED token (not an unrelated random one) --
        an earlier version of this test posted a fresh token that could never
        match, so it "proved" the password field changes nothing while never
        exercising the path where a real match occurs. Mocking `.delay` lets
        this assert the extra field never reaches the enqueued task's
        arguments, without needing the task itself to run.
        """
        token = make_token()
        get_duress_code_service().register_signal_token(self.user, token)

        with mock.patch(
            'security.tasks.duress_tasks.activate_duress_signal_task.apply_async'
        ) as mock_apply_async:
            response = self.client.post(
                self.report_url,
                {'signal': token, 'password': 'MyR3alP@ss'},  # noqa: S106
                format='json',
            )

        # The extra field is ignored, not honoured: same response, and it
        # never leaks into the task's arguments.
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(response.content, b'')
        mock_apply_async.assert_called_once()
        task_kwargs = mock_apply_async.call_args.kwargs['kwargs']
        self.assertEqual(task_kwargs['signal'], token)
        self.assertNotIn('password', task_kwargs)

    def test_report_endpoint_carries_no_throttle(self):
        """The default DEFAULT_THROTTLE_CLASSES (UserRateThrottle, 60/min in
        production, SHARED across every endpoint that doesn't override it --
        not scoped to this view) would make DRF return 429 from
        check_throttles() before this view even runs, once a user's combined
        API usage crosses that shared budget. That breaks the "always 204"
        contract under nothing more than ordinary heavy app use, let alone
        the sustained-coercion case this feature exists for.

        Asserted on the view's own declared throttle_classes rather than by
        firing 60+ real requests in a test -- deterministic and fast, and it
        fails immediately if the `@throttle_classes([])` decorator is ever
        removed, rather than only under load.
        """
        from security.api.duress_code_views import duress_signal_report

        self.assertEqual(duress_signal_report.cls.throttle_classes, [])


class DuressSignalReportRateLimitTests(TestCase):
    """The silent per-user cap that replaced the shared UserRateThrottle
    @throttle_classes([]) removed from duress_signal_report.

    Not a DRF throttle class: those return a 429 from check_throttles()
    before the view runs, which is exactly what @throttle_classes([]) was
    added to avoid. This is a plain function the view calls internally and
    branches on silently -- 204 either way, whether the request was
    processed or the budget skipped it.
    """

    def setUp(self):
        self.user = User.objects.create_user(
            username='rate-user',
            email='rate@example.com',
            password='test-password-not-a-secret',  # noqa: S106
        )
        # The 'rate_limiting' cache is process-wide and NOT part of Django's
        # per-test transaction rollback -- unlike the DB, it persists across
        # test methods. Django's auto-incremented user PKs get reused across
        # tests in the same run (each TestCase's transaction rolls back,
        # resetting the sequence), so a stale counter from an EARLIER test
        # that happened to create a user with the same numeric id would leak
        # into this one and desync the count from what each test expects.
        # Confirmed empirically, not assumed: this exact test failed with a
        # stale count before this clear() was added.
        caches['rate_limiting'].clear()

    def test_within_budget_allows_every_request(self):
        from security.api.duress_code_views import (
            _REPORT_RATE_LIMIT,
            _within_report_budget,
        )

        for _ in range(_REPORT_RATE_LIMIT):
            self.assertTrue(_within_report_budget(self.user.id))

    def test_exceeding_budget_returns_false(self):
        from security.api.duress_code_views import (
            _REPORT_RATE_LIMIT,
            _REPORT_RESERVE_LIMIT,
            _within_report_budget,
        )

        # The primary budget alone is not the whole story any more -- the
        # reserve slot (see test_reserve_survives_budget_exhaustion below)
        # lets one more request through after it. Exhaust both before
        # expecting a False.
        for _ in range(_REPORT_RATE_LIMIT + _REPORT_RESERVE_LIMIT):
            _within_report_budget(self.user.id)

        self.assertFalse(_within_report_budget(self.user.id))

    def test_reserve_survives_budget_exhaustion(self):
        """A coercer who exhausts the primary budget with a one-time burst
        of noise, then stops, must not be able to silently suppress the
        next report for the rest of that 60s window -- the reserve slot
        still lets exactly one more through, real signal or noise. This
        does NOT cover a continuously flooding attacker, who can keep
        winning the reserve's single slot every _REPORT_RESERVE_WINDOW_SECONDS
        indefinitely -- see the reserve's own comment in
        duress_code_views.py and plan doc §14.3."""
        from security.api.duress_code_views import (
            _REPORT_RATE_LIMIT,
            _within_report_budget,
        )

        for _ in range(_REPORT_RATE_LIMIT):
            _within_report_budget(self.user.id)

        self.assertTrue(_within_report_budget(self.user.id))
        # The reserve slot itself is a single-shot allowance per its own
        # window -- a second call right after it is exhausted too.
        self.assertFalse(_within_report_budget(self.user.id))

    def test_budget_is_tracked_per_user(self):
        """Exhausting one user's budget must not affect another's -- a
        shared counter would let one coerced/compromised session silence
        alarms for every other user on the same worker."""
        from security.api.duress_code_views import (
            _REPORT_RATE_LIMIT,
            _within_report_budget,
        )

        other = User.objects.create_user(
            username='other-rate-user',
            email='other-rate@example.com',
            password='test-password-not-a-secret',  # noqa: S106
        )

        for _ in range(_REPORT_RATE_LIMIT):
            _within_report_budget(self.user.id)

        self.assertTrue(_within_report_budget(other.id))

    def test_over_budget_report_still_returns_204_and_skips_the_enqueue(self):
        """The property that actually matters: exceeding the budget is
        silent. Same 204, same empty body, no observable difference from a
        normal call -- only the internal enqueue is skipped."""
        from security.api.duress_code_views import (
            _REPORT_RATE_LIMIT,
            _REPORT_RATE_WINDOW_SECONDS,
            _REPORT_RESERVE_LIMIT,
        )

        client = APIClient()
        client.force_authenticate(user=self.user)
        report_url = reverse('duress-signal-report')

        # The reserve slot's own window is only 5s (_REPORT_RESERVE_WINDOW_SECONDS);
        # 61 real POSTs plus DB/cache overhead could exceed that on a slow
        # runner, letting the reserve expire and the final request claim a
        # fresh slot -- flaking the assertion below for a reason unrelated to
        # the budget logic under test. Widened to match the primary window
        # for this test only, so the outcome depends on request COUNT, not
        # wall-clock time.
        with mock.patch(
            'security.api.duress_code_views._REPORT_RESERVE_WINDOW_SECONDS',
            _REPORT_RATE_WINDOW_SECONDS,
        ):
            # Exhaust the primary budget AND the reserve slot -- only the
            # request after both are spent should skip the enqueue.
            for _ in range(_REPORT_RATE_LIMIT + _REPORT_RESERVE_LIMIT):
                client.post(report_url, {'signal': make_token()}, format='json')

            with mock.patch(
                'security.tasks.duress_tasks.activate_duress_signal_task.apply_async'
            ) as mock_apply_async:
                response = client.post(
                    report_url, {'signal': make_token()}, format='json',
                )

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(response.content, b'')
        mock_apply_async.assert_not_called()

    def test_cache_failure_fails_open(self):
        """A Redis outage must not stop this endpoint answering 204 -- see
        _within_report_budget's own docstring on why it fails open. Patches
        the 'rate_limiting' alias with a mock whose add() raises, covering
        the except-and-return-True branch the primary-budget tests above
        never exercise (they all hit a working cache)."""
        from security.api.duress_code_views import _within_report_budget

        broken = mock.MagicMock()
        broken.add.side_effect = ConnectionError('redis down')
        with mock.patch(
            'security.api.duress_code_views.caches',
            {'rate_limiting': broken},
        ):
            self.assertTrue(_within_report_budget(self.user.id))

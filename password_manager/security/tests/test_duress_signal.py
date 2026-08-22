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
from django.test import TestCase
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
            password='test-password-not-a-secret',  # nosec B106
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
            password='test-password-not-a-secret',  # nosec B106
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

    def test_matching_signal_fires_but_defers_the_work(self):
        """`consume_unlock_signal` must dispatch, not execute, on a match.

        The activation work (DB writes beyond the signal row, evidence
        packages, decoy-vault generation, and outbound SilentAlarmService I/O)
        used to run inline here. That made a match measurably slower than a
        non-match's single digest comparison -- a latency oracle for a
        coercer holding the user's session. This asserts the fix structurally
        (nothing heavy runs on this call) rather than by timing, which would
        be flaky in CI.
        """
        token = make_token()
        signal = self.service.register_signal_token(self.user, token)

        with mock.patch(
            'security.tasks.duress_tasks.activate_duress_signal_task.delay'
        ) as mock_delay:
            fired = self.service.consume_unlock_signal(
                self.user, token, self.context,
            )

        self.assertTrue(fired)
        mock_delay.assert_called_once_with(
            signal_id=str(signal.id), request_context=self.context,
        )
        # Nothing synchronous touched the signal row or created an event --
        # that is now exclusively the enqueued task's job.
        signal.refresh_from_db()
        self.assertEqual(signal.trigger_count, 0)
        self.assertEqual(DuressEvent.objects.count(), 0)

    def test_matching_signal_never_calls_activate_duress_mode_inline(self):
        """Direct guard against the timing regression: `activate_duress_mode`
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

    def test_non_matching_signal_does_nothing(self):
        self.service.register_signal_token(self.user, make_token())

        with mock.patch(
            'security.tasks.duress_tasks.activate_duress_signal_task.delay'
        ) as mock_delay:
            fired = self.service.consume_unlock_signal(
                self.user, make_token(), self.context,
            )

        self.assertFalse(fired)
        mock_delay.assert_not_called()
        self.assertEqual(DuressEvent.objects.count(), 0)

    def test_a_deactivated_token_no_longer_fires(self):
        """The is_active flag is only meaningful if consume honours it."""
        old_token = make_token()
        self.service.register_signal_token(self.user, old_token)
        self.service.register_signal_token(self.user, make_token())

        fired = self.service.consume_unlock_signal(
            self.user, old_token, self.context,
        )

        self.assertFalse(fired)
        self.assertEqual(DuressEvent.objects.count(), 0)

    def test_another_users_token_never_matches(self):
        token = make_token()
        self.service.register_signal_token(self.user, token)
        other = User.objects.create_user(
            username='other-user',
            email='other@example.com',
            password='test-password-not-a-secret',  # nosec B106
        )

        fired = self.service.consume_unlock_signal(other, token, self.context)

        self.assertFalse(fired)


class DuressSignalActivationTaskTests(TestCase):
    """The work `consume_unlock_signal` now defers to Celery.

    Run via `.apply()`, which executes the task body synchronously in-process
    (no broker/worker needed) while still passing a real bound task instance
    as `self` for the `bind=True` task -- the same pattern already used by
    ml_dark_web/tests/test_check_compromised_passwords.py for a bound task.
    """

    def setUp(self):
        self.user = User.objects.create_user(
            username='duress-user',
            email='duress@example.com',
            password='test-password-not-a-secret',  # nosec B106
        )
        self.service = get_duress_code_service()
        self.context = {'ip_address': '203.0.113.10', 'user_agent': 'test-agent'}

    def _run(self, signal):
        from security.tasks.duress_tasks import activate_duress_signal_task

        activate_duress_signal_task.apply(
            kwargs={'signal_id': str(signal.id), 'request_context': self.context},
        )

    def test_fires_and_counts(self):
        signal = self.service.register_signal_token(self.user, make_token())

        self._run(signal)

        signal.refresh_from_db()
        self.assertEqual(signal.trigger_count, 1)
        self.assertIsNotNone(signal.last_triggered_at)

    def test_does_not_deactivate_after_firing(self):
        """Sustained coercion means repeated unlocks; silently disarming the
        alarm after the first would defeat the feature."""
        signal = self.service.register_signal_token(self.user, make_token())

        self._run(signal)
        self._run(signal)

        signal.refresh_from_db()
        self.assertTrue(signal.is_active)
        self.assertEqual(signal.trigger_count, 2)

    def test_missing_signal_does_not_raise(self):
        """The signal can vanish between match and task execution (e.g. the
        user re-runs duress setup in that window); must not crash the worker."""
        from security.tasks.duress_tasks import activate_duress_signal_task

        activate_duress_signal_task.apply(
            kwargs={
                'signal_id': '00000000-0000-0000-0000-000000000000',
                'request_context': self.context,
            },
        )  # no exception

    def test_no_configured_code_still_records_an_event(self):
        """The alarm must not be silently swallowed."""
        signal = self.service.register_signal_token(self.user, make_token())

        self._run(signal)

        event = DuressEvent.objects.get(user=self.user)
        self.assertEqual(event.event_type, 'code_activated')
        self.assertEqual(event.ip_address, '203.0.113.10')

    def test_fallback_picks_highest_severity_code_not_alphabetical(self):
        """`order_by('-threat_level')` on a CharField would rank
        medium > low > high > critical -- the mildest response for the worst
        situation. Severity must be ranked explicitly."""
        signal = self.service.register_signal_token(self.user, make_token())
        for level in ('low', 'medium', 'critical', 'high'):
            DuressCode.objects.create(
                user=self.user,
                code_hash=f'hash-{level}',
                threat_level=level,
                is_active=True,
            )

        self._run(signal)

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
        signal = self.service.register_signal_token(
            self.user, make_token(), duress_code=low_code,
        )

        self._run(signal)

        event = DuressEvent.objects.filter(user=self.user).first()
        self.assertEqual(event.threat_level, 'low')


class DuressSignalAPITests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='duress-user',
            email='duress@example.com',
            password='test-password-not-a-secret',  # nosec B106
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
        self.register_url = reverse('duress-signal-register')
        self.report_url = reverse('duress-signal-report')

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
        """
        token = make_token()
        get_duress_code_service().register_signal_token(self.user, token)

        response = self.client.post(
            self.report_url,
            {'signal': make_token(), 'password': 'MyR3alP@ss'},
            format='json',
        )

        # The extra field is ignored, not honoured: no alarm, no error.
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(DuressEvent.objects.count(), 0)

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

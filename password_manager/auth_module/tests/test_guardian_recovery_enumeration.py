"""
POST /api/auth/quantum-recovery/initiate_recovery/ is anonymous, so it must not
say anything about the account (OWASP Forgot Password Cheat Sheet).

It used to answer an unknown email with a generic message, an inactive setup
with 400, a travel lock with 403, a used-up monthly limit with 429 and a real
setup with the attempt_id. Every email now gets the same synchronous work and
the same answer; the account-dependent work runs in a task, and the attempt
link goes to the account's email.
"""

import base64
import re
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core import mail
from django.core.cache import cache
from django.db import connection
from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from auth_module.models import RecoveryNotice
from auth_module.quantum_recovery_models import (
    PasskeyRecoverySetup,
    RecoveryAttempt,
    RecoveryAuditLog,
)
from shared.tests import sealed_share_fixtures as fx


def _setup_for(email, **fields):
    user = User.objects.create_user(email.split('@')[0], email, 'Owner-Pass-1!')
    return PasskeyRecoverySetup.objects.create(
        user=user, total_shards=3, threshold_shards=2,
        **{'is_active': True, **fields},
    )


def _used_up(setup):
    for i in range(setup.max_recovery_attempts_per_month):
        RecoveryAttempt.objects.create(
            recovery_setup=setup, initiated_from_ip='127.0.0.1', shards_required=2,
            guardian_approvals_required=0, expires_at=timezone.now() + timedelta(days=1),
        )
    return setup


class AccountFixtureMixin:
    def setUp(self):
        cache.clear()  # initiate throttle counters
        self.anon = APIClient()
        self.url = reverse('quantum-recovery-initiate')
        self.key = fx.hybrid_public_key()
        User.objects.create_user('nosetup', 'nosetup@example.com', 'Owner-Pass-1!')
        _setup_for('active@example.com')
        _setup_for('inactive@example.com', is_active=False)
        _setup_for('locked@example.com', travel_lock_enabled=True,
                   travel_lock_until=timezone.now() + timedelta(days=7))
        _used_up(_setup_for('limited@example.com'))
        disabled = _setup_for('disabled@example.com')
        User.objects.filter(pk=disabled.user_id).update(is_active=False)
        # Django does not make User.email unique
        _setup_for('shared@example.com')
        User.objects.create_user('shared2', 'shared@example.com', 'Owner-Pass-1!')

    def _post(self, email, **extra):
        return self.anon.post(self.url, {
            'email': email, 'requester_public_key': self.key,
            'device_fingerprint': 'fp', **extra,
        }, format='json')


# With the test settings' memory:// broker a queued task does not run, so what
# these tests see is the synchronous half alone.
class InitiateAnswersEveryEmailAlikeTests(AccountFixtureMixin, TestCase):
    EMAILS = (
        'nobody@example.com',
        'nosetup@example.com',
        'active@example.com',
        'inactive@example.com',
        'locked@example.com',
        'limited@example.com',
        'disabled@example.com',
        'shared@example.com',
    )

    def _observe(self, email, **extra):
        cache.clear()
        with CaptureQueriesContext(connection) as queries:
            r = self._post(email, **extra)
        return r.status_code, r.content, len(queries)

    def test_status_body_and_query_count_do_not_depend_on_the_account(self):
        baseline = self._observe('nobody@example.com')
        self.assertEqual(baseline[0], 200, baseline[1])
        for email in self.EMAILS:
            with self.subTest(email=email):
                self.assertEqual(self._observe(email), baseline)

    def test_the_attempt_is_not_in_the_response(self):
        body = self._post('active@example.com').json()
        self.assertEqual(set(body), {'message'})

    def test_the_request_itself_touches_no_account_data(self):
        attempts = RecoveryAttempt.objects.count()
        self._post('active@example.com')
        self.assertEqual(RecoveryAttempt.objects.count(), attempts)
        self.assertFalse(RecoveryNotice.objects.exists())
        self.assertEqual(mail.outbox, [])

    def test_a_field_only_a_real_account_would_store_cannot_change_the_answer(self):
        # Values the attempt row could not hold must not fail for active
        # accounts alone.
        baseline = self._observe('nobody@example.com')
        for fingerprint in ('x' * 5000, {'a': 1}, 7):
            for email in ('nobody@example.com', 'active@example.com'):
                with self.subTest(email=email, fingerprint=str(fingerprint)[:8]):
                    self.assertEqual(self._observe(email, device_fingerprint=fingerprint), baseline)

    def test_bad_input_is_refused_the_same_way_for_every_email(self):
        for bad in ({'requester_public_key': 'nope'}, {'requester_public_key': None}):
            answers = {self._observe(email, **bad) for email in self.EMAILS}
            self.assertEqual(len(answers), 1, answers)
            self.assertEqual(answers.pop()[0], 400)
        for email in ('', None, {'a': 1}, ['active@example.com']):
            with self.subTest(email=email):
                self.assertEqual(self._post(email).status_code, 400)

    def test_every_email_shares_one_throttle(self):
        for _ in range(5):
            self.assertEqual(self._post('nobody@example.com').status_code, 200)
        self.assertEqual(self._post('active@example.com').status_code, 429)


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class InitiateTaskTests(AccountFixtureMixin, TestCase):
    def setUp(self):
        super().setUp()
        from auth_module.tasks import start_guardian_recovery
        patcher = patch.object(start_guardian_recovery, 'delay',
                               side_effect=lambda *a: start_guardian_recovery.apply(args=a))
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_an_active_setup_gets_an_attempt_that_keeps_the_requester_key(self):
        self.assertEqual(self._post('active@example.com').status_code, 200)
        attempt = RecoveryAttempt.objects.get(recovery_setup__user__email='active@example.com')
        self.assertEqual(bytes(attempt.requester_public_key), base64.b64decode(self.key))
        self.assertEqual(attempt.initiated_from_device_fingerprint, 'fp')
        self.assertEqual(attempt.initiated_from_ip, '127.0.0.1')
        self.assertEqual(attempt.status, 'initiated')
        self.assertIsNotNone(attempt.canary_alert_sent_at)
        self.assertTrue(RecoveryAuditLog.objects.filter(
            event_type='recovery_initiated', recovery_attempt_id=attempt.id).exists())

    def test_the_link_goes_to_the_accounts_email_with_a_cancel_link(self):
        self._post('active@example.com')
        attempt = RecoveryAttempt.objects.get(recovery_setup__user__email='active@example.com')
        self.assertEqual(len(mail.outbox), 1)
        message = mail.outbox[0]
        self.assertEqual(message.to, ['active@example.com'])
        self.assertIn(f'/recovery/guardian-attempt?attempt={attempt.id}', message.body)
        token = re.search(r'/recovery/cancel\?notice=([A-Za-z0-9_\-]+)', message.body).group(1)
        notice = RecoveryNotice.objects.get(user=attempt.recovery_setup.user)
        self.assertEqual(notice.event, 'guardian_recovery_started')
        self.assertTrue(notice.email_sent)

        r = self.anon.post(reverse('recovery-notice-cancel'), {'token': token}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        attempt.refresh_from_db()
        self.assertEqual(attempt.status, 'cancelled')

    def test_only_an_active_setup_gets_an_attempt_or_an_email(self):
        before = RecoveryAttempt.objects.count()
        for email in ('nobody@example.com', 'nosetup@example.com', 'inactive@example.com',
                      'locked@example.com', 'limited@example.com', 'disabled@example.com'):
            with self.subTest(email=email):
                cache.clear()
                self.assertEqual(self._post(email).status_code, 200)
                self.assertEqual(RecoveryAttempt.objects.count(), before)
                self.assertEqual(mail.outbox, [])
                self.assertFalse(RecoveryNotice.objects.exists())

    def test_an_email_two_accounts_share_reaches_the_one_with_a_setup(self):
        self.assertEqual(self._post('shared@example.com').status_code, 200)
        self.assertEqual(
            RecoveryAttempt.objects.filter(recovery_setup__user__email='shared@example.com').count(), 1)
        self.assertEqual(len(mail.outbox), 1)

    def test_the_monthly_limit_stops_a_repeated_request(self):
        setup = PasskeyRecoverySetup.objects.get(user__email='active@example.com')
        for _ in range(setup.max_recovery_attempts_per_month + 1):
            cache.clear()
            self.assertEqual(self._post('active@example.com').status_code, 200)
        self.assertEqual(setup.recovery_attempts.count(), setup.max_recovery_attempts_per_month)
        self.assertEqual(len(mail.outbox), setup.max_recovery_attempts_per_month)

    def test_an_oversized_fingerprint_does_not_lose_the_attempt(self):
        self._post('active@example.com', device_fingerprint='x' * 5000)
        attempt = RecoveryAttempt.objects.get(recovery_setup__user__email='active@example.com')
        self.assertEqual(attempt.initiated_from_device_fingerprint, 'x' * 255)

    def test_an_undelivered_email_is_not_recorded_as_sent(self):
        with patch('django.core.mail.send_mail', return_value=0):
            self._post('active@example.com')
        attempt = RecoveryAttempt.objects.get(recovery_setup__user__email='active@example.com')
        self.assertIsNone(attempt.canary_alert_sent_at)
        self.assertFalse(RecoveryNotice.objects.get(user=attempt.recovery_setup.user).email_sent)

    def test_a_broker_outage_gives_the_same_answer(self):
        from auth_module.tasks import start_guardian_recovery
        baseline = self._post('nobody@example.com')
        with patch.object(start_guardian_recovery, 'delay', side_effect=OSError('broker down')), \
                patch('auth_module.recovery_notice._fallback_pool') as pool:
            for email in ('nobody@example.com', 'active@example.com'):
                r = self._post(email)
                self.assertEqual((r.status_code, r.content),
                                 (baseline.status_code, baseline.content))
        self.assertEqual(pool.submit.call_count, 2)

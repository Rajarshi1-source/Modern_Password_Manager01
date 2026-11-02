"""
Guardian recovery after initiate: the owner confirms from the emailed link on
the requesting device, guardians are asked, a wait gives the owner time to
cancel, and only that device can fetch the re-sealed shares.

The whole path with real client crypto is in frontend/e2e/guardian_recovery.spec.js.
"""
import base64
import json
import re
import smtplib
from datetime import timedelta
from io import StringIO
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core import mail
from django.core.cache import cache
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from auth_module.quantum_recovery_models import (
    GuardianApproval,
    PasskeyRecoverySetup,
    RecoveryAttempt,
    RecoveryAuditLog,
    RecoveryGuardian,
)
from auth_module.recovery_models_v2 import VaultWrappedDEK
from auth_module.quantum_recovery_tasks import (
    request_guardian_approvals,
    send_guardian_approval_request,
    send_guardian_invitation,
)
from auth_module.tasks import start_guardian_recovery
from shared import sealed_shares
from shared.tests import sealed_share_fixtures as fx


def _run_now(task):
    """Run a queued task in the test, as a worker would."""
    return patch.object(task, 'delay', side_effect=lambda *a: task.apply(args=a))


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
                   FRONTEND_URL='https://app.example.com')
class GuardianFlowBase(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user('owner', 'owner@example.com', 'Owner-Pass-1!')
        self.anon = APIClient()
        owner = APIClient()
        owner.force_authenticate(self.user)
        self.proofs = []
        guardians = []
        for i in (1, 2, 3):
            proof, proof_hash = fx.share_proof()
            self.proofs.append(proof)
            guardians.append({
                'email': f'g{i}@example.com', 'requires_video': False,
                'public_key': fx.hybrid_public_key(), 'share_index': i,
                'sealed_share': fx.sealed_share(), 'share_proof_hash': proof_hash})
        self.owner = owner
        self.setup_body = {'threshold_shards': 2, 'guardians': guardians,
                           'recovery_factor': fx.recovery_factor(self.user),
                           'secret_check': fx.seed_check()}
        with patch.object(send_guardian_invitation, 'delay'):
            r = owner.post(reverse('quantum-recovery-setup'), self.setup_body, format='json')
        self.assertEqual(r.status_code, 201, r.content)
        for s, proof in zip(r.json()['shards_created'], self.proofs):
            self.anon.post(reverse('quantum-recovery-accept-invitation'), {
                'invitation_token': s['invitation_token'], 'share_proof': proof}, format='json')
        self.setup = PasskeyRecoverySetup.objects.get(user=self.user)
        self.assertTrue(self.setup.is_active)

    def _start(self):
        """A request from a device; returns the attempt and that device's token."""
        token, token_hash = fx.requester_token()
        key = fx.hybrid_public_key()
        with _run_now(start_guardian_recovery):
            r = self.anon.post(reverse('quantum-recovery-initiate'), {
                'email': 'owner@example.com', 'requester_public_key': key,
                'requester_token_hash': token_hash}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        attempt = self.setup.recovery_attempts.filter(
            requester_public_key=base64.b64decode(key)).first()
        return attempt, token

    def _confirm(self, attempt, token):
        cache.clear()
        with _run_now(request_guardian_approvals), \
                patch.object(send_guardian_approval_request, 'apply_async') as queued:
            r = self.anon.post(reverse('quantum-recovery-confirm'), {
                'attempt_id': str(attempt.id), 'requester_token': token}, format='json')
        self.queued = queued
        return r

    def _open_windows(self, attempt):
        attempt.guardian_approvals.update(
            approval_window_start=timezone.now() - timedelta(minutes=1),
            approval_window_end=timezone.now() + timedelta(hours=1))


class ConfirmTests(GuardianFlowBase):
    def test_a_request_alone_asks_no_guardian(self):
        attempt, _ = self._start()
        self.assertEqual(attempt.status, 'initiated')
        self.assertFalse(GuardianApproval.objects.exists())
        self.assertEqual([m.to for m in mail.outbox], [['owner@example.com']])

    def test_the_link_names_the_attempt_and_the_key_for_this_browser(self):
        attempt, _ = self._start()
        fingerprint = sealed_shares.key_fingerprint(bytes(attempt.requester_public_key))
        self.assertIn(
            f'https://app.example.com/recovery/guardian-attempt?attempt={attempt.id}&key={fingerprint}',
            mail.outbox[0].body)

    def test_the_token_is_not_stored_or_emailed(self):
        attempt, token = self._start()
        self.assertNotEqual(bytes(attempt.requester_token_hash), base64.b64decode(token))
        self.assertNotIn(token, mail.outbox[0].body)

    def test_confirming_asks_every_active_guardian_at_its_window(self):
        attempt, token = self._start()
        r = self._confirm(attempt, token)
        self.assertEqual(r.status_code, 200, r.content)
        attempt.refresh_from_db()
        self.assertEqual(attempt.status, 'guardian_approval')
        approvals = attempt.guardian_approvals.all()
        self.assertEqual(approvals.count(), 3)
        self.assertEqual(self.queued.call_count, 3)
        for call in self.queued.call_args_list:
            approval = GuardianApproval.objects.get(id=call.kwargs['args'][0])
            self.assertEqual(call.kwargs['eta'], approval.approval_window_start)
        self.assertEqual(r.json()['guardians_asked'], 3)

    def test_confirming_twice_or_a_redelivered_job_keeps_the_same_approvals(self):
        attempt, token = self._start()
        self._confirm(attempt, token)
        tokens = set(attempt.guardian_approvals.values_list('approval_token', flat=True))
        self.assertEqual(self._confirm(attempt, token).status_code, 200)
        request_guardian_approvals.apply(args=[str(attempt.id)])
        self.assertEqual(set(attempt.guardian_approvals.values_list('approval_token', flat=True)), tokens)

    def test_only_the_requesting_device_can_confirm(self):
        attempt, _ = self._start()
        for body in ({'attempt_id': str(attempt.id)},
                     {'attempt_id': str(attempt.id), 'requester_token': fx.requester_token()[0]},
                     {'attempt_id': 'not-a-uuid', 'requester_token': fx.requester_token()[0]}):
            r = self.anon.post(reverse('quantum-recovery-confirm'), body, format='json')
            self.assertEqual(r.status_code, 404, r.content)
            self.assertEqual(r.json(), {'error': 'Recovery attempt not found'})
        self.assertFalse(GuardianApproval.objects.exists())

    def test_the_link_stops_starting_recovery_after_a_day(self):
        attempt, token = self._start()
        RecoveryAttempt.objects.filter(pk=attempt.pk).update(
            initiated_at=timezone.now() - timedelta(hours=25))
        self.assertEqual(self._confirm(attempt, token).status_code, 400)
        self.assertFalse(GuardianApproval.objects.exists())

    def test_a_cancelled_attempt_cannot_be_confirmed(self):
        attempt, token = self._start()
        RecoveryAttempt.objects.filter(pk=attempt.pk).update(status='cancelled')
        self.assertEqual(self._confirm(attempt, token).json()['status'], 'cancelled')
        self.assertFalse(GuardianApproval.objects.exists())

    def test_a_lost_job_can_be_queued_again_by_confirming(self):
        attempt, token = self._start()
        with patch.object(request_guardian_approvals, 'delay'):
            self.anon.post(reverse('quantum-recovery-confirm'), {
                'attempt_id': str(attempt.id), 'requester_token': token}, format='json')
        self.assertFalse(GuardianApproval.objects.exists())
        self._confirm(attempt, token)
        self.assertEqual(attempt.guardian_approvals.count(), 3)


class MonthlyLimitTests(GuardianFlowBase):
    """OWASP: a stranger must not be able to lock the owner out of recovery."""

    def _strangers_use_up_the_day(self):
        for _ in range(self.setup.max_recovery_attempts_per_month):
            cache.clear()
            self._start()
        mail.outbox.clear()

    def test_unconfirmed_attempts_limit_emails_for_a_day_only(self):
        self._strangers_use_up_the_day()
        cache.clear()
        attempt, _ = self._start()
        self.assertIsNone(attempt)  # no flood of emails
        self.assertEqual(mail.outbox, [])

        # Nobody used the cancel links, and 25 hours later the owner gets through.
        self.setup.recovery_attempts.update(initiated_at=timezone.now() - timedelta(hours=25))
        cache.clear()
        attempt, token = self._start()
        self.assertIsNotNone(attempt)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(self._confirm(attempt, token).status_code, 200)

    def test_strangers_attempts_do_not_stop_the_owner_confirming(self):
        cache.clear()
        attempt, token = self._start()
        for _ in range(self.setup.max_recovery_attempts_per_month - 1):
            cache.clear()
            self._start()
        self.assertEqual(self._confirm(attempt, token).status_code, 200)

    def test_confirmed_attempts_are_what_the_month_counts(self):
        limit = self.setup.max_recovery_attempts_per_month
        for _ in range(limit):
            cache.clear()
            attempt, token = self._start()
            self.assertEqual(self._confirm(attempt, token).status_code, 200)
        cache.clear()
        attempt, _ = self._start()
        self.assertIsNone(attempt)
        # Thirty days on, they no longer count.
        self.setup.recovery_attempts.update(initiated_at=timezone.now() - timedelta(days=31))
        cache.clear()
        attempt, _ = self._start()
        self.assertIsNotNone(attempt)

    def test_a_limit_used_up_while_a_link_waits_stops_its_confirm(self):
        waiting, token = self._start()
        self.setup.max_recovery_attempts_per_month = 1
        self.setup.save()
        other, other_token = waiting, token
        cache.clear()
        RecoveryAttempt.objects.create(
            recovery_setup=self.setup, status='guardian_approval', initiated_from_ip='127.0.0.1',
            shards_required=2, guardian_approvals_required=3,
            expires_at=timezone.now() + timedelta(days=1))
        limited = self._confirm(other, other_token)
        self.assertEqual(limited.status_code, 429)
        self.assertNotIn('code', limited.json())
        self.assertFalse(other.guardian_approvals.exists())


class ProgressAndReleaseTests(GuardianFlowBase):
    def _approved(self, count=2):
        attempt, token = self._start()
        self._confirm(attempt, token)
        self._open_windows(attempt)
        for approval in attempt.guardian_approvals.all()[:count]:
            r = self.anon.post(reverse('quantum-recovery-approve'), {
                'approval_token': approval.approval_token, 'approved': True,
                'resealed_share': fx.sealed_share()}, format='json')
            self.assertEqual(r.status_code, 200, r.content)
        return attempt, token

    def _progress(self, attempt, token):
        return self.anon.post(reverse('quantum-recovery-progress'), {
            'attempt_id': str(attempt.id), 'requester_token': token}, format='json')

    def _complete(self, attempt, token):
        cache.clear()
        return self.anon.post(reverse('quantum-recovery-complete'), {
            'attempt_id': str(attempt.id), 'requester_token': token}, format='json')

    @override_settings(RECOVERY_THROTTLE_RATE='3/hour')
    def test_repeated_confirms_leave_the_tries_for_complete(self):
        attempt, token = self._approved()
        cache.clear()
        confirm = lambda: self.anon.post(reverse('quantum-recovery-confirm'), {
            'attempt_id': str(attempt.id), 'requester_token': token}, format='json')
        self.assertEqual([confirm().status_code for _ in range(3)], [200, 200, 200])
        limited = confirm()
        self.assertEqual((limited.status_code, limited.json()['code']), (429, 'throttled'))
        r = self.anon.post(reverse('quantum-recovery-complete'), {
            'attempt_id': str(attempt.id), 'requester_token': token}, format='json')
        self.assertEqual(r.status_code, 400, r.content)

    def test_shares_wait_for_the_owners_window_even_with_enough_approvals(self):
        attempt, token = self._approved()
        body = self._progress(attempt, token).json()
        self.assertEqual((body['approvals_received'], body['threshold'], body['ready']), (2, 2, False))
        r = self._complete(attempt, token)
        self.assertEqual(r.status_code, 400)
        self.assertNotIn('sealed_shares', r.json())
        attempt.refresh_from_db()
        self.assertEqual(attempt.status, 'guardian_approval')

    def test_after_the_wait_the_device_gets_its_shares_and_no_session(self):
        attempt, token = self._approved()
        RecoveryAttempt.objects.filter(pk=attempt.pk).update(
            canary_alert_sent_at=timezone.now() - timedelta(hours=49))
        self.assertTrue(self._progress(attempt, token).json()['ready'])
        r = self._complete(attempt, token)
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(len(r.json()['sealed_shares']), 2)
        self.assertNotIn('access', r.json())
        self.assertNotIn('recovery_token', r.json())

    def test_a_low_trust_score_no_longer_matters(self):
        attempt, token = self._approved()
        RecoveryAttempt.objects.filter(pk=attempt.pk).update(
            trust_score=0.0, canary_alert_sent_at=timezone.now() - timedelta(hours=49))
        self.assertEqual(self._complete(attempt, token).status_code, 200)

    def test_the_attempt_id_alone_gets_nothing(self):
        attempt, _ = self._approved()
        RecoveryAttempt.objects.filter(pk=attempt.pk).update(
            canary_alert_sent_at=timezone.now() - timedelta(hours=49))
        for name in ('quantum-recovery-progress', 'quantum-recovery-complete'):
            cache.clear()
            for token in (None, 'x', fx.requester_token()[0]):
                r = self.anon.post(reverse(name), {'attempt_id': str(attempt.id),
                                                   'requester_token': token}, format='json')
                self.assertEqual(r.status_code, 404, r.content)
                self.assertEqual(r.json(), {'error': 'Recovery attempt not found'})
                cache.clear()

    def test_an_attempt_from_before_the_token_cannot_be_used(self):
        attempt, _ = self._approved()
        RecoveryAttempt.objects.filter(pk=attempt.pk).update(requester_token_hash=b'')
        self.assertEqual(self._complete(attempt, fx.requester_token()[0]).status_code, 404)

    def test_progress_shows_denials(self):
        attempt, token = self._start()
        self._confirm(attempt, token)
        self._open_windows(attempt)
        approval = attempt.guardian_approvals.first()
        self.anon.post(reverse('quantum-recovery-approve'), {
            'approval_token': approval.approval_token, 'approved': False}, format='json')
        self.assertEqual(self._progress(attempt, token).json()['denials'], 1)

    def test_a_recovery_past_its_time_shows_as_expired(self):
        attempt, token = self._approved()
        RecoveryAttempt.objects.filter(pk=attempt.pk).update(
            canary_alert_sent_at=timezone.now() - timedelta(hours=49),
            expires_at=timezone.now() - timedelta(minutes=1))
        body = self._progress(attempt, token).json()
        self.assertEqual((body['status'], body['ready'], body['ask_again']), ('expired', False, False))

    def test_a_finished_recovery_stays_finished_past_its_time(self):
        attempt, token = self._approved()
        RecoveryAttempt.objects.filter(pk=attempt.pk).update(
            status='completed', expires_at=timezone.now() - timedelta(minutes=1))
        self.assertEqual(self._progress(attempt, token).json()['status'], 'completed')


class GuardianWindowTests(GuardianFlowBase):
    def setUp(self):
        super().setUp()
        self.attempt, token = self._start()
        self._confirm(self.attempt, token)
        self._open_windows(self.attempt)
        self.approval = self.attempt.guardian_approvals.first()

    def _share(self):
        return self.anon.post(reverse('quantum-recovery-guardian-share'),
                              {'approval_token': self.approval.approval_token}, format='json')

    def _approve(self):
        return self.anon.post(reverse('quantum-recovery-approve'), {
            'approval_token': self.approval.approval_token, 'approved': True,
            'resealed_share': fx.sealed_share()}, format='json')

    def test_an_open_window_works(self):
        self.assertEqual(self._share().status_code, 200)
        self.assertEqual(self._approve().status_code, 200)

    def test_each_answer_is_audited_with_where_it_came_from(self):
        self.assertEqual(self._approve().status_code, 200)
        entry = RecoveryAuditLog.objects.get(event_type='guardian_approved',
                                             recovery_attempt_id=self.attempt.id)
        self.assertEqual(entry.event_data['approval_id'], str(self.approval.id))
        self.assertIsNotNone(entry.ip_address)
        self.approval.refresh_from_db()
        self.assertEqual(self.approval.response_ip, entry.ip_address)

        other = self.attempt.guardian_approvals.filter(status='pending').first()
        self.anon.post(reverse('quantum-recovery-approve'), {
            'approval_token': other.approval_token, 'approved': False}, format='json')
        self.assertTrue(RecoveryAuditLog.objects.filter(
            event_type='guardian_denied', recovery_attempt_id=self.attempt.id).exists())

    def test_before_its_window_a_guardian_gets_nothing(self):
        GuardianApproval.objects.filter(pk=self.approval.pk).update(
            approval_window_start=timezone.now() + timedelta(hours=1))
        for r in (self._share(), self._approve()):
            self.assertEqual(r.status_code, 400, r.content)
        self.approval.refresh_from_db()
        self.assertEqual(self.approval.status, 'pending')

    def test_after_its_window_a_guardian_gets_nothing(self):
        GuardianApproval.objects.filter(pk=self.approval.pk).update(
            approval_window_end=timezone.now() - timedelta(minutes=1))
        self.assertEqual(self._share().status_code, 400)
        self.approval.refresh_from_db()
        self.assertEqual(self.approval.status, 'expired')

    def test_a_cancelled_or_expired_recovery_takes_no_approval(self):
        for change in ({'status': 'cancelled'},
                       {'status': 'guardian_approval',
                        'expires_at': timezone.now() - timedelta(minutes=1)}):
            RecoveryAttempt.objects.filter(pk=self.attempt.pk).update(**change)
            for r in (self._share(), self._approve()):
                self.assertEqual(r.status_code, 400, r.content)
        self.approval.refresh_from_db()
        self.assertFalse(self.approval.shard_released)


class GuardianEmailTests(GuardianFlowBase):
    def setUp(self):
        super().setUp()
        self.attempt, token = self._start()
        self._confirm(self.attempt, token)
        self.approval = self.attempt.guardian_approvals.select_related('guardian').first()
        mail.outbox.clear()

    def test_the_guardian_gets_a_link_to_this_site(self):
        send_guardian_approval_request.apply(args=[str(self.approval.id)])
        self.assertEqual(len(mail.outbox), 1)
        message = mail.outbox[0]
        self.assertEqual(message.to, [self.approval.guardian.encrypted_guardian_info.decode()])
        self.assertIn(
            f'https://app.example.com/recovery/guardian-approve#{self.approval.approval_token}',
            message.body)
        self.assertIn('owner', message.body)

    def test_a_repeated_delivery_sends_one_email(self):
        for _ in range(2):
            send_guardian_approval_request.apply(args=[str(self.approval.id)])
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(RecoveryAuditLog.objects.filter(
            event_type='guardian_approval_requested').count(), 1)

    def test_no_email_once_the_recovery_is_cancelled(self):
        RecoveryAttempt.objects.filter(pk=self.attempt.pk).update(status='cancelled')
        send_guardian_approval_request.apply(args=[str(self.approval.id)])
        self.assertEqual(mail.outbox, [])

    def test_a_mail_failure_is_retried_without_an_audit_entry(self):
        with patch('auth_module.quantum_recovery_tasks.send_mail', side_effect=OSError('smtp')), \
                patch.object(send_guardian_approval_request, 'retry',
                             side_effect=RuntimeError('retry')) as retry:
            send_guardian_approval_request.apply(args=[str(self.approval.id)])
        retry.assert_called_once()
        self.assertFalse(RecoveryAuditLog.objects.filter(
            event_type='guardian_approval_requested').exists())

    def _both_tasks_retry(self, error):
        """Whether each guardian email task retries when sending raises error."""
        guardian = self.approval.guardian
        RecoveryGuardian.objects.filter(pk=guardian.pk).update(
            status='pending', invitation_expires_at=timezone.now() + timedelta(days=1))
        retried = []
        for task, target in ((send_guardian_approval_request, self.approval.id),
                             (send_guardian_invitation, guardian.id)):
            with patch('auth_module.quantum_recovery_tasks.send_mail', side_effect=error), \
                    patch.object(task, 'retry', side_effect=RuntimeError('retry')) as retry:
                result = task.apply(args=[str(target)])
            self.assertEqual(result.state, 'FAILURE')
            retried.append(retry.called)
        return retried

    def test_a_temporary_mail_failure_is_retried(self):
        for error in (TimeoutError('slow'),
                      smtplib.SMTPServerDisconnected('gone'),
                      smtplib.SMTPDataError(451, b'busy'),
                      smtplib.SMTPRecipientsRefused({'g@example.com': (450, b'greylisted')})):
            with self.subTest(error=error):
                self.assertEqual(self._both_tasks_retry(error), [True, True])

    def test_a_refused_address_or_a_bug_is_not_retried(self):
        for error in (smtplib.SMTPRecipientsRefused({'g@example.com': (550, b'no such user')}),
                      smtplib.SMTPDataError(554, b'rejected'),
                      ValueError('bad header'),
                      TypeError('bug')):
            with self.subTest(error=error):
                self.assertEqual(self._both_tasks_retry(error), [False, False])
        self.assertFalse(RecoveryAuditLog.objects.filter(
            event_type='guardian_approval_requested').exists())

    def test_no_email_after_the_guardians_window_closed(self):
        GuardianApproval.objects.filter(pk=self.approval.pk).update(
            approval_window_end=timezone.now() - timedelta(minutes=1))
        send_guardian_approval_request.apply(args=[str(self.approval.id)])
        self.assertEqual(mail.outbox, [])
        self.assertFalse(RecoveryAuditLog.objects.filter(
            event_type='guardian_approval_requested').exists())


class LostDeliveryTests(GuardianFlowBase):
    def _progress(self, attempt, token):
        return self.anon.post(reverse('quantum-recovery-progress'), {
            'attempt_id': str(attempt.id), 'requester_token': token}, format='json').json()

    def test_an_approval_email_that_never_queued_can_be_asked_for_again(self):
        attempt, token = self._start()
        self._confirm(attempt, token)  # its publishes go nowhere
        # A window that has not opened is not late yet.
        attempt.guardian_approvals.update(
            approval_window_start=timezone.now() + timedelta(hours=1),
            approval_window_end=timezone.now() + timedelta(hours=25))
        self.assertFalse(self._progress(attempt, token)['ask_again'])
        self._open_windows(attempt)
        self.assertTrue(self._progress(attempt, token)['ask_again'])

        self._confirm(attempt, token)
        self.assertEqual(self.queued.call_count, 3)
        mail.outbox.clear()
        for approval in attempt.guardian_approvals.all():
            send_guardian_approval_request.apply(args=[str(approval.id)])
        self.assertEqual(len(mail.outbox), 3)
        self.assertFalse(self._progress(attempt, token)['ask_again'])

        # Everyone has been asked, so another confirm queues nothing.
        self._confirm(attempt, token)
        self.queued.assert_not_called()

    def _redeliver(self, attempt, token_hash):
        return start_guardian_recovery.apply(args=(
            'owner@example.com', sealed_shares.b64(bytes(attempt.requester_public_key)),
            '', '127.0.0.1', '', token_hash)).get()

    def _confirmed_with_a_lost_alert(self):
        attempt, token = self._start()
        self._confirm(attempt, token)
        RecoveryAttempt.objects.filter(pk=attempt.pk).update(canary_alert_sent_at=None)
        mail.outbox.clear()
        return attempt, token

    def test_a_redelivered_task_sends_the_alert_a_confirmed_attempt_lost(self):
        attempt, token = self._confirmed_with_a_lost_alert()
        self.assertIsNone(self._progress(attempt, token)['release_after'])
        self.assertEqual(self._redeliver(attempt, fx.requester_token()[1]), 1)
        self.assertEqual([m.to for m in mail.outbox], [['owner@example.com']])
        self.assertIsNotNone(self._progress(attempt, token)['release_after'])

    def test_a_resend_that_fails_does_not_fail_a_confirmed_attempt(self):
        attempt, _ = self._confirmed_with_a_lost_alert()
        with patch('django.core.mail.send_mail', return_value=0):
            self._redeliver(attempt, fx.requester_token()[1])
        attempt.refresh_from_db()
        self.assertEqual(attempt.status, 'guardian_approval')
        self.assertIsNone(attempt.canary_alert_sent_at)

    def test_a_redelivered_task_does_not_alert_for_a_closed_attempt(self):
        attempt, _ = self._confirmed_with_a_lost_alert()
        for change in ({'status': 'cancelled'},
                       {'status': 'guardian_approval',
                        'expires_at': timezone.now() - timedelta(minutes=1)}):
            RecoveryAttempt.objects.filter(pk=attempt.pk).update(**change)
            self._redeliver(attempt, fx.requester_token()[1])
        self.assertEqual(mail.outbox, [])


class InvitationTests(GuardianFlowBase):
    def _second_owner(self):
        user = User.objects.create_user('owner2', 'owner2@example.com', 'Owner-Pass-1!')
        client = APIClient()
        client.force_authenticate(user)
        self.setup_body = {**self.setup_body, 'recovery_factor': fx.recovery_factor(user)}
        return user, client

    def test_setup_emails_each_guardian_its_invitation(self):
        _, client = self._second_owner()
        mail.outbox.clear()
        with _run_now(send_guardian_invitation), self.captureOnCommitCallbacks(execute=True):
            r = client.post(reverse('quantum-recovery-setup'), self.setup_body, format='json')
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual({m.to[0] for m in mail.outbox},
                         {'g1@example.com', 'g2@example.com', 'g3@example.com'})
        for s in r.json()['shards_created']:
            message = next(m for m in mail.outbox if m.to == [s['guardian_email']])
            self.assertIn(f"/recovery/guardian-invite#{s['invitation_token']}", message.body)

    def test_a_setup_with_a_lapsed_invitation_can_be_replaced(self):
        user, client = self._second_owner()
        with patch.object(send_guardian_invitation, 'delay'):
            self.assertEqual(client.post(reverse('quantum-recovery-setup'), self.setup_body,
                                         format='json').status_code, 201)
            # Invitations still open: the setup stays.
            self.assertEqual(client.post(reverse('quantum-recovery-setup'), self.setup_body,
                                         format='json').status_code, 400)
            first = PasskeyRecoverySetup.objects.get(user=user)
            RecoveryGuardian.objects.filter(recovery_setup=first).update(
                invitation_expires_at=timezone.now() - timedelta(minutes=1))
            user = User.objects.get(pk=user.pk)
            client.force_authenticate(user)
            r = client.post(reverse('quantum-recovery-setup'), self.setup_body, format='json')
        self.assertEqual(r.status_code, 201, r.content)
        self.assertNotEqual(PasskeyRecoverySetup.objects.get(user=user).pk, first.pk)

    def test_an_active_setup_is_not_replaced(self):
        self.assertEqual(self.owner.post(reverse('quantum-recovery-setup'), self.setup_body,
                                         format='json').status_code, 400)


class FingerprintTests(TestCase):
    def test_it_matches_the_client(self):
        # The same vector is in frontend/.../sealedShareRecovery.test.js.
        self.assertEqual(sealed_shares.key_fingerprint(bytes(range(32))),
                         '94CC-6B14-F58E-8B99-A0CC')


class WorkerRegistrationTests(TestCase):
    def test_a_worker_loads_the_guardian_tasks(self):
        from password_manager.celery import app
        app.loader.import_default_modules()
        for name in ('request_guardian_approvals', 'send_guardian_approval_request',
                     'send_guardian_invitation'):
            self.assertIn(f'auth_module.quantum_recovery_tasks.{name}', app.tasks)


class StaleTokenTests(GuardianFlowBase):
    """A browser may still send an old token, on steps that need no sign-in."""

    def _post(self, name, body=None):
        cache.clear()
        return self.anon.post(reverse(name), body or {}, format='json').status_code

    def test_a_stale_bearer_token_does_not_stop_the_anonymous_steps(self):
        self.anon.credentials(HTTP_AUTHORIZATION='Bearer stale')
        attempt, token = self._start()  # asserts its own 200
        self.assertEqual(self._confirm(attempt, token).status_code, 200)
        requester = {'attempt_id': str(attempt.id), 'requester_token': token}
        self.assertEqual(self._post('quantum-recovery-progress', requester), 200)
        self.assertEqual(self._post('quantum-recovery-complete', requester), 400)  # still waiting
        for name in ('quantum-recovery-approve', 'quantum-recovery-guardian-share',
                     'quantum-recovery-guardian-invitation',
                     'quantum-recovery-accept-invitation'):
            self.assertEqual(self._post(name), 400, name)
        self.assertEqual(self._post('vault-recovery-factor-lookup'), 400)
        self.assertEqual(self._post('vault-wrapped-dek-recover-rotate'), 400)

    def test_a_stale_bearer_token_still_fails_where_sign_in_is_needed(self):
        self.anon.credentials(HTTP_AUTHORIZATION='Bearer stale')
        self.assertEqual(self._post('quantum-recovery-setup'), 401)
        self.assertEqual(self.anon.get(reverse('quantum-recovery-get-status')).status_code, 401)


class RotationNeedsAFinishedRecoveryTests(GuardianFlowBase):
    """Guardians who pool the shares they opened when accepting know the seed,
    so the seed alone must not set a new master password."""

    _approved = ProgressAndReleaseTests._approved
    _complete = ProgressAndReleaseTests._complete

    def _rotate(self, **extra):
        cache.clear()
        factor = self.setup_body['recovery_factor']
        return self.anon.post(reverse('vault-wrapped-dek-recover-rotate'), {
            'username': 'owner', 'factor_type': 'social_mesh', 'dek_id': factor['dek_id'],
            'blob': dict(factor['blob'], wrapped=fx.b64(b'n' * 48)),
            'auth_hash': extra.pop('auth_hash', factor['auth_hash']),
            'login_verifier': fx.b64(b'v' * 32), 'new_auth_hash': fx.b64(b'm' * 32),
            **extra}, format='json')

    def _finished(self):
        attempt, token = self._approved()
        RecoveryAttempt.objects.filter(pk=attempt.pk).update(
            canary_alert_sent_at=timezone.now() - timedelta(hours=49))
        self.assertEqual(self._complete(attempt, token).status_code, 200)
        return {'attempt_id': str(attempt.id), 'requester_token': token}

    def _assert_vault_key_unchanged(self):
        self.assertEqual(VaultWrappedDEK.objects.get(user=self.user).blob,
                         self.setup_body['recovery_factor']['blob'])

    def test_the_seed_alone_does_not_rotate(self):
        self.assertEqual(self._rotate().status_code, 403)
        self._assert_vault_key_unchanged()

    def test_a_wrong_secret_learns_nothing_about_the_attempt_check(self):
        self.assertEqual(self._rotate(auth_hash='b' * 64).status_code, 404)

    def test_a_recovery_still_in_its_wait_does_not_rotate(self):
        attempt, token = self._approved()
        r = self._rotate(attempt_id=str(attempt.id), requester_token=token)
        self.assertEqual(r.status_code, 403)
        self._assert_vault_key_unchanged()

    def test_a_finished_recovery_needs_its_own_token(self):
        proof = self._finished()
        for bad in ({**proof, 'requester_token': fx.requester_token()[0]},
                    {**proof, 'attempt_id': 'not-a-uuid'},
                    {'attempt_id': proof['attempt_id']}):
            self.assertEqual(self._rotate(**bad).status_code, 403, bad)
        self._assert_vault_key_unchanged()

    def test_a_finished_recovery_sets_one_new_password(self):
        proof = self._finished()
        self.assertEqual(self._rotate(**proof).status_code, 200)
        self.assertNotEqual(VaultWrappedDEK.objects.get(user=self.user).blob,
                            self.setup_body['recovery_factor']['blob'])
        self.assertEqual(self._rotate(**proof).status_code, 403)

    def test_an_expired_recovery_does_not_rotate(self):
        proof = self._finished()
        RecoveryAttempt.objects.filter(pk=proof['attempt_id']).update(
            expires_at=timezone.now() - timedelta(minutes=1))
        self.assertEqual(self._rotate(**proof).status_code, 403)


class E2EHelperTests(GuardianFlowBase):
    def test_ending_the_wait_needs_an_alert_on_record(self):
        attempt, _ = self._start()
        RecoveryAttempt.objects.filter(pk=attempt.pk).update(canary_alert_sent_at=None)
        with self.assertRaises(CommandError):
            call_command('guardian_recovery_e2e', 'owner', '--end-wait', stdout=StringIO())
        attempt.refresh_from_db()
        self.assertIsNone(attempt.canary_alert_sent_at)

    def test_ending_the_wait_moves_the_alert_back(self):
        attempt, _ = self._start()
        out = StringIO()
        call_command('guardian_recovery_e2e', 'owner', '--end-wait', stdout=out)
        self.assertTrue(json.loads(out.getvalue())['alert_sent'])
        attempt.refresh_from_db()
        self.assertLess(attempt.canary_alert_sent_at, timezone.now() - timedelta(
            hours=self.setup.canary_alert_window_hours))

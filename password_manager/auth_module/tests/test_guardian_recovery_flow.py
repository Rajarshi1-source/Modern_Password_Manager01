"""
Guardian recovery after initiate: the owner confirms from the emailed link on
the requesting device, guardians are asked, a wait gives the owner time to
cancel, and only that device can fetch the re-sealed shares.

The whole path with real client crypto is in frontend/e2e/guardian_recovery.spec.js.
"""
import base64
import re
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core import mail
from django.core.cache import cache
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
        self.assertEqual(self._confirm(other, other_token).status_code, 429)
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
            f'https://app.example.com/recovery/guardian-approve/{self.approval.approval_token}',
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


class InvitationTests(GuardianFlowBase):
    def _second_owner(self):
        user = User.objects.create_user('owner2', 'owner2@example.com', 'Owner-Pass-1!')
        client = APIClient()
        client.force_authenticate(user)
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
            self.assertIn(f"/recovery/guardian-invite/{s['invitation_token']}", message.body)

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

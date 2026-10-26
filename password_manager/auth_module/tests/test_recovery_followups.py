"""
Follow-ups to the anonymous recovery hardening.

- verify-email-exists is retired: it answered whether an email has an account.
- Behavioral initiate answers every email the same way; an enrolled account
  gets its attempt link by email, never in the response.
- Passkey-primary initiate writes nothing on any path, and a recovery key
  completes recovery once (single use).
- The email password-reset link works once and its request is answered the
  same way for every email.
- Global KEM metrics are staff only.
"""
import base64
import os
import re
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core import mail
from django.db import connection
from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from rest_framework.test import APIClient

from auth_module.models import UserPasskey, UserSalt

# A login verifier: base64 of 32 bytes (auth_module/login_verifier.py)
VERIFIER = base64.b64encode(b'v' * 32).decode()


@override_settings(
    QUANTUM_CRYPTO={'ALLOW_SIMULATION': True, 'ENABLED': True},
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
    FRONTEND_URL='https://app.example.com',
)
class RecoveryFollowupTests(TestCase):
    def setUp(self):
        from auth_module.tasks import send_password_reset_email
        from behavioral_recovery.tasks import start_behavioral_recovery
        self.owner = User.objects.create_user('owner', 'owner@example.com', 'Owner-Pass-1!')
        UserSalt.objects.create(user=self.owner, salt=os.urandom(16), auth_hash=b'original-hash')
        self.anon = APIClient()
        # Run the account-dependent tasks in-process, as a worker would
        for task in (send_password_reset_email, start_behavioral_recovery):
            patcher = patch.object(task, 'delay', side_effect=lambda *a, _t=task: _t.apply(args=a))
            patcher.start()
            self.addCleanup(patcher.stop)

    # --- account existence ---------------------------------------------------

    def test_verify_email_exists_is_retired(self):
        for email in ('owner@example.com', 'nobody@example.com'):
            r = self.anon.post(reverse('verify-email-exists'), {'email': email}, format='json')
            self.assertEqual(r.status_code, 410, r.content)
            self.assertNotIn('exists', r.json())

    def test_behavioral_initiate_answers_every_email_the_same_way(self):
        from behavioral_recovery.models import BehavioralCommitment, BehavioralRecoveryAttempt
        enrolled = User.objects.create_user('enrolled', 'enrolled@example.com', 'Enrolled-Pass-1!')
        BehavioralCommitment.objects.create(
            user=enrolled, encrypted_embedding=b'x', challenge_type='typing')
        # The first challenge is typing: a mouse-only account could not pass it
        mouse_only = User.objects.create_user('mouse', 'mouse@example.com', 'Mouse-Pass-1!')
        BehavioralCommitment.objects.create(
            user=mouse_only, encrypted_embedding=b'x', challenge_type='mouse')
        url = '/api/behavioral-recovery/initiate/'
        answers = [self.anon.post(url, {'email': e}, format='json')
                   for e in ('nobody@example.com', 'owner@example.com',
                             'mouse@example.com', 'enrolled@example.com')]
        for r in answers:
            self.assertEqual(r.status_code, 200, r.content)
            self.assertEqual(r.json(), answers[0].json())
            self.assertNotIn('attempt_id', r.json())
        # Only the enrolled account gets a link, by email, to its own attempt
        attempt = BehavioralRecoveryAttempt.objects.get(user=enrolled)
        links = [m for m in mail.outbox if 'behavioral_attempt=' in m.body]
        self.assertEqual([m.to for m in links], [['enrolled@example.com']])
        # The link opens the frontend origin, and states the attempt's deadline
        self.assertIn(
            f'https://app.example.com/password-recovery?behavioral_attempt={attempt.attempt_id}',
            links[0].body)
        days = attempt.metadata['recovery_config']['days']
        self.assertIn(f'over the next {days} days', links[0].body)

    def _queries(self, url, email):
        with CaptureQueriesContext(connection) as queries:
            self.anon.post(url, {'email': email}, format='json')
        return len(queries)

    def test_initiate_and_reset_do_the_same_work_for_every_email(self):
        # The account-dependent work runs in a task; with the task not run,
        # the request itself is the same for known and unknown emails.
        from auth_module.tasks import send_password_reset_email
        from behavioral_recovery.models import BehavioralCommitment
        from behavioral_recovery.tasks import start_behavioral_recovery
        BehavioralCommitment.objects.create(
            user=self.owner, encrypted_embedding=b'x', challenge_type='typing')
        with patch.object(send_password_reset_email, 'delay') as reset,                 patch.object(start_behavioral_recovery, 'delay') as behavioral:
            for url in ('/api/auth/request_password_reset/', '/api/behavioral-recovery/initiate/'):
                self.assertEqual(self._queries(url, 'owner@example.com'),
                                 self._queries(url, 'nobody@example.com'), url)
        self.assertEqual(reset.call_count, 2)
        self.assertEqual(behavioral.call_count, 2)

    def test_behavioral_challenge_errors_are_logged_not_crashed(self):
        # The audit log field is `details`; writing `event_data` raised a
        # TypeError that replaced the real error.
        from behavioral_recovery.models import (
            BehavioralChallenge, BehavioralRecoveryAttempt, RecoveryAuditLog)
        from behavioral_recovery.services import RecoveryOrchestrator
        attempt = BehavioralRecoveryAttempt.objects.create(user=self.owner)
        challenge = BehavioralChallenge.objects.create(
            recovery_attempt=attempt, challenge_type='typing', challenge_data={})
        with self.assertRaises(ValueError):  # no behavioral commitment
            RecoveryOrchestrator().evaluate_challenge(challenge, {'keys': []})
        log = RecoveryAuditLog.objects.get(recovery_attempt=attempt)
        self.assertIn('error', log.details)

    # --- passkey-primary recovery --------------------------------------------

    def _backup(self):
        UserPasskey.objects.create(
            user=self.owner, credential_id=b'cred-1', public_key=b'pk-bytes', rp_id='localhost')
        authed = APIClient()
        authed.force_authenticate(self.owner)
        r = authed.post(reverse('setup_primary_passkey_recovery'),
                        {'passkey_credential_id': b'cred-1'.hex()}, format='json')
        self.assertEqual(r.status_code, 201, r.content)
        return r.json()['recovery_key']

    def _initiate(self, who):
        r = self.anon.post(reverse('initiate_primary_passkey_recovery'),
                           {'username_or_email': who}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        return r.json()['recovery_attempt_id']

    def _complete(self, token, key):
        return self.anon.post(reverse('complete_primary_passkey_recovery'), {
            'recovery_attempt_id': token, 'recovery_key': key,
        }, format='json')

    def test_passkey_initiate_writes_nothing_on_any_path(self):
        from auth_module.passkey_primary_recovery_models import PasskeyRecoveryAttempt
        self._backup()
        for who in ('nobody@example.com', 'owner'):
            self._initiate(who)
        self.assertFalse(PasskeyRecoveryAttempt.objects.exists())

    def test_passkey_recovery_key_is_single_use(self):
        key = self._backup()
        self.assertEqual(self._complete(self._initiate('owner'), key).status_code, 200)
        # The same key, with a fresh attempt, no longer completes recovery
        self.assertEqual(self._complete(self._initiate('owner'), key).status_code, 401)

    def test_passkey_attempt_token_cannot_complete_twice(self):
        key = self._backup()
        token = self._initiate('owner')
        self.assertEqual(self._complete(token, key).status_code, 200)
        self.assertEqual(self._complete(token, key).status_code, 401)

    # --- email password reset -------------------------------------------------

    def test_password_reset_request_answers_every_email_the_same_way(self):
        url = '/api/auth/request_password_reset/'
        known = self.anon.post(url, {'email': 'owner@example.com'}, format='json')
        unknown = self.anon.post(url, {'email': 'nobody@example.com'}, format='json')
        self.assertEqual(known.status_code, unknown.status_code)
        self.assertEqual(known.json(), unknown.json())

    def test_password_reset_link_works_once(self):
        self.anon.post('/api/auth/request_password_reset/', {'email': 'owner@example.com'}, format='json')
        # The outbox also holds the account's security-alert email
        links = [re.search(r'/reset-password/([^/]+)/([^/]+)/', m.body) for m in mail.outbox]
        uid, token = next(link for link in links if link).groups()
        self.assertIn('https://app.example.com/reset-password/', mail.outbox[-1].body)
        new_hash = base64.b64encode(b'new-hash').decode()
        first = self.anon.post('/api/auth/reset_password/', {
            'uid': uid, 'token': token, 'new_login_verifier': VERIFIER, 'username': 'owner', 'new_auth_hash': new_hash}, format='json')
        self.assertEqual(first.status_code, 200, first.content)
        again = self.anon.post('/api/auth/reset_password/', {
            'uid': uid, 'token': token, 'new_login_verifier': VERIFIER, 'username': 'owner',
            'new_auth_hash': base64.b64encode(b'other-hash').decode()}, format='json')
        self.assertEqual(again.status_code, 400, again.content)
        self.assertEqual(bytes(UserSalt.objects.get(user=self.owner).auth_hash), b'new-hash')

    def _reset_link(self):
        self.anon.post('/api/auth/request_password_reset/', {'email': 'owner@example.com'}, format='json')
        links = [re.search(r'/reset-password/([^/]+)/([^/]+)/', m.body) for m in mail.outbox]
        return next(link for link in links if link).groups()

    def test_password_reset_link_works_once_even_with_the_same_hash(self):
        uid, token = self._reset_link()
        same = base64.b64encode(b'original-hash').decode()
        first = self.anon.post('/api/auth/reset_password/', {
            'uid': uid, 'token': token, 'new_login_verifier': VERIFIER, 'username': 'owner', 'new_auth_hash': same}, format='json')
        self.assertEqual(first.status_code, 200, first.content)
        again = self.anon.post('/api/auth/reset_password/', {
            'uid': uid, 'token': token, 'new_login_verifier': VERIFIER, 'username': 'owner',
            'new_auth_hash': base64.b64encode(b'other-hash').decode()}, format='json')
        self.assertEqual(again.status_code, 400, again.content)
        self.assertEqual(bytes(UserSalt.objects.get(user=self.owner).auth_hash), b'original-hash')

    def test_master_password_change_voids_an_unused_reset_link(self):
        uid, token = self._reset_link()
        authed = APIClient()
        authed.force_authenticate(self.owner)
        changed = authed.post('/api/auth/change_master/', {
            'current_auth_hash': base64.b64encode(b'original-hash').decode(),
            'new_auth_hash': base64.b64encode(b'changed-hash').decode(),
            'new_login_verifier': VERIFIER}, format='json')
        self.assertEqual(changed.status_code, 200, changed.content)
        r = self.anon.post('/api/auth/reset_password/', {
            'uid': uid, 'token': token, 'new_login_verifier': VERIFIER, 'username': 'owner',
            'new_auth_hash': base64.b64encode(b'attacker-hash').decode()}, format='json')
        self.assertEqual(r.status_code, 400, r.content)
        self.assertEqual(bytes(UserSalt.objects.get(user=self.owner).auth_hash), b'changed-hash')

    def test_undelivered_reset_email_is_audited_as_a_failure(self):
        from vault.models import AuditLog
        with patch('django.core.mail.send_mail', return_value=0):
            self.anon.post('/api/auth/request_password_reset/', {'email': 'owner@example.com'}, format='json')
        log = AuditLog.objects.get(user=self.owner, action='password_reset_req')
        self.assertEqual(log.status, 'failure')

    def test_passkey_backup_is_consumed_once_under_concurrency(self):
        # A concurrent completion consumes the backup after this one checked
        # the key: this one must not also start a registration.
        from auth_module.passkey_primary_recovery_models import PasskeyRecoveryBackup
        key = self._backup()
        real_verify = PasskeyRecoveryBackup.verify_recovery_key

        def verify_while_another_request_wins(backup, recovery_key):
            matched = real_verify(backup, recovery_key)
            PasskeyRecoveryBackup.objects.filter(user=self.owner).update(is_active=False)
            return matched

        with patch.object(PasskeyRecoveryBackup, 'verify_recovery_key',
                          verify_while_another_request_wins):
            r = self._complete(self._initiate('owner'), key)
        self.assertEqual(r.status_code, 401, r.content)
        self.assertNotIn('registration_options', r.json())

    # --- KEM metrics ----------------------------------------------------------

    def test_kem_metrics_are_staff_only(self):
        user = APIClient()
        user.force_authenticate(self.owner)
        self.assertEqual(user.get(reverse('kyber_metrics')).status_code, 403)
        self.assertEqual(user.post(reverse('kyber_reset_metrics')).status_code, 403)
        staff = User.objects.create_user('staff', 'staff@example.com', 'Staff-Pass-1!', is_staff=True)
        admin = APIClient()
        admin.force_authenticate(staff)
        self.assertEqual(admin.get(reverse('kyber_metrics')).status_code, 200)

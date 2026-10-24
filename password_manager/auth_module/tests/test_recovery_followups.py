"""
Follow-ups to the anonymous recovery hardening.

- verify-email-exists is retired: it answered whether an email has an account.
- Behavioral initiate answers every email the same way; an enrolled account
  gets its attempt link by email, never in the response.
- Passkey-primary initiate writes nothing on any path, and a recovery key
  completes recovery once (single use).
- The email password-reset link works once and its request is answered the
  same way for every email.
"""
import base64
import os
import re

from django.contrib.auth.models import User
from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework.test import APIClient

from auth_module.models import UserPasskey, UserSalt


@override_settings(
    QUANTUM_CRYPTO={'ALLOW_SIMULATION': True, 'ENABLED': True},
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
)
class RecoveryFollowupTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user('owner', 'owner@example.com', 'Owner-Pass-1!')
        UserSalt.objects.create(user=self.owner, salt=os.urandom(16), auth_hash=b'original-hash')
        self.anon = APIClient()

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
        url = '/api/behavioral-recovery/initiate/'
        answers = [self.anon.post(url, {'email': e}, format='json')
                   for e in ('nobody@example.com', 'owner@example.com', 'enrolled@example.com')]
        for r in answers:
            self.assertEqual(r.status_code, 200, r.content)
            self.assertEqual(r.json(), answers[0].json())
            self.assertNotIn('attempt_id', r.json())
        # Only the enrolled account gets a link, by email, to its own attempt
        attempt = BehavioralRecoveryAttempt.objects.get(user=enrolled)
        links = [m for m in mail.outbox if 'behavioral_attempt=' in m.body]
        self.assertEqual([m.to for m in links], [['enrolled@example.com']])
        self.assertIn(f'behavioral_attempt={attempt.attempt_id}', links[0].body)

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
        new_hash = base64.b64encode(b'new-hash').decode()
        first = self.anon.post('/api/auth/reset_password/', {
            'uid': uid, 'token': token, 'new_auth_hash': new_hash}, format='json')
        self.assertEqual(first.status_code, 200, first.content)
        again = self.anon.post('/api/auth/reset_password/', {
            'uid': uid, 'token': token,
            'new_auth_hash': base64.b64encode(b'other-hash').decode()}, format='json')
        self.assertEqual(again.status_code, 400, again.content)
        self.assertEqual(bytes(UserSalt.objects.get(user=self.owner).auth_hash), b'new-hash')

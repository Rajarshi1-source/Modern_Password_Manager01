"""
Phase 1 leftovers of the zero-knowledge recovery plan.

- UserSalt.auth_hash (the client's PBKDF2 output) was stored as sent: a
  database leak allowed offline master-password guessing at PBKDF2 cost. It is
  now stored as an Argon2id password-hasher record (auth_module/auth_hash.py).
- The vault's verify_auth cached the hash of what a client sent, so a wrong
  auth_hash passed on its second try.
- Every recovery and reset sends an email and in-app notice with a cancel
  window (auth_module/recovery_notice.py).
"""
import base64
import os
import re
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core import mail
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from auth_module.auth_hash import check_auth_hash, is_hashed_record, make_auth_hash_record
from auth_module.models import RecoveryNotice, UserSalt
from auth_module.tasks import (
    notify_passkey_recovery_started,
    send_password_reset_email,
    send_recovery_notice,
)

VERIFIER = base64.b64encode(b'v' * 32).decode()
NEW_VERIFIER = base64.b64encode(b'n' * 32).decode()
RAW = b'r' * 32


def _b64(raw):
    return base64.b64encode(raw).decode()


def _run_tasks_in_process(test):
    for task in (send_password_reset_email, send_recovery_notice, notify_passkey_recovery_started):
        patcher = patch.object(task, 'delay', side_effect=lambda *a, _t=task: _t.apply(args=a))
        patcher.start()
        test.addCleanup(patcher.stop)


class AuthHashStorageTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('owner', 'owner@example.com', VERIFIER)
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def test_registration_stores_a_record_not_the_value(self):
        anon = APIClient()
        r = anon.post('/api/auth/register/', {
            'username': 'fresh', 'email': 'fresh@example.com', 'password': VERIFIER,
            'password_confirm': VERIFIER, 'login_verifier': 'lv1',
            'auth_hash': _b64(RAW)}, format='json')
        self.assertIn(r.status_code, (200, 201), r.content)
        stored = UserSalt.objects.get(user__username='fresh').auth_hash
        self.assertNotIn(RAW, bytes(stored))
        self.assertTrue(is_hashed_record(stored))
        self.assertTrue(bytes(stored).startswith(b'argon2$'))
        self.assertTrue(check_auth_hash(stored, RAW))
        self.assertFalse(check_auth_hash(stored, b'x' * 32))

    def test_change_master_checks_and_stores_records(self):
        UserSalt.objects.create(user=self.user, salt=os.urandom(16),
                                auth_hash=make_auth_hash_record(RAW))
        wrong = self.client.post('/api/auth/change_master/', {
            'current_auth_hash': _b64(b'w' * 32), 'new_auth_hash': _b64(b'n' * 32),
            'new_login_verifier': NEW_VERIFIER}, format='json')
        self.assertEqual(wrong.status_code, 400, wrong.content)
        r = self.client.post('/api/auth/change_master/', {
            'current_auth_hash': _b64(RAW), 'new_auth_hash': _b64(b'n' * 32),
            'new_login_verifier': NEW_VERIFIER}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        stored = UserSalt.objects.get(user=self.user).auth_hash
        self.assertTrue(is_hashed_record(stored))
        self.assertTrue(check_auth_hash(stored, b'n' * 32))

    def test_verify_master_upgrades_a_raw_row(self):
        UserSalt.objects.create(user=self.user, salt=os.urandom(16), auth_hash=RAW)
        r = self.client.post('/api/auth/verify_master/', {'auth_hash': _b64(b'w' * 32)}, format='json')
        self.assertFalse(r.json().get('data', r.json()).get('is_valid'), r.content)
        self.assertEqual(bytes(UserSalt.objects.get(user=self.user).auth_hash), RAW)
        r = self.client.post('/api/auth/verify_master/', {'auth_hash': _b64(RAW)}, format='json')
        self.assertTrue(r.json().get('data', r.json()).get('is_valid'), r.content)
        stored = UserSalt.objects.get(user=self.user).auth_hash
        self.assertTrue(is_hashed_record(stored))
        self.assertTrue(check_auth_hash(stored, RAW))

    def test_the_migration_hashes_every_raw_row(self):
        from importlib import import_module
        from django.apps import apps
        from vault.models import UserSalt as VaultSalt
        UserSalt.objects.create(user=self.user, salt=os.urandom(16), auth_hash=RAW)
        VaultSalt.objects.create(user=self.user, salt=os.urandom(16), auth_hash=RAW)
        other = User.objects.create_user('other', 'other@example.com', VERIFIER)
        UserSalt.objects.create(user=other, salt=os.urandom(16), auth_hash=b'')
        import_module('auth_module.migrations.0021_hash_auth_hash').hash_rows(apps, None)
        import_module('vault.migrations.0016_hash_auth_hash').hash_rows(apps, None)
        for stored in (UserSalt.objects.get(user=self.user).auth_hash,
                       VaultSalt.objects.get(user=self.user).auth_hash):
            self.assertTrue(is_hashed_record(stored))
            self.assertTrue(check_auth_hash(stored, RAW))
        self.assertEqual(bytes(UserSalt.objects.get(user=other).auth_hash), b'')


class VaultVerifyAuthTests(TestCase):
    URL = '/api/vault/items/verify_auth/'

    def setUp(self):
        from vault.models import UserSalt as VaultSalt
        self.user = User.objects.create_user('owner', 'owner@example.com', VERIFIER)
        record = make_auth_hash_record(RAW)
        UserSalt.objects.create(user=self.user, salt=os.urandom(16), auth_hash=record)
        VaultSalt.objects.create(user=self.user, salt=os.urandom(16), auth_hash=record)
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def test_a_wrong_hash_never_passes_even_when_repeated(self):
        for _ in range(3):
            r = self.client.post(self.URL, {'auth_hash': _b64(b'w' * 32)}, format='json')
            self.assertEqual(r.status_code, 401, r.content)

    def test_the_right_hash_passes(self):
        r = self.client.post(self.URL, {'auth_hash': _b64(RAW)}, format='json')
        self.assertEqual(r.status_code, 200, r.content)

    def test_it_follows_a_master_password_change(self):
        # The vault copy is not updated by change_master; the check uses the
        # authoritative record.
        salt = UserSalt.objects.get(user=self.user)
        salt.auth_hash = make_auth_hash_record(b'n' * 32)
        salt.save()
        self.assertEqual(self.client.post(self.URL, {'auth_hash': _b64(RAW)}, format='json').status_code, 401)
        self.assertEqual(self.client.post(self.URL, {'auth_hash': _b64(b'n' * 32)}, format='json').status_code, 200)


@override_settings(
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
    FRONTEND_URL='https://app.example.com',
)
class RecoveryNoticeTests(TestCase):
    def setUp(self):
        cache.clear()  # throttle counters
        _run_tasks_in_process(self)
        self.user = User.objects.create_user('owner', 'owner@example.com', VERIFIER)
        UserSalt.objects.create(user=self.user, salt=os.urandom(16),
                                auth_hash=make_auth_hash_record(RAW))
        self.anon = APIClient()

    def _cancel_token(self, message):
        return re.search(r'/recovery/cancel\?notice=([A-Za-z0-9_\-]+)', message.body).group(1)

    def _reset_link(self):
        mail.outbox.clear()
        self.anon.post('/api/auth/request_password_reset/', {'email': 'owner@example.com'}, format='json')
        message = mail.outbox[-1]
        uid, token = re.search(r'/reset-password/([^/]+)/([^/]+)/', message.body).groups()
        return uid, token, self._cancel_token(message)

    def _reset(self, uid, token):
        return self.anon.post('/api/auth/reset_password/', {
            'uid': uid, 'token': token, 'username': 'owner',
            'new_auth_hash': _b64(b'n' * 32), 'new_login_verifier': NEW_VERIFIER}, format='json')

    def _cancel(self, token):
        return self.anon.post('/api/auth/recovery-notices/cancel/', {'token': token}, format='json')

    def test_a_reset_request_can_be_cancelled_from_its_email(self):
        uid, token, cancel = self._reset_link()
        notice = RecoveryNotice.objects.get(user=self.user)
        self.assertEqual(notice.event, 'reset_requested')
        self.assertTrue(notice.email_sent)
        self.assertNotEqual(notice.cancel_token_hash, cancel)  # only a hash is stored
        self.assertEqual(self._cancel(cancel).status_code, 200)
        self.assertEqual(self._reset(uid, token).status_code, 400)
        self.user.refresh_from_db()
        self.assertTrue(self.user.is_active)

    def test_a_completed_reset_is_notified_and_its_cancel_locks_the_account(self):
        uid, token, _ = self._reset_link()
        with self.captureOnCommitCallbacks(execute=True):
            self.assertEqual(self._reset(uid, token).status_code, 200)
        notice = RecoveryNotice.objects.get(user=self.user, event='reset_completed')
        message = mail.outbox[-1]
        self.assertIn('Security notice', message.subject)
        self.assertEqual(self._cancel(self._cancel_token(message)).status_code, 200)
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_active)
        notice.refresh_from_db()
        self.assertIsNotNone(notice.cancelled_at)
        r = self.anon.post('/api/auth/token/', {'username': 'owner', 'password': NEW_VERIFIER},
                           format='json')
        self.assertEqual(r.status_code, 401, r.content)

    def test_a_cancel_link_works_once_and_only_in_its_window(self):
        uid, token, _ = self._reset_link()
        with self.captureOnCommitCallbacks(execute=True):
            self._reset(uid, token)
        cancel = self._cancel_token(mail.outbox[-1])
        RecoveryNotice.objects.filter(event='reset_completed').update(
            cancel_until=timezone.now() - timedelta(minutes=1))
        self.assertEqual(self._cancel(cancel).status_code, 200)
        self.user.refresh_from_db()
        self.assertTrue(self.user.is_active)

    def test_invalid_tokens_get_the_same_answer(self):
        _, _, cancel = self._reset_link()
        # Three calls: the endpoint allows three an hour per client.
        answers = [self._cancel(t).json() for t in (cancel, 'x' * 43, None)]
        self.assertTrue(all(a == answers[0] for a in answers))

    def test_the_owner_sees_notices_in_the_app(self):
        self._reset_link()
        other = User.objects.create_user('other', 'other@example.com', VERIFIER)
        authed = APIClient()
        authed.force_authenticate(self.user)
        notices = authed.get('/api/auth/recovery-notices/').json()['notices']
        self.assertEqual([n['event'] for n in notices], ['reset_requested'])
        self.assertNotIn('cancel_token_hash', notices[0])
        authed.force_authenticate(other)
        self.assertEqual(authed.get('/api/auth/recovery-notices/').json()['notices'], [])

    def test_passkey_recovery_start_notifies_only_accounts_with_a_backup(self):
        from auth_module.passkey_primary_recovery_models import PasskeyRecoveryBackup
        url = '/api/auth/passkey-recovery/initiate/'
        for who in ('owner', 'nobody'):
            self.anon.post(url, {'username_or_email': who}, format='json')
        self.assertFalse(RecoveryNotice.objects.exists())
        PasskeyRecoveryBackup.objects.create(
            user=self.user, passkey_credential_id=b'cred', encrypted_credential_data=b'x',
            recovery_key_hash='0' * 64, kyber_public_key=b'k', encryption_metadata={},
            device_name='Phone', is_active=True)
        with patch.object(notify_passkey_recovery_started, 'delay',
                          wraps=notify_passkey_recovery_started.delay) as queued:
            self.anon.post(url, {'username_or_email': 'nobody'}, format='json')
            self.anon.post(url, {'username_or_email': 'owner'}, format='json')
        self.assertEqual(queued.call_count, 2)  # the same work for every account
        self.assertEqual(list(RecoveryNotice.objects.values_list('event', flat=True)),
                         ['passkey_recovery_started'])

    def test_cancelling_a_started_guardian_recovery_cancels_the_attempt(self):
        from auth_module.quantum_recovery_models import PasskeyRecoverySetup, RecoveryAttempt
        PasskeyRecoverySetup.objects.create(user=self.user, total_shards=3, threshold_shards=2,
                                            is_active=True)
        with self.captureOnCommitCallbacks(execute=True):
            r = self.anon.post('/api/auth/quantum-recovery/initiate_recovery/',
                               {'email': 'owner@example.com'}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        RecoveryNotice.objects.get(user=self.user, event='guardian_recovery_started')
        self.assertEqual(self._cancel(self._cancel_token(mail.outbox[-1])).status_code, 200)
        self.assertEqual(RecoveryAttempt.objects.get().status, 'cancelled')
        self.user.refresh_from_db()
        self.assertTrue(self.user.is_active)


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class CompletionNoticeTests(TestCase):
    def setUp(self):
        cache.clear()
        _run_tasks_in_process(self)

    def test_vault_recovery_is_notified(self):
        import uuid
        from auth_module.recovery_models_v2 import RecoveryWrappedDEK, VaultWrappedDEK
        from auth_module.tests.test_login_verifier import AUTH_HASH, BLOB, NEW_BLOB
        user = User.objects.create_user('owner@example.com', 'owner@example.com', VERIFIER)
        UserSalt.objects.create(user=user, salt=os.urandom(16), auth_hash=make_auth_hash_record(RAW))
        dek_id = uuid.uuid4()
        VaultWrappedDEK.objects.create(user=user, blob=BLOB, dek_id=dek_id)
        RecoveryWrappedDEK.objects.create(user=user, factor_type='recovery_key', dek_id=dek_id,
                                          blob=BLOB, auth_hash=AUTH_HASH)
        with self.captureOnCommitCallbacks(execute=True):
            r = APIClient().post('/api/auth/vault/wrapped-dek/recover-rotate/', {
                'username': 'owner@example.com', 'factor_type': 'recovery_key',
                'dek_id': str(dek_id), 'blob': NEW_BLOB, 'auth_hash': AUTH_HASH,
                'login_verifier': NEW_VERIFIER, 'new_auth_hash': _b64(b'n' * 32)}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        RecoveryNotice.objects.get(user=user, event='recovery_completed')
        self.assertEqual(mail.outbox[-1].to, ['owner@example.com'])
        stored = UserSalt.objects.get(user=user).auth_hash
        self.assertTrue(is_hashed_record(stored))
        self.assertTrue(check_auth_hash(stored, b'n' * 32))

    def test_social_recovery_start_is_notified_and_cancellable(self):
        from social_recovery.models import RecoveryCircle, SocialRecoveryRequest
        from social_recovery.services import initiate_request
        from auth_module.recovery_notice import cancel_from_notice
        owner = User.objects.create_user('circle-owner', 'circle@example.com', VERIFIER)
        circle = RecoveryCircle.objects.create(user=owner, threshold=2, total_vouchers=2,
                                               secret_commitment=b'c', status='active')
        with self.captureOnCommitCallbacks(execute=True):
            request = initiate_request(circle=circle)
        RecoveryNotice.objects.get(user=owner, event='social_recovery_started')
        token = re.search(r'notice=([A-Za-z0-9_\-]+)', mail.outbox[-1].body).group(1)
        self.assertTrue(cancel_from_notice(token))
        self.assertEqual(SocialRecoveryRequest.objects.get(pk=request.pk).status, 'cancelled')
        self.assertFalse(cancel_from_notice(token))  # once

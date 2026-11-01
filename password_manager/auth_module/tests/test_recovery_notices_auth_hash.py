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
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from auth_module.auth_hash import check_auth_hash, is_hashed_record, make_auth_hash_record
from auth_module.models import RecoveryNotice, UserSalt
from shared.tests import sealed_share_fixtures as fx
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

    def test_the_migration_does_not_overwrite_a_concurrent_change(self):
        from importlib import import_module
        from django.db import models
        UserSalt.objects.create(user=self.user, salt=os.urandom(16), auth_hash=RAW)
        changed = make_auth_hash_record(b'n' * 32)
        real_iterator = models.QuerySet.iterator

        def change_after_read(queryset, *args, **kwargs):
            rows = list(real_iterator(queryset, *args, **kwargs))
            UserSalt.objects.filter(user=self.user).update(auth_hash=changed)
            return iter(rows)

        with patch.object(models.QuerySet, 'iterator', change_after_read):
            import_module('auth_module.migrations.0022_hash_auth_hash').hash_model_rows(UserSalt)
        self.assertEqual(bytes(UserSalt.objects.get(user=self.user).auth_hash), changed)

    def test_the_migration_hashes_every_raw_row(self):
        from importlib import import_module
        from django.apps import apps
        from vault.models import UserSalt as VaultSalt
        UserSalt.objects.create(user=self.user, salt=os.urandom(16), auth_hash=RAW)
        VaultSalt.objects.create(user=self.user, salt=os.urandom(16), auth_hash=RAW)
        other = User.objects.create_user('other', 'other@example.com', VERIFIER)
        UserSalt.objects.create(user=other, salt=os.urandom(16), auth_hash=b'')
        import_module('auth_module.migrations.0022_hash_auth_hash').hash_rows(apps, None)
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

    def test_a_stale_token_or_a_shared_ip_does_not_stop_a_cancel(self):
        uid, token, cancel = self._reset_link()
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION='Bearer expired-or-revoked')
        for _ in range(5):  # others behind the same address
            r = client.post('/api/auth/recovery-notices/cancel/', {'token': 'x' * 43}, format='json')
            self.assertEqual(r.status_code, 200, r.content)
        r = client.post('/api/auth/recovery-notices/cancel/', {'token': cancel}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(self._reset(uid, token).status_code, 400)

    def test_a_stale_token_does_not_stop_a_time_lock_cancel(self):
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION='Bearer expired-or-revoked')
        r = client.post('/api/auth/vault/time-locked/canary-ack/', {'token': 'x' * 43}, format='json')
        self.assertEqual(r.status_code, 200, r.content)

    def test_a_locked_account_cannot_be_reset(self):
        uid, token, _ = self._reset_link()
        stored = bytes(UserSalt.objects.get(user=self.user).auth_hash)
        User.objects.filter(pk=self.user.pk).update(is_active=False)
        self.assertEqual(self._reset(uid, token).status_code, 400)
        self.assertEqual(bytes(UserSalt.objects.get(user=self.user).auth_hash), stored)
        mail.outbox.clear()
        self.anon.post('/api/auth/request_password_reset/', {'email': 'owner@example.com'}, format='json')
        self.assertEqual(mail.outbox, [])

    def test_a_locked_account_gets_a_decoy_passkey_token(self):
        from auth_module.passkey_primary_recovery_models import PasskeyRecoveryBackup
        from auth_module.passkey_primary_recovery_views import _token_payload
        PasskeyRecoveryBackup.objects.create(
            user=self.user, passkey_credential_id=b'cred', encrypted_credential_data=b'x',
            recovery_key_hash='0' * 64, kyber_public_key=b'k', encryption_metadata={},
            device_name='Phone', is_active=True)
        User.objects.filter(pk=self.user.pk).update(is_active=False)
        r = self.anon.post('/api/auth/passkey-recovery/initiate/',
                           {'username_or_email': 'owner'}, format='json')
        self.assertEqual(_token_payload(r.json()['recovery_attempt_id'])[0], 0)
        self.assertFalse(RecoveryNotice.objects.exists())

    def test_change_master_rejects_an_empty_new_auth_hash(self):
        authed = APIClient()
        authed.force_authenticate(self.user)
        r = authed.post('/api/auth/change_master/', {
            'current_auth_hash': _b64(RAW), 'new_auth_hash': '====',
            'new_login_verifier': NEW_VERIFIER}, format='json')
        self.assertEqual(r.status_code, 400, r.content)
        self.assertTrue(check_auth_hash(UserSalt.objects.get(user=self.user).auth_hash, RAW))

    def test_cancelling_a_started_guardian_recovery_cancels_the_attempt(self):
        from auth_module.quantum_recovery_models import PasskeyRecoverySetup, RecoveryAttempt
        PasskeyRecoverySetup.objects.create(user=self.user, total_shards=3, threshold_shards=2,
                                            is_active=True)
        with self.captureOnCommitCallbacks(execute=True):
            r = self.anon.post('/api/auth/quantum-recovery/initiate_recovery/',
                               {'email': 'owner@example.com',
                                'requester_public_key': fx.hybrid_public_key()}, format='json')
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
        User.objects.filter(pk=user.pk).update(is_active=False)
        locked = APIClient().post('/api/auth/vault/wrapped-dek/recover-rotate/', {
            'username': 'owner@example.com', 'factor_type': 'recovery_key',
            'dek_id': str(dek_id), 'blob': BLOB, 'auth_hash': AUTH_HASH,
            'login_verifier': VERIFIER, 'new_auth_hash': _b64(b'x' * 32)}, format='json')
        self.assertEqual(locked.status_code, 404, locked.content)
        stored = UserSalt.objects.get(user=user).auth_hash
        self.assertTrue(is_hashed_record(stored))
        self.assertTrue(check_auth_hash(stored, b'n' * 32))

    def test_social_recovery_start_is_notified_and_cancellable(self):
        from social_recovery.models import RecoveryCircle, SocialRecoveryRequest
        from social_recovery.services import initiate_request
        from auth_module.recovery_notice import cancel_from_notice
        owner = User.objects.create_user('circle-owner', 'circle@example.com', VERIFIER)
        circle = RecoveryCircle.objects.create(user=owner, threshold=2, total_vouchers=2,
                                               secret_check=base64.b64decode(fx.seed_check()),
                                               status='active')
        with self.captureOnCommitCallbacks(execute=True):
            request = initiate_request(circle=circle,
                                       requester_public_key=base64.b64decode(fx.hybrid_public_key()))
        RecoveryNotice.objects.get(user=owner, event='social_recovery_started')
        token = re.search(r'notice=([A-Za-z0-9_\-]+)', mail.outbox[-1].body).group(1)
        self.assertTrue(cancel_from_notice(token))
        self.assertEqual(SocialRecoveryRequest.objects.get(pk=request.pk).status, 'cancelled')
        self.assertFalse(cancel_from_notice(token))  # once


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class NoticeCancelRaceTests(TestCase):
    """Review fixes: a cancel must stop recoveries whose state is not stored
    yet or is in flight, and a broker outage must not break a recovery."""

    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user('owner', 'owner@example.com', VERIFIER)
        UserSalt.objects.create(user=self.user, salt=os.urandom(16),
                                auth_hash=make_auth_hash_record(RAW))
        self.anon = APIClient()

    def _passkey_backup(self):
        from auth_module.models import UserPasskey
        UserPasskey.objects.create(user=self.user, credential_id=b'cred-1',
                                   public_key=b'pk-bytes', rp_id='localhost')
        authed = APIClient()
        authed.force_authenticate(self.user)
        r = authed.post('/api/auth/passkey-recovery/setup/',
                        {'passkey_credential_id': b'cred-1'.hex()}, format='json')
        self.assertEqual(r.status_code, 201, r.content)
        return r.json()['recovery_key']

    def _passkey_token(self):
        r = self.anon.post('/api/auth/passkey-recovery/initiate/',
                           {'username_or_email': 'owner'}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        return r.json()['recovery_attempt_id']

    def _cancelled_notice(self, at):
        return RecoveryNotice.objects.create(
            user=self.user, event='passkey_recovery_started', cancel_until=at + timedelta(hours=1),
            cancel_token_hash=os.urandom(32).hex(), cancelled_at=at)

    def _complete(self, token, key):
        return self.anon.post('/api/auth/passkey-recovery/complete/', {
            'recovery_attempt_id': token, 'recovery_key': key}, format='json')

    def test_a_cancel_voids_a_passkey_token_issued_before_it(self):
        key = self._passkey_backup()
        token = self._passkey_token()
        # Cancelled after the token was issued; no attempt row exists yet.
        self._cancelled_notice(timezone.now() + timedelta(seconds=1))
        self.assertEqual(self._complete(token, key).status_code, 401)

    def test_a_token_issued_after_a_cancel_still_works(self):
        key = self._passkey_backup()
        self._cancelled_notice(timezone.now() - timedelta(seconds=5))
        r = self._complete(self._passkey_token(), key)
        self.assertEqual(r.status_code, 200, r.content)

    def test_a_cancel_after_the_first_check_stops_the_claim(self):
        from auth_module.passkey_primary_recovery_models import PasskeyRecoveryBackup
        key = self._passkey_backup()
        token = self._passkey_token()
        real_verify = PasskeyRecoveryBackup.verify_recovery_key

        def cancel_meanwhile(backup, value):
            self._cancelled_notice(timezone.now())
            return real_verify(backup, value)

        with patch.object(PasskeyRecoveryBackup, 'verify_recovery_key', cancel_meanwhile):
            self.assertEqual(self._complete(token, key).status_code, 401)
        self.assertTrue(PasskeyRecoveryBackup.objects.get(user=self.user).is_active)

    def test_a_cancel_ends_a_registration_grant(self):
        begin = '/api/auth/passkey-recovery/register/begin/'
        key = self._passkey_backup()
        self.assertEqual(self._complete(self._passkey_token(), key).status_code, 200)
        self.assertEqual(self.anon.post(begin, {}, format='json').status_code, 200)
        self._cancelled_notice(timezone.now())
        self.assertEqual(self.anon.post(begin, {}, format='json').status_code, 400)

    def test_guardian_completion_does_not_overwrite_a_cancel(self):
        from auth_module.quantum_recovery_models import (
            GuardianApproval, PasskeyRecoverySetup, RecoveryAttempt)
        # Threshold 0: no released shares are needed to reach the locked re-check.
        setup = PasskeyRecoverySetup.objects.create(user=self.user, total_shards=3,
                                                    threshold_shards=0, is_active=True,
                                                    secret_check=base64.b64decode(fx.seed_check()))
        attempt = RecoveryAttempt.objects.create(
            recovery_setup=setup, status='shard_collection', initiated_from_ip='127.0.0.1',
            shards_required=2, guardian_approvals_required=2, trust_score=0.95,
            requester_public_key=base64.b64decode(fx.hybrid_public_key()),
            expires_at=timezone.now() + timedelta(days=1))

        def cancel_in_flight(*args, **kwargs):
            # A cancel lands after the view read and checked the attempt.
            RecoveryAttempt.objects.filter(pk=attempt.pk).update(status='cancelled')
            return GuardianApproval.objects.none()

        authed = APIClient()
        authed.force_authenticate(self.user)
        with patch('auth_module.quantum_recovery_views.GuardianApproval.objects.filter',
                   side_effect=cancel_in_flight):
            r = authed.post('/api/auth/quantum-recovery/complete_recovery/',
                            {'attempt_id': str(attempt.pk)}, format='json')
        self.assertEqual(r.status_code, 400, r.content)
        self.assertEqual(RecoveryAttempt.objects.get(pk=attempt.pk).status, 'cancelled')

    def test_a_broker_outage_neither_breaks_a_recovery_nor_loses_the_notice(self):
        from auth_module.recovery_notice import notify
        with patch.object(send_recovery_notice, 'delay', side_effect=OSError('broker down')), \
                patch('auth_module.recovery_notice._fallback_pool') as pool, \
                self.captureOnCommitCallbacks(execute=True):
            notify(self.user, 'reset_completed')
        # Nothing account-dependent ran on the request thread: how long the
        # email takes would show who has an account or a recovery backup.
        pool.submit.assert_called_once()
        self.assertFalse(RecoveryNotice.objects.filter(user=self.user).exists())
        self.assertEqual(mail.outbox, [])
        with patch('auth_module.recovery_notice.connections.close_all'):
            run, *args = pool.submit.call_args.args
            run(*args)
        RecoveryNotice.objects.get(user=self.user, event='reset_completed')
        with patch.object(notify_passkey_recovery_started, 'delay',
                          side_effect=OSError('broker down')), \
                patch('auth_module.recovery_notice._fallback_pool'):
            self.assertEqual(self.anon.post('/api/auth/passkey-recovery/initiate/', {
                'username_or_email': 'owner'}, format='json').status_code, 200)


class ConcurrencyAndInputTests(TestCase):
    """Second review round: races with a cancel or a password change, and
    malformed input on the anonymous cancel endpoint."""

    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user('owner', 'owner@example.com', VERIFIER)
        self.anon = APIClient()

    def test_a_non_ascii_cancel_token_gets_the_generic_answer(self):
        r = self.anon.post('/api/auth/recovery-notices/cancel/', {'token': 'é' * 30}, format='json')
        self.assertEqual(r.status_code, 200, r.content)

    def test_upgrading_a_raw_row_does_not_undo_a_concurrent_change(self):
        from auth_module.auth_hash import verify_and_upgrade
        UserSalt.objects.create(user=self.user, salt=os.urandom(16), auth_hash=RAW)
        stale = UserSalt.objects.get(user=self.user)
        UserSalt.objects.filter(user=self.user).update(auth_hash=make_auth_hash_record(b'n' * 32))
        self.assertFalse(verify_and_upgrade(stale, RAW))
        stored = UserSalt.objects.get(user=self.user).auth_hash
        self.assertTrue(check_auth_hash(stored, b'n' * 32))
        self.assertFalse(check_auth_hash(stored, RAW))

    def test_social_completion_does_not_overwrite_a_cancel(self):
        from social_recovery.models import RecoveryCircle, SocialRecoveryRequest
        from social_recovery.services import complete_request
        circle = RecoveryCircle.objects.create(user=self.user, threshold=2, total_vouchers=2,
                                               secret_check=base64.b64decode(fx.seed_check()),
                                               status='active')
        request = SocialRecoveryRequest.objects.create(
            circle=circle, status='approved', required_approvals=2, challenge_nonce='n',
            expires_at=timezone.now() + timedelta(days=1))
        SocialRecoveryRequest.objects.filter(pk=request.pk).update(status='cancelled')
        # The stale object still says approved; the locked re-read sees the cancel.
        with self.assertRaisesRegex(ValueError, 'must be approved'):
            complete_request(request=request)
        self.assertEqual(SocialRecoveryRequest.objects.get(pk=request.pk).status, 'cancelled')

    def test_passkey_completion_does_not_overwrite_a_cancel(self):
        from auth_module.models import UserPasskey
        from auth_module.passkey_primary_recovery_models import (
            PasskeyRecoveryAttempt, PasskeyRecoveryBackup)
        UserPasskey.objects.create(user=self.user, credential_id=b'cred-1',
                                   public_key=b'pk-bytes', rp_id='localhost')
        authed = APIClient()
        authed.force_authenticate(self.user)
        key = authed.post('/api/auth/passkey-recovery/setup/', {
            'passkey_credential_id': b'cred-1'.hex()}, format='json').json()['recovery_key']
        token = self.anon.post('/api/auth/passkey-recovery/initiate/', {
            'username_or_email': 'owner'}, format='json').json()['recovery_attempt_id']
        real_verify = PasskeyRecoveryBackup.verify_recovery_key

        def cancel_meanwhile(backup, value):
            # The owner's cancel commits while the key is being checked.
            PasskeyRecoveryAttempt.objects.filter(user=self.user).update(status='failed')
            return real_verify(backup, value)

        with patch.object(PasskeyRecoveryBackup, 'verify_recovery_key', cancel_meanwhile):
            r = self.anon.post('/api/auth/passkey-recovery/complete/', {
                'recovery_attempt_id': token, 'recovery_key': key}, format='json')
        self.assertEqual(r.status_code, 401, r.content)
        self.assertTrue(PasskeyRecoveryBackup.objects.get(user=self.user).is_active)
        self.assertEqual(PasskeyRecoveryAttempt.objects.get(user=self.user).status, 'failed')


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class UnlockLockedAccountTests(TestCase):
    """manage.py unlock_recovery_locked_account: restores an account a cancel
    locked, but not to whoever caused the lock."""

    TOKEN = r'notice=([A-Za-z0-9_\-]+)'

    def setUp(self):
        cache.clear()
        _run_tasks_in_process(self)
        self.user = User.objects.create_user('owner', 'owner@example.com', VERIFIER)

    def _lock(self):
        from auth_module.recovery_notice import cancel_from_notice, create_notice
        link = create_notice(self.user, 'reset_completed').cancel_link
        self.assertTrue(cancel_from_notice(re.search(self.TOKEN, link).group(1)))
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_active)

    def _unlock(self):
        with self.captureOnCommitCallbacks(execute=True):
            call_command('unlock_recovery_locked_account', 'owner',
                         '--operator', 'agent-7', '--reason', 'ticket 42, identity checked')
        self.user.refresh_from_db()

    def test_unlock_restores_the_account_without_the_lockers_credentials(self):
        from auth_module.models import UserPasskey
        from auth_module.passkey_primary_recovery_models import PasskeyRecoveryBackup
        from auth_module.quantum_recovery_models import RecoveryAuditLog
        self._lock()
        UserPasskey.objects.create(user=self.user, credential_id=b'attacker',
                                   public_key=b'pk-bytes', rp_id='localhost')
        backup = PasskeyRecoveryBackup.objects.create(
            user=self.user, passkey_credential_id=b'attacker', encrypted_credential_data=b'x',
            recovery_key_hash='0' * 64, kyber_public_key=b'k', encryption_metadata={},
            device_name='Phone', is_active=True)
        self._unlock()
        self.assertTrue(self.user.is_active)
        self.assertFalse(self.user.has_usable_password())
        self.assertFalse(UserPasskey.objects.filter(user=self.user).exists())
        backup.refresh_from_db()
        self.assertFalse(backup.is_active)
        log = RecoveryAuditLog.objects.get(user=self.user, event_type='account_unlocked')
        self.assertEqual(log.event_data, {'operator': 'agent-7',
                                          'reason': 'ticket 42, identity checked'})

    def test_the_owner_is_told_and_can_lock_it_again(self):
        from auth_module.recovery_notice import cancel_from_notice
        self._lock()
        self._unlock()
        message = mail.outbox[-1]
        self.assertIn('Support unlocked your account', message.body)
        self.assertEqual(message.to, ['owner@example.com'])
        self.assertTrue(cancel_from_notice(re.search(self.TOKEN, message.body).group(1)))
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_active)

    def test_the_owner_sets_a_new_password_with_forgot_password(self):
        UserSalt.objects.create(user=self.user, salt=os.urandom(16),
                                auth_hash=make_auth_hash_record(RAW))
        self._lock()
        self._unlock()
        anon = APIClient()
        anon.post('/api/auth/request_password_reset/', {'email': 'owner@example.com'}, format='json')
        uid, token = re.search(r'/reset-password/([^/]+)/([^/]+)/', mail.outbox[-1].body).groups()
        r = anon.post('/api/auth/reset_password/', {
            'uid': uid, 'token': token, 'username': 'owner',
            'new_auth_hash': _b64(b'n' * 32), 'new_login_verifier': NEW_VERIFIER}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        self.user.refresh_from_db()
        self.assertTrue(self.user.has_usable_password())

    def test_older_links_cannot_lock_the_restored_account(self):
        from auth_module.recovery_notice import cancel_from_notice, create_notice
        older = re.search(self.TOKEN, create_notice(self.user, 'reset_completed').cancel_link).group(1)
        self._lock()
        self._unlock()
        self.assertFalse(cancel_from_notice(older))
        self.user.refresh_from_db()
        self.assertTrue(self.user.is_active)

    def test_a_later_disable_is_not_lifted(self):
        self._lock()
        self._unlock()
        self.user.is_active = False
        self.user.save(update_fields=['is_active'])
        with self.assertRaises(CommandError):
            self._unlock()
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_active)

    def test_cancelling_a_notice_on_a_disabled_account_does_not_open_it_to_unlock(self):
        from auth_module.recovery_notice import cancel_from_notice, create_notice
        link = create_notice(self.user, 'reset_completed').cancel_link
        self.user.is_active = False
        self.user.save(update_fields=['is_active'])
        self.assertTrue(cancel_from_notice(re.search(self.TOKEN, link).group(1)))
        with self.assertRaises(CommandError):
            self._unlock()
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_active)

    def test_an_account_disabled_for_another_reason_is_refused(self):
        self.user.is_active = False
        self.user.save(update_fields=['is_active'])
        with self.assertRaises(CommandError):
            self._unlock()
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_active)
        self.assertTrue(self.user.check_password(VERIFIER))

    def test_an_active_account_is_refused(self):
        with self.assertRaises(CommandError):
            self._unlock()
        self.assertTrue(User.objects.get(pk=self.user.pk).check_password(VERIFIER))


class TimeLockCanaryLinkTests(TestCase):
    @override_settings(FRONTEND_URL='https://vault.example.org/')
    def test_the_canary_email_links_to_the_frontend_cancel_route(self):
        from types import SimpleNamespace
        from auth_module.time_locked_view import _build_canary_email
        _, body = _build_canary_email(
            SimpleNamespace(username='owner'),
            SimpleNamespace(canary_ack_token='tok', release_after=timezone.now()),
        )
        self.assertIn('https://vault.example.org/recovery/time-lock/cancel?token=tok', body)

"""
Sign-in checks a login verifier derived in the browser, not the master
password (zero-knowledge plan, Phase 1).

- V1/F8: recover-rotate replaces the wrapped vault key AND the login
  verifier in one transaction behind the auth_hash proof, so the user can
  sign in with the new master password afterwards.
- Accounts still on their master password switch to the verifier at their
  next sign-in, once, after the old password is checked.
- E1: the email reset sets the login verifier, ends existing sessions, and
  says the vault is not recovered.
- P2: a passkey-primary recovery revokes the lost passkey and registers a
  new one instead of returning the lost passkey's public data.
"""
import base64
import os
import re
import uuid
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core import mail
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta
from rest_framework.test import APIClient

from auth_module.login_verifier import uses_login_verifier
from auth_module.models import UserPasskey, UserSalt
from auth_module.recovery_models_v2 import RecoveryWrappedDEK, VaultWrappedDEK

OLD_MASTER = 'Old-Master-Pass-1!'
# Shape of a verifier: base64 of 32 bytes. The server cannot tell how it
# was derived, so any 32 bytes stand in for Argon2id output here.
OLD_VERIFIER = base64.b64encode(b'o' * 32).decode()
NEW_VERIFIER = base64.b64encode(b'n' * 32).decode()
BLOB = {
    'v': 'wdek-1', 'kdf': 'argon2id', 'kdf_params': {'t': 3, 'm': 65536, 'p': 2},
    'salt': 'c2FsdA==', 'iv': 'aXY=', 'wrapped': 'd3JhcHBlZA==',
}
NEW_BLOB = dict(BLOB, wrapped='bmV3LXdyYXBwZWQ=')
AUTH_HASH = 'a' * 64
NEW_MASTER_HASH = base64.b64encode(b'm' * 32).decode()


def _sign_in(client, username, password, **extra):
    return client.post('/api/auth/token/', dict(username=username, password=password, **extra),
                       format='json')


class LegacyMigrationTests(TestCase):
    def setUp(self):
        # An account from before the verifier: its Django password is the
        # master password itself.
        self.user = User.objects.create_user('owner@example.com', 'owner@example.com', OLD_MASTER)
        self.anon = APIClient()

    def test_verifier_alone_does_not_sign_in_a_legacy_account(self):
        self.assertEqual(_sign_in(self.anon, 'owner@example.com', OLD_VERIFIER).status_code, 401)
        self.assertFalse(uses_login_verifier(self.user))

    def test_first_sign_in_switches_to_the_verifier(self):
        r = _sign_in(self.anon, 'owner@example.com', OLD_VERIFIER, legacy_password=OLD_MASTER)
        self.assertEqual(r.status_code, 200, r.content)
        self.user.refresh_from_db()
        self.assertTrue(uses_login_verifier(self.user))
        self.assertTrue(self.user.check_password(OLD_VERIFIER))
        self.assertFalse(self.user.check_password(OLD_MASTER))
        # From now on the verifier alone signs in, and the master password does not
        self.assertEqual(_sign_in(self.anon, 'owner@example.com', OLD_VERIFIER).status_code, 200)
        self.assertEqual(_sign_in(self.anon, 'owner@example.com', OLD_MASTER).status_code, 401)

    def test_a_wrong_legacy_password_changes_nothing(self):
        r = _sign_in(self.anon, 'owner@example.com', OLD_VERIFIER, legacy_password='wrong')
        self.assertEqual(r.status_code, 401)
        self.user.refresh_from_db()
        self.assertFalse(uses_login_verifier(self.user))
        self.assertTrue(self.user.check_password(OLD_MASTER))

    def test_legacy_password_is_ignored_once_switched(self):
        _sign_in(self.anon, 'owner@example.com', OLD_VERIFIER, legacy_password=OLD_MASTER)
        # Knowing the old master password no longer replaces the verifier
        r = _sign_in(self.anon, 'owner@example.com', NEW_VERIFIER, legacy_password=OLD_MASTER)
        self.assertEqual(r.status_code, 401)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(OLD_VERIFIER))

    def test_unknown_account_answers_like_a_wrong_password(self):
        unknown = _sign_in(self.anon, 'nobody@example.com', OLD_VERIFIER, legacy_password=OLD_MASTER)
        wrong = _sign_in(self.anon, 'owner@example.com', OLD_VERIFIER, legacy_password='wrong')
        self.assertEqual(unknown.status_code, wrong.status_code)
        self.assertEqual(unknown.json(), wrong.json())

    def test_the_cookie_sign_in_switches_too(self):
        r = self.anon.post('/api/auth/cookie/token/', {
            'username': 'owner@example.com', 'password': OLD_VERIFIER,
            'legacy_password': OLD_MASTER}, format='json', HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertTrue(uses_login_verifier(self.user))

    def test_the_viewset_login_switches_too(self):
        UserSalt.objects.create(user=self.user, salt=os.urandom(16), auth_hash=b'h')
        r = self.anon.post('/api/auth/login/', {
            'username': 'owner@example.com', 'password': OLD_VERIFIER,
            'legacy_password': OLD_MASTER}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertTrue(uses_login_verifier(self.user))


class RegistrationTests(TestCase):
    def test_registration_with_a_verifier_never_stores_the_master_password(self):
        r = APIClient().post('/api/auth/register/', {
            'username': 'new@example.com', 'email': 'new@example.com',
            'password': NEW_VERIFIER, 'password_confirm': NEW_VERIFIER,
            'login_verifier': 'lv1', 'auth_hash': base64.b64encode(b'h').decode(),
        }, format='json')
        self.assertEqual(r.status_code, 201, r.content)
        user = User.objects.get(username='new@example.com')
        self.assertTrue(uses_login_verifier(user))
        self.assertEqual(_sign_in(APIClient(), 'new@example.com', NEW_VERIFIER).status_code, 200)

    def test_registration_rejects_a_non_verifier_marked_as_one(self):
        r = APIClient().post('/api/auth/register/', {
            'username': 'new@example.com', 'email': 'new@example.com',
            'password': 'plain-master-password', 'password_confirm': 'plain-master-password',
            'login_verifier': 'lv1',
        }, format='json')
        self.assertEqual(r.status_code, 400)
        self.assertFalse(User.objects.filter(username='new@example.com').exists())


class RecoverRotateTests(TestCase):
    URL = '/api/auth/vault/wrapped-dek/recover-rotate/'

    def setUp(self):
        self.user = User.objects.create_user('owner@example.com', 'owner@example.com', OLD_VERIFIER)
        UserSalt.objects.create(user=self.user, salt=os.urandom(16), auth_hash=b'old-hash')
        self.dek_id = uuid.uuid4()
        VaultWrappedDEK.objects.create(user=self.user, blob=BLOB, dek_id=self.dek_id)
        RecoveryWrappedDEK.objects.create(
            user=self.user, factor_type='recovery_key', dek_id=self.dek_id,
            blob=BLOB, auth_hash=AUTH_HASH)
        self.anon = APIClient()

    def _rotate(self, **overrides):
        body = {
            'username': 'owner@example.com', 'factor_type': 'recovery_key',
            'dek_id': str(self.dek_id), 'blob': NEW_BLOB, 'auth_hash': AUTH_HASH,
            'login_verifier': NEW_VERIFIER, 'new_auth_hash': NEW_MASTER_HASH,
        }
        body.update(overrides)
        body = {k: v for k, v in body.items() if v is not None}
        return self.anon.post(self.URL, body, format='json')

    def test_the_new_master_password_signs_in_after_recovery(self):
        r = self._rotate()
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(VaultWrappedDEK.objects.get(user=self.user).blob, NEW_BLOB)
        self.assertEqual(_sign_in(self.anon, 'owner@example.com', NEW_VERIFIER).status_code, 200)
        self.assertEqual(_sign_in(self.anon, 'owner@example.com', OLD_VERIFIER).status_code, 401)

    def test_rotation_without_a_login_verifier_is_refused(self):
        # Rotating only the envelope is what locked users out
        r = self._rotate(login_verifier=None)
        self.assertEqual(r.status_code, 400)
        self.assertEqual(VaultWrappedDEK.objects.get(user=self.user).blob, BLOB)
        self.assertEqual(self._rotate(login_verifier='not-a-verifier').status_code, 400)

    def test_a_wrong_auth_hash_changes_neither(self):
        r = self._rotate(auth_hash='b' * 64)
        self.assertEqual(r.status_code, 404)
        self.assertEqual(VaultWrappedDEK.objects.get(user=self.user).blob, BLOB)
        self.assertEqual(_sign_in(self.anon, 'owner@example.com', OLD_VERIFIER).status_code, 200)

    def test_recovery_ends_existing_sessions(self):
        tokens = _sign_in(self.anon, 'owner@example.com', OLD_VERIFIER).json()
        authed = APIClient()
        authed.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")
        self.assertEqual(authed.get('/api/auth/vault/wrapped-dek/').status_code, 200)
        # iat has whole seconds; revoke a few seconds later than the sign-in
        later = timezone.now() + timedelta(seconds=5)
        with patch('auth_module.login_verifier.timezone.now', return_value=later):
            self.assertEqual(self._rotate().status_code, 200)
        r = self.anon.post('/api/auth/token/refresh/', {'refresh': tokens['refresh']}, format='json')
        self.assertEqual(r.status_code, 401)
        # The access token issued before the recovery stops working too
        self.assertEqual(authed.get('/api/auth/vault/wrapped-dek/').status_code, 401)

    def test_recovery_moves_the_master_password_check(self):
        self.assertEqual(self._rotate().status_code, 200)
        self.assertEqual(bytes(UserSalt.objects.get(user=self.user).auth_hash), b'm' * 32)
        self.assertEqual(self._rotate(new_auth_hash=None).status_code, 400)
        short = base64.b64encode(b'not-32-bytes').decode()
        self.assertEqual(self._rotate(new_auth_hash=short).status_code, 400)


@override_settings(
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
    FRONTEND_URL='https://app.example.com',
)
class EmailResetTests(TestCase):
    def setUp(self):
        from auth_module.tasks import send_password_reset_email
        self.user = User.objects.create_user('owner', 'owner@example.com', OLD_VERIFIER)
        UserSalt.objects.create(user=self.user, salt=os.urandom(16), auth_hash=b'original-hash')
        self.anon = APIClient()
        patcher = patch.object(send_password_reset_email, 'delay',
                               side_effect=lambda *a: send_password_reset_email.apply(args=a))
        patcher.start()
        self.addCleanup(patcher.stop)

    def _link(self):
        self.anon.post('/api/auth/request_password_reset/', {'email': 'owner@example.com'}, format='json')
        links = [re.search(r'/reset-password/([^/]+)/([^/]+)/', m.body) for m in mail.outbox]
        return next(link for link in links if link).groups()

    def _reset(self, uid, token, verifier=NEW_VERIFIER, username='owner'):
        body = {'uid': uid, 'token': token, 'username': username,
                'new_auth_hash': base64.b64encode(b'new-hash').decode()}
        if verifier is not None:
            body['new_login_verifier'] = verifier
        return self.anon.post('/api/auth/reset_password/', body, format='json')

    def test_the_reset_changes_what_sign_in_checks(self):
        r = self._reset(*self._link())
        self.assertEqual(r.status_code, 200, r.content)
        self.assertIs(r.json()['vault_recovered'], False)
        self.assertEqual(_sign_in(self.anon, 'owner', NEW_VERIFIER).status_code, 200)
        self.assertEqual(_sign_in(self.anon, 'owner', OLD_VERIFIER).status_code, 401)

    def test_the_reset_requires_a_login_verifier(self):
        uid, token = self._link()
        self.assertEqual(self._reset(uid, token, verifier=None).status_code, 400)
        self.assertEqual(self._reset(uid, token, verifier='plain').status_code, 400)
        self.assertEqual(bytes(UserSalt.objects.get(user=self.user).auth_hash), b'original-hash')

    def test_a_reset_for_another_username_is_refused_and_keeps_the_link(self):
        uid, token = self._link()
        self.assertEqual(self._reset(uid, token, username='someone-else').status_code, 400)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(OLD_VERIFIER))
        self.assertEqual(self._reset(uid, token, username=' Owner ').status_code, 200)

    def test_the_link_works_once(self):
        uid, token = self._link()
        self.assertEqual(self._reset(uid, token).status_code, 200)
        self.assertEqual(self._reset(uid, token, verifier=OLD_VERIFIER).status_code, 400)
        self.assertEqual(_sign_in(self.anon, 'owner', NEW_VERIFIER).status_code, 200)

    def test_the_reset_ends_existing_sessions(self):
        refresh = _sign_in(self.anon, 'owner', OLD_VERIFIER).json()['refresh']
        self.assertEqual(self._reset(*self._link()).status_code, 200)
        r = self.anon.post('/api/auth/token/refresh/', {'refresh': refresh}, format='json')
        self.assertEqual(r.status_code, 401)

    def test_the_link_expires_after_an_hour(self):
        from django.conf import settings
        self.assertEqual(settings.PASSWORD_RESET_TIMEOUT, 3600)

    def test_the_email_does_not_promise_vault_access(self):
        self._link()
        body = next(m.body for m in mail.outbox if '/reset-password/' in m.body)
        self.assertIn('signing in', body)
        self.assertIn('cannot decrypt your vault', body)


@override_settings(QUANTUM_CRYPTO={'ALLOW_SIMULATION': True, 'ENABLED': True})
class PasskeyRecoveryRegistrationTests(TestCase):
    def setUp(self):
        cache.clear()  # throttle counters
        self.owner = User.objects.create_user('owner', 'owner@example.com', OLD_VERIFIER)
        UserPasskey.objects.create(
            user=self.owner, credential_id=b'lost-cred', public_key=b'pk', rp_id='localhost')
        authed = APIClient()
        authed.force_authenticate(self.owner)
        r = authed.post(reverse('setup_primary_passkey_recovery'),
                        {'passkey_credential_id': b'lost-cred'.hex()}, format='json')
        self.assertEqual(r.status_code, 201, r.content)
        self.key = r.json()['recovery_key']
        self.anon = APIClient()

    def _recover(self):
        token = self.anon.post(reverse('initiate_primary_passkey_recovery'),
                               {'username_or_email': 'owner'}, format='json').json()['recovery_attempt_id']
        return self.anon.post(reverse('complete_primary_passkey_recovery'), {
            'recovery_attempt_id': token, 'recovery_key': self.key}, format='json')

    def _register(self, credential_id=b'new-cred'):
        auth_data = SimpleNamespace(
            credential_data=SimpleNamespace(credential_id=credential_id, public_key={1: 2, 3: -7}),
            counter=0,
        )
        with patch('auth_module.passkey_views.server.register_complete', return_value=auth_data):
            return self.anon.post(reverse('complete_recovery_passkey_registration'), {
                'id': 'x', 'rawId': 'x', 'type': 'public-key',
                'response': {'clientDataJSON': 'x', 'attestationObject': 'x'},
            }, format='json')

    def test_recovery_revokes_the_lost_passkey_and_starts_a_registration(self):
        r = self._recover()
        self.assertEqual(r.status_code, 200, r.content)
        body = r.json()
        self.assertNotIn('passkey_credential', body)
        self.assertIn('challenge', body['registration_options'])
        self.assertEqual(body['registration_options']['authenticatorSelection']['userVerification'],
                         'required')
        self.assertFalse(UserPasskey.objects.filter(credential_id=b'lost-cred').exists())

    def test_the_new_passkey_is_registered_once(self):
        self._recover()
        r = self._register()
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(
            list(UserPasskey.objects.filter(user=self.owner).values_list('credential_id', flat=True)),
            [b'new-cred'])
        # The grant is spent: no second passkey from the same recovery
        self.assertEqual(self.anon.post(reverse('begin_recovery_passkey_registration')).status_code, 400)
        self.assertEqual(self._register(b'other-cred').status_code, 400)

    def test_a_cancelled_ceremony_can_be_started_again(self):
        self._recover()
        again = self.anon.post(reverse('begin_recovery_passkey_registration'))
        self.assertEqual(again.status_code, 200, again.content)
        self.assertEqual(self._register().status_code, 201)

    def test_a_failed_registration_start_keeps_the_key_and_the_passkey(self):
        from auth_module.passkey_primary_recovery_models import PasskeyRecoveryBackup
        with patch('auth_module.passkey_views.server.register_begin', side_effect=RuntimeError):
            self.assertEqual(self._recover().status_code, 500)
        self.assertTrue(PasskeyRecoveryBackup.objects.get(user=self.owner).is_active)
        self.assertTrue(UserPasskey.objects.filter(credential_id=b'lost-cred').exists())
        self.assertEqual(self.anon.post(reverse('begin_recovery_passkey_registration')).status_code, 400)
        # The same key works once the server can start the registration
        self.assertEqual(self._recover().status_code, 200)

    def test_registration_needs_a_recovery_in_this_session(self):
        self.assertEqual(self.anon.post(reverse('begin_recovery_passkey_registration')).status_code, 400)
        self.assertEqual(self._register().status_code, 400)
        self.assertFalse(UserPasskey.objects.filter(credential_id=b'new-cred').exists())


class ChangeMasterTests(TestCase):
    def test_a_master_password_change_moves_sign_in_too(self):
        user = User.objects.create_user('owner', 'owner@example.com', OLD_VERIFIER)
        UserSalt.objects.create(user=user, salt=os.urandom(16), auth_hash=b'old-hash')
        authed = APIClient()
        authed.force_authenticate(user)
        body = {'current_auth_hash': base64.b64encode(b'old-hash').decode(),
                'new_auth_hash': base64.b64encode(b'new-hash').decode()}
        self.assertEqual(authed.post('/api/auth/change_master/', body, format='json').status_code, 400)
        r = authed.post('/api/auth/change_master/', dict(body, new_login_verifier=NEW_VERIFIER), format='json')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(_sign_in(APIClient(), 'owner', NEW_VERIFIER).status_code, 200)
        self.assertEqual(_sign_in(APIClient(), 'owner', OLD_VERIFIER).status_code, 401)


class RefreshRevocationRaceTests(TestCase):
    """A refresh that passed its blacklist check and then waited on the
    account lock while a reset or recovery committed must not rotate: its
    new token would never be in the revocation's scan."""

    def setUp(self):
        self.user = User.objects.create_user('owner', 'owner@example.com', OLD_VERIFIER)
        self.anon = APIClient()

    def _no_live_refresh_tokens(self):
        from rest_framework_simplejwt.token_blacklist.models import OutstandingToken
        return not OutstandingToken.objects.filter(
            user=self.user, blacklistedtoken__isnull=True).exists()

    def test_json_refresh_still_rotates_normally(self):
        refresh = _sign_in(self.anon, 'owner', OLD_VERIFIER).json()['refresh']
        r = self.anon.post('/api/auth/token/refresh/', {'refresh': refresh}, format='json')
        self.assertEqual(r.status_code, 200, r.content)

    def test_json_refresh_that_waited_on_a_revocation_is_refused(self):
        # The revocation commits on its own, right after this refresh decoded
        # and blacklist-checked its token and before it takes the lock. (The
        # window between simplejwt's own re-check and outstand() is closed by
        # the row lock, which SQLite does not implement; only PostgreSQL can
        # show that one.)
        from rest_framework_simplejwt.tokens import RefreshToken
        from auth_module.login_verifier import revoke_sessions
        from auth_module.token_family import RevocationSafeTokenRefreshSerializer
        calls = []

        def decode_then_revoke(raw):
            token = RefreshToken(raw)
            if not calls:
                calls.append(raw)
                revoke_sessions(self.user)
            return token

        refresh = _sign_in(self.anon, 'owner', OLD_VERIFIER).json()['refresh']
        with patch.object(RevocationSafeTokenRefreshSerializer, 'token_class', staticmethod(decode_then_revoke)):
            r = self.anon.post('/api/auth/token/refresh/', {'refresh': refresh}, format='json')
        self.assertEqual(r.status_code, 401, r.content)
        self.assertTrue(self._no_live_refresh_tokens())

    def test_cookie_refresh_that_waited_on_a_revocation_is_refused(self):
        signed_in = self.anon.post('/api/auth/cookie/token/', {
            'username': 'owner', 'password': OLD_VERIFIER}, format='json')
        self.assertEqual(signed_in.status_code, 200, signed_in.content)
        # The revocation commits right after the view decoded and
        # blacklist-checked the cookie's token, before it rotates it.
        from rest_framework_simplejwt.tokens import RefreshToken
        from auth_module.login_verifier import revoke_sessions

        def decode_then_revoke(raw):
            token = RefreshToken(raw)
            revoke_sessions(self.user)
            return token

        with patch('auth_module.cookie_auth_view.RefreshToken', side_effect=decode_then_revoke):
            r = self.anon.post('/api/auth/cookie/token/refresh/', HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(r.status_code, 401, r.content)
        self.assertTrue(self._no_live_refresh_tokens())

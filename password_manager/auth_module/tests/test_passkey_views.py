"""
Passkey registration and sign-in against fido2 2.x.

- Registration binds to the signed-in user and stores only public material.
- Anonymous authenticate/begin uses discoverable credentials: it lists no
  credential and is the same whatever email is sent, so it reveals nothing
  about any account (including through credential-id length).
- authenticate/complete finds the credential by id, signs in with a real
  assertion and gives one answer for every failure (unknown credential, bad
  signature, user-handle mismatch, another account's credential during
  re-authentication, counter regression).
"""
import hashlib
import os
from unittest.mock import patch

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from fido2 import cbor
from fido2.cose import ES256
from fido2.utils import websafe_decode, websafe_encode
from fido2.webauthn import (
    Aaguid,
    AttestationObject,
    AttestedCredentialData,
    AuthenticatorData,
    CollectedClientData,
)
from rest_framework.test import APIClient

from auth_module import passkey_views
from auth_module.models import UserPasskey

ORIGIN = 'http://localhost:5173'


class SoftAuthenticator:
    """A minimal ES256 platform authenticator for driving the real views."""

    def __init__(self, counter=0, counter_step=1, credential_id_length=32):
        self.key = ec.generate_private_key(ec.SECP256R1())
        self.cose_key = ES256.from_cryptography_key(self.key.public_key())
        self.credential_id = os.urandom(credential_id_length)
        self.user_handle = None
        self.counter = counter
        self.counter_step = counter_step
        self.rp_id_hash = hashlib.sha256(passkey_views.RP_ID.encode()).digest()

    def _credential_ids(self):
        return {
            'id': websafe_encode(self.credential_id),
            'rawId': websafe_encode(self.credential_id),
            'type': 'public-key',
        }

    def create(self, options):
        self.user_handle = websafe_decode(options['user']['id'])
        client_data = CollectedClientData.create(
            type=CollectedClientData.TYPE.CREATE,
            challenge=websafe_decode(options['challenge']),
            origin=ORIGIN,
        )
        auth_data = AuthenticatorData.create(
            self.rp_id_hash,
            AuthenticatorData.FLAG.UP | AuthenticatorData.FLAG.UV | AuthenticatorData.FLAG.AT,
            self.counter,
            AttestedCredentialData.create(Aaguid.NONE, self.credential_id, self.cose_key),
        )
        attestation = AttestationObject.create('none', auth_data, {})
        return {
            **self._credential_ids(),
            'response': {
                'clientDataJSON': websafe_encode(bytes(client_data)),
                'attestationObject': websafe_encode(bytes(attestation)),
            },
            'device_type': 'Test',
        }

    def get(self, options, credential_id=None, user_handle=None):
        self.counter += self.counter_step
        client_data = CollectedClientData.create(
            type=CollectedClientData.TYPE.GET,
            challenge=websafe_decode(options['challenge']),
            origin=ORIGIN,
        )
        auth_data = AuthenticatorData.create(
            self.rp_id_hash,
            AuthenticatorData.FLAG.UP | AuthenticatorData.FLAG.UV,
            self.counter,
        )
        signature = self.key.sign(auth_data + client_data.hash, ec.ECDSA(hashes.SHA256()))
        ids = self._credential_ids()
        if credential_id is not None:
            ids['id'] = ids['rawId'] = websafe_encode(credential_id)
        return {
            **ids,
            'response': {
                'clientDataJSON': websafe_encode(bytes(client_data)),
                'authenticatorData': websafe_encode(bytes(auth_data)),
                'signature': websafe_encode(signature),
                'userHandle': websafe_encode(user_handle or self.user_handle or b'none'),
            },
        }


class PasskeyViewTests(TestCase):
    def setUp(self):
        cache.clear()
        patcher = patch.object(passkey_views, 'ALLOWED_ORIGINS', [ORIGIN])
        patcher.start()
        self.addCleanup(patcher.stop)
        self.owner = User.objects.create_user('owner', 'owner@example.com', 'Owner-Pass-1!')
        self.no_passkey = User.objects.create_user('plain', 'plain@example.com', 'Plain-Pass-1!')

    def _register(self, user, authenticator):
        client = APIClient()
        client.force_authenticate(user)
        begin = client.post(reverse('register_passkey_begin'), {}, format='json')
        self.assertEqual(begin.status_code, 200, begin.content)
        complete = client.post(
            reverse('register_passkey_complete'), authenticator.create(begin.json()), format='json'
        )
        self.assertEqual(complete.status_code, 200, complete.content)

    def _begin(self, client, email=None):
        body = {'email': email} if email is not None else {}
        r = client.post(reverse('authenticate_passkey_begin'), body, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        return r.json()

    # --- registration ----------------------------------------------------------

    def test_registration_stores_public_material_for_the_signed_in_user(self):
        authenticator = SoftAuthenticator()
        self._register(self.owner, authenticator)

        passkey = UserPasskey.objects.get(user=self.owner)
        self.assertEqual(bytes(passkey.credential_id), authenticator.credential_id)
        self.assertEqual(cbor.decode(bytes(passkey.public_key)), dict(authenticator.cose_key))

    def test_registration_requires_a_signed_in_user(self):
        r = APIClient().post(reverse('register_passkey_begin'), {'email': 'owner@example.com'}, format='json')
        self.assertEqual(r.status_code, 401, r.content)
        self.assertFalse(UserPasskey.objects.exists())

    def test_registration_asks_for_a_discoverable_credential(self):
        client = APIClient()
        client.force_authenticate(self.owner)
        r = client.post(reverse('register_passkey_begin'), {}, format='json')
        self.assertEqual(r.json()['authenticatorSelection']['residentKey'], 'required')

    # --- begin uniformity -----------------------------------------------------

    def test_anonymous_begin_is_the_same_for_every_email(self):
        self._register(self.owner, SoftAuthenticator(credential_id_length=64))
        client = APIClient()

        answers = [
            self._begin(client, email)
            for email in ('owner@example.com', 'plain@example.com', 'nobody@example.com', None)
        ]

        for answer in answers:
            self.assertNotIn('allowCredentials', answer)
        without_challenge = {
            repr(sorted((k, v) for k, v in a.items() if k != 'challenge')) for a in answers
        }
        self.assertEqual(len(without_challenge), 1, without_challenge)

    def test_reauth_begin_lists_only_the_signed_in_users_credentials(self):
        authenticator = SoftAuthenticator()
        self._register(self.owner, authenticator)
        client = APIClient()
        client.force_authenticate(self.owner)

        options = self._begin(client)
        self.assertEqual(
            [websafe_decode(c['id']) for c in options['allowCredentials']],
            [authenticator.credential_id],
        )

    # --- complete -------------------------------------------------------------

    def test_complete_round_trip_signs_in_and_advances_the_counter(self):
        authenticator = SoftAuthenticator()
        self._register(self.owner, authenticator)
        client = APIClient()

        options = self._begin(client)
        r = client.post(
            reverse('authenticate_passkey_complete'), authenticator.get(options), format='json'
        )

        self.assertEqual(r.status_code, 200, r.content)
        body = r.json()
        self.assertEqual(body['user']['id'], self.owner.id)
        self.assertTrue(body['tokens']['access'])
        self.assertEqual(UserPasskey.objects.get(user=self.owner).sign_count, authenticator.counter)

    def test_complete_round_trip_with_a_64_byte_credential_id(self):
        authenticator = SoftAuthenticator(credential_id_length=64)
        self._register(self.owner, authenticator)
        client = APIClient()

        r = client.post(
            reverse('authenticate_passkey_complete'), authenticator.get(self._begin(client)), format='json'
        )
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.json()['user']['id'], self.owner.id)

    def test_complete_accepts_an_authenticator_that_never_counts(self):
        authenticator = SoftAuthenticator(counter=0, counter_step=0)
        self._register(self.owner, authenticator)
        client = APIClient()

        for _ in range(2):
            options = self._begin(client)
            r = client.post(
                reverse('authenticate_passkey_complete'), authenticator.get(options), format='json'
            )
            self.assertEqual(r.status_code, 200, r.content)

    def test_complete_state_is_single_use(self):
        authenticator = SoftAuthenticator()
        self._register(self.owner, authenticator)
        client = APIClient()

        options = self._begin(client)
        url = reverse('authenticate_passkey_complete')
        self.assertEqual(client.post(url, authenticator.get(options), format='json').status_code, 200)
        self.assertEqual(client.post(url, authenticator.get(options), format='json').status_code, 400)

    def _assert_uniform_failure(self, response):
        self.assertEqual(response.status_code, 401, response.content)
        self.assertEqual(response.json()['message'], passkey_views.AUTHENTICATION_FAILED)
        self.assertEqual(response.json()['code'], 'passkey_auth_failed')

    def test_complete_fails_uniformly(self):
        owner_authenticator = SoftAuthenticator()
        self._register(self.owner, owner_authenticator)
        other_authenticator = SoftAuthenticator()
        self._register(self.no_passkey, other_authenticator)
        url = reverse('authenticate_passkey_complete')

        # A credential no account has.
        client = APIClient()
        options = self._begin(client)
        self._assert_uniform_failure(client.post(url, SoftAuthenticator().get(options), format='json'))

        # The owner's credential id, signed by a different key.
        client = APIClient()
        options = self._begin(client)
        forged = SoftAuthenticator().get(options, credential_id=owner_authenticator.credential_id)
        self._assert_uniform_failure(client.post(url, forged, format='json'))

        # A user handle naming another account.
        client = APIClient()
        options = self._begin(client)
        mismatched = owner_authenticator.get(options, user_handle=str(self.no_passkey.id).encode())
        self._assert_uniform_failure(client.post(url, mismatched, format='json'))

        # Re-authentication bound to the owner, completed with another account's passkey.
        client = APIClient()
        client.force_authenticate(self.owner)
        options = self._begin(client)
        self._assert_uniform_failure(client.post(url, other_authenticator.get(options), format='json'))

        # A counter that does not increase.
        client = APIClient()
        options = self._begin(client)
        UserPasskey.objects.filter(user=self.owner).update(sign_count=50)
        self._assert_uniform_failure(client.post(url, owner_authenticator.get(options), format='json'))

        self.assertIsNone(UserPasskey.objects.get(user=self.owner).last_used_at)
        self.assertIsNone(UserPasskey.objects.get(user=self.no_passkey).last_used_at)

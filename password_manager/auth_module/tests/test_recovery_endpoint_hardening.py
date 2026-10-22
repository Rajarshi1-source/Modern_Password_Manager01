"""
Anonymous recovery endpoints: legacy recovery key, behavioral completion and
passkey-primary initiation.

- The legacy recovery-key endpoints (validate / get-encrypted-vault /
  reset-with-recovery-key) are retired with 410 and change nothing.
- Behavioral completion is retired with 410; challenge submission and status
  return no similarity scores, and a challenge must belong to its attempt.
- Passkey-primary initiate answers every account the same way and never
  returns a user id; complete and fallback work from the attempt token alone.
"""
import base64
import os
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework.test import APIClient

from auth_module.models import RecoveryKey, UserPasskey, UserSalt


@override_settings(QUANTUM_CRYPTO={'ALLOW_SIMULATION': True, 'ENABLED': True})
class RecoveryEndpointHardeningTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user('owner', 'owner@example.com', 'Owner-Pass-1!')
        UserSalt.objects.create(user=self.owner, salt=os.urandom(16), auth_hash=b'original-hash')
        RecoveryKey.objects.create(user=self.owner, encrypted_vault='owner-vault-ct', salt='s')
        self.anon = APIClient()

    # --- legacy recovery key -------------------------------------------------

    def test_legacy_reset_with_recovery_key_is_retired_and_changes_nothing(self):
        r = self.anon.post(reverse('reset-with-recovery-key'), {
            'user_id': self.owner.id,
            'new_encrypted_vault': 'other-vault',
            'new_password_hash': base64.b64encode(b'other-hash').decode(),
        }, format='json')
        self.assertEqual(r.status_code, 410, r.content)
        self.assertEqual(bytes(UserSalt.objects.get(user=self.owner).auth_hash), b'original-hash')
        self.assertEqual(RecoveryKey.objects.get(user=self.owner).encrypted_vault, 'owner-vault-ct')

    def test_legacy_get_encrypted_vault_is_retired(self):
        r = self.anon.post(reverse('get-encrypted-vault'), {
            'email': 'owner@example.com', 'recovery_key_hash': 'anything',
        }, format='json')
        self.assertEqual(r.status_code, 410, r.content)
        self.assertNotIn(b'owner-vault-ct', r.content)

    def test_legacy_validate_recovery_key_is_retired(self):
        r = self.anon.post(reverse('validate-recovery-key'), {
            'email': 'owner@example.com', 'recovery_key_hash': 'anything',
        }, format='json')
        self.assertEqual(r.status_code, 410, r.content)

    # --- behavioral recovery -------------------------------------------------

    def _attempt(self, similarity=0.95):
        from behavioral_recovery.models import BehavioralRecoveryAttempt
        attempt = BehavioralRecoveryAttempt.objects.create(user=self.owner)
        attempt.overall_similarity = similarity
        attempt.similarity_scores = {'typing': similarity}
        attempt.save()
        return attempt

    def test_behavioral_complete_is_retired_and_keeps_the_password(self):
        attempt = self._attempt()
        r = self.anon.post('/api/behavioral-recovery/complete/', {
            'attempt_id': str(attempt.attempt_id), 'new_password': 'Other-Pass-123!',
        }, format='json')
        self.assertEqual(r.status_code, 410, r.content)
        self.owner.refresh_from_db()
        self.assertTrue(self.owner.check_password('Owner-Pass-1!'))

    def _challenge(self, attempt):
        from behavioral_recovery.models import BehavioralChallenge
        return BehavioralChallenge.objects.create(
            recovery_attempt=attempt, challenge_type='typing', challenge_data={})

    @patch('behavioral_recovery.views.ChallengeGenerator.get_next_challenge', return_value=None)
    @patch('behavioral_recovery.views.RecoveryOrchestrator.evaluate_challenge',
           return_value={'similarity_score': 0.91, 'passed': True})
    def test_submit_challenge_returns_no_similarity_scores(self, _evaluate, _next):
        attempt = self._attempt()
        r = self.anon.post('/api/behavioral-recovery/submit-challenge/', {
            'attempt_id': str(attempt.attempt_id),
            'challenge_id': str(self._challenge(attempt).challenge_id),
            'behavioral_data': {'keys': []},
        }, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        data = r.json()
        for field in ('similarity_score', 'overall_similarity', 'similarity_scores', 'passed'):
            self.assertNotIn(field, data)

    @patch('behavioral_recovery.views.RecoveryOrchestrator.evaluate_challenge')
    def test_submit_challenge_rejects_a_challenge_from_another_attempt(self, evaluate):
        attempt, other = self._attempt(), self._attempt()
        r = self.anon.post('/api/behavioral-recovery/submit-challenge/', {
            'attempt_id': str(attempt.attempt_id),
            'challenge_id': str(self._challenge(other).challenge_id),
            'behavioral_data': {'keys': []},
        }, format='json')
        self.assertEqual(r.status_code, 404, r.content)
        evaluate.assert_not_called()

    def test_recovery_status_returns_no_similarity_scores(self):
        attempt = self._attempt()
        r = self.anon.get(f'/api/behavioral-recovery/status/{attempt.attempt_id}/')
        self.assertEqual(r.status_code, 200, r.content)
        data = r.json()
        self.assertNotIn('overall_similarity', data)
        self.assertNotIn('similarity_scores', data)

    # --- passkey-primary recovery -------------------------------------------

    def _initiate(self, who):
        r = self.anon.post(reverse('initiate_primary_passkey_recovery'),
                           {'username_or_email': who}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        return r.json()

    def _backup(self):
        UserPasskey.objects.create(
            user=self.owner, credential_id=b'cred-1', public_key=b'pk-bytes', rp_id='localhost')
        authed = APIClient()
        authed.force_authenticate(self.owner)
        r = authed.post(reverse('setup_primary_passkey_recovery'),
                        {'passkey_credential_id': b'cred-1'.hex()}, format='json')
        self.assertEqual(r.status_code, 201, r.content)
        return r.json()['recovery_key']

    def _complete(self, token, key):
        return self.anon.post(reverse('complete_primary_passkey_recovery'), {
            'recovery_attempt_id': token, 'recovery_key': key,
        }, format='json')

    def test_passkey_initiate_answers_every_account_the_same_way(self):
        unknown = self._initiate('nobody@example.com')
        no_backup = self._initiate('owner@example.com')
        self._backup()
        with_backup = self._initiate('owner@example.com')
        for body in (unknown, no_backup, with_backup):
            self.assertNotIn('user_id', body)
            self.assertEqual(set(body), {'message', 'recovery_attempt_id'})
            self.assertEqual(body['message'], unknown['message'])
            self.assertEqual(len(body['recovery_attempt_id']), len(unknown['recovery_attempt_id']))

    def test_passkey_complete_answers_a_decoy_like_a_wrong_key(self):
        key = self._backup()
        decoy = self._complete(self._initiate('nobody@example.com')['recovery_attempt_id'], key)
        wrong = self._complete(self._initiate('owner')['recovery_attempt_id'], 'A' * 24)
        self.assertEqual(decoy.status_code, 401)
        self.assertEqual(wrong.status_code, 401)
        self.assertEqual(decoy.json(), wrong.json())

    def test_passkey_complete_works_from_the_attempt_token_alone(self):
        key = self._backup()
        r = self._complete(self._initiate('owner')['recovery_attempt_id'], key)
        self.assertEqual(r.status_code, 200, r.content)
        self.assertIn('passkey_credential', r.json())

    def test_passkey_complete_rejects_a_raw_attempt_id(self):
        from auth_module.passkey_primary_recovery_models import PasskeyRecoveryAttempt
        key = self._backup()
        self._initiate('owner')
        attempt = PasskeyRecoveryAttempt.objects.get(user=self.owner)
        r = self._complete(str(attempt.id), key)
        self.assertEqual(r.status_code, 401, r.content)

    def test_passkey_fallback_answers_a_decoy_like_an_account_without_guardians(self):
        self._backup()
        decoy = self.anon.post(reverse('fallback_to_social_mesh_recovery'), {
            'primary_recovery_attempt_id': self._initiate('nobody')['recovery_attempt_id'],
        }, format='json')
        real = self.anon.post(reverse('fallback_to_social_mesh_recovery'), {
            'primary_recovery_attempt_id': self._initiate('owner')['recovery_attempt_id'],
        }, format='json')
        self.assertEqual(decoy.status_code, 400, decoy.content)
        self.assertEqual(decoy.json(), real.json())

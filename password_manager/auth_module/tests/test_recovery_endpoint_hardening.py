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

    def test_legacy_setup_recovery_key_is_retired(self):
        authed = APIClient()
        authed.force_authenticate(self.owner)
        r = authed.post(reverse('setup-recovery-key'), {
            'encryptedVault': 'new-vault', 'salt': 's2', 'method': 'm',
        }, format='json')
        self.assertEqual(r.status_code, 410, r.content)
        self.assertIn('/recovery/key/enroll-v2', r.json()['error'])
        self.assertEqual(RecoveryKey.objects.get(user=self.owner).encrypted_vault, 'owner-vault-ct')

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

    def test_behavioral_initiate_is_retired_for_every_email(self):
        from behavioral_recovery.models import BehavioralCommitment, BehavioralRecoveryAttempt
        BehavioralCommitment.objects.create(
            user=self.owner, encrypted_embedding=b'x', challenge_type='typing')
        url = '/api/behavioral-recovery/initiate/'
        unknown = self.anon.post(url, {'email': 'nobody@example.com'}, format='json')
        enrolled = self.anon.post(url, {'email': 'owner@example.com'}, format='json')
        self.assertEqual(unknown.status_code, 410, unknown.content)
        self.assertEqual(enrolled.status_code, 410, enrolled.content)
        self.assertEqual(enrolled.json(), unknown.json())
        self.assertFalse(BehavioralRecoveryAttempt.objects.exists())

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

    @patch('behavioral_recovery.services.RecoveryOrchestrator.evaluate_challenge')
    def test_submit_challenge_is_retired_and_reads_no_behavioral_data(self, evaluate):
        # Challenge responses were raw keystroke and mouse data; the server
        # must not receive them.
        attempt = self._attempt()
        r = self.anon.post('/api/behavioral-recovery/submit-challenge/', {
            'attempt_id': str(attempt.attempt_id),
            'challenge_id': str(self._challenge(attempt).challenge_id),
            'behavioral_data': {'keys': [{'key': 'a', 'down': 1, 'up': 2}]},
        }, format='json')
        self.assertEqual(r.status_code, 410, r.content)
        evaluate.assert_not_called()

    def test_commitment_setup_is_retired_and_stores_nothing(self):
        from behavioral_recovery.models import BehavioralCommitment
        client = APIClient()
        client.force_authenticate(self.owner)
        with patch('behavioral_recovery.services.CommitmentService.create_commitments') as create:
            r = client.post('/api/behavioral-recovery/setup-commitments/', {
                'behavioral_profile': {'typing': {'press_duration': [80, 95, 110]}},
            }, format='json')
        self.assertEqual(r.status_code, 410, r.content)
        create.assert_not_called()
        self.assertFalse(BehavioralCommitment.objects.exists())

    def test_recovery_status_returns_no_similarity_scores(self):
        attempt = self._attempt()
        challenge = self._challenge(attempt)
        challenge.similarity_score, challenge.passed = 0.91, True
        challenge.save()
        r = self.anon.get(f'/api/behavioral-recovery/status/{attempt.attempt_id}/')
        self.assertEqual(r.status_code, 200, r.content)
        data = r.json()
        self.assertNotIn('overall_similarity', data)
        self.assertNotIn('similarity_scores', data)
        self.assertEqual(len(data['challenges']), 1)
        for nested in data['challenges']:
            self.assertNotIn('similarity_score', nested)
            self.assertNotIn('passed', nested)

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
        self.assertIn('registration_options', r.json())

    def test_passkey_complete_accepts_the_right_key_after_a_typo(self):
        key = self._backup()
        token = self._initiate('owner')['recovery_attempt_id']
        self.assertEqual(self._complete(token, 'A' * 24).status_code, 401)
        r = self._complete(token, key)
        self.assertEqual(r.status_code, 200, r.content)

    def test_passkey_complete_rejects_a_raw_attempt_id(self):
        from auth_module.passkey_primary_recovery_models import PasskeyRecoveryAttempt
        key = self._backup()
        # The attempt row exists from the token's first use
        self._complete(self._initiate('owner')['recovery_attempt_id'], 'A' * 24)
        attempt = PasskeyRecoveryAttempt.objects.get(user=self.owner)
        r = self._complete(str(attempt.id), key)
        self.assertEqual(r.status_code, 401, r.content)

    def _fallback(self, token):
        return self.anon.post(reverse('fallback_to_social_mesh_recovery'), {
            'primary_recovery_attempt_id': token,
        }, format='json')

    def test_passkey_fallback_answers_every_account_the_same_way(self):
        from auth_module.passkey_primary_recovery_models import PasskeyRecoveryAttempt
        from auth_module.quantum_recovery_models import (
            PasskeyRecoverySetup, RecoveryShard, RecoveryShardType)
        self._backup()
        setup = PasskeyRecoverySetup.objects.create(
            user=self.owner, total_shards=3, threshold_shards=2, is_active=True)
        RecoveryShard.objects.create(
            recovery_setup=setup, shard_type=RecoveryShardType.DEVICE, shard_index=1,
            encrypted_shard_data=b'x')
        token = self._initiate('owner')['recovery_attempt_id']
        self.assertEqual(self._complete(token, 'A' * 24).status_code, 401)
        real = self._fallback(token)
        decoy = self._fallback(self._initiate('nobody')['recovery_attempt_id'])
        self.assertEqual(real.status_code, 200, real.content)
        self.assertEqual(decoy.status_code, 200, decoy.content)
        self.assertEqual(real.json(), decoy.json())
        self.assertNotIn('threshold', real.json())
        self.assertNotIn('total_guardians', real.json())
        attempt = PasskeyRecoveryAttempt.objects.get(user=self.owner)
        self.assertEqual(attempt.status, 'fallback_initiated')

    def test_passkey_fallback_leaves_an_unverified_attempt_in_primary_recovery(self):
        from auth_module.passkey_primary_recovery_models import PasskeyRecoveryAttempt
        from auth_module.quantum_recovery_models import (
            PasskeyRecoverySetup, RecoveryShard, RecoveryShardType)
        key = self._backup()
        setup = PasskeyRecoverySetup.objects.create(
            user=self.owner, total_shards=3, threshold_shards=2, is_active=True)
        RecoveryShard.objects.create(
            recovery_setup=setup, shard_type=RecoveryShardType.DEVICE, shard_index=1,
            encrypted_shard_data=b'x')
        token = self._initiate('owner')['recovery_attempt_id']
        self.assertEqual(self._fallback(token).status_code, 200)
        self.assertFalse(PasskeyRecoveryAttempt.objects.filter(status='fallback_initiated').exists())
        self.assertEqual(self._complete(token, key).status_code, 200)

"""
Guardian recovery (quantum_recovery_views) with shares sealed on the client.

Setup used to split a random placeholder secret on the server, wrap an owner
key under a discarded random key, and seal shares with a server-side KEM;
completion treated a guardian shard's ciphertext as the shard. The server now
stores and relays only what the owner's and guardians' devices sealed to
hybrid X25519 + ML-KEM-768 keys (shared/sealed_shares.py), and never holds a
share or the seed.
"""

import base64
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from auth_module.quantum_recovery_models import (
    GuardianApproval,
    PasskeyRecoverySetup,
    RecoveryAttempt,
    RecoveryGuardian,
    RecoveryShard,
    RecoveryShardType,
)
from auth_module.services.quantum_crypto_service import quantum_crypto_service
from shared.tests import sealed_share_fixtures as fx


def _guardian(i, **overrides):
    proof, proof_hash = fx.share_proof()
    g = {
        'email': f'g{i}@example.com', 'requires_video': False,
        'public_key': fx.hybrid_public_key(), 'share_index': i,
        'sealed_share': fx.sealed_share(), 'share_proof_hash': proof_hash,
    }
    g.update(overrides)
    return g, proof


class GuardianRecoverySetupTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('owner', 'owner@example.com', 'Owner-Pass-1!')
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.url = reverse('quantum-recovery-setup')

    def _setup(self, guardians, **extra):
        body = {'threshold_shards': 2, 'guardians': guardians,
                'secret_check': fx.seed_check(), **extra}
        return self.client.post(self.url, body, format='json')

    def test_sealed_shares_are_stored_exactly_as_sent_and_no_key_is_made(self):
        guardians = [_guardian(i)[0] for i in (1, 2, 3)]
        with patch.object(quantum_crypto_service, 'generate_kyber_keypair') as keygen, \
                patch.object(quantum_crypto_service, 'shamir_split_secret') as split:
            r = self._setup(guardians)
        self.assertEqual(r.status_code, 201, r.content)
        keygen.assert_not_called()
        split.assert_not_called()
        setup = PasskeyRecoverySetup.objects.get(user=self.user)
        self.assertEqual(bytes(setup.kyber_private_key_encrypted), b'')
        self.assertEqual(len(bytes(setup.secret_check)), 32)
        for g in guardians:
            guardian = RecoveryGuardian.objects.get(shard__shard_index=g['share_index'])
            self.assertEqual(bytes(guardian.shard.encrypted_shard_data),
                             base64.b64decode(g['sealed_share']))
            self.assertEqual(bytes(guardian.guardian_public_key),
                             base64.b64decode(g['public_key']))
        # No device shard sealed under a server-known fingerprint.
        self.assertFalse(RecoveryShard.objects.filter(shard_type=RecoveryShardType.DEVICE).exists())

    def test_a_plaintext_secret_is_refused(self):
        guardians = [_guardian(i)[0] for i in (1, 2, 3)]
        for field in ('secret', 'secret_hex', 'master_secret_hex'):
            r = self._setup(guardians, **{field: 'ab' * 32})
            self.assertEqual(r.status_code, 400, r.content)
        self.assertFalse(PasskeyRecoverySetup.objects.filter(user=self.user).exists())

    def test_malformed_keys_shares_and_proofs_are_refused(self):
        bad_keys = [
            None, 'short', '%%not-base64%%',
            # ML-KEM-768 alone, without the X25519 half
            fx.b64(fx.ml_kem_768_public_key()),
            fx.b64(b'\x01' * 32 + fx.ml_kem_768_public_key(bad_coefficient=True)),
            fx.b64(b'\x00' * 32 + fx.ml_kem_768_public_key()),
        ]
        cases = [{'public_key': k} for k in bad_keys] + [
            {'sealed_share': fx.b64(b'\x01' * 40)},
            {'sealed_share': fx.b64(b'\x02' + base64.b64decode(fx.sealed_share())[1:])},
            {'share_proof_hash': fx.b64(b'\x01' * 31)},
            {'share_index': 0}, {'share_index': True}, {'email': 'no-at-sign'},
        ]
        for override in cases:
            guardians = [_guardian(1, **override)[0], _guardian(2)[0], _guardian(3)[0]]
            r = self._setup(guardians)
            self.assertEqual(r.status_code, 400, (override, r.content))
        r = self._setup([_guardian(1)[0], _guardian(2)[0], _guardian(3)[0]], secret_check='')
        self.assertEqual(r.status_code, 400, r.content)
        self.assertFalse(PasskeyRecoverySetup.objects.filter(user=self.user).exists())

    def test_threshold_and_index_rules(self):
        two = [_guardian(i)[0] for i in (1, 2)]
        self.assertEqual(self._setup(two).status_code, 400)
        three = [_guardian(i)[0] for i in (1, 2, 3)]
        self.assertEqual(self._setup(three, threshold_shards=4).status_code, 400)
        dup = [_guardian(1)[0], _guardian(1)[0], _guardian(3)[0]]
        self.assertEqual(self._setup(dup).status_code, 400)
        self.assertFalse(PasskeyRecoverySetup.objects.filter(user=self.user).exists())

    def test_a_setup_from_before_client_sealing_is_replaced(self):
        legacy = PasskeyRecoverySetup.objects.create(
            user=self.user, total_shards=3, threshold_shards=2, is_active=True,
            kyber_public_key=b'old', kyber_private_key_encrypted=b'old')
        # An invalid request leaves the old setup alone.
        self.assertEqual(self._setup([_guardian(1)[0]]).status_code, 400)
        self.assertTrue(PasskeyRecoverySetup.objects.filter(pk=legacy.pk).exists())
        r = self._setup([_guardian(i)[0] for i in (1, 2, 3)])
        self.assertEqual(r.status_code, 201, r.content)
        setup = PasskeyRecoverySetup.objects.get(user=self.user)
        self.assertNotEqual(setup.pk, legacy.pk)
        self.assertEqual(len(bytes(setup.secret_check)), 32)

    def test_retrying_a_pending_setup_is_a_clear_400(self):
        guardians = [_guardian(i)[0] for i in (1, 2, 3)]
        self.assertEqual(self._setup(guardians).status_code, 201)
        r = self._setup(guardians)
        self.assertEqual(r.status_code, 400, r.content)
        self.assertEqual(PasskeyRecoverySetup.objects.filter(user=self.user).count(), 1)


class GuardianInvitationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('owner', 'owner@example.com', 'Owner-Pass-1!')
        owner = APIClient()
        owner.force_authenticate(self.user)
        made = [_guardian(i) for i in (1, 2, 3)]
        self.guardians = [g for g, _ in made]
        self.proofs = [p for _, p in made]
        r = owner.post(reverse('quantum-recovery-setup'), {
            'threshold_shards': 2, 'guardians': self.guardians,
            'secret_check': fx.seed_check()}, format='json')
        self.assertEqual(r.status_code, 201, r.content)
        self.tokens = [s['invitation_token'] for s in r.json()['shards_created']]
        self.anon = APIClient()

    def _accept(self, i, proof):
        return self.anon.post(reverse('quantum-recovery-accept-invitation'), {
            'invitation_token': self.tokens[i], 'share_proof': proof}, format='json')

    def test_the_invitation_returns_the_guardians_sealed_share(self):
        r = self.anon.post(reverse('quantum-recovery-guardian-invitation'),
                           {'invitation_token': self.tokens[0]}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.json()['sealed_share'], self.guardians[0]['sealed_share'])
        r = self.anon.post(reverse('quantum-recovery-guardian-invitation'),
                           {'invitation_token': 'nope'}, format='json')
        self.assertEqual(r.status_code, 400)

    def test_acceptance_needs_the_share_proof(self):
        for proof in (None, '', fx.share_proof()[0], self.proofs[1]):
            r = self._accept(0, proof)
            self.assertEqual(r.status_code, 400, (proof, r.content))
        self.assertEqual(RecoveryGuardian.objects.filter(status='active').count(), 0)

    def test_all_guardians_proving_their_shares_activates_recovery(self):
        for i in range(3):
            r = self._accept(i, self.proofs[i])
            self.assertEqual(r.status_code, 200, r.content)
        self.assertTrue(PasskeyRecoverySetup.objects.get(user=self.user).is_active)
        # An invitation is single-use.
        self.assertEqual(self._accept(0, self.proofs[0]).status_code, 400)


class GuardianRecoveryFlowTests(TestCase):
    def setUp(self):
        cache.clear()  # completion throttle counters
        self.user = User.objects.create_user('owner', 'owner@example.com', 'Owner-Pass-1!')
        owner = APIClient()
        owner.force_authenticate(self.user)
        made = [_guardian(i) for i in (1, 2, 3)]
        self.secret_check = fx.seed_check()
        r = owner.post(reverse('quantum-recovery-setup'), {
            'threshold_shards': 2, 'guardians': [g for g, _ in made],
            'secret_check': self.secret_check}, format='json')
        self.assertEqual(r.status_code, 201, r.content)
        self.anon = APIClient()
        for s, (_, proof) in zip(r.json()['shards_created'], made):
            self.anon.post(reverse('quantum-recovery-accept-invitation'), {
                'invitation_token': s['invitation_token'], 'share_proof': proof}, format='json')
        self.setup = PasskeyRecoverySetup.objects.get(user=self.user)
        self.assertTrue(self.setup.is_active)
        self.requester_key = fx.hybrid_public_key()

    def _initiate(self, **body):
        return self.anon.post(reverse('quantum-recovery-initiate'), {
            'email': 'owner@example.com', **body}, format='json')

    def test_initiation_needs_a_requester_key_for_every_email(self):
        for email in ('owner@example.com', 'nobody@example.com'):
            r = self.anon.post(reverse('quantum-recovery-initiate'), {'email': email}, format='json')
            self.assertEqual(r.status_code, 400, r.content)
        self.assertFalse(RecoveryAttempt.objects.exists())
        r = self._initiate(requester_public_key=self.requester_key)
        self.assertEqual(r.status_code, 200, r.content)
        attempt = RecoveryAttempt.objects.get()
        self.assertEqual(bytes(attempt.requester_public_key), base64.b64decode(self.requester_key))
        # Every active guardian is asked, so the threshold can be met.
        self.assertEqual(attempt.guardian_approvals_required, 3)
        self.assertGreaterEqual(attempt.guardian_approvals_required, self.setup.threshold_shards)
        from auth_module.quantum_recovery_tasks import request_guardian_approvals
        request_guardian_approvals(str(attempt.id))
        self.assertEqual(GuardianApproval.objects.filter(recovery_attempt=attempt).count(), 3)

    def _attempt_with_approvals(self):
        self._initiate(requester_public_key=self.requester_key)
        attempt = RecoveryAttempt.objects.get()
        attempt.status = 'guardian_approval'
        attempt.trust_score = 0.95
        attempt.save()
        approvals = []
        for i, g in enumerate(RecoveryGuardian.objects.order_by('shard__shard_index')):
            approvals.append(GuardianApproval.objects.create(
                recovery_attempt=attempt, guardian=g, approval_token=f'token-{i}',
                approval_window_start=timezone.now() - timedelta(minutes=1),
                approval_window_end=timezone.now() + timedelta(hours=1)))
        return attempt, approvals

    def test_a_guardian_gets_its_sealed_share_and_the_requester_key(self):
        _, approvals = self._attempt_with_approvals()
        r = self.anon.post(reverse('quantum-recovery-guardian-share'),
                           {'approval_token': 'token-0'}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        shard = approvals[0].guardian.shard
        self.assertEqual(base64.b64decode(r.json()['sealed_share']), bytes(shard.encrypted_shard_data))
        self.assertEqual(r.json()['requester_public_key'], self.requester_key)

    def test_approval_requires_a_resealed_share(self):
        self._attempt_with_approvals()
        url = reverse('quantum-recovery-approve')
        for bad in (None, '', fx.b64(b'x' * 50)):
            r = self.anon.post(url, {'approval_token': 'token-0', 'approved': True,
                                     'resealed_share': bad}, format='json')
            self.assertEqual(r.status_code, 400, r.content)
        self.assertEqual(GuardianApproval.objects.get(approval_token='token-0').status, 'pending')
        # A denial needs nothing.
        r = self.anon.post(url, {'approval_token': 'token-1', 'approved': False}, format='json')
        self.assertEqual(r.status_code, 200, r.content)

    def test_completion_returns_only_the_resealed_shares_without_a_session(self):
        attempt, _ = self._attempt_with_approvals()
        url = reverse('quantum-recovery-complete')
        resealed = {}
        approve = reverse('quantum-recovery-approve')
        r = self.anon.post(approve, {'approval_token': 'token-0', 'approved': True,
                                     'resealed_share': (s := fx.sealed_share())}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        resealed[1] = s
        # One share is below the threshold of two.
        r = self.anon.post(url, {'attempt_id': str(attempt.id)}, format='json')
        self.assertEqual(r.status_code, 400, r.content)
        r = self.anon.post(approve, {'approval_token': 'token-2', 'approved': True,
                                     'resealed_share': (s := fx.sealed_share())}, format='json')
        resealed[3] = s

        r = self.anon.post(url, {'attempt_id': str(attempt.id)}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        body = r.json()
        self.assertEqual(body['secret_check'], self.secret_check)
        self.assertEqual(body['threshold'], 2)
        self.assertEqual({x['share_index']: x['sealed_share'] for x in body['sealed_shares']},
                         resealed)
        self.assertNotIn('recovery_token', body)
        attempt.refresh_from_db()
        self.assertEqual(attempt.status, 'completed')
        # A retry (say, after a lost response) gets the same shares; they open
        # only with the requester's key.
        r = self.anon.post(url, {'attempt_id': str(attempt.id)}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.json()['sealed_shares'], body['sealed_shares'])
        # ...even once the attempt's window has passed.
        attempt.expires_at = timezone.now() - timedelta(minutes=1)
        attempt.save(update_fields=['expires_at'])
        cache.clear()  # the completion URL allows three calls an hour
        r = self.anon.post(url, {'attempt_id': str(attempt.id)}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.json()['sealed_shares'], body['sealed_shares'])

    def test_low_trust_or_expired_attempts_release_nothing(self):
        attempt, _ = self._attempt_with_approvals()
        for i in (0, 1):
            self.anon.post(reverse('quantum-recovery-approve'), {
                'approval_token': f'token-{i}', 'approved': True,
                'resealed_share': fx.sealed_share()}, format='json')
        url = reverse('quantum-recovery-complete')
        attempt.trust_score = 0.1
        attempt.save()
        self.assertEqual(self.anon.post(url, {'attempt_id': str(attempt.id)}, format='json').status_code, 400)
        attempt.trust_score = 0.95
        attempt.expires_at = timezone.now() - timedelta(minutes=1)
        attempt.save()
        self.assertEqual(self.anon.post(url, {'attempt_id': str(attempt.id)}, format='json').status_code, 400)
        self.assertEqual(self.anon.post(url, {'attempt_id': 'not-a-uuid'}, format='json').status_code, 404)

    def test_completion_is_rate_limited_at_its_url(self):
        url = reverse('quantum-recovery-complete')
        codes = [self.anon.post(url, {'attempt_id': 'not-a-uuid'}, format='json').status_code
                 for _ in range(4)]
        self.assertEqual(codes[:3], [404, 404, 404])
        self.assertEqual(codes[3], 429)

    def test_a_setup_from_before_client_sealing_cannot_complete(self):
        attempt, _ = self._attempt_with_approvals()
        self.setup.secret_check = b''
        self.setup.save()
        r = self.anon.post(reverse('quantum-recovery-complete'),
                           {'attempt_id': str(attempt.id)}, format='json')
        self.assertEqual(r.status_code, 410, r.content)

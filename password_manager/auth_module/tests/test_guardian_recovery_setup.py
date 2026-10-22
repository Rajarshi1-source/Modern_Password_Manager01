"""
Guardian recovery setup (quantum_recovery_views.setup_recovery).

Setup used to generate each guardian's keypair on the server and discard the
private key, so no guardian shard could ever be opened. It also passed
password-encrypted dicts to a serializer that only knew the hybrid-shard
format, so every setup failed with a 500.
"""

import base64
import os
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework.test import APIClient

from auth_module.quantum_recovery_models import (
    PasskeyRecoverySetup,
    RecoveryGuardian,
    RecoveryShard,
    RecoveryShardType,
)
from auth_module.services.kyber_crypto import ProductionKyber
from auth_module.services.quantum_crypto_service import quantum_crypto_service


def _guardian(email, public_key=None):
    data = {'email': email, 'requires_video': False}
    if public_key is not None:
        data['public_key'] = base64.b64encode(public_key).decode()
    return data


@override_settings(QUANTUM_CRYPTO={'ALLOW_SIMULATION': True, 'ENABLED': True})
class GuardianRecoverySetupTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('owner', 'owner@example.com', 'Owner-Pass-1!')
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.url = reverse('quantum-recovery-setup')

    def _setup(self, guardians):
        return self.client.post(self.url, {
            'total_shards': 3, 'threshold_shards': 2, 'guardians': guardians,
            'device_fingerprint': 'device-fp',
        }, format='json')

    def test_guardian_without_own_public_key_is_rejected(self):
        for bad in (None, b'short', os.urandom(ProductionKyber.PUBLIC_KEY_SIZE + 1)):
            r = self._setup([_guardian('g1@example.com', bad)])
            self.assertEqual(r.status_code, 400, r.content)
        r = self._setup([{'email': 'g1@example.com', 'public_key': '%%not-base64%%'}])
        self.assertEqual(r.status_code, 400, r.content)
        self.assertFalse(PasskeyRecoverySetup.objects.filter(user=self.user).exists())

    def test_guardian_shards_are_sealed_to_the_guardians_own_keys(self):
        keys = [os.urandom(ProductionKyber.PUBLIC_KEY_SIZE) for _ in range(2)]
        with patch.object(quantum_crypto_service, 'generate_kyber_keypair',
                          wraps=quantum_crypto_service.generate_kyber_keypair) as keygen, \
                patch.object(quantum_crypto_service, 'encrypt_shard_hybrid',
                             wraps=quantum_crypto_service.encrypt_shard_hybrid) as seal:
            r = self._setup([_guardian('g1@example.com', keys[0]),
                             _guardian('g2@example.com', keys[1])])
        self.assertEqual(r.status_code, 201, r.content)
        # Only the owner's own keypair; no guardian keypair is made server-side.
        self.assertEqual(keygen.call_count, 1)
        self.assertEqual([c.args[1] for c in seal.call_args_list], keys)
        stored = [bytes(g.guardian_public_key)
                  for g in RecoveryGuardian.objects.order_by('shard__shard_index')]
        self.assertEqual(stored, keys)

    def test_password_encrypted_data_round_trips_through_storage(self):
        r = self._setup([_guardian('g1@example.com', os.urandom(ProductionKyber.PUBLIC_KEY_SIZE))])
        self.assertEqual(r.status_code, 201, r.content)
        device = RecoveryShard.objects.get(shard_type=RecoveryShardType.DEVICE)
        encrypted = quantum_crypto_service.deserialize_encrypted_shard(device.encrypted_shard_data)
        shard = quantum_crypto_service.decrypt_with_password(encrypted, 'device-fp')
        self.assertTrue(shard)

    def test_hybrid_shard_serialization_is_unchanged(self):
        hybrid = {'kyber_ciphertext': b'k', 'aes_ciphertext': b'a', 'nonce': b'n',
                  'algorithm': 'ML-KEM-768-AES-256-GCM', 'version': '1.0'}
        stored = quantum_crypto_service.serialize_encrypted_shard(hybrid)
        self.assertEqual(quantum_crypto_service.deserialize_encrypted_shard(stored), hybrid)

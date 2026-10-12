"""
F13 (docs/pqc-hybrid-architecture-review.md): auth_module's recovery KEM.

``QuantumCryptoService`` used to return fresh ``os.urandom`` bytes from
keygen, encapsulation and decapsulation in every environment, and
passkey-primary recovery decapsulated with a "private key" hashed from the
recovery key. Neither could ever decrypt.

CI does not install liboqs-python, so the real path runs against a fake
``oqs`` module whose decapsulation depends on the secret key, as in liboqs:
only the private key generated with a public key recovers secrets
encapsulated to it.
"""

import base64
import hashlib
import os
from unittest.mock import MagicMock, patch

from cryptography.exceptions import InvalidTag
from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase, override_settings

import auth_module.services.kyber_crypto as kc
from auth_module.services.passkey_primary_recovery_service import PasskeyPrimaryRecoveryService
from auth_module.services.quantum_crypto_service import Kyber, QuantumCryptoService

ALLOW_SIM = override_settings(QUANTUM_CRYPTO={'ALLOW_SIMULATION': True})
DENY_SIM = override_settings(QUANTUM_CRYPTO={'ALLOW_SIMULATION': False})

CREDENTIAL = {'credential_id': 'abc123', 'rp_id': 'localhost', 'user_id': 7}


def _public_from_secret(secret_key):
    return hashlib.shake_256(b'pk|' + secret_key).digest(1184)


class _FakeKeyEncapsulation:
    """Kyber768-shaped KEM where a public key is a function of its secret key."""

    def __init__(self, alg, secret_key=None):
        if alg != 'Kyber768':
            raise ValueError(f'unexpected algorithm {alg!r}')
        self.secret_key = secret_key

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def generate_keypair(self):
        self.secret_key = os.urandom(2400)
        return _public_from_secret(self.secret_key)

    def export_secret_key(self):
        return self.secret_key

    def encap_secret(self, public_key):
        ciphertext = os.urandom(1088)
        return ciphertext, hashlib.sha256(public_key + ciphertext).digest()

    def decap_secret(self, ciphertext):
        return hashlib.sha256(_public_from_secret(self.secret_key) + ciphertext).digest()


def fake_liboqs():
    oqs = MagicMock(name='oqs')
    oqs.KeyEncapsulation.side_effect = _FakeKeyEncapsulation
    patcher = patch.multiple(kc, LIBOQS_AVAILABLE=True, PQCRYPTO_AVAILABLE=False, oqs=oqs)
    return oqs, patcher


def simulated_kem():
    return patch.multiple(kc, LIBOQS_AVAILABLE=False, PQCRYPTO_AVAILABLE=False)


def secret_keys_used_for_decapsulation(oqs):
    return [c.args[1] for c in oqs.KeyEncapsulation.call_args_list if len(c.args) > 1]


@DENY_SIM
class QuantumCryptoServiceRealKemTests(SimpleTestCase):
    def setUp(self):
        self.oqs, patcher = fake_liboqs()
        patcher.start()
        self.addCleanup(patcher.stop)
        self.service = QuantumCryptoService()

    def test_keypair_comes_from_liboqs_kyber768(self):
        public_key, private_key = self.service.generate_kyber_keypair()
        self.oqs.KeyEncapsulation.assert_called_with('Kyber768')
        self.assertEqual(public_key, _public_from_secret(private_key))

    def test_decapsulation_reproduces_the_encapsulated_secret(self):
        public_key, private_key = self.service.generate_kyber_keypair()
        ciphertext, secret = self.service.kyber_encapsulate(public_key)
        self.assertEqual(self.service.kyber_decapsulate(ciphertext, private_key), secret)
        self.assertEqual(secret_keys_used_for_decapsulation(self.oqs), [private_key])

    def test_kyber_wrapper_passes_the_callers_private_key(self):
        public_key, private_key = Kyber.generate_keypair()
        ciphertext, secret = Kyber.encapsulate(public_key)
        self.assertEqual(Kyber.decapsulate(private_key, ciphertext), secret)
        self.assertEqual(secret_keys_used_for_decapsulation(self.oqs), [private_key])

    def test_shard_round_trip(self):
        public_key, private_key = self.service.generate_kyber_keypair()
        encrypted = self.service.encrypt_shard_hybrid(b'shard-bytes', public_key)
        stored = self.service.serialize_encrypted_shard(encrypted)
        restored = self.service.deserialize_encrypted_shard(stored)
        self.assertEqual(self.service.decrypt_shard_hybrid(restored, private_key), b'shard-bytes')

    def test_shard_does_not_open_with_another_private_key(self):
        public_key, _ = self.service.generate_kyber_keypair()
        _, other_private_key = self.service.generate_kyber_keypair()
        encrypted = self.service.encrypt_shard_hybrid(b'shard-bytes', public_key)
        with self.assertRaises(InvalidTag):
            self.service.decrypt_shard_hybrid(encrypted, other_private_key)


class QuantumCryptoServiceSimulationGateTests(SimpleTestCase):
    @DENY_SIM
    def test_simulation_refused_without_allow_simulation(self):
        with simulated_kem():
            with self.assertRaises(ImproperlyConfigured):
                QuantumCryptoService().generate_kyber_keypair()
            with self.assertRaises(ImproperlyConfigured):
                QuantumCryptoService().encrypt_shard_hybrid(b'x', b'P' * 1184)

    @ALLOW_SIM
    def test_simulation_round_trips_when_allowed(self):
        service = QuantumCryptoService()
        with simulated_kem():
            public_key, private_key = service.generate_kyber_keypair()
            encrypted = service.encrypt_shard_hybrid(b'shard-bytes', public_key)
            self.assertEqual(service.decrypt_shard_hybrid(encrypted, private_key), b'shard-bytes')


@DENY_SIM
class PasskeyPrimaryRecoveryKyberCustodyTests(SimpleTestCase):
    def setUp(self):
        self.oqs, patcher = fake_liboqs()
        patcher.start()
        self.addCleanup(patcher.stop)
        self.service = PasskeyPrimaryRecoveryService()
        self.recovery_key = self.service.generate_recovery_key()

    def test_round_trip_with_the_recovery_key(self):
        encrypted, metadata = self.service.encrypt_passkey_credential(CREDENTIAL, self.recovery_key)
        self.assertEqual(
            self.service.decrypt_passkey_credential(encrypted, self.recovery_key, metadata),
            CREDENTIAL,
        )

    def test_decapsulates_with_the_private_key_matching_the_stored_public_key(self):
        encrypted, metadata = self.service.encrypt_passkey_credential(CREDENTIAL, self.recovery_key)
        self.service.decrypt_passkey_credential(encrypted, self.recovery_key, metadata)

        stored_public_key = base64.b64decode(metadata['kyber_public_key'])
        (used_private_key,) = secret_keys_used_for_decapsulation(self.oqs)
        self.assertEqual(_public_from_secret(used_private_key), stored_public_key)

    def test_private_key_is_not_stored_in_the_clear(self):
        encrypted, metadata = self.service.encrypt_passkey_credential(CREDENTIAL, self.recovery_key)
        self.service.decrypt_passkey_credential(encrypted, self.recovery_key, metadata)
        (private_key,) = secret_keys_used_for_decapsulation(self.oqs)
        wrapped = base64.b64decode(metadata['kyber_private_key_wrapped'])
        self.assertNotIn(private_key[:64], wrapped)

    def test_wrong_recovery_key_is_rejected(self):
        encrypted, metadata = self.service.encrypt_passkey_credential(CREDENTIAL, self.recovery_key)
        with self.assertRaises(ValueError):
            self.service.decrypt_passkey_credential(
                encrypted, self.service.generate_recovery_key(), metadata,
            )
        self.assertEqual(secret_keys_used_for_decapsulation(self.oqs), [])

    def test_swapped_public_key_is_rejected(self):
        encrypted, metadata = self.service.encrypt_passkey_credential(CREDENTIAL, self.recovery_key)
        metadata['kyber_public_key'] = base64.b64encode(b'X' * 1184).decode()
        with self.assertRaises(ValueError):
            self.service.decrypt_passkey_credential(encrypted, self.recovery_key, metadata)

    def test_pre_fix_backup_reports_it_was_never_decryptable(self):
        encrypted, metadata = self.service.encrypt_passkey_credential(CREDENTIAL, self.recovery_key)
        metadata['version'] = 1
        with self.assertRaisesRegex(ValueError, 'never decryptable'):
            self.service.decrypt_passkey_credential(encrypted, self.recovery_key, metadata)

    def test_simulation_refusal_is_not_reported_as_bad_input(self):
        with simulated_kem():
            with self.assertRaises(ImproperlyConfigured):
                self.service.encrypt_passkey_credential(CREDENTIAL, self.recovery_key)

"""
Tests for behavioral_recovery's QuantumCryptoService.

CI does not install liboqs-python, so the real-Kyber path is exercised against
a mocked ``oqs`` module; what is asserted is that the real branch is taken,
with the right algorithm and the caller's private key. Findings F1, F2 and F7
in docs/pqc-hybrid-architecture-review.md.
"""

import importlib.util
import sys
import types
from unittest.mock import MagicMock, patch

from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase, override_settings

import behavioral_recovery.services.quantum_crypto_service as qcs

PUB = b'P' * 1184
PRIV = b'S' * 2400
KYBER_CT = b'C' * 1088
SHARED = b'K' * 32
EMBEDDING = [0.125, -0.5, 0.75]

ALLOW_SIM = override_settings(QUANTUM_CRYPTO={'ALLOW_SIMULATION': True})
DENY_SIM = override_settings(QUANTUM_CRYPTO={'ALLOW_SIMULATION': False})


def fake_oqs():
    """A stand-in for liboqs-python with a working KeyEncapsulation."""
    oqs = MagicMock(name='oqs')
    kem = oqs.KeyEncapsulation.return_value
    kem.__enter__.return_value = kem
    kem.generate_keypair.return_value = PUB
    kem.export_secret_key.return_value = PRIV
    kem.encap_secret.return_value = (KYBER_CT, SHARED)
    kem.decap_secret.return_value = SHARED
    return oqs, kem


def real_liboqs(oqs):
    return patch.multiple(qcs, create=True, LIBOQS_AVAILABLE=True, oqs=oqs)


def no_liboqs():
    return patch.multiple(qcs, create=True, LIBOQS_AVAILABLE=False, oqs=None)


class LiboqsImportTests(SimpleTestCase):
    def test_module_detects_liboqs_python_api(self):
        """F1: liboqs-python exports KeyEncapsulation and Signature, no KEM.
        With such a module importable, the service must report liboqs as
        available (the old ``from oqs import KEM`` always failed here)."""
        api = types.ModuleType('oqs')
        api.KeyEncapsulation = MagicMock(name='KeyEncapsulation')
        api.Signature = MagicMock(name='Signature')

        # Load a private copy so the real module's state is left untouched.
        spec = importlib.util.spec_from_file_location('_qcs_import_probe', qcs.__file__)
        probe = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, {'oqs': api}):
            spec.loader.exec_module(probe)

        self.assertTrue(probe.LIBOQS_AVAILABLE)
        self.assertIs(probe.oqs, api)


class RealKyberPathTests(SimpleTestCase):
    @DENY_SIM
    def test_round_trip_uses_key_encapsulation_and_supplied_private_key(self):
        """F1 + F2: the real branch is taken (even with simulation denied),
        and decapsulation is done by a KeyEncapsulation built from the
        private key the caller passed, not a service-wide object."""
        oqs, kem = fake_oqs()
        with real_liboqs(oqs):
            svc = qcs.QuantumCryptoService()

            public_key, private_key = svc.generate_keypair()
            self.assertEqual((public_key, private_key), (PUB, PRIV))
            oqs.KeyEncapsulation.assert_called_with('Kyber768')

            encrypted = svc.encrypt_behavioral_embedding(EMBEDDING, public_key)
            kem.encap_secret.assert_called_once_with(PUB)
            self.assertEqual(encrypted['algorithm'], 'kyber768-aes256gcm')
            self.assertTrue(svc.is_quantum_protected(encrypted))

            other_private_key = b'O' * 2400
            oqs.KeyEncapsulation.reset_mock()
            self.assertEqual(
                svc.decrypt_behavioral_embedding(encrypted, other_private_key),
                EMBEDDING,
            )
            oqs.KeyEncapsulation.assert_called_once_with('Kyber768', other_private_key)
            kem.decap_secret.assert_called_once_with(KYBER_CT)

    @ALLOW_SIM
    def test_wrong_shared_secret_does_not_decrypt(self):
        """The AES key really comes from the decapsulated secret."""
        oqs, kem = fake_oqs()
        with real_liboqs(oqs):
            svc = qcs.QuantumCryptoService()
            encrypted = svc.encrypt_behavioral_embedding(EMBEDDING, PUB)
            kem.decap_secret.return_value = b'X' * 32
            with self.assertRaises(Exception):
                svc.decrypt_behavioral_embedding(encrypted, PRIV)


class FailClosedTests(SimpleTestCase):
    """F7: without liboqs, the non-PQ fallback runs only when
    QUANTUM_CRYPTO['ALLOW_SIMULATION'] is True."""

    @DENY_SIM
    def test_key_generation_refused(self):
        with no_liboqs():
            with self.assertRaises(ImproperlyConfigured):
                qcs.QuantumCryptoService().generate_keypair()

    @DENY_SIM
    def test_encryption_refused(self):
        with no_liboqs():
            with self.assertRaises(ImproperlyConfigured):
                qcs.QuantumCryptoService().encrypt_behavioral_embedding(EMBEDDING, PUB)

    @DENY_SIM
    def test_decrypting_a_fallback_blob_refused(self):
        blob = {'algorithm': 'fallback-aes256gcm', 'nonce': '', 'aes_ciphertext': ''}
        with no_liboqs():
            with self.assertRaises(ImproperlyConfigured):
                qcs.QuantumCryptoService().decrypt_behavioral_embedding(blob, PRIV)

    @override_settings(QUANTUM_CRYPTO={})
    def test_missing_setting_fails_closed(self):
        with no_liboqs():
            with self.assertRaises(ImproperlyConfigured):
                qcs.QuantumCryptoService().generate_keypair()

    @ALLOW_SIM
    def test_fallback_still_available_when_simulation_allowed(self):
        with no_liboqs():
            svc = qcs.QuantumCryptoService()
            public_key, private_key = svc.generate_keypair()
            self.assertEqual(len(public_key), qcs.QuantumCryptoService.PUBLIC_KEY_SIZE)
            self.assertEqual(len(private_key), qcs.QuantumCryptoService.PRIVATE_KEY_SIZE)
            encrypted = svc.encrypt_behavioral_embedding(EMBEDDING, public_key)
            self.assertFalse(svc.is_quantum_protected(encrypted))

    @ALLOW_SIM
    def test_kyber_blob_without_liboqs_is_an_error_not_a_fallback_decrypt(self):
        """A stored Kyber blob is never handed to the fallback decryptor."""
        blob = {'algorithm': 'kyber768-aes256gcm', 'kyber_ciphertext': '',
                'nonce': '', 'aes_ciphertext': ''}
        with no_liboqs():
            with self.assertRaises(ImproperlyConfigured):
                qcs.QuantumCryptoService().decrypt_behavioral_embedding(blob, PRIV)


class CommitmentServiceDowngradeTests(SimpleTestCase):
    """The commitment service's "classical" path is plain base64. A refused
    or failed quantum encryption must not silently land there outside
    DEBUG/tests."""

    def _service(self, use_quantum=True):
        from behavioral_recovery.services.commitment_service import CommitmentService
        return CommitmentService(use_quantum=use_quantum, use_blockchain=False)

    @DENY_SIM
    def test_classical_path_refused_when_quantum_explicitly_off(self):
        with self.assertRaises(ImproperlyConfigured):
            self._service(use_quantum=False)._encrypt_embedding(EMBEDDING)

    @DENY_SIM
    def test_classical_path_refused_when_quantum_init_failed(self):
        """__init__ swallows an init error and sets use_quantum=False; that
        must not reopen the base64 path."""
        with patch('behavioral_recovery.services.commitment_service.get_quantum_crypto_service',
                   side_effect=RuntimeError('init failed')):
            service = self._service()
        self.assertFalse(service.use_quantum)
        with self.assertRaises(ImproperlyConfigured):
            service._encrypt_embedding(EMBEDDING)

    @override_settings(QUANTUM_CRYPTO={'ENABLED': False, 'ALLOW_SIMULATION': False})
    def test_explicit_feature_opt_out_uses_labelled_classical_path(self):
        """QUANTUM_CRYPTO_ENABLED=False is an operator opt-out (as for
        LatticeCryptoEngine): no Kyber, even with liboqs present, and no 500."""
        oqs, kem = fake_oqs()
        with real_liboqs(oqs):
            service = self._service()
            result = service._encrypt_embedding(EMBEDDING)
        self.assertFalse(service.use_quantum)
        self.assertIsInstance(result, bytes)
        oqs.KeyEncapsulation.assert_not_called()

    @DENY_SIM
    def test_refused_fallback_is_raised_not_downgraded_to_base64(self):
        with no_liboqs():
            with self.assertRaises(ImproperlyConfigured):
                self._service()._encrypt_embedding(EMBEDDING)

    @DENY_SIM
    def test_real_kyber_error_is_raised_not_downgraded_to_base64(self):
        oqs, kem = fake_oqs()
        kem.encap_secret.side_effect = RuntimeError('liboqs failure')
        with real_liboqs(oqs):
            with self.assertRaises(RuntimeError):
                self._service()._encrypt_embedding(EMBEDDING)

    @ALLOW_SIM
    def test_debug_keeps_the_existing_base64_fallback(self):
        oqs, kem = fake_oqs()
        kem.encap_secret.side_effect = RuntimeError('liboqs failure')
        with real_liboqs(oqs):
            result = self._service()._encrypt_embedding(EMBEDDING)
        self.assertIsInstance(result, bytes)

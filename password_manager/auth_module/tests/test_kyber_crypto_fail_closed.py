"""
F7 (docs/pqc-hybrid-architecture-review.md): ProductionKyber's simulated KEM
is not post-quantum (it is not even a KEM), so it may run only when
QUANTUM_CRYPTO['ALLOW_SIMULATION'] is True.
"""

from unittest.mock import patch

from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase, override_settings

import auth_module.services.kyber_crypto as kc


def simulated_kem():
    return patch.multiple(kc, LIBOQS_AVAILABLE=False, PQCRYPTO_AVAILABLE=False)


class SimulatedKyberFailClosedTests(SimpleTestCase):
    @override_settings(QUANTUM_CRYPTO={'ALLOW_SIMULATION': False})
    def test_every_simulated_operation_is_refused(self):
        with simulated_kem():
            kyber = kc.ProductionKyber()
            self.assertEqual(kyber.implementation, 'simulation')
            with self.assertRaises(ImproperlyConfigured):
                kyber.generate_keypair()
            with self.assertRaises(ImproperlyConfigured):
                kyber.encapsulate(b'P' * kyber.PUBLIC_KEY_SIZE)
            with self.assertRaises(ImproperlyConfigured):
                kyber.decapsulate(b'C' * kyber.CIPHERTEXT_SIZE, b'S' * kyber.PRIVATE_KEY_SIZE)

    @override_settings(QUANTUM_CRYPTO={'ALLOW_SIMULATION': False})
    def test_hybrid_encryption_refused(self):
        with simulated_kem():
            with self.assertRaises(ImproperlyConfigured):
                kc.HybridKyberEncryption().encrypt(b'secret', b'P' * 1184)

    @override_settings(QUANTUM_CRYPTO={})
    def test_missing_setting_fails_closed(self):
        with simulated_kem():
            with self.assertRaises(ImproperlyConfigured):
                kc.ProductionKyber().generate_keypair()

    @override_settings(QUANTUM_CRYPTO={'ALLOW_SIMULATION': True})
    def test_simulation_still_available_when_allowed(self):
        with simulated_kem():
            kyber = kc.ProductionKyber()
            public_key, private_key = kyber.generate_keypair()
            self.assertEqual(len(public_key), kyber.PUBLIC_KEY_SIZE)
            self.assertEqual(len(private_key), kyber.PRIVATE_KEY_SIZE)

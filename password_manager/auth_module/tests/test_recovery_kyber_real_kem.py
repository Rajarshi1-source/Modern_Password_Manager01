"""
F13 (docs/pqc-hybrid-architecture-review.md): auth_module's recovery KEM, and
its migration from round-3 Kyber768 to FIPS 203 ML-KEM-768.

``QuantumCryptoService`` used to return fresh ``os.urandom`` bytes from
keygen, encapsulation and decapsulation in every environment, and
passkey-primary recovery decapsulated with a "private key" hashed from the
recovery key. Neither could ever decrypt.

New data is ML-KEM-768. Kyber768 data written before the migration must
still decrypt, with Kyber768: the two KEMs have identical sizes but are not
interoperable, and decapsulating with the wrong one returns a wrong secret
instead of raising. So every stored artefact records its KEM.

CI does not install liboqs-python, so the real path runs against a fake
``oqs`` module that models both properties of liboqs that matter here:
decapsulation depends on the secret key (only the private key generated with
a public key recovers secrets encapsulated to it), and on the KEM (a
Kyber768 key or ciphertext used as ML-KEM-768 yields an unrelated secret).
"""

import base64
import hashlib
import json
import os
import secrets
from unittest.mock import MagicMock, patch

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase, override_settings

import auth_module.services.kyber_crypto as kc
from auth_module.services.kyber_cache import KyberCacheManager
from auth_module.services.passkey_primary_recovery_service import PasskeyPrimaryRecoveryService
from auth_module.services.quantum_crypto_service import Kyber, QuantumCryptoService

ALLOW_SIM = override_settings(QUANTUM_CRYPTO={'ALLOW_SIMULATION': True})
DENY_SIM = override_settings(QUANTUM_CRYPTO={'ALLOW_SIMULATION': False})

CREDENTIAL = {'credential_id': 'abc123', 'rp_id': 'localhost', 'user_id': 7}
FAKE_KEMS = ('ML-KEM-768', 'Kyber768')


def _public_from_secret(alg, secret_key):
    return hashlib.shake_256(alg.encode() + b'|pk|' + secret_key).digest(1184)


class _FakeKeyEncapsulation:
    """ML-KEM-768/Kyber768-shaped KEMs; a public key is a function of its
    secret key, and every output depends on the algorithm name."""

    instances = []

    def __init__(self, alg, secret_key=None):
        if alg not in FAKE_KEMS:
            raise ValueError(f'unexpected algorithm {alg!r}')
        self.alg = alg
        self.secret_key = secret_key
        self.freed = False
        _FakeKeyEncapsulation.instances.append(self)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.free()  # as liboqs-python's __exit__ does
        return False

    def free(self):
        self.freed = True

    def generate_keypair(self):
        self.secret_key = os.urandom(2400)
        return _public_from_secret(self.alg, self.secret_key)

    def export_secret_key(self):
        return self.secret_key

    def _secret(self, public_key, ciphertext):
        return hashlib.sha256(self.alg.encode() + b'|' + public_key + ciphertext).digest()

    def encap_secret(self, public_key):
        ciphertext = os.urandom(1088)
        return ciphertext, self._secret(public_key, ciphertext)

    def decap_secret(self, ciphertext):
        return self._secret(_public_from_secret(self.alg, self.secret_key), ciphertext)


def fake_liboqs():
    oqs = MagicMock(name='oqs')
    oqs.KeyEncapsulation.side_effect = _FakeKeyEncapsulation
    patcher = patch.multiple(kc, LIBOQS_AVAILABLE=True, PQCRYPTO_AVAILABLE=False, oqs=oqs)
    return oqs, patcher


def simulated_kem():
    return patch.multiple(kc, LIBOQS_AVAILABLE=False, PQCRYPTO_AVAILABLE=False)


def secret_keys_used_for_decapsulation(oqs):
    return [c.args[1] for c in oqs.KeyEncapsulation.call_args_list if len(c.args) > 1]


def algorithms_used_for_decapsulation(oqs):
    return [c.args[0] for c in oqs.KeyEncapsulation.call_args_list if len(c.args) > 1]


def legacy_kyber768_keypair():
    """A Kyber768 keypair, as liboqs made them before the migration.

    ProductionKyber no longer generates Kyber768 keys, so this goes to the
    (fake) liboqs directly.
    """
    with _FakeKeyEncapsulation('Kyber768') as kem:
        public_key = kem.generate_keypair()
        return public_key, kem.export_secret_key()


def legacy_v2_passkey_blob(service, credential, recovery_key):
    """A version-2 blob exactly as the pre-ML-KEM encrypt_passkey_credential
    wrote it: Kyber768, no 'kem' field, sk-wrap AAD b'kyber768-sk|' + H(pk).

    Written out here rather than via the service, so the test pins the old
    on-disk format instead of whatever the current code would produce.
    """
    public_key, private_key = legacy_kyber768_keypair()
    salt = secrets.token_bytes(32)
    master_key = service._derive_master_key_from_recovery_key(recovery_key, salt)
    sk_wrap_key = HKDF(
        algorithm=hashes.SHA256(), length=32, salt=None,
        info=b'passkey-primary-recovery-kyber-sk-wrap-v2', backend=default_backend(),
    ).derive(master_key)
    sk_iv = secrets.token_bytes(12)
    wrapped = AESGCM(sk_wrap_key).encrypt(
        sk_iv, private_key, b'kyber768-sk|' + hashlib.sha256(public_key).digest(),
    )
    with _FakeKeyEncapsulation('Kyber768') as kem:
        kyber_ciphertext, shared_secret = kem.encap_secret(public_key)
    hkdf_salt = secrets.token_bytes(16)
    aes_key = HKDF(
        algorithm=hashes.SHA256(), length=32, salt=hkdf_salt,
        info=b'passkey-primary-recovery-v1', backend=default_backend(),
    ).derive(master_key + shared_secret)
    iv = secrets.token_bytes(12)
    encryptor = Cipher(algorithms.AES(aes_key), modes.GCM(iv), backend=default_backend()).encryptor()
    encryptor.authenticate_additional_data(hashlib.sha256(master_key).digest() + public_key[:32])
    ciphertext = encryptor.update(json.dumps(credential).encode()) + encryptor.finalize()
    b64 = lambda b: base64.b64encode(b).decode()  # noqa: E731
    return ciphertext, {
        'version': 2,
        'algorithm': 'kyber768-aes256-gcm',
        'salt': b64(salt),
        'hkdf_salt': b64(hkdf_salt),
        'iv': b64(iv),
        'tag': b64(encryptor.tag),
        'kyber_ciphertext': b64(kyber_ciphertext),
        'kyber_public_key': b64(public_key),
        'kyber_private_key_wrapped': b64(wrapped),
        'kyber_private_key_iv': b64(sk_iv),
        'timestamp': 1,
    }


@DENY_SIM
class QuantumCryptoServiceRealKemTests(SimpleTestCase):
    def setUp(self):
        self.oqs, patcher = fake_liboqs()
        patcher.start()
        self.addCleanup(patcher.stop)
        self.service = QuantumCryptoService()

    def test_keypair_comes_from_liboqs_ml_kem_768(self):
        public_key, private_key = self.service.generate_kyber_keypair()
        self.oqs.KeyEncapsulation.assert_called_with('ML-KEM-768')
        self.assertEqual(public_key, _public_from_secret('ML-KEM-768', private_key))

    def test_no_new_kyber768_keys(self):
        with self.assertRaisesRegex(ValueError, 'legacy: no new keypairs'):
            self.service.generate_kyber_keypair('Kyber768')
        self.oqs.KeyEncapsulation.assert_not_called()

    def test_unknown_kem_is_refused(self):
        with self.assertRaisesRegex(ValueError, 'Unsupported KEM'):
            self.service.kyber_encapsulate(b'P' * 1184, 'Kyber1024')

    def test_decapsulation_reproduces_the_encapsulated_secret(self):
        public_key, private_key = self.service.generate_kyber_keypair()
        ciphertext, secret = self.service.kyber_encapsulate(public_key)
        self.assertEqual(
            self.service.kyber_decapsulate(ciphertext, private_key, kem='ML-KEM-768'), secret,
        )
        self.assertEqual(secret_keys_used_for_decapsulation(self.oqs), [private_key])

    def test_decapsulation_requires_the_kem(self):
        # No default: the KEM must come from the stored artefact.
        with self.assertRaises(TypeError):
            self.service.kyber_decapsulate(b'C' * 1088, b'S' * 2400)
        with self.assertRaises(TypeError):
            Kyber.decapsulate(b'S' * 2400, b'C' * 1088)

    def test_every_native_kem_is_freed(self):
        # free() is what cleanses liboqs's secret-key buffer; there is no __del__.
        _FakeKeyEncapsulation.instances.clear()
        public_key, private_key = self.service.generate_kyber_keypair()
        ciphertext, _ = self.service.kyber_encapsulate(public_key)
        self.service.kyber_decapsulate(ciphertext, private_key, kem='ML-KEM-768')
        self.assertEqual(len(_FakeKeyEncapsulation.instances), 3)
        self.assertTrue(all(kem.freed for kem in _FakeKeyEncapsulation.instances))

    def test_kyber_wrapper_passes_the_callers_private_key(self):
        public_key, private_key = Kyber.generate_keypair()
        ciphertext, secret = Kyber.encapsulate(public_key)
        self.assertEqual(Kyber.decapsulate(private_key, ciphertext, kem='ML-KEM-768'), secret)
        self.assertEqual(secret_keys_used_for_decapsulation(self.oqs), [private_key])

    def test_shard_round_trip_records_ml_kem(self):
        public_key, private_key = self.service.generate_kyber_keypair()
        encrypted = self.service.encrypt_shard_hybrid(b'shard-bytes', public_key)
        self.assertEqual(encrypted['algorithm'], 'ML-KEM-768-AES-256-GCM')
        stored = self.service.serialize_encrypted_shard(encrypted)
        restored = self.service.deserialize_encrypted_shard(stored)
        self.assertEqual(self.service.decrypt_shard_hybrid(restored, private_key), b'shard-bytes')
        self.assertEqual(algorithms_used_for_decapsulation(self.oqs), ['ML-KEM-768'])

    def test_legacy_kyber768_shard_still_decrypts_with_kyber768(self):
        public_key, private_key = legacy_kyber768_keypair()
        encrypted = self.service.encrypt_shard_hybrid(b'shard-bytes', public_key, 'Kyber768')
        self.assertEqual(encrypted['algorithm'], 'Kyber-768-AES-256-GCM')  # the pre-migration label
        restored = self.service.deserialize_encrypted_shard(
            self.service.serialize_encrypted_shard(encrypted)
        )
        self.assertEqual(self.service.decrypt_shard_hybrid(restored, private_key), b'shard-bytes')
        self.assertEqual(algorithms_used_for_decapsulation(self.oqs), ['Kyber768'])

    def test_kyber768_shard_relabelled_as_ml_kem_does_not_open(self):
        # The KEMs are not interoperable: the label, not the sizes, decides.
        public_key, private_key = legacy_kyber768_keypair()
        encrypted = self.service.encrypt_shard_hybrid(b'shard-bytes', public_key, 'Kyber768')
        encrypted['algorithm'] = 'ML-KEM-768-AES-256-GCM'
        with self.assertRaises(InvalidTag):
            self.service.decrypt_shard_hybrid(encrypted, private_key)

    def test_unknown_shard_algorithm_is_refused_not_guessed(self):
        public_key, private_key = self.service.generate_kyber_keypair()
        encrypted = self.service.encrypt_shard_hybrid(b'shard-bytes', public_key)
        encrypted['algorithm'] = 'Kyber-1024-AES-256-GCM'
        with self.assertRaisesRegex(ValueError, 'Unsupported recovery shard algorithm'):
            self.service.decrypt_shard_hybrid(encrypted, private_key)
        self.assertEqual(secret_keys_used_for_decapsulation(self.oqs), [])

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

    @ALLOW_SIM
    def test_simulation_is_not_interoperable_across_kems_either(self):
        service = QuantumCryptoService()
        with simulated_kem():
            public_key, private_key = service.generate_kyber_keypair()
            encrypted = service.encrypt_shard_hybrid(b'shard-bytes', public_key)
            encrypted['algorithm'] = 'Kyber-768-AES-256-GCM'
            with self.assertRaises(InvalidTag):
                service.decrypt_shard_hybrid(encrypted, private_key)


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

    def test_new_backup_is_version_3_and_records_ml_kem(self):
        encrypted, metadata = self.service.encrypt_passkey_credential(CREDENTIAL, self.recovery_key)
        self.assertEqual(metadata['version'], 3)
        self.assertEqual(metadata['kem'], 'ML-KEM-768')
        self.assertEqual(metadata['algorithm'], 'ml-kem-768-aes256-gcm')
        self.service.decrypt_passkey_credential(encrypted, self.recovery_key, metadata)
        self.assertEqual(algorithms_used_for_decapsulation(self.oqs), ['ML-KEM-768'])

    def test_legacy_kyber768_v2_backup_still_decrypts(self):
        encrypted, metadata = legacy_v2_passkey_blob(self.service, CREDENTIAL, self.recovery_key)
        self.assertEqual(
            self.service.decrypt_passkey_credential(encrypted, self.recovery_key, metadata),
            CREDENTIAL,
        )
        self.assertEqual(algorithms_used_for_decapsulation(self.oqs), ['Kyber768'])

    def test_v2_backup_ignores_a_kem_field_it_never_had(self):
        # Version 2 implies Kyber768; a 'kem' added later cannot redirect it.
        encrypted, metadata = legacy_v2_passkey_blob(self.service, CREDENTIAL, self.recovery_key)
        metadata['kem'] = 'ML-KEM-768'
        self.assertEqual(
            self.service.decrypt_passkey_credential(encrypted, self.recovery_key, metadata),
            CREDENTIAL,
        )
        self.assertEqual(algorithms_used_for_decapsulation(self.oqs), ['Kyber768'])

    def test_v3_relabelled_to_another_kem_is_rejected_before_decapsulation(self):
        # The KEM name is bound into the private-key wrap's AAD.
        encrypted, metadata = self.service.encrypt_passkey_credential(CREDENTIAL, self.recovery_key)
        metadata['kem'] = 'Kyber768'
        with self.assertRaises(ValueError):
            self.service.decrypt_passkey_credential(encrypted, self.recovery_key, metadata)
        self.assertEqual(secret_keys_used_for_decapsulation(self.oqs), [])

    def test_v3_with_unknown_or_missing_kem_is_rejected(self):
        encrypted, metadata = self.service.encrypt_passkey_credential(CREDENTIAL, self.recovery_key)
        for kem in ('Kyber1024', None):
            bad = dict(metadata, kem=kem)
            with self.assertRaisesRegex(ValueError, 'Unsupported recovery backup KEM'):
                self.service.decrypt_passkey_credential(encrypted, self.recovery_key, bad)
        del metadata['kem']
        with self.assertRaisesRegex(ValueError, 'Unsupported recovery backup KEM'):
            self.service.decrypt_passkey_credential(encrypted, self.recovery_key, metadata)

    def test_decapsulates_with_the_private_key_matching_the_stored_public_key(self):
        encrypted, metadata = self.service.encrypt_passkey_credential(CREDENTIAL, self.recovery_key)
        self.service.decrypt_passkey_credential(encrypted, self.recovery_key, metadata)

        stored_public_key = base64.b64decode(metadata['kyber_public_key'])
        (used_private_key,) = secret_keys_used_for_decapsulation(self.oqs)
        self.assertEqual(_public_from_secret('ML-KEM-768', used_private_key), stored_public_key)

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

    def test_missing_version_is_a_pre_fix_backup(self):
        encrypted, metadata = self.service.encrypt_passkey_credential(CREDENTIAL, self.recovery_key)
        del metadata['version']
        with self.assertRaisesRegex(ValueError, 'never decryptable'):
            self.service.decrypt_passkey_credential(encrypted, self.recovery_key, metadata)

    def test_newer_version_is_unsupported_not_never_decryptable(self):
        encrypted, metadata = self.service.encrypt_passkey_credential(CREDENTIAL, self.recovery_key)
        metadata['version'] = self.service.BLOB_VERSION + 1
        with self.assertRaisesRegex(ValueError, 'Unsupported recovery backup version'):
            self.service.decrypt_passkey_credential(encrypted, self.recovery_key, metadata)

    def test_non_integer_version_is_unsupported(self):
        encrypted, metadata = self.service.encrypt_passkey_credential(CREDENTIAL, self.recovery_key)
        for version in ('3', [3], True):
            bad = dict(metadata, version=version)
            with self.assertRaisesRegex(ValueError, 'Unsupported recovery backup version'):
                self.service.decrypt_passkey_credential(encrypted, self.recovery_key, bad)

    def test_simulation_refusal_is_not_reported_as_bad_input(self):
        with simulated_kem():
            with self.assertRaises(ImproperlyConfigured):
                self.service.encrypt_passkey_credential(CREDENTIAL, self.recovery_key)


@DENY_SIM
class HybridKyberEncryptionKemLabelTests(SimpleTestCase):
    """/api/kyber/* blobs (HybridKyberEncryption) carry their KEM in 'algorithm'."""

    def setUp(self):
        self.oqs, patcher = fake_liboqs()
        patcher.start()
        self.addCleanup(patcher.stop)
        self.hybrid = kc.HybridKyberEncryption(allow_simulation=False)

    def test_new_blob_is_labelled_ml_kem_and_round_trips(self):
        public_key, private_key = kc.ProductionKyber().generate_keypair()
        blob = self.hybrid.encrypt(b'secret', public_key)
        self.assertEqual(blob['algorithm'], 'ML-KEM-768-AES256-GCM')
        self.assertEqual(self.hybrid.decrypt(blob, private_key), b'secret')
        self.assertEqual(algorithms_used_for_decapsulation(self.oqs), ['ML-KEM-768'])

    def test_kyber768_blob_and_unlabelled_blob_decrypt_with_kyber768(self):
        public_key, private_key = legacy_kyber768_keypair()
        blob = self.hybrid.encrypt(b'secret', public_key, kem='Kyber768')
        self.assertEqual(blob['algorithm'], 'Kyber768-AES256-GCM')  # the pre-migration label
        self.assertEqual(self.hybrid.decrypt(blob, private_key), b'secret')
        # The decrypt endpoint never forwarded the label before, so a client
        # replaying an old blob may not send one: that is Kyber768.
        unlabelled = {k: v for k, v in blob.items() if k != 'algorithm'}
        self.assertEqual(self.hybrid.decrypt(unlabelled, private_key), b'secret')

    def test_encapsulating_with_the_wrong_kem_makes_an_unopenable_blob(self):
        # Why callers must pass the key's KEM (KyberKeyPair.algorithm).
        public_key, private_key = legacy_kyber768_keypair()
        blob = self.hybrid.encrypt(b'secret', public_key)  # default ML-KEM-768
        with self.assertRaises(InvalidTag):
            self.hybrid.decrypt(blob, private_key)

    def test_unknown_label_is_refused(self):
        with self.assertRaisesRegex(ValueError, 'Unsupported hybrid encryption algorithm'):
            self.hybrid.decrypt({'algorithm': 'Kyber1024-AES256-GCM'}, b'S' * 2400)


class KyberPublicKeyCacheKemTests(SimpleTestCase):
    def test_cached_public_key_carries_its_kem(self):
        cache = KyberCacheManager()
        cache.cache_public_key(41, b'P' * 1184, algorithm='Kyber768')
        self.assertEqual(cache.get_cached_public_key_entry(41), (b'P' * 1184, 'Kyber768'))
        self.assertEqual(cache.get_cached_public_key(41), b'P' * 1184)

    def test_kem_is_required_when_caching(self):
        with self.assertRaises(TypeError):
            KyberCacheManager().cache_public_key(42, b'P' * 1184)

    def test_pre_migration_entry_is_never_read(self):
        # Old entries were a bare base64 Kyber768 key under 'kyber:pubkey:'.
        cache = KyberCacheManager()
        cache._l1_set('kyber:pubkey:43', base64.b64encode(b'P' * 1184).decode(), 60)
        self.assertIsNone(cache.get_cached_public_key_entry(43))

    def test_batch_readers_and_writers_share_the_entry_format(self):
        cache = KyberCacheManager()
        cache.cache_public_key(44, b'A' * 1184, algorithm='Kyber768')
        cache.set_many_public_keys({45: (b'B' * 1184, 'ML-KEM-768')})
        self.assertEqual(
            cache.get_many_public_keys([44, 45, 46]),
            {44: (b'A' * 1184, 'Kyber768'), 45: (b'B' * 1184, 'ML-KEM-768'), 46: None},
        )
        self.assertEqual(cache.get_cached_public_key_entry(45), (b'B' * 1184, 'ML-KEM-768'))

    def test_cached_keypair_reports_its_kem(self):
        cache = KyberCacheManager()
        cache.cache_keypair(47, b'P' * 1184, b'S' * 2400, algorithm='Kyber768')
        self.assertEqual(cache.get_cached_keypair(47)['algorithm'], 'Kyber768')


@DENY_SIM
class KemInputLengthTests(SimpleTestCase):
    """liboqs-python copies inputs with create_string_buffer(value, length),
    which zero-pads a short value silently. ProductionKyber must refuse wrong
    lengths before any backend sees them."""

    def setUp(self):
        self.oqs, patcher = fake_liboqs()
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_wrong_length_inputs_are_refused_before_liboqs(self):
        kem = kc.ProductionKyber()
        cases = [
            (lambda: kem.encapsulate(b'P' * 1183), 'public key must be 1184 bytes, got 1183'),
            (lambda: kem.encapsulate(b'P' * 1185), 'public key must be 1184 bytes, got 1185'),
            (lambda: kem.decapsulate(b'C' * 1087, b'S' * 2400), 'ciphertext must be 1088 bytes'),
            (lambda: kem.decapsulate(b'C' * 1088, b'S' * 2399), 'private key must be 2400 bytes'),
            (lambda: kem.encapsulate('P' * 1184), 'must be bytes'),
        ]
        for call, message in cases:
            with self.assertRaisesRegex(ValueError, message):
                call()
        self.oqs.KeyEncapsulation.assert_not_called()

    def test_simulation_checks_lengths_too(self):
        with simulated_kem(), override_settings(QUANTUM_CRYPTO={'ALLOW_SIMULATION': True}):
            with self.assertRaisesRegex(ValueError, 'ciphertext must be 1088 bytes'):
                kc.ProductionKyber().decapsulate(b'C' * 10, b'S' * 2400)


class PasskeyRecoveryKeyVerificationTests(SimpleTestCase):
    def test_key_is_accepted_as_displayed_and_compacted(self):
        from auth_module.passkey_primary_recovery_models import PasskeyRecoveryBackup
        service = PasskeyPrimaryRecoveryService()
        key = service.generate_recovery_key()
        backup = PasskeyRecoveryBackup(recovery_key_hash=service.hash_recovery_key(key))
        self.assertIn('-', key)
        self.assertTrue(backup.verify_recovery_key(key))
        self.assertTrue(backup.verify_recovery_key(key.replace('-', '')))
        self.assertTrue(backup.verify_recovery_key(key.lower()))
        self.assertFalse(backup.verify_recovery_key(service.generate_recovery_key()))
        self.assertFalse(backup.verify_recovery_key(None))


class PqcryptoSelectionTests(SimpleTestCase):
    """pqcrypto is used only for a KEM it actually provides."""

    def test_pqcrypto_without_ml_kem_is_not_selected_for_ml_kem(self):
        with patch.multiple(kc, LIBOQS_AVAILABLE=False, PQCRYPTO_AVAILABLE=True,
                            _PQCRYPTO_KEMS={'Kyber768': MagicMock()}):
            ml_kem = kc.ProductionKyber(allow_simulation=True)
            self.assertEqual(ml_kem.implementation, 'simulation')
            self.assertFalse(ml_kem.is_real_pqc)
            self.assertEqual(kc.ProductionKyber(algorithm='Kyber768').implementation, 'pqcrypto')
            with self.assertRaises(RuntimeError):
                kc.ProductionKyber(allow_simulation=False)

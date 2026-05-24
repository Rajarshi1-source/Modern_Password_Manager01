"""
Tests for the blockchain KeyProvider abstraction (C7 follow-up).

Covers:
* EnvKeyProvider reads the env var, exposes address, signs round-trip.
* EnvKeyProvider gracefully reports unavailable when the env var is unset.
* KmsKeyProvider uses an injected boto3 client (so no network in tests),
  derives the EOA address from the SPKI public key, and produces a
  recoverable Ethereum signature for an EIP-191 message.
* The `get_key_provider()` factory honours the BLOCKCHAIN_KEY_PROVIDER
  setting and the singleton cache.
"""

from __future__ import annotations

import os
from unittest import mock

import pytest
from django.test import override_settings

from blockchain.services import key_provider as kp_mod
from blockchain.services.key_provider import (
    EnvKeyProvider,
    KmsKeyProvider,
    get_key_provider,
    reset_key_provider_for_tests,
)


# A deterministic 32-byte test key — DO NOT USE FOR REAL VALUE.
TEST_PRIV_HEX = '0x' + 'ab' * 32


@pytest.fixture(autouse=True)
def _reset_singleton():
    reset_key_provider_for_tests()
    yield
    reset_key_provider_for_tests()


# ---------------------------------------------------------------------------
# EnvKeyProvider
# ---------------------------------------------------------------------------

class TestEnvKeyProvider:
    def test_reports_unavailable_when_env_missing(self, monkeypatch):
        monkeypatch.delenv('BLOCKCHAIN_PRIVATE_KEY', raising=False)
        p = EnvKeyProvider()
        assert p.is_available is False
        assert p.provider_kind == 'env'
        with pytest.raises(RuntimeError):
            _ = p.address

    def test_exposes_address_and_signs_message(self, monkeypatch):
        from eth_account import Account
        from eth_account.messages import encode_defunct
        monkeypatch.setenv('BLOCKCHAIN_PRIVATE_KEY', TEST_PRIV_HEX)

        p = EnvKeyProvider()
        expected_addr = Account.from_key(TEST_PRIV_HEX).address
        assert p.is_available is True
        assert p.address == expected_addr

        msg = encode_defunct(text="hello world")
        signed = p.sign_message(msg)
        # Round-trip: recover the signer and check it matches.
        recovered = Account.recover_message(msg, signature=signed.signature)
        assert recovered == expected_addr


# ---------------------------------------------------------------------------
# KmsKeyProvider — uses a real local key behind a fake KMS client so we
# get end-to-end coverage without an AWS round trip.
# ---------------------------------------------------------------------------

class _FakeKmsClient:
    """
    Pretends to be `boto3.client('kms')` backed by a local secp256k1
    key. Implements just enough of the surface that KmsKeyProvider uses:
    `get_public_key` and `sign`.
    """

    def __init__(self, hex_private_key: str):
        from eth_keys.datatypes import PrivateKey
        self._pk = PrivateKey(bytes.fromhex(hex_private_key.removeprefix('0x')))

    def get_public_key(self, KeyId):  # noqa: N803 — boto3 style
        # Build a real DER-encoded SubjectPublicKeyInfo so the provider's
        # SPKI parser exercises the realistic format.
        raw_pub = b'\x04' + self._pk.public_key.to_bytes()
        # Minimal SPKI for secp256k1 — the parser only needs the trailing
        # 65 bytes to be the uncompressed point. A real KMS response is
        # 88 bytes; we pad the front with a constant 23-byte header.
        header = bytes(23)
        return {'PublicKey': header + raw_pub}

    def sign(self, KeyId, Message, MessageType, SigningAlgorithm):  # noqa: N803
        assert MessageType == 'DIGEST'
        assert SigningAlgorithm == 'ECDSA_SHA_256'
        sig = self._pk.sign_msg_hash(Message)
        # Re-encode to DER. KMS always returns DER-encoded sigs.
        return {'Signature': _to_der(sig.r, sig.s)}


def _to_der(r: int, s: int) -> bytes:
    def _enc(n: int) -> bytes:
        b = n.to_bytes((n.bit_length() + 7) // 8 or 1, 'big')
        # Prepend 0x00 if high bit set (DER positive-integer rule).
        if b[0] & 0x80:
            b = b'\x00' + b
        return b'\x02' + bytes([len(b)]) + b
    body = _enc(r) + _enc(s)
    return b'\x30' + bytes([len(body)]) + body


class TestKmsKeyProvider:
    def test_derives_address_from_kms_public_key(self):
        from eth_account import Account
        fake = _FakeKmsClient(TEST_PRIV_HEX)
        p = KmsKeyProvider('arn:test', boto_client=fake)
        assert p.is_available is True
        assert p.provider_kind == 'kms'
        # The address must match what eth_account derives locally from
        # the same private key — proves the SPKI parser + keccak path
        # is bit-for-bit equivalent.
        assert p.address == Account.from_key(TEST_PRIV_HEX).address

    def test_sign_message_round_trip(self):
        from eth_account import Account
        from eth_account.messages import encode_defunct

        fake = _FakeKmsClient(TEST_PRIV_HEX)
        p = KmsKeyProvider('arn:test', boto_client=fake)

        msg = encode_defunct(text="kms signed hello")
        signed = p.sign_message(msg)

        # Recover the signer from the KMS-produced signature using
        # eth_account's standard path. If recovery_id selection, s-low
        # normalisation, or v calculation were off, this would not
        # recover to the same address.
        recovered = Account.recover_message(msg, signature=signed.signature)
        assert recovered == p.address

    def test_requires_key_id(self):
        with pytest.raises(ValueError):
            KmsKeyProvider('', boto_client=_FakeKmsClient(TEST_PRIV_HEX))


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

class TestGetKeyProvider:
    @override_settings(BLOCKCHAIN_KEY_PROVIDER='env')
    def test_env_is_default(self, monkeypatch):
        monkeypatch.setenv('BLOCKCHAIN_PRIVATE_KEY', TEST_PRIV_HEX)
        p = get_key_provider()
        assert isinstance(p, EnvKeyProvider)
        # Singleton: second call returns same instance.
        assert get_key_provider() is p

    @override_settings(BLOCKCHAIN_KEY_PROVIDER='kms', BLOCKCHAIN_KMS_KEY_ID='arn:test')
    def test_kms_selection_requires_boto3(self, monkeypatch):
        # Force the import path that boto3 doesn't exist to verify the
        # error surface is friendly. We monkey-patch the local symbol.
        with mock.patch.dict('sys.modules', {'boto3': None}):
            with pytest.raises(Exception):
                # ImportError is wrapped into a RuntimeError by the provider.
                get_key_provider()

    @override_settings(BLOCKCHAIN_KEY_PROVIDER='unknown_thing')
    def test_unknown_value_raises(self):
        with pytest.raises(ValueError):
            get_key_provider()

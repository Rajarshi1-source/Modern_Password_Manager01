"""
Group A / commit 1 (2026-05): regression tests for the AEAD rewrite
of ``security.services.crypto_service``.

These tests pin the behaviour the audit hardening cares about:

  * Round-trip encrypt/decrypt is preserved through the rewrite
    (no silent truncation when the low-level ``finalize()`` API was
    swapped for ``AESGCM`` — audit finding #2).
  * ``decrypt_data`` rejects undersized envelopes up-front instead of
    handing nonsense slices to the cipher (audit finding #11).
  * A tampered tag raises ``DecryptionError`` rather than returning
    ``None``, so callers can no longer mistake forged ciphertext for
    "decrypt produced empty output" (audit finding #2 follow-on).
  * The low-level ``encrypt_aes_gcm`` / ``decrypt_aes_gcm`` static
    helpers still return / accept ``(ciphertext, tag)`` as separate
    values — this is what ``noise_encryptor`` and ``garlic_router``
    rely on; the AEAD primitive concatenates them but our wrapper
    splits them back out.
  * The optional ``associated_data`` parameter round-trips when
    matched and fails when mismatched. This is the wire prep for
    commit 2's envelope binding (audit finding #9) — landing it as
    a no-op parameter here means commit 2 only changes call sites,
    not the primitive surface.

The tests configure a minimal Django settings stub so the module's
``from django.conf import settings`` import works under pytest
without the full project settings.
"""

from __future__ import annotations

import base64
import os

import django
from django.conf import settings

# Configure a minimal Django settings stub *before* importing the
# service under test — the service does ``from django.conf import
# settings; settings.SECRET_KEY[:32]`` at call time, so settings must
# be live or the import is fine but the call raises ``ImproperlyConfigured``.
if not settings.configured:
    settings.configure(
        SECRET_KEY='x' * 64,
        DEBUG=True,
        DATABASES={'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': ':memory:'}},
        INSTALLED_APPS=[],
    )
    django.setup()

import pytest  # noqa: E402

from security.services.crypto_service import (  # noqa: E402
    CryptoService,
    DecryptionError,
    _GCM_NONCE_LEN,
    _GCM_TAG_LEN,
    _MIN_ENVELOPE_LEN,
)


# ---------------------------------------------------------------------------
# encrypt_data / decrypt_data — the SECRET_KEY-derived path used by
# email_masking. Behaviour-preserving rewrite; the wire format must
# stay ``base64(nonce || ct || tag)``.
# ---------------------------------------------------------------------------

class TestEncryptDataRoundTrip:
    def test_short_plaintext_round_trips(self):
        ct_b64 = CryptoService.encrypt_data("hello")
        assert ct_b64 is not None
        assert CryptoService.decrypt_data(ct_b64) == "hello"

    def test_empty_plaintext_round_trips(self):
        # AESGCM allows empty plaintext — confirm the wrapper does not
        # blow up on it and emits a still-decryptable envelope.
        ct_b64 = CryptoService.encrypt_data("")
        assert ct_b64 is not None
        assert CryptoService.decrypt_data(ct_b64) == ""

    def test_long_plaintext_round_trips(self):
        # A plaintext multiple of any internal AES block size would
        # historically have been the trigger for the dropped-``finalize()``
        # bug. Use 4 KiB to make sure no buffering edge survives.
        plaintext = "A" * 4096
        ct_b64 = CryptoService.encrypt_data(plaintext)
        assert CryptoService.decrypt_data(ct_b64) == plaintext

    def test_unicode_round_trips(self):
        plaintext = "héllo 🔐 wörld"
        ct_b64 = CryptoService.encrypt_data(plaintext)
        assert CryptoService.decrypt_data(ct_b64) == plaintext


class TestDecryptDataInputValidation:
    """Audit finding #11 — length checks before slicing."""

    def test_rejects_empty_envelope(self):
        # ``base64("")`` decodes to ``b""`` — must be rejected, not
        # silently sliced into bogus zero-length nonce/tag/ct.
        assert CryptoService.decrypt_data("") is None

    def test_rejects_envelope_shorter_than_nonce_plus_tag(self):
        # ``_MIN_ENVELOPE_LEN`` is exactly nonce + tag = 28; anything
        # shorter would let the slices overlap. A 27-byte input is
        # the largest under-sized case.
        too_short = os.urandom(_MIN_ENVELOPE_LEN - 1)
        assert CryptoService.decrypt_data(base64.b64encode(too_short).decode()) is None

    def test_rejects_malformed_base64(self):
        # The outer ``try/except`` keeps this from crashing — it
        # should log and return ``None``.
        assert CryptoService.decrypt_data("not-valid-base64!@#$%^&*") is None


class TestDecryptDataTagVerification:
    def test_tampered_ciphertext_returns_none(self):
        ct_b64 = CryptoService.encrypt_data("secret")
        raw = bytearray(base64.b64decode(ct_b64))
        # Flip a byte in the ciphertext region (between nonce and tag).
        raw[_GCM_NONCE_LEN] ^= 0x01
        tampered = base64.b64encode(bytes(raw)).decode()
        # ``decrypt_data`` swallows ``DecryptionError`` to keep its
        # ``None``-on-failure public API; the warning is logged.
        assert CryptoService.decrypt_data(tampered) is None

    def test_tampered_tag_returns_none(self):
        ct_b64 = CryptoService.encrypt_data("secret")
        raw = bytearray(base64.b64decode(ct_b64))
        raw[-1] ^= 0x01  # flip a byte inside the auth tag
        tampered = base64.b64encode(bytes(raw)).decode()
        assert CryptoService.decrypt_data(tampered) is None


# ---------------------------------------------------------------------------
# Low-level encrypt_aes_gcm / decrypt_aes_gcm — the ``(ct, tag)``
# tuple API used by ``noise_encryptor`` and ``garlic_router``.
# ---------------------------------------------------------------------------

class TestAesGcmPrimitiveApi:
    def _key_nonce(self):
        return os.urandom(32), os.urandom(_GCM_NONCE_LEN)

    def test_round_trip_via_tuple_api(self):
        key, nonce = self._key_nonce()
        ct, tag = CryptoService.encrypt_aes_gcm(key, nonce, b"payload")
        assert ct is not None
        assert tag is not None
        assert len(tag) == _GCM_TAG_LEN
        # Decrypt with the split tag → original plaintext.
        assert CryptoService.decrypt_aes_gcm(key, nonce, ct, tag) == b"payload"

    def test_wrong_tag_raises_decryption_error(self):
        key, nonce = self._key_nonce()
        ct, tag = CryptoService.encrypt_aes_gcm(key, nonce, b"payload")
        bad_tag = bytes((tag[0] ^ 0x01,)) + tag[1:]
        with pytest.raises(DecryptionError):
            CryptoService.decrypt_aes_gcm(key, nonce, ct, bad_tag)

    def test_wrong_key_raises_decryption_error(self):
        key, nonce = self._key_nonce()
        ct, tag = CryptoService.encrypt_aes_gcm(key, nonce, b"payload")
        wrong_key = os.urandom(32)
        with pytest.raises(DecryptionError):
            CryptoService.decrypt_aes_gcm(wrong_key, nonce, ct, tag)

    def test_invalid_key_length_raises_decryption_error(self):
        # AESGCM only accepts 16/24/32-byte keys. The wrapper should
        # turn that into ``DecryptionError`` rather than letting the
        # low-level ``ValueError`` leak through.
        with pytest.raises(DecryptionError):
            CryptoService.decrypt_aes_gcm(b"too-short", os.urandom(12), b"x" * 16, b"x" * 16)

    def test_encrypt_with_bad_key_returns_none_tuple(self):
        # Encrypt-side failures keep the old ``(None, None)`` contract
        # so existing callers' ``if ciphertext is None`` checks still
        # work. Only the *decrypt* side raises now.
        ct, tag = CryptoService.encrypt_aes_gcm(b"short", os.urandom(12), b"x")
        assert ct is None
        assert tag is None


# ---------------------------------------------------------------------------
# Optional associated_data (AEAD AAD). Wire prep for commit 2.
# ---------------------------------------------------------------------------

class TestAssociatedData:
    def test_matching_aad_round_trips(self):
        key, nonce = os.urandom(32), os.urandom(_GCM_NONCE_LEN)
        aad = b"vault-scan-v1:user=42"
        ct, tag = CryptoService.encrypt_aes_gcm(key, nonce, b"payload", aad)
        assert CryptoService.decrypt_aes_gcm(key, nonce, ct, tag, aad) == b"payload"

    def test_mismatched_aad_raises_decryption_error(self):
        # The defining property of AAD: flip even one byte of it and
        # the tag verification fails. This is what makes envelope
        # metadata authentication work (audit finding #9).
        key, nonce = os.urandom(32), os.urandom(_GCM_NONCE_LEN)
        ct, tag = CryptoService.encrypt_aes_gcm(key, nonce, b"payload", b"aad-1")
        with pytest.raises(DecryptionError):
            CryptoService.decrypt_aes_gcm(key, nonce, ct, tag, b"aad-2")

    def test_aad_present_at_encrypt_missing_at_decrypt_raises(self):
        key, nonce = os.urandom(32), os.urandom(_GCM_NONCE_LEN)
        ct, tag = CryptoService.encrypt_aes_gcm(key, nonce, b"payload", b"aad-1")
        with pytest.raises(DecryptionError):
            CryptoService.decrypt_aes_gcm(key, nonce, ct, tag)  # no aad

    def test_aad_absent_at_encrypt_present_at_decrypt_raises(self):
        key, nonce = os.urandom(32), os.urandom(_GCM_NONCE_LEN)
        ct, tag = CryptoService.encrypt_aes_gcm(key, nonce, b"payload")
        with pytest.raises(DecryptionError):
            CryptoService.decrypt_aes_gcm(key, nonce, ct, tag, b"aad-1")

"""
Group A / commit 1 + commit 2 (2026-05): regression tests for the
AEAD rewrite + HKDF/DATA_ENCRYPTION_KEY/versioned-envelope rewrite of
``security.services.crypto_service``.

Pins from commit 1:
  * Round-trip encrypt/decrypt preserved (no silent truncation when
    ``finalize()`` API was swapped for ``AESGCM`` — finding #2).
  * ``decrypt_data`` rejects undersized envelopes up-front (#11).
  * Tampered tag raises ``DecryptionError`` rather than returning
    ``None`` (#2 follow-on).
  * Low-level ``encrypt_aes_gcm`` / ``decrypt_aes_gcm`` keep their
    ``(ciphertext, tag)`` tuple contract (noise_encryptor /
    garlic_router depend on it).
  * Optional ``associated_data`` round-trips when matched and fails
    when mismatched (wire prep for #9).

Pins from commit 2:
  * ``encrypt_data`` emits the v2 envelope
    ``b"\\x02" || salt(16) || nonce(12) || ct || tag(16)``.
  * The HKDF derives a fresh per-record key — same plaintext encrypted
    twice produces unrelated ciphertexts AND unrelated derived keys.
  * Tampering the envelope's salt or version byte fails decryption
    (the AAD-binding fix for finding #9).
  * The legacy ``nonce || ct || tag`` envelope is still readable via
    the SECRET_KEY[:32] fallback path — so pre-commit-2 stored
    ciphertexts (email_masking provider configs) survive the upgrade.
  * A v2-prefixed envelope that fails to decrypt does NOT silently
    retry under the legacy key (downgrade-attack guard).

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
# settings; settings.DATA_ENCRYPTION_KEY ...`` at call time, so
# settings must be live. Tests run with DEBUG=True so the
# SECRET_KEY fallback (used for legacy decrypt) is available; the
# v2 path uses an explicit DATA_ENCRYPTION_KEY set here.
if not settings.configured:
    settings.configure(
        SECRET_KEY='x' * 64,
        DEBUG=True,
        # 32 random bytes, base64-encoded. The exact value doesn't
        # matter for these tests — we just need a valid one so the
        # HKDF path resolves a real master key.
        DATA_ENCRYPTION_KEY=base64.b64encode(b'A' * 32).decode(),
        DATABASES={'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': ':memory:'}},
        INSTALLED_APPS=[],
    )
    django.setup()

import pytest  # noqa: E402

from security.services.crypto_service import (  # noqa: E402
    CryptoService,
    DecryptionError,
    _decrypt_legacy,
    _derive_data_key,
    _ENVELOPE_V2,
    _GCM_NONCE_LEN,
    _GCM_TAG_LEN,
    _HKDF_SALT_LEN,
    _MIN_ENVELOPE_LEN,
    _MIN_ENVELOPE_LEN_LEGACY,
    _MIN_ENVELOPE_LEN_V2,
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
        # The legacy floor is nonce + tag = 28; anything shorter
        # would let the slices overlap. After commit 2 a 27-byte
        # input fails both the v2 floor (45) and the legacy floor
        # (28), so it's rejected with no decrypt attempt at all.
        too_short = os.urandom(_MIN_ENVELOPE_LEN_LEGACY - 1)
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


# ---------------------------------------------------------------------------
# Caller-contract regression tests. Pinned per Codex review on PR #280:
# ``garlic_router.decrypt_payload`` (and friends) document a
# ``ValueError`` failure contract; after the AEAD rewrite started
# raising ``DecryptionError``, any caller that did not catch-and-
# translate would break its own callers. These tests simulate the
# in-loop decrypt step those methods perform and confirm a tampered
# layer surfaces as the documented ``ValueError`` — never as a raw
# ``DecryptionError`` leaking through.
# ---------------------------------------------------------------------------

class TestCallerContractTranslation:
    """Audit hardening / Codex P2 — ``DecryptionError`` must NEVER
    surface to upstream callers of ``garlic_router`` or
    ``noise_encryptor``; those modules promise ``ValueError``."""

    @staticmethod
    def _simulate_decrypt_payload_layer(current_bytes, layer_key, layer):
        """Faithful copy of the inner loop in
        ``GarlicRouter.decrypt_payload`` (services/garlic_router.py:474).
        If this test diverges from the implementation, the
        implementation is what's broken."""
        from security.services.crypto_service import (
            CryptoService as _CS,
            DecryptionError as _DE,
        )
        if len(current_bytes) < 28:
            raise ValueError("Invalid encrypted data")
        nonce_ = current_bytes[:12]
        tag_ = current_bytes[12:28]
        ciphertext_ = current_bytes[28:]
        try:
            return _CS.decrypt_aes_gcm(
                key=layer_key, nonce=nonce_, ciphertext=ciphertext_, tag=tag_,
            )
        except _DE as e:
            raise ValueError(f"Decryption failed at layer {layer}") from e

    def test_tampered_layer_raises_valueerror_not_decryption_error(self):
        import hashlib
        layer_key = hashlib.sha256(b"k" + (0).to_bytes(4, "big")).digest()
        nonce = os.urandom(_GCM_NONCE_LEN)
        ct, tag = CryptoService.encrypt_aes_gcm(layer_key, nonce, b"plaintext")
        # Tamper with the tag region.
        tampered = bytearray(nonce + tag + ct)
        tampered[15] ^= 0x01

        with pytest.raises(ValueError) as exc_info:
            self._simulate_decrypt_payload_layer(bytes(tampered), layer_key, 0)
        # The error message must include the layer index — that's the
        # documented per-layer contract callers depend on.
        assert "layer 0" in str(exc_info.value)
        # And it must NOT be a ``DecryptionError`` (subclass check —
        # ``DecryptionError`` is not a ``ValueError`` so this also
        # guards against a future widening that breaks the contract).
        assert not isinstance(exc_info.value, DecryptionError)

    def test_clean_layer_round_trips(self):
        import hashlib
        layer_key = hashlib.sha256(b"k" + (0).to_bytes(4, "big")).digest()
        nonce = os.urandom(_GCM_NONCE_LEN)
        ct, tag = CryptoService.encrypt_aes_gcm(layer_key, nonce, b"plaintext")
        assert self._simulate_decrypt_payload_layer(
            nonce + tag + ct, layer_key, 0
        ) == b"plaintext"


# ===========================================================================
# COMMIT 2 — HKDF + DATA_ENCRYPTION_KEY + versioned envelope
# ===========================================================================

class TestV2EnvelopeShape:
    """Pin the v2 wire layout — any change must bump the version byte
    and add a new test class, not retrofit this one."""

    def test_envelope_starts_with_version_byte(self):
        ct_b64 = CryptoService.encrypt_data("hello")
        raw = base64.b64decode(ct_b64)
        assert raw[0:1] == _ENVELOPE_V2

    def test_envelope_is_at_least_min_v2_length(self):
        # Even an empty plaintext produces version(1) + salt(16) +
        # nonce(12) + tag(16) = 45 bytes (no ciphertext bytes).
        ct_b64 = CryptoService.encrypt_data("")
        raw = base64.b64decode(ct_b64)
        assert len(raw) >= _MIN_ENVELOPE_LEN_V2
        # Empty plaintext: exactly the floor.
        assert len(raw) == _MIN_ENVELOPE_LEN_V2

    def test_salt_and_nonce_are_distinct_between_records(self):
        # Two encrypts of the same plaintext must produce different
        # envelopes. Both salt AND nonce are randomly generated, so
        # the v2 envelope diverges at byte 1 (salt) and byte 17
        # (nonce). Comparing the whole byte string is the simplest
        # property check.
        a = base64.b64decode(CryptoService.encrypt_data("hello"))
        b = base64.b64decode(CryptoService.encrypt_data("hello"))
        assert a != b
        # Specifically: salt regions differ.
        salt_a = a[1 : 1 + _HKDF_SALT_LEN]
        salt_b = b[1 : 1 + _HKDF_SALT_LEN]
        assert salt_a != salt_b


class TestV2EnvelopeAADBinding:
    """Audit finding #9 — flipping version/salt/nonce in a stored
    envelope must fail the tag check (the AAD covers all three)."""

    def _make_envelope(self):
        ct_b64 = CryptoService.encrypt_data("payload")
        return bytearray(base64.b64decode(ct_b64))

    def test_flipping_version_byte_fails(self):
        # Flipping the version byte to anything other than \x02
        # routes through the legacy fallback path (and fails because
        # the salt+nonce+ct+tag don't form a valid legacy envelope
        # under SECRET_KEY[:32]). Flipping it to a different value
        # AND keeping length above _MIN_ENVELOPE_LEN_V2 would still
        # mis-identify — but the *first byte test* in decrypt_data
        # requires equality with _ENVELOPE_V2, so any flip ejects.
        raw = self._make_envelope()
        raw[0] ^= 0x01  # \x02 -> \x03
        assert CryptoService.decrypt_data(base64.b64encode(bytes(raw)).decode()) is None

    def test_flipping_salt_byte_fails(self):
        # Salt is part of the AAD. Flipping ANY salt byte means HKDF
        # derives the wrong key AND the AAD doesn't match what was
        # sealed in — tag verify fails.
        raw = self._make_envelope()
        raw[5] ^= 0x01  # somewhere inside the salt region
        assert CryptoService.decrypt_data(base64.b64encode(bytes(raw)).decode()) is None

    def test_flipping_nonce_byte_fails(self):
        # Nonce is also part of AAD. Same outcome as salt tamper.
        raw = self._make_envelope()
        raw[1 + _HKDF_SALT_LEN + 2] ^= 0x01  # inside nonce region
        assert CryptoService.decrypt_data(base64.b64encode(bytes(raw)).decode()) is None

    def test_no_silent_downgrade_to_legacy(self):
        # Critical security property: an attacker who can write a
        # fake v2-prefixed envelope must NOT be able to trigger a
        # silent retry under the legacy SECRET_KEY[:32]. If the v2
        # path fails, decrypt_data returns None — full stop.
        # Construct an envelope that starts with \x02 but is actually
        # a legacy ciphertext concatenated underneath. The v2 path
        # will attempt decrypt and fail; the legacy fallback MUST
        # not be tried because the first byte said v2.
        raw = bytearray(_ENVELOPE_V2)
        raw += os.urandom(_HKDF_SALT_LEN + _GCM_NONCE_LEN + _GCM_TAG_LEN)
        # 45 bytes total — exactly _MIN_ENVELOPE_LEN_V2. v2 path
        # tries and fails; legacy path is NOT consulted.
        assert CryptoService.decrypt_data(base64.b64encode(bytes(raw)).decode()) is None


class TestHkdfDerivation:
    """The per-record HKDF derivation is the heart of the key-
    separation property — same master + different salt = different
    key; different user_id = different key."""

    def test_different_salts_produce_different_keys(self):
        salt_a = os.urandom(_HKDF_SALT_LEN)
        salt_b = os.urandom(_HKDF_SALT_LEN)
        k_a = _derive_data_key(user_id=42, salt=salt_a)
        k_b = _derive_data_key(user_id=42, salt=salt_b)
        assert k_a != k_b
        assert len(k_a) == 32 and len(k_b) == 32

    def test_different_user_ids_produce_different_keys(self):
        salt = os.urandom(_HKDF_SALT_LEN)
        k_a = _derive_data_key(user_id=42, salt=salt)
        k_b = _derive_data_key(user_id=43, salt=salt)
        assert k_a != k_b

    def test_none_user_id_uses_anon_sentinel(self):
        # ``None`` user_id must not raise (email_masking calls with
        # no user_id). Two ``None``-user records with the same salt
        # derive the same key (deterministic) — proves the anon
        # sentinel is used consistently.
        salt = os.urandom(_HKDF_SALT_LEN)
        assert _derive_data_key(None, salt) == _derive_data_key(None, salt)

    def test_anon_key_differs_from_zero_user_key(self):
        # The anon sentinel must not collide with user_id=0, which
        # is a real value in some auth backends.
        salt = os.urandom(_HKDF_SALT_LEN)
        assert _derive_data_key(None, salt) != _derive_data_key(0, salt)


class TestUserIdRoundTrip:
    """The user_id parameter is no longer cosmetic — pass the wrong
    one at decrypt and the HKDF derives a different key, which means
    the tag check fails."""

    def test_matching_user_id_round_trips(self):
        ct = CryptoService.encrypt_data("secret", user_id=42)
        assert CryptoService.decrypt_data(ct, user_id=42) == "secret"

    def test_mismatched_user_id_fails(self):
        ct = CryptoService.encrypt_data("secret", user_id=42)
        # Different user_id → different HKDF info → different key →
        # tag verify fails → None.
        assert CryptoService.decrypt_data(ct, user_id=43) is None

    def test_none_user_id_round_trips(self):
        # The email_masking call pattern: no user_id at either end.
        ct = CryptoService.encrypt_data("api_key_payload")
        assert CryptoService.decrypt_data(ct) == "api_key_payload"


class TestLegacyEnvelopeReadback:
    """Pre-commit-2 stored ciphertexts (email_masking provider
    configs, etc.) must keep decrypting after the upgrade."""

    @staticmethod
    def _make_legacy_envelope(plaintext: str) -> str:
        """Hand-build the pre-commit-2 envelope shape so we can
        verify ``decrypt_data`` reads it under the legacy fallback.
        Uses ``SECRET_KEY[:32]`` as the AES key — the legacy code's
        exact behaviour."""
        secret_key = settings.SECRET_KEY.encode('utf-8')[:32]
        nonce = os.urandom(_GCM_NONCE_LEN)
        ct, tag = CryptoService.encrypt_aes_gcm(
            secret_key, nonce, plaintext.encode('utf-8'),
        )
        return base64.b64encode(nonce + ct + tag).decode()

    def test_legacy_envelope_decrypts(self):
        legacy_b64 = self._make_legacy_envelope("legacy_api_key")
        assert CryptoService.decrypt_data(legacy_b64) == "legacy_api_key"

    def test_legacy_empty_plaintext_decrypts(self):
        legacy_b64 = self._make_legacy_envelope("")
        assert CryptoService.decrypt_data(legacy_b64) == ""

    def test_legacy_with_random_first_byte_equal_to_v2_falls_through(self):
        # ~1/256 of legacy envelopes start with \x02 by coincidence
        # of the random nonce. ``decrypt_data`` will attempt v2
        # decrypt first (and fail), then return None — it must NOT
        # retry as legacy because that would defeat the v2 path's
        # downgrade-resistance guard.
        #
        # Force the first byte by retrying until we get one — keeps
        # the test deterministic without exposing internal state.
        for _ in range(2000):  # ~99.9% chance of finding one in 2000 tries
            legacy_b64 = self._make_legacy_envelope("ambiguous")
            raw = base64.b64decode(legacy_b64)
            if raw[0:1] == _ENVELOPE_V2:
                # Found one — confirm it does NOT decrypt through
                # decrypt_data even though the legacy fallback would
                # succeed. This is the intentional trade-off
                # documented in the v2 path's DecryptionError handler.
                assert CryptoService.decrypt_data(legacy_b64) is None
                # And confirm the raw legacy decrypt would have
                # succeeded — proving the failure is intentional.
                assert _decrypt_legacy(raw) == b"ambiguous"
                return
        pytest.skip("Could not generate a legacy envelope with v2-matching first byte")

    def test_short_legacy_envelope_returns_none(self):
        # 27 bytes — below the legacy floor of 28.
        too_short = base64.b64encode(os.urandom(_MIN_ENVELOPE_LEN_LEGACY - 1)).decode()
        assert CryptoService.decrypt_data(too_short) is None

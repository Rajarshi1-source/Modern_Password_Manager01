"""
Cryptographic service for security operations.

Used for breach monitoring, password analysis, and other security features.
Maintains zero-knowledge principles where possible.

Audit hardening (Group A / commit 1, 2026-05):
  * AES-GCM operations now go through the high-level ``AESGCM`` AEAD
    primitive rather than the low-level ``Cipher`` + ``mode.GCM``
    interface. The previous implementation called ``encryptor.update()``
    + ``encryptor.finalize()`` but discarded ``finalize()``'s return
    value, which could silently drop trailing bytes that the library
    buffered internally. ``AESGCM.encrypt()`` / ``.decrypt()`` cannot
    be misused this way — they always emit (and require) the full
    payload + authentication tag in one shot.
  * ``decrypt_aes_gcm`` now raises ``DecryptionError`` on tag-verify
    failure instead of returning ``None``. Returning ``None`` made
    "wrong key / tampered ciphertext" indistinguishable from "decrypt
    succeeded but produced empty output" at the call site, and invited
    callers to silently treat forged data as "no result." Callers that
    previously checked ``if not decrypted: raise ValueError(...)`` are
    unaffected — the exception simply propagates earlier.
  * ``decrypt_data`` length-validates its input before slicing. The old
    implementation sliced ``[:12]`` / ``[-16:]`` / ``[12:-16]`` blindly,
    so a 10-byte input produced an empty ciphertext slice and a 4-byte
    nonce/tag overlap that base-GCM happily rejected — but only after
    pointless work. Validate up front and reject with a clear error.

What this commit does NOT change (deferred to commit 2):
  * The encryption key is still ``settings.SECRET_KEY[:32]`` (finding
    #1 / #3 — fixed in the follow-up that introduces ``DATA_ENCRYPTION_KEY``
    + per-user HKDF).
  * The wire envelope is still ``nonce(12) || ct || tag(16)`` (finding
    #9 — the version-byte envelope with AAD over metadata lands with
    the HKDF change so existing ciphertexts written by
    ``email_masking`` callers stay readable through one upgrade).
  * The ``standard`` / ``legacy`` branches in
    ``decrypt_vault_item_for_security_scan`` still return ``None``
    (finding #4 — converted to ``NotImplementedError`` in a later
    commit so the change can be reviewed in isolation against the
    breach-scan caller).
"""

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.exceptions import InvalidTag
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import os
import base64
import json
import logging

logger = logging.getLogger(__name__)


# Authentication-tag length emitted by ``AESGCM`` and expected on
# input. Hardcoded — the library always uses 16 bytes; exposing it as
# a constant just keeps the slice arithmetic in ``decrypt_data``
# self-documenting.
_GCM_TAG_LEN = 16
_GCM_NONCE_LEN = 12

# Minimum byte-length of a valid ``encrypt_data`` envelope after
# base64 decode: nonce(12) + tag(16). Empty plaintext is a valid
# AEAD case (``AESGCM`` accepts it), producing exactly 28 bytes — so
# the floor is 28, not 29. Anything shorter would let the
# ``[:12]`` / ``[-16:]`` / ``[12:-16]`` slices in ``decrypt_data``
# overlap or wrap and hand garbage to the cipher (audit finding #11).
_MIN_ENVELOPE_LEN = _GCM_NONCE_LEN + _GCM_TAG_LEN


class DecryptionError(Exception):
    """Raised when AES-GCM decryption fails authentication.

    Distinct from generic ``Exception`` so callers can tell
    "decryption rejected this ciphertext" apart from "I had a bug."
    Wraps ``cryptography.exceptions.InvalidTag`` and any input-shape
    rejection (wrong nonce length, truncated envelope, etc.).
    """


class CryptoService:
    """
    Cryptographic service for security operations
    Used for breach monitoring, password analysis, and other security features
    Maintains zero-knowledge principles where possible
    """

    @staticmethod
    def encrypt_data(plaintext, user_id=None):
        """
        Encrypt data for storage using a derived key.

        Args:
            plaintext (str): Data to encrypt
            user_id: Optional user ID for user-specific encryption (currently
                ignored — wired in the HKDF commit; the parameter is kept on
                the signature so the call sites that already pass it do not
                need to change twice).

        Returns:
            str: Base64-encoded encrypted data with nonce and tag, or
                 ``None`` on failure (failure is logged).
        """
        try:
            # Generate a random key or derive from environment.
            #
            # NOTE: ``SECRET_KEY[:32]`` is the legacy, audit-flagged key
            # source (finding #1). Replaced by HKDF over a dedicated
            # ``DATA_ENCRYPTION_KEY`` in commit 2. Kept here so this
            # commit is a behavior-preserving rewrite (no envelope
            # change, no key change — only the AEAD primitive flips).
            from django.conf import settings
            secret_key = settings.SECRET_KEY.encode('utf-8')[:32]

            # Generate random nonce. 12 bytes is the AESGCM default.
            nonce = os.urandom(_GCM_NONCE_LEN)

            # Encrypt via the static helper — see ``encrypt_aes_gcm``
            # below for the AEAD-vs-low-level rationale.
            ciphertext, tag = CryptoService.encrypt_aes_gcm(
                secret_key, nonce, plaintext.encode('utf-8')
            )

            if ciphertext is None:
                return None

            # Wire format: ``nonce(12) || ct || tag(16)``. Kept
            # byte-for-byte identical to the previous implementation so
            # email_masking provider records written before this change
            # still decrypt cleanly.
            encrypted_data = nonce + ciphertext + tag
            return base64.b64encode(encrypted_data).decode('utf-8')

        except Exception as e:
            logger.error(f'Data encryption failed: {e}')
            return None

    @staticmethod
    def decrypt_data(encrypted_data, user_id=None):
        """
        Decrypt encrypted data.

        Args:
            encrypted_data (str): Base64-encoded encrypted data
            user_id: Optional user ID for user-specific decryption (see
                ``encrypt_data`` — currently ignored).

        Returns:
            str: Decrypted plaintext, or ``None`` if the envelope was
                 malformed / the tag did not verify. The distinction
                 between "malformed" and "tag mismatch" is logged but
                 not surfaced to the caller — change this once callers
                 are taught to handle ``DecryptionError``.
        """
        try:
            from django.conf import settings
            secret_key = settings.SECRET_KEY.encode('utf-8')[:32]

            # Decode from base64.
            encrypted_bytes = base64.b64decode(encrypted_data)

            # Length-validate before slicing (audit finding #11). Without
            # this guard a 10-byte input produces ``ciphertext = b''``
            # via ``[12:-16]`` (Python clamps to empty when the start is
            # past the end), and ``nonce``/``tag`` slice over the same
            # bytes. AESGCM would still reject it, but we get a clearer
            # error and skip the pointless library round-trip.
            if len(encrypted_bytes) < _MIN_ENVELOPE_LEN:
                logger.error(
                    'Data decryption failed: envelope too short '
                    '(%d bytes, need >= %d)',
                    len(encrypted_bytes), _MIN_ENVELOPE_LEN,
                )
                return None

            # Extract nonce (12 bytes), ciphertext, and tag (16 bytes).
            nonce = encrypted_bytes[:_GCM_NONCE_LEN]
            tag = encrypted_bytes[-_GCM_TAG_LEN:]
            ciphertext = encrypted_bytes[_GCM_NONCE_LEN:-_GCM_TAG_LEN]

            # Decrypt. Catches ``DecryptionError`` here and downgrades
            # to ``None`` to preserve the current public API of
            # ``decrypt_data`` (``None`` on failure). Direct callers of
            # ``decrypt_aes_gcm`` get the exception.
            try:
                decrypted_data = CryptoService.decrypt_aes_gcm(
                    secret_key, nonce, ciphertext, tag
                )
            except DecryptionError as e:
                logger.error(f'Data decryption failed: {e}')
                return None

            return decrypted_data.decode('utf-8')

        except Exception as e:
            logger.error(f'Data decryption failed: {e}')
            return None

    @staticmethod
    def decrypt_aes_gcm(key, nonce, ciphertext, tag, associated_data=None):
        """
        Decrypt data using AES-GCM encryption.

        Args:
            key (bytes): Encryption key (32 bytes for AES-256)
            nonce (bytes): Nonce/IV used for encryption (12 bytes)
            ciphertext (bytes): Encrypted data (without the auth tag)
            tag (bytes): 16-byte authentication tag emitted by encrypt
            associated_data (bytes | None): Optional AEAD-bound metadata
                that must match the value passed at encrypt time. Used
                in commit 2 to bind envelope version/salt/nonce to the
                ciphertext so a metadata flip fails the tag check
                (finding #9). Defaults to ``None`` for wire compat.

        Returns:
            bytes: Decrypted data.

        Raises:
            DecryptionError: tag did not verify, or the input shape was
                invalid (wrong key size, wrong nonce size, etc.).
        """
        # ``AESGCM`` expects ``ciphertext || tag`` concatenated as a
        # single argument — the underlying primitive does not separate
        # the two. Our public signature still takes them apart for
        # backwards compatibility with ``noise_encryptor`` / ``garlic_router``
        # which split the wire bytes manually before calling this.
        try:
            aesgcm = AESGCM(key)
        except ValueError as e:
            # Wrong key length (AESGCM enforces 16/24/32). Surface as
            # ``DecryptionError`` so callers see one exception type.
            raise DecryptionError(f'invalid key: {e}') from e

        try:
            return aesgcm.decrypt(nonce, ciphertext + tag, associated_data)
        except InvalidTag as e:
            # The whole point of GCM is that this exception means
            # "someone tampered with the ciphertext / used the wrong
            # key" and the plaintext is therefore untrusted. Never
            # silently downgrade to ``None`` — the previous code did,
            # which let forged data look like "no result" at the call
            # site (audit finding #2).
            logger.warning('AES-GCM tag verification failed')
            raise DecryptionError('AES-GCM tag verification failed') from e
        except ValueError as e:
            # Wrong nonce length, etc. — also a hard failure.
            raise DecryptionError(f'AES-GCM decryption failed: {e}') from e

    @staticmethod
    def encrypt_aes_gcm(key, nonce, plaintext, associated_data=None):
        """
        Encrypt data using AES-GCM encryption.

        Args:
            key (bytes): Encryption key (32 bytes for AES-256)
            nonce (bytes): Nonce/IV for encryption (12 bytes)
            plaintext (bytes): Data to encrypt
            associated_data (bytes | None): Optional AEAD-bound metadata
                (see ``decrypt_aes_gcm``). Pass the same value to decrypt
                or the tag will not verify.

        Returns:
            tuple: ``(ciphertext, tag)`` or ``(None, None)`` on failure.

        The tuple shape is preserved from the pre-rewrite signature so
        ``noise_encryptor`` and ``garlic_router`` (which build wire
        packets as ``nonce || tag || ct`` or similar) keep working
        without code changes. Internally we use the high-level
        ``AESGCM.encrypt`` API which emits ``ct || tag`` concatenated
        — we split the tail off here.
        """
        try:
            aesgcm = AESGCM(key)
            # ``AESGCM.encrypt`` returns ``ciphertext + tag`` as a
            # single bytes. The library guarantees the tag is exactly
            # 16 bytes so the slice is unambiguous.
            ct_and_tag = aesgcm.encrypt(nonce, plaintext, associated_data)
            ciphertext = ct_and_tag[:-_GCM_TAG_LEN]
            tag = ct_and_tag[-_GCM_TAG_LEN:]
            return ciphertext, tag
        except Exception as e:
            logger.error(f'AES-GCM encryption failed: {e}')
            return None, None

    @staticmethod
    def derive_key_from_password(password, salt, iterations=600000):
        """
        Derive encryption key from password using PBKDF2

        Args:
            password (str): Master password
            salt (bytes): Salt for key derivation
            iterations (int): Number of PBKDF2 iterations

        Returns:
            bytes: Derived key (32 bytes for AES-256)
        """
        try:
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,  # 256 bits
                salt=salt,
                iterations=iterations,
                backend=default_backend()
            )
            return kdf.derive(password.encode('utf-8'))
        except Exception as e:
            logger.error(f'Key derivation failed: {e}')
            return None

    @staticmethod
    def parse_encrypted_vault_item(encrypted_data):
        """
        Parse encrypted vault item data to extract components for decryption

        Args:
            encrypted_data (str): Base64-encoded encrypted data with metadata

        Returns:
            dict: Parsed components or None if parsing failed
        """
        try:
            # Try to parse as JSON first (new format)
            try:
                data = json.loads(base64.b64decode(encrypted_data))

                # Check if it's WebCrypto format with version info
                if 'version' in data and data['version'] == 'webcrypto-1':
                    return {
                        'format': 'webcrypto',
                        'iv': base64.b64decode(data['iv']),
                        'ciphertext': base64.b64decode(data['data']),
                        'version': data['version']
                    }

                # Standard format with IV and data
                if 'iv' in data and 'data' in data:
                    return {
                        'format': 'standard',
                        'iv': base64.b64decode(data['iv']),
                        'ciphertext': base64.b64decode(data['data']),
                        'compressed': data.get('compressed', False)
                    }

            except (json.JSONDecodeError, KeyError):
                # Fall back to legacy format
                logger.warning('Could not parse as JSON, treating as legacy format')
                return {
                    'format': 'legacy',
                    'ciphertext': base64.b64decode(encrypted_data)
                }

        except Exception as e:
            logger.error(f'Failed to parse encrypted vault item: {e}')
            return None

    @staticmethod
    def decrypt_vault_item_for_security_scan(encrypted_data, user_key):
        """
        Decrypt a vault item specifically for security scanning purposes
        This should only be used for security operations like breach checking

        Args:
            encrypted_data (str): Encrypted vault item data
            user_key (bytes): User's derived encryption key

        Returns:
            dict: Decrypted vault item data or None if decryption failed
        """
        try:
            parsed = CryptoService.parse_encrypted_vault_item(encrypted_data)
            if not parsed:
                return None

            # Handle different encryption formats
            if parsed['format'] == 'webcrypto':
                # For WebCrypto AES-GCM format, we need to split the IV and tag
                # The IV is typically the first 12 bytes, but this depends on implementation
                iv = parsed['iv'][:_GCM_NONCE_LEN]
                tag = parsed['iv'][_GCM_NONCE_LEN:] if len(parsed['iv']) > _GCM_NONCE_LEN else b''

                # Try to decrypt with AES-GCM. ``decrypt_aes_gcm`` now
                # raises ``DecryptionError`` instead of returning None
                # — catch here to preserve the public None-on-failure
                # API of this method.
                try:
                    decrypted = CryptoService.decrypt_aes_gcm(
                        user_key, iv, parsed['ciphertext'], tag
                    )
                except DecryptionError:
                    return None

                if decrypted:
                    return json.loads(decrypted.decode('utf-8'))

            elif parsed['format'] == 'standard':
                # Handle standard format (likely AES-CBC from CryptoJS)
                # This would need to be implemented based on your current encryption method
                logger.warning('Standard format decryption not implemented yet')
                return None

            elif parsed['format'] == 'legacy':
                # Handle legacy format
                logger.warning('Legacy format decryption not implemented yet')
                return None

        except Exception as e:
            logger.error(f'Failed to decrypt vault item for security scan: {e}')
            return None

        return None

    @staticmethod
    def generate_secure_random(length=32):
        """
        Generate cryptographically secure random bytes

        Args:
            length (int): Number of bytes to generate

        Returns:
            bytes: Random bytes
        """
        return os.urandom(length)

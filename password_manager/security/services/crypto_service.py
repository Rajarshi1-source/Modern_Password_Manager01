"""
Cryptographic service for security operations.

Used for breach monitoring, password analysis, and other security features.
Maintains zero-knowledge principles where possible.

Audit hardening (Group A, 2026-05):

Commit 1 — AEAD primitive + length validation + tag-verify raises:
  * AES-GCM operations now go through the high-level ``AESGCM`` AEAD
    primitive rather than the low-level ``Cipher`` + ``mode.GCM``
    interface. The previous implementation called ``encryptor.update()``
    + ``encryptor.finalize()`` but discarded ``finalize()``'s return
    value, which could silently drop trailing bytes that the library
    buffered internally. ``AESGCM.encrypt()`` / ``.decrypt()`` cannot
    be misused this way — they always emit (and require) the full
    payload + authentication tag in one shot.
  * ``decrypt_aes_gcm`` now raises ``DecryptionError`` on tag-verify
    failure instead of returning ``None``.
  * ``decrypt_data`` length-validates its input before slicing.

Commit 2 — HKDF + DATA_ENCRYPTION_KEY + versioned envelope (this file):
  * High-level ``encrypt_data`` / ``decrypt_data`` no longer derive
    the AES key by truncating ``settings.SECRET_KEY`` (audit findings
    #1, #3). The key is now produced by HKDF-SHA256 over a dedicated
    ``settings.DATA_ENCRYPTION_KEY`` (32 random bytes, base64-encoded
    env var), with a fresh 16-byte random salt per record and a
    domain-separated info string ``b"vault-scan-v1:" + user_id`` so
    leaking one record's key does not break the rest.
  * The wire envelope is now ``b"\\x02" || salt(16) || nonce(12) ||
    ct || tag(16)``. ``b"\\x02" || salt || nonce`` is passed as AEAD
    AAD so any envelope-metadata tamper (flip the version, swap the
    salt) fails the tag check (audit finding #9).
  * ``decrypt_data`` supports reading the legacy ``nonce(12) || ct ||
    tag(16)`` format under the old ``SECRET_KEY[:32]`` key, so
    existing email_masking provider records keep decrypting through
    the upgrade. Records are re-encrypted under the v2 envelope on
    the next write (no automatic batch migration).
  * In production (``DEBUG=False``) the legacy decrypt path requires
    that ``DATA_ENCRYPTION_KEY`` IS set — otherwise the module raises
    ``ImproperlyConfigured`` at first decrypt, mirroring the
    JWT_PRIVATE_KEY guard in settings/base.py.

What this commit does NOT change (deferred):
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
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from django.core.exceptions import ImproperlyConfigured
import os
import base64
import json
import logging

logger = logging.getLogger(__name__)


# Authentication-tag length emitted by ``AESGCM`` and expected on
# input. Hardcoded — the library always uses 16 bytes; exposing it as
# a constant just keeps the slice arithmetic self-documenting.
_GCM_TAG_LEN = 16
_GCM_NONCE_LEN = 12

# Random per-record salt fed to HKDF in v2 envelopes. 16 bytes is the
# RFC 5869 recommendation; long enough that collisions across records
# stored under a single ``DATA_ENCRYPTION_KEY`` are astronomically
# unlikely (2^64 records before a 50% collision).
_HKDF_SALT_LEN = 16

# Envelope version byte. Bumped whenever the envelope layout
# changes — current readers know to fall back to legacy when this
# byte does not match.
#   v1 (legacy, no version byte): ``nonce(12) || ct || tag(16)``
#   v2:                           ``b"\\x02" || salt(16) || nonce(12) || ct || tag(16)``
_ENVELOPE_V2 = b"\x02"

# Minimum byte-length of a valid v2 envelope after base64 decode:
# version(1) + salt(16) + nonce(12) + tag(16). Empty plaintext is a
# valid AEAD case so the floor is 45, not 46.
_MIN_ENVELOPE_LEN_V2 = 1 + _HKDF_SALT_LEN + _GCM_NONCE_LEN + _GCM_TAG_LEN

# Minimum byte-length of a valid legacy envelope (audit finding #11
# from commit 1 — kept so the legacy read path keeps the same
# slice-overlap guard).
_MIN_ENVELOPE_LEN_LEGACY = _GCM_NONCE_LEN + _GCM_TAG_LEN

# Backwards-compatible alias for callers / tests that import the
# pre-commit-2 constant. Resolves to the v2 floor — the larger of
# the two — so any caller validating against ``_MIN_ENVELOPE_LEN``
# now demands a v2 envelope. The legacy read path uses
# ``_MIN_ENVELOPE_LEN_LEGACY`` directly.
_MIN_ENVELOPE_LEN = _MIN_ENVELOPE_LEN_V2

# HKDF info-prefix. Bumped whenever the *meaning* of a record changes
# (not the envelope layout). Anchors derived keys to a purpose so a
# key derived for vault-scan cannot accidentally decrypt a record
# encrypted for a different subsystem under the same master.
_HKDF_INFO_PREFIX = b"vault-scan-v1:"

# Sentinel passed in place of an absent user_id (e.g. email_masking
# provider configs, which are not per-user-scoped at the API
# boundary). All anon records share an HKDF info string but still
# get a fresh per-record salt — so two anon records still derive
# different keys.
_HKDF_ANON_USER = b"anon"


class DecryptionError(Exception):
    """Raised when AES-GCM decryption fails authentication.

    Distinct from generic ``Exception`` so callers can tell
    "decryption rejected this ciphertext" apart from "I had a bug."
    Wraps ``cryptography.exceptions.InvalidTag`` and any input-shape
    rejection (wrong nonce length, truncated envelope, etc.).
    """


def _get_master_key():
    """Return the 32-byte master key for HKDF-based data encryption.

    Resolution order:
      1. ``settings.DATA_ENCRYPTION_KEY`` (base64-encoded 32 bytes) —
         the production source. Generated once via
         ``python -c "import secrets, base64;
         print(base64.b64encode(secrets.token_bytes(32)).decode())"``
         and set in the deployment environment.
      2. ``settings.SECRET_KEY[:32]`` — DEBUG-only fallback so dev
         imports keep working when ``DATA_ENCRYPTION_KEY`` is unset.
         A startup guard in ``settings/base.py`` raises
         ``ImproperlyConfigured`` for non-DEBUG / non-test deploys
         that try to take this path, mirroring the JWT_PRIVATE_KEY
         guard.

    Returning the master key directly (not a per-record key) keeps
    HKDF's salt + info flexibility at the call site.
    """
    from django.conf import settings
    raw = getattr(settings, 'DATA_ENCRYPTION_KEY', None)
    if raw:
        # A malformed key is a deployment misconfiguration, not a
        # decryption failure — raise ``ImproperlyConfigured`` (which the
        # public entrypoints deliberately re-raise instead of swallowing)
        # so a broken production key fails closed and loud rather than
        # masquerading as an ordinary "decrypt returned None". PR #280
        # review (CodeRabbit). settings/base.py also validates this at
        # startup; this is the defence-in-depth catch for paths that
        # configure settings directly (e.g. tests).
        try:
            key = base64.b64decode(raw, validate=True)
        except Exception as e:
            raise ImproperlyConfigured(
                f'DATA_ENCRYPTION_KEY is not valid base64: {e}'
            ) from e
        if len(key) != 32:
            raise ImproperlyConfigured(
                f'DATA_ENCRYPTION_KEY must decode to 32 bytes, got {len(key)}'
            )
        return key

    # Fallback for DEBUG / tests. The settings guard means this
    # branch is unreachable in production.
    return settings.SECRET_KEY.encode('utf-8')[:32]


def _derive_data_key(user_id, salt):
    """Derive a 32-byte AES-GCM key for one record.

    Args:
        user_id: Anything stringifiable. ``None`` is mapped to the
            anon sentinel so the HKDF info is always non-empty.
        salt (bytes): 16-byte random per-record salt.

    Returns:
        bytes: 32-byte derived key.

    The info string ``"vault-scan-v1:" + user_id`` is the domain
    separator — change the prefix (and bump the envelope version)
    if this key derivation is ever reused for a different subsystem.
    """
    if user_id is None:
        info = _HKDF_INFO_PREFIX + _HKDF_ANON_USER
    else:
        info = _HKDF_INFO_PREFIX + str(user_id).encode('utf-8')

    return HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        info=info,
        backend=default_backend(),
    ).derive(_get_master_key())


def _decrypt_legacy(encrypted_bytes):
    """Read a pre-commit-2 ``nonce(12) || ct || tag(16)`` envelope.

    Used by ``decrypt_data`` to keep already-stored ciphertexts
    (email_masking provider configs etc.) readable across the
    upgrade. Records get re-encrypted under the v2 envelope on the
    next write — no batch migration job is provided because
    plaintext is not recoverable here unless the legacy SECRET_KEY
    is still present in the environment.

    The legacy key is ``SECRET_KEY[:32]``. In production (DEBUG=False)
    this path is the *only* reason the service still touches
    SECRET_KEY at all — once all stored ciphertexts have been
    rewritten, the path can be deleted.

    Returns ``None`` if the envelope is too short or the tag does
    not verify (matches ``decrypt_data``'s public API contract).
    """
    from django.conf import settings

    if len(encrypted_bytes) < _MIN_ENVELOPE_LEN_LEGACY:
        logger.error(
            'Legacy decrypt failed: envelope too short (%d < %d)',
            len(encrypted_bytes), _MIN_ENVELOPE_LEN_LEGACY,
        )
        return None

    legacy_key = settings.SECRET_KEY.encode('utf-8')[:32]
    nonce = encrypted_bytes[:_GCM_NONCE_LEN]
    tag = encrypted_bytes[-_GCM_TAG_LEN:]
    ciphertext = encrypted_bytes[_GCM_NONCE_LEN:-_GCM_TAG_LEN]
    try:
        return CryptoService.decrypt_aes_gcm(legacy_key, nonce, ciphertext, tag)
    except DecryptionError as e:
        logger.error(f'Legacy decrypt failed: {e}')
        return None


class CryptoService:
    """
    Cryptographic service for security operations
    Used for breach monitoring, password analysis, and other security features
    Maintains zero-knowledge principles where possible
    """

    @staticmethod
    def encrypt_data(plaintext, user_id=None):
        """
        Encrypt data for storage under an HKDF-derived per-record key.

        Args:
            plaintext (str): Data to encrypt.
            user_id: Optional identifier folded into the HKDF info
                string. ``None`` falls back to a fixed anon sentinel
                — all "no user" records share an info string but
                still get a fresh random salt per record.

        Returns:
            str: Base64-encoded v2 envelope
                ``b"\\x02" || salt(16) || nonce(12) || ct || tag(16)``,
                or ``None`` on failure (failure is logged).

        Envelope-binding: ``b"\\x02" || salt || nonce`` is fed to
        ``AESGCM`` as Additional Authenticated Data. A flip of the
        version byte or salt breaks the tag check at decrypt time —
        attackers cannot steer the legacy fallback or replay a record
        under a different salt (audit finding #9).
        """
        try:
            # Fresh per-record salt → fresh derived key. The same
            # plaintext encrypted twice produces unrelated keys, so
            # a nonce-reuse attacker who somehow forces a duplicate
            # ``os.urandom(12)`` still gets a different AESGCM
            # instance with a different key.
            salt = os.urandom(_HKDF_SALT_LEN)
            key = _derive_data_key(user_id, salt)

            nonce = os.urandom(_GCM_NONCE_LEN)

            # AAD = version || salt || nonce. Binds the envelope
            # metadata to the ciphertext so any tamper of those
            # fields fails the tag check.
            aad = _ENVELOPE_V2 + salt + nonce

            ciphertext, tag = CryptoService.encrypt_aes_gcm(
                key, nonce, plaintext.encode('utf-8'), aad
            )
            if ciphertext is None:
                return None

            envelope = _ENVELOPE_V2 + salt + nonce + ciphertext + tag
            return base64.b64encode(envelope).decode('utf-8')

        except ImproperlyConfigured:
            # A broken DATA_ENCRYPTION_KEY is a deployment error, not a
            # routine encrypt failure — let it propagate so it fails
            # closed instead of looking like "encryption returned None"
            # (PR #280 review, CodeRabbit).
            raise
        except Exception as e:
            logger.error(f'Data encryption failed: {e}')
            return None

    @staticmethod
    def decrypt_data(encrypted_data, user_id=None):
        """
        Decrypt encrypted data.

        Reads the v2 envelope produced by ``encrypt_data`` after
        commit 2. Falls back to the pre-commit-2 ``nonce || ct ||
        tag`` envelope under the legacy ``SECRET_KEY[:32]`` key when
        the version byte does not match — so already-stored
        ciphertexts (email_masking provider configs etc.) keep
        decrypting through the upgrade.

        Args:
            encrypted_data (str): Base64-encoded envelope.
            user_id: Must match the value passed to ``encrypt_data``.
                Passed through to HKDF only on the v2 path; ignored
                on the legacy path because legacy did not derive
                per-user keys.

        Returns:
            str: Decrypted plaintext, or ``None`` on failure
                 (malformed envelope, tag mismatch, etc.).
        """
        try:
            encrypted_bytes = base64.b64decode(encrypted_data)

            # Detect envelope version. ``encrypted_bytes[0:1]``
            # slices safely even on an empty input (returns ``b""``).
            if (
                len(encrypted_bytes) >= _MIN_ENVELOPE_LEN_V2
                and encrypted_bytes[0:1] == _ENVELOPE_V2
            ):
                # v2 envelope: ``b"\x02" || salt || nonce || ct || tag``.
                salt = encrypted_bytes[1 : 1 + _HKDF_SALT_LEN]
                nonce_start = 1 + _HKDF_SALT_LEN
                nonce = encrypted_bytes[nonce_start : nonce_start + _GCM_NONCE_LEN]
                tag = encrypted_bytes[-_GCM_TAG_LEN:]
                ciphertext = encrypted_bytes[
                    nonce_start + _GCM_NONCE_LEN : -_GCM_TAG_LEN
                ]

                aad = _ENVELOPE_V2 + salt + nonce
                key = _derive_data_key(user_id, salt)

                try:
                    plaintext = CryptoService.decrypt_aes_gcm(
                        key, nonce, ciphertext, tag, associated_data=aad,
                    )
                    return plaintext.decode('utf-8')
                except DecryptionError as e:
                    # A v2-prefixed envelope that fails to decrypt is
                    # NOT silently retried as legacy — that would let
                    # an attacker who can write a fake v2 header
                    # downgrade to the legacy key. Fail closed.
                    logger.error(f'Data decryption failed (v2): {e}')
                    return None

            # Legacy envelope (no version byte). Pre-commit-2 wire
            # format. Removed once email_masking records have all
            # been rewritten under v2.
            if len(encrypted_bytes) < _MIN_ENVELOPE_LEN_LEGACY:
                logger.error(
                    'Data decryption failed: envelope too short '
                    '(%d bytes, need >= %d)',
                    len(encrypted_bytes), _MIN_ENVELOPE_LEN_LEGACY,
                )
                return None

            plaintext_bytes = _decrypt_legacy(encrypted_bytes)
            if plaintext_bytes is None:
                return None
            return plaintext_bytes.decode('utf-8')

        except ImproperlyConfigured:
            # A broken DATA_ENCRYPTION_KEY is a deployment error, not a
            # tag-verify failure — let it propagate so it fails closed
            # instead of masquerading as an ordinary "decrypt returned
            # None" (PR #280 review, CodeRabbit).
            raise
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
        except TypeError as e:
            # Non-bytes nonce / non-bytes associated_data trip the
            # underlying CFFI buffer conversion with ``TypeError``,
            # NOT ``ValueError``. Without this branch a caller that
            # passes the wrong type would see a bare ``TypeError``
            # leak past the ``except DecryptionError`` translation
            # in ``noise_encryptor.unmask_noise`` /
            # ``garlic_router.peel_layer`` / ``decrypt_payload``,
            # breaking their documented ``ValueError`` contract
            # (CodeRabbit review on PR #280).
            raise DecryptionError(f'AES-GCM decryption failed: {e}') from e
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

            except (json.JSONDecodeError, UnicodeDecodeError, KeyError):
                # Fall back to legacy format.
                #
                # ``UnicodeDecodeError`` is critical here: ``json.loads``
                # accepts bytes and decodes as UTF-8 (or auto-detected
                # UTF-16 BOM), so a legacy ciphertext that happens to
                # contain a ``\xff\xfe`` prefix lights up the UTF-16
                # decoder and bubbles ``UnicodeDecodeError`` — NOT
                # ``JSONDecodeError``. Without catching it, every
                # legacy envelope whose first two bytes form a valid
                # UTF-16 BOM would silently fall through to the outer
                # ``except Exception: return None`` and lose the
                # legacy fallback (CodeRabbit review on PR #280).
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
                # Handle standard format (likely AES-CBC from CryptoJS).
                # Audit finding #4: this branch was never implemented and
                # silently returned ``None``. A breach-scan caller reads
                # ``None`` as "nothing to scan / no breach", so an
                # unimplemented format quietly skipped scanning instead of
                # surfacing the gap. Fail loud so the missing
                # implementation cannot masquerade as a clean result.
                raise NotImplementedError(
                    'standard (AES-CBC) vault format decryption is not '
                    'implemented'
                )

            elif parsed['format'] == 'legacy':
                # Handle legacy format. Same finding #4 rationale as the
                # ``standard`` branch above — never implemented, must not
                # silently return ``None``.
                raise NotImplementedError(
                    'legacy vault format decryption is not implemented'
                )

        except NotImplementedError:
            # Audit finding #4: a genuinely-unimplemented format is a
            # programming/coverage gap, not a decryption failure — let it
            # propagate instead of being flattened to ``None`` by the
            # broad handler below (which exists to swallow malformed-input
            # / tag-verify failures).
            raise
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

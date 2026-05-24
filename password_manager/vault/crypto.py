import os
import base64
import hashlib
import logging
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt
from cryptography.fernet import Fernet
from argon2 import PasswordHasher, Type
from argon2.low_level import Type as LLType, hash_secret_raw
import argon2

logger = logging.getLogger(__name__)

def generate_salt():
    """Generate a cryptographically secure salt"""
    return os.urandom(16)

def derive_key_from_password(password, salt, time_cost=4, memory_cost=131072, parallelism=2, crypto_version=2):
    """
    Derive encryption key using Argon2id
    
    Args:
        password: User's master password
        salt: Cryptographic salt
        time_cost: Number of iterations (v2 default: 4)
        memory_cost: Memory usage in KiB (v2 default: 131072 = 128 MB)
        parallelism: Parallelism factor (v2 default: 2)
        crypto_version: Crypto version (1 = legacy, 2 = enhanced)
        
    Returns:
        bytes: Base64-encoded derived key
    """
    # Legacy parameters for backward compatibility
    if crypto_version == 1:
        time_cost = 3
        memory_cost = 65536  # 64 MB
        parallelism = 1
    
    # ``PasswordHasher.hash()`` generates a fresh random salt on every call,
    # so the previous implementation returned a different ``key`` each time
    # for the same inputs — breaking any round-trip that relies on
    # deterministic key derivation. ``hash_secret_raw`` uses the caller-
    # supplied salt and produces reproducible output, which is what we need
    # for a key-derivation function.
    try:
        raw = hash_secret_raw(
            secret=password.encode('utf-8') if isinstance(password, str) else password,
            salt=salt,
            time_cost=time_cost,
            memory_cost=memory_cost,
            parallelism=parallelism,
            hash_len=32,  # 32 bytes for AES-256
            type=LLType.ID,  # Argon2id for balanced security
        )
        return base64.urlsafe_b64encode(raw)
    except Exception as e:
        logger.error(f'Argon2 key derivation failed: {e}')
        raise ValueError('Key derivation failed')

"""
Audit-fix H7 (2026-05): proper AES-256-GCM crypto.

These helpers are INTERNAL — production vault items are encrypted
client-side and the server only ever stores opaque ciphertext.
Verified at fix time (Q1 of the audit follow-up): no production
caller invokes `encrypt_vault_item` / `decrypt_vault_item`; the only
import in the live tree is `vault/tests.py` and even those tests are
commented out. The functions exist for completeness / future internal
use only.

The previous implementation did
``Fernet(base64(sha256(key)))`` — which silently threw away whatever
entropy the Argon2id KDF produced and reduced security to
``SHA-256(input)``. If a refactor ever passed a low-entropy "key"
(a username, a session id), encryption became guessable. The new
implementation rejects any key that isn't exactly 32 bytes and uses
AES-256-GCM directly so the output format matches what the rest of
the codebase already uses (and what the WebCrypto client produces).

Envelope format
---------------
::

    version_byte(0x01) || nonce(12) || ciphertext+tag

`version_byte` exists so a future scheme bump (e.g. XChaCha20) can
be added without breaking existing internal ciphertexts. The current
version is 0x01.
"""


_AES_GCM_VERSION_V1 = 0x01
_AES_GCM_NONCE_LEN = 12
_AES_GCM_KEY_LEN = 32


def encrypt_vault_item(data, key: bytes) -> bytes:
    """
    Encrypt vault item data under AES-256-GCM.

    Args:
        data: Python dict, str, or bytes. dicts/strs are JSON/UTF-8
              encoded before encryption.
        key:  Exactly 32 random bytes (e.g. the Argon2id-derived KDK).
              Raises ``ValueError`` for anything else — no silent SHA
              re-hashing of low-entropy inputs.

    Returns:
        bytes envelope: ``version(1) || nonce(12) || ct+tag``.
    """
    import json
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    if not isinstance(key, (bytes, bytearray)) or len(key) != _AES_GCM_KEY_LEN:
        raise ValueError(
            f"key must be exactly {_AES_GCM_KEY_LEN} raw bytes; got "
            f"{type(key).__name__} of length "
            f"{len(key) if isinstance(key, (bytes, bytearray)) else 'n/a'}"
        )

    if isinstance(data, dict):
        plaintext = json.dumps(data, separators=(',', ':'), sort_keys=True).encode('utf-8')
    elif isinstance(data, str):
        # Audit-fix (PR #272 review): wrap str payloads in JSON so the
        # decrypt path's `json.loads(plaintext)` returns the original
        # string. Without this, an input like '"hunter2"' / '123' /
        # '{"a":1}' came back as int / list / dict — a silent
        # round-trip-breaking type change.
        plaintext = json.dumps(data).encode('utf-8')
    elif isinstance(data, (bytes, bytearray)):
        plaintext = bytes(data)
    else:
        raise TypeError(f"data must be dict|str|bytes, got {type(data).__name__}")

    nonce = os.urandom(_AES_GCM_NONCE_LEN)
    ct = AESGCM(bytes(key)).encrypt(nonce, plaintext, None)
    return bytes([_AES_GCM_VERSION_V1]) + nonce + ct


def decrypt_vault_item(encrypted_data, key: bytes):
    """
    Inverse of :func:`encrypt_vault_item`.

    Returns a Python value parsed from JSON if possible, else the raw
    UTF-8 string, else raw bytes. Same key-length enforcement.
    """
    import json
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    if not isinstance(key, (bytes, bytearray)) or len(key) != _AES_GCM_KEY_LEN:
        raise ValueError(
            f"key must be exactly {_AES_GCM_KEY_LEN} raw bytes; got "
            f"{type(key).__name__} of length "
            f"{len(key) if isinstance(key, (bytes, bytearray)) else 'n/a'}"
        )

    if isinstance(encrypted_data, str):
        # Allow base64-wrapped envelopes for callers that round-tripped
        # them through JSON. We refuse legacy Fernet strings (which begin
        # with the URL-safe-b64 'gAAAA' header) — those would silently
        # use the broken SHA256(key) → Fernet path the previous code
        # took; refuse loudly instead.
        if encrypted_data.startswith('gAAAA'):
            raise ValueError(
                "legacy Fernet ciphertext is no longer accepted by "
                "decrypt_vault_item; re-encrypt with AES-GCM"
            )
        try:
            encrypted_data = base64.b64decode(encrypted_data)
        except Exception:
            encrypted_data = encrypted_data.encode('utf-8')

    if not isinstance(encrypted_data, (bytes, bytearray)) or len(encrypted_data) < (1 + _AES_GCM_NONCE_LEN + 16):
        raise ValueError("encrypted_data is too short to be an AES-GCM envelope")

    blob = bytes(encrypted_data)
    if blob[0] != _AES_GCM_VERSION_V1:
        raise ValueError(
            f"unsupported envelope version 0x{blob[0]:02x}; expected "
            f"0x{_AES_GCM_VERSION_V1:02x}"
        )

    nonce = blob[1:1 + _AES_GCM_NONCE_LEN]
    ct = blob[1 + _AES_GCM_NONCE_LEN:]
    plaintext = AESGCM(bytes(key)).decrypt(nonce, ct, None)

    try:
        return json.loads(plaintext.decode('utf-8'))
    except (json.JSONDecodeError, UnicodeDecodeError):
        try:
            return plaintext.decode('utf-8')
        except UnicodeDecodeError:
            return plaintext


def derive_auth_key(password, salt, iterations=100000):
    """Derive authentication key for verifying master password"""
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=iterations,
    )
    return base64.b64encode(kdf.derive(password.encode()))

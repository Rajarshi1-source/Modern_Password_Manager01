"""
Cryptography utilities for Password Manager

Provides encryption services including:
- XChaCha20-Poly1305 AEAD encryption
- Key derivation (PBKDF2, HKDF)
- Stream encryption for large files
"""

from .xchacha20 import (
    XChaCha20EncryptionService,
    XChaCha20StreamEncryption,
    EncryptionError,
    DecryptionError,
    derive_key_from_password,
    derive_key_from_master_key
)

__all__ = [
    'XChaCha20EncryptionService',
    'XChaCha20StreamEncryption',
    'EncryptionError',
    'DecryptionError',
    'derive_key_from_password',
    'derive_key_from_master_key',
]


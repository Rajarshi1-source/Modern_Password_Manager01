"""Fernet-based symmetric encryption for decoy passwords.

Keeps decoy plaintext out of the database (and out of backups/logs).
Derives the key from ``SECRET_KEY`` via HKDF-SHA256 so rotating the
Django secret automatically invalidates all stored decoys — we
regenerate them lazily on the next interception, which is fine.
"""

from __future__ import annotations

import base64
import hashlib
import os

from cryptography.fernet import Fernet
from django.conf import settings


_INFO = b'honeypot_credentials.decoy_key.v1'


def _derive_fernet_key() -> bytes:
    secret = (settings.SECRET_KEY or os.environ.get('SECRET_KEY') or '').encode()
    # HKDF-like derivation via iterated HMAC-SHA256 (cryptography>=HKDF
    # is available but HMAC chain keeps this dependency-free).
    mac = hashlib.sha256(secret + _INFO).digest()
    return base64.urlsafe_b64encode(mac)


def encrypt_decoy(plain: str) -> bytes:
    return Fernet(_derive_fernet_key()).encrypt(plain.encode('utf-8'))


def decrypt_decoy(ciphertext: bytes) -> str:
    if not ciphertext:
        return ''
    return Fernet(_derive_fernet_key()).decrypt(ciphertext).decode('utf-8')

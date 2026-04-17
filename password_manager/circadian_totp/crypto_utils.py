"""Shared symmetric-encryption helpers for circadian_totp.

All secrets (TOTP seeds, OAuth tokens) are encrypted at rest using a Fernet key
derived deterministically from Django ``SECRET_KEY`` plus a fixed purpose
string. This keeps the module self-contained and consistent with
``security.services.time_lock_service``.
"""

from __future__ import annotations

import base64
import hashlib

from cryptography.fernet import Fernet
from django.conf import settings

_PURPOSE = b"circadian_totp.v1"


def _derive_fernet_key() -> bytes:
    material = hashlib.sha256(
        settings.SECRET_KEY.encode("utf-8") + b"::" + _PURPOSE
    ).digest()
    return base64.urlsafe_b64encode(material)


def get_fernet() -> Fernet:
    return Fernet(_derive_fernet_key())


def encrypt_bytes(plaintext: bytes) -> bytes:
    if plaintext is None:
        return b""
    return get_fernet().encrypt(plaintext)


def decrypt_bytes(token: bytes) -> bytes:
    if not token:
        return b""
    return get_fernet().decrypt(bytes(token))


def encrypt_string(value: str) -> bytes:
    return encrypt_bytes((value or "").encode("utf-8"))


def decrypt_string(token: bytes) -> str:
    return decrypt_bytes(token).decode("utf-8") if token else ""

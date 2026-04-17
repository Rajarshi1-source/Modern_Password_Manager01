"""Shared Fernet helpers for decentralized_identity."""

from __future__ import annotations

import base64
import hashlib

from cryptography.fernet import Fernet
from django.conf import settings

_PURPOSE = b"decentralized_identity.v1"


def _derive_fernet_key() -> bytes:
    material = hashlib.sha256(
        settings.SECRET_KEY.encode("utf-8") + b"::" + _PURPOSE
    ).digest()
    return base64.urlsafe_b64encode(material)


def get_fernet() -> Fernet:
    return Fernet(_derive_fernet_key())


def encrypt_bytes(plaintext: bytes) -> bytes:
    return get_fernet().encrypt(plaintext)


def decrypt_bytes(token: bytes) -> bytes:
    return get_fernet().decrypt(bytes(token))

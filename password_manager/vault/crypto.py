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

def encrypt_vault_item(data, key):
    """Encrypt vault item data using Fernet symmetric encryption."""
    import json
    if isinstance(data, dict):
        data = json.dumps(data)
    if isinstance(data, str):
        data = data.encode('utf-8')
    padded_key = hashlib.sha256(key if isinstance(key, bytes) else key.encode()).digest()
    fernet_key = base64.urlsafe_b64encode(padded_key)
    f = Fernet(fernet_key)
    return f.encrypt(data).decode('utf-8')


def decrypt_vault_item(encrypted_data, key):
    """Decrypt vault item data."""
    import json
    padded_key = hashlib.sha256(key if isinstance(key, bytes) else key.encode()).digest()
    fernet_key = base64.urlsafe_b64encode(padded_key)
    f = Fernet(fernet_key)
    decrypted = f.decrypt(
        encrypted_data.encode('utf-8') if isinstance(encrypted_data, str) else encrypted_data
    )
    try:
        return json.loads(decrypted.decode('utf-8'))
    except json.JSONDecodeError:
        return decrypted.decode('utf-8')


def derive_auth_key(password, salt, iterations=100000):
    """Derive authentication key for verifying master password"""
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=iterations,
    )
    return base64.b64encode(kdf.derive(password.encode()))

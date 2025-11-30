import os
import base64
import hashlib
import logging
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt
from cryptography.fernet import Fernet
from argon2 import PasswordHasher, Type
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
    
    try:
        ph = PasswordHasher(
            time_cost=time_cost,
            memory_cost=memory_cost,
            parallelism=parallelism,
            hash_len=32,  # 32 bytes for AES-256
            salt_len=16,
            type=argon2.Type.ID  # Argon2id for balanced security
        )
        
        # Hash password with salt
        key = ph.hash(password + salt.hex())
        
        # Derive final key using SHA-256 for consistent output
        return base64.urlsafe_b64encode(hashlib.sha256(key.encode()).digest())
    except Exception as e:
        logger.error(f'Argon2 key derivation failed: {e}')
        raise ValueError('Key derivation failed')

def derive_auth_key(password, salt, iterations=100000):
    """Derive authentication key for verifying master password"""
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=iterations,
    )
    return base64.b64encode(kdf.derive(password.encode()))

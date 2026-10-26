"""
Server-side storage of the client's master-password ``auth_hash``.

The browser sends ``auth_hash`` = PBKDF2-SHA256(master password, email,
310 000 iterations). Stored as sent, a database leak lets an attacker guess
master passwords offline at PBKDF2 cost, cheaper than the Argon2id login
verifier. So ``UserSalt.auth_hash`` (auth_module and vault) stores a Django
password-hasher record of it instead (Argon2id, the first entry of
``PASSWORD_HASHERS``): each guess then costs PBKDF2 plus Argon2id, and the
record verifies the value without revealing it.

The record is kept in the existing BinaryField as the UTF-8 hasher string.
Rows written before this change hold the raw 32 bytes; migration
auth_module 0021 rewrites them (the server has the raw value, so no client
is needed), and ``check_auth_hash`` still accepts a raw row so a row missed
by the migration is upgraded on its next successful check.
"""

import base64
import hmac

from django.contrib.auth.hashers import check_password, identify_hasher, make_password


def _encode(raw: bytes) -> str:
    return base64.b64encode(bytes(raw)).decode('ascii')


def make_auth_hash_record(raw: bytes) -> bytes:
    """The value to store for the client's ``auth_hash`` bytes."""
    if not raw:
        raise ValueError('auth_hash is empty')
    return make_password(_encode(raw)).encode('ascii')


def is_hashed_record(stored) -> bool:
    try:
        identify_hasher(bytes(stored or b'').decode('ascii'))
        return True
    except (UnicodeDecodeError, ValueError):
        return False


def check_auth_hash(stored, raw: bytes) -> bool:
    """True if ``raw`` (the client's auth_hash bytes) matches ``stored``."""
    stored = bytes(stored or b'')
    if not stored or not raw:
        return False
    if is_hashed_record(stored):
        return check_password(_encode(raw), stored.decode('ascii'))
    # Raw row from before the migration.
    return hmac.compare_digest(stored, bytes(raw))


def verify_and_upgrade(salt_obj, raw: bytes) -> bool:
    """Check ``raw`` against ``salt_obj.auth_hash`` and rewrite a raw row as a
    record on success."""
    stored = bytes(salt_obj.auth_hash or b'')
    if not check_auth_hash(stored, raw):
        return False
    if not is_hashed_record(stored):
        # Conditional on the value just checked: a concurrent change_master
        # that wrote a new record is not overwritten with the old password's.
        record = make_auth_hash_record(raw)
        model = type(salt_obj)
        if not model.objects.filter(pk=salt_obj.pk, auth_hash=stored).update(auth_hash=record):
            # It changed meanwhile: answer for the current value instead.
            salt_obj.refresh_from_db(fields=['auth_hash'])
            return check_auth_hash(salt_obj.auth_hash, raw)
        salt_obj.auth_hash = record
    return True

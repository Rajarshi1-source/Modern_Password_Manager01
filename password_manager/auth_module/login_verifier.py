"""
Login verifier: what sign-in checks instead of the master password.

The browser derives the verifier from the master password with Argon2id
(``frontend/src/services/loginVerifier.js``):

    salt     = SHA-256("pwm-login-verifier-v1|" + lower(trim(username)))
    verifier = base64(Argon2id(master_password, salt, t=3, m=64 MiB, p=2, 32 bytes))

The salt is domain-separated from every vault KEK (those use random salts
stored in their envelopes), so the verifier is a different value from any
key that decrypts the vault. The verifier is sent as the ``password`` of
the normal sign-in endpoints and stored as the Django password, which
hashes it again server-side, so ``authenticate()`` and every view built on
it need no change. The server never receives the master password.

Accounts created before this scheme have the raw master password as their
Django password. Their first sign-in sends the verifier and, if the client
has not signed this account in with a verifier before, the old password as
``legacy_password``. ``migrate_legacy_login`` checks that old password once
and, if it matches, replaces it with the verifier; from then on
``legacy_password`` is ignored for that account.
"""
import base64
import binascii
import logging

from django.contrib.auth.password_validation import validate_password
from django.db import transaction
from django.utils import timezone

logger = logging.getLogger(__name__)

VERIFIER_SCHEME = 'lv1'
VERIFIER_BYTES = 32

LEGACY_PASSWORD_FIELD = 'legacy_password'


def is_login_verifier(value):
    """True if ``value`` has the shape of a verifier (base64 of 32 bytes).

    The shape is all the server can check: the verifier is derived from a
    secret it never sees."""
    if not isinstance(value, str) or len(value) != 44:
        return False
    try:
        return len(base64.b64decode(value, validate=True)) == VERIFIER_BYTES
    except (binascii.Error, ValueError):
        return False


def uses_login_verifier(user):
    from .models import LoginVerifierState
    return LoginVerifierState.objects.filter(user=user).exists()


def set_login_verifier(user, verifier):
    """Make ``verifier`` the credential sign-in checks for ``user``.

    Callers run this inside the transaction that also writes whatever else
    the new master password changes (the wrapped vault key, the auth hash),
    so sign-in and vault unlock never disagree about which password is in
    force."""
    if not is_login_verifier(verifier):
        raise ValueError('not a login verifier')
    # The configured validators see the verifier, not the master password
    # (the server never receives that; its strength is checked in the
    # browser). A 44-character base64 verifier always passes them, so this
    # only guards the boundary.
    validate_password(verifier, user)
    user.set_password(verifier)
    user.save(update_fields=['password'])
    mark_login_verifier(user)


def mark_login_verifier(user):
    """Record that ``user``'s Django password is already a verifier."""
    from .models import LoginVerifierState
    LoginVerifierState.objects.update_or_create(
        user=user,
        defaults={'scheme': VERIFIER_SCHEME, 'set_at': timezone.now()},
    )


def revoke_sessions(user):
    """End every session of ``user`` after its credential was replaced
    through recovery or an email reset: blacklist its live refresh tokens
    and drop its legacy DRF token."""
    from rest_framework.authtoken.models import Token
    try:
        from rest_framework_simplejwt.token_blacklist.models import (
            BlacklistedToken,
            OutstandingToken,
        )
    except ImportError:  # blacklist app not installed
        OutstandingToken = None
    if OutstandingToken is not None:
        live_ids = (
            OutstandingToken.objects
            .filter(user=user, blacklistedtoken__isnull=True)
            .values_list('id', flat=True)
        )
        BlacklistedToken.objects.bulk_create(
            [BlacklistedToken(token_id=token_id) for token_id in live_ids],
            ignore_conflicts=True,
        )
    Token.objects.filter(user=user).delete()


def migrate_legacy_login(username, verifier, legacy_password):
    """Switch an account that still signs in with its master password to
    ``verifier``, if ``legacy_password`` is that master password.

    Runs before the sign-in serializer authenticates, so a successful
    migration is followed by a normal verifier sign-in, and every failure
    (no such account, already migrated, wrong password, malformed
    verifier) leaves the account as it was and falls through to the same
    "invalid credentials" answer. Returns True if the account was switched.
    """
    from django.contrib.auth import get_user_model
    from django.contrib.auth.hashers import make_password
    if (
        not isinstance(username, str)
        or not isinstance(legacy_password, str)
        or not legacy_password
        or not is_login_verifier(verifier)
    ):
        return False
    User = get_user_model()
    with transaction.atomic():
        user = (
            User.objects.select_for_update()
            .filter(**{User.USERNAME_FIELD: username})
            .first()
        )
        if user is None or not user.is_active or uses_login_verifier(user):
            # Hash once anyway, as Django's ModelBackend does for an unknown
            # user, so the time taken does not say which case this was.
            make_password(legacy_password)
            return False
        if not user.check_password(legacy_password):
            return False
        set_login_verifier(user, verifier)
    logger.info('Login verifier enabled for user_id=%s at sign-in', user.pk)
    return True

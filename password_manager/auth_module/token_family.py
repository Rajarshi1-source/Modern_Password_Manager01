"""
JWT Refresh Token Family Enforcement
======================================

Enforces the REFRESH_TOKEN_FAMILY_MAX_SIZE setting from SIMPLE_JWT,
which djangorestframework-simplejwt does not support natively.

When a user has more active (non-blacklisted) outstanding refresh tokens
than the configured max, the oldest tokens are automatically blacklisted.
This effectively limits concurrent logged-in devices per user.

Behaviour:
    - Max size defaults to 5 (from settings.SIMPLE_JWT['REFRESH_TOKEN_FAMILY_MAX_SIZE'])
    - When the (max+1)th token is issued, the oldest outstanding token is blacklisted
    - "Oldest" is determined by OutstandingToken.created_at timestamp
    - Token blacklisting uses the built-in token_blacklist app

Usage:
    In settings.py SIMPLE_JWT:
        'TOKEN_OBTAIN_SERIALIZER': 'auth_module.token_family.FamilyLimitedTokenObtainPairSerializer',
"""

import logging

from asgiref.sync import sync_to_async
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer, TokenRefreshSerializer
from rest_framework_simplejwt.settings import api_settings

from .login_verifier import LEGACY_PASSWORD_FIELD, lock_sessions, migrate_legacy_login

logger = logging.getLogger(__name__)


def get_family_max_size() -> int:
    """Get the maximum refresh token family size from settings."""
    simple_jwt = getattr(settings, 'SIMPLE_JWT', {})
    return simple_jwt.get('REFRESH_TOKEN_FAMILY_MAX_SIZE', 5)


def enforce_token_family_limit(user) -> int:
    """
    Enforce the refresh token family size limit for a user.

    If the user has more outstanding (non-blacklisted) refresh tokens
    than REFRESH_TOKEN_FAMILY_MAX_SIZE, blacklist the oldest ones.

    The count and the blacklisting run in one transaction with the user's
    row locked, so concurrent logins for the same user are serialized: each
    sees the others' new tokens and blacklists, instead of both picking the
    same "oldest" tokens (one of them then failed with an IntegrityError).
    The excess is blacklisted in a single bulk insert.

    Args:
        user: The Django User instance.

    Returns:
        The number of tokens blacklisted.
    """
    from rest_framework_simplejwt.token_blacklist.models import (
        OutstandingToken,
        BlacklistedToken,
    )

    max_size = get_family_max_size()

    with transaction.atomic():
        # Row lock. SQLite ignores select_for_update(): there a concurrent
        # pass can fail with "database is locked" when bulk_create upgrades
        # its read to a write, and the login serializer logs and skips it.
        get_user_model().objects.select_for_update().filter(pk=user.pk).exists()

        live_ids = list(
            OutstandingToken.objects
            .filter(user=user, blacklistedtoken__isnull=True)
            .order_by('created_at', 'id')
            .values_list('id', flat=True)
        )
        excess = len(live_ids) - max_size
        if excess <= 0:
            return 0  # Under the limit, nothing to do

        BlacklistedToken.objects.bulk_create(
            [BlacklistedToken(token_id=token_id) for token_id in live_ids[:excess]],
            ignore_conflicts=True,
        )

    logger.info(
        "Token family enforcement: blacklisted %d oldest refresh token(s) for "
        "user %s (limit=%d, had=%d)",
        excess, user.pk, max_size, len(live_ids),
    )
    return excess


async def aenforce_token_family_limit(user) -> int:
    """
    ``enforce_token_family_limit`` for async views and consumers.

    Runs the ORM work in Django's thread-sensitive sync executor (the ORM is
    synchronous). Today every caller is a sync view, so this exists only for
    future async callers; wrapping the sync serializer in async would not
    unblock anything, because Django already runs sync views off the event
    loop under ASGI.
    """
    return await sync_to_async(enforce_token_family_limit, thread_sensitive=True)(user)


class FamilyLimitedTokenObtainPairSerializer(TokenObtainPairSerializer):
    """
    Custom TokenObtainPairSerializer that enforces the refresh token
    family size limit after issuing a new token pair.

    Drop-in replacement — just set in SIMPLE_JWT config:
        'TOKEN_OBTAIN_SERIALIZER': 'auth_module.token_family.FamilyLimitedTokenObtainPairSerializer'
    """

    def validate(self, attrs):
        # An account still on its master password switches to the login
        # verifier here, before the normal check runs on the verifier.
        migrate_legacy_login(
            attrs.get(self.username_field),
            attrs.get('password'),
            self.initial_data.get(LEGACY_PASSWORD_FIELD),
        )

        # Standard validation + token generation
        data = super().validate(attrs)

        # Enforce family limit after the new refresh token is created
        try:
            enforce_token_family_limit(self.user)
        except Exception as e:
            # Never fail login due to family enforcement errors
            logger.error(
                f"Token family enforcement error for user {self.user.id}: {e}"
            )

        return data


class RevocationSafeTokenRefreshSerializer(TokenRefreshSerializer):
    """TokenRefreshSerializer that rotates under the account lock
    ``revoke_sessions`` also takes, re-checking the blacklist once it is
    held. Otherwise a refresh that passed its blacklist check just before a
    reset or recovery could still write a replacement token after the
    revocation's scan, and that token would outlive the reset.

        'TOKEN_REFRESH_SERIALIZER': 'auth_module.token_family.RevocationSafeTokenRefreshSerializer'
    """

    def validate(self, attrs):
        refresh = self.token_class(attrs["refresh"])
        with transaction.atomic():
            lock_sessions(refresh.payload.get(api_settings.USER_ID_CLAIM))
            refresh.check_blacklist()  # TokenError -> the view answers 401
            return super().validate(attrs)

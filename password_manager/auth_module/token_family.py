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
from django.conf import settings
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.tokens import RefreshToken

logger = logging.getLogger(__name__)


def get_family_max_size() -> int:
    """Get the maximum refresh token family size from settings."""
    simple_jwt = getattr(settings, 'SIMPLE_JWT', {})
    return simple_jwt.get('REFRESH_TOKEN_FAMILY_MAX_SIZE', 5)


def enforce_token_family_limit(user):
    """
    Enforce the refresh token family size limit for a user.

    If the user has more outstanding (non-blacklisted) refresh tokens
    than REFRESH_TOKEN_FAMILY_MAX_SIZE, blacklist the oldest ones.

    Args:
        user: The Django User instance.
    """
    from rest_framework_simplejwt.token_blacklist.models import (
        OutstandingToken,
        BlacklistedToken,
    )

    max_size = get_family_max_size()

    # Get all outstanding tokens for this user that are NOT blacklisted,
    # ordered by created_at ascending (oldest first).
    outstanding = (
        OutstandingToken.objects
        .filter(user=user)
        .exclude(id__in=BlacklistedToken.objects.values_list('token_id', flat=True))
        .order_by('created_at')
    )

    count = outstanding.count()

    if count <= max_size:
        return  # Under the limit, nothing to do

    # Number of tokens to blacklist (keep only max_size)
    excess = count - max_size
    tokens_to_blacklist = outstanding[:excess]

    blacklisted_count = 0
    for token in tokens_to_blacklist:
        try:
            BlacklistedToken.objects.get_or_create(token=token)
            blacklisted_count += 1
        except Exception as e:
            logger.error(
                f"Failed to blacklist token {token.id} for user {user.id}: {e}"
            )

    if blacklisted_count > 0:
        logger.info(
            f"Token family enforcement: blacklisted {blacklisted_count} oldest "
            f"refresh token(s) for user {user.id} "
            f"(limit={max_size}, had={count})"
        )


class FamilyLimitedTokenObtainPairSerializer(TokenObtainPairSerializer):
    """
    Custom TokenObtainPairSerializer that enforces the refresh token
    family size limit after issuing a new token pair.

    Drop-in replacement — just set in SIMPLE_JWT config:
        'TOKEN_OBTAIN_SERIALIZER': 'auth_module.token_family.FamilyLimitedTokenObtainPairSerializer'
    """

    def validate(self, attrs):
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


class FamilyLimitedRefreshToken(RefreshToken):
    """
    Custom RefreshToken that enforces family limits on rotation.

    When ROTATE_REFRESH_TOKENS is True and a refresh token is used,
    a new one is issued — this class ensures the family limit is
    checked on rotation too.
    """

    def set_jti(self):
        """Override to enforce family limit after rotation."""
        super().set_jti()

    @classmethod
    def for_user(cls, user):
        """Create a new token for a user and enforce family limits."""
        token = super().for_user(user)

        try:
            enforce_token_family_limit(user)
        except Exception as e:
            logger.error(
                f"Token family enforcement error on rotation for user {user.id}: {e}"
            )

        return token

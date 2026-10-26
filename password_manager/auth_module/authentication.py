"""
JWT authentication that honours a reset or recovery.

``revoke_sessions`` (auth_module/login_verifier.py) blacklists the
account's refresh tokens, but an access token is checked only by its
signature and expiry, so one issued before the reset would keep working
for up to ACCESS_TOKEN_LIFETIME. This class also refuses access tokens
issued before the account's last session revocation.
"""
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.authentication import JWTAuthentication

from .login_verifier import access_token_revoked


class RevocableJWTAuthentication(JWTAuthentication):
    def get_user(self, validated_token):
        user = super().get_user(validated_token)
        if access_token_revoked(user, validated_token):
            raise AuthenticationFailed('Token was revoked', code='token_revoked')
        return user

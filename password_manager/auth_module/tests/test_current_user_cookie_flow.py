"""
Tests for `GET /api/auth/me/` in the cookie-auth foundation PR.

The cookie-flow bootstrap (`hooks/useAuth.jsx::initAuth`) fetches
this endpoint after a successful refresh-via-cookie to hydrate
the real user profile (Codex P2 finding on PR #246). The endpoint
itself is also defined in PR #245; when both PRs merge, the
second-merged drops this duplicate file at conflict-resolution
time. Keeping the contents minimal but pinning the contract.
"""
from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient


User = get_user_model()


@pytest.fixture
def cookie_user(db):
    return User.objects.create_user(
        username='cookie-alice',
        email='cookie-alice@example.com',
        password='masterpw1234',  # noqa: S106 — test fixture
    )


@pytest.mark.django_db
class TestCurrentUserViewCookieFlow:
    URL = '/api/auth/me/'

    def test_unauthenticated_returns_401(self):
        assert APIClient().get(self.URL).status_code == 401

    def test_jwt_bearer_works(self, cookie_user):
        """Cookie-flow bootstrap calls /me/ with the access token
        minted by /cookie/token/refresh/. That access token is a
        SimpleJWT bearer; the endpoint must accept it.
        """
        from rest_framework_simplejwt.tokens import AccessToken
        token = str(AccessToken.for_user(cookie_user))
        c = APIClient()
        c.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        resp = c.get(self.URL)
        assert resp.status_code == 200
        body = resp.json()
        assert body['username'] == 'cookie-alice'
        assert body['email'] == 'cookie-alice@example.com'
        # Refresh-token never surfaces in the user profile — defense
        # in depth on top of the SAFE_USER_FIELDS whitelist.
        assert 'refresh' not in body
        assert 'password' not in {k.lower() for k in body.keys()}

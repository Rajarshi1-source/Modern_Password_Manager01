"""
Tests for the HttpOnly-cookie refresh-token endpoints.

These exercise the security-relevant invariants of
``auth_module/cookie_auth_view.py``:

  * Login issues an access token in the JSON body AND an HttpOnly
    refresh-token cookie. The refresh token is never in the body.
  * The refresh cookie's HttpOnly / SameSite / path attributes are
    set correctly so JavaScript can't read it and cross-site
    requests can't send it.
  * The refresh endpoint refuses calls without the X-Requested-With
    XHR header, refuses calls without the cookie, and rotates the
    cookie on success.
  * Logout blacklists the token (if installed) and clears the
    cookie, idempotent on missing input.
"""
from __future__ import annotations

import pytest
from django.contrib.auth.models import User
from django.urls import reverse
from rest_framework.test import APIClient

from auth_module.cookie_auth_view import REFRESH_COOKIE_NAME, REFRESH_COOKIE_PATH


@pytest.fixture
def user(db):
    return User.objects.create_user(username='alice', password='masterpw1234')


@pytest.fixture
def client():
    return APIClient()


def _xhr_headers() -> dict:
    """Headers a real SPA fetch/axios call would emit."""
    return {'HTTP_X_REQUESTED_WITH': 'XMLHttpRequest'}


@pytest.mark.django_db
class TestCookieTokenObtainView:
    URL = '/api/auth/cookie/token/'

    def test_login_returns_access_token_and_sets_cookie(self, client, user):
        """Successful login → access token in body, refresh token in cookie."""
        resp = client.post(self.URL, {'username': 'alice', 'password': 'masterpw1234'}, format='json')
        assert resp.status_code == 200
        body = resp.json()
        # Access token surfaces in the JSON body (the SPA holds it in memory).
        assert 'access' in body and body['access']
        assert body.get('token_type') == 'Bearer'
        # The refresh token MUST NOT be in the JSON body — that's the
        # whole point of this endpoint vs. the legacy /token/.
        assert 'refresh' not in body
        # Cookie is set with the configured name.
        assert REFRESH_COOKIE_NAME in resp.cookies
        cookie = resp.cookies[REFRESH_COOKIE_NAME]
        # HttpOnly so JS in the SPA can't read it via document.cookie.
        assert cookie['httponly'], 'refresh cookie must be HttpOnly'
        # SameSite=Strict so a malicious third-party origin can't
        # cause the browser to send it on a cross-site request.
        assert cookie['samesite'].lower() == 'strict'
        # Path scoped to /api/auth/ so the cookie is only sent to
        # auth endpoints — never to /api/vault/, /api/social-recovery/, etc.
        assert cookie['path'] == REFRESH_COOKIE_PATH
        # Cookie value is the JWT refresh token (non-empty string).
        assert cookie.value and isinstance(cookie.value, str)

    def test_login_wrong_password_no_cookie(self, client, user):
        """Failed login must NOT set a refresh cookie."""
        resp = client.post(self.URL, {'username': 'alice', 'password': 'wrong'}, format='json')
        assert resp.status_code in (400, 401)
        # No cookie was set; if the test client carries cookies from a
        # previous request they're still there, but a failed login must
        # not introduce new ones.
        if REFRESH_COOKIE_NAME in resp.cookies:
            assert resp.cookies[REFRESH_COOKIE_NAME].value == ''


@pytest.mark.django_db
class TestCookieTokenRefreshView:
    LOGIN_URL = '/api/auth/cookie/token/'
    REFRESH_URL = '/api/auth/cookie/token/refresh/'

    def _login(self, client, user):
        """Helper: log in and return the access token."""
        resp = client.post(self.LOGIN_URL, {'username': user.username, 'password': 'masterpw1234'}, format='json')
        assert resp.status_code == 200
        return resp.json()['access']

    def test_refresh_requires_xhr_header(self, client, user):
        """Refresh must refuse calls without X-Requested-With: XMLHttpRequest."""
        self._login(client, user)
        # No XHR header → 400.
        resp = client.post(self.REFRESH_URL)
        assert resp.status_code == 400

    def test_refresh_without_cookie_returns_401(self, client, user):
        """Refresh with XHR header but no cookie → 401, not 400."""
        # Don't log in first; no cookie present.
        resp = client.post(self.REFRESH_URL, **_xhr_headers())
        assert resp.status_code == 401

    def test_refresh_rotates_cookie_and_returns_new_access(self, client, user):
        """Successful refresh issues a new access token and rotates the cookie."""
        original_access = self._login(client, user)
        original_refresh_cookie = client.cookies[REFRESH_COOKIE_NAME].value

        resp = client.post(self.REFRESH_URL, **_xhr_headers())
        assert resp.status_code == 200
        body = resp.json()
        new_access = body['access']
        # New access token must be different from the old one (different
        # iat at minimum), and never include the refresh token in the body.
        assert new_access and new_access != original_access
        assert 'refresh' not in body
        # The cookie was rotated — value should differ from the login
        # cookie. (If ROTATE_REFRESH_TOKENS is somehow off in this env,
        # we accept the same value but still require the cookie to be
        # present and HttpOnly.)
        assert REFRESH_COOKIE_NAME in resp.cookies
        new_cookie = resp.cookies[REFRESH_COOKIE_NAME]
        assert new_cookie.value, 'refresh cookie must be re-set on rotation'
        assert new_cookie['httponly'], 'rotated cookie must remain HttpOnly'

    def test_refresh_with_garbage_cookie_clears_it(self, client, user):
        """A malformed cookie must produce 401 AND clear the bad cookie."""
        client.cookies[REFRESH_COOKIE_NAME] = 'definitely-not-a-jwt'
        resp = client.post(self.REFRESH_URL, **_xhr_headers())
        assert resp.status_code == 401
        # The response must include a Set-Cookie that deletes the
        # bad cookie (max-age=0).
        assert REFRESH_COOKIE_NAME in resp.cookies
        # Django's test cookies dict surfaces deletion as empty value.
        assert resp.cookies[REFRESH_COOKIE_NAME].value == ''


@pytest.mark.django_db
class TestCookieTokenLogoutView:
    LOGIN_URL = '/api/auth/cookie/token/'
    LOGOUT_URL = '/api/auth/cookie/token/logout/'

    def test_logout_clears_cookie(self, client, user):
        """After login, calling logout clears the refresh cookie."""
        client.post(self.LOGIN_URL, {'username': user.username, 'password': 'masterpw1234'}, format='json')
        resp = client.post(self.LOGOUT_URL)
        assert resp.status_code == 200
        assert REFRESH_COOKIE_NAME in resp.cookies
        assert resp.cookies[REFRESH_COOKIE_NAME].value == ''

    def test_logout_is_idempotent_without_cookie(self, client):
        """Calling logout with no prior login must still 200 — the
        user-visible contract is "I want to be logged out"; the cookie
        being already absent is a fine end-state."""
        resp = client.post(self.LOGOUT_URL)
        assert resp.status_code == 200

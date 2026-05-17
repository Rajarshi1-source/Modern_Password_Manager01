"""
Tests for `GET /api/auth/me/`.

Endpoint exists to let the SPA bootstrap hydrate the user profile
without persisting it to localStorage (CodeQL #1048 follow-up on
PR #245). The contract:

  * Authenticated GET → 200 with a whitelisted profile body
  * Unauthenticated GET → 401
  * Body shape matches `SAFE_USER_FIELDS` on the frontend so a
    component switching from cached-localStorage to bootstrap-fetch
    sees the same field set
"""
from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient


User = get_user_model()


@pytest.fixture
def user(db):
    return User.objects.create_user(
        username='alice',
        email='alice@example.com',
        password='masterpw1234',  # noqa: S106 — test fixture
        first_name='Alice',
        last_name='Liddell',
    )


@pytest.fixture
def auth_client(user):
    c = APIClient()
    c.force_authenticate(user=user)
    return c


@pytest.mark.django_db
class TestCurrentUserView:
    URL = '/api/auth/me/'

    def test_unauthenticated_returns_401(self):
        """No credentials at all → 401, never any profile data."""
        resp = APIClient().get(self.URL)
        assert resp.status_code in (401, 403)

    def test_authenticated_returns_whitelisted_profile(self, auth_client, user):
        """Authenticated GET → 200 with whitelisted fields only."""
        resp = auth_client.get(self.URL)
        assert resp.status_code == 200
        body = resp.json()

        # Identity claims.
        assert body['id'] == user.pk
        assert body['username'] == 'alice'
        assert body['email'] == 'alice@example.com'

        # Display fields.
        assert body['first_name'] == 'Alice'
        assert body['last_name'] == 'Liddell'

        # Role flags.
        assert body['is_staff'] is False
        assert body['is_superuser'] is False

        # Joined timestamp present (ISO-8601 string), not null.
        assert isinstance(body['date_joined'], str) and body['date_joined']

    def test_response_shape_is_whitelist_only(self, auth_client):
        """The endpoint must NOT include fields the SPA's
        SAFE_USER_FIELDS whitelist doesn't recognise — e.g.
        `password`, `last_login` raw object, or any future
        backend-only addition. Pinning the key set prevents
        accidental leakage.

        Profile-extension fields (`display_name`, `avatar`,
        `avatar_url`, `locale`, `preferred_language`, `timezone`)
        only appear when `request.user.profile` exists — they're
        in the SAFE_USER_FIELDS whitelist on the frontend but
        not all deployments have a Profile model. The assertion
        below uses `<=` (subset) instead of `==` (equality) so a
        deployment that DOES surface profile fields is also valid
        and the test isn't flaky against Profile-model existence.
        """
        resp = auth_client.get(self.URL)
        assert resp.status_code == 200
        body = resp.json()

        always_present = {
            'id', 'username', 'email',
            'first_name', 'last_name',
            'date_joined',
            'is_staff', 'is_superuser',
        }
        optional_profile_fields = {
            'display_name', 'avatar', 'avatar_url',
            'locale', 'preferred_language', 'timezone',
        }
        allowed = always_present | optional_profile_fields

        # Every key in the response must be in the allowed set
        # (mirror of SAFE_USER_FIELDS) — nothing else is permitted
        # to leak through.
        unexpected = set(body.keys()) - allowed
        assert not unexpected, (
            f'Response keys include non-whitelisted fields: {unexpected}'
        )
        # And the always-present subset must be there.
        missing = always_present - set(body.keys())
        assert not missing, f'Always-present keys missing: {missing}'

    def test_password_hash_never_surfaces(self, auth_client):
        """Defense in depth: the user's password hash must never
        appear in the JSON body, regardless of the whitelist."""
        resp = auth_client.get(self.URL)
        raw_body = resp.content.decode('utf-8')
        # Two independent invariants, each its own assertion so a
        # failure of either is unambiguous in the report. Using
        # `and` joined into a single OR-expression previously made
        # the test pass trivially whenever `$` was absent
        # (which ISO-8601 timestamps guarantee on every response).
        assert 'pbkdf2' not in raw_body.lower(), (
            'password hash algorithm prefix leaked into response body'
        )
        assert 'password' not in {k.lower() for k in resp.json().keys()}, (
            'response has a key named "password"'
        )

    def test_drf_token_auth_works(self, db):
        """Legacy AuthContext.jsx sessions present
        `Authorization: Token <drf_token>`. The endpoint must
        accept that, not just the JWT bearer header — otherwise
        users on the legacy provider get 401 on every reload
        and the bootstrap code drops their token. Codex P2 on
        PR #245 follow-up.
        """
        from rest_framework.authtoken.models import Token
        user = User.objects.create_user(
            username='legacy',
            email='legacy@example.com',
            password='masterpw1234',  # noqa: S106
        )
        token, _ = Token.objects.get_or_create(user=user)
        c = APIClient()
        c.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')
        resp = c.get(self.URL)
        assert resp.status_code == 200, (
            'DRF Token auth must work on /api/auth/me/ '
            'so legacy AuthContext sessions can hydrate on reload'
        )
        assert resp.json()['username'] == 'legacy'

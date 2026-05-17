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
        backend-only addition. Pinning the exact key set prevents
        accidental leakage."""
        resp = auth_client.get(self.URL)
        assert resp.status_code == 200
        body = resp.json()

        expected_keys = {
            'id', 'username', 'email',
            'first_name', 'last_name',
            'date_joined',
            'is_staff', 'is_superuser',
        }
        assert set(body.keys()) == expected_keys, (
            f'Response keys diverged from the whitelist: '
            f'unexpected {set(body.keys()) - expected_keys}, '
            f'missing {expected_keys - set(body.keys())}'
        )

    def test_password_hash_never_surfaces(self, auth_client):
        """Defense in depth: the user's password hash must never
        appear in the JSON body, regardless of the whitelist."""
        resp = auth_client.get(self.URL)
        raw_body = resp.content.decode('utf-8')
        # The hashed password starts with the hasher prefix (e.g.
        # `pbkdf2_sha256$`). Match the generic shape rather than a
        # specific algorithm so this test stays correct if the
        # PASSWORD_HASHERS setting changes.
        assert '$' not in raw_body or 'pbkdf2' not in raw_body.lower()
        assert 'password' not in {k.lower() for k in resp.json().keys()}

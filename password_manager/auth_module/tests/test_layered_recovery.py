"""
Integration tests for the Layered Recovery Mesh (Units 1-7).

This file is INTENTIONALLY tolerant of sibling-unit absence: if any of
the new models/views are not yet present (because their PR has not
landed in this branch), the dependent test classes skip — they do NOT
error at import time. That keeps this PR mergeable on its own.

The keystone here is `TestZeroKnowledgeAssertion` — a meta-test that
greps the new view modules for forbidden cryptographic primitives and
fails the build if any view ever attempts to decrypt the wrapped blob.
That assertion is the one we must never relax.
"""
import base64
import os
import uuid
import pytest
from datetime import timedelta

from django.contrib.auth.models import User
from django.utils import timezone
from rest_framework.test import APIClient

# Sibling-unit imports — wrapped in try/except so the test file always
# loads cleanly. Each test class checks the relevant flag.
try:
    from auth_module.recovery_models_v2 import (
        VaultWrappedDEK,
        RecoveryWrappedDEK,
    )
    HAS_WRAPPED_DEK = True
except Exception:
    HAS_WRAPPED_DEK = False

try:
    from auth_module.time_locked_models import (
        TimeLockedRecovery,
        ServerHalfReleaseLog,
    )
    HAS_TIME_LOCKED = True
except Exception:
    HAS_TIME_LOCKED = False


VALID_BLOB = {
    'v': 'wdek-1',
    'kdf': 'argon2id',
    'kdf_params': {'t': 3, 'm': 65536, 'p': 2},
    'salt': 'c2FsdHNhbHRzYWx0c2E=',
    'iv': 'aXZpdml2aXZpdml2',
    'wrapped': 'd3JhcHBlZHdyYXBwZWR3cmFwcGVk',
}


@pytest.fixture
def user(db):
    return User.objects.create_user(username='alice', password='masterpw1234')


@pytest.fixture
def auth_client(user):
    c = APIClient()
    c.force_authenticate(user=user)
    return c


# ----------------------------------------------------------------------
# Unit 4 — VaultWrappedDEKView
# ----------------------------------------------------------------------

@pytest.mark.skipif(not HAS_WRAPPED_DEK, reason='Unit 1 not landed')
@pytest.mark.django_db
class TestVaultWrappedDEKView:
    URL = '/api/auth/vault/wrapped-dek/'

    def test_get_returns_not_enrolled_when_no_row(self, auth_client):
        r = auth_client.get(self.URL)
        assert r.status_code == 200
        assert r.json() == {'enrolled': False}

    def test_put_creates_row_with_dek_id(self, auth_client, user):
        r = auth_client.put(self.URL, {'blob': VALID_BLOB}, format='json')
        assert r.status_code == 200
        assert 'dek_id' in r.json()
        assert VaultWrappedDEK.objects.filter(user=user).count() == 1

    def test_put_invalid_envelope_rejected(self, auth_client):
        r = auth_client.put(self.URL, {'blob': {'v': 'wrong'}}, format='json')
        assert r.status_code == 400

    def test_put_rotation_requires_dek_id(self, auth_client, user):
        r1 = auth_client.put(self.URL, {'blob': VALID_BLOB}, format='json')
        dek_id = r1.json()['dek_id']
        # Rotation without dek_id -> 409
        r2 = auth_client.put(self.URL, {'blob': VALID_BLOB}, format='json')
        assert r2.status_code == 409
        # Rotation with correct dek_id -> 200, dek_id stable
        r3 = auth_client.put(self.URL, {'blob': VALID_BLOB, 'dek_id': dek_id}, format='json')
        assert r3.status_code == 200
        assert r3.json()['dek_id'] == dek_id

    def test_unauthenticated_rejected(self):
        c = APIClient()
        assert c.get(self.URL).status_code in (401, 403)


# ----------------------------------------------------------------------
# Unit 5 — RecoveryFactorListCreateView
# ----------------------------------------------------------------------

@pytest.mark.skipif(not HAS_WRAPPED_DEK, reason='Unit 1 not landed')
@pytest.mark.django_db
class TestRecoveryFactorView:
    URL = '/api/auth/vault/recovery-factors/'
    DEK_URL = '/api/auth/vault/wrapped-dek/'

    def _enroll_dek(self, client):
        r = client.put(self.DEK_URL, {'blob': VALID_BLOB}, format='json')
        return r.json()['dek_id']

    def test_post_requires_dek_enrollment(self, auth_client):
        r = auth_client.post(self.URL, {
            'factor_type': 'recovery_key', 'blob': VALID_BLOB,
            'dek_id': str(uuid.uuid4()),
        }, format='json')
        assert r.status_code == 400

    def test_post_requires_matching_dek_id(self, auth_client):
        self._enroll_dek(auth_client)
        r = auth_client.post(self.URL, {
            'factor_type': 'recovery_key', 'blob': VALID_BLOB,
            'dek_id': str(uuid.uuid4()),
        }, format='json')
        assert r.status_code == 409

    def test_post_creates_factor(self, auth_client, user):
        dek_id = self._enroll_dek(auth_client)
        r = auth_client.post(self.URL, {
            'factor_type': 'recovery_key', 'blob': VALID_BLOB,
            'dek_id': dek_id, 'meta': {},
        }, format='json')
        assert r.status_code == 201
        assert RecoveryWrappedDEK.objects.filter(user=user).count() == 1

    def test_get_lists_active_only(self, auth_client, user):
        dek_id = self._enroll_dek(auth_client)
        auth_client.post(self.URL, {
            'factor_type': 'recovery_key', 'blob': VALID_BLOB, 'dek_id': dek_id,
        }, format='json')
        RecoveryWrappedDEK.objects.filter(user=user).update(status='revoked')
        r = auth_client.get(self.URL)
        assert r.status_code == 200
        assert r.json() == []

    def test_unique_active_recovery_key(self, auth_client):
        dek_id = self._enroll_dek(auth_client)
        body = {'factor_type': 'recovery_key', 'blob': VALID_BLOB, 'dek_id': dek_id}
        r1 = auth_client.post(self.URL, body, format='json')
        assert r1.status_code == 201
        r2 = auth_client.post(self.URL, body, format='json')
        # Partial unique constraint enforced at DB layer
        assert r2.status_code in (400, 409, 500)


# ----------------------------------------------------------------------
# Unit 6 — TimeLocked* views
# ----------------------------------------------------------------------

@pytest.mark.skipif(not HAS_TIME_LOCKED, reason='Unit 2 not landed')
@pytest.mark.django_db
class TestTimeLocked:
    ENROLL = '/api/auth/vault/time-locked/enroll/'
    INITIATE = '/api/auth/vault/time-locked/initiate/'
    RELEASE = '/api/auth/vault/time-locked/release/'
    ACK = '/api/auth/vault/time-locked/canary-ack/'

    def test_enroll_stores_server_half(self, auth_client, user):
        r = auth_client.post(self.ENROLL, {
            'server_half': base64.b64encode(b'opaque-share-bytes').decode(),
            'half_metadata': {'salt': 'c2FsdA==', 'kdf_params': {'t': 3}},
        }, format='json')
        assert r.status_code == 201
        assert TimeLockedRecovery.objects.filter(user=user, is_active=True).count() == 1

    def test_release_refused_before_delay(self, user, db):
        rec = TimeLockedRecovery.objects.create(
            user=user, server_half=b'opaque', half_metadata={},
            release_after=timezone.now() + timedelta(days=7),
            initiated_at=timezone.now(), is_active=True,
        )
        r = APIClient().post(self.RELEASE, {'username': user.username}, format='json')
        assert r.status_code == 403
        assert ServerHalfReleaseLog.objects.filter(
            recovery=rec, succeeded=False, refusal_reason='too_early',
        ).count() == 1

    def test_release_succeeds_after_delay(self, user, db):
        TimeLockedRecovery.objects.create(
            user=user, server_half=b'opaque-share-bytes', half_metadata={},
            release_after=timezone.now() - timedelta(seconds=1),
            initiated_at=timezone.now() - timedelta(days=8),
            is_active=True,
        )
        r = APIClient().post(self.RELEASE, {'username': user.username}, format='json')
        assert r.status_code == 200
        assert base64.b64decode(r.json()['server_half']) == b'opaque-share-bytes'

    def test_canary_ack_cancels_recovery(self, user, db):
        rec = TimeLockedRecovery.objects.create(
            user=user, server_half=b'x', half_metadata={},
            release_after=timezone.now() + timedelta(days=7),
            canary_ack_token='abc-token-xyz',
            initiated_at=timezone.now(), is_active=True,
        )
        r = APIClient().post(self.ACK, {'token': 'abc-token-xyz'}, format='json')
        assert r.status_code == 200
        rec.refresh_from_db()
        assert rec.is_active is False
        assert rec.canary_state == 'acknowledged'

    def test_initiate_does_not_leak_existence(self):
        r = APIClient().post(self.INITIATE, {'username': 'ghost-account'}, format='json')
        assert r.status_code == 200


# ----------------------------------------------------------------------
# Zero-knowledge meta-assertion — keystone of the whole design.
# ----------------------------------------------------------------------

class TestZeroKnowledgeAssertion:
    """
    Greps the new view modules for forbidden cryptographic primitives.
    If any view ever calls AES.new(), Fernet(), unwrap_key(),
    argon2.hash(), etc., this fails the build.

    Skipping a file is permitted only when that file does not exist
    yet (sibling unit unlanded). It is NEVER permitted to weaken or
    remove these patterns once the corresponding view has landed.
    """

    FORBIDDEN_PATTERNS = [
        'AES.new(',
        'cipher.decrypt(',
        'Fernet(',
        'argon2.hash(',
        'hash_password(',
        'unwrap_key(',
        'decrypt_blob(',
        'wrapped_dek_decrypt',
    ]

    VIEW_PATHS = [
        'auth_module/views/wrapped_dek_view.py',
        'auth_module/views/recovery_factor_view.py',
        'auth_module/views/time_locked_view.py',
    ]

    @pytest.mark.parametrize('rel_path', VIEW_PATHS)
    def test_view_does_not_decrypt(self, rel_path):
        # Resolve the view file relative to the password_manager package.
        # Tests are invoked from password_manager/, so views live one
        # directory up from auth_module/tests.
        candidate = os.path.join(os.path.dirname(__file__), '..', '..', rel_path)
        candidate = os.path.normpath(candidate)
        if not os.path.exists(candidate):
            pytest.skip(f'{rel_path} not yet landed in this branch')
        with open(candidate, encoding='utf-8') as f:
            source = f.read()
        violations = [p for p in self.FORBIDDEN_PATTERNS if p in source]
        assert not violations, (
            f'ZK violation in {rel_path}: forbidden patterns {violations}. '
            f'Server views must NEVER decrypt the wrapped blob.'
        )

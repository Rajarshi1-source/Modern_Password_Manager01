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
# Narrow exception class on purpose: only ModuleNotFoundError /
# ImportError indicate "the sibling unit hasn't merged yet". A
# SyntaxError, NameError, or any other failure inside an already-
# landed module means a real regression and MUST fail CI rather than
# being silently downgraded to "skip the whole test class".
try:
    from auth_module.recovery_models_v2 import (
        VaultWrappedDEK,
        RecoveryWrappedDEK,
    )
    HAS_WRAPPED_DEK = True
except (ImportError, ModuleNotFoundError):
    HAS_WRAPPED_DEK = False

try:
    from auth_module.time_locked_models import (
        TimeLockedRecovery,
        ServerHalfReleaseLog,
    )
    HAS_TIME_LOCKED = True
except (ImportError, ModuleNotFoundError):
    HAS_TIME_LOCKED = False


VALID_BLOB = {
    'v': 'wdek-1',
    'kdf': 'argon2id',
    'kdf_params': {'t': 3, 'm': 65536, 'p': 2},
    'salt': 'c2FsdHNhbHRzYWx0c2E=',
    'iv': 'aXZpdml2aXZpdml2',
    'wrapped': 'd3JhcHBlZHdyYXBwZWR3cmFwcGVk',
}

# Proof-of-secret-knowledge hash the wrapped-DEK rotation endpoint
# checks at recovery time. The recovery-factor create/bundle endpoints
# require it at enrollment so the server has bytes to compare against
# during a later rotation. Shape is 64-char lowercase hex (a SHA-256
# digest of "rotation-auth-v1:" + recovery_secret); the server never
# decrypts it, only memcmp's it under hmac.compare_digest.
VALID_AUTH_HASH = 'a' * 64


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
            'auth_hash': VALID_AUTH_HASH,
        }, format='json')
        assert r.status_code == 201
        assert RecoveryWrappedDEK.objects.filter(user=user).count() == 1

    def test_get_lists_active_only(self, auth_client, user):
        dek_id = self._enroll_dek(auth_client)
        auth_client.post(self.URL, {
            'factor_type': 'recovery_key', 'blob': VALID_BLOB, 'dek_id': dek_id,
            'auth_hash': VALID_AUTH_HASH,
        }, format='json')
        RecoveryWrappedDEK.objects.filter(user=user).update(status='revoked')
        r = auth_client.get(self.URL)
        assert r.status_code == 200
        assert r.json() == []

    def test_unique_active_recovery_key(self, auth_client):
        dek_id = self._enroll_dek(auth_client)
        body = {
            'factor_type': 'recovery_key',
            'blob': VALID_BLOB,
            'dek_id': dek_id,
            'auth_hash': VALID_AUTH_HASH,
        }
        r1 = auth_client.post(self.URL, body, format='json')
        assert r1.status_code == 201
        r2 = auth_client.post(self.URL, body, format='json')
        # Partial unique constraint enforced at DB layer. The view (#214)
        # catches IntegrityError and translates it to 409. We intentionally
        # do NOT accept 5xx here — a 500 means the view failed to handle
        # the constraint and is a real regression we want CI to fail on.
        assert r2.status_code in (400, 409), (
            f'duplicate enrollment must be a client/conflict error, '
            f'got {r2.status_code}: {r2.content[:200]!r}'
        )


# ----------------------------------------------------------------------
# Unit 6 — TimeLocked* views
# ----------------------------------------------------------------------

@pytest.mark.skipif(not HAS_TIME_LOCKED, reason='Unit 2 not landed')
@pytest.mark.django_db
class TestTimeLocked:
    # NOTE: the standalone /enroll/ URL was retired (see comment in
    # auth_module/urls.py around vault/time-locked/enroll-bundle/).
    # All tier-3 enrollments must now go through the atomic bundle
    # endpoint that writes the TimeLockedRecovery server half AND
    # the matching RecoveryWrappedDEK row in one transaction.
    ENROLL_BUNDLE = '/api/auth/vault/time-locked/enroll-bundle/'
    DEK_URL = '/api/auth/vault/wrapped-dek/'
    INITIATE = '/api/auth/vault/time-locked/initiate/'
    RELEASE = '/api/auth/vault/time-locked/release/'
    ACK = '/api/auth/vault/time-locked/canary-ack/'

    def test_enroll_stores_server_half(self, auth_client, user):
        # The bundle endpoint is gated on a prior wrapped-DEK
        # enrollment (proof-of-DEK-possession via dek_id). Enroll one
        # first so the tier-3 bundle has a dek_id to bind against.
        wdek_resp = auth_client.put(self.DEK_URL, {'blob': VALID_BLOB}, format='json')
        dek_id = wdek_resp.json()['dek_id']

        r = auth_client.post(self.ENROLL_BUNDLE, {
            'server_half': base64.b64encode(b'opaque-share-bytes').decode(),
            'half_metadata': {'salt': 'c2FsdA==', 'kdf_params': {'t': 3}},
            'dek_id': dek_id,
            'blob': VALID_BLOB,
            'auth_hash': VALID_AUTH_HASH,
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
        # By design (see TimeLockedCanaryAckView.post comment), the
        # canary-ack endpoint flips canary_state but deliberately
        # KEEPS is_active=True. That keeps the row visible to a
        # subsequent /release/ call so it can read the ACKNOWLEDGED
        # state under the same row lock and refuse with
        # 'cancelled_by_canary' — a property test_release_refused_
        # after_canary_ack exercises end-to-end. Asserting is_active
        # False here would force the view back into a design that
        # erases the cancel signal from the forensics trail.
        assert rec.canary_state == 'acknowledged'
        assert rec.is_active is True

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

    Path resolution and presence are HARD requirements: a missing file
    is treated as a CI failure, not a skip. The previous "skip when
    file doesn't exist" behavior created a blind spot — a rename or
    reorganisation would silently disable the ZK guard while keeping
    CI green. Any future move of these view modules must update
    VIEW_PATHS in lockstep so the guard keeps firing on the new
    location.

    PRs #213/#214/#215 — which created the views — are all merged on
    main, so the files MUST exist whenever this test runs.
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
        # Each view sits at the auth_module top level (NOT in a
        # views/ subpackage — that would shadow auth_module/views.py
        # and break the existing AuthViewSet routes; see Codex P0
        # comments on PRs #213/#214/#215 for the full rationale).
        'auth_module/wrapped_dek_view.py',
        'auth_module/recovery_factor_view.py',
        'auth_module/time_locked_view.py',
    ]

    @pytest.mark.parametrize('rel_path', VIEW_PATHS)
    def test_view_does_not_decrypt(self, rel_path):
        # Resolve the view file relative to the password_manager
        # package. Tests are invoked from password_manager/, so views
        # live one directory up from auth_module/tests.
        candidate = os.path.normpath(
            os.path.join(os.path.dirname(__file__), '..', '..', rel_path)
        )
        # HARD assertion: missing target = ZK guard is broken, fail CI.
        # Do NOT downgrade this to pytest.skip — that would let a
        # rename or refactor silently disable the security check.
        assert os.path.exists(candidate), (
            f'ZK guard target missing: {rel_path!r} (looked at {candidate!r}). '
            f'If the file was renamed, update VIEW_PATHS in this test in '
            f'the same commit; never let the guard go quiet.'
        )
        with open(candidate, encoding='utf-8') as f:
            source = f.read()
        violations = [p for p in self.FORBIDDEN_PATTERNS if p in source]
        assert not violations, (
            f'ZK violation in {rel_path}: forbidden patterns {violations}. '
            f'Server views must NEVER decrypt the wrapped blob.'
        )

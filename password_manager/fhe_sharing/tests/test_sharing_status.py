"""
Tests for `/api/fhe-sharing/status/`.

The status endpoint is the client's source of truth for feature
flags: it reports which cipher suites are supported server-side and
whether the PRE feature flag is enabled.  The frontend feature flag
code in `preClient.isPreAvailable()` and the extension's popup panel
both rely on it, so we assert an explicit contract here.
"""

import pytest
from django.contrib.auth.models import User
from django.test import override_settings
from rest_framework.test import APIClient


pytestmark = pytest.mark.django_db


@pytest.fixture
def user(db):
    return User.objects.create_user(
        username='status_user', password='x', email='u@example.com',
    )


@pytest.fixture
def client(user):
    c = APIClient()
    c.force_authenticate(user=user)
    return c


def test_status_lists_pre_umbral_feature(client):
    resp = client.get('/api/fhe-sharing/status/')
    assert resp.status_code == 200
    features = resp.data.get('features') or resp.data
    # The feature name is `pre_umbral_v1` per the SPEC.
    assert 'pre_umbral_v1' in _flatten_keys(resp.data), (
        "Status response must advertise pre_umbral_v1 feature, got: %r" % resp.data
    )


def test_status_lists_both_cipher_suites(client):
    resp = client.get('/api/fhe-sharing/status/')
    assert resp.status_code == 200
    suites = _find_value(resp.data, 'supported_cipher_suites') or _find_value(
        resp.data, 'cipher_suites'
    )
    assert suites is not None, (
        'Status response must list supported_cipher_suites, got: %r' % resp.data
    )
    assert 'simulated-v1' in suites
    assert 'umbral-v1' in suites


# ---------------------------------------------------------------------------
# Kill-switch contract — see fhe_sharing/README.md §2.1.
#
# When ops flips `FHE_SHARING_SETTINGS.PRE_ENABLED` to False:
#   - /status/ must advertise `features.pre_umbral_v1 == False`.
#   - /status/ must drop `umbral-v1` from supported_cipher_suites so
#     that clients hide the toggle and stop minting new umbral shares.
# ---------------------------------------------------------------------------

@override_settings(FHE_SHARING_SETTINGS={
    'PRE_ENABLED': False,
    'ROLLOUT_STAGE': 'off',
})
def test_status_respects_pre_kill_switch(client):
    resp = client.get('/api/fhe-sharing/status/')
    assert resp.status_code == 200
    feature_val = _find_value(resp.data, 'pre_umbral_v1')
    assert feature_val is False, (
        "When PRE_ENABLED=False, features.pre_umbral_v1 must be False. Got: %r"
        % resp.data
    )
    suites = _find_value(resp.data, 'supported_cipher_suites')
    assert suites is not None
    assert 'simulated-v1' in suites, (
        'simulated-v1 must remain advertised even with PRE disabled'
    )
    assert 'umbral-v1' not in suites, (
        "When PRE_ENABLED=False, umbral-v1 must drop out of supported_cipher_suites. Got: %r"
        % suites
    )


def _flatten_keys(obj):
    """Return all keys reachable in a nested dict/list structure."""
    if isinstance(obj, dict):
        keys = set(obj.keys())
        for v in obj.values():
            keys |= _flatten_keys(v)
        return keys
    if isinstance(obj, list):
        out = set()
        for item in obj:
            out |= _flatten_keys(item)
        return out
    return set()


def _find_value(obj, key):
    if isinstance(obj, dict):
        if key in obj:
            return obj[key]
        for v in obj.values():
            r = _find_value(v, key)
            if r is not None:
                return r
    if isinstance(obj, list):
        for v in obj:
            r = _find_value(v, key)
            if r is not None:
                return r
    return None

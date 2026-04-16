"""
End-to-end lifecycle tests for `cipher_suite='umbral-v1'` shares.

These tests exercise:
- `POST /api/fhe-sharing/shares/` with umbral-v1 payload
- `POST /api/fhe-sharing/shares/<id>/use/` returns capsule+cfrag+ciphertext
  (no plaintext in response)
- `/keys/register/` and `/keys/<username>/`
- Revocation blocks further `/use/`
- Domain mismatch rejected
- Backcompat: legacy simulated-v1 path unchanged

The tests monkeypatch `PreService.reencrypt` when pyUmbral is not
installed so the lifecycle can be exercised deterministically.
"""

import base64
import uuid

import pytest
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient


pytestmark = pytest.mark.django_db


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode('ascii').rstrip('=')


@pytest.fixture
def owner(db):
    return User.objects.create_user(
        username='share_owner', password='x', email='o@example.com',
    )


@pytest.fixture
def recipient(db):
    return User.objects.create_user(
        username='share_recipient', password='x', email='r@example.com',
    )


@pytest.fixture
def vault_item(owner):
    from vault.models import EncryptedVaultItem
    return EncryptedVaultItem.objects.create(
        user=owner,
        item_type='password',
        encrypted_data='ciphertext',
        name_hash='namehash',
        name_search='s',
    )


@pytest.fixture
def stub_pre(monkeypatch):
    """Force PreService.reencrypt to return a deterministic cfrag so the
    lifecycle tests run without pyUmbral installed."""
    from fhe_sharing.services import pre_service

    def _fake(self, capsule_bytes, kfrag_bytes):
        return b'CFRAG::' + bytes(capsule_bytes)[:8]

    monkeypatch.setattr(
        pre_service.PreService, 'reencrypt', _fake, raising=True,
    )
    monkeypatch.setattr(pre_service, '_UMBRAL_AVAILABLE', True)
    yield


@pytest.fixture
def client(recipient):
    c = APIClient()
    c.force_authenticate(user=recipient)
    return c


@pytest.fixture
def owner_client(owner):
    c = APIClient()
    c.force_authenticate(user=owner)
    return c


def _make_umbral_payload():
    """Fabricate payload bytes for tests that don't need real crypto."""
    return {
        'capsule': b'capsule-bytes-1234',
        'ciphertext': b'ciphertext-bytes-1234',
        'kfrag': b'kfrag-bytes-1234',
        'delegating_pk': b'delegating-pk-1234',
        'verifying_pk': b'verifying-pk-1234',
        'receiving_pk': b'receiving-pk-1234',
    }


def test_register_umbral_key(client, recipient):
    resp = client.post(
        '/api/fhe-sharing/keys/register/',
        data={
            'umbral_public_key': _b64(b'pk-public'),
            'umbral_verifying_key': _b64(b'pk-verify'),
        },
        format='json',
    )
    assert resp.status_code == 200, resp.data
    assert resp.data['success'] is True

    # Now another user can fetch it
    resp2 = client.get(f'/api/fhe-sharing/keys/{recipient.username}/')
    assert resp2.status_code == 200
    assert resp2.data['umbral_public_key'] == _b64(b'pk-public')


def test_get_umbral_key_404_when_not_registered(owner_client):
    resp = owner_client.get('/api/fhe-sharing/keys/ghost-user/')
    assert resp.status_code == 404


def test_create_umbral_share_requires_all_fields(owner_client, recipient, vault_item):
    resp = owner_client.post(
        '/api/fhe-sharing/shares/',
        data={
            'vault_item_id': str(vault_item.id),
            'recipient_username': recipient.username,
            'domain_constraints': ['example.com'],
            'cipher_suite': 'umbral-v1',
            # missing ciphertext/kfrag/etc.
            'capsule': _b64(b'capsule'),
        },
        format='json',
    )
    assert resp.status_code == 400
    assert 'ciphertext' in resp.data.get('details', {})


def test_create_umbral_share_succeeds(owner_client, recipient, vault_item):
    payload = _make_umbral_payload()
    resp = owner_client.post(
        '/api/fhe-sharing/shares/',
        data={
            'vault_item_id': str(vault_item.id),
            'recipient_username': recipient.username,
            'domain_constraints': ['example.com'],
            'cipher_suite': 'umbral-v1',
            **{k: _b64(v) for k, v in payload.items()},
        },
        format='json',
    )
    assert resp.status_code == 201, resp.data
    assert resp.data['cipher_suite'] == 'umbral-v1'
    from fhe_sharing.models import HomomorphicShare
    share = HomomorphicShare.objects.get(id=resp.data['share']['id'])
    assert share.cipher_suite == 'umbral-v1'
    assert bytes(share.capsule) == payload['capsule']
    assert bytes(share.kfrag) == payload['kfrag']
    assert share.encrypted_autofill_token in (None, b'', bytes())


def test_use_umbral_share_returns_capsule_cfrag_no_plaintext(
    owner_client, client, recipient, vault_item, stub_pre,
):
    payload = _make_umbral_payload()
    resp = owner_client.post(
        '/api/fhe-sharing/shares/',
        data={
            'vault_item_id': str(vault_item.id),
            'recipient_username': recipient.username,
            'domain_constraints': ['example.com'],
            'cipher_suite': 'umbral-v1',
            **{k: _b64(v) for k, v in payload.items()},
        },
        format='json',
    )
    assert resp.status_code == 201
    share_id = resp.data['share']['id']

    use_resp = client.post(
        f'/api/fhe-sharing/shares/{share_id}/use/',
        data={'domain': 'example.com'},
        format='json',
    )
    assert use_resp.status_code == 200, use_resp.data
    body = use_resp.data
    assert body['schema_version'] == 2
    assert body['cipher_suite'] == 'umbral-v1'
    assert body['capsule'] == _b64(payload['capsule'])
    assert body['ciphertext'] == _b64(payload['ciphertext'])
    assert body['cfrag']  # present and non-empty

    # CRITICAL: no plaintext password anywhere in the response body
    raw = repr(body).lower()
    assert 'password' not in raw  # no "password": "xxxx" keyed fields
    assert 'plaintext' not in raw


def test_use_umbral_share_domain_mismatch(
    owner_client, client, recipient, vault_item, stub_pre,
):
    payload = _make_umbral_payload()
    resp = owner_client.post(
        '/api/fhe-sharing/shares/',
        data={
            'vault_item_id': str(vault_item.id),
            'recipient_username': recipient.username,
            'domain_constraints': ['example.com'],
            'cipher_suite': 'umbral-v1',
            **{k: _b64(v) for k, v in payload.items()},
        },
        format='json',
    )
    share_id = resp.data['share']['id']

    use_resp = client.post(
        f'/api/fhe-sharing/shares/{share_id}/use/',
        data={'domain': 'evil.com'},
        format='json',
    )
    assert use_resp.status_code == 400
    assert 'not allowed' in str(use_resp.data).lower()


def test_revoked_umbral_share_blocks_use(
    owner_client, client, recipient, vault_item, stub_pre,
):
    payload = _make_umbral_payload()
    resp = owner_client.post(
        '/api/fhe-sharing/shares/',
        data={
            'vault_item_id': str(vault_item.id),
            'recipient_username': recipient.username,
            'domain_constraints': ['example.com'],
            'cipher_suite': 'umbral-v1',
            **{k: _b64(v) for k, v in payload.items()},
        },
        format='json',
    )
    share_id = resp.data['share']['id']

    rev = owner_client.delete(
        f'/api/fhe-sharing/shares/{share_id}/revoke/',
        data={'reason': 'test'},
        format='json',
    )
    assert rev.status_code == 200

    use_resp = client.post(
        f'/api/fhe-sharing/shares/{share_id}/use/',
        data={'domain': 'example.com'},
        format='json',
    )
    assert use_resp.status_code == 400
    assert 'revoked' in str(use_resp.data).lower()


def test_backcompat_simulated_share_still_works(
    owner_client, client, recipient, vault_item,
):
    # No cipher_suite → defaults to simulated-v1
    resp = owner_client.post(
        '/api/fhe-sharing/shares/',
        data={
            'vault_item_id': str(vault_item.id),
            'recipient_username': recipient.username,
            'domain_constraints': ['example.com'],
        },
        format='json',
    )
    assert resp.status_code == 201
    assert resp.data['cipher_suite'] == 'simulated-v1'
    share_id = resp.data['share']['id']

    use_resp = client.post(
        f'/api/fhe-sharing/shares/{share_id}/use/',
        data={'domain': 'example.com'},
        format='json',
    )
    assert use_resp.status_code == 200
    assert use_resp.data['cipher_suite'] == 'simulated-v1'
    assert use_resp.data['schema_version'] == 1

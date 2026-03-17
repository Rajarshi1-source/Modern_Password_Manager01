"""
Tests for FHE Sharing API Views

Tests cover:
- Share CRUD endpoints (create, list, detail, revoke)
- Autofill usage endpoint
- Received shares endpoint
- Access logs endpoint
- Share groups endpoints
- Permission checks (owner vs recipient vs unauthorized)
- Input validation
"""

import pytest
import json
import uuid
import os
import sys
from datetime import timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'password_manager'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'password_manager.settings')

import django
django.setup()

from django.utils import timezone
from django.contrib.auth.models import User
from rest_framework.test import APIClient, APITestCase

from fhe_sharing.models import HomomorphicShare, ShareAccessLog, ShareGroup


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def owner(db):
    return User.objects.create_user(username='api_owner', password='testpass123', email='owner@test.com')


@pytest.fixture
def recipient(db):
    return User.objects.create_user(username='api_recipient', password='testpass123', email='recipient@test.com')


@pytest.fixture
def other_user(db):
    return User.objects.create_user(username='api_other', password='testpass123', email='other@test.com')


@pytest.fixture
def vault_item(db, owner):
    from vault.models import EncryptedVaultItem
    return EncryptedVaultItem.objects.create(
        user=owner,
        item_id='api-test-item-001',
        item_type='password',
        encrypted_data='encrypted-data',
    )


@pytest.fixture
def share(db, owner, recipient, vault_item):
    """Create a share directly in DB for testing."""
    return HomomorphicShare.objects.create(
        owner=owner,
        recipient=recipient,
        vault_item=vault_item,
        encrypted_autofill_token=b'test-token',
        encrypted_domain_binding='github.com',
        token_metadata={'version': 1},
        permission_level='autofill_only',
        can_autofill=True,
        can_view_password=False,
        can_copy_password=False,
        max_uses=100,
        expires_at=timezone.now() + timedelta(hours=72),
    )


class TestCreateShareView:
    """Tests for POST /api/fhe-sharing/shares/"""

    def test_create_share_success(self, api_client, owner, recipient, vault_item):
        api_client.force_authenticate(user=owner)
        response = api_client.post('/api/fhe-sharing/shares/', {
            'vault_item_id': str(vault_item.id),
            'recipient_username': recipient.username,
            'domain_constraints': ['github.com'],
            'max_uses': 50,
        }, format='json')
        assert response.status_code == 201
        assert response.data['success'] is True
        assert 'share' in response.data

    def test_create_share_unauthenticated(self, api_client, vault_item, recipient):
        response = api_client.post('/api/fhe-sharing/shares/', {
            'vault_item_id': str(vault_item.id),
            'recipient_username': recipient.username,
            'domain_constraints': ['github.com'],
        }, format='json')
        assert response.status_code == 401

    def test_create_share_invalid_vault_item(self, api_client, owner, recipient):
        api_client.force_authenticate(user=owner)
        response = api_client.post('/api/fhe-sharing/shares/', {
            'vault_item_id': str(uuid.uuid4()),
            'recipient_username': recipient.username,
            'domain_constraints': ['github.com'],
        }, format='json')
        assert response.status_code == 404

    def test_create_share_invalid_recipient(self, api_client, owner, vault_item):
        api_client.force_authenticate(user=owner)
        response = api_client.post('/api/fhe-sharing/shares/', {
            'vault_item_id': str(vault_item.id),
            'recipient_username': 'nonexistent_user',
            'domain_constraints': ['github.com'],
        }, format='json')
        assert response.status_code in (400, 404)

    def test_create_share_missing_fields(self, api_client, owner):
        api_client.force_authenticate(user=owner)
        response = api_client.post('/api/fhe-sharing/shares/', {}, format='json')
        assert response.status_code == 400


class TestListSharesView:
    """Tests for GET /api/fhe-sharing/shares/list/"""

    def test_list_shares_owner(self, api_client, owner, share):
        api_client.force_authenticate(user=owner)
        response = api_client.get('/api/fhe-sharing/shares/list/')
        assert response.status_code == 200
        assert response.data['success'] is True
        assert response.data['count'] >= 1

    def test_list_shares_empty(self, api_client, other_user):
        api_client.force_authenticate(user=other_user)
        response = api_client.get('/api/fhe-sharing/shares/list/')
        assert response.status_code == 200
        assert response.data['count'] == 0

    def test_list_shares_unauthenticated(self, api_client):
        response = api_client.get('/api/fhe-sharing/shares/list/')
        assert response.status_code == 401


class TestShareDetailView:
    """Tests for GET /api/fhe-sharing/shares/<uuid>/"""

    def test_owner_sees_full_details(self, api_client, owner, share):
        api_client.force_authenticate(user=owner)
        response = api_client.get(f'/api/fhe-sharing/shares/{share.id}/')
        assert response.status_code == 200
        assert 'owner_username' in response.data['share']
        assert 'recipient_username' in response.data['share']

    def test_recipient_sees_limited_details(self, api_client, recipient, share):
        api_client.force_authenticate(user=recipient)
        response = api_client.get(f'/api/fhe-sharing/shares/{share.id}/')
        assert response.status_code == 200
        # Recipient should not see vault_item
        assert 'vault_item' not in response.data['share']

    def test_other_user_denied(self, api_client, other_user, share):
        api_client.force_authenticate(user=other_user)
        response = api_client.get(f'/api/fhe-sharing/shares/{share.id}/')
        assert response.status_code == 403

    def test_nonexistent_share(self, api_client, owner):
        api_client.force_authenticate(user=owner)
        response = api_client.get(f'/api/fhe-sharing/shares/{uuid.uuid4()}/')
        assert response.status_code == 404


class TestRevokeShareView:
    """Tests for DELETE /api/fhe-sharing/shares/<uuid>/revoke/"""

    def test_revoke_by_owner(self, api_client, owner, share):
        api_client.force_authenticate(user=owner)
        response = api_client.delete(
            f'/api/fhe-sharing/shares/{share.id}/revoke/',
            {'reason': 'Test revocation'},
            format='json',
        )
        assert response.status_code == 200
        assert response.data['success'] is True
        share.refresh_from_db()
        assert share.is_active is False

    def test_revoke_by_non_owner(self, api_client, other_user, share):
        api_client.force_authenticate(user=other_user)
        response = api_client.delete(
            f'/api/fhe-sharing/shares/{share.id}/revoke/',
            format='json',
        )
        assert response.status_code == 403


class TestUseAutofillView:
    """Tests for POST /api/fhe-sharing/shares/<uuid>/use/"""

    def test_use_autofill_success(self, api_client, recipient, share):
        api_client.force_authenticate(user=recipient)
        response = api_client.post(
            f'/api/fhe-sharing/shares/{share.id}/use/',
            {'domain': 'github.com'},
            format='json',
        )
        assert response.status_code == 200
        assert response.data['success'] is True

    def test_use_autofill_wrong_user(self, api_client, other_user, share):
        api_client.force_authenticate(user=other_user)
        response = api_client.post(
            f'/api/fhe-sharing/shares/{share.id}/use/',
            {'domain': 'github.com'},
            format='json',
        )
        assert response.status_code == 403

    def test_use_autofill_missing_domain(self, api_client, recipient, share):
        api_client.force_authenticate(user=recipient)
        response = api_client.post(
            f'/api/fhe-sharing/shares/{share.id}/use/',
            {},
            format='json',
        )
        assert response.status_code == 400


class TestReceivedSharesView:
    """Tests for GET /api/fhe-sharing/received/"""

    def test_received_shares(self, api_client, recipient, share):
        api_client.force_authenticate(user=recipient)
        response = api_client.get('/api/fhe-sharing/received/')
        assert response.status_code == 200
        assert response.data['count'] >= 1

    def test_received_shares_empty(self, api_client, other_user):
        api_client.force_authenticate(user=other_user)
        response = api_client.get('/api/fhe-sharing/received/')
        assert response.status_code == 200
        assert response.data['count'] == 0


class TestShareLogsView:
    """Tests for GET /api/fhe-sharing/shares/<uuid>/logs/"""

    def test_owner_can_view_logs(self, api_client, owner, share):
        # Create a log entry
        ShareAccessLog.objects.create(
            share=share, user=owner, action='share_created', success=True,
        )
        api_client.force_authenticate(user=owner)
        response = api_client.get(f'/api/fhe-sharing/shares/{share.id}/logs/')
        assert response.status_code == 200
        assert response.data['total'] >= 1

    def test_non_owner_cannot_view_logs(self, api_client, other_user, share):
        api_client.force_authenticate(user=other_user)
        response = api_client.get(f'/api/fhe-sharing/shares/{share.id}/logs/')
        assert response.status_code == 403


class TestShareGroupViews:
    """Tests for /api/fhe-sharing/groups/ endpoints."""

    def test_create_group(self, api_client, owner, vault_item):
        api_client.force_authenticate(user=owner)
        response = api_client.post('/api/fhe-sharing/groups/', {
            'name': 'Team GitHub',
            'vault_item_id': str(vault_item.id),
            'description': 'Team account access',
        }, format='json')
        assert response.status_code == 201
        assert response.data['success'] is True

    def test_list_groups(self, api_client, owner, vault_item):
        ShareGroup.objects.create(
            name='Group 1', owner=owner, vault_item=vault_item,
        )
        api_client.force_authenticate(user=owner)
        response = api_client.get('/api/fhe-sharing/groups/list/')
        assert response.status_code == 200
        assert response.data['count'] >= 1


class TestSharingStatusView:
    """Tests for GET /api/fhe-sharing/status/"""

    def test_status_endpoint(self, api_client):
        response = api_client.get('/api/fhe-sharing/status/')
        assert response.status_code == 200
        assert response.data['service'] == 'fhe_sharing'
        assert 'features' in response.data

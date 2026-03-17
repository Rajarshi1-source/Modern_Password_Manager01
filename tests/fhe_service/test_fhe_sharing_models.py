"""
Tests for FHE Sharing Models

Tests cover:
- HomomorphicShare creation, properties, constraints
- ShareAccessLog creation and querying
- ShareGroup creation
- Domain binding validation
- Expiration and usage limit logic
"""

import pytest
import uuid
import os
import sys
from datetime import timedelta
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'password_manager'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'password_manager.settings')

import django
django.setup()

from django.utils import timezone
from django.contrib.auth.models import User

from fhe_sharing.models import HomomorphicShare, ShareAccessLog, ShareGroup


@pytest.fixture
def owner(db):
    return User.objects.create_user(username='owner', password='testpass123')


@pytest.fixture
def recipient(db):
    return User.objects.create_user(username='recipient', password='testpass123')


@pytest.fixture
def mock_vault_item(db, owner):
    """Create a mock vault item using the real model."""
    from vault.models import EncryptedVaultItem
    return EncryptedVaultItem.objects.create(
        user=owner,
        item_id='test-vault-item-001',
        item_type='password',
        encrypted_data='encrypted-password-data',
    )


@pytest.fixture
def share(db, owner, recipient, mock_vault_item):
    """Create a basic HomomorphicShare for testing."""
    return HomomorphicShare.objects.create(
        owner=owner,
        recipient=recipient,
        vault_item=mock_vault_item,
        encrypted_autofill_token=b'test-token-data',
        encrypted_domain_binding='encrypted-domain-data',
        token_metadata={'version': 1, 'circuit_type': 'autofill'},
        permission_level='autofill_only',
        can_autofill=True,
        can_view_password=False,
        can_copy_password=False,
        max_uses=100,
        expires_at=timezone.now() + timedelta(hours=72),
    )


class TestHomomorphicShareCreation:
    """Tests for creating HomomorphicShare instances."""

    def test_create_basic_share(self, share):
        assert share.id is not None
        assert share.is_active is True
        assert share.use_count == 0
        assert share.can_autofill is True
        assert share.can_view_password is False
        assert share.can_copy_password is False

    def test_uuid_primary_key(self, share):
        assert isinstance(share.id, uuid.UUID)

    def test_default_values(self, db, owner, recipient, mock_vault_item):
        share = HomomorphicShare.objects.create(
            owner=owner,
            recipient=recipient,
            vault_item=mock_vault_item,
            encrypted_autofill_token=b'data',
        )
        assert share.permission_level == 'autofill_only'
        assert share.can_autofill is True
        assert share.can_view_password is False
        assert share.can_copy_password is False
        assert share.is_active is True
        assert share.max_uses is None
        assert share.expires_at is None

    def test_owner_is_set(self, share, owner):
        assert share.owner == owner
        assert share.owner.username == 'owner'

    def test_recipient_is_set(self, share, recipient):
        assert share.recipient == recipient
        assert share.recipient.username == 'recipient'


class TestHomomorphicShareProperties:
    """Tests for HomomorphicShare model properties."""

    def test_is_expired_false(self, share):
        assert share.is_expired is False

    def test_is_expired_true(self, db, owner, recipient, mock_vault_item):
        share = HomomorphicShare.objects.create(
            owner=owner,
            recipient=recipient,
            vault_item=mock_vault_item,
            encrypted_autofill_token=b'data',
            expires_at=timezone.now() - timedelta(hours=1),
        )
        assert share.is_expired is True

    def test_is_expired_none_expiry(self, db, owner, recipient, mock_vault_item):
        share = HomomorphicShare.objects.create(
            owner=owner,
            recipient=recipient,
            vault_item=mock_vault_item,
            encrypted_autofill_token=b'data',
            expires_at=None,
        )
        assert share.is_expired is False

    def test_is_usage_limit_reached(self, share):
        assert share.is_usage_limit_reached is False
        share.use_count = 100
        assert share.is_usage_limit_reached is True

    def test_is_usage_limit_unlimited(self, db, owner, recipient, mock_vault_item):
        share = HomomorphicShare.objects.create(
            owner=owner,
            recipient=recipient,
            vault_item=mock_vault_item,
            encrypted_autofill_token=b'data',
            max_uses=None,
        )
        share.use_count = 999999
        assert share.is_usage_limit_reached is False

    def test_is_usable_active_share(self, share):
        assert share.is_usable is True

    def test_is_usable_inactive(self, share):
        share.is_active = False
        assert share.is_usable is False

    def test_is_usable_expired(self, share):
        share.expires_at = timezone.now() - timedelta(hours=1)
        assert share.is_usable is False

    def test_is_usable_limit_reached(self, share):
        share.use_count = 100
        assert share.is_usable is False

    def test_remaining_uses(self, share):
        assert share.remaining_uses == 100
        share.use_count = 50
        assert share.remaining_uses == 50

    def test_remaining_uses_unlimited(self, db, owner, recipient, mock_vault_item):
        share = HomomorphicShare.objects.create(
            owner=owner,
            recipient=recipient,
            vault_item=mock_vault_item,
            encrypted_autofill_token=b'data',
            max_uses=None,
        )
        assert share.remaining_uses is None

    def test_string_representation(self, share):
        s = str(share)
        assert 'owner' in s
        assert 'recipient' in s


class TestHomomorphicShareDomainBinding:
    """Tests for domain binding functionality."""

    def test_get_bound_domains_empty(self, share):
        share.encrypted_domain_binding = ''
        assert share.get_bound_domains() == []

    def test_get_bound_domains_with_data(self, share):
        share.encrypted_domain_binding = 'github.com,gitlab.com'
        domains = share.get_bound_domains()
        # Note: domains are encrypted in practice, this tests the accessor exists
        assert isinstance(domains, list)


class TestShareAccessLog:
    """Tests for ShareAccessLog model."""

    def test_create_log_entry(self, db, share, recipient):
        log = ShareAccessLog.objects.create(
            share=share,
            user=recipient,
            action='autofill_used',
            domain='github.com',
            ip_address='192.168.1.1',
            success=True,
        )
        assert log.id is not None
        assert log.action == 'autofill_used'
        assert log.success is True

    def test_log_with_failure(self, db, share, recipient):
        log = ShareAccessLog.objects.create(
            share=share,
            user=recipient,
            action='autofill_denied',
            domain='evil.com',
            success=False,
            failure_reason='Domain mismatch',
        )
        assert log.success is False
        assert log.failure_reason == 'Domain mismatch'

    def test_log_action_choices(self, db, share, recipient):
        for action in ['share_created', 'autofill_used', 'share_revoked',
                       'share_expired', 'autofill_denied', 'domain_mismatch',
                       'usage_limit_reached', 'share_viewed']:
            log = ShareAccessLog.objects.create(
                share=share, user=recipient,
                action=action, success=True,
            )
            assert log.action == action

    def test_log_ordering(self, db, share, recipient):
        log1 = ShareAccessLog.objects.create(
            share=share, user=recipient, action='share_created', success=True,
        )
        log2 = ShareAccessLog.objects.create(
            share=share, user=recipient, action='autofill_used', success=True,
        )
        logs = list(ShareAccessLog.objects.filter(share=share))
        # Most recent first (default ordering is -timestamp)
        assert logs[0].id == log2.id


class TestShareGroup:
    """Tests for ShareGroup model."""

    def test_create_group(self, db, owner, mock_vault_item):
        group = ShareGroup.objects.create(
            name='Team GitHub',
            description='GitHub team account',
            owner=owner,
            vault_item=mock_vault_item,
        )
        assert group.id is not None
        assert group.name == 'Team GitHub'
        assert group.owner == owner

    def test_group_shares_count(self, db, owner, recipient, mock_vault_item):
        group = ShareGroup.objects.create(
            name='Team GitHub', owner=owner, vault_item=mock_vault_item,
        )
        # shares_count is annotated — test directly
        assert ShareGroup.objects.filter(id=group.id).count() == 1

    def test_group_string_representation(self, db, owner, mock_vault_item):
        group = ShareGroup.objects.create(
            name='Test Group', owner=owner, vault_item=mock_vault_item,
        )
        assert 'Test Group' in str(group)

"""
Tests for FHE Sharing Service

Tests cover:
- AutofillCircuitService: token creation, domain binding, validation
- HomomorphicSharingService: share lifecycle (create, use, revoke, list, cleanup)
"""

import pytest
import json
import base64
import os
import sys
from datetime import timedelta
from unittest.mock import Mock, patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'password_manager'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'password_manager.settings')

import django
django.setup()

from django.utils import timezone
from django.contrib.auth.models import User

from fhe_sharing.models import HomomorphicShare, ShareAccessLog, ShareGroup
from fhe_sharing.services.autofill_circuit_service import AutofillCircuitService
from fhe_sharing.services.fhe_sharing_service import HomomorphicSharingService


# ================================================================
# AutofillCircuitService Tests
# ================================================================

class TestAutofillCircuitService:
    """Tests for the AutofillCircuitService."""

    def setup_method(self):
        self.service = AutofillCircuitService()
        self.service.initialize()

    def test_initialization(self):
        assert self.service._initialized is True

    def test_create_autofill_circuit_basic(self):
        result = self.service.create_autofill_circuit(
            fhe_encrypted_password=b'test-encrypted-password',
            recipient_public_key=b'test-public-key',
            domain_constraints=['github.com'],
        )
        assert 'encrypted_token' in result
        assert 'domain_binding' in result
        assert 'metadata' in result
        assert result['metadata']['version'] == self.service.TOKEN_VERSION

    def test_create_autofill_circuit_multiple_domains(self):
        result = self.service.create_autofill_circuit(
            fhe_encrypted_password=b'test-encrypted-password',
            recipient_public_key=b'test-recipient-key',
            domain_constraints=['github.com', 'gitlab.com', 'bitbucket.org'],
        )
        assert result['metadata']['domain_count'] == 3

    def test_create_autofill_circuit_empty_password_raises(self):
        with pytest.raises(ValueError, match="password"):
            self.service.create_autofill_circuit(
                fhe_encrypted_password=b'',
                recipient_public_key=b'key',
                domain_constraints=['example.com'],
            )

    def test_validate_autofill_circuit_valid_domain(self):
        result = self.service.create_autofill_circuit(
            fhe_encrypted_password=b'test-password',
            recipient_public_key=b'test-key',
            domain_constraints=['github.com'],
        )
        is_valid = self.service.validate_autofill_circuit(
            token=result['encrypted_token'],
            domain='github.com',
            domain_binding=result['domain_binding'],
        )
        assert is_valid is True

    def test_validate_autofill_circuit_invalid_domain(self):
        result = self.service.create_autofill_circuit(
            fhe_encrypted_password=b'test-password',
            recipient_public_key=b'test-key',
            domain_constraints=['github.com'],
        )
        is_valid = self.service.validate_autofill_circuit(
            token=result['encrypted_token'],
            domain='evil.com',
            domain_binding=result['domain_binding'],
        )
        assert is_valid is False

    def test_generate_form_fill_payload(self):
        result = self.service.create_autofill_circuit(
            fhe_encrypted_password=b'test-password',
            recipient_public_key=b'test-key',
            domain_constraints=['github.com'],
        )
        payload = self.service.generate_form_fill_payload(
            token=result['encrypted_token'],
            form_field_selector='input[type="password"]',
        )
        assert 'payload' in payload
        assert 'selector' in payload
        assert payload['selector'] == 'input[type="password"]'

    def test_tokens_are_unique(self):
        """Two circuits for the same password should produce different tokens."""
        r1 = self.service.create_autofill_circuit(
            fhe_encrypted_password=b'password1',
            recipient_public_key=b'key1',
            domain_constraints=['a.com'],
        )
        r2 = self.service.create_autofill_circuit(
            fhe_encrypted_password=b'password1',
            recipient_public_key=b'key2',
            domain_constraints=['a.com'],
        )
        assert r1['encrypted_token'] != r2['encrypted_token']


# ================================================================
# HomomorphicSharingService Tests
# ================================================================

class TestHomomorphicSharingService:
    """Tests for the HomomorphicSharingService."""

    @pytest.fixture(autouse=True)
    def setup_service(self, db):
        self.service = HomomorphicSharingService()
        self.service.initialize()

    @pytest.fixture
    def owner(self, db):
        return User.objects.create_user(username='svc_owner', password='testpass')

    @pytest.fixture
    def recipient(self, db):
        return User.objects.create_user(username='svc_recipient', password='testpass')

    @pytest.fixture
    def vault_item(self, db, owner):
        from vault.models import EncryptedVaultItem
        return EncryptedVaultItem.objects.create(
            user=owner,
            item_id='svc-test-item-001',
            item_type='password',
            encrypted_data='encrypted-data',
        )

    @pytest.fixture
    def mock_request(self):
        req = Mock()
        req.META = {'REMOTE_ADDR': '127.0.0.1', 'HTTP_USER_AGENT': 'pytest'}
        return req

    def test_create_autofill_share(self, owner, recipient, vault_item, mock_request):
        share = self.service.create_autofill_share(
            owner=owner,
            vault_item=vault_item,
            recipient=recipient,
            domain_constraints=['github.com'],
            request=mock_request,
        )
        assert share is not None
        assert share.owner == owner
        assert share.recipient == recipient
        assert share.is_active is True
        assert share.can_view_password is False
        assert share.can_copy_password is False

    def test_create_share_self_sharing_raises(self, owner, vault_item, mock_request):
        with pytest.raises(ValueError, match="share.*yourself"):
            self.service.create_autofill_share(
                owner=owner,
                vault_item=vault_item,
                recipient=owner,
                domain_constraints=['github.com'],
                request=mock_request,
            )

    def test_create_share_logs_action(self, owner, recipient, vault_item, mock_request):
        share = self.service.create_autofill_share(
            owner=owner,
            vault_item=vault_item,
            recipient=recipient,
            domain_constraints=['github.com'],
            request=mock_request,
        )
        logs = ShareAccessLog.objects.filter(share=share, action='share_created')
        assert logs.count() >= 1

    def test_use_autofill_token_success(self, owner, recipient, vault_item, mock_request):
        share = self.service.create_autofill_share(
            owner=owner,
            vault_item=vault_item,
            recipient=recipient,
            domain_constraints=['github.com'],
            request=mock_request,
        )
        result = self.service.use_autofill_token(
            share_id=str(share.id),
            recipient=recipient,
            domain='github.com',
            request=mock_request,
        )
        assert 'autofill_payload' in result
        # Verify use_count incremented
        share.refresh_from_db()
        assert share.use_count == 1

    def test_use_autofill_wrong_recipient(self, owner, recipient, vault_item, mock_request):
        other_user = User.objects.create_user(username='intruder', password='testpass')
        share = self.service.create_autofill_share(
            owner=owner,
            vault_item=vault_item,
            recipient=recipient,
            domain_constraints=['github.com'],
            request=mock_request,
        )
        with pytest.raises(PermissionError):
            self.service.use_autofill_token(
                share_id=str(share.id),
                recipient=other_user,
                domain='github.com',
                request=mock_request,
            )

    def test_use_autofill_expired_share(self, owner, recipient, vault_item, mock_request):
        share = self.service.create_autofill_share(
            owner=owner,
            vault_item=vault_item,
            recipient=recipient,
            domain_constraints=['github.com'],
            expires_at=timezone.now() - timedelta(hours=1),
            request=mock_request,
        )
        with pytest.raises(ValueError, match="expired|usable"):
            self.service.use_autofill_token(
                share_id=str(share.id),
                recipient=recipient,
                domain='github.com',
                request=mock_request,
            )

    def test_use_autofill_revoked_share(self, owner, recipient, vault_item, mock_request):
        share = self.service.create_autofill_share(
            owner=owner,
            vault_item=vault_item,
            recipient=recipient,
            domain_constraints=['github.com'],
            request=mock_request,
        )
        self.service.revoke_share(
            share_id=str(share.id),
            revoking_user=owner,
            reason='test revocation',
            request=mock_request,
        )
        with pytest.raises(ValueError, match="usable|active"):
            self.service.use_autofill_token(
                share_id=str(share.id),
                recipient=recipient,
                domain='github.com',
                request=mock_request,
            )

    def test_revoke_share_by_owner(self, owner, recipient, vault_item, mock_request):
        share = self.service.create_autofill_share(
            owner=owner,
            vault_item=vault_item,
            recipient=recipient,
            domain_constraints=['github.com'],
            request=mock_request,
        )
        revoked = self.service.revoke_share(
            share_id=str(share.id),
            revoking_user=owner,
            reason='No longer needed',
            request=mock_request,
        )
        assert revoked.is_active is False
        assert revoked.revocation_reason == 'No longer needed'

    def test_revoke_share_non_owner_raises(self, owner, recipient, vault_item, mock_request):
        other_user = User.objects.create_user(username='random', password='testpass')
        share = self.service.create_autofill_share(
            owner=owner,
            vault_item=vault_item,
            recipient=recipient,
            domain_constraints=['github.com'],
            request=mock_request,
        )
        with pytest.raises(PermissionError):
            self.service.revoke_share(
                share_id=str(share.id),
                revoking_user=other_user,
                request=mock_request,
            )

    def test_list_shares_for_owner(self, owner, recipient, vault_item, mock_request):
        self.service.create_autofill_share(
            owner=owner, vault_item=vault_item, recipient=recipient,
            domain_constraints=['a.com'], request=mock_request,
        )
        self.service.create_autofill_share(
            owner=owner, vault_item=vault_item, recipient=recipient,
            domain_constraints=['b.com'], request=mock_request,
        )
        shares = self.service.list_shares_for_owner(owner)
        assert shares.count() == 2

    def test_list_shares_for_recipient(self, owner, recipient, vault_item, mock_request):
        self.service.create_autofill_share(
            owner=owner, vault_item=vault_item, recipient=recipient,
            domain_constraints=['a.com'], request=mock_request,
        )
        shares = self.service.list_shares_for_recipient(recipient)
        assert shares.count() == 1

    def test_create_share_group(self, owner, vault_item):
        group = self.service.create_share_group(
            owner=owner,
            vault_item=vault_item,
            name='Team GitHub',
            description='GitHub access',
        )
        assert group is not None
        assert group.name == 'Team GitHub'
        assert group.owner == owner

    def test_list_share_groups(self, owner, vault_item):
        self.service.create_share_group(
            owner=owner, vault_item=vault_item, name='Group 1',
        )
        self.service.create_share_group(
            owner=owner, vault_item=vault_item, name='Group 2',
        )
        groups = self.service.list_share_groups(owner)
        assert groups.count() == 2

    def test_get_share_logs(self, owner, recipient, vault_item, mock_request):
        share = self.service.create_autofill_share(
            owner=owner, vault_item=vault_item, recipient=recipient,
            domain_constraints=['github.com'], request=mock_request,
        )
        logs = self.service.get_share_logs(str(share.id), owner)
        assert logs.count() >= 1  # At least the creation log

    def test_get_share_logs_non_owner_raises(self, owner, recipient, vault_item, mock_request):
        share = self.service.create_autofill_share(
            owner=owner, vault_item=vault_item, recipient=recipient,
            domain_constraints=['github.com'], request=mock_request,
        )
        other_user = User.objects.create_user(username='spy', password='testpass')
        with pytest.raises(PermissionError):
            self.service.get_share_logs(str(share.id), other_user)

"""
Unit Tests for Vault Module
Tests vault models, encryption, and vault operations
"""

from django.test import TestCase, RequestFactory
from rest_framework.test import APIClient
from django.contrib.auth.models import User
from django.utils import timezone
from unittest.mock import patch, Mock
from datetime import timedelta
import json
import base64
import os

from .models import VaultItem, VaultBackup, UserSalt, AuditLog
from .crypto import encrypt_vault_item, decrypt_vault_item
from .views.crud_views import VaultItemViewSet


class VaultItemModelTests(TestCase):
    """Test VaultItem model"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
    
    def test_create_vault_item(self):
        """Test creating a vault item"""
        item = VaultItem.objects.create(
            user=self.user,
            item_id='test_item_123',
            item_type='password',
            encrypted_data='encrypted_test_data',
            favorite=False
        )
        
        self.assertEqual(item.user, self.user)
        self.assertEqual(item.item_type, 'password')
        self.assertFalse(item.favorite)
        self.assertIsNotNone(item.created_at)
        self.assertIsNotNone(item.updated_at)
    
    def test_vault_item_str_representation(self):
        """Test string representation of vault item"""
        item = VaultItem.objects.create(
            user=self.user,
            item_id='test_item_123',
            item_type='card',
            encrypted_data='encrypted_test_data'
        )
        
        str_repr = str(item)
        self.assertIn('testuser', str_repr)
        self.assertIn('card', str_repr)
    
    def test_favorite_toggle(self):
        """Test toggling favorite status"""
        item = VaultItem.objects.create(
            user=self.user,
            item_id='test_item_123',
            item_type='password',
            encrypted_data='data',
            favorite=False
        )
        
        # Toggle to true
        item.favorite = True
        item.save()
        item.refresh_from_db()
        self.assertTrue(item.favorite)
        
        # Toggle back to false
        item.favorite = False
        item.save()
        item.refresh_from_db()
        self.assertFalse(item.favorite)
    
    def test_vault_item_types(self):
        """Test different vault item types"""
        item_types = ['password', 'card', 'identity', 'note']
        
        for item_type in item_types:
            item = VaultItem.objects.create(
                user=self.user,
                item_id=f'test_{item_type}',
                item_type=item_type,
                encrypted_data='data'
            )
            self.assertEqual(item.item_type, item_type)
    
    def test_user_can_have_multiple_items(self):
        """Test user can have multiple vault items"""
        for i in range(5):
            VaultItem.objects.create(
                user=self.user,
                item_id=f'item_{i}',
                item_type='password',
                encrypted_data=f'data_{i}'
            )
        
        items = VaultItem.objects.filter(user=self.user)
        self.assertEqual(items.count(), 5)
    
    def test_vault_item_ordering(self):
        """Test vault items are ordered by creation date (newest first)."""
        item1 = VaultItem.objects.create(
            user=self.user,
            item_id='item_1',
            item_type='password',
            encrypted_data='data_1'
        )
        
        item2 = VaultItem.objects.create(
            user=self.user,
            item_id='item_2',
            item_type='password',
            encrypted_data='data_2'
        )
        
        items = VaultItem.objects.filter(user=self.user)
        # Test actual ordering field, not ID (IDs don't guarantee order)
        if items.count() >= 2:
            self.assertGreaterEqual(
                items.first().created_at,
                items.last().created_at
            )


class VaultBackupModelTests(TestCase):
    """Test VaultBackup model"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
    
    def test_create_backup(self):
        backup = VaultBackup.objects.create(
            user=self.user,
            name='Test Backup',
            encrypted_data='{"items": []}',
        )
        self.assertEqual(backup.user, self.user)
        self.assertIsNotNone(backup.created_at)

    def test_backup_with_items(self):
        backup = VaultBackup.objects.create(
            user=self.user,
            name='Test Backup',
            encrypted_data='{"items": [{}, {}, {}]}',
        )
        self.assertIsNotNone(backup.id)

    def test_multiple_backups_allowed(self):
        for i in range(3):
            VaultBackup.objects.create(
                user=self.user,
                name=f'Backup {i}',
                encrypted_data=f'{{"backup": {i}}}',
            )
        backups = VaultBackup.objects.filter(user=self.user)
        self.assertEqual(backups.count(), 3)


from django.test import override_settings


@override_settings(SECURE_SSL_REDIRECT=False, DEBUG=True)
class BackupZeroKnowledgeContractTests(TestCase):
    """Verify the backup API never accepts a plaintext KEK.

    Regression coverage for the zero-knowledge violation: previously,
    ``POST /backups/create_backup/`` would derive a wrapping key on the
    server from a client-supplied ``encryption_key``, defeating the rest
    of the codebase's zero-knowledge posture. The endpoint must now
    refuse any payload that includes such a field.

    ``SECURE_SSL_REDIRECT`` is forced off here because the default
    settings turn it on outside DEBUG, which 301-redirects DRF's
    ``APIClient`` (an HTTP client) before the view ever runs.
    """

    def setUp(self):
        from rest_framework.test import APIClient
        self.user = User.objects.create_user(
            username='zkuser',
            email='zk@example.com',
            password='zkpass123',
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def _envelope(self):
        """Build a structurally-valid v1 envelope (random bytes inside)."""
        import os
        return {
            'version': 'envelope-v1',
            'encrypted_data': base64.b64encode(os.urandom(64)).decode('ascii'),
            'data_nonce': base64.b64encode(os.urandom(12)).decode('ascii'),
            'wrapped_dek': base64.b64encode(os.urandom(48)).decode('ascii'),
            'kek_nonce': base64.b64encode(os.urandom(12)).decode('ascii'),
        }

    def test_create_backup_rejects_plaintext_encryption_key(self):
        """A payload with ``encryption_key`` is refused with 400."""
        url = '/api/vault/backups/create_backup/'
        with self.settings(BACKUP_REQUIRE_CLIENT_ENVELOPE=True):
            response = self.client.post(
                url,
                data={'name': 'attempt', 'encryption_key': 'hunter2'},
                format='json',
            )
        self.assertEqual(response.status_code, 400)
        body = response.json()
        self.assertEqual(body.get('code'), 'zero_knowledge_violation')
        # And no backup row was created as a side-effect of the rejection.
        self.assertFalse(
            VaultBackup.objects.filter(user=self.user).exists()
        )

    def test_create_backup_rejects_aliases(self):
        """Aliases for the KEK (``kek``/``wrapping_key``/``master_key``)
        are equally refused — an attacker cannot bypass the check by
        renaming the field."""
        url = '/api/vault/backups/create_backup/'
        for field in ('kek', 'wrapping_key', 'master_key'):
            with self.subTest(field=field):
                response = self.client.post(
                    url,
                    data={'name': 'attempt', field: 'hunter2'},
                    format='json',
                )
                self.assertEqual(response.status_code, 400)
                self.assertEqual(
                    response.json().get('code'),
                    'zero_knowledge_violation',
                )

    def test_create_backup_lenient_mode_returns_422(self):
        """In ``off`` mode the server still refuses the key but with a
        softer 422 + deprecation code (rollout safety net)."""
        url = '/api/vault/backups/create_backup/'
        with self.settings(BACKUP_ENVELOPE_ENFORCEMENT='off'):
            response = self.client.post(
                url,
                data={'name': 'attempt', 'encryption_key': 'hunter2'},
                format='json',
            )
        self.assertEqual(response.status_code, 422)
        body = response.json()
        self.assertEqual(
            body.get('code'),
            'zero_knowledge_violation_deprecated',
        )
        # Details surface the rollout state for the client to log/UX.
        self.assertEqual(body['details']['enforcement_mode'], 'off')
        self.assertTrue(body['details']['upgrade_required'])

    def test_canary_header_mode_v2_client_gets_400(self):
        """In ``header`` mode a client that announces v2 via
        ``X-Backup-Envelope-Client-Version`` AND regresses to sending
        ``encryption_key`` gets the strict 400 — it should know better."""
        url = '/api/vault/backups/create_backup/'
        with self.settings(BACKUP_ENVELOPE_ENFORCEMENT='header'):
            response = self.client.post(
                url,
                data={'name': 'regress', 'encryption_key': 'hunter2'},
                format='json',
                HTTP_X_BACKUP_ENVELOPE_CLIENT_VERSION='v2',
            )
        self.assertEqual(response.status_code, 400)
        body = response.json()
        self.assertEqual(body['code'], 'zero_knowledge_violation')
        self.assertTrue(body['details']['client_claims_v2'])

    def test_canary_header_mode_legacy_client_gets_422(self):
        """In ``header`` mode a pre-migration client (no header) sending
        ``encryption_key`` gets a soft 422 so its UI can surface a clear
        "update your client" message rather than an opaque 400."""
        url = '/api/vault/backups/create_backup/'
        with self.settings(BACKUP_ENVELOPE_ENFORCEMENT='header'):
            response = self.client.post(
                url,
                data={'name': 'legacy', 'encryption_key': 'hunter2'},
                format='json',
            )
        self.assertEqual(response.status_code, 422)
        body = response.json()
        self.assertEqual(body['code'], 'zero_knowledge_violation_deprecated')
        self.assertFalse(body['details']['client_claims_v2'])
        self.assertEqual(body['details']['enforcement_mode'], 'header')

    def test_canary_header_mode_v2_client_with_envelope_succeeds(self):
        """A v2 client that POSTs a real envelope still gets a 200 in
        ``header`` mode — the canary check only matters for KEK-bearing
        requests."""
        url = '/api/vault/backups/create_backup/'
        envelope = self._envelope()
        with self.settings(BACKUP_ENVELOPE_ENFORCEMENT='header'):
            response = self.client.post(
                url,
                data={'name': 'sealed-canary', 'envelope': envelope},
                format='json',
                HTTP_X_BACKUP_ENVELOPE_CLIENT_VERSION='v2',
            )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['envelope_encrypted'])

    def test_telemetry_counters_track_rollout(self):
        """The canary mitigation surfaces a per-mode counter so operators
        can watch the legacy-traffic curve approach zero before flipping
        to strict. This is the metric that gates the rollout decision."""
        from vault.views import backup_views
        # Reset to a known baseline (the global is process-scoped).
        for key in backup_views._kek_rejection_stats:
            backup_views._kek_rejection_stats[key] = 0
        url = '/api/vault/backups/create_backup/'
        with self.settings(BACKUP_ENVELOPE_ENFORCEMENT='header'):
            # A v2 client that regresses -> header_400.
            self.client.post(
                url,
                data={'encryption_key': 'x'},
                format='json',
                HTTP_X_BACKUP_ENVELOPE_CLIENT_VERSION='v2',
            )
            # Two legacy hits -> header_422 twice.
            for _ in range(2):
                self.client.post(
                    url, data={'encryption_key': 'x'}, format='json',
                )
        self.assertEqual(backup_views._kek_rejection_stats['header_400'], 1)
        self.assertEqual(backup_views._kek_rejection_stats['header_422'], 2)
        self.assertEqual(backup_views._kek_rejection_stats['strict_400'], 0)
        self.assertEqual(backup_views._kek_rejection_stats['off_422'], 0)

    def test_create_backup_accepts_client_envelope(self):
        """A correctly-shaped envelope is stored verbatim and reported
        back as ``envelope_encrypted=True``."""
        url = '/api/vault/backups/create_backup/'
        envelope = self._envelope()
        response = self.client.post(
            url,
            data={'name': 'sealed', 'envelope': envelope},
            format='json',
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body['envelope_encrypted'])
        backup = VaultBackup.objects.get(user=self.user, name='sealed')
        # Server stored the envelope JSON verbatim — no decryption happened.
        stored = json.loads(backup.encrypted_data)
        self.assertEqual(stored['version'], 'envelope-v1')
        self.assertEqual(stored['encrypted_data'], envelope['encrypted_data'])

    def test_create_backup_rejects_malformed_envelope(self):
        """A v1 envelope missing a required field or with the wrong nonce
        length is rejected with 400 invalid_envelope."""
        url = '/api/vault/backups/create_backup/'
        envelope = self._envelope()
        envelope.pop('wrapped_dek')
        response = self.client.post(
            url,
            data={'name': 'broken', 'envelope': envelope},
            format='json',
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json().get('code'), 'invalid_envelope')

    def test_create_backup_rejects_envelope_with_smuggled_kek(self):
        """A client cannot bypass the zero-knowledge contract by hiding
        a ``encryption_key`` field INSIDE the envelope dict. The
        validator's allow-list rejects any unexpected key, so the
        ``{envelope: {..., encryption_key: ...}}`` smuggling path
        returns 400 ``invalid_envelope`` and the row is never created."""
        url = '/api/vault/backups/create_backup/'
        envelope = self._envelope()
        envelope['encryption_key'] = 'should-never-be-stored'
        response = self.client.post(
            url,
            data={'name': 'sneaky', 'envelope': envelope},
            format='json',
        )
        self.assertEqual(response.status_code, 400)
        body = response.json()
        self.assertEqual(body['code'], 'invalid_envelope')
        self.assertIn('encryption_key', body['message'])
        # And no backup row was created.
        self.assertFalse(
            VaultBackup.objects.filter(user=self.user, name='sneaky').exists()
        )

    def test_create_backup_rejects_envelope_with_arbitrary_extra_field(self):
        """Same allow-list defence catches any other unknown key — not
        just ``encryption_key`` — so a future smuggling vector that
        invents a new field name is also closed off."""
        url = '/api/vault/backups/create_backup/'
        envelope = self._envelope()
        envelope['junk_field'] = 'noise'
        response = self.client.post(
            url,
            data={'name': 'junky', 'envelope': envelope},
            format='json',
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json().get('code'), 'invalid_envelope')

    def test_restore_allows_empty_plaintext_backup(self):
        """An empty vault legitimately backs up as ``{"items": []}``.
        ``restore`` must accept that (return 200, zero items written)
        rather than treating empty-list as malformed."""
        backup = VaultBackup.objects.create(
            user=self.user,
            name='empty',
            encrypted_data=json.dumps({
                'version': '1.0',
                'created_at': '2026-01-01T00:00:00+00:00',
                'item_count': 0,
                'items': [],
            }),
        )
        url = f'/api/vault/backups/{backup.id}/restore/'
        response = self.client.post(url, data={}, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['restored_items'], 0)

    def test_create_backup_without_envelope_falls_through_to_plain_json(self):
        """When the client supplies no envelope, the server stores the
        list of (already field-level encrypted) items as plain JSON. This
        path is for legacy clients that haven't migrated yet."""
        url = '/api/vault/backups/create_backup/'
        response = self.client.post(url, data={'name': 'plain'}, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()['envelope_encrypted'])

    def test_restore_rejects_plaintext_encryption_key(self):
        """``restore`` must also refuse a plaintext KEK — the original
        bug appeared on this endpoint too."""
        backup = VaultBackup.objects.create(
            user=self.user,
            name='stored',
            encrypted_data=json.dumps(self._envelope()),
        )
        url = f'/api/vault/backups/{backup.id}/restore/'
        response = self.client.post(
            url,
            data={'encryption_key': 'hunter2'},
            format='json',
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.json().get('code'), 'zero_knowledge_violation',
        )

    def test_restore_envelope_without_client_items_returns_422(self):
        """Asking the server to restore an envelope backup without
        supplying decrypted items is not 500 — it's a structured 422
        with the ciphertext attached so the client can decrypt and
        re-call."""
        envelope = self._envelope()
        backup = VaultBackup.objects.create(
            user=self.user,
            name='sealed',
            encrypted_data=json.dumps(envelope),
        )
        url = f'/api/vault/backups/{backup.id}/restore/'
        response = self.client.post(url, data={}, format='json')
        self.assertEqual(response.status_code, 422)
        body = response.json()
        self.assertEqual(
            body.get('code'), 'envelope_requires_client_decryption',
        )
        # And the envelope is returned to the client verbatim.
        self.assertEqual(
            body['details']['envelope']['encrypted_data'],
            envelope['encrypted_data'],
        )

    def test_restore_from_client_supplied_items(self):
        """Posting ``items=[...]`` to ``restore`` writes them to the
        vault without the server ever touching a KEK."""
        backup = VaultBackup.objects.create(
            user=self.user,
            name='sealed',
            encrypted_data=json.dumps(self._envelope()),
        )
        items = [
            {
                'item_id': 'restored-1',
                'item_type': 'password',
                'encrypted_data': 'ciphertext-1',
                'favorite': False,
                'tags': [],
            },
            {
                'item_id': 'restored-2',
                'item_type': 'note',
                'encrypted_data': 'ciphertext-2',
                'favorite': True,
                'tags': ['work'],
            },
        ]
        url = f'/api/vault/backups/{backup.id}/restore/'
        response = self.client.post(
            url, data={'items': items}, format='json',
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body['restored_items'], 2)
        self.assertTrue(
            VaultItem.objects.filter(
                user=self.user, item_id='restored-1',
            ).exists()
        )
        self.assertTrue(
            VaultItem.objects.filter(
                user=self.user, item_id='restored-2',
            ).exists()
        )

    def test_ciphertext_returns_stored_blob_unchanged(self):
        """The ``ciphertext`` action exists so the client can fetch the
        envelope for local decryption. The server attaches no KEK and
        does no decryption."""
        envelope = self._envelope()
        backup = VaultBackup.objects.create(
            user=self.user,
            name='sealed',
            encrypted_data=json.dumps(envelope),
        )
        url = f'/api/vault/backups/{backup.id}/ciphertext/'
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body['format'], 'envelope-v1')
        self.assertEqual(
            body['data']['encrypted_data'], envelope['encrypted_data'],
        )

    # ------------------------------------------------------------------
    # Cloud-upload validation (valet-key path)
    # ------------------------------------------------------------------
    def _cloud_backup_row(self):
        """Pre-stage a backup row in the same shape ``start_cloud_upload``
        would create, ready for ``complete_cloud_upload`` to validate."""
        from vault.views.backup_views import CLOUD_ONLY_PAYLOAD_META
        return VaultBackup.objects.create(
            user=self.user,
            name='cloud',
            encrypted_data=json.dumps(CLOUD_ONLY_PAYLOAD_META),
            size=0,
            cloud_sync_status='pending',
            cloud_storage_path=f'backups/{self.user.id}/test-blob',
        )

    def test_complete_cloud_upload_accepts_valid_envelope(self):
        """A v1 envelope already PUT to object storage validates and
        the row flips to ``synced``."""
        from unittest.mock import patch
        envelope = self._envelope()
        blob = json.dumps(envelope).encode('utf-8')
        backup = self._cloud_backup_row()
        url = f'/api/vault/backups/{backup.id}/complete-cloud-upload/'
        with patch(
            'vault.views.backup_views.CloudStorageService.download_backup',
            return_value=blob,
        ):
            response = self.client.post(
                url, data={'size': len(blob)}, format='json',
            )
        self.assertEqual(response.status_code, 200)
        backup.refresh_from_db()
        self.assertEqual(backup.cloud_sync_status, 'synced')

    def test_complete_cloud_upload_rejects_blob_with_kek_field(self):
        """An attacker who PUT a JSON blob carrying ``encryption_key``
        (anywhere in the structure) directly to object storage cannot
        get the server to mark it synced. The row goes to ``failed``
        and the endpoint returns 400 ``invalid_cloud_blob``."""
        from unittest.mock import patch
        blob = json.dumps({
            'version': '1.0',
            'items': [],
            'encryption_key': 'leaked',
        }).encode('utf-8')
        backup = self._cloud_backup_row()
        url = f'/api/vault/backups/{backup.id}/complete-cloud-upload/'
        with patch(
            'vault.views.backup_views.CloudStorageService.download_backup',
            return_value=blob,
        ):
            response = self.client.post(url, data={}, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['code'], 'invalid_cloud_blob')
        backup.refresh_from_db()
        self.assertEqual(backup.cloud_sync_status, 'failed')

    def test_complete_cloud_upload_rejects_kek_nested_inside_items(self):
        """The recursive KEK scanner catches a KEK alias even when it's
        buried inside a nested item record."""
        from unittest.mock import patch
        blob = json.dumps({
            'version': '1.0',
            'items': [
                {'item_id': 'x', 'kek': 'sneaky-deeply-nested'},
            ],
        }).encode('utf-8')
        backup = self._cloud_backup_row()
        url = f'/api/vault/backups/{backup.id}/complete-cloud-upload/'
        with patch(
            'vault.views.backup_views.CloudStorageService.download_backup',
            return_value=blob,
        ):
            response = self.client.post(url, data={}, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['code'], 'invalid_cloud_blob')

    def test_complete_cloud_upload_rejects_envelope_with_extra_fields(self):
        """An envelope-shaped blob with smuggled ``encryption_key`` is
        rejected by ``_validate_envelope``'s allow-list, same as in the
        synchronous create path."""
        from unittest.mock import patch
        envelope = self._envelope()
        envelope['encryption_key'] = 'smuggled-via-cloud-path'
        blob = json.dumps(envelope).encode('utf-8')
        backup = self._cloud_backup_row()
        url = f'/api/vault/backups/{backup.id}/complete-cloud-upload/'
        with patch(
            'vault.views.backup_views.CloudStorageService.download_backup',
            return_value=blob,
        ):
            response = self.client.post(url, data={}, format='json')
        self.assertEqual(response.status_code, 400)
        backup.refresh_from_db()
        self.assertEqual(backup.cloud_sync_status, 'failed')

    def test_complete_cloud_upload_rejects_non_json_blob(self):
        """An opaque/binary upload is refused — the cloud path is
        contracted to be a JSON-encoded v1 envelope."""
        from unittest.mock import patch
        backup = self._cloud_backup_row()
        url = f'/api/vault/backups/{backup.id}/complete-cloud-upload/'
        with patch(
            'vault.views.backup_views.CloudStorageService.download_backup',
            return_value=b'\x00\x01\x02 not json',
        ):
            response = self.client.post(url, data={}, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['code'], 'invalid_cloud_blob')


class UserSaltModelTests(TestCase):
    """Test UserSalt model"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
    
    def test_create_user_salt(self):
        """Test creating a user salt"""
        salt = b'test_salt_bytes'
        auth_hash = b'test_auth_hash'
        
        user_salt = UserSalt.objects.create(
            user=self.user,
            salt=salt,
            auth_hash=auth_hash
        )
        
        self.assertEqual(user_salt.user, self.user)
        self.assertEqual(user_salt.salt, salt)
        self.assertEqual(user_salt.auth_hash, auth_hash)
    
    def test_one_salt_per_user(self):
        """Test that each user should have one salt"""
        salt = b'test_salt'
        
        UserSalt.objects.create(
            user=self.user,
            salt=salt,
            auth_hash=b'hash'
        )
        
        # Getting the salt for user
        user_salt = UserSalt.objects.get(user=self.user)
        # PostgreSQL returns BinaryField as memoryview; convert to bytes
        self.assertEqual(bytes(user_salt.salt), salt)


class VaultCryptoTests(TestCase):
    """
    Test vault encryption/decryption functions.

    Audit-fix H7 regressions: these helpers are INTERNAL (production
    items are client-encrypted) but the function contract is now:
    requires 32 raw key bytes, returns an AES-256-GCM envelope,
    rejects legacy Fernet ciphertext explicitly.
    """

    def test_encrypt_roundtrip_with_dict(self):
        from .crypto import encrypt_vault_item, decrypt_vault_item
        data = {"username": "test", "password": "secret"}
        key = os.urandom(32)

        envelope = encrypt_vault_item(data, key)
        # Envelope shape: 0x01 version | 12-byte nonce | ct+tag.
        self.assertEqual(envelope[0], 0x01)
        self.assertGreater(len(envelope), 1 + 12 + 16)

        decoded = decrypt_vault_item(envelope, key)
        self.assertEqual(decoded, data)

    def test_encrypt_roundtrip_with_string(self):
        from .crypto import encrypt_vault_item, decrypt_vault_item
        key = os.urandom(32)
        envelope = encrypt_vault_item("hello world", key)
        self.assertEqual(decrypt_vault_item(envelope, key), "hello world")

    def test_encrypt_roundtrip_preserves_json_shaped_strings(self):
        """PR #272 review regression: strings that LOOK like JSON
        (e.g. '"hunter2"', '123', '{"a":1}') must come back as strings,
        not the JSON value they happen to encode. Previously the str
        path encoded raw UTF-8 and decrypt's `json.loads` silently
        converted '123' → 123 (int)."""
        from .crypto import encrypt_vault_item, decrypt_vault_item
        key = os.urandom(32)
        for tricky in ('"hunter2"', '123', 'null', '[1, 2, 3]', '{"a": 1}'):
            envelope = encrypt_vault_item(tricky, key)
            decoded = decrypt_vault_item(envelope, key)
            self.assertEqual(
                decoded, tricky,
                msg=f"round-trip failed for {tricky!r}: got {decoded!r}",
            )
            self.assertIsInstance(decoded, str)

    def test_encrypt_rejects_short_key(self):
        from .crypto import encrypt_vault_item
        with self.assertRaises(ValueError):
            encrypt_vault_item({"x": 1}, b'too_short')

    def test_encrypt_rejects_non_bytes_key(self):
        from .crypto import encrypt_vault_item
        with self.assertRaises(ValueError):
            encrypt_vault_item({"x": 1}, "string-key-32-chars-not-bytes-xx")

    def test_decrypt_rejects_legacy_fernet_string(self):
        # 'gAAAA' is the standard Fernet prefix; we refuse it loudly so
        # any caller still on the old SHA256(key) → Fernet path can be
        # found, instead of silently producing wrong plaintext.
        from .crypto import decrypt_vault_item
        with self.assertRaises(ValueError):
            decrypt_vault_item('gAAAAAB' + 'A' * 64, os.urandom(32))

    def test_decrypt_rejects_unknown_version(self):
        from .crypto import decrypt_vault_item
        bogus = bytes([0xFE]) + os.urandom(12) + os.urandom(32)
        with self.assertRaises(ValueError):
            decrypt_vault_item(bogus, os.urandom(32))

    def test_decrypt_rejects_tampered_ciphertext(self):
        from .crypto import encrypt_vault_item, decrypt_vault_item
        key = os.urandom(32)
        envelope = bytearray(encrypt_vault_item({"x": 1}, key))
        # Flip a byte inside the ciphertext.
        envelope[-3] ^= 0xFF
        with self.assertRaises(Exception):
            decrypt_vault_item(bytes(envelope), key)


class VaultItemViewSetTests(TestCase):
    """Test VaultItemViewSet API views"""
    
    def setUp(self):
        self.factory = RequestFactory()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        # Create test vault items
        for i in range(3):
            VaultItem.objects.create(
                user=self.user,
                item_id=f'item_{i}',
                item_type='password',
                encrypted_data=f'data_{i}'
            )
    
    def test_list_vault_items(self):
        """Test listing vault items"""
        items = VaultItem.objects.filter(user=self.user)
        self.assertEqual(items.count(), 3)
    
    def test_filter_by_favorite(self):
        """Test filtering items by favorite status"""
        # Mark one as favorite
        item = VaultItem.objects.filter(user=self.user).first()
        item.favorite = True
        item.save()
        
        favorites = VaultItem.objects.filter(user=self.user, favorite=True)
        self.assertEqual(favorites.count(), 1)
    
    def test_filter_by_item_type(self):
        """Test filtering items by type"""
        # Create a card item
        VaultItem.objects.create(
            user=self.user,
            item_id='card_1',
            item_type='card',
            encrypted_data='card_data'
        )
        
        cards = VaultItem.objects.filter(user=self.user, item_type='card')
        self.assertEqual(cards.count(), 1)

        passwords = VaultItem.objects.filter(user=self.user, item_type='password')
        self.assertEqual(passwords.count(), 3)


@override_settings(SECURE_SSL_REDIRECT=False, DEBUG=True)
class VaultFavoritePatchTests(TestCase):
    """PR A: the `favorite` flag is writable via a metadata-only PATCH on
    /api/vault/{id}/ (served by ApiVaultItemViewSet) without touching the
    encrypted payload."""

    def setUp(self):
        """Create an authenticated user with one un-favorited vault item."""
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='favuser',
            email='fav@example.com',
            password='testpass123',
        )
        self.client.force_authenticate(user=self.user)
        self.item = VaultItem.objects.create(
            user=self.user,
            item_id='fav_item_1',
            item_type='password',
            encrypted_data='cipher-blob',
            favorite=False,
        )

    def test_patch_sets_favorite_without_touching_ciphertext(self):
        """A PATCH with only {favorite} persists and leaves encrypted_data intact."""
        resp = self.client.patch(
            f'/api/vault/{self.item.id}/',
            {'favorite': True},
            format='json',
        )
        self.assertEqual(resp.status_code, 200)
        self.item.refresh_from_db()
        self.assertTrue(self.item.favorite)
        # The metadata-only PATCH must not require or alter the ciphertext.
        self.assertEqual(self.item.encrypted_data, 'cipher-blob')

    def test_patch_can_clear_favorite(self):
        """A PATCH with {favorite: False} clears a previously-set favorite."""
        self.item.favorite = True
        self.item.save(update_fields=['favorite'])
        resp = self.client.patch(
            f'/api/vault/{self.item.id}/',
            {'favorite': False},
            format='json',
        )
        self.assertEqual(resp.status_code, 200)
        self.item.refresh_from_db()
        self.assertFalse(self.item.favorite)

    def test_favorite_is_serialized_in_response(self):
        """`favorite` is now part of the serializer output."""
        resp = self.client.patch(
            f'/api/vault/{self.item.id}/',
            {'favorite': True},
            format='json',
        )
        self.assertEqual(resp.status_code, 200)
        self.assertIn('favorite', resp.data)
        self.assertTrue(resp.data['favorite'])

    def test_patch_rejects_other_users_item(self):
        """Scoped queryset: a user cannot favorite someone else's item."""
        other = User.objects.create_user(
            username='other', email='other@example.com', password='testpass123'
        )
        other_item = VaultItem.objects.create(
            user=other,
            item_id='other_item_1',
            item_type='password',
            encrypted_data='other-blob',
            favorite=False,
        )
        resp = self.client.patch(
            f'/api/vault/{other_item.id}/',
            {'favorite': True},
            format='json',
        )
        self.assertEqual(resp.status_code, 404)
        other_item.refresh_from_db()
        self.assertFalse(other_item.favorite)


class AuditLogTests(TestCase):
    """Test audit logging functionality"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
    
    def test_create_audit_log(self):
        log = AuditLog.objects.create(
            user=self.user,
            action='create_item',   # must be a valid ACTION_TYPES choice
            item_type='password',
            status='success',
            ip_address='192.168.1.1'
        )
        self.assertEqual(log.user, self.user)
        self.assertEqual(log.action, 'create_item')
        self.assertIsNotNone(log.timestamp)

    def test_audit_log_tracks_actions(self):
        actions = ['create_item', 'update_item', 'delete_item', 'access_item']
        for action in actions:
            AuditLog.objects.create(
                user=self.user,
                action=action,
                status='success',
                ip_address='192.168.1.1'
            )
        logs = AuditLog.objects.filter(user=self.user)
        self.assertEqual(logs.count(), 4)

    def test_audit_log_ordering(self):
        for i in range(3):
            AuditLog.objects.create(
                user=self.user,
                action='access_item',
                status='success',
                ip_address='192.168.1.1'
            )
        logs = AuditLog.objects.filter(user=self.user).order_by('-timestamp')
        self.assertTrue(logs.first().timestamp >= logs.last().timestamp)


class VaultItemLifecycleTests(TestCase):
    """Test complete lifecycle of a vault item"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
    
    def test_create_update_delete_cycle(self):
        """Test full CRUD cycle for vault item"""
        # Create
        item = VaultItem.objects.create(
            user=self.user,
            item_id='lifecycle_test',
            item_type='password',
            encrypted_data='original_data'
        )
        original_id = item.id
        self.assertTrue(VaultItem.objects.filter(id=original_id).exists())
        
        # Update
        item.encrypted_data = 'updated_data'
        item.save()
        item.refresh_from_db()
        self.assertEqual(item.encrypted_data, 'updated_data')
        
        # Delete
        item.delete()
        self.assertFalse(VaultItem.objects.filter(id=original_id).exists())
    
    def test_cascade_delete_on_user_deletion(self):
        """Test that vault items are deleted when user is deleted"""
        # Create items
        for i in range(3):
            VaultItem.objects.create(
                user=self.user,
                item_id=f'item_{i}',
                item_type='password',
                encrypted_data='data'
            )
        
        user_id = self.user.id
        item_count = VaultItem.objects.filter(user=self.user).count()
        self.assertEqual(item_count, 3)
        
        # Delete user
        self.user.delete()
        
        # Items should be deleted too
        remaining_items = VaultItem.objects.filter(user_id=user_id).count()
        self.assertEqual(remaining_items, 0)


class VaultSyncTests(TestCase):
    """Test vault synchronization functionality"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
    
    def test_sync_with_no_changes(self):
        """Test sync when there are no changes"""
        # Create items
        items = []
        for i in range(3):
            item = VaultItem.objects.create(
                user=self.user,
                item_id=f'item_{i}',
                item_type='password',
                encrypted_data='data'
            )
            items.append(item)
        
        # Sync should return same items
        current_items = VaultItem.objects.filter(user=self.user)
        self.assertEqual(current_items.count(), 3)
    
    def test_sync_with_new_items(self):
        """Test sync adds new items"""
        initial_count = VaultItem.objects.filter(user=self.user).count()
        self.assertEqual(initial_count, 0)
        
        # Add new items
        VaultItem.objects.create(
            user=self.user,
            item_id='new_item',
            item_type='password',
            encrypted_data='new_data'
        )
        
        new_count = VaultItem.objects.filter(user=self.user).count()
        self.assertEqual(new_count, 1)


# Test utilities and helpers
class VaultTestHelpers:
    """Helper methods for vault testing"""
    
    @staticmethod
    def create_test_vault_item(user, item_type='password', favorite=False):
        """Create a test vault item"""
        return VaultItem.objects.create(
            user=user,
            item_id=f'test_{item_type}_{user.id}',
            item_type=item_type,
            encrypted_data='test_encrypted_data',
            favorite=favorite
        )
    
    @staticmethod
    def create_test_backup(user):
        """Create a test backup"""
        return VaultBackup.objects.create(
            user=user,
            name='Test Backup',
            encrypted_data='{"items": []}',
        )


# ---------------------------------------------------------------------------
# Audit-fix regression: C10 (verify_auth privilege escalation)
# ---------------------------------------------------------------------------

from rest_framework.test import APIClient


class VerifyAuthC10Tests(TestCase):
    """
    The pre-fix `verify_auth` view would write whatever auth_hash a JWT-
    bearing caller posted into an empty `vault.UserSalt` row, letting an
    attacker who'd stolen a session token claim the victim's vault.
    The fix refuses that path: an empty `auth_hash` must error 400, never
    silently store the caller's hash.
    """

    def setUp(self):
        self.user = User.objects.create_user(
            username='c10user', email='c10@example.com', password='x'
        )
        # Empty `auth_hash` is the dangerous state we're guarding against.
        UserSalt.objects.create(user=self.user, salt=b'\x00' * 16, auth_hash=b'')
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_empty_auth_hash_is_rejected(self):
        """No silent first-time-setup: must NOT store the attacker's hash.

        Asserts the endpoint refuses with 400 + `vault_not_initialized` —
        not 404. A 404 here would mean the URL is unwired and the test
        is rubber-stamping the fix without exercising it.
        """
        resp = self.client.post(
            '/api/vault/items/verify_auth/',
            data={'auth_hash': 'attacker-supplied-hash'},
            format='json',
        )
        self.assertEqual(resp.status_code, 400, resp.content)
        body = resp.json()
        self.assertEqual(body.get('code'), 'vault_not_initialized')
        refreshed = UserSalt.objects.get(user=self.user)
        self.assertEqual(bytes(refreshed.auth_hash or b''), b'')


# ---------------------------------------------------------------------------
# PR D regression: vault URLconf shadowing
# ---------------------------------------------------------------------------

from django.urls import resolve as _resolve, reverse as _reverse
from vault.views.api_views import VaultItemViewSet as _ApiVaultItemViewSet
from vault.views.crud_views import VaultItemViewSet as _CrudVaultItemViewSet


@override_settings(SECURE_SSL_REDIRECT=False, DEBUG=True)
class VaultUrlconfRoutingTests(TestCase):
    """PR D: the empty-prefix ``r''`` ModelViewSet detail route
    ``^(?P<pk>[^/.]+)/$`` is a greedy single-segment catch-all. Registered
    before its siblings (and with ``vault_root`` parked at ``^$``) it used to
    shadow:

      * ``GET /api/vault/``     -> the ``vault_root`` info view (not the list)
      * ``/api/vault/folders/`` -> ``api-vault-detail`` (pk='folders')
      * ``/api/vault/backups/`` -> ``api-vault-detail`` (pk='backups')
      * ``/api/vault/items/``   -> ``api-vault-detail`` (pk='items')
      * ``/api/vault/sync/``    -> ``api-vault-detail`` (POST -> 405)

    These tests pin both the ``resolve()`` matrix and the end-to-end behavior
    so the shadowing cannot silently regress.
    """

    def setUp(self):
        """Two scoped users (one authenticated) each owning one vault item.

        Passwords are intentionally omitted: the suite authenticates via
        ``force_authenticate`` and never logs in, so a literal password would
        only add a Ruff S106 hardcoded-credential warning with no test value.
        """
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='urluser', email='url@example.com',
        )
        self.client.force_authenticate(user=self.user)
        self.item = VaultItem.objects.create(
            user=self.user, item_id='url_item_1', item_type='password',
            encrypted_data='cipher-blob', favorite=False,
        )
        # A second user's item — must never leak into self.user's list.
        self.other = User.objects.create_user(
            username='urlother', email='urlother@example.com',
        )
        self.other_item = VaultItem.objects.create(
            user=self.other, item_id='other_url_item', item_type='password',
            encrypted_data='other-blob', favorite=False,
        )

    # --- resolve() matrix -------------------------------------------------

    def test_root_resolves_to_list_not_info_view(self):
        """GET /api/vault/ reaches the list/create view, not vault_root."""
        match = _resolve('/api/vault/')
        self.assertIs(match.func.cls, _ApiVaultItemViewSet)
        self.assertEqual(match.func.actions.get('get'), 'list')
        self.assertEqual(match.func.actions.get('post'), 'create')

    def test_folders_resolves_to_folder_list(self):
        """/api/vault/folders/ reaches FolderViewSet.list, not the catch-all."""
        match = _resolve('/api/vault/folders/')
        self.assertEqual(match.func.cls.__name__, 'FolderViewSet')
        self.assertEqual(match.func.actions.get('get'), 'list')
        self.assertNotIn('pk', match.kwargs)  # not the detail catch-all

    def test_backups_resolves_to_backup_list(self):
        """/api/vault/backups/ reaches BackupViewSet.list, not the catch-all."""
        match = _resolve('/api/vault/backups/')
        self.assertEqual(match.func.cls.__name__, 'BackupViewSet')
        self.assertEqual(match.func.actions.get('get'), 'list')
        self.assertNotIn('pk', match.kwargs)

    def test_items_resolves_to_list(self):
        """/api/vault/items/ reaches the items list, not the detail catch-all."""
        match = _resolve('/api/vault/items/')
        self.assertIs(match.func.cls, _ApiVaultItemViewSet)
        self.assertEqual(match.func.actions.get('get'), 'list')
        self.assertNotIn('pk', match.kwargs)

    def test_sync_resolves_to_crud_sync_action(self):
        """/api/vault/sync/ POST reaches CrudVaultItemViewSet.sync."""
        match = _resolve('/api/vault/sync/')
        self.assertIs(match.func.cls, _CrudVaultItemViewSet)
        self.assertEqual(match.func.actions.get('post'), 'sync')
        self.assertNotIn('pk', match.kwargs)

    def test_detail_still_resolves_to_api_detail(self):
        """/api/vault/{id}/ still resolves to the item detail (favorite PATCH)."""
        match = _resolve(f'/api/vault/{self.item.id}/')
        self.assertIs(match.func.cls, _ApiVaultItemViewSet)
        self.assertEqual(match.func.actions.get('patch'), 'partial_update')
        self.assertEqual(str(match.kwargs.get('pk')), str(self.item.id))

    def test_list_level_actions_still_resolve(self):
        """The detail=False @actions resolve to their action, not detail(pk=...)."""
        for path_, expected_action in [
            ('/api/vault/get_salt/', 'get_salt'),
            ('/api/vault/verify_auth/', 'verify_auth'),
            ('/api/vault/statistics/', 'statistics'),
            ('/api/vault/check_initialization/', 'check_initialization'),
        ]:
            match = _resolve(path_)
            self.assertIs(match.func.cls, _ApiVaultItemViewSet, path_)
            self.assertIn(expected_action, match.func.actions.values(), path_)
            self.assertNotIn('pk', match.kwargs, path_)

    def test_reverse_names_point_at_canonical_urls(self):
        """Named routes reverse to their canonical post-fix URLs."""
        self.assertEqual(_reverse('vault-root'), '/api/vault/meta/')
        self.assertEqual(_reverse('vault-items-list'), '/api/vault/items/')
        self.assertEqual(_reverse('vault-sync'), '/api/vault/sync/')
        self.assertEqual(_reverse('vault-search'), '/api/vault/search/')

    # --- end-to-end behavior ---------------------------------------------

    def test_get_root_returns_user_items_as_list(self):
        """GET /api/vault/ returns the caller's items as a list, scoped per user."""
        resp = self.client.get('/api/vault/')
        self.assertEqual(resp.status_code, 200, resp.content)
        # Regression: before the fix this was the vault_root info view, whose
        # ``items`` was a URL *string*, not the item list.
        self.assertIsInstance(resp.data.get('items'), list)
        returned_ids = {i['item_id'] for i in resp.data['items'] if 'item_id' in i}
        self.assertIn('url_item_1', returned_ids)
        self.assertNotIn('other_url_item', returned_ids)  # scoped to the user

    def test_favorite_patch_on_detail_still_works(self):
        """The metadata-only favorite PATCH persists without touching ciphertext."""
        resp = self.client.patch(
            f'/api/vault/{self.item.id}/', {'favorite': True}, format='json',
        )
        self.assertEqual(resp.status_code, 200, resp.content)
        self.item.refresh_from_db()
        self.assertTrue(self.item.favorite)
        # Metadata-only PATCH must not disturb the ciphertext.
        self.assertEqual(self.item.encrypted_data, 'cipher-blob')

    def test_folders_list_is_reachable(self):
        """GET /api/vault/folders/ returns 200 (no longer shadowed -> 404)."""
        resp = self.client.get('/api/vault/folders/')
        self.assertEqual(resp.status_code, 200, resp.content)

    def test_backups_list_is_reachable(self):
        """GET /api/vault/backups/ returns 200 (no longer shadowed -> 404)."""
        resp = self.client.get('/api/vault/backups/')
        self.assertEqual(resp.status_code, 200, resp.content)

    def test_sync_post_reaches_sync_action_not_405(self):
        """POST /api/vault/sync/ reaches the sync action, not the 405 catch-all."""
        # Before the fix POST /api/vault/sync/ hit the detail catch-all (which
        # has no POST handler) -> 405. Now it reaches CrudVaultItemViewSet.sync,
        # which with no UserSalt row returns 400 vault_not_initialized.
        resp = self.client.post('/api/vault/sync/', {}, format='json')
        self.assertNotEqual(resp.status_code, 405, resp.content)
        self.assertNotEqual(resp.status_code, 404, resp.content)
        self.assertEqual(resp.status_code, 400, resp.content)
        self.assertEqual(resp.json().get('code'), 'vault_not_initialized')

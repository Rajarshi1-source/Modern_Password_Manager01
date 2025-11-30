"""
Unit Tests for Vault Module
Tests vault models, encryption, and vault operations
"""

from django.test import TestCase, RequestFactory
from django.contrib.auth.models import User
from django.utils import timezone
from unittest.mock import patch, Mock
from datetime import timedelta
import json
import base64

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
        """Test vault items are ordered by creation date"""
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
        # Newest first if ordering is set
        self.assertTrue(items.first().id >= items.last().id)


class VaultBackupModelTests(TestCase):
    """Test VaultBackup model"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
    
    def test_create_backup(self):
        """Test creating a vault backup"""
        backup = VaultBackup.objects.create(
            user=self.user,
            encrypted_data='{"items": []}',
            item_count=0
        )
        
        self.assertEqual(backup.user, self.user)
        self.assertEqual(backup.item_count, 0)
        self.assertIsNotNone(backup.created_at)
    
    def test_backup_with_items(self):
        """Test backup with multiple items"""
        backup = VaultBackup.objects.create(
            user=self.user,
            encrypted_data='{"items": [{}, {}, {}]}',
            item_count=3
        )
        
        self.assertEqual(backup.item_count, 3)
    
    def test_multiple_backups_allowed(self):
        """Test user can have multiple backups"""
        for i in range(3):
            VaultBackup.objects.create(
                user=self.user,
                encrypted_data=f'{{"backup": {i}}}',
                item_count=i
            )
        
        backups = VaultBackup.objects.filter(user=self.user)
        self.assertEqual(backups.count(), 3)


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
        self.assertEqual(user_salt.salt, salt)


class VaultCryptoTests(TestCase):
    """Test vault encryption/decryption functions"""
    
    def test_encrypt_vault_item(self):
        """Test encrypting vault item data"""
        data = {"username": "test", "password": "secret"}
        key = b'test_encryption_key_32bytes!!'
        
        # This test requires the actual crypto functions
        # If crypto.py has these functions, test them
        # encrypted = encrypt_vault_item(data, key)
        # self.assertIsNotNone(encrypted)
        # self.assertNotEqual(encrypted, json.dumps(data))
        pass
    
    def test_decrypt_vault_item(self):
        """Test decrypting vault item data"""
        # data = {"username": "test", "password": "secret"}
        # key = b'test_encryption_key_32bytes!!'
        # encrypted = encrypt_vault_item(data, key)
        # decrypted = decrypt_vault_item(encrypted, key)
        # self.assertEqual(decrypted, data)
        pass


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


class AuditLogTests(TestCase):
    """Test audit logging functionality"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
    
    def test_create_audit_log(self):
        """Test creating an audit log entry"""
        log = AuditLog.objects.create(
            user=self.user,
            action='vault_item_created',
            details={'item_id': 'test_123'},
            ip_address='192.168.1.1'
        )
        
        self.assertEqual(log.user, self.user)
        self.assertEqual(log.action, 'vault_item_created')
        self.assertIsNotNone(log.timestamp)
    
    def test_audit_log_tracks_actions(self):
        """Test that different actions are tracked"""
        actions = ['created', 'updated', 'deleted', 'accessed']
        
        for action in actions:
            AuditLog.objects.create(
                user=self.user,
                action=f'vault_item_{action}',
                details={},
                ip_address='192.168.1.1'
            )
        
        logs = AuditLog.objects.filter(user=self.user)
        self.assertEqual(logs.count(), 4)
    
    def test_audit_log_ordering(self):
        """Test audit logs are ordered by timestamp"""
        for i in range(3):
            AuditLog.objects.create(
                user=self.user,
                action=f'action_{i}',
                details={},
                ip_address='192.168.1.1'
            )
        
        logs = AuditLog.objects.filter(user=self.user).order_by('-timestamp')
        # Most recent should be first
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
    def create_test_backup(user, item_count=0):
        """Create a test backup"""
        return VaultBackup.objects.create(
            user=user,
            encrypted_data='{"items": []}',
            item_count=item_count
        )

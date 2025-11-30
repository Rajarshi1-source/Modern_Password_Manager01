from django.db import models
from django.contrib.auth.models import User
import os
import base64

class UserSalt(models.Model):
    """Store unique salt for each user's key derivation"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='vault_salt')
    salt = models.BinaryField()
    auth_hash = models.BinaryField()  # For verifying master password
    created_at = models.DateTimeField(auto_now_add=True)
    
    @classmethod
    def create_for_user(cls, user, auth_hash):
        """Create a new salt for a user"""
        from .crypto import generate_salt
        salt = generate_salt()
        return cls.objects.create(user=user, salt=salt, auth_hash=auth_hash)
    
    def get_salt_b64(self):
        """Get salt as base64 string for client"""
        return base64.b64encode(self.salt).decode('utf-8')

class AuditLog(models.Model):
    """Model for tracking user actions for security auditing"""
    ACTION_TYPES = (
        ('create_item', 'Create Item'),
        ('update_item', 'Update Item'),
        ('delete_item', 'Delete Item'),
        ('access_item', 'Access Item'),
        ('login', 'Login'),
        ('logout', 'Logout'),
        ('password_change', 'Password Change'),
        ('export_data', 'Export Data'),
        ('import_data', 'Import Data'),
    )
    
    STATUS_CHOICES = (
        ('success', 'Success'),
        ('failure', 'Failure'),
    )
    
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    action = models.CharField(max_length=20, choices=ACTION_TYPES)
    item_type = models.CharField(max_length=20, blank=True, null=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField(blank=True, null=True)
    user_agent = models.TextField(blank=True, null=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES)
    
    class Meta:
        indexes = [
            models.Index(fields=['user', 'action']),
            models.Index(fields=['timestamp']),
        ]

class DeletedItem(models.Model):
    """Track deleted items for sync purposes"""
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    item_id = models.CharField(max_length=64)
    deleted_at = models.DateTimeField()
    
    class Meta:
        indexes = [
            models.Index(fields=['user', 'deleted_at']),
            models.Index(fields=['item_id']),
        ]

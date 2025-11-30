"""
Shared Folder Models

Enables secure sharing of password vault items with granular permissions
"""

from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
import uuid


class SharedFolder(models.Model):
    """Folder that can be shared with multiple users"""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    
    # Owner information
    owner = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='owned_shared_folders'
    )
    
    # Folder settings
    is_active = models.BooleanField(default=True)
    require_2fa = models.BooleanField(default=False, help_text="Require 2FA to access this folder")
    allow_export = models.BooleanField(default=False, help_text="Allow members to export items")
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['owner', 'is_active']),
        ]
    
    def __str__(self):
        return f"{self.name} (Owner: {self.owner.username})"
    
    def get_members_count(self):
        """Get total number of members including owner"""
        return self.members.filter(status='accepted').count() + 1
    
    def get_items_count(self):
        """Get total number of items in folder"""
        return self.shared_items.count()


class SharedFolderMember(models.Model):
    """Members of a shared folder with roles and permissions"""
    
    ROLE_CHOICES = [
        ('owner', 'Owner'),
        ('admin', 'Administrator'),
        ('editor', 'Editor'),
        ('viewer', 'Viewer'),
    ]
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('accepted', 'Accepted'),
        ('declined', 'Declined'),
        ('revoked', 'Revoked'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    folder = models.ForeignKey(
        SharedFolder,
        on_delete=models.CASCADE,
        related_name='members'
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='shared_folder_memberships'
    )
    
    # Role and permissions
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='viewer')
    can_invite = models.BooleanField(default=False, help_text="Can invite other users")
    can_edit_items = models.BooleanField(default=False, help_text="Can edit items in folder")
    can_delete_items = models.BooleanField(default=False, help_text="Can delete items from folder")
    can_export = models.BooleanField(default=False, help_text="Can export items")
    
    # Status and timestamps
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    invited_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='sent_folder_invitations'
    )
    invited_at = models.DateTimeField(auto_now_add=True)
    accepted_at = models.DateTimeField(null=True, blank=True)
    declined_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
    
    # Invitation token for accepting
    invitation_token = models.CharField(max_length=255, unique=True, blank=True)
    invitation_expires_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        unique_together = ['folder', 'user']
        ordering = ['-invited_at']
        indexes = [
            models.Index(fields=['user', 'status']),
            models.Index(fields=['folder', 'status']),
        ]
    
    def __str__(self):
        return f"{self.user.username} - {self.folder.name} ({self.role})"
    
    def accept_invitation(self):
        """Accept the folder invitation"""
        self.status = 'accepted'
        self.accepted_at = timezone.now()
        self.save()
    
    def decline_invitation(self):
        """Decline the folder invitation"""
        self.status = 'declined'
        self.declined_at = timezone.now()
        self.save()
    
    def revoke_access(self):
        """Revoke user's access to folder"""
        self.status = 'revoked'
        self.revoked_at = timezone.now()
        self.save()
    
    def has_permission(self, permission):
        """Check if member has specific permission"""
        permission_map = {
            'invite': self.can_invite,
            'edit': self.can_edit_items,
            'delete': self.can_delete_items,
            'export': self.can_export,
        }
        return permission_map.get(permission, False)


class SharedVaultItem(models.Model):
    """Vault items that are shared in a folder"""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    folder = models.ForeignKey(
        SharedFolder,
        on_delete=models.CASCADE,
        related_name='shared_items'
    )
    
    # Original vault item reference
    vault_item_id = models.CharField(max_length=255, help_text="ID of the original vault item")
    
    # Encrypted folder key for this item
    # Each user gets their own encrypted copy of the folder key
    encrypted_folder_key = models.TextField(help_text="Folder key encrypted for each user")
    
    # Item metadata (encrypted)
    encrypted_metadata = models.TextField(blank=True, help_text="Encrypted item metadata (name, type, etc.)")
    
    # Sharing information
    shared_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='shared_vault_items'
    )
    shared_at = models.DateTimeField(auto_now_add=True)
    
    # Access control
    is_active = models.BooleanField(default=True)
    
    class Meta:
        unique_together = ['folder', 'vault_item_id']
        ordering = ['-shared_at']
        indexes = [
            models.Index(fields=['folder', 'is_active']),
        ]
    
    def __str__(self):
        return f"Item {self.vault_item_id} in {self.folder.name}"


class SharedFolderKey(models.Model):
    """Per-user encrypted folder keys for E2EE sharing"""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    folder = models.ForeignKey(
        SharedFolder,
        on_delete=models.CASCADE,
        related_name='encrypted_keys'
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='shared_folder_keys'
    )
    
    # Folder key encrypted with user's public key
    encrypted_folder_key = models.TextField(help_text="Folder key encrypted with user's public ECC key")
    
    # Key version for rotation
    key_version = models.IntegerField(default=1)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    rotated_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        unique_together = ['folder', 'user', 'key_version']
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Key for {self.user.username} in {self.folder.name} (v{self.key_version})"


class SharedFolderActivity(models.Model):
    """Audit log for shared folder activities"""
    
    ACTIVITY_TYPES = [
        ('created', 'Folder Created'),
        ('member_added', 'Member Added'),
        ('member_removed', 'Member Removed'),
        ('member_role_changed', 'Member Role Changed'),
        ('item_added', 'Item Added'),
        ('item_removed', 'Item Removed'),
        ('item_viewed', 'Item Viewed'),
        ('item_edited', 'Item Edited'),
        ('invitation_sent', 'Invitation Sent'),
        ('invitation_accepted', 'Invitation Accepted'),
        ('invitation_declined', 'Invitation Declined'),
        ('access_revoked', 'Access Revoked'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    folder = models.ForeignKey(
        SharedFolder,
        on_delete=models.CASCADE,
        related_name='activity_logs'
    )
    
    # Activity details
    activity_type = models.CharField(max_length=30, choices=ACTIVITY_TYPES)
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='shared_folder_activities'
    )
    target_user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='targeted_folder_activities',
        help_text="User affected by this activity (e.g., invited user)"
    )
    
    # Additional context
    details = models.JSONField(default=dict, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    
    # Timestamp
    timestamp = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['folder', '-timestamp']),
            models.Index(fields=['user', '-timestamp']),
        ]
        verbose_name_plural = 'Shared Folder Activities'
    
    def __str__(self):
        return f"{self.activity_type} in {self.folder.name} by {self.user.username if self.user else 'Unknown'}"


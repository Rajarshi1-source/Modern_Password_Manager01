"""
Email Masking Models

Manages email aliases for privacy protection
"""

from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


class EmailAlias(models.Model):
    """Store email aliases created for users"""
    
    PROVIDER_CHOICES = [
        ('simplelogin', 'SimpleLogin'),
        ('anonaddy', 'AnonAddy'),
        ('custom', 'Custom Provider'),
    ]
    
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('disabled', 'Disabled'),
        ('deleted', 'Deleted'),
    ]
    
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='email_aliases'
    )
    
    # Alias details
    alias_email = models.EmailField(unique=True, help_text="The masked email address")
    alias_name = models.CharField(max_length=255, blank=True, help_text="User-friendly name for the alias")
    description = models.TextField(blank=True, help_text="What this alias is used for")
    
    # Provider information
    provider = models.CharField(max_length=20, choices=PROVIDER_CHOICES, default='simplelogin')
    provider_alias_id = models.CharField(max_length=255, blank=True, help_text="ID from the provider's API")
    
    # Forwarding
    forwards_to = models.EmailField(help_text="Real email address that receives forwarded emails")
    
    # Status and statistics
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    emails_received = models.IntegerField(default=0)
    emails_forwarded = models.IntegerField(default=0)
    emails_blocked = models.IntegerField(default=0)
    
    # Associated vault item (optional)
    vault_item_id = models.CharField(max_length=255, blank=True, null=True, help_text="Associated password vault item")
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_used_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True, help_text="Optional expiration date")
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'status']),
            models.Index(fields=['alias_email']),
            models.Index(fields=['provider', 'provider_alias_id']),
        ]
    
    def __str__(self):
        return f"{self.alias_email} -> {self.forwards_to}"
    
    def is_active(self):
        """Check if alias is active and not expired"""
        if self.status != 'active':
            return False
        if self.expires_at and self.expires_at < timezone.now():
            return False
        return True
    
    def mark_used(self):
        """Update last_used_at timestamp"""
        self.last_used_at = timezone.now()
        self.save(update_fields=['last_used_at'])


class EmailMaskingProvider(models.Model):
    """Store user's email masking provider credentials"""
    
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='email_providers'
    )
    
    provider = models.CharField(max_length=20, choices=EmailAlias.PROVIDER_CHOICES)
    api_key = models.CharField(max_length=500, help_text="Encrypted API key")
    api_endpoint = models.URLField(blank=True, help_text="Custom API endpoint if applicable")
    
    # Settings
    is_active = models.BooleanField(default=True)
    is_default = models.BooleanField(default=False, help_text="Default provider for new aliases")
    
    # Limits and quotas
    monthly_quota = models.IntegerField(default=0, help_text="Monthly alias creation limit (0 = unlimited)")
    aliases_created_this_month = models.IntegerField(default=0)
    quota_reset_date = models.DateField(null=True, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_sync_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        unique_together = ['user', 'provider']
        verbose_name = 'Email Masking Provider'
        verbose_name_plural = 'Email Masking Providers'
    
    def __str__(self):
        return f"{self.user.username} - {self.provider}"
    
    def can_create_alias(self):
        """Check if user can create more aliases this month"""
        if self.monthly_quota == 0:
            return True
        return self.aliases_created_this_month < self.monthly_quota


class EmailAliasActivity(models.Model):
    """Log email alias activity"""
    
    ACTIVITY_TYPES = [
        ('received', 'Email Received'),
        ('forwarded', 'Email Forwarded'),
        ('blocked', 'Email Blocked'),
        ('spam', 'Spam Detected'),
        ('created', 'Alias Created'),
        ('deleted', 'Alias Deleted'),
        ('disabled', 'Alias Disabled'),
        ('enabled', 'Alias Enabled'),
    ]
    
    alias = models.ForeignKey(
        EmailAlias,
        on_delete=models.CASCADE,
        related_name='activity_logs'
    )
    
    activity_type = models.CharField(max_length=20, choices=ACTIVITY_TYPES)
    sender_email = models.EmailField(blank=True, help_text="Sender of the email (if applicable)")
    subject = models.CharField(max_length=500, blank=True)
    details = models.JSONField(default=dict, blank=True)
    
    timestamp = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['alias', '-timestamp']),
        ]
    
    def __str__(self):
        return f"{self.alias.alias_email} - {self.activity_type} at {self.timestamp}"


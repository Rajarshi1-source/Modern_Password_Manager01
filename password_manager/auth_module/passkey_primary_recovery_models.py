"""
Primary Passkey Recovery Models
Implements direct passkey recovery using encrypted backups with Kyber + AES-GCM
Falls back to Social Mesh Recovery if primary recovery fails
"""

from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
import hashlib

User = get_user_model()


class PasskeyRecoveryBackup(models.Model):
    """
    Stores encrypted backup of a user's passkey credentials.
    Encrypted using Kyber + AES-GCM hybrid encryption with a recovery key.
    """
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='passkey_recovery_backups'
    )
    passkey_credential_id = models.BinaryField(
        help_text="ID of the passkey this backup is for"
    )
    encrypted_credential_data = models.BinaryField(
        help_text="Kyber + AES-GCM encrypted passkey credential data (public key, metadata)"
    )
    recovery_key_hash = models.CharField(
        max_length=128,
        help_text="SHA-256 hash of the recovery key for validation"
    )
    kyber_public_key = models.BinaryField(
        help_text="User's Kyber public key for this backup"
    )
    encryption_metadata = models.JSONField(
        default=dict,
        help_text="Metadata for decryption (salt, IV, etc.)"
    )
    device_name = models.CharField(
        max_length=255,
        blank=True,
        help_text="Name of the device this backup is for"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_verified_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Last time this backup was verified"
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Whether this backup is currently valid"
    )
    
    class Meta:
        verbose_name = "Passkey Recovery Backup"
        verbose_name_plural = "Passkey Recovery Backups"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'is_active']),
            models.Index(fields=['recovery_key_hash']),
        ]
    
    def __str__(self):
        return f"Passkey backup for {self.user.username} - {self.device_name or 'Unnamed device'}"
    
    def verify_recovery_key(self, recovery_key: str) -> bool:
        """Verify if the provided recovery key matches the stored hash."""
        key_hash = hashlib.sha256(recovery_key.encode()).hexdigest()
        return key_hash == self.recovery_key_hash


class PasskeyRecoveryAttempt(models.Model):
    """
    Logs attempts to recover passkeys using the primary recovery mechanism.
    Tracks success/failure and fallback to social mesh recovery.
    """
    STATUS_CHOICES = [
        ('initiated', 'Initiated'),
        ('key_verified', 'Recovery Key Verified'),
        ('decryption_success', 'Decryption Successful'),
        ('recovery_complete', 'Recovery Complete'),
        ('key_invalid', 'Invalid Recovery Key'),
        ('decryption_failed', 'Decryption Failed'),
        ('fallback_initiated', 'Fallback to Social Mesh Initiated'),
        ('failed', 'Failed'),
    ]
    
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='passkey_primary_recovery_attempts'
    )
    backup = models.ForeignKey(
        PasskeyRecoveryBackup,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='recovery_attempts'
    )
    status = models.CharField(
        max_length=30,
        choices=STATUS_CHOICES,
        default='initiated'
    )
    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
        help_text="IP address of recovery attempt"
    )
    user_agent = models.TextField(
        blank=True,
        help_text="Browser/device user agent"
    )
    initiated_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    failed_at = models.DateTimeField(null=True, blank=True)
    fallback_recovery_attempt_id = models.IntegerField(
        null=True,
        blank=True,
        help_text="ID of social mesh recovery attempt if fallback was initiated"
    )
    failure_reason = models.TextField(
        blank=True,
        help_text="Reason for failure if recovery failed"
    )
    notes = models.TextField(
        blank=True,
        help_text="Additional notes or context"
    )
    
    class Meta:
        verbose_name = "Passkey Primary Recovery Attempt"
        verbose_name_plural = "Passkey Primary Recovery Attempts"
        ordering = ['-initiated_at']
        indexes = [
            models.Index(fields=['user', 'status']),
            models.Index(fields=['initiated_at']),
        ]
    
    def __str__(self):
        return f"Recovery attempt by {self.user.username} - {self.status} ({self.initiated_at})"
    
    def mark_failed(self, reason: str):
        """Mark this recovery attempt as failed."""
        self.status = 'failed'
        self.failed_at = timezone.now()
        self.failure_reason = reason
        self.save()
    
    def mark_complete(self):
        """Mark this recovery attempt as complete."""
        self.status = 'recovery_complete'
        self.completed_at = timezone.now()
        self.save()
    
    def initiate_fallback(self):
        """Initiate fallback to social mesh recovery."""
        self.status = 'fallback_initiated'
        self.save()


class RecoveryKeyRevocation(models.Model):
    """
    Tracks revocation of recovery keys (e.g., if user suspects compromise).
    """
    backup = models.ForeignKey(
        PasskeyRecoveryBackup,
        on_delete=models.CASCADE,
        related_name='revocations'
    )
    revoked_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE
    )
    revoked_at = models.DateTimeField(auto_now_add=True)
    reason = models.TextField(
        blank=True,
        help_text="Reason for revocation"
    )
    new_backup_created = models.BooleanField(
        default=False,
        help_text="Whether a new backup was created after revocation"
    )
    
    class Meta:
        verbose_name = "Recovery Key Revocation"
        verbose_name_plural = "Recovery Key Revocations"
        ordering = ['-revoked_at']
    
    def __str__(self):
        return f"Revocation of backup {self.backup.id} by {self.revoked_by.username}"


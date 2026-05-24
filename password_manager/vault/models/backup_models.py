from django.db import models
from django.conf import settings
from django.utils import timezone
import uuid

class VaultBackup(models.Model):
    """Model for storing encrypted vault backups"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='vault_backups'
    )
    name = models.CharField(max_length=100)
    encrypted_data = models.TextField()
    size = models.IntegerField(default=0)  # Size in bytes
    cloud_storage_path = models.CharField(max_length=255, blank=True, null=True)
    cloud_sync_status = models.CharField(
        max_length=20,
        choices=[
            ('pending', 'Pending'),
            ('synced', 'Synced'),
            ('failed', 'Failed')
        ],
        default='pending'
    )
    # Audit-fix M8 (2026-05): the client commits to a Content-MD5 of
    # the bytes it's about to PUT at presign time. The presigned URL
    # bakes the digest in as a precondition (S3 ContentMD5 / GCS
    # Content-MD5 header), so a leaked URL alone cannot be used to
    # corrupt the backup with attacker-chosen bytes. We persist it
    # on the row so `complete_cloud_upload` can re-verify post-PUT.
    content_md5 = models.CharField(max_length=32, blank=True, default='')
    created_at = models.DateTimeField(default=timezone.now)
    
    class Meta:
        ordering = ['-created_at']
        
    def __str__(self):
        return f"Backup {self.name} ({self.created_at.strftime('%Y-%m-%d %H:%M')})"

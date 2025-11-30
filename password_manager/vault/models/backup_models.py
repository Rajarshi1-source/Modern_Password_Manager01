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
    created_at = models.DateTimeField(default=timezone.now)
    
    class Meta:
        ordering = ['-created_at']
        
    def __str__(self):
        return f"Backup {self.name} ({self.created_at.strftime('%Y-%m-%d %H:%M')})"

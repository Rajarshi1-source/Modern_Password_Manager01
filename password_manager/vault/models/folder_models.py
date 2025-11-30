from django.db import models
from django.contrib.auth.models import User

class VaultFolder(models.Model):
    """Model for organizing vault items into folders"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='vault_folders')
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='subfolders')
    color = models.CharField(max_length=20, default='#4A6CF7')
    icon = models.CharField(max_length=50, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['name']
        unique_together = ['user', 'name', 'parent']
        
    def __str__(self):
        return f"{self.name} ({self.user.username})"
        
    @property
    def path(self):
        """Get the full path of the folder"""
        if self.parent:
            return f"{self.parent.path}/{self.name}"
        return self.name

from django.db import models
from django.conf import settings
from django.utils import timezone

class BreachAlert(models.Model):
    """Model to store data breach alerts for users"""
    SEVERITY_CHOICES = (
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('critical', 'Critical'),
    )
    
    DATA_TYPE_CHOICES = (
        ('password', 'Password'),
        ('email', 'Email'),
        ('username', 'Username'),
        ('phone', 'Phone Number'),
        ('other', 'Other'),
    )
    
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE,
        related_name='breach_alerts'
    )
    breach_name = models.CharField(max_length=255)
    breach_date = models.DateField(null=True, blank=True)
    breach_description = models.TextField(blank=True)
    data_type = models.CharField(
        max_length=20, 
        choices=DATA_TYPE_CHOICES,
        default='password'
    )
    identifier = models.CharField(max_length=255, help_text="Item identifier (email/username)")
    exposed_data = models.JSONField(default=dict, blank=True)
    severity = models.CharField(
        max_length=10, 
        choices=SEVERITY_CHOICES,
        default='medium'
    )
    detected_at = models.DateTimeField(default=timezone.now)
    resolved = models.BooleanField(default=False)
    resolved_at = models.DateTimeField(null=True, blank=True)
    notified = models.BooleanField(default=False)
    notification_sent_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-detected_at']
        indexes = [
            models.Index(fields=['user', 'resolved']),
            models.Index(fields=['user', 'breach_name', 'identifier']),
        ]
    
    def __str__(self):
        return f"{self.breach_name} - {self.identifier} ({self.user.username})"
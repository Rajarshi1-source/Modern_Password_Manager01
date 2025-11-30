from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
import uuid

# Create your models here.

class UserDevice(models.Model):
    """Stores information about user devices for authentication verification"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='devices')
    device_id = models.UUIDField(default=uuid.uuid4, unique=True)
    device_name = models.CharField(max_length=255, blank=True)
    device_type = models.CharField(max_length=50, blank=True)  # mobile, desktop, tablet
    fingerprint = models.CharField(max_length=255, unique=True, blank=True)  # Device fingerprint
    browser = models.CharField(max_length=100, blank=True)
    os = models.CharField(max_length=100, blank=True)
    ip_address = models.GenericIPAddressField()
    is_trusted = models.BooleanField(default=False)
    last_seen = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['user', 'device_id']
        
    def __str__(self):
        return f"{self.device_name} - {self.user.username}"

class SocialMediaAccount(models.Model):
    """Stores user's social media accounts for protection"""
    PLATFORM_CHOICES = [
        ('facebook', 'Facebook'),
        ('twitter', 'Twitter/X'),
        ('instagram', 'Instagram'),
        ('linkedin', 'LinkedIn'),
        ('github', 'GitHub'),
        ('google', 'Google'),
        ('microsoft', 'Microsoft'),
        ('apple', 'Apple'),
    ]
    
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('locked', 'Locked'),
        ('suspended', 'Suspended'),
        ('monitoring', 'Under Monitoring'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='social_accounts')
    platform = models.CharField(max_length=20, choices=PLATFORM_CHOICES)
    username = models.CharField(max_length=255)
    email = models.EmailField(blank=True)
    account_id = models.CharField(max_length=255, blank=True)
    api_token = models.TextField(blank=True)  # Encrypted token for API access
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    auto_lock_enabled = models.BooleanField(default=True)
    last_checked = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['user', 'platform', 'username']
        
    def __str__(self):
        return f"{self.platform} - {self.username} ({self.user.username})"

class LoginAttempt(models.Model):
    """Tracks login attempts for security monitoring"""
    STATUS_CHOICES = [
        ('success', 'Success'),
        ('failed', 'Failed'),
        ('blocked', 'Blocked'),
        ('suspicious', 'Suspicious'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='login_attempts', null=True, blank=True)
    username_attempted = models.CharField(max_length=255)
    ip_address = models.GenericIPAddressField()
    device_fingerprint = models.CharField(max_length=255, blank=True)  # Device fingerprint
    user_agent = models.TextField()
    location = models.CharField(max_length=255, blank=True)
    device = models.ForeignKey(UserDevice, on_delete=models.SET_NULL, null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)
    failure_reason = models.CharField(max_length=255, blank=True)
    is_suspicious = models.BooleanField(default=False)
    threat_score = models.IntegerField(default=0)  # 0-100 risk score
    suspicious_factors = models.JSONField(default=dict, blank=True)  # Factors contributing to suspicion
    timestamp = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['user', 'timestamp']),
            models.Index(fields=['ip_address', 'timestamp']),
            models.Index(fields=['is_suspicious', 'timestamp']),
        ]
        
    def __str__(self):
        return f"Login attempt for {self.username_attempted} from {self.ip_address}"

class SecurityAlert(models.Model):
    """Security alerts and notifications"""
    ALERT_TYPES = [
        ('unauthorized_login', 'Unauthorized Login Attempt'),
        ('account_locked', 'Account Locked'),
        ('suspicious_activity', 'Suspicious Activity'),
        ('new_device', 'New Device Login'),
        ('location_anomaly', 'Unusual Location'),
        ('multiple_failures', 'Multiple Failed Attempts'),
    ]
    
    SEVERITY_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('critical', 'Critical'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='security_alerts')
    alert_type = models.CharField(max_length=30, choices=ALERT_TYPES)
    severity = models.CharField(max_length=10, choices=SEVERITY_CHOICES)
    title = models.CharField(max_length=255)
    message = models.TextField()
    data = models.JSONField(default=dict, blank=True)  # Additional alert data
    is_read = models.BooleanField(default=False)
    is_resolved = models.BooleanField(default=False)
    resolved_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
        
    def __str__(self):
        return f"{self.alert_type} - {self.user.username}"

class UserNotificationSettings(models.Model):
    """User preferences for security notifications"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='notification_settings')
    email_alerts = models.BooleanField(default=True)
    sms_alerts = models.BooleanField(default=False)
    push_alerts = models.BooleanField(default=True)
    alert_on_new_device = models.BooleanField(default=True)
    alert_on_new_location = models.BooleanField(default=True)
    alert_on_suspicious_activity = models.BooleanField(default=True)
    auto_lock_accounts = models.BooleanField(default=True)
    suspicious_activity_threshold = models.IntegerField(default=3)  # Number of failed attempts
    minimum_risk_score_for_alert = models.DecimalField(max_digits=5, decimal_places=2, default=0.7)
    alert_cooldown_minutes = models.IntegerField(default=15)  # Minimum time between alerts
    phone_number = models.CharField(max_length=20, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"Notification settings for {self.user.username}"

class AccountLockEvent(models.Model):
    """Tracks when accounts are locked/unlocked"""
    ACTION_CHOICES = [
        ('lock', 'Lock'),
        ('unlock', 'Unlock'),
        ('suspend', 'Suspend'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='lock_events')
    social_account = models.ForeignKey(SocialMediaAccount, on_delete=models.CASCADE, related_name='lock_events')
    action = models.CharField(max_length=10, choices=ACTION_CHOICES)
    reason = models.TextField()
    triggered_by_alert = models.ForeignKey(SecurityAlert, on_delete=models.SET_NULL, null=True, blank=True)
    auto_triggered = models.BooleanField(default=False)
    success = models.BooleanField(default=False)
    error_message = models.TextField(blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-timestamp']
        
    def __str__(self):
        return f"{self.action} {self.social_account.platform} for {self.user.username}"

class Notification(models.Model):
    NOTIFICATION_TYPES = [
        ('login_alert', 'Login Alert'),
        ('device_alert', 'New Device Alert'),
        ('location_alert', 'New Location Alert'),
        ('security_alert', 'Security Alert'),
    ]
    
    CHANNELS = [
        ('email', 'Email'),
        ('sms', 'SMS'),
        ('push', 'Push Notification'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    notification_type = models.CharField(max_length=50, choices=NOTIFICATION_TYPES)
    channel = models.CharField(max_length=20, choices=CHANNELS)
    content = models.TextField()
    related_event_id = models.IntegerField(null=True, blank=True)
    is_delivered = models.BooleanField(default=False)
    delivered_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.notification_type} for {self.user.username}"

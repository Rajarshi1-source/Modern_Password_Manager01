"""
Honeypot Email Models for Breach Detection
===========================================

Models for managing honeypot (canary) email addresses used to detect data breaches
before public disclosure. When a honeypot receives spam/contact, the associated 
service is flagged as potentially compromised.

@author Password Manager Team
@created 2026-02-01
"""

import uuid
import hashlib
import json
from django.conf import settings
from django.db import models
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator


class HoneypotConfiguration(models.Model):
    """
    User-level configuration for honeypot email feature.
    Controls behavior like auto-rotation and notification preferences.
    """
    
    EMAIL_PROVIDER_CHOICES = [
        ('simplelogin', 'SimpleLogin'),
        ('anonaddy', 'AnonAddy'),
        ('custom', 'Custom SMTP'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='honeypot_config'
    )
    
    # Feature toggles
    is_enabled = models.BooleanField(
        default=True,
        help_text="Master switch for honeypot email feature"
    )
    
    # Email provider settings
    email_provider = models.CharField(
        max_length=20,
        choices=EMAIL_PROVIDER_CHOICES,
        default='simplelogin',
        help_text="Email aliasing service to use"
    )
    provider_api_key = models.TextField(
        blank=True,
        help_text="Encrypted API key for the email provider"
    )
    custom_domain = models.CharField(
        max_length=255,
        blank=True,
        help_text="Custom domain for honeypot emails (enterprise only)"
    )
    
    # Rotation behavior (per user recommendations)
    auto_rotate_on_breach = models.BooleanField(
        default=False,  # Safe default - user must opt-in
        help_text="Automatically rotate credentials when breach detected"
    )
    require_confirmation = models.BooleanField(
        default=True,  # Always ask user by default
        help_text="Require user confirmation before credential rotation"
    )
    
    # Vault integration settings
    auto_create_on_signup = models.BooleanField(
        default=False,  # Manual creation by default
        help_text="Automatically create honeypot when adding vault items"
    )
    suggest_honeypot_creation = models.BooleanField(
        default=True,
        help_text="Show suggestion to create honeypot when adding vault items"
    )
    
    # Notification preferences
    notify_on_any_activity = models.BooleanField(
        default=True,
        help_text="Notify on any honeypot email activity"
    )
    notify_on_breach = models.BooleanField(
        default=True,
        help_text="Notify when breach is confirmed"
    )
    notification_email = models.EmailField(
        blank=True,
        help_text="Override email for honeypot notifications"
    )
    
    # Limits
    max_honeypots = models.PositiveIntegerField(
        default=50,
        validators=[MinValueValidator(1), MaxValueValidator(500)],
        help_text="Maximum honeypot emails allowed"
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Honeypot Configuration"
        verbose_name_plural = "Honeypot Configurations"
    
    def __str__(self):
        return f"Honeypot Config for {self.user.username}"
    
    @property
    def honeypot_count(self):
        """Get current honeypot count for this user."""
        return self.user.honeypot_emails.filter(is_active=True).count()
    
    @property
    def can_create_honeypot(self):
        """Check if user can create more honeypots."""
        return self.honeypot_count < self.max_honeypots


class HoneypotEmail(models.Model):
    """
    Individual honeypot email address linked to a service/vault item.
    Each honeypot is unique and monitors for breach activity.
    """
    
    STATUS_CHOICES = [
        ('active', 'Active - Monitoring'),
        ('triggered', 'Triggered - Activity Detected'),
        ('breached', 'Breached - Confirmed Compromise'),
        ('disabled', 'Disabled'),
        ('expired', 'Expired'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='honeypot_emails'
    )
    
    # Honeypot email details
    honeypot_address = models.EmailField(
        unique=True,
        help_text="The unique honeypot email address"
    )
    provider_alias_id = models.CharField(
        max_length=255,
        blank=True,
        help_text="ID of the alias in the email provider's system"
    )
    
    # Service association
    service_name = models.CharField(
        max_length=255,
        help_text="Name of the service this honeypot is registered with"
    )
    service_domain = models.CharField(
        max_length=255,
        blank=True,
        help_text="Domain of the associated service (e.g., example.com)"
    )
    vault_item_id = models.UUIDField(
        null=True,
        blank=True,
        help_text="Optional link to vault password entry"
    )
    
    # Status tracking
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='active'
    )
    is_active = models.BooleanField(default=True)
    
    # Activity metrics
    total_emails_received = models.PositiveIntegerField(default=0)
    spam_emails_received = models.PositiveIntegerField(default=0)
    last_activity_at = models.DateTimeField(null=True, blank=True)
    first_activity_at = models.DateTimeField(null=True, blank=True)
    
    # Breach detection
    breach_detected = models.BooleanField(default=False)
    breach_detected_at = models.DateTimeField(null=True, blank=True)
    breach_confidence = models.FloatField(
        default=0.0,
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        help_text="Confidence level that this is a real breach (0-1)"
    )
    
    # Metadata
    notes = models.TextField(blank=True, help_text="User notes about this honeypot")
    tags = models.JSONField(default=list, blank=True, help_text="Tags for organization")
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    expires_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Optional expiration date for the honeypot"
    )
    
    class Meta:
        verbose_name = "Honeypot Email"
        verbose_name_plural = "Honeypot Emails"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'status']),
            models.Index(fields=['honeypot_address']),
            models.Index(fields=['service_name']),
            models.Index(fields=['breach_detected']),
        ]
    
    def __str__(self):
        return f"Honeypot for {self.service_name}: {self.honeypot_address}"
    
    def record_activity(self, is_spam=False):
        """Record email activity on this honeypot."""
        now = timezone.now()
        self.total_emails_received += 1
        if is_spam:
            self.spam_emails_received += 1
        self.last_activity_at = now
        if not self.first_activity_at:
            self.first_activity_at = now
        if self.status == 'active':
            self.status = 'triggered'
        self.save()
    
    def confirm_breach(self, confidence=0.9):
        """Mark this honeypot as breached."""
        self.breach_detected = True
        self.breach_detected_at = timezone.now()
        self.breach_confidence = confidence
        self.status = 'breached'
        self.save()
    
    @property
    def days_active(self):
        """Number of days since honeypot was created."""
        return (timezone.now() - self.created_at).days
    
    @property
    def is_expired(self):
        """Check if honeypot has expired."""
        if self.expires_at:
            return timezone.now() > self.expires_at
        return False


class HoneypotActivity(models.Model):
    """
    Log of all activity (emails) received by honeypot addresses.
    Used for breach analysis and forensics.
    """
    
    ACTIVITY_TYPES = [
        ('email_received', 'Email Received'),
        ('spam_detected', 'Spam Detected'),
        ('phishing_detected', 'Phishing Detected'),
        ('marketing_email', 'Marketing Email'),
        ('password_reset', 'Password Reset Request'),
        ('account_notification', 'Account Notification'),
        ('unknown', 'Unknown'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    honeypot = models.ForeignKey(
        HoneypotEmail,
        on_delete=models.CASCADE,
        related_name='activities'
    )
    
    # Activity details
    activity_type = models.CharField(
        max_length=30,
        choices=ACTIVITY_TYPES,
        default='email_received'
    )
    
    # Email metadata (no actual content for privacy)
    sender_address = models.EmailField(blank=True)
    sender_domain = models.CharField(max_length=255, blank=True)
    subject_hash = models.CharField(
        max_length=64,
        blank=True,
        help_text="SHA-256 hash of subject for pattern matching"
    )
    subject_preview = models.CharField(
        max_length=100,
        blank=True,
        help_text="First 100 chars of subject (redacted sensitive info)"
    )
    
    # Analysis
    is_spam = models.BooleanField(default=False)
    spam_score = models.FloatField(
        default=0.0,
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)]
    )
    is_breach_indicator = models.BooleanField(
        default=False,
        help_text="Whether this activity indicates a breach"
    )
    breach_indicators = models.JSONField(
        default=dict,
        blank=True,
        help_text="Detected breach indicators"
    )
    
    # Raw data (encrypted)
    raw_headers = models.TextField(
        blank=True,
        help_text="Encrypted email headers for forensics"
    )
    
    # Timestamps
    received_at = models.DateTimeField(default=timezone.now)
    processed_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Honeypot Activity"
        verbose_name_plural = "Honeypot Activities"
        ordering = ['-received_at']
        indexes = [
            models.Index(fields=['honeypot', 'received_at']),
            models.Index(fields=['activity_type']),
            models.Index(fields=['is_breach_indicator']),
        ]
    
    def __str__(self):
        return f"Activity on {self.honeypot.service_name} at {self.received_at}"
    
    @staticmethod
    def hash_subject(subject):
        """Hash email subject for privacy-preserving pattern matching."""
        return hashlib.sha256(subject.encode()).hexdigest()
    
    def analyze_for_breach(self):
        """Analyze this activity for breach indicators."""
        indicators = {}
        
        # Spam from unknown sender = high breach indicator
        if self.is_spam and self.sender_domain:
            indicators['spam_from_unknown'] = True
        
        # Marketing email = medium breach indicator
        if self.activity_type == 'marketing_email':
            indicators['marketing_received'] = True
        
        # Multiple activities in short period
        recent_count = HoneypotActivity.objects.filter(
            honeypot=self.honeypot,
            received_at__gte=timezone.now() - timezone.timedelta(hours=24)
        ).count()
        if recent_count > 3:
            indicators['activity_spike'] = recent_count
        
        self.breach_indicators = indicators
        self.is_breach_indicator = bool(indicators)
        self.save()
        
        return indicators


class HoneypotBreachEvent(models.Model):
    """
    Confirmed breach event detected via honeypot.
    Tracks timeline and response actions.
    """
    
    SEVERITY_CHOICES = [
        ('low', 'Low - Possible data sharing'),
        ('medium', 'Medium - Likely breach'),
        ('high', 'High - Confirmed breach'),
        ('critical', 'Critical - Active exploitation'),
    ]
    
    STATUS_CHOICES = [
        ('detected', 'Detected'),
        ('investigating', 'Investigating'),
        ('confirmed', 'Confirmed'),
        ('mitigated', 'Mitigated'),
        ('resolved', 'Resolved'),
        ('false_positive', 'False Positive'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='honeypot_breaches'
    )
    honeypot = models.ForeignKey(
        HoneypotEmail,
        on_delete=models.SET_NULL,
        null=True,
        related_name='breach_events'
    )
    
    # Breach details
    service_name = models.CharField(max_length=255)
    severity = models.CharField(
        max_length=20,
        choices=SEVERITY_CHOICES,
        default='medium'
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='detected'
    )
    
    # Timeline
    detected_at = models.DateTimeField(default=timezone.now)
    first_activity_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When first suspicious activity was detected"
    )
    public_disclosure_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When breach was publicly disclosed (if known)"
    )
    resolved_at = models.DateTimeField(null=True, blank=True)
    
    # Detection details
    detection_method = models.CharField(
        max_length=100,
        default='honeypot_activity',
        help_text="How the breach was detected"
    )
    confidence_score = models.FloatField(
        default=0.8,
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)]
    )
    triggering_activities = models.JSONField(
        default=list,
        help_text="IDs of activities that triggered breach detection"
    )
    
    # Analysis
    exposed_data_types = models.JSONField(
        default=list,
        help_text="Types of data likely exposed (email, password, etc.)"
    )
    breach_source = models.CharField(
        max_length=255,
        blank=True,
        help_text="Suspected or confirmed source of breach"
    )
    
    # Response
    credentials_rotated = models.BooleanField(default=False)
    user_notified = models.BooleanField(default=False)
    notification_sent_at = models.DateTimeField(null=True, blank=True)
    
    # User response
    user_acknowledged = models.BooleanField(default=False)
    user_acknowledged_at = models.DateTimeField(null=True, blank=True)
    user_notes = models.TextField(blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Honeypot Breach Event"
        verbose_name_plural = "Honeypot Breach Events"
        ordering = ['-detected_at']
        indexes = [
            models.Index(fields=['user', 'status']),
            models.Index(fields=['severity']),
            models.Index(fields=['detected_at']),
        ]
    
    def __str__(self):
        return f"Breach: {self.service_name} ({self.severity})"
    
    @property
    def days_before_public(self):
        """Days breach was detected before public disclosure."""
        if self.public_disclosure_at and self.detected_at:
            delta = self.public_disclosure_at - self.detected_at
            return delta.days
        return None
    
    @property
    def timeline(self):
        """Get breach timeline as structured data."""
        events = []
        
        if self.first_activity_at:
            events.append({
                'event': 'first_activity',
                'timestamp': self.first_activity_at.isoformat(),
                'label': 'First suspicious activity'
            })
        
        events.append({
            'event': 'detected',
            'timestamp': self.detected_at.isoformat(),
            'label': 'Breach detected'
        })
        
        if self.notification_sent_at:
            events.append({
                'event': 'notified',
                'timestamp': self.notification_sent_at.isoformat(),
                'label': 'User notified'
            })
        
        if self.user_acknowledged_at:
            events.append({
                'event': 'acknowledged',
                'timestamp': self.user_acknowledged_at.isoformat(),
                'label': 'User acknowledged'
            })
        
        if self.public_disclosure_at:
            events.append({
                'event': 'public_disclosure',
                'timestamp': self.public_disclosure_at.isoformat(),
                'label': 'Public disclosure'
            })
        
        if self.resolved_at:
            events.append({
                'event': 'resolved',
                'timestamp': self.resolved_at.isoformat(),
                'label': 'Resolved'
            })
        
        return sorted(events, key=lambda x: x['timestamp'])


class CredentialRotationLog(models.Model):
    """
    Audit log for credential rotations triggered by breach detection.
    Tracks both automatic and manual rotations.
    """
    
    TRIGGER_CHOICES = [
        ('auto_breach', 'Automatic - Breach Detected'),
        ('manual_user', 'Manual - User Initiated'),
        ('manual_admin', 'Manual - Admin Initiated'),
        ('scheduled', 'Scheduled Rotation'),
    ]
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='credential_rotations'
    )
    
    # Linked entities
    honeypot = models.ForeignKey(
        HoneypotEmail,
        on_delete=models.SET_NULL,
        null=True,
        related_name='rotation_logs'
    )
    breach_event = models.ForeignKey(
        HoneypotBreachEvent,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='rotation_logs'
    )
    vault_item_id = models.UUIDField(
        null=True,
        blank=True,
        help_text="Vault item whose credentials were rotated"
    )
    
    # Rotation details
    service_name = models.CharField(max_length=255)
    trigger = models.CharField(
        max_length=20,
        choices=TRIGGER_CHOICES,
        default='manual_user'
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending'
    )
    
    # Execution details
    old_credential_hash = models.CharField(
        max_length=64,
        blank=True,
        help_text="SHA-256 hash of old credential (for verification)"
    )
    new_credential_hash = models.CharField(
        max_length=64,
        blank=True,
        help_text="SHA-256 hash of new credential"
    )
    rotation_method = models.CharField(
        max_length=50,
        default='manual',
        help_text="How the rotation was performed"
    )
    
    # Results
    success = models.BooleanField(default=False)
    error_message = models.TextField(blank=True)
    
    # Confirmation
    user_confirmed = models.BooleanField(default=False)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    
    # Timestamps
    initiated_at = models.DateTimeField(default=timezone.now)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        verbose_name = "Credential Rotation Log"
        verbose_name_plural = "Credential Rotation Logs"
        ordering = ['-initiated_at']
        indexes = [
            models.Index(fields=['user', 'status']),
            models.Index(fields=['honeypot']),
            models.Index(fields=['initiated_at']),
        ]
    
    def __str__(self):
        return f"Rotation for {self.service_name} ({self.status})"
    
    def mark_completed(self, success=True, error_message=''):
        """Mark the rotation as completed."""
        self.status = 'completed' if success else 'failed'
        self.success = success
        self.error_message = error_message
        self.completed_at = timezone.now()
        self.save()
    
    @staticmethod
    def hash_credential(credential):
        """Hash a credential for audit logging (not storage)."""
        return hashlib.sha256(credential.encode()).hexdigest()

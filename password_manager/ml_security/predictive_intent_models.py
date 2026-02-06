"""
Predictive Intent Models
=========================

Models for AI-powered password prediction based on usage patterns.

Features:
- Pattern learning from browsing/access history
- Context-aware predictions
- Preloaded credential caching
- Feedback loop for model improvement

@author Password Manager Team
@created 2026-02-06
"""

from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from vault.models import EncryptedVaultItem
import uuid


# =============================================================================
# Usage Pattern Tracking
# =============================================================================

class PasswordUsagePattern(models.Model):
    """
    Tracks when and where passwords are used to learn access patterns.
    
    Captures temporal, contextual, and sequential features for ML training.
    """
    
    TIME_OF_DAY_CHOICES = [
        ('early_morning', 'Early Morning (5-8am)'),
        ('morning', 'Morning (8-12pm)'),
        ('afternoon', 'Afternoon (12-5pm)'),
        ('evening', 'Evening (5-9pm)'),
        ('night', 'Night (9pm-12am)'),
        ('late_night', 'Late Night (12-5am)'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='usage_patterns'
    )
    vault_item = models.ForeignKey(
        EncryptedVaultItem,
        on_delete=models.CASCADE,
        related_name='usage_patterns'
    )
    
    # Temporal features
    access_time = models.DateTimeField(default=timezone.now)
    day_of_week = models.SmallIntegerField(
        help_text="0=Monday, 6=Sunday"
    )
    time_of_day = models.CharField(
        max_length=20,
        choices=TIME_OF_DAY_CHOICES
    )
    hour_of_day = models.SmallIntegerField()
    
    # Domain/context
    domain = models.CharField(max_length=255)
    domain_category = models.CharField(
        max_length=50,
        blank=True,
        help_text="work/personal/social/financial/shopping/entertainment"
    )
    
    # Session context (encrypted/hashed for privacy)
    device_fingerprint_hash = models.CharField(max_length=64, blank=True)
    location_hash = models.CharField(
        max_length=64,
        blank=True,
        help_text="Hashed location for pattern matching"
    )
    referrer_domain_hash = models.CharField(max_length=64, blank=True)
    
    # Sequence tracking
    previous_vault_item = models.ForeignKey(
        EncryptedVaultItem,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='followed_by_patterns'
    )
    session_sequence_position = models.SmallIntegerField(
        default=1,
        help_text="Position in session access sequence"
    )
    
    # Access metadata
    access_method = models.CharField(
        max_length=30,
        choices=[
            ('search', 'Search'),
            ('browse', 'Browse List'),
            ('autofill', 'Browser Autofill'),
            ('prediction', 'From Prediction'),
            ('quick_access', 'Quick Access/Favorites'),
        ],
        default='browse'
    )
    time_to_access_ms = models.IntegerField(
        null=True,
        blank=True,
        help_text="Time from page load to credential use"
    )
    
    class Meta:
        ordering = ['-access_time']
        indexes = [
            models.Index(fields=['user', 'access_time']),
            models.Index(fields=['user', 'vault_item']),
            models.Index(fields=['user', 'domain']),
            models.Index(fields=['user', 'day_of_week', 'hour_of_day']),
            models.Index(fields=['domain', 'vault_item']),
        ]
    
    def __str__(self):
        return f"{self.user.username} - {self.domain} @ {self.access_time}"


# =============================================================================
# Intent Predictions
# =============================================================================

class IntentPrediction(models.Model):
    """
    AI-generated predictions for password needs.
    
    Stores predictions with confidence scores and tracks accuracy for
    continuous model improvement.
    """
    
    REASON_CHOICES = [
        ('time_pattern', 'Time-Based Pattern'),
        ('sequence_pattern', 'Sequence Pattern'),
        ('domain_correlation', 'Domain Correlation'),
        ('context_match', 'Context Match'),
        ('frequency', 'High Frequency'),
        ('recent', 'Recently Used'),
        ('combined', 'Multiple Signals'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='intent_predictions'
    )
    predicted_vault_item = models.ForeignKey(
        EncryptedVaultItem,
        on_delete=models.CASCADE,
        related_name='predictions'
    )
    
    # Prediction details
    confidence_score = models.FloatField(
        help_text="Prediction confidence 0.0-1.0"
    )
    prediction_reason = models.CharField(
        max_length=30,
        choices=REASON_CHOICES
    )
    reason_details = models.JSONField(
        default=dict,
        blank=True,
        help_text="Detailed breakdown of prediction factors"
    )
    
    # Ranking
    rank = models.SmallIntegerField(
        default=1,
        help_text="Rank among predictions for this context"
    )
    
    # Context that triggered prediction
    trigger_domain = models.CharField(max_length=255, blank=True)
    trigger_context = models.JSONField(
        default=dict,
        blank=True,
        help_text="Context snapshot when prediction was made"
    )
    
    # Timing
    predicted_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    
    # Outcome tracking
    was_used = models.BooleanField(
        null=True,
        blank=True,
        help_text="True if user used this prediction"
    )
    used_at = models.DateTimeField(null=True, blank=True)
    was_dismissed = models.BooleanField(default=False)
    alternative_item_used = models.ForeignKey(
        EncryptedVaultItem,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='used_instead_of_predictions'
    )
    
    # Model version for A/B testing
    model_version = models.CharField(max_length=20, default='1.0')
    
    class Meta:
        ordering = ['-predicted_at', 'rank']
        indexes = [
            models.Index(fields=['user', 'expires_at']),
            models.Index(fields=['user', 'predicted_at']),
            models.Index(fields=['user', 'trigger_domain']),
            models.Index(fields=['was_used']),
        ]
    
    def __str__(self):
        return f"Prediction for {self.user.username}: {self.confidence_score:.2f}"
    
    @property
    def is_expired(self):
        return timezone.now() > self.expires_at


# =============================================================================
# Real-Time Context
# =============================================================================

class ContextSignal(models.Model):
    """
    Real-time browsing context signals for prediction triggering.
    
    Short-lived records that capture current browsing state.
    """
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='context_signals'
    )
    
    # Current page context
    current_domain = models.CharField(max_length=255)
    current_url_hash = models.CharField(
        max_length=64,
        help_text="SHA-256 hash of full URL for privacy"
    )
    page_title_keywords = models.JSONField(
        default=list,
        blank=True,
        help_text="Extracted keywords from page title"
    )
    
    # Form detection
    active_form_detected = models.BooleanField(default=False)
    login_form_probability = models.FloatField(
        default=0.0,
        help_text="ML confidence that a login form is present"
    )
    form_fields_detected = models.JSONField(
        default=list,
        blank=True,
        help_text="Types of form fields detected"
    )
    
    # Tab/navigation context
    tab_count = models.SmallIntegerField(default=1)
    time_on_page_seconds = models.IntegerField(default=0)
    is_new_tab = models.BooleanField(default=False)
    
    # Device context
    device_type = models.CharField(
        max_length=20,
        choices=[
            ('desktop', 'Desktop'),
            ('mobile', 'Mobile'),
            ('tablet', 'Tablet'),
        ],
        default='desktop'
    )
    
    # Timing
    timestamp = models.DateTimeField(auto_now_add=True)
    
    # Processing status
    predictions_generated = models.BooleanField(default=False)
    
    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['user', 'timestamp']),
            models.Index(fields=['user', 'current_domain']),
            models.Index(fields=['predictions_generated']),
        ]
    
    def __str__(self):
        return f"{self.user.username} @ {self.current_domain}"


# =============================================================================
# Preloaded Credentials
# =============================================================================

class PreloadedCredential(models.Model):
    """
    Cached credentials ready for instant delivery.
    
    Stores encrypted credentials that were predicted with high confidence,
    allowing sub-millisecond access when the user needs them.
    """
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='preloaded_credentials'
    )
    vault_item = models.ForeignKey(
        EncryptedVaultItem,
        on_delete=models.CASCADE,
        related_name='preloaded_instances'
    )
    prediction = models.ForeignKey(
        IntentPrediction,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='preloaded_credentials'
    )
    
    # Encrypted credential (session-key encrypted, not master password)
    encrypted_credential = models.BinaryField(
        help_text="Session-key encrypted credential for fast access"
    )
    encryption_iv = models.BinaryField()
    session_key_id = models.CharField(
        max_length=64,
        help_text="Reference to session encryption key"
    )
    
    # Preload metadata
    preload_reason = models.CharField(max_length=50)
    confidence_at_preload = models.FloatField()
    
    # Timing
    preloaded_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    
    # Usage tracking
    was_used = models.BooleanField(default=False)
    used_at = models.DateTimeField(null=True, blank=True)
    
    # Security
    requires_biometric = models.BooleanField(
        default=False,
        help_text="Require biometric confirmation before delivery"
    )
    delivery_count = models.SmallIntegerField(
        default=0,
        help_text="Number of times delivered (for rate limiting)"
    )
    
    class Meta:
        ordering = ['-preloaded_at']
        indexes = [
            models.Index(fields=['user', 'expires_at']),
            models.Index(fields=['user', 'vault_item']),
            models.Index(fields=['session_key_id']),
        ]
    
    def __str__(self):
        return f"Preloaded: {self.vault_item} for {self.user.username}"
    
    @property
    def is_expired(self):
        return timezone.now() > self.expires_at


# =============================================================================
# Prediction Feedback
# =============================================================================

class PredictionFeedback(models.Model):
    """
    User feedback for model training and improvement.
    
    Captures both explicit feedback and implicit signals about
    prediction quality.
    """
    
    FEEDBACK_TYPE_CHOICES = [
        ('used', 'Prediction Used'),
        ('dismissed', 'Prediction Dismissed'),
        ('wrong', 'Wrong Prediction'),
        ('helpful', 'Marked Helpful'),
        ('not_helpful', 'Marked Not Helpful'),
        ('timeout', 'Prediction Expired'),
        ('alternative', 'Used Alternative'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    prediction = models.OneToOneField(
        IntentPrediction,
        on_delete=models.CASCADE,
        related_name='feedback'
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='prediction_feedback'
    )
    
    # Outcome
    feedback_type = models.CharField(
        max_length=20,
        choices=FEEDBACK_TYPE_CHOICES
    )
    was_correct = models.BooleanField(
        null=True,
        blank=True,
        help_text="Whether prediction matched user intent"
    )
    
    # Timing metrics
    time_to_use_ms = models.IntegerField(
        null=True,
        blank=True,
        help_text="Time from prediction shown to use"
    )
    time_to_dismiss_ms = models.IntegerField(
        null=True,
        blank=True,
        help_text="Time from prediction shown to dismiss"
    )
    
    # Alternative used
    alternative_item = models.ForeignKey(
        EncryptedVaultItem,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='+'
    )
    
    # Context at feedback time
    context_snapshot = models.JSONField(
        default=dict,
        blank=True
    )
    
    # Explicit user feedback
    explicit_rating = models.SmallIntegerField(
        null=True,
        blank=True,
        help_text="User rating 1-5 if explicitly provided"
    )
    user_comment = models.TextField(blank=True)
    
    # Timing
    created_at = models.DateTimeField(auto_now_add=True)
    
    # Training status
    used_for_training = models.BooleanField(default=False)
    training_batch_id = models.CharField(max_length=64, blank=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'created_at']),
            models.Index(fields=['feedback_type']),
            models.Index(fields=['was_correct']),
            models.Index(fields=['used_for_training']),
        ]
    
    def __str__(self):
        return f"Feedback: {self.feedback_type} for {self.prediction}"


# =============================================================================
# User Settings
# =============================================================================

class PredictiveIntentSettings(models.Model):
    """
    User preferences for predictive intent features.
    """
    
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='predictive_intent_settings'
    )
    
    # Feature toggles
    is_enabled = models.BooleanField(default=True)
    learn_from_vault_access = models.BooleanField(default=True)
    learn_from_autofill = models.BooleanField(default=True)
    show_predictions = models.BooleanField(default=True)
    
    # Thresholds
    min_confidence_threshold = models.FloatField(
        default=0.7,
        help_text="Minimum confidence to show prediction"
    )
    preload_confidence_threshold = models.FloatField(
        default=0.85,
        help_text="Minimum confidence to preload credential"
    )
    
    # Limits
    max_predictions_shown = models.SmallIntegerField(default=5)
    max_preloaded = models.SmallIntegerField(default=3)
    
    # Privacy
    excluded_domains = models.JSONField(
        default=list,
        blank=True,
        help_text="Domains to never learn from or predict for"
    )
    pattern_retention_days = models.SmallIntegerField(
        default=90,
        help_text="Days to retain usage patterns"
    )
    
    # Notification preferences
    notify_high_confidence = models.BooleanField(
        default=False,
        help_text="Push notification for high-confidence predictions"
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Predictive Intent Settings"
        verbose_name_plural = "Predictive Intent Settings"
    
    def __str__(self):
        return f"Predictive Settings for {self.user.username}"

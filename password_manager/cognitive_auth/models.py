"""
Cognitive Password Testing with Implicit Memory - Django Models
================================================================

Core models for cognitive verification that tests whether users
genuinely created their passwords using implicit memory traces.

@author Password Manager Team
@created 2026-02-07
"""

from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator
import uuid
import hashlib

User = get_user_model()


class CognitiveProfile(models.Model):
    """
    User's cognitive baseline for reaction times and recognition patterns.
    
    This profile stores the user's typical response characteristics when
    interacting with their own passwords. Attackers cannot replicate these
    implicit memory traces even with plaintext access.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='cognitive_profile'
    )
    
    # Baseline reaction times (milliseconds)
    baseline_reaction_time_mean = models.FloatField(
        default=0.0,
        help_text="Mean reaction time in ms for correct recognitions"
    )
    baseline_reaction_time_std = models.FloatField(
        default=0.0,
        help_text="Standard deviation of reaction times"
    )
    
    # Per-challenge-type baselines (JSON)
    scrambled_baseline = models.JSONField(
        default=dict,
        help_text="Baseline metrics for scrambled recognition tests"
    )
    stroop_baseline = models.JSONField(
        default=dict,
        help_text="Baseline metrics for Stroop-effect tests"
    )
    priming_baseline = models.JSONField(
        default=dict,
        help_text="Baseline metrics for priming tests"
    )
    partial_baseline = models.JSONField(
        default=dict,
        help_text="Baseline metrics for partial reveal tests"
    )
    
    # Calibration status
    calibration_challenges_completed = models.IntegerField(
        default=0,
        help_text="Number of calibration challenges completed"
    )
    is_calibrated = models.BooleanField(
        default=False,
        help_text="Whether the profile has sufficient calibration data"
    )
    last_calibration_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When calibration was last updated"
    )
    
    # Profile quality metrics
    profile_confidence = models.FloatField(
        default=0.0,
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        help_text="Confidence level in profile accuracy (0-1)"
    )
    
    # Cognitive fingerprint (encrypted hash of behavioral patterns)
    cognitive_fingerprint = models.CharField(
        max_length=256,
        blank=True,
        help_text="Encrypted hash of cognitive patterns"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Cognitive Profile"
        verbose_name_plural = "Cognitive Profiles"
    
    def __str__(self):
        status = "Calibrated" if self.is_calibrated else "Pending Calibration"
        return f"CognitiveProfile({self.user.username}, {status})"
    
    def update_baseline(self, challenge_type, metrics):
        """Update baseline metrics for a specific challenge type."""
        baselines = {
            'scrambled': 'scrambled_baseline',
            'stroop': 'stroop_baseline',
            'priming': 'priming_baseline',
            'partial': 'partial_baseline',
        }
        
        if challenge_type in baselines:
            setattr(self, baselines[challenge_type], metrics)
            self.last_calibration_at = timezone.now()
            self.save()


class CognitiveSession(models.Model):
    """
    A verification session consisting of multiple cognitive challenges.
    
    Sessions are used to verify password ownership by aggregating
    responses to multiple challenge types.
    """
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('passed', 'Passed'),
        ('failed', 'Failed'),
        ('expired', 'Expired'),
    ]
    
    VERIFICATION_CONTEXT_CHOICES = [
        ('login', 'Login Verification'),
        ('high_security', 'High Security Action'),
        ('recovery', 'Account Recovery'),
        ('periodic', 'Periodic Re-verification'),
        ('suspicious', 'Suspicious Activity'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='cognitive_sessions'
    )
    
    # Session context
    vault_item_id = models.UUIDField(
        null=True,
        blank=True,
        help_text="Optional: specific vault item being verified"
    )
    verification_context = models.CharField(
        max_length=32,
        choices=VERIFICATION_CONTEXT_CHOICES,
        default='login'
    )
    
    # Session status
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending'
    )
    
    # Challenge configuration
    total_challenges = models.IntegerField(
        default=5,
        help_text="Total number of challenges in this session"
    )
    challenges_completed = models.IntegerField(default=0)
    challenges_passed = models.IntegerField(default=0)
    
    # Timing
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(
        help_text="Session expiration time"
    )
    
    # Results
    overall_score = models.FloatField(
        default=0.0,
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        help_text="Overall verification score (0-1)"
    )
    confidence = models.FloatField(
        default=0.0,
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        help_text="Confidence in the verification result"
    )
    
    # Creator probability from ML model
    creator_probability = models.FloatField(
        default=0.0,
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        help_text="Probability that the responder is the password creator"
    )
    
    # Device/environment info
    device_fingerprint = models.CharField(max_length=256, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Cognitive Session"
        verbose_name_plural = "Cognitive Sessions"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'status']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        return f"CognitiveSession({self.id}, {self.status})"
    
    def is_expired(self):
        return timezone.now() > self.expires_at
    
    def pass_rate(self):
        if self.challenges_completed == 0:
            return 0.0
        return self.challenges_passed / self.challenges_completed


class CognitiveChallenge(models.Model):
    """
    Individual cognitive test within a verification session.
    
    Challenge types include:
    - scrambled: Recognize jumbled password fragments
    - stroop: Handle color-word interference with password elements
    - priming: Respond to primed password-related stimuli
    - partial: Complete partially revealed password
    """
    
    CHALLENGE_TYPE_CHOICES = [
        ('scrambled', 'Scrambled Recognition'),
        ('stroop', 'Stroop Effect Test'),
        ('priming', 'Priming Test'),
        ('partial', 'Partial Reveal'),
    ]
    
    DIFFICULTY_CHOICES = [
        ('easy', 'Easy'),
        ('medium', 'Medium'),
        ('hard', 'Hard'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session = models.ForeignKey(
        CognitiveSession,
        on_delete=models.CASCADE,
        related_name='challenges'
    )
    
    # Challenge configuration
    challenge_type = models.CharField(
        max_length=20,
        choices=CHALLENGE_TYPE_CHOICES
    )
    difficulty = models.CharField(
        max_length=10,
        choices=DIFFICULTY_CHOICES,
        default='medium'
    )
    sequence_number = models.IntegerField(
        help_text="Order of this challenge in the session"
    )
    
    # Challenge data (encrypted/hashed)
    challenge_data = models.JSONField(
        default=dict,
        help_text="Encrypted challenge stimulus data"
    )
    correct_answer_hash = models.CharField(
        max_length=256,
        help_text="Hash of the correct answer for verification"
    )
    
    # Timing constraints
    time_limit_ms = models.IntegerField(
        default=5000,
        help_text="Maximum time allowed in milliseconds"
    )
    display_duration_ms = models.IntegerField(
        default=0,
        help_text="How long stimulus is displayed (0 = until response)"
    )
    
    # Status
    is_presented = models.BooleanField(default=False)
    presented_at = models.DateTimeField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Cognitive Challenge"
        verbose_name_plural = "Cognitive Challenges"
        ordering = ['session', 'sequence_number']
        unique_together = ['session', 'sequence_number']
    
    def __str__(self):
        return f"Challenge({self.challenge_type}, #{self.sequence_number})"


class ChallengeResponse(models.Model):
    """
    User's response to a cognitive challenge with precise timing data.
    
    Captures reaction time, accuracy, and behavioral metrics that
    distinguish genuine password creators from attackers.
    """
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    challenge = models.OneToOneField(
        CognitiveChallenge,
        on_delete=models.CASCADE,
        related_name='response'
    )
    
    # Response data
    response_hash = models.CharField(
        max_length=256,
        help_text="Hash of the user's response"
    )
    is_correct = models.BooleanField(
        help_text="Whether the response was correct"
    )
    
    # Timing metrics (critical for implicit memory detection)
    reaction_time_ms = models.IntegerField(
        help_text="Time from stimulus to response in milliseconds"
    )
    first_keystroke_ms = models.IntegerField(
        null=True,
        blank=True,
        help_text="Time to first keystroke (for typing responses)"
    )
    total_input_duration_ms = models.IntegerField(
        null=True,
        blank=True,
        help_text="Total time spent inputting response"
    )
    
    # Behavioral metrics
    hesitation_count = models.IntegerField(
        default=0,
        help_text="Number of pauses during input"
    )
    correction_count = models.IntegerField(
        default=0,
        help_text="Number of corrections/backspaces"
    )
    confidence_score = models.FloatField(
        default=0.0,
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        help_text="Calculated confidence based on timing patterns"
    )
    
    # Eye tracking data (if available)
    eye_tracking_data = models.JSONField(
        default=dict,
        blank=True,
        help_text="Optional eye tracking metrics"
    )
    
    # Device timing precision
    client_timestamp = models.BigIntegerField(
        help_text="Client-side timestamp in milliseconds"
    )
    server_received_at = models.DateTimeField(auto_now_add=True)
    
    # Analysis results
    z_score = models.FloatField(
        default=0.0,
        help_text="Z-score compared to user's baseline"
    )
    is_anomalous = models.BooleanField(
        default=False,
        help_text="Whether this response is statistically anomalous"
    )
    
    class Meta:
        verbose_name = "Challenge Response"
        verbose_name_plural = "Challenge Responses"
    
    def __str__(self):
        result = "Correct" if self.is_correct else "Incorrect"
        return f"Response({result}, {self.reaction_time_ms}ms)"


class PasswordCreationSignature(models.Model):
    """
    Cryptographic binding of cognitive data to a specific password.
    
    Created when a user sets a new password, this stores the cognitive
    signature that can be used to verify the creator's implicit memory
    of the password creation process.
    """
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='cognitive_signatures'
    )
    
    # Password reference (hashed, not plaintext)
    password_hash = models.CharField(
        max_length=256,
        help_text="Hash of the password this signature is for"
    )
    vault_item_id = models.UUIDField(
        null=True,
        blank=True,
        help_text="Associated vault item if applicable"
    )
    
    # Cognitive signature components
    creation_reaction_times = models.JSONField(
        default=list,
        help_text="Reaction times during password creation"
    )
    creation_typing_pattern = models.JSONField(
        default=dict,
        help_text="Typing rhythm during password creation"
    )
    element_associations = models.JSONField(
        default=dict,
        help_text="Semantic associations with password elements"
    )
    
    # Encrypted signature
    signature_hash = models.CharField(
        max_length=512,
        help_text="Cryptographic hash of the full cognitive signature"
    )
    signature_salt = models.CharField(
        max_length=64,
        help_text="Salt used in signature generation"
    )
    
    # Validity
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Optional expiration for the signature"
    )
    
    class Meta:
        verbose_name = "Password Creation Signature"
        verbose_name_plural = "Password Creation Signatures"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'is_active']),
            models.Index(fields=['password_hash']),
        ]
    
    def __str__(self):
        return f"Signature({self.user.username}, {self.created_at.date()})"
    
    def generate_signature(self, cognitive_data):
        """Generate cryptographic signature from cognitive data."""
        import secrets
        
        self.signature_salt = secrets.token_hex(32)
        data_str = str(cognitive_data) + self.signature_salt
        self.signature_hash = hashlib.sha512(data_str.encode()).hexdigest()
        self.save()


class CognitiveSettings(models.Model):
    """
    User preferences for cognitive verification challenges.
    """
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='cognitive_settings'
    )
    
    # Enabled challenge types
    enable_scrambled = models.BooleanField(
        default=True,
        help_text="Enable scrambled recognition challenges"
    )
    enable_stroop = models.BooleanField(
        default=True,
        help_text="Enable Stroop-effect challenges"
    )
    enable_priming = models.BooleanField(
        default=True,
        help_text="Enable priming tests"
    )
    enable_partial = models.BooleanField(
        default=True,
        help_text="Enable partial reveal challenges"
    )
    
    # Difficulty preferences
    preferred_difficulty = models.CharField(
        max_length=10,
        choices=[('easy', 'Easy'), ('medium', 'Medium'), ('hard', 'Hard')],
        default='medium'
    )
    
    # Verification frequency
    verify_on_login = models.BooleanField(
        default=False,
        help_text="Require cognitive verification on every login"
    )
    verify_on_sensitive_actions = models.BooleanField(
        default=True,
        help_text="Require verification for sensitive actions"
    )
    periodic_verification_days = models.IntegerField(
        default=30,
        help_text="Days between periodic re-verification (0 = disabled)"
    )
    
    # Accessibility settings
    extended_time_limit = models.BooleanField(
        default=False,
        help_text="Allow extra time for responses"
    )
    high_contrast_mode = models.BooleanField(
        default=False,
        help_text="Use high contrast visuals for challenges"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Cognitive Settings"
        verbose_name_plural = "Cognitive Settings"
    
    def __str__(self):
        return f"CognitiveSettings({self.user.username})"
    
    def get_enabled_challenge_types(self):
        """Return list of enabled challenge types."""
        types = []
        if self.enable_scrambled:
            types.append('scrambled')
        if self.enable_stroop:
            types.append('stroop')
        if self.enable_priming:
            types.append('priming')
        if self.enable_partial:
            types.append('partial')
        return types

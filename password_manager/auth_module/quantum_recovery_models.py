"""
Quantum-Resilient Social Mesh Recovery System Models

This module implements a next-generation passkey recovery mechanism using:
- Distributed Trust Shards
- Temporal Proof-of-Identity (TPoI)
- Zero-Knowledge Social Verification
- Post-Quantum Cryptography (CRYSTALS-Kyber)
"""

from django.db import models
from django.conf import settings
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator
import json
import uuid


class RecoveryShardType(models.TextChoices):
    """Types of distributed trust shards"""
    GUARDIAN = 'guardian', 'Guardian Shard'
    DEVICE = 'device', 'Device Shard'
    BIOMETRIC = 'biometric', 'Biometric Shard'
    BEHAVIORAL = 'behavioral', 'Behavioral Shard'
    TEMPORAL = 'temporal', 'Temporal Shard'
    HONEYPOT = 'honeypot', 'Honeypot Shard (Decoy)'


class PasskeyRecoverySetup(models.Model):
    """
    Main configuration for a user's passkey recovery system
    """
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='passkey_recovery_setup'
    )
    
    # Recovery configuration
    is_active = models.BooleanField(default=False)
    total_shards = models.IntegerField(default=5, validators=[MinValueValidator(3), MaxValueValidator(10)])
    threshold_shards = models.IntegerField(default=3, validators=[MinValueValidator(2)])
    
    # Quantum-resistant encryption metadata
    encryption_algorithm = models.CharField(max_length=50, default='CRYSTALS-Kyber-768')
    kyber_public_key = models.BinaryField(help_text="Post-quantum public key")
    kyber_private_key_encrypted = models.BinaryField(help_text="Encrypted private key")
    
    # Security settings
    max_recovery_attempts_per_month = models.IntegerField(default=3)
    recovery_cooldown_days = models.IntegerField(default=7)
    decay_window_days = models.IntegerField(default=14, help_text="Recovery request auto-expires after this period")
    canary_alert_window_hours = models.IntegerField(default=48, help_text="Time window for user to cancel recovery")
    
    # Temporal settings
    challenge_distribution_days = models.IntegerField(default=3)
    minimum_challenge_success_rate = models.FloatField(default=0.80, validators=[MinValueValidator(0.5), MaxValueValidator(1.0)])
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_rehearsal_at = models.DateTimeField(null=True, blank=True)
    
    # Travel lock feature
    travel_lock_enabled = models.BooleanField(default=False)
    travel_lock_until = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        verbose_name = "Passkey Recovery Setup"
        verbose_name_plural = "Passkey Recovery Setups"
        indexes = [
            models.Index(fields=['user', 'is_active']),
        ]
    
    def __str__(self):
        return f"Recovery Setup for {self.user.username} ({'Active' if self.is_active else 'Inactive'})"
    
    def is_travel_locked(self):
        """Check if recovery is currently locked due to travel mode"""
        if not self.travel_lock_enabled or not self.travel_lock_until:
            return False
        return timezone.now() < self.travel_lock_until


class RecoveryShard(models.Model):
    """
    Individual distributed trust shards
    Each shard is encrypted and stored in different contexts
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    recovery_setup = models.ForeignKey(
        PasskeyRecoverySetup,
        on_delete=models.CASCADE,
        related_name='shards'
    )
    
    shard_type = models.CharField(max_length=20, choices=RecoveryShardType.choices)
    shard_index = models.IntegerField()  # Position in Shamir's secret sharing
    
    # Encrypted shard data (post-quantum encrypted)
    encrypted_shard_data = models.BinaryField()
    encryption_metadata = models.JSONField(default=dict)
    
    # Contextual data based on shard type
    context_data = models.JSONField(default=dict, help_text="Type-specific context (guardian ID, device fingerprint, etc)")
    
    # Status
    is_active = models.BooleanField(default=True)
    is_honeypot = models.BooleanField(default=False, help_text="Decoy shard that triggers alerts")
    
    # Access tracking
    last_accessed_at = models.DateTimeField(null=True, blank=True)
    access_count = models.IntegerField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Recovery Shard"
        verbose_name_plural = "Recovery Shards"
        unique_together = ('recovery_setup', 'shard_index')
        indexes = [
            models.Index(fields=['recovery_setup', 'shard_type', 'is_active']),
        ]
    
    def __str__(self):
        return f"{self.shard_type} Shard #{self.shard_index} for {self.recovery_setup.user.username}"


class RecoveryGuardian(models.Model):
    """
    Trusted contacts who hold guardian shards for zero-knowledge social verification
    """
    STATUS_CHOICES = (
        ('pending', 'Invitation Pending'),
        ('active', 'Active'),
        ('declined', 'Declined'),
        ('revoked', 'Revoked'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    recovery_setup = models.ForeignKey(
        PasskeyRecoverySetup,
        on_delete=models.CASCADE,
        related_name='guardians'
    )
    
    # Guardian information (encrypted to maintain anonymity from other guardians)
    encrypted_guardian_info = models.BinaryField(help_text="Encrypted email/phone/identity")
    guardian_public_key = models.BinaryField(help_text="Guardian's public key for shard encryption")
    
    # Shard reference
    shard = models.OneToOneField(
        RecoveryShard,
        on_delete=models.CASCADE,
        related_name='guardian_holder',
        null=True,
        blank=True
    )
    
    # Status and settings
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    requires_video_verification = models.BooleanField(default=False)
    requires_in_person_verification = models.BooleanField(default=False)
    custom_security_requirements = models.JSONField(default=dict)
    
    # Invitation management
    invitation_token = models.CharField(max_length=255, unique=True)
    invitation_sent_at = models.DateTimeField(auto_now_add=True)
    invitation_expires_at = models.DateTimeField()
    accepted_at = models.DateTimeField(null=True, blank=True)
    
    # Approval tracking
    last_approval_given_at = models.DateTimeField(null=True, blank=True)
    total_approvals_given = models.IntegerField(default=0)
    
    # Anti-collusion: randomized approval window
    approval_window_start = models.DateTimeField(null=True, blank=True)
    approval_window_end = models.DateTimeField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Recovery Guardian"
        verbose_name_plural = "Recovery Guardians"
        indexes = [
            models.Index(fields=['recovery_setup', 'status']),
            models.Index(fields=['invitation_token']),
        ]
    
    def __str__(self):
        return f"Guardian {self.id} for {self.recovery_setup.user.username} ({self.status})"
    
    def is_invitation_valid(self):
        """Check if invitation is still valid"""
        return self.status == 'pending' and timezone.now() < self.invitation_expires_at


class RecoveryAttempt(models.Model):
    """
    Tracks recovery attempts with comprehensive audit trail
    """
    STATUS_CHOICES = (
        ('initiated', 'Initiated'),
        ('challenge_phase', 'Challenge Phase'),
        ('shard_collection', 'Shard Collection'),
        ('guardian_approval', 'Guardian Approval Pending'),
        ('final_verification', 'Final Verification'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled by User'),
        ('expired', 'Expired'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    recovery_setup = models.ForeignKey(
        PasskeyRecoverySetup,
        on_delete=models.CASCADE,
        related_name='recovery_attempts'
    )
    
    # Attempt metadata
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='initiated')
    initiated_from_ip = models.GenericIPAddressField()
    initiated_from_device_fingerprint = models.CharField(max_length=255, blank=True)
    initiated_from_location = models.JSONField(default=dict, blank=True)
    
    # Temporal Proof-of-Identity tracking
    challenges_sent = models.IntegerField(default=0)
    challenges_completed = models.IntegerField(default=0)
    challenges_failed = models.IntegerField(default=0)
    trust_score = models.FloatField(default=0.0, validators=[MinValueValidator(0.0), MaxValueValidator(1.0)])
    
    # Shard collection tracking
    shards_collected = models.JSONField(default=list, help_text="List of collected shard IDs")
    shards_required = models.IntegerField()
    
    # Guardian approval tracking
    guardian_approvals_received = models.JSONField(default=list, help_text="List of guardian IDs who approved")
    guardian_approvals_required = models.IntegerField()
    
    # Security events
    honeypot_triggered = models.BooleanField(default=False)
    suspicious_activity_detected = models.BooleanField(default=False)
    suspicious_activity_details = models.JSONField(default=dict, blank=True)
    
    # Canary alert
    canary_alert_sent_at = models.DateTimeField(null=True, blank=True)
    canary_alert_acknowledged = models.BooleanField(default=False)
    user_cancelled = models.BooleanField(default=False)
    
    # Timestamps
    initiated_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    completed_at = models.DateTimeField(null=True, blank=True)
    
    # Result
    recovery_successful = models.BooleanField(default=False)
    failure_reason = models.TextField(blank=True)
    
    class Meta:
        verbose_name = "Recovery Attempt"
        verbose_name_plural = "Recovery Attempts"
        ordering = ['-initiated_at']
        indexes = [
            models.Index(fields=['recovery_setup', 'status']),
            models.Index(fields=['initiated_at', 'status']),
        ]
    
    def __str__(self):
        return f"Recovery Attempt {self.id} by {self.recovery_setup.user.username} - {self.status}"
    
    def is_expired(self):
        """Check if recovery attempt has expired"""
        return timezone.now() > self.expires_at
    
    def calculate_trust_score(self):
        """
        Calculate comprehensive trust score using TrustScorerService
        Trust Score = (Challenge Success × 0.4) + (Device Recognition × 0.2) + 
                     (Behavioral Match × 0.2) + (Temporal Consistency × 0.2)
        """
        from .services.trust_scorer import trust_scorer
        
        self.trust_score = trust_scorer.calculate_comprehensive_trust_score(self)
        self.save(update_fields=['trust_score'])
        return self.trust_score


class TemporalChallenge(models.Model):
    """
    Time-distributed identity verification challenges
    """
    CHALLENGE_TYPES = (
        ('historical_activity', 'Historical Account Activity'),
        ('device_fingerprint', 'Device Fingerprint Recognition'),
        ('geolocation_pattern', 'Geolocation Pattern Matching'),
        ('usage_time_window', 'Typical Usage Time Window'),
        ('vault_content_knowledge', 'Vault Content Knowledge'),
        ('behavioral_biometric', 'Behavioral Biometric'),
    )
    
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('sent', 'Sent'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('expired', 'Expired'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    recovery_attempt = models.ForeignKey(
        RecoveryAttempt,
        on_delete=models.CASCADE,
        related_name='challenges'
    )
    
    challenge_type = models.CharField(max_length=30, choices=CHALLENGE_TYPES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    # Challenge data (encrypted)
    encrypted_challenge_data = models.BinaryField()
    encrypted_expected_response = models.BinaryField(help_text="Encrypted correct answer")
    
    # Delivery
    delivery_channel = models.CharField(max_length=50, help_text="email, sms, app_notification")
    sent_to = models.CharField(max_length=255, help_text="Encrypted recipient")
    sent_at = models.DateTimeField(null=True, blank=True)
    
    # Response
    user_response = models.TextField(blank=True)
    response_received_at = models.DateTimeField(null=True, blank=True)
    response_correct = models.BooleanField(default=False)
    response_location = models.JSONField(default=dict, blank=True)
    response_device_fingerprint = models.CharField(max_length=255, blank=True)
    
    # Timing analysis
    expected_response_time_window_start = models.DateTimeField()
    expected_response_time_window_end = models.DateTimeField()
    actual_response_time_seconds = models.IntegerField(null=True, blank=True)
    timing_pattern_matches = models.BooleanField(default=False)
    
    # Expiration
    expires_at = models.DateTimeField()
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Temporal Challenge"
        verbose_name_plural = "Temporal Challenges"
        ordering = ['created_at']
        indexes = [
            models.Index(fields=['recovery_attempt', 'status']),
            models.Index(fields=['sent_at', 'status']),
        ]
    
    def __str__(self):
        return f"{self.challenge_type} Challenge for Attempt {self.recovery_attempt.id}"
    
    def is_expired(self):
        """Check if challenge has expired"""
        return timezone.now() > self.expires_at


class GuardianApproval(models.Model):
    """
    Tracks guardian approvals for recovery attempts
    """
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('denied', 'Denied'),
        ('expired', 'Expired'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    recovery_attempt = models.ForeignKey(
        RecoveryAttempt,
        on_delete=models.CASCADE,
        related_name='guardian_approvals'
    )
    guardian = models.ForeignKey(
        RecoveryGuardian,
        on_delete=models.CASCADE,
        related_name='approvals_given'
    )
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    # Approval request
    approval_token = models.CharField(max_length=255, unique=True)
    requested_at = models.DateTimeField(auto_now_add=True)
    
    # Randomized approval window (anti-collusion)
    approval_window_start = models.DateTimeField()
    approval_window_end = models.DateTimeField()
    
    # Response
    responded_at = models.DateTimeField(null=True, blank=True)
    response_ip = models.GenericIPAddressField(null=True, blank=True)
    response_device_fingerprint = models.CharField(max_length=255, blank=True)
    
    # Additional verification (if required by guardian)
    video_verification_completed = models.BooleanField(default=False)
    video_verification_session_id = models.CharField(max_length=255, blank=True)
    in_person_verification_completed = models.BooleanField(default=False)
    
    # Shard release
    shard_released = models.BooleanField(default=False)
    shard_released_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        verbose_name = "Guardian Approval"
        verbose_name_plural = "Guardian Approvals"
        unique_together = ('recovery_attempt', 'guardian')
        indexes = [
            models.Index(fields=['recovery_attempt', 'status']),
            models.Index(fields=['approval_token']),
        ]
    
    def __str__(self):
        return f"Guardian Approval for Attempt {self.recovery_attempt.id} - {self.status}"
    
    def is_in_approval_window(self):
        """Check if current time is within the randomized approval window"""
        now = timezone.now()
        return self.approval_window_start <= now <= self.approval_window_end


class RecoveryAuditLog(models.Model):
    """
    Immutable audit trail for all recovery-related events
    Uses append-only logging with cryptographic timestamps
    """
    EVENT_TYPES = (
        ('setup_created', 'Recovery Setup Created'),
        ('setup_updated', 'Recovery Setup Updated'),
        ('guardian_invited', 'Guardian Invited'),
        ('guardian_accepted', 'Guardian Accepted Invitation'),
        ('guardian_declined', 'Guardian Declined Invitation'),
        ('guardian_revoked', 'Guardian Revoked'),
        ('shard_created', 'Shard Created'),
        ('shard_accessed', 'Shard Accessed'),
        ('honeypot_triggered', 'Honeypot Shard Triggered'),
        ('recovery_initiated', 'Recovery Initiated'),
        ('challenge_sent', 'Challenge Sent'),
        ('challenge_completed', 'Challenge Completed'),
        ('challenge_failed', 'Challenge Failed'),
        ('guardian_approval_requested', 'Guardian Approval Requested'),
        ('guardian_approved', 'Guardian Approved'),
        ('guardian_denied', 'Guardian Denied'),
        ('canary_alert_sent', 'Canary Alert Sent'),
        ('user_cancelled_recovery', 'User Cancelled Recovery'),
        ('recovery_completed', 'Recovery Completed'),
        ('recovery_failed', 'Recovery Failed'),
        ('suspicious_activity', 'Suspicious Activity Detected'),
        ('travel_lock_enabled', 'Travel Lock Enabled'),
        ('travel_lock_disabled', 'Travel Lock Disabled'),
        ('rehearsal_conducted', 'Recovery Rehearsal Conducted'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='recovery_audit_logs'
    )
    
    event_type = models.CharField(max_length=50, choices=EVENT_TYPES)
    event_data = models.JSONField(default=dict, help_text="Additional event details")
    
    # Context
    recovery_attempt_id = models.UUIDField(null=True, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    device_fingerprint = models.CharField(max_length=255, blank=True)
    geolocation = models.JSONField(default=dict, blank=True)
    
    # Cryptographic timestamp (for immutability verification)
    timestamp = models.DateTimeField(auto_now_add=True)
    cryptographic_hash = models.CharField(max_length=64, help_text="SHA-256 hash of previous log entry")
    
    class Meta:
        verbose_name = "Recovery Audit Log"
        verbose_name_plural = "Recovery Audit Logs"
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['user', 'event_type', 'timestamp']),
            models.Index(fields=['recovery_attempt_id', 'timestamp']),
        ]
    
    def __str__(self):
        return f"{self.event_type} for {self.user.username} at {self.timestamp}"


class BehavioralBiometrics(models.Model):
    """
    Stores behavioral biometric patterns for user authentication
    Used for behavioral shard verification
    """
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='behavioral_biometrics'
    )
    
    # Typing patterns
    avg_typing_speed_wpm = models.FloatField(null=True, blank=True)
    keystroke_dynamics = models.JSONField(default=dict, help_text="Timing patterns between keystrokes")
    
    # Mouse/touch patterns
    mouse_movement_patterns = models.JSONField(default=dict)
    touch_pressure_patterns = models.JSONField(default=dict, blank=True)
    
    # Usage patterns
    typical_login_times = models.JSONField(default=list, help_text="List of typical login hours")
    typical_locations = models.JSONField(default=list, help_text="List of typical geolocations")
    typical_devices = models.JSONField(default=list, help_text="List of device fingerprints")
    
    # Session patterns
    avg_session_duration_minutes = models.FloatField(null=True, blank=True)
    typical_actions_sequence = models.JSONField(default=list, help_text="Common action sequences")
    
    # Last updated
    last_updated = models.DateTimeField(auto_now=True)
    samples_collected = models.IntegerField(default=0, help_text="Number of behavioral samples")
    
    class Meta:
        verbose_name = "Behavioral Biometrics"
        verbose_name_plural = "Behavioral Biometrics"
    
    def __str__(self):
        return f"Behavioral Biometrics for {self.user.username}"


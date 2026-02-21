"""
Password Archaeology & Time Travel Models
==========================================

Models for tracking password history, security events, strength evolution,
gamification achievements, and "what if" scenario simulations.
"""

from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
import uuid

User = get_user_model()


# =============================================================================
# Password History Entry
# =============================================================================

class PasswordHistoryEntry(models.Model):
    """
    Core record of a password change event.

    Stores encrypted hashes (never plaintext) of old/new passwords,
    strength scores before/after, and optional blockchain commitment for
    tamper-proof timestamping.
    """

    TRIGGER_CHOICES = [
        ('user_initiated', 'User Initiated'),
        ('breach_response', 'Breach Response'),
        ('policy_expiration', 'Policy Expiration'),
        ('predictive_alert', 'Predictive Alert'),
        ('admin_forced', 'Admin Forced'),
        ('scheduled_rotation', 'Scheduled Rotation'),
        ('proactive', 'Proactive Change'),
        ('system_generated', 'System Generated'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='password_history_entries',
    )
    vault_item = models.ForeignKey(
        'vault.EncryptedVaultItem',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='password_history',
        help_text="The vault credential this change applies to",
    )
    credential_domain = models.CharField(
        max_length=255,
        blank=True,
        help_text="Domain or service name (e.g. google.com)",
    )
    credential_label = models.CharField(
        max_length=255,
        blank=True,
        help_text="Human-readable label for the credential",
    )

    # Encrypted password hashes (NEVER plaintext)
    old_password_hash = models.CharField(
        max_length=256,
        blank=True,
        help_text="SHA-256 hash of old password (for comparison, never plaintext)",
    )
    new_password_hash = models.CharField(
        max_length=256,
        blank=True,
        help_text="SHA-256 hash of new password (for comparison, never plaintext)",
    )

    # Strength metrics
    strength_before = models.IntegerField(
        default=0,
        help_text="Password strength score (0-100) before this change",
    )
    strength_after = models.IntegerField(
        default=0,
        help_text="Password strength score (0-100) after this change",
    )
    entropy_before = models.FloatField(
        default=0.0,
        help_text="Entropy bits before change",
    )
    entropy_after = models.FloatField(
        default=0.0,
        help_text="Entropy bits after change",
    )

    # Change metadata
    trigger = models.CharField(
        max_length=30,
        choices=TRIGGER_CHOICES,
        default='user_initiated',
    )
    change_notes = models.TextField(
        blank=True,
        help_text="Reason or notes about this change",
    )

    # Blockchain anchoring
    blockchain_commitment = models.ForeignKey(
        'blockchain.PendingCommitment',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='password_history_entries',
        help_text="Blockchain commitment for tamper-proof timestamping",
    )
    commitment_hash = models.CharField(
        max_length=64,
        blank=True,
        help_text="SHA-256 hash submitted to blockchain",
    )

    # Metadata
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    changed_at = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'password_archaeology_history'
        verbose_name = 'Password History Entry'
        verbose_name_plural = 'Password History Entries'
        ordering = ['-changed_at']
        indexes = [
            models.Index(fields=['user', '-changed_at']),
            models.Index(fields=['vault_item', '-changed_at']),
            models.Index(fields=['trigger', '-changed_at']),
            models.Index(fields=['credential_domain']),
        ]

    def __str__(self):
        domain = self.credential_domain or 'unknown'
        return f"Password change: {domain} ({self.changed_at:%Y-%m-%d})"


# =============================================================================
# Security Event
# =============================================================================

class SecurityEvent(models.Model):
    """
    Security-relevant events linked to the user's timeline.

    Includes breaches detected, suspicious logins, account locks,
    MFA changes, and other security-relevant actions.
    """

    EVENT_TYPES = [
        ('breach_detected', 'Breach Detected'),
        ('suspicious_login', 'Suspicious Login'),
        ('account_locked', 'Account Locked'),
        ('account_unlocked', 'Account Unlocked'),
        ('mfa_enabled', 'MFA Enabled'),
        ('mfa_disabled', 'MFA Disabled'),
        ('device_added', 'New Device Added'),
        ('device_removed', 'Device Removed'),
        ('impossible_travel', 'Impossible Travel Detected'),
        ('password_reuse', 'Password Reuse Detected'),
        ('weak_password', 'Weak Password Detected'),
        ('credential_exposed', 'Credential Exposed'),
        ('phishing_attempt', 'Phishing Attempt'),
        ('recovery_used', 'Recovery Used'),
        ('duress_triggered', 'Duress Code Triggered'),
    ]

    SEVERITY_CHOICES = [
        ('info', 'Info'),
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('critical', 'Critical'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='archaeology_security_events',
    )
    vault_item = models.ForeignKey(
        'vault.EncryptedVaultItem',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='archaeology_security_events',
        help_text="Optional: specific credential this event relates to",
    )
    event_type = models.CharField(max_length=30, choices=EVENT_TYPES)
    severity = models.CharField(
        max_length=10,
        choices=SEVERITY_CHOICES,
        default='medium',
    )
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Additional structured data about the event",
    )

    # Impact tracking
    risk_score_impact = models.IntegerField(
        default=0,
        help_text="How much this event affected the security score (+/-)",
    )
    resolved = models.BooleanField(default=False)
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolution_notes = models.TextField(blank=True)

    # Timestamps
    occurred_at = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'password_archaeology_security_events'
        verbose_name = 'Security Event'
        verbose_name_plural = 'Security Events'
        ordering = ['-occurred_at']
        indexes = [
            models.Index(fields=['user', '-occurred_at']),
            models.Index(fields=['event_type', '-occurred_at']),
            models.Index(fields=['severity', '-occurred_at']),
            models.Index(fields=['user', 'resolved']),
        ]

    def __str__(self):
        return f"{self.get_event_type_display()} ({self.occurred_at:%Y-%m-%d})"


# =============================================================================
# Strength Snapshot
# =============================================================================

class StrengthSnapshot(models.Model):
    """
    Periodic strength-score snapshots for each credential.

    Used to build strength evolution charts showing how password
    security has changed over time.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='strength_snapshots',
    )
    vault_item = models.ForeignKey(
        'vault.EncryptedVaultItem',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='strength_snapshots',
    )
    credential_domain = models.CharField(max_length=255, blank=True)

    # Strength metrics
    strength_score = models.IntegerField(
        default=0,
        help_text="Overall strength score (0-100)",
    )
    entropy_bits = models.FloatField(
        default=0.0,
        help_text="Estimated entropy in bits",
    )
    character_class_coverage = models.FloatField(
        default=0.0,
        help_text="Fraction of character classes used (0.0-1.0)",
    )
    length = models.IntegerField(
        default=0,
        help_text="Password length at this snapshot",
    )
    breach_exposure_count = models.IntegerField(
        default=0,
        help_text="Number of known breaches this password appeared in",
    )
    is_reused = models.BooleanField(
        default=False,
        help_text="Whether this password was reused across services",
    )

    # Snapshot timestamp
    snapshot_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = 'password_archaeology_strength_snapshots'
        verbose_name = 'Strength Snapshot'
        verbose_name_plural = 'Strength Snapshots'
        ordering = ['-snapshot_at']
        indexes = [
            models.Index(fields=['user', '-snapshot_at']),
            models.Index(fields=['vault_item', '-snapshot_at']),
            models.Index(fields=['credential_domain', '-snapshot_at']),
        ]

    def __str__(self):
        domain = self.credential_domain or 'overall'
        return f"Strength {self.strength_score}/100 for {domain} ({self.snapshot_at:%Y-%m-%d})"


# =============================================================================
# Password Timeline (Aggregate Cache)
# =============================================================================

class PasswordTimeline(models.Model):
    """
    Aggregate timeline statistics per user.

    Cached summary data for fast dashboard loading.
    Periodically recomputed by the service layer.
    """

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='password_timeline',
        primary_key=True,
    )

    # Aggregate stats
    total_credentials_tracked = models.IntegerField(default=0)
    total_password_changes = models.IntegerField(default=0)
    total_security_events = models.IntegerField(default=0)
    total_breaches_detected = models.IntegerField(default=0)

    # Current state
    current_overall_score = models.IntegerField(
        default=50,
        help_text="Current overall security score (0-100)",
    )
    weakest_credential_domain = models.CharField(
        max_length=255,
        blank=True,
        help_text="Domain of the weakest credential",
    )
    weakest_credential_score = models.IntegerField(
        default=0,
        help_text="Score of the weakest credential",
    )
    strongest_credential_domain = models.CharField(
        max_length=255,
        blank=True,
    )
    strongest_credential_score = models.IntegerField(default=0)

    # Averages
    average_password_age_days = models.FloatField(
        default=0.0,
        help_text="Average age of passwords in days",
    )
    average_strength_score = models.FloatField(default=50.0)

    # Streaks (for gamification)
    current_all_strong_streak_days = models.IntegerField(
        default=0,
        help_text="Days with all passwords above threshold",
    )
    longest_all_strong_streak_days = models.IntegerField(default=0)
    current_no_breach_streak_days = models.IntegerField(
        default=0,
        help_text="Days since last breach detection",
    )

    # Timestamps
    last_password_change_at = models.DateTimeField(null=True, blank=True)
    last_security_event_at = models.DateTimeField(null=True, blank=True)
    last_computed_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'password_archaeology_timeline'
        verbose_name = 'Password Timeline'
        verbose_name_plural = 'Password Timelines'

    def __str__(self):
        return f"Timeline for {self.user.username} (score: {self.current_overall_score})"


# =============================================================================
# Achievement Record (Gamification)
# =============================================================================

class AchievementRecord(models.Model):
    """
    Gamification achievements earned by users for good security practices.
    """

    ACHIEVEMENT_TYPES = [
        ('all_strong_7', 'All Strong (7 Days)'),
        ('all_strong_30', 'All Strong (30 Days)'),
        ('all_strong_90', 'All Strong (90 Days)'),
        ('all_strong_365', 'All Strong (365 Days)'),
        ('zero_breaches_30', 'Zero Breaches (30 Days)'),
        ('zero_breaches_90', 'Zero Breaches (90 Days)'),
        ('zero_breaches_365', 'Zero Breaches (365 Days)'),
        ('quick_responder', 'Quick Responder'),
        ('proactive_changer', 'Proactive Changer'),
        ('diversity_champion', 'Diversity Champion'),
        ('mfa_everywhere', 'MFA Everywhere'),
        ('first_password_change', 'First Password Change'),
        ('ten_passwords_changed', '10 Passwords Changed'),
        ('fifty_passwords_changed', '50 Passwords Changed'),
        ('security_score_80', 'Security Score 80+'),
        ('security_score_90', 'Security Score 90+'),
        ('security_score_100', 'Perfect Score'),
        ('time_traveler', 'Used Time Machine'),
        ('what_if_explorer', 'Used What-If Simulator'),
        ('streak_master', 'Streak Master (90 days strong)'),
    ]

    BADGE_TIERS = [
        ('bronze', 'Bronze'),
        ('silver', 'Silver'),
        ('gold', 'Gold'),
        ('platinum', 'Platinum'),
        ('diamond', 'Diamond'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='archaeology_achievements',
    )
    achievement_type = models.CharField(max_length=30, choices=ACHIEVEMENT_TYPES)
    badge_tier = models.CharField(
        max_length=10,
        choices=BADGE_TIERS,
        default='bronze',
    )
    title = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    icon_name = models.CharField(
        max_length=50,
        blank=True,
        help_text="Lucide icon name for the badge",
    )
    score_points = models.IntegerField(
        default=10,
        help_text="Points awarded for this achievement",
    )
    earned_at = models.DateTimeField(default=timezone.now)
    acknowledged = models.BooleanField(
        default=False,
        help_text="Whether the user has seen this achievement",
    )

    class Meta:
        db_table = 'password_archaeology_achievements'
        verbose_name = 'Achievement Record'
        verbose_name_plural = 'Achievement Records'
        ordering = ['-earned_at']
        unique_together = ['user', 'achievement_type']
        indexes = [
            models.Index(fields=['user', '-earned_at']),
            models.Index(fields=['achievement_type']),
        ]

    def __str__(self):
        return f"{self.title} ({self.badge_tier}) - {self.user.username}"


# =============================================================================
# What-If Scenario
# =============================================================================

class WhatIfScenario(models.Model):
    """
    Stores "what if" simulation results.

    Allows users to explore alternative timelines, e.g.
    "what if I had changed this password 30 days earlier?"
    """

    SCENARIO_TYPES = [
        ('earlier_change', 'Changed Password Earlier'),
        ('stronger_password', 'Used Stronger Password'),
        ('mfa_enabled', 'Enabled MFA Earlier'),
        ('breach_response', 'Responded to Breach Faster'),
        ('no_reuse', 'Avoided Password Reuse'),
        ('regular_rotation', 'Regular Rotation Schedule'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='what_if_scenarios',
    )
    vault_item = models.ForeignKey(
        'vault.EncryptedVaultItem',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='what_if_scenarios',
    )
    credential_domain = models.CharField(max_length=255, blank=True)

    scenario_type = models.CharField(max_length=30, choices=SCENARIO_TYPES)
    scenario_params = models.JSONField(
        default=dict,
        help_text="Parameters for the simulation (e.g. {days_earlier: 30})",
    )

    # Results
    actual_risk_score = models.IntegerField(
        default=0,
        help_text="Actual risk score at the time",
    )
    simulated_risk_score = models.IntegerField(
        default=0,
        help_text="Risk score if the scenario had played out",
    )
    risk_reduction = models.IntegerField(
        default=0,
        help_text="How much risk would have been reduced",
    )
    exposure_days_saved = models.IntegerField(
        default=0,
        help_text="Days of exposure that could have been avoided",
    )
    insight_text = models.TextField(
        blank=True,
        help_text="Human-readable insight from the simulation",
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'password_archaeology_what_if'
        verbose_name = 'What-If Scenario'
        verbose_name_plural = 'What-If Scenarios'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['scenario_type']),
        ]

    def __str__(self):
        return f"What-If: {self.get_scenario_type_display()} ({self.created_at:%Y-%m-%d})"

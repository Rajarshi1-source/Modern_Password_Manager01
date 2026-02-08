"""
Predictive Password Expiration Models
======================================

Models for AI-powered prediction of password compromise based on:
- User password creation patterns
- Threat actor TTPs (Tactics, Techniques, Procedures)
- Industry-specific threat intelligence
- Dark web monitoring for similar password structures
"""

from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
import uuid


class PasswordPatternProfile(models.Model):
    """
    Stores user's password creation patterns for vulnerability analysis.
    
    Analyzes structure, character class distribution, and creation habits
    to predict susceptibility to targeted attacks.
    """
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='password_pattern_profile'
    )
    
    # Pattern fingerprints (hashed, not actual passwords)
    structure_fingerprint = models.BinaryField(
        null=True,
        blank=True,
        help_text="Embedded representation of password structure patterns"
    )
    
    # Character class distribution preferences
    char_class_distribution = models.JSONField(
        default=dict,
        help_text="Statistical distribution of character classes used (uppercase, lowercase, digits, symbols)"
    )
    
    # Length preferences
    avg_password_length = models.FloatField(
        default=0.0,
        help_text="Average password length across all stored credentials"
    )
    length_variance = models.FloatField(
        default=0.0,
        help_text="Variance in password lengths"
    )
    min_length_used = models.IntegerField(default=0)
    max_length_used = models.IntegerField(default=0)
    
    # Pattern tendencies
    uses_common_base_words = models.BooleanField(
        default=False,
        help_text="Tends to use dictionary words as password base"
    )
    uses_keyboard_patterns = models.BooleanField(
        default=False,
        help_text="Tends to use keyboard walk patterns (qwerty, etc.)"
    )
    uses_date_patterns = models.BooleanField(
        default=False,
        help_text="Tends to include dates in passwords"
    )
    uses_leet_substitutions = models.BooleanField(
        default=False,
        help_text="Tends to use l33t speak substitutions (a→@, e→3)"
    )
    
    # Mutation patterns
    common_mutations = models.JSONField(
        default=list,
        help_text="Common character substitutions user applies"
    )
    
    # Statistics
    total_passwords_analyzed = models.IntegerField(default=0)
    weak_patterns_detected = models.IntegerField(default=0)
    
    # Risk scoring
    overall_pattern_risk_score = models.FloatField(
        default=0.0,
        help_text="Overall risk score based on pattern analysis (0-1)"
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_analysis_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'security_password_pattern_profile'
        verbose_name = 'Password Pattern Profile'
        verbose_name_plural = 'Password Pattern Profiles'
    
    def __str__(self):
        return f"Pattern Profile for {self.user.username}"


class ThreatActorTTP(models.Model):
    """
    Threat Actor Tactics, Techniques, and Procedures.
    
    Tracks known threat actor behaviors, targeted industries,
    and password patterns they exploit.
    """
    ACTOR_TYPES = [
        ('ransomware', 'Ransomware Group'),
        ('apt', 'Advanced Persistent Threat'),
        ('cybercrime', 'Cybercrime Syndicate'),
        ('hacktivist', 'Hacktivist Group'),
        ('nation_state', 'Nation State Actor'),
        ('unknown', 'Unknown'),
    ]
    
    THREAT_LEVELS = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('critical', 'Critical'),
    ]
    
    actor_id = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False
    )
    
    name = models.CharField(
        max_length=255,
        help_text="Threat actor name or identifier"
    )
    aliases = models.JSONField(
        default=list,
        help_text="Alternative names/aliases for this threat actor"
    )
    
    actor_type = models.CharField(
        max_length=50,
        choices=ACTOR_TYPES,
        default='unknown'
    )
    
    # Targeting information
    target_industries = models.JSONField(
        default=list,
        help_text="Industries this actor typically targets"
    )
    target_regions = models.JSONField(
        default=list,
        help_text="Geographic regions targeted"
    )
    target_organization_sizes = models.JSONField(
        default=list,
        help_text="Organization sizes targeted (small, medium, enterprise)"
    )
    
    # Password attack patterns
    password_patterns_exploited = models.JSONField(
        default=list,
        help_text="Known password patterns this actor exploits"
    )
    dictionary_names = models.JSONField(
        default=list,
        help_text="Known password dictionaries used by this actor"
    )
    attack_techniques = models.JSONField(
        default=list,
        help_text="Password attack techniques (brute force, credential stuffing, etc.)"
    )
    
    # Current threat assessment
    threat_level = models.CharField(
        max_length=20,
        choices=THREAT_LEVELS,
        default='medium'
    )
    is_currently_active = models.BooleanField(
        default=True,
        help_text="Whether this actor is currently active"
    )
    
    # Temporal data
    first_observed = models.DateField(null=True, blank=True)
    last_active = models.DateTimeField(null=True, blank=True)
    
    # Metadata
    source = models.CharField(
        max_length=255,
        blank=True,
        help_text="Intelligence source (MISP, AlienVault, internal)"
    )
    external_references = models.JSONField(
        default=list,
        help_text="External reference URLs and identifiers"
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'security_threat_actor_ttp'
        verbose_name = 'Threat Actor TTP'
        verbose_name_plural = 'Threat Actor TTPs'
        ordering = ['-threat_level', '-last_active']
        indexes = [
            models.Index(fields=['is_currently_active', 'threat_level']),
            models.Index(fields=['actor_type', 'is_currently_active']),
            models.Index(fields=['last_active']),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.actor_type})"


class IndustryThreatLevel(models.Model):
    """
    Industry-specific threat assessments.
    
    Tracks current threat levels for different industries
    to correlate with user's organizational context.
    """
    THREAT_LEVELS = [
        ('low', 'Low'),
        ('elevated', 'Elevated'),
        ('high', 'High'),
        ('severe', 'Severe'),
        ('critical', 'Critical'),
    ]
    
    industry_code = models.CharField(
        max_length=50,
        unique=True,
        help_text="Industry identifier (e.g., healthcare, finance, tech)"
    )
    industry_name = models.CharField(max_length=255)
    
    # Current threat assessment
    current_threat_level = models.CharField(
        max_length=20,
        choices=THREAT_LEVELS,
        default='low'
    )
    threat_score = models.FloatField(
        default=0.0,
        help_text="Numeric threat score (0-1)"
    )
    
    # Active threats
    active_threat_actors = models.ManyToManyField(
        ThreatActorTTP,
        blank=True,
        related_name='targeted_industries_m2m'
    )
    active_campaigns_count = models.IntegerField(default=0)
    
    # Recent activity
    recent_breaches_count = models.IntegerField(
        default=0,
        help_text="Number of breaches in last 30 days"
    )
    recent_credential_leaks = models.IntegerField(
        default=0,
        help_text="Number of credential leaks in last 30 days"
    )
    
    # Trend data
    threat_trend = models.CharField(
        max_length=20,
        choices=[
            ('decreasing', 'Decreasing'),
            ('stable', 'Stable'),
            ('increasing', 'Increasing'),
            ('rapidly_increasing', 'Rapidly Increasing'),
        ],
        default='stable'
    )
    
    # Advisory
    advisory_message = models.TextField(
        blank=True,
        help_text="Current threat advisory for this industry"
    )
    recommended_actions = models.JSONField(
        default=list,
        help_text="Recommended security actions"
    )
    
    # Timestamps
    last_assessment_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'security_industry_threat_level'
        verbose_name = 'Industry Threat Level'
        verbose_name_plural = 'Industry Threat Levels'
        ordering = ['-threat_score']
    
    def __str__(self):
        return f"{self.industry_name}: {self.current_threat_level}"


class PredictiveExpirationRule(models.Model):
    """
    AI-generated expiration rules for individual credentials.
    
    Stores predictions about when a specific password might
    be compromised based on threat intelligence analysis.
    """
    RISK_LEVELS = [
        ('minimal', 'Minimal'),
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('critical', 'Critical'),
    ]
    
    RECOMMENDED_ACTIONS = [
        ('no_action', 'No Action Required'),
        ('monitor', 'Monitor Closely'),
        ('plan_rotation', 'Plan Rotation'),
        ('rotate_soon', 'Rotate Within 7 Days'),
        ('rotate_immediately', 'Rotate Immediately'),
    ]
    
    rule_id = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False
    )
    
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='expiration_rules'
    )
    
    # Credential reference (vault entry ID)
    credential_id = models.UUIDField(
        db_index=True,
        help_text="UUID of the credential in vault"
    )
    credential_domain = models.CharField(
        max_length=255,
        blank=True,
        help_text="Domain/service for this credential"
    )
    
    # Risk assessment
    risk_level = models.CharField(
        max_length=20,
        choices=RISK_LEVELS,
        default='low'
    )
    risk_score = models.FloatField(
        default=0.0,
        help_text="Calculated risk score (0-1)"
    )
    
    # Prediction
    predicted_compromise_date = models.DateField(
        null=True,
        blank=True,
        help_text="AI-predicted date when password might be compromised"
    )
    prediction_confidence = models.FloatField(
        default=0.0,
        help_text="Confidence in the prediction (0-1)"
    )
    
    # Contributing factors
    threat_factors = models.JSONField(
        default=list,
        help_text="Factors contributing to the risk assessment"
    )
    matched_threat_actors = models.ManyToManyField(
        ThreatActorTTP,
        blank=True,
        related_name='matching_credentials'
    )
    pattern_similarity_score = models.FloatField(
        default=0.0,
        help_text="Similarity to known compromised patterns"
    )
    industry_threat_correlation = models.FloatField(
        default=0.0,
        help_text="Correlation with industry-specific threats"
    )
    
    # Recommended action
    recommended_action = models.CharField(
        max_length=30,
        choices=RECOMMENDED_ACTIONS,
        default='no_action'
    )
    recommended_rotation_date = models.DateField(
        null=True,
        blank=True
    )
    
    # State
    is_active = models.BooleanField(default=True)
    user_acknowledged = models.BooleanField(
        default=False,
        help_text="User has acknowledged this risk"
    )
    user_acknowledged_at = models.DateTimeField(null=True, blank=True)
    
    # Notification tracking
    last_notification_sent = models.DateTimeField(null=True, blank=True)
    notification_count = models.IntegerField(default=0)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_evaluated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'security_predictive_expiration_rule'
        verbose_name = 'Predictive Expiration Rule'
        verbose_name_plural = 'Predictive Expiration Rules'
        ordering = ['-risk_score', '-updated_at']
        indexes = [
            models.Index(fields=['user', 'is_active', 'risk_level']),
            models.Index(fields=['credential_id']),
            models.Index(fields=['risk_score', 'is_active']),
            models.Index(fields=['recommended_action', 'user_acknowledged']),
        ]
        unique_together = ['user', 'credential_id']
    
    def __str__(self):
        return f"Rule {self.rule_id} - {self.credential_domain}: {self.risk_level}"


class PasswordRotationEvent(models.Model):
    """
    Tracks password rotation events, both proactive and forced.
    
    Records when passwords were rotated, why, and the outcome.
    """
    ROTATION_TYPES = [
        ('user_initiated', 'User Initiated'),
        ('scheduled', 'Scheduled Rotation'),
        ('proactive', 'Proactive (Threat Based)'),
        ('forced', 'Forced by System'),
        ('breach_response', 'Breach Response'),
    ]
    
    OUTCOMES = [
        ('completed', 'Completed'),
        ('pending', 'Pending'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
        ('skipped', 'Skipped by User'),
    ]
    
    event_id = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False
    )
    
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='rotation_events'
    )
    
    # Credential reference
    credential_id = models.UUIDField(
        db_index=True,
        help_text="UUID of the rotated credential"
    )
    credential_domain = models.CharField(max_length=255, blank=True)
    
    # Rotation details
    rotation_type = models.CharField(
        max_length=30,
        choices=ROTATION_TYPES
    )
    outcome = models.CharField(
        max_length=20,
        choices=OUTCOMES,
        default='pending'
    )
    
    # Trigger information
    triggered_by_rule = models.ForeignKey(
        PredictiveExpirationRule,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='triggered_rotations'
    )
    trigger_reason = models.TextField(
        blank=True,
        help_text="Reason for the rotation"
    )
    threat_factors_at_rotation = models.JSONField(
        default=list,
        help_text="Threat factors that triggered the rotation"
    )
    risk_score_at_rotation = models.FloatField(
        default=0.0,
        help_text="Risk score when rotation was triggered"
    )
    
    # Password quality change
    old_password_strength = models.FloatField(
        null=True,
        blank=True,
        help_text="Strength score before rotation"
    )
    new_password_strength = models.FloatField(
        null=True,
        blank=True,
        help_text="Strength score after rotation"
    )
    
    # Timing
    initiated_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    # Metadata
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    
    class Meta:
        db_table = 'security_password_rotation_event'
        verbose_name = 'Password Rotation Event'
        verbose_name_plural = 'Password Rotation Events'
        ordering = ['-initiated_at']
        indexes = [
            models.Index(fields=['user', 'initiated_at']),
            models.Index(fields=['credential_id', 'initiated_at']),
            models.Index(fields=['rotation_type', 'outcome']),
        ]
    
    def __str__(self):
        return f"Rotation {self.event_id} - {self.rotation_type}: {self.outcome}"


class ThreatIntelFeed(models.Model):
    """
    External threat intelligence feed sources.
    
    Configures and tracks external threat intel integrations.
    """
    FEED_TYPES = [
        ('misp', 'MISP Platform'),
        ('alienvault_otx', 'AlienVault OTX'),
        ('internal_darkweb', 'Internal Dark Web Monitor'),
        ('hibp', 'Have I Been Pwned'),
        ('custom_api', 'Custom API'),
        ('rss', 'RSS/Atom Feed'),
    ]
    
    feed_id = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False
    )
    
    name = models.CharField(max_length=255)
    feed_type = models.CharField(
        max_length=30,
        choices=FEED_TYPES
    )
    
    # Connection details
    api_endpoint = models.URLField(blank=True)
    api_key_encrypted = models.BinaryField(
        null=True,
        blank=True,
        help_text="Encrypted API key"
    )
    additional_config = models.JSONField(
        default=dict,
        help_text="Additional configuration parameters"
    )
    
    # Reliability
    reliability_score = models.FloatField(
        default=0.8,
        help_text="Reliability of this feed (0-1)"
    )
    
    # State
    is_active = models.BooleanField(default=True)
    is_healthy = models.BooleanField(default=True)
    health_check_message = models.TextField(blank=True)
    
    # Sync details
    sync_frequency_minutes = models.IntegerField(default=60)
    last_sync_at = models.DateTimeField(null=True, blank=True)
    last_sync_success = models.BooleanField(default=True)
    last_sync_items_count = models.IntegerField(default=0)
    total_items_ingested = models.IntegerField(default=0)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'security_threat_intel_feed'
        verbose_name = 'Threat Intelligence Feed'
        verbose_name_plural = 'Threat Intelligence Feeds'
        ordering = ['-reliability_score', 'name']
    
    def __str__(self):
        return f"{self.name} ({self.feed_type})"


class PredictiveExpirationSettings(models.Model):
    """
    User-specific settings for predictive password expiration.
    """
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='predictive_expiration_settings'
    )
    
    # Feature toggles
    is_enabled = models.BooleanField(
        default=True,
        help_text="Enable predictive expiration analysis"
    )
    auto_rotation_enabled = models.BooleanField(
        default=False,
        help_text="Allow automatic password rotation for critical risks"
    )
    
    # Thresholds
    force_rotation_threshold = models.FloatField(
        default=0.8,
        help_text="Risk score threshold for forced rotation (0-1)"
    )
    warning_threshold = models.FloatField(
        default=0.5,
        help_text="Risk score threshold for warnings (0-1)"
    )
    
    # User context
    industry = models.CharField(
        max_length=50,
        blank=True,
        help_text="User's industry for threat correlation"
    )
    organization_size = models.CharField(
        max_length=20,
        blank=True,
        choices=[
            ('individual', 'Individual'),
            ('small', 'Small Business'),
            ('medium', 'Medium Business'),
            ('enterprise', 'Enterprise'),
        ]
    )
    
    # Notification preferences
    notify_on_high_risk = models.BooleanField(default=True)
    notify_on_medium_risk = models.BooleanField(default=True)
    notification_frequency_hours = models.IntegerField(
        default=24,
        help_text="Minimum hours between risk notifications"
    )
    
    # Scan preferences
    include_all_credentials = models.BooleanField(
        default=True,
        help_text="Include all credentials in analysis"
    )
    exclude_domains = models.JSONField(
        default=list,
        help_text="Domains to exclude from analysis"
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'security_predictive_expiration_settings'
        verbose_name = 'Predictive Expiration Settings'
        verbose_name_plural = 'Predictive Expiration Settings'
    
    def __str__(self):
        return f"Predictive Settings for {self.user.username}"

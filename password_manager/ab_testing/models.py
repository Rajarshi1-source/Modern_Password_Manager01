"""
A/B Testing & Feature Flags Models
===================================

Models for managing feature flags, A/B tests, and experiments.
"""

from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
import uuid


class FeatureFlag(models.Model):
    """
    Feature flags for enabling/disabling features
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Flag details
    name = models.CharField(max_length=200, unique=True, db_index=True)
    description = models.TextField(blank=True)
    
    # Flag state
    enabled = models.BooleanField(default=False)
    
    # Targeting
    enabled_for_all = models.BooleanField(default=False)
    enabled_for_users = models.ManyToManyField(User, blank=True, related_name='feature_flags')
    enabled_for_cohorts = models.JSONField(default=list, blank=True)  # List of cohort names
    
    # Percentage rollout (0-100)
    rollout_percentage = models.IntegerField(default=0, help_text='Percentage of users to enable for (0-100)')
    
    # Configuration
    config = models.JSONField(default=dict, blank=True, help_text='Additional configuration')
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='created_flags')
    
    class Meta:
        ordering = ['name']
        verbose_name = 'Feature Flag'
        verbose_name_plural = 'Feature Flags'
    
    def __str__(self):
        return f"{self.name} ({'Enabled' if self.enabled else 'Disabled'})"
    
    def is_enabled_for_user(self, user):
        """Check if flag is enabled for a specific user"""
        if not self.enabled:
            return False
        
        if self.enabled_for_all:
            return True
        
        if user and self.enabled_for_users.filter(id=user.id).exists():
            return True
        
        # Check rollout percentage
        if self.rollout_percentage > 0:
            # Use user ID to deterministically assign to rollout
            if user:
                hash_val = hash(f"{user.id}_{self.name}") % 100
                return hash_val < self.rollout_percentage
        
        return False


class Experiment(models.Model):
    """
    A/B tests and multivariate experiments
    """
    EXPERIMENT_TYPES = [
        ('ab_test', 'A/B Test'),
        ('multivariate', 'Multivariate Test'),
        ('feature_rollout', 'Feature Rollout'),
    ]
    
    EXPERIMENT_STATUS = [
        ('draft', 'Draft'),
        ('running', 'Running'),
        ('paused', 'Paused'),
        ('completed', 'Completed'),
        ('archived', 'Archived'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Experiment details
    name = models.CharField(max_length=200, unique=True, db_index=True)
    description = models.TextField(blank=True)
    type = models.CharField(max_length=50, choices=EXPERIMENT_TYPES, default='ab_test')
    status = models.CharField(max_length=50, choices=EXPERIMENT_STATUS, default='draft', db_index=True)
    
    # Configuration
    active = models.BooleanField(default=False)
    variants = models.JSONField(default=list, help_text='List of variants with weights')
    
    # Targeting
    traffic_allocation = models.FloatField(default=1.0, help_text='Percentage of traffic to include (0.0-1.0)')
    targeting = models.JSONField(default=dict, blank=True, help_text='Targeting rules')
    
    # Goals and metrics
    primary_goal = models.CharField(max_length=200, blank=True)
    secondary_goals = models.JSONField(default=list, blank=True)
    
    # Dates
    start_date = models.DateTimeField(null=True, blank=True)
    end_date = models.DateTimeField(null=True, blank=True)
    
    # Results
    results = models.JSONField(default=dict, blank=True)
    winner = models.CharField(max_length=100, blank=True)
    confidence = models.FloatField(null=True, blank=True, help_text='Statistical confidence (0.0-1.0)')
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='created_experiments')
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Experiment'
        verbose_name_plural = 'Experiments'
    
    def __str__(self):
        return f"{self.name} ({self.type}) - {self.status}"
    
    def is_running(self):
        """Check if experiment is currently running"""
        if not self.active or self.status != 'running':
            return False
        
        now = timezone.now()
        
        if self.start_date and now < self.start_date:
            return False
        
        if self.end_date and now > self.end_date:
            return False
        
        return True


class ExperimentAssignment(models.Model):
    """
    Track user assignments to experiment variants
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Experiment reference
    experiment = models.ForeignKey(Experiment, on_delete=models.CASCADE, related_name='assignments')
    
    # User
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True, related_name='experiment_assignments')
    anonymous_id = models.CharField(max_length=200, blank=True, db_index=True)
    
    # Assignment
    variant = models.CharField(max_length=100)
    
    # Metadata
    assigned_at = models.DateTimeField(default=timezone.now)
    
    class Meta:
        ordering = ['-assigned_at']
        indexes = [
            models.Index(fields=['experiment', 'user']),
            models.Index(fields=['experiment', 'anonymous_id']),
        ]
        # Ensure unique assignment per user/experiment
        constraints = [
            models.UniqueConstraint(
                fields=['experiment', 'user'],
                condition=models.Q(user__isnull=False),
                name='unique_user_experiment_assignment'
            ),
            models.UniqueConstraint(
                fields=['experiment', 'anonymous_id'],
                condition=models.Q(anonymous_id__isnull=False) & ~models.Q(anonymous_id=''),
                name='unique_anon_experiment_assignment'
            ),
        ]
        verbose_name = 'Experiment Assignment'
        verbose_name_plural = 'Experiment Assignments'
    
    def __str__(self):
        user_id = self.user.username if self.user else self.anonymous_id
        return f"{self.experiment.name} - {user_id}: {self.variant}"


class ExperimentMetric(models.Model):
    """
    Track metrics for experiments (exposures, outcomes, interactions)
    """
    METRIC_TYPES = [
        ('exposure', 'Exposure'),
        ('outcome', 'Outcome'),
        ('interaction', 'Interaction'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Experiment reference
    experiment = models.ForeignKey(Experiment, on_delete=models.CASCADE, related_name='metrics')
    variant = models.CharField(max_length=100)
    
    # User
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='experiment_metrics')
    anonymous_id = models.CharField(max_length=200, blank=True, db_index=True)
    
    # Metric details
    type = models.CharField(max_length=50, choices=METRIC_TYPES, db_index=True)
    name = models.CharField(max_length=200)
    value = models.FloatField(default=0)
    
    # Properties
    properties = models.JSONField(default=dict, blank=True)
    
    # Context
    context = models.JSONField(default=dict, blank=True)
    
    # Timestamp
    timestamp = models.DateTimeField(default=timezone.now, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['experiment', 'type', 'timestamp']),
            models.Index(fields=['experiment', 'variant', 'type', 'timestamp']),
        ]
        verbose_name = 'Experiment Metric'
        verbose_name_plural = 'Experiment Metrics'
    
    def __str__(self):
        return f"{self.experiment.name} - {self.type}: {self.name}"


class FeatureFlagUsage(models.Model):
    """
    Track feature flag usage
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Feature flag reference
    feature_flag = models.ForeignKey(FeatureFlag, on_delete=models.CASCADE, related_name='usage_logs')
    
    # User
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='feature_flag_usage')
    
    # Usage details
    was_enabled = models.BooleanField()
    
    # Context
    context = models.JSONField(default=dict, blank=True)
    
    # Timestamp
    timestamp = models.DateTimeField(default=timezone.now, db_index=True)
    
    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['feature_flag', 'timestamp']),
            models.Index(fields=['user', 'timestamp']),
        ]
        verbose_name = 'Feature Flag Usage'
        verbose_name_plural = 'Feature Flag Usage Logs'
    
    def __str__(self):
        status = 'Enabled' if self.was_enabled else 'Disabled'
        return f"{self.feature_flag.name} - {status} at {self.timestamp}"


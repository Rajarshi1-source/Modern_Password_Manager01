"""
Analytics Models
================

Models for storing analytics events, user engagement metrics,
conversions, and performance data.
"""

from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
import uuid


class AnalyticsEvent(models.Model):
    """
    Store analytics events (page views, user actions, feature usage)
    """
    EVENT_CATEGORIES = [
        ('general', 'General'),
        ('navigation', 'Navigation'),
        ('interaction', 'Interaction'),
        ('feature', 'Feature Usage'),
        ('error', 'Error'),
        ('performance', 'Performance'),
        ('funnel', 'Funnel'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Event details
    name = models.CharField(max_length=200, db_index=True)
    category = models.CharField(max_length=50, choices=EVENT_CATEGORIES, default='general', db_index=True)
    
    # User context
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='analytics_events')
    session_id = models.CharField(max_length=200, db_index=True)
    
    # Event properties (JSON)
    properties = models.JSONField(default=dict, blank=True)
    
    # Context
    url = models.TextField(blank=True)
    path = models.CharField(max_length=500, db_index=True)
    referrer = models.TextField(blank=True)
    
    # User metadata
    user_agent = models.TextField(blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    language = models.CharField(max_length=10, blank=True)
    platform = models.CharField(max_length=100, blank=True)
    
    # Timestamp
    timestamp = models.DateTimeField(default=timezone.now, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['user', 'timestamp']),
            models.Index(fields=['session_id', 'timestamp']),
            models.Index(fields=['name', 'category', 'timestamp']),
        ]
        verbose_name = 'Analytics Event'
        verbose_name_plural = 'Analytics Events'
    
    def __str__(self):
        return f"{self.name} ({self.category}) - {self.timestamp}"


class UserEngagement(models.Model):
    """
    Store user engagement metrics (session duration, time on page, scroll depth)
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # User context
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='engagements')
    session_id = models.CharField(max_length=200, db_index=True)
    
    # Engagement metric
    metric = models.CharField(max_length=100, db_index=True)
    value = models.FloatField()
    
    # Properties
    properties = models.JSONField(default=dict, blank=True)
    
    # Timestamp
    timestamp = models.DateTimeField(default=timezone.now, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['user', 'metric', 'timestamp']),
            models.Index(fields=['session_id', 'timestamp']),
        ]
        verbose_name = 'User Engagement'
        verbose_name_plural = 'User Engagements'
    
    def __str__(self):
        return f"{self.metric}: {self.value} - {self.timestamp}"


class Conversion(models.Model):
    """
    Store conversion events (goals achieved, purchases, sign-ups)
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # User context
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='conversions')
    session_id = models.CharField(max_length=200, db_index=True)
    
    # Conversion details
    name = models.CharField(max_length=200, db_index=True)
    value = models.FloatField(default=0)
    
    # Properties
    properties = models.JSONField(default=dict, blank=True)
    
    # Attribution
    first_touch = models.CharField(max_length=500, blank=True)  # First source
    last_touch = models.CharField(max_length=500, blank=True)   # Last source
    
    # Timestamp
    timestamp = models.DateTimeField(default=timezone.now, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['user', 'name', 'timestamp']),
            models.Index(fields=['name', 'timestamp']),
        ]
        verbose_name = 'Conversion'
        verbose_name_plural = 'Conversions'
    
    def __str__(self):
        return f"{self.name} (${self.value}) - {self.timestamp}"


class UserSession(models.Model):
    """
    Store user session information
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # User
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='sessions')
    session_id = models.CharField(max_length=200, unique=True, db_index=True)
    
    # Session details
    start_time = models.DateTimeField(default=timezone.now)
    end_time = models.DateTimeField(null=True, blank=True)
    duration = models.IntegerField(null=True, blank=True)  # in seconds
    
    # Session data
    page_views = models.IntegerField(default=0)
    event_count = models.IntegerField(default=0)
    feature_usage = models.JSONField(default=dict, blank=True)
    user_journey = models.JSONField(default=list, blank=True)
    
    # Context
    referrer = models.TextField(blank=True)
    landing_page = models.CharField(max_length=500, blank=True)
    exit_page = models.CharField(max_length=500, blank=True)
    
    # Device info
    user_agent = models.TextField(blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    device_type = models.CharField(max_length=50, blank=True)  # desktop, mobile, tablet
    browser = models.CharField(max_length=100, blank=True)
    os = models.CharField(max_length=100, blank=True)
    screen_resolution = models.CharField(max_length=50, blank=True)
    
    # Engagement
    is_bounce = models.BooleanField(default=False)
    is_engaged = models.BooleanField(default=False)  # >30s or >1 page view
    
    # Timestamp
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-start_time']
        indexes = [
            models.Index(fields=['user', 'start_time']),
            models.Index(fields=['session_id']),
        ]
        verbose_name = 'User Session'
        verbose_name_plural = 'User Sessions'
    
    def __str__(self):
        return f"Session {self.session_id} - {self.start_time}"
    
    def calculate_duration(self):
        """Calculate session duration"""
        if self.end_time:
            delta = self.end_time - self.start_time
            self.duration = int(delta.total_seconds())
            return self.duration
        return 0


class PerformanceMetric(models.Model):
    """
    Store performance metrics (API response times, page load times, etc.)
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # User context
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='performance_metrics')
    session_id = models.CharField(max_length=200, db_index=True)
    
    # Metric details
    metric_type = models.CharField(max_length=100, db_index=True)  # api_response, page_load, user_flow
    metric_name = models.CharField(max_length=200)
    value = models.FloatField()  # in milliseconds
    
    # Properties
    properties = models.JSONField(default=dict, blank=True)
    
    # Timestamp
    timestamp = models.DateTimeField(default=timezone.now, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['metric_type', 'timestamp']),
            models.Index(fields=['user', 'timestamp']),
        ]
        verbose_name = 'Performance Metric'
        verbose_name_plural = 'Performance Metrics'
    
    def __str__(self):
        return f"{self.metric_type}: {self.metric_name} = {self.value}ms"


class Funnel(models.Model):
    """
    Define conversion funnels
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Funnel details
    name = models.CharField(max_length=200, unique=True)
    description = models.TextField(blank=True)
    
    # Steps (ordered list of event names)
    steps = models.JSONField(default=list)
    
    # Configuration
    active = models.BooleanField(default=True)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    
    class Meta:
        ordering = ['name']
        verbose_name = 'Funnel'
        verbose_name_plural = 'Funnels'
    
    def __str__(self):
        return f"{self.name} ({len(self.steps)} steps)"


class FunnelCompletion(models.Model):
    """
    Track funnel completions
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Funnel reference
    funnel = models.ForeignKey(Funnel, on_delete=models.CASCADE, related_name='completions')
    
    # User context
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='funnel_completions')
    session_id = models.CharField(max_length=200, db_index=True)
    
    # Completion details
    completed = models.BooleanField(default=False)
    abandoned_at_step = models.IntegerField(null=True, blank=True)
    
    # Steps completed (list of step indices)
    steps_completed = models.JSONField(default=list)
    
    # Timing
    start_time = models.DateTimeField(default=timezone.now)
    end_time = models.DateTimeField(null=True, blank=True)
    duration = models.IntegerField(null=True, blank=True)  # in seconds
    
    # Properties
    properties = models.JSONField(default=dict, blank=True)
    
    # Timestamp
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-start_time']
        indexes = [
            models.Index(fields=['funnel', 'completed', 'start_time']),
            models.Index(fields=['user', 'start_time']),
        ]
        verbose_name = 'Funnel Completion'
        verbose_name_plural = 'Funnel Completions'
    
    def __str__(self):
        status = 'Completed' if self.completed else f'Abandoned at step {self.abandoned_at_step}'
        return f"{self.funnel.name} - {status}"


class CohortDefinition(models.Model):
    """
    Define user cohorts for analysis
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Cohort details
    name = models.CharField(max_length=200, unique=True)
    description = models.TextField(blank=True)
    
    # Cohort criteria (JSON)
    criteria = models.JSONField(default=dict)
    
    # Configuration
    active = models.BooleanField(default=True)
    
    # Metadata
    user_count = models.IntegerField(default=0)
    last_calculated = models.DateTimeField(null=True, blank=True)
    
    # Timestamp
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    
    class Meta:
        ordering = ['name']
        verbose_name = 'Cohort Definition'
        verbose_name_plural = 'Cohort Definitions'
    
    def __str__(self):
        return f"{self.name} ({self.user_count} users)"


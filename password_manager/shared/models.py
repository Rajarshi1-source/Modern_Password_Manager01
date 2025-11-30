"""
Performance Monitoring Models
==============================

Models for storing performance metrics and system health data.
"""

from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


class PerformanceMetric(models.Model):
    """Store request/response performance metrics"""
    
    path = models.CharField(max_length=500)
    method = models.CharField(max_length=10)
    duration_ms = models.FloatField(help_text="Request duration in milliseconds")
    status_code = models.IntegerField()
    query_count = models.IntegerField(default=0)
    query_time_ms = models.FloatField(default=0)
    memory_mb = models.FloatField(default=0, help_text="Memory used in MB")
    timestamp = models.DateTimeField(default=timezone.now, db_index=True)
    user = models.CharField(max_length=150, default='anonymous')
    
    class Meta:
        db_table = 'performance_metrics'
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['-timestamp', 'path']),
            models.Index(fields=['path', 'method']),
        ]
    
    def __str__(self):
        return f"{self.method} {self.path} - {self.duration_ms}ms"


class APIPerformanceMetric(models.Model):
    """Store API-specific performance metrics"""
    
    endpoint = models.CharField(max_length=500)
    method = models.CharField(max_length=10)
    duration_ms = models.FloatField()
    status = models.IntegerField()
    timestamp = models.DateTimeField(default=timezone.now, db_index=True)
    
    class Meta:
        db_table = 'api_performance_metrics'
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['-timestamp', 'endpoint']),
            models.Index(fields=['endpoint', 'method']),
        ]
    
    def __str__(self):
        return f"API: {self.method} {self.endpoint} - {self.duration_ms}ms"


class SystemMetric(models.Model):
    """Store system resource metrics"""
    
    cpu_percent = models.FloatField()
    memory_percent = models.FloatField()
    memory_available_mb = models.FloatField()
    disk_percent = models.FloatField()
    disk_free_gb = models.FloatField()
    timestamp = models.DateTimeField(default=timezone.now, db_index=True)
    
    class Meta:
        db_table = 'system_metrics'
        ordering = ['-timestamp']
    
    def __str__(self):
        return f"System: CPU {self.cpu_percent}%, Memory {self.memory_percent}%"


class ErrorLog(models.Model):
    """Store application errors for tracking and analysis"""
    
    ERROR_LEVELS = [
        ('DEBUG', 'Debug'),
        ('INFO', 'Info'),
        ('WARNING', 'Warning'),
        ('ERROR', 'Error'),
        ('CRITICAL', 'Critical'),
    ]
    
    level = models.CharField(max_length=10, choices=ERROR_LEVELS)
    message = models.TextField()
    exception_type = models.CharField(max_length=200, null=True, blank=True)
    traceback = models.TextField(null=True, blank=True)
    path = models.CharField(max_length=500, null=True, blank=True)
    method = models.CharField(max_length=10, null=True, blank=True)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    user_agent = models.CharField(max_length=500, null=True, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    request_data = models.JSONField(null=True, blank=True)
    timestamp = models.DateTimeField(default=timezone.now, db_index=True)
    resolved = models.BooleanField(default=False)
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolved_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='resolved_errors'
    )
    count = models.IntegerField(default=1, help_text="Number of times this error occurred")
    last_occurrence = models.DateTimeField(default=timezone.now)
    
    class Meta:
        db_table = 'error_logs'
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['-timestamp', 'level']),
            models.Index(fields=['resolved', '-timestamp']),
            models.Index(fields=['exception_type', '-timestamp']),
        ]
    
    def __str__(self):
        return f"{self.level}: {self.message[:100]}"
    
    def mark_resolved(self, user=None):
        """Mark error as resolved"""
        self.resolved = True
        self.resolved_at = timezone.now()
        if user:
            self.resolved_by = user
        self.save()


class PerformanceAlert(models.Model):
    """Track performance alerts and anomalies"""
    
    ALERT_TYPES = [
        ('SLOW_REQUEST', 'Slow Request'),
        ('EXCESSIVE_QUERIES', 'Excessive Queries'),
        ('HIGH_CPU', 'High CPU Usage'),
        ('HIGH_MEMORY', 'High Memory Usage'),
        ('HIGH_DISK', 'High Disk Usage'),
        ('ERROR_RATE', 'High Error Rate'),
        ('ANOMALY', 'Performance Anomaly'),
    ]
    
    SEVERITY_LEVELS = [
        ('LOW', 'Low'),
        ('MEDIUM', 'Medium'),
        ('HIGH', 'High'),
        ('CRITICAL', 'Critical'),
    ]
    
    alert_type = models.CharField(max_length=50, choices=ALERT_TYPES)
    severity = models.CharField(max_length=10, choices=SEVERITY_LEVELS)
    message = models.TextField()
    details = models.JSONField(null=True, blank=True)
    timestamp = models.DateTimeField(default=timezone.now, db_index=True)
    acknowledged = models.BooleanField(default=False)
    acknowledged_at = models.DateTimeField(null=True, blank=True)
    acknowledged_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    resolved = models.BooleanField(default=False)
    resolved_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'performance_alerts'
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['acknowledged', 'resolved', '-timestamp']),
            models.Index(fields=['severity', '-timestamp']),
            models.Index(fields=['alert_type', '-timestamp']),
        ]
    
    def __str__(self):
        return f"{self.severity} - {self.alert_type}: {self.message[:50]}"
    
    def acknowledge(self, user=None):
        """Acknowledge the alert"""
        self.acknowledged = True
        self.acknowledged_at = timezone.now()
        if user:
            self.acknowledged_by = user
        self.save()
    
    def resolve(self):
        """Mark alert as resolved"""
        self.resolved = True
        self.resolved_at = timezone.now()
        self.save()


class DependencyVersion(models.Model):
    """Track installed dependency versions and vulnerabilities"""
    
    name = models.CharField(max_length=200)
    current_version = models.CharField(max_length=50)
    latest_version = models.CharField(max_length=50, null=True, blank=True)
    update_available = models.BooleanField(default=False)
    has_vulnerabilities = models.BooleanField(default=False)
    vulnerability_count = models.IntegerField(default=0)
    vulnerability_details = models.JSONField(null=True, blank=True)
    last_checked = models.DateTimeField(default=timezone.now)
    ecosystem = models.CharField(max_length=50, default='python')  # python, npm, etc.
    
    class Meta:
        db_table = 'dependency_versions'
        unique_together = ['name', 'ecosystem']
        ordering = ['name']
    
    def __str__(self):
        return f"{self.name} {self.current_version}"


class PerformancePrediction(models.Model):
    """Store ML predictions for performance optimization"""
    
    endpoint = models.CharField(max_length=500)
    predicted_duration_ms = models.FloatField()
    actual_duration_ms = models.FloatField(null=True, blank=True)
    prediction_accuracy = models.FloatField(null=True, blank=True)
    confidence_score = models.FloatField()
    features_used = models.JSONField()
    model_version = models.CharField(max_length=50)
    timestamp = models.DateTimeField(default=timezone.now, db_index=True)
    
    class Meta:
        db_table = 'performance_predictions'
        ordering = ['-timestamp']
    
    def __str__(self):
        return f"Prediction for {self.endpoint}: {self.predicted_duration_ms}ms"
    
    def calculate_accuracy(self):
        """Calculate prediction accuracy"""
        if self.actual_duration_ms:
            error = abs(self.predicted_duration_ms - self.actual_duration_ms)
            self.prediction_accuracy = max(0, 100 - (error / self.actual_duration_ms * 100))
            self.save()


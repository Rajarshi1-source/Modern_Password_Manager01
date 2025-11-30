"""
FHE Service Database Models

Models for storing FHE-related data:
- FHEKeyStore: Encrypted FHE keys per user
- FHEComputationCache: Cached encrypted computation results
- FHEOperationLog: Audit trail for FHE operations
"""

from django.db import models
from django.conf import settings
from django.utils import timezone
import uuid


class FHEKeyStore(models.Model):
    """
    Stores FHE keys for each user.
    Keys are encrypted with user's master key before storage.
    """
    
    KEY_TYPES = (
        ('concrete', 'Concrete-Python'),
        ('seal_public', 'SEAL Public Key'),
        ('seal_secret', 'SEAL Secret Key'),
        ('seal_relin', 'SEAL Relinearization Key'),
        ('seal_galois', 'SEAL Galois Key'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='fhe_keys'
    )
    
    key_type = models.CharField(max_length=20, choices=KEY_TYPES)
    
    # Encrypted key data (encrypted with user's master-derived key)
    encrypted_key_data = models.BinaryField()
    
    # Key metadata
    key_size_bits = models.IntegerField(default=0)
    polynomial_modulus_degree = models.IntegerField(default=8192)
    security_level = models.IntegerField(default=128)
    
    # CKKS-specific parameters
    scale = models.FloatField(null=True, blank=True)
    coefficient_modulus = models.JSONField(default=list, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    last_used_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    
    # Status
    is_active = models.BooleanField(default=True)
    
    class Meta:
        verbose_name = 'FHE Key Store'
        verbose_name_plural = 'FHE Key Stores'
        unique_together = ['user', 'key_type']
        indexes = [
            models.Index(fields=['user', 'key_type', 'is_active']),
            models.Index(fields=['expires_at']),
        ]
    
    def __str__(self):
        return f"{self.user.username} - {self.key_type}"
    
    def mark_used(self):
        """Update last_used_at timestamp."""
        self.last_used_at = timezone.now()
        self.save(update_fields=['last_used_at'])


class FHEComputationCacheModel(models.Model):
    """
    Database-backed cache for FHE computation results.
    Complements Redis cache for persistent storage.
    """
    
    OPERATION_TYPES = (
        ('strength_check', 'Password Strength Check'),
        ('similarity_search', 'Similarity Search'),
        ('breach_detection', 'Breach Detection'),
        ('batch_strength', 'Batch Strength Evaluation'),
        ('encrypted_compare', 'Encrypted Comparison'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Operation identification
    operation_type = models.CharField(max_length=30, choices=OPERATION_TYPES)
    input_hash = models.CharField(max_length=64, db_index=True)  # SHA-256 hash
    
    # User association (optional - some operations may be user-agnostic)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='fhe_cache_entries'
    )
    
    # Encrypted result
    encrypted_result = models.BinaryField()
    result_size_bytes = models.IntegerField(default=0)
    
    # Computation metadata
    computation_time_ms = models.IntegerField(default=0)
    circuit_depth = models.IntegerField(default=0)
    encryption_tier = models.CharField(max_length=20, default='full_fhe')
    
    # Cache management
    hit_count = models.IntegerField(default=0)
    created_at = models.DateTimeField(default=timezone.now)
    expires_at = models.DateTimeField()
    last_accessed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        verbose_name = 'FHE Computation Cache'
        verbose_name_plural = 'FHE Computation Caches'
        indexes = [
            models.Index(fields=['operation_type', 'input_hash']),
            models.Index(fields=['user', 'operation_type']),
            models.Index(fields=['expires_at']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        return f"{self.operation_type} - {self.input_hash[:16]}..."
    
    def record_hit(self):
        """Record a cache hit."""
        self.hit_count += 1
        self.last_accessed_at = timezone.now()
        self.save(update_fields=['hit_count', 'last_accessed_at'])
    
    @property
    def is_expired(self):
        """Check if cache entry has expired."""
        return timezone.now() > self.expires_at


class FHEOperationLog(models.Model):
    """
    Audit log for all FHE operations.
    Tracks usage patterns and potential security issues.
    """
    
    OPERATION_STATUS = (
        ('success', 'Success'),
        ('failed', 'Failed'),
        ('timeout', 'Timeout'),
        ('fallback', 'Fallback Used'),
        ('cached', 'Cache Hit'),
    )
    
    ENCRYPTION_TIERS = (
        ('client_only', 'Client Only'),
        ('hybrid_fhe', 'Hybrid FHE'),
        ('full_fhe', 'Full FHE'),
        ('cached_fhe', 'Cached FHE'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # User and request info
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='fhe_operations'
    )
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(null=True, blank=True)
    
    # Operation details
    operation_type = models.CharField(max_length=50)
    encryption_tier = models.CharField(max_length=20, choices=ENCRYPTION_TIERS)
    status = models.CharField(max_length=20, choices=OPERATION_STATUS)
    
    # Performance metrics
    total_time_ms = models.IntegerField(default=0)
    encryption_time_ms = models.IntegerField(default=0)
    computation_time_ms = models.IntegerField(default=0)
    decryption_time_ms = models.IntegerField(default=0)
    
    # Circuit details
    circuit_depth = models.IntegerField(default=0)
    circuit_complexity = models.CharField(max_length=20, default='unknown')
    
    # Input/output metadata (no actual data)
    input_size_bytes = models.IntegerField(default=0)
    output_size_bytes = models.IntegerField(default=0)
    
    # Error tracking
    error_message = models.TextField(null=True, blank=True)
    error_code = models.CharField(max_length=50, null=True, blank=True)
    
    # Cache info
    cache_hit = models.BooleanField(default=False)
    cache_key = models.CharField(max_length=64, null=True, blank=True)
    
    # Adaptive depth info
    requested_profile = models.CharField(max_length=20, null=True, blank=True)
    actual_profile = models.CharField(max_length=20, null=True, blank=True)
    fallback_used = models.BooleanField(default=False)
    
    # Timestamps
    created_at = models.DateTimeField(default=timezone.now)
    
    class Meta:
        verbose_name = 'FHE Operation Log'
        verbose_name_plural = 'FHE Operation Logs'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'created_at']),
            models.Index(fields=['operation_type', 'status']),
            models.Index(fields=['created_at']),
            models.Index(fields=['encryption_tier']),
        ]
    
    def __str__(self):
        return f"{self.operation_type} - {self.status} ({self.created_at})"


class FHEMetrics(models.Model):
    """
    Aggregated metrics for FHE operations.
    Used for monitoring and optimization.
    """
    
    METRIC_PERIODS = (
        ('hourly', 'Hourly'),
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    period_type = models.CharField(max_length=10, choices=METRIC_PERIODS)
    period_start = models.DateTimeField()
    period_end = models.DateTimeField()
    
    # Operation counts
    total_operations = models.IntegerField(default=0)
    successful_operations = models.IntegerField(default=0)
    failed_operations = models.IntegerField(default=0)
    timeout_operations = models.IntegerField(default=0)
    
    # Tier distribution
    client_only_count = models.IntegerField(default=0)
    hybrid_fhe_count = models.IntegerField(default=0)
    full_fhe_count = models.IntegerField(default=0)
    cached_fhe_count = models.IntegerField(default=0)
    
    # Performance metrics
    avg_latency_ms = models.FloatField(default=0)
    p50_latency_ms = models.FloatField(default=0)
    p95_latency_ms = models.FloatField(default=0)
    p99_latency_ms = models.FloatField(default=0)
    
    # Cache metrics
    cache_hit_rate = models.FloatField(default=0)
    cache_size_bytes = models.BigIntegerField(default=0)
    
    # Fallback metrics
    fallback_rate = models.FloatField(default=0)
    
    created_at = models.DateTimeField(default=timezone.now)
    
    class Meta:
        verbose_name = 'FHE Metrics'
        verbose_name_plural = 'FHE Metrics'
        unique_together = ['period_type', 'period_start']
        indexes = [
            models.Index(fields=['period_type', 'period_start']),
        ]
    
    def __str__(self):
        return f"{self.period_type}: {self.period_start} - {self.period_end}"


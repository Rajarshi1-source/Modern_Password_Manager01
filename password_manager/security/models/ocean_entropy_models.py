"""
Ocean Wave Entropy Models
==========================

Django models for ocean entropy tracking, hybrid password certificates,
buoy health monitoring, and per-user usage statistics.

Add the model registrations to security/models.py if needed.

@author Password Manager Team
@created 2026-01-23
"""

from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
import uuid

User = get_user_model()


# =============================================================================
# Ocean Entropy Batch
# =============================================================================

class OceanEntropyBatch(models.Model):
    """
    Tracks ocean entropy fetches for auditing and transparency.
    
    Similar to QuantumEntropyBatch, provides provenance for ocean-sourced entropy.
    """
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Buoy information
    buoy_id = models.CharField(
        max_length=20,
        help_text="NOAA buoy identifier (e.g., '44013')"
    )
    buoy_name = models.CharField(
        max_length=255,
        blank=True,
        help_text="Friendly buoy name (e.g., 'Boston 16 NM East of Boston')"
    )
    buoy_latitude = models.DecimalField(
        max_digits=10,
        decimal_places=7,
        null=True,
        blank=True
    )
    buoy_longitude = models.DecimalField(
        max_digits=10,
        decimal_places=7,
        null=True,
        blank=True
    )
    
    # Ocean data captured
    wave_height = models.FloatField(
        null=True,
        blank=True,
        help_text="Wave height in meters"
    )
    wave_period = models.FloatField(
        null=True,
        blank=True,
        help_text="Wave period in seconds"
    )
    wave_direction = models.IntegerField(
        null=True,
        blank=True,
        help_text="Wave direction in degrees"
    )
    water_temperature = models.FloatField(
        null=True,
        blank=True,
        help_text="Water temperature in Celsius"
    )
    wind_speed = models.FloatField(
        null=True,
        blank=True,
        help_text="Wind speed in m/s"
    )
    
    # Entropy metrics
    bytes_fetched = models.IntegerField(
        help_text="Number of entropy bytes generated"
    )
    quality_score = models.FloatField(
        help_text="Entropy quality score (0.0-1.0)"
    )
    shannon_entropy = models.FloatField(
        null=True,
        blank=True,
        help_text="Calculated Shannon entropy (bits per byte)"
    )
    
    # Timestamps
    buoy_reading_timestamp = models.DateTimeField(
        help_text="When the buoy took the reading"
    )
    fetched_at = models.DateTimeField(
        auto_now_add=True,
        help_text="When we fetched the entropy"
    )
    
    # Metadata
    fetch_duration_ms = models.IntegerField(
        null=True,
        blank=True,
        help_text="Time to fetch in milliseconds"
    )
    api_response_code = models.IntegerField(
        null=True,
        blank=True,
        help_text="NOAA API response code"
    )
    
    class Meta:
        db_table = 'ocean_entropy_batch'
        verbose_name = 'Ocean Entropy Batch'
        verbose_name_plural = 'Ocean Entropy Batches'
        ordering = ['-fetched_at']
        indexes = [
            models.Index(fields=['buoy_id', '-fetched_at']),
            models.Index(fields=['-quality_score']),
        ]
    
    def __str__(self):
        return f"Ocean: {self.buoy_id} - {self.bytes_fetched} bytes @ {self.fetched_at}"


# =============================================================================
# Hybrid Password Certificate
# =============================================================================

class HybridPasswordCertificate(models.Model):
    """
    Certificate for passwords generated from multiple entropy sources.
    
    Extends the single-source certificates (QuantumPasswordCertificate,
    GeneticPasswordCertificate) to track multi-source mixing.
    """
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='hybrid_certificates'
    )
    
    # Password reference (hash prefix only)
    password_hash_prefix = models.CharField(
        max_length=64,
        help_text="First 16 chars of SHA256 hash"
    )
    
    # Source tracking
    sources_used = models.JSONField(
        help_text="List of sources: ['quantum', 'ocean', 'genetic']"
    )
    
    # Quantum source info
    quantum_provider = models.CharField(
        max_length=50,
        blank=True,
        help_text="Quantum provider (ANU/IBM/IonQ)"
    )
    quantum_certificate_id = models.UUIDField(
        null=True,
        blank=True,
        help_text="Reference to QuantumPasswordCertificate"
    )
    
    # Ocean source info
    ocean_buoy_id = models.CharField(
        max_length=20,
        blank=True,
        help_text="NOAA buoy used"
    )
    ocean_batch_id = models.UUIDField(
        null=True,
        blank=True,
        help_text="Reference to OceanEntropyBatch"
    )
    ocean_wave_height = models.FloatField(
        null=True,
        blank=True,
        help_text="Wave height at generation time"
    )
    
    # Genetic source info (if applicable)
    genetic_provider = models.CharField(
        max_length=50,
        blank=True,
        help_text="Genetic provider (Sequencing.com/23andMe/etc.)"
    )
    genetic_certificate_id = models.UUIDField(
        null=True,
        blank=True,
        help_text="Reference to GeneticPasswordCertificate"
    )
    
    # Mixing metadata
    mixing_algorithm = models.CharField(
        max_length=100,
        default='XOR + SHA3-512 + SHAKE256',
        help_text="Algorithm used to combine sources"
    )
    total_entropy_bits = models.IntegerField(
        help_text="Total entropy bits from all sources"
    )
    
    # Password properties
    password_length = models.IntegerField()
    charset_used = models.CharField(
        max_length=100,
        default='standard',
        help_text="Character types: uppercase,lowercase,numbers,symbols"
    )
    
    # Quality assessment
    combined_quality_score = models.FloatField(
        help_text="Combined quality score (0.0-1.0)"
    )
    
    # Timestamps and signature
    generation_timestamp = models.DateTimeField(auto_now_add=True)
    signature = models.CharField(
        max_length=256,
        help_text="HMAC signature of certificate data"
    )
    
    # Optional vault link
    vault_item_id = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        help_text="Link to password manager vault item"
    )
    
    class Meta:
        db_table = 'hybrid_password_certificate'
        verbose_name = 'Hybrid Password Certificate'
        verbose_name_plural = 'Hybrid Password Certificates'
        ordering = ['-generation_timestamp']
        indexes = [
            models.Index(fields=['user', '-generation_timestamp']),
            models.Index(fields=['password_hash_prefix']),
        ]
    
    def __str__(self):
        sources = '+'.join(self.sources_used)
        return f"HC-{str(self.id)[:8]} ({sources})"
    
    def to_dict(self):
        """Convert to dictionary for API responses."""
        return {
            'certificate_id': str(self.id),
            'password_hash_prefix': self.password_hash_prefix,
            'sources_used': self.sources_used,
            'quantum': {
                'provider': self.quantum_provider,
                'certificate_id': str(self.quantum_certificate_id) if self.quantum_certificate_id else None,
            },
            'ocean': {
                'buoy_id': self.ocean_buoy_id,
                'wave_height': self.ocean_wave_height,
                'batch_id': str(self.ocean_batch_id) if self.ocean_batch_id else None,
            },
            'genetic': {
                'provider': self.genetic_provider,
                'certificate_id': str(self.genetic_certificate_id) if self.genetic_certificate_id else None,
            },
            'mixing_algorithm': self.mixing_algorithm,
            'total_entropy_bits': self.total_entropy_bits,
            'password_length': self.password_length,
            'quality_score': self.combined_quality_score,
            'generation_timestamp': self.generation_timestamp.isoformat(),
            'signature': self.signature,
        }


# =============================================================================
# Buoy Health Status
# =============================================================================

class BuoyHealthStatus(models.Model):
    """
    Tracks health status of NOAA buoys over time.
    
    Used for monitoring, alerting, and selecting best buoys.
    """
    
    HEALTH_CHOICES = [
        ('excellent', 'Excellent'),
        ('good', 'Good'),
        ('degraded', 'Degraded'),
        ('offline', 'Offline'),
    ]
    
    id = models.AutoField(primary_key=True)
    
    buoy_id = models.CharField(max_length=20)
    buoy_name = models.CharField(max_length=255, blank=True)
    
    # Health assessment
    health_status = models.CharField(
        max_length=20,
        choices=HEALTH_CHOICES
    )
    
    # Metrics
    data_freshness_minutes = models.IntegerField(
        help_text="Minutes since last buoy reading"
    )
    data_completeness = models.FloatField(
        help_text="Fraction of expected parameters present (0.0-1.0)"
    )
    average_quality_score = models.FloatField(
        help_text="Average quality score over recent readings"
    )
    
    # Availability tracking
    uptime_percentage = models.FloatField(
        help_text="Percentage uptime over last 24 hours"
    )
    total_readings_24h = models.IntegerField(
        help_text="Number of readings in last 24 hours"
    )
    
    # Wave conditions (for context)
    current_wave_height = models.FloatField(null=True, blank=True)
    current_wind_speed = models.FloatField(null=True, blank=True)
    
    # Timestamps
    last_successful_fetch = models.DateTimeField(null=True, blank=True)
    last_check = models.DateTimeField(auto_now=True)
    recorded_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'buoy_health_status'
        verbose_name = 'Buoy Health Status'
        verbose_name_plural = 'Buoy Health Statuses'
        ordering = ['-recorded_at']
        indexes = [
            models.Index(fields=['buoy_id', '-recorded_at']),
            models.Index(fields=['health_status']),
        ]
    
    def __str__(self):
        icons = {
            'excellent': '🟢',
            'good': '🟡',
            'degraded': '🟠',
            'offline': '🔴',
        }
        icon = icons.get(self.health_status, '⚪')
        return f"{icon} {self.buoy_id}: {self.health_status}"


# =============================================================================
# Ocean Entropy Usage Stats
# =============================================================================

class OceanEntropyUsageStats(models.Model):
    """
    User statistics for ocean entropy usage.
    
    Tracks how much each user has benefited from ocean-sourced passwords.
    """
    
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        primary_key=True,
        related_name='ocean_entropy_stats'
    )
    
    # Usage counts
    total_ocean_passwords = models.IntegerField(
        default=0,
        help_text="Total passwords with ocean entropy"
    )
    total_hybrid_passwords = models.IntegerField(
        default=0,
        help_text="Total passwords mixing quantum + ocean"
    )
    
    # Favorite buoys (most used)
    favorite_buoy_id = models.CharField(
        max_length=20,
        blank=True,
        help_text="Most frequently used buoy"
    )
    favorite_buoy_usage_count = models.IntegerField(default=0)
    
    # Quality metrics
    average_quality_score = models.FloatField(
        default=0.0,
        help_text="Average quality across all ocean entropy fetches"
    )
    
    # Timestamps
    first_ocean_password = models.DateTimeField(null=True, blank=True)
    last_ocean_password = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'ocean_entropy_usage_stats'
        verbose_name = 'Ocean Entropy Usage Stats'
    
    def __str__(self):
        return f"Ocean stats: {self.user.username} ({self.total_ocean_passwords} passwords)"

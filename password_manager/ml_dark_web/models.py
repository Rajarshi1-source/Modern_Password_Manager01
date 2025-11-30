"""
ML-Enhanced Dark Web Monitoring Models
Extends the existing BreachAlert model with ML-specific tables
"""

from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
import hashlib


class BreachSource(models.Model):
    """Tracks dark web sources being monitored"""
    SOURCE_TYPES = [
        ('forum', 'Dark Web Forum'),
        ('paste', 'Paste Site'),
        ('marketplace', 'Marketplace'),
        ('telegram', 'Telegram Channel'),
        ('irc', 'IRC Channel'),
        ('onion', 'Onion Site'),
        ('clearweb', 'Clear Web'),
    ]
    
    name = models.CharField(max_length=255)
    url = models.URLField(max_length=500)
    source_type = models.CharField(max_length=20, choices=SOURCE_TYPES)
    last_scraped = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    reliability_score = models.FloatField(default=0.5, help_text="ML-computed reliability (0-1)")
    scrape_frequency_hours = models.IntegerField(default=24)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'ml_breach_sources'
        ordering = ['-reliability_score', '-last_scraped']
        indexes = [
            models.Index(fields=['is_active', 'last_scraped']),
            models.Index(fields=['source_type', 'reliability_score']),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.get_source_type_display()})"


class MLBreachData(models.Model):
    """Stores ML-detected breach information"""
    SEVERITY_CHOICES = [
        ('LOW', 'Low'),
        ('MEDIUM', 'Medium'),
        ('HIGH', 'High'),
        ('CRITICAL', 'Critical'),
    ]
    
    PROCESSING_STATUS = [
        ('pending', 'Pending Analysis'),
        ('analyzing', 'Being Analyzed'),
        ('matched', 'Credentials Matched'),
        ('completed', 'Completed'),
        ('failed', 'Analysis Failed'),
    ]
    
    breach_id = models.CharField(max_length=100, unique=True, db_index=True)
    title = models.CharField(max_length=500)
    description = models.TextField()
    source = models.ForeignKey(BreachSource, on_delete=models.CASCADE, related_name='breaches')
    
    # Temporal data
    detected_at = models.DateTimeField(auto_now_add=True, db_index=True)
    breach_date = models.DateTimeField(null=True, blank=True)
    
    # ML Classification Results
    severity = models.CharField(max_length=10, choices=SEVERITY_CHOICES, db_index=True)
    confidence_score = models.FloatField(help_text="ML model confidence (0-1)")
    ml_model_version = models.CharField(max_length=50, default='1.0')
    
    # Breach details
    affected_records = models.BigIntegerField(default=0)
    exposed_data_types = models.JSONField(default=list, help_text="['email', 'password', 'phone', etc.]")
    
    # Content
    raw_content = models.TextField(help_text="Original scraped content")
    processed_content = models.TextField(blank=True, help_text="Cleaned and processed content")
    
    # Processing status
    processing_status = models.CharField(max_length=20, choices=PROCESSING_STATUS, default='pending')
    processed_at = models.DateTimeField(null=True, blank=True)
    
    # Extracted entities (from ML)
    extracted_emails = models.JSONField(default=list)
    extracted_domains = models.JSONField(default=list)
    extracted_credentials = models.JSONField(default=list, help_text="Hashed credential pairs")
    
    # Embeddings for similarity search
    content_embedding = models.BinaryField(null=True, blank=True, help_text="BERT embedding vector")
    
    class Meta:
        db_table = 'ml_breach_data'
        ordering = ['-detected_at']
        indexes = [
            models.Index(fields=['breach_date', 'severity']),
            models.Index(fields=['confidence_score', 'severity']),
            models.Index(fields=['processing_status', 'detected_at']),
            models.Index(fields=['source', 'detected_at']),
        ]
    
    def __str__(self):
        return f"{self.breach_id} - {self.severity} ({self.confidence_score:.2f})"


class UserCredentialMonitoring(models.Model):
    """Stores hashed user credentials for ML-based monitoring"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='monitored_credentials')
    
    # Hashed credentials (SHA-256)
    email_hash = models.CharField(max_length=64, db_index=True)
    username_hash = models.CharField(max_length=64, blank=True, db_index=True)
    domain = models.CharField(max_length=255, db_index=True)
    
    # ML Embeddings
    email_embedding = models.BinaryField(null=True, blank=True, help_text="Siamese network embedding")
    
    # Metadata
    credential_type = models.CharField(max_length=50, default='email')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_checked = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'ml_user_credential_monitoring'
        unique_together = ['user', 'email_hash']
        indexes = [
            models.Index(fields=['email_hash', 'is_active']),
            models.Index(fields=['domain', 'is_active']),
            models.Index(fields=['user', 'is_active', 'last_checked']),
        ]
    
    def __str__(self):
        return f"{self.user.username} - {self.domain}"


class MLBreachMatch(models.Model):
    """Stores ML-detected matches between user credentials and breaches"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='ml_breach_matches')
    breach = models.ForeignKey(MLBreachData, on_delete=models.CASCADE, related_name='matches')
    monitored_credential = models.ForeignKey(
        UserCredentialMonitoring, 
        on_delete=models.CASCADE,
        related_name='matches'
    )
    
    # ML Match scores
    similarity_score = models.FloatField(help_text="Siamese network similarity score (0-1)")
    confidence_score = models.FloatField(help_text="Overall match confidence (0-1)")
    
    # Match details
    match_type = models.CharField(max_length=50, default='credential')  # credential, email, username
    matched_data = models.JSONField(default=dict, help_text="Details about the match")
    
    # Alert status
    alert_created = models.BooleanField(default=False)
    alert_id = models.IntegerField(null=True, blank=True, help_text="Reference to BreachAlert")
    
    # Temporal
    detected_at = models.DateTimeField(auto_now_add=True)
    resolved = models.BooleanField(default=False)
    resolved_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'ml_breach_matches'
        unique_together = ['user', 'breach', 'monitored_credential']
        ordering = ['-detected_at']
        indexes = [
            models.Index(fields=['user', 'resolved', 'detected_at']),
            models.Index(fields=['similarity_score', 'confidence_score']),
            models.Index(fields=['alert_created', 'detected_at']),
        ]
    
    def __str__(self):
        return f"{self.user.username} - {self.breach.breach_id} ({self.similarity_score:.2f})"


class MLModelMetadata(models.Model):
    """Tracks ML model versions and performance"""
    MODEL_TYPES = [
        ('breach_classifier', 'BERT Breach Classifier'),
        ('credential_matcher', 'Siamese Credential Matcher'),
        ('pattern_detector', 'LSTM Pattern Detector'),
        ('entity_extractor', 'NER Entity Extractor'),
    ]
    
    model_type = models.CharField(max_length=50, choices=MODEL_TYPES)
    version = models.CharField(max_length=50)
    file_path = models.CharField(max_length=500, help_text="Path to model file")
    
    # Performance metrics
    accuracy = models.FloatField(null=True, blank=True)
    precision = models.FloatField(null=True, blank=True)
    recall = models.FloatField(null=True, blank=True)
    f1_score = models.FloatField(null=True, blank=True)
    
    # Training info
    training_samples = models.IntegerField(default=0)
    training_date = models.DateTimeField(auto_now_add=True)
    last_used = models.DateTimeField(auto_now=True)
    
    # Configuration
    hyperparameters = models.JSONField(default=dict)
    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True)
    
    class Meta:
        db_table = 'ml_model_metadata'
        unique_together = ['model_type', 'version']
        ordering = ['-training_date']
    
    def __str__(self):
        return f"{self.get_model_type_display()} v{self.version}"


class DarkWebScrapeLog(models.Model):
    """Logs dark web scraping activities"""
    source = models.ForeignKey(BreachSource, on_delete=models.CASCADE, related_name='scrape_logs')
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    # Results
    items_found = models.IntegerField(default=0)
    breaches_detected = models.IntegerField(default=0)
    processing_time_seconds = models.FloatField(default=0)
    
    # Status
    status = models.CharField(
        max_length=20,
        choices=[
            ('running', 'Running'),
            ('completed', 'Completed'),
            ('failed', 'Failed'),
            ('partial', 'Partial Success'),
        ],
        default='running'
    )
    error_message = models.TextField(blank=True)
    
    class Meta:
        db_table = 'ml_darkweb_scrape_logs'
        ordering = ['-started_at']
        indexes = [
            models.Index(fields=['source', 'started_at']),
            models.Index(fields=['status', 'started_at']),
        ]


class BreachPatternAnalysis(models.Model):
    """Stores LSTM-detected patterns in breach data"""
    pattern_id = models.CharField(max_length=100, unique=True)
    pattern_type = models.CharField(
        max_length=50,
        choices=[
            ('temporal', 'Temporal Pattern'),
            ('geographical', 'Geographical Pattern'),
            ('threat_actor', 'Threat Actor Pattern'),
            ('credential_reuse', 'Credential Reuse Pattern'),
        ]
    )
    
    # Pattern details
    description = models.TextField()
    confidence_score = models.FloatField()
    affected_breaches = models.ManyToManyField(MLBreachData, related_name='patterns')
    
    # Temporal data
    first_seen = models.DateTimeField()
    last_seen = models.DateTimeField()
    frequency = models.IntegerField(default=1)
    
    # Risk assessment
    risk_level = models.CharField(
        max_length=20,
        choices=[
            ('low', 'Low'),
            ('medium', 'Medium'),
            ('high', 'High'),
            ('critical', 'Critical'),
        ]
    )
    
    # Metadata
    detected_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        db_table = 'ml_breach_patterns'
        ordering = ['-last_seen']


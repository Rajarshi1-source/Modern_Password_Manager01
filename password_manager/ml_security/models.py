from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
import json

# Create your models here.

class PasswordStrengthPrediction(models.Model):
    """Stores password strength predictions from ML model"""
    STRENGTH_CHOICES = [
        ('very_weak', 'Very Weak'),
        ('weak', 'Weak'),
        ('moderate', 'Moderate'),
        ('strong', 'Strong'),
        ('very_strong', 'Very Strong'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='password_predictions', null=True, blank=True)
    password_hash = models.CharField(max_length=255, help_text="SHA-256 hash of password for tracking")
    strength = models.CharField(max_length=20, choices=STRENGTH_CHOICES)
    confidence_score = models.FloatField(help_text="Model confidence (0-1)")
    entropy = models.FloatField(help_text="Password entropy score")
    character_diversity = models.FloatField()
    length = models.IntegerField()
    has_numbers = models.BooleanField(default=False)
    has_uppercase = models.BooleanField(default=False)
    has_lowercase = models.BooleanField(default=False)
    has_special = models.BooleanField(default=False)
    contains_common_patterns = models.BooleanField(default=False)
    guessability_score = models.FloatField(help_text="How easily guessable (0-100)")
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'created_at']),
            models.Index(fields=['strength']),
        ]
    
    def __str__(self):
        return f"Password strength: {self.strength} (confidence: {self.confidence_score:.2f})"


class UserBehaviorProfile(models.Model):
    """Stores learned user behavior patterns for anomaly detection"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='behavior_profile')
    
    # Temporal patterns
    typical_login_hours = models.JSONField(default=list, help_text="Hours user typically logs in")
    typical_login_days = models.JSONField(default=list, help_text="Days user typically logs in")
    avg_session_duration = models.FloatField(default=0.0, help_text="Average session duration in minutes")
    
    # Behavioral patterns
    typing_speed_avg = models.FloatField(default=0.0, help_text="Average typing speed (chars/sec)")
    typing_speed_std = models.FloatField(default=0.0, help_text="Typing speed standard deviation")
    mouse_movement_pattern = models.JSONField(default=dict, help_text="Mouse movement characteristics")
    
    # Location patterns
    common_locations = models.JSONField(default=list, help_text="Common login locations (lat, lon)")
    common_ip_ranges = models.JSONField(default=list, help_text="Common IP address ranges")
    
    # Device patterns
    common_devices = models.JSONField(default=list, help_text="Device fingerprints")
    common_browsers = models.JSONField(default=list, help_text="Common browsers used")
    common_os = models.JSONField(default=list, help_text="Common operating systems")
    
    # Activity patterns
    vault_access_frequency = models.FloatField(default=0.0)
    password_update_frequency = models.FloatField(default=0.0)
    avg_passwords_accessed_per_session = models.FloatField(default=0.0)
    
    # Model metadata
    last_trained = models.DateTimeField(null=True, blank=True)
    samples_used = models.IntegerField(default=0)
    model_version = models.CharField(max_length=50, default='1.0')
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"Behavior profile for {self.user.username}"


class AnomalyDetection(models.Model):
    """Records anomaly detections for user sessions"""
    ANOMALY_TYPES = [
        ('location', 'Unusual Location'),
        ('time', 'Unusual Time'),
        ('device', 'Unknown Device'),
        ('behavior', 'Unusual Behavior'),
        ('velocity', 'Impossible Travel Velocity'),
        ('frequency', 'Unusual Access Frequency'),
        ('multiple', 'Multiple Anomalies'),
    ]
    
    SEVERITY_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('critical', 'Critical'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='anomalies')
    session_id = models.CharField(max_length=255)
    anomaly_type = models.CharField(max_length=20, choices=ANOMALY_TYPES)
    severity = models.CharField(max_length=10, choices=SEVERITY_CHOICES)
    anomaly_score = models.FloatField(help_text="Anomaly score from model (0-1)")
    confidence = models.FloatField(help_text="Model confidence (0-1)")
    
    # Context information
    ip_address = models.GenericIPAddressField()
    location = models.CharField(max_length=255, blank=True)
    device_fingerprint = models.CharField(max_length=255, blank=True)
    user_agent = models.TextField(blank=True)
    
    # Anomaly details
    expected_values = models.JSONField(default=dict, help_text="Expected behavior values")
    actual_values = models.JSONField(default=dict, help_text="Actual observed values")
    deviations = models.JSONField(default=dict, help_text="Calculated deviations")
    
    # Action taken
    action_taken = models.CharField(max_length=50, blank=True, help_text="MFA, lock, alert, etc.")
    was_false_positive = models.BooleanField(default=False)
    user_feedback = models.TextField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'created_at']),
            models.Index(fields=['severity', 'created_at']),
            models.Index(fields=['anomaly_type']),
        ]
    
    def __str__(self):
        return f"{self.anomaly_type} anomaly for {self.user.username} (severity: {self.severity})"


class ThreatPrediction(models.Model):
    """Real-time threat predictions using hybrid CNN-LSTM model"""
    THREAT_TYPES = [
        ('brute_force', 'Brute Force Attack'),
        ('credential_stuffing', 'Credential Stuffing'),
        ('account_takeover', 'Account Takeover'),
        ('bot_activity', 'Bot Activity'),
        ('phishing', 'Phishing Attempt'),
        ('data_exfiltration', 'Data Exfiltration'),
        ('suspicious_pattern', 'Suspicious Pattern'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='threat_predictions', null=True, blank=True)
    session_id = models.CharField(max_length=255)
    threat_type = models.CharField(max_length=30, choices=THREAT_TYPES)
    threat_score = models.FloatField(help_text="Threat probability (0-1)")
    risk_level = models.IntegerField(help_text="Overall risk level (0-100)")
    
    # Input features
    sequence_features = models.JSONField(help_text="Time-series features analyzed")
    spatial_features = models.JSONField(help_text="Spatial features (from CNN)")
    temporal_features = models.JSONField(help_text="Temporal features (from LSTM)")
    
    # Model predictions
    cnn_output = models.JSONField(help_text="CNN layer output")
    lstm_output = models.JSONField(help_text="LSTM layer output")
    final_prediction = models.JSONField(help_text="Final hybrid model prediction")
    
    # Context
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    device_fingerprint = models.CharField(max_length=255, blank=True)
    
    # Response
    recommended_action = models.CharField(max_length=100, help_text="MFA, block, monitor, etc.")
    action_executed = models.CharField(max_length=100, blank=True)
    was_true_positive = models.BooleanField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'created_at']),
            models.Index(fields=['threat_type', 'created_at']),
            models.Index(fields=['risk_level']),
        ]
    
    def __str__(self):
        return f"{self.threat_type} prediction (risk: {self.risk_level})"


class MLModelMetadata(models.Model):
    """Tracks ML model versions and performance metrics"""
    MODEL_TYPES = [
        ('password_strength', 'Password Strength (LSTM)'),
        ('anomaly_detection', 'Anomaly Detection (Isolation Forest)'),
        ('behavior_clustering', 'Behavior Clustering (K-Means)'),
        ('threat_classification', 'Threat Classification (CNN-LSTM)'),
        ('risk_prediction', 'Risk Prediction (Random Forest)'),
    ]
    
    model_type = models.CharField(max_length=30, choices=MODEL_TYPES, unique=True)
    version = models.CharField(max_length=50)
    file_path = models.CharField(max_length=500, help_text="Path to saved model file")
    
    # Performance metrics
    accuracy = models.FloatField(null=True, blank=True)
    precision = models.FloatField(null=True, blank=True)
    recall = models.FloatField(null=True, blank=True)
    f1_score = models.FloatField(null=True, blank=True)
    auc_roc = models.FloatField(null=True, blank=True)
    
    # Training info
    training_samples = models.IntegerField(default=0)
    training_date = models.DateTimeField(auto_now_add=True)
    last_used = models.DateTimeField(auto_now=True)
    
    # Configuration
    hyperparameters = models.JSONField(default=dict)
    feature_importance = models.JSONField(default=dict, blank=True)
    
    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-training_date']
        verbose_name_plural = "ML Model Metadata"
    
    def __str__(self):
        return f"{self.get_model_type_display()} v{self.version}"


class MLTrainingData(models.Model):
    """Stores training data for model retraining"""
    model_type = models.CharField(max_length=30)
    features = models.JSONField(help_text="Input features")
    label = models.JSONField(help_text="Ground truth label")
    weight = models.FloatField(default=1.0, help_text="Sample weight for training")
    
    # Metadata
    source = models.CharField(max_length=100, blank=True, help_text="Data source")
    is_validated = models.BooleanField(default=False)
    validation_date = models.DateTimeField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['model_type', 'is_validated']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        return f"Training data for {self.model_type}"


# Backwards compatibility for tests expecting old model name
AnomalyDetectionLog = AnomalyDetection


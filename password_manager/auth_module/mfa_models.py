"""
Multi-Factor Authentication Models

This module defines models for advanced MFA including:
- Biometric authentication records
- MFA factor management
- Adaptive MFA policies
- Authentication attempts tracking
"""

from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta
import json


class BiometricProfile(models.Model):
    """Store user's biometric authentication data"""
    
    BIOMETRIC_TYPES = [
        ('face', 'Face Recognition'),
        ('voice', 'Voice Recognition'),
        ('fingerprint', 'Fingerprint'),
        ('iris', 'Iris Scan'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='biometric_profiles')
    biometric_type = models.CharField(max_length=20, choices=BIOMETRIC_TYPES)
    
    # Biometric data (stored as encrypted embeddings)
    embedding_data = models.TextField(help_text="Encrypted biometric embedding")
    embedding_hash = models.CharField(max_length=64, unique=True, help_text="SHA-256 hash of embedding for lookup")
    
    # Metadata
    device_id = models.CharField(max_length=255, blank=True, help_text="Device used for registration")
    is_active = models.BooleanField(default=True)
    confidence_threshold = models.FloatField(default=0.7, help_text="Minimum confidence for authentication")
    
    # Liveness detection
    requires_liveness = models.BooleanField(default=True)
    liveness_score = models.FloatField(null=True, blank=True, help_text="Last liveness detection score")
    
    # Timestamps
    registered_at = models.DateTimeField(auto_now_add=True)
    last_used_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)
    expires_at = models.DateTimeField(null=True, blank=True, help_text="Biometric expiration date")
    
    # Usage statistics
    success_count = models.IntegerField(default=0)
    failure_count = models.IntegerField(default=0)
    
    class Meta:
        unique_together = ['user', 'biometric_type', 'device_id']
        ordering = ['-registered_at']
    
    def __str__(self):
        return f"{self.user.username} - {self.get_biometric_type_display()}"
    
    def is_expired(self):
        """Check if biometric data has expired"""
        if self.expires_at:
            return timezone.now() > self.expires_at
        return False
    
    def record_success(self):
        """Record successful authentication"""
        self.success_count += 1
        self.last_used_at = timezone.now()
        self.save()
    
    def record_failure(self):
        """Record failed authentication"""
        self.failure_count += 1
        self.save()


class MFAPolicy(models.Model):
    """Adaptive MFA policy based on risk assessment"""
    
    RISK_LEVELS = [
        ('low', 'Low Risk'),
        ('medium', 'Medium Risk'),
        ('high', 'High Risk'),
        ('critical', 'Critical Risk'),
    ]
    
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='mfa_policy')
    
    # Required factors by risk level
    low_risk_factors = models.IntegerField(default=1, help_text="Factors required for low risk")
    medium_risk_factors = models.IntegerField(default=2, help_text="Factors required for medium risk")
    high_risk_factors = models.IntegerField(default=3, help_text="Factors required for high risk")
    critical_risk_factors = models.IntegerField(default=3, help_text="Factors required for critical risk + admin approval")
    
    # Enabled authentication methods
    allow_password = models.BooleanField(default=True)
    allow_totp = models.BooleanField(default=True)
    allow_sms = models.BooleanField(default=True)
    allow_email = models.BooleanField(default=True)
    allow_passkey = models.BooleanField(default=True)
    allow_biometric_face = models.BooleanField(default=True)
    allow_biometric_voice = models.BooleanField(default=True)
    allow_push_notification = models.BooleanField(default=True)
    
    # Adaptive settings
    enable_adaptive_mfa = models.BooleanField(default=True, help_text="Automatically adjust factors based on risk")
    enable_continuous_auth = models.BooleanField(default=False, help_text="Enable continuous authentication")
    
    # Geofencing
    enable_geofencing = models.BooleanField(default=False)
    allowed_countries = models.JSONField(default=list, blank=True, help_text="List of allowed country codes")
    trusted_locations = models.JSONField(default=list, blank=True, help_text="List of trusted lat/lon coordinates")
    
    # Time-based restrictions
    enable_time_restrictions = models.BooleanField(default=False)
    allowed_hours = models.JSONField(default=dict, blank=True, help_text="Allowed hours by day of week")
    
    # Fallback options
    fallback_to_email = models.BooleanField(default=True, help_text="Allow email as fallback")
    fallback_to_recovery_codes = models.BooleanField(default=True)
    
    # Session settings
    max_session_duration_minutes = models.IntegerField(default=60)
    require_reauth_for_sensitive_ops = models.BooleanField(default=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"MFA Policy for {self.user.username}"
    
    def get_required_factors(self, risk_level: str) -> int:
        """Get number of required factors for a given risk level"""
        mapping = {
            'low': self.low_risk_factors,
            'medium': self.medium_risk_factors,
            'high': self.high_risk_factors,
            'critical': self.critical_risk_factors,
        }
        return mapping.get(risk_level, 2)
    
    def get_allowed_methods(self) -> list:
        """Get list of allowed authentication methods"""
        methods = []
        
        if self.allow_password:
            methods.append('password')
        if self.allow_totp:
            methods.append('totp')
        if self.allow_sms:
            methods.append('sms')
        if self.allow_email:
            methods.append('email')
        if self.allow_passkey:
            methods.append('passkey')
        if self.allow_biometric_face:
            methods.append('face')
        if self.allow_biometric_voice:
            methods.append('voice')
        if self.allow_push_notification:
            methods.append('push')
        
        return methods


class MFAFactor(models.Model):
    """Track individual MFA factors for a user"""
    
    FACTOR_TYPES = [
        ('password', 'Password'),
        ('totp', 'TOTP (Authenticator App)'),
        ('sms', 'SMS'),
        ('email', 'Email'),
        ('passkey', 'Passkey/WebAuthn'),
        ('face', 'Face Recognition'),
        ('voice', 'Voice Recognition'),
        ('fingerprint', 'Fingerprint'),
        ('push', 'Push Notification'),
        ('backup_code', 'Backup Code'),
    ]
    
    FACTOR_STATUS = [
        ('active', 'Active'),
        ('pending', 'Pending Setup'),
        ('suspended', 'Suspended'),
        ('revoked', 'Revoked'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='mfa_factors')
    factor_type = models.CharField(max_length=20, choices=FACTOR_TYPES)
    status = models.CharField(max_length=20, choices=FACTOR_STATUS, default='pending')
    
    # Factor-specific data
    factor_data = models.JSONField(default=dict, help_text="Encrypted factor-specific data")
    device_info = models.JSONField(default=dict, help_text="Device information")
    
    # Trust and reliability
    trust_score = models.FloatField(default=1.0, help_text="Factor reliability score (0-1)")
    is_primary = models.BooleanField(default=False, help_text="Primary authentication factor")
    
    # Usage tracking
    last_used_at = models.DateTimeField(null=True, blank=True)
    success_count = models.IntegerField(default=0)
    failure_count = models.IntegerField(default=0)
    
    # Timestamps
    registered_at = models.DateTimeField(auto_now_add=True)
    activated_at = models.DateTimeField(null=True, blank=True)
    suspended_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-is_primary', '-registered_at']
        unique_together = ['user', 'factor_type', 'device_info']
    
    def __str__(self):
        return f"{self.user.username} - {self.get_factor_type_display()} ({self.status})"
    
    def activate(self):
        """Activate this factor"""
        self.status = 'active'
        self.activated_at = timezone.now()
        self.save()
    
    def suspend(self):
        """Temporarily suspend this factor"""
        self.status = 'suspended'
        self.suspended_at = timezone.now()
        self.save()
    
    def revoke(self):
        """Permanently revoke this factor"""
        self.status = 'revoked'
        self.revoked_at = timezone.now()
        self.save()
    
    def record_success(self):
        """Record successful use of this factor"""
        self.success_count += 1
        self.last_used_at = timezone.now()
        # Increase trust score on successful use
        self.trust_score = min(1.0, self.trust_score + 0.01)
        self.save()
    
    def record_failure(self):
        """Record failed use of this factor"""
        self.failure_count += 1
        # Decrease trust score on failure
        self.trust_score = max(0.0, self.trust_score - 0.05)
        self.save()


class AuthenticationAttempt(models.Model):
    """Log all authentication attempts for security monitoring"""
    
    ATTEMPT_RESULTS = [
        ('success', 'Success'),
        ('failure', 'Failure'),
        ('partial', 'Partial Success'),
        ('blocked', 'Blocked'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='auth_attempts', null=True, blank=True)
    username = models.CharField(max_length=150, help_text="Attempted username")
    
    # Authentication details
    factors_used = models.JSONField(default=list, help_text="List of factors used")
    factors_required = models.IntegerField(default=1, help_text="Number of factors required")
    factors_completed = models.IntegerField(default=0, help_text="Number of factors successfully completed")
    
    result = models.CharField(max_length=20, choices=ATTEMPT_RESULTS)
    failure_reason = models.TextField(blank=True)
    
    # Risk assessment
    risk_level = models.CharField(max_length=20, default='low')
    risk_score = models.FloatField(default=0.0, help_text="ML-computed risk score (0-1)")
    anomaly_detected = models.BooleanField(default=False)
    anomaly_details = models.JSONField(default=dict, blank=True)
    
    # Context
    ip_address = models.GenericIPAddressField()
    user_agent = models.TextField()
    device_fingerprint = models.CharField(max_length=255, blank=True)
    location_data = models.JSONField(default=dict, blank=True)
    
    # Timestamps
    attempt_timestamp = models.DateTimeField(auto_now_add=True)
    duration_ms = models.IntegerField(default=0, help_text="Authentication duration in milliseconds")
    
    # Actions taken
    blocked_until = models.DateTimeField(null=True, blank=True, help_text="Account locked until")
    notification_sent = models.BooleanField(default=False)
    admin_notified = models.BooleanField(default=False)
    
    class Meta:
        ordering = ['-attempt_timestamp']
        indexes = [
            models.Index(fields=['user', '-attempt_timestamp']),
            models.Index(fields=['ip_address', '-attempt_timestamp']),
            models.Index(fields=['result', '-attempt_timestamp']),
        ]
    
    def __str__(self):
        return f"{self.username} - {self.result} at {self.attempt_timestamp}"
    
    @classmethod
    def get_recent_failures(cls, user, minutes=15):
        """Get recent failed attempts for a user"""
        since = timezone.now() - timedelta(minutes=minutes)
        return cls.objects.filter(
            user=user,
            result='failure',
            attempt_timestamp__gte=since
        ).count()
    
    @classmethod
    def is_user_blocked(cls, user):
        """Check if user is currently blocked"""
        latest_attempt = cls.objects.filter(user=user).first()
        
        if latest_attempt and latest_attempt.blocked_until:
            return timezone.now() < latest_attempt.blocked_until
        
        return False


class ContinuousAuthSession(models.Model):
    """Track continuous authentication sessions"""
    
    SESSION_STATUS = [
        ('active', 'Active'),
        ('challenged', 'Challenged'),
        ('terminated', 'Terminated'),
        ('expired', 'Expired'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='continuous_auth_sessions')
    session_id = models.CharField(max_length=255, unique=True)
    status = models.CharField(max_length=20, choices=SESSION_STATUS, default='active')
    
    # Continuous auth scores
    initial_auth_score = models.FloatField(default=1.0)
    current_auth_score = models.FloatField(default=1.0)
    min_auth_threshold = models.FloatField(default=0.6)
    
    # Biometric monitoring
    face_checks_count = models.IntegerField(default=0)
    voice_checks_count = models.IntegerField(default=0)
    behavioral_checks_count = models.IntegerField(default=0)
    
    # Session details
    device_fingerprint = models.CharField(max_length=255)
    ip_address = models.GenericIPAddressField()
    user_agent = models.TextField()
    
    # Timestamps
    started_at = models.DateTimeField(auto_now_add=True)
    last_check_at = models.DateTimeField(auto_now=True)
    challenged_at = models.DateTimeField(null=True, blank=True)
    terminated_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField()
    
    # Challenge details
    challenge_reason = models.TextField(blank=True)
    challenge_passed = models.BooleanField(default=False)
    
    class Meta:
        ordering = ['-started_at']
    
    def __str__(self):
        return f"{self.user.username} - Session {self.session_id[:8]} ({self.status})"
    
    def update_auth_score(self, new_score: float):
        """Update authentication score and check if re-auth needed"""
        self.current_auth_score = new_score
        self.last_check_at = timezone.now()
        
        if new_score < self.min_auth_threshold:
            self.challenge_session()
        
        self.save()
    
    def challenge_session(self):
        """Challenge the session for re-authentication"""
        self.status = 'challenged'
        self.challenged_at = timezone.now()
        self.save()
    
    def pass_challenge(self):
        """Mark challenge as passed"""
        self.status = 'active'
        self.challenge_passed = True
        self.current_auth_score = self.initial_auth_score
        self.save()
    
    def terminate(self, reason: str = ''):
        """Terminate the session"""
        self.status = 'terminated'
        self.terminated_at = timezone.now()
        if reason:
            self.challenge_reason = reason
        self.save()
    
    def is_expired(self):
        """Check if session has expired"""
        return timezone.now() > self.expires_at


class AdaptiveMFALog(models.Model):
    """Log adaptive MFA decisions for analysis and auditing"""
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='adaptive_mfa_logs')
    
    # Risk assessment
    calculated_risk_level = models.CharField(max_length=20)
    risk_factors = models.JSONField(default=list, help_text="Factors contributing to risk")
    ml_risk_score = models.FloatField(help_text="ML-computed risk score")
    
    # MFA decision
    factors_required = models.IntegerField()
    factors_available = models.JSONField(default=list)
    factors_selected = models.JSONField(default=list)
    
    # Context
    trigger_action = models.CharField(max_length=100, help_text="Action that triggered MFA")
    ip_address = models.GenericIPAddressField()
    device_fingerprint = models.CharField(max_length=255, blank=True)
    location = models.JSONField(default=dict, blank=True)
    
    # Outcome
    auth_successful = models.BooleanField(default=False)
    time_to_complete_seconds = models.IntegerField(default=0)
    
    # Timestamp
    timestamp = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-timestamp']
    
    def __str__(self):
        return f"{self.user.username} - {self.calculated_risk_level} risk at {self.timestamp}"


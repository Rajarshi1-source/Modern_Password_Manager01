"""
Military-Grade Duress Codes Models

This module provides models for sophisticated duress detection and response:
- Multiple duress codes for different threat levels
- Silent alarms to authorities
- Fake compliance mode (decoy vaults)
- Automatic evidence preservation
- Legal compliance features

Enterprise feature for high-risk users (executives, activists, whistleblowers).
"""

from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
import uuid
import hashlib


# =============================================================================
# Duress Configuration
# =============================================================================

class DuressCodeConfiguration(models.Model):
    """
    Per-user duress code configuration and settings.
    Controls overall duress protection behavior.
    """
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='duress_config'
    )
    
    # Feature toggles
    is_enabled = models.BooleanField(
        default=False,
        help_text="Master switch for duress protection"
    )
    threat_level_count = models.IntegerField(
        default=3,
        help_text="Number of threat levels (1-5)"
    )
    
    # Protection features
    evidence_preservation_enabled = models.BooleanField(
        default=True,
        help_text="Automatically preserve forensic evidence on duress"
    )
    silent_alarm_enabled = models.BooleanField(
        default=False,
        help_text="Send silent alerts to trusted authorities"
    )
    behavioral_detection_enabled = models.BooleanField(
        default=True,
        help_text="Use behavioral analysis to detect duress"
    )
    
    # Enterprise features
    legal_compliance_mode = models.BooleanField(
        default=False,
        help_text="Enable RFC 3161 timestamping and legal export"
    )
    is_enterprise = models.BooleanField(
        default=False,
        help_text="Enterprise tier with full features"
    )
    
    # Decoy settings
    auto_refresh_decoy = models.BooleanField(
        default=True,
        help_text="Automatically refresh decoy vault periodically"
    )
    decoy_refresh_interval_days = models.IntegerField(
        default=7,
        help_text="Days between decoy vault refreshes"
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_tested_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Last time user tested duress system"
    )
    
    class Meta:
        verbose_name = "Duress Configuration"
        verbose_name_plural = "Duress Configurations"
    
    def __str__(self):
        status = "enabled" if self.is_enabled else "disabled"
        return f"Duress Config for {self.user.username} ({status})"


# =============================================================================
# Duress Codes
# =============================================================================

class DuressCode(models.Model):
    """
    Individual duress codes with associated threat levels and actions.
    Each user can have multiple codes for different scenarios.
    """
    THREAT_LEVELS = [
        ('low', 'Low - Show Limited Decoy'),
        ('medium', 'Medium - Full Decoy + Preserve Evidence'),
        ('high', 'High - Decoy + Alert Authorities + Lock Real Vault'),
        ('critical', 'Critical - Full Response + Wipe Session Keys'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='duress_codes'
    )
    
    # Code storage (Argon2id hashed, never stored in plaintext)
    code_hash = models.CharField(
        max_length=256,
        help_text="Argon2id hash of the duress code"
    )
    code_hint = models.CharField(
        max_length=100,
        blank=True,
        help_text="Optional hint for the user (e.g., 'family emergency code')"
    )
    
    # Threat classification
    threat_level = models.CharField(
        max_length=20,
        choices=THREAT_LEVELS,
        default='medium'
    )
    
    # Custom action configuration
    action_config = models.JSONField(
        default=dict,
        help_text="Custom actions: {show_decoy: bool, alert_authorities: bool, ...}"
    )
    
    # Status
    is_active = models.BooleanField(default=True)
    activation_count = models.IntegerField(
        default=0,
        help_text="Number of times this code has been activated"
    )
    last_activated_at = models.DateTimeField(null=True, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Duress Code"
        verbose_name_plural = "Duress Codes"
        indexes = [
            models.Index(fields=['user', 'is_active']),
            models.Index(fields=['user', 'threat_level']),
        ]
    
    def __str__(self):
        return f"Duress Code ({self.threat_level}) for {self.user.username}"
    
    def get_default_actions(self):
        """Return default actions based on threat level"""
        defaults = {
            'low': {
                'show_decoy': True,
                'decoy_items_percent': 30,
                'preserve_evidence': False,
                'alert_authorities': False,
                'lock_real_vault': False,
            },
            'medium': {
                'show_decoy': True,
                'decoy_items_percent': 70,
                'preserve_evidence': True,
                'alert_authorities': False,
                'lock_real_vault': False,
            },
            'high': {
                'show_decoy': True,
                'decoy_items_percent': 100,
                'preserve_evidence': True,
                'alert_authorities': True,
                'lock_real_vault': True,
            },
            'critical': {
                'show_decoy': True,
                'decoy_items_percent': 100,
                'preserve_evidence': True,
                'alert_authorities': True,
                'lock_real_vault': True,
                'wipe_session_keys': True,
            },
        }
        return defaults.get(self.threat_level, defaults['medium'])


# =============================================================================
# Decoy Vault
# =============================================================================

class DecoyVault(models.Model):
    """
    Fake vault data shown when user enters a duress code.
    Contains realistic but harmless fake credentials.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='decoy_vaults'
    )
    
    # Threat level this decoy is for
    threat_level = models.CharField(
        max_length=20,
        choices=DuressCode.THREAT_LEVELS,
        default='medium'
    )
    
    # Decoy content (encrypted)
    decoy_items = models.JSONField(
        default=list,
        help_text="List of fake credential entries"
    )
    decoy_folders = models.JSONField(
        default=list,
        help_text="Folder structure for realism"
    )
    
    # Realism configuration
    item_count = models.IntegerField(
        default=0,
        help_text="Number of decoy items"
    )
    mirrors_real_structure = models.BooleanField(
        default=True,
        help_text="Mirrors real vault's folder structure"
    )
    includes_tracking_tokens = models.BooleanField(
        default=True,
        help_text="Embed tracking tokens in decoy credentials"
    )
    
    # Quality metrics
    realism_score = models.FloatField(
        default=0.0,
        help_text="AI-computed realism score (0-1)"
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    last_refreshed = models.DateTimeField(auto_now=True)
    last_accessed = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        verbose_name = "Decoy Vault"
        verbose_name_plural = "Decoy Vaults"
        unique_together = ['user', 'threat_level']
        indexes = [
            models.Index(fields=['user', 'threat_level']),
        ]
    
    def __str__(self):
        return f"Decoy Vault ({self.threat_level}) for {self.user.username}"


# =============================================================================
# Duress Events
# =============================================================================

class DuressEvent(models.Model):
    """
    Log of duress code activations.
    Records all details for forensic analysis.
    """
    EVENT_TYPES = [
        ('code_activated', 'Duress Code Activated'),
        ('behavioral_detected', 'Behavioral Duress Detected'),
        ('manual_trigger', 'Manual Panic Trigger'),
        ('test_activation', 'Test Activation'),
    ]
    
    RESPONSE_STATUS = [
        ('success', 'Response Executed Successfully'),
        ('partial', 'Partial Response (Some Actions Failed)'),
        ('failed', 'Response Failed'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='duress_events'
    )
    
    # Event details
    event_type = models.CharField(
        max_length=30,
        choices=EVENT_TYPES,
        default='code_activated'
    )
    duress_code = models.ForeignKey(
        DuressCode,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='events'
    )
    threat_level = models.CharField(
        max_length=20,
        choices=DuressCode.THREAT_LEVELS
    )
    
    # Context at time of event
    ip_address = models.GenericIPAddressField()
    user_agent = models.TextField(blank=True)
    device_fingerprint = models.JSONField(
        default=dict,
        help_text="Device identification data"
    )
    geo_location = models.JSONField(
        default=dict,
        help_text="Geolocation at time of event"
    )
    
    # Behavioral data
    behavioral_data = models.JSONField(
        default=dict,
        help_text="Stress indicators from DuressDetector"
    )
    behavioral_stress_score = models.FloatField(
        default=0.0,
        help_text="Stress score at time of event"
    )
    
    # Response tracking
    response_status = models.CharField(
        max_length=20,
        choices=RESPONSE_STATUS,
        default='success'
    )
    actions_taken = models.JSONField(
        default=list,
        help_text="List of actions executed"
    )
    
    # Alerts
    silent_alarm_sent = models.BooleanField(default=False)
    authorities_notified = models.JSONField(
        default=list,
        help_text="List of authorities notified"
    )
    
    # Evidence link
    evidence_package = models.ForeignKey(
        'EvidencePackage',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='duress_events'
    )
    
    # Timestamps
    timestamp = models.DateTimeField(auto_now_add=True)
    session_duration_seconds = models.IntegerField(
        default=0,
        help_text="Duration of duress session"
    )
    
    class Meta:
        verbose_name = "Duress Event"
        verbose_name_plural = "Duress Events"
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['user', 'timestamp']),
            models.Index(fields=['user', 'threat_level']),
            models.Index(fields=['event_type', 'timestamp']),
        ]
    
    def __str__(self):
        return f"Duress Event ({self.threat_level}) for {self.user.username} at {self.timestamp}"


# =============================================================================
# Evidence Package
# =============================================================================

class EvidencePackage(models.Model):
    """
    Preserved forensic evidence from duress events.
    Designed for legal admissibility.
    """
    EVIDENCE_STATUS = [
        ('collecting', 'Collecting Evidence'),
        ('complete', 'Evidence Complete'),
        ('exported', 'Exported for Legal Use'),
        ('sealed', 'Cryptographically Sealed'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='evidence_packages'
    )
    
    # Status
    status = models.CharField(
        max_length=20,
        choices=EVIDENCE_STATUS,
        default='collecting'
    )
    
    # Evidence components
    behavioral_snapshot = models.JSONField(
        default=dict,
        help_text="Behavioral biometrics at moment of duress"
    )
    device_info = models.JSONField(
        default=dict,
        help_text="Device fingerprint and hardware info"
    )
    network_info = models.JSONField(
        default=dict,
        help_text="Network details (IP, ISP, etc)"
    )
    geo_location = models.JSONField(
        default=dict,
        help_text="Geographic location data"
    )
    session_recording = models.JSONField(
        default=dict,
        help_text="Session activity since login"
    )
    
    # Encrypted evidence blob (for secure storage)
    encrypted_evidence_blob = models.BinaryField(
        null=True,
        blank=True,
        help_text="Full encrypted evidence package"
    )
    evidence_encryption_key_id = models.CharField(
        max_length=100,
        blank=True,
        help_text="Reference to encryption key (HSM)"
    )
    
    # Integrity verification
    evidence_hash = models.CharField(
        max_length=128,
        blank=True,
        help_text="SHA-512 hash of evidence"
    )
    
    # Legal compliance (RFC 3161 timestamping)
    legal_timestamp = models.DateTimeField(
        null=True,
        blank=True,
        help_text="RFC 3161 timestamp token time"
    )
    timestamp_authority = models.CharField(
        max_length=200,
        blank=True,
        help_text="TSA that issued timestamp"
    )
    timestamp_token = models.BinaryField(
        null=True,
        blank=True,
        help_text="RFC 3161 timestamp token"
    )
    
    # Chain of custody
    custody_log = models.JSONField(
        default=list,
        help_text="Log of evidence access/export"
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    sealed_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Evidence retention policy expiry"
    )
    
    class Meta:
        verbose_name = "Evidence Package"
        verbose_name_plural = "Evidence Packages"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'status']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        return f"Evidence Package {str(self.id)[:8]} for {self.user.username}"
    
    def compute_hash(self):
        """Compute SHA-512 hash of evidence components"""
        evidence_data = {
            'behavioral': self.behavioral_snapshot,
            'device': self.device_info,
            'network': self.network_info,
            'geo': self.geo_location,
            'session': self.session_recording,
        }
        evidence_str = str(sorted(evidence_data.items()))
        return hashlib.sha512(evidence_str.encode()).hexdigest()
    
    def add_custody_entry(self, action, actor, details=None):
        """Add entry to chain of custody log"""
        entry = {
            'timestamp': timezone.now().isoformat(),
            'action': action,
            'actor': actor,
            'details': details or {},
        }
        self.custody_log.append(entry)
        self.save(update_fields=['custody_log'])


# =============================================================================
# Trusted Authorities
# =============================================================================

class TrustedAuthority(models.Model):
    """
    Silent alarm recipients - trusted contacts who should be
    notified when duress is detected.
    """
    AUTHORITY_TYPES = [
        ('law_enforcement', 'Law Enforcement'),
        ('legal_counsel', 'Legal Counsel'),
        ('security_team', 'Corporate Security Team'),
        ('family', 'Family/Emergency Contact'),
        ('custom', 'Custom Contact'),
    ]
    
    CONTACT_METHODS = [
        ('email', 'Email'),
        ('sms', 'SMS'),
        ('phone', 'Phone Call'),
        ('webhook', 'Webhook/API'),
        ('signal', 'Signal Messenger'),
    ]
    
    VERIFICATION_STATUS = [
        ('pending', 'Verification Pending'),
        ('verified', 'Verified'),
        ('failed', 'Verification Failed'),
        ('expired', 'Verification Expired'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='trusted_authorities'
    )
    
    # Authority details
    name = models.CharField(max_length=200)
    authority_type = models.CharField(
        max_length=30,
        choices=AUTHORITY_TYPES
    )
    
    # Contact configuration
    contact_method = models.CharField(
        max_length=20,
        choices=CONTACT_METHODS,
        default='email'
    )
    contact_details = models.JSONField(
        help_text="Encrypted contact info: {email/phone/webhook_url}"
    )
    
    # Which threat levels trigger this authority
    trigger_threat_levels = models.JSONField(
        default=list,
        help_text="List of threat levels that trigger notification"
    )
    
    # Verification
    verification_status = models.CharField(
        max_length=20,
        choices=VERIFICATION_STATUS,
        default='pending'
    )
    verification_code = models.CharField(
        max_length=100,
        blank=True
    )
    verified_at = models.DateTimeField(null=True, blank=True)
    
    # Configuration
    delay_seconds = models.IntegerField(
        default=0,
        help_text="Delay before sending alert (stealth mode)"
    )
    include_location = models.BooleanField(
        default=True,
        help_text="Include location in alert"
    )
    include_evidence_link = models.BooleanField(
        default=False,
        help_text="Include link to evidence package"
    )
    
    # Status
    is_active = models.BooleanField(default=True)
    notification_count = models.IntegerField(default=0)
    last_notified_at = models.DateTimeField(null=True, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Trusted Authority"
        verbose_name_plural = "Trusted Authorities"
        indexes = [
            models.Index(fields=['user', 'is_active']),
            models.Index(fields=['user', 'authority_type']),
            models.Index(fields=['verification_status']),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.authority_type}) for {self.user.username}"
    
    def should_notify_for_level(self, threat_level):
        """Check if this authority should be notified for a threat level"""
        return threat_level in self.trigger_threat_levels

from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
import uuid

# Create your models here.

class UserDevice(models.Model):
    """Stores information about user devices for authentication verification"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='devices')
    device_id = models.UUIDField(default=uuid.uuid4, unique=True)
    device_name = models.CharField(max_length=255, blank=True)
    device_type = models.CharField(max_length=50, blank=True)  # mobile, desktop, tablet
    fingerprint = models.CharField(max_length=255, unique=True, blank=True)  # Device fingerprint
    browser = models.CharField(max_length=100, blank=True)
    os = models.CharField(max_length=100, blank=True)
    ip_address = models.GenericIPAddressField()
    is_trusted = models.BooleanField(default=False)
    last_seen = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['user', 'device_id']
        
    def __str__(self):
        return f"{self.device_name} - {self.user.username}"

class SocialMediaAccount(models.Model):
    """Stores user's social media accounts for protection"""
    PLATFORM_CHOICES = [
        ('facebook', 'Facebook'),
        ('twitter', 'Twitter/X'),
        ('instagram', 'Instagram'),
        ('linkedin', 'LinkedIn'),
        ('github', 'GitHub'),
        ('google', 'Google'),
        ('microsoft', 'Microsoft'),
        ('apple', 'Apple'),
    ]
    
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('locked', 'Locked'),
        ('suspended', 'Suspended'),
        ('monitoring', 'Under Monitoring'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='social_accounts')
    platform = models.CharField(max_length=20, choices=PLATFORM_CHOICES)
    username = models.CharField(max_length=255)
    email = models.EmailField(blank=True)
    account_id = models.CharField(max_length=255, blank=True)
    api_token = models.TextField(blank=True)  # Encrypted token for API access
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    auto_lock_enabled = models.BooleanField(default=True)
    last_checked = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['user', 'platform', 'username']
        
    def __str__(self):
        return f"{self.platform} - {self.username} ({self.user.username})"

class LoginAttempt(models.Model):
    """Tracks login attempts for security monitoring"""
    STATUS_CHOICES = [
        ('success', 'Success'),
        ('failed', 'Failed'),
        ('blocked', 'Blocked'),
        ('suspicious', 'Suspicious'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='login_attempts', null=True, blank=True)
    username_attempted = models.CharField(max_length=255)
    ip_address = models.GenericIPAddressField()
    device_fingerprint = models.CharField(max_length=255, blank=True)  # Device fingerprint
    user_agent = models.TextField()
    location = models.CharField(max_length=255, blank=True)
    device = models.ForeignKey(UserDevice, on_delete=models.SET_NULL, null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)
    failure_reason = models.CharField(max_length=255, blank=True)
    is_suspicious = models.BooleanField(default=False)
    threat_score = models.IntegerField(default=0)  # 0-100 risk score
    suspicious_factors = models.JSONField(default=dict, blank=True)  # Factors contributing to suspicion
    timestamp = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['user', 'timestamp']),
            models.Index(fields=['ip_address', 'timestamp']),
            models.Index(fields=['is_suspicious', 'timestamp']),
        ]
        
    def __str__(self):
        return f"Login attempt for {self.username_attempted} from {self.ip_address}"

class SecurityAlert(models.Model):
    """Security alerts and notifications"""
    ALERT_TYPES = [
        ('unauthorized_login', 'Unauthorized Login Attempt'),
        ('account_locked', 'Account Locked'),
        ('suspicious_activity', 'Suspicious Activity'),
        ('new_device', 'New Device Login'),
        ('location_anomaly', 'Unusual Location'),
        ('multiple_failures', 'Multiple Failed Attempts'),
    ]
    
    SEVERITY_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('critical', 'Critical'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='security_alerts')
    alert_type = models.CharField(max_length=30, choices=ALERT_TYPES)
    severity = models.CharField(max_length=10, choices=SEVERITY_CHOICES)
    title = models.CharField(max_length=255)
    message = models.TextField()
    data = models.JSONField(default=dict, blank=True)  # Additional alert data
    is_read = models.BooleanField(default=False)
    is_resolved = models.BooleanField(default=False)
    resolved_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
        
    def __str__(self):
        return f"{self.alert_type} - {self.user.username}"

class UserNotificationSettings(models.Model):
    """User preferences for security notifications"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='notification_settings')
    email_alerts = models.BooleanField(default=True)
    sms_alerts = models.BooleanField(default=False)
    push_alerts = models.BooleanField(default=True)
    alert_on_new_device = models.BooleanField(default=True)
    alert_on_new_location = models.BooleanField(default=True)
    alert_on_suspicious_activity = models.BooleanField(default=True)
    auto_lock_accounts = models.BooleanField(default=True)
    suspicious_activity_threshold = models.IntegerField(default=3)  # Number of failed attempts
    minimum_risk_score_for_alert = models.DecimalField(max_digits=5, decimal_places=2, default=0.7)
    alert_cooldown_minutes = models.IntegerField(default=15)  # Minimum time between alerts
    phone_number = models.CharField(max_length=20, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"Notification settings for {self.user.username}"

class AccountLockEvent(models.Model):
    """Tracks when accounts are locked/unlocked"""
    ACTION_CHOICES = [
        ('lock', 'Lock'),
        ('unlock', 'Unlock'),
        ('suspend', 'Suspend'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='lock_events')
    social_account = models.ForeignKey(SocialMediaAccount, on_delete=models.CASCADE, related_name='lock_events')
    action = models.CharField(max_length=10, choices=ACTION_CHOICES)
    reason = models.TextField()
    triggered_by_alert = models.ForeignKey(SecurityAlert, on_delete=models.SET_NULL, null=True, blank=True)
    auto_triggered = models.BooleanField(default=False)
    success = models.BooleanField(default=False)
    error_message = models.TextField(blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-timestamp']
        
    def __str__(self):
        return f"{self.action} {self.social_account.platform} for {self.user.username}"

class Notification(models.Model):
    NOTIFICATION_TYPES = [
        ('login_alert', 'Login Alert'),
        ('device_alert', 'New Device Alert'),
        ('location_alert', 'New Location Alert'),
        ('security_alert', 'Security Alert'),
    ]
    
    CHANNELS = [
        ('email', 'Email'),
        ('sms', 'SMS'),
        ('push', 'Push Notification'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    notification_type = models.CharField(max_length=50, choices=NOTIFICATION_TYPES)
    channel = models.CharField(max_length=20, choices=CHANNELS)
    content = models.TextField()
    related_event_id = models.IntegerField(null=True, blank=True)
    is_delivered = models.BooleanField(default=False)
    delivered_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.notification_type} for {self.user.username}"


# =============================================================================
# Quantum Random Number Generation Models
# =============================================================================

class QuantumEntropyBatch(models.Model):
    """
    Stores fetched quantum entropy batches for auditing.
    
    Tracks when quantum entropy was fetched and from which provider.
    """
    
    PROVIDER_CHOICES = [
        ('anu_qrng', 'ANU QRNG'),
        ('ibm_quantum', 'IBM Quantum'),
        ('ionq_quantum', 'IonQ Quantum'),
        ('cryptographic_fallback', 'Cryptographic Fallback'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    provider = models.CharField(max_length=50, choices=PROVIDER_CHOICES)
    bytes_fetched = models.IntegerField(help_text="Number of bytes fetched")
    fetched_at = models.DateTimeField(auto_now_add=True)
    circuit_id = models.CharField(max_length=100, null=True, blank=True,
                                   help_text="IBM/IonQ circuit execution ID")
    expires_at = models.DateTimeField(null=True, blank=True)
    
    # Metadata
    fetch_duration_ms = models.IntegerField(null=True, blank=True,
                                             help_text="Time taken to fetch in milliseconds")
    api_response_code = models.IntegerField(null=True, blank=True)
    
    class Meta:
        db_table = 'quantum_entropy_batch'
        verbose_name = 'Quantum Entropy Batch'
        verbose_name_plural = 'Quantum Entropy Batches'
        ordering = ['-fetched_at']
    
    def __str__(self):
        return f"{self.provider}: {self.bytes_fetched} bytes @ {self.fetched_at}"


class QuantumPasswordCertificate(models.Model):
    """
    Proof of quantum origin for passwords.
    
    Stores cryptographically signed certificates proving a password
    was generated using true quantum randomness.
    """
    
    QUANTUM_SOURCES = [
        ('vacuum_fluctuations', 'Vacuum Fluctuations (ANU)'),
        ('superconducting_qubit_superposition', 'Superconducting Qubit Superposition (IBM)'),
        ('trapped_ion_superposition', 'Trapped Ion Superposition (IonQ)'),
        ('cryptographic_prng', 'Cryptographic PRNG (Fallback)'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, 
                             related_name='quantum_certificates')
    
    # Certificate details
    password_hash_prefix = models.CharField(max_length=64,
                                             help_text="First 16 chars of SHA256 hash")
    provider = models.CharField(max_length=50)
    quantum_source = models.CharField(max_length=100, choices=QUANTUM_SOURCES)
    entropy_bits = models.IntegerField(help_text="Bits of quantum entropy used")
    circuit_id = models.CharField(max_length=100, null=True, blank=True,
                                   help_text="Quantum circuit execution ID")
    
    # Timestamps
    generation_timestamp = models.DateTimeField(auto_now_add=True)
    
    # Cryptographic signature
    signature = models.CharField(max_length=256)
    
    # Optional: Link to vault item
    vault_item_id = models.CharField(max_length=100, null=True, blank=True)
    
    class Meta:
        db_table = 'quantum_password_certificate'
        verbose_name = 'Quantum Password Certificate'
        verbose_name_plural = 'Quantum Password Certificates'
        ordering = ['-generation_timestamp']
        indexes = [
            models.Index(fields=['user', '-generation_timestamp']),
            models.Index(fields=['password_hash_prefix']),
        ]
    
    def __str__(self):
        return f"QC-{str(self.id)[:8]} ({self.provider})"
    
    def to_dict(self):
        """Convert to dictionary for API responses."""
        return {
            'certificate_id': str(self.id),
            'password_hash_prefix': self.password_hash_prefix,
            'provider': self.provider,
            'quantum_source': self.quantum_source,
            'entropy_bits': self.entropy_bits,
            'circuit_id': self.circuit_id,
            'generation_timestamp': self.generation_timestamp.isoformat(),
            'signature': self.signature,
        }


class QuantumPoolStatus(models.Model):
    """
    Tracks quantum entropy pool health over time.
    
    Used for monitoring and alerting on pool depletion.
    """
    
    HEALTH_CHOICES = [
        ('good', 'Good'),
        ('low', 'Low'),
        ('critical', 'Critical'),
        ('empty', 'Empty'),
    ]
    
    id = models.AutoField(primary_key=True)
    recorded_at = models.DateTimeField(auto_now_add=True)
    total_bytes_available = models.IntegerField()
    batch_count = models.IntegerField()
    health = models.CharField(max_length=20, choices=HEALTH_CHOICES)
    
    # Provider availability
    anu_available = models.BooleanField(default=True)
    ibm_available = models.BooleanField(default=False)
    ionq_available = models.BooleanField(default=False)
    
    class Meta:
        db_table = 'quantum_pool_status'
        verbose_name = 'Quantum Pool Status'
        verbose_name_plural = 'Quantum Pool Statuses'
        ordering = ['-recorded_at']
    
    def __str__(self):
        return f"{self.health}: {self.total_bytes_available} bytes @ {self.recorded_at}"


# =============================================================================
# Genetic Password Evolution Models
# =============================================================================

class GeneticSubscription(models.Model):
    """
    Manages genetic/epigenetic feature subscriptions.
    
    - Basic features: Free for 1 month for new users
    - Epigenetic Evolution: Premium (subscription required)
    """
    
    TIER_CHOICES = [
        ('trial', 'Free Trial'),
        ('basic', 'Basic'),
        ('premium', 'Premium'),
        ('enterprise', 'Enterprise'),
    ]
    
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('expired', 'Expired'),
        ('cancelled', 'Cancelled'),
        ('pending', 'Pending'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(User, on_delete=models.CASCADE,
                                 related_name='genetic_subscription')
    tier = models.CharField(max_length=20, choices=TIER_CHOICES, default='trial')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    
    # Trial and subscription dates
    trial_started_at = models.DateTimeField(auto_now_add=True)
    trial_expires_at = models.DateTimeField(null=True, blank=True)
    subscription_started_at = models.DateTimeField(null=True, blank=True)
    subscription_expires_at = models.DateTimeField(null=True, blank=True)
    
    # Feature flags
    epigenetic_evolution_enabled = models.BooleanField(default=False,
        help_text="Premium feature: epigenetic password evolution")
    quantum_combination_enabled = models.BooleanField(default=True,
        help_text="Combine genetic seed with quantum entropy")
    
    # Usage tracking
    passwords_generated = models.IntegerField(default=0)
    evolutions_triggered = models.IntegerField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'genetic_subscription'
        verbose_name = 'Genetic Subscription'
    
    def __str__(self):
        return f"{self.user.username}: {self.tier} ({self.status})"
    
    def is_trial_active(self):
        """Check if trial period is still active."""
        if self.tier != 'trial':
            return False
        if self.trial_expires_at is None:
            return True
        return timezone.now() < self.trial_expires_at
    
    def is_premium_active(self):
        """Check if premium subscription is active."""
        if self.tier in ['premium', 'enterprise'] and self.status == 'active':
            if self.subscription_expires_at is None:
                return True
            return timezone.now() < self.subscription_expires_at
        return False
    
    def can_use_epigenetic(self):
        """Check if user can use epigenetic evolution feature."""
        return self.epigenetic_evolution_enabled and (
            self.is_premium_active() or self.is_trial_active()
        )
    
    def save(self, *args, **kwargs):
        # Set trial expiry to 1 month from creation for new users
        if not self.trial_expires_at and self.tier == 'trial':
            from datetime import timedelta
            self.trial_expires_at = timezone.now() + timedelta(days=30)
            # Enable all features during trial
            self.epigenetic_evolution_enabled = True
        super().save(*args, **kwargs)


class DNAConnection(models.Model):
    """
    Stores user's DNA provider connection.
    
    PRIVACY: Only stores encrypted OAuth tokens.
    Raw genetic data is NEVER stored - only cryptographic hashes.
    """
    
    PROVIDER_CHOICES = [
        ('sequencing', 'Sequencing.com'),
        ('23andme', '23andMe'),
        ('ancestry', 'AncestryDNA'),
        ('manual', 'Manual Upload'),
    ]
    
    CONNECTION_STATUS = [
        ('pending', 'Pending Authorization'),
        ('connected', 'Connected'),
        ('expired', 'Token Expired'),
        ('revoked', 'Access Revoked'),
        ('error', 'Connection Error'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(User, on_delete=models.CASCADE, 
                                 related_name='dna_connection')
    provider = models.CharField(max_length=50, choices=PROVIDER_CHOICES)
    status = models.CharField(max_length=20, choices=CONNECTION_STATUS, default='pending')
    
    # Encrypted OAuth tokens (encrypted with user's key)
    access_token_encrypted = models.BinaryField(null=True, blank=True)
    refresh_token_encrypted = models.BinaryField(null=True, blank=True)
    token_expires_at = models.DateTimeField(null=True, blank=True)
    
    # Genetic hash (NOT raw data - only hash prefix for verification)
    genetic_hash_prefix = models.CharField(max_length=64, blank=True,
        help_text="First 32 chars of genetic seed hash for verification")
    genetic_seed_salt = models.BinaryField(null=True, blank=True,
        help_text="Salt used for genetic seed derivation")
    snp_count = models.IntegerField(default=0,
        help_text="Number of SNPs used in seed generation")
    
    # Epigenetic tracking (Premium feature)
    last_biological_age = models.FloatField(null=True, blank=True)
    last_epigenetic_update = models.DateTimeField(null=True, blank=True)
    evolution_generation = models.IntegerField(default=1,
        help_text="Current password evolution generation")
    
    # User consent record
    consent_given_at = models.DateTimeField(null=True, blank=True)
    consent_version = models.CharField(max_length=20, default='1.0')
    gdpr_consent = models.BooleanField(default=False)
    
    # Metadata
    connected_at = models.DateTimeField(null=True, blank=True)
    last_sync = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    
    # User preference: combine with quantum
    combine_with_quantum = models.BooleanField(default=True,
        help_text="Whether to combine genetic seed with quantum entropy")
    
    class Meta:
        db_table = 'dna_connection'
        verbose_name = 'DNA Connection'
        verbose_name_plural = 'DNA Connections'
    
    def __str__(self):
        return f"{self.user.username}: {self.provider} ({self.status})"
    
    def is_token_valid(self):
        """Check if OAuth token is still valid."""
        if self.status != 'connected':
            return False
        if self.token_expires_at is None:
            return True
        return timezone.now() < self.token_expires_at


class GeneticPasswordCertificate(models.Model):
    """
    Proof of genetic origin for passwords.
    
    Similar to QuantumPasswordCertificate but includes
    genetic and epigenetic information.
    """
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE,
                             related_name='genetic_certificates')
    
    # Password reference (hash prefix only for verification)
    password_hash_prefix = models.CharField(max_length=64,
        help_text="First 16 chars of SHA256 hash")
    
    # Genetic verification
    genetic_hash_prefix = models.CharField(max_length=64,
        help_text="First 16 chars of genetic seed hash")
    provider = models.CharField(max_length=50)
    snp_markers_used = models.IntegerField()
    
    # Epigenetic evolution tracking
    epigenetic_age = models.FloatField(null=True, blank=True,
        help_text="Biological age at generation time")
    evolution_generation = models.IntegerField(default=1,
        help_text="Password evolution generation number")
    
    # Quantum combination (optional based on user preference)
    combined_with_quantum = models.BooleanField(default=True)
    quantum_certificate_id = models.UUIDField(null=True, blank=True,
        help_text="Reference to quantum certificate if combined")
    
    # Certificate metadata
    password_length = models.IntegerField()
    charset_used = models.CharField(max_length=100, default='standard',
        help_text="Character types used: uppercase,lowercase,numbers,symbols")
    entropy_bits = models.IntegerField(default=0,
        help_text="Estimated entropy bits")
    
    # Timestamps and signature
    generation_timestamp = models.DateTimeField(auto_now_add=True)
    signature = models.CharField(max_length=256)
    
    # Optional link to vault item
    vault_item_id = models.CharField(max_length=100, null=True, blank=True)
    
    class Meta:
        db_table = 'genetic_password_certificate'
        verbose_name = 'Genetic Password Certificate'
        verbose_name_plural = 'Genetic Password Certificates'
        ordering = ['-generation_timestamp']
        indexes = [
            models.Index(fields=['user', '-generation_timestamp']),
            models.Index(fields=['genetic_hash_prefix']),
            models.Index(fields=['evolution_generation']),
        ]
    
    def __str__(self):
        return f"GC-{str(self.id)[:8]} ({self.provider}, gen {self.evolution_generation})"
    
    def to_dict(self):
        """Convert to dictionary for API responses."""
        return {
            'certificate_id': str(self.id),
            'password_hash_prefix': self.password_hash_prefix,
            'genetic_hash_prefix': self.genetic_hash_prefix,
            'provider': self.provider,
            'snp_markers_used': self.snp_markers_used,
            'epigenetic_age': self.epigenetic_age,
            'evolution_generation': self.evolution_generation,
            'combined_with_quantum': self.combined_with_quantum,
            'quantum_certificate_id': str(self.quantum_certificate_id) if self.quantum_certificate_id else None,
            'password_length': self.password_length,
            'entropy_bits': self.entropy_bits,
            'generation_timestamp': self.generation_timestamp.isoformat(),
            'signature': self.signature,
        }


class GeneticEvolutionLog(models.Model):
    """
    Tracks password evolution events (Premium feature).
    
    Records when passwords "evolve" due to epigenetic changes.
    """
    
    TRIGGER_CHOICES = [
        ('automatic', 'Automatic (Biological Age Change)'),
        ('manual', 'Manual User Trigger'),
        ('scheduled', 'Scheduled Evolution'),
    ]
    
    id = models.AutoField(primary_key=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE,
                             related_name='evolution_logs')
    
    # Evolution details
    trigger_type = models.CharField(max_length=20, choices=TRIGGER_CHOICES, default='automatic')
    old_evolution_gen = models.IntegerField()
    new_evolution_gen = models.IntegerField()
    old_biological_age = models.FloatField(null=True, blank=True)
    new_biological_age = models.FloatField(null=True, blank=True)
    
    # Affected passwords (count only for privacy)
    passwords_evolved = models.IntegerField(default=0)
    
    # Status
    success = models.BooleanField(default=True)
    error_message = models.TextField(blank=True)
    
    triggered_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'genetic_evolution_log'
        verbose_name = 'Genetic Evolution Log'
        verbose_name_plural = 'Genetic Evolution Logs'
        ordering = ['-triggered_at']
    
    def __str__(self):
        return f"Evolution {self.old_evolution_gen}→{self.new_evolution_gen} @ {self.triggered_at}"


class DNAConsentRecord(models.Model):
    """
    Stores explicit consent records for GDPR compliance.
    
    Required for handling genetic data under GDPR Article 9.
    """
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE,
                             related_name='dna_consent_records')
    
    # Consent details
    consent_type = models.CharField(max_length=50,
        help_text="Type: genetic_processing, epigenetic_updates, data_sharing")
    consent_version = models.CharField(max_length=20)
    consent_text_hash = models.CharField(max_length=64,
        help_text="Hash of consent text at time of agreement")
    
    # Consent status
    consented = models.BooleanField(default=False)
    consented_at = models.DateTimeField(null=True, blank=True)
    withdrawn_at = models.DateTimeField(null=True, blank=True)
    
    # Metadata
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    
    class Meta:
        db_table = 'dna_consent_record'
        verbose_name = 'DNA Consent Record'
        verbose_name_plural = 'DNA Consent Records'
        unique_together = ['user', 'consent_type', 'consent_version']
    
    def __str__(self):
        status = "Consented" if self.consented else "Withdrawn"
        return f"{self.user.username}: {self.consent_type} ({status})"


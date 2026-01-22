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


# =============================================================================
# Chemical Password Storage Models
# =============================================================================

class ChemicalStorageSubscription(models.Model):
    """
    Subscription for chemical password storage features.
    
    Tiers:
    - free: Demo mode, 1 password, no real synthesis
    - enterprise: Real synthesis, physical storage, retrieval
    """
    
    TIER_CHOICES = [
        ('free', 'Free (Demo)'),
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
                                 related_name='chemical_subscription')
    tier = models.CharField(max_length=20, choices=TIER_CHOICES, default='free')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    
    # Lab provider preference
    lab_provider = models.CharField(max_length=50, default='mock',
        help_text="Preferred lab provider: mock, twist, idt, genscript")
    
    # Usage limits
    max_passwords = models.IntegerField(default=1)
    passwords_stored = models.IntegerField(default=0)
    synthesis_credits = models.IntegerField(default=0,
        help_text="Pre-paid synthesis credits in base pairs")
    
    # Subscription dates
    started_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    
    # Feature flags
    real_synthesis_enabled = models.BooleanField(default=False)
    physical_storage_enabled = models.BooleanField(default=False)
    time_lock_enabled = models.BooleanField(default=True)
    lab_integration_enabled = models.BooleanField(default=False,
        help_text="Alias for real_synthesis_enabled for compatibility")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'chemical_storage_subscription'
        verbose_name = 'Chemical Storage Subscription'
    
    def __str__(self):
        return f"{self.user.username}: {self.tier} ({self.status})"
    
    def can_store_password(self):
        """Check if user can store another password."""
        return self.passwords_stored < self.max_passwords
    
    def is_active(self):
        """Check if subscription is active."""
        if self.status != 'active':
            return False
        if self.expires_at and timezone.now() > self.expires_at:
            return False
        return True


class DNAEncodedPassword(models.Model):
    """
    Tracks passwords stored as DNA sequences.
    
    PRIVACY: Never stores actual DNA sequence or password.
    Only stores hashes and references.
    """
    
    STATUS_CHOICES = [
        ('encoded', 'Encoded (Digital Only)'),
        ('synthesis_pending', 'Synthesis Pending'),
        ('synthesis_complete', 'Synthesis Complete'),
        ('in_storage', 'In Physical Storage'),
        ('retrieval_pending', 'Retrieval Pending'),
        ('retrieved', 'Retrieved'),
        ('expired', 'Expired'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE,
                             related_name='dna_encoded_passwords')
    
    # Service identification
    service_name = models.CharField(max_length=255, blank=True, default='',
        help_text="Name of the service/account this password is for")
    notes = models.TextField(blank=True, default='',
        help_text="Optional notes about this stored password")
    
    # References (no actual data stored)
    sequence_hash = models.CharField(max_length=64,
        help_text="SHA-256 of DNA sequence")
    password_hash_prefix = models.CharField(max_length=16,
        help_text="First 16 chars of password hash for verification")
    
    # Encoding details
    sequence_length_bp = models.IntegerField(
        help_text="DNA sequence length in base pairs")
    gc_content = models.FloatField(
        help_text="GC content percentage (0.0-1.0)")
    has_error_correction = models.BooleanField(default=True)
    encoding_version = models.CharField(max_length=20, default='v1')
    
    # Synthesis tracking
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='encoded')
    synthesis_order_id = models.CharField(max_length=100, null=True, blank=True)
    synthesis_provider = models.CharField(max_length=50, null=True, blank=True)
    synthesis_cost_usd = models.DecimalField(max_digits=10, decimal_places=2,
                                              null=True, blank=True)
    
    # Physical storage
    physical_sample_id = models.CharField(max_length=100, null=True, blank=True,
        help_text="ID of physical DNA sample in storage")
    storage_location = models.CharField(max_length=255, null=True, blank=True)
    storage_temperature_kelvin = models.FloatField(null=True, blank=True)
    
    # Time-lock (optional)
    time_lock_enabled = models.BooleanField(default=False)
    time_lock_capsule_id = models.CharField(max_length=100, null=True, blank=True)
    time_lock_unlock_at = models.DateTimeField(null=True, blank=True)
    
    # QR backup
    qr_backup_generated = models.BooleanField(default=False)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_accessed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'dna_encoded_password'
        verbose_name = 'DNA Encoded Password'
        verbose_name_plural = 'DNA Encoded Passwords'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'status']),
            models.Index(fields=['sequence_hash']),
            models.Index(fields=['synthesis_order_id']),
        ]
    
    def __str__(self):
        return f"DNA-{str(self.id)[:8]} ({self.status})"


class TimeLockCapsule(models.Model):
    """
    Server-enforced time-lock capsule for delayed password access.
    
    User cannot skip ahead - server releases password only after delay.
    Perfect for emergency access, dead man's switch functionality.
    """
    
    MODE_CHOICES = [
        ('server', 'Server Enforced'),
        ('client', 'Client Solvable'),
        ('hybrid', 'Hybrid (Both)'),
    ]
    
    STATUS_CHOICES = [
        ('locked', 'Locked'),
        ('solving', 'Solving'),
        ('unlocked', 'Unlocked'),
        ('cancelled', 'Cancelled'),
        ('expired', 'Expired'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE,
                             related_name='time_lock_capsules')
    
    # Capsule data (encrypted)
    encrypted_data = models.BinaryField(
        help_text="AES-encrypted password data")
    encryption_key_encrypted = models.BinaryField(
        help_text="Encryption key, encrypted with master key")
    
    # Time-lock configuration
    mode = models.CharField(max_length=20, choices=MODE_CHOICES, default='server')
    delay_seconds = models.IntegerField(
        help_text="Original delay in seconds")
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='locked')
    created_at = models.DateTimeField(auto_now_add=True)
    unlock_at = models.DateTimeField()
    unlocked_at = models.DateTimeField(null=True, blank=True)
    
    # Beneficiary (for emergency access)
    beneficiary_email = models.EmailField(null=True, blank=True,
        help_text="Email to notify when capsule unlocks")
    requires_verification = models.BooleanField(default=True,
        help_text="Require identity verification to unlock")
    
    # Client puzzle data (for client mode)
    puzzle_data = models.JSONField(null=True, blank=True,
        help_text="RSA puzzle parameters for client-side solving")
    
    class Meta:
        db_table = 'time_lock_capsule'
        verbose_name = 'Time-Lock Capsule'
        verbose_name_plural = 'Time-Lock Capsules'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Capsule-{str(self.id)[:8]} ({self.status})"
    
    def is_unlockable(self):
        """Check if capsule can be unlocked."""
        if self.status != 'locked':
            return False
        return timezone.now() >= self.unlock_at
    
    def time_remaining(self):
        """Get remaining time until unlock."""
        if self.status != 'locked':
            return 0
        delta = self.unlock_at - timezone.now()
        return max(0, int(delta.total_seconds()))


class ChemicalStorageCertificate(models.Model):
    """
    Certificate proving chemical storage of password.
    
    Provides audit trail and verification for compliance.
    """
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE,
                             related_name='chemical_certificates')
    dna_password = models.ForeignKey(DNAEncodedPassword, on_delete=models.CASCADE,
                                      related_name='certificates', null=True, blank=True)
    
    # Certificate details
    sequence_hash = models.CharField(max_length=64)
    encoding_method = models.CharField(max_length=50, default='huffman_nucleotide_v1')
    error_correction_level = models.CharField(max_length=20, default='high')
    
    # Synthesis info
    synthesis_provider = models.CharField(max_length=50, null=True, blank=True)
    synthesis_date = models.DateTimeField(null=True, blank=True)
    
    # Storage conditions
    storage_temperature_kelvin = models.FloatField(default=193.15,
        help_text="-80°C in Kelvin")
    estimated_half_life_years = models.IntegerField(default=1000)
    
    # Time-lock info
    time_lock_enabled = models.BooleanField(default=False)
    time_lock_mode = models.CharField(max_length=20, null=True, blank=True)
    
    # Cryptographic signature
    signature = models.CharField(max_length=256)
    
    # Chain of custody (for enterprise)
    chain_of_custody = models.JSONField(default=list, blank=True,
        help_text="Custody transfer records")
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'chemical_storage_certificate'
        verbose_name = 'Chemical Storage Certificate'
        verbose_name_plural = 'Chemical Storage Certificates'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Cert-{str(self.id)[:8]}"
    
    def to_dict(self):
        """Convert to dictionary for PDF/API."""
        return {
            'certificate_id': str(self.id),
            'sequence_hash': self.sequence_hash,
            'encoding_method': self.encoding_method,
            'error_correction': self.error_correction_level,
            'synthesis_provider': self.synthesis_provider,
            'synthesis_date': self.synthesis_date.isoformat() if self.synthesis_date else None,
            'storage_temp_kelvin': self.storage_temperature_kelvin,
            'half_life_years': self.estimated_half_life_years,
            'time_lock': self.time_lock_enabled,
            'signature': self.signature,
            'created_at': self.created_at.isoformat(),
        }


# =============================================================================
# Epigenetic Password Adaptation Models
# =============================================================================

class AdaptivePasswordConfig(models.Model):
    """
    User configuration for adaptive password feature.
    
    Privacy-first: Opt-in by default (is_enabled=False).
    All pattern collection requires explicit user consent.
    """
    
    user = models.OneToOneField(User, on_delete=models.CASCADE,
                                 related_name='adaptive_password_config')
    
    # Consent and enablement (OPT-IN, default OFF)
    is_enabled = models.BooleanField(
        default=False,
        help_text="User consent for typing pattern collection (opt-in)"
    )
    consent_given_at = models.DateTimeField(null=True, blank=True,
        help_text="When user explicitly enabled adaptive passwords")
    consent_version = models.CharField(max_length=20, default='1.0')
    
    # Adaptation frequency (30-60 days with adaptive scheduling)
    suggestion_frequency_days = models.IntegerField(
        default=30,
        help_text="Days between adaptation suggestions (1-365)"
    )
    last_suggestion_at = models.DateTimeField(null=True, blank=True)
    
    # ML training preferences
    allow_centralized_training = models.BooleanField(
        default=True,
        help_text="Allow anonymized data for model improvement (with DP)"
    )
    allow_federated_learning = models.BooleanField(
        default=False,
        help_text="Use on-device training only (more private, opt-in)"
    )
    
    # Privacy settings
    differential_privacy_epsilon = models.FloatField(
        default=0.5,
        help_text="DP epsilon value (0.1=strong, 1.0=weak, 0.5=balanced)"
    )
    
    # Feature toggles
    auto_suggest_enabled = models.BooleanField(
        default=True,
        help_text="Automatically show adaptation suggestions"
    )
    typing_timing_enabled = models.BooleanField(
        default=True,
        help_text="Collect timing patterns (for rhythm analysis)"
    )
    error_position_enabled = models.BooleanField(
        default=True,
        help_text="Track error positions (for difficulty detection)"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'adaptive_password_config'
        verbose_name = 'Adaptive Password Config'
    
    def __str__(self):
        status = "Enabled" if self.is_enabled else "Disabled"
        return f"{self.user.username}: Adaptive Passwords ({status})"
    
    def should_suggest_adaptation(self):
        """Check if it's time to suggest a new adaptation."""
        if not self.is_enabled:
            return False
        if self.last_suggestion_at is None:
            return True
        days_since = (timezone.now() - self.last_suggestion_at).days
        return days_since >= self.suggestion_frequency_days


class TypingSession(models.Model):
    """
    Records typing attempt metadata.
    
    PRIVACY: Never stores raw keystrokes!
    Only stores:
    - Error positions (which positions had typos)
    - Timing profile (anonymized inter-key delays)
    - Success/failure status
    """
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE,
                             related_name='typing_sessions')
    
    # Password reference (hash prefix only, never actual password)
    password_hash_prefix = models.CharField(max_length=16,
        help_text="First 16 chars of password hash for correlation")
    password_length = models.IntegerField(
        help_text="Length of password (for position normalization)")
    
    # Session outcome
    success = models.BooleanField(
        help_text="Whether password was entered correctly")
    attempt_number = models.IntegerField(default=1,
        help_text="Which attempt this was (1st, 2nd, etc.)")
    
    # Error data (positions only, never characters)
    error_positions = models.JSONField(
        default=list,
        help_text="List of positions where errors occurred (0-indexed)"
    )
    error_count = models.IntegerField(default=0)
    
    # Timing profile (anonymized, normalized)
    timing_profile = models.JSONField(
        default=dict,
        help_text="Anonymized timing: {position: relative_delay_bucket}"
    )
    total_time_ms = models.IntegerField(null=True, blank=True,
        help_text="Total time to enter password in milliseconds")
    
    # Device context (for cross-device learning)
    device_type = models.CharField(max_length=20, default='desktop',
        help_text="desktop, mobile, tablet")
    input_method = models.CharField(max_length=20, default='keyboard',
        help_text="keyboard, touchscreen, voice")
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'typing_session'
        verbose_name = 'Typing Session'
        verbose_name_plural = 'Typing Sessions'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['password_hash_prefix', '-created_at']),
        ]
    
    def __str__(self):
        status = "✓" if self.success else "✗"
        return f"{status} Session for {self.user.username} @ {self.created_at}"


class PasswordAdaptation(models.Model):
    """
    Tracks password evolution/adaptation history.
    
    Implements linked list for FULL ROLLBACK support.
    Each adaptation can be rolled back to previous version.
    """
    
    ADAPTATION_TYPES = [
        ('substitution', 'Character Substitution'),
        ('reorder', 'Character Reordering'),
        ('simplify', 'Simplification'),
        ('hybrid', 'Hybrid (Multiple)'),
    ]
    
    STATUS_CHOICES = [
        ('suggested', 'Suggested'),
        ('accepted', 'Accepted'),
        ('rejected', 'Rejected'),
        ('active', 'Active'),
        ('rolled_back', 'Rolled Back'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE,
                             related_name='password_adaptations')
    
    # Password reference
    password_hash_prefix = models.CharField(max_length=16,
        help_text="Hash prefix of ORIGINAL password")
    adapted_hash_prefix = models.CharField(max_length=16,
        help_text="Hash prefix of ADAPTED password")
    
    # Linked list for rollback
    previous_adaptation = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='next_adaptations',
        help_text="Previous adaptation (for rollback chain)"
    )
    adaptation_generation = models.IntegerField(default=1,
        help_text="Generation number in adaptation chain")
    
    # Adaptation details
    adaptation_type = models.CharField(max_length=20, choices=ADAPTATION_TYPES)
    substitutions_applied = models.JSONField(
        default=dict,
        help_text="Map of substitutions: {position: {from: 'a', to: '@'}}"
    )
    
    # ML confidence
    confidence_score = models.FloatField(
        help_text="ML model confidence (0.0-1.0)")
    memorability_score_before = models.FloatField(null=True, blank=True)
    memorability_score_after = models.FloatField(null=True, blank=True)
    
    # Status tracking
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, 
                               default='suggested')
    suggested_at = models.DateTimeField(auto_now_add=True)
    decided_at = models.DateTimeField(null=True, blank=True,
        help_text="When user accepted/rejected")
    rolled_back_at = models.DateTimeField(null=True, blank=True)
    
    # Reason for suggestion
    reason = models.TextField(blank=True,
        help_text="Human-readable reason for this adaptation")
    
    class Meta:
        db_table = 'password_adaptation'
        verbose_name = 'Password Adaptation'
        verbose_name_plural = 'Password Adaptations'
        ordering = ['-suggested_at']
        indexes = [
            models.Index(fields=['user', 'status']),
            models.Index(fields=['password_hash_prefix']),
        ]
    
    def __str__(self):
        return f"Adaptation gen{self.adaptation_generation} ({self.status}) - {self.user.username}"
    
    def can_rollback(self):
        """Check if this adaptation can be rolled back."""
        return self.status == 'active' and self.previous_adaptation is not None
    
    def get_rollback_chain(self):
        """Get full rollback chain as list."""
        chain = [self]
        current = self.previous_adaptation
        while current:
            chain.append(current)
            current = current.previous_adaptation
        return chain


class UserTypingProfile(models.Model):
    """
    Aggregated typing characteristics for a user.
    
    PRIVACY: This is an AGGREGATED profile, not raw data.
    Built from many typing sessions using differential privacy.
    """
    
    user = models.OneToOneField(User, on_delete=models.CASCADE,
                                 related_name='typing_profile')
    
    # Preferred substitutions (learned from patterns)
    preferred_substitutions = models.JSONField(
        default=dict,
        help_text="Learned substitutions: {'o': '0', 'a': '@', 'e': '3'}"
    )
    substitution_confidence = models.JSONField(
        default=dict,
        help_text="Confidence per substitution: {'o->0': 0.85}"
    )
    
    # Typing speed characteristics
    average_wpm = models.FloatField(
        null=True, blank=True,
        help_text="Average words per minute"
    )
    wpm_variance = models.FloatField(
        null=True, blank=True,
        help_text="Variance in typing speed"
    )
    
    # Error patterns (aggregated, not per-session)
    error_prone_positions = models.JSONField(
        default=dict,
        help_text="Positions with high error rate: {3: 0.25, 7: 0.15}"
    )
    common_error_types = models.JSONField(
        default=dict,
        help_text="Common error types: {'adjacent_key': 0.4, 'case_swap': 0.3}"
    )
    
    # Rhythm profile
    rhythm_signature = models.JSONField(
        default=list,
        help_text="Normalized timing pattern signature"
    )
    
    # Statistics
    total_sessions = models.IntegerField(default=0)
    successful_sessions = models.IntegerField(default=0)
    success_rate = models.FloatField(default=0.0)
    
    # Profile quality
    profile_confidence = models.FloatField(
        default=0.0,
        help_text="Confidence in profile (0-1, based on data quantity)"
    )
    minimum_sessions_for_suggestion = models.IntegerField(
        default=10,
        help_text="Min sessions before suggesting adaptations"
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_session_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'user_typing_profile'
        verbose_name = 'User Typing Profile'
    
    def __str__(self):
        return f"Typing Profile: {self.user.username} ({self.total_sessions} sessions)"
    
    def has_sufficient_data(self):
        """Check if profile has enough data for suggestions."""
        return self.total_sessions >= self.minimum_sessions_for_suggestion
    
    def get_top_substitutions(self, n=5):
        """Get top N most confident substitutions."""
        sorted_subs = sorted(
            self.substitution_confidence.items(),
            key=lambda x: x[1],
            reverse=True
        )
        return dict(sorted_subs[:n])


# =============================================================================
# Adaptation Feedback Model
# =============================================================================

class AdaptationFeedback(models.Model):
    """
    User feedback on password adaptations.
    
    Tracks:
    - User rating (1-5 stars)
    - Whether typing accuracy improved
    - Whether memorability improved
    - Optional text feedback
    
    Used to improve RL model and substitution learning.
    """
    
    RATING_CHOICES = [
        (1, '1 - Very Poor'),
        (2, '2 - Poor'),
        (3, '3 - Neutral'),
        (4, '4 - Good'),
        (5, '5 - Excellent'),
    ]
    
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )
    
    # Link to the adaptation being rated
    adaptation = models.ForeignKey(
        'PasswordAdaptation',
        on_delete=models.CASCADE,
        related_name='feedback'
    )
    
    # User (redundant but useful for queries)
    user = models.ForeignKey(
        'auth.User',
        on_delete=models.CASCADE,
        related_name='adaptation_feedback'
    )
    
    # Rating (1-5 stars)
    rating = models.IntegerField(
        choices=RATING_CHOICES,
        help_text="Overall rating 1-5"
    )
    
    # Specific improvement indicators
    typing_accuracy_improved = models.BooleanField(
        null=True,
        blank=True,
        help_text="Did typing accuracy improve?"
    )
    memorability_improved = models.BooleanField(
        null=True,
        blank=True,
        help_text="Was the password easier to remember?"
    )
    typing_speed_improved = models.BooleanField(
        null=True,
        blank=True,
        help_text="Did typing speed improve?"
    )
    
    # Text feedback
    additional_feedback = models.TextField(
        blank=True,
        help_text="Optional text feedback from user"
    )
    
    # Metadata
    days_since_adaptation = models.IntegerField(
        default=0,
        help_text="Days between adaptation and feedback"
    )
    typing_sessions_since = models.IntegerField(
        default=0,
        help_text="Typing sessions between adaptation and feedback"
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'adaptation_feedback'
        verbose_name = 'Adaptation Feedback'
        verbose_name_plural = 'Adaptation Feedback'
        ordering = ['-created_at']
        unique_together = ['adaptation', 'user']  # One feedback per adaptation
    
    def __str__(self):
        return f"Feedback: {self.user.username} rated adaptation {self.rating}/5"
    
    def save(self, *args, **kwargs):
        """Calculate days since adaptation on save."""
        if self.adaptation and not self.days_since_adaptation:
            delta = timezone.now() - self.adaptation.suggested_at
            self.days_since_adaptation = delta.days
        super().save(*args, **kwargs)


# =============================================================================
# Quantum Entanglement-Inspired Key Distribution Models
# =============================================================================

class EntangledDevicePair(models.Model):
    """
    Two devices with quantum-inspired entangled cryptographic keys.
    
    Simulates quantum entanglement properties:
    - Synchronized key material between devices
    - Changes are instantly detectable
    - Eavesdropping detection through entropy monitoring
    - Instant revocation upon compromise
    """
    
    STATUS_CHOICES = [
        ('pending', 'Pending Pairing'),
        ('active', 'Active'),
        ('suspended', 'Suspended'),
        ('revoked', 'Revoked'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        User, 
        on_delete=models.CASCADE,
        related_name='entangled_pairs'
    )
    
    # The two paired devices
    device_a = models.ForeignKey(
        UserDevice,
        on_delete=models.CASCADE,
        related_name='entangled_as_device_a',
        help_text="First device in the entangled pair"
    )
    device_b = models.ForeignKey(
        UserDevice,
        on_delete=models.CASCADE,
        related_name='entangled_as_device_b',
        help_text="Second device in the entangled pair"
    )
    
    # Status
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending'
    )
    
    # Timestamps
    pairing_initiated_at = models.DateTimeField(auto_now_add=True)
    pairing_completed_at = models.DateTimeField(null=True, blank=True)
    last_sync_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
    
    # Revocation info
    revocation_reason = models.TextField(blank=True)
    
    class Meta:
        db_table = 'entangled_device_pair'
        verbose_name = 'Entangled Device Pair'
        verbose_name_plural = 'Entangled Device Pairs'
        ordering = ['-pairing_initiated_at']
        constraints = [
            models.UniqueConstraint(
                fields=['device_a', 'device_b'],
                condition=models.Q(status='active'),
                name='unique_active_pair'
            )
        ]
    
    def __str__(self):
        return f"Entangled: {self.device_a.device_name} <-> {self.device_b.device_name} ({self.status})"
    
    def is_healthy(self) -> bool:
        """Check if pair is healthy based on entropy."""
        try:
            return self.sharedrandomnesspool.entropy_measurement >= 7.5
        except SharedRandomnessPool.DoesNotExist:
            return False
    
    def get_other_device(self, device_id: str):
        """Get the other device in the pair."""
        if str(self.device_a.device_id) == device_id:
            return self.device_b
        elif str(self.device_b.device_id) == device_id:
            return self.device_a
        return None


class SharedRandomnessPool(models.Model):
    """
    Synchronized random pool for an entangled pair.
    
    Contains encrypted randomness that both devices use for
    deriving symmetric keys. Entropy is monitored to detect tampering.
    """
    
    pair = models.OneToOneField(
        EntangledDevicePair,
        on_delete=models.CASCADE,
        primary_key=True
    )
    
    # Encrypted pools - each device has its own encrypted copy
    encrypted_pool_a = models.BinaryField(
        help_text="Pool encrypted with device A's derived key"
    )
    encrypted_pool_b = models.BinaryField(
        help_text="Pool encrypted with device B's derived key"
    )
    
    # Generation tracking - increments on each key rotation
    pool_generation = models.IntegerField(
        default=0,
        help_text="Generation number, incremented on each rotation"
    )
    
    # Entropy measurement (bits per byte, max 8.0 for perfect randomness)
    entropy_measurement = models.FloatField(
        default=8.0,
        help_text="Shannon entropy in bits per byte (8.0 = perfect random)"
    )
    
    # Timestamps
    last_refreshed_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'shared_randomness_pool'
        verbose_name = 'Shared Randomness Pool'
        verbose_name_plural = 'Shared Randomness Pools'
    
    def __str__(self):
        return f"Pool gen {self.pool_generation} (entropy: {self.entropy_measurement:.2f})"
    
    def is_entropy_healthy(self) -> bool:
        """Check if entropy is at healthy level."""
        return self.entropy_measurement >= 7.5
    
    def is_entropy_critical(self) -> bool:
        """Check if entropy is at critical level."""
        return self.entropy_measurement < 7.0


class EntanglementSyncEvent(models.Model):
    """
    Log of synchronization and security events for entangled pairs.
    
    Tracks:
    - Key rotations
    - Entropy checks
    - Anomaly detections
    - Instant revocations
    """
    
    EVENT_TYPE_CHOICES = [
        ('key_rotation', 'Key Rotation'),
        ('entropy_check', 'Entropy Check'),
        ('anomaly_detected', 'Anomaly Detected'),
        ('instant_revoke', 'Instant Revocation'),
        ('pool_refresh', 'Pool Refresh'),
        ('sync_request', 'Sync Request'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    pair = models.ForeignKey(
        EntangledDevicePair,
        on_delete=models.CASCADE,
        related_name='sync_events'
    )
    
    event_type = models.CharField(
        max_length=30,
        choices=EVENT_TYPE_CHOICES
    )
    
    # Which device initiated the event (null for system-initiated)
    initiated_by_device = models.ForeignKey(
        UserDevice,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='initiated_sync_events'
    )
    
    # Outcome
    success = models.BooleanField(default=True)
    
    # Additional details (JSON)
    details = models.JSONField(
        default=dict,
        blank=True,
        help_text="Additional event details"
    )
    
    # Timestamp
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'entanglement_sync_event'
        verbose_name = 'Entanglement Sync Event'
        verbose_name_plural = 'Entanglement Sync Events'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['pair', 'event_type']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        status = "✓" if self.success else "✗"
        return f"{status} {self.get_event_type_display()} @ {self.created_at}"


class EntropyMeasurementRecord(models.Model):
    """
    Historical entropy measurements for trend analysis.
    
    Stores periodic entropy readings from entangled pairs for:
    - Trend visualization
    - Anomaly pattern detection
    - Audit trail
    """
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    pair = models.ForeignKey(
        EntangledDevicePair,
        on_delete=models.CASCADE,
        related_name='entropy_history'
    )
    device = models.ForeignKey(
        UserDevice,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='entropy_measurements'
    )
    
    # Entropy metrics
    entropy_value = models.FloatField(
        help_text="Shannon entropy in bits per byte (0-8)"
    )
    kl_divergence = models.FloatField(
        null=True,
        blank=True,
        help_text="KL divergence from paired pool"
    )
    
    # Health status
    is_healthy = models.BooleanField(default=True)
    is_warning = models.BooleanField(default=False)
    is_critical = models.BooleanField(default=False)
    
    # Sample info
    sample_size = models.IntegerField(help_text="Pool size in bytes")
    sample_hash = models.CharField(
        max_length=64,
        help_text="SHA-256 hash of sampled data for verification"
    )
    
    # Timestamp
    measured_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'entropy_measurement_record'
        verbose_name = 'Entropy Measurement Record'
        verbose_name_plural = 'Entropy Measurement Records'
        ordering = ['-measured_at']
        indexes = [
            models.Index(fields=['pair', 'measured_at']),
            models.Index(fields=['is_critical', 'measured_at']),
        ]
    
    def __str__(self):
        status = "🟢" if self.is_healthy else ("🟡" if self.is_warning else "🔴")
        return f"{status} Entropy={self.entropy_value:.2f} @ {self.measured_at}"


class AnomalyEvent(models.Model):
    """
    Dedicated anomaly tracking with severity levels.
    
    Provides structured tracking of detected anomalies for:
    - Security analytics and reporting
    - Auto-revocation decisions
    - Historical pattern analysis
    """
    
    SEVERITY_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('critical', 'Critical'),
    ]
    
    TYPE_CHOICES = [
        ('low_entropy', 'Low Entropy'),
        ('high_kl_divergence', 'High KL Divergence'),
        ('tampering_suspected', 'Tampering Suspected'),
        ('sync_failure', 'Sync Failure'),
        ('device_offline', 'Device Offline'),
        ('chi_squared_anomaly', 'Chi-Squared Anomaly'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    pair = models.ForeignKey(
        EntangledDevicePair,
        on_delete=models.CASCADE,
        related_name='anomaly_events'
    )
    device = models.ForeignKey(
        UserDevice,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='anomaly_events'
    )
    
    # Anomaly classification
    anomaly_type = models.CharField(
        max_length=30,
        choices=TYPE_CHOICES,
        help_text="Type of anomaly detected"
    )
    severity = models.CharField(
        max_length=20,
        choices=SEVERITY_CHOICES,
        help_text="Severity level of the anomaly"
    )
    
    # Metrics at time of detection
    entropy_value = models.FloatField(
        null=True,
        blank=True,
        help_text="Entropy value when anomaly was detected"
    )
    kl_divergence = models.FloatField(
        null=True,
        blank=True,
        help_text="KL divergence when anomaly was detected"
    )
    
    # Response tracking
    auto_revoked = models.BooleanField(
        default=False,
        help_text="Whether pair was auto-revoked due to this anomaly"
    )
    resolved = models.BooleanField(default=False)
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolution_notes = models.TextField(blank=True)
    
    # Additional details
    details = models.JSONField(
        default=dict,
        blank=True,
        help_text="Additional anomaly details"
    )
    recommendation = models.TextField(
        help_text="Recommended action for this anomaly"
    )
    
    # Timestamps
    detected_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'anomaly_event'
        verbose_name = 'Anomaly Event'
        verbose_name_plural = 'Anomaly Events'
        ordering = ['-detected_at']
        indexes = [
            models.Index(fields=['pair', 'severity']),
            models.Index(fields=['resolved', 'detected_at']),
            models.Index(fields=['anomaly_type', 'detected_at']),
        ]
    
    def __str__(self):
        resolved = "✓" if self.resolved else "⚠"
        return f"{resolved} [{self.severity.upper()}] {self.get_anomaly_type_display()} @ {self.detected_at}"
    
    def resolve(self, notes: str = ""):
        """Mark anomaly as resolved."""
        from django.utils import timezone
        self.resolved = True
        self.resolved_at = timezone.now()
        self.resolution_notes = notes
        self.save()


# =============================================================================
# Geofencing & Impossible Travel Detection Models
# =============================================================================

class LocationHistory(models.Model):
    """
    Stores precise GPS coordinates for login events.
    Used for physics-based impossible travel detection.
    """
    SOURCE_CHOICES = [
        ('gps', 'GPS (High Accuracy)'),
        ('network', 'Network Location'),
        ('ip_fallback', 'IP Geolocation'),
        ('manual', 'Manually Provided'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        User, on_delete=models.CASCADE,
        related_name='location_history'
    )
    device = models.ForeignKey(
        'UserDevice', on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='location_records'
    )
    
    # GPS Coordinates (high precision)
    latitude = models.DecimalField(
        max_digits=10, decimal_places=7,
        help_text="Latitude in decimal degrees (-90 to 90)"
    )
    longitude = models.DecimalField(
        max_digits=10, decimal_places=7,
        help_text="Longitude in decimal degrees (-180 to 180)"
    )
    accuracy_meters = models.FloatField(
        default=0,
        help_text="GPS accuracy in meters"
    )
    altitude = models.FloatField(
        null=True, blank=True,
        help_text="Altitude in meters (for satellite verification)"
    )
    
    # IP-based fallback location
    ip_address = models.GenericIPAddressField()
    ip_location_city = models.CharField(max_length=255, blank=True)
    ip_location_country = models.CharField(max_length=255, blank=True)
    ip_location_country_code = models.CharField(max_length=10, blank=True)
    
    # Metadata
    source = models.CharField(
        max_length=20,
        choices=SOURCE_CHOICES,
        default='ip_fallback'
    )
    timestamp = models.DateTimeField(auto_now_add=True)
    server_timestamp = models.DateTimeField(
        auto_now_add=True,
        help_text="NTP-synchronized server time"
    )
    is_ntp_verified = models.BooleanField(
        default=True,
        help_text="Whether timestamp is NTP-verified"
    )
    
    # Login association
    login_attempt = models.ForeignKey(
        'LoginAttempt', on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='location_records'
    )
    
    class Meta:
        db_table = 'location_history'
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['user', 'timestamp']),
            models.Index(fields=['latitude', 'longitude']),
            models.Index(fields=['ip_address']),
        ]
    
    def __str__(self):
        return f"📍 {self.user.username} @ ({self.latitude}, {self.longitude}) - {self.timestamp}"
    
    @property
    def coordinates(self):
        """Return tuple of (lat, lon)."""
        return (float(self.latitude), float(self.longitude))


class ImpossibleTravelEvent(models.Model):
    """
    Records detected impossible travel anomalies.
    Uses physics-based calculations to determine travel plausibility.
    """
    SEVERITY_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('critical', 'Critical'),
    ]
    
    ACTION_CHOICES = [
        ('allowed', 'Allowed'),
        ('challenged', 'MFA Challenge Required'),
        ('blocked', 'Access Blocked'),
        ('travel_verified', 'Travel Verified via Airline'),
        ('user_confirmed', 'User Confirmed Legitimate'),
    ]
    
    TRAVEL_MODE_CHOICES = [
        ('walking', 'Walking'),
        ('driving', 'Driving'),
        ('train', 'Train/Rail'),
        ('flight', 'Commercial Flight'),
        ('supersonic', 'Supersonic (Impossible)'),
        ('unknown', 'Unknown'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        User, on_delete=models.CASCADE,
        related_name='impossible_travel_events'
    )
    
    # Source and destination locations
    source_location = models.ForeignKey(
        LocationHistory, on_delete=models.CASCADE,
        related_name='travel_from_events'
    )
    destination_location = models.ForeignKey(
        LocationHistory, on_delete=models.CASCADE,
        related_name='travel_to_events'
    )
    
    # Physics calculations
    distance_km = models.FloatField(help_text="Great-circle distance in kilometers")
    time_difference_seconds = models.IntegerField(help_text="Time between locations")
    required_speed_kmh = models.FloatField(help_text="Speed required to travel")
    max_allowed_speed_kmh = models.FloatField(
        default=920,
        help_text="Maximum plausible speed (commercial flight ~920 km/h)"
    )
    
    # Inferred travel mode
    inferred_travel_mode = models.CharField(
        max_length=20,
        choices=TRAVEL_MODE_CHOICES,
        default='unknown'
    )
    
    # Risk assessment
    severity = models.CharField(max_length=20, choices=SEVERITY_CHOICES)
    risk_score = models.IntegerField(
        default=0,
        help_text="Risk score 0-100"
    )
    
    # Action taken
    action_taken = models.CharField(
        max_length=30,
        choices=ACTION_CHOICES,
        default='challenged'
    )
    
    # Resolution
    is_legitimate = models.BooleanField(default=False)
    airline_verified = models.BooleanField(default=False)
    verification_data = models.JSONField(
        default=dict, blank=True,
        help_text="Airline booking proof or verification details"
    )
    
    # Cloned session detection
    is_cloned_session = models.BooleanField(
        default=False,
        help_text="Indicates simultaneous sessions from impossible locations"
    )
    concurrent_session_id = models.CharField(max_length=255, blank=True)
    
    resolved = models.BooleanField(default=False)
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolved_by = models.ForeignKey(
        User, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='resolved_travel_events'
    )
    resolution_notes = models.TextField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'impossible_travel_event'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'created_at']),
            models.Index(fields=['severity', 'resolved']),
            models.Index(fields=['action_taken']),
        ]
    
    def __str__(self):
        status = "✓" if self.is_legitimate else "⚠"
        return f"{status} [{self.severity.upper()}] {self.distance_km:.0f}km in {self.time_difference_seconds//60}min = {self.required_speed_kmh:.0f}km/h"
    
    def resolve(self, user=None, legitimate=True, notes=""):
        """Mark event as resolved."""
        self.resolved = True
        self.resolved_at = timezone.now()
        self.resolved_by = user
        self.is_legitimate = legitimate
        self.resolution_notes = notes
        self.save()


class GeofenceZone(models.Model):
    """
    User-defined trusted location zones.
    Logins from within these zones are considered trusted.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        User, on_delete=models.CASCADE,
        related_name='geofence_zones'
    )
    
    name = models.CharField(
        max_length=100,
        help_text="Friendly name (e.g., 'Home', 'Office')"
    )
    
    # Zone center
    latitude = models.DecimalField(max_digits=10, decimal_places=7)
    longitude = models.DecimalField(max_digits=10, decimal_places=7)
    radius_meters = models.IntegerField(
        default=500,
        help_text="Zone radius in meters"
    )
    
    # Trust settings
    is_always_trusted = models.BooleanField(
        default=True,
        help_text="Skip MFA checks from this zone"
    )
    require_mfa_outside = models.BooleanField(
        default=True,
        help_text="Require MFA when logging in from outside all zones"
    )
    
    # Notifications
    notify_on_entry = models.BooleanField(default=False)
    notify_on_exit = models.BooleanField(default=False)
    
    # Metadata
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'geofence_zone'
        ordering = ['name']
    
    def __str__(self):
        status = "🟢" if self.is_active else "⚪"
        return f"{status} {self.name} ({self.radius_meters}m radius)"
    
    def contains_point(self, lat: float, lon: float) -> bool:
        """Check if a point is within this geofence zone."""
        from math import radians, sin, cos, sqrt, atan2
        
        R = 6371000  # Earth's radius in meters
        
        lat1, lon1 = radians(float(self.latitude)), radians(float(self.longitude))
        lat2, lon2 = radians(lat), radians(lon)
        
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        
        a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
        c = 2 * atan2(sqrt(a), sqrt(1-a))
        distance = R * c
        
        return distance <= self.radius_meters


class TravelItinerary(models.Model):
    """
    Pre-registered legitimate travel for verification.
    Allows users to pre-declare travel plans to avoid false positives.
    """
    VERIFICATION_STATUS_CHOICES = [
        ('pending', 'Pending Verification'),
        ('verified', 'Verified'),
        ('failed', 'Verification Failed'),
        ('expired', 'Expired'),
    ]
    
    PROVIDER_CHOICES = [
        ('amadeus', 'Amadeus GDS'),
        ('sabre', 'Sabre'),
        ('travelport', 'Travelport'),
        ('manual', 'Manual Entry'),
        ('email_parse', 'Email Parsed'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        User, on_delete=models.CASCADE,
        related_name='travel_itineraries'
    )
    
    # Trip details
    departure_city = models.CharField(max_length=255)
    departure_country = models.CharField(max_length=100, blank=True)
    departure_airport_code = models.CharField(max_length=10, blank=True)
    departure_latitude = models.DecimalField(
        max_digits=10, decimal_places=7,
        null=True, blank=True
    )
    departure_longitude = models.DecimalField(
        max_digits=10, decimal_places=7,
        null=True, blank=True
    )
    
    arrival_city = models.CharField(max_length=255)
    arrival_country = models.CharField(max_length=100, blank=True)
    arrival_airport_code = models.CharField(max_length=10, blank=True)
    arrival_latitude = models.DecimalField(
        max_digits=10, decimal_places=7,
        null=True, blank=True
    )
    arrival_longitude = models.DecimalField(
        max_digits=10, decimal_places=7,
        null=True, blank=True
    )
    
    # Timing
    departure_time = models.DateTimeField()
    arrival_time = models.DateTimeField()
    
    # Flight details (optional)
    airline_code = models.CharField(max_length=10, blank=True)
    airline_name = models.CharField(max_length=100, blank=True)
    flight_number = models.CharField(max_length=20, blank=True)
    booking_reference = models.CharField(
        max_length=50, blank=True,
        help_text="PNR / Confirmation number"
    )
    
    # Verification
    verification_status = models.CharField(
        max_length=20,
        choices=VERIFICATION_STATUS_CHOICES,
        default='pending'
    )
    verification_provider = models.CharField(
        max_length=20,
        choices=PROVIDER_CHOICES,
        default='manual'
    )
    verification_data = models.JSONField(
        default=dict, blank=True,
        help_text="API response or verification details"
    )
    verified_at = models.DateTimeField(null=True, blank=True)
    
    # Metadata
    notes = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'travel_itinerary'
        ordering = ['-departure_time']
        indexes = [
            models.Index(fields=['user', 'departure_time']),
            models.Index(fields=['verification_status']),
        ]
    
    def __str__(self):
        status = "✓" if self.verification_status == 'verified' else "⏳"
        return f"{status} {self.departure_city} → {self.arrival_city} ({self.departure_time.date()})"
    
    @property
    def duration_hours(self):
        """Calculate trip duration in hours."""
        delta = self.arrival_time - self.departure_time
        return delta.total_seconds() / 3600
    
    def covers_timeframe(self, timestamp):
        """Check if this itinerary covers a given timestamp."""
        # Add buffer time for airport procedures
        buffer = timezone.timedelta(hours=3)
        return (self.departure_time - buffer) <= timestamp <= (self.arrival_time + buffer)


# =============================================================================
# Time-Lock Encryption Models
# =============================================================================

class TimeLockCapsule(models.Model):
    """
    Persisted time-lock capsule for delayed access to secrets.
    
    Supports:
    - Server-enforced delays (recommended)
    - Client-side RSA puzzles (offline capable)
    - Hybrid mode (both options)
    """
    MODE_CHOICES = [
        ('server', 'Server-Enforced'),
        ('client', 'Client-Side Puzzle'),
        ('hybrid', 'Hybrid Mode'),
    ]
    
    STATUS_CHOICES = [
        ('locked', 'Locked'),
        ('solving', 'Solving (Client Mode)'),
        ('unlocked', 'Unlocked'),
        ('expired', 'Expired'),
        ('cancelled', 'Cancelled'),
    ]
    
    TYPE_CHOICES = [
        ('general', 'General'),
        ('will', 'Password Will'),
        ('escrow', 'Escrow'),
        ('time_capsule', 'Time Capsule'),
        ('emergency', 'Emergency Access'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(
        User, on_delete=models.CASCADE,
        related_name='time_lock_capsules'
    )
    
    # Encrypted content
    encrypted_data = models.BinaryField(
        help_text="AES-encrypted secret data"
    )
    encryption_key_encrypted = models.BinaryField(
        help_text="Encryption key encrypted with server master key"
    )
    
    # Timing
    unlock_at = models.DateTimeField(
        help_text="When the capsule becomes accessible"
    )
    delay_seconds = models.IntegerField(
        help_text="Original delay duration in seconds"
    )
    
    # Mode and status
    mode = models.CharField(
        max_length=20,
        choices=MODE_CHOICES,
        default='server'
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='locked'
    )
    capsule_type = models.CharField(
        max_length=20,
        choices=TYPE_CHOICES,
        default='general'
    )
    
    # Client-side puzzle parameters (for client/hybrid modes)
    puzzle_n = models.TextField(
        blank=True,
        help_text="RSA modulus (large integer as string)"
    )
    puzzle_a = models.TextField(
        blank=True,
        help_text="Base value for repeated squaring"
    )
    puzzle_t = models.BigIntegerField(
        null=True, blank=True,
        help_text="Number of squarings required"
    )
    
    # Metadata
    title = models.CharField(
        max_length=255,
        help_text="User-friendly title for the capsule"
    )
    description = models.TextField(
        blank=True,
        help_text="Additional details about the capsule"
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    opened_at = models.DateTimeField(
        null=True, blank=True,
        help_text="When the capsule was unlocked"
    )
    cancelled_at = models.DateTimeField(null=True, blank=True)
    
    # Access control
    max_unlock_attempts = models.IntegerField(default=3)
    unlock_attempts = models.IntegerField(default=0)
    
    class Meta:
        db_table = 'time_lock_capsule'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['owner', 'status']),
            models.Index(fields=['unlock_at', 'status']),
            models.Index(fields=['capsule_type']),
        ]
    
    def __str__(self):
        status_icons = {
            'locked': '🔒',
            'solving': '⏳',
            'unlocked': '🔓',
            'expired': '⌛',
            'cancelled': '❌'
        }
        icon = status_icons.get(self.status, '❓')
        return f"{icon} {self.title} (unlocks: {self.unlock_at})"
    
    @property
    def is_ready_to_unlock(self):
        """Check if capsule can be unlocked (time has passed)."""
        return self.status == 'locked' and timezone.now() >= self.unlock_at
    
    @property
    def time_remaining_seconds(self):
        """Get remaining seconds until unlock."""
        if self.status != 'locked':
            return 0
        remaining = (self.unlock_at - timezone.now()).total_seconds()
        return max(0, int(remaining))
    
    def cancel(self):
        """Cancel the capsule."""
        self.status = 'cancelled'
        self.cancelled_at = timezone.now()
        self.save()


class CapsuleBeneficiary(models.Model):
    """
    Beneficiary for password wills and shared access.
    
    Allows users to designate trusted people who can
    access the capsule contents after unlock.
    """
    ACCESS_LEVEL_CHOICES = [
        ('view', 'View Only'),
        ('full', 'Full Access'),
        ('download', 'Download Only'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    capsule = models.ForeignKey(
        TimeLockCapsule, on_delete=models.CASCADE,
        related_name='beneficiaries'
    )
    
    # Beneficiary info
    email = models.EmailField()
    name = models.CharField(max_length=255)
    relationship = models.CharField(
        max_length=100, blank=True,
        help_text="e.g., 'Spouse', 'Lawyer', 'Business Partner'"
    )
    
    # Access settings
    access_level = models.CharField(
        max_length=20,
        choices=ACCESS_LEVEL_CHOICES,
        default='view'
    )
    requires_verification = models.BooleanField(
        default=True,
        help_text="Require identity verification before access"
    )
    
    # Verification status
    verification_token = models.CharField(max_length=255, blank=True)
    verified = models.BooleanField(default=False)
    verified_at = models.DateTimeField(null=True, blank=True)
    
    # Notification status
    notified_at = models.DateTimeField(
        null=True, blank=True,
        help_text="When unlock notification was sent"
    )
    accessed_at = models.DateTimeField(
        null=True, blank=True,
        help_text="When beneficiary accessed the content"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'capsule_beneficiary'
        unique_together = ['capsule', 'email']
    
    def __str__(self):
        verified = "✓" if self.verified else "○"
        return f"{verified} {self.name} <{self.email}> - {self.capsule.title}"


class VDFProof(models.Model):
    """
    Stores VDF (Verifiable Delay Function) proofs.
    
    Based on Wesolowski VDF for proving computation time.
    Allows verification in O(log t) time.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    capsule = models.ForeignKey(
        TimeLockCapsule, on_delete=models.CASCADE,
        related_name='vdf_proofs'
    )
    
    # VDF parameters
    challenge = models.TextField(
        help_text="Initial challenge value (g)"
    )
    output = models.TextField(
        help_text="VDF output (y = g^(2^t) mod n)"
    )
    proof = models.TextField(
        help_text="Wesolowski proof (π)"
    )
    modulus = models.TextField(
        help_text="RSA modulus (n)"
    )
    iterations = models.BigIntegerField(
        help_text="Number of squarings (t)"
    )
    
    # Verification
    verified = models.BooleanField(default=False)
    verified_at = models.DateTimeField(null=True, blank=True)
    verification_time_ms = models.IntegerField(
        null=True, blank=True,
        help_text="Time to verify the proof in milliseconds"
    )
    
    # Computation metadata
    computation_time_seconds = models.FloatField(
        help_text="Actual computation time"
    )
    hardware_info = models.JSONField(
        default=dict, blank=True,
        help_text="Information about the computing hardware"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'vdf_proof'
        ordering = ['-created_at']
    
    def __str__(self):
        verified = "✓" if self.verified else "○"
        return f"{verified} VDF proof for {self.capsule.title} ({self.iterations:,} iterations)"


class PasswordWill(models.Model):
    """
    Digital password will for inheritance.
    
    Implements a "dead man's switch" pattern:
    - User must check in periodically
    - If check-in is missed, beneficiaries are notified
    - Capsule unlocks and passwords are released
    """
    TRIGGER_TYPE_CHOICES = [
        ('inactivity', 'Inactivity Trigger'),
        ('date', 'Specific Date'),
        ('manual', 'Manual Trigger'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(
        User, on_delete=models.CASCADE,
        related_name='password_wills'
    )
    capsule = models.ForeignKey(
        TimeLockCapsule, on_delete=models.CASCADE,
        related_name='password_will'
    )
    
    # Trigger settings
    trigger_type = models.CharField(
        max_length=20,
        choices=TRIGGER_TYPE_CHOICES,
        default='inactivity'
    )
    inactivity_days = models.IntegerField(
        null=True, blank=True,
        help_text="Days of inactivity before trigger (for inactivity type)"
    )
    target_date = models.DateTimeField(
        null=True, blank=True,
        help_text="Specific date to trigger (for date type)"
    )
    
    # Check-in tracking
    last_check_in = models.DateTimeField(
        default=timezone.now,
        help_text="Last time owner confirmed they're alive"
    )
    check_in_reminder_days = models.IntegerField(
        default=7,
        help_text="Days before deadline to send reminder"
    )
    
    # Status
    is_active = models.BooleanField(default=True)
    is_triggered = models.BooleanField(default=False)
    triggered_at = models.DateTimeField(null=True, blank=True)
    
    # Notifications
    reminder_sent = models.BooleanField(default=False)
    reminder_sent_at = models.DateTimeField(null=True, blank=True)
    beneficiaries_notified = models.BooleanField(default=False)
    beneficiaries_notified_at = models.DateTimeField(null=True, blank=True)
    
    # Metadata
    notes = models.TextField(
        blank=True,
        help_text="Personal message to beneficiaries"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'password_will'
        ordering = ['-created_at']
    
    def __str__(self):
        status = "🟢" if self.is_active else "⚪"
        if self.is_triggered:
            status = "🔴"
        return f"{status} Will for {self.owner.username} ({self.trigger_type})"
    
    @property
    def days_until_trigger(self):
        """Calculate days until the will triggers."""
        if not self.is_active or self.is_triggered:
            return None
        
        if self.trigger_type == 'inactivity':
            deadline = self.last_check_in + timezone.timedelta(days=self.inactivity_days)
        elif self.trigger_type == 'date':
            deadline = self.target_date
        else:
            return None
        
        remaining = (deadline - timezone.now()).days
        return max(0, remaining)
    
    def check_in(self):
        """User confirms they're still active."""
        self.last_check_in = timezone.now()
        self.reminder_sent = False
        self.save()
    
    def trigger(self):
        """Activate the will and notify beneficiaries."""
        self.is_triggered = True
        self.triggered_at = timezone.now()
        self.save()


class EscrowAgreement(models.Model):
    """
    Escrow-style time-locked release.
    
    Allows multiple parties to agree on conditions
    for releasing time-locked secrets.
    """
    RELEASE_CONDITION_CHOICES = [
        ('date', 'On Specific Date'),
        ('all_approve', 'All Parties Approve'),
        ('any_approve', 'Any Party Approves'),
        ('majority', 'Majority Approves'),
        ('date_or_approve', 'Date OR Approval'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    capsule = models.ForeignKey(
        TimeLockCapsule, on_delete=models.CASCADE,
        related_name='escrow_agreement'
    )
    
    # Agreement details
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    release_condition = models.CharField(
        max_length=20,
        choices=RELEASE_CONDITION_CHOICES,
        default='date'
    )
    
    # Parties
    parties = models.ManyToManyField(
        User,
        related_name='escrow_agreements'
    )
    
    # Approval tracking
    approved_by = models.JSONField(
        default=list,
        help_text="List of user IDs who have approved"
    )
    approval_deadline = models.DateTimeField(
        null=True, blank=True,
        help_text="Deadline for parties to approve"
    )
    
    # Dispute resolution
    dispute_resolution_email = models.EmailField(
        blank=True,
        help_text="Contact for dispute resolution"
    )
    is_disputed = models.BooleanField(default=False)
    dispute_notes = models.TextField(blank=True)
    
    # Status
    is_released = models.BooleanField(default=False)
    released_at = models.DateTimeField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'escrow_agreement'
        ordering = ['-created_at']
    
    def __str__(self):
        status = "🔓" if self.is_released else "🔐"
        return f"{status} Escrow: {self.title}"
    
    @property
    def approval_count(self):
        """Number of parties who have approved."""
        return len(self.approved_by)
    
    @property
    def total_parties(self):
        """Total number of parties."""
        return self.parties.count()
    
    @property
    def can_release(self):
        """Check if release conditions are met."""
        if self.is_released or self.is_disputed:
            return False
        
        now = timezone.now()
        
        if self.release_condition == 'date':
            return now >= self.capsule.unlock_at
        elif self.release_condition == 'all_approve':
            return self.approval_count >= self.total_parties
        elif self.release_condition == 'any_approve':
            return self.approval_count >= 1
        elif self.release_condition == 'majority':
            return self.approval_count > self.total_parties // 2
        elif self.release_condition == 'date_or_approve':
            return now >= self.capsule.unlock_at or self.approval_count >= self.total_parties
        
        return False
    
    def approve(self, user_id):
        """Record approval from a party."""
        if user_id not in self.approved_by:
            self.approved_by.append(user_id)
            self.save()
    
    def release(self):
        """Release the escrow."""
        if self.can_release:
            self.is_released = True
            self.released_at = timezone.now()
            self.capsule.status = 'unlocked'
            self.capsule.opened_at = timezone.now()
            self.capsule.save()
            self.save()



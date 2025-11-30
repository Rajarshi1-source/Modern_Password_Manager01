from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from push_notifications.models import APNSDevice, GCMDevice
import uuid

# Create your models here.


# =============================================================================
# CRYSTALS-Kyber Post-Quantum Cryptography Models
# =============================================================================

class KyberKeyPair(models.Model):
    """
    Optimized model for storing CRYSTALS-Kyber-768 key pairs.
    
    Key Sizes (NIST Level 3):
    - Public key: 1184 bytes
    - Private key: 2400 bytes
    - Ciphertext: 1088 bytes
    - Shared secret: 32 bytes
    
    Security Considerations:
    - Private keys are encrypted at rest
    - Keys have version numbers for rotation
    - Last used timestamp for auditing
    """
    
    # Primary key
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # User relationship
    user = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name='kyber_keypairs',
        db_index=True
    )
    
    # Key material (binary fields for efficiency)
    public_key = models.BinaryField(
        max_length=1568,  # Kyber-1024 max size for future-proofing
        help_text="CRYSTALS-Kyber-768 public key (1184 bytes)"
    )
    private_key = models.BinaryField(
        max_length=3168,  # Kyber-1024 max size
        help_text="CRYSTALS-Kyber-768 private key (2400 bytes) - encrypted at rest"
    )
    
    # Key metadata
    key_version = models.IntegerField(
        default=1, 
        db_index=True,
        help_text="Key version for rotation support"
    )
    algorithm = models.CharField(
        max_length=50, 
        default='Kyber768',
        help_text="Kyber variant (Kyber512, Kyber768, Kyber1024)"
    )
    security_level = models.IntegerField(
        default=3,
        help_text="NIST security level (1, 3, or 5)"
    )
    
    # Status flags
    is_active = models.BooleanField(
        default=True, 
        db_index=True,
        help_text="Whether this key is currently active"
    )
    is_compromised = models.BooleanField(
        default=False,
        help_text="Flag if key is suspected compromised"
    )
    
    # Timestamps
    created_at = models.DateTimeField(
        default=timezone.now, 
        db_index=True
    )
    last_used = models.DateTimeField(
        auto_now=True,
        help_text="Last time key was used for encryption/decryption"
    )
    expires_at = models.DateTimeField(
        null=True, 
        blank=True,
        help_text="Optional key expiration time"
    )
    
    # Hybrid encryption support
    x25519_public_key = models.BinaryField(
        max_length=32,
        null=True,
        blank=True,
        help_text="Optional X25519 public key for hybrid mode"
    )
    x25519_private_key = models.BinaryField(
        max_length=32,
        null=True,
        blank=True,
        help_text="Optional X25519 private key for hybrid mode"
    )
    
    # Usage statistics
    encryption_count = models.IntegerField(
        default=0,
        help_text="Number of times key used for encryption"
    )
    decryption_count = models.IntegerField(
        default=0,
        help_text="Number of times key used for decryption"
    )
    
    class Meta:
        db_table = 'kyber_keypairs'
        verbose_name = 'Kyber Key Pair'
        verbose_name_plural = 'Kyber Key Pairs'
        ordering = ['-created_at']
        
        indexes = [
            # Composite indexes for common queries
            models.Index(
                fields=['user', 'is_active'],
                name='idx_kyber_user_active'
            ),
            models.Index(
                fields=['user', 'key_version'],
                name='idx_kyber_user_version'
            ),
            models.Index(
                fields=['created_at'],
                name='idx_kyber_created'
            ),
            models.Index(
                fields=['key_version', 'is_active'],
                name='idx_kyber_version_active'
            ),
            models.Index(
                fields=['user', 'algorithm', 'is_active'],
                name='idx_kyber_user_algo_active'
            ),
        ]
        
        constraints = [
            # Only one active key per user per version
            models.UniqueConstraint(
                fields=['user', 'key_version'],
                condition=models.Q(is_active=True),
                name='unique_active_key_per_version'
            ),
        ]
    
    def __str__(self):
        return f"Kyber KeyPair v{self.key_version} for {self.user.username}"
    
    @property
    def public_key_size(self) -> int:
        """Get public key size in bytes."""
        return len(self.public_key) if self.public_key else 0
    
    @property
    def private_key_size(self) -> int:
        """Get private key size in bytes."""
        return len(self.private_key) if self.private_key else 0
    
    @property
    def is_expired(self) -> bool:
        """Check if key has expired."""
        if self.expires_at is None:
            return False
        return timezone.now() > self.expires_at
    
    @property
    def is_usable(self) -> bool:
        """Check if key can be used."""
        return self.is_active and not self.is_compromised and not self.is_expired
    
    def increment_encryption_count(self):
        """Increment encryption counter."""
        self.encryption_count += 1
        self.save(update_fields=['encryption_count', 'last_used'])
    
    def increment_decryption_count(self):
        """Increment decryption counter."""
        self.decryption_count += 1
        self.save(update_fields=['decryption_count', 'last_used'])
    
    def mark_compromised(self, reason: str = None):
        """Mark key as compromised."""
        self.is_compromised = True
        self.is_active = False
        self.save(update_fields=['is_compromised', 'is_active'])
    
    def deactivate(self):
        """Deactivate the key."""
        self.is_active = False
        self.save(update_fields=['is_active'])


class KyberEncryptedPassword(models.Model):
    """
    Optimized model for storing Kyber-encrypted password entries.
    
    Uses hybrid encryption:
    1. Kyber KEM for key encapsulation (post-quantum)
    2. AES-256-GCM for data encryption (symmetric)
    """
    
    # Primary key
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Relationships
    user = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name='kyber_passwords',
        db_index=True
    )
    keypair = models.ForeignKey(
        KyberKeyPair,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='encrypted_items',
        help_text="Reference to the Kyber keypair used for encryption"
    )
    
    # Password metadata (not encrypted)
    service_name = models.CharField(
        max_length=255, 
        db_index=True,
        help_text="Service name (e.g., 'Google', 'GitHub')"
    )
    username = models.CharField(
        max_length=255,
        help_text="Username for the service"
    )
    url = models.URLField(
        max_length=2048,
        blank=True,
        null=True,
        help_text="Service URL"
    )
    
    # Kyber-encrypted data
    kyber_ciphertext = models.BinaryField(
        max_length=2048,
        help_text="Kyber KEM ciphertext (1088 bytes for Kyber-768)"
    )
    aes_ciphertext = models.BinaryField(
        help_text="AES-256-GCM encrypted password data"
    )
    nonce = models.BinaryField(
        max_length=32,
        help_text="AES-GCM nonce (12 bytes)"
    )
    
    # Ephemeral key for forward secrecy (optional)
    ephemeral_public_key = models.BinaryField(
        max_length=1568,
        null=True,
        blank=True,
        help_text="Ephemeral public key for forward secrecy"
    )
    
    # Encryption metadata
    encryption_version = models.IntegerField(
        default=1,
        help_text="Encryption scheme version"
    )
    algorithm = models.CharField(
        max_length=100,
        default='Kyber768-AES256-GCM',
        help_text="Full encryption algorithm identifier"
    )
    
    # Additional encrypted fields (JSON blob)
    encrypted_metadata = models.BinaryField(
        null=True,
        blank=True,
        help_text="Additional encrypted metadata (notes, tags, etc.)"
    )
    
    # Timestamps
    created_at = models.DateTimeField(default=timezone.now, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_accessed = models.DateTimeField(
        auto_now=True,
        help_text="Last time password was accessed"
    )
    
    # Flags
    is_favorite = models.BooleanField(default=False, db_index=True)
    is_deleted = models.BooleanField(default=False, db_index=True)
    
    class Meta:
        db_table = 'kyber_encrypted_passwords'
        verbose_name = 'Kyber Encrypted Password'
        verbose_name_plural = 'Kyber Encrypted Passwords'
        ordering = ['-updated_at']
        
        indexes = [
            models.Index(
                fields=['user', 'service_name'],
                name='idx_kyber_pwd_user_service'
            ),
            models.Index(
                fields=['user', 'created_at'],
                name='idx_kyber_pwd_user_created'
            ),
            models.Index(
                fields=['user', 'is_deleted'],
                name='idx_kyber_pwd_user_deleted'
            ),
            models.Index(
                fields=['user', 'is_favorite'],
                name='idx_kyber_pwd_user_favorite'
            ),
            models.Index(
                fields=['encryption_version'],
                name='idx_kyber_pwd_enc_version'
            ),
        ]
        
        constraints = [
            # Unique service+username per user
            models.UniqueConstraint(
                fields=['user', 'service_name', 'username'],
                condition=models.Q(is_deleted=False),
                name='unique_service_username_per_user'
            ),
        ]
    
    def __str__(self):
        return f"{self.service_name} ({self.username}) - {self.user.username}"
    
    def soft_delete(self):
        """Soft delete the password entry."""
        self.is_deleted = True
        self.save(update_fields=['is_deleted', 'updated_at'])
    
    def restore(self):
        """Restore a soft-deleted password entry."""
        self.is_deleted = False
        self.save(update_fields=['is_deleted', 'updated_at'])


class KyberSession(models.Model):
    """
    Model for storing Kyber session keys and shared secrets.
    
    Used for:
    - Caching derived session keys
    - Implementing forward secrecy
    - Audit logging of key exchanges
    """
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='kyber_sessions'
    )
    keypair = models.ForeignKey(
        KyberKeyPair,
        on_delete=models.CASCADE,
        related_name='sessions'
    )
    
    # Session identifier
    session_id = models.CharField(
        max_length=128,
        unique=True,
        db_index=True
    )
    
    # Kyber encapsulation data
    ciphertext = models.BinaryField(
        help_text="Kyber ciphertext from encapsulation"
    )
    
    # Derived key material (encrypted at rest)
    encrypted_shared_secret = models.BinaryField(
        null=True,
        blank=True,
        help_text="Encrypted shared secret (if persisted)"
    )
    
    # Session metadata
    created_at = models.DateTimeField(default=timezone.now)
    expires_at = models.DateTimeField()
    
    # Client information
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    
    # Status
    is_active = models.BooleanField(default=True)
    
    class Meta:
        db_table = 'kyber_sessions'
        verbose_name = 'Kyber Session'
        verbose_name_plural = 'Kyber Sessions'
        
        indexes = [
            models.Index(fields=['user', 'is_active']),
            models.Index(fields=['session_id']),
            models.Index(fields=['expires_at']),
        ]
    
    def __str__(self):
        return f"Kyber Session {self.session_id[:8]}... for {self.user.username}"
    
    @property
    def is_expired(self) -> bool:
        """Check if session has expired."""
        return timezone.now() > self.expires_at
    
    @property
    def is_valid(self) -> bool:
        """Check if session is valid and active."""
        return self.is_active and not self.is_expired

class TwoFactorAuth(models.Model):
    """Model for storing two-factor authentication settings"""
    MFA_TYPES = (
        ('totp', 'Time-based OTP'),
        ('authy', 'Authy TOTP'),
        ('push', 'Push Notification'),
    )
    
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    is_enabled = models.BooleanField(default=False)
    mfa_type = models.CharField(max_length=10, choices=MFA_TYPES, default='totp')
    secret_key = models.CharField(max_length=32, blank=True)
    backup_codes = models.TextField(blank=True, help_text="Comma-separated backup codes")
    authy_id = models.CharField(max_length=50, blank=True)
    phone_number = models.CharField(max_length=15, blank=True)
    country_code = models.CharField(max_length=5, default='1')
    last_used = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"2FA for {self.user.username}"
    
    def get_device_for_push(self):
        """Get the user's mobile device for push notifications"""
        try:
            # Try to get iOS device first
            device = APNSDevice.objects.filter(user=self.user).first()
            if device:
                return device, 'apns'
                
            # Fall back to Android device
            device = GCMDevice.objects.filter(user=self.user).first()
            if device:
                return device, 'gcm'
                
            return None, None
        except:
            return None, None

class UserSalt(models.Model):
    """Store unique salt for each user's key derivation"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='auth_salt')
    salt = models.BinaryField()
    auth_hash = models.BinaryField()  # For verifying master password
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"Salt for {self.user.username}"
        
    def get_salt_b64(self):
        """Get base64 encoded salt"""
        import base64
        return base64.b64encode(self.salt).decode('utf-8')

class PushAuth(models.Model):
    """Model for storing push authentication requests"""
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('denied', 'Denied'),
        ('expired', 'Expired'),
    )
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='push_auths')
    request_id = models.CharField(max_length=64, unique=True)
    authy_uuid = models.CharField(max_length=64, blank=True, null=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    
    def __str__(self):
        return f"Push auth for {self.user.username} ({self.status})"
    
    def is_valid(self):
        """Check if the request is still valid"""
        from django.utils import timezone
        return self.status == 'pending' and self.expires_at > timezone.now()

class RecoveryKey(models.Model):
    """Model for storing recovery key data"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='recovery_key')
    encrypted_vault = models.TextField(help_text="Encrypted vault data with recovery key")
    salt = models.CharField(max_length=255, help_text="Salt used for key derivation")
    method = models.CharField(max_length=50, default='recovery-key', help_text="Encryption method used")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Recovery Key"
        verbose_name_plural = "Recovery Keys"
    
    def __str__(self):
        return f"Recovery Key for {self.user.username}"

class UserPasskey(models.Model):
    """Model for storing WebAuthn/passkey credentials"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='passkeys')
    credential_id = models.BinaryField(unique=True)
    public_key = models.BinaryField()
    sign_count = models.IntegerField(default=0)
    rp_id = models.CharField(max_length=253)  # Relying Party ID (your domain)
    created_at = models.DateTimeField(auto_now_add=True)
    last_used_at = models.DateTimeField(null=True, blank=True)
    device_type = models.CharField(max_length=255, null=True, blank=True)

    class Meta:
        unique_together = ('user', 'credential_id')
        
    def __str__(self):
        return f"Passkey for {self.user.username}"

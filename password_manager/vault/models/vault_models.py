from django.db import models
from django.conf import settings
from django.utils import timezone
import uuid
import logging
from .folder_models import VaultFolder

logger = logging.getLogger(__name__)

class EncryptedVaultItem(models.Model):
    """
    Unified model for storing encrypted vault items 
    (passwords, cards, identity, notes)
    """
    ITEM_TYPES = (
        ('password', 'Password'),
        ('card', 'Payment Card'),
        ('identity', 'Identity'),
        ('note', 'Secure Note'),
    )
    
    # Primary key
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Relations
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE,
        related_name='vault_items'
    )
    folder = models.ForeignKey(
        VaultFolder, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='items'
    )
    
    # Core fields
    item_id = models.CharField(max_length=64, unique=True, help_text="Client-generated ID")
    item_type = models.CharField(max_length=20, choices=ITEM_TYPES)
    encrypted_data = models.TextField()
    
    # Cryptographic versioning (for future upgrades)
    crypto_version = models.IntegerField(
        default=1,
        help_text="Cryptographic algorithm version (1=legacy, 2=enhanced Argon2id+dual ECC)"
    )
    crypto_metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Cryptographic metadata (algorithm versions, parameters, public keys)"
    )
    
    # Future post-quantum support
    pqc_wrapped_key = models.BinaryField(
        null=True,
        blank=True,
        help_text="Post-quantum wrapped encryption key (for future PQC migration)"
    )
    
    # FHE (Fully Homomorphic Encryption) fields
    fhe_password = models.BinaryField(
        null=True,
        blank=True,
        help_text="FHE encrypted password (SEAL CKKS ciphertext)"
    )
    encrypted_domain_hash = models.BinaryField(
        null=True,
        blank=True,
        help_text="Encrypted domain hash for FHE search"
    )
    encrypted_username_hash = models.BinaryField(
        null=True,
        blank=True,
        help_text="Encrypted username hash for FHE search"
    )
    domain_fuzzy_hash = models.CharField(
        max_length=128,
        null=True,
        blank=True,
        help_text="Fuzzy hash for similarity search (OPE encrypted)"
    )
    
    # FHE computation cache
    cached_strength_score = models.BinaryField(
        null=True,
        blank=True,
        help_text="Cached FHE-computed password strength score"
    )
    cached_breach_check = models.BinaryField(
        null=True,
        blank=True,
        help_text="Cached FHE-computed breach check result"
    )
    fhe_cache_timestamp = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp of last FHE cache update"
    )
    
    # Tags for categorization
    tags = models.JSONField(default=list, blank=True, help_text="List of tags for categorization")
    
    # Timestamps
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    last_used_at = models.DateTimeField(null=True, blank=True)
    
    # Flags
    favorite = models.BooleanField(default=False)
    deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-updated_at']
        indexes = [
            models.Index(fields=['user', 'item_type']),
            models.Index(fields=['user', 'deleted']),
            models.Index(fields=['item_id']),
            models.Index(fields=['folder']),
            models.Index(fields=['user', 'item_type', 'favorite']),
            models.Index(fields=['user', 'updated_at']),
            # FHE search indexes
            models.Index(fields=['user', 'domain_fuzzy_hash']),
            models.Index(fields=['fhe_cache_timestamp']),
        ]
    
    def __str__(self):
        return f"{self.item_type} - {self.item_id[:8]} ({self.user.username})"
    
    def soft_delete(self):
        """Soft delete the item by marking it as deleted"""
        self.deleted = True
        self.deleted_at = timezone.now()
        self.save(update_fields=['deleted', 'deleted_at'])
    
    def get_decrypted_password(self, user):
        """
        Decrypt password for security scanning purposes only
        This method should only be used for security operations like breach checking
        """
        if user.id != self.user.id or self.item_type != 'password':
            return None
            
        # TODO: Implement actual decryption using SecurityCryptoService when needed
        # For now, return None to maintain security until proper key management is implemented
        return None

# For backwards compatibility
VaultItem = EncryptedVaultItem

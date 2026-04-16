"""
FHE Sharing Models

Models for Homomorphic Password Sharing:
- HomomorphicShare: FHE-encrypted autofill token for a shared password
- ShareAccessLog: Audit trail for every share usage
- ShareGroup: Group multiple shares of one password to multiple recipients
"""

from django.db import models
from django.conf import settings
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator
import uuid


class ShareGroup(models.Model):
    """
    Groups multiple HomomorphicShares of the same vault item.
    Useful for sharing one password to multiple recipients at once.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    name = models.CharField(
        max_length=255,
        help_text="Human-readable name for this share group"
    )
    description = models.TextField(blank=True, default='')

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='owned_share_groups'
    )

    vault_item = models.ForeignKey(
        'vault.EncryptedVaultItem',
        on_delete=models.CASCADE,
        related_name='share_groups',
        help_text="The vault item being shared in this group"
    )

    # Timestamps
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Share Group'
        verbose_name_plural = 'Share Groups'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['owner', '-created_at']),
            models.Index(fields=['vault_item']),
        ]

    def __str__(self):
        return f"{self.name} (Owner: {self.owner.username})"

    @property
    def shares_count(self):
        return self.shares.filter(is_active=True).count()

    @property
    def active_shares(self):
        return self.shares.filter(
            is_active=True,
        ).exclude(
            expires_at__lt=timezone.now()
        )


class HomomorphicShare(models.Model):
    """
    Represents a single FHE-encrypted autofill token shared with a recipient.

    The core idea: the owner's password is encrypted with FHE. An "autofill
    circuit" token is created that can inject the password into a form field
    but CANNOT be decrypted to reveal the plaintext password.

    The recipient can USE the password (autofill) but cannot SEE it.
    """

    # Permission constants
    PERMISSION_AUTOFILL = 'autofill_only'
    PERMISSION_CHOICES = [
        ('autofill_only', 'Autofill Only (cannot view password)'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Participants
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='sent_homomorphic_shares',
        help_text="User who owns the original password"
    )
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='received_homomorphic_shares',
        help_text="User who can USE but not SEE the password"
    )

    # Source vault item
    vault_item = models.ForeignKey(
        'vault.EncryptedVaultItem',
        on_delete=models.CASCADE,
        related_name='homomorphic_shares',
        help_text="The original vault item being shared"
    )

    # Optional group membership
    group = models.ForeignKey(
        ShareGroup,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='shares',
        help_text="Optional share group this belongs to"
    )

    # ============================================================
    # FHE Autofill Token — THE CORE OF THIS FEATURE
    # ============================================================
    encrypted_autofill_token = models.BinaryField(
        help_text=(
            "FHE-encrypted autofill circuit token. This is the encrypted "
            "payload that can fill form fields but CANNOT be decrypted to "
            "reveal the password. Created using create_autofill_circuit()."
        )
    )

    # Domain binding — restrict autofill to specific domains
    encrypted_domain_binding = models.TextField(
        blank=True,
        default='',
        help_text=(
            "JSON-serialized list of domains where this token can autofill. "
            "If empty, the token works on any domain (less secure)."
        )
    )

    # Token metadata (non-sensitive)
    token_metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text=(
            "Metadata: FHE circuit parameters, key versions, creation "
            "device info. No sensitive data."
        )
    )

    # ============================================================
    # Permissions — For FHE shares, view/copy are always False
    # ============================================================
    permission_level = models.CharField(
        max_length=30,
        choices=PERMISSION_CHOICES,
        default='autofill_only',
        help_text="Permission level. FHE shares are always autofill_only."
    )
    can_autofill = models.BooleanField(default=True)
    can_view_password = models.BooleanField(
        default=False,
        help_text="Always False for FHE shares — the whole point of the feature"
    )
    can_copy_password = models.BooleanField(
        default=False,
        help_text="Always False for FHE shares"
    )

    # ============================================================
    # Usage Limits
    # ============================================================
    max_uses = models.IntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(10000)],
        help_text="Maximum number of autofill uses. Null = unlimited."
    )
    use_count = models.IntegerField(
        default=0,
        help_text="How many times the autofill token has been used"
    )

    # ============================================================
    # Lifecycle
    # ============================================================
    expires_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When this share expires. Null = no expiration."
    )
    is_active = models.BooleanField(
        default=True,
        db_index=True,
        help_text="Whether this share is currently active"
    )

    # Revocation tracking
    revoked_at = models.DateTimeField(null=True, blank=True)
    revoked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='revoked_shares',
        help_text="User who revoked this share"
    )
    revocation_reason = models.CharField(max_length=255, blank=True, default='')

    # Timestamps
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    last_used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'Homomorphic Share'
        verbose_name_plural = 'Homomorphic Shares'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['owner', 'is_active', '-created_at']),
            models.Index(fields=['recipient', 'is_active', '-created_at']),
            models.Index(fields=['vault_item', 'is_active']),
            models.Index(fields=['expires_at']),
            models.Index(fields=['group']),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(can_view_password=False),
                name='fhe_share_no_view_password',
            ),
            models.CheckConstraint(
                condition=models.Q(can_copy_password=False),
                name='fhe_share_no_copy_password',
            ),
        ]

    def __str__(self):
        status = "active" if self.is_active and not self.is_expired else "inactive"
        return (
            f"Share {str(self.id)[:8]} | "
            f"{self.owner.username} → {self.recipient.username} | "
            f"{status}"
        )

    @property
    def is_expired(self):
        """Check if this share has expired."""
        if self.expires_at is None:
            return False
        return timezone.now() > self.expires_at

    @property
    def is_usage_limit_reached(self):
        """Check if usage limit has been reached."""
        if self.max_uses is None:
            return False
        return self.use_count >= self.max_uses

    @property
    def is_usable(self):
        """Check if the share can currently be used for autofill."""
        return (
            self.is_active
            and not self.is_expired
            and not self.is_usage_limit_reached
            and self.can_autofill
        )

    @property
    def remaining_uses(self):
        """Get remaining uses, or None if unlimited."""
        if self.max_uses is None:
            return None
        return max(0, self.max_uses - self.use_count)

    def record_use(self):
        """Record a usage of this share."""
        self.use_count += 1
        self.last_used_at = timezone.now()
        self.save(update_fields=['use_count', 'last_used_at', 'updated_at'])

    def revoke(self, user, reason=''):
        """Revoke this share."""
        self.is_active = False
        self.revoked_at = timezone.now()
        self.revoked_by = user
        self.revocation_reason = reason
        self.save(update_fields=[
            'is_active', 'revoked_at', 'revoked_by',
            'revocation_reason', 'updated_at'
        ])

    def get_bound_domains(self):
        """Get the list of domains this token is bound to."""
        if not self.encrypted_domain_binding:
            return []
        import json
        try:
            return json.loads(self.encrypted_domain_binding)
        except (json.JSONDecodeError, TypeError):
            return []


class ShareAccessLog(models.Model):
    """
    Audit log for every autofill usage and share lifecycle event.
    Provides full traceability for compliance.
    """

    ACTION_CHOICES = [
        ('share_created', 'Share Created'),
        ('autofill_used', 'Autofill Used'),
        ('autofill_denied', 'Autofill Denied'),
        ('share_revoked', 'Share Revoked'),
        ('share_expired', 'Share Expired'),
        ('domain_mismatch', 'Domain Mismatch'),
        ('usage_limit_reached', 'Usage Limit Reached'),
        ('share_viewed', 'Share Details Viewed'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    share = models.ForeignKey(
        HomomorphicShare,
        on_delete=models.CASCADE,
        related_name='access_logs',
        help_text="The share this log entry relates to"
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='share_access_logs',
        help_text="The user who performed the action"
    )

    # Action details
    action = models.CharField(max_length=30, choices=ACTION_CHOICES)
    domain = models.CharField(
        max_length=255,
        blank=True,
        default='',
        help_text="Domain where autofill was attempted"
    )
    success = models.BooleanField(default=True)
    failure_reason = models.CharField(
        max_length=255,
        blank=True,
        default='',
        help_text="Reason for failure (if success=False)"
    )

    # Request metadata
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True, default='')

    # Additional context
    details = models.JSONField(
        default=dict,
        blank=True,
        help_text="Additional context (device info, etc.)"
    )

    # Timestamp
    timestamp = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        verbose_name = 'Share Access Log'
        verbose_name_plural = 'Share Access Logs'
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['share', '-timestamp']),
            models.Index(fields=['user', '-timestamp']),
            models.Index(fields=['action', '-timestamp']),
        ]

    def __str__(self):
        return (
            f"{self.action} | Share {str(self.share_id)[:8]} | "
            f"{self.user.username if self.user else 'Unknown'} | "
            f"{self.timestamp.strftime('%Y-%m-%d %H:%M')}"
        )

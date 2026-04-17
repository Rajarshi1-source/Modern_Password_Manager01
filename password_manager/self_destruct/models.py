"""
Self-destruct policies for vault entries.

A ``SelfDestructPolicy`` is attached one-to-one to an
``EncryptedVaultItem`` (via a UUID reference — we avoid a hard FK to
keep the two apps loosely coupled). Each policy describes one or more
conditions that cause the credential to be considered self-destructed:

* **TTL** — ``expires_at`` deadline.
* **Use limit** — ``max_uses`` + ``access_count``.
* **Burn after reading** — single-use credential.
* **Geofence** — allow only within a bounded region.

Once a policy fires we mark it ``expired``; the credential is no longer
returned by the vault API and a periodic Celery task hard-deletes the
underlying ciphertext.
"""

from __future__ import annotations

import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone


class PolicyKind(models.TextChoices):
    TTL = 'ttl', 'Time-to-live'
    USE_LIMIT = 'use_limit', 'Max use count'
    BURN_AFTER_READ = 'burn', 'Burn after reading (single use)'
    GEOFENCE = 'geofence', 'Geofence'


class PolicyStatus(models.TextChoices):
    ACTIVE = 'active', 'Active'
    EXPIRED = 'expired', 'Expired (policy fired)'
    REVOKED = 'revoked', 'Revoked by owner'


class SelfDestructPolicy(models.Model):
    """One policy per vault entry (most-recent wins if there are multiples)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='self_destruct_policies',
    )
    # Keep the vault item as a UUID reference rather than an FK so the
    # two apps don't have a hard import dependency.
    vault_item_id = models.UUIDField(db_index=True)

    kinds = models.JSONField(
        default=list,
        help_text='Subset of PolicyKind values; multiple may be active.',
    )
    status = models.CharField(
        max_length=16,
        choices=PolicyStatus.choices,
        default=PolicyStatus.ACTIVE,
    )

    # TTL
    expires_at = models.DateTimeField(null=True, blank=True)

    # Use-limit / burn-after-read
    max_uses = models.PositiveIntegerField(null=True, blank=True)
    access_count = models.PositiveIntegerField(default=0)

    # Geofence: center point + radius in metres. Optional; only enforced
    # when the kind is GEOFENCE.
    geofence_lat = models.FloatField(null=True, blank=True)
    geofence_lng = models.FloatField(null=True, blank=True)
    geofence_radius_m = models.PositiveIntegerField(null=True, blank=True)

    last_accessed_at = models.DateTimeField(null=True, blank=True)
    last_denied_reason = models.CharField(max_length=64, blank=True, default='')

    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'self_destruct_policies'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'status']),
            models.Index(fields=['expires_at']),
        ]

    def __str__(self) -> str:
        return f'SelfDestructPolicy<{self.id}> item={self.vault_item_id} status={self.status}'

    def mark_expired(self, reason: str) -> None:
        self.status = PolicyStatus.EXPIRED
        self.last_denied_reason = reason[:64]
        self.save(update_fields=['status', 'last_denied_reason', 'updated_at'])


class SelfDestructEvent(models.Model):
    """Forensic trail of allow/deny decisions for auditability."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    policy = models.ForeignKey(
        SelfDestructPolicy,
        on_delete=models.CASCADE,
        related_name='events',
    )
    decision = models.CharField(max_length=16)  # allow|deny
    reason = models.CharField(max_length=64, blank=True, default='')
    ip = models.GenericIPAddressField(null=True, blank=True)
    lat = models.FloatField(null=True, blank=True)
    lng = models.FloatField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        db_table = 'self_destruct_events'
        ordering = ['-created_at']

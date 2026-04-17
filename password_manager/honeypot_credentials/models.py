"""
Honeypot credential models.

A ``HoneypotCredential`` looks indistinguishable from a real
``EncryptedVaultItem`` to anyone browsing the vault. It lives in a
separate table so the real retrieve path never sees it and vice versa.

Every access — list, retrieve, copy, autofill — is recorded via
``HoneypotAccessEvent`` and fans out to the owner's configured
alert channels (email / sms / webhook / Signal).
"""

from __future__ import annotations

import uuid
from django.conf import settings
from django.db import models
from django.utils import timezone


class DecoyStrategy(models.TextChoices):
    STATIC = 'static', 'Static decoy from template'
    ROTATING = 'rotating', 'Rotating decoy (nightly refresh)'
    FROM_TEMPLATE = 'from_template', 'Template-parameterised by user'


class HoneypotAccessType(models.TextChoices):
    LIST_VIEW = 'list_view', 'Listed alongside real entries'
    RETRIEVE = 'retrieve', 'Retrieved (detail fetch)'
    COPY = 'copy', 'Copied to clipboard'
    AUTOFILL = 'autofill', 'Browser autofill fired'


class HoneypotTemplate(models.Model):
    """
    Seed data for believable decoys. A handful of templates ship with the
    app; users can pick one or the service auto-selects based on the
    user's own email domain to maximise plausibility.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(
        max_length=128,
        unique=True,
        help_text='Short identifier ("corporate-admin-backup").',
    )
    fake_site_template = models.CharField(
        max_length=255,
        help_text=(
            'Format string with {domain} placeholder, '
            'e.g. "internal-portal.{domain}".'
        ),
    )
    fake_username_template = models.CharField(
        max_length=255,
        help_text='E.g. "admin_backup@{domain}".',
    )
    password_pattern = models.CharField(
        max_length=128,
        default='corporate',
        help_text=(
            'Generator pattern: "corporate" (Title + Year + !), '
            '"leet" (l33tspeak), or "phrase" (two-word phrase).'
        ),
    )
    description = models.TextField(blank=True, default='')
    is_builtin = models.BooleanField(default=False)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = 'honeypot_templates'
        ordering = ['name']

    def __str__(self) -> str:
        return self.name


class HoneypotCredential(models.Model):
    """
    A single deceptive credential planted in a user's vault.

    The decoy password is stored encrypted at rest so admins and DB
    snapshots don't reveal which strings our code hands out — the
    attacker only learns the decoy after an interception event,
    which is already the triggering condition.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='honeypot_credentials',
    )
    label = models.CharField(
        max_length=255,
        help_text='Owner-facing label — never shown to an attacker.',
    )
    fake_username = models.CharField(max_length=255)
    fake_site = models.CharField(max_length=255)
    decoy_password_encrypted = models.BinaryField(
        help_text='Fernet-encrypted decoy password bytes.',
    )
    decoy_strategy = models.CharField(
        max_length=20,
        choices=DecoyStrategy.choices,
        default=DecoyStrategy.STATIC,
    )
    template = models.ForeignKey(
        HoneypotTemplate,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='credentials',
    )
    is_active = models.BooleanField(default=True)
    alert_channels = models.JSONField(
        default=list,
        blank=True,
        help_text='Subset of ["email","sms","webhook","signal"].',
    )
    # Cached public metadata so list serializers never need to pull
    # ciphertext into memory.
    last_rotated_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'honeypot_credentials'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'is_active']),
            models.Index(fields=['fake_site']),
        ]

    def __str__(self) -> str:
        return f"Honeypot[{self.label}] user={self.user_id}"


class HoneypotAccessEvent(models.Model):
    """
    Forensic record of every time a honeypot was touched — this is the
    *actual* security signal. One event per access.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    honeypot = models.ForeignKey(
        HoneypotCredential,
        on_delete=models.CASCADE,
        related_name='access_events',
    )
    access_type = models.CharField(
        max_length=20,
        choices=HoneypotAccessType.choices,
    )
    ip = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=512, blank=True, default='')
    geo_country = models.CharField(max_length=64, blank=True, default='')
    geo_city = models.CharField(max_length=128, blank=True, default='')
    session_key = models.CharField(max_length=64, blank=True, default='')
    alert_sent = models.BooleanField(default=False)
    alert_errors = models.JSONField(default=dict, blank=True)
    accessed_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        db_table = 'honeypot_access_events'
        ordering = ['-accessed_at']
        indexes = [
            models.Index(fields=['honeypot', '-accessed_at']),
            models.Index(fields=['ip', '-accessed_at']),
        ]

    def __str__(self) -> str:
        return f"AccessEvent[{self.access_type}] honeypot={self.honeypot_id}"

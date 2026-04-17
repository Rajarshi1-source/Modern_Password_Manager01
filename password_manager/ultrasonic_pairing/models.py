"""
Models for ultrasonic device pairing.

A ``PairingSession`` is the single source of truth for one pairing
attempt. Its lifecycle is:

    awaiting_responder -> claimed -> confirmed -> delivered|expired

State transitions are enforced by ``services.pairing_service``; the
models themselves only validate shape. Every transition writes a
``PairingEvent`` row for forensic replay.

Cryptographic notes:
    * Public keys are stored as raw SEC1/uncompressed bytes (65B for
      P-256). The server never sees private keys.
    * ``nonce`` is 6 random bytes — short because it has to ride the
      ultrasonic channel. Reuse is prevented by the ``unique=True``
      constraint PLUS server-side claim-once semantics in the service.
    * ``sas_hmac`` is a 32-byte HMAC-SHA256(shared_secret, "sas") the
      responder submits so the initiator can verify the ECDH result
      without exposing the shared key.
"""

from __future__ import annotations

import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone


class PairingPurpose(models.TextChoices):
    DEVICE_ENROLL = 'device_enroll', 'Enroll a new device on this account'
    ITEM_SHARE = 'item_share', 'In-person one-shot vault item transfer'


class PairingStatus(models.TextChoices):
    AWAITING_RESPONDER = 'awaiting_responder', 'Waiting for responder to claim nonce'
    CLAIMED = 'claimed', 'Responder has claimed; awaiting SAS confirmation'
    CONFIRMED = 'confirmed', 'Both sides confirmed shared secret'
    DELIVERED = 'delivered', 'Terminal action (share/enroll) complete'
    EXPIRED = 'expired', 'TTL exceeded before completion'
    FAILED = 'failed', 'Verification or protocol failure'


class PairingSession(models.Model):
    """Single ECDH+SAS pairing attempt."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    initiator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='initiated_pairings',
    )
    responder = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='claimed_pairings',
    )
    purpose = models.CharField(
        max_length=20,
        choices=PairingPurpose.choices,
    )
    status = models.CharField(
        max_length=24,
        choices=PairingStatus.choices,
        default=PairingStatus.AWAITING_RESPONDER,
    )

    # Crypto material
    initiator_pub_key = models.BinaryField(
        help_text='SEC1 uncompressed P-256 public key of the initiator (65B).',
    )
    responder_pub_key = models.BinaryField(
        null=True, blank=True,
        help_text='Responder public key, written on claim.',
    )
    nonce = models.BinaryField(
        help_text='6 random bytes emitted over the ultrasonic channel.',
    )
    # 12-char hex representation of nonce for DB uniqueness (BinaryField
    # on SQLite can\'t be unique-indexed in all backends). Enforced by
    # the service layer on insert.
    nonce_key = models.CharField(max_length=12, unique=True)

    sas_hmac = models.BinaryField(null=True, blank=True)

    # Optional terminal-action payload (item_share only). Encrypted
    # with the ECDH-derived key; the server stores ciphertext only.
    payload_ciphertext = models.BinaryField(null=True, blank=True)
    payload_nonce = models.BinaryField(null=True, blank=True)
    payload_vault_item_id = models.CharField(max_length=64, blank=True, default='')

    created_at = models.DateTimeField(default=timezone.now)
    expires_at = models.DateTimeField(db_index=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'ultrasonic_pairing_sessions'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['initiator', 'status']),
            models.Index(fields=['status', 'expires_at']),
        ]

    def __str__(self) -> str:
        return f'PairingSession<{self.id}> {self.purpose} status={self.status}'

    @property
    def is_live(self) -> bool:
        if self.status in (PairingStatus.EXPIRED, PairingStatus.FAILED,
                           PairingStatus.DELIVERED):
            return False
        return self.expires_at > timezone.now()


class PairingEvent(models.Model):
    """Forensic log of every state transition on a session."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session = models.ForeignKey(
        PairingSession,
        on_delete=models.CASCADE,
        related_name='events',
    )
    kind = models.CharField(
        max_length=32,
        help_text='initiate|claim|confirm|share|deliver|enroll_device|expire|fail',
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
    )
    ip = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=255, blank=True, default='')
    detail = models.CharField(max_length=255, blank=True, default='')
    created_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        db_table = 'ultrasonic_pairing_events'
        ordering = ['-created_at']

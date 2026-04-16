"""
Database models for :mod:`stegano_vault`.

Two models:

* :class:`StegoVault` - one row per user per named steganographic
  container. Holds the stego-image bytes plus bookkeeping. The image
  payload itself is an already-embedded PNG; the server never sees the
  underlying plaintext vault JSON.

* :class:`StegoAccessEvent` - append-only audit log for embed /
  extract / download / upload operations. Critical for the
  forensics-after-compromise story in the threat model.

All index names stay under 30 characters (Django ``models.E034``
lesson learned from ``zk_proofs``).
"""

from __future__ import annotations

import uuid

from django.conf import settings
from django.db import models


def _stego_image_upload_path(instance: "StegoVault", filename: str) -> str:
    # Stored as an opaque image; filename on disk is random.
    return f"stego_vaults/{instance.user_id}/{instance.id}.png"


class StegoVault(models.Model):
    """
    One steganographic container owned by a user.

    The ``image`` field holds the PNG bytes that have the hidden-vault
    blob LSB-embedded in them. The server cannot decrypt the blob -
    only the user, with at least one of the two passwords, can.
    """

    TIER_CHOICES = (
        (0, "Tier 0 - 32 KiB"),
        (1, "Tier 1 - 128 KiB"),
        (2, "Tier 2 - 1 MiB"),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="stego_vaults",
    )
    label = models.CharField(
        max_length=120,
        default="Default",
        help_text="User-facing name for this stego container.",
    )
    image = models.FileField(
        upload_to=_stego_image_upload_path,
        max_length=512,
        help_text="PNG bytes with HiddenVaultBlob embedded via LSB.",
    )
    image_mime = models.CharField(
        max_length=32,
        default="image/png",
        help_text="Locked to 'image/png' in v1; JPEG would destroy LSB payload.",
    )
    blob_size_tier = models.PositiveSmallIntegerField(
        choices=TIER_CHOICES,
        default=0,
    )
    crypto_ver = models.PositiveSmallIntegerField(
        default=1,
        help_text="HiddenVaultBlob format version.",
    )
    cover_hash = models.CharField(
        max_length=64,
        blank=True,
        default="",
        help_text=(
            "SHA-256 hex of the cover image before embedding. Lets "
            "the user later compare against the original to detect "
            "unexpected re-encoding by a hosting provider."
        ),
    )
    schema_ver = models.PositiveSmallIntegerField(default=1)
    notes = models.CharField(max_length=240, blank=True, default="")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_accessed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Stego Vault"
        verbose_name_plural = "Stego Vaults"
        ordering = ("-updated_at",)
        # Index names kept <= 30 chars (Django models.E034).
        indexes = [
            models.Index(fields=["user", "-updated_at"], name="stego_user_updated_idx"),
            models.Index(fields=["user", "label"], name="stego_user_label_idx"),
        ]

    def __str__(self) -> str:  # pragma: no cover - trivial
        return f"StegoVault({self.user_id}, {self.label})"


class StegoAccessEvent(models.Model):
    """
    Append-only audit trail for stego-vault operations.
    """

    class Kind(models.TextChoices):
        EMBED = "embed", "Embed"
        EXTRACT = "extract", "Extract"
        DOWNLOAD = "download", "Download"
        STORE = "store", "Store"
        DELETE = "delete", "Delete"
        UPGRADE_DURESS = "upgrade_duress", "Upgrade duress"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    stego_vault = models.ForeignKey(
        StegoVault,
        on_delete=models.CASCADE,
        related_name="access_events",
        null=True,  # allow embed/extract w/o a persisted vault
        blank=True,
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="stego_events",
    )
    kind = models.CharField(max_length=24, choices=Kind.choices)
    surface = models.CharField(max_length=16, default="web")
    ip = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=240, blank=True, default="")
    details = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Stego Access Event"
        verbose_name_plural = "Stego Access Events"
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=["user", "-created_at"], name="stego_evt_user_at_idx"),
            models.Index(fields=["stego_vault", "kind"], name="stego_evt_vault_kind_idx"),
        ]

    def __str__(self) -> str:  # pragma: no cover
        return f"StegoAccessEvent({self.user_id}, {self.kind})"

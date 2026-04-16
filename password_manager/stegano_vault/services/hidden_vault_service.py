"""
Glue service between the generic ``hidden_vault`` primitive and the
Django ``StegoVault`` model.

All functions here are side-effect-oriented: they persist rows, log
audit events, and enforce feature-flag / size limits. They never
touch vault plaintext - the opaque blob is already encrypted by the
client.
"""

from __future__ import annotations

import logging
from typing import Optional

from django.conf import settings
from django.core.files.base import ContentFile
from django.db import transaction
from django.utils import timezone

from stegano_vault.models import StegoAccessEvent, StegoVault

logger = logging.getLogger(__name__)


def enabled() -> bool:
    cfg = getattr(settings, "STEGO_VAULT", {}) or {}
    return bool(cfg.get("ENABLED", True))


def max_image_bytes() -> int:
    cfg = getattr(settings, "STEGO_VAULT", {}) or {}
    mb = int(cfg.get("MAX_IMAGE_MB", 8))
    return mb * 1024 * 1024


def bytes_for_tier(tier: int) -> int:
    cfg = getattr(settings, "STEGO_VAULT", {}) or {}
    tiers = cfg.get("TIERS_BYTES", [32768, 131072, 1048576])
    try:
        return int(tiers[tier])
    except (IndexError, TypeError, ValueError):
        raise ValueError(f"Unknown tier: {tier}")


def log_event(
    *,
    user,
    kind: str,
    stego_vault: Optional[StegoVault] = None,
    surface: str = "web",
    ip: Optional[str] = None,
    user_agent: str = "",
    details: Optional[dict] = None,
) -> StegoAccessEvent:
    try:
        return StegoAccessEvent.objects.create(
            user=user,
            stego_vault=stego_vault,
            kind=kind,
            surface=(surface or "web")[:16],
            ip=ip or None,
            user_agent=(user_agent or "")[:240],
            details=details or {},
        )
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("Failed to log StegoAccessEvent(%s): %s", kind, exc)
        # Return an unsaved placeholder so callers don't have to branch.
        return StegoAccessEvent(user=user, kind=kind)


@transaction.atomic
def store_stego_vault(
    *,
    user,
    image_bytes: bytes,
    label: str = "Default",
    tier: int = 0,
    cover_hash: str = "",
    surface: str = "web",
    ip: Optional[str] = None,
    user_agent: str = "",
    replace_existing_for_label: bool = True,
) -> StegoVault:
    """
    Persist a pre-built stego PNG for a user.

    * ``image_bytes`` already contain the HiddenVaultBlob embedded via
      LSB - we do not inspect them.
    * If ``replace_existing_for_label`` is True (default), any
      existing vault with the same label is deleted first. This keeps
      the server footprint predictable.
    """
    if not isinstance(image_bytes, (bytes, bytearray)):
        raise TypeError("image_bytes must be bytes")
    if len(image_bytes) == 0:
        raise ValueError("image_bytes is empty")
    if len(image_bytes) > max_image_bytes():
        raise ValueError(f"Image exceeds {max_image_bytes()} bytes")

    if replace_existing_for_label:
        StegoVault.objects.filter(user=user, label=label).delete()

    sv = StegoVault.objects.create(
        user=user,
        label=label or "Default",
        image_mime="image/png",
        blob_size_tier=int(tier),
        crypto_ver=1,
        cover_hash=(cover_hash or "")[:64],
    )
    # Name the stored file after the PK so the path lines up with
    # ``_stego_image_upload_path``.
    sv.image.save(f"{sv.id}.png", ContentFile(bytes(image_bytes)), save=True)
    sv.last_accessed_at = timezone.now()
    sv.save(update_fields=["last_accessed_at"])

    log_event(
        user=user,
        kind=StegoAccessEvent.Kind.STORE,
        stego_vault=sv,
        surface=surface,
        ip=ip,
        user_agent=user_agent,
        details={"label": sv.label, "tier": int(tier)},
    )
    return sv


def get_stego_vault_for_user(user, vault_id) -> Optional[StegoVault]:
    try:
        return StegoVault.objects.get(id=vault_id, user=user)
    except StegoVault.DoesNotExist:
        return None


@transaction.atomic
def delete_stego_vault(
    *,
    user,
    vault_id,
    surface: str = "web",
    ip: Optional[str] = None,
    user_agent: str = "",
) -> bool:
    sv = get_stego_vault_for_user(user, vault_id)
    if sv is None:
        return False
    log_event(
        user=user,
        kind=StegoAccessEvent.Kind.DELETE,
        stego_vault=sv,
        surface=surface,
        ip=ip,
        user_agent=user_agent,
        details={"label": sv.label},
    )
    sv.delete()
    return True

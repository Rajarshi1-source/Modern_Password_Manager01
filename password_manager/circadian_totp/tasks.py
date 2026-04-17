"""Celery tasks for circadian_totp.

All tasks are defensive: they catch adapter-level errors so a single misbehaving
wearable link cannot crash the beat schedule.
"""

from __future__ import annotations

import logging
from datetime import timedelta

from celery import shared_task
from django.contrib.auth import get_user_model
from django.utils import timezone

from .crypto_utils import encrypt_string
from .models import WearableLink
from .services import circadian_totp_service as _svc
from .services.wearable_adapters import get_adapter

logger = logging.getLogger(__name__)
User = get_user_model()


@shared_task(name="circadian_totp.refresh_wearable_tokens")
def refresh_wearable_tokens() -> dict:
    """Refresh any wearable links whose access token is expiring within 1h."""

    horizon = timezone.now() + timedelta(hours=1)
    refreshed = 0
    errors = 0
    for link in WearableLink.objects.filter(expires_at__lte=horizon):
        try:
            adapter = get_adapter(link.provider)
            tokens = adapter.refresh(link)
            if not tokens:
                continue
            link.oauth_access_token_encrypted = encrypt_string(tokens["access_token"])
            if tokens.get("refresh_token"):
                link.oauth_refresh_token_encrypted = encrypt_string(
                    tokens["refresh_token"]
                )
            link.expires_at = tokens.get("expires_at")
            link.scope = tokens.get("scope", link.scope)
            link.save()
            refreshed += 1
        except Exception:
            errors += 1
            logger.exception("refresh failed for wearable link %s", link.pk)
    return {"refreshed": refreshed, "errors": errors}


@shared_task(name="circadian_totp.pull_sleep_for_user")
def pull_sleep_for_user(user_id: int, provider: str = "fitbit", days: int = 3) -> int:
    """Pull recent sleep observations for one user / provider."""

    try:
        link = WearableLink.objects.get(user_id=user_id, provider=provider)
    except WearableLink.DoesNotExist:
        return 0
    adapter = get_adapter(provider)
    now = timezone.now()
    try:
        payload = adapter.fetch_sleep(link, now - timedelta(days=days), now)
    except Exception:
        logger.exception("sleep fetch failed for user=%s provider=%s", user_id, provider)
        return 0
    link.last_synced_at = now
    link.save(update_fields=["last_synced_at"])
    created = _svc.ingest_sleep_observations(link.user, provider, payload)
    _svc.recompute_profile(link.user)
    return created


@shared_task(name="circadian_totp.pull_sleep_for_all_linked_users")
def pull_sleep_for_all_linked_users(provider: str = "fitbit", days: int = 3) -> int:
    """Fan out a sleep pull for every user with a live provider link."""

    total = 0
    for link in WearableLink.objects.filter(provider=provider):
        total += pull_sleep_for_user(link.user_id, provider, days)
    return total


@shared_task(name="circadian_totp.recompute_all_profiles")
def recompute_all_profiles() -> int:
    """Daily profile recomputation."""
    count = 0
    for uid in WearableLink.objects.values_list("user_id", flat=True).distinct():
        try:
            user = User.objects.get(pk=uid)
        except User.DoesNotExist:
            continue
        _svc.recompute_profile(user)
        count += 1
    return count

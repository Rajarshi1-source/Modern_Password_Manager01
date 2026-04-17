"""Celery tasks for self-destructing passwords."""

from __future__ import annotations

import logging

from celery import shared_task
from django.utils import timezone

from .models import PolicyKind, PolicyStatus, SelfDestructPolicy

logger = logging.getLogger(__name__)


@shared_task(name='self_destruct.tasks.expire_stale_policies')
def expire_stale_policies() -> int:
    """
    Sweep active policies and flip anything whose deadline has passed
    to ``expired``. Runs periodically (see celery.py beat schedule).

    Returns the number of rows flipped, primarily for test observability.
    """
    now = timezone.now()
    flipped = 0

    qs = SelfDestructPolicy.objects.filter(status=PolicyStatus.ACTIVE)
    for policy in qs.iterator():
        kinds = set(policy.kinds or [])
        reason = None

        if PolicyKind.TTL in kinds and policy.expires_at and policy.expires_at <= now:
            reason = 'ttl_expired'
        elif PolicyKind.USE_LIMIT in kinds and policy.max_uses is not None \
                and policy.access_count >= policy.max_uses:
            reason = 'use_limit_exceeded'

        if reason:
            policy.mark_expired(reason)
            flipped += 1

    if flipped:
        logger.info('expire_stale_policies: flipped %s policies', flipped)
    return flipped


@shared_task(name='self_destruct.tasks.purge_expired_ciphertext')
def purge_expired_ciphertext() -> int:
    """
    Hard-delete vault items whose policy is expired/revoked. This is
    the truly destructive step; we run it less frequently than the
    flip above so users have time to see the "gone" UI message before
    the row is gone.
    """
    try:
        from vault.models.vault_models import EncryptedVaultItem
    except Exception:
        return 0

    cutoff = timezone.now() - timezone.timedelta(hours=1)
    terminal = (PolicyStatus.EXPIRED, PolicyStatus.REVOKED)
    qs = SelfDestructPolicy.objects.filter(status__in=terminal, updated_at__lte=cutoff)

    deleted = 0
    for policy in qs.iterator():
        try:
            EncryptedVaultItem.objects.filter(id=policy.vault_item_id).delete()
            deleted += 1
        except Exception as exc:  # pragma: no cover
            logger.warning('Failed to purge vault item %s: %s', policy.vault_item_id, exc)

    if deleted:
        logger.info('purge_expired_ciphertext: deleted %s items', deleted)
    return deleted

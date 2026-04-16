"""Celery tasks for ambient_auth."""

from __future__ import annotations

import logging

from celery import shared_task
from django.contrib.auth import get_user_model

from . import services

logger = logging.getLogger(__name__)


@shared_task(name="ambient_auth.tasks.recompute_signal_reliability")
def recompute_signal_reliability():
    """
    Nightly job: recompute per-signal reliability weights for every user
    with recent ambient activity. Cheap heuristic, bounded by the user
    count and a hard cap of 500 observations per user.
    """
    User = get_user_model()
    active_user_ids = (
        User.objects.filter(ambient_observations__isnull=False)
        .values_list("id", flat=True)
        .distinct()
    )
    total = 0
    for uid in active_user_ids:
        try:
            user = User.objects.get(id=uid)
        except User.DoesNotExist:
            continue
        try:
            services.recompute_signal_reliability(user)
            total += 1
        except Exception:  # pragma: no cover - keep the beat loop alive
            logger.exception("recompute_signal_reliability failed for user %s", uid)
    logger.info("ambient_auth: recomputed reliability for %s users", total)
    return total

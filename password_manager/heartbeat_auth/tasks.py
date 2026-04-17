"""Background tasks for heartbeat_auth.

Scheduled from :mod:`password_manager.celery` beat config.
"""

from __future__ import annotations

import logging

from celery import shared_task
from django.utils import timezone

from .models import HeartbeatProfile, HeartbeatReading, ProfileStatus
from .services import feature_matcher

logger = logging.getLogger(__name__)

EMA_ALPHA = 0.2  # weight of the most-recent reading in baseline re-smoothing
REBUILD_LIMIT = 30  # look at the N most-recent enrolled readings


@shared_task(name='heartbeat_auth.tasks.recompute_baselines')
def recompute_baselines() -> int:
    """Nightly EMA re-smoothing of per-user baselines.

    Returns the number of profiles rebuilt. Only enrolled profiles
    are touched; pending/reset profiles are left alone until the user
    completes fresh enrollment.
    """
    updated = 0
    for profile in HeartbeatProfile.objects.filter(status=ProfileStatus.ENROLLED):
        readings = list(
            HeartbeatReading.objects
            .filter(session__user=profile.user, session__session_type='enroll')
            .order_by('-captured_at')[:REBUILD_LIMIT]
        )
        if len(readings) < 3:
            continue
        try:
            mean = list(profile.baseline_mean or [])
            cov = list(profile.baseline_cov or [])
            count = profile.enrollment_count or 0
            if not mean:
                mean = [0.0] * len(feature_matcher.FEATURE_ORDER)
            for reading in reversed(readings):  # oldest first so EMA compounds
                vec = feature_matcher.vector_from_features(reading.features or {})
                # Use a fixed small weight to absorb slow drift; we
                # intentionally do NOT feed verification readings back
                # in here to avoid opening a replay window where an
                # attacker can mould the baseline.
                mean = [
                    (1 - EMA_ALPHA) * m + EMA_ALPHA * v
                    for m, v in zip(mean, vec)
                ]
            profile.baseline_mean = mean
            # Cov is re-estimated from the recent readings with numpy
            # so the matcher keeps a well-conditioned matrix.
            try:
                import numpy as np
                vecs = np.asarray([
                    feature_matcher.vector_from_features(r.features or {})
                    for r in readings
                ], dtype=float)
                vecs = np.where(np.isnan(vecs), 0.0, vecs)
                cov_np = np.cov(vecs, rowvar=False)
                if cov_np.ndim == 0:
                    cov_np = np.array([[float(cov_np)]])
                profile.baseline_cov = cov_np.tolist()
            except Exception:
                logger.exception('heartbeat recompute: cov update failed for %s', profile.user_id)

            profile.updated_at = timezone.now()
            profile.save(update_fields=['baseline_mean', 'baseline_cov', 'updated_at'])
            updated += 1
        except Exception:
            logger.exception('heartbeat recompute: failed for user=%s', profile.user_id)
    if updated:
        logger.info('heartbeat_auth: recomputed baselines for %s profiles', updated)
    return updated

"""Celery tasks for personality-based auth."""
from __future__ import annotations

import logging
from datetime import timedelta

from celery import shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task(name='personality_auth.nightly_inference_refresh')
def nightly_inference_refresh(batch_size: int = 50):
    """Re-run inference for opted-in profiles that haven't been updated in a week."""
    from .models import PersonalityProfile
    from .services import PersonalityInferenceService, LLMSchemaError

    cutoff = timezone.now() - timedelta(days=7)
    stale = PersonalityProfile.objects.filter(
        opted_in=True,
    ).filter(
        models_or_null('last_inferred_at', cutoff),
    ).order_by('last_inferred_at')[:batch_size]

    service = PersonalityInferenceService()
    processed = 0
    failed = 0
    for profile in stale:
        try:
            service.infer(profile.user)
            processed += 1
        except PermissionError:
            continue
        except LLMSchemaError as exc:
            logger.warning("nightly inference failed for %s: %s", profile.user_id, exc)
            failed += 1
        except Exception as exc:  # noqa: BLE001
            logger.exception(
                "unexpected nightly inference error for %s: %s", profile.user_id, exc
            )
            failed += 1

    return {'processed': processed, 'failed': failed}


@shared_task(name='personality_auth.prune_expired_questions')
def prune_expired_questions(batch_size: int = 1000):
    """Delete expired question pool entries and close stale challenges."""
    from .models import ChallengeStatus, PersonalityChallenge, PersonalityQuestion

    now = timezone.now()
    expired_qs = PersonalityQuestion.objects.filter(expires_at__lt=now).values_list('id', flat=True)[:batch_size]
    q_ids = list(expired_qs)
    deleted = PersonalityQuestion.objects.filter(id__in=q_ids).delete()[0]

    stale_challenges = PersonalityChallenge.objects.filter(
        status__in=[ChallengeStatus.PENDING, ChallengeStatus.IN_PROGRESS],
        expires_at__lt=now,
    )
    closed = stale_challenges.update(status=ChallengeStatus.EXPIRED, completed_at=now)

    result = {'questions_deleted': deleted, 'challenges_expired': closed}
    if deleted or closed:
        logger.info('prune_expired_questions: %s', result)
    return result


def models_or_null(field: str, cutoff):
    """Small helper to build a ``Q`` that matches rows with null or stale field."""
    from django.db.models import Q

    return Q(**{f'{field}__lt': cutoff}) | Q(**{f'{field}__isnull': True})


# ---------------------------------------------------------------------------
# Celery beat schedule (imported by project settings).
# ---------------------------------------------------------------------------

CELERY_BEAT_SCHEDULE = {
    'personality-nightly-inference': {
        'task': 'personality_auth.nightly_inference_refresh',
        'schedule': 60 * 60 * 24,  # Once per day
    },
    'personality-prune-expired-questions': {
        'task': 'personality_auth.prune_expired_questions',
        'schedule': 60 * 60,  # Hourly
    },
}

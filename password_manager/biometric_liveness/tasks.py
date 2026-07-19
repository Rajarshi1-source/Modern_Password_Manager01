"""
Celery Tasks for Biometric Liveness
====================================

Durable retry for mirroring a finalized liveness verdict onto its DB row when the
inline write (see ``views.persist_session_result``) hits a *transient*
``DatabaseError``. The task queue is a separate service from the application DB,
so a queued verdict survives a DB blip and is applied once the DB recovers. The
write is idempotent, so re-running the task simply re-applies the same terminal
fields.
"""

import logging

from celery import shared_task
from django.core.exceptions import ValidationError
from django.db import DatabaseError

logger = logging.getLogger(__name__)

# Ceiling on the exponential backoff between retries (seconds).
_MAX_RETRY_COUNTDOWN = 3600


@shared_task(bind=True, max_retries=10, acks_late=True)
def retry_persist_liveness_result(self, payload):
    """
    Re-apply a liveness verdict to its ``LivenessSession`` row; retry on a
    transient DB failure with capped exponential backoff.

    ``payload`` is the JSON-safe dict produced by
    ``views._liveness_result_payload``.
    """
    # Imported inside the task body to avoid a circular import (views imports this
    # module to enqueue) and to keep Celery's autodiscover import light.
    from .views import apply_liveness_result
    from .models import LivenessSession
    try:
        apply_liveness_result(payload)
    except LivenessSession.DoesNotExist:
        # Row gone (e.g. user/session deleted); nothing left to persist.
        return
    except (ValidationError, ValueError, TypeError, KeyError):
        # A malformed payload can never succeed -- do not retry forever.
        logger.exception("Dropping unusable liveness persistence payload")
        return
    except DatabaseError as exc:
        # Capped exponential backoff so a longer outage doesn't hot-loop.
        countdown = min(_MAX_RETRY_COUNTDOWN, 60 * (2 ** self.request.retries))
        raise self.retry(exc=exc, countdown=countdown) from exc

"""
Celery Tasks for Biometric Liveness
====================================

Durable retry for mirroring a finalized liveness verdict onto its DB row when the
inline write (see ``views.persist_session_result``) hits a *transient*
``DatabaseError``. The task queue is a separate service from the application DB,
so a queued verdict survives a DB blip and is applied once the DB recovers. The
write is idempotent, so re-running the task simply re-applies the same terminal
fields.

Behind the broker sits a LAST-RESORT net: the DB-backed persist outbox
(``models.LivenessPersistOutbox``). A verdict lands there only when the broker
layer itself fails (enqueue error, or ``retry_persist_liveness_result``
exhausts its retries); ``drain_liveness_persist_outbox`` sweeps it on a beat
schedule, re-applying idempotently and deleting rows on success.
"""

import logging

from celery import shared_task
from celery.exceptions import MaxRetriesExceededError
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
    from .views import apply_liveness_result, _record_persist_outbox
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
        try:
            raise self.retry(exc=exc, countdown=countdown) from exc
        except (MaxRetriesExceededError, DatabaseError):
            # Broker retries are exhausted (a multi-hour outage). Fall through
            # to the DB-backed outbox as the last-resort net: by now the DB may
            # be back (or the failure was row-level all along), and the beat
            # sweeper keeps re-applying idempotently. Best-effort -- if this
            # write fails too, the loss is logged, same as pre-outbox behavior.
            # NB BOTH classes must be caught: when retry() is given exc=,
            # Celery re-raises THAT original exception on exhaustion
            # (raise_with_context(exc) in Task.retry) instead of raising
            # MaxRetriesExceededError -- catching only the latter would skip
            # this net in a real worker and lose the verdict on the final
            # retry. Retry (budget remaining) is neither and still propagates.
            _record_persist_outbox(
                payload, reason=f'broker retries exhausted: {exc}')


@shared_task
def drain_liveness_persist_outbox():
    """
    Beat-scheduled sweeper for the last-resort persist outbox.

    Re-applies each pending verdict payload to its ``LivenessSession`` row and
    deletes the record on success. Correctness does NOT rely on locking:
    ``apply_liveness_result`` is idempotent (same frozen terminal fields,
    stable completed_at), so two overlapping sweeps -- or an outbox row racing
    a still-queued broker retry for the same session -- at worst duplicate a
    write of identical values. Permanent failures (row deleted, malformed
    payload) are dropped: a deleted session's verdict has no home, and keeping
    biometric-derived data for a deleted session would be a privacy liability,
    not durability. Transient DatabaseErrors leave the row pending with
    attempts+1 until ``OUTBOX_MAX_ATTEMPTS``, after which the row is marked
    abandoned (kept for operator inspection, excluded from future sweeps).
    Returns the number of rows successfully drained.
    """
    from django.conf import settings
    from .views import apply_liveness_result
    from .models import LivenessPersistOutbox, LivenessSession

    config = getattr(settings, 'BIOMETRIC_LIVENESS', {})
    max_attempts = config.get('OUTBOX_MAX_ATTEMPTS', 1000)
    batch = config.get('OUTBOX_DRAIN_BATCH', 500)

    drained = 0
    rows = list(
        LivenessPersistOutbox.objects.filter(status='pending')
        .order_by('created_at')[:batch])
    for row in rows:
        try:
            apply_liveness_result(row.payload)
        except (LivenessSession.DoesNotExist, ValidationError, ValueError,
                TypeError, KeyError):
            # Same non-retryable classification as retry_persist_liveness_result:
            # this payload can never succeed, so nothing is left to persist.
            logger.exception(
                f"Dropping unusable liveness persist-outbox row for {row.session_id}")
            _delete_outbox_row(row)
        except DatabaseError as exc:
            _bump_outbox_attempts(row, exc, max_attempts)
        else:
            _delete_outbox_row(row)
            drained += 1
    return drained


def _delete_outbox_row(row):
    """Best-effort delete; a DB failure here leaves the row for the next sweep."""
    try:
        row.delete()
    except DatabaseError:
        logger.exception(
            f"Could not delete liveness persist-outbox row {row.session_id}")


def _bump_outbox_attempts(row, exc, max_attempts):
    """Record a transient drain failure; abandon the row once attempts exhaust."""
    row.attempts += 1
    row.last_error = str(exc)[:500]
    if row.attempts >= max_attempts:
        row.status = 'abandoned'
        logger.error(
            f"Abandoning liveness persist-outbox row for {row.session_id} "
            f"after {row.attempts} failed attempts")
    try:
        # updated_at is auto_now, which only fires when named in update_fields.
        row.save(update_fields=['attempts', 'last_error', 'status', 'updated_at'])
    except DatabaseError:
        # DB still down -- the row simply stays as-is for the next sweep.
        logger.exception(
            f"Could not update liveness persist-outbox row {row.session_id}")

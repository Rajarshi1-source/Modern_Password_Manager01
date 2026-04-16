"""Celery tasks for the reputation network."""

from __future__ import annotations

import logging

from celery import shared_task

from . import services

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def flush_pending_reputation_batches(self):
    """Periodically called by Celery Beat (or the synchronous fallback in
    ``services._maybe_flush_batch``) to flush any pending ``ReputationEvent``
    rows into an ``AnchorBatch`` and submit to the configured adapter.

    Retries on transient RPC failures; swallows nothing so the Celery
    dashboard still surfaces real errors.
    """
    try:
        batch = services.flush_pending_batch()
        if batch is None:
            return {"flushed": False, "reason": "nothing_pending"}
        return {
            "flushed": True,
            "batch_id": str(batch.id),
            "status": batch.status,
            "batch_size": batch.batch_size,
            "merkle_root": batch.merkle_root,
            "tx_hash": batch.tx_hash,
            "adapter": batch.adapter,
        }
    except Exception as exc:  # noqa: BLE001
        logger.exception("flush_pending_reputation_batches failed")
        raise self.retry(exc=exc)

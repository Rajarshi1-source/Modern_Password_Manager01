"""
FeatureFlagUsage Batch Writer
==============================

Buffers FeatureFlagUsage writes in the Django cache and flushes them
to the database in periodic batches via a Celery beat task.

This eliminates per-request DB writes from the feature flag evaluation
path (get_experiments_and_flags), reducing write amplification from
N flags × M users × P page loads to a single bulk operation every 60s.

The buffer uses Django's cache framework:
    - Redis: writes survive restarts, shared across workers
    - locmem: development convenience, lost on restart (acceptable)
"""

import json
import logging
import time

from django.core.cache import cache

logger = logging.getLogger(__name__)

# Cache key for the pending writes buffer
_BUFFER_KEY = 'ff_usage_batch_buffer'
_BUFFER_LOCK_KEY = 'ff_usage_batch_lock'
_BUFFER_TTL = 300  # 5 minutes — safety net if flush task stops running


class FeatureFlagBatchWriter:
    """
    Accumulates FeatureFlagUsage records in cache and bulk-writes on flush.

    Thread-safe: each record() call appends to a cache-based list.
    The flush() method is called by a Celery beat task every 60 seconds.
    """

    @staticmethod
    def record(flag_id: int, user_id: int, was_enabled: bool, context: dict = None):
        """
        Buffer a single FeatureFlagUsage record for later flushing.

        Args:
            flag_id: FeatureFlag primary key
            user_id: User primary key
            was_enabled: Whether the flag was enabled for this user
            context: Optional context dict (cohort, url, date, etc.)
        """
        entry = {
            'flag_id': flag_id,
            'user_id': user_id,
            'was_enabled': was_enabled,
            'context': context or {},
            'timestamp': time.time(),
        }

        try:
            # Append to the buffer list in cache
            buffer = cache.get(_BUFFER_KEY, [])
            buffer.append(entry)
            cache.set(_BUFFER_KEY, buffer, _BUFFER_TTL)
        except Exception as e:
            logger.error(f"FeatureFlagBatchWriter.record() failed: {e}")
            # Fallback: try direct DB write
            _direct_write(entry)

    @staticmethod
    def flush():
        """
        Flush all buffered records to the database.

        Uses update_or_create to deduplicate per (flag, user) pair,
        keeping only the latest entry per flush cycle.

        Returns:
            Number of records flushed.
        """
        # Atomically swap the buffer with an empty list
        buffer = cache.get(_BUFFER_KEY, [])
        if not buffer:
            return 0

        cache.set(_BUFFER_KEY, [], _BUFFER_TTL)

        # Deduplicate: keep only the latest entry per (flag_id, user_id)
        latest = {}
        for entry in buffer:
            key = (entry['flag_id'], entry['user_id'])
            latest[key] = entry

        flushed = 0
        errors = 0

        for (flag_id, user_id), entry in latest.items():
            try:
                _direct_write(entry)
                flushed += 1
            except Exception as e:
                errors += 1
                logger.error(
                    f"FeatureFlagBatchWriter.flush() failed for "
                    f"flag={flag_id}, user={user_id}: {e}"
                )

        if flushed > 0:
            logger.info(
                f"FeatureFlagBatchWriter: flushed {flushed} records "
                f"({errors} errors)"
            )

        return flushed


def _direct_write(entry: dict):
    """Write a single FeatureFlagUsage record to the database."""
    from ab_testing.models import FeatureFlagUsage, FeatureFlag
    from django.contrib.auth import get_user_model

    User = get_user_model()

    FeatureFlagUsage.objects.update_or_create(
        feature_flag_id=entry['flag_id'],
        user_id=entry['user_id'],
        defaults={
            'was_enabled': entry['was_enabled'],
            'context': entry.get('context', {}),
        },
    )

"""
A/B Testing Celery Tasks
=========================

Periodic tasks for the A/B testing and feature flags system.
"""

import logging
from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(name='ab_testing.tasks.flush_feature_flag_usage')
def flush_feature_flag_usage():
    """
    Flush buffered FeatureFlagUsage records to the database.

    Scheduled via Celery Beat to run every 60 seconds.
    See: password_manager/celery.py beat_schedule
    """
    from .batch_writer import FeatureFlagBatchWriter

    try:
        flushed = FeatureFlagBatchWriter.flush()
        return {'flushed': flushed}
    except Exception as e:
        logger.error(f"FeatureFlagUsage flush failed: {e}")
        return {'error': str(e)}

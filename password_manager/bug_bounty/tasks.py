"""
Celery tasks for the continuous (scheduled) self-pentest.

``run_scheduled_self_tests`` is the beat entry point; it fans out one
``run_self_test`` per active user so the work spreads across workers.
"""

from __future__ import annotations

import logging

from celery import shared_task
from django.contrib.auth import get_user_model

from .models import RunTrigger
from .services.self_test_service import run_self_test as _run_self_test

logger = logging.getLogger(__name__)


@shared_task(name='bug_bounty.tasks.run_self_test')
def run_self_test(user_id):
    """Run the harness for a single user (scheduled trigger)."""
    User = get_user_model()
    try:
        user = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        logger.warning('bug_bounty.run_self_test: user %s no longer exists', user_id)
        return None
    run = _run_self_test(user, trigger=RunTrigger.SCHEDULED)
    return str(run.id)


@shared_task(name='bug_bounty.tasks.run_scheduled_self_tests')
def run_scheduled_self_tests():
    """Fan out a scheduled self-test to every active user."""
    User = get_user_model()
    dispatched = 0
    user_ids = User.objects.filter(is_active=True).values_list('id', flat=True)
    for user_id in user_ids.iterator():
        run_self_test.delay(user_id)
        dispatched += 1
    logger.info('bug_bounty: dispatched %s scheduled self-tests', dispatched)
    return dispatched

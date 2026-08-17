"""
Shared Celery Tasks
===================

Background tasks that don't belong to any single feature app.
"""

import logging

from celery import shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task
def cleanup_expired_sessions():
    """
    Daily sweep of expired Django sessions.

    `SESSION_ENGINE` is the DB-backed default
    (`django.contrib.sessions.backends.db`), so `django_session` accumulates
    one row per login and is never pruned on its own -- Django ships exactly
    this cleanup as the `clearsessions` management command; this is a
    scheduled equivalent of that same query.
    """
    from django.contrib.sessions.models import Session

    now = timezone.now()
    expired = Session.objects.filter(expire_date__lt=now)
    expired_count = expired.count()
    expired.delete()

    logger.info("Cleaned up %s expired session(s)", expired_count)
    return {'expired_sessions_deleted': expired_count}

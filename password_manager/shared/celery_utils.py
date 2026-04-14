"""
Celery queue monitoring and backpressure utilities.

Provides queue-depth checking so views can reject work with HTTP 503
when the task queue is saturated, preventing unbounded queue growth.

Usage in views::

    from shared.celery_utils import check_queue_or_reject

    @api_view(['POST'])
    def trigger_scan(request):
        rejection = check_queue_or_reject('ml', max_depth=500)
        if rejection:
            return rejection
        scan_user_vault.delay(request.user.id)
        return Response({'status': 'queued'}, status=202)
"""

import logging

from django.conf import settings
from rest_framework.response import Response
from rest_framework import status

logger = logging.getLogger(__name__)

_DEFAULT_MAX_DEPTH = 1000


def get_queue_depth(queue_name: str = 'default') -> int | None:
    """
    Return the approximate number of pending messages in a Celery queue.

    Returns None if the depth cannot be determined (broker unavailable,
    unsupported transport, etc.).
    """
    try:
        from password_manager.celery import app

        with app.connection_or_acquire() as conn:
            channel = conn.default_channel
            _, depth, _ = channel.queue_declare(
                queue=queue_name, passive=True,
            )
            return depth
    except Exception as exc:
        logger.debug("Could not read depth for queue %s: %s", queue_name, exc)
        return None


def check_queue_or_reject(
    queue_name: str = 'default',
    max_depth: int | None = None,
) -> Response | None:
    """
    Check the queue depth and return a 503 Response if it exceeds the
    threshold, or None if the caller may proceed.

    ``max_depth`` defaults to ``settings.CELERY_QUEUE_MAX_DEPTH``
    (falling back to 1000).
    """
    if max_depth is None:
        max_depth = getattr(settings, 'CELERY_QUEUE_MAX_DEPTH', _DEFAULT_MAX_DEPTH)

    depth = get_queue_depth(queue_name)
    if depth is not None and depth > max_depth:
        logger.warning(
            "Queue %s depth %d exceeds threshold %d — rejecting task",
            queue_name, depth, max_depth,
        )
        return Response(
            {
                'error': 'Service busy, please try again later.',
                'queue': queue_name,
                'retry_after': 30,
            },
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
            headers={'Retry-After': '30'},
        )
    return None

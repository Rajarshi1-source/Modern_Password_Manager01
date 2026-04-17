"""Background tasks for ultrasonic_pairing.

Scheduled from :mod:`password_manager.celery` beat config:

* :func:`expire_stale_sessions` every 2 minutes.
* :func:`purge_delivered_payloads` hourly.
"""

from __future__ import annotations

import logging
from datetime import timedelta

from celery import shared_task
from django.utils import timezone

from .models import PairingSession, PairingStatus
from .services import pairing_service as ps

logger = logging.getLogger(__name__)


@shared_task(name='ultrasonic_pairing.tasks.expire_stale_sessions')
def expire_stale_sessions() -> int:
    """Mark sessions past TTL as expired.

    Returns the number of rows flipped, for test observability.
    """
    now = timezone.now()
    live_states = (
        PairingStatus.AWAITING_RESPONDER,
        PairingStatus.CLAIMED,
        PairingStatus.CONFIRMED,
    )
    qs = PairingSession.objects.filter(status__in=live_states, expires_at__lte=now)
    flipped = 0
    for session in qs.iterator():
        session.status = PairingStatus.EXPIRED
        session.save(update_fields=['status'])
        try:
            from .models import PairingEvent
            PairingEvent.objects.create(session=session, kind='expire')
        except Exception:
            logger.exception('failed to log expire event for %s', session.id)
        flipped += 1
    if flipped:
        logger.info('ultrasonic_pairing: expired %s stale sessions', flipped)
    return flipped


@shared_task(name='ultrasonic_pairing.tasks.purge_delivered_payloads')
def purge_delivered_payloads(grace_hours: int = 24) -> int:
    """Hard-delete ciphertext from delivered/expired sessions after grace.

    Keeps the audit row but wipes the now-useless encrypted blob to
    shrink the attack surface.
    """
    cutoff = timezone.now() - timedelta(hours=grace_hours)
    qs = PairingSession.objects.filter(
        status__in=(PairingStatus.DELIVERED, PairingStatus.EXPIRED, PairingStatus.FAILED),
        completed_at__lte=cutoff,
    ).exclude(payload_ciphertext__isnull=True)

    purged = 0
    for session in qs.iterator():
        session.payload_ciphertext = None
        session.payload_nonce = None
        session.save(update_fields=['payload_ciphertext', 'payload_nonce'])
        purged += 1
    if purged:
        logger.info('ultrasonic_pairing: purged payloads from %s sessions', purged)
    return purged

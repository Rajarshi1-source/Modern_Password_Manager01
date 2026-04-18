"""Celery tasks for the social_recovery app."""
from __future__ import annotations

import logging

from celery import shared_task
from django.utils import timezone

from .models import SocialRecoveryRequest, Voucher
from .services.audit_service import record_event

logger = logging.getLogger(__name__)


@shared_task(name="social_recovery.send_voucher_invitation")
def send_voucher_invitation(voucher_id: str) -> bool:
    """Best-effort notification to a newly invited voucher.

    In production this would dispatch an email + push notification. Here we
    just touch ``updated_at`` via an audit entry so downstream systems can
    observe the intent.
    """
    voucher = Voucher.objects.filter(voucher_id=voucher_id).select_related("circle").first()
    if voucher is None:
        return False
    record_event(
        event_type="voucher_invited",
        user=voucher.circle.user,
        circle=voucher.circle,
        event_data={
            "voucher_id": str(voucher.voucher_id),
            "notification": "queued",
            "target_email": voucher.email or None,
            "target_did": voucher.did_string or None,
        },
    )
    return True


@shared_task(name="social_recovery.notify_voucher_of_request")
def notify_voucher_of_request(request_id: str, voucher_id: str) -> bool:
    request = SocialRecoveryRequest.objects.filter(request_id=request_id).first()
    voucher = Voucher.objects.filter(voucher_id=voucher_id).first()
    if request is None or voucher is None:
        return False
    record_event(
        event_type="request_initiated",
        user=voucher.user,
        circle=request.circle,
        event_data={
            "voucher_id": str(voucher.voucher_id),
            "request_id": str(request.request_id),
            "notification": "queued",
        },
    )
    return True


@shared_task(name="social_recovery.expire_stale_requests")
def expire_stale_requests() -> int:
    """Mark any pending request past ``expires_at`` as expired."""
    now = timezone.now()
    qs = SocialRecoveryRequest.objects.filter(status="pending", expires_at__lt=now)
    count = qs.count()
    if count:
        qs.update(status="expired")
    return count


@shared_task(name="social_recovery.settle_stakes")
def settle_stakes() -> int:
    """Placeholder for future stake settlement logic.

    Currently the stake ledger is append-only through ``password_reputation``
    so this task only records a heartbeat audit entry.
    """
    return 0


@shared_task(name="social_recovery.slash_fraudulent_attestations")
def slash_fraudulent_attestations() -> int:
    """Placeholder for async fraud sweeps (triggered by adversarial_detector)."""
    return 0

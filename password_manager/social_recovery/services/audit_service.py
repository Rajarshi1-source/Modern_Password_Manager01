"""Hash-chained audit log for the social_recovery app."""
from __future__ import annotations

import uuid
from typing import Any, Dict, Optional

from django.db import transaction
from django.utils import timezone

from ..models import RecoveryCircle, SocialRecoveryAuditLog


@transaction.atomic
def record_event(
    *,
    event_type: str,
    user=None,
    circle: Optional[RecoveryCircle] = None,
    event_data: Optional[Dict[str, Any]] = None,
    ip_address: Optional[str] = None,
    user_agent: str = "",
) -> SocialRecoveryAuditLog:
    """Append a tamper-evident audit entry.

    Looks up the previous entry's ``entry_hash`` under a row lock so that
    concurrent writers can't fork the chain.
    """
    prev = (
        SocialRecoveryAuditLog.objects.select_for_update()
        .order_by("-created_at")
        .first()
    )
    prev_hash = bytes(prev.entry_hash) if prev else b""
    now = timezone.now()

    circle_id = circle.circle_id if circle is not None else None
    user_id = getattr(user, "id", None)

    entry_hash = SocialRecoveryAuditLog.compute_entry_hash(
        prev_hash=prev_hash,
        user_id=user_id,
        circle_id=circle_id,
        event_type=event_type,
        event_data=event_data or {},
        created_at_iso=now.isoformat(),
    )

    return SocialRecoveryAuditLog.objects.create(
        entry_id=uuid.uuid4(),
        user=user,
        circle=circle,
        event_type=event_type,
        event_data=event_data or {},
        ip_address=ip_address,
        user_agent=user_agent,
        prev_hash=prev_hash,
        entry_hash=entry_hash,
        created_at=now,
    )

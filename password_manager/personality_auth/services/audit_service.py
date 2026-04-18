"""Hash-chained audit log for personality-auth events."""

from __future__ import annotations

from typing import Optional

from django.db import transaction

from ..models import (
    AuditEventType,
    PersonalityAuditLog,
    PersonalityChallenge,
    PersonalityProfile,
)


@transaction.atomic
def record_event(
    profile: PersonalityProfile,
    event_type: str,
    payload: Optional[dict] = None,
    *,
    challenge: Optional[PersonalityChallenge] = None,
    ip_address: Optional[str] = None,
) -> PersonalityAuditLog:
    """Append a tamper-evident entry linked to the previous hash for the profile."""

    if event_type not in dict(AuditEventType.choices):
        raise ValueError(f"Unknown personality audit event: {event_type!r}")

    previous = (
        PersonalityAuditLog.objects.filter(profile=profile)
        .order_by('-created_at')
        .first()
    )
    entry = PersonalityAuditLog(
        profile=profile,
        challenge=challenge,
        event_type=event_type,
        event_payload=dict(payload or {}),
        ip_address=ip_address,
        previous_hash=previous.entry_hash if previous else '',
    )
    entry.entry_hash = entry.compute_hash()
    entry.save()
    return entry

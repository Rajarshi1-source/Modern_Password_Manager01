"""
PolicyService
=============

Small surface area — callers invoke ``evaluate_access(vault_item, request)``
and ``record_access(vault_item)`` around every retrieve.

``evaluate_access`` returns one of:

* ``'allow'``     — let the caller proceed.
* ``'ttl_expired'``    — ``expires_at`` has passed.
* ``'use_limit_exceeded'`` — ``access_count >= max_uses``.
* ``'burned'``    — burn-after-reading single-use policy already fired.
* ``'out_of_geofence'`` — geofence configured and caller is outside it.
* ``'revoked'``   — owner revoked the credential.

Any non-``allow`` string is a denial and the HTTP layer converts it to
``410 Gone``. ``record_access`` is only called on an ``allow`` decision
and increments counters, flipping burn-after-reading entries to
``expired`` immediately.
"""

from __future__ import annotations

import logging
from typing import Optional

from django.db import transaction
from django.utils import timezone

from ..models import PolicyKind, PolicyStatus, SelfDestructEvent, SelfDestructPolicy
from .geofence import GeofenceEvaluator, extract_coords

logger = logging.getLogger(__name__)


def _policy_for(vault_item) -> Optional[SelfDestructPolicy]:
    """
    Resolve the active policy (if any) for a given vault item.
    ``vault_item`` may be a model instance with ``.id`` or a UUID string.
    """
    vault_id = getattr(vault_item, 'id', None) or vault_item
    try:
        return SelfDestructPolicy.objects.filter(
            vault_item_id=vault_id,
            status=PolicyStatus.ACTIVE,
        ).first()
    except (ValueError, TypeError):
        return None


def evaluate_access(vault_item, request=None) -> str:
    """
    Returns a short reason string. ``'allow'`` means the read may proceed.
    Any other value is a denial reason.
    """
    policy = _policy_for(vault_item)
    if policy is None:
        return 'allow'  # no policy attached, normal credential.

    if policy.status == PolicyStatus.REVOKED:
        return 'revoked'

    kinds = set(policy.kinds or [])

    if PolicyKind.TTL in kinds and policy.expires_at:
        if policy.expires_at <= timezone.now():
            policy.mark_expired('ttl_expired')
            _log_event(policy, 'deny', 'ttl_expired', request)
            return 'ttl_expired'

    if PolicyKind.USE_LIMIT in kinds and policy.max_uses is not None:
        if policy.access_count >= policy.max_uses:
            policy.mark_expired('use_limit_exceeded')
            _log_event(policy, 'deny', 'use_limit_exceeded', request)
            return 'use_limit_exceeded'

    if PolicyKind.BURN_AFTER_READ in kinds and policy.access_count >= 1:
        policy.mark_expired('burned')
        _log_event(policy, 'deny', 'burned', request)
        return 'burned'

    if PolicyKind.GEOFENCE in kinds and policy.geofence_radius_m:
        evaluator = GeofenceEvaluator(
            center_lat=policy.geofence_lat or 0.0,
            center_lng=policy.geofence_lng or 0.0,
            radius_m=policy.geofence_radius_m,
        )
        lat, lng = extract_coords(request)
        if not evaluator.contains(lat, lng):
            _log_event(policy, 'deny', 'out_of_geofence', request, lat=lat, lng=lng)
            return 'out_of_geofence'

    return 'allow'


@transaction.atomic
def record_access(vault_item, request=None) -> None:
    """Increment counters after a successful retrieve."""
    policy = _policy_for(vault_item)
    if policy is None:
        return

    policy.access_count = (policy.access_count or 0) + 1
    policy.last_accessed_at = timezone.now()
    update_fields = ['access_count', 'last_accessed_at', 'updated_at']

    # Burn-after-read: flip to expired the moment we record the first
    # successful access so a concurrent second reader can't race past
    # the check above.
    if PolicyKind.BURN_AFTER_READ in set(policy.kinds or []):
        policy.status = PolicyStatus.EXPIRED
        policy.last_denied_reason = 'burned'
        update_fields.extend(['status', 'last_denied_reason'])

    policy.save(update_fields=update_fields)
    _log_event(policy, 'allow', 'ok', request)


def _log_event(policy, decision, reason, request, lat=None, lng=None):
    ip = None
    try:
        from shared.utils import get_client_ip
        ip = get_client_ip(request) if request is not None else None
    except Exception:
        pass

    try:
        SelfDestructEvent.objects.create(
            policy=policy,
            decision=decision,
            reason=reason,
            ip=ip,
            lat=lat,
            lng=lng,
        )
    except Exception as exc:  # pragma: no cover - forensic log is best effort
        logger.warning('Failed to log self-destruct event: %s', exc)

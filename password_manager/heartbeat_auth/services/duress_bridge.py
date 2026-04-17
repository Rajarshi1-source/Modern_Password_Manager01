"""Bridge from HRV-duress detection to the existing decoy-vault flow.

:func:`maybe_activate_duress` is a thin wrapper around
:class:`security.services.duress_code_service.DuressCodeService` that
returns the exact decoy payload the normal duress-code pipeline would
return. The HRV detector does NOT create a new DuressCode row — that
would leak the fact that HRV-based duress is enabled to an adversary
with DB access. Instead we reach straight into
``_get_or_create_decoy_vault`` which already handles refresh and
formatting, and additionally write a :class:`SecurityAlert` record so
the owner's alert channels fan out the event.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from django.conf import settings

logger = logging.getLogger(__name__)


def _request_context(request) -> Dict[str, Any]:
    if request is None:
        return {}
    ip = request.META.get('HTTP_X_FORWARDED_FOR', '').split(',')[0].strip() \
        or request.META.get('REMOTE_ADDR')
    return {
        'ip_address': ip or None,
        'user_agent': request.META.get('HTTP_USER_AGENT', '')[:255],
        'trigger': 'heartbeat_hrv',
    }


def maybe_activate_duress(user, request=None, probability: float = 0.0) -> Optional[Dict[str, Any]]:
    """Return a decoy vault payload when the HRV duress path fires.

    Fail-closed: if anything in the decoy pipeline raises, return
    ``None`` and log loudly. The caller (verify_reading) keeps the
    session in the ``duress`` state either way, so a ``None`` decoy
    still denies access to the real vault.
    """
    if not bool(getattr(settings, 'HEARTBEAT_DURESS_ENABLED', True)):
        return None

    try:
        from security.services.duress_code_service import DuressCodeService
    except Exception:  # pragma: no cover - DuressCodeService may be absent in partial installs
        logger.exception('heartbeat duress: DuressCodeService unavailable')
        return None

    try:
        service = DuressCodeService()
        # The decoy vault is keyed by threat_level; "high" mirrors the
        # behaviour the duress-code flow picks when no explicit code
        # is known.
        decoy = service._get_or_create_decoy_vault(user, threat_level='high')
    except Exception:
        logger.exception('heartbeat duress: failed to build decoy vault for user=%s', user.id)
        decoy = None

    # Fire a SecurityAlert so operator dashboards + silent-alarm fan-out
    # reflect the HRV trigger. We isolate this from the decoy path so a
    # logging failure never suppresses the decoy.
    try:
        from security.models.core import SecurityAlert
        SecurityAlert.objects.create(
            user=user,
            alert_type='hrv_duress',
            severity='high',
            message='HRV-duress signature detected during heartbeat verification.',
            metadata={
                'probability': float(probability),
                **_request_context(request),
            },
        )
    except Exception:  # pragma: no cover
        logger.exception('heartbeat duress: SecurityAlert insert failed')

    # Silent alarm fan-out (best-effort).
    try:
        from security.services.silent_alarm_service import get_silent_alarm_service
        alarm = get_silent_alarm_service()
        if alarm:
            alarm.send_alert(
                user=user,
                category='duress',
                detail='HRV duress signature detected',
                context={'probability': float(probability)},
            )
    except Exception:
        logger.exception('heartbeat duress: silent_alarm_service fan-out failed')

    return decoy

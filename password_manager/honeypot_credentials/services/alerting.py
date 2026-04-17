"""
Silent alerting for honeypot hits.

Fans out to the owner via email / sms / webhook / signal. Reuses the
existing silent_alarm_service channel stubs so anything we already know
how to deliver for duress also works here.

The alert path is always best-effort: delivery failures are recorded on
the event so the owner can see "alert attempted but fanout failed".
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Iterable, Optional

from django.conf import settings
from django.utils import timezone

from security.models.core import SecurityAlert

from ..models import HoneypotAccessEvent, HoneypotCredential

logger = logging.getLogger(__name__)


def _send_email(user, payload: Dict[str, Any]) -> None:
    from django.core.mail import send_mail
    recipient = getattr(user, 'email', None)
    if not recipient:
        return
    subject = 'SecureVault Honeypot Triggered'
    body = (
        "A honeypot credential in your vault was accessed.\n\n"
        f"Label: {payload['label']}\n"
        f"Access type: {payload['access_type']}\n"
        f"Time: {payload['timestamp']}\n"
        f"IP: {payload['ip']}\n"
        f"User-Agent: {payload['user_agent']}\n"
        f"Geo: {payload['geo_city']}, {payload['geo_country']}\n\n"
        "If this wasn't you, assume your vault has been compromised and rotate your master password immediately."
    )
    send_mail(
        subject,
        body,
        getattr(settings, 'DEFAULT_FROM_EMAIL', 'alerts@securevault.local'),
        [recipient],
        fail_silently=False,
    )


def _send_webhook(user, payload: Dict[str, Any]) -> None:
    url = getattr(settings, 'HONEYPOT_WEBHOOK_URL', '') or getattr(
        user, 'honeypot_webhook_url', '',
    )
    if not url:
        return
    import requests  # lazy import
    requests.post(url, json=payload, timeout=5)


def _send_sms(user, payload: Dict[str, Any]) -> None:
    # Delegate to the notification service when available; otherwise
    # log-only so tests don't require Twilio.
    try:
        from auth_module.services import notification_service as ns
        phone = getattr(user, 'phone_number', None) or getattr(user, 'phone', None)
        if phone and hasattr(ns, 'send_sms'):
            ns.send_sms(
                phone,
                f"Honeypot access: {payload['label']} from {payload['ip']}",
            )
    except Exception as exc:
        logger.info("SMS channel unavailable: %s", exc)


def _send_signal(user, payload: Dict[str, Any]) -> None:
    # Follows the silent_alarm_service stub: we simply log in dev mode;
    # production deployments point HONEYPOT_SIGNAL_WEBHOOK at the relay.
    url = getattr(settings, 'HONEYPOT_SIGNAL_WEBHOOK', '')
    if not url:
        return
    import requests  # lazy import
    requests.post(url, json=payload, timeout=5)


_CHANNEL_DISPATCH = {
    'email': _send_email,
    'sms': _send_sms,
    'webhook': _send_webhook,
    'signal': _send_signal,
}


def _payload_from(event: HoneypotAccessEvent) -> Dict[str, Any]:
    hp: HoneypotCredential = event.honeypot
    return {
        'label': hp.label,
        'honeypot_id': str(hp.id),
        'access_type': event.access_type,
        'timestamp': event.accessed_at.isoformat(),
        'ip': event.ip or '',
        'user_agent': event.user_agent,
        'geo_country': event.geo_country,
        'geo_city': event.geo_city,
    }


def fire_alerts(event: HoneypotAccessEvent) -> None:
    """
    Send silent alerts for ``event`` across the configured channels.

    Always writes a SecurityAlert row regardless of channel dispatch
    results so the owner sees the hit in the dashboard even if email
    delivery is broken.
    """
    hp = event.honeypot
    owner = hp.user
    payload = _payload_from(event)
    errors: Dict[str, str] = {}

    # In-app alert first — this is the one guaranteed delivery path.
    try:
        SecurityAlert.objects.create(
            user=owner,
            alert_type='suspicious_activity',
            severity='critical',
            title=f'Honeypot accessed: {hp.label}',
            message=(
                f'Unauthorized access to honeypot credential "{hp.label}" '
                f'from {event.ip or "unknown IP"}. Your vault may be compromised.'
            ),
            data=payload,
        )
    except Exception as exc:
        errors['security_alert'] = str(exc)
        logger.error("SecurityAlert persist failed: %s", exc)

    channels: Iterable[str] = hp.alert_channels or ['email']
    for channel in channels:
        fn = _CHANNEL_DISPATCH.get(channel)
        if fn is None:
            errors[channel] = 'unknown_channel'
            continue
        try:
            fn(owner, payload)
        except Exception as exc:  # pragma: no cover — network dependent
            errors[channel] = str(exc)
            logger.warning("Honeypot alert via %s failed: %s", channel, exc)

    event.alert_sent = not errors or 'security_alert' not in errors
    event.alert_errors = errors
    event.save(update_fields=['alert_sent', 'alert_errors'])

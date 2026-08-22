"""
Celery task for duress-signal activation.

Split out of ``DuressCodeService.consume_unlock_signal`` for a timing reason,
not an organisational one. ``consume_unlock_signal`` runs on EVERY unlock and
must do IDENTICAL synchronous work whether the signal matched or not -- see
``DuressSignal``'s docstring. Before this split, a match ran the full
``activate_duress_mode`` inline: DB writes for an evidence package, decoy-vault
lookup/generation, a ``DuressEvent``, and -- when silent alarms are enabled --
``SilentAlarmService.send_alerts()``, which does blocking SMTP (``send_mail``)
and an outbound ``requests.post()`` webhook call. A non-match returned after a
single digest comparison. That is a large, measurable, network-observable
latency difference on the same endpoint -- exactly the oracle the duress
feature exists to deny an attacker holding the user's session.

Everything with real cost now runs here, off the request thread. The view
enqueues this task and returns; it does not wait for it, so response latency
no longer depends on whether the signal matched.
"""

import logging

from celery import shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task(
    name='security.activate_duress_signal',
    bind=True,
    max_retries=2,
    default_retry_delay=30,
)
def activate_duress_signal_task(self, signal_id, request_context):
    """Run the full duress response for a matched ``DuressSignal``.

    Mirrors exactly what ``DuressCodeService.consume_unlock_signal``'s matched
    branch used to do inline. ``signal_id`` is sufficient to look up
    everything else -- the user, the linked ``DuressCode`` (if any), and the
    severity fallback -- so the request thread that enqueues this only needs
    to pass the signal's id and the request context, not re-derive any of it.

    Never raises back to the caller: this always runs detached from any
    request (Celery already isolates task failures from the enqueueing
    thread), and a missing signal (deleted between match and task execution)
    or activation failure should not crash the worker loop.
    """
    from security.models import DuressCode, DuressEvent, DuressSignal
    from security.services.duress_code_service import get_duress_code_service

    try:
        signal = DuressSignal.objects.select_related('user', 'duress_code').get(
            id=signal_id
        )
    except DuressSignal.DoesNotExist:
        logger.warning(
            "activate_duress_signal_task: signal %s no longer exists", signal_id
        )
        return

    signal.trigger_count += 1
    signal.last_triggered_at = timezone.now()
    signal.save(update_fields=['trigger_count', 'last_triggered_at'])

    user = signal.user
    duress_code = signal.duress_code

    if duress_code is None:
        # A signal registered before any code was configured still has to
        # raise something, or the alarm is silently swallowed. Fall back to
        # the user's highest-severity active code, else log an event only.
        #
        # Severity is ranked in Python, NOT via `order_by('-threat_level')`:
        # that column is a CharField, so descending sort is alphabetical and
        # would rank 'medium' > 'low' > 'high' > 'critical' -- picking the
        # mildest response for the most severe situation. Mirrors the
        # explicit ordering in `TrustedAuthority.should_notify_for_level`.
        severity = {'low': 0, 'medium': 1, 'high': 2, 'critical': 3}
        duress_code = max(
            DuressCode.objects.filter(user=user, is_active=True),
            key=lambda code: severity.get(code.threat_level, -1),
            default=None,
        )

    if duress_code is None:
        logger.warning(
            "Duress signal matched for user %s but no duress code is "
            "configured; recording event without an action config",
            user.username,
        )
        DuressEvent.objects.create(
            user=user,
            event_type='code_activated',
            threat_level='high',
            # `ip_address` is a non-nullable GenericIPAddressField, so a
            # missing IP must fall back rather than pass None -- the same
            # loopback default `check_for_duress_code` uses.
            ip_address=request_context.get('ip_address') or '127.0.0.1',  # nosec B104
            user_agent=request_context.get('user_agent', ''),
            response_status='partial',
            actions_taken=[{
                'action': 'signal_recorded',
                'note': 'no duress code configured; no response actions run',
            }],
        )
        return

    service = get_duress_code_service()
    service.activate_duress_mode(
        user=user,
        duress_code=duress_code,
        request_context=request_context,
        is_test=False,
    )

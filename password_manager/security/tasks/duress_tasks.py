"""
Celery task for duress-signal matching and activation.

Split out of ``DuressCodeService.consume_unlock_signal`` for a timing reason,
not an organisational one -- and split *twice*, for two different timing
reasons layered on top of each other.

Round 1: the ACTIVATION work moved here. ``consume_unlock_signal`` runs on
EVERY unlock and must do IDENTICAL work whether the signal matched or not --
see ``DuressSignal``'s docstring. A match used to run the full
``activate_duress_mode`` inline: DB writes for an evidence package, decoy-vault
lookup/generation, a ``DuressEvent``, and -- when silent alarms are enabled --
``SilentAlarmService.send_alerts()``, which does blocking SMTP (``send_mail``)
and an outbound ``requests.post()`` webhook call. A non-match returned after a
single digest comparison. That was a large, measurable, network-observable
latency difference on the same endpoint.

Round 2: the MATCH DETERMINATION itself moved here too, not just the
activation that follows it. Deferring only the activation work still left
``consume_unlock_signal`` calling ``.delay()`` ONLY on a match -- and
``Task.delay()``/``apply_async()`` synchronously publish the task message to
the broker before returning (real network I/O, not free), so whether that
publish happens at all was itself a smaller but still real, still
match-dependent timing signal. The fix: the request thread now enqueues this
task UNCONDITIONALLY, passing the raw signal, and the digest-comparison loop
against the user's active tokens runs here too -- entirely off the request
thread, where its outcome cannot affect response timing at all.
"""

import logging
import secrets

from celery import shared_task
from django.db.models import F
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task(name='security.activate_duress_signal')
def activate_duress_signal_task(user_id, signal, request_context):
    """Determine whether ``signal`` matches an active duress token for
    ``user_id``, and if so, run the full duress response.

    Deliberately NOT ``bind=True``/``max_retries``/``autoretry_for``: those
    only take effect if something in the body calls ``self.retry()``, which
    this never did -- the parameters were dead configuration that implied a
    retry guarantee this task never actually had (a genuine finding: an
    uncaught exception here always failed the task outright, exactly as it
    does now). Real retries are NOT a safe drop-in fix either, not without
    first making the activation path idempotent: it creates a
    ``DuressEvent``, may create an ``EvidencePackage`` and a decoy vault, and
    may call ``SilentAlarmService.send_alerts()`` (real outbound SMTP/
    webhook). A naive retry on transient failure would risk re-running all of
    that and double-sending a genuine alert to trusted authorities -- worse
    than the failure it was retrying. Idempotent activation is real,
    separately-scoped follow-up work, not a one-line addition to this task.

    Mirrors exactly what ``DuressCodeService.consume_unlock_signal`` used to
    do inline (both the matching loop and, on a match, the activation
    branch). Runs entirely off the request thread, so neither the comparison
    outcome nor the activation work that may follow it can be observed via
    HTTP response timing -- the request already returned before this runs.

    Never raises back to the caller: this always runs detached from any
    request (Celery already isolates task failures from the enqueueing
    thread), and a missing user or activation failure should not crash the
    worker loop.
    """
    from django.contrib.auth.models import User
    from security.models import DuressCode, DuressEvent, DuressSignal
    from security.services.duress_code_service import get_duress_code_service

    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        logger.warning(
            "activate_duress_signal_task: user %s no longer exists", user_id
        )
        return

    # Same constant-work loop `consume_unlock_signal` used to run on the
    # request thread -- compare every active signal rather than letting the
    # DB short-circuit on a hash lookup. Timing no longer matters for the
    # HTTP response at this point, but a worker process shared across many
    # users' tasks is still worth not leaking query-plan timing from, and
    # there is no reason to weaken the invariant just because it moved.
    candidate_hash = DuressSignal.hash_token(signal)
    active_signals = list(
        DuressSignal.objects.filter(user=user, is_active=True)
        .select_related('duress_code')
    )

    matched = None
    for candidate in active_signals:
        if secrets.compare_digest(candidate.token_hash, candidate_hash):
            matched = candidate

    if matched is None:
        return

    # A duress signal is single-fire per registration in spirit, but we do
    # NOT deactivate it here: a user under sustained coercion may unlock
    # repeatedly, and silently disarming the alarm after the first use is
    # the opposite of what this feature is for. Count instead.
    #
    # F()-expression update, not `matched.trigger_count += 1` then `.save()`:
    # the Python-side read-modify-write is a lost-update race under real
    # concurrent unlocks (two matching reports for the same signal, close
    # together, each task reads the same starting count) -- the DB performs
    # the increment atomically instead. `matched` is not read again after
    # this in the current task body, so no `refresh_from_db()` is needed to
    # see the new value locally.
    DuressSignal.objects.filter(pk=matched.pk).update(
        trigger_count=F('trigger_count') + 1,
        last_triggered_at=timezone.now(),
    )

    duress_code = matched.duress_code
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

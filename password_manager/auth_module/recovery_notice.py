"""
Notices of recovery and reset activity, with a cancel window.

Every recovery or reset path, when it starts and when it completes, records a
``RecoveryNotice`` (shown in the app under ``GET /api/auth/recovery-notices/``)
and emails the account a "this wasn't me" link valid for ``CANCEL_WINDOW``
(OWASP Forgot Password Cheat Sheet: notify the user; NIST SP 800-63B 6.1.2.4:
notify on authenticator changes). Following the link
(``POST /api/auth/recovery-notices/cancel/``):

* for a recovery that has started: voids it. Outstanding reset links stop
  working and pending guardian, social and passkey recovery attempts for the
  account are cancelled. Time-locked recovery has its own canary.
* for a recovery or reset that completed: ends every session and locks the
  account (``is_active = False``). Whoever completed it can no longer sign
  in; the owner restores access through support. In a zero-knowledge vault
  the server cannot give the vault back: the owner opens it again with their
  own recovery factor.

Only SHA-256 of the link's token is stored. Anonymous endpoints enqueue the
notice through a task (``send_recovery_notice``) so neither their response
nor its timing depends on whether the account exists.
"""

import hashlib
import logging
import secrets
from datetime import timedelta

from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction
from django.utils import timezone

logger = logging.getLogger(__name__)

CANCEL_WINDOW = timedelta(hours=72)

STARTED_EVENTS = {
    'reset_requested', 'passkey_recovery_started',
    'guardian_recovery_started', 'social_recovery_started',
}
COMPLETED_EVENTS = {
    'reset_completed', 'recovery_completed', 'passkey_recovery_completed',
    'guardian_recovery_completed', 'social_recovery_completed',
}

_DESCRIPTIONS = {
    'reset_requested': 'A password reset was requested',
    'reset_completed': 'Your sign-in password was reset',
    'recovery_completed': 'Your vault was recovered and its master password changed',
    'passkey_recovery_started': 'Passkey recovery was started',
    'passkey_recovery_completed': 'Your passkey was replaced through recovery',
    'guardian_recovery_started': 'Guardian recovery was started',
    'guardian_recovery_completed': 'Your guardians released your recovery shares',
    'social_recovery_started': 'Social recovery was started',
    'social_recovery_completed': 'Your vouchers released your recovery shares',
}


def _token_hash(token):
    return hashlib.sha256(token.encode('ascii')).hexdigest()


def _cancel_effect(event):
    if event in COMPLETED_EVENTS:
        return ('it ends every session and locks the account until you '
                'restore access through support')
    return 'it stops the recovery in progress'


def create_notice(user, event, ip_address=None, user_agent='', send_email=True):
    """Record the notice and email the cancel link. Returns the notice, with
    the link on ``notice.cancel_link`` (not stored) for a caller that puts it
    in an email of its own (``send_email=False``)."""
    from .models import RecoveryNotice

    token = secrets.token_urlsafe(32)
    now = timezone.now()
    notice = RecoveryNotice.objects.create(
        user=user, event=event, created_at=now, cancel_until=now + CANCEL_WINDOW,
        cancel_token_hash=_token_hash(token), ip_address=ip_address or None,
        user_agent=(user_agent or '')[:512],
    )
    link = f"{settings.FRONTEND_URL.rstrip('/')}/recovery/cancel?notice={token}"
    notice.cancel_link = link
    if not send_email:
        return notice
    hours = int(CANCEL_WINDOW.total_seconds() // 3600)
    body = (
        f"{_DESCRIPTIONS[event]} on your account at {now:%Y-%m-%d %H:%M} UTC"
        f"{f' from {ip_address}' if ip_address else ''}.\n\n"
        "If this was you, you need do nothing.\n\n"
        f"If this was NOT you, open this link within {hours} hours: {link}\n"
        f"Following it, {_cancel_effect(event)}."
    )
    sent = 0
    if user.email:
        sent = send_mail(f'Security notice: {_DESCRIPTIONS[event]}', body, None,
                         [user.email], fail_silently=True)
    if sent:
        notice.email_sent = True
        notice.save(update_fields=['email_sent'])
    else:
        logger.warning('Recovery notice %s not delivered by email', notice.id)
    return notice


def notify(user, event, request=None):
    """Queue a notice for ``user`` once the current transaction commits."""
    from .tasks import send_recovery_notice

    if event not in _DESCRIPTIONS:
        raise ValueError(f'unknown recovery event {event!r}')
    ip = None
    ua = ''
    if request is not None:
        from shared.client_ip import get_client_ip
        ip = get_client_ip(request)
        ua = request.META.get('HTTP_USER_AGENT', '')
    transaction.on_commit(lambda: dispatch(send_recovery_notice, user.pk, event, ip, ua))


def dispatch(task, *args):
    """Queue ``task``; if the broker is down, record the notice in-process.

    Runs after the recovery or reset has committed, so a failure here must
    not turn a completed recovery into an error response.
    """
    try:
        task.delay(*args)
    except Exception:
        logger.exception('Could not queue %s; running it in-process', task.name)
        try:
            task.apply(args=args)
        except Exception:
            logger.exception('Recovery notice %s failed', task.name)


def cancelled_since(user_id, when):
    """True if a notice of ``user_id`` was cancelled at or after ``when``.

    Lets a flow that has not stored its attempt yet (passkey recovery hands
    out a token at initiate and creates the row at complete) honour a cancel
    that happened after the token was issued.
    """
    from .models import RecoveryNotice

    return RecoveryNotice.objects.filter(
        user_id=user_id, cancelled_at__isnull=False, cancelled_at__gte=when,
    ).exists()


def _void_started_recovery(user):
    from .models import UserSalt
    from .passkey_primary_recovery_models import PasskeyRecoveryAttempt
    from .quantum_recovery_models import RecoveryAttempt

    # Outstanding reset links are bound to reset_generation.
    salt = UserSalt.objects.select_for_update().filter(user=user).first()
    if salt is not None:
        salt.reset_generation += 1
        salt.save(update_fields=['reset_generation'])
    RecoveryAttempt.objects.filter(
        recovery_setup__user=user,
        status__in=['initiated', 'challenge_phase', 'shard_collection',
                    'guardian_approval', 'final_verification'],
    ).update(status='cancelled', user_cancelled=True,
             failure_reason='Cancelled from a recovery notice')
    PasskeyRecoveryAttempt.objects.filter(
        user=user, status__in=['initiated', 'key_invalid', 'key_verified'],
    ).update(status='failed', failure_reason='Cancelled from a recovery notice')
    try:
        from social_recovery.models import SocialRecoveryRequest
    except ImportError:  # app not installed
        return
    SocialRecoveryRequest.objects.filter(
        circle__user=user, status__in=['pending', 'approved'],
    ).update(status='cancelled', completed_at=timezone.now())


def _lock_account(user):
    from .login_verifier import revoke_sessions

    revoke_sessions(user)
    user.is_active = False
    user.save(update_fields=['is_active'])


@transaction.atomic
def cancel_from_notice(token):
    """Apply a notice's cancel link. True if it did something."""
    from .models import RecoveryNotice

    if not isinstance(token, str) or not token.isascii() or not 20 <= len(token) <= 128:
        return False
    notice = RecoveryNotice.objects.select_for_update().select_related('user').filter(
        cancel_token_hash=_token_hash(token)).first()
    now = timezone.now()
    if notice is None or notice.cancelled_at or now > notice.cancel_until:
        return False
    notice.cancelled_at = now
    notice.save(update_fields=['cancelled_at'])
    if notice.event in COMPLETED_EVENTS:
        _lock_account(notice.user)
    _void_started_recovery(notice.user)
    logger.warning('Recovery notice %s (%s) cancelled; account %s', notice.id,
                   notice.event, 'locked' if notice.event in COMPLETED_EVENTS else 'kept')
    return True

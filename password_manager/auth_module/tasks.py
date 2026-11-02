"""
Celery tasks for auth_module.

Task modules named ``tasks.py`` are found by ``app.autodiscover_tasks()``.
"""

import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task
def send_password_reset_email(email, ip_address, user_agent):
    """
    The account-dependent half of POST /api/auth/request_password_reset/.

    The view answers every email the same way and does the same synchronous
    work for each (validate, enqueue this task), so neither the response nor
    its timing says whether the email has an account. Here, an existing
    account gets its reset link.
    """
    from django.conf import settings
    from django.contrib.auth.models import User
    from django.core.mail import send_mail
    from django.utils.encoding import force_bytes
    from django.utils.http import urlsafe_base64_encode

    from vault.models import AuditLog
    from .views import password_reset_token_generator

    user = User.objects.filter(email=email, is_active=True).first()
    if user is None:
        return False

    token = password_reset_token_generator.make_token(user)
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    # The link opens the frontend, which may be on another origin than the API
    reset_url = f"{settings.FRONTEND_URL.rstrip('/')}/reset-password/{uid}/{token}/"

    # fail_silently: a mail error must not surface as an error only real
    # accounts produce. The wording promises nothing the link does not do:
    # it sets a new password for signing in, and in a zero-knowledge vault
    # it cannot decrypt the items saved under the previous one.
    # The notice's cancel link voids this reset link (recovery_notice.py)
    from .recovery_notice import create_notice
    notice = create_notice(user, 'reset_requested', ip_address, user_agent, send_email=False)
    sent = send_mail(
        'Password Reset Request',
        f'A password reset was requested for your account: {reset_url} '
        'This link works once and sets a new password for signing in. It '
        'cannot decrypt your vault: items saved before the reset open only '
        'with a recovery factor such as your recovery key. '
        'If you did not ask for this, open this link to cancel the reset: '
        f'{notice.cancel_link}',
        'noreply@yourpasswordmanager.com',
        [user.email],
        fail_silently=True,
    )

    AuditLog.objects.create(
        user=user,
        action='password_reset_req',  # AuditLog.action is max_length=20
        ip_address=ip_address,
        user_agent=user_agent,
        status='success' if sent else 'failure'
    )
    if sent:
        notice.email_sent = True
        notice.save(update_fields=['email_sent'])
    return bool(sent)


@shared_task
def send_recovery_notice(user_id, event, ip_address=None, user_agent='', recovery_factor_id=None):
    """Record a recovery notice and email its cancel link
    (auth_module/recovery_notice.py)."""
    from django.contrib.auth.models import User

    from .recovery_notice import create_notice

    user = User.objects.filter(pk=user_id).first()
    if user is None:
        return None
    return str(create_notice(user, event, ip_address, user_agent,
                             recovery_factor_id=recovery_factor_id).id)


@shared_task
def notify_passkey_recovery_started(user_id, ip_address=None, user_agent=''):
    """The account-dependent half of passkey-recovery initiate: the view
    enqueues this for every request, so neither its response nor its timing
    says whether the account exists or has a recovery backup. ``user_id`` is
    the account the view issued a real token for, None for a decoy, so a backup
    that goes away while this is queued does not lose the notice."""
    from django.contrib.auth.models import User

    from .recovery_notice import create_notice

    user = User.objects.filter(pk=user_id).first() if user_id else None
    if user is None:
        return None
    return str(create_notice(user, 'passkey_recovery_started', ip_address, user_agent).id)


# failure_reason of an attempt whose link never reached the account. Nobody can
# use such an attempt, so it does not count toward the monthly limit.
GUARDIAN_EMAIL_NOT_DELIVERED = 'Recovery email not delivered'

# How long the emailed link can start an attempt. Until someone opens it on the
# device that made the request, an attempt says nothing about who asked, so it
# only uses up the limit on emails for this long: a stranger cannot hold the
# monthly limit against the owner.
GUARDIAN_UNCONFIRMED_WINDOW_HOURS = 24


def confirmed_guardian_attempts(recovery_setup):
    """This month's attempts someone confirmed from the emailed link and the
    requesting device, which is what the monthly limit counts. A cancelled one
    does not count, nor does one whose email never went out."""
    from datetime import timedelta

    from django.utils import timezone

    from .quantum_recovery_models import RecoveryAttempt

    return RecoveryAttempt.objects.filter(
        recovery_setup=recovery_setup,
        initiated_at__gte=timezone.now() - timedelta(days=30),
    ).exclude(status__in=['initiated', 'cancelled']).exclude(
        status='failed', failure_reason=GUARDIAN_EMAIL_NOT_DELIVERED)


@shared_task
def start_guardian_recovery(email, requester_public_key, device_fingerprint, ip_address, user_agent,
                            requester_token_hash):
    """
    The account-dependent half of POST /api/auth/quantum-recovery/initiate_recovery/.

    The view answers every email the same way and does the same synchronous
    work for each (validate, enqueue this task), so neither the response nor
    its timing says whether the email has an account or what state its recovery
    is in. Here, an account whose recovery can start gets an attempt and, by
    email, the link to it. A travel lock or a used-up monthly limit ends it
    quietly: one email per request would let anyone flood the account's inbox.
    ``requester_public_key`` and ``requester_token_hash`` are base64; the view
    has checked them.

    Django does not make User.email unique and the request names no account,
    so each account on the email is handled on its own: one with no setup, a
    lock or a used-up limit does not stop another.

    Returns how many accounts have an attempt, never its ID: Celery writes a
    task's return value to the worker log and the result backend, and the ID
    belongs in the account's email alone.
    """
    from .quantum_recovery_models import PasskeyRecoverySetup

    setup_ids = PasskeyRecoverySetup.objects.filter(
        user__email=email, user__is_active=True, is_active=True,
    ).order_by('pk').values_list('pk', flat=True)
    return sum(
        _start_guardian_attempt(setup_id, requester_public_key, device_fingerprint,
                                ip_address, user_agent, requester_token_hash)
        for setup_id in list(setup_ids)
    )


def _start_guardian_attempt(setup_id, requester_public_key, device_fingerprint, ip_address, user_agent,
                            requester_token_hash):
    """One account's attempt and email for start_guardian_recovery. Returns
    whether the account has a live attempt for this request."""
    import base64
    import hashlib
    import time
    from datetime import timedelta

    from django.conf import settings
    from django.core.mail import send_mail
    from django.db import transaction
    from django.utils import timezone

    from .quantum_recovery_models import PasskeyRecoverySetup, RecoveryAttempt, RecoveryAuditLog
    from .recovery_notice import create_notice
    from shared import sealed_shares

    public_key = base64.b64decode(requester_public_key)
    with transaction.atomic():
        # Locked so concurrent requests cannot pass the monthly limit together,
        # or create two attempts for one requester key.
        recovery_setup = PasskeyRecoverySetup.objects.select_for_update(of=('self',)).select_related(
            'user'
        ).filter(pk=setup_id, user__is_active=True, is_active=True).first()
        # A setup with no secret_check cannot complete (complete_recovery: 410)
        if (recovery_setup is None or not bytes(recovery_setup.secret_check)
                or recovery_setup.is_travel_locked()):
            return False
        user = recovery_setup.user
        usable = RecoveryAttempt.objects.filter(recovery_setup=recovery_setup).exclude(
            status='failed', failure_reason=GUARDIAN_EMAIL_NOT_DELIVERED)

        # The requester key is one-time, so it identifies the request. Workers
        # acknowledge after a task returns, and one lost mid-task gets this task
        # redelivered: that must not spend another monthly slot, and if the
        # email did not go out, it still has to. The same goes for one confirmed
        # meanwhile, whose shares stay locked until the alert is on record.
        attempt = usable.filter(requester_public_key=public_key).first()
        if attempt is not None and (attempt.canary_alert_sent_at or attempt.is_expired()
                                    or attempt.status not in ('initiated', 'guardian_approval')):
            return True
        if attempt is None:
            # Anyone can start an attempt for this email, so an unconfirmed one
            # only limits emails, and only for a day. Cancelled ones do not
            # count, so the owner's one cancel link, which stops every open
            # attempt, frees those slots at once.
            limit = recovery_setup.max_recovery_attempts_per_month
            unconfirmed = usable.filter(
                status='initiated',
                initiated_at__gte=timezone.now() - timedelta(hours=GUARDIAN_UNCONFIRMED_WINDOW_HOURS),
            ).count()
            if unconfirmed >= limit or confirmed_guardian_attempts(recovery_setup).count() >= limit:
                return False

            attempt = RecoveryAttempt.objects.create(
                recovery_setup=recovery_setup,
                initiated_from_ip=ip_address,
                initiated_from_device_fingerprint=device_fingerprint,
                requester_public_key=public_key,
                requester_token_hash=base64.b64decode(requester_token_hash),
                shards_required=recovery_setup.threshold_shards,
                # Every active guardian is asked: completion needs
                # threshold_shards re-sealed shares, and asking more than
                # the threshold lets recovery finish if one does not answer.
                guardian_approvals_required=recovery_setup.guardians.filter(status='active').count(),
                expires_at=timezone.now() + timedelta(days=recovery_setup.decay_window_days),
            )
            RecoveryAuditLog.objects.create(
                user=user,
                event_type='recovery_initiated',
                recovery_attempt_id=attempt.id,
                event_data={'attempt_id': str(attempt.id)},
                ip_address=ip_address,
                user_agent=user_agent,
                cryptographic_hash=hashlib.sha256(f"{user.id}:{time.time()}".encode()).hexdigest(),
            )

    # The link opens the frontend, which may be on another origin than the API.
    # The notice's cancel link cancels this attempt (recovery_notice.py).
    # The fingerprint tells the page which of this browser's one-time keys is
    # the one for this attempt; it is not a secret.
    link = (f"{settings.FRONTEND_URL.rstrip('/')}/recovery/guardian-attempt"
            f"?attempt={attempt.id}&key={sealed_shares.key_fingerprint(public_key)}")
    notice = create_notice(user, 'guardian_recovery_started', ip_address, user_agent, send_email=False)
    # The username tells apart the emails of accounts that share this address
    sent = send_mail(
        'Guardian recovery',
        f'Someone started guardian recovery for your account {user.username} from {ip_address}. '
        f'If it was you, open this link within {GUARDIAN_UNCONFIRMED_WINDOW_HOURS} hours, in the '
        f'browser you started from: {link} '
        "Only that browser holds the one-time key that opens your guardians' shares, "
        'so recovery cannot be finished anywhere else. Your guardians are asked only '
        'after you open the link. '
        f'If it was not you, open this link to cancel it: {notice.cancel_link}',
        None,
        [user.email],
        fail_silently=True,
    )
    if sent:
        now = timezone.now()
        RecoveryAttempt.objects.filter(pk=attempt.pk).update(canary_alert_sent_at=now)
        notice.email_sent = True
        notice.save(update_fields=['email_sent'])
    else:
        RecoveryAttempt.objects.filter(pk=attempt.pk, status='initiated').update(
            status='failed', failure_reason=GUARDIAN_EMAIL_NOT_DELIVERED)
        logger.warning('Guardian recovery email not delivered for attempt %s', attempt.id)
    return bool(sent)

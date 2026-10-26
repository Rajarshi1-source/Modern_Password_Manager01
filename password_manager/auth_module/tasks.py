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

    user = User.objects.filter(email=email).first()
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
def send_recovery_notice(user_id, event, ip_address=None, user_agent=''):
    """Record a recovery notice and email its cancel link
    (auth_module/recovery_notice.py)."""
    from django.contrib.auth.models import User

    from .recovery_notice import create_notice

    user = User.objects.filter(pk=user_id).first()
    if user is None:
        return None
    return str(create_notice(user, event, ip_address, user_agent).id)


@shared_task
def notify_passkey_recovery_started(username_or_email, ip_address=None, user_agent=''):
    """The account-dependent half of passkey-recovery initiate: the view
    enqueues this for every request, so neither its response nor its timing
    says whether the account exists or has a recovery backup."""
    from django.contrib.auth.models import User

    from .passkey_primary_recovery_models import PasskeyRecoveryBackup
    from .recovery_notice import create_notice

    user = (User.objects.filter(username=username_or_email).first()
            or User.objects.filter(email=username_or_email).first())
    if user is None or not PasskeyRecoveryBackup.objects.filter(user=user, is_active=True).exists():
        return None
    return str(create_notice(user, 'passkey_recovery_started', ip_address, user_agent).id)

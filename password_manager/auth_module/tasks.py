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
    sent = send_mail(
        'Password Reset Request',
        f'A password reset was requested for your account: {reset_url} '
        'This link works once and sets a new password for signing in. It '
        'cannot decrypt your vault: items saved before the reset open only '
        'with a recovery factor such as your recovery key.',
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
    return bool(sent)

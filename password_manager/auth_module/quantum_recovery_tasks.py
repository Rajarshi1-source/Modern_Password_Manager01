"""
Celery Tasks for Quantum-Resilient Recovery System

Handles:
- Guardian approval requests with randomized windows
- Automatic recovery expiration
- Canary alerts
"""

from celery import shared_task
from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction
from django.utils import timezone
from datetime import timedelta
import hashlib
import random
import smtplib
import time as _time
import logging

from .quantum_recovery_models import (
    RecoveryGuardian,
    RecoveryAttempt,
    TemporalChallenge,
    GuardianApproval,
    RecoveryAuditLog
)
from .recovery_notice import CANCEL_WINDOW, create_notice

logger = logging.getLogger(__name__)


@shared_task
def request_guardian_approvals(attempt_id):
    """
    Ask each guardian to approve a confirmed attempt, in a randomized window so
    guardians cannot coordinate. Workers acknowledge late and a repeated confirm
    can queue this again, so a guardian already asked keeps its approval.
    """
    with transaction.atomic():
        attempt = RecoveryAttempt.objects.select_for_update().filter(id=attempt_id).first()
        if (attempt is None or attempt.is_expired()
                or attempt.status not in ('initiated', 'guardian_approval')):
            return 0

        guardians = attempt.recovery_setup.guardians.filter(status='active').order_by('pk')
        if not guardians.exists():
            logger.warning(f"No active guardians for attempt {attempt_id}")
            return 0

        asked = set(attempt.guardian_approvals.values_list('guardian_id', flat=True))
        base_time = timezone.now()
        for guardian in guardians[:attempt.guardian_approvals_required]:
            if guardian.pk in asked:
                continue
            # Randomize approval window start (prevents coordinated attack)
            window_start = base_time + timedelta(hours=random.uniform(0, 12))  # nosec B311
            GuardianApproval.objects.create(
                recovery_attempt=attempt,
                guardian=guardian,
                approval_token=secrets.token_urlsafe(32),
                approval_window_start=window_start,
                approval_window_end=window_start + timedelta(hours=24),
            )

        attempt.status = 'guardian_approval'
        attempt.save(update_fields=['status'])
        approvals = list(attempt.guardian_approvals.filter(status='pending'))

    # The email goes out when the guardian's window opens.
    for approval in approvals:
        send_guardian_approval_request.apply_async(
            args=[str(approval.id)], eta=approval.approval_window_start)
    logger.info(f"Requested {len(approvals)} guardian approvals for attempt {attempt_id}")
    return len(approvals)


def guardians_left_unasked(attempt):
    """Whether request_guardian_approvals should run again: it never asked
    anyone, or a guardian's window is open with no email on record because
    queueing or sending it failed. Repeating it emails nobody twice
    (send_guardian_approval_request)."""
    if not attempt.guardian_approvals.exists():
        return True
    now = timezone.now()
    open_ids = attempt.guardian_approvals.filter(
        status='pending', approval_window_start__lte=now, approval_window_end__gte=now,
    ).values_list('id', flat=True)
    emailed = set(RecoveryAuditLog.objects.filter(
        event_type='guardian_approval_requested', recovery_attempt_id=attempt.id,
    ).values_list('event_data__approval_id', flat=True))
    return any(str(approval_id) not in emailed for approval_id in open_ids)


def _mail_failure_is_temporary(exc):
    """Whether sending again could work, given an OSError from send_mail (which
    SMTPException is): a lost connection or a 4xx reply such as greylisting. A
    5xx reply, such as a refused address, would only repeat."""
    if isinstance(exc, smtplib.SMTPRecipientsRefused):
        return any(400 <= code < 500 for code, _ in exc.recipients.values())
    if isinstance(exc, smtplib.SMTPResponseException):
        return 400 <= exc.smtp_code < 500
    return True


@shared_task(bind=True, max_retries=3, default_retry_delay=600)
def send_guardian_approval_request(self, approval_id):
    """
    Email a guardian its approval link, unless the attempt or the guardian's
    window has closed since the window was picked. A task with a far-off ETA can be delivered more than once
    (the broker's visibility timeout), and the audit entry below stops a repeat.
    """
    with transaction.atomic():
        approval = GuardianApproval.objects.select_for_update(of=('self',)).select_related(
            'guardian', 'recovery_attempt__recovery_setup__user',
        ).filter(id=approval_id, status='pending').first()
        if approval is None:
            return False
        attempt = approval.recovery_attempt
        if (attempt.status != 'guardian_approval' or attempt.is_expired()
                or attempt.recovery_setup.is_travel_locked()
                or timezone.now() > approval.approval_window_end):
            return False
        if RecoveryAuditLog.objects.filter(
                event_type='guardian_approval_requested', recovery_attempt_id=attempt.id,
                event_data__approval_id=str(approval_id)).exists():
            return False

        user = attempt.recovery_setup.user
        # In the fragment, so the token reaches no server's logs (linkToken.js).
        approval_url = (f"{settings.FRONTEND_URL.rstrip('/')}/recovery/guardian-approve#"
                        f"{approval.approval_token}")
        try:
            send_mail(
                'Recovery approval needed',
                f'Someone started account recovery for {user.username}, who chose you as a guardian.\n\n'
                'Contact them by phone or in person before you do anything. If they did not '
                'start this, deny it. If they did, ask them to read you the code on their '
                'recovery page, and enter it here, in the browser that holds your guardian key:\n'
                f'{approval_url}\n\n'
                f'This request closes at {approval.approval_window_end:%Y-%m-%d %H:%M} UTC.',
                None,
                [approval.guardian.encrypted_guardian_info.decode('utf-8')],
            )
        except OSError as exc:
            if not _mail_failure_is_temporary(exc):
                raise
            raise self.retry(exc=exc)

        RecoveryAuditLog.objects.create(
            user=user,
            event_type='guardian_approval_requested',
            recovery_attempt_id=attempt.id,
            event_data={
                'guardian_id': str(approval.guardian_id),
                'approval_id': str(approval_id),
            },
            cryptographic_hash=hashlib.sha256(
                f"{user.id}:{_time.time()}".encode()
            ).hexdigest(),
        )
    logger.info(f"Sent guardian approval request {approval_id}")
    return True


@shared_task(bind=True, max_retries=3, default_retry_delay=600)
def send_guardian_invitation(self, guardian_id):
    """Email a guardian its invitation link. The owner's setup page also shows
    the link, so a failed send does not strand the setup."""
    guardian = RecoveryGuardian.objects.select_related('recovery_setup__user').filter(
        id=guardian_id, status='pending').first()
    if guardian is None or not guardian.is_invitation_valid():
        return False
    invitation_url = (f"{settings.FRONTEND_URL.rstrip('/')}/recovery/guardian-invite#"
                      f"{guardian.invitation_token}")
    try:
        send_mail(
            'You have been asked to be a recovery guardian',
            f'{guardian.recovery_setup.user.username} chose you as a recovery guardian. '
            'If you do not know them or did not give them your guardian key, ignore this email.\n\n'
            'To accept, open this link in the browser that holds your guardian key:\n'
            f'{invitation_url}\n\n'
            f'The invitation closes at {guardian.invitation_expires_at:%Y-%m-%d %H:%M} UTC.',
            None,
            [guardian.encrypted_guardian_info.decode('utf-8')],
        )
    except OSError as exc:
        if not _mail_failure_is_temporary(exc):
            raise
        raise self.retry(exc=exc)
    return True


@shared_task
def send_canary_alert(attempt_id):
    """
    Send canary alert to legitimate user about recovery attempt
    
    This gives the real user time to cancel if they didn't initiate recovery
    """
    try:
        attempt = RecoveryAttempt.objects.get(id=attempt_id)
        user = attempt.recovery_setup.user
        
        # The notice holds only a hash of the link's secret token, and its
        # page cancels on a button press (recovery_notice.py).
        notice = create_notice(user, 'guardian_recovery_started', attempt.initiated_from_ip,
                               send_email=False)
        cancel_url = notice.cancel_link
        hours = int(CANCEL_WINDOW.total_seconds() // 3600)
        
        message = f"""
        ⚠️ URGENT: Account Recovery Initiated
        
        Someone initiated account recovery for your SecureVault account.
        
        If this WAS you:
        - No action needed
        - Continue from the link in your recovery email
        
        If this WAS NOT you:
        - Your account may be under attack
        - Cancel immediately: {cancel_url}
        - Change your password
        
        Recovery initiated from:
        - IP: {attempt.initiated_from_ip}
        - Location: {attempt.initiated_from_location}
        - Time: {attempt.initiated_at}
        
        You have {hours} hours to cancel this recovery.
        """
        
        # Send via multiple channels for critical alert
        from django.core.mail import send_mail
        sent = send_mail(
            subject='⚠️ URGENT: Account Recovery Initiated',
            message=message,
            from_email='security@securevault.com',
            recipient_list=[user.email],
            fail_silently=False
        )
        if sent:
            notice.email_sent = True
            notice.save(update_fields=['email_sent'])
        
        # Also send SMS if available
        # send_sms(user.phone, message_short)
        
        # Log audit event
        RecoveryAuditLog.objects.create(
            user=user,
            event_type='canary_alert_sent',
            recovery_attempt_id=attempt.id,
            event_data={
                'attempt_id': str(attempt_id),
                'sent_at': timezone.now().isoformat()
            },
            cryptographic_hash=hashlib.sha256(
                f"{user.id}:{_time.time()}".encode()
            ).hexdigest(),
        )
        
        logger.info(f"Sent canary alert for attempt {attempt_id}")
        
    except Exception as e:
        logger.error(f"Error sending canary alert: {str(e)}")


@shared_task
def check_expired_recovery_attempts():
    """
    Periodic task to check and expire old recovery attempts
    Runs every hour
    """
    try:
        expired_attempts = RecoveryAttempt.objects.filter(
            status__in=['initiated', 'challenge_phase', 'guardian_approval'],
            expires_at__lt=timezone.now()
        )
        
        for attempt in expired_attempts:
            attempt.status = 'expired'
            attempt.failure_reason = 'Recovery attempt expired'
            attempt.save()
            
            # Log audit event
            RecoveryAuditLog.objects.create(
                user=attempt.recovery_setup.user,
                event_type='recovery_failed',
                recovery_attempt_id=attempt.id,
                event_data={
                    'reason': 'expired'
                },
                cryptographic_hash=hashlib.sha256(
                    f"{attempt.recovery_setup.user.id}:{_time.time()}".encode()
                ).hexdigest(),
            )
        
        logger.info(f"Expired {expired_attempts.count()} recovery attempts")
        
    except Exception as e:
        logger.error(f"Error checking expired recovery attempts: {str(e)}")


@shared_task
def check_expired_challenges():
    """
    Periodic task to mark expired challenges
    Runs every 30 minutes
    """
    try:
        expired_challenges = TemporalChallenge.objects.filter(
            status__in=['pending', 'sent'],
            expires_at__lt=timezone.now()
        )
        
        for challenge in expired_challenges:
            challenge.status = 'expired'
            challenge.save()
            
            # Update attempt statistics
            attempt = challenge.recovery_attempt
            attempt.challenges_failed += 1
            attempt.calculate_trust_score()
        
        logger.info(f"Expired {expired_challenges.count()} challenges")
        
    except Exception as e:
        logger.error(f"Error checking expired challenges: {str(e)}")


# Helper functions

def generate_challenge_data(challenge_type, user, attempt):
    """
    Generate challenge data based on type
    
    Returns: (encrypted_challenge_data, encrypted_expected_response)
    """
    import secrets
    
    if challenge_type == 'historical_activity':
        # Ask about past account activity
        challenge = "What was the first website you saved to your vault?"
        expected = "example.com"  # Would be from user history
    
    elif challenge_type == 'device_fingerprint':
        # Ask about typical devices
        challenge = "Which browser do you typically use?"
        expected = "Chrome"  # Would be from behavioral data
    
    elif challenge_type == 'geolocation_pattern':
        # Ask about typical locations
        challenge = "Which city do you usually log in from?"
        expected = "San Francisco"  # Would be from location history
    
    elif challenge_type == 'usage_time_window':
        # Ask about typical usage times
        challenge = "What time of day do you usually access your vault?"
        expected = "evening"  # Would be from behavioral data
    
    elif challenge_type == 'vault_content_knowledge':
        # Ask about vault contents (without exposing passwords)
        challenge = "How many passwords do you have saved?"
        expected = "15"  # Would be from vault statistics
    
    else:
        challenge = "Verify your identity"
        expected = "confirmed"
    
    # Encrypt challenge and response (simplified here)
    # In production, use proper encryption
    encrypted_challenge = challenge.encode('utf-8')
    encrypted_response = expected.encode('utf-8')
    
    return encrypted_challenge, encrypted_response


# Add these imports at the top
import secrets


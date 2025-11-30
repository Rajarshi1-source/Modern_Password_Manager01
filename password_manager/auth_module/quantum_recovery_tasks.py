"""
Celery Tasks for Quantum-Resilient Recovery System

Handles:
- Temporal challenge distribution over 3-7 days
- Guardian approval requests with randomized windows
- Automatic recovery expiration
- Canary alerts
"""

from celery import shared_task
from django.utils import timezone
from datetime import timedelta
import random
import logging

from .quantum_recovery_models import (
    RecoveryAttempt,
    TemporalChallenge,
    GuardianApproval,
    RecoveryAuditLog
)
from .services.challenge_generator import challenge_generator

logger = logging.getLogger(__name__)


@shared_task
def create_and_send_temporal_challenges(attempt_id):
    """
    Create and schedule temporal challenges for a recovery attempt
    
    Challenges are distributed over 3 days at random intervals
    to verify identity through temporal patterns.
    """
    try:
        attempt = RecoveryAttempt.objects.get(id=attempt_id)
        recovery_setup = attempt.recovery_setup
        user = recovery_setup.user
        
        # Generate personalized challenges using the challenge generator
        challenges = challenge_generator.generate_challenge_set(user, num_challenges=5)
        
        distribution_days = recovery_setup.challenge_distribution_days
        
        for i, (challenge_type, question, answer) in enumerate(challenges):
            # Randomize send time within distribution period
            hours_offset = random.uniform(0, distribution_days * 24)
            send_time = timezone.now() + timedelta(hours=hours_offset)
            
            # Encrypt challenge data
            encrypted_question, encrypted_answer = challenge_generator.encrypt_challenge_data(
                question, answer
            )
            
            # Create challenge
            challenge = TemporalChallenge.objects.create(
                recovery_attempt=attempt,
                challenge_type=challenge_type,
                encrypted_challenge_data=encrypted_question,
                encrypted_expected_response=encrypted_answer,
                delivery_channel='email',  # Can be email, sms, app_notification
                sent_to=user.email,
                expected_response_time_window_start=send_time,
                expected_response_time_window_end=send_time + timedelta(hours=24),
                expires_at=send_time + timedelta(hours=48)
            )
            
            # Schedule challenge delivery
            send_temporal_challenge.apply_async(
                args=[str(challenge.id)],
                eta=send_time
            )
        
        # Update attempt
        attempt.challenges_sent = len(challenges)
        attempt.status = 'challenge_phase'
        attempt.save()
        
        logger.info(f"Created {len(challenges)} temporal challenges for attempt {attempt_id}")
        
    except Exception as e:
        logger.error(f"Error creating temporal challenges: {str(e)}")


@shared_task
def send_temporal_challenge(challenge_id):
    """
    Send a temporal challenge to the user via specified channel
    """
    try:
        challenge = TemporalChallenge.objects.get(id=challenge_id)
        
        # Check if challenge is still valid
        if challenge.status != 'pending':
            logger.info(f"Challenge {challenge_id} already processed, skipping")
            return
        
        attempt = challenge.recovery_attempt
        user = attempt.recovery_setup.user
        
        # Prepare challenge message based on type
        message = prepare_challenge_message(challenge)
        
        # Send via appropriate channel
        if challenge.delivery_channel == 'email':
            send_challenge_email(user.email, message, challenge_id)
        elif challenge.delivery_channel == 'sms':
            send_challenge_sms(challenge.sent_to, message, challenge_id)
        elif challenge.delivery_channel == 'app_notification':
            send_challenge_push_notification(user, message, challenge_id)
        
        # Update challenge status
        challenge.status = 'sent'
        challenge.sent_at = timezone.now()
        challenge.save()
        
        # Log audit event
        RecoveryAuditLog.objects.create(
            user=user,
            event_type='challenge_sent',
            recovery_attempt_id=attempt.id,
            event_data={
                'challenge_id': str(challenge_id),
                'challenge_type': challenge.challenge_type
            }
        )
        
        logger.info(f"Sent temporal challenge {challenge_id} to {user.email}")
        
    except Exception as e:
        logger.error(f"Error sending temporal challenge {challenge_id}: {str(e)}")


@shared_task
def request_guardian_approvals(attempt_id):
    """
    Request approvals from guardians with randomized windows
    to prevent collusion attacks
    """
    try:
        attempt = RecoveryAttempt.objects.get(id=attempt_id)
        recovery_setup = attempt.recovery_setup
        
        # Get active guardians
        guardians = recovery_setup.guardians.filter(status='active')
        
        if guardians.count() == 0:
            logger.warning(f"No active guardians for attempt {attempt_id}")
            return
        
        # Calculate how many guardian approvals needed
        approvals_needed = attempt.guardian_approvals_required
        selected_guardians = list(guardians[:approvals_needed])
        
        # Create approval requests with randomized windows
        base_time = timezone.now()
        
        for i, guardian in enumerate(selected_guardians):
            # Randomize approval window start (prevents coordinated attack)
            window_start_offset = random.uniform(0, 12)  # 0-12 hours
            window_start = base_time + timedelta(hours=window_start_offset)
            window_end = window_start + timedelta(hours=24)  # 24-hour window
            
            # Generate secure approval token
            approval_token = secrets.token_urlsafe(32)
            
            # Create approval request
            approval = GuardianApproval.objects.create(
                recovery_attempt=attempt,
                guardian=guardian,
                approval_token=approval_token,
                approval_window_start=window_start,
                approval_window_end=window_end
            )
            
            # Schedule approval request notification
            send_guardian_approval_request.apply_async(
                args=[str(approval.id)],
                eta=window_start
            )
        
        # Update attempt status
        attempt.status = 'guardian_approval'
        attempt.save()
        
        logger.info(f"Created {len(selected_guardians)} guardian approval requests for attempt {attempt_id}")
        
    except Exception as e:
        logger.error(f"Error requesting guardian approvals: {str(e)}")


@shared_task
def send_guardian_approval_request(approval_id):
    """
    Send approval request to a guardian
    """
    try:
        approval = GuardianApproval.objects.get(id=approval_id)
        guardian = approval.guardian
        attempt = approval.recovery_attempt
        user = attempt.recovery_setup.user
        
        # Decrypt guardian contact info (simplified here)
        guardian_email = guardian.encrypted_guardian_info.decode('utf-8')
        
        # Prepare approval request message
        approval_url = f"https://securevault.com/recovery/guardian-approve/{approval.approval_token}"
        
        message = f"""
        Recovery Approval Request
        
        A user you're protecting has initiated account recovery.
        
        If you recognize this request, please approve it:
        {approval_url}
        
        This request expires at: {approval.approval_window_end}
        
        If you don't recognize this request, please report it immediately.
        """
        
        # Send email (using Django email backend)
        from django.core.mail import send_mail
        send_mail(
            subject='Recovery Approval Needed - SecureVault',
            message=message,
            from_email='noreply@securevault.com',
            recipient_list=[guardian_email],
            fail_silently=False
        )
        
        # Log audit event
        RecoveryAuditLog.objects.create(
            user=user,
            event_type='guardian_approval_requested',
            recovery_attempt_id=attempt.id,
            event_data={
                'guardian_id': str(guardian.id),
                'approval_id': str(approval_id)
            }
        )
        
        logger.info(f"Sent guardian approval request {approval_id}")
        
    except Exception as e:
        logger.error(f"Error sending guardian approval request {approval_id}: {str(e)}")


@shared_task
def send_canary_alert(attempt_id):
    """
    Send canary alert to legitimate user about recovery attempt
    
    This gives the real user 48 hours to cancel if they didn't initiate recovery
    """
    try:
        attempt = RecoveryAttempt.objects.get(id=attempt_id)
        user = attempt.recovery_setup.user
        
        # Prepare canary alert message
        cancel_url = f"https://securevault.com/recovery/cancel/{attempt.id}"
        
        message = f"""
        ⚠️ URGENT: Account Recovery Initiated
        
        Someone initiated account recovery for your SecureVault account.
        
        If this WAS you:
        - No action needed
        - Check your email for recovery challenges
        
        If this WAS NOT you:
        - Your account may be under attack
        - Cancel immediately: {cancel_url}
        - Change your password
        
        Recovery initiated from:
        - IP: {attempt.initiated_from_ip}
        - Location: {attempt.initiated_from_location}
        - Time: {attempt.initiated_at}
        
        You have 48 hours to cancel this recovery.
        """
        
        # Send via multiple channels for critical alert
        from django.core.mail import send_mail
        send_mail(
            subject='⚠️ URGENT: Account Recovery Initiated',
            message=message,
            from_email='security@securevault.com',
            recipient_list=[user.email],
            fail_silently=False
        )
        
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
            }
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
                }
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


def prepare_challenge_message(challenge):
    """
    Prepare user-friendly challenge message
    """
    challenge_data = challenge.encrypted_challenge_data.decode('utf-8')
    
    message = f"""
    Recovery Challenge {challenge.recovery_attempt.challenges_completed + 1}/5
    
    {challenge_data}
    
    Respond at: https://securevault.com/recovery/challenge/{challenge.id}
    
    This challenge expires in 48 hours.
    """
    
    return message


def send_challenge_email(email, message, challenge_id):
    """
    Send challenge via email
    """
    from django.core.mail import send_mail
    
    send_mail(
        subject='SecureVault Recovery Challenge',
        message=message,
        from_email='noreply@securevault.com',
        recipient_list=[email],
        fail_silently=False
    )


def send_challenge_sms(phone, message, challenge_id):
    """
    Send challenge via SMS (placeholder)
    """
    # Implement SMS sending using Twilio or similar
    pass


def send_challenge_push_notification(user, message, challenge_id):
    """
    Send challenge via push notification (placeholder)
    """
    # Implement push notification using Firebase or similar
    pass


# Add these imports at the top
import secrets


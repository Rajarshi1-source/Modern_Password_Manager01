"""
Notification Service for Recovery System

Handles email, SMS, and push notifications for:
- Temporal challenges
- Guardian approval requests
- Canary alerts
"""

from django.core.mail import send_mail, EmailMultiAlternatives
from django.template.loader import render_to_string
from django.conf import settings
from django.utils.html import strip_tags
import logging

logger = logging.getLogger(__name__)


class NotificationService:
    """Send recovery-related notifications"""
    
    def __init__(self):
        # Initialize Twilio client if configured
        self.twilio_client = None
        if hasattr(settings, 'TWILIO_ACCOUNT_SID') and settings.TWILIO_ACCOUNT_SID:
            try:
                from twilio.rest import Client
                self.twilio_client = Client(
                    settings.TWILIO_ACCOUNT_SID,
                    settings.TWILIO_AUTH_TOKEN
                )
            except ImportError:
                logger.warning("Twilio library not installed. SMS notifications disabled.")
    
    def send_temporal_challenge_email(self, user, challenge):
        """Send challenge via email"""
        try:
            context = {
                'user': user,
                'challenge_question': challenge.encrypted_challenge_data.decode('utf-8'),
                'challenge_url': f"{settings.FRONTEND_URL}/recovery/challenge/{challenge.id}",
                'expires_at': challenge.expires_at,
                'challenge_number': challenge.recovery_attempt.challenges_completed + 1,
                'total_challenges': challenge.recovery_attempt.challenges_sent
            }
            
            # Render templates
            html_message = render_to_string('recovery/challenge_email.html', context)
            plain_message = render_to_string('recovery/challenge_email.txt', context)
            
            # Send email
            msg = EmailMultiAlternatives(
                subject='SecureVault Recovery Challenge',
                body=plain_message,
                from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@securevault.com'),
                to=[user.email]
            )
            msg.attach_alternative(html_message, "text/html")
            msg.send()
            
            logger.info(f"Sent challenge email to {user.email} for challenge {challenge.id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send challenge email: {str(e)}")
            return False
    
    def send_guardian_approval_email(self, guardian, approval):
        """Send approval request to guardian"""
        try:
            guardian_email = guardian.encrypted_guardian_info.decode('utf-8')
            user = approval.recovery_attempt.recovery_setup.user
            
            context = {
                'guardian_email': guardian_email,
                'user_email': user.email,
                'approval_url': f"{settings.FRONTEND_URL}/recovery/guardian-approve/{approval.approval_token}",
                'expires_at': approval.approval_window_end,
                'requires_video': guardian.requires_video_verification
            }
            
            # Render templates
            html_message = render_to_string('recovery/guardian_approval_email.html', context)
            plain_message = render_to_string('recovery/guardian_approval_email.txt', context)
            
            # Send email
            msg = EmailMultiAlternatives(
                subject='Recovery Approval Needed - SecureVault',
                body=plain_message,
                from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@securevault.com'),
                to=[guardian_email]
            )
            msg.attach_alternative(html_message, "text/html")
            msg.send()
            
            logger.info(f"Sent guardian approval email to {guardian_email}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send guardian approval email: {str(e)}")
            return False
    
    def send_canary_alert(self, attempt):
        """Send canary alert to user"""
        try:
            user = attempt.recovery_setup.user
            
            context = {
                'user': user,
                'cancel_url': f"{settings.FRONTEND_URL}/recovery/cancel/{attempt.id}",
                'ip_address': attempt.initiated_from_ip,
                'location': attempt.initiated_from_location,
                'initiated_at': attempt.initiated_at,
                'expires_at': attempt.expires_at
            }
            
            # Render templates
            html_message = render_to_string('recovery/canary_alert_email.html', context)
            plain_message = render_to_string('recovery/canary_alert_email.txt', context)
            
            # Send email
            msg = EmailMultiAlternatives(
                subject='⚠️ URGENT: Account Recovery Initiated',
                body=plain_message,
                from_email=getattr(settings, 'SECURITY_EMAIL', 'security@securevault.com'),
                to=[user.email]
            )
            msg.attach_alternative(html_message, "text/html")
            msg.send()
            
            # Send SMS if available and user has phone number
            if hasattr(user, 'phone_number') and user.phone_number and self.twilio_client:
                self.send_canary_alert_sms(user, attempt)
            
            logger.info(f"Sent canary alert to {user.email} for attempt {attempt.id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send canary alert: {str(e)}")
            return False
    
    def send_canary_alert_sms(self, user, attempt):
        """Send canary alert via SMS"""
        if not self.twilio_client:
            logger.warning("Twilio not configured, skipping SMS")
            return False
        
        try:
            message = (
                f"⚠️ URGENT: Someone initiated recovery for your SecureVault account. "
                f"If this wasn't you, cancel immediately at: {settings.FRONTEND_URL}/recovery/cancel/{attempt.id}"
            )
            
            self.twilio_client.messages.create(
                body=message,
                from_=settings.TWILIO_PHONE_NUMBER,
                to=user.phone_number
            )
            
            logger.info(f"Sent canary alert SMS to {user.phone_number}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send SMS: {str(e)}")
            return False
    
    def send_recovery_complete_email(self, user, attempt):
        """Send recovery completion notification"""
        try:
            context = {
                'user': user,
                'completed_at': attempt.completed_at,
                'trust_score': attempt.trust_score,
            }
            
            # Render templates
            html_message = render_to_string('recovery/recovery_complete_email.html', context)
            plain_message = render_to_string('recovery/recovery_complete_email.txt', context)
            
            # Send email
            msg = EmailMultiAlternatives(
                subject='Account Recovery Completed - SecureVault',
                body=plain_message,
                from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@securevault.com'),
                to=[user.email]
            )
            msg.attach_alternative(html_message, "text/html")
            msg.send()
            
            logger.info(f"Sent recovery complete email to {user.email}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send recovery complete email: {str(e)}")
            return False


# Global instance
notification_service = NotificationService()


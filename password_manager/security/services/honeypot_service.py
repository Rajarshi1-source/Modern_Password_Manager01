"""
Honeypot Email Service
======================

Core business logic for honeypot email breach detection system.
Handles honeypot creation, activity monitoring, breach detection,
and credential rotation coordination.

@author Password Manager Team
@created 2026-02-01
"""

import logging
from typing import Optional, Dict, Any, List, Tuple
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from django.core.mail import send_mail
from datetime import timedelta

from ..models import (
    HoneypotConfiguration,
    HoneypotEmail,
    HoneypotActivity,
    HoneypotBreachEvent,
    CredentialRotationLog,
)
from .honeypot_email_provider import HoneypotEmailProvider

logger = logging.getLogger(__name__)


class HoneypotEmailService:
    """
    Main service for managing honeypot emails and breach detection.
    """
    
    # Breach detection thresholds
    SPAM_THRESHOLD_FOR_BREACH = 1  # Any spam = breach
    ACTIVITY_SPIKE_THRESHOLD = 3  # Activities in 24h
    HIGH_CONFIDENCE_THRESHOLD = 0.8
    
    def __init__(self):
        self._provider_class = HoneypotEmailProvider
    
    # =========================================================================
    # Configuration Management
    # =========================================================================
    
    def get_or_create_config(self, user) -> HoneypotConfiguration:
        """Get or create honeypot configuration for a user."""
        config, created = HoneypotConfiguration.objects.get_or_create(
            user=user,
            defaults={
                'is_enabled': True,
                'email_provider': 'simplelogin',
                'auto_rotate_on_breach': False,
                'require_confirmation': True,
                'auto_create_on_signup': False,
                'suggest_honeypot_creation': True,
            }
        )
        if created:
            logger.info(f"Created honeypot config for user {user.username}")
        return config
    
    def update_config(self, user, **kwargs) -> HoneypotConfiguration:
        """Update honeypot configuration settings."""
        config = self.get_or_create_config(user)
        
        allowed_fields = {
            'is_enabled', 'email_provider', 'provider_api_key',
            'custom_domain', 'auto_rotate_on_breach', 'require_confirmation',
            'auto_create_on_signup', 'suggest_honeypot_creation',
            'notify_on_any_activity', 'notify_on_breach', 'notification_email',
            'max_honeypots'
        }
        
        for key, value in kwargs.items():
            if key in allowed_fields:
                setattr(config, key, value)
        
        config.save()
        logger.info(f"Updated honeypot config for user {user.username}")
        return config
    
    # =========================================================================
    # Honeypot CRUD Operations
    # =========================================================================
    
    @transaction.atomic
    def create_honeypot(
        self,
        user,
        service_name: str,
        service_domain: str = '',
        vault_item_id: str = None,
        notes: str = '',
        tags: List[str] = None
    ) -> HoneypotEmail:
        """
        Create a new honeypot email for a service.
        
        Args:
            user: Django user
            service_name: Name of the service
            service_domain: Domain of the service (optional)
            vault_item_id: UUID of linked vault item (optional)
            notes: User notes
            tags: List of tags
            
        Returns:
            HoneypotEmail instance
        """
        config = self.get_or_create_config(user)
        
        # Check limits
        if not config.can_create_honeypot:
            raise ValueError(
                f"Honeypot limit reached ({config.max_honeypots}). "
                "Please delete unused honeypots or upgrade your plan."
            )
        
        # Check if honeypot already exists for this service
        existing = HoneypotEmail.objects.filter(
            user=user,
            service_name=service_name,
            is_active=True
        ).first()
        
        if existing:
            raise ValueError(f"Honeypot already exists for {service_name}")
        
        try:
            # Create alias via provider
            alias_email, provider_alias_id = self._provider_class.create_honeypot_alias(
                config, service_name
            )
            
            # Create honeypot record
            honeypot = HoneypotEmail.objects.create(
                user=user,
                honeypot_address=alias_email,
                provider_alias_id=provider_alias_id,
                service_name=service_name,
                service_domain=service_domain,
                vault_item_id=vault_item_id,
                status='active',
                notes=notes,
                tags=tags or []
            )
            
            logger.info(
                f"Created honeypot for {service_name}: {alias_email} "
                f"(user: {user.username})"
            )
            
            return honeypot
            
        except Exception as e:
            logger.error(f"Failed to create honeypot: {e}")
            raise
    
    def get_honeypot(self, honeypot_id: str, user) -> Optional[HoneypotEmail]:
        """Get a honeypot by ID for a user."""
        try:
            return HoneypotEmail.objects.get(
                id=honeypot_id,
                user=user
            )
        except HoneypotEmail.DoesNotExist:
            return None
    
    def get_user_honeypots(
        self,
        user,
        status: str = None,
        include_inactive: bool = False
    ) -> List[HoneypotEmail]:
        """Get all honeypots for a user."""
        queryset = HoneypotEmail.objects.filter(user=user)
        
        if not include_inactive:
            queryset = queryset.filter(is_active=True)
        
        if status:
            queryset = queryset.filter(status=status)
        
        return list(queryset.order_by('-created_at'))
    
    @transaction.atomic
    def delete_honeypot(self, honeypot: HoneypotEmail) -> bool:
        """
        Delete (deactivate) a honeypot.
        
        This deactivates the honeypot but keeps records for audit.
        Also deletes the alias from the provider.
        """
        try:
            config = self.get_or_create_config(honeypot.user)
            
            # Delete from provider
            if honeypot.provider_alias_id:
                self._provider_class.delete_honeypot_alias(
                    config, 
                    honeypot.provider_alias_id
                )
            
            # Deactivate honeypot
            honeypot.is_active = False
            honeypot.status = 'disabled'
            honeypot.save()
            
            logger.info(f"Deleted honeypot {honeypot.id} for {honeypot.service_name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete honeypot: {e}")
            return False
    
    # =========================================================================
    # Activity Processing
    # =========================================================================
    
    def process_incoming_email(
        self,
        honeypot_address: str,
        sender_address: str,
        subject: str,
        headers: Dict[str, Any] = None,
        is_spam: bool = False,
        spam_score: float = 0.0
    ) -> Tuple[HoneypotActivity, bool]:
        """
        Process an incoming email to a honeypot address.
        
        This is called by webhook handlers when email providers
        forward incoming emails.
        
        Args:
            honeypot_address: The honeypot email that received mail
            sender_address: Sender's email address
            subject: Email subject (will be hashed for privacy)
            headers: Email headers (will be encrypted)
            is_spam: Whether provider flagged as spam
            spam_score: Spam confidence score (0-1)
            
        Returns:
            Tuple of (HoneypotActivity, breach_detected)
        """
        try:
            # Find the honeypot
            honeypot = HoneypotEmail.objects.get(
                honeypot_address=honeypot_address,
                is_active=True
            )
        except HoneypotEmail.DoesNotExist:
            logger.warning(f"Email to unknown honeypot: {honeypot_address}")
            return None, False
        
        # Determine activity type
        activity_type = self._classify_activity(subject, sender_address, is_spam)
        
        # Create activity record
        activity = HoneypotActivity.objects.create(
            honeypot=honeypot,
            activity_type=activity_type,
            sender_address=sender_address,
            sender_domain=sender_address.split('@')[-1] if '@' in sender_address else '',
            subject_hash=HoneypotActivity.hash_subject(subject),
            subject_preview=self._redact_subject(subject)[:100],
            is_spam=is_spam,
            spam_score=spam_score,
            raw_headers=self._encrypt_headers(headers) if headers else '',
            received_at=timezone.now()
        )
        
        # Update honeypot metrics
        honeypot.record_activity(is_spam=is_spam)
        
        # Analyze for breach
        activity.analyze_for_breach()
        
        # Check if breach should be triggered
        breach_detected = self._check_for_breach(honeypot, activity)
        
        # Send notifications if configured
        if honeypot.user.honeypot_config.notify_on_any_activity:
            self._send_activity_notification(honeypot, activity)
        
        return activity, breach_detected
    
    def check_honeypot_for_activity(self, honeypot: HoneypotEmail) -> List[Dict]:
        """
        Manually check a honeypot for new activity via provider API.
        
        This is used for periodic checks and manual refresh.
        """
        config = self.get_or_create_config(honeypot.user)
        
        try:
            activities = self._provider_class.check_alias_activity(
                config,
                honeypot.provider_alias_id
            )
            
            # Process any new activities
            new_activities = []
            for activity_data in activities:
                # Check if we've already processed this
                # (implementation depends on provider data format)
                new_activities.append(activity_data)
            
            return new_activities
            
        except Exception as e:
            logger.error(f"Failed to check honeypot activity: {e}")
            return []
    
    def check_all_honeypots(self, user) -> Dict[str, Any]:
        """
        Check all active honeypots for a user.
        
        Returns summary of findings.
        """
        honeypots = self.get_user_honeypots(user, status='active')
        
        results = {
            'checked': 0,
            'new_activity': 0,
            'breaches_detected': 0,
            'honeypots': []
        }
        
        for honeypot in honeypots:
            activities = self.check_honeypot_for_activity(honeypot)
            
            results['checked'] += 1
            if activities:
                results['new_activity'] += len(activities)
            
            if honeypot.breach_detected:
                results['breaches_detected'] += 1
            
            results['honeypots'].append({
                'id': str(honeypot.id),
                'service': honeypot.service_name,
                'status': honeypot.status,
                'new_activities': len(activities)
            })
        
        return results
    
    # =========================================================================
    # Breach Detection
    # =========================================================================
    
    def _check_for_breach(
        self,
        honeypot: HoneypotEmail,
        activity: HoneypotActivity
    ) -> bool:
        """
        Analyze activity to determine if a breach should be triggered.
        
        Breach indicators:
        - Any spam email (honeypot should NEVER receive spam normally)
        - Marketing emails from unknown sources
        - Multiple emails in short period
        - Phishing attempts
        """
        breach_detected = False
        confidence = 0.0
        
        # High confidence: spam on honeypot = definite breach
        if activity.is_spam:
            breach_detected = True
            confidence = 0.95
            logger.warning(
                f"Breach detected via spam: {honeypot.service_name} "
                f"(user: {honeypot.user.username})"
            )
        
        # Medium confidence: any activity on fresh honeypot
        elif honeypot.total_emails_received == 1 and honeypot.days_active < 7:
            breach_detected = True
            confidence = 0.7
        
        # Medium-high confidence: multiple activities quickly
        elif honeypot.total_emails_received >= self.ACTIVITY_SPIKE_THRESHOLD:
            recent = HoneypotActivity.objects.filter(
                honeypot=honeypot,
                received_at__gte=timezone.now() - timedelta(hours=24)
            ).count()
            
            if recent >= self.ACTIVITY_SPIKE_THRESHOLD:
                breach_detected = True
                confidence = 0.85
        
        # Phishing = definite breach
        if activity.activity_type == 'phishing_detected':
            breach_detected = True
            confidence = max(confidence, 0.95)
        
        # Create breach event if detected
        if breach_detected:
            honeypot.confirm_breach(confidence)
            self._create_breach_event(honeypot, activity, confidence)
        
        return breach_detected
    
    @transaction.atomic
    def _create_breach_event(
        self,
        honeypot: HoneypotEmail,
        triggering_activity: HoneypotActivity,
        confidence: float
    ) -> HoneypotBreachEvent:
        """Create a breach event record and trigger notifications."""
        
        # Determine severity based on confidence and activity type
        if confidence >= 0.9:
            severity = 'high'
        elif confidence >= 0.7:
            severity = 'medium'
        else:
            severity = 'low'
        
        # Create breach event
        breach = HoneypotBreachEvent.objects.create(
            user=honeypot.user,
            honeypot=honeypot,
            service_name=honeypot.service_name,
            severity=severity,
            status='detected',
            detected_at=timezone.now(),
            first_activity_at=honeypot.first_activity_at,
            detection_method='honeypot_activity',
            confidence_score=confidence,
            triggering_activities=[str(triggering_activity.id)],
            exposed_data_types=['email'],  # At minimum, email was exposed
        )
        
        logger.warning(
            f"Breach event created: {breach.service_name} "
            f"(severity: {severity}, confidence: {confidence})"
        )
        
        # Send breach notification
        self._send_breach_notification(breach)
        
        # Handle auto-rotation if enabled
        config = self.get_or_create_config(honeypot.user)
        if config.auto_rotate_on_breach and not config.require_confirmation:
            self.initiate_credential_rotation(breach)
        
        return breach
    
    def get_user_breaches(
        self,
        user,
        status: str = None,
        include_resolved: bool = False
    ) -> List[HoneypotBreachEvent]:
        """Get breach events for a user."""
        queryset = HoneypotBreachEvent.objects.filter(user=user)
        
        if not include_resolved:
            queryset = queryset.exclude(status='resolved')
        
        if status:
            queryset = queryset.filter(status=status)
        
        return list(queryset.order_by('-detected_at'))
    
    def get_breach_timeline(self, breach_id: str, user) -> Dict[str, Any]:
        """Get detailed timeline for a breach event."""
        try:
            breach = HoneypotBreachEvent.objects.get(id=breach_id, user=user)
            return {
                'breach_id': str(breach.id),
                'service_name': breach.service_name,
                'severity': breach.severity,
                'status': breach.status,
                'timeline': breach.timeline,
                'days_before_public': breach.days_before_public,
                'credentials_rotated': breach.credentials_rotated,
            }
        except HoneypotBreachEvent.DoesNotExist:
            return None
    
    # =========================================================================
    # Credential Rotation
    # =========================================================================
    
    @transaction.atomic
    def initiate_credential_rotation(
        self,
        breach: HoneypotBreachEvent,
        trigger: str = 'auto_breach'
    ) -> CredentialRotationLog:
        """
        Initiate credential rotation for a breached service.
        
        This creates a rotation log and notifies the user.
        Actual rotation is performed manually or via integration.
        """
        honeypot = breach.honeypot
        
        rotation = CredentialRotationLog.objects.create(
            user=breach.user,
            honeypot=honeypot,
            breach_event=breach,
            vault_item_id=honeypot.vault_item_id if honeypot else None,
            service_name=breach.service_name,
            trigger=trigger,
            status='pending',
        )
        
        logger.info(
            f"Credential rotation initiated for {breach.service_name} "
            f"(trigger: {trigger})"
        )
        
        return rotation
    
    def confirm_credential_rotation(
        self,
        rotation: CredentialRotationLog,
        new_password_hash: str = None
    ) -> bool:
        """
        Confirm that credentials have been rotated.
        
        Called after user has actually changed their password.
        """
        rotation.status = 'completed'
        rotation.success = True
        rotation.completed_at = timezone.now()
        rotation.user_confirmed = True
        rotation.confirmed_at = timezone.now()
        
        if new_password_hash:
            rotation.new_credential_hash = new_password_hash
        
        rotation.save()
        
        # Update breach event
        if rotation.breach_event:
            rotation.breach_event.credentials_rotated = True
            rotation.breach_event.status = 'mitigated'
            rotation.breach_event.save()
        
        logger.info(f"Credential rotation confirmed for {rotation.service_name}")
        return True
    
    # =========================================================================
    # Notifications
    # =========================================================================
    
    def _send_activity_notification(
        self,
        honeypot: HoneypotEmail,
        activity: HoneypotActivity
    ):
        """Send notification about honeypot activity."""
        config = honeypot.user.honeypot_config
        
        if not config.notify_on_any_activity:
            return
        
        recipient = config.notification_email or honeypot.user.email
        
        subject = f"🔔 Activity on honeypot for {honeypot.service_name}"
        message = f"""
Hello {honeypot.user.get_full_name() or honeypot.user.username},

Activity has been detected on your honeypot email for {honeypot.service_name}.

Activity Type: {activity.get_activity_type_display()}
Sender: {activity.sender_domain}
Time: {activity.received_at.strftime('%Y-%m-%d %H:%M UTC')}

This may indicate that your data has been shared or leaked from {honeypot.service_name}.

Please review this activity in your SecureVault dashboard.

Best regards,
SecureVault Security Team
        """
        
        try:
            send_mail(
                subject=subject,
                message=message,
                from_email=getattr(settings, 'SECURITY_EMAIL', 'security@securevault.com'),
                recipient_list=[recipient],
                fail_silently=True
            )
        except Exception as e:
            logger.error(f"Failed to send activity notification: {e}")
    
    def _send_breach_notification(self, breach: HoneypotBreachEvent):
        """Send urgent notification about detected breach."""
        config = breach.user.honeypot_config
        
        if not config.notify_on_breach:
            return
        
        recipient = config.notification_email or breach.user.email
        
        subject = f"🚨 BREACH DETECTED: {breach.service_name}"
        message = f"""
⚠️ URGENT: Data Breach Detected

Hello {breach.user.get_full_name() or breach.user.username},

A potential data breach has been detected affecting your account at {breach.service_name}.

Severity: {breach.get_severity_display()}
Detected: {breach.detected_at.strftime('%Y-%m-%d %H:%M UTC')}
Confidence: {breach.confidence_score:.0%}

Your honeypot email for this service received suspicious activity, indicating your data may have been leaked.

RECOMMENDED ACTIONS:
1. Change your password for {breach.service_name} immediately
2. Enable 2FA if not already active
3. Review recent account activity
4. Check for any unauthorized access

You can manage this breach and rotate credentials in your SecureVault dashboard.

Best regards,
SecureVault Security Team
        """
        
        # Mark notification as sent
        breach.user_notified = True
        breach.notification_sent_at = timezone.now()
        breach.save()
        
        try:
            send_mail(
                subject=subject,
                message=message,
                from_email=getattr(settings, 'SECURITY_EMAIL', 'security@securevault.com'),
                recipient_list=[recipient],
                fail_silently=False
            )
            logger.info(f"Breach notification sent for {breach.service_name}")
        except Exception as e:
            logger.error(f"Failed to send breach notification: {e}")
    
    # =========================================================================
    # Helper Methods
    # =========================================================================
    
    def _classify_activity(
        self,
        subject: str,
        sender: str,
        is_spam: bool
    ) -> str:
        """Classify the type of email activity."""
        subject_lower = subject.lower()
        
        if is_spam:
            return 'spam_detected'
        
        # Check for phishing indicators
        phishing_keywords = ['verify', 'confirm', 'suspended', 'urgent', 'action required']
        if any(kw in subject_lower for kw in phishing_keywords):
            return 'phishing_detected'
        
        # Check for password reset
        if 'password' in subject_lower and ('reset' in subject_lower or 'change' in subject_lower):
            return 'password_reset'
        
        # Check for marketing
        marketing_keywords = ['newsletter', 'offer', 'deal', 'sale', 'discount', 'unsubscribe']
        if any(kw in subject_lower for kw in marketing_keywords):
            return 'marketing_email'
        
        return 'email_received'
    
    def _redact_subject(self, subject: str) -> str:
        """Redact potentially sensitive information from subject."""
        import re
        
        # Redact email addresses
        subject = re.sub(r'[\w\.-]+@[\w\.-]+', '[EMAIL]', subject)
        
        # Redact potential codes/tokens
        subject = re.sub(r'\b[A-Z0-9]{6,}\b', '[CODE]', subject)
        
        return subject
    
    def _encrypt_headers(self, headers: Dict) -> str:
        """Encrypt email headers for storage."""
        import json
        # TODO: Implement proper encryption
        # For now, just serialize
        return json.dumps(headers)


# Singleton instance
_honeypot_service = None


def get_honeypot_service() -> HoneypotEmailService:
    """Get or create the honeypot email service singleton."""
    global _honeypot_service
    if _honeypot_service is None:
        _honeypot_service = HoneypotEmailService()
    return _honeypot_service

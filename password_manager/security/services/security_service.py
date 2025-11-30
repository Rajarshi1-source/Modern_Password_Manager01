from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone
from django.contrib.auth.models import User
from django.db.models import Q, Count
from django.db import transaction
import requests
import json
import logging
from datetime import timedelta
from ipware import get_client_ip
import user_agents
from ..models import (
    LoginAttempt, SocialMediaAccount, UserDevice, 
    UserNotificationSettings, SecurityAlert, AccountLockEvent,
    Notification
)

logger = logging.getLogger(__name__)

class SecurityService:
    """Enhanced service for analyzing security threats and taking protective actions"""
    
    def __init__(self):
        self.max_failed_attempts = getattr(settings, 'MAX_FAILED_ATTEMPTS', 5)
        self.lockout_duration_minutes = getattr(settings, 'LOCKOUT_DURATION_MINUTES', 30)
        self.suspicious_threshold = getattr(settings, 'SUSPICIOUS_THRESHOLD', 3)
        self.geo_db_path = getattr(settings, 'GEOIP_PATH', None)
    
    @transaction.atomic
    def analyze_login_attempt(self, user, request, is_successful, failure_reason=None):
        """
        Analyzes a login attempt and calculates a risk score
        Returns a LoginAttempt object with risk assessment
        """
        try:
            ip_address, _ = get_client_ip(request)
            device_fingerprint = request.data.get('device_fingerprint', '')
            user_agent_string = request.META.get('HTTP_USER_AGENT', '')
            
            # Parse user agent for device info
            user_agent = user_agents.parse(user_agent_string)
            
            # Create login attempt record
            attempt = LoginAttempt(
                user=user,
                username_attempted=user.username if user else request.data.get('username', ''),
                ip_address=ip_address,
                device_fingerprint=device_fingerprint,
                user_agent=user_agent_string,
                status='success' if is_successful else 'failed',
                failure_reason=failure_reason or '',
                is_suspicious=False,  # Will be set after risk calculation
                threat_score=0  # Will be set after risk calculation
            )
            
            # Get geolocation from IP if available
            try:
                location_data = self._get_location_from_ip(ip_address)
                if location_data:
                    attempt.location = f"{location_data.get('city', '')}, {location_data.get('country', '')}"
            except Exception as e:
                logger.error(f"Error getting location data: {e}")
                attempt.location = "Unknown Location"
            
            # Calculate risk score and identify suspicious factors
            risk_data = self._calculate_risk_score(user, attempt, user_agent)
            attempt.threat_score = risk_data['risk_score']
            attempt.suspicious_factors = risk_data['suspicious_factors']
            attempt.is_suspicious = attempt.threat_score >= 70
            
            # Save the attempt
            attempt.save()
            
            # Handle new device registration for successful logins
            if is_successful and user:
                self._handle_device_registration(user, request, user_agent, ip_address)
            
            # Take action if suspicious
            if attempt.is_suspicious:
                if is_successful:
                    self.handle_suspicious_login(user, attempt)
                else:
                    self.handle_failed_login_attempt(user, attempt)
            
            return attempt
            
        except Exception as e:
            logger.error(f"Error analyzing login attempt: {str(e)}")
            raise
    
    def _get_location_from_ip(self, ip_address):
        """Get location information from IP address using GeoIP2 or external service"""
        if not ip_address or ip_address == '127.0.0.1':
            return {}
        
        # Try GeoIP2 first if available
        if self.geo_db_path:
            try:
                import geoip2.database
                with geoip2.database.Reader(f"{self.geo_db_path}/GeoLite2-City.mmdb") as reader:
                    response = reader.city(ip_address)
                    return {
                        'city': response.city.name,
                        'country': response.country.name,
                        'country_code': response.country.iso_code
                    }
            except Exception as e:
                logger.warning(f"GeoIP2 lookup failed: {e}")
        
        # Fallback to external service
        try:
            response = requests.get(f"https://ipinfo.io/{ip_address}/json", timeout=5)
            if response.status_code == 200:
                data = response.json()
                return {
                    'city': data.get('city', ''),
                    'country': data.get('country', ''),
                    'country_code': data.get('country', '')
                }
        except Exception as e:
            logger.error(f"Error in IP geolocation: {e}")
        
        return {}
    
    def _calculate_risk_score(self, user, login_attempt, user_agent):
        """
        Calculate a risk score for the login attempt based on various factors
        Returns dict with risk_score (0-100) and suspicious_factors
        """
        risk_score = 0
        suspicious_factors = {}
        
        try:
            # Check if this is a known device
            if login_attempt.device_fingerprint:
                known_device = UserDevice.objects.filter(
                    user=user, 
                    fingerprint=login_attempt.device_fingerprint
                ).exists()
                
                if not known_device:
                    risk_score += 30
                    suspicious_factors['new_device'] = True
            
            # Check for recent failed attempts from same IP
            if login_attempt.ip_address:
                recent_failed_attempts = LoginAttempt.objects.filter(
                    ip_address=login_attempt.ip_address,
                    status='failed',
                    timestamp__gte=timezone.now() - timedelta(hours=24)
                ).count()
                
                if recent_failed_attempts >= 3:
                    risk_score += min(40, recent_failed_attempts * 10)
                    suspicious_factors['recent_failures'] = recent_failed_attempts
            
            # Check if location is new for this user
            if user and login_attempt.location:
                known_location = LoginAttempt.objects.filter(
                    user=user,
                    status='success',
                    location=login_attempt.location
                ).exists()
                
                if not known_location:
                    risk_score += 30
                    suspicious_factors['new_location'] = login_attempt.location
            
            # Check for time anomalies (logins at unusual hours)
            hour = timezone.now().hour
            
            # Analyze user's typical login hours
            if user:
                typical_hours = LoginAttempt.objects.filter(
                    user=user,
                    status='success',
                    timestamp__gte=timezone.now() - timedelta(days=30)
                ).extra(select={'hour': 'EXTRACT(hour FROM timestamp)'}).values_list('hour', flat=True)
                
                typical_hours_set = set(typical_hours)
                if typical_hours_set and hour not in typical_hours_set:
                    risk_score += 20
                    suspicious_factors['unusual_time'] = f"{hour}:00"
            
            # Check for rapid location changes (impossible travel)
            if user and login_attempt.location:
                last_login = LoginAttempt.objects.filter(
                    user=user,
                    status='success'
                ).order_by('-timestamp').first()
                
                if last_login and last_login.location and last_login.location != login_attempt.location:
                    time_diff = timezone.now() - last_login.timestamp
                    if time_diff.total_seconds() < 3600:  # Less than an hour
                        risk_score += 50
                        suspicious_factors['impossible_travel'] = {
                            'previous': last_login.location,
                            'current': login_attempt.location,
                            'time_diff_minutes': time_diff.total_seconds() / 60
                        }
            
            # Check for unusual user agent patterns
            if user and user_agent:
                recent_agents = LoginAttempt.objects.filter(
                    user=user,
                    status='success',
                    timestamp__gte=timezone.now() - timedelta(days=7)
                ).values_list('user_agent', flat=True).distinct()
                
                similar_agent_found = any(
                    user_agent.browser.family in agent and user_agent.os.family in agent 
                    for agent in recent_agents
                )
                
                if not similar_agent_found:
                    risk_score += 15
                    suspicious_factors['unusual_user_agent'] = f"{user_agent.browser.family} on {user_agent.os.family}"
            
            # Check IP reputation (if available)
            if self._is_ip_blacklisted(login_attempt.ip_address):
                risk_score += 50
                suspicious_factors['blacklisted_ip'] = True
            
            # Check for velocity attacks (multiple attempts from different IPs)
            if user:
                recent_ips = LoginAttempt.objects.filter(
                    username_attempted=user.username,
                    timestamp__gte=timezone.now() - timedelta(hours=1)
                ).values('ip_address').distinct().count()
                
                if recent_ips > 5:
                    risk_score += 30
                    suspicious_factors['multiple_ips'] = recent_ips
            
            # Cap risk score at 100
            risk_score = min(risk_score, 100)
            
        except Exception as e:
            logger.error(f"Error calculating risk score: {e}")
            
        return {
            'risk_score': risk_score,
            'suspicious_factors': suspicious_factors
        }
    
    def _handle_device_registration(self, user, request, user_agent, ip_address):
        """Register or update device information for successful logins"""
        try:
            device_fingerprint = request.data.get('device_fingerprint', '')
            if not device_fingerprint:
                return
            
            device, created = UserDevice.objects.get_or_create(
                user=user,
                fingerprint=device_fingerprint,
                defaults={
                    'device_name': f"{user_agent.browser.family} on {user_agent.os.family}",
                    'device_type': 'mobile' if user_agent.is_mobile else 'desktop',
                    'browser': user_agent.browser.family,
                    'os': user_agent.os.family,
                    'ip_address': ip_address,
                    'is_trusted': False
                }
            )
            
            if not created:
                # Update last seen
                device.last_seen = timezone.now()
                device.ip_address = ip_address
                device.save()
            else:
                # Send new device alert
                self._send_new_device_alert(user, device)
                
        except Exception as e:
            logger.error(f"Error handling device registration: {e}")
    
    def _send_new_device_alert(self, user, device):
        """Send alert for new device login"""
        try:
            alert = SecurityAlert.objects.create(
                user=user,
                alert_type='new_device',
                severity='medium',
                title='New Device Login Detected',
                message=f'Login from new device: {device.device_name}',
                data={
                    'device_id': str(device.device_id),
                    'device_name': device.device_name,
                    'ip_address': device.ip_address
                }
            )
            
            NotificationService.send_security_alert(user, alert)
            
        except Exception as e:
            logger.error(f"Error sending new device alert: {e}")
    
    def handle_suspicious_login(self, user, login_attempt):
        """Handle a suspicious but successful login attempt"""
        try:
            # Create security alert
            alert = SecurityAlert.objects.create(
                user=user,
                alert_type='suspicious_activity',
                severity='high' if login_attempt.threat_score >= 80 else 'medium',
                title='Suspicious Login Activity Detected',
                message=f'Suspicious login detected from {login_attempt.ip_address}',
                data={
                    'ip_address': login_attempt.ip_address,
                    'location': login_attempt.location,
                    'threat_score': login_attempt.threat_score,
                    'suspicious_factors': login_attempt.suspicious_factors
                }
            )
            
            # Send notification
            NotificationService.send_suspicious_login_alert(user, login_attempt)
            
            # Lock social media accounts if risk is very high
            if login_attempt.threat_score >= 80:
                reason = f"Suspicious login detected with threat score {login_attempt.threat_score}"
                self.lock_social_accounts(user, reason, alert)
                
        except Exception as e:
            logger.error(f"Error handling suspicious login: {e}")
    
    def handle_failed_login_attempt(self, user, login_attempt):
        """Handle suspicious failed login attempts"""
        try:
            # Check for brute force patterns
            recent_failed = LoginAttempt.objects.filter(
                Q(user=user) | Q(username_attempted=login_attempt.username_attempted),
                status='failed',
                timestamp__gte=timezone.now() - timedelta(hours=1)
            ).count()
            
            if recent_failed >= self.max_failed_attempts:
                # Create security alert
                alert = SecurityAlert.objects.create(
                    user=user or User.objects.filter(username=login_attempt.username_attempted).first(),
                    alert_type='multiple_failures',
                    severity='high',
                    title='Multiple Failed Login Attempts',
                    message=f'Multiple failed login attempts detected from {login_attempt.ip_address}',
                    data={
                        'ip_address': login_attempt.ip_address,
                        'location': login_attempt.location,
                        'attempts_count': recent_failed
                    }
                )
                
                # Consider temporary account lockout or IP blocking
                # This would be implemented based on your security policy
                
        except Exception as e:
            logger.error(f"Error handling failed login attempt: {e}")
    
    @transaction.atomic
    def lock_social_accounts(self, user, reason, alert=None):
        """Lock all of a user's social media accounts with auto-lock enabled"""
        try:
            accounts = SocialMediaAccount.objects.filter(
                user=user,
                auto_lock_enabled=True,
                status='active'
            )
            
            locked_accounts = []
            for account in accounts:
                # Attempt to lock via API (placeholder for actual implementation)
                lock_success = self._attempt_platform_lock(account)
                
                # Record the lock event
                lock_event = AccountLockEvent.objects.create(
                    user=user,
                    social_account=account,
                    action='lock',
                    reason=reason,
                    triggered_by_alert=alert,
                    auto_triggered=True,
                    success=lock_success
                )
                
                if lock_success:
                    account.status = 'locked'
                    account.save()
                    locked_accounts.append(account)
                    
                    # Send individual account locked notification
                    NotificationService.send_account_locked_alert(user, account)
            
            return locked_accounts
            
        except Exception as e:
            logger.error(f"Error locking social accounts: {e}")
            return []
    
    def _attempt_platform_lock(self, account):
        """Attempt to lock account via platform API"""
        # This is a placeholder for actual platform API integration
        # Each platform would have its own implementation
        platform_handlers = {
            'facebook': self._lock_facebook_account,
            'twitter': self._lock_twitter_account,
            'google': self._lock_google_account,
            'instagram': self._lock_instagram_account,
            'linkedin': self._lock_linkedin_account
        }
        
        handler = platform_handlers.get(account.platform)
        if handler:
            return handler(account)
        
        # For now, just mark as locked in our system
        return True
    
    def _lock_facebook_account(self, account):
        """Lock Facebook account (placeholder)"""
        # Implement Facebook Graph API integration
        return True
    
    def _lock_twitter_account(self, account):
        """Lock Twitter account (placeholder)"""
        # Implement Twitter API integration
        return True
    
    def _lock_google_account(self, account):
        """Lock Google account (placeholder)"""
        # Implement Google Admin API integration
        return True
    
    def _lock_instagram_account(self, account):
        """Lock Instagram account (placeholder)"""
        # Implement Instagram API integration
        return True
    
    def _lock_linkedin_account(self, account):
        """Lock LinkedIn account (placeholder)"""
        # Implement LinkedIn API integration
        return True
    
    def unlock_social_account(self, account, verification_method):
        """Unlock a social media account after identity verification"""
        try:
            if not account.status == 'locked':
                return False
            
            # Attempt to unlock via platform API
            unlock_success = self._attempt_platform_unlock(account)
            
            # Record the unlock event
            AccountLockEvent.objects.create(
                user=account.user,
                social_account=account,
                action='unlock',
                reason=f'Unlocked after {verification_method} verification',
                auto_triggered=False,
                success=unlock_success
            )
            
            if unlock_success:
                account.status = 'active'
                account.save()
                
                # Log the unlock event
                logger.info(f"Account {account.id} unlocked after {verification_method} verification")
                
                # Notify user
                NotificationService.send_account_unlocked_alert(account.user, account)
                
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error unlocking social account: {e}")
            return False
    
    def _attempt_platform_unlock(self, account):
        """Attempt to unlock account via platform API"""
        # This would mirror the lock functionality but for unlocking
        return True
    
    def _is_ip_blacklisted(self, ip_address):
        """Check if IP is blacklisted"""
        # Implement IP reputation checking
        # Could integrate with threat intelligence feeds
        blacklisted_ips = getattr(settings, 'BLACKLISTED_IPS', set())
        return ip_address in blacklisted_ips


class NotificationService:
    """Enhanced service for sending security alerts across multiple channels"""
    
    @staticmethod
    def send_suspicious_login_alert(user, login_attempt):
        """Send alert about suspicious login activity"""
        try:
            settings_obj = SecurityService._get_user_notification_settings(user)
            
            # Only send if risk score exceeds user's minimum threshold
            # Convert decimal threshold (0.0-1.0) to integer scale (0-100)
            threshold = float(settings_obj.minimum_risk_score_for_alert) * 100
            if login_attempt.threat_score < threshold:
                return
            
            # Check cooldown period
            recent_notification = Notification.objects.filter(
                user=user,
                notification_type='login_alert',
                created_at__gte=timezone.now() - timedelta(minutes=settings_obj.alert_cooldown_minutes)
            ).exists()
            
            if recent_notification:
                return  # Skip due to cooldown
            
            # Prepare notification content
            location = login_attempt.location or "Unknown location"
            time = login_attempt.timestamp.strftime("%Y-%m-%d %H:%M:%S")
            
            subject = "Security Alert: Suspicious login detected"
            message = f"""
            Hello {user.get_full_name() or user.username},
            
            We detected a suspicious login to your account at {time}.
            
            Device: {login_attempt.device_fingerprint[:8] if login_attempt.device_fingerprint else 'Unknown'}...
            Location: {location}
            IP Address: {login_attempt.ip_address}
            Risk Score: {login_attempt.threat_score:.2f}
            
            Suspicious factors: {', '.join(login_attempt.suspicious_factors.keys()) if login_attempt.suspicious_factors else 'None'}
            
            If this was you, you can ignore this message. If not, please secure your account immediately.
            
            Best regards,
            SecureVault Security Team
            """
            
            # Send notifications based on user preferences
            NotificationService._send_notifications(user, settings_obj, subject, message, 'login_alert')
            
        except Exception as e:
            logger.error(f"Error sending suspicious login alert: {e}")
    
    @staticmethod
    def send_account_locked_alert(user, account):
        """Send alert about account being locked"""
        try:
            settings_obj = SecurityService._get_user_notification_settings(user)
            
            subject = f"Security Alert: Your {account.get_platform_display()} account has been locked"
            message = f"""
            Hello {user.get_full_name() or user.username},
            
            As a precautionary measure, we have temporarily locked your {account.get_platform_display()} account.
            
            Platform: {account.get_platform_display()}
            Username: {account.username}
            Locked at: {timezone.now().strftime("%Y-%m-%d %H:%M:%S")}
            
            To unlock your account, please verify your identity in the Account Protection section of your dashboard.
            
            Best regards,
            SecureVault Security Team
            """
            
            NotificationService._send_notifications(user, settings_obj, subject, message, 'security_alert')
            
        except Exception as e:
            logger.error(f"Error sending account locked alert: {e}")
    
    @staticmethod
    def send_account_unlocked_alert(user, account):
        """Send confirmation that account has been unlocked"""
        try:
            settings_obj = SecurityService._get_user_notification_settings(user)
            
            subject = f"Account Unlocked: Your {account.get_platform_display()} account"
            message = f"""
            Hello {user.get_full_name() or user.username},
            
            Your {account.get_platform_display()} account has been successfully unlocked after identity verification.
            
            Platform: {account.get_platform_display()}
            Username: {account.username}
            Unlocked at: {timezone.now().strftime("%Y-%m-%d %H:%M:%S")}
            
            If you did not request this action, please contact support immediately.
            
            Best regards,
            SecureVault Security Team
            """
            
            NotificationService._send_notifications(user, settings_obj, subject, message, 'security_alert')
            
        except Exception as e:
            logger.error(f"Error sending account unlocked alert: {e}")
    
    @staticmethod
    def send_security_alert(user, alert):
        """Send general security alert"""
        try:
            settings_obj = SecurityService._get_user_notification_settings(user)
            
            subject = f"Security Alert: {alert.title}"
            message = f"""
            Hello {user.get_full_name() or user.username},
            
            A security alert has been triggered for your account:
            
            Alert Type: {alert.get_alert_type_display()}
            Severity: {alert.get_severity_display()}
            Time: {alert.created_at.strftime('%Y-%m-%d %H:%M:%S')}
            
            Details: {alert.message}
            
            Please review your account security settings if this seems unusual.
            
            Best regards,
            SecureVault Security Team
            """
            
            NotificationService._send_notifications(user, settings_obj, subject, message, 'security_alert')
            
        except Exception as e:
            logger.error(f"Error sending security alert: {e}")
    
    @staticmethod
    def _send_notifications(user, settings_obj, subject, message, notification_type):
        """Send notifications via enabled channels"""
        try:
            # Send email alert
            if settings_obj.email_alerts:
                success = NotificationService._send_email(user.email, subject, message)
                NotificationService._log_notification(user, notification_type, 'email', message, success)
            
            # Send SMS alert if phone number available
            if settings_obj.sms_alerts and settings_obj.phone_number:
                sms_message = f"SecureVault Security Alert: {subject}"
                success = NotificationService._send_sms(settings_obj.phone_number, sms_message)
                NotificationService._log_notification(user, notification_type, 'sms', sms_message, success)
            
            # Send push notification
            if settings_obj.push_alerts:
                success = NotificationService._send_push(user.id, subject, message)
                NotificationService._log_notification(user, notification_type, 'push', message, success)
            
        except Exception as e:
            logger.error(f"Error sending notifications: {e}")
    
    @staticmethod
    def _log_notification(user, notification_type, channel, content, is_delivered):
        """Log notification attempt"""
        try:
            Notification.objects.create(
                user=user,
                notification_type=notification_type,
                channel=channel,
                content=content,
                is_delivered=is_delivered,
                delivered_at=timezone.now() if is_delivered else None
            )
        except Exception as e:
            logger.error(f"Error logging notification: {e}")
    
    @staticmethod
    def _send_email(recipient, subject, message):
        """Send an email notification"""
        try:
            send_mail(
                subject=subject,
                message=message,
                from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'security@yourapp.com'),
                recipient_list=[recipient],
                fail_silently=False
            )
            return True
        except Exception as e:
            logger.error(f"Error sending email: {e}")
            return False
    
    @staticmethod
    def _send_sms(phone_number, message):
        """Send an SMS notification"""
        try:
            # Implement SMS service integration (Twilio, AWS SNS, etc.)
            # Example with Twilio:
            """
            from twilio.rest import Client
            client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
            client.messages.create(
                body=message,
                from_=settings.TWILIO_PHONE_NUMBER,
                to=phone_number
            )
            """
            
            # Placeholder for SMS sending logic
            logger.info(f"SMS would be sent to {phone_number}: {message}")
            return True
        except Exception as e:
            logger.error(f"Error sending SMS: {e}")
            return False
    
    @staticmethod
    def _send_push(user_id, title, message):
        """Send a push notification"""
        try:
            # Implement push notification service integration
            # Example with Firebase Cloud Messaging:
            """
            from push_notifications.models import GCMDevice, APNSDevice
            
            devices = list(GCMDevice.objects.filter(user_id=user_id, active=True)) + \
                     list(APNSDevice.objects.filter(user_id=user_id, active=True))
            
            for device in devices:
                device.send_message(title=title, body=message)
            """
            
            # Placeholder for push notification logic
            logger.info(f"Push notification would be sent to user {user_id}: {title}")
            return True
        except Exception as e:
            logger.error(f"Error sending push notification: {e}")
            return False
    
    @staticmethod
    def _get_user_notification_settings(user):
        """Get or create user notification settings"""
        settings_obj, created = UserNotificationSettings.objects.get_or_create(
            user=user,
            defaults={
                'email_alerts': True,
                'sms_alerts': False,
                'push_alerts': True,
                'alert_on_new_device': True,
                'alert_on_new_location': True,
                'alert_on_suspicious_activity': True,
                'auto_lock_accounts': True,
                'suspicious_activity_threshold': 3,
                'minimum_risk_score_for_alert': 0.7,
                'alert_cooldown_minutes': 15
            }
        )
        return settings_obj


# Create service instances
security_service = SecurityService()
notification_service = NotificationService()

# Fix missing method reference
SecurityService._get_user_notification_settings = NotificationService._get_user_notification_settings 
from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone
from django.contrib.auth.models import User
from django.db.models import Q, Count
from ..models import (
    LoginAttempt, SecurityAlert, SocialMediaAccount, 
    UserDevice, UserNotificationSettings, AccountLockEvent
)
import requests
import json
import logging
from datetime import timedelta, datetime
from ipware import get_client_ip
import user_agents
import geoip2.database
import hashlib
import hmac

logger = logging.getLogger(__name__)

class AccountProtectionService:
    """Service for monitoring and protecting user accounts from unauthorized access"""
    
    def __init__(self):
        self.max_failed_attempts = 5
        self.lockout_duration_minutes = 30
        self.suspicious_threshold = 3
        self.geo_db_path = getattr(settings, 'GEOIP_PATH', None)
    
    def analyze_login_attempt(self, request, user=None, username=None, success=False, failure_reason=None):
        """
        Analyze a login attempt and determine if it's suspicious
        
        Args:
            request: HTTP request object
            user: User object if login was successful
            username: Username attempted if login failed
            success: Whether login was successful
            failure_reason: Reason for failure if applicable
            
        Returns:
            dict: Analysis results with threat score and recommendations
        """
        try:
            # Extract request information
            ip_address = self.get_client_ip(request)
            user_agent_string = request.META.get('HTTP_USER_AGENT', '')
            user_agent = user_agents.parse(user_agent_string)
            
            # Get location information
            location = self.get_location_from_ip(ip_address)
            
            # Detect device information
            device_info = self.detect_device(user_agent, ip_address)
            
            # Calculate threat score
            threat_score = self.calculate_threat_score(
                ip_address, user_agent, location, user, username
            )
            
            # Determine if attempt is suspicious
            is_suspicious = threat_score >= 50
            
            # Create login attempt record
            attempt = LoginAttempt.objects.create(
                user=user,
                username_attempted=username or (user.username if user else ''),
                ip_address=ip_address,
                user_agent=user_agent_string,
                location=location,
                status='success' if success else 'failed',
                failure_reason=failure_reason or '',
                is_suspicious=is_suspicious,
                threat_score=threat_score
            )
            
            # Handle suspicious activity
            if is_suspicious or not success:
                self.handle_suspicious_activity(attempt, request)
            
            # Handle successful login from new device
            if success and user:
                self.handle_new_device_login(user, device_info, request)
            
            return {
                'threat_score': threat_score,
                'is_suspicious': is_suspicious,
                'location': location,
                'device_info': device_info,
                'attempt_id': attempt.id
            }
            
        except Exception as e:
            logger.error(f"Error analyzing login attempt: {str(e)}")
            return {'error': str(e)}
    
    def calculate_threat_score(self, ip_address, user_agent, location, user=None, username=None):
        """Calculate threat score based on various factors"""
        score = 0
        
        try:
            # Check for recent failed attempts from same IP
            recent_failures = LoginAttempt.objects.filter(
                ip_address=ip_address,
                status='failed',
                timestamp__gte=timezone.now() - timedelta(hours=1)
            ).count()
            score += min(recent_failures * 15, 40)
            
            # Check for attempts from multiple IPs for same username
            if username:
                recent_ips = LoginAttempt.objects.filter(
                    username_attempted=username,
                    timestamp__gte=timezone.now() - timedelta(hours=24)
                ).values('ip_address').distinct().count()
                if recent_ips > 3:
                    score += 20
            
            # Check for unusual location
            if user and location:
                usual_locations = LoginAttempt.objects.filter(
                    user=user,
                    status='success',
                    timestamp__gte=timezone.now() - timedelta(days=30)
                ).values('location').distinct()
                
                if location not in [loc['location'] for loc in usual_locations]:
                    score += 25
            
            # Check for unusual user agent
            if user:
                recent_agents = LoginAttempt.objects.filter(
                    user=user,
                    status='success',
                    timestamp__gte=timezone.now() - timedelta(days=7)
                ).values('user_agent').distinct()
                
                if user_agent not in [agent['user_agent'] for agent in recent_agents]:
                    score += 15
            
            # Check for blacklisted IPs (you can maintain a blacklist)
            if self.is_ip_blacklisted(ip_address):
                score += 50
            
            return min(score, 100)
            
        except Exception as e:
            logger.error(f"Error calculating threat score: {str(e)}")
            return 0
    
    def handle_suspicious_activity(self, login_attempt, request):
        """Handle suspicious login activity"""
        try:
            user = login_attempt.user
            if not user:
                # Try to find user by username
                try:
                    user = User.objects.get(username=login_attempt.username_attempted)
                except User.DoesNotExist:
                    return
            
            # Check if we should trigger an alert
            settings_obj = self.get_user_notification_settings(user)
            
            # Count recent suspicious attempts
            recent_suspicious = LoginAttempt.objects.filter(
                Q(user=user) | Q(username_attempted=user.username),
                is_suspicious=True,
                timestamp__gte=timezone.now() - timedelta(hours=1)
            ).count()
            
            if recent_suspicious >= settings_obj.suspicious_activity_threshold:
                # Create security alert
                alert = SecurityAlert.objects.create(
                    user=user,
                    alert_type='suspicious_activity',
                    severity='high' if login_attempt.threat_score >= 75 else 'medium',
                    title='Suspicious Login Activity Detected',
                    message=f'Multiple suspicious login attempts detected from {login_attempt.ip_address}',
                    data={
                        'ip_address': login_attempt.ip_address,
                        'location': login_attempt.location,
                        'threat_score': login_attempt.threat_score,
                        'attempts_count': recent_suspicious
                    }
                )
                
                # Send notifications
                self.send_security_notification(user, alert)
                
                # Auto-lock social media accounts if enabled
                if settings_obj.auto_lock_accounts:
                    self.auto_lock_social_accounts(user, alert)
            
        except Exception as e:
            logger.error(f"Error handling suspicious activity: {str(e)}")
    
    def handle_new_device_login(self, user, device_info, request):
        """Handle login from a new device"""
        try:
            # Check if device is already known
            device_id = self.generate_device_id(device_info, request)
            
            device, created = UserDevice.objects.get_or_create(
                user=user,
                device_id=device_id,
                defaults={
                    'device_name': device_info.get('name', 'Unknown Device'),
                    'device_type': device_info.get('type', 'unknown'),
                    'browser': device_info.get('browser', ''),
                    'os': device_info.get('os', ''),
                    'ip_address': device_info.get('ip_address', ''),
                    'is_trusted': False
                }
            )
            
            if created:
                # New device detected - send alert
                alert = SecurityAlert.objects.create(
                    user=user,
                    alert_type='new_device',
                    severity='medium',
                    title='New Device Login Detected',
                    message=f'Login from new device: {device.device_name}',
                    data={
                        'device_id': str(device.device_id),
                        'device_name': device.device_name,
                        'ip_address': device.ip_address,
                        'location': device_info.get('location', 'Unknown')
                    }
                )
                
                self.send_security_notification(user, alert)
            
        except Exception as e:
            logger.error(f"Error handling new device login: {str(e)}")
    
    def auto_lock_social_accounts(self, user, alert):
        """Automatically lock user's social media accounts"""
        try:
            social_accounts = SocialMediaAccount.objects.filter(
                user=user,
                auto_lock_enabled=True,
                status='active'
            )
            
            for account in social_accounts:
                try:
                    # Attempt to lock the account via API
                    success = self.lock_social_account(account)
                    
                    # Record the lock event
                    AccountLockEvent.objects.create(
                        user=user,
                        social_account=account,
                        action='lock',
                        reason=f'Auto-locked due to suspicious activity: {alert.title}',
                        triggered_by_alert=alert,
                        auto_triggered=True,
                        success=success
                    )
                    
                    if success:
                        account.status = 'locked'
                        account.save()
                        
                        logger.info(f"Auto-locked {account.platform} account for user {user.username}")
                    
                except Exception as e:
                    logger.error(f"Failed to lock {account.platform} account: {str(e)}")
            
        except Exception as e:
            logger.error(f"Error auto-locking social accounts: {str(e)}")
    
    def lock_social_account(self, social_account):
        """Lock a specific social media account via API"""
        try:
            platform = social_account.platform
            
            if platform == 'facebook':
                return self.lock_facebook_account(social_account)
            elif platform == 'twitter':
                return self.lock_twitter_account(social_account)
            elif platform == 'google':
                return self.lock_google_account(social_account)
            # Add more platforms as needed
            
            return False
            
        except Exception as e:
            logger.error(f"Error locking {social_account.platform} account: {str(e)}")
            return False
    
    def lock_facebook_account(self, account):
        """Lock Facebook account using Graph API"""
        # Implementation depends on Facebook's API capabilities
        # This is a placeholder - actual implementation would require proper API integration
        return False
    
    def lock_twitter_account(self, account):
        """Lock Twitter account using Twitter API"""
        # Implementation depends on Twitter's API capabilities
        # This is a placeholder - actual implementation would require proper API integration
        return False
    
    def lock_google_account(self, account):
        """Lock Google account using Google Admin API"""
        # Implementation depends on Google's API capabilities
        # This is a placeholder - actual implementation would require proper API integration
        return False
    
    def send_security_notification(self, user, alert):
        """Send security notification to user"""
        try:
            settings_obj = self.get_user_notification_settings(user)
            
            # Check cooldown period
            last_alert = SecurityAlert.objects.filter(
                user=user,
                alert_type=alert.alert_type,
                created_at__gte=timezone.now() - timedelta(minutes=settings_obj.alert_cooldown_minutes)
            ).exclude(id=alert.id).first()
            
            if last_alert:
                return  # Skip notification due to cooldown
            
            # Send email notification
            if settings_obj.email_alerts:
                self.send_email_notification(user, alert)
            
            # Send SMS notification
            if settings_obj.sms_alerts and settings_obj.phone_number:
                self.send_sms_notification(user, alert, settings_obj.phone_number)
            
            # Send push notification
            if settings_obj.push_alerts:
                self.send_push_notification(user, alert)
            
        except Exception as e:
            logger.error(f"Error sending security notification: {str(e)}")
    
    def send_email_notification(self, user, alert):
        """Send email notification"""
        try:
            subject = f"Security Alert: {alert.title}"
            message = f"""
            Dear {user.get_full_name() or user.username},
            
            A security alert has been triggered for your account:
            
            Alert Type: {alert.get_alert_type_display()}
            Severity: {alert.get_severity_display()}
            Time: {alert.created_at.strftime('%Y-%m-%d %H:%M:%S')}
            
            Details: {alert.message}
            
            If this was not you, please log in to your account immediately to review your security settings.
            
            Best regards,
            SecureVault Security Team
            """
            
            send_mail(
                subject=subject,
                message=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user.email],
                fail_silently=False
            )
            
        except Exception as e:
            logger.error(f"Error sending email notification: {str(e)}")
    
    def send_sms_notification(self, user, alert, phone_number):
        """Send SMS notification (requires SMS service integration)"""
        # Placeholder for SMS integration (Twilio, AWS SNS, etc.)
        pass
    
    def send_push_notification(self, user, alert):
        """Send push notification"""
        try:
            # Use existing push notification system
            from push_notifications.models import GCMDevice, APNSDevice
            
            devices = list(GCMDevice.objects.filter(user=user)) + list(APNSDevice.objects.filter(user=user))
            
            for device in devices:
                device.send_message(
                    message=alert.message,
                    extra={
                        'alert_id': alert.id,
                        'alert_type': alert.alert_type,
                        'severity': alert.severity
                    }
                )
            
        except Exception as e:
            logger.error(f"Error sending push notification: {str(e)}")
    
    def get_user_notification_settings(self, user):
        """Get or create user notification settings"""
        settings_obj, created = UserNotificationSettings.objects.get_or_create(
            user=user,
            defaults={
                'email_alerts': True,
                'push_alerts': True,
                'auto_lock_accounts': True,
                'suspicious_activity_threshold': 3,
                'alert_cooldown_minutes': 15
            }
        )
        return settings_obj
    
    def get_client_ip(self, request):
        """Extract client IP address"""
        ip, is_routable = get_client_ip(request)
        return ip or '127.0.0.1'
    
    def get_location_from_ip(self, ip_address):
        """Get location from IP address using GeoIP"""
        try:
            if self.geo_db_path and ip_address != '127.0.0.1':
                with geoip2.database.Reader(self.geo_db_path) as reader:
                    response = reader.city(ip_address)
                    return f"{response.city.name}, {response.country.name}"
        except:
            pass
        return "Unknown Location"
    
    def detect_device(self, user_agent, ip_address):
        """Detect device information from user agent"""
        return {
            'name': f"{user_agent.browser.family} on {user_agent.os.family}",
            'type': 'mobile' if user_agent.is_mobile else 'desktop',
            'browser': user_agent.browser.family,
            'os': user_agent.os.family,
            'ip_address': ip_address
        }
    
    def generate_device_id(self, device_info, request):
        """Generate a unique device ID"""
        user_agent = request.META.get('HTTP_USER_AGENT', '')
        ip_address = device_info.get('ip_address', '')
        
        # Create a hash based on user agent and other factors
        device_string = f"{user_agent}_{ip_address}_{device_info.get('browser', '')}_{device_info.get('os', '')}"
        return hashlib.sha256(device_string.encode()).hexdigest()[:32]
    
    def is_ip_blacklisted(self, ip_address):
        """Check if IP is blacklisted"""
        # Implement your IP blacklist logic here
        # This could check against external threat intelligence feeds
        return False
    
    def unlock_social_accounts(self, user, platforms=None):
        """Manually unlock social media accounts"""
        try:
            query = SocialMediaAccount.objects.filter(user=user, status='locked')
            if platforms:
                query = query.filter(platform__in=platforms)
            
            for account in query:
                # Attempt to unlock via API
                success = self.unlock_social_account(account)
                
                AccountLockEvent.objects.create(
                    user=user,
                    social_account=account,
                    action='unlock',
                    reason='Manual unlock by user',
                    auto_triggered=False,
                    success=success
                )
                
                if success:
                    account.status = 'active'
                    account.save()
            
            return True
            
        except Exception as e:
            logger.error(f"Error unlocking social accounts: {str(e)}")
            return False
    
    def unlock_social_account(self, social_account):
        """Unlock a specific social media account"""
        # Implement platform-specific unlock logic
        return True  # Placeholder

# Create service instance
account_protection_service = AccountProtectionService()
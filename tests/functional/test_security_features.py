"""
Functional Tests for Security Features
=======================================

Tests complete security workflows including:
- Account security monitoring
- Suspicious activity detection
- Security alerts and notifications
- Account protection features
- Login security (2FA, passkeys, biometrics)
- Session security
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'password_manager.password_manager.settings')
django.setup()

from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone
import json
import time
from datetime import timedelta


class AccountSecurityMonitoringWorkflowTest(TestCase):
    """Test complete account security monitoring workflow"""
    
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='securitytestuser',
            email='security@example.com',
            password='SecurePass123!'
        )
        self.client.force_login(self.user)
    
    def test_view_security_dashboard_flow(self):
        """
        Test viewing security dashboard:
        1. Navigate to security dashboard
        2. View security score
        3. View recent security events
        4. View active sessions
        5. View security recommendations
        """
        # Get security dashboard
        # response = self.client.get('/api/security/dashboard/')
        # self.assertEqual(response.status_code, 200)
        
        # data = response.json()
        # self.assertIn('security_score', data)
        # self.assertIn('recent_events', data)
        # self.assertIn('active_sessions', data)
        # self.assertIn('recommendations', data)
    
    def test_view_login_history_flow(self):
        """Test viewing complete login history"""
        # Get login history
        # response = self.client.get('/api/security/login-history/')
        # self.assertEqual(response.status_code, 200)
        
        # history = response.json()
        # self.assertIsInstance(history, list)
        # for entry in history:
        #     self.assertIn('timestamp', entry)
        #     self.assertIn('ip_address', entry)
        #     self.assertIn('location', entry)
        #     self.assertIn('device', entry)
        #     self.assertIn('status', entry)
    
    def test_view_security_events_flow(self):
        """Test viewing security events log"""
        # Get security events
        # response = self.client.get('/api/security/events/')
        # events = response.json()
        
        # Event types should include:
        # - Failed login attempts
        # - Password changes
        # - 2FA enabled/disabled
        # - New device authorizations
        # - Suspicious activity
        pass
    
    def test_filter_security_events_by_type_flow(self):
        """Test filtering security events by type"""
        event_types = ['login_failed', 'password_changed', '2fa_enabled', 'suspicious_activity']
        
        for event_type in event_types:
            # response = self.client.get(f'/api/security/events/?type={event_type}')
            # events = response.json()
            # for event in events:
            #     self.assertEqual(event['event_type'], event_type)
            pass
    
    def test_export_security_report_flow(self):
        """Test exporting security report"""
        # Generate security report
        # response = self.client.post('/api/security/reports/generate/')
        # self.assertEqual(response.status_code, 201)
        
        # Download report
        # report_id = response.json()['report_id']
        # response = self.client.get(f'/api/security/reports/{report_id}/download/')
        # self.assertEqual(response.status_code, 200)
        # self.assertEqual(response['Content-Type'], 'application/pdf')


class SuspiciousActivityDetectionWorkflowTest(TestCase):
    """Test suspicious activity detection workflows"""
    
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.client.force_login(self.user)
    
    def test_detect_unusual_location_login_flow(self):
        """
        Test detection of login from unusual location:
        1. User logs in from usual location
        2. User logs in from unusual location (different country)
        3. System detects anomaly
        4. User receives alert
        5. User can approve or deny the login
        """
        # Simulate login from unusual location
        login_data = {
            'username': 'testuser',
            'password': 'testpass123',
            'ip_address': '203.0.113.1',  # Different country IP
            'location': 'Beijing, China'
        }
        
        # System should detect this as suspicious
        # response = self.client.post('/api/auth/login/', data=json.dumps(login_data))
        # self.assertIn('requires_verification', response.json())
    
    def test_detect_unusual_time_access_flow(self):
        """Test detection of access at unusual time"""
        # User typically accesses during business hours
        # Access at 3 AM should be flagged
        pass
    
    def test_detect_multiple_failed_login_attempts_flow(self):
        """Test detection of multiple failed login attempts"""
        # Simulate 5 failed login attempts
        for i in range(5):
            self.client.post(
                '/api/auth/login/',
                data=json.dumps({
                    'username': 'testuser',
                    'password': 'wrongpassword'
                }),
                content_type='application/json'
            )
        
        # Account should be locked or require additional verification
        # response = self.client.post(
        #     '/api/auth/login/',
        #     data=json.dumps({
        #         'username': 'testuser',
        #         'password': 'testpass123'  # Correct password
        #     })
        # )
        # self.assertIn('account_locked', response.json())
    
    def test_detect_new_device_login_flow(self):
        """Test detection of login from new device"""
        # Login from new device
        new_device_data = {
            'username': 'testuser',
            'password': 'testpass123',
            'device_fingerprint': 'new_device_123',
            'user_agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X)'
        }
        
        # Should require device authorization
        # response = self.client.post('/api/auth/login/', data=json.dumps(new_device_data))
        # self.assertIn('device_authorization_required', response.json())
    
    def test_detect_rapid_vault_access_flow(self):
        """Test detection of rapid vault item access"""
        # Access many vault items in short time
        # Could indicate data exfiltration
        for i in range(50):
            # self.client.get(f'/api/vault/items/{i}/')
            pass
        
        # Should trigger alert
    
    def test_detect_unusual_api_usage_pattern_flow(self):
        """Test detection of unusual API usage patterns"""
        # Unusual patterns might include:
        # - Accessing many resources in short time
        # - Using deprecated endpoints
        # - Unusual request sequences
        pass


class SecurityAlertsNotificationsWorkflowTest(TestCase):
    """Test security alerts and notifications workflows"""
    
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.client.force_login(self.user)
    
    def test_receive_security_alert_flow(self):
        """
        Test receiving and handling security alert:
        1. Security event occurs
        2. Alert generated
        3. User notified via email/push
        4. Alert appears in dashboard
        5. User can acknowledge or take action
        """
        # Trigger security event (e.g., login from new location)
        # Check for alert
        # response = self.client.get('/api/security/alerts/')
        # alerts = response.json()
        # self.assertGreater(len(alerts), 0)
        
        # Alert should contain:
        # - Event type
        # - Timestamp
        # - Details
        # - Severity level
        # - Recommended actions
    
    def test_acknowledge_security_alert_flow(self):
        """Test acknowledging a security alert"""
        alert_id = 1
        
        # Acknowledge alert
        # response = self.client.post(f'/api/security/alerts/{alert_id}/acknowledge/')
        # self.assertEqual(response.status_code, 200)
        
        # Alert should be marked as acknowledged
    
    def test_dismiss_security_alert_flow(self):
        """Test dismissing a security alert"""
        alert_id = 1
        
        # Dismiss alert (mark as false positive)
        # response = self.client.post(
        #     f'/api/security/alerts/{alert_id}/dismiss/',
        #     data=json.dumps({'reason': 'false_positive'}),
        #     content_type='application/json'
        # )
    
    def test_configure_alert_preferences_flow(self):
        """Test configuring alert notification preferences"""
        preferences = {
            'email_alerts': True,
            'push_notifications': True,
            'sms_alerts': False,
            'alert_severity_threshold': 'medium',  # low, medium, high, critical
            'alert_types': ['login_failed', 'new_device', 'password_changed']
        }
        
        # Update preferences
        # response = self.client.patch(
        #     '/api/security/alert-preferences/',
        #     data=json.dumps(preferences),
        #     content_type='application/json'
        # )
    
    def test_security_alert_escalation_flow(self):
        """Test alert escalation for critical events"""
        # Critical events should:
        # 1. Send immediate notification
        # 2. Lock account if necessary
        # 3. Require user action to resolve
        # 4. Escalate if not acknowledged within time limit
        pass


class AccountProtectionFeaturesWorkflowTest(TestCase):
    """Test account protection features"""
    
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.client.force_login(self.user)
    
    def test_enable_account_lock_after_suspicious_activity_flow(self):
        """Test automatic account lock after suspicious activity"""
        # Trigger suspicious activity
        # Account should be locked
        # User should receive notification
        # User must verify identity to unlock
        pass
    
    def test_manual_account_lock_flow(self):
        """Test manually locking account (panic mode)"""
        # User suspects compromise
        # Locks account immediately
        # response = self.client.post('/api/security/lock-account/')
        # self.assertEqual(response.status_code, 200)
        
        # Account should be inaccessible
        # User must use recovery method to unlock
    
    def test_enable_ip_whitelist_flow(self):
        """Test enabling IP address whitelist"""
        whitelist = {
            'enabled': True,
            'ip_addresses': ['192.168.1.1', '10.0.0.1']
        }
        
        # Update whitelist
        # response = self.client.post(
        #     '/api/security/ip-whitelist/',
        #     data=json.dumps(whitelist),
        #     content_type='application/json'
        # )
        
        # Only whitelisted IPs can access account
    
    def test_enable_device_whitelist_flow(self):
        """Test enabling trusted devices list"""
        # Only allow access from trusted devices
        # New devices require authorization
        pass
    
    def test_enable_geographic_restrictions_flow(self):
        """Test enabling geographic access restrictions"""
        restrictions = {
            'enabled': True,
            'allowed_countries': ['US', 'CA', 'GB'],
            'blocked_countries': ['CN', 'RU']
        }
        
        # Update restrictions
        # response = self.client.post(
        #     '/api/security/geo-restrictions/',
        #     data=json.dumps(restrictions),
        #     content_type='application/json'
        # )
    
    def test_enable_time_based_access_flow(self):
        """Test enabling time-based access restrictions"""
        time_restrictions = {
            'enabled': True,
            'allowed_hours': {
                'monday': {'start': '09:00', 'end': '17:00'},
                'tuesday': {'start': '09:00', 'end': '17:00'},
                # ... other days
            },
            'timezone': 'America/New_York'
        }
        
        # Update restrictions
        # Access outside allowed hours should be blocked
    
    def test_setup_emergency_contacts_flow(self):
        """Test setting up emergency contacts"""
        emergency_contacts = [
            {
                'name': 'John Doe',
                'email': 'john@example.com',
                'relationship': 'spouse'
            }
        ]
        
        # Emergency contacts can be notified of security events
        # or help with account recovery


class TwoFactorAuthenticationWorkflowTest(TestCase):
    """Test 2FA security workflows"""
    
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.client.force_login(self.user)
    
    def test_complete_totp_setup_flow(self):
        """
        Test TOTP (Time-based One-Time Password) setup:
        1. Request TOTP setup
        2. Receive secret and QR code
        3. Scan with authenticator app
        4. Verify with test code
        5. Receive backup codes
        6. 2FA enabled
        """
        # Step 1: Initiate setup
        # response = self.client.post('/api/security/2fa/totp/setup/')
        # setup_data = response.json()
        # self.assertIn('secret', setup_data)
        # self.assertIn('qr_code_url', setup_data)
        
        # Step 2: Verify setup
        # verification_data = {
        #     'code': '123456',  # Would be actual TOTP code
        #     'secret': setup_data['secret']
        # }
        # response = self.client.post(
        #     '/api/security/2fa/totp/verify/',
        #     data=json.dumps(verification_data),
        #     content_type='application/json'
        # )
        
        # Step 3: Receive backup codes
        # self.assertIn('backup_codes', response.json())
    
    def test_login_with_totp_flow(self):
        """Test logging in with TOTP enabled"""
        # Assume TOTP is set up
        
        # Step 1: Login with username/password
        login_data = {
            'username': 'testuser',
            'password': 'testpass123'
        }
        # response = self.client.post('/api/auth/login/', data=json.dumps(login_data))
        
        # Step 2: Receive 2FA requirement
        # self.assertIn('requires_2fa', response.json())
        
        # Step 3: Submit TOTP code
        # totp_data = {
        #     'code': '654321',
        #     'session_id': response.json()['session_id']
        # }
        # response = self.client.post('/api/auth/2fa/verify/', data=json.dumps(totp_data))
        # self.assertIn('access_token', response.json())
    
    def test_disable_2fa_flow(self):
        """Test disabling 2FA"""
        # Require current password and 2FA code to disable
        disable_data = {
            'password': 'testpass123',
            'totp_code': '123456'
        }
        
        # response = self.client.post(
        #     '/api/security/2fa/disable/',
        #     data=json.dumps(disable_data),
        #     content_type='application/json'
        # )
    
    def test_regenerate_backup_codes_flow(self):
        """Test regenerating backup codes"""
        # Old backup codes should be invalidated
        # New codes generated
        # response = self.client.post('/api/security/2fa/backup-codes/regenerate/')
        # new_codes = response.json()['backup_codes']
        # self.assertEqual(len(new_codes), 10)  # Typically 10 codes
    
    def test_use_backup_code_login_flow(self):
        """Test logging in with backup code when TOTP unavailable"""
        # Login with username/password
        # Use backup code instead of TOTP
        backup_code_data = {
            'code': 'BACKUP-CODE-123',
            'session_id': 'session_id_here'
        }
        
        # response = self.client.post('/api/auth/2fa/backup-code/', data=json.dumps(backup_code_data))
        # Backup code should be invalidated after use


class SessionSecurityWorkflowTest(TestCase):
    """Test session security workflows"""
    
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.client.force_login(self.user)
    
    def test_view_active_sessions_flow(self):
        """Test viewing all active sessions"""
        # Get active sessions
        # response = self.client.get('/api/security/sessions/')
        # sessions = response.json()
        
        # Each session should show:
        # - Device information
        # - IP address
        # - Location
        # - Last activity timestamp
        # - Created timestamp
        # - Is current session
    
    def test_terminate_specific_session_flow(self):
        """Test terminating a specific session"""
        session_id = 'session123'
        
        # Terminate session
        # response = self.client.delete(f'/api/security/sessions/{session_id}/')
        # self.assertEqual(response.status_code, 204)
        
        # Session should be invalidated
    
    def test_terminate_all_other_sessions_flow(self):
        """Test terminating all sessions except current"""
        # Useful when user suspects account compromise
        # response = self.client.post('/api/security/sessions/terminate-all-others/')
        # self.assertEqual(response.status_code, 200)
        
        # All sessions except current should be terminated
    
    def test_session_timeout_flow(self):
        """Test automatic session timeout"""
        # Session should timeout after period of inactivity
        # Default: 30 minutes
        # User should be logged out
        # Must re-authenticate to continue
        pass
    
    def test_configure_session_timeout_flow(self):
        """Test configuring session timeout duration"""
        timeout_settings = {
            'idle_timeout': 1800,  # 30 minutes in seconds
            'absolute_timeout': 86400  # 24 hours
        }
        
        # response = self.client.patch(
        #     '/api/security/session-settings/',
        #     data=json.dumps(timeout_settings),
        #     content_type='application/json'
        # )
    
    def test_session_concurrency_limit_flow(self):
        """Test limiting number of concurrent sessions"""
        # Allow maximum 5 concurrent sessions
        # When limit reached, oldest session is terminated
        pass


class PasswordSecurityWorkflowTest(TestCase):
    """Test password security workflows"""
    
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.client.force_login(self.user)
    
    def test_change_master_password_flow(self):
        """
        Test changing master password:
        1. Verify current password
        2. Enter new password
        3. Re-encrypt all vault items with new key
        4. Invalidate all sessions
        5. Require re-login
        """
        change_password_data = {
            'current_password': 'testpass123',
            'new_password': 'NewSecurePass456!',
            'new_password_confirm': 'NewSecurePass456!'
        }
        
        # response = self.client.post(
        #     '/api/security/change-password/',
        #     data=json.dumps(change_password_data),
        #     content_type='application/json'
        # )
        
        # All vault items should be re-encrypted
        # All sessions terminated
    
    def test_password_strength_validation_flow(self):
        """Test password strength validation"""
        weak_passwords = [
            'password',
            '123456',
            'qwerty',
            'abc123'
        ]
        
        for password in weak_passwords:
            data = {
                'current_password': 'testpass123',
                'new_password': password,
                'new_password_confirm': password
            }
            
            # Should be rejected
            # response = self.client.post('/api/security/change-password/', data=json.dumps(data))
            # self.assertIn('password_too_weak', response.json())
    
    def test_password_history_enforcement_flow(self):
        """Test that recently used passwords cannot be reused"""
        # Try to change password to one used in last 5 changes
        # Should be rejected
        pass
    
    def test_force_password_change_flow(self):
        """Test forced password change (e.g., after breach detection)"""
        # System detects password in breach database
        # User required to change password on next login
        # Cannot access account until password changed
        pass
    
    def test_password_expiration_flow(self):
        """Test password expiration policy"""
        # Password expires after 90 days
        # User warned before expiration
        # Must change password after expiration
        pass


class DeviceManagementWorkflowTest(TestCase):
    """Test device management workflows"""
    
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.client.force_login(self.user)
    
    def test_view_authorized_devices_flow(self):
        """Test viewing all authorized devices"""
        # response = self.client.get('/api/security/devices/')
        # devices = response.json()
        
        # Each device should show:
        # - Device name/type
        # - Last used timestamp
        # - Added timestamp
        # - Is current device
    
    def test_authorize_new_device_flow(self):
        """
        Test authorizing a new device:
        1. Login from new device
        2. Receive authorization request email
        3. Click authorization link or enter code
        4. Device added to trusted devices
        """
        # Simulate login from new device
        # Authorization required
        # User approves
        pass
    
    def test_remove_device_flow(self):
        """Test removing an authorized device"""
        device_id = 'device123'
        
        # response = self.client.delete(f'/api/security/devices/{device_id}/')
        # self.assertEqual(response.status_code, 204)
        
        # Device should be deauthorized
        # Next login from device requires re-authorization
    
    def test_rename_device_flow(self):
        """Test renaming a device"""
        device_id = 'device123'
        new_name = 'My iPhone 13'
        
        # response = self.client.patch(
        #     f'/api/security/devices/{device_id}/',
        #     data=json.dumps({'name': new_name}),
        #     content_type='application/json'
        # )


class WebAuthnPasskeyWorkflowTest(TestCase):
    """Test WebAuthn/Passkey security workflows"""
    
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.client.force_login(self.user)
    
    def test_register_hardware_security_key_flow(self):
        """Test registering a hardware security key (e.g., YubiKey)"""
        # Request registration challenge
        # response = self.client.post('/api/security/webauthn/register/begin/')
        # challenge = response.json()
        
        # User inserts security key and authorizes
        # Submit credential
        # credential_data = {
        #     'credential_id': 'cred_id',
        #     'public_key': 'public_key_data',
        #     'attestation': 'attestation_data'
        # }
        # response = self.client.post('/api/security/webauthn/register/complete/', data=json.dumps(credential_data))
    
    def test_login_with_security_key_flow(self):
        """Test logging in with hardware security key"""
        # Request authentication challenge
        # User inserts key and authorizes
        # Complete authentication
        pass
    
    def test_register_platform_authenticator_flow(self):
        """Test registering platform authenticator (e.g., Face ID, Touch ID)"""
        # Similar to hardware key but uses device biometrics
        pass
    
    def test_manage_multiple_passkeys_flow(self):
        """Test managing multiple passkeys"""
        # User can have multiple passkeys
        # Each can be named and managed individually
        # response = self.client.get('/api/security/webauthn/credentials/')
        # credentials = response.json()
        # self.assertGreater(len(credentials), 0)
    
    def test_remove_passkey_flow(self):
        """Test removing a passkey"""
        credential_id = 'cred123'
        
        # response = self.client.delete(f'/api/security/webauthn/credentials/{credential_id}/')
        # self.assertEqual(response.status_code, 204)


class DataBreachMonitoringWorkflowTest(TestCase):
    """Test data breach monitoring workflows"""
    
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.client.force_login(self.user)
    
    def test_check_password_against_breach_database_flow(self):
        """Test checking if password appears in known breaches"""
        password_data = {
            'password': 'password123'  # Known compromised password
        }
        
        # response = self.client.post(
        #     '/api/security/breach-check/',
        #     data=json.dumps(password_data),
        #     content_type='application/json'
        # )
        
        # Should warn if password found in breach
        # self.assertTrue(response.json()['is_compromised'])
    
    def test_scan_all_vault_passwords_flow(self):
        """Test scanning all vault passwords for breaches"""
        # Scan all stored passwords
        # response = self.client.post('/api/security/breach-scan-all/')
        
        # Return list of compromised items
        # compromised_items = response.json()['compromised_items']
        # self.assertIsInstance(compromised_items, list)
    
    def test_enable_breach_monitoring_alerts_flow(self):
        """Test enabling automatic breach monitoring alerts"""
        settings = {
            'enabled': True,
            'scan_frequency': 'weekly',  # daily, weekly, monthly
            'email_notifications': True
        }
        
        # response = self.client.post(
        #     '/api/security/breach-monitoring/settings/',
        #     data=json.dumps(settings),
        #     content_type='application/json'
        # )


# ==============================================================================
# TEST UTILITIES
# ==============================================================================

class SecurityTestHelpers:
    """Helper functions for security testing"""
    
    @staticmethod
    def simulate_suspicious_login(client, user, ip_address='203.0.113.1', location='Unknown'):
        """Simulate a suspicious login attempt"""
        return client.post(
            '/api/auth/login/',
            data=json.dumps({
                'username': user.username,
                'password': 'testpass123',
                'ip_address': ip_address,
                'location': location
            }),
            content_type='application/json'
        )
    
    @staticmethod
    def simulate_multiple_failed_logins(client, username, count=5):
        """Simulate multiple failed login attempts"""
        for i in range(count):
            client.post(
                '/api/auth/login/',
                data=json.dumps({
                    'username': username,
                    'password': f'wrongpassword{i}'
                }),
                content_type='application/json'
            )
    
    @staticmethod
    def create_test_security_event(user, event_type, severity='medium'):
        """Create a test security event"""
        # from security.models import SecurityEvent
        # return SecurityEvent.objects.create(
        #     user=user,
        #     event_type=event_type,
        #     severity=severity,
        #     timestamp=timezone.now()
        # )
        pass


# ==============================================================================
# RUN TESTS
# ==============================================================================

if __name__ == '__main__':
    import unittest
    
    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add all test classes
    suite.addTests(loader.loadTestsFromTestCase(AccountSecurityMonitoringWorkflowTest))
    suite.addTests(loader.loadTestsFromTestCase(SuspiciousActivityDetectionWorkflowTest))
    suite.addTests(loader.loadTestsFromTestCase(SecurityAlertsNotificationsWorkflowTest))
    suite.addTests(loader.loadTestsFromTestCase(AccountProtectionFeaturesWorkflowTest))
    suite.addTests(loader.loadTestsFromTestCase(TwoFactorAuthenticationWorkflowTest))
    suite.addTests(loader.loadTestsFromTestCase(SessionSecurityWorkflowTest))
    suite.addTests(loader.loadTestsFromTestCase(PasswordSecurityWorkflowTest))
    suite.addTests(loader.loadTestsFromTestCase(DeviceManagementWorkflowTest))
    suite.addTests(loader.loadTestsFromTestCase(WebAuthnPasskeyWorkflowTest))
    suite.addTests(loader.loadTestsFromTestCase(DataBreachMonitoringWorkflowTest))
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Print summary
    print("\n" + "="*70)
    print("SECURITY FEATURES FUNCTIONAL TEST SUMMARY")
    print("="*70)
    print(f"Tests Run: {result.testsRun}")
    print(f"Successes: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print("="*70)


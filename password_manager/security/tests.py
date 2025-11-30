from django.test import TestCase, RequestFactory
from django.contrib.auth.models import User
from django.utils import timezone
from unittest.mock import patch, Mock, MagicMock
from datetime import timedelta
import json

from .models import LoginAttempt, UserDevice, SocialMediaAccount, SecurityAlert
from .services.security_service import SecurityService, NotificationService
from auth_module.views import AuthViewSet


class SecurityServiceTestCase(TestCase):
    """Test cases for the SecurityService"""
    
    def setUp(self):
        """Set up test data"""
        self.factory = RequestFactory()
        self.security_service = SecurityService()
        
        # Create test user
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        # Create test social account
        self.social_account = SocialMediaAccount.objects.create(
            user=self.user,
            platform='facebook',
            username='testuser_fb',
            status='active',
            auto_lock_enabled=True
        )
    
    def create_mock_request(self, ip='192.168.1.100', user_agent='Mozilla/5.0'):
        """Helper to create mock request with specific parameters"""
        request = self.factory.post('/auth/login/', {
            'username': 'testuser',
            'password': 'testpass123',
            'device_fingerprint': 'test_fingerprint_123'
        })
        request.META['HTTP_USER_AGENT'] = user_agent
        request.META['REMOTE_ADDR'] = ip
        return request

    @patch('security.services.security_service.get_client_ip')
    def test_analyze_successful_login_normal_case(self, mock_get_ip):
        """Test analysis of a normal successful login"""
        # Mock IP detection
        mock_get_ip.return_value = ('192.168.1.100', True)
        
        request = self.create_mock_request()
        
        # Analyze login attempt
        attempt = self.security_service.analyze_login_attempt(
            user=self.user,
            request=request,
            is_successful=True
        )
        
        # Assertions
        self.assertIsInstance(attempt, LoginAttempt)
        self.assertEqual(attempt.user, self.user)
        self.assertEqual(attempt.status, 'success')
        self.assertEqual(attempt.ip_address, '192.168.1.100')
        self.assertLess(attempt.threat_score, 50)  # Should be low risk
        self.assertFalse(attempt.is_suspicious)

    @patch('security.services.security_service.get_client_ip')
    def test_analyze_suspicious_login_new_device(self, mock_get_ip):
        """Test analysis of login from new device"""
        mock_get_ip.return_value = ('10.0.0.1', True)
        
        request = self.create_mock_request(ip='10.0.0.1')
        
        # Analyze login attempt
        attempt = self.security_service.analyze_login_attempt(
            user=self.user,
            request=request,
            is_successful=True
        )
        
        # Should be suspicious due to new device
        self.assertGreater(attempt.threat_score, 0)
        self.assertIn('new_device', attempt.suspicious_factors)

    @patch('security.services.security_service.get_client_ip')
    def test_analyze_failed_login_brute_force(self, mock_get_ip):
        """Test analysis of failed login that looks like brute force"""
        mock_get_ip.return_value = ('10.0.0.1', True)
        
        # Create multiple recent failed attempts
        for i in range(5):
            LoginAttempt.objects.create(
                user=self.user,
                username_attempted='testuser',
                ip_address='10.0.0.1',
                status='failed',
                timestamp=timezone.now() - timedelta(minutes=i*10)
            )
        
        request = self.create_mock_request(ip='10.0.0.1')
        
        # Analyze new failed attempt
        attempt = self.security_service.analyze_login_attempt(
            user=self.user,
            request=request,
            is_successful=False,
            failure_reason='Invalid password'
        )
        
        # Should be highly suspicious
        self.assertGreater(attempt.threat_score, 30)
        self.assertIn('recent_failures', attempt.suspicious_factors)

    @patch('security.services.security_service.get_client_ip')
    @patch('security.services.security_service.NotificationService.send_suspicious_login_alert')
    def test_handle_suspicious_login_triggers_alert(self, mock_send_alert, mock_get_ip):
        """Test that suspicious logins trigger security alerts"""
        mock_get_ip.return_value = ('10.0.0.1', True)
        
        request = self.create_mock_request(ip='10.0.0.1')
        
        # Create a high-risk login attempt
        with patch.object(self.security_service, '_calculate_risk_score') as mock_calc:
            mock_calc.return_value = {
                'risk_score': 80,
                'suspicious_factors': {'new_device': True, 'new_location': 'Unknown, US'}
            }
            
            attempt = self.security_service.analyze_login_attempt(
                user=self.user,
                request=request,
                is_successful=True
            )
        
        # Check that alert was created
        self.assertTrue(SecurityAlert.objects.filter(user=self.user).exists())
        
        # Check that notification was sent
        mock_send_alert.assert_called_once()

    @patch('security.services.security_service.get_client_ip')
    def test_device_registration_on_successful_login(self, mock_get_ip):
        """Test that successful logins register/update device info"""
        mock_get_ip.return_value = ('192.168.1.100', True)
        
        request = self.create_mock_request()
        
        # Ensure no device exists initially
        self.assertFalse(UserDevice.objects.filter(user=self.user).exists())
        
        # Analyze successful login
        attempt = self.security_service.analyze_login_attempt(
            user=self.user,
            request=request,
            is_successful=True
        )
        
        # Check that device was registered
        self.assertTrue(UserDevice.objects.filter(
            user=self.user,
            fingerprint='test_fingerprint_123'
        ).exists())

    @patch('security.services.security_service.get_client_ip')
    def test_account_locking_on_high_risk(self, mock_get_ip):
        """Test that social accounts are locked on very high risk logins"""
        mock_get_ip.return_value = ('10.0.0.1', True)
        
        request = self.create_mock_request(ip='10.0.0.1')
        
        # Mock a very high risk score
        with patch.object(self.security_service, '_calculate_risk_score') as mock_calc:
            mock_calc.return_value = {
                'risk_score': 85,
                'suspicious_factors': {
                    'new_device': True,
                    'impossible_travel': True,
                    'blacklisted_ip': True
                }
            }
            
            attempt = self.security_service.analyze_login_attempt(
                user=self.user,
                request=request,
                is_successful=True
            )
        
        # Check that social account was locked
        self.social_account.refresh_from_db()
        self.assertEqual(self.social_account.status, 'locked')


class AuthViewIntegrationTestCase(TestCase):
    """Integration tests for security service in auth views"""
    
    def setUp(self):
        self.factory = RequestFactory()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        # Create auth view instance
        self.auth_viewset = AuthViewSet()

    @patch('auth_module.views.security_service.analyze_login_attempt')
    def test_login_view_calls_security_service(self, mock_analyze):
        """Test that login view properly calls security service"""
        # Mock the analysis result
        mock_attempt = Mock()
        mock_attempt.is_suspicious = False
        mock_attempt.threat_score = 25
        mock_analyze.return_value = mock_attempt
        
        request = self.factory.post('/auth/login/', {
            'username': 'testuser',
            'password': 'testpass123'
        })
        
        # Mock authentication
        with patch('auth_module.serializers.authenticate') as mock_auth:
            mock_auth.return_value = self.user
            
            response = self.auth_viewset.login(request)
        
        # Verify security service was called
        mock_analyze.assert_called_once()
        call_args = mock_analyze.call_args
        
        self.assertEqual(call_args[1]['user'], self.user)
        self.assertEqual(call_args[1]['is_successful'], True)
        self.assertIsNone(call_args[1]['failure_reason'])

    @patch('auth_module.views.security_service.analyze_login_attempt')
    def test_failed_login_analysis(self, mock_analyze):
        """Test security analysis on failed login"""
        mock_attempt = Mock()
        mock_attempt.is_suspicious = True
        mock_attempt.threat_score = 60
        mock_analyze.return_value = mock_attempt
        
        request = self.factory.post('/auth/login/', {
            'username': 'testuser',
            'password': 'wrongpassword'
        })
        
        # Mock failed authentication
        with patch('auth_module.serializers.authenticate') as mock_auth:
            mock_auth.return_value = None
            
            response = self.auth_viewset.login(request)
        
        # Verify security service was called for failed attempt
        mock_analyze.assert_called_once()
        call_args = mock_analyze.call_args
        
        self.assertEqual(call_args[1]['is_successful'], False)
        self.assertEqual(call_args[1]['failure_reason'], "Invalid credentials")


class SecurityServiceRiskCalculationTestCase(TestCase):
    """Detailed tests for risk calculation logic"""
    
    def setUp(self):
        self.security_service = SecurityService()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
    
    def test_risk_calculation_with_multiple_factors(self):
        """Test risk calculation with various suspicious factors"""
        # Create a login attempt object
        attempt = LoginAttempt(
            user=self.user,
            ip_address='10.0.0.1',
            device_fingerprint='unknown_device',
            location='New York, US'
        )
        
        # Create some historical data
        LoginAttempt.objects.create(
            user=self.user,
            ip_address='192.168.1.1',
            status='success',
            location='Los Angeles, US',
            timestamp=timezone.now() - timedelta(days=1)
        )
        
        # Mock user agent
        mock_user_agent = Mock()
        mock_user_agent.browser.family = 'Chrome'
        mock_user_agent.os.family = 'Windows'
        
        # Calculate risk
        risk_data = self.security_service._calculate_risk_score(
            self.user, attempt, mock_user_agent
        )
        
        # Should detect new device and location
        self.assertGreater(risk_data['risk_score'], 0)
        self.assertIn('new_device', risk_data['suspicious_factors'])
        self.assertIn('new_location', risk_data['suspicious_factors'])


class NotificationServiceTestCase(TestCase):
    """Tests for the notification service"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
    
    @patch('security.services.security_service.send_mail')
    def test_send_suspicious_login_alert(self, mock_send_mail):
        """Test sending suspicious login alert"""
        attempt = LoginAttempt.objects.create(
            user=self.user,
            ip_address='10.0.0.1',
            status='success',
            is_suspicious=True,
            threat_score=75,
            suspicious_factors={'new_device': True}
        )
        
        NotificationService.send_suspicious_login_alert(self.user, attempt)
        
        # Verify email was sent
        mock_send_mail.assert_called_once()
        args = mock_send_mail.call_args[1]
        self.assertIn('Suspicious Login', args['subject'])
        self.assertEqual(args['recipient_list'], [self.user.email])


class ManualTestingHelper:
    """Helper class for manual testing scenarios"""
    
    @staticmethod
    def create_test_scenarios():
        """Create various test scenarios for manual testing"""
        scenarios = {
            'normal_login': {
                'description': 'Normal login from known device',
                'ip': '192.168.1.100',
                'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'device_fingerprint': 'known_device_123',
                'expected_risk': 'low'
            },
            'new_device': {
                'description': 'Login from new device',
                'ip': '192.168.1.100',
                'user_agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 14_0)',
                'device_fingerprint': 'new_device_456',
                'expected_risk': 'medium'
            },
            'suspicious_location': {
                'description': 'Login from unusual location',
                'ip': '203.0.113.1',  # Different country IP
                'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
                'device_fingerprint': 'known_device_123',
                'expected_risk': 'medium'
            },
            'high_risk': {
                'description': 'High risk login with multiple factors',
                'ip': '198.51.100.1',  # Suspicious IP
                'user_agent': 'curl/7.68.0',  # Automated tool
                'device_fingerprint': 'suspicious_device_789',
                'expected_risk': 'high'
            }
        }
        return scenarios


# Test data fixtures
TEST_FIXTURES = {
    'user_agents': [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X)',
        'Mozilla/5.0 (Android 10; Mobile; rv:81.0) Gecko/81.0',
        'curl/7.68.0',  # Suspicious
        'python-requests/2.25.1'  # Suspicious
    ],
    'ip_addresses': [
        '192.168.1.100',  # Local
        '203.0.113.1',    # Example IP
        '198.51.100.1',   # Example IP
        '8.8.8.8',        # Google DNS
        '1.1.1.1'         # Cloudflare DNS
    ],
    'device_fingerprints': [
        'device_123_normal',
        'device_456_mobile',
        'device_789_suspicious',
        'device_000_bot'
    ]
}


# Example of how to run manual tests
"""
# Manual Testing Guide

## 1. Test Normal Login
from security.tests import ManualTestingHelper
from django.test import RequestFactory
from django.contrib.auth.models import User

# Setup
factory = RequestFactory()
user = User.objects.get(username='your_test_user')

# Create request for normal login
request = factory.post('/auth/login/', {
    'username': 'your_test_user',
    'password': 'correct_password',
    'device_fingerprint': 'known_device_123'
})
request.META['HTTP_USER_AGENT'] = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'
request.META['REMOTE_ADDR'] = '192.168.1.100'

# Test the integration
from security.services.security_service import security_service
attempt = security_service.analyze_login_attempt(
    user=user,
    request=request,
    is_successful=True
)

print(f"Threat Score: {attempt.threat_score}")
print(f"Is Suspicious: {attempt.is_suspicious}")
print(f"Suspicious Factors: {attempt.suspicious_factors}")

## 2. Test Suspicious Login
request.META['REMOTE_ADDR'] = '203.0.113.1'  # Different IP
request.data['device_fingerprint'] = 'new_device_456'

attempt = security_service.analyze_login_attempt(
    user=user,
    request=request,
    is_successful=True
)

# Should show higher risk score and suspicious factors

## 3. Test Failed Login Brute Force
for i in range(6):
    request = factory.post('/auth/login/', {
        'username': 'your_test_user',
        'password': 'wrong_password'
    })
    request.META['REMOTE_ADDR'] = '10.0.0.1'
    
    attempt = security_service.analyze_login_attempt(
        user=user,
        request=request,
        is_successful=False,
        failure_reason='Invalid password'
    )
    
    print(f"Attempt {i+1}: Risk {attempt.threat_score}")
"""

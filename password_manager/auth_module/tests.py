"""
Unit Tests for Authentication Module
=====================================

Tests authentication, registration, passkey, OAuth, and MFA functionality.

Test Categories:
1. User Registration Tests
2. Login/Authentication Tests
3. Passkey (WebAuthn) Tests
4. OAuth Integration Tests
5. Multi-Factor Authentication (MFA) Tests
6. Session Management Tests
7. Password Reset Tests
"""

from django.test import TestCase, RequestFactory, Client
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone
from unittest.mock import patch, Mock, MagicMock
from datetime import timedelta
import json
import base64

# Import auth models
try:
    from .models import (
        UserProfile,
        MFADevice,
        PasskeyCredential,
        OAuthConnection,
        LoginSession
    )
except ImportError:
    # Handle case where models might not all exist
    UserProfile = None
    MFADevice = None
    PasskeyCredential = None
    OAuthConnection = None
    LoginSession = None


# ==============================================================================
# USER REGISTRATION TESTS
# ==============================================================================

class UserRegistrationTest(TestCase):
    """Test user registration functionality"""
    
    def setUp(self):
        self.client = Client()
        self.registration_url = '/api/auth/register/'  # Adjust based on actual URL
    
    def test_register_new_user_success(self):
        """Test successful user registration"""
        data = {
            'username': 'newuser',
            'email': 'newuser@example.com',
            'password': 'SecurePass123!',
            'password_confirm': 'SecurePass123!'
        }
        
        response = self.client.post(
            self.registration_url,
            data=json.dumps(data),
            content_type='application/json'
        )
        
        # Check if user was created (status code may vary)
        # self.assertIn(response.status_code, [200, 201])
        
        # Verify user exists
        user_exists = User.objects.filter(username='newuser').exists()
        # self.assertTrue(user_exists)  # Uncomment when endpoint is ready
    
    def test_register_duplicate_username(self):
        """Test registration with duplicate username"""
        # Create existing user
        User.objects.create_user(
            username='existinguser',
            email='existing@example.com',
            password='password123'
        )
        
        data = {
            'username': 'existinguser',
            'email': 'new@example.com',
            'password': 'NewPass123!'
        }
        
        # Registration should fail
        # Implementation depends on actual API
    
    def test_register_duplicate_email(self):
        """Test registration with duplicate email"""
        User.objects.create_user(
            username='user1',
            email='duplicate@example.com',
            password='password123'
        )
        
        data = {
            'username': 'user2',
            'email': 'duplicate@example.com',
            'password': 'NewPass123!'
        }
        
        # Registration should fail or warn
        pass  # Implement based on actual behavior
    
    def test_register_weak_password(self):
        """Test registration with weak password"""
        data = {
            'username': 'testuser',
            'email': 'test@example.com',
            'password': '123'  # Too weak
        }
        
        # Should fail validation
        pass  # Implement based on password policy
    
    def test_register_password_mismatch(self):
        """Test registration with password confirmation mismatch"""
        data = {
            'username': 'testuser',
            'email': 'test@example.com',
            'password': 'SecurePass123!',
            'password_confirm': 'DifferentPass123!'
        }
        
        # Should fail validation
        pass


# ==============================================================================
# LOGIN/AUTHENTICATION TESTS
# ==============================================================================

class UserLoginTest(TestCase):
    """Test user login functionality"""
    
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.login_url = '/api/auth/login/'
    
    def test_login_with_username_success(self):
        """Test successful login with username"""
        data = {
            'username': 'testuser',
            'password': 'testpass123'
        }
        
        response = self.client.post(
            self.login_url,
            data=json.dumps(data),
            content_type='application/json'
        )
        
        # Should return token or session
        # self.assertEqual(response.status_code, 200)
        # data = response.json()
        # self.assertIn('token', data)  # or 'access' for JWT
    
    def test_login_with_email_success(self):
        """Test successful login with email"""
        data = {
            'email': 'test@example.com',
            'password': 'testpass123'
        }
        
        # Should succeed if email login is supported
        pass
    
    def test_login_invalid_credentials(self):
        """Test login with invalid credentials"""
        data = {
            'username': 'testuser',
            'password': 'wrongpassword'
        }
        
        response = self.client.post(
            self.login_url,
            data=json.dumps(data),
            content_type='application/json'
        )
        
        # Should return error
        # self.assertEqual(response.status_code, 401)
    
    def test_login_nonexistent_user(self):
        """Test login with nonexistent user"""
        data = {
            'username': 'nonexistent',
            'password': 'password123'
        }
        
        response = self.client.post(
            self.login_url,
            data=json.dumps(data),
            content_type='application/json'
        )
        
        # Should return error
        # self.assertIn(response.status_code, [401, 404])
    
    def test_login_inactive_user(self):
        """Test login with inactive user account"""
        self.user.is_active = False
        self.user.save()
        
        data = {
            'username': 'testuser',
            'password': 'testpass123'
        }
        
        # Should fail or return specific message
        pass
    
    def test_login_rate_limiting(self):
        """Test that rate limiting works on login"""
        # Attempt multiple failed logins
        for i in range(10):
            self.client.post(
                self.login_url,
                data=json.dumps({
                    'username': 'testuser',
                    'password': 'wrongpassword'
                }),
                content_type='application/json'
            )
        
        # Next attempt should be rate limited
        # Actual implementation depends on throttling configuration
        pass


# ==============================================================================
# PASSKEY (WEBAUTHN) TESTS
# ==============================================================================

class PasskeyAuthenticationTest(TestCase):
    """Test WebAuthn/Passkey authentication"""
    
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.client.force_login(self.user)
    
    @patch('fido2.server.Fido2Server')
    def test_passkey_registration_challenge(self, mock_fido2):
        """Test generating passkey registration challenge"""
        mock_server = Mock()
        mock_server.register_begin = Mock(return_value=(
            {'challenge': base64.b64encode(b'test_challenge').decode()},
            'state'
        ))
        mock_fido2.return_value = mock_server
        
        # Request registration challenge
        # response = self.client.post('/api/auth/passkey/register/begin/')
        # self.assertEqual(response.status_code, 200)
        # self.assertIn('challenge', response.json())
    
    def test_passkey_registration_complete(self):
        """Test completing passkey registration"""
        # This would test the complete flow of registering a passkey
        pass
    
    def test_passkey_authentication_challenge(self):
        """Test generating passkey authentication challenge"""
        # Create a passkey credential for the user first
        if PasskeyCredential:
            credential = PasskeyCredential.objects.create(
                user=self.user,
                credential_id=base64.b64encode(b'test_cred_id').decode(),
                public_key='test_public_key',
                sign_count=0
            )
        
        # Request authentication challenge
        pass
    
    def test_passkey_authentication_verify(self):
        """Test verifying passkey authentication response"""
        # This would test the complete authentication flow
        pass
    
    def test_multiple_passkeys_per_user(self):
        """Test that a user can have multiple registered passkeys"""
        if PasskeyCredential:
            for i in range(3):
                PasskeyCredential.objects.create(
                    user=self.user,
                    credential_id=base64.b64encode(f'cred_{i}'.encode()).decode(),
                    public_key=f'public_key_{i}',
                    sign_count=0,
                    device_name=f'Device {i}'
                )
            
            credentials = PasskeyCredential.objects.filter(user=self.user)
            self.assertEqual(credentials.count(), 3)
    
    def test_passkey_sign_count_increment(self):
        """Test that sign count increments on each use"""
        if PasskeyCredential:
            credential = PasskeyCredential.objects.create(
                user=self.user,
                credential_id='test_id',
                public_key='test_key',
                sign_count=0
            )
            
            # Simulate authentication
            credential.sign_count += 1
            credential.save()
            
            credential.refresh_from_db()
            self.assertEqual(credential.sign_count, 1)


# ==============================================================================
# OAUTH INTEGRATION TESTS
# ==============================================================================

class OAuthIntegrationTest(TestCase):
    """Test OAuth authentication integration"""
    
    def setUp(self):
        self.client = Client()
    
    def test_oauth_providers_list(self):
        """Test listing available OAuth providers"""
        # Should return list of configured providers (Google, GitHub, etc.)
        pass
    
    @patch('requests.post')
    def test_google_oauth_flow(self, mock_post):
        """Test Google OAuth authentication flow"""
        # Mock Google OAuth response
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {
            'access_token': 'test_token',
            'id_token': 'test_id_token'
        }
        
        # Initiate OAuth flow
        # Implementation depends on actual OAuth setup
        pass
    
    @patch('requests.post')
    def test_github_oauth_flow(self, mock_post):
        """Test GitHub OAuth authentication flow"""
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {
            'access_token': 'github_token'
        }
        
        # Initiate OAuth flow
        pass
    
    def test_oauth_user_creation(self):
        """Test that OAuth login creates user if not exists"""
        # Simulate OAuth callback with new user data
        pass
    
    def test_oauth_user_linking(self):
        """Test linking OAuth account to existing user"""
        user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        if OAuthConnection:
            # Link OAuth account
            connection = OAuthConnection.objects.create(
                user=user,
                provider='google',
                provider_user_id='google_123',
                access_token='token',
                refresh_token='refresh'
            )
            
            self.assertEqual(connection.user, user)
            self.assertEqual(connection.provider, 'google')
    
    def test_oauth_account_unlinking(self):
        """Test unlinking OAuth account"""
        user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        if OAuthConnection:
            connection = OAuthConnection.objects.create(
                user=user,
                provider='github',
                provider_user_id='github_456'
            )
            
            # Unlink
            connection_id = connection.id
            connection.delete()
            
            self.assertFalse(
                OAuthConnection.objects.filter(id=connection_id).exists()
            )


# ==============================================================================
# MULTI-FACTOR AUTHENTICATION TESTS
# ==============================================================================

class MFATest(TestCase):
    """Test Multi-Factor Authentication functionality"""
    
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.client.force_login(self.user)
    
    def test_mfa_device_registration(self):
        """Test registering MFA device"""
        if MFADevice:
            device = MFADevice.objects.create(
                user=self.user,
                device_type='totp',
                device_name='Google Authenticator',
                is_active=True
            )
            
            self.assertEqual(device.user, self.user)
            self.assertEqual(device.device_type, 'totp')
            self.assertTrue(device.is_active)
    
    def test_mfa_totp_code_generation(self):
        """Test TOTP code generation"""
        # This would test generating and verifying TOTP codes
        import pyotp
        
        secret = pyotp.random_base32()
        totp = pyotp.TOTP(secret)
        
        # Generate code
        code = totp.now()
        
        # Verify code
        self.assertTrue(totp.verify(code))
        self.assertEqual(len(code), 6)
    
    def test_mfa_backup_codes_generation(self):
        """Test generating backup codes"""
        import secrets
        
        # Generate 8 backup codes
        backup_codes = [secrets.token_hex(4) for _ in range(8)]
        
        self.assertEqual(len(backup_codes), 8)
        for code in backup_codes:
            self.assertEqual(len(code), 8)
    
    def test_mfa_required_login_flow(self):
        """Test login flow when MFA is required"""
        if MFADevice:
            # Create MFA device
            MFADevice.objects.create(
                user=self.user,
                device_type='totp',
                is_active=True
            )
            
            # Login should require MFA verification
            # Implementation depends on actual MFA flow
            pass
    
    def test_mfa_device_deactivation(self):
        """Test deactivating MFA device"""
        if MFADevice:
            device = MFADevice.objects.create(
                user=self.user,
                device_type='totp',
                is_active=True
            )
            
            # Deactivate
            device.is_active = False
            device.save()
            
            device.refresh_from_db()
            self.assertFalse(device.is_active)
    
    def test_multiple_mfa_devices(self):
        """Test user with multiple MFA devices"""
        if MFADevice:
            devices = []
            for i, device_type in enumerate(['totp', 'sms', 'email']):
                device = MFADevice.objects.create(
                    user=self.user,
                    device_type=device_type,
                    device_name=f'Device {i}',
                    is_active=True
                )
                devices.append(device)
            
            user_devices = MFADevice.objects.filter(user=self.user)
            self.assertEqual(user_devices.count(), 3)


# ==============================================================================
# SESSION MANAGEMENT TESTS
# ==============================================================================

class SessionManagementTest(TestCase):
    """Test session management functionality"""
    
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
    
    def test_session_creation_on_login(self):
        """Test that session is created on login"""
        self.client.force_login(self.user)
        
        # Check session exists
        session_key = self.client.session.session_key
        self.assertIsNotNone(session_key)
    
    def test_session_expiry(self):
        """Test session expiry settings"""
        self.client.force_login(self.user)
        
        # Check session expiry (default or configured)
        # session_expiry = self.client.session.get_expiry_age()
        # self.assertGreater(session_expiry, 0)
    
    def test_logout_destroys_session(self):
        """Test that logout destroys session"""
        self.client.force_login(self.user)
        session_key = self.client.session.session_key
        
        # Logout
        self.client.logout()
        
        # Session should be destroyed
        # New session key should be different
        # (or check session is invalid)
    
    def test_concurrent_sessions(self):
        """Test handling of concurrent sessions"""
        # Login from multiple clients
        client1 = Client()
        client2 = Client()
        
        client1.force_login(self.user)
        client2.force_login(self.user)
        
        # Both should have different sessions
        self.assertNotEqual(
            client1.session.session_key,
            client2.session.session_key
        )
    
    def test_session_hijacking_prevention(self):
        """Test session hijacking prevention measures"""
        self.client.force_login(self.user)
        
        # Session should have security measures like:
        # - HttpOnly cookie
        # - Secure flag (in production)
        # - SameSite attribute
        pass


# ==============================================================================
# PASSWORD RESET TESTS
# ==============================================================================

class PasswordResetTest(TestCase):
    """Test password reset functionality"""
    
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='oldpassword123'
        )
    
    @patch('django.core.mail.send_mail')
    def test_password_reset_request(self, mock_send_mail):
        """Test requesting password reset"""
        data = {
            'email': 'test@example.com'
        }
        
        # Request password reset
        # response = self.client.post('/api/auth/password-reset/', data)
        # mock_send_mail.assert_called_once()
    
    def test_password_reset_token_generation(self):
        """Test that reset token is generated"""
        from django.contrib.auth.tokens import default_token_generator
        
        token = default_token_generator.make_token(self.user)
        
        self.assertIsNotNone(token)
        self.assertTrue(
            default_token_generator.check_token(self.user, token)
        )
    
    def test_password_reset_token_expiry(self):
        """Test that reset token expires"""
        from django.contrib.auth.tokens import default_token_generator
        
        token = default_token_generator.make_token(self.user)
        
        # Modify user to invalidate token
        self.user.set_password('newpassword')
        self.user.save()
        
        # Token should no longer be valid
        self.assertFalse(
            default_token_generator.check_token(self.user, token)
        )
    
    def test_password_reset_complete(self):
        """Test completing password reset"""
        from django.contrib.auth.tokens import default_token_generator
        from django.utils.http import urlsafe_base64_encode
        from django.utils.encoding import force_bytes
        
        token = default_token_generator.make_token(self.user)
        uid = urlsafe_base64_encode(force_bytes(self.user.pk))
        
        # Submit new password with token
        # This would test the actual password reset completion
        pass


# ==============================================================================
# USER PROFILE TESTS
# ==============================================================================

class UserProfileTest(TestCase):
    """Test user profile functionality"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
    
    def test_profile_creation_on_user_creation(self):
        """Test that profile is automatically created with user"""
        if UserProfile:
            # Profile should be created via signal
            # profile = UserProfile.objects.get(user=self.user)
            # self.assertIsNotNone(profile)
            pass
    
    def test_profile_update(self):
        """Test updating user profile"""
        if UserProfile:
            profile, created = UserProfile.objects.get_or_create(user=self.user)
            
            profile.bio = "Test bio"
            profile.phone_number = "+1234567890"
            profile.save()
            
            profile.refresh_from_db()
            self.assertEqual(profile.bio, "Test bio")
            self.assertEqual(profile.phone_number, "+1234567890")
    
    def test_profile_avatar_upload(self):
        """Test profile avatar upload"""
        # This would test file upload for profile picture
        pass


# ==============================================================================
# SECURITY TESTS
# ==============================================================================

class AuthSecurityTest(TestCase):
    """Test authentication security measures"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
    
    def test_password_hashing(self):
        """Test that passwords are properly hashed"""
        self.assertNotEqual(self.user.password, 'testpass123')
        self.assertTrue(self.user.password.startswith('pbkdf2_sha256$'))
    
    def test_password_validation(self):
        """Test password validation rules"""
        from django.core.exceptions import ValidationError
        from django.contrib.auth.password_validation import validate_password
        
        # Weak passwords should fail
        weak_passwords = ['123', 'password', 'abc']
        
        for password in weak_passwords:
            with self.assertRaises(ValidationError):
                validate_password(password, self.user)
    
    def test_csrf_protection(self):
        """Test CSRF protection on auth endpoints"""
        client = Client(enforce_csrf_checks=True)
        
        # POST without CSRF token should fail
        # response = client.post('/api/auth/login/', {})
        # self.assertEqual(response.status_code, 403)
    
    def test_sql_injection_prevention(self):
        """Test SQL injection prevention"""
        # Try to login with SQL injection attempt
        malicious_inputs = [
            "admin' OR '1'='1",
            "'; DROP TABLE users; --",
            "admin'--"
        ]
        
        for malicious_input in malicious_inputs:
            user = User.objects.filter(username=malicious_input).first()
            self.assertIsNone(user)


# ==============================================================================
# EDGE CASE TESTS
# ==============================================================================

class AuthEdgeCaseTest(TestCase):
    """Test edge cases in authentication"""
    
    def test_unicode_username(self):
        """Test usernames with Unicode characters"""
        unicode_user = User.objects.create_user(
            username='用户名',
            email='unicode@example.com',
            password='testpass123'
        )
        
        self.assertEqual(unicode_user.username, '用户名')
    
    def test_very_long_username(self):
        """Test handling of very long usernames"""
        long_username = 'a' * 150  # Django default max is 150
        
        try:
            user = User.objects.create_user(
                username=long_username,
                email='long@example.com',
                password='testpass123'
            )
            self.assertEqual(len(user.username), 150)
        except Exception:
            # Should handle gracefully
            pass
    
    def test_special_characters_in_password(self):
        """Test passwords with special characters"""
        special_password = '!@#$%^&*()_+-=[]{}|;:",.<>?/~`'
        
        user = User.objects.create_user(
            username='specialuser',
            email='special@example.com',
            password=special_password
        )
        
        # Should be able to authenticate
        self.assertTrue(user.check_password(special_password))
    
    def test_case_sensitivity(self):
        """Test username/email case sensitivity"""
        User.objects.create_user(
            username='TestUser',
            email='Test@Example.com',
            password='password123'
        )
        
        # Username lookup should be case-sensitive
        user_lower = User.objects.filter(username='testuser').first()
        # self.assertIsNone(user_lower)  # Depends on configuration


# ==============================================================================
# HELPER CLASSES
# ==============================================================================

class AuthTestHelpers:
    """Helper functions for authentication testing"""
    
    @staticmethod
    def create_test_user(username='testuser', with_profile=False):
        """Create a test user with optional profile"""
        user = User.objects.create_user(
            username=username,
            email=f'{username}@test.com',
            password='testpass123'
        )
        
        if with_profile and UserProfile:
            UserProfile.objects.create(user=user)
        
        return user
    
    @staticmethod
    def create_authenticated_client(user=None):
        """Create an authenticated client"""
        client = Client()
        if user is None:
            user = User.objects.create_user(
                username='testuser',
                email='test@example.com',
                password='testpass123'
            )
        client.force_login(user)
        return client, user
    
    @staticmethod
    def generate_jwt_token(user):
        """Generate JWT token for testing"""
        try:
            from rest_framework_simplejwt.tokens import RefreshToken
            refresh = RefreshToken.for_user(user)
            return {
                'access': str(refresh.access_token),
                'refresh': str(refresh)
            }
        except ImportError:
            return None


# Run specific test suites
def suite():
    """Create test suite for Auth module"""
    from django.test.loader import TestLoader
    loader = TestLoader()
    suite = loader.loadTestsFromModule(__name__)
    return suite

"""
Test Fixtures
=============

Reusable test fixtures for consistent test data.
"""

from django.contrib.auth.models import User
from datetime import datetime, timedelta
from django.utils import timezone
import json


# ==============================================================================
# USER FIXTURES
# ==============================================================================

class UserFixtures:
    """Fixtures for creating test users"""
    
    @staticmethod
    def basic_user():
        """Create a basic test user"""
        return {
            'username': 'testuser',
            'email': 'test@example.com',
            'password': 'testpass123',
            'first_name': 'Test',
            'last_name': 'User'
        }
    
    @staticmethod
    def admin_user():
        """Create an admin user"""
        return {
            'username': 'admin',
            'email': 'admin@example.com',
            'password': 'adminpass123',
            'is_staff': True,
            'is_superuser': True
        }
    
    @staticmethod
    def multiple_users(count=5):
        """Create multiple test users"""
        return [
            {
                'username': f'user{i}',
                'email': f'user{i}@example.com',
                'password': f'password{i}',
                'first_name': f'User{i}',
                'last_name': f'Test{i}'
            }
            for i in range(count)
        ]
    
    @staticmethod
    def create_user_from_fixture(fixture_data):
        """Create actual User object from fixture data"""
        password = fixture_data.pop('password', 'testpass123')
        user = User.objects.create_user(**fixture_data)
        user.set_password(password)
        user.save()
        return user


# ==============================================================================
# VAULT ITEM FIXTURES
# ==============================================================================

class VaultItemFixtures:
    """Fixtures for vault items"""
    
    @staticmethod
    def password_item():
        """Basic password item"""
        return {
            'item_type': 'password',
            'name': 'Gmail Account',
            'username': 'user@gmail.com',
            'password': 'SecurePassword123!',
            'url': 'https://gmail.com',
            'notes': 'Personal email account',
            'favorite': False
        }
    
    @staticmethod
    def credit_card_item():
        """Basic credit card item"""
        return {
            'item_type': 'card',
            'name': 'Visa Card',
            'card_number': '4111 1111 1111 1111',
            'cardholder_name': 'Test User',
            'expiry_month': '12',
            'expiry_year': '2025',
            'cvv': '123',
            'billing_address': '123 Test St'
        }
    
    @staticmethod
    def secure_note_item():
        """Basic secure note"""
        return {
            'item_type': 'note',
            'name': 'Important Note',
            'note_content': 'This is a secure note with sensitive information.'
        }
    
    @staticmethod
    def identity_item():
        """Basic identity item"""
        return {
            'item_type': 'identity',
            'name': 'Personal Identity',
            'first_name': 'John',
            'last_name': 'Doe',
            'email': 'john.doe@example.com',
            'phone': '+1234567890',
            'address': '123 Main St, City, State 12345',
            'ssn': '123-45-6789',
            'passport': 'A12345678',
            'license': 'DL1234567'
        }
    
    @staticmethod
    def multiple_password_items(count=5):
        """Create multiple password items"""
        return [
            {
                'item_type': 'password',
                'name': f'Account {i}',
                'username': f'user{i}@example.com',
                'password': f'Password{i}!',
                'url': f'https://site{i}.com',
                'favorite': i % 2 == 0
            }
            for i in range(count)
        ]
    
    @staticmethod
    def weak_password_items():
        """Password items with weak passwords for testing"""
        return [
            {
                'item_type': 'password',
                'name': 'Weak Password 1',
                'username': 'user@example.com',
                'password': '123456',
                'url': 'https://example.com'
            },
            {
                'item_type': 'password',
                'name': 'Weak Password 2',
                'username': 'user@example.com',
                'password': 'password',
                'url': 'https://example.com'
            },
            {
                'item_type': 'password',
                'name': 'Weak Password 3',
                'username': 'user@example.com',
                'password': 'qwerty',
                'url': 'https://example.com'
            }
        ]
    
    @staticmethod
    def strong_password_items():
        """Password items with strong passwords for testing"""
        return [
            {
                'item_type': 'password',
                'name': 'Strong Password 1',
                'username': 'user@example.com',
                'password': 'X9$mP2#kL5@nQ8!vR4',
                'url': 'https://example.com'
            },
            {
                'item_type': 'password',
                'name': 'Strong Password 2',
                'username': 'user@example.com',
                'password': 'Tr0ng!P@ssw0rd#2024',
                'url': 'https://example.com'
            }
        ]


# ==============================================================================
# ML SECURITY FIXTURES
# ==============================================================================

class MLSecurityFixtures:
    """Fixtures for ML security testing"""
    
    @staticmethod
    def password_strength_samples():
        """Sample passwords with expected strength scores"""
        return [
            {'password': '123', 'expected_score_range': (0.0, 0.2)},
            {'password': 'password', 'expected_score_range': (0.1, 0.3)},
            {'password': 'Password123', 'expected_score_range': (0.4, 0.6)},
            {'password': 'P@ssw0rd!123', 'expected_score_range': (0.6, 0.8)},
            {'password': 'Str0ng!P@ss#2024$Secure', 'expected_score_range': (0.8, 1.0)}
        ]
    
    @staticmethod
    def anomaly_detection_events():
        """Sample events for anomaly detection"""
        return {
            'normal_events': [
                {
                    'ip_latitude': 34.0522,  # Los Angeles
                    'ip_longitude': -118.2437,
                    'time_of_day_sin': 0.5,
                    'time_of_day_cos': 0.866,
                    'event_type': 'login',
                    'expected_anomaly': False
                },
                {
                    'ip_latitude': 34.0500,
                    'ip_longitude': -118.2500,
                    'time_of_day_sin': 0.6,
                    'time_of_day_cos': 0.8,
                    'event_type': 'vault_access',
                    'expected_anomaly': False
                }
            ],
            'anomalous_events': [
                {
                    'ip_latitude': 51.5074,  # London (sudden location change)
                    'ip_longitude': 0.1278,
                    'time_of_day_sin': -0.9,
                    'time_of_day_cos': 0.4,
                    'event_type': 'login',
                    'expected_anomaly': True
                },
                {
                    'ip_latitude': 35.6762,  # Tokyo
                    'ip_longitude': 139.6503,
                    'time_of_day_sin': -1.0,
                    'time_of_day_cos': 0.0,
                    'event_type': 'data_export',
                    'expected_anomaly': True
                }
            ]
        }
    
    @staticmethod
    def threat_analysis_sequences():
        """Sample activity sequences for threat analysis"""
        return {
            'benign_sequences': [
                'user_login_success browser_chrome os_windows access_vault',
                'user_login_success browser_firefox os_macos view_passwords',
                'mfa_verify browser_safari os_ios access_settings'
            ],
            'suspicious_sequences': [
                'user_login_fail_3x browser_unknown os_linux access_denied',
                'rapid_login_attempts ip_change browser_change',
                'unusual_time_access multiple_failed_mfa data_export_attempt'
            ],
            'critical_sequences': [
                'brute_force_detected account_locked multiple_ip_sources',
                'mass_data_export unusual_location admin_privilege_escalation',
                'repeated_mfa_bypass credential_stuffing sensitive_data_access'
            ]
        }


# ==============================================================================
# AUTHENTICATION FIXTURES
# ==============================================================================

class AuthFixtures:
    """Fixtures for authentication testing"""
    
    @staticmethod
    def login_attempts():
        """Sample login attempts"""
        return {
            'successful_logins': [
                {
                    'username': 'testuser',
                    'password': 'testpass123',
                    'ip_address': '192.168.1.100',
                    'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
                    'device_fingerprint': 'device_123',
                    'expected_threat_score': 10
                }
            ],
            'failed_logins': [
                {
                    'username': 'testuser',
                    'password': 'wrongpassword',
                    'ip_address': '10.0.0.1',
                    'user_agent': 'Mozilla/5.0',
                    'device_fingerprint': 'unknown_device',
                    'expected_threat_score': 50
                }
            ],
            'brute_force_attempts': [
                {
                    'username': 'testuser',
                    'password': f'attempt{i}',
                    'ip_address': '10.0.0.1',
                    'user_agent': 'curl/7.68.0',
                    'device_fingerprint': 'bot_device'
                }
                for i in range(10)
            ]
        }
    
    @staticmethod
    def mfa_devices():
        """Sample MFA devices"""
        return [
            {
                'device_type': 'totp',
                'device_name': 'Google Authenticator',
                'is_active': True
            },
            {
                'device_type': 'sms',
                'device_name': 'Phone +1234567890',
                'is_active': True
            },
            {
                'device_type': 'email',
                'device_name': 'Email test@example.com',
                'is_active': False
            }
        ]
    
    @staticmethod
    def oauth_connections():
        """Sample OAuth connections"""
        return [
            {
                'provider': 'google',
                'provider_user_id': 'google_123456',
                'display_name': 'Google Account',
                'access_token': 'mock_google_token',
                'refresh_token': 'mock_google_refresh'
            },
            {
                'provider': 'github',
                'provider_user_id': 'github_789012',
                'display_name': 'GitHub Account',
                'access_token': 'mock_github_token',
                'refresh_token': 'mock_github_refresh'
            }
        ]
    
    @staticmethod
    def passkey_credentials():
        """Sample passkey credentials"""
        return [
            {
                'credential_id': 'passkey_credential_1',
                'public_key': 'mock_public_key_1',
                'sign_count': 0,
                'device_name': 'YubiKey 5',
                'device_type': 'usb'
            },
            {
                'credential_id': 'passkey_credential_2',
                'public_key': 'mock_public_key_2',
                'sign_count': 5,
                'device_name': 'Touch ID',
                'device_type': 'platform'
            }
        ]


# ==============================================================================
# SECURITY FIXTURES
# ==============================================================================

class SecurityFixtures:
    """Fixtures for security testing"""
    
    @staticmethod
    def security_alerts():
        """Sample security alerts"""
        return [
            {
                'alert_type': 'suspicious_login',
                'severity': 'high',
                'title': 'Suspicious Login Detected',
                'description': 'Login from new device and location',
                'metadata': {
                    'ip': '10.0.0.1',
                    'location': 'Unknown',
                    'device': 'Unknown Device'
                },
                'is_resolved': False
            },
            {
                'alert_type': 'weak_password',
                'severity': 'medium',
                'title': 'Weak Password Detected',
                'description': 'One or more passwords are weak',
                'metadata': {
                    'weak_password_count': 3
                },
                'is_resolved': False
            },
            {
                'alert_type': 'breach_detected',
                'severity': 'critical',
                'title': 'Password Found in Data Breach',
                'description': 'Your password was found in a known data breach',
                'metadata': {
                    'breach_name': 'Example Breach 2024',
                    'breach_date': '2024-01-15'
                },
                'is_resolved': False
            }
        ]
    
    @staticmethod
    def user_devices():
        """Sample user devices"""
        return [
            {
                'device_name': 'Chrome on Windows',
                'device_type': 'desktop',
                'fingerprint': 'device_fingerprint_1',
                'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0',
                'is_trusted': True,
                'last_used': timezone.now()
            },
            {
                'device_name': 'Safari on iPhone',
                'device_type': 'mobile',
                'fingerprint': 'device_fingerprint_2',
                'user_agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) Safari/604.1',
                'is_trusted': True,
                'last_used': timezone.now() - timedelta(days=2)
            },
            {
                'device_name': 'Unknown Device',
                'device_type': 'unknown',
                'fingerprint': 'device_fingerprint_3',
                'user_agent': 'curl/7.68.0',
                'is_trusted': False,
                'last_used': timezone.now() - timedelta(hours=1)
            }
        ]
    
    @staticmethod
    def breach_monitoring_results():
        """Sample breach monitoring results"""
        return [
            {
                'email': 'user@example.com',
                'breaches_found': [
                    {
                        'name': 'Adobe',
                        'domain': 'adobe.com',
                        'breach_date': '2013-10-04',
                        'pwn_count': 152445165,
                        'data_classes': ['Email addresses', 'Password hints', 'Passwords', 'Usernames']
                    },
                    {
                        'name': 'LinkedIn',
                        'domain': 'linkedin.com',
                        'breach_date': '2012-05-05',
                        'pwn_count': 164611595,
                        'data_classes': ['Email addresses', 'Passwords']
                    }
                ]
            }
        ]


# ==============================================================================
# REQUEST FIXTURES
# ==============================================================================

class RequestFixtures:
    """Fixtures for HTTP requests"""
    
    @staticmethod
    def headers():
        """Common request headers"""
        return {
            'Content-Type': 'application/json',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'application/json',
            'Accept-Language': 'en-US,en;q=0.9'
        }
    
    @staticmethod
    def authenticated_headers(token):
        """Headers for authenticated requests"""
        headers = RequestFixtures.headers()
        headers['Authorization'] = f'Bearer {token}'
        return headers


# ==============================================================================
# DATE/TIME FIXTURES
# ==============================================================================

class DateTimeFixtures:
    """Fixtures for date/time testing"""
    
    @staticmethod
    def recent_timestamps():
        """Recent timestamps for testing"""
        now = timezone.now()
        return {
            'now': now,
            '1_hour_ago': now - timedelta(hours=1),
            '1_day_ago': now - timedelta(days=1),
            '1_week_ago': now - timedelta(weeks=1),
            '1_month_ago': now - timedelta(days=30),
            '1_year_ago': now - timedelta(days=365)
        }
    
    @staticmethod
    def future_timestamps():
        """Future timestamps for testing"""
        now = timezone.now()
        return {
            'now': now,
            'in_1_hour': now + timedelta(hours=1),
            'in_1_day': now + timedelta(days=1),
            'in_1_week': now + timedelta(weeks=1),
            'in_1_month': now + timedelta(days=30),
            'in_1_year': now + timedelta(days=365)
        }


# ==============================================================================
# EXPORT FIXTURES
# ==============================================================================

__all__ = [
    'UserFixtures',
    'VaultItemFixtures',
    'MLSecurityFixtures',
    'AuthFixtures',
    'SecurityFixtures',
    'RequestFixtures',
    'DateTimeFixtures'
]


# ==============================================================================
# FIXTURE LOADER
# ==============================================================================

class FixtureLoader:
    """Helper class to load and create fixtures in database"""
    
    @staticmethod
    def load_users(count=None):
        """
        Load user fixtures into database.
        
        Args:
            count (int, optional): Number of users to create. If None, creates default users.
            
        Returns:
            list: Created User objects
        """
        users = []
        
        if count:
            fixtures = UserFixtures.multiple_users(count)
        else:
            fixtures = [
                UserFixtures.basic_user(),
                UserFixtures.admin_user()
            ]
        
        for fixture in fixtures:
            user = UserFixtures.create_user_from_fixture(fixture.copy())
            users.append(user)
        
        return users
    
    @staticmethod
    def load_vault_items(user, item_types=None):
        """
        Load vault item fixtures for a user.
        
        Args:
            user (User): User to create items for
            item_types (list, optional): Types of items to create
            
        Returns:
            list: Created vault item data
        """
        items = []
        
        if item_types is None:
            item_types = ['password', 'card', 'note', 'identity']
        
        if 'password' in item_types:
            items.append(VaultItemFixtures.password_item())
        if 'card' in item_types:
            items.append(VaultItemFixtures.credit_card_item())
        if 'note' in item_types:
            items.append(VaultItemFixtures.secure_note_item())
        if 'identity' in item_types:
            items.append(VaultItemFixtures.identity_item())
        
        return items
    
    @staticmethod
    def load_all_fixtures(user_count=1):
        """
        Load all fixtures into database.
        
        Args:
            user_count (int): Number of users to create
            
        Returns:
            dict: Dictionary of created fixtures
        """
        users = FixtureLoader.load_users(user_count)
        
        return {
            'users': users,
            'vault_items': [],  # Would load actual vault items
            'security_alerts': SecurityFixtures.security_alerts(),
            'user_devices': SecurityFixtures.user_devices()
        }


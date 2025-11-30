"""
Test Utilities
==============

Utility functions and helpers for testing.
"""

from django.test import Client
from django.contrib.auth.models import User
import json
import random
import string
import hashlib


# ==============================================================================
# USER CREATION UTILITIES
# ==============================================================================

def create_test_user(username='testuser', email=None, password='testpass123', **kwargs):
    """
    Create a test user with given credentials.
    
    Args:
        username (str): Username for the test user
        email (str): Email for the test user (defaults to username@test.com)
        password (str): Password for the test user
        **kwargs: Additional fields for user creation
        
    Returns:
        User: Created user object
    """
    if email is None:
        email = f'{username}@test.com'
    
    user = User.objects.create_user(
        username=username,
        email=email,
        password=password,
        **kwargs
    )
    return user


def create_multiple_test_users(count=5, prefix='user'):
    """
    Create multiple test users.
    
    Args:
        count (int): Number of users to create
        prefix (str): Prefix for usernames
        
    Returns:
        list: List of created user objects
    """
    users = []
    for i in range(count):
        user = create_test_user(
            username=f'{prefix}{i}',
            email=f'{prefix}{i}@test.com'
        )
        users.append(user)
    return users


def generate_random_username(length=10):
    """Generate a random username."""
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=length))


def generate_random_email():
    """Generate a random email address."""
    username = generate_random_username(8)
    domain = random.choice(['test.com', 'example.com', 'demo.com'])
    return f'{username}@{domain}'


# ==============================================================================
# CLIENT UTILITIES
# ==============================================================================

def create_authenticated_client(user=None):
    """
    Create an authenticated Django test client.
    
    Args:
        user (User, optional): User to authenticate as. Creates new user if None.
        
    Returns:
        tuple: (client, user)
    """
    client = Client()
    
    if user is None:
        user = create_test_user()
    
    client.force_login(user)
    return client, user


def make_api_request(client, method, url, data=None, headers=None):
    """
    Make an API request using the test client.
    
    Args:
        client: Django test client
        method (str): HTTP method ('GET', 'POST', 'PUT', 'PATCH', 'DELETE')
        url (str): URL to request
        data (dict, optional): Request data
        headers (dict, optional): Additional headers
        
    Returns:
        Response: Django response object
    """
    kwargs = {'content_type': 'application/json'}
    
    if headers:
        for key, value in headers.items():
            kwargs[f'HTTP_{key.upper().replace("-", "_")}'] = value
    
    if data:
        kwargs['data'] = json.dumps(data)
    
    method = method.upper()
    
    if method == 'GET':
        return client.get(url, **kwargs)
    elif method == 'POST':
        return client.post(url, **kwargs)
    elif method == 'PUT':
        return client.put(url, **kwargs)
    elif method == 'PATCH':
        return client.patch(url, **kwargs)
    elif method == 'DELETE':
        return client.delete(url, **kwargs)
    else:
        raise ValueError(f"Unsupported HTTP method: {method}")


# ==============================================================================
# DATA GENERATION UTILITIES
# ==============================================================================

def generate_password(length=16, include_special=True):
    """
    Generate a random password.
    
    Args:
        length (int): Length of password
        include_special (bool): Whether to include special characters
        
    Returns:
        str: Generated password
    """
    chars = string.ascii_letters + string.digits
    if include_special:
        chars += string.punctuation
    
    return ''.join(random.choices(chars, k=length))


def generate_vault_item_data(item_type='password'):
    """
    Generate test vault item data.
    
    Args:
        item_type (str): Type of vault item ('password', 'card', 'note', 'identity')
        
    Returns:
        dict: Vault item data
    """
    if item_type == 'password':
        return {
            'item_type': 'password',
            'name': f'Test Login {random.randint(1, 1000)}',
            'username': generate_random_username(),
            'password': generate_password(),
            'url': f'https://example{random.randint(1, 100)}.com',
            'notes': 'Test notes',
            'favorite': random.choice([True, False])
        }
    elif item_type == 'card':
        return {
            'item_type': 'card',
            'name': f'Test Card {random.randint(1, 1000)}',
            'card_number': f'{random.randint(1000, 9999)} **** **** ****',
            'cardholder_name': 'Test User',
            'expiry_month': str(random.randint(1, 12)).zfill(2),
            'expiry_year': str(random.randint(2024, 2030)),
            'cvv': str(random.randint(100, 999))
        }
    elif item_type == 'note':
        return {
            'item_type': 'note',
            'name': f'Test Note {random.randint(1, 1000)}',
            'note_content': 'This is a test secure note.'
        }
    elif item_type == 'identity':
        return {
            'item_type': 'identity',
            'name': f'Test Identity {random.randint(1, 1000)}',
            'first_name': 'John',
            'last_name': 'Doe',
            'email': generate_random_email(),
            'phone': f'+1{random.randint(1000000000, 9999999999)}',
            'address': '123 Test Street'
        }
    else:
        raise ValueError(f"Unknown item type: {item_type}")


def generate_ml_test_data():
    """Generate test data for ML models."""
    return {
        'password_samples': [
            'password123',
            'P@ssw0rd!',
            '123456',
            'Str0ng!P@ssw0rd#2024',
            'weakpass'
        ],
        'anomaly_events': [
            {
                'ip_latitude': 34.0522,
                'ip_longitude': -118.2437,
                'time_of_day_sin': 0.5,
                'time_of_day_cos': 0.866
            },
            {
                'ip_latitude': 51.5074,  # London
                'ip_longitude': 0.1278,
                'time_of_day_sin': -0.9,
                'time_of_day_cos': 0.4
            }
        ],
        'threat_sequences': [
            'user_login_success browser_chrome os_windows',
            'user_login_fail_3x browser_unknown os_linux',
            'brute_force_attempt ip_change data_exfil'
        ]
    }


# ==============================================================================
# ASSERTION UTILITIES
# ==============================================================================

def assert_response_success(response, expected_status=200):
    """
    Assert that a response is successful.
    
    Args:
        response: Django response object
        expected_status (int): Expected status code
    """
    assert response.status_code == expected_status, (
        f"Expected status {expected_status}, got {response.status_code}. "
        f"Response: {response.content.decode('utf-8')}"
    )


def assert_response_has_keys(response, keys):
    """
    Assert that response JSON contains expected keys.
    
    Args:
        response: Django response object
        keys (list): List of expected keys
    """
    data = response.json()
    for key in keys:
        assert key in data, f"Expected key '{key}' not found in response"


def assert_response_error(response, expected_status=400):
    """
    Assert that a response is an error.
    
    Args:
        response: Django response object
        expected_status (int): Expected error status code
    """
    assert response.status_code == expected_status, (
        f"Expected error status {expected_status}, got {response.status_code}"
    )
    data = response.json()
    assert 'error' in data or 'detail' in data, (
        "Response should contain 'error' or 'detail' field"
    )


# ==============================================================================
# MOCK DATA UTILITIES
# ==============================================================================

def create_mock_request_data(ip='192.168.1.1', user_agent='Mozilla/5.0', **kwargs):
    """
    Create mock request data for testing.
    
    Args:
        ip (str): IP address
        user_agent (str): User agent string
        **kwargs: Additional request data
        
    Returns:
        dict: Mock request data
    """
    data = {
        'REMOTE_ADDR': ip,
        'HTTP_USER_AGENT': user_agent,
    }
    data.update(kwargs)
    return data


def create_mock_login_attempt_data(username, success=True, threat_score=0):
    """
    Create mock login attempt data.
    
    Args:
        username (str): Username
        success (bool): Whether login was successful
        threat_score (int): Threat score (0-100)
        
    Returns:
        dict: Login attempt data
    """
    return {
        'username': username,
        'status': 'success' if success else 'failed',
        'threat_score': threat_score,
        'ip_address': f'192.168.1.{random.randint(1, 254)}',
        'user_agent': 'Mozilla/5.0',
        'is_suspicious': threat_score > 50
    }


# ==============================================================================
# CLEANUP UTILITIES
# ==============================================================================

def cleanup_test_data(user=None):
    """
    Clean up test data from database.
    
    Args:
        user (User, optional): Specific user to clean up. If None, cleans all test users.
    """
    if user:
        # Clean up specific user's data
        user.delete()
    else:
        # Clean up all test users
        User.objects.filter(email__endswith='@test.com').delete()
        User.objects.filter(username__startswith='test').delete()


def reset_database_sequences():
    """Reset database auto-increment sequences (useful for consistent test IDs)."""
    from django.core.management import call_command
    call_command('flush', '--noinput')


# ==============================================================================
# TIME UTILITIES
# ==============================================================================

from datetime import datetime, timedelta
from django.utils import timezone


def get_datetime_n_days_ago(n):
    """Get datetime n days ago."""
    return timezone.now() - timedelta(days=n)


def get_datetime_n_hours_ago(n):
    """Get datetime n hours ago."""
    return timezone.now() - timedelta(hours=n)


def get_datetime_n_minutes_ago(n):
    """Get datetime n minutes ago."""
    return timezone.now() - timedelta(minutes=n)


# ==============================================================================
# ENCRYPTION UTILITIES (FOR TESTING)
# ==============================================================================

import base64


def mock_encrypt(data):
    """
    Mock encryption function for testing.
    NOT SECURE - only for testing!
    
    Args:
        data (str): Data to "encrypt"
        
    Returns:
        str: Base64 encoded data
    """
    return base64.b64encode(data.encode()).decode()


def mock_decrypt(encrypted_data):
    """
    Mock decryption function for testing.
    
    Args:
        encrypted_data (str): Base64 encoded data
        
    Returns:
        str: Decoded data
    """
    return base64.b64decode(encrypted_data.encode()).decode()


def generate_password_hash(password):
    """
    Generate a SHA256 hash of a password.
    
    Args:
        password (str): Password to hash
        
    Returns:
        str: Hexadecimal hash
    """
    return hashlib.sha256(password.encode()).hexdigest()


# ==============================================================================
# DATABASE UTILITIES
# ==============================================================================

def count_database_objects(model_class, **filters):
    """
    Count objects in database with optional filters.
    
    Args:
        model_class: Django model class
        **filters: Filter criteria
        
    Returns:
        int: Count of objects
    """
    return model_class.objects.filter(**filters).count()


def get_or_create_test_object(model_class, defaults, **lookup):
    """
    Get or create a test object.
    
    Args:
        model_class: Django model class
        defaults (dict): Default values for creation
        **lookup: Lookup criteria
        
    Returns:
        tuple: (object, created)
    """
    return model_class.objects.get_or_create(defaults=defaults, **lookup)


# ==============================================================================
# LOGGING UTILITIES
# ==============================================================================

import logging


def suppress_test_logging():
    """Suppress logging during tests to reduce output."""
    logging.disable(logging.CRITICAL)


def enable_test_logging():
    """Re-enable logging after tests."""
    logging.disable(logging.NOTSET)


def capture_log_output(logger_name='django'):
    """
    Context manager to capture log output during tests.
    
    Args:
        logger_name (str): Name of logger to capture
        
    Usage:
        with capture_log_output() as log_output:
            # Run test code
            pass
        assert 'expected message' in log_output.getvalue()
    """
    import io
    from contextlib import contextmanager
    
    @contextmanager
    def _capture():
        log_output = io.StringIO()
        handler = logging.StreamHandler(log_output)
        logger = logging.getLogger(logger_name)
        logger.addHandler(handler)
        try:
            yield log_output
        finally:
            logger.removeHandler(handler)
    
    return _capture()


# ==============================================================================
# PERFORMANCE UTILITIES
# ==============================================================================

import time


class PerformanceTimer:
    """Context manager for timing code execution."""
    
    def __init__(self, name='Operation'):
        self.name = name
        self.start_time = None
        self.end_time = None
        self.elapsed = None
    
    def __enter__(self):
        self.start_time = time.time()
        return self
    
    def __exit__(self, *args):
        self.end_time = time.time()
        self.elapsed = self.end_time - self.start_time
    
    def __str__(self):
        return f"{self.name} took {self.elapsed:.4f} seconds"


def measure_query_count(func):
    """
    Decorator to measure database query count for a function.
    
    Usage:
        @measure_query_count
        def my_test_function():
            # Test code
            pass
    """
    from django.test.utils import override_settings
    from django.db import connection
    from django.test.utils import CaptureQueriesContext
    
    def wrapper(*args, **kwargs):
        with CaptureQueriesContext(connection) as queries:
            result = func(*args, **kwargs)
        print(f"\n{func.__name__} executed {len(queries)} database queries")
        return result
    
    return wrapper


# ==============================================================================
# VALIDATION UTILITIES
# ==============================================================================

def validate_email_format(email):
    """Validate email format."""
    import re
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None


def validate_password_strength(password, min_length=8):
    """
    Validate password meets minimum requirements.
    
    Args:
        password (str): Password to validate
        min_length (int): Minimum length
        
    Returns:
        tuple: (is_valid, errors)
    """
    errors = []
    
    if len(password) < min_length:
        errors.append(f"Password must be at least {min_length} characters")
    
    if not any(c.isupper() for c in password):
        errors.append("Password must contain at least one uppercase letter")
    
    if not any(c.islower() for c in password):
        errors.append("Password must contain at least one lowercase letter")
    
    if not any(c.isdigit() for c in password):
        errors.append("Password must contain at least one digit")
    
    return len(errors) == 0, errors


# ==============================================================================
# EXPORT UTILITIES
# ==============================================================================

__all__ = [
    # User creation
    'create_test_user',
    'create_multiple_test_users',
    'generate_random_username',
    'generate_random_email',
    
    # Client utilities
    'create_authenticated_client',
    'make_api_request',
    
    # Data generation
    'generate_password',
    'generate_vault_item_data',
    'generate_ml_test_data',
    
    # Assertions
    'assert_response_success',
    'assert_response_has_keys',
    'assert_response_error',
    
    # Mock data
    'create_mock_request_data',
    'create_mock_login_attempt_data',
    
    # Cleanup
    'cleanup_test_data',
    'reset_database_sequences',
    
    # Time
    'get_datetime_n_days_ago',
    'get_datetime_n_hours_ago',
    'get_datetime_n_minutes_ago',
    
    # Encryption (mock)
    'mock_encrypt',
    'mock_decrypt',
    'generate_password_hash',
    
    # Database
    'count_database_objects',
    'get_or_create_test_object',
    
    # Logging
    'suppress_test_logging',
    'enable_test_logging',
    'capture_log_output',
    
    # Performance
    'PerformanceTimer',
    'measure_query_count',
    
    # Validation
    'validate_email_format',
    'validate_password_strength',
]


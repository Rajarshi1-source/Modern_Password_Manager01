# Manual Testing Guide for Security Service

## Table of Contents
- [Overview](#overview)
- [Prerequisites](#prerequisites)
- [Quick Start](#quick-start)
- [Testing Methods](#testing-methods)
  - [Method 1: Management Command (Recommended)](#method-1-management-command-recommended)
  - [Method 2: Django Shell](#method-2-django-shell)
  - [Method 3: Integration Testing](#method-3-integration-testing)
- [Test Scenarios](#test-scenarios)
- [Advanced Testing](#advanced-testing)
- [Troubleshooting](#troubleshooting)
- [Best Practices](#best-practices)

## Overview

This guide provides comprehensive instructions for manually testing the SecurityService functionality, including:

- Login attempt analysis
- Threat detection
- Social account locking
- Notification services
- Performance testing
- Database state verification

## Prerequisites

### Environment Setup

1. **Activate Virtual Environment:**
   ```bash
   # Windows
   .\canny\Scripts\activate
   
   # Linux/Mac
   source canny/bin/activate
   ```

2. **Navigate to Backend:**
   ```bash
   cd password_manager
   ```

3. **Ensure Database is Migrated:**
   ```bash
   python manage.py migrate
   ```

4. **Create Test User (Optional):**
   ```bash
   python manage.py createsuperuser --username testuser --email test@example.com
   ```

## Quick Start

### Fastest Way to Test

```bash
# Run all security tests
python manage.py test_security --all

# Run a specific scenario
python manage.py test_security --scenario normal_login

# List available scenarios
python manage.py test_security --list
```

## Testing Methods

### Method 1: Management Command (Recommended)

The easiest way to run tests without entering Django shell.

#### Basic Commands

```bash
# 1. Run ALL test scenarios
python manage.py test_security --all

# 2. Run SPECIFIC scenario
python manage.py test_security --scenario normal_login
python manage.py test_security --scenario high_risk_combination
python manage.py test_security --scenario brute_force_attempt

# 3. List AVAILABLE scenarios
python manage.py test_security --list

# 4. Run PERFORMANCE test
python manage.py test_security --performance --requests 200

# 5. Test SOCIAL ACCOUNT locking
python manage.py test_security --test-locking

# 6. Verify DATABASE state
python manage.py test_security --verify-db

# 7. CLEANUP test data
python manage.py test_security --cleanup

# 8. Test NOTIFICATIONS
python manage.py test_security --test-notifications
```

#### Advanced Usage

```bash
# Use custom username
python manage.py test_security --scenario new_device --username myuser

# Run all tests without cleanup
python manage.py test_security --all --no-cleanup

# Performance test with more requests
python manage.py test_security --performance --requests 500

# Verbose output for debugging
python manage.py test_security --all --verbose
```

### Method 2: Django Shell

For interactive testing and debugging.

#### Step 1: Start Django Shell

```bash
python manage.py shell
```

#### Step 2: Import Testing Modules

```python
from tests.manual_security_tests import (
    SecurityTestRunner,
    TestScenarios,
    NotificationTestHelper,
    quick_test,
    run_all,
    test_performance,
    cleanup
)
```

#### Step 3: Run Tests

**Option A: Quick Functions**

```python
# Run a single test
quick_test('normal_login')

# Run all tests
results = run_all()

# Performance test
metrics = test_performance(num_requests=100)

# Cleanup
cleanup()
```

**Option B: Full Control**

```python
# Initialize runner
runner = SecurityTestRunner(username='testuser')

# Run specific scenario
runner.test_scenario('normal_login')
runner.test_scenario('high_risk_combination')

# Run all scenarios
results = runner.run_all_tests(cleanup=True)

# Test specific features
runner.test_social_account_locking()
runner.test_performance(num_requests=200)
runner.verify_database_state()
runner.cleanup_test_data()
```

### Method 3: Integration Testing

Test the actual authentication flow with security analysis.

#### Using Django Test Client

```python
from django.test import Client
from django.contrib.auth.models import User

# Initialize client
client = Client()

# Test normal login
response = client.post('/auth/login/', {
    'username': 'testuser',
    'password': 'correct_password'
}, HTTP_USER_AGENT='Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
   REMOTE_ADDR='192.168.1.100')

print(f"Status Code: {response.status_code}")
print(f"Response: {response.json()}")

# Verify security analysis was triggered
from security.models import LoginAttempt
latest_attempt = LoginAttempt.objects.filter(
    username_attempted='testuser'
).order_by('-timestamp').first()

if latest_attempt:
    print(f"Threat Score: {latest_attempt.threat_score}")
    print(f"Is Suspicious: {latest_attempt.is_suspicious}")
    print(f"Suspicious Factors: {latest_attempt.suspicious_factors}")
```

## Test Scenarios

### Available Scenarios

| Scenario Name | Description | Expected Risk |
|---------------|-------------|---------------|
| `normal_login` | Login from known device and location | Low (0-30) |
| `new_device` | Login from new device | Medium (30-60) |
| `new_location` | Login from unusual geographic location | Medium (30-60) |
| `suspicious_user_agent` | Login using automated tool (curl, etc.) | High (60-85) |
| `high_risk_combination` | Multiple suspicious factors combined | High (70-100) |
| `brute_force_attempt` | Multiple failed login attempts | Critical (80-100) |
| `impossible_travel` | Login from distant location in short time | High (70-90) |

### Scenario Details

#### 1. Normal Login
```bash
python manage.py test_security --scenario normal_login
```
**Expected Results:**
- Threat Score: 0-30
- Is Suspicious: False
- Device registered/updated

#### 2. New Device
```bash
python manage.py test_security --scenario new_device
```
**Expected Results:**
- Threat Score: 30-60
- Is Suspicious: Possibly (depends on threshold)
- New device factor flagged

#### 3. High Risk Combination
```bash
python manage.py test_security --scenario high_risk_combination
```
**Expected Results:**
- Threat Score: 70-100
- Is Suspicious: True
- Multiple factors flagged
- Security alert created
- Possible account locking

#### 4. Brute Force Attempt
```bash
python manage.py test_security --scenario brute_force_attempt
```
**Expected Results:**
- Simulates 6 failed attempts
- Threat score increases with each attempt
- Final score: 80-100
- Account may be locked

## Advanced Testing

### Custom Test Scenarios

#### Create Custom Scenario in Django Shell

```python
from django.test import RequestFactory
from security.services.security_service import SecurityService
from django.contrib.auth.models import User

# Setup
factory = RequestFactory()
security_service = SecurityService()
user = User.objects.get(username='testuser')

# Create custom request
request = factory.post('/auth/login/', {
    'username': 'testuser',
    'password': 'testpass123',
    'device_fingerprint': 'custom_device_456'
})

# Custom headers
request.META['HTTP_USER_AGENT'] = 'CustomBrowser/1.0'
request.META['REMOTE_ADDR'] = '198.51.100.50'

# Analyze
attempt = security_service.analyze_login_attempt(
    user=user,
    request=request,
    is_successful=True
)

# Results
print(f"Threat Score: {attempt.threat_score}")
print(f"Suspicious: {attempt.is_suspicious}")
print(f"Factors: {attempt.suspicious_factors}")
```

### Testing Different IP Ranges

```python
# Test various IP addresses
test_ips = [
    ('192.168.1.100', 'Local Network'),
    ('203.0.113.1', 'Different Country'),
    ('198.51.100.1', 'Suspicious Range'),
    ('8.8.8.8', 'Google DNS'),
    ('1.1.1.1', 'Cloudflare DNS')
]

for ip, description in test_ips:
    request.META['REMOTE_ADDR'] = ip
    attempt = security_service.analyze_login_attempt(
        user=user,
        request=request,
        is_successful=True
    )
    print(f"{description} ({ip}): Score={attempt.threat_score}")
```

### Testing User Agents

```python
# Test different user agents
test_user_agents = [
    ('Mozilla/5.0 (Windows NT 10.0; Win64; x64)', 'Normal Browser'),
    ('Mozilla/5.0 (iPhone; CPU iPhone OS 17_0)', 'Mobile Device'),
    ('curl/7.68.0', 'Command Line Tool - Suspicious'),
    ('python-requests/2.28.1', 'Python Script - Suspicious'),
    ('PostmanRuntime/7.29.2', 'API Testing Tool')
]

for ua, description in test_user_agents:
    request.META['HTTP_USER_AGENT'] = ua
    attempt = security_service.analyze_login_attempt(
        user=user,
        request=request,
        is_successful=True
    )
    print(f"{description}: Score={attempt.threat_score}")
```

### Performance and Load Testing

```python
import time
from django.utils import timezone

# Test with rapid requests
start_time = time.time()
results = []

for i in range(100):
    request.META['REMOTE_ADDR'] = f'192.168.1.{(i % 255) + 1}'
    request.data['device_fingerprint'] = f'device_{i}'
    
    attempt = security_service.analyze_login_attempt(
        user=user,
        request=request,
        is_successful=True
    )
    results.append(attempt.threat_score)

end_time = time.time()

# Statistics
print(f"Completed: {len(results)} analyses")
print(f"Total Time: {end_time - start_time:.2f} seconds")
print(f"Avg Time: {(end_time - start_time) / len(results):.4f} seconds")
print(f"Throughput: {len(results) / (end_time - start_time):.2f} req/sec")
print(f"Avg Score: {sum(results) / len(results):.2f}")
```

### Testing Social Account Locking

```python
from security.models import SocialMediaAccount
from unittest.mock import patch

# Create social account
social_account = SocialMediaAccount.objects.create(
    user=user,
    platform='facebook',
    username='testuser_fb',
    status='active',
    auto_lock_enabled=True
)

print(f"Initial Status: {social_account.status}")

# Mock high-risk scenario
with patch.object(security_service, '_calculate_risk_score') as mock_calc:
    mock_calc.return_value = {
        'risk_score': 85,
        'suspicious_factors': {
            'new_device': True,
            'suspicious_user_agent': True,
            'blacklisted_ip': True
        }
    }
    
    attempt = security_service.analyze_login_attempt(
        user=user,
        request=request,
        is_successful=True
    )

# Check if locked
social_account.refresh_from_db()
print(f"Final Status: {social_account.status}")
print(f"Was Locked: {social_account.status == 'locked'}")
```

### Testing Notification Service

```python
from security.services.security_service import NotificationService
from security.models import LoginAttempt
from unittest.mock import patch

# Create suspicious login attempt
attempt = LoginAttempt.objects.create(
    user=user,
    username_attempted=user.username,
    ip_address='10.0.0.1',
    status='success',
    is_suspicious=True,
    threat_score=75,
    suspicious_factors={'new_device': True},
    location='Unknown, US'
)

# Test email notification
with patch('security.services.security_service.send_mail') as mock_send:
    NotificationService.send_suspicious_login_alert(user, attempt)
    
    if mock_send.called:
        print("✓ Email notification sent")
        call_args = mock_send.call_args[1]
        print(f"  Subject: {call_args['subject']}")
        print(f"  To: {call_args['recipient_list']}")
    else:
        print("⚠ No email sent (check threshold settings)")
```

## Database State Verification

### Check Security Records

```python
from security.models import (
    LoginAttempt, UserDevice, SecurityAlert,
    AccountLockEvent, SocialMediaAccount
)

# Get statistics
stats = {
    'total_attempts': LoginAttempt.objects.count(),
    'suspicious_attempts': LoginAttempt.objects.filter(is_suspicious=True).count(),
    'user_attempts': LoginAttempt.objects.filter(user=user).count(),
    'devices': UserDevice.objects.filter(user=user).count(),
    'alerts': SecurityAlert.objects.filter(user=user).count(),
    'lock_events': AccountLockEvent.objects.filter(user=user).count()
}

for key, value in stats.items():
    print(f"{key}: {value}")

# View recent suspicious attempts
suspicious = LoginAttempt.objects.filter(
    user=user,
    is_suspicious=True
).order_by('-timestamp')[:5]

for attempt in suspicious:
    print(f"{attempt.timestamp} - IP: {attempt.ip_address} - Score: {attempt.threat_score}")
```

### Query Specific Data

```python
# Failed login attempts in last hour
from datetime import timedelta
from django.utils import timezone

recent_failures = LoginAttempt.objects.filter(
    user=user,
    status='failed',
    timestamp__gte=timezone.now() - timedelta(hours=1)
).count()

print(f"Failed attempts in last hour: {recent_failures}")

# Highest risk attempts
high_risk = LoginAttempt.objects.filter(
    user=user,
    threat_score__gte=70
).order_by('-threat_score')[:10]

for attempt in high_risk:
    print(f"Score: {attempt.threat_score} - IP: {attempt.ip_address}")
```

## Cleanup After Testing

### Method 1: Management Command
```bash
python manage.py test_security --cleanup
```

### Method 2: Django Shell
```python
from tests.manual_security_tests import cleanup
cleanup('testuser')
```

### Method 3: Manual Cleanup
```python
from security.models import *
from django.contrib.auth.models import User

user = User.objects.get(username='testuser')

# Delete all test data
LoginAttempt.objects.filter(user=user).delete()
UserDevice.objects.filter(user=user).delete()
SecurityAlert.objects.filter(user=user).delete()
AccountLockEvent.objects.filter(user=user).delete()
SocialMediaAccount.objects.filter(user=user).delete()

print("✓ Test data cleaned up")
```

## Troubleshooting

### Common Issues

#### 1. ModuleNotFoundError

**Problem:**
```
ModuleNotFoundError: No module named 'tests.manual_security_tests'
```

**Solution:**
```python
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
```

#### 2. User Does Not Exist

**Problem:**
```
User matching query does not exist.
```

**Solution:**
```python
# The test runner creates the user automatically, or:
from django.contrib.auth.models import User
User.objects.create_user('testuser', 'test@example.com', 'testpass123')
```

#### 3. GeoIP Database Not Found

**Problem:**
```
GeoIP database not found
```

**Solution:**
- This is expected if GeoIP2 databases aren't installed
- Location will default to "Unknown Location"
- Tests will still run successfully

#### 4. Import Errors

**Problem:**
```
ImportError: cannot import name 'SecurityService'
```

**Solution:**
```bash
# Ensure you're in the password_manager directory
cd password_manager
python manage.py shell
```

## Best Practices

### 1. Always Clean Up After Testing
```bash
python manage.py test_security --all
python manage.py test_security --cleanup
```

### 2. Test on a Separate Test User
```bash
python manage.py test_security --all --username test_security_user
python manage.py test_security --cleanup --username test_security_user
```

### 3. Run Tests in Order
1. Normal scenarios first
2. High-risk scenarios
3. Performance tests
4. Verification
5. Cleanup

### 4. Document Test Results
```bash
# Save output to file
python manage.py test_security --all > test_results.txt 2>&1
```

### 5. Regular Testing Schedule
- After security service changes
- Before deployment
- Weekly security audits
- After suspicious activity detection

## Integration with CI/CD

### Automated Testing Script

Create `test_security_ci.sh`:

```bash
#!/bin/bash
# CI/CD Security Testing Script

cd password_manager

# Run all security tests
python manage.py test_security --all --no-cleanup

# Check exit code
if [ $? -eq 0 ]; then
    echo "✓ Security tests passed"
    python manage.py test_security --cleanup
    exit 0
else
    echo "✗ Security tests failed"
    python manage.py test_security --cleanup
    exit 1
fi
```

Make executable:
```bash
chmod +x test_security_ci.sh
```

## Additional Resources

- **Security Service Code:** `password_manager/security/services/security_service.py`
- **Test Module:** `tests/manual_security_tests.py`
- **Management Command:** `password_manager/security/management/commands/test_security.py`
- **Models:** `password_manager/security/models.py`
- **Automated Tests:** `password_manager/security/tests.py`

## Support

For issues or questions:
1. Check the troubleshooting section above
2. Review security service logs in `logs/security.log`
3. Check Django logs in `logs/django.log`
4. Run with `--verbose` flag for detailed output

## Contributing

When adding new test scenarios:
1. Add to `TestScenarios.get_all_scenarios()` in `tests/manual_security_tests.py`
2. Update this documentation
3. Test with both management command and shell
4. Document expected results

---

**Last Updated:** October 2025  
**Version:** 1.0  
**Maintained By:** Password Manager Security Team


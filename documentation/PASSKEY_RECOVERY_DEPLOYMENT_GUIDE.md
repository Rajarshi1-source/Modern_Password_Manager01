# Passkey Recovery System - Deployment Guide

## Table of Contents
1. [Prerequisites](#prerequisites)
2. [System Testing](#system-testing)
3. [Security Hardening](#security-hardening)
4. [Production Deployment](#production-deployment)
5. [Monitoring Setup](#monitoring-setup)
6. [Troubleshooting](#troubleshooting)

---

## Prerequisites

### Required Dependencies

Ensure all required packages are installed:

```bash
cd password_manager
pip install -r requirements.txt
```

#### Critical Packages for Recovery System:
- `liboqs-python>=0.10.0` - Real CRYSTALS-Kyber implementation
- `pycryptodome>=3.20.0` - Alternative crypto library
- `secretsharing>=0.2.9` - Shamir's Secret Sharing
- `celery>=5.3.0` - Async task processing
- `redis>=5.0.0` - Cache and message broker

### Database Requirements
- PostgreSQL 14+ (recommended for production)
- SQLite (development only)

---

## System Testing

### 1. Run Migrations

```bash
# Navigate to project root
cd password_manager

# Generate and apply migrations
python manage.py makemigrations auth_module
python manage.py migrate
```

### 2. Run Test Suite

```bash
# Run all recovery tests
python manage.py test_passkey_recovery --test all --verbose

# Run specific tests
python manage.py test_passkey_recovery --test crypto     # Cryptography tests
python manage.py test_passkey_recovery --test setup      # Setup flow tests
python manage.py test_passkey_recovery --test recovery   # Recovery flow tests
python manage.py test_passkey_recovery --test fallback   # Fallback mechanism tests
python manage.py test_passkey_recovery --test monitoring # Monitoring tests

# Run with cleanup
python manage.py test_passkey_recovery --test all --cleanup
```

### 3. Test Setup Flow

```python
# Django shell test
python manage.py shell

from django.contrib.auth import get_user_model
from auth_module.services.passkey_primary_recovery_service import PasskeyPrimaryRecoveryService

User = get_user_model()
user = User.objects.get(username='testuser')

service = PasskeyPrimaryRecoveryService()

# Generate recovery key
recovery_key = service.generate_recovery_key()
print(f"Recovery Key: {recovery_key}")  # SAVE THIS!

# Create credential data
credential_data = {
    'credential_id': 'test_cred_001',
    'public_key': 'your_public_key_data',
    'rp_id': 'localhost',
}

# Encrypt
encrypted_data, metadata = service.encrypt_passkey_credential(
    credential_data=credential_data,
    recovery_key=recovery_key
)

print("Encryption successful!")
```

### 4. Test Recovery Flow

```python
# Verify recovery key
is_valid = backup.verify_recovery_key(recovery_key)
print(f"Key Valid: {is_valid}")

# Decrypt credential data
decrypted = service.decrypt_passkey_credential(
    encrypted_data=backup.encrypted_credential_data,
    recovery_key=recovery_key,
    encryption_metadata=backup.encryption_metadata
)
print(f"Decrypted: {decrypted}")
```

### 5. Test Fallback Mechanism

```python
from auth_module.passkey_primary_recovery_models import PasskeyRecoveryAttempt

# Create a failed attempt
attempt = PasskeyRecoveryAttempt.objects.create(
    user=user,
    status='key_invalid',
    failure_reason='Test fallback'
)

# Trigger fallback
attempt.initiate_fallback()
print(f"Status: {attempt.status}")  # Should be 'fallback_initiated'
```

---

## Security Hardening

### 1. Install Real Kyber Implementation

Replace the simulated Kyber with a real post-quantum cryptography library:

```bash
# Option 1: liboqs-python (recommended)
pip install liboqs-python

# Option 2: pqcrypto
pip install pqcrypto
```

**Verify installation:**
```python
from auth_module.services.kyber_crypto import get_crypto_status

status = get_crypto_status()
print(f"Using real PQC: {status['using_real_pqc']}")
print(f"Implementation: {status['implementation']}")
```

### 2. Enable Rate Limiting

Add to `settings.py`:

```python
# Recovery-specific throttle rates
REST_FRAMEWORK['DEFAULT_THROTTLE_RATES'].update({
    'recovery': '3/hour',          # General recovery operations
    'recovery_initiate': '5/hour', # Recovery initiation
    'recovery_complete': '3/hour', # Key verification (strict)
})

# Progressive lockout settings
RECOVERY_THROTTLE_RATE = '3/hour'
RECOVERY_INITIATE_RATE = '5/hour'
RECOVERY_COMPLETE_RATE = '3/hour'
```

Add throttle classes to views:

```python
from auth_module.recovery_throttling import (
    RecoveryThrottle,
    RecoveryCompleteThrottle,
    ProgressiveLockoutThrottle
)

@api_view(['POST'])
@throttle_classes([RecoveryThrottle, ProgressiveLockoutThrottle])
def complete_primary_passkey_recovery(request):
    # ...
```

### 3. Enable Security Monitoring

Add to `settings.py`:

```python
# Security monitoring
SECURITY_ALERT_EMAIL = os.environ.get('SECURITY_ALERT_EMAIL', 'security@yourcompany.com')
RECOVERY_ALERT_THRESHOLD = 5  # Trigger alert after 5 failed attempts

# Logging configuration
LOGGING['loggers']['auth_module'] = {
    'handlers': ['security_file', 'console'],
    'level': 'INFO',
    'propagate': False,
}
```

### 4. Configure Production Crypto Settings

Add to `settings.py`:

```python
# Post-Quantum Cryptography Configuration
QUANTUM_CRYPTO = {
    'ENABLED': True,
    'ALGORITHM': 'Kyber768',
    'ALLOW_SIMULATION': False,  # Disable simulation in production!
    'HYBRID_MODE': True,  # Always use hybrid Kyber + AES-256-GCM
}

# Passkey Recovery Settings
PASSKEY_RECOVERY = {
    'KEY_LENGTH': 24,
    'MAX_BACKUPS_PER_USER': 5,
    'BACKUP_EXPIRY_DAYS': 365,
    'MAX_RECOVERY_ATTEMPTS': 3,
    'LOCKOUT_DURATION_HOURS': 24,
}
```

---

## Production Deployment

### 1. Environment Variables

Create `.env` file:

```env
# Django
SECRET_KEY=your-super-secret-key-min-50-chars
DEBUG=False
ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com

# Database
DATABASE_URL=postgres://user:password@localhost:5432/password_manager

# Redis
REDIS_URL=redis://localhost:6379/0
CELERY_BROKER_URL=redis://localhost:6379/1
CELERY_RESULT_BACKEND=redis://localhost:6379/2

# Security
SECURE_SSL_REDIRECT=True
SESSION_COOKIE_SECURE=True
CSRF_COOKIE_SECURE=True

# Email (for recovery notifications)
EMAIL_HOST=smtp.yourprovider.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=your-email@domain.com
EMAIL_HOST_PASSWORD=your-email-password
DEFAULT_FROM_EMAIL=SecureVault <noreply@yourdomain.com>

# Monitoring
SENTRY_DSN=your-sentry-dsn
SECURITY_ALERT_EMAIL=security@yourdomain.com
```

### 2. Database Migration

```bash
# Production migration
python manage.py migrate --no-input
python manage.py collectstatic --no-input
```

### 3. Celery Configuration

Create `celery_config.py`:

```python
from celery.schedules import crontab

# Celery Beat Schedule
CELERY_BEAT_SCHEDULE = {
    # Clean up expired recovery attempts
    'cleanup-expired-recovery-attempts': {
        'task': 'auth_module.tasks.cleanup_expired_recovery_attempts',
        'schedule': crontab(hour='3', minute='0'),  # 3 AM daily
    },
    # Verify backup integrity (monthly)
    'verify-backup-integrity': {
        'task': 'auth_module.tasks.verify_all_backup_integrity',
        'schedule': crontab(day_of_month='1', hour='4', minute='0'),
    },
    # Generate recovery metrics report
    'generate-recovery-metrics': {
        'task': 'auth_module.tasks.generate_recovery_metrics_report',
        'schedule': crontab(hour='6', minute='0'),  # 6 AM daily
    },
}
```

Start Celery workers:

```bash
# Worker for recovery tasks
celery -A password_manager worker -l info -Q recovery -c 2

# Beat scheduler
celery -A password_manager beat -l info
```

### 4. Nginx Configuration

```nginx
server {
    listen 443 ssl http2;
    server_name yourdomain.com;

    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;

    # Security headers
    add_header X-Frame-Options DENY;
    add_header X-Content-Type-Options nosniff;
    add_header X-XSS-Protection "1; mode=block";
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains; preload";

    # Rate limiting for recovery endpoints
    location /api/auth/passkey-recovery/ {
        limit_req zone=recovery burst=5 nodelay;
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}

# Rate limit zone
limit_req_zone $binary_remote_addr zone=recovery:10m rate=5r/m;
```

### 5. Gunicorn Configuration

```python
# gunicorn.conf.py
bind = "127.0.0.1:8000"
workers = 4
worker_class = "gthread"
threads = 2
timeout = 120
max_requests = 1000
max_requests_jitter = 50
preload_app = True

# Logging
accesslog = "/var/log/gunicorn/access.log"
errorlog = "/var/log/gunicorn/error.log"
loglevel = "info"
```

Start Gunicorn:

```bash
gunicorn password_manager.wsgi:application -c gunicorn.conf.py
```

---

## Monitoring Setup

### 1. Health Check Endpoint

Add to `urls.py`:

```python
from auth_module.recovery_monitoring import health_checker, get_recovery_dashboard_data

@api_view(['GET'])
@permission_classes([IsAdminUser])
def recovery_health_check(request):
    return Response(health_checker.check_health())

@api_view(['GET'])
@permission_classes([IsAdminUser])
def recovery_dashboard(request):
    return Response(get_recovery_dashboard_data())
```

### 2. Sentry Integration

```python
# settings.py
import sentry_sdk
from sentry_sdk.integrations.django import DjangoIntegration
from sentry_sdk.integrations.celery import CeleryIntegration

sentry_sdk.init(
    dsn=os.environ.get('SENTRY_DSN'),
    integrations=[DjangoIntegration(), CeleryIntegration()],
    traces_sample_rate=0.1,
    profiles_sample_rate=0.1,
    environment=os.environ.get('ENVIRONMENT', 'production'),
)
```

### 3. Prometheus Metrics

```python
# Add to your monitoring setup
from prometheus_client import Counter, Histogram

recovery_attempts_total = Counter(
    'recovery_attempts_total',
    'Total recovery attempts',
    ['type', 'status']
)

recovery_duration_seconds = Histogram(
    'recovery_duration_seconds',
    'Recovery operation duration',
    ['type']
)
```

### 4. Alert Configuration

```yaml
# prometheus/alerts.yml
groups:
  - name: recovery-alerts
    rules:
      - alert: HighRecoveryFailureRate
        expr: |
          sum(rate(recovery_attempts_total{status="failed"}[1h])) /
          sum(rate(recovery_attempts_total[1h])) > 0.2
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: High recovery failure rate detected
          
      - alert: RecoveryServiceUnhealthy
        expr: recovery_health_status != 1
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: Recovery service health check failing
```

---

## Troubleshooting

### Common Issues

#### 1. "No post-quantum cryptography library available"

**Solution:** Install liboqs-python or pqcrypto:
```bash
pip install liboqs-python  # or pip install pqcrypto
```

#### 2. "Recovery key verification failed"

**Possible causes:**
- Key was modified (check for spaces, case sensitivity)
- Key hash mismatch due to database migration
- Using wrong key format

**Debug:**
```python
from auth_module.services.passkey_primary_recovery_service import PasskeyPrimaryRecoveryService

service = PasskeyPrimaryRecoveryService()
hash1 = service.hash_recovery_key(user_provided_key)
print(f"Computed hash: {hash1}")
print(f"Stored hash: {backup.recovery_key_hash}")
```

#### 3. "Decryption failed: Invalid authentication tag"

**Possible causes:**
- Corrupted encrypted data
- Wrong recovery key
- Tampered data

**Solution:** User needs to use fallback to social mesh recovery.

#### 4. "Rate limit exceeded"

**Solution:** Wait for lockout to expire or contact administrator.

**Admin override:**
```python
from django.core.cache import cache

# Clear rate limit for specific IP
ip_hash = hashlib.sha256('user_ip'.encode()).hexdigest()[:16]
cache.delete(f'progressive_lockout_{ip_hash}')
```

### Log Locations

- Django logs: `/var/log/password_manager/django.log`
- Security logs: `/var/log/password_manager/security.log`
- Celery logs: `/var/log/celery/worker.log`
- Gunicorn logs: `/var/log/gunicorn/error.log`

### Support

For issues, check:
1. Django logs for error details
2. Sentry for exception tracking
3. Prometheus metrics for trends
4. Health check endpoint for system status

---

## Quick Reference

### Management Commands

```bash
# Test recovery system
python manage.py test_passkey_recovery --test all

# Create superuser
python manage.py createsuperuser

# Generate migrations
python manage.py makemigrations auth_module

# Apply migrations
python manage.py migrate
```

### API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/auth/passkey-recovery/setup/` | POST | Set up recovery backup |
| `/api/auth/passkey-recovery/backups/` | GET | List recovery backups |
| `/api/auth/passkey-recovery/initiate/` | POST | Start recovery process |
| `/api/auth/passkey-recovery/complete/` | POST | Complete with recovery key |
| `/api/auth/passkey-recovery/fallback/` | POST | Fallback to social mesh |
| `/api/auth/passkey-recovery/status/` | GET | Get recovery status |

### Environment Variables Quick Reference

| Variable | Description | Default |
|----------|-------------|---------|
| `QUANTUM_CRYPTO_ENABLED` | Enable PQC | `True` |
| `RECOVERY_THROTTLE_RATE` | Rate limit | `3/hour` |
| `SECURITY_ALERT_EMAIL` | Alert recipient | - |
| `REDIS_URL` | Redis connection | `redis://localhost:6379` |


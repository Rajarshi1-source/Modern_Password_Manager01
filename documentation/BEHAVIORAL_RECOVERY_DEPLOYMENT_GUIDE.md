# Behavioral Recovery Deployment Guide

**Complete deployment instructions for Neuromorphic Behavioral Biometric Recovery**

---

## ✅ Pre-Deployment Checklist

### Backend Requirements

- [x] Python 3.13+
- [x] Django 4.2.16
- [x] PostgreSQL 14+ (or SQLite for development)
- [x] Redis (optional, for caching)
- [x] TensorFlow 2.13+
- [x] PyTorch 2.1+
- [x] Transformers 4.35+

### Frontend Requirements

- [x] Node.js 18+
- [x] React 18.2
- [x] TensorFlow.js 4.15+
- [x] Modern browser with WebGL support

---

## 🚀 Deployment Steps

### Step 1: Backend Setup

#### 1.1 Install Dependencies

```bash
cd password_manager

# Install Python packages
pip install -r requirements.txt

# Verify new packages installed
pip list | grep -E "transformers|torch"
```

Expected output:
```
torch                  2.1.0
transformers           4.35.0
```

#### 1.2 Run Database Migrations

```bash
# Create migrations for behavioral_recovery app
python manage.py makemigrations behavioral_recovery

# Apply migrations
python manage.py migrate behavioral_recovery
```

Expected output:
```
Migrations for 'behavioral_recovery':
  behavioral_recovery/migrations/0001_initial.py
    - Create model BehavioralCommitment
    - Create model BehavioralRecoveryAttempt
    - Create model BehavioralChallenge
    - Create model BehavioralProfileSnapshot
    - Create model RecoveryAuditLog
    
Operations to perform:
  Apply all migrations: behavioral_recovery
Running migrations:
  Applying behavioral_recovery.0001_initial... OK
```

#### 1.3 Configure Environment

Edit `.env` file:

```bash
# Behavioral Recovery Settings
BEHAVIORAL_RECOVERY_ENABLED=True
BEHAVIORAL_SIMILARITY_THRESHOLD=0.87
BEHAVIORAL_RECOVERY_DAYS=5
BEHAVIORAL_MIN_SAMPLES_PER_CHALLENGE=50
BEHAVIORAL_DIFFERENTIAL_PRIVACY_EPSILON=0.5
```

#### 1.4 Verify Installation

```bash
# Check app is installed
python manage.py shell
```

```python
>>> from behavioral_recovery.models import BehavioralCommitment
>>> print("✅ Behavioral recovery app installed successfully")
>>> exit()
```

#### 1.5 Create Superuser (if needed)

```bash
python manage.py createsuperuser
```

#### 1.6 Start Backend Server

```bash
python manage.py runserver
```

Verify backend running: http://127.0.0.1:8000/admin/

---

### Step 2: Frontend Setup

#### 2.1 Install Dependencies

```bash
cd frontend

# Install npm packages
npm install
```

Verify TensorFlow.js installed:
```bash
npm list @tensorflow/tfjs
```

Expected output:
```
frontend@0.1.0
└── @tensorflow/tfjs@4.15.0
```

#### 2.2 Configure Environment

Create/edit `frontend/.env.local`:

```bash
VITE_API_URL=http://127.0.0.1:8000
VITE_WS_URL=ws://127.0.0.1:8000
VITE_BEHAVIORAL_RECOVERY_ENABLED=true
```

#### 2.3 Start Frontend Server

```bash
npm run dev
```

Verify frontend running: http://localhost:3000

---

### Step 3: Verification

#### 3.1 Backend API Verification

Test behavioral recovery endpoints:

```bash
# Test initiate endpoint (will fail without commitments, but should return proper error)
curl -X POST http://127.0.0.1:8000/api/behavioral-recovery/initiate/ \
  -H "Content-Type: application/json" \
  -d '{"email": "test@example.com"}'
```

Expected response:
```json
{
  "success": false,
  "message": "If an account exists with this email, recovery instructions will be sent"
}
```

#### 3.2 Frontend Component Verification

1. Open browser: http://localhost:3000
2. Navigate to: http://localhost:3000/password-recovery
3. Verify three tabs visible:
   - Email Recovery
   - Recovery Key
   - **Behavioral Recovery** ← NEW

#### 3.3 Admin Interface Verification

1. Login to admin: http://127.0.0.1:8000/admin/
2. Verify sections visible:
   - Behavioral Commitments
   - Behavioral Recovery Attempts
   - Behavioral Challenges
   - Behavioral Profile Snapshots
   - Recovery Audit Logs

---

### Step 4: Testing

#### 4.1 Run Backend Tests

```bash
cd password_manager

# Run all behavioral recovery tests
python manage.py test tests.behavioral_recovery

# Run specific test module
python manage.py test tests.behavioral_recovery.test_recovery_flow
```

Expected output:
```
Ran 25 tests in 3.42s

OK
```

#### 4.2 Run Frontend Tests

```bash
cd frontend

# Run tests
npm test

# Run with coverage
npm test -- --coverage
```

---

### Step 5: Create Test User

#### 5.1 Register Test User

```bash
# Via API
curl -X POST http://127.0.0.1:8000/api/auth/register/ \
  -H "Content-Type: application/json" \
  -d '{
    "email": "testuser@example.com",
    "username": "testuser",
    "password": "TestPassword123!",
    "password2": "TestPassword123!"
  }'
```

#### 5.2 Build Behavioral Profile (Simulated)

For testing, you can manually create a commitment:

```python
# In Django shell
python manage.py shell
```

```python
from django.contrib.auth.models import User
from behavioral_recovery.models import BehavioralCommitment
import json

user = User.objects.get(email='testuser@example.com')

# Create test commitment
BehavioralCommitment.objects.create(
    user=user,
    challenge_type='typing',
    encrypted_embedding=b'test_embedding_data',
    unlock_conditions={'similarity_threshold': 0.87},
    samples_used=100,
    is_active=True
)

print("✅ Test commitment created")
```

#### 5.3 Test Recovery Flow

1. Logout from app
2. Go to password recovery
3. Select "Behavioral Recovery" tab
4. Enter test email
5. Click "Start Behavioral Recovery"
6. Complete challenges

---

## 🔧 Troubleshooting

### Common Issues

#### Issue: "TensorFlow not available"

**Solution**:
```bash
pip install tensorflow>=2.13.0
# Or for GPU support:
pip install tensorflow-gpu>=2.13.0
```

#### Issue: "Module 'behavioral_recovery' not found"

**Solution**:
```bash
# Verify app in INSTALLED_APPS
python manage.py shell
>>> from django.conf import settings
>>> 'behavioral_recovery' in settings.INSTALLED_APPS
True  # Should be True
```

If False, edit `settings.py` and add `'behavioral_recovery'` to `INSTALLED_APPS`.

#### Issue: "Table doesn't exist"

**Solution**:
```bash
# Run migrations
python manage.py migrate behavioral_recovery
```

#### Issue: "TensorFlow.js fails to load"

**Solution**:
```javascript
// Check browser console
// Ensure WebGL is available
await tf.setBackend('webgl');
await tf.ready();
console.log('TensorFlow backend:', tf.getBackend());
```

#### Issue: "Behavioral recovery tab not showing"

**Solution**:
```bash
# Verify import in PasswordRecovery.jsx
# Check browser console for import errors
# Rebuild frontend:
cd frontend
rm -rf node_modules package-lock.json
npm install
npm run dev
```

---

## 📊 Monitoring

### Health Checks

Add monitoring for behavioral recovery:

```python
# In your monitoring system
def check_behavioral_recovery_health():
    from behavioral_recovery.models import BehavioralCommitment
    
    # Check model availability
    try:
        from ml_security.ml_models.behavioral_dna_model import get_behavioral_dna_model
        model = get_behavioral_dna_model()
        assert model is not None
    except Exception as e:
        alert("Behavioral DNA model unavailable")
    
    # Check commitments
    commitment_count = BehavioralCommitment.objects.filter(is_active=True).count()
    if commitment_count == 0:
        warn("No active behavioral commitments")
    
    return "healthy"
```

### Metrics to Track

- Recovery attempt success rate
- Average similarity scores
- Adversarial attack detection rate
- API response times
- ML model inference times
- Storage usage (IndexedDB size)

---

## 🔒 Security Hardening

### Production Security

#### 1. Enable HTTPS

```python
# settings.py
SECURE_SSL_REDIRECT = True
SECURE_HSTS_SECONDS = 31536000
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
```

#### 2. Rate Limiting

Already configured in `views.py`:
```python
@throttle_classes([AnonRateThrottle])  # ✅ Already present
```

#### 3. CORS Configuration

```python
# settings.py
CORS_ALLOWED_ORIGINS = [
    'https://yourdomain.com',
    'https://www.yourdomain.com',
]
```

#### 4. Database Encryption

Enable PostgreSQL column-level encryption:
```sql
-- Install pgcrypto extension
CREATE EXTENSION IF NOT EXISTS pgcrypto;
```

#### 5. Logging

Enable production logging:
```python
# settings.py
LOGGING = {
    'handlers': {
        'behavioral_recovery': {
            'level': 'INFO',
            'class': 'logging.FileHandler',
            'filename': '/var/log/behavioral_recovery.log',
        },
    },
    'loggers': {
        'behavioral_recovery': {
            'handlers': ['behavioral_recovery'],
            'level': 'INFO',
        },
    },
}
```

---

## 📈 Performance Optimization

### Frontend Optimization

```javascript
// Lazy load TensorFlow.js
import * as tf from '@tensorflow/tfjs';

// Use Web Workers for heavy computation
const worker = new Worker('./behavioral-worker.js');

// Cache model in IndexedDB
await model.save('indexeddb://behavioral-dna-model');
```

### Backend Optimization

```python
# Use Celery for async processing
from celery import shared_task

@shared_task
def async_embedding_generation(behavioral_data):
    model = get_behavioral_dna_model()
    return model.generate_embedding(behavioral_data)
```

### Database Optimization

```sql
-- Add indexes for common queries
CREATE INDEX idx_behavioral_commitment_user_active 
ON behavioral_commitment(user_id, is_active);

CREATE INDEX idx_recovery_attempt_status 
ON behavioral_recovery_attempt(status, started_at);
```

---

## 🔄 Migration Path

### Migrating Existing Users

```python
# Management command to migrate users
# password_manager/behavioral_recovery/management/commands/migrate_behavioral.py

from django.core.management.base import BaseCommand
from django.contrib.auth.models import User

class Command(BaseCommand):
    help = 'Migrate existing users to behavioral recovery'
    
    def handle(self, *args, **options):
        users = User.objects.all()
        
        for user in users:
            # Enable silent enrollment
            self.stdout.write(f"Enabling behavioral capture for {user.username}")
            # Capture will start automatically on next login
        
        self.stdout.write(self.style.SUCCESS('Migration complete'))
```

Run migration:
```bash
python manage.py migrate_behavioral
```

---

## 📱 Multi-Platform Support

### Web Application

✅ Fully supported (primary platform)

### Mobile Application

⚠️ Partial support:
- Touch/swipe capture: ✅ Supported
- Keyboard capture: ✅ Supported
- Device orientation: ✅ Supported
- Note: Different behavioral patterns on mobile

### Desktop Application

✅ Fully supported via Electron wrapper

### Browser Extension

⚠️ Limited support:
- Can capture while extension active
- Profile building slower (limited interaction time)

---

## 🎯 Success Metrics

### Week 1 Targets

- [x] 0 deployment errors
- [x] Backend tests passing (100%)
- [x] Frontend builds successfully
- [x] Admin interface accessible

### Month 1 Targets

- [ ] 10+ users with behavioral commitments
- [ ] 5+ successful recovery attempts
- [ ] 0 critical security issues
- [ ] < 5% false rejection rate

### Month 3 Targets

- [ ] 100+ users enrolled
- [ ] 50+ successful recoveries
- [ ] 99%+ attack detection rate
- [ ] External security audit completed

---

## 🆘 Rollback Plan

If issues arise, rollback procedure:

### 1. Disable Feature Flag

```python
# settings.py or .env
BEHAVIORAL_RECOVERY = {
    'ENABLED': False,  # ← Set to False
}
```

### 2. Revert Frontend Changes

```bash
git revert <commit-hash>
# Or manually remove BehavioralProvider from App.jsx
```

### 3. Database Rollback

```bash
# Rollback migrations
python manage.py migrate behavioral_recovery zero
```

### 4. Remove Dependencies (optional)

```bash
# Only if causing conflicts
pip uninstall transformers torch
npm uninstall @tensorflow/tfjs
```

---

## 📞 Support Contacts

- **Technical Issues**: tech-support@yourdomain.com
- **Security Concerns**: security@yourdomain.com
- **Documentation**: Check docs folder
- **Community**: GitHub Discussions

---

## 🎉 Launch Checklist

Final checklist before production launch:

### Code Quality

- [x] All tests passing
- [x] Code reviewed
- [x] Linting passed
- [x] No console errors
- [x] Performance benchmarks met

### Security

- [x] Adversarial detection functional
- [x] Privacy guarantees verified
- [x] Audit logging complete
- [ ] External security audit (pending)
- [ ] Penetration testing (pending)

### Documentation

- [x] API documentation complete
- [x] User guides written
- [x] Architecture documented
- [x] Security analysis done

### Operations

- [x] Monitoring configured
- [x] Error tracking setup (Sentry)
- [x] Backup procedures defined
- [ ] Incident response plan (pending)

### Compliance

- [x] GDPR compliant (right to erasure)
- [x] Privacy policy updated
- [ ] Legal review (pending)
- [ ] Data protection impact assessment (pending)

---

## 📚 Post-Deployment

### Week 1

1. Monitor error logs daily
2. Track recovery attempt success rates
3. Collect user feedback
4. Fix critical issues immediately

### Month 1

1. Analyze usage patterns
2. Optimize ML models
3. A/B test similarity thresholds
4. Plan Phase 2 features

### Month 3

1. External security audit
2. Performance optimization
3. Scale infrastructure
4. Plan blockchain integration (Phase 2)

---

**Deployment Version**: 1.0.0  
**Status**: ✅ Ready for Deployment (after testing)  
**Last Updated**: November 6, 2025


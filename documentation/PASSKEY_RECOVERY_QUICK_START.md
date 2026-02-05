# Passkey Recovery - Quick Start Guide

**⏱️ Setup Time:** 15 minutes  
**🎯 Goal:** Get primary passkey recovery working with fallback to social mesh recovery

---

## 🚀 Quick Setup (3 Steps)

### Step 1: Backend Setup (5 minutes)

```bash
# 1. Install dependencies
pip install cryptography argon2-cffi djangorestframework celery redis

# 2. Run migrations
cd password_manager
python manage.py makemigrations auth_module
python manage.py migrate

# 3. Start Django server
python manage.py runserver
```

### Step 2: Add URLs (2 minutes)

Add to `password_manager/auth_module/urls.py`:

```python
from . import passkey_primary_recovery_views as recovery_views

urlpatterns += [
    # Primary Recovery
    path('passkey-recovery/setup/', recovery_views.setup_primary_passkey_recovery),
    path('passkey-recovery/backups/', recovery_views.list_passkey_recovery_backups),
    path('passkey-recovery/initiate/', recovery_views.initiate_primary_passkey_recovery),
    path('passkey-recovery/complete/', recovery_views.complete_primary_passkey_recovery),
    path('passkey-recovery/fallback/', recovery_views.fallback_to_social_mesh_recovery),
    path('passkey-recovery/backups/<int:backup_id>/revoke/', recovery_views.revoke_recovery_backup),
    path('passkey-recovery/status/', recovery_views.get_recovery_status),
]
```

### Step 3: Frontend Setup (8 minutes)

```bash
# 1. Install dependencies
cd frontend
npm install styled-components qrcode.react react-hot-toast

# 2. Build
npm run build

# 3. Start dev server (optional)
npm run dev
```

✅ **Done!** Navigate to:
- Setup: `/passkey-recovery/setup`
- Recover: `/passkey-recovery/recover`
- Social Mesh: `/recovery/social-mesh`

---

## 🧪 Quick Test

### 1. Setup Recovery Backup

```bash
curl -X POST http://localhost:8000/auth/passkey-recovery/setup/ \
  -H "Authorization: Bearer <YOUR_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "passkey_credential_id": "abc123...",
    "device_name": "Test Device"
  }'
```

**Response:**
```json
{
  "recovery_key": "ABCD-EFGH-IJKL-MNOP-QRST-UVWX",
  "backup_id": 1,
  "message": "Primary passkey recovery set up successfully"
}
```

⚠️ **Save this recovery key!**

### 2. Initiate Recovery

```bash
curl -X POST http://localhost:8000/auth/passkey-recovery/initiate/ \
  -H "Content-Type: application/json" \
  -d '{
    "username_or_email": "user@example.com"
  }'
```

**Response:**
```json
{
  "recovery_attempt_id": 123,
  "user_id": 456,
  "has_backups": true,
  "message": "Active backups found. Please provide your recovery key."
}
```

### 3. Complete Recovery

```bash
curl -X POST http://localhost:8000/auth/passkey-recovery/complete/ \
  -H "Content-Type: application/json" \
  -d '{
    "recovery_attempt_id": 123,
    "recovery_key": "ABCDEFGHIJKLMNOPQRSTUVWX",
    "user_id": 456
  }'
```

**Response:**
```json
{
  "message": "Passkey recovered successfully!",
  "passkey_credential": {
    "credential_id": "abc123...",
    "public_key": "def456...",
    "rp_id": "example.com"
  }
}
```

✅ **Recovery Complete!**

---

## 🔀 Quick Fallback Test

### If Primary Recovery Fails

```bash
curl -X POST http://localhost:8000/auth/passkey-recovery/fallback/ \
  -H "Content-Type: application/json" \
  -d '{
    "primary_recovery_attempt_id": 123,
    "user_id": 456
  }'
```

**Response:**
```json
{
  "message": "Fallback to social mesh recovery initiated",
  "threshold": 3,
  "total_guardians": 5,
  "estimated_time": "3-7 days"
}
```

---

## 🎨 Frontend Usage

### Setup Component

```jsx
import PasskeyPrimaryRecoverySetup from './Components/auth/PasskeyPrimaryRecoverySetup';

<PasskeyPrimaryRecoverySetup
  passkeyCredentialId="abc123..."
  deviceName="My Laptop"
  onComplete={(data) => console.log('Setup complete!', data)}
  onSkip={() => console.log('User skipped setup')}
/>
```

### Recovery Component

```jsx
import PasskeyPrimaryRecoveryInitiate from './Components/auth/PasskeyPrimaryRecoveryInitiate';

<PasskeyPrimaryRecoveryInitiate />
```

---

## ⚙️ Configuration

### Optional: Enhance Security

**1. Add Rate Limiting:**

```python
# settings.py
REST_FRAMEWORK = {
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle'
    ],
    'DEFAULT_THROTTLE_RATES': {
        'anon': '3/hour',  # Max 3 recovery attempts per hour
        'user': '10/day',
    }
}
```

**2. Enable Logging:**

```python
# settings.py
LOGGING = {
    'version': 1,
    'handlers': {
        'file': {
            'class': 'logging.FileHandler',
            'filename': 'recovery.log',
        },
    },
    'loggers': {
        'auth_module.passkey_primary_recovery_views': {
            'handlers': ['file'],
            'level': 'INFO',
        },
    },
}
```

---

## 🐛 Common Issues

### Issue: "Module 'argon2' not found"
```bash
pip install argon2-cffi
```

### Issue: "Table 'passkey_recovery_backup' doesn't exist"
```bash
python manage.py makemigrations auth_module
python manage.py migrate
```

### Issue: "CORS error in frontend"
```python
# settings.py
INSTALLED_APPS += ['corsheaders']
MIDDLEWARE += ['corsheaders.middleware.CorsMiddleware']
CORS_ALLOWED_ORIGINS = ['http://localhost:5173']
```

---

## 📚 Next Steps

1. ✅ **Complete Guide:** See `PASSKEY_RECOVERY_COMPLETE_GUIDE.md`
2. 🔐 **Security Hardening:** Replace simulated Kyber with real PQC library
3. 🧪 **Write Tests:** Add unit and integration tests
4. 📊 **Monitor:** Set up logging and alerting
5. 👥 **Setup Social Mesh:** Configure guardian-based recovery

---

## 🎯 Recovery Flow Summary

```
┌──────────────┐
│ User Setup   │ ──> Recovery Key Generated
└──────┬───────┘     (Save Securely!)
       │
       ▼
┌──────────────┐
│ Passkey Lost │
└──────┬───────┘
       │
       ▼
  Has Recovery Key?
       │
   ┌───┴───┐
  YES      NO
   │       │
   ▼       ▼
PRIMARY  SOCIAL MESH
(Instant) (3-7 days)
   │       │
   └───┬───┘
       │
       ▼
┌──────────────┐
│   SUCCESS    │
└──────────────┘
```

---

**Ready to Deploy?** See the full guide for production setup!

**Questions?** Check the Troubleshooting section in the complete guide.



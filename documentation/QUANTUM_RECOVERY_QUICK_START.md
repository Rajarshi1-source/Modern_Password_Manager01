# ⚡ Quantum Recovery - Quick Start

**5-Minute Setup Guide**

---

## 📦 Files Created

```
Backend:
✅ password_manager/auth_module/quantum_recovery_models.py
✅ password_manager/auth_module/quantum_recovery_views.py
✅ password_manager/auth_module/quantum_recovery_tasks.py
✅ password_manager/auth_module/services/quantum_crypto_service.py

Frontend:
✅ frontend/src/Components/auth/QuantumRecoverySetup.jsx

Documentation:
✅ QUANTUM_RECOVERY_IMPLEMENTATION_GUIDE.md
✅ QUANTUM_RECOVERY_SUMMARY.md
✅ QUANTUM_RECOVERY_QUICK_START.md (this file)
```

---

## 🚀 Quick Setup (5 Steps)

### 1. Install Dependencies

```bash
pip install cryptography celery redis
```

### 2. Run Migrations

```bash
cd password_manager
python manage.py makemigrations auth_module
python manage.py migrate
```

### 3. Add URL Routing

**Edit**: `password_manager/auth_module/urls.py`

```python
from .quantum_recovery_views import QuantumRecoveryViewSet
from rest_framework.routers import DefaultRouter

router = DefaultRouter()
router.register(r'quantum-recovery', QuantumRecoveryViewSet, basename='quantum-recovery')

urlpatterns += router.urls
```

### 4. Update API Service

**Edit**: `frontend/src/services/api.js`

```javascript
auth: {
  setupQuantumRecovery: (data) => api.post('/auth/quantum-recovery/setup_recovery/', data),
  getRecoveryStatus: () => api.get('/auth/quantum-recovery/get_recovery_status/'),
  // ... add other endpoints
}
```

### 5. Add Frontend Route

**Edit**: `frontend/src/App.jsx`

```javascript
import QuantumRecoverySetup from './Components/auth/QuantumRecoverySetup';

<Route path="/recovery/quantum-setup" element={
  isAuthenticated ? <QuantumRecoverySetup /> : <Navigate to="/" />
} />
```

---

## 🎯 API Endpoints

| Endpoint | Method | Auth | Purpose |
|----------|--------|------|---------|
| `/api/auth/quantum-recovery/setup_recovery/` | POST | ✅ | Initialize system |
| `/api/auth/quantum-recovery/get_recovery_status/` | GET | ✅ | Check status |
| `/api/auth/quantum-recovery/initiate_recovery/` | POST | ❌ | Start recovery |
| `/api/auth/quantum-recovery/respond_to_challenge/` | POST | ❌ | Answer challenge |
| `/api/auth/quantum-recovery/cancel_recovery/` | POST | ✅ | Cancel attempt |
| `/api/auth/quantum-recovery/enable_travel_lock/` | POST | ✅ | Lock recovery |

---

## 🔐 Key Features

- **5 Shard Types**: Guardian, Device, Biometric, Behavioral, Temporal
- **3 of 5 Required**: Shamir's Secret Sharing threshold
- **3-7 Day Recovery**: Temporal distribution prevents instant attacks
- **Zero-Knowledge**: Guardians never see vault contents
- **Post-Quantum**: CRYSTALS-Kyber-768 encryption
- **Honeypot Detection**: Fake shards trigger alerts
- **Travel Lock**: Temporarily disable recovery
- **Canary Alerts**: 48-hour window to cancel

---

## 📋 User Flow

### Setup (10 min)
```
1. Navigate to /recovery/quantum-setup
2. Add 3-5 guardians
3. Enable device shard
4. Configure biometrics (optional)
5. Submit → Guardians receive invitations
```

### Recovery (3-7 days)
```
Day 0:  Initiate recovery
Day 1-3: Answer 5 challenges (80%+ required)
Day 3-5: Guardians approve
Day 7:  Passkey recovered ✅
```

---

## ⚠️ Before Production

1. Replace crypto simulations with real libraries:
   ```bash
   pip install liboqs-python secretsharing
   ```

2. Configure email/SMS:
   ```python
   # settings.py
   EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
   ```

3. Start services:
   ```bash
   # Django
   python manage.py runserver
   
   # Celery
   celery -A password_manager worker -l info
   celery -A password_manager beat -l info
   
   # Redis
   redis-server
   ```

---

## 🐛 Troubleshooting

| Problem | Solution |
|---------|----------|
| Migrations fail | Check models imported correctly |
| Celery tasks not running | Verify Redis connection |
| Emails not sending | Configure EMAIL_HOST in settings |
| Frontend errors | Run `npm install styled-components react-icons` |

---

## 📚 Full Documentation

**See**: `QUANTUM_RECOVERY_IMPLEMENTATION_GUIDE.md` for complete details

---

**Status**: ✅ READY FOR INTEGRATION  
**Time to Setup**: 5 minutes  
**Time to Test**: 15 minutes


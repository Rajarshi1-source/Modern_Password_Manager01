# 🚀 ML Dark Web Monitoring - Quick Reference Card

## ⚡ Quick Commands

### Setup (First Time)
```bash
# Install dependencies
pip install -r ml_dark_web/requirements_ml_darkweb.txt

# Run migrations
python manage.py migrate ml_dark_web

# Train models (10 minutes)
python ml_dark_web/training/train_breach_classifier.py
```

### Start Services
```bash
# Terminal 1: Django
python manage.py runserver

# Terminal 2: Celery
celery -A password_manager worker -l info

# Terminal 3: Celery Beat
celery -A password_manager beat -l info
```

---

## 📍 Key Locations

| What | Where |
|------|-------|
| **Main App** | `password_manager/ml_dark_web/` |
| **Models** | `ml_dark_web/models.py` |
| **ML Services** | `ml_dark_web/ml_services.py` |
| **API Views** | `ml_dark_web/views.py` |
| **Celery Tasks** | `ml_dark_web/tasks.py` |
| **Training** | `ml_dark_web/training/train_breach_classifier.py` |
| **Config** | `ml_dark_web/ml_config.py` |
| **Trained Models** | `ml_models/dark_web/` |

---

## 🔗 API Endpoints

### User Endpoints
```
POST /api/ml-darkweb/add_credential_monitoring/
GET  /api/ml-darkweb/monitored_credentials/
GET  /api/ml-darkweb/breach_matches/
POST /api/ml-darkweb/scan_now/
GET  /api/ml-darkweb/statistics/
```

### Admin Endpoints
```
GET  /api/ml-darkweb/admin/sources/
POST /api/ml-darkweb/admin/trigger_scrape/
GET  /api/ml-darkweb/admin/system_statistics/
```

---

## 🎯 Common Tasks

### Add Credentials for Monitoring
```python
from ml_dark_web.tasks import monitor_user_credentials
monitor_user_credentials.delay(user_id, ['email@example.com'])
```

### Trigger Breach Scan
```python
from ml_dark_web.tasks import check_user_against_all_breaches
check_user_against_all_breaches.delay(user_id)
```

### Check Breach Matches
```python
from ml_dark_web.models import MLBreachMatch
matches = MLBreachMatch.objects.filter(user_id=1, resolved=False)
```

---

## 🛠️ Configuration

### Add to `settings.py`
```python
INSTALLED_APPS = [
    # ... existing ...
    'ml_dark_web',
    'channels',
]

CELERY_BROKER_URL = 'redis://localhost:6379/0'
CELERY_RESULT_BACKEND = 'redis://localhost:6379/0'
```

### Add to `urls.py`
```python
urlpatterns = [
    # ... existing ...
    path('api/ml-darkweb/', include('ml_dark_web.urls')),
]
```

---

## 📊 Admin Interface

Access: `http://localhost:8000/admin/ml_dark_web/`

**Key Sections:**
- Breach Sources → Manage scraping sources
- ML Breach Data → View detected breaches
- User Credential Monitoring → Monitor credentials
- ML Breach Matches → View user matches
- ML Model Metadata → Track model versions

---

## 🐛 Troubleshooting

### Models Not Loading?
```bash
# Retrain
python ml_dark_web/training/train_breach_classifier.py
```

### Celery Not Working?
```bash
# Check Redis
redis-cli ping

# Restart Celery
celery -A password_manager worker -l info
```

### Database Issues?
```bash
# Reset migrations (WARNING: loses data)
python manage.py migrate ml_dark_web zero
python manage.py migrate ml_dark_web
```

---

## 📈 Monitoring

### Celery Tasks (Flower)
```bash
celery -A password_manager flower
# Access: http://localhost:5555
```

### System Statistics
```bash
curl http://localhost:8000/api/ml-darkweb/admin/system_statistics/ \
  -H "Authorization: Bearer ADMIN_TOKEN"
```

---

## 🔐 Security Checklist

- [x] All credentials hashed (SHA-256)
- [x] API authentication required
- [x] Rate limiting enabled
- [x] WebSocket channels secured
- [x] Admin endpoints protected
- [ ] HTTPS enabled (production)
- [ ] Redis password set
- [ ] Tor proxy configured

---

## 📚 Documentation

| Document | Purpose |
|----------|---------|
| `ml_dark_web/README.md` | Comprehensive guide |
| `ML_DARKWEB_SETUP_GUIDE.md` | Quick setup |
| `ML_DARKWEB_IMPLEMENTATION_SUMMARY.md` | Implementation details |
| This file | Quick reference |

---

## 🆘 Need Help?

**Check:**
1. Full documentation: `ml_dark_web/README.md`
2. Setup guide: `ML_DARKWEB_SETUP_GUIDE.md`
3. Django admin: `/admin/ml_dark_web/`
4. API docs: `/api/docs/` (if configured)

**Common Issues:**
- Models not found → Retrain
- Celery errors → Check Redis
- API 403 → Check authentication
- Slow performance → Reduce batch size

---

## ✅ Verification Steps

```bash
# 1. Models exist?
ls ml_models/dark_web/breach_classifier/

# 2. Migrations applied?
python manage.py showmigrations ml_dark_web

# 3. Celery working?
celery -A password_manager inspect active

# 4. API accessible?
curl http://localhost:8000/api/ml-darkweb/statistics/
```

---

## 📞 Quick Links

- Admin: `http://localhost:8000/admin/ml_dark_web/`
- API: `http://localhost:8000/api/ml-darkweb/`
- Flower: `http://localhost:5555`
- Docs: See README files

---

**Version:** 1.0.0
**Last Updated:** 2024
**Status:** ✅ Production Ready


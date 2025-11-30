# 🚀 ML Dark Web Monitoring - Quick Setup Guide

This guide will help you set up the ML-powered dark web monitoring feature in your password manager.

---

## 📋 Prerequisites

- Python 3.8+
- PostgreSQL 12+ (with pgvector extension recommended)
- Redis 6.0+
- Tor Browser (for dark web scraping)
- 4GB+ RAM for ML models

---

## ⚡ Quick Setup (5 minutes)

### Step 1: Install Dependencies

```bash
cd password_manager

# Install ML dependencies
pip install -r ml_dark_web/requirements_ml_darkweb.txt

# Install spaCy model
python -m spacy download en_core_web_sm

# Optional: Install pgvector for PostgreSQL
pip install pgvector
```

### Step 2: Update Settings

Add to `password_manager/password_manager/settings.py`:

```python
INSTALLED_APPS = [
    # ... existing apps ...
    'ml_dark_web',           # ML Dark Web Monitoring
    'channels',               # WebSocket support
]

# Celery Configuration
CELERY_BROKER_URL = 'redis://localhost:6379/0'
CELERY_RESULT_BACKEND = 'redis://localhost:6379/0'

# Channels Configuration
CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels_redis.core.RedisChannelLayer',
        'CONFIG': {
            "hosts": [('127.0.0.1', 6379)],
        },
    },
}
```

### Step 3: Update URLs

Add to `password_manager/password_manager/urls.py`:

```python
from django.urls import path, include

urlpatterns = [
    # ... existing patterns ...
    path('api/ml-darkweb/', include('ml_dark_web.urls')),
]
```

### Step 4: Run Migrations

```bash
python manage.py makemigrations ml_dark_web
python manage.py migrate ml_dark_web
```

### Step 5: Train Models (First Time Only)

```bash
# Train BERT classifier (~10 minutes on CPU)
python ml_dark_web/training/train_breach_classifier.py --samples 10000 --epochs 10

# Models saved to: ml_models/dark_web/
```

### Step 6: Start Services

```bash
# Terminal 1: Django
python manage.py runserver

# Terminal 2: Celery Worker
celery -A password_manager worker -l info

# Terminal 3: Celery Beat (Scheduled Tasks)
celery -A password_manager beat -l info
```

---

## 🔧 Configuration

### Celery Beat Schedule

Add to `password_manager/password_manager/settings.py`:

```python
from celery.schedules import crontab

CELERY_BEAT_SCHEDULE = {
    'scrape-dark-web-sources': {
        'task': 'ml_dark_web.tasks.scrape_all_active_sources',
        'schedule': crontab(hour='*/24'),  # Every 24 hours
    },
    'analyze-breach-patterns': {
        'task': 'ml_dark_web.tasks.analyze_breach_patterns',
        'schedule': crontab(hour='0', minute='0'),  # Daily at midnight
    },
    'cleanup-old-data': {
        'task': 'ml_dark_web.tasks.cleanup_old_breach_data',
        'schedule': crontab(day_of_week='sunday', hour='2', minute='0'),  # Weekly
    },
}
```

---

## 🎯 Usage Examples

### Add Credentials for Monitoring

```python
from ml_dark_web.tasks import monitor_user_credentials

# Add credentials for user
user_id = 1
credentials = ['user@example.com', 'another@example.com']
monitor_user_credentials.delay(user_id, credentials)
```

### Trigger Manual Scan

```python
from ml_dark_web.tasks import check_user_against_all_breaches

# Scan user's credentials against all breaches
user_id = 1
check_user_against_all_breaches.delay(user_id)
```

### Check Breach Status

```python
from ml_dark_web.models import MLBreachMatch

# Get user's breach matches
matches = MLBreachMatch.objects.filter(
    user_id=1,
    resolved=False
).select_related('breach')

for match in matches:
    print(f"Breach: {match.breach.title}")
    print(f"Severity: {match.breach.severity}")
    print(f"Confidence: {match.confidence_score}")
```

---

## 📊 Admin Interface

Access admin at: `http://localhost:8000/admin/ml_dark_web/`

### Add a Breach Source

1. Go to **Breach Sources**
2. Click **Add Breach Source**
3. Fill in:
   - Name: "Example Forum"
   - URL: "http://example.onion"
   - Source Type: "forum"
   - Is Active: ✅
4. Save

### Trigger Scraping

1. Go to **Breach Sources**
2. Select sources
3. Actions → **Trigger scraping for selected sources**

### View Statistics

1. Go to **ML Breach Data** for all detected breaches
2. Go to **ML Breach Matches** for user matches
3. Go to **Dark Web Scrape Logs** for scraping history

---

## 🔍 Testing

### Test Breach Classification

```bash
curl -X POST http://localhost:8000/api/ml-darkweb/classify-text/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
    "text": "Massive data breach at TechCorp - 10 million users affected"
  }'
```

Response:
```json
{
  "is_breach": true,
  "severity": "HIGH",
  "confidence": 0.92,
  "probabilities": {
    "LOW": 0.02,
    "MEDIUM": 0.06,
    "HIGH": 0.92,
    "CRITICAL": 0.00
  }
}
```

---

## 🐛 Troubleshooting

### Issue: Models Not Loading

**Solution:**
```bash
# Verify model files exist
ls -la ml_models/dark_web/breach_classifier/

# Retrain if missing
python ml_dark_web/training/train_breach_classifier.py
```

### Issue: Celery Not Connecting

**Solution:**
```bash
# Check Redis is running
redis-cli ping  # Should return PONG

# Start Redis if needed
sudo service redis-server start

# Check Celery worker status
celery -A password_manager inspect active
```

### Issue: Out of Memory During Training

**Solution:**
```python
# Reduce batch size in training script
python ml_dark_web/training/train_breach_classifier.py \
    --samples 5000 \
    --batch-size 8  # Smaller batch
```

### Issue: Slow Inference

**Solution:**
```bash
# Use GPU if available
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu118

# Or optimize model
# Add to ml_dark_web/ml_config.py:
BERT_MAX_LENGTH = 256  # Reduce from 512
```

---

## 📈 Performance Tuning

### For Production

```python
# settings.py

# Use multiple Celery workers
CELERYD_CONCURRENCY = 4

# Enable result caching
CELERY_CACHE_BACKEND = 'django-cache'

# Optimize database queries
DATABASES = {
    'default': {
        # ... existing config ...
        'CONN_MAX_AGE': 600,  # Connection pooling
        'OPTIONS': {
            'MAX_CONNS': 20,
        }
    }
}
```

### Optimize ML Models

```python
# ml_config.py

# Use smaller model
BERT_MODEL_NAME = 'distilbert-base-uncased'  # Already optimized

# Reduce embedding dimensions
SIAMESE_EMBEDDING_DIM = 64  # From 128

# Enable mixed precision (GPU only)
ENABLE_MIXED_PRECISION = True
```

---

## 🔐 Security Checklist

- [ ] All credentials hashed with SHA-256
- [ ] API endpoints protected with authentication
- [ ] Rate limiting enabled
- [ ] HTTPS/TLS enabled in production
- [ ] Tor proxy configured for dark web scraping
- [ ] Redis password protected
- [ ] Database backups encrypted
- [ ] Celery flower dashboard password protected

---

## 📚 Next Steps

1. **Customize Models**: Fine-tune on your specific data
2. **Add Sources**: Configure dark web sources to monitor
3. **Set Alerts**: Configure WebSocket notifications
4. **Monitor Performance**: Use Flower dashboard
5. **Scale**: Add more Celery workers for production

---

## 🆘 Need Help?

- **Documentation**: See `ml_dark_web/README.md`
- **API Docs**: `http://localhost:8000/api/docs/`
- **Celery Monitor**: `http://localhost:5555` (Flower)
- **Admin Panel**: `http://localhost:8000/admin/ml_dark_web/`

---

## ✅ Verification

Run this checklist to verify setup:

```bash
# 1. Check models exist
ls ml_models/dark_web/breach_classifier/

# 2. Test classification
curl http://localhost:8000/api/ml-darkweb/classify-text/ -X POST \
     -H "Content-Type: application/json" \
     -d '{"text": "test breach"}'

# 3. Check Celery
celery -A password_manager inspect active

# 4. Verify database
python manage.py dbshell
# SQL: SELECT COUNT(*) FROM ml_breach_sources;
```

All green? **You're ready to go!** 🎉

---

**⚠️ Important**: This is a security-critical feature. Always:
- Keep models updated
- Monitor false positives
- Comply with data privacy regulations
- Use responsibly and legally


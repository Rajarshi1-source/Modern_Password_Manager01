# 🚀 Deployment Quick Reference Card

## **Recommended Strategy: Separated Deployment (Decoupled Frontend & Backend)**

### Why This Strategy?
- ✅ **Best Performance**: Frontend on CDN (Vercel/Netlify)
- ✅ **Best Cost**: $45-120/month (vs $205-520 for containers)
- ✅ **Fast Deployments**: Frontend in 2-5 min, Backend in 10-15 min
- ✅ **Easy Scaling**: Independent scaling of services
- ✅ **Modern DevOps**: Git-based deployments

---

## 📦 Component Deployment Map

| Component | Platform | Port | Cost |
|-----------|----------|------|------|
| **Frontend** | Vercel/Netlify | 443 (HTTPS) | $0-20/month |
| **Backend API** | DigitalOcean/AWS | 8000 | $20-50/month |
| **WebSockets** | Same as Backend | 8001 | Included |
| **PostgreSQL** | Managed DB | 5432 | $15-30/month |
| **Redis** | Managed Redis | 6379 | $10-20/month |
| **Celery Workers** | Same as Backend | N/A | Included |
| **Total** | | | **$45-120/month** |

---

## 🔧 Configuration Checklist

### Backend (Django)
- [ ] Update `DATABASES` to use PostgreSQL
- [ ] Configure `CACHES` with Redis
- [ ] Add Celery configuration
- [ ] Configure Django Channels (ASGI)
- [ ] Set up CORS for frontend domain
- [ ] Update cookie settings for cross-origin
- [ ] Add frontend domain to `CSRF_TRUSTED_ORIGINS`
- [ ] Create `.env` file with secrets
- [ ] Update `ALLOWED_HOSTS`

### Frontend (React)
- [ ] Create `.env.production` with API URL
- [ ] Update API service to use `withCredentials: true`
- [ ] Create `vercel.json` configuration
- [ ] Test CORS locally
- [ ] Test WebSocket connection
- [ ] Update all API calls to use environment variable

### Infrastructure
- [ ] Set up PostgreSQL database
- [ ] Set up Redis instance
- [ ] Configure Nginx reverse proxy
- [ ] Set up SSL certificates (Let's Encrypt)
- [ ] Configure Supervisor for Celery workers
- [ ] Set up Daphne for WebSockets

---

## 🌐 URLs Structure

```
Frontend:
  https://yourapp.com                    → React App (Vercel)
  https://www.yourapp.com                → React App (Vercel)

Backend:
  https://api.yourapp.com/api/           → REST API
  https://api.yourapp.com/admin/         → Django Admin
  wss://api.yourapp.com/ws/              → WebSockets
```

---

## ⚡ Quick Deployment Commands

### Backend Deployment
```bash
# 1. SSH into server
ssh user@api.yourapp.com

# 2. Pull latest code
cd /opt/password_manager
git pull origin main

# 3. Activate virtual environment
source venv/bin/activate

# 4. Install dependencies
pip install -r password_manager/requirements.txt

# 5. Run migrations
cd password_manager
python manage.py migrate

# 6. Collect static files
python manage.py collectstatic --noinput

# 7. Restart services
sudo supervisorctl restart all
```

### Frontend Deployment
```bash
# 1. Navigate to frontend
cd frontend

# 2. Deploy to Vercel
vercel --prod

# OR for Netlify
netlify deploy --prod --dir=dist
```

---

## 🔒 Environment Variables

### Backend `.env`
```bash
# Core
SECRET_KEY=your-secret-key-here
DEBUG=False
ALLOWED_HOSTS=api.yourapp.com

# Database
DB_NAME=password_manager
DB_USER=pm_user
DB_PASSWORD=your-db-password
DB_HOST=localhost
DB_PORT=5432

# Redis
REDIS_URL=redis://localhost:6379/0
REDIS_PASSWORD=your-redis-password

# Celery
CELERY_BROKER_URL=redis://localhost:6379/1
CELERY_RESULT_BACKEND=redis://localhost:6379/2

# CORS
CORS_ALLOWED_ORIGINS=https://yourapp.com,https://www.yourapp.com
CSRF_TRUSTED_ORIGINS=https://yourapp.com,https://www.yourapp.com

# Security
SECURE_SSL_REDIRECT=True
SESSION_COOKIE_SECURE=True
CSRF_COOKIE_SECURE=True
```

### Frontend `.env.production`
```bash
VITE_API_BASE_URL=https://api.yourapp.com
VITE_WS_URL=wss://api.yourapp.com
```

---

## 🔍 Health Check Endpoints

Create a health check endpoint in Django:

```python
# password_manager/api/views.py

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from django.db import connection
from django.core.cache import cache
import redis

@api_view(['GET'])
@permission_classes([AllowAny])
def health_check(request):
    """
    Health check endpoint for monitoring
    """
    status = {
        'status': 'healthy',
        'database': 'unknown',
        'cache': 'unknown',
        'redis': 'unknown',
    }
    
    # Check database
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        status['database'] = 'healthy'
    except Exception as e:
        status['database'] = 'unhealthy'
        status['status'] = 'unhealthy'
    
    # Check cache
    try:
        cache.set('health_check', 'ok', 10)
        if cache.get('health_check') == 'ok':
            status['cache'] = 'healthy'
    except Exception as e:
        status['cache'] = 'unhealthy'
        status['status'] = 'unhealthy'
    
    return Response(status)
```

**Test Health Check**:
```bash
curl https://api.yourapp.com/api/health/
```

---

## 📊 Monitoring Setup

### 1. Sentry (Error Tracking)
```bash
pip install sentry-sdk
```

```python
# settings.py
import sentry_sdk
from sentry_sdk.integrations.django import DjangoIntegration

if not DEBUG:
    sentry_sdk.init(
        dsn="your-sentry-dsn",
        integrations=[DjangoIntegration()],
        traces_sample_rate=0.1,
        send_default_pii=False,
    )
```

### 2. UptimeRobot (Uptime Monitoring)
- Monitor: `https://api.yourapp.com/api/health/`
- Monitor: `https://yourapp.com`
- Alert: Email/Slack when down

### 3. Logging
```python
# settings.py
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'file': {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': '/var/log/password_manager/django.log',
            'maxBytes': 1024 * 1024 * 15,  # 15MB
            'backupCount': 10,
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['file'],
        'level': 'INFO',
    },
}
```

---

## 🔄 CI/CD Pipeline (GitHub Actions)

### Backend CI/CD
```yaml
# .github/workflows/backend.yml
name: Backend Deploy

on:
  push:
    branches: [main]
    paths:
      - 'password_manager/**'

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Deploy to server
        uses: appleboy/ssh-action@master
        with:
          host: ${{ secrets.SERVER_HOST }}
          username: ${{ secrets.SERVER_USER }}
          key: ${{ secrets.SSH_PRIVATE_KEY }}
          script: |
            cd /opt/password_manager
            git pull origin main
            source venv/bin/activate
            pip install -r password_manager/requirements.txt
            cd password_manager
            python manage.py migrate
            python manage.py collectstatic --noinput
            sudo supervisorctl restart all
```

### Frontend CI/CD
```yaml
# .github/workflows/frontend.yml
name: Frontend Deploy

on:
  push:
    branches: [main]
    paths:
      - 'frontend/**'

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Setup Node.js
        uses: actions/setup-node@v3
        with:
          node-version: '20'
      
      - name: Install dependencies
        run: |
          cd frontend
          npm ci
      
      - name: Build
        run: |
          cd frontend
          npm run build
        env:
          VITE_API_BASE_URL: ${{ secrets.API_URL }}
          VITE_WS_URL: ${{ secrets.WS_URL }}
      
      - name: Deploy to Vercel
        uses: amondnet/vercel-action@v20
        with:
          vercel-token: ${{ secrets.VERCEL_TOKEN }}
          vercel-org-id: ${{ secrets.VERCEL_ORG_ID }}
          vercel-project-id: ${{ secrets.VERCEL_PROJECT_ID }}
          working-directory: frontend
```

---

## 🐛 Common Issues & Solutions

### Issue 1: CORS Errors
**Symptom**: "No 'Access-Control-Allow-Origin' header is present"

**Solution**:
```python
# settings.py
CORS_ALLOWED_ORIGINS = [
    'https://yourapp.vercel.app',  # Add Vercel preview URLs
    'https://yourapp.com',
]
CORS_ALLOW_CREDENTIALS = True
```

### Issue 2: WebSocket Connection Failed
**Symptom**: WebSocket connection fails or closes immediately

**Solution**:
1. Check Nginx WebSocket configuration
2. Verify Daphne is running
3. Check firewall rules for port 8001

```nginx
# /etc/nginx/sites-available/password_manager
location /ws/ {
    proxy_pass http://127.0.0.1:8001;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
}
```

### Issue 3: Cookie Not Being Set
**Symptom**: CSRF token or session cookie not received

**Solution**:
```python
# settings.py
SESSION_COOKIE_SAMESITE = 'None'
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SAMESITE = 'None'
CSRF_COOKIE_SECURE = True
```

### Issue 4: Static Files Not Loading
**Symptom**: CSS/JS files return 404

**Solution**:
```bash
# Collect static files
python manage.py collectstatic --noinput

# Check Nginx configuration
sudo nginx -t
sudo systemctl reload nginx
```

### Issue 5: Celery Tasks Not Running
**Symptom**: Background tasks queue up but don't execute

**Solution**:
```bash
# Check Celery worker status
sudo supervisorctl status celery_worker

# Restart Celery
sudo supervisorctl restart celery_worker

# Check logs
tail -f /var/log/celery/worker.log
```

---

## 📈 Performance Optimization

### 1. Enable Django Cache
```python
# settings.py
CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': 'redis://127.0.0.1:6379/0',
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
        }
    }
}

# Cache API responses
from django.views.decorators.cache import cache_page

@cache_page(60 * 15)  # Cache for 15 minutes
def my_api_view(request):
    # ...
```

### 2. Database Connection Pooling
```python
# settings.py
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.environ.get('DB_NAME'),
        'USER': os.environ.get('DB_USER'),
        'PASSWORD': os.environ.get('DB_PASSWORD'),
        'HOST': os.environ.get('DB_HOST'),
        'PORT': os.environ.get('DB_PORT'),
        'CONN_MAX_AGE': 600,  # Connection pooling
        'OPTIONS': {
            'connect_timeout': 10,
        },
    }
}
```

### 3. Gunicorn Workers
```bash
# /etc/supervisor/conf.d/gunicorn.conf
[program:gunicorn]
command=/opt/venv/bin/gunicorn password_manager.wsgi:application \
    --bind 127.0.0.1:8000 \
    --workers 4 \
    --threads 2 \
    --worker-class sync \
    --worker-connections 1000 \
    --max-requests 1000 \
    --max-requests-jitter 50 \
    --timeout 120 \
    --graceful-timeout 30 \
    --keep-alive 5
```

### 4. Nginx Caching
```nginx
# /etc/nginx/sites-available/password_manager

# Cache zone
proxy_cache_path /var/cache/nginx levels=1:2 keys_zone=api_cache:10m max_size=1g inactive=60m;

location /api/ {
    proxy_cache api_cache;
    proxy_cache_valid 200 15m;
    proxy_cache_methods GET HEAD;
    proxy_cache_key "$scheme$request_method$host$request_uri";
    add_header X-Cache-Status $upstream_cache_status;
    
    proxy_pass http://127.0.0.1:8000;
}
```

---

## 🎯 Production Checklist

### Before Going Live
- [ ] SSL certificates installed and working
- [ ] CORS configured correctly
- [ ] All environment variables set
- [ ] Database backups configured
- [ ] Redis persistence enabled
- [ ] Monitoring set up (Sentry, UptimeRobot)
- [ ] Logging configured
- [ ] Firewall rules configured
- [ ] Rate limiting enabled
- [ ] Health check endpoint working
- [ ] CI/CD pipeline tested
- [ ] Load testing completed
- [ ] Security audit performed
- [ ] Documentation updated

### Day 1 After Launch
- [ ] Monitor error rates (Sentry)
- [ ] Check server resources (CPU, RAM, Disk)
- [ ] Verify backups are working
- [ ] Test all critical user flows
- [ ] Monitor API response times
- [ ] Check Celery task queue
- [ ] Verify WebSocket connections

### Week 1 After Launch
- [ ] Analyze user behavior
- [ ] Review server logs
- [ ] Optimize slow queries
- [ ] Adjust worker counts if needed
- [ ] Review and fix any bugs
- [ ] Update documentation based on issues

---

## 🆘 Emergency Contacts

### Service Status Pages
- Vercel: https://www.vercel-status.com/
- DigitalOcean: https://status.digitalocean.com/
- AWS: https://health.aws.amazon.com/health/status

### Quick Rollback
```bash
# Backend
git revert HEAD
git push origin main

# Frontend (Vercel)
vercel rollback
```

---

## 📚 Helpful Resources

- **Django Deployment**: https://docs.djangoproject.com/en/4.2/howto/deployment/
- **Vercel Docs**: https://vercel.com/docs
- **Nginx Config**: https://nginx.org/en/docs/
- **Let's Encrypt**: https://letsencrypt.org/docs/
- **Supervisor**: http://supervisord.org/
- **Celery**: https://docs.celeryq.dev/

---

**Last Updated**: 2025-01-25  
**Strategy**: Separated Deployment (Decoupled)  
**Status**: ✅ Recommended for Production


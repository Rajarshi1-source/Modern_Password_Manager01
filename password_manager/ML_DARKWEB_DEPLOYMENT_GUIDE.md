# ML Dark Web Monitoring - Production Deployment Guide 🚀

## 📋 Pre-Deployment Checklist

Before deploying to production, ensure you have:

- [ ] Trained ML models (BERT + Siamese)
- [ ] Redis server (production-ready)
- [ ] PostgreSQL database with pgvector extension
- [ ] Celery workers configured
- [ ] Django Channels with Daphne
- [ ] SSL/TLS certificates for WSS
- [ ] Environment variables configured
- [ ] Monitoring and logging setup
- [ ] Backup strategy in place

---

## 🔧 Infrastructure Requirements

### Minimum Requirements

| Component | Specification |
|-----------|--------------|
| **CPU** | 4 cores (8 recommended) |
| **RAM** | 8GB (16GB recommended) |
| **Storage** | 50GB SSD |
| **GPU** | Optional (speeds up ML inference) |
| **Network** | 100 Mbps |

### Recommended Production Stack

```
┌─────────────────────────────────────────────────────────────┐
│                         Load Balancer                        │
│                    (NGINX / AWS ALB / Cloudflare)           │
└────────────────────┬────────────────────────────────────────┘
                     │
        ┌────────────┴────────────┐
        │                         │
┌───────▼────────┐       ┌───────▼────────┐
│   Django App   │       │   Django App   │
│   (Daphne)     │       │   (Daphne)     │
│   Port 8000    │       │   Port 8001    │
└───────┬────────┘       └───────┬────────┘
        │                         │
        └────────────┬────────────┘
                     │
        ┌────────────┴────────────┐
        │                         │
┌───────▼────────┐       ┌───────▼────────┐
│  Redis Cluster │       │   PostgreSQL   │
│  (Channels)    │       │  + pgvector    │
└────────────────┘       └────────────────┘
        │
┌───────▼────────┐
│ Celery Workers │
│  (Multiple)    │
└────────────────┘
```

---

## 📦 Step 1: Install Dependencies

### System Packages

```bash
# Ubuntu/Debian
sudo apt-get update
sudo apt-get install -y \
    python3.11 \
    python3.11-dev \
    python3-pip \
    redis-server \
    postgresql-15 \
    postgresql-contrib \
    nginx \
    supervisor \
    git \
    build-essential

# Install PostgreSQL pgvector extension
cd /tmp
git clone https://github.com/pgvector/pgvector.git
cd pgvector
make
sudo make install
```

### Python Packages

```bash
pip install -r password_manager/ml_dark_web/requirements_ml_darkweb.txt
pip install gunicorn daphne channels-redis
```

---

## 🗄️ Step 2: Database Setup

### PostgreSQL Configuration

```bash
# Create database
sudo -u postgres psql
```

```sql
-- Create database and user
CREATE DATABASE password_manager_prod;
CREATE USER pm_user WITH PASSWORD 'your_secure_password';

-- Enable pgvector extension
\c password_manager_prod
CREATE EXTENSION vector;

-- Grant permissions
GRANT ALL PRIVILEGES ON DATABASE password_manager_prod TO pm_user;
ALTER DATABASE password_manager_prod OWNER TO pm_user;

\q
```

### Run Migrations

```bash
cd password_manager
python manage.py migrate
python manage.py migrate ml_dark_web
```

---

## 🔴 Step 3: Redis Setup

### Redis Configuration

Edit `/etc/redis/redis.conf`:

```conf
# Bind to localhost and private network
bind 127.0.0.1 10.0.0.5

# Set password
requirepass your_redis_password

# Enable persistence
save 900 1
save 300 10
save 60 10000

# Max memory
maxmemory 2gb
maxmemory-policy allkeys-lru

# Logging
loglevel notice
logfile /var/log/redis/redis-server.log
```

### Start Redis

```bash
sudo systemctl enable redis-server
sudo systemctl start redis-server
sudo systemctl status redis-server
```

---

## ⚙️ Step 4: Django Configuration

### Environment Variables

Create `.env` file:

```bash
# Django
SECRET_KEY=your-secret-key-here
DEBUG=False
ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com

# Database
DB_NAME=password_manager_prod
DB_USER=pm_user
DB_PASSWORD=your_secure_password
DB_HOST=localhost
DB_PORT=5432

# Redis
REDIS_URL=redis://:your_redis_password@localhost:6379/0

# Celery
CELERY_BROKER_URL=redis://:your_redis_password@localhost:6379/1
CELERY_RESULT_BACKEND=redis://:your_redis_password@localhost:6379/2

# Channels
CHANNEL_LAYERS_HOST=localhost
CHANNEL_LAYERS_PASSWORD=your_redis_password

# ML Models
ML_MODELS_PATH=/opt/ml_models/
DEVICE=cuda  # or 'cpu'

# Security
SECURE_SSL_REDIRECT=True
SESSION_COOKIE_SECURE=True
CSRF_COOKIE_SECURE=True
SECURE_HSTS_SECONDS=31536000

# CORS
CORS_ALLOWED_ORIGINS=https://yourdomain.com,https://www.yourdomain.com
```

### Update `settings.py`

```python
import os
from dotenv import load_dotenv

load_dotenv()

# Security
SECRET_KEY = os.environ['SECRET_KEY']
DEBUG = os.environ.get('DEBUG', 'False') == 'True'
ALLOWED_HOSTS = os.environ['ALLOWED_HOSTS'].split(',')

# Database
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.environ['DB_NAME'],
        'USER': os.environ['DB_USER'],
        'PASSWORD': os.environ['DB_PASSWORD'],
        'HOST': os.environ['DB_HOST'],
        'PORT': os.environ['DB_PORT'],
    }
}

# Redis & Celery
CELERY_BROKER_URL = os.environ['CELERY_BROKER_URL']
CELERY_RESULT_BACKEND = os.environ['CELERY_RESULT_BACKEND']

# Channels
CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels_redis.core.RedisChannelLayer',
        'CONFIG': {
            "hosts": [(
                os.environ['CHANNEL_LAYERS_HOST'], 
                6379
            )],
            "password": os.environ.get('CHANNEL_LAYERS_PASSWORD'),
        },
    },
}

# Static files
STATIC_ROOT = '/var/www/password_manager/static/'
MEDIA_ROOT = '/var/www/password_manager/media/'

# Logging
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
    'loggers': {
        'ml_dark_web': {
            'handlers': ['file'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}
```

---

## 🤖 Step 5: ML Models Deployment

### Download/Upload Models

```bash
# Create models directory
sudo mkdir -p /opt/ml_models/dark_web

# Copy models from training
scp -r ml_models/dark_web/* user@server:/opt/ml_models/dark_web/

# Or download from cloud
aws s3 sync s3://your-bucket/ml_models/ /opt/ml_models/

# Set permissions
sudo chown -R www-data:www-data /opt/ml_models/
sudo chmod -R 755 /opt/ml_models/
```

### Verify Models

```bash
python manage.py shell
>>> from ml_dark_web.ml_services import BreachClassifier
>>> classifier = BreachClassifier()
>>> print("Model loaded successfully!")
```

---

## 🌐 Step 6: Daphne Configuration

### Supervisor Configuration

Create `/etc/supervisor/conf.d/daphne.conf`:

```ini
[program:daphne]
command=/opt/venv/bin/daphne -u /run/daphne/daphne.sock password_manager.asgi:application
directory=/opt/password_manager
user=www-data
autostart=true
autorestart=true
redirect_stderr=true
stdout_logfile=/var/log/daphne/daphne.log
environment=DJANGO_SETTINGS_MODULE="password_manager.settings"
```

### Start Daphne

```bash
sudo mkdir -p /run/daphne /var/log/daphne
sudo chown www-data:www-data /run/daphne /var/log/daphne
sudo supervisorctl reread
sudo supervisorctl update
sudo supervisorctl start daphne
```

---

## 🔄 Step 7: Celery Workers

### Supervisor Configuration

Create `/etc/supervisor/conf.d/celery.conf`:

```ini
[program:celery_worker]
command=/opt/venv/bin/celery -A password_manager worker -l info -c 4
directory=/opt/password_manager
user=www-data
autostart=true
autorestart=true
redirect_stderr=true
stdout_logfile=/var/log/celery/worker.log
environment=DJANGO_SETTINGS_MODULE="password_manager.settings"

[program:celery_beat]
command=/opt/venv/bin/celery -A password_manager beat -l info
directory=/opt/password_manager
user=www-data
autostart=true
autorestart=true
redirect_stderr=true
stdout_logfile=/var/log/celery/beat.log
environment=DJANGO_SETTINGS_MODULE="password_manager.settings"
```

### Start Celery

```bash
sudo mkdir -p /var/log/celery
sudo chown www-data:www-data /var/log/celery
sudo supervisorctl reread
sudo supervisorctl update
sudo supervisorctl start celery_worker
sudo supervisorctl start celery_beat
```

---

## 🔒 Step 8: NGINX Configuration

### NGINX Config

Create `/etc/nginx/sites-available/password_manager`:

```nginx
upstream daphne {
    server unix:/run/daphne/daphne.sock;
}

# HTTP -> HTTPS redirect
server {
    listen 80;
    server_name yourdomain.com www.yourdomain.com;
    return 301 https://$server_name$request_uri;
}

# HTTPS server
server {
    listen 443 ssl http2;
    server_name yourdomain.com www.yourdomain.com;

    # SSL certificates
    ssl_certificate /etc/letsencrypt/live/yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/yourdomain.com/privkey.pem;

    # SSL configuration
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;

    # Security headers
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header X-Content-Type-Options nosniff;
    add_header X-Frame-Options DENY;
    add_header X-XSS-Protection "1; mode=block";

    # Static files
    location /static/ {
        alias /var/www/password_manager/static/;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }

    location /media/ {
        alias /var/www/password_manager/media/;
        expires 7d;
    }

    # WebSocket (upgrade connection)
    location /ws/ {
        proxy_pass http://daphne;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 86400;
    }

    # HTTP requests
    location / {
        proxy_pass http://daphne;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### Enable Site

```bash
sudo ln -s /etc/nginx/sites-available/password_manager /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

---

## 📊 Step 9: Monitoring

### Prometheus + Grafana (Optional)

```bash
# Install Prometheus
wget https://github.com/prometheus/prometheus/releases/download/v2.40.0/prometheus-2.40.0.linux-amd64.tar.gz
tar xvf prometheus-2.40.0.linux-amd64.tar.gz
sudo mv prometheus-2.40.0.linux-amd64 /opt/prometheus

# Configure targets in prometheus.yml
# ...

# Install Grafana
sudo apt-get install -y grafana
sudo systemctl enable grafana-server
sudo systemctl start grafana-server
```

### Health Check Endpoint

Add to `urls.py`:

```python
path('health/', views.health_check, name='health_check'),
```

---

## 🧪 Step 10: Testing

### Test WebSocket Connection

```bash
# From server
python manage.py test_breach_alert 1 --severity HIGH

# From client
wscat -c wss://yourdomain.com/ws/breach-alerts/1/?token=YOUR_TOKEN
```

### Test ML Models

```bash
python manage.py shell
>>> from ml_dark_web.tasks import process_scraped_content
>>> process_scraped_content.delay("test content", 1, 1)
```

### Load Testing

```bash
# Using locust
pip install locust

# Create locustfile.py
# Run load test
locust -f locustfile.py --host=https://yourdomain.com
```

---

## 🔄 Step 11: Continuous Deployment

### Git Hooks

Create `deploy.sh`:

```bash
#!/bin/bash
cd /opt/password_manager
git pull origin main
source /opt/venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py collectstatic --noinput
sudo supervisorctl restart daphne celery_worker
```

### GitHub Actions

```yaml
name: Deploy to Production

on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - name: Deploy to server
        uses: appleboy/ssh-action@master
        with:
          host: ${{ secrets.SERVER_HOST }}
          username: ${{ secrets.SERVER_USER }}
          key: ${{ secrets.SSH_PRIVATE_KEY }}
          script: |
            cd /opt/password_manager
            ./deploy.sh
```

---

## 🔐 Security Hardening

### Firewall

```bash
# UFW
sudo ufw allow 22/tcp      # SSH
sudo ufw allow 80/tcp      # HTTP
sudo ufw allow 443/tcp     # HTTPS
sudo ufw enable
```

### Fail2Ban

```bash
sudo apt-get install fail2ban
sudo systemctl enable fail2ban
sudo systemctl start fail2ban
```

### Regular Updates

```bash
# Auto-updates
sudo apt-get install unattended-upgrades
sudo dpkg-reconfigure --priority=low unattended-upgrades
```

---

## 📈 Performance Tuning

### PostgreSQL

```sql
-- Increase shared buffers
shared_buffers = 2GB

-- Increase work memory
work_mem = 64MB

-- Connection pooling
max_connections = 200
```

### Redis

```conf
# Increase max clients
maxclients 10000

# Use pipelining
tcp-backlog 511
```

### Celery

```python
# Increase worker processes
celery -A password_manager worker -c 8

# Use gevent pool for I/O bound tasks
celery -A password_manager worker -P gevent -c 1000
```

---

## ✅ Post-Deployment Checklist

- [ ] All services running (Daphne, Celery, Redis, PostgreSQL)
- [ ] SSL certificates installed and valid
- [ ] WebSocket connections working (WSS)
- [ ] ML models loaded successfully
- [ ] Celery tasks executing
- [ ] Monitoring and logging configured
- [ ] Backups scheduled
- [ ] Health checks passing
- [ ] Load testing completed
- [ ] Security audit performed

---

## 🆘 Troubleshooting

### Service Not Starting

```bash
# Check logs
sudo journalctl -u redis
sudo supervisorctl tail -f daphne
sudo supervisorctl tail -f celery_worker

# Check status
sudo systemctl status redis
sudo supervisorctl status
```

### WebSocket Connection Fails

```bash
# Check NGINX WebSocket config
sudo nginx -t

# Check Daphne logs
sudo tail -f /var/log/daphne/daphne.log

# Test locally
curl -i -N -H "Connection: Upgrade" -H "Upgrade: websocket" http://localhost:8000/ws/breach-alerts/1/
```

### ML Model Errors

```bash
# Check model files exist
ls -lh /opt/ml_models/dark_web/

# Check permissions
stat /opt/ml_models/dark_web/

# Test model loading
python manage.py shell
>>> from ml_dark_web.ml_services import BreachClassifier
>>> BreachClassifier()
```

---

## 📞 Support

For issues, check:
1. Service logs: `/var/log/`
2. Django logs: `/var/log/password_manager/`
3. Supervisor status: `sudo supervisorctl status`
4. System resources: `htop`, `free -h`, `df -h`

---

**Deployment Guide Version**: 1.0.0  
**Last Updated**: 2025-01-24  
**Production Ready**: Yes ✅


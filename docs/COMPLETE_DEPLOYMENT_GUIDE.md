# 🚀 Complete Deployment Guide - Password Manager with ML Dark Web Monitoring

## 📋 Table of Contents

1. [Overview](#overview)
2. [Prerequisites](#prerequisites)
3. [Quick Start (Development)](#quick-start-development)
4. [Production Deployment](#production-deployment)
5. [Docker Deployment](#docker-deployment)
6. [ML Model Training](#ml-model-training)
7. [WebSocket Configuration](#websocket-configuration)
8. [Monitoring & Maintenance](#monitoring--maintenance)
9. [Troubleshooting](#troubleshooting)

---

## Overview

This guide covers the complete deployment of the Password Manager application with ML-powered dark web monitoring, including:

- ✅ Django REST API backend
- ✅ React frontend (Vite)
- ✅ Django Channels WebSocket (real-time alerts)
- ✅ Celery background workers
- ✅ Redis (cache & message broker)
- ✅ PostgreSQL database
- ✅ ML models for breach detection
- ✅ Optional: Scrapy dark web scraping
- ✅ Optional: pgvector similarity search
- ✅ Optional: Blockchain anchoring (Arbitrum Sepolia)

---

## Prerequisites

### System Requirements

- **OS**: Linux, macOS, or Windows 10/11
- **RAM**: 8GB minimum (16GB recommended for ML training)
- **Disk**: 10GB free space
- **Python**: 3.11+
- **Node.js**: 18+
- **PostgreSQL**: 13+
- **Redis**: 6+

### Software Dependencies

```bash
# Ubuntu/Debian
sudo apt-get update
sudo apt-get install -y \
    python3.11 python3-pip python3-venv \
    postgresql postgresql-contrib \
    redis-server \
    nodejs npm \
    git curl wget

# macOS
brew install python@3.11 postgresql redis node git

# Windows
# Install via Chocolatey
choco install python nodejs postgresql redis git
```

---

## Quick Start (Development)

### 1. Clone Repository

```bash
git clone https://github.com/yourusername/password-manager.git
cd password-manager
```

### 2. Setup Backend

```bash
cd password_manager

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Copy environment file
cp env.example .env

# Update .env with your settings
nano .env  # or use any text editor

# Run migrations
python manage.py migrate

# Create superuser
python manage.py createsuperuser

# Collect static files
python manage.py collectstatic --noinput

# Run development server
python manage.py runserver
```

### 3. Setup Frontend

```bash
cd ../frontend

# Install dependencies
npm install

# Copy environment file
cp env.example .env.local

# Update .env.local with API URLs
nano .env.local

# Run development server
npm run dev
```

### 4. Start Redis

```bash
# Linux/macOS
redis-server

# Windows
redis-server.exe
```

### 5. Start Celery Worker

```bash
cd password_manager

# Activate virtual environment
source venv/bin/activate

# Start Celery worker
celery -A password_manager worker -l info

# In another terminal, start Celery Beat
celery -A password_manager beat -l info
```

### 6. Start WebSocket Server

```bash
cd password_manager

# Activate virtual environment
source venv/bin/activate

# Start Daphne ASGI server
daphne -b 0.0.0.0 -p 8001 password_manager.asgi:application
```

### 7. Access Application

- **Frontend**: http://localhost:5173
- **Backend API**: http://localhost:8000/api/
- **Admin Panel**: http://localhost:8000/admin/
- **WebSocket**: ws://localhost:8001/ws/

---

## Production Deployment

### 1. Server Setup

```bash
# Update system
sudo apt-get update && sudo apt-get upgrade -y

# Install system dependencies
sudo apt-get install -y \
    python3.11 python3-pip python3-venv \
    postgresql postgresql-contrib \
    redis-server \
    nginx \
    supervisor \
    git

# Create application user
sudo useradd -m -s /bin/bash pmuser
sudo su - pmuser
```

### 2. Clone and Setup Application

```bash
cd /home/pmuser
git clone https://github.com/yourusername/password-manager.git
cd password-manager

# Setup virtual environment
python3.11 -m venv venv
source venv/bin/activate

# Install Python dependencies
pip install -r password_manager/requirements.txt
pip install gunicorn

# Setup environment
cp password_manager/env.example password_manager/.env
nano password_manager/.env  # Configure production settings
```

### 3. Configure PostgreSQL

```bash
# Create database and user
sudo -u postgres psql << EOF
CREATE DATABASE password_manager;
CREATE USER pm_user WITH PASSWORD 'your-strong-password';
ALTER ROLE pm_user SET client_encoding TO 'utf8';
ALTER ROLE pm_user SET default_transaction_isolation TO 'read committed';
ALTER ROLE pm_user SET timezone TO 'UTC';
GRANT ALL PRIVILEGES ON DATABASE password_manager TO pm_user;
\q
EOF

# Run migrations
cd password_manager
source venv/bin/activate
python manage.py migrate
python manage.py createsuperuser
python manage.py collectstatic --noinput
```

### 4. Configure Nginx

```bash
sudo nano /etc/nginx/sites-available/password-manager
```

```nginx
# Backend API
upstream backend {
    server 127.0.0.1:8000;
}

# WebSocket
upstream websocket {
    server 127.0.0.1:8001;
}

server {
    listen 80;
    server_name your-domain.com;

    client_max_body_size 100M;

    # Frontend (React build)
    location / {
        root /home/pmuser/password-manager/frontend/dist;
        try_files $uri $uri/ /index.html;
    }

    # Backend API
    location /api/ {
        proxy_pass http://backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Django Admin
    location /admin/ {
        proxy_pass http://backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    # Static files
    location /static/ {
        alias /home/pmuser/password-manager/password_manager/staticfiles/;
    }

    # Media files
    location /media/ {
        alias /home/pmuser/password-manager/password_manager/media/;
    }

    # WebSocket
    location /ws/ {
        proxy_pass http://websocket;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

```bash
# Enable site
sudo ln -s /etc/nginx/sites-available/password-manager /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

### 5. Configure Supervisor

```bash
sudo nano /etc/supervisor/conf.d/password-manager.conf
```

```ini
[program:pm_backend]
command=/home/pmuser/password-manager/venv/bin/gunicorn password_manager.wsgi:application --bind 127.0.0.1:8000 --workers 4
directory=/home/pmuser/password-manager/password_manager
user=pmuser
autostart=true
autorestart=true
stderr_logfile=/var/log/pm_backend.err.log
stdout_logfile=/var/log/pm_backend.out.log

[program:pm_websocket]
command=/home/pmuser/password-manager/venv/bin/daphne -b 127.0.0.1 -p 8001 password_manager.asgi:application
directory=/home/pmuser/password-manager/password_manager
user=pmuser
autostart=true
autorestart=true
stderr_logfile=/var/log/pm_websocket.err.log
stdout_logfile=/var/log/pm_websocket.out.log

[program:pm_celery_worker]
command=/home/pmuser/password-manager/venv/bin/celery -A password_manager worker -l info --concurrency=4
directory=/home/pmuser/password-manager/password_manager
user=pmuser
autostart=true
autorestart=true
stderr_logfile=/var/log/pm_celery_worker.err.log
stdout_logfile=/var/log/pm_celery_worker.out.log

[program:pm_celery_beat]
command=/home/pmuser/password-manager/venv/bin/celery -A password_manager beat -l info
directory=/home/pmuser/password-manager/password_manager
user=pmuser
autostart=true
autorestart=true
stderr_logfile=/var/log/pm_celery_beat.err.log
stdout_logfile=/var/log/pm_celery_beat.out.log

[group:password_manager]
programs=pm_backend,pm_websocket,pm_celery_worker,pm_celery_beat
```

```bash
# Reload supervisor
sudo supervisorctl reread
sudo supervisorctl update
sudo supervisorctl start password_manager:*

# Check status
sudo supervisorctl status
```

### 6. SSL Certificate (Let's Encrypt)

```bash
# Install Certbot
sudo apt-get install -y certbot python3-certbot-nginx

# Get certificate
sudo certbot --nginx -d your-domain.com

# Auto-renewal is configured automatically
```

---

## Docker Deployment

### 1. Using Docker Compose

```bash
# Copy environment file
cp .env.docker.example .env

# Update .env with your settings
nano .env

# Build and start services
docker-compose up -d --build

# Check status
docker-compose ps

# View logs
docker-compose logs -f

# Run migrations
docker-compose exec backend python manage.py migrate

# Create superuser
docker-compose exec backend python manage.py createsuperuser
```

### 2. Individual Service Commands

```bash
# Start specific service
docker-compose up -d postgres redis

# Restart services
docker-compose restart backend websocket

# Stop all services
docker-compose down

# Stop and remove volumes
docker-compose down -v
```

### 3. Production Docker Configuration

```bash
# Use production docker-compose file
docker-compose -f docker-compose.prod.yml up -d

# Scale workers
docker-compose -f docker-compose.prod.yml up -d --scale celery_worker=4
```

---

## ML Model Training

### Automated Training (Recommended)

```bash
# Linux/macOS
cd password_manager
chmod +x ../scripts/setup_ml_training.sh
../scripts/setup_ml_training.sh

# Windows
cd password_manager
..\scripts\setup_ml_training.bat
```

### Manual Training

```bash
cd password_manager

# Install ML dependencies
pip install -r ml_dark_web/requirements_ml_darkweb.txt

# Install spaCy model
python -m spacy download en_core_web_sm

# Train BERT classifier
python ml_dark_web/training/train_breach_classifier.py --samples 10000 --epochs 10

# Train all models
python ml_dark_web/training/train_all_models.py --models all --samples 10000 --epochs 10
```

### Verify Training

```bash
# Check model files
ls -lh ml_models/dark_web/breach_classifier/

# Should see:
# - pytorch_model.bin (200-400 MB)
# - config.json
# - tokenizer_config.json
# - vocab.txt

# Test model
python manage.py shell
>>> from ml_dark_web.ml_services import get_breach_classifier
>>> classifier = get_breach_classifier()
>>> result = classifier.classify_breach("Test breach content")
>>> print(result)
```

---

## WebSocket Configuration

### Testing WebSocket Connection

```javascript
// In browser console
const ws = new WebSocket('ws://localhost:8001/ws/breach-alerts/1/?token=YOUR_JWT_TOKEN');

ws.onopen = () => console.log('Connected');
ws.onmessage = (event) => console.log('Message:', JSON.parse(event.data));
ws.onerror = (error) => console.error('Error:', error);
```

### Send Test Alert

```bash
cd password_manager

# Send test breach alert to user
python manage.py test_breach_alert 1 --severity HIGH --confidence 0.95
```

### WebSocket Debugging

```bash
# Check Daphne logs
tail -f /var/log/pm_websocket.out.log

# Check Redis connection
redis-cli ping

# Test channel layer
python manage.py shell
>>> from channels.layers import get_channel_layer
>>> channel_layer = get_channel_layer()
>>> print(channel_layer)
```

---

## Monitoring & Maintenance

### System Monitoring

```bash
# Check service status
sudo supervisorctl status

# View logs
sudo tail -f /var/log/pm_backend.out.log
sudo tail -f /var/log/pm_celery_worker.out.log

# Monitor resources
htop
```

### Database Maintenance

```bash
# Backup database
pg_dump -U pm_user password_manager > backup_$(date +%Y%m%d).sql

# Restore database
psql -U pm_user password_manager < backup_20240101.sql

# Vacuum database
sudo -u postgres psql password_manager -c "VACUUM ANALYZE;"
```

### Redis Maintenance

```bash
# Check Redis status
redis-cli info

# Monitor Redis
redis-cli --stat

# Clear cache
redis-cli FLUSHALL
```

### Log Rotation

```bash
sudo nano /etc/logrotate.d/password-manager
```

```
/var/log/pm_*.log {
    daily
    rotate 14
    compress
    delaycompress
    notifempty
    create 0640 pmuser pmuser
    sharedscripts
    postrotate
        supervisorctl restart password_manager:*
    endscript
}
```

---

## Troubleshooting

### Backend Won't Start

```bash
# Check Python version
python --version

# Check dependencies
pip list

# Check database connection
python manage.py dbshell

# Run with debug
DEBUG=True python manage.py runserver
```

### WebSocket Connection Fails

```bash
# Check Daphne is running
ps aux | grep daphne

# Check Redis connection
redis-cli ping

# Check channel layers
python manage.py shell
>>> from channels.layers import get_channel_layer
>>> channel_layer = get_channel_layer()
>>> print(channel_layer)

# Check firewall
sudo ufw status
sudo ufw allow 8001/tcp
```

### Celery Tasks Not Running

```bash
# Check Celery worker status
celery -A password_manager inspect active

# Check Redis connection
redis-cli ping

# Purge all tasks
celery -A password_manager purge

# Restart workers
sudo supervisorctl restart password_manager:pm_celery_worker
```

### ML Models Not Loading

```bash
# Check model files exist
ls -lh password_manager/ml_models/dark_web/breach_classifier/

# Retrain if needed
cd password_manager
python ml_dark_web/training/train_breach_classifier.py

# Check PyTorch installation
python -c "import torch; print(torch.__version__)"
```

### High Memory Usage

```bash
# Check memory usage
free -h

# Reduce Celery workers
# Edit supervisor config: --concurrency=2

# Restart services
sudo supervisorctl restart password_manager:*
```

---

## Additional Resources

- [Django Documentation](https://docs.djangoproject.com/)
- [Django Channels Documentation](https://channels.readthedocs.io/)
- [Celery Documentation](https://docs.celeryproject.org/)
- [Redis Documentation](https://redis.io/documentation)
- [PostgreSQL Documentation](https://www.postgresql.org/docs/)
- [pgvector Setup Guide](./PGVECTOR_SETUP_GUIDE.md)

---

## Support

For issues or questions:

1. Check [Troubleshooting](#troubleshooting) section
2. Review application logs
3. Check system resources
4. Consult documentation
5. Open GitHub issue

---

**Last Updated**: November 25, 2025  
**Version**: 1.0.0


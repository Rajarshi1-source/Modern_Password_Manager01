# 🚀 Password Manager - Production Deployment Guide

## 📋 Table of Contents

1. [Overview](#overview)
2. [Prerequisites](#prerequisites)
3. [Architecture](#architecture)
4. [Quick Start](#quick-start)
5. [Backend Deployment](#backend-deployment)
6. [Frontend Deployment](#frontend-deployment)
7. [Docker Deployment](#docker-deployment)
8. [Environment Variables](#environment-variables)
9. [Security Checklist](#security-checklist)
10. [Monitoring & Maintenance](#monitoring--maintenance)
11. [Troubleshooting](#troubleshooting)

---

## 🎯 Overview

This guide covers deploying the Password Manager application to production using a **separated deployment strategy** - Backend (Django API) on a VPS/Cloud, Frontend (React) on Vercel/CDN.

### Deployment Strategy

**Backend (Django API):**
- Hosting: DigitalOcean/AWS/GCP/Azure
- Server: Gunicorn (HTTP) + Daphne (WebSockets)
- Database: PostgreSQL
- Cache/Queue: Redis
- Task Queue: Celery

**Frontend (React SPA):**
- Hosting: Vercel/Netlify/Cloudflare Pages
- CDN: Automatic (built-in)
- Build Tool: Vite

---

## ✅ Prerequisites

### Required Services

- [ ] **Domain Name** (e.g., `yourapp.com`)
- [ ] **Cloud Server** (2GB RAM minimum, 4GB recommended)
- [ ] **PostgreSQL Database** (managed or self-hosted)
- [ ] **Redis Instance** (for caching and Celery)
- [ ] **Vercel Account** (free tier sufficient)
- [ ] **GitHub Account** (for CI/CD)

### Required Tools (Local Development)

```bash
# Backend
python 3.13+
postgresql-client
redis-cli

# Frontend
node 20+
npm 10+

# Deployment
docker & docker-compose
git
```

---

## 🏗 Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                         Internet                             │
└─────────────────────┬───────────────────┬───────────────────┘
                      │                   │
              ┌───────▼────────┐  ┌──────▼──────┐
              │  Vercel CDN    │  │   Backend    │
              │  (Frontend)    │  │  (API Server)│
              │  React + Vite  │  │ Gunicorn+Daphne│
              └────────────────┘  └───┬──────────┘
                                      │
                     ┌────────────────┼────────────────┐
                     │                │                │
              ┌──────▼─────┐  ┌──────▼─────┐  ┌───────▼──────┐
              │ PostgreSQL │  │   Redis    │  │    Celery    │
              │  Database  │  │ Cache/Queue│  │   Workers    │
              └────────────┘  └────────────┘  └──────────────┘
```

---

## 🚀 Quick Start

### 1. Clone Repository

```bash
git clone https://github.com/yourusername/password_manager.git
cd password_manager
```

### 2. Configure Environment Variables

```bash
# Backend
cd password_manager
cp env.example .env
nano .env  # Update all values

# Frontend
cd ../frontend
cp env.example .env.production
nano .env.production  # Update API_BASE_URL and WS_URL
```

### 3. Deploy Backend (Docker)

```bash
cd ../docker
docker-compose up -d
```

### 4. Deploy Frontend (Vercel)

```bash
cd ../frontend
npm install -g vercel
vercel login
vercel --prod
```

---

## 🖥 Backend Deployment

### Option 1: Docker Deployment (Recommended)

#### Step 1: Prepare Server

```bash
# SSH into your server
ssh user@your-server-ip

# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sh get-docker.sh

# Install Docker Compose
sudo apt-get install docker-compose-plugin

# Verify installation
docker --version
docker compose version
```

#### Step 2: Clone Repository

```bash
cd /opt
sudo git clone https://github.com/yourusername/password_manager.git
cd password_manager
```

#### Step 3: Configure Environment

```bash
# Create .env file
sudo nano docker/.env

# Add the following (update values):
```

```bash
# Django Core
SECRET_KEY=your-secret-key-here-minimum-50-characters
DEBUG=False
ALLOWED_HOSTS=api.yourapp.com,yourapp.com

# Database
DB_NAME=password_manager
DB_USER=pm_user
DB_PASSWORD=your-secure-db-password
DB_HOST=postgres
DB_PORT=5432

# Redis
REDIS_PASSWORD=your-redis-password
REDIS_URL=redis://:your-redis-password@redis:6379/0

# Celery
CELERY_BROKER_URL=redis://:your-redis-password@redis:6379/1
CELERY_RESULT_BACKEND=redis://:your-redis-password@redis:6379/2

# CORS
CORS_ALLOWED_ORIGINS=https://yourapp.com,https://www.yourapp.com
CSRF_TRUSTED_ORIGINS=https://yourapp.com,https://www.yourapp.com

# Security (Production)
SECURE_SSL_REDIRECT=True
DJANGO_SESSION_COOKIE_SECURE=True
DJANGO_CSRF_COOKIE_SECURE=True
```

#### Step 4: Deploy with Docker Compose

```bash
cd docker

# Build and start services
sudo docker-compose -f docker-compose.yml up -d

# Check logs
sudo docker-compose logs -f

# Verify services are running
sudo docker-compose ps
```

#### Step 5: Setup SSL (Let's Encrypt)

```bash
# Install certbot
sudo apt-get install certbot python3-certbot-nginx

# Obtain SSL certificate
sudo certbot --nginx -d api.yourapp.com

# Test automatic renewal
sudo certbot renew --dry-run
```

### Option 2: Manual Deployment

#### Step 1: Install Dependencies

```bash
# System packages
sudo apt-get update
sudo apt-get install -y python3.13 python3-pip python3-venv
sudo apt-get install -y postgresql postgresql-contrib
sudo apt-get install -y redis-server
sudo apt-get install -y nginx supervisor

# SSL
sudo apt-get install -y certbot python3-certbot-nginx
```

#### Step 2: Setup PostgreSQL

```bash
sudo -u postgres psql

CREATE DATABASE password_manager;
CREATE USER pm_user WITH PASSWORD 'your-secure-password';
ALTER ROLE pm_user SET client_encoding TO 'utf8';
ALTER ROLE pm_user SET default_transaction_isolation TO 'read committed';
ALTER ROLE pm_user SET timezone TO 'UTC';
GRANT ALL PRIVILEGES ON DATABASE password_manager TO pm_user;
\q
```

#### Step 3: Setup Application

```bash
# Create directory
sudo mkdir -p /opt/password_manager
sudo chown $USER:$USER /opt/password_manager

# Clone repository
cd /opt
git clone https://github.com/yourusername/password_manager.git
cd password_manager

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
cd password_manager
pip install --upgrade pip
pip install -r requirements.txt

# Configure environment
cp env.example .env
nano .env  # Update all values

# Run migrations
python manage.py migrate

# Create superuser
python manage.py createsuperuser

# Collect static files
python manage.py collectstatic --noinput
```

#### Step 4: Configure Supervisor

Create `/etc/supervisor/conf.d/password_manager.conf`:

```ini
[program:gunicorn]
command=/opt/password_manager/venv/bin/gunicorn password_manager.wsgi:application --bind 127.0.0.1:8000 --workers 4
directory=/opt/password_manager/password_manager
user=www-data
autostart=true
autorestart=true
redirect_stderr=true
stdout_logfile=/var/log/password_manager/gunicorn.log

[program:daphne]
command=/opt/password_manager/venv/bin/daphne -b 127.0.0.1 -p 8001 password_manager.asgi:application
directory=/opt/password_manager/password_manager
user=www-data
autostart=true
autorestart=true
redirect_stderr=true
stdout_logfile=/var/log/password_manager/daphne.log

[program:celery_worker]
command=/opt/password_manager/venv/bin/celery -A password_manager worker -l info
directory=/opt/password_manager/password_manager
user=www-data
autostart=true
autorestart=true
redirect_stderr=true
stdout_logfile=/var/log/password_manager/celery.log

[program:celery_beat]
command=/opt/password_manager/venv/bin/celery -A password_manager beat -l info
directory=/opt/password_manager/password_manager
user=www-data
autostart=true
autorestart=true
redirect_stderr=true
stdout_logfile=/var/log/password_manager/celery_beat.log
```

```bash
# Create log directory
sudo mkdir -p /var/log/password_manager
sudo chown www-data:www-data /var/log/password_manager

# Update supervisor
sudo supervisorctl reread
sudo supervisorctl update
sudo supervisorctl start all
```

#### Step 5: Configure Nginx

Create `/etc/nginx/sites-available/password_manager`:

```nginx
server {
    listen 80;
    server_name api.yourapp.com;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl http2;
    server_name api.yourapp.com;

    # SSL certificates (managed by Certbot)
    ssl_certificate /etc/letsencrypt/live/api.yourapp.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/api.yourapp.com/privkey.pem;

    # Security headers
    add_header X-Frame-Options "DENY" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;

    # API requests
    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # WebSocket
    location /ws/ {
        proxy_pass http://127.0.0.1:8001;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_read_timeout 86400;
    }

    # Static files
    location /static/ {
        alias /opt/password_manager/password_manager/staticfiles/;
        expires 30d;
    }

    # Health check
    location /api/health/ {
        proxy_pass http://127.0.0.1:8000;
        access_log off;
    }
}
```

```bash
# Enable site
sudo ln -s /etc/nginx/sites-available/password_manager /etc/nginx/sites-enabled/

# Test configuration
sudo nginx -t

# Restart nginx
sudo systemctl restart nginx
```

---

## 🌐 Frontend Deployment

### Option 1: Vercel (Recommended)

#### Step 1: Install Vercel CLI

```bash
npm install -g vercel
vercel login
```

#### Step 2: Configure Project

```bash
cd frontend

# Link project
vercel link

# Add environment variables
vercel env add VITE_API_BASE_URL production
# Enter: https://api.yourapp.com

vercel env add VITE_WS_URL production
# Enter: wss://api.yourapp.com
```

#### Step 3: Deploy

```bash
# Deploy to production
vercel --prod
```

#### Step 4: Configure Custom Domain

1. Go to Vercel Dashboard
2. Select your project
3. Go to Settings → Domains
4. Add your domain: `yourapp.com`
5. Update DNS records as instructed

### Option 2: Netlify

```bash
# Install Netlify CLI
npm install -g netlify-cli
netlify login

# Deploy
cd frontend
netlify deploy --prod
```

---

## 🔐 Security Checklist

### Pre-Deployment

- [ ] Change all default passwords
- [ ] Generate strong `SECRET_KEY` (50+ characters)
- [ ] Set `DEBUG=False` in production
- [ ] Configure `ALLOWED_HOSTS` correctly
- [ ] Setup SSL certificates
- [ ] Enable firewall (UFW)
- [ ] Configure CORS properly
- [ ] Review all environment variables

### Post-Deployment

- [ ] Run `python manage.py check --deploy`
- [ ] Test all API endpoints
- [ ] Verify WebSocket connections
- [ ] Test authentication flows
- [ ] Check SSL configuration (ssllabs.com)
- [ ] Enable automatic backups
- [ ] Setup monitoring and alerts
- [ ] Configure log rotation

---

## 📊 Monitoring & Maintenance

### Setup Sentry (Error Tracking)

```bash
# Install Sentry SDK
pip install sentry-sdk

# Add to settings.py
import sentry_sdk
from sentry_sdk.integrations.django import DjangoIntegration

if not DEBUG:
    sentry_sdk.init(
        dsn="your-sentry-dsn",
        integrations=[DjangoIntegration()],
        traces_sample_rate=0.1,
    )
```

### Setup UptimeRobot (Uptime Monitoring)

1. Create account at uptimerobot.com
2. Add monitors:
   - Frontend: `https://yourapp.com`
   - Backend Health: `https://api.yourapp.com/api/health/`
3. Configure email alerts

### Database Backups

```bash
# Create backup script
sudo nano /opt/backup_db.sh

#!/bin/bash
BACKUP_DIR="/opt/backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
mkdir -p $BACKUP_DIR

pg_dump -U pm_user password_manager | gzip > $BACKUP_DIR/backup_$TIMESTAMP.sql.gz

# Keep only last 30 days
find $BACKUP_DIR -name "backup_*.sql.gz" -mtime +30 -delete

# Make executable
sudo chmod +x /opt/backup_db.sh

# Add to crontab (daily at 2 AM)
sudo crontab -e
0 2 * * * /opt/backup_db.sh
```

---

## 🐛 Troubleshooting

### Backend Issues

#### Service not starting

```bash
# Check logs
sudo docker-compose logs backend
# OR
sudo supervisorctl status
sudo tail -f /var/log/password_manager/gunicorn.log
```

#### Database connection errors

```bash
# Test database connection
psql -U pm_user -d password_manager -h localhost -W

# Check PostgreSQL status
sudo systemctl status postgresql
```

#### Redis connection errors

```bash
# Test Redis connection
redis-cli -a your-redis-password ping

# Check Redis status
sudo systemctl status redis
```

### Frontend Issues

#### Build failures

```bash
# Clear cache and rebuild
cd frontend
rm -rf node_modules dist
npm install
npm run build
```

#### API connection errors

- Verify `VITE_API_BASE_URL` is correct
- Check CORS configuration in backend
- Verify SSL certificates are valid

---

## 📚 Additional Resources

- [Django Deployment Checklist](https://docs.djangoproject.com/en/4.2/howto/deployment/checklist/)
- [Docker Production Guide](https://docs.docker.com/config/containers/resource_constraints/)
- [Vercel Documentation](https://vercel.com/docs)
- [Let's Encrypt Setup](https://letsencrypt.org/getting-started/)

---

## 🆘 Support

For issues or questions:
- Check the [Troubleshooting](#troubleshooting) section
- Review [GitHub Issues](https://github.com/yourusername/password_manager/issues)
- Consult the [DEPLOYMENT_IMPLEMENTATION_CHECKLIST.md](./DEPLOYMENT_IMPLEMENTATION_CHECKLIST.md)

---

**Last Updated:** 2025-01-27  
**Version:** 1.0.0


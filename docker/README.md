# 🐳 Docker Deployment Guide

## Quick Start

### Prerequisites

- Docker Engine 20.10+ 
- Docker Compose V2 (plugin)
- 4GB RAM minimum
- 20GB disk space

### 1. Clone Repository

```bash
git clone https://github.com/yourusername/password_manager.git
cd password_manager/docker
```

### 2. Create Environment File

```bash
cp .env.example .env
nano .env
```

**Minimum Required Variables:**

```bash
SECRET_KEY=your-secret-key-minimum-50-characters
DB_PASSWORD=your-secure-database-password
REDIS_PASSWORD=your-redis-password
CORS_ALLOWED_ORIGINS=https://yourapp.com
```

### 3. Start Services

```bash
# Production deployment
docker compose up -d

# Development with hot reload
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d
```

### 4. Verify Deployment

```bash
# Check all services are running
docker compose ps

# View logs
docker compose logs -f

# Test health endpoint
curl http://localhost:8000/api/health/
```

### 5. Create Superuser

```bash
docker compose exec backend python manage.py createsuperuser
```

---

## 📦 Services

The stack includes the following services:

| Service | Port | Description |
|---------|------|-------------|
| **postgres** | 5432 | PostgreSQL 15 database |
| **redis** | 6379 | Redis cache & message broker |
| **backend** | 8000 | Django API (Gunicorn) |
| **websocket** | 8001 | WebSocket server (Daphne) |
| **celery_worker** | - | Background task worker |
| **celery_beat** | - | Scheduled task scheduler |
| **frontend** | 3000 | React UI (production build) |
| **nginx** | 80, 443 | Reverse proxy & SSL termination |

---

## 🔧 Common Commands

### View Logs

```bash
# All services
docker compose logs -f

# Specific service
docker compose logs -f backend
docker compose logs -f celery_worker
```

### Restart Services

```bash
# All services
docker compose restart

# Specific service
docker compose restart backend
```

### Stop Services

```bash
# Stop all
docker compose stop

# Stop specific service
docker compose stop backend
```

### Remove Everything

```bash
# Stop and remove containers, networks
docker compose down

# Also remove volumes (DELETES DATA!)
docker compose down -v
```

### Execute Commands

```bash
# Django shell
docker compose exec backend python manage.py shell

# Database migrations
docker compose exec backend python manage.py migrate

# Collect static files
docker compose exec backend python manage.py collectstatic --noinput

# Access PostgreSQL
docker compose exec postgres psql -U pm_user -d password_manager

# Access Redis CLI
docker compose exec redis redis-cli -a your-redis-password
```

---

## 🔐 Environment Variables

### Required Variables

```bash
# Django
SECRET_KEY=<generate with: python -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())'>
DEBUG=False
ALLOWED_HOSTS=api.yourapp.com,localhost

# Database
DB_NAME=password_manager
DB_USER=pm_user
DB_PASSWORD=<secure password>

# Redis  
REDIS_PASSWORD=<secure password>

# CORS
CORS_ALLOWED_ORIGINS=https://yourapp.com,https://www.yourapp.com
CSRF_TRUSTED_ORIGINS=https://yourapp.com,https://www.yourapp.com
```

### Optional Variables

```bash
# Gunicorn Workers (default: 4)
GUNICORN_WORKERS=4

# Celery Concurrency (default: 4)
CELERY_CONCURRENCY=4

# Blockchain (if enabled)
BLOCKCHAIN_ENABLED=True
BLOCKCHAIN_PRIVATE_KEY=0x...

# Sentry (error tracking)
SENTRY_DSN=https://...@sentry.io/...
```

---

## 📊 Monitoring

### Health Checks

```bash
# Backend API
curl http://localhost:8000/api/health/

# Frontend
curl http://localhost:3000/health

# Check service health status
docker compose ps
```

### Resource Usage

```bash
# View container stats
docker stats

# Specific service
docker stats password-manager-backend
```

---

## 🔄 Updates & Maintenance

### Update Application

```bash
# Pull latest code
git pull

# Rebuild and restart services
docker compose up -d --build

# Run migrations
docker compose exec backend python manage.py migrate
```

### Database Backup

```bash
# Create backup
docker compose exec postgres pg_dump -U pm_user password_manager | gzip > backup_$(date +%Y%m%d).sql.gz

# Restore backup
gunzip -c backup_20250127.sql.gz | docker compose exec -T postgres psql -U pm_user -d password_manager
```

### View Volumes

```bash
# List volumes
docker volume ls

# Inspect volume
docker volume inspect password_manager_postgres_data
```

---

## 🐛 Troubleshooting

### Port Already in Use

```bash
# Check what's using the port
sudo lsof -i :8000

# Kill the process or change port in docker-compose.yml
```

### Permission Errors

```bash
# Fix ownership
sudo chown -R $USER:$USER .

# Recreate volumes
docker compose down -v
docker compose up -d
```

### Database Connection Errors

```bash
# Check PostgreSQL logs
docker compose logs postgres

# Verify database is ready
docker compose exec postgres pg_isready -U pm_user
```

### Out of Memory

```bash
# Check Docker resource limits
docker info | grep Memory

# Increase Docker Desktop memory (GUI)
# Or reduce service concurrency in .env:
GUNICORN_WORKERS=2
CELERY_CONCURRENCY=2
```

---

## 🔒 Security Best Practices

1. **Never commit `.env` file** - Add to `.gitignore`
2. **Use strong passwords** - Generate with `openssl rand -base64 32`
3. **Enable SSL in production** - Configure nginx with Let's Encrypt
4. **Limit exposed ports** - Only expose 80/443 in production
5. **Regular updates** - Keep base images updated
6. **Monitor logs** - Set up centralized logging
7. **Backup regularly** - Automate database backups

---

## 📚 Additional Resources

- [Docker Compose Documentation](https://docs.docker.com/compose/)
- [PostgreSQL Docker Hub](https://hub.docker.com/_/postgres)
- [Redis Docker Hub](https://hub.docker.com/_/redis)
- [Django Deployment Checklist](https://docs.djangoproject.com/en/4.2/howto/deployment/checklist/)

---

**Need Help?** Check the main [DEPLOYMENT_GUIDE.md](../DEPLOYMENT_GUIDE.md) or open an issue on GitHub.


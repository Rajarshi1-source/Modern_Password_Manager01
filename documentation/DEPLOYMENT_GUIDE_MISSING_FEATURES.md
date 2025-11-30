# Deployment Guide: Missing Features

## 🚀 Quick Deployment Checklist

This guide provides step-by-step instructions to deploy the newly implemented missing features.

---

## ✅ Pre-Deployment Checklist

### System Requirements
- [ ] Python 3.10+ installed
- [ ] Node.js 18+ installed
- [ ] PostgreSQL 14+ running
- [ ] Redis 7+ running (for Celery/caching)
- [ ] Git installed

### Environment Setup
- [ ] Virtual environment activated
- [ ] `.env` file configured
- [ ] Database created and accessible
- [ ] Redis accessible

---

## 📦 Part 1: Email Masking Deployment

### Step 1: Install Backend Dependencies

```bash
cd password_manager

# Already included in requirements.txt:
# - requests>=2.31.0
# - cryptography>=41.0.0

# Install/update dependencies
pip install -r requirements.txt
```

### Step 2: Run Migrations

```bash
# Create migration files
python manage.py makemigrations email_masking

# Expected output:
# Migrations for 'email_masking':
#   email_masking/migrations/0001_initial.py
#     - Create model EmailAlias
#     - Create model EmailMaskingProvider
#     - Create model EmailAliasActivity

# Apply migrations
python manage.py migrate email_masking

# Verify migrations
python manage.py showmigrations email_masking
```

### Step 3: Verify Django Configuration

Check that `settings.py` includes:
```python
INSTALLED_APPS = [
    # ... other apps
    'email_masking',  # ✅ Should be present
]
```

Check that `urls.py` includes:
```python
urlpatterns = [
    # ... other patterns
    path('api/email-masking/', include('email_masking.urls')),  # ✅ Should be present
]
```

### Step 4: Test Email Masking API

```bash
# Start Django server
python manage.py runserver

# In another terminal, test the API
# (Replace YOUR_TOKEN with actual auth token)

# 1. Configure SimpleLogin provider
curl -X POST http://localhost:8000/api/email-masking/providers/configure/ \
  -H "Authorization: Token YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "provider": "simplelogin",
    "api_key": "sl_xxxxxxxxxxxx",
    "is_default": true
  }'

# Expected response:
# {
#   "message": "simplelogin configured successfully",
#   "provider": "simplelogin",
#   "is_default": true
# }

# 2. Create an alias
curl -X POST http://localhost:8000/api/email-masking/aliases/create/ \
  -H "Authorization: Token YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "provider": "simplelogin",
    "name": "Test Alias",
    "description": "Testing email masking"
  }'

# Expected response:
# {
#   "id": 1,
#   "alias_email": "random-alias-abc123@simplelogin.com",
#   "forwards_to": "user@gmail.com",
#   "provider": "simplelogin",
#   "status": "active",
#   "created_at": "2025-01-15T10:30:00Z"
# }

# 3. List aliases
curl -X GET http://localhost:8000/api/email-masking/aliases/ \
  -H "Authorization: Token YOUR_TOKEN"

# Expected response: Array of alias objects
```

### Step 5: Admin Interface Check

```bash
# Access Django admin
# http://localhost:8000/admin/email_masking/

# You should see:
# - Email aliases
# - Email masking providers
# - Email alias activities
```

---

## 📦 Part 2: Shared Folders Deployment

### Step 1: Run Migrations

```bash
cd password_manager

# Create migration files for shared folders
python manage.py makemigrations vault

# Expected output:
# Migrations for 'vault':
#   vault/migrations/000X_shared_folders.py
#     - Create model SharedFolder
#     - Create model SharedFolderMember
#     - Create model SharedVaultItem
#     - Create model SharedFolderKey
#     - Create model SharedFolderActivity

# Apply migrations
python manage.py migrate vault

# Verify migrations
python manage.py showmigrations vault | grep shared
```

### Step 2: Verify Models

```bash
python manage.py shell

# Test imports
>>> from vault.models import SharedFolder, SharedFolderMember
>>> from vault.models import SharedVaultItem, SharedFolderKey, SharedFolderActivity
>>> print("All shared folder models loaded successfully!")
>>> exit()
```

### Step 3: Database Verification

```sql
-- Connect to your PostgreSQL database
psql -U your_user -d password_manager_db

-- List new tables
\dt *shared*

-- Expected tables:
-- vault_sharedfolder
-- vault_sharedfoldermember
-- vault_sharedvaultitem
-- vault_sharedfolderkey
-- vault_sharedfolderactivity

-- Check table structure
\d vault_sharedfolder
\d vault_sharedfoldermember

-- Exit
\q
```

### Step 4: Test Data Creation (Optional)

```bash
python manage.py shell

# Create test shared folder
>>> from django.contrib.auth.models import User
>>> from vault.models import SharedFolder
>>> user = User.objects.first()  # Get a test user
>>> folder = SharedFolder.objects.create(
...     name="Test Shared Folder",
...     description="Testing shared folders feature",
...     owner=user
... )
>>> print(f"Created folder: {folder.id} - {folder.name}")
>>> exit()
```

---

## 📦 Part 3: XChaCha20 Encryption (Optional)

### Prerequisites

XChaCha20 implementation is **design-complete** but not yet implemented.  
This section provides setup instructions for when you're ready to implement it.

### Backend Setup (Future)

```bash
# Dependencies already included in cryptography package
pip install cryptography>=41.0.0

# Verify ChaCha20-Poly1305 availability
python -c "from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305; print('XChaCha20 support: OK')"
```

### Frontend Setup (Future)

```bash
cd frontend

# Install libsodium for XChaCha20 support
npm install libsodium-wrappers

# Verify installation
npm list libsodium-wrappers
```

---

## 🔐 Security Configuration

### Environment Variables

Add to your `.env` file:

```bash
# Email Masking Security
EMAIL_MASKING_ENCRYPTION_KEY=<generate-secure-key>

# Shared Folders
SHARED_FOLDER_MAX_MEMBERS=50
SHARED_FOLDER_INVITATION_EXPIRY_HOURS=72

# API Rate Limiting
EMAIL_MASKING_RATE_LIMIT=100/hour
SHARED_FOLDER_RATE_LIMIT=200/hour
```

Generate secure keys:
```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

### API Key Encryption

Email masking API keys are encrypted using the existing `CryptoService`.  
Ensure your encryption keys are properly configured:

```python
# In settings.py
ENCRYPTION_KEY = os.environ.get('ENCRYPTION_KEY')  # Must be set
```

---

## 📊 Monitoring & Logging

### Enable Logging

Add to `settings.py`:

```python
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'file': {
            'level': 'INFO',
            'class': 'logging.FileHandler',
            'filename': 'logs/email_masking.log',
        },
    },
    'loggers': {
        'email_masking': {
            'handlers': ['file'],
            'level': 'INFO',
            'propagate': False,
        },
        'vault.shared_folders': {
            'handlers': ['file'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}
```

### Monitor Activity

```bash
# Watch email masking logs
tail -f logs/email_masking.log

# Watch shared folders logs
tail -f logs/django.log | grep shared_folder
```

---

## 🧪 Testing

### Unit Tests

```bash
# Test email masking
python manage.py test email_masking

# Test shared folders
python manage.py test vault.tests.test_shared_folders
```

### Integration Tests

```bash
# Run all tests
python manage.py test

# Generate coverage report
coverage run --source='.' manage.py test
coverage report
coverage html  # Generate HTML report
```

### Manual Testing Scenarios

#### Email Masking Test Cases

1. **Provider Configuration**:
   - [ ] Configure SimpleLogin with valid API key
   - [ ] Configure AnonAddy with valid API key
   - [ ] Try invalid API key (should fail)
   - [ ] Set default provider

2. **Alias Management**:
   - [ ] Create new alias
   - [ ] List all aliases
   - [ ] Toggle alias on/off
   - [ ] Delete alias
   - [ ] View activity logs

3. **Security**:
   - [ ] Verify API keys are encrypted in database
   - [ ] Test quota limits
   - [ ] Test rate limiting

#### Shared Folders Test Cases (When API is complete)

1. **Folder Creation**:
   - [ ] Create shared folder as owner
   - [ ] Set folder permissions
   - [ ] Configure 2FA requirement

2. **Member Management**:
   - [ ] Invite user to folder
   - [ ] Accept invitation
   - [ ] Decline invitation
   - [ ] Update member role
   - [ ] Remove member

3. **Item Sharing**:
   - [ ] Add item to shared folder
   - [ ] View shared item as different user
   - [ ] Edit shared item (if permitted)
   - [ ] Remove item from folder

4. **Permissions**:
   - [ ] Test viewer can only read
   - [ ] Test editor can modify
   - [ ] Test admin can manage members
   - [ ] Test owner has full control

---

## 🐛 Troubleshooting

### Common Issues

#### 1. Migration Errors

**Issue**: `django.db.utils.OperationalError: no such table`

**Solution**:
```bash
python manage.py makemigrations
python manage.py migrate
```

#### 2. Import Errors

**Issue**: `ModuleNotFoundError: No module named 'email_masking'`

**Solution**:
```bash
# Verify app is in INSTALLED_APPS
python manage.py check

# Restart Django server
python manage.py runserver
```

#### 3. API Key Encryption Errors

**Issue**: `CryptoService encryption failed`

**Solution**:
```bash
# Ensure ENCRYPTION_KEY is set
echo $ENCRYPTION_KEY

# If not set, add to .env:
ENCRYPTION_KEY=$(python -c "import secrets; print(secrets.token_urlsafe(32))")
```

#### 4. SimpleLogin/AnonAddy API Errors

**Issue**: `Failed to create alias: 401 Unauthorized`

**Solution**:
- Verify API key is correct
- Check API key permissions
- Verify account is active
- Check rate limits

---

## 📈 Performance Optimization

### Database Indexing

```sql
-- Email masking indexes (already created by migrations)
CREATE INDEX idx_email_alias_user_status ON email_masking_emailalias(user_id, status);
CREATE INDEX idx_email_alias_provider ON email_masking_emailalias(provider, provider_alias_id);

-- Shared folder indexes (already created by migrations)
CREATE INDEX idx_shared_folder_owner ON vault_sharedfolder(owner_id, is_active);
CREATE INDEX idx_shared_folder_member ON vault_sharedfoldermember(user_id, status);
CREATE INDEX idx_shared_folder_activity ON vault_sharedfolderactivity(folder_id, timestamp DESC);
```

### Caching

```python
# Add to settings.py for production
CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': 'redis://127.0.0.1:6379/1',
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
        }
    }
}

# Cache email aliases list
from django.core.cache import cache

def get_user_aliases(user_id):
    cache_key = f'user_aliases_{user_id}'
    aliases = cache.get(cache_key)
    
    if not aliases:
        aliases = EmailAlias.objects.filter(user_id=user_id)
        cache.set(cache_key, aliases, 300)  # Cache for 5 minutes
    
    return aliases
```

---

## 🌐 Production Deployment

### Pre-Production Checklist

- [ ] All migrations applied
- [ ] Tests passing (95%+ coverage)
- [ ] Security audit completed
- [ ] API documentation updated
- [ ] Monitoring configured
- [ ] Backup strategy in place
- [ ] Rate limiting configured
- [ ] SSL/TLS enabled
- [ ] CORS configured
- [ ] Logging enabled

### Production Settings

```python
# settings_production.py

DEBUG = False
ALLOWED_HOSTS = ['yourdomain.com', 'www.yourdomain.com']

# Security
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 31536000

# Rate Limiting
REST_FRAMEWORK = {
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle'
    ],
    'DEFAULT_THROTTLE_RATES': {
        'anon': '100/hour',
        'user': '1000/hour',
        'email_masking': '100/hour',
        'shared_folders': '200/hour',
    }
}
```

### Docker Deployment (Optional)

```dockerfile
# Dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN python manage.py collectstatic --noinput
RUN python manage.py migrate

CMD ["gunicorn", "--bind", "0.0.0.0:8000", "password_manager.wsgi:application"]
```

```yaml
# docker-compose.yml
version: '3.8'

services:
  web:
    build: .
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql://user:pass@db:5432/dbname
      - REDIS_URL=redis://redis:6379/0
    depends_on:
      - db
      - redis

  db:
    image: postgres:15
    environment:
      - POSTGRES_PASSWORD=secure_password
      - POSTGRES_DB=password_manager

  redis:
    image: redis:7-alpine
```

---

## 📚 Additional Resources

### Documentation
- [Email Masking Implementation Guide](./MISSING_FEATURES_IMPLEMENTATION.md)
- [Complete Summary](./MISSING_FEATURES_COMPLETE_SUMMARY.md)
- [API Documentation](http://localhost:8000/docs/)

### External Services
- [SimpleLogin API Docs](https://github.com/simple-login/app/blob/master/docs/api.md)
- [AnonAddy API Docs](https://app.addy.io/docs/)
- [Django Best Practices](https://docs.djangoproject.com/en/stable/topics/best-practices/)

### Support
- GitHub Issues: [Create Issue](https://github.com/your-repo/issues)
- Documentation: [Wiki](https://github.com/your-repo/wiki)

---

## ✅ Post-Deployment Verification

### Checklist

After deployment, verify:

- [ ] Email masking API responds correctly
- [ ] SimpleLogin/AnonAddy integration works
- [ ] Aliases can be created and managed
- [ ] Shared folder models are accessible
- [ ] Database indexes are created
- [ ] Logging is working
- [ ] No errors in logs
- [ ] Admin interface accessible
- [ ] API rate limiting works
- [ ] SSL/TLS enabled (production)

### Health Check

```bash
# Check API health
curl http://localhost:8000/health/

# Check email masking endpoint
curl http://localhost:8000/api/email-masking/providers/

# Check database
python manage.py dbshell
\dt email_masking*
\dt vault_shared*
\q
```

---

## 🎉 Success Criteria

Deployment is successful when:

✅ **Email Masking**:
- Users can configure SimpleLogin/AnonAddy
- Aliases can be created and managed
- Activity logs are recorded
- API keys are encrypted

✅ **Shared Folders**:
- Models are migrated
- Database tables exist
- Admin interface works
- Ready for API implementation

✅ **System Health**:
- No critical errors
- All tests passing
- Logs are clean
- Performance is acceptable

---

**Deployment Guide Version**: 1.0.0  
**Last Updated**: $(date '+%Y-%m-%d')  
**Status**: ✅ **PRODUCTION READY** (Email Masking + Shared Folders Models)

---

## 📞 Need Help?

If you encounter issues:

1. Check the [Troubleshooting](#troubleshooting) section
2. Review the logs in `logs/` directory
3. Consult the [Implementation Guide](./MISSING_FEATURES_IMPLEMENTATION.md)
4. Create a GitHub issue with:
   - Error message
   - Steps to reproduce
   - System information
   - Logs

**Good luck with your deployment!** 🚀


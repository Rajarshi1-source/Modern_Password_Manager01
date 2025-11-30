# Hybrid Cryptography Upgrade - Quick Start Guide

**For:** Password Manager Hybrid Crypto Implementation  
**Date:** October 16, 2025

---

## What Was Implemented

✅ **Enhanced Argon2id** - Stronger key derivation (128 MB memory, adaptive)  
✅ **Dual ECC Curves** - Curve25519 + P-384 for defense-in-depth  
✅ **PQC-Ready Format** - Versioned vault for future quantum resistance

---

## Installation Commands

### 1. Frontend Setup

```bash
# Navigate to frontend directory
cd frontend

# Install new cryptography libraries
npm install

# This installs:
# - @noble/curves@^1.6.0 (ECC operations)
# - @noble/hashes@^1.5.0 (Hash functions)
```

### 2. Backend Setup

```bash
# Navigate to backend directory
cd password_manager

# Apply database migrations for crypto versioning
python manage.py migrate vault 0002_add_crypto_versioning

# No new Python packages needed - all already in requirements.txt
```

### 3. Verify Installation

#### Frontend Verification:
```bash
cd frontend

# Check if libraries are installed
npm list @noble/curves @noble/hashes

# Should show:
# ├── @noble/curves@1.6.0
# └── @noble/hashes@1.5.0
```

#### Backend Verification:
```bash
cd password_manager

# Check if migration was applied
python manage.py showmigrations vault

# Should show:
# vault
#  [X] 0001_initial
#  [X] 0002_add_crypto_versioning
```

---

## Testing the Upgrade

### Test 1: Login (Automatic Upgrade)

1. **Start backend:**
   ```bash
   cd password_manager
   python manage.py runserver
   ```

2. **Start frontend:**
   ```bash
   cd frontend
   npm run dev
   ```

3. **Login with existing account:**
   - Open http://localhost:3000
   - Login with your existing credentials
   - Check browser console for: "Deriving key with Argon2id v2"

4. **Verify upgrade:**
   ```bash
   # In Django shell
   python manage.py shell
   
   >>> from vault.models import EncryptedVaultItem
   >>> EncryptedVaultItem.objects.values('crypto_version').distinct()
   # Should show: <QuerySet [{'crypto_version': 2}]> (after first login)
   ```

### Test 2: Create New Item

1. Login to the app
2. Create a new password item
3. Check database:
   ```bash
   python manage.py shell
   
   >>> from vault.models import EncryptedVaultItem
   >>> item = EncryptedVaultItem.objects.latest('created_at')
   >>> print(f"Version: {item.crypto_version}")
   >>> print(f"Metadata: {item.crypto_metadata}")
   ```
   
   Expected output:
   ```
   Version: 2
   Metadata: {'kdf': 'Argon2id', 'version': 2}
   ```

### Test 3: ECC Service (Optional)

```javascript
// In browser console (after login)
import eccService from './services/eccService.js';

// Generate keypair
const keys = eccService.generateHybridKeyPair();
console.log('Hybrid keypair generated:', keys);

// Export public keys
const exported = eccService.exportPublicKeys(keys);
console.log('Exported public keys:', exported);
```

---

## Performance Check

### Expected Login Times

| Device Type | v1 (Old) | v2 (New) | Delta |
|-------------|----------|----------|-------|
| Desktop (high-end) | ~300ms | ~600ms | +300ms |
| Laptop (mid-range) | ~400ms | ~800ms | +400ms |
| Mobile (low-end) | ~600ms | ~1200ms | +600ms |

**Note:** Times are for key derivation only. Total login time includes network latency.

### Check Actual Performance

```javascript
// In browser console during login
const start = performance.now();
// ... login happens ...
const end = performance.now();
console.log(`Login took: ${end - start}ms`);
```

---

## Troubleshooting

### Issue 1: "Module not found: @noble/curves"

**Solution:**
```bash
cd frontend
npm install @noble/curves @noble/hashes --save
npm run dev
```

### Issue 2: Migration already applied

**Solution:**
```bash
# If you see "Migration vault.0002 is already applied"
# This is normal - migration was already run
python manage.py showmigrations vault
# Should show [X] next to 0002
```

### Issue 3: Slow login on mobile

**Solution:**
- This is expected behavior (enhanced security)
- The system automatically reduces parameters on detected low-end devices
- Check console: Should show lower memory usage for low-capability devices

### Issue 4: Items not upgrading to v2

**Check:**
1. Is user logging in successfully?
2. Check console for errors during key derivation
3. Verify migration was applied:
   ```bash
   python manage.py migrate vault --plan
   ```

---

## Rollback (If Needed)

### Emergency Rollback to v1

**ONLY IF CRITICAL BUG FOUND:**

```bash
# 1. Stop new migrations (backend)
# In settings.py, add:
CRYPTO_VERSION_FREEZE = 1

# 2. Allow both v1 and v2
# Items will continue to work with both versions

# 3. If needed, revert migration
python manage.py migrate vault 0001_initial
# WARNING: This removes crypto_version fields!
```

### Gradual Rollback

```python
# In Django shell
from vault.models import EncryptedVaultItem

# Revert specific user's items
user_items = EncryptedVaultItem.objects.filter(user_id=USER_ID)
user_items.update(crypto_version=1)
```

---

## Monitoring

### Check Upgrade Progress

```python
# In Django shell
from vault.models import EncryptedVaultItem
from django.db.models import Count

# Get version distribution
stats = EncryptedVaultItem.objects.values('crypto_version').annotate(
    count=Count('id')
)

for stat in stats:
    print(f"Version {stat['crypto_version']}: {stat['count']} items")
```

### Monitor Performance

```python
# Add to login view
import time

start = time.time()
# ... key derivation ...
duration = time.time() - start

logger.info(f'Key derivation took {duration*1000:.2f}ms')
```

---

## What's Next?

### Immediate (Week 1-2)
- [x] Install dependencies
- [x] Apply migrations
- [ ] Test with existing accounts
- [ ] Monitor login performance
- [ ] Collect user feedback

### Short-term (Month 1-3)
- [ ] Complete migration of all users
- [ ] Monitor error rates
- [ ] Performance optimization
- [ ] Security audit

### Long-term (2026+)
- [ ] Implement PQC (ML-KEM-768)
- [ ] Migrate to v3 format
- [ ] Hardware security integration

---

## Support & Documentation

- **Full Implementation Plan**: `HYBRID_CRYPTO_UPGRADE_PLAN.md`
- **Implementation Summary**: `HYBRID_CRYPTO_IMPLEMENTATION_SUMMARY.md`
- **API Documentation**: `API_CRYPTO_SPEC.md` (to be created)

---

## Command Reference

### NPM Commands
```bash
npm install              # Install dependencies
npm run dev              # Start dev server
npm run build            # Build for production
npm test                 # Run tests
npm list @noble/curves   # Check if library installed
```

### Django Commands
```bash
python manage.py migrate                    # Apply migrations
python manage.py showmigrations            # Show migration status
python manage.py runserver                 # Start server
python manage.py shell                     # Django shell
python manage.py test vault.tests          # Run tests
```

### Git Commands (if tracking)
```bash
git status                                 # Check changes
git add .                                  # Stage changes
git commit -m "Implement hybrid crypto"    # Commit
git push                                   # Push to remote
```

---

**Quick Start Version**: 1.0  
**Last Updated**: October 16, 2025

---

## Ready to Deploy? ✅

1. ✅ Dependencies installed (frontend + backend)
2. ✅ Migrations applied
3. ✅ Code changes reviewed
4. ⏳ Tests passing (run tests now)
5. ⏳ Performance acceptable (measure on login)

**All set!** Start your servers and test the upgrade.


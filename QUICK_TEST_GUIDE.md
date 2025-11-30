# Quick Testing Guide - TestSprite Fixes

## 🚀 Quick Start

### Prerequisites
- Ensure `.env` file in `password_manager/` directory has `DEBUG=True`
- Python 3.11+ and Node.js 18+ installed

### 1. Start Backend Server
```bash
cd password_manager
python manage.py runserver 8000
```

### 2. Start Frontend Server (New Terminal)
```bash
cd frontend
npm run dev
```

### 3. Access Application
Open browser: `http://localhost:5173`

### Test Credentials
- **Email:** `testuser@gmail.com`
- **Password:** `TestPass123!`

> **Note:** If user doesn't exist, create it with:
> ```bash
> cd password_manager
> python manage.py shell -c "
> from django.contrib.auth.models import User
> from auth_module.models import UserSalt
> import os
> u, created = User.objects.get_or_create(username='testuser@gmail.com', defaults={'email': 'testuser@gmail.com'})
> u.set_password('TestPass123!')
> u.save()
> if not UserSalt.objects.filter(user=u).exists():
>     UserSalt.objects.create(user=u, salt=os.urandom(32), auth_hash=os.urandom(64))
> print('Test user ready!')
> "
> ```

---

## ✅ What Was Fixed

| Issue | Status | Impact |
|-------|--------|--------|
| Backend 500 errors | ✅ Fixed | Analytics/performance endpoints now work |
| Login flow | ✅ Fixed | Authentication working correctly |
| Kyber WASM loading | ✅ Fixed | Quantum-resistant encryption restored |
| Styled-components warnings | ✅ Fixed | Clean console output |
| Error messages | ✅ Fixed | User-friendly feedback |

---

## 🧪 Quick Verification Tests

### Test 1: Check Console (Should be Clean)
1. Open browser DevTools (F12)
2. Go to Console tab
3. **Expected:** No "unknown prop" warnings
4. **Expected:** No "Kyber WASM not available" warnings
5. **Expected:** See "[KyberWASM] Module loaded" message

### Test 2: Check Backend Endpoints
1. Open Network tab in DevTools
2. Refresh the page
3. Look for these requests:
   - `/api/ab-testing/` → Should return **200** (not 500)
   - `/api/performance/frontend/` → Should return **200** (not 500)
   - `/api/analytics/events/` → Should return **200** or **201** (not 500)

### Test 3: Test Login
1. Enter email and password
2. Click "Login to Vault"
3. **Expected:** Either success or clear error message
4. **Expected:** No silent failures

### Test 4: Test Network Error Handling
1. Disconnect internet
2. Try to login
3. **Expected:** "Network error: Unable to connect to the server..." message

---

## 🔄 Re-run TestSprite

Once you've verified the fixes manually:

```bash
# Make sure both servers are running
# Then run TestSprite from project root:
npx @testsprite/testsprite-mcp generateCodeAndExecute
```

**Expected Improvement:**
- Previous pass rate: **5% (1/20 tests)**
- Expected new pass rate: **80%+ (16+/20 tests)**

---

## 📊 What Should Work Now

✅ User registration  
✅ Login with password  
✅ Passkey authentication  
✅ Error handling  
✅ Analytics tracking  
✅ Performance monitoring  
✅ Kyber quantum encryption  
✅ Password strength meter  
✅ Vault operations (if user is authenticated)  

---

## 🐛 Known Limitations

Some tests may still fail due to **environment setup** (not code issues):

1. **OAuth Login** - Requires OAuth provider credentials
2. **2FA/TOTP** - Requires TOTP setup for test users
3. **WebSocket Features** - Requires WebSocket server configuration
4. **Test Data** - Some tests need pre-seeded database records

These are **configuration issues**, not bugs in the code.

---

## 📝 Files Changed

### Backend (1 file)
- `password_manager/shared/performance_views.py`

### Frontend (7 files)
- `frontend/src/utils/kyber-wasm-loader.js`
- `frontend/src/Components/common/LoadingIndicator.jsx`
- `frontend/src/Components/security/PasswordStrengthMeter.jsx`
- `frontend/src/Components/security/PasswordStrengthMeterML.jsx`
- `frontend/src/Components/vault/VaultItemDetail.jsx`
- `frontend/src/Components/auth/Login.jsx`
- `frontend/src/Components/auth/PasskeyAuth.jsx`

---

## 🎯 Success Criteria

After fixes, you should see:

✅ No 500 errors in Network tab  
✅ Clean console (no styled-components warnings)  
✅ Kyber WASM loads successfully  
✅ Clear error messages when things fail  
✅ Login flow completes successfully  
✅ TestSprite pass rate above 80%  

---

## 💡 Troubleshooting

### If login still fails:
1. Check backend is running on port 8000
2. Check frontend is running on port 5173
3. **Verify DEBUG=True** in `password_manager/.env` file
4. Clear browser cache and localStorage
5. Check browser console for specific errors

### HTTPS Redirect Issues (500 errors everywhere):
If you see `net::ERR_SSL_PROTOCOL_ERROR` or HTTPS redirect issues:
1. Open `password_manager/.env`
2. Set `DEBUG=True` (this disables SECURE_SSL_REDIRECT)
3. Restart the backend server

### Rate Limiting (HTTP 429 errors):
If you get "Too Many Requests" errors during testing:
- Rate limits are automatically increased in DEBUG mode (30 auth requests/minute vs 3/minute in production)
- Wait 1 minute or restart the backend server to reset limits

### ASGI/Daphne Issues:
If you see `HttpResponsePermanentRedirect can't be used in 'await' expression`:
- The Django Channels and Daphne are disabled by default in development
- Use `python manage.py runserver` (WSGI) instead of Daphne (ASGI)

### If Kyber WASM still not loading:
1. Verify file exists: `frontend/public/assets/kyber.wasm`
2. Check browser console for fetch errors
3. Verify Vite is serving static assets correctly

### If 500 errors persist:
1. **Most common:** Check `DEBUG=True` in `.env` file
2. Check Django logs for specific error messages
3. Verify database migrations are applied: `python manage.py migrate`
4. Check CORS settings in Django

### If form submission doesn't work:
1. The login form uses uncontrolled inputs for browser automation compatibility
2. Make sure to fill in both email and password fields
3. Check browser console for debug logs starting with `[DEBUG]`

---

## 🔧 Key Configuration Files

| File | Purpose |
|------|---------|
| `password_manager/.env` | Backend settings (DEBUG, database, etc.) |
| `frontend/vite.config.js` | Frontend proxy configuration |
| `password_manager/password_manager/settings.py` | Django settings |

---

**For detailed information, see:** `TESTSPRITE_FIXES_SUMMARY.md`


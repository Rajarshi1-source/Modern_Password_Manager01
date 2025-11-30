# FIDO2/WebAuthn Passkey - Production Deployment Checklist

## ✅ All Critical Fixes Applied

All critical security vulnerabilities have been resolved. The passkey implementation is now **production-ready** after completing this checklist.

---

## 📋 Pre-Deployment Checklist

### 1. Environment Configuration ⚙️

- [ ] Create `.env` file in `password_manager/` directory if it doesn't exist
- [ ] Add passkey configuration:
  ```bash
  # For Development (localhost)
  PASSKEY_RP_ID=localhost
  PASSKEY_RP_NAME=Password Manager
  PASSKEY_ALLOWED_ORIGINS=
  
  # For Production (replace with your domain)
  PASSKEY_RP_ID=yourdomain.com
  PASSKEY_RP_NAME=Your Password Manager
  PASSKEY_ALLOWED_ORIGINS=https://yourdomain.com,https://www.yourdomain.com
  ```
- [ ] Verify `DEBUG=False` in production
- [ ] Verify `SECRET_KEY` is set to a secure value (not the default)

### 2. Database ��️

- [ ] Run migrations (if any):
  ```bash
  cd password_manager
  python manage.py makemigrations
  python manage.py migrate
  ```
- [ ] Verify `UserPasskey` model exists:
  ```bash
  python manage.py shell
  >>> from auth_module.models import UserPasskey
  >>> UserPasskey.objects.count()
  ```

### 3. HTTPS Configuration 🔒

- [ ] **CRITICAL**: Ensure HTTPS is enabled in production
  - WebAuthn **requires** HTTPS (except for localhost)
  - Configure SSL certificate
  - Update `SECURE_SSL_REDIRECT = True` in settings.py

- [ ] Verify HTTPS redirect is working:
  ```bash
  curl -I http://yourdomain.com
  # Should return 301/302 redirect to https://
  ```

### 4. CORS Configuration 🌐

- [ ] Update `CORS_ALLOWED_ORIGINS` in settings.py:
  ```python
  CORS_ALLOWED_ORIGINS = [
      "https://yourdomain.com",
      "https://www.yourdomain.com",
  ]
  ```

- [ ] Verify CORS headers are present:
  ```bash
  curl -H "Origin: https://yourdomain.com" \
       -H "Access-Control-Request-Method: POST" \
       -X OPTIONS https://yourdomain.com/api/auth/passkey/register/begin/
  ```

### 5. Testing 🧪

#### a) Registration Flow
- [ ] Open application in supported browser (Chrome, Firefox, Safari, Edge)
- [ ] Navigate to passkey registration
- [ ] Click "Register Passkey"
- [ ] Complete biometric/PIN verification
- [ ] Verify success message
- [ ] Check database: `UserPasskey.objects.filter(user=your_user)`

#### b) Authentication Flow
- [ ] Log out
- [ ] Navigate to login page
- [ ] Click "Sign in with Passkey"
- [ ] Complete biometric/PIN verification
- [ ] Verify successful login
- [ ] Check that JWT tokens are present in response

#### c) Management Flow
- [ ] Navigate to passkey management page
- [ ] Verify registered passkeys are listed
- [ ] Test deleting a passkey
- [ ] Test registering multiple passkeys

#### d) Error Scenarios
- [ ] Test duplicate passkey registration (should fail)
- [ ] Test authentication with invalid credential
- [ ] Test authentication after passkey deletion
- [ ] Verify appropriate error messages

### 6. Security Verification 🔐

- [ ] Check logs for passkey operations:
  ```bash
  tail -f password_manager/logs/security.log
  ```

- [ ] Verify origin validation:
  ```python
  # In Django shell
  from auth_module.passkey_views import verify_origin_custom
  
  # Should return True
  print(verify_origin_custom('https://yourdomain.com'))
  
  # Should return False
  print(verify_origin_custom('https://evil.com'))
  ```

- [ ] Verify sign count is incrementing:
  ```python
  from auth_module.models import UserPasskey
  
  passkey = UserPasskey.objects.first()
  print(f"Initial sign count: {passkey.sign_count}")
  # After authentication
  passkey.refresh_from_db()
  print(f"New sign count: {passkey.sign_count}")  # Should be higher
  ```

### 7. Browser Compatibility 🌍

Test on supported browsers:

- [ ] Chrome/Chromium (Windows, macOS, Linux, Android)
- [ ] Firefox (Windows, macOS, Linux, Android)
- [ ] Safari (macOS, iOS)
- [ ] Edge (Windows, macOS)

Test different authenticator types:
- [ ] Platform authenticator (Windows Hello, Touch ID, Face ID)
- [ ] Security key (YubiKey, etc.)
- [ ] Mobile device

### 8. Monitoring & Logging 📊

- [ ] Configure log rotation for `logs/security.log`
- [ ] Set up monitoring for:
  - Passkey registration failures
  - Authentication failures
  - Sign count violations (potential replay attacks)

- [ ] Create alerts for:
  - High failure rate
  - Sign count verification failures
  - Origin verification failures

### 9. Documentation 📚

- [ ] Update user documentation with passkey instructions
- [ ] Create troubleshooting guide for common issues
- [ ] Document browser compatibility
- [ ] Document fallback authentication methods

### 10. Backup & Recovery 💾

- [ ] Document passkey recovery process
- [ ] Ensure users can access account without passkey
- [ ] Test account recovery flow
- [ ] Document what happens if user loses all passkeys

---

## 🚀 Deployment Steps

### Development Environment

```bash
# 1. Update environment
cd password_manager
cp env.example .env
# Edit .env with your settings

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run migrations
python manage.py migrate

# 4. Start development server
python manage.py runserver

# 5. Start frontend (in another terminal)
cd ../frontend
npm install
npm run dev
```

### Production Environment

```bash
# 1. Set environment variables
export PASSKEY_RP_ID=yourdomain.com
export PASSKEY_RP_NAME="Your App Name"
export PASSKEY_ALLOWED_ORIGINS="https://yourdomain.com,https://www.yourdomain.com"
export DEBUG=False
export SECRET_KEY="your-secure-secret-key"

# 2. Collect static files
python manage.py collectstatic --noinput

# 3. Run migrations
python manage.py migrate

# 4. Restart application server
sudo systemctl restart gunicorn  # Or your WSGI server

# 5. Verify deployment
curl https://yourdomain.com/api/health/
```

---

## ⚠️ Common Issues & Solutions

### Issue: "Origin verification failed"
**Solution**: Check `PASSKEY_ALLOWED_ORIGINS` includes your domain with correct protocol (https://)

### Issue: "This passkey is already registered"
**Solution**: User already registered this authenticator. Try with a different device or delete the old passkey first.

### Issue: "Sign count verification failed"
**Potential Cause**: Cloned authenticator or replay attack
**Solution**: Delete the passkey and re-register. If problem persists, investigate security breach.

### Issue: "Authentication failed. Invalid signature"
**Potential Causes**:
- Origin mismatch
- Wrong user/passkey combination
- Corrupted database entry

**Solution**: Verify origin settings, try re-registration

### Issue: WebAuthn not available in browser
**Solution**: 
- Ensure HTTPS is enabled (required in production)
- Check browser supports WebAuthn
- Verify user has compatible authenticator

---

## 📈 Post-Deployment Monitoring

### Week 1
- [ ] Monitor registration success rate
- [ ] Check for authentication failures
- [ ] Review security logs daily
- [ ] Gather user feedback

### Week 2-4
- [ ] Analyze usage patterns
- [ ] Identify common issues
- [ ] Optimize error messages
- [ ] Update documentation based on feedback

### Ongoing
- [ ] Monthly security audit
- [ ] Keep `fido2` library updated
- [ ] Monitor for new browser support
- [ ] Track authenticator compatibility

---

## 📞 Support Resources

- **FIDO Alliance**: https://fidoalliance.org/
- **WebAuthn Guide**: https://webauthn.guide/
- **python-fido2 Docs**: https://github.com/Yubico/python-fido2
- **Django REST Framework**: https://www.django-rest-framework.org/

---

## ✅ Final Verification

Before marking deployment as complete, verify:

- [ ] All items in pre-deployment checklist completed
- [ ] Testing completed successfully
- [ ] Production environment configured
- [ ] HTTPS enabled and working
- [ ] Monitoring and logging configured
- [ ] Documentation updated
- [ ] Team trained on passkey support

---

## 🎉 Deployment Complete!

Once all checkboxes are marked, your passkey implementation is **production-ready** and secure!

---

**Checklist Version**: 1.0  
**Last Updated**: October 11, 2025  
**Status**: Ready for Production Deployment


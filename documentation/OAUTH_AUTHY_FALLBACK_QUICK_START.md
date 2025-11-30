# OAuth → Authy Fallback Quick Start Guide

## 🚀 Quick Overview

This feature automatically activates Authy SMS verification when OAuth authentication (Google, GitHub, Apple) fails, ensuring users can always authenticate.

## ✅ Implementation Complete

| Component | Status | Files Modified |
|-----------|--------|----------------|
| Backend | ✅ Complete | `oauth_views.py`, `urls.py` |
| Frontend | ✅ Complete | `oauthService.js`, `OAuthCallback.jsx` |
| Documentation | ✅ Complete | This guide + full docs |

## 📋 Prerequisites

### Required Packages

**Already Installed in requirements.txt:**
- ✅ `authy==2.2.6`
- ✅ `django-allauth==65.12.0`
- ✅ `dj-rest-auth==7.0.1`

## 🔧 Setup (5 Minutes)

### Step 1: Configure Authy API Key

Get your Authy API key from [Twilio Console](https://www.twilio.com/console/authy):

1. Sign up for Twilio account
2. Navigate to Authy section
3. Copy your API key

### Step 2: Update Backend .env

Edit `password_manager/.env`:

```env
# Add or update this line
AUTHY_API_KEY=your_authy_api_key_here
```

### Step 3: Restart Backend

```bash
cd password_manager
python manage.py runserver
```

### Step 4: Test Frontend

```bash
cd frontend
npm run dev
```

## 🧪 Quick Test (3 Minutes)

### Test the Fallback Mechanism:

1. **Navigate to Login:**
   ```
   http://localhost:3000
   ```

2. **Trigger OAuth Failure:**
   - Click "Sign in with Google"
   - In the OAuth popup, close it manually OR
   - Disconnect internet briefly

3. **Verify Fallback Appears:**
   - ✅ Should see "Authy Verification" screen
   - ✅ Phone number input field visible

4. **Complete Authy Flow:**
   - Enter phone number: `5551234567`
   - Click "Send Verification Code"
   - Check phone for SMS
   - Enter 6-digit code
   - Click "Verify Code"
   - ✅ Should login successfully

## 🎯 How It Works

```
User clicks OAuth → OAuth Fails → Authy Fallback → SMS Sent → Code Verified → Login ✅
```

### Visual Flow:

```
┌─────────────────┐
│   Try OAuth     │
│  (Google/etc)   │
└────────┬────────┘
         │
    ❌ Failed
         │
         ▼
┌─────────────────┐
│ Authy Fallback  │
│ "Enter Phone"   │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   SMS Sent      │
│ "Enter Code"    │
└────────┬────────┘
         │
         ▼
    ✅ Success!
```

## 📡 API Endpoints

### 1. Initiate Authy Fallback

```http
POST /api/auth/oauth/fallback/authy/

{
  "email": "user@example.com",
  "phone": "5551234567",
  "country_code": "1"
}
```

**Response:**
```json
{
  "success": true,
  "authy_id": "12345678",
  "requires_verification": true
}
```

### 2. Verify Authy Code

```http
POST /api/auth/oauth/fallback/authy/verify/

{
  "authy_id": "12345678",
  "token": "123456"
}
```

**Response:**
```json
{
  "success": true,
  "tokens": {
    "access": "jwt_access_token",
    "refresh": "jwt_refresh_token"
  },
  "user": {
    "id": 1,
    "email": "user@example.com"
  }
}
```

## 🔍 Troubleshooting

### "ModuleNotFoundError: No module named 'authy'"

**Solution:**
```bash
cd password_manager
pip install authy==2.2.6
```

### "AUTHY_API_KEY not configured"

**Solution:**
1. Check `password_manager/.env` file exists
2. Verify `AUTHY_API_KEY=...` is present
3. Restart Django server

### "Phone number required"

**Solution:**
- Enter phone number without spaces: `5551234567`
- Don't include country code in number (use separate field)

### "Invalid verification code"

**Solution:**
- Code expires after 10 minutes
- Click "Resend Code" to get new code
- Ensure correct code entered (6 digits)

### Fallback Not Appearing

**Solution:**
1. Check browser console for errors
2. Verify OAuth actually failed (not just closed popup)
3. Ensure backend is running
4. Check network tab for API responses

## 📊 Monitoring

### Check Logs

**Backend:**
```bash
# Watch for these log messages
tail -f password_manager/logs/django.log | grep "Authy"
```

You should see:
```
INFO: OAuth failed for user@example.com, initiating Authy fallback
INFO: Authy fallback initiated for user user@example.com
INFO: User user@example.com authenticated via Authy fallback
```

**Frontend:**
```javascript
// Check browser console for:
console.log('OAuth callback error:', error);
console.log('Fallback info:', fallbackInfo);
```

## 🎨 UI Customization

### Change Fallback Colors

Edit `frontend/src/Components/auth/OAuthCallback.jsx`:

```javascript
// Orange icon for fallback
<IconWrapper color="#FF9800">

// Change to your brand color:
<IconWrapper color="#YOUR_COLOR">
```

### Customize Messages

Edit button text:
```javascript
<Button onClick={handleAuthyFallback}>
  Send Verification Code  // Change this
</Button>
```

## 🚨 Important Notes

1. **Authy API Key Required:**
   - Fallback won't work without valid Authy API key
   - Get free key from Twilio

2. **User Must Exist:**
   - Fallback only works for existing users
   - New users must complete signup first

3. **Phone Number Needed:**
   - Users must provide valid phone number
   - SMS verification required

4. **Session-Based:**
   - Authy ID stored in session
   - Session expires after 1 hour

## 📚 Additional Resources

- **Full Documentation:** `OAUTH_AUTHY_FALLBACK_IMPLEMENTATION.md`
- **OAuth Setup:** `OAUTH_SETUP_GUIDE.md`
- **Authy Service:** `password_manager/auth_module/services/authy_service.py`
- **Frontend Service:** `frontend/src/services/oauthService.js`

## ✨ Features

✅ **Automatic Fallback** - No user configuration needed  
✅ **SMS Verification** - Industry-standard 2FA  
✅ **Session Management** - Secure temporary storage  
✅ **Error Handling** - Clear user feedback  
✅ **Mobile Friendly** - Responsive design  
✅ **Logging** - Full audit trail  
✅ **JWT Integration** - Seamless token flow  

## 🎯 Next Steps

1. ✅ Complete setup (above)
2. ✅ Test fallback flow
3. ⭐ **Optional:** Configure additional OAuth providers
4. ⭐ **Optional:** Add voice call fallback
5. ⭐ **Optional:** Enable push notifications

## 🤝 Support

### Common Questions

**Q: Does this work with all OAuth providers?**  
A: Yes, fallback activates for Google, GitHub, and Apple OAuth failures.

**Q: Can users skip OAuth and use Authy directly?**  
A: Not currently, but can be added as a feature.

**Q: Is Authy free?**  
A: Yes, Twilio provides free Authy API access.

**Q: What if Authy also fails?**  
A: User sees error message and can retry or use password login.

## 🎉 Success!

You now have a fully functional OAuth → Authy fallback system!

Test it by:
1. Trying OAuth login
2. Closing OAuth popup (simulating failure)
3. Seeing Authy fallback UI
4. Completing SMS verification

---

**Version:** 1.0  
**Date:** October 20, 2025  
**Status:** ✅ Ready to Use


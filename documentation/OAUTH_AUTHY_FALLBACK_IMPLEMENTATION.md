# OAuth → Authy Fallback Mechanism Implementation

## Overview

This document describes the implementation of an automatic fallback mechanism where Authy service is activated when OAuth authentication fails. This ensures users can still authenticate even if OAuth providers (Google, GitHub, Apple) are unavailable or experience issues.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Authentication Flow                      │
└─────────────────────────────────────────────────────────────┘

User Initiates Login
        │
        ▼
┌───────────────────┐
│  OAuth Attempt    │ ◄─── Try Google/GitHub/Apple
└───────────────────┘
        │
        ├───► Success ──────► JWT Tokens ──────► Login Complete
        │
        └───► Failure
                │
                ▼
        ┌───────────────────┐
        │  Check Fallback   │
        │    Available?     │
        └───────────────────┘
                │
                ├───► No ──────► Show Error ──────► Retry
                │
                └───► Yes
                        │
                        ▼
                ┌───────────────────┐
                │  Authy Fallback   │
                │  1. Enter Phone   │
                │  2. Receive SMS   │
                │  3. Enter Code    │
                └───────────────────┘
                        │
                        ▼
                JWT Tokens ──────► Login Complete
```

## Implementation Details

### 1. Backend Implementation

#### File: `password_manager/auth_module/oauth_views.py`

**Added Authy Integration:**
```python
from .services.authy_service import authy_service
from django.contrib.auth.models import User
```

**Enhanced Error Handling in OAuth Views:**

Each OAuth login class (Google, GitHub, Apple) now catches failures and returns fallback information:

```python
except Exception as e:
    logger.error(f"Google OAuth error: {str(e)}")
    
    # Try to get user info from the request to enable Authy fallback
    email = request.data.get('email') or request.GET.get('email')
    
    if email:
        # Trigger Authy fallback mechanism
        logger.info(f"OAuth failed for {email}, initiating Authy fallback")
        return Response({
            'success': False,
            'message': 'OAuth authentication failed',
            'error': str(e),
            'fallback_available': True,
            'fallback_method': 'authy',
            'email': email
        }, status=status.HTTP_401_UNAUTHORIZED)
```

**New Endpoints:**

1. **`/api/auth/oauth/fallback/authy/`** - Initiate Authy verification
   - **Method:** POST
   - **Parameters:** 
     - `email`: User's email address
     - `phone`: User's phone number
     - `country_code`: Phone country code (default: '1')
   - **Response:**
     ```json
     {
       "success": true,
       "message": "Authy verification initiated",
       "authy_id": "12345678",
       "requires_verification": true,
       "verification_method": "sms"
     }
     ```

2. **`/api/auth/oauth/fallback/authy/verify/`** - Verify Authy code
   - **Method:** POST
   - **Parameters:**
     - `authy_id`: Authy ID from initial request
     - `token`: Verification code from SMS
   - **Response:**
     ```json
     {
       "success": true,
       "message": "Authentication successful",
       "user": {
         "id": 1,
         "email": "user@example.com",
         "username": "user"
       },
       "tokens": {
         "access": "jwt_access_token",
         "refresh": "jwt_refresh_token"
       },
       "auth_method": "authy_fallback"
     }
     ```

#### File: `password_manager/auth_module/urls.py`

**Added Routes:**
```python
# OAuth Authy Fallback URLs
path('oauth/fallback/authy/', oauth_views.oauth_fallback_authy, name='oauth_fallback_authy'),
path('oauth/fallback/authy/verify/', oauth_views.verify_authy_fallback, name='verify_authy_fallback'),
```

### 2. Frontend Implementation

#### File: `frontend/src/services/oauthService.js`

**Added Methods:**

1. **`initiateAuthyFallback(email, phone, countryCode)`**
   - Sends request to initiate Authy verification
   - Returns Authy ID and verification status

2. **`verifyAuthyFallback(authyId, token)`**
   - Verifies the SMS code entered by user
   - Returns JWT tokens on success

3. **`handleOAuthFailure(error)`**
   - Parses error response from OAuth attempt
   - Checks if Authy fallback is available
   - Returns fallback information

```javascript
handleOAuthFailure(error) {
  const response = error.response?.data;
  
  if (response && response.fallback_available && response.fallback_method === 'authy') {
    return {
      fallbackAvailable: true,
      fallbackMethod: 'authy',
      email: response.email,
      message: response.message || 'OAuth failed. Authy fallback available.'
    };
  }

  return {
    fallbackAvailable: false,
    message: error.message || 'Authentication failed'
  };
}
```

#### File: `frontend/src/Components/auth/OAuthCallback.jsx`

**Enhanced UI:**

1. **New States:**
   - `status`: 'processing' | 'success' | 'error' | 'fallback'
   - `showAuthyFallback`: Boolean for showing fallback UI
   - `fallbackData`: Stores fallback information from OAuth failure
   - `phone`: User's phone number input
   - `authyCode`: SMS verification code input
   - `authyId`: Authy ID from backend

2. **New UI Components:**

   - **Phone Entry Form:**
     ```jsx
     <FallbackForm>
       <Input
         type="tel"
         placeholder="Phone Number (e.g., 5551234567)"
         value={phone}
         onChange={(e) => setPhone(e.target.value)}
       />
       <Button onClick={handleAuthyFallback}>
         Send Verification Code
       </Button>
     </FallbackForm>
     ```

   - **Code Verification Form:**
     ```jsx
     <FallbackForm>
       <Input
         type="text"
         placeholder="Enter 6-digit code"
         value={authyCode}
         onChange={(e) => setAuthyCode(e.target.value)}
         maxLength="7"
       />
       <Button onClick={handleVerifyAuthyCode}>
         Verify Code
       </Button>
       <Button onClick={resendCode}>
         Resend Code
       </Button>
     </FallbackForm>
     ```

## User Experience Flow

### Scenario 1: OAuth Success (Normal Flow)

1. User clicks "Sign in with Google/GitHub/Apple"
2. OAuth popup opens
3. User authenticates with provider
4. Redirect to callback page
5. Tokens stored, user logged in ✅

### Scenario 2: OAuth Fails → Authy Fallback

1. User clicks "Sign in with Google/GitHub/Apple"
2. OAuth popup opens
3. OAuth fails (provider unavailable, network issue, etc.)
4. **Callback detects failure** 🔄
5. **Authy fallback UI appears** with phone entry
6. User enters phone number
7. SMS sent with verification code
8. User enters code
9. Code verified, JWT tokens issued
10. User logged in ✅

### Scenario 3: OAuth & Authy Both Fail

1. OAuth attempt fails
2. Authy fallback initiated
3. User enters phone and code
4. Code verification fails (invalid code/expired)
5. Error message shown with retry option
6. User can:
   - Resend code
   - Try different phone number
   - Return to login page

## Error Handling

### Backend Errors

1. **User Not Found:**
   ```json
   {
     "success": false,
     "message": "User not found. Please sign up first.",
     "status": 404
   }
   ```

2. **Authy Service Failure:**
   ```json
   {
     "success": false,
     "message": "Failed to register with Authy service",
     "status": 500
   }
   ```

3. **Invalid Verification Code:**
   ```json
   {
     "success": false,
     "message": "Invalid verification code",
     "status": 401
   }
   ```

4. **Session Expired:**
   ```json
   {
     "success": false,
     "message": "Session expired. Please try again.",
     "status": 400
   }
   ```

### Frontend Error Handling

```javascript
try {
  const result = await oauthService.verifyAuthyFallback(authyId, authyCode);
  // Handle success
} catch (error) {
  setStatus('fallback');
  setMessage(
    error.response?.data?.message || 
    error.message || 
    'Invalid code. Please try again.'
  );
}
```

## Security Considerations

### 1. Session Management

- Authy ID and user ID stored in server-side session
- Session cleared after successful authentication
- Session expiration for added security

### 2. Rate Limiting

Recommended rate limits:
- **Initiate Authy:** 3 attempts per 5 minutes
- **Verify Code:** 5 attempts per 10 minutes
- **OAuth Attempts:** Existing OAuth rate limits apply

### 3. Data Protection

- Phone numbers never stored in logs
- Authy ID temporary and session-scoped
- JWT tokens used for authenticated sessions

### 4. Validation

- Email format validation
- Phone number format validation
- Verification code format (6-7 digits)
- Country code validation

## Configuration

### Environment Variables

#### Backend `.env`:
```env
# Authy API Configuration
AUTHY_API_KEY=your_authy_api_key_here

# OAuth Configuration
GOOGLE_OAUTH_CLIENT_ID=your_google_client_id
GOOGLE_OAUTH_CLIENT_SECRET=your_google_secret
GITHUB_OAUTH_CLIENT_ID=your_github_client_id
GITHUB_OAUTH_CLIENT_SECRET=your_github_secret

# Session Configuration
SESSION_COOKIE_AGE=3600  # 1 hour
SESSION_EXPIRE_AT_BROWSER_CLOSE=True
```

#### Frontend `.env.local`:
```env
VITE_API_URL=http://127.0.0.1:8000
```

### Django Settings

Add to `settings.py`:
```python
# Authy settings
AUTHY_API_KEY = os.environ.get('AUTHY_API_KEY', 'your_authy_api_key')

# Session settings for Authy fallback
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Strict'
SESSION_COOKIE_AGE = 3600  # 1 hour
```

## Testing

### Manual Testing

1. **Test OAuth Failure Detection:**
   - Disconnect internet during OAuth attempt
   - Use invalid OAuth credentials
   - Block OAuth provider domain

2. **Test Authy Fallback:**
   - Enter valid phone number
   - Verify SMS received
   - Enter correct code
   - Verify login success

3. **Test Error Scenarios:**
   - Invalid phone number format
   - Wrong verification code
   - Expired verification code
   - Multiple resend attempts

### Automated Testing

```python
# Backend Test
def test_oauth_fallback_authy(self):
    response = self.client.post('/api/auth/oauth/fallback/authy/', {
        'email': 'test@example.com',
        'phone': '5551234567',
        'country_code': '1'
    })
    
    self.assertEqual(response.status_code, 200)
    self.assertTrue(response.data['success'])
    self.assertIn('authy_id', response.data)
```

```javascript
// Frontend Test
test('handles OAuth fallback', async () => {
  const mockError = {
    response: {
      data: {
        fallback_available: true,
        fallback_method: 'authy',
        email: 'test@example.com'
      }
    }
  };
  
  const result = oauthService.handleOAuthFailure(mockError);
  expect(result.fallbackAvailable).toBe(true);
  expect(result.fallbackMethod).toBe('authy');
});
```

## Monitoring & Logging

### Backend Logging

```python
logger.info(f"OAuth failed for {email}, initiating Authy fallback")
logger.info(f"Authy fallback initiated for user {email}")
logger.info(f"User {user.email} authenticated via Authy fallback")
```

### Metrics to Track

1. **OAuth Failure Rate:** % of OAuth attempts that fail
2. **Fallback Usage Rate:** % of failures that use Authy fallback
3. **Fallback Success Rate:** % of Authy fallback attempts that succeed
4. **Average Fallback Time:** Time from OAuth failure to successful login
5. **Code Verification Attempts:** Number of code entry attempts per session

## Troubleshooting

### Common Issues

1. **"Authy API key not configured"**
   - **Solution:** Add `AUTHY_API_KEY` to `.env` file

2. **"Phone number required"**
   - **Solution:** Ensure phone number is provided in correct format (no spaces, dashes)

3. **"Session expired"**
   - **Solution:** User needs to restart OAuth process (session timeout occurred)

4. **"Invalid verification code"**
   - **Solution:** 
     - Check if code is still valid (not expired)
     - Verify user entered correct code
     - Try resending code

## Future Enhancements

### Planned Features

1. **Multiple Fallback Options:**
   - SMS fallback (current)
   - Voice call fallback
   - Email OTP fallback
   - Backup recovery codes

2. **Intelligent Fallback Selection:**
   - Auto-detect best fallback method
   - User preference storage
   - Fallback priority configuration

3. **Enhanced Security:**
   - Biometric verification on mobile
   - Device fingerprinting
   - Behavioral analysis

4. **Analytics Dashboard:**
   - Real-time fallback monitoring
   - Success/failure trends
   - User experience metrics

## Best Practices

1. **User Communication:**
   - Clear error messages
   - Explain why fallback is needed
   - Set expectations (SMS may take 30-60 seconds)

2. **Performance:**
   - Cache Authy service responses
   - Implement retry logic with exponential backoff
   - Use async operations where possible

3. **Accessibility:**
   - Screen reader support
   - Keyboard navigation
   - High contrast mode support

4. **Mobile Optimization:**
   - Auto-detect phone number from device
   - Auto-fill verification code from SMS
   - Touch-friendly input fields

## Conclusion

The OAuth → Authy fallback mechanism provides a robust authentication system that ensures users can always access their accounts, even when primary OAuth providers are unavailable. This implementation balances security, usability, and reliability.

---

**Document Version:** 1.0  
**Last Updated:** October 20, 2025  
**Status:** ✅ Production Ready


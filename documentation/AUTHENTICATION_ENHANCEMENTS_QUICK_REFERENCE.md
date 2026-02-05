# Authentication Enhancements - Quick Reference Guide

Quick reference for implementing the three authentication enhancements.

---

## 🔄 1. Refresh Token Family (JWT)

### Backend - Already Configured ✅

No action needed. The settings are already configured in `settings.py`:

```python
SIMPLE_JWT = {
    'REFRESH_TOKEN_ROTATE_ON_USE': True,
    'REFRESH_TOKEN_FAMILY_MAX_SIZE': 5,
}
```

### Frontend - Use Refresh Tokens

```javascript
// Token refresh is automatic, but if you need manual refresh:
import axios from 'axios';

const refreshAccessToken = async () => {
  try {
    const refreshToken = localStorage.getItem('refreshToken');
    const response = await axios.post('/api/auth/token/refresh/', {
      refresh: refreshToken
    });
    
    // Store new tokens
    localStorage.setItem('token', response.data.access);
    localStorage.setItem('refreshToken', response.data.refresh);
    
    // Update axios default header
    axios.defaults.headers.common['Authorization'] = `Bearer ${response.data.access}`;
  } catch (error) {
    // Refresh failed - redirect to login
    window.location.href = '/login';
  }
};
```

---

## 🌐 2. IP Whitelisting

### Enable IP Whitelisting

**In `.env` file:**

```env
# Enable the feature
IP_WHITELISTING_ENABLED=True

# Define allowed IPs
ALLOWED_IP_RANGES=192.168.1.0/24,10.0.0.0/8,203.0.113.100
```

### Common Configurations

```env
# Office network only
ALLOWED_IP_RANGES=203.0.113.0/24

# Multiple office locations
ALLOWED_IP_RANGES=203.0.113.0/24,198.51.100.0/24

# Office + specific remote IPs
ALLOWED_IP_RANGES=203.0.113.0/24,198.51.100.50,198.51.100.51

# Disable IP whitelisting
IP_WHITELISTING_ENABLED=False
```

### Testing IP Whitelist

```bash
# Check your current IP
curl https://api.ipify.org

# Test access
curl http://localhost:8000/api/vault/ \
  -H "Authorization: Bearer <YOUR_TOKEN>"

# Expected responses:
# - 200 OK (if IP is allowed)
# - 403 Forbidden (if IP is blocked)
```

---

## 🔐 3. Biometric Re-authentication

### Integration Guide

#### Step 1: Import Components

```javascript
import BiometricReauth from './Components/security/BiometricReauth';
import useBiometricReauth from './hooks/useBiometricReauth';
```

#### Step 2: Setup Hook

```javascript
function MyComponent() {
  const { 
    isReauthOpen, 
    operation, 
    requireReauth, 
    cancelReauth, 
    handleReauthSuccess 
  } = useBiometricReauth();
  
  // ... rest of component
}
```

#### Step 3: Protect Sensitive Operations

```javascript
const handleSensitiveOperation = async () => {
  // Actual sensitive operation
  await deleteSomething();
  console.log('Operation completed');
};

const requestOperation = () => {
  // Request re-authentication before operation
  requireReauth('delete this item', handleSensitiveOperation);
};
```

#### Step 4: Add Biometric Modal

```javascript
return (
  <div>
    {/* Your UI */}
    <button onClick={requestOperation}>
      Delete Account
    </button>

    {/* Biometric Re-auth Modal */}
    <BiometricReauth
      isOpen={isReauthOpen}
      onSuccess={handleReauthSuccess}
      onCancel={cancelReauth}
      operation={operation}
    />
  </div>
);
```

### Complete Examples

#### Example 1: Master Password Change

```javascript
import React, { useState } from 'react';
import BiometricReauth from '../security/BiometricReauth';
import useBiometricReauth from '../../hooks/useBiometricReauth';
import axios from 'axios';

function ChangeMasterPassword() {
  const [newPassword, setNewPassword] = useState('');
  const { 
    isReauthOpen, 
    operation, 
    requireReauth, 
    cancelReauth, 
    handleReauthSuccess 
  } = useBiometricReauth();

  const performPasswordChange = async () => {
    try {
      await axios.post('/api/auth/change-master-password/', {
        new_password: newPassword
      });
      alert('Master password changed successfully!');
    } catch (error) {
      alert('Failed to change password');
    }
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    requireReauth('change your master password', performPasswordChange);
  };

  return (
    <div>
      <form onSubmit={handleSubmit}>
        <input
          type="password"
          value={newPassword}
          onChange={(e) => setNewPassword(e.target.value)}
          placeholder="New Master Password"
        />
        <button type="submit">Change Password</button>
      </form>

      <BiometricReauth
        isOpen={isReauthOpen}
        onSuccess={handleReauthSuccess}
        onCancel={cancelReauth}
        operation={operation}
      />
    </div>
  );
}
```

#### Example 2: Account Deletion

```javascript
function DeleteAccount() {
  const { 
    isReauthOpen, 
    operation, 
    requireReauth, 
    cancelReauth, 
    handleReauthSuccess 
  } = useBiometricReauth();

  const performAccountDeletion = async () => {
    try {
      await axios.delete('/api/auth/delete-account/');
      // Redirect to goodbye page
      window.location.href = '/goodbye';
    } catch (error) {
      alert('Failed to delete account');
    }
  };

  const handleDelete = () => {
    const confirmed = window.confirm(
      'Are you absolutely sure? This action cannot be undone.'
    );
    if (confirmed) {
      requireReauth('delete your account', performAccountDeletion);
    }
  };

  return (
    <div>
      <button onClick={handleDelete} className="danger-button">
        Delete My Account
      </button>

      <BiometricReauth
        isOpen={isReauthOpen}
        onSuccess={handleReauthSuccess}
        onCancel={cancelReauth}
        operation={operation}
      />
    </div>
  );
}
```

#### Example 3: Recovery Key Generation

```javascript
function RecoveryKeySetup() {
  const [recoveryKey, setRecoveryKey] = useState('');
  const { 
    isReauthOpen, 
    operation, 
    requireReauth, 
    cancelReauth, 
    handleReauthSuccess 
  } = useBiometricReauth();

  const generateRecoveryKey = async () => {
    try {
      const response = await axios.post('/api/auth/generate-recovery-key/');
      setRecoveryKey(response.data.recovery_key);
    } catch (error) {
      alert('Failed to generate recovery key');
    }
  };

  const handleGenerate = () => {
    requireReauth('generate a recovery key', generateRecoveryKey);
  };

  return (
    <div>
      <button onClick={handleGenerate}>
        Generate Recovery Key
      </button>

      {recoveryKey && (
        <div className="recovery-key-display">
          <p>Save this recovery key in a safe place:</p>
          <code>{recoveryKey}</code>
        </div>
      )}

      <BiometricReauth
        isOpen={isReauthOpen}
        onSuccess={handleReauthSuccess}
        onCancel={cancelReauth}
        operation={operation}
      />
    </div>
  );
}
```

### Props Reference

#### BiometricReauth Component

| Prop | Type | Required | Description |
|------|------|----------|-------------|
| `isOpen` | boolean | Yes | Controls modal visibility |
| `onSuccess` | function | Yes | Called after successful authentication |
| `onCancel` | function | Yes | Called when user cancels |
| `operation` | string | No | Description of operation (e.g., "delete your account") |

#### useBiometricReauth Hook

| Return Value | Type | Description |
|-------------|------|-------------|
| `isReauthOpen` | boolean | Whether modal is open |
| `operation` | string | Current operation description |
| `requireReauth` | function | Request re-authentication |
| `cancelReauth` | function | Cancel re-authentication |
| `handleReauthSuccess` | function | Handle successful auth |

---

## 🎯 Operations That Should Use Biometric Re-auth

### High Priority ✅

- ✅ Change master password
- ✅ Delete account
- ✅ Generate recovery key
- ✅ Disable two-factor authentication
- ✅ Add/remove emergency contacts

### Medium Priority

- 🔄 Export vault data
- 🔄 Remove trusted devices
- 🔄 Change email address
- 🔄 Deactivate account

### Low Priority

- ⏳ Change avatar/profile picture
- ⏳ Update notification preferences
- ⏳ Change language settings

---

## 🐛 Troubleshooting

### Biometric Authentication Not Working

```javascript
// Check if biometrics are supported
if (window.PublicKeyCredential) {
  const available = await window.PublicKeyCredential
    .isUserVerifyingPlatformAuthenticatorAvailable();
  console.log('Biometric available:', available);
} else {
  console.log('WebAuthn not supported');
}
```

### IP Whitelisting Blocking Access

```python
# Temporarily disable in settings.py or .env
IP_WHITELISTING_ENABLED=False

# Or add your IP to whitelist
ALLOWED_IP_RANGES=your.ip.address.here
```

### Token Refresh Failing

```javascript
// Check token expiration
const token = localStorage.getItem('token');
if (token) {
  const payload = JSON.parse(atob(token.split('.')[1]));
  const expiresAt = new Date(payload.exp * 1000);
  console.log('Token expires at:', expiresAt);
}
```

---

## 📝 Checklist for Developers

When implementing biometric re-authentication:

- [ ] Import `BiometricReauth` component
- [ ] Import `useBiometricReauth` hook
- [ ] Setup hook in component
- [ ] Define sensitive operation function
- [ ] Wrap operation with `requireReauth()`
- [ ] Add modal to JSX
- [ ] Test biometric flow
- [ ] Test password fallback
- [ ] Test cancel flow

---

## 🚨 Common Mistakes to Avoid

1. **Don't forget the modal component:**
   ```javascript
   // ❌ Wrong - Missing modal
   const MyComponent = () => {
     const { requireReauth } = useBiometricReauth();
     return <button onClick={() => requireReauth('...', fn)}>Delete</button>;
   };
   
   // ✅ Correct - Modal included
   const MyComponent = () => {
     const { isReauthOpen, requireReauth, ... } = useBiometricReauth();
     return (
       <>
         <button onClick={() => requireReauth('...', fn)}>Delete</button>
         <BiometricReauth {...props} />
       </>
     );
   };
   ```

2. **Don't call the sensitive function directly:**
   ```javascript
   // ❌ Wrong - Direct call
   <button onClick={deleteSomething}>Delete</button>
   
   // ✅ Correct - Wrapped with requireReauth
   <button onClick={() => requireReauth('...', deleteSomething)}>Delete</button>
   ```

3. **Don't forget to handle promise rejection:**
   ```javascript
   // ✅ Good
   const sensitiveOp = async () => {
     try {
       await doSomething();
     } catch (error) {
       console.error('Operation failed:', error);
     }
   };
   ```

---

## 📚 Additional Resources

- Full documentation: `AUTHENTICATION_ENHANCEMENTS_IMPLEMENTED.md`
- Original recommendations: `AUTHENTICATION_ANALYSIS_AND_RECOMMENDATIONS.md`
- Component source: `frontend/src/Components/security/BiometricReauth.jsx`
- Hook source: `frontend/src/hooks/useBiometricReauth.js`

---

**Last Updated:** October 20, 2025  
**Version:** 1.0


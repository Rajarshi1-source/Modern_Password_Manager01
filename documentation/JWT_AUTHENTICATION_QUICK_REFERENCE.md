# ⚡ JWT Authentication Quick Reference

## 🎯 TL;DR

✅ **Django**: JWT-only authentication, no sessions for API  
✅ **React**: `useAuth` hook handles everything automatically  
✅ **Vite**: Proxy eliminates CORS issues  
✅ **Security**: Short-lived tokens, auto-refresh, no cookies  

---

## 🚀 Quick Start (30 Seconds)

### 1. Wrap Your App

```javascript
// main.jsx
import { AuthProvider } from './hooks/useAuth';

<AuthProvider>
  <App />
</AuthProvider>
```

### 2. Use Auth in Components

```javascript
import { useAuth } from '@/hooks/useAuth';

function MyComponent() {
  const { user, login, logout, isAuthenticated } = useAuth();
  
  const handleLogin = async () => {
    await login({ email: 'user@example.com', password: 'pass' });
  };
  
  return isAuthenticated ? (
    <div>Welcome {user.email} <button onClick={logout}>Logout</button></div>
  ) : (
    <button onClick={handleLogin}>Login</button>
  );
}
```

### 3. Make Authenticated Requests

```javascript
import axios from 'axios';

// Authorization header is added automatically!
const response = await axios.get('/api/vault/items/');
```

---

## 📝 API Endpoints

| Endpoint | Method | Purpose | Body |
|----------|--------|---------|------|
| `/api/token/` | POST | Login | `{ email, password }` |
| `/api/token/refresh/` | POST | Refresh token | `{ refresh }` |
| `/api/token/blacklist/` | POST | Logout | `{ refresh }` |

---

## 🔑 useAuth Hook API

### Properties

```javascript
const {
  user,               // User object { email, ... }
  isAuthenticated,    // Boolean
  isLoading,          // Boolean
  login,              // Function (credentials) => Promise
  logout,             // Function () => Promise
  refreshToken,       // Function () => Promise
  updateUser,         // Function (updates) => void
  getAccessToken,     // Function () => string
  getRefreshToken,    // Function () => string
} = useAuth();
```

### Methods

**login(credentials)**
```javascript
await login({ 
  email: 'user@example.com', 
  password: 'password' 
});
```

**logout()**
```javascript
await logout();
```

**refreshToken()**
```javascript
const newToken = await refreshToken();
```

---

## 🛠️ useAuthenticatedRequest Hook

```javascript
import { useAuthenticatedRequest } from '@/hooks/useAuth';

function MyComponent() {
  const { makeRequest, loading, error } = useAuthenticatedRequest();
  const [data, setData] = useState(null);
  
  useEffect(() => {
    makeRequest('get', '/api/vault/items/')
      .then(setData)
      .catch(console.error);
  }, []);
  
  if (loading) return <p>Loading...</p>;
  if (error) return <p>Error: {error.message}</p>;
  
  return <pre>{JSON.stringify(data, null, 2)}</pre>;
}
```

---

## 🔧 Configuration

### Django (settings.py)

```python
# JWT-only authentication
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ],
}

# CORS (no credentials for JWT)
CORS_ALLOW_CREDENTIALS = False
CORS_ALLOWED_ORIGINS = [
    "http://localhost:5173",  # Vite
]

# CSRF trusted origins
CSRF_TRUSTED_ORIGINS = [
    'http://localhost:5173',
]
```

### Vite (vite.config.js)

```javascript
server: {
  proxy: {
    '/api': {
      target: 'http://127.0.0.1:8000',
      changeOrigin: true,
      secure: false,
    },
  }
}
```

---

## 🚨 Troubleshooting

### 401 Unauthorized

```javascript
// Check token
localStorage.getItem('accessToken')

// Manual refresh
await fetch('/api/token/refresh/', {
  method: 'POST',
  body: JSON.stringify({ refresh: localStorage.getItem('refreshToken') })
})
```

### CORS Error

1. Check `CORS_ALLOWED_ORIGINS` includes frontend origin
2. Check Vite proxy is configured
3. Restart both servers

### Token Expired

- Access token expires in 15 minutes
- Refresh automatically on 401
- Refresh token expires in 7 days

---

## 📚 Common Patterns

### Protected Route

```javascript
import { useAuth } from '@/hooks/useAuth';
import { Navigate } from 'react-router-dom';

function ProtectedRoute({ children }) {
  const { isAuthenticated, isLoading } = useAuth();
  
  if (isLoading) return <div>Loading...</div>;
  if (!isAuthenticated) return <Navigate to="/login" />;
  
  return children;
}

// Usage
<Route path="/dashboard" element={
  <ProtectedRoute>
    <Dashboard />
  </ProtectedRoute>
} />
```

### Login Form

```javascript
import { useAuth } from '@/hooks/useAuth';
import { useState } from 'react';

function LoginForm() {
  const { login, isLoading } = useAuth();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState(null);
  
  const handleSubmit = async (e) => {
    e.preventDefault();
    try {
      await login({ email, password });
      // Redirect handled by app
    } catch (err) {
      setError(err.message);
    }
  };
  
  return (
    <form onSubmit={handleSubmit}>
      <input value={email} onChange={e => setEmail(e.target.value)} />
      <input type="password" value={password} onChange={e => setPassword(e.target.value)} />
      <button disabled={isLoading}>Login</button>
      {error && <p>{error}</p>}
    </form>
  );
}
```

### Fetch Data on Mount

```javascript
import { useAuth, useAuthenticatedRequest } from '@/hooks/useAuth';
import { useEffect, useState } from 'react';

function VaultItems() {
  const { makeRequest } = useAuthenticatedRequest();
  const [items, setItems] = useState([]);
  
  useEffect(() => {
    makeRequest('get', '/api/vault/items/')
      .then(setItems)
      .catch(console.error);
  }, []);
  
  return (
    <ul>
      {items.map(item => <li key={item.id}>{item.name}</li>)}
    </ul>
  );
}
```

### Manual API Call with Axios

```javascript
import axios from 'axios';

// Authorization header added automatically
const response = await axios.get('/api/vault/items/');
const items = response.data;

// POST request
await axios.post('/api/vault/items/', {
  name: 'New Item',
  username: 'user@example.com'
});
```

---

## 🔐 Security Checklist

- [x] JWT-only auth (no sessions for API)
- [x] Short-lived access tokens (15 min)
- [x] Refresh token rotation enabled
- [x] Token blacklisting on logout
- [x] CORS credentials disabled
- [x] HTTPS in production
- [x] Content Security Policy (CSP) configured
- [x] XSS protection (sanitize inputs)
- [x] Rate limiting enabled
- [x] Token storage (localStorage with CSP)

---

## 📦 Files Reference

| File | Purpose |
|------|---------|
| `password_manager/password_manager/settings.py` | Django JWT & CORS config |
| `frontend/vite.config.js` | Vite proxy config |
| `frontend/src/hooks/useAuth.js` | Auth hook implementation |
| `JWT_AUTHENTICATION_SETUP_COMPLETE.md` | Full documentation |

---

## ✅ Testing Commands

```bash
# Login
curl -X POST http://localhost:8000/api/token/ \
  -H "Content-Type: application/json" \
  -d '{"email":"user@example.com","password":"pass"}'

# Refresh
curl -X POST http://localhost:8000/api/token/refresh/ \
  -H "Content-Type: application/json" \
  -d '{"refresh":"<REFRESH_TOKEN>"}'

# Protected endpoint
curl http://localhost:8000/api/vault/items/ \
  -H "Authorization: Bearer <ACCESS_TOKEN>"
```

---

## 🎉 Summary

✅ **Zero Configuration** - Just wrap app with `AuthProvider`  
✅ **Automatic Refresh** - Handles 401 errors seamlessly  
✅ **Secure by Default** - JWT best practices built-in  
✅ **Developer Friendly** - Clean, modern React hooks API  
✅ **Production Ready** - Battle-tested patterns  

**Status**: ✅ **READY TO USE**  
**Version**: 1.0.0


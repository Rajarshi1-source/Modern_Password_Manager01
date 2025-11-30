# ML Dark Web Monitoring - Real-time Alerts Quick Start 🚀

## ⚡ 5-Minute Setup Guide

### Step 1: Install Dependencies

```bash
# Backend
pip install channels channels-redis daphne redis

# Start Redis
docker run -d -p 6379:6379 redis:7-alpine
```

### Step 2: Update Django Settings

Add to `password_manager/password_manager/settings.py`:

```python
INSTALLED_APPS = [
    # ... existing apps
    'channels',
]

ASGI_APPLICATION = 'password_manager.asgi.application'

CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels_redis.core.RedisChannelLayer',
        'CONFIG': {
            "hosts": [('127.0.0.1', 6379)],
        },
    },
}

CORS_ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://localhost:5173",
]
CORS_ALLOW_CREDENTIALS = True
```

### Step 3: Update ASGI Configuration

Update `password_manager/password_manager/asgi.py`:

```python
import os
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.security.websocket import AllowedHostsOriginValidator
from ml_dark_web.middleware import TokenAuthMiddlewareStack
from ml_dark_web.routing import websocket_urlpatterns

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'password_manager.settings')

django_asgi_app = get_asgi_application()

application = ProtocolTypeRouter({
    "http": django_asgi_app,
    "websocket": AllowedHostsOriginValidator(
        TokenAuthMiddlewareStack(
            URLRouter(websocket_urlpatterns)
            )
        )
    ),
})
```

### Step 4: Run Services

```bash
# Terminal 1: Django with Daphne
cd password_manager
daphne password_manager.asgi:application

# Terminal 2: Celery Worker
celery -A password_manager worker -l info

# Terminal 3: Frontend
cd frontend
npm run dev
```

### Step 5: Test It!

```bash
# Send a test alert
python manage.py test_breach_alert 1 --severity HIGH --confidence 0.95
```

Then:
1. Open browser: `http://localhost:5173`
2. Login
3. Navigate to `/security/breach-alerts`
4. Watch for the toast notification! 🎉

---

## 📁 What Was Created

### Frontend (React)
- ✅ `hooks/useBreachWebSocket.js` - WebSocket connection hook
- ✅ `Components/security/components/BreachAlertsDashboard.jsx` - Main dashboard
- ✅ `Components/security/components/BreachToast.jsx` - Toast notifications
- ✅ `Components/security/components/BreachAlertCard.jsx` - Alert cards
- ✅ `Components/security/components/BreachDetailModal.jsx` - Detail modal
- ✅ Route added to `App.jsx` at `/security/breach-alerts`

### Backend (Django)
- ✅ `ml_dark_web/consumers.py` - WebSocket consumer
- ✅ `ml_dark_web/routing.py` - URL routing
- ✅ `ml_dark_web/middleware.py` - Authentication middleware
- ✅ `ml_dark_web/management/commands/test_breach_alert.py` - Test command

---

## 🎯 Key Features

| Feature | Status |
|---------|--------|
| Real-time WebSocket alerts | ✅ |
| Toast notifications | ✅ |
| Dashboard with filters | ✅ |
| Mark as read | ✅ |
| Severity color coding | ✅ |
| Auto-reconnection | ✅ |
| Unread count badge | ✅ |
| Connection status | ✅ |
| Mobile responsive | ✅ |

---

## 🔍 Verify It's Working

### 1. Check WebSocket Connection
```javascript
// Browser Console
// Should see:
// "✓ WebSocket connected"
// "Connection established: Connected to ML-powered breach alert system"
```

### 2. Check Backend Logs
```bash
# Should see in Django logs:
# "User 1 connected to breach alerts WebSocket"
```

### 3. Send Test Alert
```bash
python manage.py test_breach_alert 1 --severity CRITICAL
```

You should see:
- Toast notification pop up (top-right)
- Alert appear in dashboard
- Unread count badge increment

---

## 🐛 Troubleshooting

### WebSocket won't connect?

```bash
# Check Redis
redis-cli ping  # Should return PONG

# Check Daphne is running
# Should see: "Listening on TCP address 0.0.0.0:8000"

# Check browser console for errors
```

### Alerts not appearing?

```bash
# Check Celery worker is running
# Should see: [worker: INFO/MainProcess] Ready.

# Verify channels layer
python manage.py shell
>>> from channels.layers import get_channel_layer
>>> print(get_channel_layer())  # Should NOT be None
```

---

## 📱 Usage

### Navigate to Dashboard
```
http://localhost:5173/security/breach-alerts
```

### What You'll See
- Live connection status indicator
- Unread count badge
- Filters (All, Unread, Critical/High)
- List of breach alerts
- Toast notifications for new alerts

### User Actions
- **View Details**: Click "View Details" button
- **Mark as Read**: Click "Mark as Read" button
- **Filter**: Click filter buttons at top
- **Dismiss Toast**: Click X on notification

---

## 🎨 Customization

### Change Toast Duration
```jsx
// In BreachAlertsDashboard.jsx
<BreachToast
  autoCloseDelay={10000}  // 10 seconds instead of 8
/>
```

### Change Reconnection Attempts
```javascript
// In useBreachWebSocket.js
const maxReconnectAttempts = 10;  // Default is 5
```

### Change Severity Colors
```javascript
// In any component
const severityColors = {
  CRITICAL: '#your-color',
  HIGH: '#your-color',
  MEDIUM: '#your-color',
  LOW: '#your-color'
};
```

---

## 📚 Full Documentation

For complete details, see:
- `ML_DARKWEB_REALTIME_ALERTS_COMPLETE.md` - Full implementation guide
- `frontend/src/Components/security/components/ML_DARKWEB_FRONTEND_SETUP.md` - Frontend setup
- `password_manager/ml_dark_web/README.md` - Backend architecture

---

## ✅ Quick Checklist

- [ ] Redis running (`redis-cli ping`)
- [ ] Django with Daphne (`daphne password_manager.asgi:application`)
- [ ] Celery worker running (`celery -A password_manager worker`)
- [ ] Frontend running (`npm run dev`)
- [ ] Test alert sent (`python manage.py test_breach_alert 1`)
- [ ] Toast notification appeared
- [ ] Dashboard shows alert
- [ ] WebSocket status shows "Live Monitoring"

---

## 🎉 You're Done!

The ML-powered real-time breach alert system is now **fully operational**!

Users will now receive instant notifications when their credentials are found in data breaches.

---

**Quick Start Version**: 1.0.0  
**Last Updated**: January 24, 2025  
**Status**: ✅ Production Ready


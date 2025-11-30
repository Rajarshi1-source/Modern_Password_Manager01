# ML Dark Web Monitoring - Frontend Setup Guide

## 📋 Overview

This guide covers the setup and integration of the ML-powered dark web monitoring frontend with real-time WebSocket breach alerts.

## 🎯 Features Implemented

### 1. **Real-time WebSocket Connection**
- Custom `useBreachWebSocket` hook for managing WebSocket connections
- Automatic reconnection with exponential backoff
- Keepalive ping/pong mechanism
- JWT/Token authentication support

### 2. **Toast Notifications**
- Real-time breach alert popups
- Severity-based color coding
- Auto-dismiss after 8 seconds
- Click to view detailed information

### 3. **Breach Alerts Dashboard**
- Comprehensive list of all breach alerts
- Filter by: All, Unread, Critical/High
- Real-time unread count badge
- Connection status indicator

### 4. **Alert Card Components**
- Individual breach alert cards
- Color-coded severity indicators
- Match confidence percentage
- Mark as read functionality

### 5. **Breach Details Modal**
- Full breach information display
- Recommended security actions
- Severity and confidence metrics
- Affected domain information

## 📦 Dependencies Required

```json
{
  "dependencies": {
    "react": "^18.2.0",
    "react-dom": "^18.2.0",
    "react-router-dom": "^7.5.2",
    "styled-components": "^6.1.17",
    "react-icons": "^5.5.0",
    "date-fns": "^2.30.0"
  }
}
```

## 🚀 Installation Steps

### 1. Install Dependencies

All required dependencies are already in your `package.json`. If you need to install them:

```bash
cd frontend
npm install
```

### 2. File Structure

The following files have been created:

```
frontend/src/
├── hooks/
│   └── useBreachWebSocket.js          # WebSocket connection hook
├── Components/
│   └── security/
│       └── components/
│           ├── BreachAlertsDashboard.jsx    # Main dashboard
│           ├── BreachToast.jsx              # Toast notifications
│           ├── BreachAlertCard.jsx          # Individual alert cards
│           └── BreachDetailModal.jsx        # Detailed alert view
```

### 3. Add Route to App.jsx

Add the breach alerts dashboard route to your `App.jsx`:

```jsx
import { lazy } from 'react';

// Lazy load the dashboard
const BreachAlertsDashboard = lazy(() => 
  import('./Components/security/components/BreachAlertsDashboard')
);

// In your Routes component:
<Route 
  path="/security/breach-alerts" 
  element={
    !isAuthenticated ? <Navigate to="/" /> : <BreachAlertsDashboard />
  } 
/>
```

### 4. Update Navigation

Add a link to the breach alerts dashboard in your navigation:

```jsx
<Link to="/security/breach-alerts" className="nav-link">
  Breach Alerts
</Link>
```

## 🔌 WebSocket Configuration

### Development Environment

The WebSocket hook automatically detects the environment:

- **Development**: Connects to `ws://localhost:8000/ws/breach-alerts/{userId}/?token={token}`
- **Production**: Connects to `wss://{host}/ws/breach-alerts/{userId}/?token={token}`

### Authentication

The WebSocket connection uses the authentication token from `localStorage`:

```javascript
const token = localStorage.getItem('token');
```

Make sure your login process stores the token properly.

## 🎨 Styling

All components use `styled-components` for styling. The color scheme follows your existing design:

- **Primary**: `#667eea` to `#764ba2` (gradient)
- **Success**: `#28a745`
- **Warning**: `#ffc107`
- **Danger**: `#dc3545`

## 📡 API Integration

### Endpoints Used

1. **Fetch Alerts**: `GET /api/ml-darkweb/breach_matches/`
2. **Mark as Read**: `POST /api/ml-darkweb/resolve_match/`

### Example API Call

```javascript
import ApiService from '../../../services/api';

// Fetch alerts
const response = await ApiService.api.get('/ml-darkweb/breach_matches/');

// Mark alert as read
await ApiService.api.post('/ml-darkweb/resolve_match/', {
  match_id: alertId
});
```

## 🧪 Testing

### Test WebSocket Connection

1. Start your Django server:
```bash
cd password_manager
python manage.py runserver
```

2. Send a test alert:
```bash
python manage.py test_breach_alert <user_id> --severity HIGH --confidence 0.95
```

3. Open the frontend and navigate to `/security/breach-alerts`
4. You should see the test alert appear in real-time!

### Test Without Backend

If the backend is not running, the dashboard will show:
- Connection status: "Disconnected"
- No alerts if none are cached
- Error tracking via `errorTracker`

## 🔧 Troubleshooting

### WebSocket Won't Connect

1. **Check Django Channels is running**:
   ```bash
   # Make sure you're using Daphne or channels runserver
   daphne password_manager.asgi:application
   ```

2. **Verify Redis is running**:
   ```bash
   redis-cli ping
   # Should respond with "PONG"
   ```

3. **Check browser console**:
   - Look for WebSocket connection errors
   - Verify the token is being sent correctly

### Alerts Not Appearing

1. **Check API endpoint**:
   - Open DevTools Network tab
   - Verify `/api/ml-darkweb/breach_matches/` returns data

2. **Check WebSocket messages**:
   - Open DevTools Console
   - Look for "New breach alert received" logs

3. **Verify user ID**:
   - Ensure `userId` is correctly extracted from localStorage
   - Check: `JSON.parse(localStorage.getItem('user')).id`

### Styling Issues

If styled-components aren't working:

1. **Check theme provider** (if you're using one):
   ```jsx
   <ThemeProvider theme={theme}>
     <BreachAlertsDashboard />
   </ThemeProvider>
   ```

2. **Verify styled-components version**:
   ```bash
   npm list styled-components
   ```

## 🎯 Usage Examples

### Basic Usage

```jsx
import BreachAlertsDashboard from './Components/security/components/BreachAlertsDashboard';

function App() {
  return (
    <div>
      <BreachAlertsDashboard />
    </div>
  );
}
```

### With Custom Styling

```jsx
import BreachAlertsDashboard from './Components/security/components/BreachAlertsDashboard';
import styled from 'styled-components';

const Container = styled.div`
  max-width: 1400px;
  margin: 0 auto;
  padding: 20px;
`;

function App() {
  return (
    <Container>
      <BreachAlertsDashboard />
    </Container>
  );
}
```

## 🔐 Security Considerations

1. **Token Security**:
   - Tokens are never logged in production
   - WebSocket URL hides token in console logs

2. **User Isolation**:
   - Users can only see their own alerts
   - Backend validates user ID matches token

3. **Error Handling**:
   - All errors are tracked via `errorTracker`
   - Graceful fallbacks for connection failures

## 📊 Performance Tips

1. **Lazy Loading**:
   - Dashboard is lazy-loaded to reduce initial bundle size
   - Use `React.lazy()` for optimal performance

2. **Memoization**:
   - Callbacks are memoized with `useCallback`
   - Consider memoizing alert cards if list is large

3. **WebSocket Management**:
   - Automatic cleanup on component unmount
   - Reconnection attempts limited to 5

## 🎨 Customization

### Change Toast Duration

In `BreachToast.jsx`:

```jsx
<BreachToast
  alert={alert}
  onClose={onClose}
  autoCloseDelay={10000}  // 10 seconds instead of 8
/>
```

### Change Severity Colors

In any component:

```javascript
const severityColors = {
  CRITICAL: '#your-color',
  HIGH: '#your-color',
  MEDIUM: '#your-color',
  LOW: '#your-color'
};
```

### Add Custom Filters

In `BreachAlertsDashboard.jsx`:

```jsx
const filteredAlerts = alerts.filter(alert => {
  if (filter === 'your-custom-filter') {
    return /* your condition */;
  }
  // ... existing filters
});
```

## 📚 Additional Resources

- [Django Channels Documentation](https://channels.readthedocs.io/)
- [WebSocket API MDN](https://developer.mozilla.org/en-US/docs/Web/API/WebSocket)
- [Styled Components](https://styled-components.com/)
- [React Icons](https://react-icons.github.io/react-icons/)

## ✅ Checklist

Before deploying to production:

- [ ] All dependencies installed
- [ ] WebSocket connection tested
- [ ] API endpoints configured correctly
- [ ] Error tracking integrated
- [ ] Toast notifications working
- [ ] Dashboard filters working
- [ ] Modal displays correctly
- [ ] Mark as read functionality works
- [ ] Mobile responsive design verified
- [ ] Browser compatibility tested

## 🚀 Next Steps

1. **Integrate with Security Dashboard**:
   - Add breach alert summary to main security dashboard
   - Show unread count in navigation

2. **Email Notifications**:
   - Send email alerts for critical breaches
   - Allow users to configure notification preferences

3. **Mobile App Integration**:
   - Implement push notifications for mobile
   - Create mobile-optimized UI

4. **Advanced Analytics**:
   - Add breach trend charts
   - Show breach statistics by severity
   - Display top affected domains

## 📞 Support

If you encounter issues:

1. Check this documentation first
2. Review browser console for errors
3. Check Django logs for backend issues
4. Verify Redis and Celery are running

---

**Created**: 2025-01-24
**Last Updated**: 2025-01-24
**Version**: 1.0.0


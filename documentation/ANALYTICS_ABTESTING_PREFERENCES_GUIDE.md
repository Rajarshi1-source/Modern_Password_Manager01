# Analytics, A/B Testing & User Preferences - Complete Guide

## 📋 Table of Contents
- [Overview](#overview)
- [Analytics Tracking](#analytics-tracking)
- [A/B Testing Framework](#ab-testing-framework)
- [User Preference Management](#user-preference-management)
- [API Reference](#api-reference)
- [Frontend Integration](#frontend-integration)
- [Best Practices](#best-practices)

---

## Overview

This guide covers three new feature systems that enhance the SecureVault password manager:

1. **Analytics Tracking**: Track user engagement, events, and behavior patterns
2. **A/B Testing Framework**: Run experiments and feature flags for controlled rollouts
3. **User Preference Management**: Comprehensive settings for theme, notifications, security, and more

---

## Analytics Tracking

### Architecture

The analytics system consists of:
- **Frontend Service**: `frontend/src/services/analyticsService.js`
- **Backend Models**: `password_manager/analytics/models.py`
- **API Endpoints**: `password_manager/analytics/views.py`

### Frontend Usage

#### Initialization

```javascript
import analyticsService from './services/analyticsService';

// Initialize with user context
await analyticsService.initialize({
  userId: user.id,
  email: user.email,
  sessionId: generateSessionId()
});
```

#### Track Events

```javascript
// Track page views
analyticsService.trackPageView('/dashboard');

// Track user actions
analyticsService.trackEvent('button_click', 'add_password', {
  location: 'vault_dashboard',
  itemType: 'password'
});

// Track feature usage
analyticsService.trackFeatureUsage('dark_web_monitoring', {
  scanType: 'full_vault',
  itemCount: 15
});

// Track errors
analyticsService.trackError(error, 'vault_encryption', {
  operation: 'encrypt_item',
  itemType: 'password'
});
```

#### Session Management

```javascript
// Start session
await analyticsService.startSession();

// End session
await analyticsService.endSession();
```

#### Conversion Tracking

```javascript
// Track conversion funnel
analyticsService.trackConversion('signup', {
  plan: 'premium',
  referrer: 'google'
});
```

### Backend Models

#### AnalyticsEvent
Stores individual analytics events:
- `event_type`: Type of event (e.g., 'page_view', 'button_click')
- `event_name`: Specific name/identifier
- `user`: ForeignKey to User
- `timestamp`: When the event occurred
- `session_id`: Session identifier
- `device_id`: Device fingerprint
- `platform`: Platform (web/mobile/desktop)
- `properties`: JSON field for custom data

#### UserEngagement
Aggregated user engagement metrics:
- `total_sessions`: Total number of sessions
- `total_session_duration`: Cumulative session time
- `average_session_duration`: Average session length
- `pages_viewed_per_session`: Average pages per session
- `items_created/updated/deleted`: Action counts
- `logins_count`: Total login count

### API Endpoints

#### POST `/api/analytics/track-event/`
Track an analytics event.

**Request:**
```json
{
  "event_type": "button_click",
  "event_name": "add_password_button",
  "properties": {
    "location": "vault_dashboard"
  },
  "session_id": "abc123",
  "device_id": "device456",
  "platform": "web",
  "page_url": "/dashboard",
  "referrer_url": "/",
  "user_agent": "Mozilla/5.0..."
}
```

**Response:**
```json
{
  "message": "Event tracked successfully"
}
```

#### GET `/api/analytics/engagement/`
Get user engagement metrics.

**Response:**
```json
{
  "total_sessions": 45,
  "total_session_duration": 18000,
  "average_session_duration": 400,
  "pages_viewed_per_session": 5.2,
  "items_created": 23,
  "items_updated": 15,
  "items_deleted": 3,
  "logins_count": 48,
  "last_login_at": "2024-01-15T10:30:00Z"
}
```

---

## A/B Testing Framework

### Architecture

The A/B testing system includes:
- **Frontend Service**: `frontend/src/services/abTestingService.js`
- **Backend Models**: `password_manager/ab_testing/models.py`
- **API Endpoints**: `password_manager/ab_testing/views.py`

### Frontend Usage

#### Initialization

```javascript
import abTestingService from './services/abTestingService';

// Initialize
await abTestingService.initialize({
  userId: user.id,
  deviceId: deviceFingerprint
});

// Fetch active experiments
await abTestingService.fetchActiveExperiments();
```

#### Feature Flags

```javascript
// Check if a feature is enabled
const isDarkWebMLEnabled = abTestingService.isFeatureEnabled('dark_web_ml_enhanced');

if (isDarkWebMLEnabled) {
  // Show ML-enhanced dark web monitoring
  showMLEnhancedDarkWebMonitoring();
} else {
  // Show standard dark web monitoring
  showStandardDarkWebMonitoring();
}
```

#### Experiment Variants

```javascript
// Get variant for an experiment
const variant = await abTestingService.getVariant('new_password_generator_ui');

if (variant === 'control') {
  // Show original UI
  renderOriginalPasswordGenerator();
} else if (variant === 'variant_a') {
  // Show new UI with strength meter on right
  renderVariantAPasswordGenerator();
} else if (variant === 'variant_b') {
  // Show new UI with strength meter below
  renderVariantBPasswordGenerator();
}

// Get variant configuration
const config = abTestingService.getVariantConfig('new_password_generator_ui');
console.log(config); // { showStrengthMeter: true, position: 'right' }
```

#### Track Experiment Events

```javascript
// Track when user sees the experiment
abTestingService.trackExperimentEvent('new_password_generator_ui', 'viewed');

// Track user actions in the experiment
abTestingService.trackExperimentEvent('new_password_generator_ui', 'generated_password', {
  length: 16,
  includeSymbols: true
});

// Track conversions
abTestingService.trackExperimentEvent('new_password_generator_ui', 'converted', {
  savedPassword: true
});
```

### Backend Models

#### FeatureFlag
Simple on/off switches for features:
- `name`: Unique name
- `description`: What the feature does
- `is_active`: Whether it's enabled globally

#### Experiment
A/B test configuration:
- `name`: Unique experiment name
- `description`: What's being tested
- `feature_flag`: Optional linked feature flag
- `start_date` / `end_date`: Time window
- `is_active`: Whether it's running
- `traffic_allocation`: % of users to include (0.0-1.0)

#### ExperimentVariant
Different versions in an experiment:
- `experiment`: ForeignKey to Experiment
- `name`: Variant name (e.g., 'Control', 'Variant A')
- `description`: What's different in this variant
- `payload`: JSON configuration for this variant
- `weight`: Relative weight for traffic distribution

#### UserExperimentAssignment
Tracks which variant each user sees:
- `user`: ForeignKey to User
- `experiment`: ForeignKey to Experiment
- `variant`: ForeignKey to ExperimentVariant
- `assigned_at`: When assigned

### API Endpoints

#### GET `/api/ab-testing/feature-flags/`
Get all active feature flags.

**Response:**
```json
{
  "dark_web_ml_enhanced": true,
  "new_dashboard_ui": false,
  "passkey_biometric": true
}
```

#### GET `/api/ab-testing/experiments/<experiment_name>/assign/`
Get user's assigned variant for an experiment.

**Response:**
```json
{
  "experiment_name": "new_password_generator_ui",
  "variant_name": "variant_a",
  "payload": {
    "showStrengthMeter": true,
    "position": "right",
    "colorScheme": "blue"
  },
  "assigned_at": "2024-01-15T10:30:00Z"
}
```

### Creating Experiments via Django Admin

1. Navigate to Django Admin → A/B Testing → Experiments
2. Click "Add Experiment"
3. Fill in:
   - **Name**: `new_dashboard_layout`
   - **Description**: "Testing new card-based dashboard layout"
   - **Traffic Allocation**: `0.5` (50% of users)
   - **Start Date**: Today
   - **Is Active**: ✓
4. Add Variants (inline):
   - **Control** (weight: 1.0)
     ```json
     {"layout": "list", "cardsPerRow": 1}
     ```
   - **Variant A** (weight: 1.0)
     ```json
     {"layout": "grid", "cardsPerRow": 3}
     ```
5. Save

Users will be automatically assigned when they first access the experiment.

---

## User Preference Management

### Architecture

The preference system includes:
- **Frontend Service**: `frontend/src/services/preferencesService.js`
- **Backend Model**: `password_manager/user/models.py` (UserPreferences)
- **API Endpoint**: `password_manager/user/views.py` (preferences view)

### Frontend Usage

#### Initialization

```javascript
import preferencesService from './services/preferencesService';

// Initialize (loads from localStorage and syncs with server)
await preferencesService.initialize();
```

#### Get Preferences

```javascript
// Get all preferences
const allPrefs = preferencesService.getAll();

// Get specific category
const themePrefs = preferencesService.get('theme');
console.log(themePrefs.mode); // 'dark', 'light', or 'auto'

// Get specific setting
const darkMode = preferencesService.get('theme', 'mode');
```

#### Set Preferences

```javascript
// Set single preference
await preferencesService.set('theme', 'mode', 'dark');

// Set multiple preferences in a category
await preferencesService.set('notifications', {
  enabled: true,
  browser: true,
  email: false,
  breachAlerts: true
});

// Bulk update
await preferencesService.update({
  theme: {
    mode: 'dark',
    primaryColor: '#4A6CF7'
  },
  security: {
    autoLockEnabled: true,
    autoLockTimeout: 300
  }
});
```

#### Reset Preferences

```javascript
// Reset specific category
await preferencesService.reset('theme');

// Reset all preferences
await preferencesService.reset();
```

#### Export/Import

```javascript
// Export preferences
const exportedData = await preferencesService.export();
// Download as JSON file

// Import preferences
const file = event.target.files[0];
await preferencesService.import(file);
```

#### Sync with Server

```javascript
// Manual sync (usually automatic)
await preferencesService.sync();
```

### Preference Categories

#### Theme
```javascript
{
  mode: 'dark',              // 'light', 'dark', 'auto'
  primaryColor: '#4A6CF7',
  fontSize: 16,
  fontFamily: 'Inter',
  compactMode: false,
  animations: true,
  highContrast: false
}
```

#### Notifications
```javascript
{
  enabled: true,
  browser: true,
  email: true,
  push: false,
  breachAlerts: true,
  securityAlerts: true,
  accountActivity: false,
  marketing: false,
  productUpdates: true,
  quietHoursEnabled: false,
  quietHoursStart: '22:00',
  quietHoursEnd: '08:00',
  sound: true,
  soundVolume: 0.7
}
```

#### Security
```javascript
{
  autoLockEnabled: true,
  autoLockTimeout: 300,        // seconds
  biometricAuth: true,
  twoFactorAuth: false,
  requireReauth: true,
  reauthTimeout: 3600,         // seconds
  clearClipboard: true,
  clipboardTimeout: 30,        // seconds
  defaultPasswordLength: 16,
  includeSymbols: true,
  includeNumbers: true,
  includeUppercase: true,
  includeLowercase: true,
  breachMonitoring: true,
  darkWebMonitoring: false
}
```

#### Privacy
```javascript
{
  analytics: true,
  errorReporting: true,
  performanceMonitoring: true,
  crashReports: true,
  usageData: false,
  keepLoginHistory: true,
  loginHistoryDays: 90,
  keepAuditLogs: true,
  auditLogDays: 365
}
```

#### UI/UX
```javascript
{
  language: 'en',
  dateFormat: 'MM/DD/YYYY',
  timeFormat: '12h',
  timezone: 'America/New_York',
  vaultView: 'grid',           // 'list', 'grid'
  sortBy: 'name',
  sortOrder: 'asc',
  groupBy: 'none',             // 'folder', 'type', 'none'
  showRecentItems: true,
  recentItemsCount: 10,
  showFavorites: true,
  showWeakPasswords: true,
  showBreachAlerts: true,
  sidebarCollapsed: false,
  sidebarPosition: 'left'      // 'left', 'right'
}
```

#### Accessibility
```javascript
{
  screenReader: false,
  reducedMotion: false,
  largeText: false,
  keyboardNavigation: true,
  focusIndicators: true,
  announceChanges: true
}
```

#### Advanced
```javascript
{
  developerMode: false,
  debugLogs: false,
  experimentalFeatures: false,
  betaFeatures: false,
  lazyLoading: true,
  cacheEnabled: true,
  offlineMode: false,
  autoSync: true,
  syncInterval: 300,           // seconds
  conflictResolution: 'server' // 'server', 'local', 'manual'
}
```

### Backend Model

#### UserPreferences
Comprehensive model storing all user settings:
- **Theme**: `theme_mode`, `theme_primary_color`, `theme_font_size`, etc.
- **Notifications**: `notifications_enabled`, `notifications_browser`, `notifications_email`, etc.
- **Security**: `security_auto_lock_enabled`, `security_auto_lock_timeout`, etc.
- **Privacy**: `privacy_analytics`, `privacy_error_reporting`, etc.
- **UI/UX**: `ui_language`, `ui_date_format`, `ui_vault_view`, etc.
- **Accessibility**: `accessibility_screen_reader`, `accessibility_reduced_motion`, etc.
- **Advanced**: `advanced_developer_mode`, `advanced_debug_logs`, etc.
- **Metadata**: `version`, `device_id`, `last_synced`, `created_at`, `updated_at`

### API Endpoint

#### GET `/api/user/preferences/`
Get current user's preferences.

**Response:**
```json
{
  "preferences": {
    "theme": {
      "mode": "dark",
      "primaryColor": "#4A6CF7",
      "fontSize": 16
      // ... other theme settings
    },
    "notifications": {
      "enabled": true,
      "browser": true
      // ... other notification settings
    }
    // ... other categories
  }
}
```

#### PUT `/api/user/preferences/`
Update user preferences.

**Request:**
```json
{
  "preferences": {
    "theme": {
      "mode": "dark"
    },
    "security": {
      "autoLockTimeout": 600
    }
  }
}
```

**Response:**
```json
{
  "message": "Preferences updated successfully",
  "preferences": {
    // ... full updated preferences
  }
}
```

---

## API Reference

### Analytics API

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/analytics/track-event/` | POST | Track an analytics event |
| `/api/analytics/engagement/` | GET | Get user engagement metrics |

### A/B Testing API

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/ab-testing/feature-flags/` | GET | Get all active feature flags |
| `/api/ab-testing/experiments/<name>/assign/` | GET | Get user's variant assignment |

### Preferences API

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/user/preferences/` | GET | Get user preferences |
| `/api/user/preferences/` | PUT | Update user preferences |

---

## Frontend Integration

### Example: Integrating Analytics in App.jsx

```javascript
import React, { useEffect } from 'react';
import analyticsService from './services/analyticsService';

function App() {
  useEffect(() => {
    // Initialize analytics on app load
    const initAnalytics = async () => {
      await analyticsService.initialize({
        userId: currentUser?.id,
        email: currentUser?.email
      });
      
      await analyticsService.startSession();
    };
    
    if (isAuthenticated) {
      initAnalytics();
    }
    
    // End session on unmount
    return () => {
      analyticsService.endSession();
    };
  }, [isAuthenticated, currentUser]);
  
  // Track page views on route change
  useEffect(() => {
    analyticsService.trackPageView(location.pathname);
  }, [location]);
  
  return (
    <div className="App">
      {/* Your app content */}
    </div>
  );
}
```

### Example: Using A/B Testing for Feature Rollout

```javascript
import React, { useEffect, useState } from 'react';
import abTestingService from './services/abTestingService';

function Dashboard() {
  const [useNewLayout, setUseNewLayout] = useState(false);
  
  useEffect(() => {
    const checkExperiment = async () => {
      await abTestingService.initialize({ userId: user.id });
      const variant = await abTestingService.getVariant('new_dashboard_layout');
      
      if (variant === 'variant_a') {
        setUseNewLayout(true);
        abTestingService.trackExperimentEvent('new_dashboard_layout', 'viewed');
      }
    };
    
    checkExperiment();
  }, []);
  
  return useNewLayout ? <NewDashboard /> : <OldDashboard />;
}
```

### Example: Applying User Preferences

```javascript
import React, { useEffect } from 'react';
import preferencesService from './services/preferencesService';

function ThemedApp() {
  useEffect(() => {
    const applyTheme = async () => {
      await preferencesService.initialize();
      
      const theme = preferencesService.get('theme');
      
      // Apply theme mode
      document.body.classList.toggle('dark-mode', theme.mode === 'dark');
      
      // Apply font size
      document.documentElement.style.fontSize = `${theme.fontSize}px`;
      
      // Apply animations
      if (!theme.animations) {
        document.body.classList.add('reduce-motion');
      }
    };
    
    applyTheme();
  }, []);
  
  return <div>{/* App content */}</div>;
}
```

---

## Best Practices

### Analytics

1. **Privacy First**: Always respect user privacy settings
   ```javascript
   if (preferencesService.get('privacy', 'analytics')) {
     analyticsService.trackEvent('action', 'details');
   }
   ```

2. **Meaningful Events**: Track events that provide actionable insights
   - ✓ Good: `button_click:add_password`, `feature_usage:dark_web_scan`
   - ✗ Bad: `mouse_move`, `scroll`

3. **Event Properties**: Include relevant context
   ```javascript
   analyticsService.trackEvent('password_generated', 'password_generator', {
     length: 16,
     includeSymbols: true,
     source: 'vault_form'
   });
   ```

4. **Error Tracking**: Always include context
   ```javascript
   try {
     await encryptData(data);
   } catch (error) {
     analyticsService.trackError(error, 'encryption', {
       operation: 'encrypt_vault_item',
       itemType: 'password'
     });
   }
   ```

### A/B Testing

1. **Single Variable**: Test one change at a time
   - ✓ Good: Test button color in isolation
   - ✗ Bad: Test button color + position + text simultaneously

2. **Statistical Significance**: Run tests until you have enough data
   - Minimum: 100 conversions per variant
   - Recommended: 1000+ conversions per variant

3. **Traffic Allocation**: Start conservatively
   ```python
   # Start with 10% traffic
   experiment.traffic_allocation = 0.1
   
   # Gradually increase if no issues
   experiment.traffic_allocation = 0.5
   ```

4. **Variant Configuration**: Use payload for flexibility
   ```python
   ExperimentVariant.objects.create(
     experiment=experiment,
     name='Variant A',
     payload={
       'buttonColor': '#4A6CF7',
       'buttonText': 'Add Password',
       'showIcon': True
     }
   )
   ```

### User Preferences

1. **Sensible Defaults**: Provide good default values
   ```javascript
   const defaultPreferences = {
     theme: { mode: 'auto', fontSize: 16 },
     security: { autoLockTimeout: 300 }
   };
   ```

2. **Validation**: Validate preference values
   ```javascript
   if (autoLockTimeout < 60 || autoLockTimeout > 3600) {
     throw new Error('Auto-lock timeout must be between 60-3600 seconds');
   }
   ```

3. **Sync Strategy**: Balance between local and server
   ```javascript
   // Save locally immediately for instant feedback
   localStorage.setItem('preferences', JSON.stringify(prefs));
   
   // Sync to server asynchronously
   await preferencesService.sync();
   ```

4. **Migration**: Handle preference version changes
   ```javascript
   if (prefs.version < 2) {
     prefs = migratePreferencesV1toV2(prefs);
   }
   ```

---

## Testing

### Analytics Testing

```javascript
// Mock analytics service in tests
jest.mock('./services/analyticsService');

test('tracks page view on navigation', () => {
  render(<Dashboard />);
  expect(analyticsService.trackPageView).toHaveBeenCalledWith('/dashboard');
});
```

### A/B Testing

```python
# Django test
def test_experiment_assignment(self):
    experiment = Experiment.objects.create(
        name='test_experiment',
        traffic_allocation=1.0
    )
    variant = ExperimentVariant.objects.create(
        experiment=experiment,
        name='Control'
    )
    
    response = self.client.get(f'/api/ab-testing/experiments/{experiment.name}/assign/')
    
    self.assertEqual(response.status_code, 201)
    self.assertEqual(response.data['variant_name'], 'Control')
```

### Preferences Testing

```javascript
test('updates theme preference', async () => {
  await preferencesService.set('theme', 'mode', 'dark');
  
  const mode = preferencesService.get('theme', 'mode');
  expect(mode).toBe('dark');
});
```

---

## Troubleshooting

### Analytics not tracking

1. Check privacy settings:
   ```javascript
   console.log(preferencesService.get('privacy', 'analytics')); // Should be true
   ```

2. Verify initialization:
   ```javascript
   console.log(analyticsService.isInitialized()); // Should be true
   ```

3. Check network requests in DevTools

### A/B test not assigning variant

1. Check experiment is active:
   ```python
   experiment.is_active = True
   experiment.save()
   ```

2. Verify traffic allocation:
   ```python
   print(experiment.traffic_allocation)  # Should be > 0
   ```

3. Check variants exist:
   ```python
   print(experiment.variants.count())  # Should be > 0
   ```

### Preferences not syncing

1. Check authentication:
   ```javascript
   console.log(axios.defaults.headers.common['Authorization']);
   ```

2. Verify endpoint:
   ```bash
   curl -H "Authorization: Bearer TOKEN" http://localhost:8000/api/user/preferences/
   ```

3. Check for sync errors:
   ```javascript
   preferencesService.getLastSyncError();
   ```

---

## Next Steps

1. **Create Settings UI**: Build React components for preference management
2. **Analytics Dashboard**: Create admin dashboard to visualize analytics data
3. **Experiment Results**: Build UI to view A/B test results and statistical significance
4. **Real-time Updates**: Implement WebSocket for live preference sync across devices

---

## Support

For questions or issues:
- Check the [GitHub Issues](https://github.com/your-repo/issues)
- Review the [API Documentation](./API_STANDARDS.md)
- Contact the development team

---

**Last Updated**: January 2024
**Version**: 1.0.0


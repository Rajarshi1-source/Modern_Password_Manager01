# Advanced Features - Quick Start Guide

**Get analytics, A/B testing, and preferences running in 5 minutes!**

## 🚀 Quick Setup

### 1. Backend Setup (2 minutes)

```bash
# Navigate to backend
cd password_manager

# Run migrations
python manage.py makemigrations analytics ab_testing user
python manage.py migrate

# Create superuser if not exists
python manage.py createsuperuser
```

### 2. Start Django Server

```bash
python manage.py runserver
```

### 3. Frontend Integration (3 minutes)

Add to your `App.jsx` or main component:

```javascript
import React, { useEffect } from 'react';
import analyticsService from './services/analyticsService';
import abTestingService from './services/abTestingService';
import preferencesService from './services/preferencesService';

function App() {
  const { currentUser, isAuthenticated } = useAuth();
  
  useEffect(() => {
    const initServices = async () => {
      if (!isAuthenticated || !currentUser) return;
      
      // 1. Initialize analytics
      await analyticsService.initialize({
        userId: currentUser.id,
        email: currentUser.email
      });
      await analyticsService.startSession();
      
      // 2. Initialize A/B testing
      await abTestingService.initialize({
        userId: currentUser.id
      });
      
      // 3. Initialize preferences
      await preferencesService.initialize();
      
      // Apply theme from preferences
      const theme = preferencesService.get('theme');
      document.body.classList.toggle('dark-mode', theme?.mode === 'dark');
    };
    
    initServices();
    
    return () => {
      analyticsService.endSession();
    };
  }, [isAuthenticated, currentUser]);
  
  return <YourAppContent />;
}
```

## 📊 Usage Examples

### Track Events

```javascript
// Track button clicks
<button onClick={() => {
  analyticsService.trackEvent('button_click', 'add_password');
  handleAddPassword();
}}>
  Add Password
</button>
```

### Feature Flags

```javascript
const showNewFeature = abTestingService.isFeatureEnabled('new_vault_ui');

{showNewFeature && <NewVaultUI />}
```

### User Preferences

```javascript
// Get preference
const darkMode = preferencesService.get('theme', 'mode') === 'dark';

// Set preference
await preferencesService.set('theme', 'mode', 'dark');
```

## 🎯 Create Your First A/B Test

### Via Django Admin

1. Go to `http://localhost:8000/admin/`
2. Navigate to **A/B Testing** → **Experiments**
3. Click **Add Experiment**
4. Fill in:
   - Name: `new_password_ui`
   - Description: "Testing new password generator UI"
   - Traffic Allocation: `0.5` (50%)
   - Is Active: ✓
5. Add Variants (inline):
   - **Control** (weight: 1.0)
   - **Variant A** (weight: 1.0) with payload:
     ```json
     {"showStrengthMeter": true, "position": "right"}
     ```
6. Save

### In Your Code

```javascript
const variant = await abTestingService.getVariant('new_password_ui');

if (variant === 'control') {
  return <OldPasswordGenerator />;
} else if (variant === 'variant_a') {
  const config = abTestingService.getVariantConfig('new_password_ui');
  return <NewPasswordGenerator config={config} />;
}
```

## ⚙️ Set Up Preferences UI (Optional)

Create a simple settings page:

```javascript
import React, { useState, useEffect } from 'react';
import preferencesService from './services/preferencesService';

function SettingsPage() {
  const [prefs, setPrefs] = useState({});
  
  useEffect(() => {
    setPrefs(preferencesService.getAll());
  }, []);
  
  const updateTheme = async (mode) => {
    await preferencesService.set('theme', 'mode', mode);
    setPrefs(preferencesService.getAll());
    document.body.classList.toggle('dark-mode', mode === 'dark');
  };
  
  return (
    <div>
      <h2>Settings</h2>
      
      <section>
        <h3>Theme</h3>
        <select 
          value={prefs.theme?.mode || 'auto'}
          onChange={(e) => updateTheme(e.target.value)}
        >
          <option value="light">Light</option>
          <option value="dark">Dark</option>
          <option value="auto">Auto</option>
        </select>
      </section>
      
      <section>
        <h3>Security</h3>
        <label>
          <input 
            type="checkbox"
            checked={prefs.security?.autoLockEnabled || false}
            onChange={(e) => preferencesService.set('security', 'autoLockEnabled', e.target.checked)}
          />
          Auto-lock vault
        </label>
        
        {prefs.security?.autoLockEnabled && (
          <input
            type="number"
            value={prefs.security?.autoLockTimeout || 300}
            onChange={(e) => preferencesService.set('security', 'autoLockTimeout', parseInt(e.target.value))}
            min="60"
            max="3600"
          />
        )}
      </section>
    </div>
  );
}
```

## 📈 View Analytics Data

### Via Django Admin

1. Go to `http://localhost:8000/admin/`
2. Navigate to **Analytics & Metrics** → **Analytics Events**
3. View tracked events with filters

### Via API

```javascript
// Get user engagement
const engagement = await fetch('/api/analytics/engagement/', {
  headers: {
    'Authorization': `Bearer ${token}`
  }
}).then(r => r.json());

console.log(engagement);
// {
//   total_sessions: 45,
//   average_session_duration: 400,
//   items_created: 23,
//   ...
// }
```

## 🧪 Testing

### Test Analytics

```javascript
import { render, screen } from '@testing-library/react';
import analyticsService from './services/analyticsService';

jest.mock('./services/analyticsService');

test('tracks page view', () => {
  render(<Dashboard />);
  expect(analyticsService.trackPageView).toHaveBeenCalledWith('/dashboard');
});
```

### Test A/B Testing

```javascript
test('shows variant A when assigned', async () => {
  abTestingService.getVariant.mockResolvedValue('variant_a');
  
  render(<PasswordGenerator />);
  
  await waitFor(() => {
    expect(screen.getByTestId('new-ui')).toBeInTheDocument();
  });
});
```

## 🎨 Advanced: Complete Settings Page

For a full-featured settings UI, create components for each preference category:

```
frontend/src/Components/settings/
├── SettingsPage.jsx           # Main settings container
├── ThemeSettings.jsx           # Theme preferences
├── NotificationSettings.jsx    # Notification preferences
├── SecuritySettings.jsx        # Security preferences
├── PrivacySettings.jsx         # Privacy preferences
└── PreferenceSection.jsx       # Reusable section component
```

Example structure:

```javascript
// SettingsPage.jsx
import React from 'react';
import { Tabs, Tab } from './ui/Tabs';
import ThemeSettings from './ThemeSettings';
import SecuritySettings from './SecuritySettings';
import NotificationSettings from './NotificationSettings';

export default function SettingsPage() {
  return (
    <div className="settings-page">
      <h1>Settings</h1>
      
      <Tabs>
        <Tab label="Theme">
          <ThemeSettings />
        </Tab>
        <Tab label="Security">
          <SecuritySettings />
        </Tab>
        <Tab label="Notifications">
          <NotificationSettings />
        </Tab>
      </Tabs>
    </div>
  );
}
```

## 🔒 Privacy Controls

Respect user privacy settings in analytics:

```javascript
// Check before tracking
if (preferencesService.get('privacy', 'analytics')) {
  analyticsService.trackEvent('action', 'details');
}

// Or use the built-in check
analyticsService.trackEvent('action', 'details'); // Automatically checks privacy setting
```

## 🚨 Common Issues

### "Analytics not tracking"
- Check: `preferencesService.get('privacy', 'analytics')` should be `true`
- Verify: `analyticsService.isInitialized()` returns `true`

### "A/B test not assigning"
- Ensure experiment is active in Django admin
- Check traffic allocation > 0
- Verify at least one variant exists

### "Preferences not syncing"
- Check authentication token is set
- Verify API endpoint is accessible
- Check browser console for errors

## 📚 Next Steps

1. **Read the full guide**: `ANALYTICS_ABTESTING_PREFERENCES_GUIDE.md`
2. **Build settings UI**: Create comprehensive preference management components
3. **Add analytics dashboard**: Visualize user engagement and behavior
4. **Monitor experiments**: Track A/B test results and make data-driven decisions

## 🆘 Support

- Full Documentation: `ANALYTICS_ABTESTING_PREFERENCES_GUIDE.md`
- API Reference: `API_STRUCTURE_SUMMARY.md`
- GitHub Issues: [Report bugs or request features]

---

**You're ready to go! Start tracking, testing, and personalizing your app.** 🎉

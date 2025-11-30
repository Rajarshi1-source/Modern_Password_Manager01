# 🎨 ML Security - React Integration Guide

## Quick Integration Checklist

- [ ] Add Password Strength Meter to Signup Form
- [ ] Add Session Monitor to Main App
- [ ] Import ML Service in App.jsx
- [ ] Test ML Components
- [ ] (Optional) Add to Password Change Form

---

## 📍 **Integration Point 1: Password Strength Meter in Signup**

### File: `frontend/src/App.jsx`

**Location:** Inside the `SignupForm` component, around **line 484-536**

**What to change:**

Replace the existing password strength indicator section with the ML version:

```jsx
// FIND THIS SECTION (around line 484):
<div className="form-group">
  <label htmlFor="signup-password">Master Password</label>

  {/* Password Strength Indicator */}
  <PasswordStrengthIndicator password={signupData.password} />

  <div style={{ position: 'relative' }}>
    <input
      type={passwordVisible ? "text" : "password"}
      // ... rest of input
    />
  </div>
</div>

// REPLACE WITH:
<div className="form-group">
  <label htmlFor="signup-password">Master Password</label>

  {/* ML-Powered Password Strength Indicator */}
  <PasswordStrengthMeterML password={signupData.password} />

  <div style={{ position: 'relative' }}>
    <input
      type={passwordVisible ? "text" : "password"}
      // ... rest of input
    />
  </div>
</div>
```

**Add import at the top of App.jsx (around line 1-20):**

```jsx
// Add this import with other component imports
import PasswordStrengthMeterML from './Components/security/PasswordStrengthMeterML';
```

---

## 📍 **Integration Point 2: Session Monitor in Main App**

### File: `frontend/src/App.jsx`

**Location:** Inside the `MainContent` function, after user logs in (around **line 906-930**)

**What to add:**

```jsx
// FIND THIS SECTION (around line 906):
return (
  <div className={appClassName}>
    <div id="main-content" tabIndex="-1">
      <nav className="app-nav">
        <h1>SecureVault</h1>
        <div className="nav-links">
          <Link to="/security/dashboard" className="nav-link">Security Dashboard</Link>
          <button onClick={handleLogout} className="logout-btn">Logout</button>
        </div>
      </nav>

      {/* ADD SESSION MONITOR HERE */}
      <SessionMonitor userId={user?.id || 'current_user'} />

      <main className="app-content">
        {/* Rest of your content */}
      </main>
    </div>
  </div>
);
```

**Add import at the top of App.jsx:**

```jsx
// Add this import with other component imports
import SessionMonitor from './Components/security/SessionMonitor';
```

**Alternative placement (less intrusive):** Add it in the header/nav area:

```jsx
<nav className="app-nav">
  <h1>SecureVault</h1>
  <div className="nav-links">
    <SessionMonitor userId={user?.id || 'current_user'} />
    <Link to="/security/dashboard" className="nav-link">Security Dashboard</Link>
    <button onClick={handleLogout} className="logout-btn">Logout</button>
  </div>
</nav>
```

---

## 📍 **Integration Point 3: ML Service Import**

### File: `frontend/src/App.jsx`

**Add at the top with other service imports (around line 14):**

```jsx
import ApiService from './services/api';
import toast from 'react-hot-toast';
import oauthService from './services/oauthService';
import mlSecurityService from './services/mlSecurityService';  // Add this line
```

---

## 🎨 **Styling the Session Monitor**

### File: `frontend/src/Components/security/SessionMonitor.css`

Create this new file with the styling:

```css
.session-monitor {
  background: var(--bg-secondary);
  border-radius: 8px;
  padding: 12px 16px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  display: flex;
  align-items: center;
  gap: 12px;
  transition: all 0.3s ease;
  border: 1px solid var(--border-color);
  max-width: 300px;
}

.session-monitor.anomaly-detected {
  border-color: var(--danger);
  background: var(--accent-light);
  animation: pulse 2s infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.8; }
}

.monitor-header {
  display: flex;
  align-items: center;
  gap: 8px;
}

.monitor-header h3 {
  font-size: 14px;
  margin: 0;
  font-weight: 600;
}

.monitor-status {
  font-size: 12px;
  color: var(--text-secondary);
  margin: 0;
}

.anomaly-details {
  background: var(--danger);
  color: white;
  padding: 8px 12px;
  border-radius: 6px;
  margin-top: 8px;
  display: flex;
  align-items: center;
  gap: 8px;
}

.anomaly-icon {
  font-size: 18px;
  animation: shake 0.5s infinite;
}

@keyframes shake {
  0%, 100% { transform: translateX(0); }
  25% { transform: translateX(-2px); }
  75% { transform: translateX(2px); }
}

.no-anomaly {
  color: var(--success);
  font-size: 13px;
  display: flex;
  align-items: center;
  gap: 6px;
  margin: 0;
}

.error-message {
  color: var(--danger);
  font-size: 12px;
  display: flex;
  align-items: center;
  gap: 6px;
}

.spinner {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

/* Compact version for navbar */
.session-monitor.compact {
  max-width: 200px;
  padding: 8px 12px;
}

.session-monitor.compact h3 {
  font-size: 12px;
}

.session-monitor.compact .monitor-status {
  display: none;
}
```

---

## 🎨 **Styling the Password Strength Meter ML**

### File: `frontend/src/Components/security/PasswordStrengthMeterML.css`

Create this new file:

```css
.password-strength-meter-ml {
  margin-bottom: 12px;
  padding: 12px;
  background: var(--bg-secondary);
  border-radius: 8px;
  border: 1px solid var(--border-color);
  transition: all 0.3s ease;
}

.strength-bar-container {
  width: 100%;
  height: 6px;
  background: var(--border-color);
  border-radius: 3px;
  overflow: hidden;
  margin-bottom: 8px;
}

.strength-bar {
  height: 100%;
  transition: width 0.5s ease, background-color 0.3s ease;
  border-radius: 3px;
}

.strength-label {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 14px;
  font-weight: 600;
  margin-bottom: 4px;
}

.strength-feedback {
  font-size: 12px;
  color: var(--text-secondary);
  margin: 4px 0 0 0;
  line-height: 1.4;
}

.error-message {
  color: var(--danger);
  font-size: 12px;
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px;
  background: var(--accent-light);
  border-radius: 6px;
  margin-top: 4px;
}

/* Loading state */
.password-strength-meter-ml p {
  margin: 0;
  padding: 4px 0;
}

/* Animation for strength bar */
@keyframes fillBar {
  from { width: 0%; }
}

.strength-bar {
  animation: fillBar 0.5s ease-out;
}
```

---

## 🧪 **Test Your Integration**

### Step 1: Start Frontend Dev Server
```bash
cd frontend
npm run dev
```

### Step 2: Test Password Strength Meter
1. Go to signup page
2. Start typing a password
3. You should see:
   - Real-time strength analysis
   - ML-powered score (0-100%)
   - Intelligent feedback

### Step 3: Test Session Monitor
1. Login to the app
2. Look for Session Monitor in the navbar or header
3. You should see:
   - "Session Security Monitor" indicator
   - Status updates every 60 seconds
   - Anomaly alerts (if detected)

---

## 🎯 **Advanced Integration (Optional)**

### Add to Password Change Form

If you have a password change form, add the ML meter there too:

```jsx
// In PasswordChangeForm component
import PasswordStrengthMeterML from '../security/PasswordStrengthMeterML';

<div className="form-group">
  <label>New Password</label>
  <PasswordStrengthMeterML password={newPassword} />
  <input
    type="password"
    value={newPassword}
    onChange={(e) => setNewPassword(e.target.value)}
  />
</div>
```

---

## 📊 **Viewing ML Data in Admin**

### Access Admin Panel

1. Navigate to: `http://127.0.0.1:8000/admin/`
2. Login with superuser credentials
3. Click "ML Security" section
4. View:
   - Password Strength Predictions
   - Anomaly Detection Logs
   - Threat Analysis Results
   - User Behavior Profiles
   - ML Model Metadata

### Create Superuser (if needed)

```bash
cd password_manager
python manage.py createsuperuser
```

---

## ✅ **Integration Checklist**

After integration, verify:

- [ ] Password strength meter appears in signup form
- [ ] ML predictions show realistic scores
- [ ] Feedback messages are helpful
- [ ] Session monitor appears after login
- [ ] No console errors in browser
- [ ] API calls succeed (check Network tab)
- [ ] CSS styling looks good
- [ ] Mobile responsive (if applicable)

---

## 🐛 **Troubleshooting**

### Issue: "Cannot find module './Components/security/PasswordStrengthMeterML'"
**Solution:** Ensure the file path is correct. Check if files exist:
- `frontend/src/Components/security/PasswordStrengthMeterML.jsx`
- `frontend/src/Components/security/SessionMonitor.jsx`

### Issue: API returns 401 Unauthorized
**Solution:** 
- For password strength: Works without auth initially
- For session monitor: Requires JWT token
- Check if `Authorization: Bearer <token>` header is set

### Issue: Component not rendering
**Solution:**
1. Check browser console for errors
2. Verify imports are correct
3. Check if parent component is rendering
4. Use React DevTools to inspect component tree

### Issue: Styling looks wrong
**Solution:**
1. Ensure CSS files are imported
2. Check CSS variable definitions in App.css
3. Clear browser cache
4. Check for CSS conflicts

---

## 📞 **Need Help?**

Check the documentation:
- `ML_SECURITY_README.md` - Full API documentation
- `ML_SECURITY_QUICK_START.md` - Quick setup guide
- `SETUP_ML_SECURITY.md` - Detailed setup instructions

---

**🎉 Your ML Security System is now integrated!**


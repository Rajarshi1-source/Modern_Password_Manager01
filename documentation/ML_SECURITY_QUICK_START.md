# ML Security Quick Start Guide

## 5-Minute Setup

### 1. Install Dependencies (2 minutes)

```bash
cd password_manager
pip install tensorflow scikit-learn numpy pandas joblib
```

### 2. Run Migrations (1 minute)

```bash
python manage.py makemigrations ml_security
python manage.py migrate ml_security
```

### 3. Test Basic Functionality (2 minutes)

```bash
# Start Django shell
python manage.py shell

# Test password strength prediction
from ml_security.ml_models.password_strength import PasswordStrengthPredictor
predictor = PasswordStrengthPredictor()
result = predictor.predict("MyP@ssw0rd!2024")
print(result)

# Test anomaly detection
from ml_security.ml_models.anomaly_detector import AnomalyDetector
detector = AnomalyDetector()
session_data = {
    'session_duration': 300,
    'typing_speed': 45,
    'vault_accesses': 5,
    'device_consistency': 0.95
}
anomaly_result = detector.detect_anomaly(session_data)
print(anomaly_result)
```

## Frontend Integration (5 minutes)

### 1. Add Password Strength Meter to Signup

```jsx
// In your signup form component
import PasswordStrengthMeterML from './Components/security/PasswordStrengthMeterML';

// Inside your form
<div className="form-group">
  <label>Password</label>
  <input
    type="password"
    value={password}
    onChange={(e) => setPassword(e.target.value)}
  />
  <PasswordStrengthMeterML 
    password={password}
    showRecommendations={true}
  />
</div>
```

### 2. Add Session Monitoring to Main App

```jsx
// In App.jsx
import SessionMonitor from './Components/security/SessionMonitor';

function App() {
  return (
    <div className="App">
      {/* Your app content */}
      
      {/* Add session monitor */}
      {isAuthenticated && (
        <SessionMonitor enabled={true} interval={60000} />
      )}
    </div>
  );
}
```

## API Usage Examples

### Password Strength

```javascript
// Using fetch API
const response = await fetch('http://localhost:8000/api/ml-security/password-strength/predict/', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
  },
  body: JSON.stringify({
    password: 'MyPassword123!',
    save_prediction: true
  })
});

const result = await response.json();
console.log(result.strength);  // "strong"
console.log(result.confidence);  // 0.92
console.log(result.recommendations);  // Array of recommendations
```

### Anomaly Detection

```javascript
// Using axios
import axios from 'axios';

const sessionData = {
  session_duration: 300,
  typing_speed: 45.5,
  vault_accesses: 5,
  device_consistency: 0.95,
  location_consistency: 0.88
};

const response = await axios.post(
  'http://localhost:8000/api/ml-security/anomaly/detect/',
  { session_data: sessionData },
  { headers: { 'Authorization': `Bearer ${token}` } }
);

console.log(response.data.is_anomaly);  // false
console.log(response.data.severity);  // "low"
```

## Training Models (Optional)

### Password Strength Model

```bash
# Generate 10,000 training samples and train for 50 epochs
python ml_security/training/train_password_strength.py --samples 10000 --epochs 50

# Quick training (5,000 samples, 30 epochs) - ~10 minutes
python ml_security/training/train_password_strength.py --samples 5000 --epochs 30
```

## Common Use Cases

### 1. Real-time Password Validation

```jsx
const [passwordStrength, setPasswordStrength] = useState(null);

const handlePasswordChange = async (e) => {
  const pwd = e.target.value;
  setPassword(pwd);
  
  // Predict strength in real-time
  const result = await mlSecurityService.predictPasswordStrength(pwd);
  setPasswordStrength(result);
};

// Show warning if password is weak
{passwordStrength && passwordStrength.strength === 'weak' && (
  <div className="warning">
    ⚠️ Weak password! {passwordStrength.recommendations[0]}
  </div>
)}
```

### 2. Session Security Monitoring

```jsx
useEffect(() => {
  if (!isAuthenticated) return;
  
  // Check session every minute
  const interval = setInterval(async () => {
    const sessionData = mlSecurityService.collectSessionData();
    const result = await mlSecurityService.detectSessionAnomaly(sessionData);
    
    if (result.is_anomaly && result.severity === 'high') {
      // Show security alert
      alert('Unusual activity detected. Please verify your identity.');
      // Trigger MFA or logout
    }
  }, 60000);
  
  return () => clearInterval(interval);
}, [isAuthenticated]);
```

### 3. Threat-based Access Control

```jsx
const handleSensitiveAction = async () => {
  // Analyze threat before allowing sensitive action
  const sessionData = mlSecurityService.collectSessionData();
  const behaviorData = mlSecurityService.collectBehaviorData();
  const threat = await mlSecurityService.analyzeThreat(sessionData, behaviorData);
  
  if (threat.risk_level > 50) {
    // Require additional authentication
    setShowMFAModal(true);
  } else {
    // Proceed with action
    performSensitiveAction();
  }
};
```

## Customization

### Adjust Anomaly Detection Sensitivity

```python
# In ml_security/ml_models/anomaly_detector.py
self.isolation_forest = IsolationForest(
    contamination=0.05,  # Lower = fewer anomalies detected (default: 0.1)
    # ... other params
)
```

### Modify Threat Risk Thresholds

```python
# In ml_security/ml_models/threat_analyzer.py
def _get_action_for_risk(self, risk_score: int) -> str:
    if risk_score >= 80:  # Adjust threshold (default: 90)
        return 'block'
    # ... etc
```

## Monitoring

### View Predictions in Django Admin

1. Go to `http://localhost:8000/admin/`
2. Navigate to "ML Security" section
3. View:
   - Password Strength Predictions
   - Anomaly Detections
   - Threat Predictions
   - User Behavior Profiles

### Check Model Status

```bash
python manage.py shell

from ml_security.models import MLModelMetadata
models = MLModelMetadata.objects.all()
for m in models:
    print(f"{m.model_type}: v{m.version}, accuracy={m.accuracy}")
```

## Troubleshooting

### Issue: "ML model not available"
**Solution**: Models will use rule-based fallback. To enable ML:
```bash
pip install tensorflow scikit-learn
```

### Issue: "Module 'ml_security' not found"
**Solution**: Ensure app is in INSTALLED_APPS:
```python
# password_manager/settings.py
INSTALLED_APPS = [
    # ...
    'ml_security',
]
```

### Issue: High API response time
**Solution**: 
- Models load once on startup (initial request may be slow)
- Subsequent requests are fast (~50-200ms)
- Consider caching predictions for identical inputs

## Performance Tips

1. **Use Batch Analysis**: Combine multiple checks in one API call
   ```javascript
   // Instead of 3 separate calls:
   const result = await mlSecurityService.batchAnalyzeSession({
     password: pwd,
     session_data: sessionData,
     behavior_data: behaviorData
   });
   ```

2. **Debounce Password Predictions**: Don't predict on every keystroke
   ```javascript
   const debouncedPredict = debounce(predictPasswordStrength, 500);
   ```

3. **Cache User Profiles**: Behavior profiles update slowly
   ```javascript
   // Cache profile for 5 minutes
   const cachedProfile = localStorage.getItem('behavior_profile');
   if (cachedProfile && Date.now() - cachedProfile.timestamp < 300000) {
     return JSON.parse(cachedProfile.data);
   }
   ```

## Next Steps

1. ✅ Basic Setup Complete
2. 📊 Train models with your data (optional)
3. 🎨 Customize UI components
4. 🔧 Adjust sensitivity thresholds
5. 📈 Monitor predictions in admin
6. 🚀 Deploy to production

## Production Considerations

- [ ] Train models with real user data (not synthetic)
- [ ] Set up model retraining pipeline
- [ ] Configure proper rate limiting
- [ ] Enable model performance monitoring
- [ ] Set up alerting for high-risk threats
- [ ] Regular model evaluation and updates

## Support

Questions? Check:
- Full documentation: `ML_SECURITY_README.md`
- API docs: `http://localhost:8000/docs/`
- Django admin: `http://localhost:8000/admin/ml_security/`


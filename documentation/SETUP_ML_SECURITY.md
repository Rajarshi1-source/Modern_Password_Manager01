# ML Security Setup Instructions

## Complete Setup Guide

Follow these steps to set up the ML security system in your password manager.

## Step 1: Install ML Dependencies

```bash
cd password_manager
pip install -r ml_security/requirements_ml.txt
```

**Required packages:**
- tensorflow >= 2.13.0
- scikit-learn >= 1.3.0
- numpy >= 1.24.0
- pandas >= 2.0.0
- joblib >= 1.3.0

**Time estimate:** 5-10 minutes (depending on internet speed)

## Step 2: Verify Django Settings

The ML security app has already been added to your `settings.py`:

```python
INSTALLED_APPS = [
    # ... other apps ...
    'ml_security',  # ✅ Already added
]
```

And URLs have been configured in `password_manager/urls.py`:

```python
urlpatterns = [
    # ... other patterns ...
    path('api/ml-security/', include('ml_security.urls')),  # ✅ Already added
]
```

## Step 3: Create Database Tables

Run Django migrations to create ML security database tables:

```bash
# From password_manager directory
python manage.py makemigrations ml_security
python manage.py migrate ml_security
```

This creates 6 new tables:
- `ml_security_passwordstrengthprediction`
- `ml_security_userbehaviorprofile`
- `ml_security_anomalydetection`
- `ml_security_threatprediction`
- `ml_security_mlmodelmetadata`
- `ml_security_mltrainingdata`

**Time estimate:** 30 seconds

## Step 4: Test ML Models

```bash
python manage.py shell
```

```python
# Test Password Strength Predictor
from ml_security.ml_models.password_strength import PasswordStrengthPredictor
predictor = PasswordStrengthPredictor()
result = predictor.predict("MyP@ssw0rd!2024")
print(f"Strength: {result['strength']}, Confidence: {result['confidence']}")

# Test Anomaly Detector
from ml_security.ml_models.anomaly_detector import AnomalyDetector
detector = AnomalyDetector()
session_data = {'session_duration': 300, 'typing_speed': 45}
anomaly_result = detector.detect_anomaly(session_data)
print(f"Is Anomaly: {anomaly_result['is_anomaly']}")

# Test Threat Analyzer
from ml_security.ml_models.threat_analyzer import ThreatAnalyzer
analyzer = ThreatAnalyzer()
print("Threat analyzer initialized successfully!")
```

**Expected output:**
```
Strength: strong, Confidence: 0.89
Is Anomaly: False
Threat analyzer initialized successfully!
```

**Time estimate:** 1 minute

## Step 5: Start Django Server

```bash
python manage.py runserver
```

## Step 6: Test API Endpoints

Open a new terminal and test the endpoints:

```bash
# Test password strength prediction (no auth required)
curl -X POST http://localhost:8000/api/ml-security/password-strength/predict/ \
  -H "Content-Type: application/json" \
  -d '{"password": "TestP@ssw0rd123!"}'

# Expected response:
# {
#   "success": true,
#   "strength": "strong",
#   "confidence": 0.92,
#   "features": {...},
#   "recommendations": [...]
# }
```

**Time estimate:** 1 minute

## Step 7: Install Frontend Dependencies (if needed)

```bash
cd frontend
npm install lodash  # For debounce in PasswordStrengthMeterML
npm install react-icons  # For icons in SessionMonitor
```

**Time estimate:** 1 minute

## Step 8: Test Frontend Integration

### Option A: Quick Test

Add to your signup component:

```jsx
import PasswordStrengthMeterML from './Components/security/PasswordStrengthMeterML';

// In your password input
<PasswordStrengthMeterML 
    password={password}
    showRecommendations={true}
/>
```

### Option B: Full Integration

See `ML_SECURITY_QUICK_START.md` for complete integration examples.

**Time estimate:** 5-10 minutes

## Step 9: Create Superuser and Explore Admin

```bash
python manage.py createsuperuser
# Follow prompts to create admin account
```

Then visit: `http://localhost:8000/admin/ml_security/`

You can view:
- Password strength predictions
- Anomaly detections
- Threat predictions
- User behavior profiles
- ML model metadata

**Time estimate:** 2 minutes

## Step 10: (Optional) Train Models with Your Data

```bash
# Train password strength model with synthetic data
python ml_security/training/train_password_strength.py --samples 10000 --epochs 50
```

**Note:** For production, you should train with real data after collecting sufficient samples.

**Time estimate:** 30-60 minutes (depending on your hardware)

## Troubleshooting

### Issue: TensorFlow Installation Fails

**Windows:**
```bash
pip install tensorflow-cpu  # If you don't have GPU
```

**Mac M1/M2:**
```bash
pip install tensorflow-macos
pip install tensorflow-metal
```

**Linux:**
```bash
pip install tensorflow  # Should work out of the box
```

### Issue: "No module named 'ml_security'"

**Solution:**
```bash
# Ensure you're in the right directory
cd password_manager

# Check if app is in INSTALLED_APPS
python manage.py check ml_security
```

### Issue: Migration Errors

**Solution:**
```bash
# Delete migration files and recreate
rm ml_security/migrations/0001_initial.py
python manage.py makemigrations ml_security
python manage.py migrate ml_security
```

### Issue: High Memory Usage

**Solution:** Models load into memory on startup. Reduce memory by:
1. Using smaller LSTM units (edit `ml_models/password_strength.py`)
2. Using fewer estimators in Random Forest (edit `ml_models/anomaly_detector.py`)
3. Reducing temporal sequence length in threat analyzer

### Issue: Slow API Responses

**Solution:**
- First request loads models (slower)
- Subsequent requests are fast (~50-200ms)
- Consider Redis caching for frequently accessed predictions

## Verification Checklist

- [ ] ML dependencies installed
- [ ] Migrations run successfully
- [ ] Models can be imported in Python shell
- [ ] Django server starts without errors
- [ ] API endpoint returns predictions
- [ ] Frontend components render correctly
- [ ] Django admin shows ML security section
- [ ] No console errors in browser

## Quick Command Reference

```bash
# Install dependencies
pip install -r ml_security/requirements_ml.txt

# Run migrations
python manage.py makemigrations ml_security
python manage.py migrate ml_security

# Start server
python manage.py runserver

# Train model (optional)
python ml_security/training/train_password_strength.py

# Django shell
python manage.py shell

# Create superuser
python manage.py createsuperuser
```

## Next Steps

1. ✅ Complete setup steps above
2. 📖 Read `ML_SECURITY_README.md` for detailed documentation
3. 🚀 Review `ML_SECURITY_QUICK_START.md` for usage examples
4. 🎨 Integrate React components into your UI
5. 📊 Monitor predictions in Django admin
6. 🔧 Customize thresholds and sensitivity
7. 🚢 Deploy to production

## Production Deployment

Before deploying to production:

1. **Train with Real Data**: Replace synthetic training data with actual user data
2. **Set Secure Keys**: Use environment variables for secret keys
3. **Enable HTTPS**: All ML endpoints should use HTTPS
4. **Configure Rate Limiting**: Adjust throttle rates in `views.py`
5. **Set Up Monitoring**: Monitor model performance and API response times
6. **Enable Logging**: Configure logging for ML predictions
7. **Backup Models**: Regularly backup trained model files
8. **Schedule Retraining**: Set up periodic model retraining

## Support & Documentation

- **Implementation Summary**: `ML_SECURITY_IMPLEMENTATION_SUMMARY.md`
- **Full Documentation**: `ML_SECURITY_README.md`
- **Quick Start Guide**: `ML_SECURITY_QUICK_START.md`
- **API Documentation**: `http://localhost:8000/docs/`
- **Django Admin**: `http://localhost:8000/admin/ml_security/`

## Estimated Total Setup Time

- **Minimum (basic functionality)**: 15-20 minutes
- **Complete (with testing)**: 30-45 minutes
- **Full (with model training)**: 1-2 hours

---

**You're all set! The ML security system is now ready to protect your password manager with advanced machine learning.** 🛡️✨


# 🔐 ML Security Admin Panel Setup Guide

Complete guide to accessing and using the ML Security admin interface.

---

## 📋 **Quick Start**

### Step 1: Create Superuser (if not already done)

```bash
cd password_manager
python manage.py createsuperuser
```

Follow the prompts:
- Username: `admin`
- Email: `admin@example.com` 
- Password: (choose a strong password)
- Password (again): (confirm)

---

### Step 2: Access Admin Panel

1. **Start Django Server** (if not running):
   ```bash
   python manage.py runserver
   ```

2. **Open Admin Panel**:
   - Navigate to: `http://127.0.0.1:8000/admin/`
   - Login with superuser credentials

3. **Find ML Security Section**:
   - Look for "ML SECURITY" section in the admin sidebar
   - Click to expand

---

## 📊 **Admin Features**

### 1. Password Strength Predictions

**Path:** `ML Security > Password strength predictions`

**What you'll see:**
- User who submitted the password
- SHA256 hash of password (for privacy)
- Strength score (0.0 to 1.0)
- Feedback message
- Prediction model used
- Timestamp

**Filters:**
- By prediction model
- By date created
- By strength score range

**Search:**
- By username
- By feedback text

**Actions:**
- Export to CSV
- Delete old predictions

---

### 2. Anomaly Detection Logs

**Path:** `ML Security > Anomaly detection logs`

**What you'll see:**
- User associated with event
- Event type (login, vault_access, etc.)
- Event data (JSON)
- Is anomaly (Yes/No)
- Anomaly score
- Model used (IsolationForest or RandomForest)
- Detection timestamp
- Resolved status

**Filters:**
- By is_anomaly (Yes/No)
- By model used
- By event type
- By resolved status

**Search:**
- By username
- By event data

**Actions:**
- Mark as resolved
- Export anomaly reports
- View detailed event data

---

### 3. Threat Analysis Results

**Path:** `ML Security > Threat analysis results`

**What you'll see:**
- User who triggered analysis
- Analysis type (login_behavior, session_activity)
- Input features (JSON)
- Threat score (0.0 to 1.0)
- Is threat (Yes/No)
- Recommended action
- Model used (Hybrid_CNN_LSTM)
- Analysis timestamp

**Filters:**
- By is_threat (Yes/No)
- By model used
- By analysis type

**Search:**
- By username
- By recommended action

**Actions:**
- Export threat reports
- View detailed analysis
- Generate security reports

---

### 4. ML Model Metadata

**Path:** `ML Security > ML model metadata`

**What you'll see:**
- Model name
- Version
- Description
- Last trained date
- Accuracy metrics (accuracy, precision, recall, F1-score)
- Model file path
- Is active (Yes/No)
- Created/Updated timestamps

**Features:**
- Track model versions
- Compare model performance
- Activate/deactivate models
- View training history

---

## 🎯 **Common Admin Tasks**

### Task 1: View Recent Password Strength Predictions

1. Go to `ML Security > Password strength predictions`
2. Click "Date created" column to sort by newest
3. View recent predictions and strength scores

### Task 2: Investigate Anomalies

1. Go to `ML Security > Anomaly detection logs`
2. Filter by `is_anomaly = Yes`
3. Click on an anomaly to see details
4. Review event data and user information
5. Mark as resolved if legitimate

### Task 3: Review Threat Detections

1. Go to `ML Security > Threat analysis results`
2. Filter by `is_threat = Yes`
3. Check recommended actions
4. Take appropriate security measures

### Task 4: Export Security Reports

1. Select the model results you want to export
2. Choose entries using checkboxes
3. Select "Export selected..." from Actions dropdown
4. Click "Go"
5. Download CSV file

### Task 5: Monitor Model Performance

1. Go to `ML Security > ML model metadata`
2. Check accuracy metrics for each model
3. Compare current vs previous versions
4. Identify models needing retraining

---

## 📈 **Understanding the Data**

### Password Strength Scores

| Score Range | Category | Meaning |
|-------------|----------|---------|
| 0.0 - 0.3 | Very Weak | Easily guessable, common patterns |
| 0.3 - 0.6 | Moderate | Acceptable but can be improved |
| 0.6 - 0.8 | Strong | Good security, meets requirements |
| 0.8 - 1.0 | Very Strong | Excellent security, hard to crack |

### Anomaly Scores

| Score Range | Risk Level | Action |
|-------------|------------|--------|
| 0.0 - 0.3 | Low | Normal behavior |
| 0.3 - 0.6 | Medium | Monitor for patterns |
| 0.6 - 0.8 | High | Investigate immediately |
| 0.8 - 1.0 | Critical | Take immediate action |

### Threat Scores

| Score Range | Threat Level | Recommended Action |
|-------------|--------------|-------------------|
| 0.0 - 0.3 | Low | Continue monitoring |
| 0.3 - 0.5 | Medium | Verify user identity |
| 0.5 - 0.7 | High | Prompt for MFA |
| 0.7 - 1.0 | Critical | Lock account, notify user |

---

## 🛡️ **Security Best Practices**

### 1. Regular Monitoring
- Check anomaly logs daily
- Review threat detections weekly
- Monitor model performance monthly

### 2. Data Privacy
- Password hashes are stored (never plaintext)
- Event data is encrypted
- Access admin panel over HTTPS in production

### 3. Model Management
- Keep models up-to-date
- Retrain with new data quarterly
- Test model accuracy regularly

### 4. Incident Response
- Investigate all critical threats immediately
- Document anomaly resolutions
- Update security policies based on ML insights

---

## 🔧 **Customizing the Admin**

### Add Custom Filters

Edit `password_manager/ml_security/admin.py`:

```python
@admin.register(AnomalyDetection)
class AnomalyDetectionAdmin(admin.ModelAdmin):
    list_filter = (
        'is_anomaly',
        'model_used',
        'event_type',
        'resolved',
        ('detected_at', admin.DateFieldListFilter),  # Add date filter
        ('anomaly_score', admin.RangeFilter),  # Add score range filter
    )
```

### Add Custom Actions

```python
@admin.register(ThreatAnalysisResult)
class ThreatAnalysisResultAdmin(admin.ModelAdmin):
    actions = ['mark_as_reviewed', 'send_alert']
    
    def mark_as_reviewed(self, request, queryset):
        count = queryset.update(reviewed=True)
        self.message_user(request, f'{count} threats marked as reviewed.')
    mark_as_reviewed.short_description = "Mark selected as reviewed"
```

### Customize Display

```python
@admin.register(PasswordStrengthPrediction)
class PasswordStrengthPredictionAdmin(admin.ModelAdmin):
    list_display = (
        'user',
        'strength_score_display',  # Custom method
        'timestamp',
        'prediction_model'
    )
    
    def strength_score_display(self, obj):
        if obj.strength_score >= 0.8:
            color = 'green'
        elif obj.strength_score >= 0.5:
            color = 'orange'
        else:
            color = 'red'
        return format_html(
            '<span style="color: {};">{:.2%}</span>',
            color,
            obj.strength_score
        )
    strength_score_display.short_description = 'Strength'
```

---

## 📊 **Dashboard Widgets (Optional)**

### Install Django Admin Dashboard

```bash
pip install django-admin-interface
```

Add to `INSTALLED_APPS` in `settings.py`:

```python
INSTALLED_APPS = [
    'admin_interface',
    'colorfield',
    'django.contrib.admin',
    # ... rest of your apps
]
```

Run migrations:

```bash
python manage.py migrate admin_interface
```

---

## 🐛 **Troubleshooting**

### Issue: Can't access admin panel

**Solution:**
1. Verify server is running: `python manage.py runserver`
2. Check URL: `http://127.0.0.1:8000/admin/` (note the trailing slash)
3. Clear browser cookies and try again

### Issue: ML Security section not visible

**Solution:**
1. Check `ml_security` is in `INSTALLED_APPS`
2. Run migrations: `python manage.py migrate ml_security`
3. Restart Django server

### Issue: No data in admin

**Solution:**
- Data is only created when ML APIs are called
- Test the APIs to generate sample data
- Use the test script: `python test_ml_apis.py`

### Issue: Permission denied

**Solution:**
1. Ensure you're logged in as superuser
2. Check user permissions in admin
3. Grant ML Security permissions to specific users

---

## 📞 **Admin Panel URLs**

| URL | Description |
|-----|-------------|
| `/admin/` | Main admin dashboard |
| `/admin/ml_security/` | ML Security overview |
| `/admin/ml_security/passwordstrengthprediction/` | Password predictions |
| `/admin/ml_security/anomalydetection/` | Anomaly logs |
| `/admin/ml_security/threatanalysisresult/` | Threat analysis |
| `/admin/ml_security/mlmodelmetadata/` | Model metadata |
| `/admin/ml_security/userbehaviorprofile/` | User profiles |

---

## 🎉 **You're All Set!**

Your ML Security admin panel is ready to use. Start monitoring your application's security with AI-powered insights!

### Quick Tips:
- Check anomaly logs daily
- Review threat detections immediately
- Monitor model performance weekly
- Export reports for compliance
- Train models with real data

**Need help?** Check the other documentation files or review the code in `ml_security/admin.py`


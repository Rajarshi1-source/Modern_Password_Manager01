# Performance Monitoring - Quick Start Guide 🚀

## 5-Minute Setup

### 1. Install Dependencies (2 minutes)

```bash
cd password_manager
pip install psutil scikit-learn pandas numpy joblib safety pip-audit
```

### 2. Run Migrations (1 minute)

```bash
python manage.py makemigrations shared
python manage.py migrate
```

### 3. Start Server (30 seconds)

```bash
python manage.py runserver
```

### 4. Test It! (1 minute)

```bash
# Check system health
curl http://localhost:8000/api/performance/system-health/

# Check dependencies
python manage.py check_dependencies
```

---

## That's It! ✅

Performance monitoring is now active and tracking:
- ✅ All API requests
- ✅ Database queries
- ✅ System resources (CPU, Memory, Disk)
- ✅ Errors and exceptions

---

## View Performance Data

### Admin Dashboard

Visit: `http://localhost:8000/admin/`

Look for:
- `Performance Metrics`
- `System Metrics`
- `Error Logs`
- `Performance Alerts`

### API Endpoints (Admin Only)

```bash
# Get your admin token first
TOKEN="your_admin_token_here"

# Performance summary
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/api/performance/summary/

# System health
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/api/performance/system-health/

# Slow endpoints
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/api/performance/endpoints/

# Database performance
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/api/performance/database/

# Errors
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/api/performance/errors/
```

---

## Frontend Performance (Optional)

The enhanced performance monitor is already integrated!

To enable auto-reporting to backend, add this to your React app:

```javascript
import { performanceMonitor } from './services/performanceMonitor';

// In your App.jsx or main component:
useEffect(() => {
  // Enable auto-reporting every 60 seconds
  performanceMonitor.enableAutoReporting('/api/performance/frontend/');
  
  return () => {
    performanceMonitor.disableAutoReporting();
  };
}, []);
```

---

## Check for Vulnerabilities

```bash
# Check dependencies for security vulnerabilities
python manage.py check_dependencies

# Save results to database
python manage.py check_dependencies --save
```

---

## ML Models (Optional)

Train ML models after collecting some data (100+ requests):

```python
from ml_security.ml_models.performance_optimizer import performance_optimizer

# Train models
results = performance_optimizer.train_all_models()

# Get optimization recommendations
recommendations = performance_optimizer.generate_optimization_recommendations()
for rec in recommendations:
    print(f"[{rec['severity']}] {rec['title']}")
```

---

## Configuration (Optional)

Create `.env` file in `password_manager/` directory:

```env
# Performance Monitoring
STORE_PERFORMANCE_METRICS=True
STORE_API_METRICS=True
SLOW_REQUEST_THRESHOLD=1.0
QUERY_COUNT_THRESHOLD=50

# System Resource Thresholds
CPU_WARNING_THRESHOLD=80
MEMORY_WARNING_THRESHOLD=80
DISK_WARNING_THRESHOLD=80
```

---

## Troubleshooting

### "No module named 'psutil'"
```bash
pip install psutil scikit-learn pandas numpy joblib
```

### "No migrations to apply"
```bash
python manage.py makemigrations shared
python manage.py migrate
```

### "Permission denied" for performance endpoints
- These endpoints require admin access
- Login as admin or superuser

---

## What's Next?

1. Let the app run for a few hours to collect data
2. Check the performance summary API
3. Review any alerts in the admin dashboard
4. Train ML models after collecting 100+ requests
5. Set up automated dependency checks (cron job)

---

## Need Help?

See the full documentation: `PERFORMANCE_MONITORING_COMPLETE.md`

---

**That's it! You're all set! 🎉**


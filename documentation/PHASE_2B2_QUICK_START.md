# Phase 2B.2 Quick Start Guide 🚀

## 3-Step Deployment

### Step 1: Apply Migrations (2 minutes)

```bash
cd password_manager
python manage.py makemigrations behavioral_recovery
python manage.py migrate
```

**Expected**: Creates `RecoveryFeedback`, `RecoveryPerformanceMetric`, `RecoveryAuditLog` models

---

### Step 2: Initialize A/B Tests (1 minute)

```bash
python manage.py shell
```

```python
from behavioral_recovery.ab_tests.recovery_experiments import create_recovery_experiments
create_recovery_experiments()
exit()
```

**Expected**: Creates 3 experiments (recovery_time_duration, similarity_threshold, challenge_frequency)

---

### Step 3: Access Dashboard (30 seconds)

1. Start your servers:
   ```bash
   # Terminal 1: Django
   python manage.py runserver

   # Terminal 2: React
   cd ../frontend
   npm start
   ```

2. Navigate to: `http://localhost:3000/admin/metrics`

3. Login as admin

4. View your metrics dashboard!

---

## ✅ That's It!

You're now collecting metrics and running A/B tests!

---

## 📊 What Happens Next?

1. **Automatic**: A/B tests assign variants to users
2. **Automatic**: Metrics collect as users recover
3. **Manual**: Review dashboard weekly
4. **After 3-6 months**: Analyze results for Phase 2B.3

---

## 📚 Full Documentation

- **Setup Guide**: `PHASE_2B2_IMPLEMENTATION_SUMMARY.md`
- **Technical Docs**: `PHASE_2B2_EVALUATION_FRAMEWORK_COMPLETE.md`
- **Troubleshooting**: See main docs

---

## 🆘 Quick Troubleshooting

**Migrations fail?**
- Check if models already exist in database
- Try: `python manage.py migrate --fake behavioral_recovery`

**A/B tests not creating?**
- Check if `ab_testing` app required but missing
- Framework works without it (graceful fallback)

**Dashboard empty?**
- Need at least 1 completed recovery for data
- Check admin permissions
- Verify API endpoint: `/api/behavioral-recovery/metrics/summary/`

---

**Next**: Run some test recoveries, wait a few days, check metrics! 🎉


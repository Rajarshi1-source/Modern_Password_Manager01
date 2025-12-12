# 🔧 Suppress Warnings & Fix Errors - Complete Guide

**Status**: All issues have solutions  
**Priority**: Low (these don't prevent the system from running)

---

## 📋 Issue Summary

| Issue | Type | Severity | Fix Available |
|-------|------|----------|---------------|
| `pkg_resources` deprecated | Warning | Low | ✅ Yes |
| Duplicate model registration | Warning | Medium | ✅ Yes |
| TensorFlow oneDNN info | Info | None | ✅ Yes (suppress) |
| Keras `input_length` deprecated | Warning | Low | ✅ Yes |
| Threat analyzer model error | Error | Medium | ✅ Yes |
| liboqs-python not available | Info (Dev) | Low | ✅ Auto-suppressed in dev |
| pqcrypto not available | Info (Dev) | Low | ✅ Auto-suppressed in dev |
| concrete-python not available | Info (Dev) | Low | ✅ Auto-suppressed in dev |
| ab_testing app not found | Warning | Low | ✅ Yes |

---

## 🔇 Automatic Warning Suppression (Development Mode)

In **local development** (DEBUG=True, not in Docker), crypto library warnings are **automatically suppressed**.

### Why These Warnings Exist

1. **liboqs-python**: Requires compiling the liboqs C library (Linux-specific)
2. **pqcrypto**: Requires native compilation (Linux-specific)  
3. **concrete-python**: Only works on Linux x86_64 (FHE library)

### When Warnings Appear

| Environment | Crypto Warnings |
|-------------|-----------------|
| Local dev (Windows/Mac) | **Suppressed** ✅ |
| Docker (Linux) | Libraries installed, no warnings |
| Production (Linux) | Libraries installed, no warnings |

### Manual Override

To see suppressed warnings in development:
```bash
# Set environment variable
set DEBUG=False  # Windows
export DEBUG=False  # Linux/Mac
```

---

## 🔧 Permanent Fixes

### Fix 1: Suppress pkg_resources Warning (djangorestframework-simplejwt)

**File**: `password_manager/password_manager/settings.py`

Add at the top of the file:

```python
# Suppress pkg_resources deprecation warning
import warnings
warnings.filterwarnings('ignore', category=UserWarning, module='rest_framework_simplejwt')
```

**OR** upgrade to latest version:

```bash
pip install --upgrade djangorestframework-simplejwt
```

---

### Fix 2: Duplicate Model Registration (RecoveryAuditLog)

**Problem**: `RecoveryAuditLog` model exists in both `auth_module` and `behavioral_recovery`

**File**: Check both apps and remove duplicate:

```bash
# Search for the model
grep -r "class RecoveryAuditLog" password_manager/
```

**Solution**: Keep only ONE version. Based on migrations, keep it in `auth_module` and remove from `behavioral_recovery`.

**File**: `password_manager/behavioral_recovery/models.py`

Comment out or remove the `RecoveryAuditLog` model if it exists there.

---

### Fix 3: Suppress TensorFlow oneDNN Info Messages

**File**: `password_manager/password_manager/settings.py`

Add at the top:

```python
import os

# Suppress TensorFlow INFO messages
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'  # 0=ALL, 1=INFO, 2=WARNING, 3=ERROR

# Disable oneDNN custom operations (optional - may reduce performance)
# os.environ['TF_ENABLE_ONEDNN_OPTS'] = '0'
```

---

### Fix 4: Keras `input_length` Deprecation

**Files**: Find all files using `input_length` parameter

```bash
# Search for the deprecated parameter
grep -r "input_length" password_manager/ml_models/
grep -r "input_length" password_manager/ml_security/
```

**Solution**: Remove the `input_length` parameter from Embedding layers:

**Before**:
```python
Embedding(vocab_size, embedding_dim, input_length=max_length)
```

**After**:
```python
Embedding(vocab_size, embedding_dim)
```

---

### Fix 5: Threat Analyzer Model Error (KerasTensor)

**Problem**: Incompatible TensorFlow function usage in Keras model

**File**: `password_manager/ml_security/models/threat_analyzer.py` (or similar)

**Find the problematic code**:

```bash
grep -r "def create_threat_analyzer_model" password_manager/
```

**Solution**: Wrap TensorFlow operations in Keras layers

**Before** (incorrect):
```python
from tensorflow.keras.layers import Input
import tensorflow as tf

input_layer = Input(shape=(100,))
x = tf.nn.relu(input_layer)  # ❌ WRONG - TensorFlow function on Keras layer
```

**After** (correct):
```python
from tensorflow.keras.layers import Input, Dense, Activation

input_layer = Input(shape=(100,))
x = Activation('relu')(input_layer)  # ✅ CORRECT - Use Keras layer
# OR
x = Dense(64, activation='relu')(input_layer)  # ✅ CORRECT
```

---

### Fix 6: Post-Quantum Cryptography Libraries (liboqs, pqcrypto, concrete-python)

These warnings are **expected during local development** on Windows. The system gracefully falls back to secure classical cryptography.

**Messages you may see in development:**
```
[DEV] liboqs-python not available - this is expected in local development
[DEV] pqcrypto not available - using secure fallback for development
[DEV] concrete-python not available - FHE operations will use fallback mode (OK for development)
```

These are **INFO messages** in development mode, not errors. The application works correctly without these libraries.

---

#### For Production Deployment (Docker)

The Docker image automatically compiles and installs all crypto libraries:

```bash
# Build and run with Docker (includes liboqs, pqcrypto, concrete-python)
docker compose -f docker/docker-compose.yml up --build
```

The production Dockerfile:
- Compiles **liboqs** C library from source
- Installs **liboqs-python** wrapper
- Installs **pqcrypto** pure-Python crypto
- Installs **concrete-python** FHE library (Linux x86_64 only)

---

#### For Local Development (Windows/macOS - Optional)

If you want to eliminate these messages locally (not required):

**Option A**: Use Docker (recommended)
```bash
docker compose -f docker/docker-compose.dev.yml up
```

**Option B**: Install on Linux/WSL2
```bash
# Install liboqs system library first
git clone https://github.com/open-quantum-safe/liboqs.git
cd liboqs && mkdir build && cd build
cmake -GNinja .. -DBUILD_SHARED_LIBS=ON -DOQS_ENABLE_KEM_KYBER=ON
ninja && sudo ninja install

# Then install Python packages
pip install liboqs-python
pip install pqcrypto
pip install concrete-python  # Linux x86_64 only
```

**Option C**: Accept the fallbacks (recommended for Windows dev)
The fallback encryption is still secure (AES-256-GCM) and works correctly for development/testing.

---

#### Legacy Reference (if you have old code)

```python
try:
    import liboqs
    LIBOQS_AVAILABLE = True
except ImportError:
    LIBOQS_AVAILABLE = False
    # Suppress warning by not logging it
```

**Option C**: Update the code to not log the warning

Find where the warning is logged and comment it out.

---

### Fix 7: Add ab_testing App or Suppress Warning

**Option A**: Create the ab_testing app (if you want A/B testing)

```bash
cd password_manager
python manage.py startapp ab_testing
```

Then add to `INSTALLED_APPS` in `settings.py`:

```python
INSTALLED_APPS = [
    # ... other apps ...
    'ab_testing',
]
```

**Option B**: Suppress the warning

Find where the warning is logged (likely in a startup file) and wrap in try-except:

```python
try:
    from ab_testing.models import Experiment
    AB_TESTING_AVAILABLE = True
except ImportError:
    AB_TESTING_AVAILABLE = False
    # Don't log warning
```

---

## 🚀 Quick Apply All Fixes

Create a new file to apply all suppressions:

**File**: `password_manager/password_manager/warning_suppressions.py`

```python
"""
Warning suppressions for development environment
Add to settings.py: from .warning_suppressions import *
"""

import os
import warnings

# Suppress TensorFlow INFO messages
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'

# Suppress specific warnings
warnings.filterwarnings('ignore', category=UserWarning, module='rest_framework_simplejwt')
warnings.filterwarnings('ignore', category=UserWarning, module='keras')
warnings.filterwarnings('ignore', category=RuntimeWarning, module='django.db.models.base')

# Optional: Disable oneDNN (may reduce performance)
# os.environ['TF_ENABLE_ONEDNN_OPTS'] = '0'

print("✅ Warning suppressions loaded")
```

**Then in** `password_manager/password_manager/settings.py`:

Add at the very top:

```python
# Suppress development warnings
from .warning_suppressions import *
```

---

## 🎯 Priority Fixes (Do These First)

### 1. High Priority: Fix Duplicate RecoveryAuditLog Model

This can cause database inconsistencies.

**Action**:
```bash
# Find all instances
grep -r "class RecoveryAuditLog" password_manager/

# Remove duplicate from behavioral_recovery app
```

### 2. Medium Priority: Fix Threat Analyzer Model

This error prevents the model from loading properly.

**Action**: Update the model code to use Keras layers instead of TensorFlow functions.

### 3. Low Priority: Suppress Warnings

These are cosmetic and don't affect functionality.

**Action**: Apply the warning suppressions above.

---

## 📝 Step-by-Step Implementation

### Step 1: Create Warning Suppression File

```bash
cd password_manager/password_manager
# Create the file with the content above
```

### Step 2: Update settings.py

```python
# At the very top of settings.py
from .warning_suppressions import *
```

### Step 3: Fix Duplicate Model (if found)

```bash
# Check both apps
# Keep the model in auth_module, remove from behavioral_recovery
```

### Step 4: Run Migrations

```bash
python manage.py makemigrations
python manage.py migrate
```

---

## ✅ Verification

After applying fixes, you should see:

```bash
python manage.py makemigrations
# Should show minimal or no warnings

python manage.py migrate
# Should complete without errors
```

**Expected Output** (clean):
```
✅ Warning suppressions loaded
INFO Password strength model loaded
INFO Anomaly detection model loaded
INFO Blockchain anchoring is disabled
INFO FIDO2 Server initialized
Migrations for 'auth_module':
  ...
```

---

## 🔍 Individual Fix Scripts

### Script 1: Suppress TensorFlow Warnings

**File**: Create `password_manager/suppress_tf_warnings.py`

```python
import os
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'
print("✅ TensorFlow warnings suppressed")
```

### Script 2: Check for Duplicate Models

**File**: Create `password_manager/check_duplicates.py`

```python
import os

def find_duplicate_models():
    for root, dirs, files in os.walk('.'):
        for file in files:
            if file == 'models.py':
                filepath = os.path.join(root, file)
                with open(filepath, 'r', encoding='utf-8') as f:
                    content = f.read()
                    if 'class RecoveryAuditLog' in content:
                        print(f"Found RecoveryAuditLog in: {filepath}")

find_duplicate_models()
```

Run:
```bash
cd password_manager
python check_duplicates.py
```

---

## 🎊 Summary of All Fixes

| Fix | File | Action | Time |
|-----|------|--------|------|
| pkg_resources warning | `settings.py` | Add warning filter | 1 min |
| Duplicate model | `models.py` | Remove duplicate | 2 min |
| TensorFlow info | `settings.py` | Set env var | 1 min |
| Keras deprecation | ML model files | Remove parameter | 5 min |
| Threat analyzer | Model file | Use Keras layers | 10 min |
| liboqs warning | Install or suppress | Optional | 2 min |
| ab_testing warning | Create app or suppress | Optional | 2 min |
| **Total** | | | **~20 minutes** |

---

## 🎯 Recommended Action Plan

### Option A: Quick Suppress (5 minutes)

Just suppress all warnings:

1. Create `warning_suppressions.py`
2. Import in `settings.py`
3. Run migrations

✅ **Result**: Clean output, all warnings hidden

### Option B: Proper Fix (20 minutes)

Fix underlying issues:

1. Remove duplicate model
2. Fix threat analyzer model
3. Install missing dependencies
4. Suppress remaining cosmetic warnings

✅ **Result**: Clean code, properly fixed issues

---

## 📚 Documentation

After fixes, your `makemigrations` output should look like:

```
✅ Warning suppressions loaded
Migrations for 'auth_module':
  auth_module\migrations\0003_...
    - Create model PasskeyRecoverySetup
    ...
```

Much cleaner! ✨

---

**Choose your approach based on your timeline and preference!**


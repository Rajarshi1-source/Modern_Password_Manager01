# 🧪 Password Manager Test Suite

This directory contains comprehensive tests for the Password Manager application, including **Unit Tests**, **Functional Tests**, and **Integration Tests**.

---

## 📋 Test Organization

### **1. Integration Tests** (This Directory)
```
tests/
├── __init__.py
├── test_ml_apis.py            # ML Security API tests
├── manual_security_tests.py   # Manual security testing framework
└── README.md                  # This file
```

**Purpose:** Test APIs as an external client would (HTTP requests)

### **2. Functional Tests** (tests/functional/)
```
tests/functional/
├── __init__.py
├── test_user_workflows.py     # Complete user registration, login, logout flows
└── test_vault_operations.py   # Vault CRUD operations, encryption, sharing
```

**Purpose:** Test complete user workflows and features end-to-end

### **3. Unit Tests** (Backend Directory)
```
password_manager/
├── ml_security/tests.py       # ML module unit tests (models, views, services)
├── vault/tests.py             # Vault module unit tests
├── auth_module/tests.py       # Auth module unit tests (comprehensive)
└── security/tests.py          # Security module unit tests
```

**Purpose:** Test Django models, views, and business logic in isolation

### **4. Test Utilities** (tests/)
```
tests/
├── utils.py                   # Test utility functions
├── fixtures.py                # Reusable test fixtures
└── TESTING_GUIDE.md          # Comprehensive testing guide
```

**Purpose:** Shared utilities and fixtures for all tests

---

## 🚀 Running Tests

### **Quick Start - Run All Tests**

```bash
# Run all tests (unit + functional + integration)
python tests/run_all_tests.py

# Or use the script
./run_tests.sh  # Linux/Mac
run_tests.bat   # Windows
```

### **Run Unit Tests** (Django)

```bash
cd password_manager
python manage.py test

# Specific module
python manage.py test ml_security
python manage.py test vault
python manage.py test auth_module
python manage.py test security

# Specific test class
python manage.py test ml_security.tests.PasswordStrengthPredictionModelTest

# With coverage
coverage run --source='.' manage.py test
coverage report
```

### **Run Functional Tests**

```bash
# Run all functional tests
python tests/functional/test_user_workflows.py
python tests/functional/test_vault_operations.py

# Or use pytest
pytest tests/functional/

# With verbose output
pytest tests/functional/ -v
```

### **Run Integration Tests**

```bash
# Ensure Django server is running first
cd password_manager
python manage.py runserver

# In another terminal:
python tests/test_ml_apis.py

# Manual security tests
python manage.py test_security --all
python manage.py test_security --scenario normal_login
```

### **Run Tests by Category**

```bash
# Unit tests only
cd password_manager && python manage.py test

# Functional tests only
pytest tests/functional/

# Integration tests only
python tests/test_ml_apis.py

# Frontend tests
cd frontend && npm test
```

---

## 📚 Available Test Suites

### ✅ **`test_ml_apis.py`** - Machine Learning APIs

**Tests:**
- Password strength prediction
- Anomaly detection
- Threat analysis
- Server connectivity

**Prerequisites:**
```bash
# Start Django server
cd password_manager
python manage.py runserver
```

**Run:**
```bash
python tests/test_ml_apis.py
```

**Expected Output:**
```
==========================================================
     ML SECURITY API TEST SUITE
     Password Manager - AI Security Testing
==========================================================

[OK] Server is running at http://127.0.0.1:8000

TEST 1: Password Strength Prediction
-------------------------------------
[OK] Strength Score: 0.87/1.00
[INFO] Feedback: Strong. Good job!

TEST 2: Anomaly Detection
-------------------------
[OK] Normal Behavior - Score: 0.12
[INFO] Feedback: Normal behavior.

TEST 3: Threat Analysis
-----------------------
[OK] No Threat Detected - Score: 0.15
[INFO] Recommended Action: No immediate threat detected.

[SUCCESS] ML Security System is working!
```

---

## 🔐 Authentication

Some endpoints require authentication. To test authenticated endpoints:

### **Option 1: Use JWT Token**

```python
# Get token from login
import requests

response = requests.post(
    "http://127.0.0.1:8000/api/auth/login/",
    json={"email": "user@example.com", "password": "password"}
)
token = response.json()['access']

# Use token in tests
headers = {"Authorization": f"Bearer {token}"}
response = requests.post(url, json=data, headers=headers)
```

### **Option 2: Modify Test Script**

Add authentication to `test_ml_apis.py`:

```python
# At the top of the file
AUTH_TOKEN = None

def get_auth_token():
    response = requests.post(
        f"{BASE_URL}/api/auth/login/",
        json={"email": "test@example.com", "password": "testpass"}
    )
    return response.json()['access']

# In each test function
headers = {"Authorization": f"Bearer {AUTH_TOKEN}"}
response = requests.post(url, json=data, headers=headers)
```

---

## 📝 Creating New Integration Tests

### **Template for New Test File**

```python
"""
API Integration Tests for [Feature Name]
Tests [feature] endpoints
"""
import requests
import json

BASE_URL = "http://127.0.0.1:8000"
API_BASE = f"{BASE_URL}/api/[feature]"

def test_[feature]_endpoint():
    """Test [feature] functionality"""
    response = requests.post(
        f"{API_BASE}/endpoint/",
        json={"key": "value"},
        headers={"Content-Type": "application/json"}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data['success'] == True

if __name__ == "__main__":
    test_[feature]_endpoint()
    print("✅ All tests passed!")
```

---

## 🎯 Test Coverage Status

| Module | Unit Tests | Functional Tests | Integration Tests | Status |
|--------|------------|------------------|-------------------|--------|
| **ML Security** | ✅ Complete | ⚠️ Partial | ✅ Complete | 85% |
| **Authentication** | ✅ Complete | ✅ Complete | ⏳ Planned | 90% |
| **Vault** | ✅ Complete | ✅ Complete | ⏳ Planned | 85% |
| **Security** | ✅ Complete | ⏳ Partial | ✅ Complete | 80% |
| **User Management** | ✅ Complete | ✅ Complete | N/A | 90% |

### Coverage by Test Type

- **Unit Tests**: ~300+ tests covering models, views, and services
- **Functional Tests**: ~50+ tests covering user workflows
- **Integration Tests**: ~30+ tests covering API endpoints
- **Total Test Count**: 380+ tests

### Running Coverage Reports

```bash
# Install coverage
pip install coverage

# Run tests with coverage
cd password_manager
coverage run --source='.' manage.py test
coverage report
coverage html  # Generate HTML report

# View report
open htmlcov/index.html  # Mac
xdg-open htmlcov/index.html  # Linux
start htmlcov/index.html  # Windows
```

---

## 🔍 Test Types Explained

### **Integration Tests** (This Directory)
- Test **API endpoints** via HTTP
- Simulate **real client behavior**
- Use **requests** library
- Test **end-to-end flows**
- **Don't require** Django test framework

**Example:**
```python
response = requests.post(
    "http://127.0.0.1:8000/api/ml-security/password-strength/",
    json={"password": "test123"}
)
```

### **Unit Tests** (Backend)
- Test **Django models** and views
- Test **business logic**
- Use **Django test framework**
- Access **database directly**
- Test **individual functions**

**Example:**
```python
from django.test import TestCase

class PasswordStrengthTests(TestCase):
    def test_model_creation(self):
        prediction = PasswordStrengthPrediction.objects.create(...)
        self.assertEqual(prediction.strength_score, 0.87)
```

---

## 🛠️ Troubleshooting

### **Error: Connection Refused**
```
[ERROR] Cannot connect to server at http://127.0.0.1:8000
```

**Solution:**
```bash
cd password_manager
python manage.py runserver
```

### **Error: 401 Unauthorized**
```
[ERROR] Authentication required (401)
```

**Solution:**
- Some endpoints require login
- Add JWT token to headers
- Or create test user first

### **Error: Module Not Found**
```
ModuleNotFoundError: No module named 'requests'
```

**Solution:**
```bash
pip install requests
```

---

## 📊 Best Practices

### ✅ **DO:**
- Keep integration tests in `tests/` directory
- Test from client perspective
- Use meaningful test names
- Add descriptive output messages
- Test both success and failure cases

### ❌ **DON'T:**
- Mix integration tests with Django unit tests
- Test internal Django functions here
- Hardcode sensitive credentials
- Skip error handling
- Assume server is always running

---

## 🚀 CI/CD Integration

### **GitHub Actions Example**

```yaml
name: Integration Tests

on: [push, pull_request]

jobs:
  integration-tests:
    runs-on: ubuntu-latest
    
    steps:
    - uses: actions/checkout@v2
    
    - name: Set up Python
      uses: actions/setup-python@v2
      with:
        python-version: 3.13
    
    - name: Install dependencies
      run: |
        pip install -r password_manager/requirements.txt
    
    - name: Start Django server
      run: |
        cd password_manager
        python manage.py migrate
        python manage.py runserver &
        sleep 10
    
    - name: Run integration tests
      run: python tests/test_ml_apis.py
```

---

## 📞 Support

- **Create Issue:** For test failures or suggestions
- **Documentation:** See main README.md
- **Django Tests:** See `password_manager/[module]/tests.py`

---

**Happy Testing! 🎉**


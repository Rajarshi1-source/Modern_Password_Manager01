# 📚 Comprehensive Testing Guide

**Password Manager - Complete Testing Documentation**

---

## Table of Contents

1. [Introduction](#introduction)
2. [Testing Philosophy](#testing-philosophy)
3. [Test Types Overview](#test-types-overview)
4. [Setting Up Your Test Environment](#setting-up-your-test-environment)
5. [Writing Unit Tests](#writing-unit-tests)
6. [Writing Functional Tests](#writing-functional-tests)
7. [Writing Integration Tests](#writing-integration-tests)
8. [Using Test Utilities and Fixtures](#using-test-utilities-and-fixtures)
9. [Running and Debugging Tests](#running-and-debugging-tests)
10. [Test Coverage](#test-coverage)
11. [Continuous Integration](#continuous-integration)
12. [Best Practices](#best-practices)
13. [Troubleshooting](#troubleshooting)

---

## Introduction

This guide provides comprehensive documentation for testing the Password Manager application. It covers all aspects of testing, from writing your first unit test to setting up continuous integration.

### What This Guide Covers

- ✅ Unit testing with Django
- ✅ Functional testing for user workflows
- ✅ Integration testing for APIs
- ✅ Using fixtures and test utilities
- ✅ Measuring and improving test coverage
- ✅ Debugging failing tests
- ✅ CI/CD integration

### Who This Guide is For

- Developers new to the project
- Contributors adding new features
- QA engineers writing test cases
- Anyone wanting to understand the test architecture

---

## Testing Philosophy

### Our Testing Principles

1. **Test-Driven Development (TDD)**: Write tests before implementing features
2. **Comprehensive Coverage**: Aim for 80%+ code coverage
3. **Fast Feedback**: Tests should run quickly
4. **Isolation**: Tests should be independent and not affect each other
5. **Readability**: Tests should be easy to understand
6. **Maintainability**: Tests should be easy to update

### Test Pyramid

```
        /\
       /  \
      / E2E \           - Few, slow, expensive
     /______\
    /        \
   /Integration\        - Medium number, moderate speed
  /____________\
 /              \
/  Unit Tests    \      - Many, fast, cheap
/________________\
```

We follow the test pyramid approach:
- **70% Unit Tests**: Test individual components
- **20% Functional Tests**: Test feature workflows
- **10% Integration Tests**: Test system integration

---

## Test Types Overview

### 1. Unit Tests

**Location**: `password_manager/[module]/tests.py`

**Purpose**: Test individual components in isolation

**Examples**:
- Testing a Django model's save method
- Testing a view function with mocked dependencies
- Testing a utility function's output

**Characteristics**:
- ✅ Fast execution (milliseconds)
- ✅ Test one thing at a time
- ✅ Mock external dependencies
- ✅ High coverage

### 2. Functional Tests

**Location**: `tests/functional/`

**Purpose**: Test complete user workflows

**Examples**:
- User registration → email verification → login
- Create vault item → encrypt → save → retrieve → decrypt
- Enable 2FA → login with 2FA → verify code

**Characteristics**:
- ⏱ Moderate execution (seconds)
- 🔄 Test multiple components together
- 🎯 Focus on user scenarios
- 📋 Test business logic

### 3. Integration Tests

**Location**: `tests/`

**Purpose**: Test system integration from external perspective

**Examples**:
- Testing REST API endpoints
- Testing database transactions
- Testing third-party integrations

**Characteristics**:
- ⏰ Slower execution (seconds to minutes)
- 🌐 Test real HTTP requests
- 💾 Test real database operations
- 🔌 Test external services

---

## Setting Up Your Test Environment

### Prerequisites

```bash
# Python 3.13+
python --version

# Django 4.2+
django-admin --version

# Required packages
pip install -r password_manager/requirements.txt

# Testing tools
pip install pytest pytest-django coverage
```

### Database Setup

For testing, Django uses a separate test database:

```python
# password_manager/settings.py
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
        'TEST': {
            'NAME': BASE_DIR / 'test_db.sqlite3',  # Test database
        }
    }
}
```

### Environment Variables

```bash
# .env.test
DEBUG=True
SECRET_KEY='test-secret-key-not-for-production'
DATABASE_URL='sqlite:///test_db.sqlite3'
ALLOWED_HOSTS='localhost,127.0.0.1'
```

### Directory Structure

```
password_manager/
├── password_manager/          # Project settings
│   └── settings.py
├── ml_security/              # ML module
│   └── tests.py             # ✅ Unit tests
├── auth_module/              # Auth module
│   └── tests.py             # ✅ Unit tests
├── vault/                    # Vault module
│   └── tests.py             # ✅ Unit tests
└── security/                 # Security module
    └── tests.py             # ✅ Unit tests

tests/                         # Test directory
├── __init__.py
├── utils.py                  # Test utilities
├── fixtures.py               # Test fixtures
├── test_ml_apis.py          # ✅ Integration tests
├── manual_security_tests.py # Manual tests
├── functional/               # Functional tests
│   ├── __init__.py
│   ├── test_user_workflows.py      # ✅ User flows
│   └── test_vault_operations.py    # ✅ Vault flows
└── TESTING_GUIDE.md         # This file
```

---

## Writing Unit Tests

### Basic Structure

```python
from django.test import TestCase
from django.contrib.auth.models import User

class MyModelTest(TestCase):
    """Test MyModel functionality"""
    
    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
    
    def test_model_creation(self):
        """Test creating a model instance"""
        # Arrange
        data = {'field': 'value'}
        
        # Act
        instance = MyModel.objects.create(**data)
        
        # Assert
        self.assertIsNotNone(instance.id)
        self.assertEqual(instance.field, 'value')
    
    def tearDown(self):
        """Clean up after tests"""
        self.user.delete()
```

### Testing Models

```python
class VaultItemModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
    
    def test_create_vault_item(self):
        """Test creating a vault item"""
        item = VaultItem.objects.create(
            user=self.user,
            item_type='password',
            name='Test Item',
            encrypted_data='encrypted_data_here'
        )
        
        self.assertEqual(item.user, self.user)
        self.assertEqual(item.item_type, 'password')
        self.assertIsNotNone(item.created_at)
    
    def test_vault_item_str_representation(self):
        """Test string representation"""
        item = VaultItem.objects.create(
            user=self.user,
            item_type='note',
            name='Test Note'
        )
        
        str_repr = str(item)
        self.assertIn('testuser', str_repr)
        self.assertIn('note', str_repr)
```

### Testing Views

```python
from django.test import Client, TestCase
from django.urls import reverse

class VaultViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        self.client.force_login(self.user)
    
    def test_list_vault_items(self):
        """Test listing vault items"""
        url = reverse('vault-item-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        self.assertIn('items', response.json())
    
    def test_create_vault_item(self):
        """Test creating a vault item"""
        url = reverse('vault-item-create')
        data = {
            'item_type': 'password',
            'name': 'Test Password',
            'encrypted_data': 'data'
        }
        
        response = self.client.post(
            url,
            data=json.dumps(data),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 201)
```

### Testing with Mocks

```python
from unittest.mock import patch, Mock

class MLSecurityTest(TestCase):
    @patch('ml_security.ml_models.password_strength.predict_strength')
    def test_password_strength_prediction(self, mock_predict):
        """Test password strength prediction with mocked ML model"""
        # Mock the prediction
        mock_predict.return_value = (0.85, "Strong password!")
        
        # Make prediction
        score, feedback = predict_strength('TestPass123!')
        
        # Verify
        self.assertEqual(score, 0.85)
        self.assertEqual(feedback, "Strong password!")
        mock_predict.assert_called_once_with('TestPass123!')
```

---

## Writing Functional Tests

### Basic Workflow Test

```python
from django.test import TestCase, Client
from django.contrib.auth.models import User

class UserRegistrationWorkflowTest(TestCase):
    def setUp(self):
        self.client = Client()
    
    def test_complete_registration_flow(self):
        """
        Test complete user registration:
        1. Submit registration form
        2. Verify email (mock)
        3. Complete profile
        4. Login successfully
        """
        # Step 1: Register
        registration_data = {
            'username': 'newuser',
            'email': 'new@example.com',
            'password': 'SecurePass123!',
            'password_confirm': 'SecurePass123!'
        }
        
        response = self.client.post(
            '/api/auth/register/',
            data=json.dumps(registration_data),
            content_type='application/json'
        )
        
        # Step 2: Verify user created
        user = User.objects.get(username='newuser')
        self.assertIsNotNone(user)
        
        # Step 3: Login
        login_data = {
            'username': 'newuser',
            'password': 'SecurePass123!'
        }
        
        response = self.client.post(
            '/api/auth/login/',
            data=json.dumps(login_data),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
```

### Multi-Step Workflow

```python
class VaultOperationsWorkflowTest(TestCase):
    def test_create_encrypt_retrieve_decrypt_flow(self):
        """
        Test complete vault item lifecycle:
        1. Create vault item
        2. Encrypt data client-side
        3. Store encrypted data
        4. Retrieve encrypted data
        5. Decrypt client-side
        6. Verify original data
        """
        # Setup
        user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        client = Client()
        client.force_login(user)
        
        # Step 1-3: Create and store
        original_data = "my_secret_password"
        encrypted_data = mock_encrypt(original_data)
        
        create_response = client.post(
            '/api/vault/items/',
            data=json.dumps({
                'item_type': 'password',
                'name': 'Test Item',
                'encrypted_data': encrypted_data
            }),
            content_type='application/json'
        )
        
        item_id = create_response.json()['id']
        
        # Step 4-5: Retrieve and decrypt
        retrieve_response = client.get(f'/api/vault/items/{item_id}/')
        retrieved_encrypted_data = retrieve_response.json()['encrypted_data']
        decrypted_data = mock_decrypt(retrieved_encrypted_data)
        
        # Step 6: Verify
        self.assertEqual(decrypted_data, original_data)
```

---

## Writing Integration Tests

### API Testing

```python
import requests

BASE_URL = "http://127.0.0.1:8000"

def test_ml_api_integration():
    """Test ML API endpoint integration"""
    # Test password strength
    response = requests.post(
        f"{BASE_URL}/api/ml-security/password-strength/",
        json={'password': 'TestPassword123!'}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert 'strength_score' in data
    assert 'feedback' in data
    assert 0 <= data['strength_score'] <= 1
```

### External Service Integration

```python
@patch('requests.post')
def test_oauth_provider_integration(mock_post):
    """Test OAuth provider integration"""
    # Mock OAuth response
    mock_post.return_value.status_code = 200
    mock_post.return_value.json.return_value = {
        'access_token': 'test_token',
        'user_info': {'email': 'user@example.com'}
    }
    
    # Test OAuth flow
    # ... test implementation
```

---

## Using Test Utilities and Fixtures

### Importing Utilities

```python
from tests.utils import (
    create_test_user,
    create_authenticated_client,
    generate_vault_item_data,
    assert_response_success
)
from tests.fixtures import (
    UserFixtures,
    VaultItemFixtures,
    MLSecurityFixtures
)
```

### Using Utilities

```python
class MyTest(TestCase):
    def setUp(self):
        # Create test user
        self.user = create_test_user(username='testuser')
        
        # Create authenticated client
        self.client, _ = create_authenticated_client(self.user)
        
        # Generate test data
        self.vault_data = generate_vault_item_data('password')
    
    def test_example(self):
        response = self.client.get('/api/vault/items/')
        assert_response_success(response, expected_status=200)
```

### Using Fixtures

```python
class MyTest(TestCase):
    def test_with_fixtures(self):
        # Load user fixtures
        user_data = UserFixtures.basic_user()
        user = UserFixtures.create_user_from_fixture(user_data)
        
        # Load vault item fixtures
        item_data = VaultItemFixtures.password_item()
        
        # Use in test
        # ...
```

---

## Running and Debugging Tests

### Running All Tests

```bash
# Run all unit tests
cd password_manager
python manage.py test

# Run all functional tests
pytest tests/functional/

# Run all integration tests
python tests/test_ml_apis.py

# Run everything
python tests/run_all_tests.py
```

### Running Specific Tests

```bash
# Run specific module
python manage.py test ml_security

# Run specific test class
python manage.py test ml_security.tests.PasswordStrengthPredictionModelTest

# Run specific test method
python manage.py test ml_security.tests.PasswordStrengthPredictionModelTest.test_create_password_strength_prediction

# Run with pytest
pytest tests/functional/test_user_workflows.py::UserRegistrationWorkflowTest::test_complete_registration_flow
```

### Debugging Failing Tests

#### 1. Verbose Output

```bash
# Django tests with verbose output
python manage.py test --verbosity=2

# Pytest with verbose output
pytest -v
pytest -vv  # Extra verbose
```

#### 2. Print Debugging

```python
def test_example(self):
    response = self.client.get('/api/endpoint/')
    
    # Print for debugging
    print(f"Status Code: {response.status_code}")
    print(f"Response Data: {response.json()}")
    
    self.assertEqual(response.status_code, 200)
```

#### 3. Using pdb

```python
def test_example(self):
    import pdb; pdb.set_trace()  # Breakpoint
    
    response = self.client.get('/api/endpoint/')
    # ... rest of test
```

#### 4. Keeping Test Database

```bash
# Keep test database after tests
python manage.py test --keepdb
```

---

## Test Coverage

### Measuring Coverage

```bash
# Install coverage
pip install coverage

# Run with coverage
coverage run --source='.' manage.py test

# View report
coverage report

# Generate HTML report
coverage html
open htmlcov/index.html
```

### Coverage Configuration

```ini
# .coveragerc
[run]
source = .
omit =
    */migrations/*
    */tests.py
    */test_*.py
    */__pycache__/*
    */venv/*

[report]
exclude_lines =
    pragma: no cover
    def __repr__
    raise AssertionError
    raise NotImplementedError
    if __name__ == .__main__.:
```

### Coverage Goals

- **Overall Project**: 80%+
- **Critical Modules**: 90%+
  - Authentication
  - Vault/Encryption
  - Security
- **New Features**: 100%

---

## Continuous Integration

### GitHub Actions Example

```yaml
# .github/workflows/tests.yml
name: Run Tests

on: [push, pull_request]

jobs:
  test:
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
        pip install coverage pytest pytest-django
    
    - name: Run unit tests
      run: |
        cd password_manager
        coverage run --source='.' manage.py test
        coverage report --fail-under=80
    
    - name: Run functional tests
      run: |
        pytest tests/functional/
    
    - name: Upload coverage
      uses: codecov/codecov-action@v2
```

---

## Best Practices

### DO ✅

1. **Write tests first (TDD)**
2. **Test edge cases**
3. **Use descriptive test names**
4. **Keep tests independent**
5. **Mock external dependencies**
6. **Clean up test data**
7. **Test error handling**
8. **Use fixtures for common data**

### DON'T ❌

1. **Don't test Django built-ins**
2. **Don't write flaky tests**
3. **Don't test implementation details**
4. **Don't share state between tests**
5. **Don't ignore failing tests**
6. **Don't skip writing tests**
7. **Don't test too much in one test**
8. **Don't use production data**

### Test Naming Convention

```python
# Good ✅
def test_user_can_create_vault_item(self):
def test_password_strength_returns_score_between_zero_and_one(self):
def test_login_fails_with_invalid_credentials(self):

# Bad ❌
def test1(self):
def test_stuff(self):
def test_it_works(self):
```

---

## Troubleshooting

### Common Issues

#### 1. Import Errors

```
ModuleNotFoundError: No module named 'tests'
```

**Solution**:
```bash
# Add parent directory to Python path
export PYTHONPATH="${PYTHONPATH}:${PWD}"

# Or in test file:
import sys
sys.path.append('..')
```

#### 2. Database Errors

```
django.db.utils.OperationalError: no such table
```

**Solution**:
```bash
# Run migrations
python manage.py migrate

# For tests, Django creates test DB automatically
python manage.py test --debug-mode
```

#### 3. Permission Errors

```
PermissionError: [Errno 13] Permission denied
```

**Solution**:
```bash
# Check file permissions
ls -la test_db.sqlite3

# Remove old test database
rm test_db.sqlite3
```

#### 4. Timeout Errors

```
TimeoutError: Test exceeded time limit
```

**Solution**:
```python
# Increase timeout
@override_settings(TEST_RUNNER='django.test.runner.DiscoverRunner')
class MyTest(TestCase):
    # Increase timeout for slow tests
    pass
```

---

## Resources

### Documentation

- [Django Testing Documentation](https://docs.djangoproject.com/en/4.2/topics/testing/)
- [Pytest Documentation](https://docs.pytest.org/)
- [Coverage.py Documentation](https://coverage.readthedocs.io/)

### Tools

- **Django Test Runner**: Built-in test runner
- **pytest**: Alternative test runner
- **coverage**: Code coverage measurement
- **factory_boy**: Test data generation
- **faker**: Fake data generation

### Further Reading

- *Test-Driven Development with Python* by Harry Percival
- *Django for Professionals* by William S. Vincent
- Martin Fowler's articles on testing

---

## Getting Help

### Internal Resources

- Check `tests/README.md` for quick reference
- Review existing tests in `password_manager/[module]/tests.py`
- Use test utilities in `tests/utils.py`
- Browse fixtures in `tests/fixtures.py`

### External Help

- Django Testing Documentation
- Stack Overflow `[django-testing]` tag
- Django Forum
- Project GitHub Issues

---

**Happy Testing! 🎉**

*Last Updated: October 2025*

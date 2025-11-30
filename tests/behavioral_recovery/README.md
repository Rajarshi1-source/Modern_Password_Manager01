# Behavioral Recovery Tests

Comprehensive test suite for the Neuromorphic Behavioral Biometric Recovery System.

## Test Structure

```
tests/behavioral_recovery/
├── __init__.py
├── test_behavioral_capture.py      # Tests for behavioral data capture
├── test_transformer_model.py       # Tests for Transformer model
├── test_recovery_flow.py           # Tests for recovery workflow
├── test_privacy.py                 # Tests for differential privacy
├── test_adversarial_detection.py   # Tests for attack detection
├── test_integration.py             # End-to-end integration tests
└── README.md                       # This file
```

## Running Tests

### Run All Behavioral Recovery Tests

```bash
cd password_manager
python manage.py test tests.behavioral_recovery
```

### Run Specific Test Module

```bash
# Test behavioral capture
python manage.py test tests.behavioral_recovery.test_behavioral_capture

# Test Transformer model
python manage.py test tests.behavioral_recovery.test_transformer_model

# Test recovery flow
python manage.py test tests.behavioral_recovery.test_recovery_flow

# Test privacy features
python manage.py test tests.behavioral_recovery.test_privacy

# Test adversarial detection
python manage.py test tests.behavioral_recovery.test_adversarial_detection

# Test integration
python manage.py test tests.behavioral_recovery.test_integration
```

### Run with Verbose Output

```bash
python manage.py test tests.behavioral_recovery --verbosity=2
```

## Test Coverage

### Backend Tests

- ✅ **Behavioral Capture Processing** - Validates 247-dimensional data structure
- ✅ **Transformer Model** - Tests embedding generation and model initialization
- ✅ **Recovery Flow** - Tests API endpoints and workflow
- ✅ **Commitments** - Tests behavioral commitment creation and verification
- ✅ **Privacy** - Tests differential privacy and secure storage
- ✅ **Adversarial Detection** - Tests replay, spoofing, and duress detection
- ✅ **Integration** - End-to-end workflow tests

### Frontend Tests (JavaScript)

Frontend tests should be run separately using Vitest:

```bash
cd frontend
npm test
```

## Test Requirements

### Python Dependencies

All required packages are in `password_manager/requirements.txt`:

- Django >= 4.2.16
- djangorestframework >= 3.16
- tensorflow >= 2.13.0
- scikit-learn >= 1.3.0
- numpy >= 1.24.0

### Optional Dependencies

Some tests require TensorFlow. If TensorFlow is not available, those tests will be skipped.

## Expected Test Results

### Passing Criteria

- All tests should pass
- No critical security vulnerabilities
- Performance benchmarks met:
  - Embedding generation < 200ms
  - Similarity calculation < 50ms
  - API response time < 500ms

### Known Issues

- TensorFlow tests may be skipped if TensorFlow not installed
- Some tests are placeholders for frontend functionality
- Performance tests may vary based on hardware

## Test Data

### Sample Behavioral Data Structure

Tests use realistic sample data covering all 247 dimensions:

```python
{
    'typing': {
        'press_duration_mean': 98.5,
        'flight_time_mean': 145.2,
        'typing_speed_wpm': 65,
        'error_rate': 0.05,
        # ... 80 total typing dimensions
    },
    'mouse': {
        'velocity_mean': 2.3,
        'click_count': 45,
        'movement_straightness': 0.65,
        # ... 60 total mouse dimensions
    },
    'cognitive': {
        'avg_decision_time': 2500,
        'navigation_efficiency': 0.75,
        # ... 40 total cognitive dimensions
    },
    'device': {
        'device_type': 'desktop',
        'screen_width': 1920,
        # ... 35 total device dimensions
    },
    'semantic': {
        'passwords_created': 3,
        'avg_password_length': 16,
        # ... 32 total semantic dimensions
    }
}
```

## Contributing

When adding new features to behavioral recovery:

1. Write tests first (TDD approach)
2. Ensure tests cover both success and failure cases
3. Include security-focused tests
4. Test edge cases and boundary conditions
5. Maintain > 80% code coverage

## Continuous Integration

Tests should be run automatically in CI/CD pipeline before deployment.

### GitHub Actions Example

```yaml
- name: Run Behavioral Recovery Tests
  run: |
    cd password_manager
    python manage.py test tests.behavioral_recovery --verbosity=2
```

## Debugging Failed Tests

### Common Issues

1. **TensorFlow Import Error**: Install TensorFlow or tests will be skipped
2. **Database Migration**: Run migrations before tests
3. **Module Not Found**: Ensure Python path includes password_manager directory

### Debug Mode

Run tests with Python debugger:

```bash
python -m pdb manage.py test tests.behavioral_recovery.test_recovery_flow
```

## Performance Benchmarks

Expected performance metrics:

| Metric | Target | Typical |
|--------|--------|---------|
| Embedding Generation | < 200ms | ~150ms |
| Similarity Calculation | < 50ms | ~30ms |
| Challenge Evaluation | < 500ms | ~300ms |
| API Response (initiate) | < 1000ms | ~600ms |

## Security Test Checklist

- [x] Replay attack detection
- [x] Spoofing detection (impossible patterns)
- [x] Duress detection (stress biomarkers)
- [x] Privacy preservation (no plaintext transmission)
- [x] Encryption verification
- [x] Similarity threshold enforcement
- [x] Audit logging completeness

## Next Steps

1. Add more edge case tests
2. Implement load testing for concurrent recovery attempts
3. Add fuzzing tests for API endpoints
4. Implement ML model robustness tests
5. Add cross-browser compatibility tests (frontend)


# Behavioral Recovery API Reference

Complete API documentation for the Neuromorphic Behavioral Biometric Recovery System.

---

## Base URL

```
Development: http://127.0.0.1:8000/api/behavioral-recovery/
Production: https://api.yourdomain.com/api/behavioral-recovery/
```

---

## Authentication

Most endpoints allow anonymous access (for password recovery use case).  
Commitment setup requires authentication.

```http
Authorization: Bearer <access_token>
```

---

## API Endpoints

### 1. Initiate Recovery

Start a new behavioral recovery attempt.

**Endpoint**: `POST /api/behavioral-recovery/initiate/`

**Request Body**:
```json
{
  "email": "user@example.com"
}
```

**Response** (200 OK):
```json
{
  "success": true,
  "message": "Behavioral recovery initiated...",
  "data": {
    "attempt_id": "550e8400-e29b-41d4-a716-446655440000",
    "timeline": {
      "expected_days": 5,
      "challenges_per_day": 4,
      "total_challenges": 20,
      "expected_completion": "2025-11-11T10:00:00Z"
    },
    "first_challenge": {
      "challenge_id": "650e8400-e29b-41d4-a716-446655440001",
      "challenge_type": "typing",
      "challenge_data": {
        "instruction": "Type the following sentence naturally:",
        "sentence": "The quick brown fox jumps over the lazy dog",
        "capture_metrics": ["key_press_duration", "inter_key_latency", ...]
      }
    }
  }
}
```

**Error** (400 Bad Request):
```json
{
  "success": false,
  "message": "Behavioral recovery not set up for this account",
  "code": "no_commitments"
}
```

---

### 2. Get Recovery Status

Get current status of a recovery attempt.

**Endpoint**: `GET /api/behavioral-recovery/status/{attempt_id}/`

**Response** (200 OK):
```json
{
  "success": true,
  "data": {
    "attempt_id": "550e8400-e29b-41d4-a716-446655440000",
    "current_stage": "mouse_challenge",
    "status": "in_progress",
    "challenges_completed": 8,
    "challenges_total": 20,
    "similarity_scores": {
      "typing": 0.92,
      "mouse": 0.89,
      "cognitive": 0.85
    },
    "overall_similarity": 0.887,
    "started_at": "2025-11-06T10:00:00Z",
    "expected_completion_date": "2025-11-11T10:00:00Z",
    "days_remaining": 3,
    "progress_percentage": 40
  }
}
```

---

### 3. Submit Challenge Response

Submit a completed behavioral challenge.

**Endpoint**: `POST /api/behavioral-recovery/submit-challenge/`

**Request Body**:
```json
{
  "attempt_id": "550e8400-e29b-41d4-a716-446655440000",
  "challenge_id": "650e8400-e29b-41d4-a716-446655440001",
  "behavioral_data": {
    "typing": {
      "press_duration_mean": 98.5,
      "flight_time_mean": 145.2,
      "typing_speed_wpm": 65,
      "error_rate": 0.05,
      "rhythm_variability": 0.42,
      "total_samples": 150,
      "data_quality_score": 0.85
    },
    "challenge_type": "typing",
    "completed": true,
    "time_taken": 45000
  }
}
```

**Response** (200 OK):
```json
{
  "success": true,
  "message": "Challenge evaluated successfully",
  "data": {
    "similarity_score": 0.92,
    "passed": true,
    "overall_similarity": 0.887,
    "next_challenge": {
      "challenge_id": "750e8400-e29b-41d4-a716-446655440002",
      "challenge_type": "mouse",
      "challenge_data": { /* ... */ }
    },
    "challenges_remaining": 12
  }
}
```

---

### 4. Complete Recovery

Finalize recovery and reset password.

**Endpoint**: `POST /api/behavioral-recovery/complete/`

**Request Body**:
```json
{
  "attempt_id": "550e8400-e29b-41d4-a716-446655440000",
  "new_password": "NewSecurePassword123!"
}
```

**Response** (200 OK):
```json
{
  "success": true,
  "message": "Password recovery completed successfully",
  "data": {
    "success": true,
    "user_id": 42,
    "recovery_completed_at": "2025-11-11T10:00:00Z"
  }
}
```

**Error** (400 Bad Request):
```json
{
  "success": false,
  "message": "Behavioral similarity too low (0.65). Required: 0.87",
  "code": "low_similarity"
}
```

---

### 5. Setup Commitments

Create behavioral commitments (requires authentication).

**Endpoint**: `POST /api/behavioral-recovery/setup-commitments/`  
**Authentication**: Required

**Request Body**:
```json
{
  "behavioral_profile": {
    "typing": { /* 80+ typing features */ },
    "mouse": { /* 60+ mouse features */ },
    "cognitive": { /* 40+ cognitive features */ },
    "device": { /* 35+ device features */ },
    "semantic": { /* 32+ semantic features */ },
    "combined_embedding": [ /* 128-dim array */ ]
  }
}
```

**Response** (200 OK):
```json
{
  "success": true,
  "message": "Behavioral commitments created successfully",
  "data": {
    "commitments_created": 5,
    "profile_quality": 0.89
  }
}
```

---

### 6. Get Commitment Status

Check if user has behavioral recovery set up.

**Endpoint**: `GET /api/behavioral-recovery/commitments/status/`  
**Authentication**: Required

**Response** (200 OK):
```json
{
  "success": true,
  "data": {
    "has_commitments": true,
    "creation_date": "2025-10-07",
    "commitments_count": 5,
    "ready_for_recovery": true
  }
}
```

---

### 7. Get Next Challenge

Get next challenge for recovery attempt.

**Endpoint**: `GET /api/behavioral-recovery/challenges/{attempt_id}/next/`

**Response** (200 OK):
```json
{
  "success": true,
  "data": {
    "challenge": {
      "challenge_id": "850e8400-e29b-41d4-a716-446655440003",
      "challenge_type": "cognitive",
      "challenge_data": {
        "instruction": "Answer the following question",
        "question": "Which of these websites do you access most frequently?",
        "question_type": "multiple_choice",
        "options": ["gmail.com", "facebook.com", "amazon.com", "github.com"]
      }
    }
  }
}
```

**Response** (No more challenges):
```json
{
  "success": true,
  "message": "No more challenges available",
  "data": {
    "challenge": null
  }
}
```

---

## Data Structures

### Behavioral Data Structure

Complete behavioral data includes features from all modules:

```typescript
interface BehavioralData {
  typing: {
    // Press dynamics (8 dimensions)
    press_duration_mean: number;
    press_duration_std: number;
    press_duration_median: number;
    press_duration_cv: number;
    
    // Flight dynamics (6 dimensions)
    flight_time_mean: number;
    flight_time_std: number;
    flight_time_cv: number;
    
    // Typing speed (2 dimensions)
    typing_speed_cps: number;
    typing_speed_wpm: number;
    
    // Error patterns (3 dimensions)
    error_rate: number;
    backspace_frequency: number;
    error_corrections: number;
    
    // Rhythm (5 dimensions)
    rhythm_regularity: number;
    rhythm_variability: number;
    rhythm_entropy: number;
    rhythm_autocorrelation: number;
    
    // ... 60+ more typing dimensions
    
    total_samples: number;
    data_quality_score: number;
  };
  
  mouse: {
    // Velocity (10 dimensions)
    velocity_mean: number;
    velocity_std: number;
    velocity_median: number;
    velocity_cv: number;
    
    // Acceleration (8 dimensions)
    acceleration_mean: number;
    acceleration_std: number;
    
    // Trajectory (12 dimensions)
    direction_mean: number;
    movement_straightness: number;
    curvature_mean: number;
    
    // Clicks (10 dimensions)
    click_count: number;
    click_duration_mean: number;
    
    // ... 20+ more mouse dimensions
    
    data_quality_score: number;
  };
  
  cognitive: {
    // Decision-making (8 dimensions)
    avg_decision_time: number;
    quick_decision_rate: number;
    
    // Navigation (10 dimensions)
    navigation_efficiency: number;
    route_repetition_rate: number;
    
    // Feature usage (8 dimensions)
    feature_diversity: number;
    
    // ... 14+ more cognitive dimensions
    
    data_quality_score: number;
  };
  
  device: {
    // Device info (5 dimensions)
    device_type: string;
    screen_width: number;
    screen_height: number;
    
    // Touch/mobile (8 dimensions)
    touch_count: number;
    swipe_count: number;
    
    // ... 22+ more device dimensions
    
    data_quality_score: number;
  };
  
  semantic: {
    // Password patterns (8 dimensions)
    passwords_created: number;
    avg_password_length: number;
    
    // Organization (10 dimensions)
    folders_created: number;
    organization_style: string;
    
    // ... 14+ more semantic dimensions
    
    data_quality_score: number;
  };
}
```

### Challenge Data Structure

```typescript
interface BehavioralChallenge {
  challenge_id: string;  // UUID
  challenge_type: 'typing' | 'mouse' | 'cognitive' | 'navigation';
  challenge_data: {
    type: string;
    instruction: string;
    // Type-specific data
    sentence?: string;        // For typing
    targets?: Target[];       // For mouse
    question?: string;        // For cognitive
    options?: string[];       // For cognitive
  };
  created_at: string;  // ISO timestamp
}
```

---

## Error Codes

| Code | Description | HTTP Status |
|------|-------------|-------------|
| `no_commitments` | User has no behavioral commitments | 400 |
| `low_similarity` | Similarity score below threshold | 400 |
| `not_found` | Recovery attempt not found | 404 |
| `invalid_challenge` | Challenge ID invalid | 400 |
| `expired` | Recovery attempt expired | 400 |
| `server_error` | Internal server error | 500 |

---

## Rate Limiting

All behavioral recovery endpoints are rate-limited:

- **Anonymous users**: 10 requests/hour
- **Authenticated users**: 100 requests/hour
- **Challenge submission**: 50/hour

---

## Security Headers

All responses include security headers:

```http
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
X-XSS-Protection: 1; mode=block
Strict-Transport-Security: max-age=31536000
```

---

## Webhook Events (Future)

Future webhook support for recovery events:

- `recovery.initiated`
- `recovery.challenge_completed`
- `recovery.similarity_threshold_met`
- `recovery.completed`
- `recovery.failed`
- `security.adversarial_detected`

---

## Examples

### Python Example

```python
import requests

# Initiate recovery
response = requests.post(
    'http://127.0.0.1:8000/api/behavioral-recovery/initiate/',
    json={'email': 'user@example.com'}
)

attempt = response.json()['data']
print(f"Recovery attempt ID: {attempt['attempt_id']}")

# Submit challenge
challenge_response = {
    'attempt_id': attempt['attempt_id'],
    'challenge_id': attempt['first_challenge']['challenge_id'],
    'behavioral_data': {
        'typing': {'typing_speed_wpm': 65, 'error_rate': 0.05},
        'data_quality_score': 0.85
    }
}

result = requests.post(
    'http://127.0.0.1:8000/api/behavioral-recovery/submit-challenge/',
    json=challenge_response
)

print(f"Similarity score: {result.json()['data']['similarity_score']}")
```

### JavaScript/React Example

```javascript
import axios from 'axios';

// Initiate recovery
const initiateRecovery = async (email) => {
  const response = await axios.post('/api/behavioral-recovery/initiate/', {
    email
  });
  
  return response.data.data;
};

// Submit challenge
const submitChallenge = async (attemptId, challengeId, behavioralData) => {
  const response = await axios.post('/api/behavioral-recovery/submit-challenge/', {
    attempt_id: attemptId,
    challenge_id: challengeId,
    behavioral_data: behavioralData
  });
  
  return response.data.data;
};

// Complete recovery
const completeRecovery = async (attemptId, newPassword) => {
  const response = await axios.post('/api/behavioral-recovery/complete/', {
    attempt_id: attemptId,
    new_password: newPassword
  });
  
  return response.data;
};
```

---

## Versioning

API Version: **1.0.0**

Future versions will use URL versioning:
```
/api/v2/behavioral-recovery/...
```

---

## Support

For API support:
- **Documentation**: Read architecture docs
- **Tests**: Check `tests/behavioral_recovery/`
- **Issues**: Report via GitHub
- **Email**: support@yourdomain.com


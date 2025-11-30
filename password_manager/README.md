# Password Manager - Backend

A secure password manager backend built with Django, featuring end-to-end encryption, zero-knowledge architecture, quantum-resistant cryptography, and advanced security features.

## Features

- **End-to-end encryption** of all sensitive data
- **Zero-knowledge architecture** (server never sees plaintext data)
- **Cross-device synchronization**
- **Secure password generation**
- **Dark web breach monitoring** with ML-powered analysis
- **Emergency access and recovery options**
- **WebAuthn/passkey support**
- **Quantum-resistant cryptography** (Kyber/CRYSTALS)
- **Behavioral biometric authentication**
- **Blockchain anchoring** for audit trails
- **Fully Homomorphic Encryption (FHE)** support
- **OpenID Connect (OIDC)** for Enterprise SSO (Okta, Azure AD, Auth0, Google)

---

## OpenID Connect (OIDC) Integration

SecureVault supports OIDC for enterprise Single Sign-On integration.

### Supported OIDC Providers

| Provider | Status | Notes |
|----------|--------|-------|
| Google | ✅ Supported | Via `accounts.google.com` |
| Okta | ✅ Supported | Enterprise SSO |
| Azure AD | ✅ Supported | Microsoft Identity Platform |
| Auth0 | ✅ Supported | Universal Login |
| Keycloak | ✅ Supported | Open-source IdP |
| Custom | ✅ Supported | Any OIDC-compliant provider |

### OIDC Features

- **Auto-discovery** via `.well-known/openid-configuration`
- **ID Token validation** with JWKS (RS256, HS256)
- **Nonce validation** for replay attack protection
- **PKCE support** (Proof Key for Code Exchange)
- **Standard claims** extraction (sub, email, name, picture)
- **Automatic user provisioning** from OIDC claims
- **Token caching** for improved performance

### OIDC Configuration

Configure via environment variables in `.env`:

```bash
# OIDC Provider Settings
OIDC_RP_CLIENT_ID=your-client-id
OIDC_RP_CLIENT_SECRET=your-client-secret
OIDC_OP_BASE_URL=https://accounts.google.com

# Security Settings
OIDC_VERIFY_SSL=True
OIDC_USE_NONCE=True
OIDC_STATE_LENGTH=32
OIDC_NONCE_LENGTH=32

# Optional: Override discovery endpoints
OIDC_OP_JWKS_ENDPOINT=
OIDC_OP_USER_ENDPOINT=
```

---

## Project Structure

```
password_manager/
├── manage.py                    # Django management script
├── requirements.txt             # Python dependencies
├── Dockerfile                   # Container configuration
├── middleware.py                # Global middleware
├── db.sqlite3                   # SQLite database (development)
├── env.example                  # Environment variables template
│
├── password_manager/            # Core Django project configuration
├── auth_module/                 # Authentication & authorization
├── vault/                       # Password vault management
├── security/                    # Security services & monitoring
├── behavioral_recovery/         # Behavioral biometric recovery
├── blockchain/                  # Blockchain anchoring service
├── email_masking/               # Email alias & masking service
├── fhe_service/                 # Fully Homomorphic Encryption
├── ml_dark_web/                 # ML-powered dark web monitoring
├── ml_security/                 # ML-based security features
├── logging_manager/             # Centralized logging
├── analytics/                   # Usage analytics
├── ab_testing/                  # A/B testing framework
├── user/                        # User management
├── api/                         # Core API endpoints
├── shared/                      # Shared utilities & constants
├── templates/                   # Email templates
├── geoip/                       # GeoIP databases
├── ml_data/                     # ML training data
├── ml_models/                   # Trained ML models
├── logs/                        # Application logs
└── public/                      # Static assets
```

---

## Directory & File Descriptions

### `password_manager/` (Core Configuration)

The main Django project configuration module.

| File | Description |
|------|-------------|
| `settings.py` | Django settings, database config, installed apps, middleware, security settings |
| `urls.py` | Root URL routing for all API endpoints |
| `wsgi.py` | WSGI application entry point for production |
| `asgi.py` | ASGI application for async support & WebSockets |
| `celery.py` | Celery task queue configuration |
| `api_utils.py` | Standardized API response utilities (`success_response`, `error_response`) |
| `throttling.py` | Rate limiting configuration |
| `compression_middleware.py` | Response compression middleware |
| `warning_suppressions.py` | Suppress non-critical warnings |
| `blockchain/services/` | Blockchain service initialization |

---

### `auth_module/` (Authentication)

Handles all authentication, authorization, and user session management.

| File/Directory | Description |
|----------------|-------------|
| `views.py` | Core authentication views (login, logout, registration) |
| `models.py` | User session, device, and authentication models |
| `serializers.py` | DRF serializers for auth data |
| `urls.py` | Authentication URL routing |
| `passkey_views.py` | WebAuthn/Passkey registration and authentication |
| `mfa_views.py` | Multi-factor authentication endpoints |
| `mfa_models.py` | MFA-related database models |
| `mfa_integration.py` | MFA service integration |
| `oauth_views.py` | OAuth/Social login handlers (Google, GitHub, etc.) |
| `oidc_views.py` | OpenID Connect (OIDC) authentication endpoints |
| `kyber_views.py` | Quantum-resistant Kyber key exchange |
| `quantum_recovery_views.py` | Quantum-safe recovery endpoints |
| `quantum_recovery_models.py` | Models for quantum recovery data |
| `passkey_primary_recovery_views.py` | Passkey-based account recovery |
| `passkey_primary_recovery_models.py` | Recovery passkey models |
| `recovery_monitoring.py` | Recovery process monitoring |
| `recovery_throttling.py` | Rate limiting for recovery attempts |
| `firebase.py` | Firebase authentication integration |
| `utils.py` | Authentication utility functions |

#### `auth_module/services/`

| Service | Description |
|---------|-------------|
| `kyber_crypto.py` | Kyber (CRYSTALS) post-quantum cryptography |
| `kyber_cache.py` | Caching for Kyber key operations |
| `kyber_monitor.py` | Monitoring Kyber operations |
| `parallel_kyber.py` | Parallelized Kyber operations |
| `optimized_ntt.py` | Number Theoretic Transform optimization |
| `quantum_crypto_service.py` | Quantum-safe cryptographic operations |
| `authy_service.py` | Twilio Authy integration for 2FA |
| `oidc_service.py` | OpenID Connect service (discovery, token validation, JWKS) |
| `notification_service.py` | Auth notification delivery |
| `challenge_generator.py` | Security challenge generation |
| `trust_scorer.py` | Device/session trust scoring |
| `passkey_primary_recovery_service.py` | Passkey recovery business logic |

---

### `vault/` (Password Vault)

Core password vault functionality with encryption, backup, and sharing.

| File/Directory | Description |
|----------------|-------------|
| `urls.py` | Vault API URL routing |
| `urls_shared_folders.py` | Shared folder URL routing |
| `serializer.py` | DRF serializers for vault items |
| `crypto.py` | Server-side cryptographic utilities |
| `tasks.py` | Celery tasks for background operations |

#### `vault/models/`

| Model | Description |
|-------|-------------|
| `vault_models.py` | Core vault item model |
| `backup_models.py` | Vault backup/restore models |
| `folder_models.py` | Folder organization models |
| `shared_folder_models.py` | Shared vault folder models |
| `Key_derivation_models.py` | Key derivation parameters |
| `Encrypted_credentials_models.py` | Encrypted credential storage |
| `Breach_Alerts.py` | Password breach alert models |

#### `vault/views/`

| View | Description |
|------|-------------|
| `api_views.py` | REST API views for vault operations |
| `crud_views.py` | Create, read, update, delete operations |
| `backup_views.py` | Backup and restore endpoints |
| `folder_views.py` | Folder management views |
| `shared_folder_views.py` | Shared folder operations |
| `shared_folder_views_part2.py` | Additional sharing features |

#### `vault/services/`

| Service | Description |
|---------|-------------|
| `cloud_storage.py` | Cloud backup storage integration |
| `vault_optimization_service.py` | Performance optimization |

---

### `security/` (Security Services)

Security monitoring, breach detection, and account protection.

| File/Directory | Description |
|----------------|-------------|
| `views.py` | Security-related API endpoints |
| `models.py` | Security event models |
| `serializers.py` | Security data serializers |
| `urls.py` | Security URL routing |
| `notifications.py` | Security alert notifications |
| `tasks.py` | Background security tasks |
| `api/` | Security API sub-module |

#### `security/services/`

| Service | Description |
|---------|-------------|
| `security_service.py` | Core security operations |
| `breach_monitor.py` | Password breach monitoring |
| `hibp.py` | Have I Been Pwned API integration |
| `account_protection.py` | Account lockout & protection |
| `crypto_service.py` | Cryptographic utilities |
| `ecc_service.py` | Elliptic Curve Cryptography |

---

### `behavioral_recovery/` (Behavioral Biometrics)

Behavioral biometric-based account recovery system.

| File/Directory | Description |
|----------------|-------------|
| `views.py` | Behavioral recovery API endpoints |
| `models.py` | Behavioral profile models |
| `serializers.py` | Behavioral data serializers |
| `urls.py` | URL routing |
| `signals.py` | Django signals for behavior events |
| `tasks.py` | Background behavioral analysis |
| `ab_tests/` | A/B testing for recovery flows |
| `analytics/` | Behavioral analytics |

#### `behavioral_recovery/services/`

| Service | Description |
|---------|-------------|
| `recovery_orchestrator.py` | Coordinates recovery process |
| `challenge_generator.py` | Generates behavioral challenges |
| `commitment_service.py` | Cryptographic commitments |
| `quantum_crypto_service.py` | Quantum-safe behavioral auth |
| `adversarial_detector.py` | Detects spoofing attacks |
| `duress_detector.py` | Detects coerced authentication |

---

### `blockchain/` (Blockchain Anchoring)

Immutable audit trail using blockchain technology.

| File/Directory | Description |
|----------------|-------------|
| `views.py` | Blockchain API endpoints |
| `models.py` | Anchor & verification models |
| `urls.py` | URL routing |
| `tasks.py` | Async blockchain operations |

#### `blockchain/services/`

| Service | Description |
|---------|-------------|
| `BlockchainAnchorService` | Anchors data hashes to blockchain |
| Additional services | Verification & retrieval |

---

### `email_masking/` (Email Alias Service)

Create and manage email aliases for privacy protection.

| File/Directory | Description |
|----------------|-------------|
| `views.py` | Email masking API endpoints |
| `models.py` | Email alias models |
| `urls.py` | URL routing |

#### `email_masking/services/`

| Service | Description |
|---------|-------------|
| Email alias creation | Generate random email aliases |
| Email forwarding | Forward masked emails to real address |
| Alias management | Enable/disable/delete aliases |

---

### `fhe_service/` (Fully Homomorphic Encryption)

Perform computations on encrypted data without decryption.

| File/Directory | Description |
|----------------|-------------|
| `views.py` | FHE API endpoints |
| `models.py` | FHE operation models |
| `urls.py` | URL routing |

#### `fhe_service/services/`

| Service | Description |
|---------|-------------|
| `seal_service.py` | Microsoft SEAL FHE library |
| `concrete_service.py` | Zama Concrete FHE library |
| `fhe_router.py` | Routes to appropriate FHE backend |
| `fhe_cache.py` | Caching for FHE operations |
| `adaptive_manager.py` | Adapts FHE parameters dynamically |

---

### `ml_dark_web/` (Dark Web Monitoring)

ML-powered dark web credential monitoring.

| File/Directory | Description |
|----------------|-------------|
| `views.py` | Dark web monitoring API |
| `models.py` | Breach & monitoring models |
| `urls.py` | URL routing |
| `consumers.py` | WebSocket consumers for real-time alerts |
| `routing.py` | WebSocket routing |
| `ml_services.py` | ML model inference |
| `ml_config.py` | ML configuration |
| `pgvector_service.py` | Vector similarity search |
| `signals.py` | Event signals |
| `tasks.py` | Background monitoring tasks |
| `middleware.py` | Request processing |
| `scrapers/` | Dark web data collection |
| `training/` | ML model training scripts |

---

### `ml_security/` (ML Security Features)

Machine learning models for security analysis.

| File/Directory | Description |
|----------------|-------------|
| `views.py` | ML security API endpoints |
| `models.py` | ML prediction models |
| `urls.py` | URL routing |
| `training/` | Model training scripts |

#### `ml_security/ml_models/`

| Model | Description |
|-------|-------------|
| `password_strength.py` | ML-based password strength analysis |
| `anomaly_detector.py` | Behavioral anomaly detection |
| `threat_analyzer.py` | Threat pattern analysis |
| `behavioral_dna_model.py` | Behavioral biometric model |
| `behavioral_training.py` | Training behavioral models |
| `biometric_authenticator.py` | Biometric authentication |
| `performance_optimizer.py` | Model optimization |

---

### `logging_manager/` (Centralized Logging)

Centralized logging and audit trail management.

| File | Description |
|------|-------------|
| `views.py` | Log viewing endpoints |
| `models.py` | Log entry models |
| `handlers.py` | Custom log handlers |

---

### `analytics/` (Usage Analytics)

Track and analyze application usage patterns.

| File | Description |
|------|-------------|
| `views.py` | Analytics API endpoints |
| `models.py` | Analytics event models |
| `urls.py` | URL routing |

---

### `ab_testing/` (A/B Testing)

Feature experimentation and A/B testing framework.

| File | Description |
|------|-------------|
| `views.py` | A/B test endpoints |
| `models.py` | Experiment & variant models |
| `urls.py` | URL routing |

---

### `user/` (User Management)

User profile and preference management.

| File | Description |
|------|-------------|
| `views.py` | User profile endpoints |
| `models.py` | Extended user model |
| `serializers.py` | User data serializers |

---

### `api/` (Core API)

Core API health checks and shared endpoints.

| File | Description |
|------|-------------|
| `views.py` | General API views |
| `health.py` | Health check endpoints |
| `urls.py` | API URL routing |

---

### `shared/` (Shared Utilities)

Common utilities, constants, and helpers.

| File | Description |
|------|-------------|
| `constants.py` | Application-wide constants |
| `utils.py` | Utility functions |
| `validators.py` | Custom validation functions |
| `decorators.py` | Custom decorators |
| `error_handlers.py` | Global error handling |
| `performance_middleware.py` | Performance monitoring |
| `performance_views.py` | Performance metrics API |
| `crypto/` | Shared cryptographic utilities |
| `views/` | Shared view utilities |

---

### Other Files & Directories

| Path | Description |
|------|-------------|
| `templates/recovery/` | Email templates for recovery flows |
| `geoip/` | MaxMind GeoIP databases for location detection |
| `ml_data/` | Training data for ML models |
| `ml_models/` | Serialized trained models |
| `logs/` | Application log files (`django.log`, `security.log`, `debug.log`) |
| `public/assets/` | Public static assets |
| `setup_geoip.py` | GeoIP database setup script |
| `setup_python3_13.py` | Python 3.13 compatibility script |
| `install_webauthn_deps.py` | WebAuthn dependency installer |

---

## API Documentation

### Authentication Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/auth/register/` | POST | Register a new user |
| `/auth/login/` | POST | Log in a user |
| `/auth/logout/` | POST | Log out current user |
| `/auth/verify_master/` | POST | Verify master password |
| `/auth/change_master/` | POST | Change master password |
| `/auth/two_factor_auth/` | GET/POST | Manage 2FA |
| `/auth/setup-recovery-key/` | POST | Set up recovery key |
| `/auth/passkey/register/begin/` | POST | Begin passkey registration |
| `/auth/passkey/register/complete/` | POST | Complete passkey registration |

### OIDC (OpenID Connect) Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/auth/oidc/.well-known/openid-configuration/` | GET | OIDC Discovery document |
| `/auth/oidc/.well-known/jwks.json` | GET | JSON Web Key Set (JWKS) |
| `/auth/oidc/providers/` | GET | List configured OIDC providers |
| `/auth/oidc/authorize/` | POST | Initiate OIDC authorization |
| `/auth/oidc/callback/` | GET | Handle OIDC callback |
| `/auth/oidc/userinfo/` | GET | Get authenticated user info |
| `/auth/oidc/token/` | POST | Token endpoint (for RP) |
| `/auth/oidc/logout/` | POST | OIDC logout |

### Vault Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/vault/` | GET | List all vault items |
| `/vault/` | POST | Create a new vault item |
| `/vault/{id}/` | PUT | Update a vault item |
| `/vault/{id}/` | DELETE | Delete a vault item |
| `/vault/get_salt/` | GET | Get user's encryption salt |
| `/vault/verify_master_password/` | POST | Verify master password |
| `/vault/sync/` | POST | Sync vault items |
| `/vault/create_backup/` | POST | Create vault backup |
| `/vault/backups/` | GET | List backups |
| `/vault/restore_backup/{id}/` | POST | Restore from backup |

### Security Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/security/check_breached/` | POST | Check for breached passwords |
| `/security/audit_log/` | GET | Get security audit logs |

---

## Setup

### Requirements

- Python 3.8+ (compatible with Python 3.13)
- PostgreSQL (production) / SQLite (development)
- Redis (for Celery)
- Node.js 14+ (for frontend)

### Development Setup

1. Create virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # Windows: venv\Scripts\activate
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Configure environment:
   ```bash
   cp env.example .env
   # Edit .env with your settings
   ```

4. Run migrations:
   ```bash
   python manage.py migrate
   ```

5. Start development server:
   ```bash
   python manage.py runserver
   ```

---

## Security Notes

- All encryption/decryption happens client-side
- Server only stores encrypted data
- Master password never transmitted to server
- Key derivation uses Argon2id with high work factors
- API endpoints enforce CSRF and rate limiting
- WebAuthn/passkeys add second factor for authentication
- Quantum-resistant cryptography protects against future threats

---

## API Response Standards

All API endpoints use standardized responses:

```python
# Success response
{
  "success": true,
  "message": "Operation successful",
    "data": { ... }
}

# Error response
{
  "success": false,
  "message": "Error message",
  "code": "error_code",
    "details": { ... }
}
```

See [API_STANDARDS.md](./API_STANDARDS.md) for detailed documentation.

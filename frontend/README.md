# Password Manager - Frontend

A secure, modern password manager frontend built with React and Vite, featuring end-to-end encryption, zero-knowledge architecture, and advanced security features.

## Features

- **Zero-knowledge encryption** - All encryption/decryption happens in the browser
- **Modern React UI** with Vite for fast development
- **WebAuthn/Passkey support** for passwordless authentication
- **Behavioral biometric authentication**
- **Dark web breach monitoring**
- **Secure password generator**
- **Cross-device synchronization**
- **Quantum-resistant cryptography** integration
- **Offline support** with service workers
- **OpenID Connect (OIDC)** for Enterprise SSO (Okta, Azure AD, Auth0)

---

## Project Structure

```
frontend/
├── public/                      # Static public assets
├── src/                         # Source code
│   ├── Components/              # React components
│   ├── contexts/                # React context providers
│   ├── hooks/                   # Custom React hooks
│   ├── services/                # API & business logic services
│   ├── ml/                      # Client-side ML models
│   ├── utils/                   # Utility functions
│   ├── workers/                 # Web Workers
│   ├── App.jsx                  # Main application component
│   ├── main.jsx                 # Application entry point
│   └── index.css                # Global styles
├── package.json                 # Dependencies & scripts
├── vite.config.js               # Vite configuration
├── vitest.config.js             # Test configuration
├── vercel.json                  # Vercel deployment config
└── Dockerfile                   # Container configuration
```

---

## Directory & File Descriptions

### `src/Components/` (UI Components)

Organized by feature/domain for maintainability.

#### `Components/auth/` - Authentication Components

| Component | Description |
|-----------|-------------|
| `Login.jsx` | Login form with email/password and social login |
| `Login.css` | Login page styles |
| `BiometricAuth.jsx` | Biometric authentication (fingerprint, face) |
| `BiometricSetup.jsx` | Configure biometric authentication |
| `PasskeyAuth.jsx` | WebAuthn passkey authentication |
| `PasskeyManagement.jsx` | Manage registered passkeys |
| `PasskeyManagement.css` | Passkey management styles |
| `PasskeyRegistration.jsx` | Register new passkeys |
| `PasskeyPrimaryRecoverySetup.jsx` | Setup passkey-based recovery |
| `PasskeyPrimaryRecoveryInitiate.jsx` | Initiate passkey recovery |
| `PasswordRecovery.jsx` | Password recovery flow |
| `RecoveryKeySetup.jsx` | Setup recovery key |
| `QuantumRecoverySetup.jsx` | Quantum-safe recovery setup |
| `TwoFactorSetup.jsx` | Configure 2FA (TOTP, SMS) |
| `OAuthCallback.jsx` | OAuth redirect handler |
| `SocialLoginButtons.jsx` | Google, GitHub, etc. login buttons |
| `SocialMediaLogin.jsx` | Social media login integration |

#### `Components/vault/` - Vault Components

| Component | Description |
|-----------|-------------|
| `VaultList.jsx` | Display list of vault items |
| `VaultItem.jsx` | Individual vault item display |
| `VaultItemDetail.jsx` | Detailed view of a vault item |
| `VaultSearch.jsx` | Search/filter vault items |
| `VaultItemCard.jsx` | Card-style vault item |
| `VaultGrid.jsx` | Grid layout for vault items |
| `AddItemButton.jsx` | Button to add new items |
| `PasswordGenerator.jsx` | Generate secure passwords |

#### `Components/forms/` - Form Components

| Component | Description |
|-----------|-------------|
| `PasswordForm.jsx` | Add/edit password entries |
| `PasswordItemForm.jsx` | Password item form wrapper |
| `CardForm.jsx` | Add/edit credit card details |
| `IdentityForm.jsx` | Add/edit identity information |
| `NoteForm.jsx` | Add/edit secure notes |

#### `Components/security/` - Security Components

| Component | Description |
|-----------|-------------|
| `AccountProtection.jsx` | Account security settings |
| `PasswordGenerator.jsx` | Secure password generator |
| `PasswordStrengthMeter.jsx` | Visual password strength indicator |
| `PasswordStrengthMeterML.jsx` | ML-powered password analysis |
| `PasswordStrengthMeterML.css` | ML meter styles |
| `SessionMonitor.jsx` | Active session monitoring |
| `SessionMonitor.css` | Session monitor styles |
| `BiometricReauth.jsx` | Re-authentication prompt |
| `components/` | Sub-components for security features |
| `services/` | Security-related services |
| `api/` | Security API integration |

#### `Components/dashboard/` - Dashboard Components

| Component | Description |
|-----------|-------------|
| `VaultDashboard.jsx` | Main vault dashboard |
| `BehavioralRecoveryStatus.jsx` | Show behavioral recovery status |

#### `Components/settings/` - Settings Components

| Component | Description |
|-----------|-------------|
| `SettingsPage.jsx` | Main settings page |
| `SettingsComponents.jsx` | Reusable settings UI components |
| `SecuritySettings.jsx` | Security preferences |
| `PrivacySettings.jsx` | Privacy configuration |
| `NotificationSettings.jsx` | Notification preferences |
| `ThemeSettings.jsx` | UI theme customization |
| `VaultSettings.jsx` | Vault-specific settings |
| `AdaptiveMFASettings.jsx` | Adaptive MFA configuration |

#### `Components/recovery/` - Recovery Components

##### `recovery/behavioral/` - Behavioral Recovery
| Component | Description |
|-----------|-------------|
| Behavioral biometric recovery challenge flow |
| Profile status and verification |

##### `recovery/blockchain/` - Blockchain Recovery
| Component | Description |
|-----------|-------------|
| Blockchain-anchored recovery verification |

##### `recovery/social/` - Social Recovery
| Component | Description |
|-----------|-------------|
| Trusted contacts recovery flow |
| Guardian management |

#### `Components/emailmasking/` - Email Masking Components

| Component | Description |
|-----------|-------------|
| `EmailMaskingDashboard.jsx` | Email alias management dashboard |
| `CreateAliasModal.jsx` | Create new email alias |
| `AliasCard.jsx` | Display email alias |
| `AliasDetailsModal.jsx` | Alias details view |
| `AliasActivityModal.jsx` | View alias activity |
| `ProviderSetup.jsx` | Setup email provider |
| `ProviderSetupModal.jsx` | Provider configuration modal |

#### `Components/sharedfolders/` - Shared Folders Components

| Component | Description |
|-----------|-------------|
| `SharedFoldersDashboard.jsx` | Shared folders overview |
| `CreateFolderModal.jsx` | Create shared folder |
| `FolderDetailsModal.jsx` | Folder details and members |
| `InvitationsModal.jsx` | Manage folder invitations |

#### `Components/admin/` - Admin Components

| Component | Description |
|-----------|-------------|
| `PerformanceMonitoring.jsx` | System performance metrics |
| `RecoveryDashboard.jsx` | Admin recovery management |
| `RecoveryDashboard.css` | Recovery dashboard styles |
| `metrics/` | Detailed metrics components |

#### `Components/layout/` - Layout Components

| Component | Description |
|-----------|-------------|
| `Header.jsx` | Application header/navbar |
| `Sidebar.jsx` | Navigation sidebar |
| `PageLayout.jsx` | Page layout wrapper |

#### `Components/common/` - Shared Components

| Component | Description |
|-----------|-------------|
| `Button.jsx` | Reusable button component |
| `Input.jsx` | Styled input component |
| `Modal.jsx` | Modal dialog component |
| `Icon.jsx` | Icon component wrapper |
| `Tooltip.jsx` | Tooltip component |
| `LoadingIndicator.jsx` | Loading spinner/skeleton |
| `ErrorBoundary.jsx` | Error boundary wrapper |
| `ErrorDisplay.jsx` | Error message display |

#### `Components/animations/` - Animation Components

| Component | Description |
|-----------|-------------|
| `ParticleBackground.jsx` | Animated particle background |

#### `Components/autofill/` - Autofill Components

| Component | Description |
|-----------|-------------|
| `AutofillSuggestion.jsx` | Browser autofill suggestions |

---

### `src/contexts/` (React Context Providers)

State management using React Context API.

| Context | Description |
|---------|-------------|
| `AuthContext.jsx` | Authentication state, login/logout, user info |
| `VaultContext.jsx` | Vault items, encryption key, sync state |
| `BehavioralContext.jsx` | Behavioral biometric data collection |
| `AccessibilityContext.jsx` | Accessibility settings & preferences |

---

### `src/hooks/` (Custom React Hooks)

Reusable logic encapsulated in custom hooks.

| Hook | Description |
|------|-------------|
| `useAuth.jsx` | Authentication operations |
| `useSecureVault.js` | Secure vault operations with encryption |
| `useSecureSession.js` | Secure session management |
| `useBehavioralRecovery.js` | Behavioral recovery flow |
| `useBiometricReauth.js` | Biometric re-authentication |
| `useBreachWebSocket.js` | Real-time breach notifications |
| `useKyber.js` | Kyber quantum-resistant crypto |

---

### `src/services/` (Business Logic Services)

Core application services for API communication and business logic.

#### Core Services

| Service | Description |
|---------|-------------|
| `api.js` | Axios-based API client with interceptors |
| `vaultService.js` | Vault CRUD operations, sync |
| `cryptoService.js` | Client-side encryption (AES-GCM, PBKDF2) |
| `secureVaultService.js` | Enhanced secure vault operations |
| `secureVaultCrypto.js` | Vault-specific crypto operations |
| `secureStorageService.js` | Secure local storage |
| `webSecureStorage.js` | Web Crypto API storage |
| `xchachaEncryption.js` | XChaCha20-Poly1305 encryption |

#### Authentication Services

| Service | Description |
|---------|-------------|
| `mfaService.js` | Multi-factor authentication |
| `oauthService.js` | OAuth/social login |
| `oidcService.js` | OpenID Connect (OIDC) for Enterprise SSO |
| `firebaseService.js` | Firebase authentication |

#### Security Services

| Service | Description |
|---------|-------------|
| `darkWebService.js` | Dark web breach checking |
| `mlSecurityService.js` | ML-based security analysis |
| `accountProtectionService.js` | Account protection features |
| `eccService.js` | Elliptic Curve Cryptography |

#### Analytics & Monitoring

| Service | Description |
|---------|-------------|
| `analyticsService.js` | Usage analytics tracking |
| `performanceMonitor.js` | Performance metrics collection |
| `errorTracker.js` | Error tracking & reporting |
| `abTestingService.js` | A/B test variant assignment |
| `preferencesService.js` | User preference management |

#### `services/quantum/` - Quantum Cryptography

| Service | Description |
|---------|-------------|
| Kyber key exchange | Post-quantum key encapsulation |
| Quantum-safe encryption | Future-proof cryptography |

#### `services/fhe/` - Fully Homomorphic Encryption

| Service | Description |
|---------|-------------|
| FHE client | Encrypted computation client |
| SEAL integration | Microsoft SEAL client |

#### `services/blockchain/` - Blockchain Services

| Service | Description |
|---------|-------------|
| Anchor service | Blockchain anchoring client |
| Smart contract ABI | Contract interface definitions |

#### OIDC Service (`oidcService.js`)

OpenID Connect integration for enterprise Single Sign-On.

| Feature | Description |
|---------|-------------|
| `getDiscovery()` | Fetch OIDC discovery configuration |
| `getProviders()` | List available OIDC providers |
| `initiateAuth()` | Start OIDC authentication flow |
| `handleCallback()` | Process OIDC callback with tokens |
| `validateIdToken()` | Verify ID token signature and claims |
| `generateNonce()` | Generate cryptographic nonce |
| `generateState()` | Generate state parameter with embedded data |

**Supported Providers:**
- Google (`accounts.google.com`)
- Okta (Enterprise SSO)
- Azure AD (Microsoft Identity)
- Auth0 (Universal Login)
- Any OIDC-compliant provider

#### `services/behavioralCapture/` - Behavioral Biometrics

| Service | Description |
|---------|-------------|
| Keystroke dynamics | Typing pattern capture |
| Mouse movement | Mouse behavior capture |
| Touch patterns | Touch/gesture capture |
| Behavioral profile | Profile aggregation |

---

### `src/ml/` (Client-Side Machine Learning)

On-device ML models for privacy-preserving analysis.

#### `ml/behavioralDNA/` - Behavioral DNA

| Module | Description |
|--------|-------------|
| `index.js` | Main entry point |
| `TransformerModel.js` | Transformer-based behavioral model |
| `HybridModel.js` | Hybrid ML architecture |
| `BehavioralSimilarity.js` | Behavioral pattern matching |
| `FederatedTraining.js` | Federated learning client |
| `ModelLoader.js` | Model loading utilities |
| `BackendAPI.js` | Backend communication |

#### `ml/privacy/` - Privacy-Preserving ML

| Module | Description |
|--------|-------------|
| Differential privacy | Privacy-preserving data analysis |

---

### `src/utils/` (Utility Functions)

Helper functions and utilities.

| Utility | Description |
|---------|-------------|
| `deviceFingerprint.js` | Browser fingerprint generation |
| `clipboard.js` | Secure clipboard operations |
| `errorHandler.js` | Error handling utilities |
| `kyber-wasm-loader.js` | WASM Kyber loader |
| `kyber-cache.js` | Kyber operation caching |
| `NetworkQualityEstimator.js` | Network quality detection |
| `OfflineQueueManager.js` | Offline operation queue |
| `serviceWorkerRegistration.js` | PWA service worker |

---

### `src/workers/` (Web Workers)

Background processing in separate threads.

| Worker | Description |
|--------|-------------|
| `kyber-worker.js` | Kyber crypto operations in background |

---

### Root Files

| File | Description |
|------|-------------|
| `App.jsx` | Main application component with routing |
| `App.css` | Application-wide styles |
| `App.test.js` | Application tests |
| `main.jsx` | React entry point, renders App |
| `index.css` | Global CSS, CSS variables |
| `Modal.jsx` | Global modal component |
| `Modal.css` | Modal styles |
| `logo.svg` | Application logo |
| `reportWebVitals.js` | Performance reporting |
| `setupTests.js` | Test configuration |

---

### Configuration Files

| File | Description |
|------|-------------|
| `package.json` | Dependencies, scripts, metadata |
| `package-lock.json` | Dependency lock file |
| `vite.config.js` | Vite build configuration |
| `vitest.config.js` | Vitest test configuration |
| `vercel.json` | Vercel deployment settings |
| `Dockerfile` | Docker container configuration |
| `env.example` | Environment variables template |
| `.npmrc` | npm configuration |
| `.gitignore` | Git ignore patterns |

---

## Available Scripts

### `npm run dev`

Runs the app in development mode with Vite's fast HMR.
Open [http://localhost:3000](http://localhost:3000) to view in browser.

### `npm test`

Launches Vitest test runner in watch mode.

### `npm run build`

Builds the app for production to the `dist` folder.
Optimized and minified for best performance.

### `npm run preview`

Serves the production build locally for testing.

---

## Setup

### Requirements

- Node.js 14+
- npm or yarn

### Development Setup

1. Install dependencies:
   ```bash
   npm install
   ```

2. Configure environment:
   ```bash
   cp env.example .env
   # Edit .env with your API URL and settings
   ```

3. Start development server:
   ```bash
   npm run dev
   ```

4. Open [http://localhost:3000](http://localhost:3000)

---

## Environment Variables

| Variable | Description |
|----------|-------------|
| `VITE_API_BASE_URL` | Backend API base URL |
| `VITE_API_TIMEOUT` | API request timeout (ms) |
| `VITE_ENABLE_ANALYTICS` | Enable analytics tracking |
| `VITE_FIREBASE_*` | Firebase configuration |

See `env.example` for complete list.

---

## Security Architecture

### Zero-Knowledge Model

1. **Master password** never leaves the browser
2. **Encryption keys** derived client-side using Argon2id
3. **All vault data** encrypted before transmission
4. **Server stores** only encrypted blobs
5. **Decryption** happens exclusively in browser

### Encryption Stack

- **Key Derivation**: Argon2id / PBKDF2 (600,000 iterations)
- **Symmetric Encryption**: AES-256-GCM
- **Additional**: XChaCha20-Poly1305
- **Quantum-Safe**: Kyber (CRYSTALS) key encapsulation
- **FHE**: SEAL/Concrete for encrypted computation

### Client-Side Security

- Web Crypto API for hardware-backed operations
- Secure memory handling
- Auto-lock on inactivity
- Biometric re-authentication
- Device fingerprinting

---

## API Integration

The frontend communicates with the backend through RESTful APIs:

```javascript
// Example: Fetch vault items
const response = await api.get('/vault/');

// Example: Save vault item
const response = await api.post('/vault/', {
    item_type: 'password',
    encrypted_data: encryptedData
});
```

All API responses follow standardized format:

```javascript
// Success
{ success: true, message: '...', data: {...} }

// Error
{ success: false, message: '...', code: 'error_code', details: {...} }
```

---

## Testing

```bash
# Run tests
npm test

# Run tests with coverage
npm run test:coverage

# Run specific test file
npm test -- src/services/cryptoService.test.js
```

---

## Build & Deployment

```bash
# Build for production
npm run build

# Preview production build
npm run preview

# Deploy to Vercel
vercel --prod
```

The `dist/` folder contains the production build.

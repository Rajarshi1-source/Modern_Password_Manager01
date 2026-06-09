# 🔐 SecureVault Password Manager

<div align="center">

**A Modern, Cross-Platform Password Manager with Advanced Security & AI-Powered Features**

![Version](https://img.shields.io/badge/version-2.4.0-blue.svg)
![Python](https://img.shields.io/badge/python-3.13-blue.svg)
![React](https://img.shields.io/badge/react-18.2.0-blue.svg)
![Django](https://img.shields.io/badge/django-4.2.26-green.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)
![Build](https://img.shields.io/badge/build-passing-brightgreen.svg)
![Coverage](https://img.shields.io/badge/coverage-85%25-green.svg)

[Features](#-key-features) • [Architecture](#-system-architecture) • [Setup](#-quick-start) • [API](#-api-documentation) • [Security](#-security-features) • [Deployment](#-deployment)

</div>

---

## 📋 Table of Contents

- [Overview](#-overview)
- [Key Features](#-key-features)
- [System Architecture](#-system-architecture)
- [Complete System Architecture Diagram](#-complete-system-architecture-diagram)
- [Authentication Flow Diagrams](#-authentication-flow-diagrams)
- [Data Flow Diagrams](#-data-flow-diagrams)
- [Entity Relationship Diagrams](#-entity-relationship-diagrams)
- [Zero-Knowledge Security Architecture](#-zero-knowledge-security-architecture)
- [Technology Stack](#-technology-stack)
- [Project Structure](#-project-structure)
- [Detailed Project Files Structure](#-detailed-project-files-structure)
- [Quick Start](#-quick-start)
- [Encryption & Decryption](#-encryption--decryption-mechanisms)
- [Client-Side Encryption](#-client-side-encryption)
- [CRYSTALS-Kyber Optimizations](#-crystals-kyber-optimizations)
- [Fully Homomorphic Encryption (FHE)](#-fully-homomorphic-encryption-fhe)
- [Backend Optimizations](#-backend-optimizations)
- [Authentication & Authorization](#-authentication--authorization)
- [Passkey Recovery System](#-passkey-recovery-system)
- [Master Password Recovery](#-master-password-recovery)
- [API Documentation](#-api-documentation)
- [Deployment](#-deployment)
- [File Descriptions](#-file-descriptions)
- [Contributing](#-contributing)
- [License](#-license)

---

## 🎯 Overview

SecureVault is a **next-generation password manager** that combines cutting-edge security practices with artificial intelligence to provide unparalleled protection for your digital credentials. Built with a **zero-knowledge architecture**, your data is encrypted client-side, ensuring that even we cannot access your passwords.

### What Makes SecureVault Different?

| Feature | Description |
|---------|-------------|
| 🧠 **AI-Powered Security** | ML models for password strength prediction, anomaly detection, and threat analysis |
| 🔒 **Zero-Knowledge** | Client-side encryption with WebCrypto API; server never sees plaintext data |
| 🚀 **Cross-Platform** | Web, Desktop (Windows/Mac/Linux), Mobile (iOS/Android), Browser Extensions |
| 🔑 **WebAuthn/Passkeys** | Modern passwordless authentication with biometric support |
| 🛡️ **Post-Quantum Ready** | Optimized Kyber-768 with NTT acceleration (6-8x faster) |
| 🔐 **FHE Encryption** | Fully Homomorphic Encryption for server-side computation on encrypted data |
| 🔄 **Advanced Recovery** | Primary recovery key + Social mesh fallback with behavioral biometrics |
| ⛓️ **Blockchain Anchoring** | Immutable audit trail on Arbitrum Sepolia |
| ⚡ **Performance Optimized** | Multi-level caching, Gzip/Brotli compression, async operations |
| 🔐 **Adaptive Security** | Device-aware Argon2id parameters (32-128MB based on capability) |
| 🔗 **OpenID Connect (OIDC)** | Enterprise SSO with Okta, Azure AD, Auth0, Google support |
| 🏢 **Enterprise SSO** | SAML-like federation with ID token validation |

---

## ✨ Key Features

### 🔐 Core Security Features

| Feature | Technology | Description |
|---------|------------|-------------|
| **End-to-End Encryption** | AES-GCM-256 + XChaCha20-Poly1305 | Dual cipher support with authenticated encryption |
| **Zero-Knowledge Architecture** | WebCrypto API + Client-side | Server never sees plaintext passwords |
| **Argon2id Key Derivation** | Adaptive Memory-hard KDF | 32-128MB memory with device capability detection |
| **Post-Quantum Cryptography** | CRYSTALS-Kyber-768 (Optimized) | NIST Level 3 quantum resistance with NTT acceleration |
| **Hybrid Encryption** | Kyber + X25519 | Defense in depth with combined shared secrets |
| **WebAuthn/FIDO2** | Passkey authentication | Hardware-backed passwordless login |
| **Multi-Factor Auth** | TOTP, SMS, Email, Push | Multiple 2FA options |
| **Biometric Auth** | Face, Voice, Fingerprint | Native biometric support |
| **Continuous Auth** | Behavioral biometrics | 247-dimensional behavioral DNA |
| **Hardware Security** | YubiKey compatible | Hardware key support |
| **FHE Operations** | Concrete-Python + TenSEAL | Server-side computation on encrypted data |
| **Adaptive FHE** | Intelligent routing | Auto-selects optimal FHE tier based on operation |
| **NTT Optimization** | NumPy vectorization | 6-8x faster Kyber polynomial operations |
| **Response Compression** | Gzip + Brotli | 10-50% network payload reduction |
| **Multi-Level Caching** | L1 Memory + L2 Redis | Sub-millisecond response times |

### 🤖 Machine Learning Features

| Feature | Model | Description |
|---------|-------|-------------|
| **Password Strength** | LSTM Neural Network | Real-time strength prediction |
| **Anomaly Detection** | Isolation Forest + Random Forest | Session behavior analysis |
| **Threat Analysis** | CNN-LSTM Hybrid | Multi-vector threat detection |
| **Dark Web Monitoring** | BERT + Siamese Networks | Credential breach detection |
| **Behavioral Profiling** | Transformer (247-dim) | User behavior learning |
| **Smart Suggestions** | ML-powered | Context-aware recommendations |

### 🌐 Multi-Platform Support

```
┌─────────────────────────────────────────────────────────────────────┐
│                         SECUREVAULT PLATFORMS                       │
├─────────────────┬──────────────┬─────────────┬─────────────────────┤
│   Web App       │   Desktop    │   Mobile    │   Browser Extension │
│   (React 18)    │  (Electron)  │   (Expo)    │   (Manifest v3)     │
│                 │              │             │                     │
│ • Vite bundler  │ • Windows    │ • iOS       │ • Chrome            │
│ • TensorFlow.js │ • macOS      │ • Android   │ • Firefox           │
│ • PWA support   │ • Linux      │ • Biometric │ • Edge              │
│ • WebAuthn      │ • Auto-lock  │ • Push      │ • Safari            │
└─────────────────┴──────────────┴─────────────┴─────────────────────┘
```

### 📦 Data Management Features

- **Encrypted Vault Storage** - Secure credential storage
- **Automatic Backup & Restore** - Scheduled and on-demand backups
- **Cross-Device Sync** - Real-time synchronization
- **Import/Export** - LastPass, 1Password, Bitwarden, CSV support
- **Emergency Access** - Trusted contacts with waiting period
- **Shared Folders** - Team collaboration with RBAC
- **Folder Organization** - Nested folders, tags, favorites
- **Email Masking** - SimpleLogin, AnonAddy integration

---

## 🏗️ System Architecture

### High-Level Architecture Diagram

```
┌────────────────────────────────────────────────────────────────────────────────┐
│                              CLIENT LAYER                                      │
├────────────────┬───────────────┬───────────────┬───────────────────────────────┤
│    Web App     │    Desktop    │    Mobile     │       Browser Extension       │
│   (React 18)   │  (Electron)   │ (React Native)│        (Manifest v3)          │
│                │               │               │                               │
│ ┌────────────┐ │ ┌───────────┐ │ ┌───────────┐ │ ┌─────────────────────────────┤
│ │ TensorFlow │ │ │  Native   │ │ │ Biometric │ │ │  Auto-fill Engine           │
│ │    .js     │ │ │  Keychain │ │ │   Auth    │ │ │  Password Capture           │
│ ├────────────┤ │ ├───────────┤ │ ├───────────┤ │ ├─────────────────────────────┤
│ │  Kyber-768 │ │ │ Secure    │ │ │   Push    │ │ │  Context Menu               │
│ │  (PQC)     │ │ │ Storage   │ │ │   Notif   │ │ │  Form Detection             │
│ └────────────┘ │ └───────────┘ │ └───────────┘ │ └─────────────────────────────┤
└───────┬────────┴───────┬───────┴───────┬───────┴───────────────┬───────────────┘
        │                │               │                       │
        └────────────────┴───────────────┴───────────────────────┘
                                    │
                          HTTPS/TLS 1.3 + WSS
                                    │
                        ┌───────────▼───────────┐
                        │     NGINX GATEWAY     │
                        │  (Load Balancer/SSL)  │
                        └───────────┬───────────┘
                                    │
            ┌───────────────────────┼───────────────────────┐
            │                       │                       │
    ┌───────▼───────┐       ┌───────▼───────┐       ┌───────▼───────┐
    │   Gunicorn    │       │    Daphne     │       │   Static      │
    │   (REST API)  │       │  (WebSockets) │       │   Files       │
    │   Port: 8000  │       │   Port: 8001  │       │   Port: 80    │
    └───────┬───────┘       └───────┬───────┘       └───────────────┘
            │                       │
            └───────────┬───────────┘
                        │
            ┌───────────▼───────────────────────────────────────┐
            │                 DJANGO BACKEND                    │
            ├─────────────┬─────────────┬─────────────┬─────────┤
            │ Auth Module │   Vault     │  Security   │   ML    │
            │             │   Service   │   Service   │ Engine  │
            │ • JWT Auth  │ • CRUD      │ • Breach    │ • LSTM  │
            │ • WebAuthn  │ • Backup    │   Monitor   │ • CNN   │
            │ • OAuth 2.0 │ • Sync      │ • MFA       │ • BERT  │
            │ • MFA       │ • Folders   │ • Audit     │ • IF    │
            │ • Recovery  │ • Sharing   │ • Session   │ • Siamese│
            └──────┬──────┴──────┬──────┴──────┬──────┴────┬────┘
                   │             │             │           │
    ┌──────────────┼─────────────┼─────────────┼───────────┼──────────┐
    │              │             │             │           │          │
┌───▼───┐    ┌─────▼─────┐  ┌────▼────┐   ┌────▼────┐  ┌───▼────┐     │
│ Celery│    │ PostgreSQL│  │  Redis  │   │ Channels│  │Arbitrum│     │
│Worker │    │    DB     │  │ Cache   │   │  Layer  │  │Sepolia │     │
│       │    │           │  │         │   │         │  │        │     │
│Tasks: │    │• Encrypted│  │• Session│   │• Breach │  │• Merkle│     │
│• Email│    │  Vault    │  │• Cache  │   │  Alerts │  │  Roots │     │
│• ML   │    │• pgvector │  │• Broker │   │• RT Sync│  │• Proofs│     │
│• Notif│    │• Audit Log│  │• Rate   │   │         │  │        │     │
└───────┘    └───────────┘  └─────────┘   └─────────┘  └────────┘     │
                                                                      │
 └────────────────────────────────────────────────────────────────────┘
```

---

## 🗺️ Complete System Architecture Diagram

### Full-Stack Architecture with All Components

```
╔══════════════════════════════════════════════════════════════════════════════════════════════════════════════════╗
║                                          SECUREVAULT COMPLETE SYSTEM ARCHITECTURE                                  ║
╠══════════════════════════════════════════════════════════════════════════════════════════════════════════════════╣
║                                                                                                                    ║
║  ┌────────────────────────────────────────── CLIENT TIER ─────────────────────────────────────────────┐           ║
║  │                                                                                                     │           ║
║  │  ┌─────────────────────┐  ┌─────────────────────┐  ┌─────────────────────┐  ┌─────────────────────┐│           ║
║  │  │    WEB APP          │  │    DESKTOP APP      │  │    MOBILE APP       │  │  BROWSER EXTENSION  ││           ║
║  │  │    (React 18)       │  │    (Electron)       │  │  (React Native)     │  │   (Manifest v3)     ││           ║
║  │  │                     │  │                     │  │                     │  │                     ││           ║
║  │  │ ┌─────────────────┐ │  │ ┌─────────────────┐ │  │ ┌─────────────────┐ │  │ ┌─────────────────┐ ││           ║
║  │  │ │ SecureVaultCrypto│ │  │ │  Native Keychain│ │  │ │ Biometric Auth  │ │  │ │ Autofill Engine │ ││           ║
║  │  │ │ • AES-256-GCM    │ │  │ │ • Secure Storage│ │  │ │ • Face ID       │ │  │ │ • Form Detect   │ ││           ║
║  │  │ │ • Argon2id KDF   │ │  │ │ • Auto-Lock     │ │  │ │ • Touch ID      │ │  │ │ • Pwd Capture   │ ││           ║
║  │  │ │ • WebCrypto API  │ │  │ │ • IPC Secure    │ │  │ │ • Push Notifs   │ │  │ │ • Context Menu  │ ││           ║
║  │  │ └─────────────────┘ │  │ └─────────────────┘ │  │ └─────────────────┘ │  │ └─────────────────┘ ││           ║
║  │  │                     │  │                     │  │                     │  │                     ││           ║
║  │  │ ┌─────────────────┐ │  │ ┌─────────────────┐ │  │ ┌─────────────────┐ │  │ ┌─────────────────┐ ││           ║
║  │  │ │ Kyber Service   │ │  │ │ Local DB        │ │  │ │ Expo SecureStore│ │  │ │ Secure Storage  │ ││           ║
║  │  │ │ • Kyber-768     │ │  │ │ • SQLite        │ │  │ │ • Encrypted     │ │  │ │ • chrome.storage│ ││           ║
║  │  │ │ • X25519 Hybrid │ │  │ │ • Auto-sync     │ │  │ │ • Keychain      │ │  │ │ • Local Only    │ ││           ║
║  │  │ │ • WASM Module   │ │  │ │ • Conflict Res  │ │  │ │ • Biometric Key │ │  │ │ • CSP Headers   │ ││           ║
║  │  │ └─────────────────┘ │  │ └─────────────────┘ │  │ └─────────────────┘ │  │ └─────────────────┘ ││           ║
║  │  │                     │  │                     │  │                     │  │                     ││           ║
║  │  │ ┌─────────────────┐ │  ┌────────────────────────────────────────────────┐ │ ┌─────────────────┐ ││           ║
║  │  │ │ FHE Client      │ │  │              SHARED SERVICES LAYER              │ │ │ Pwd Generator   │ ││           ║
║  │  │ │ • TFHE-rs WASM  │ │  │  • IndexedDB Cache  • Web Workers              │ │ │ • Secure Random │ ││           ║
║  │  │ │ • Key Gen       │ │  │  • Service Workers  • Behavioral Capture       │ │ │ • Policy Based  │ ││           ║
║  │  │ │ • Encrypt/Dec   │ │  │  • TensorFlow.js    • Real-time Sync           │ │ │ • Entropy Check │ ││           ║
║  │  │ └─────────────────┘ │  └────────────────────────────────────────────────┘ │ └─────────────────┘ ││           ║
║  │  └─────────────────────┴─────────────────────────────────────────────────────┴─────────────────────┘│           ║
║  └─────────────────────────────────────────────────────────────────────────────────────────────────────┘           ║
║                                                        │                                                            ║
║                                                        │ HTTPS/TLS 1.3 + WebSocket Secure                          ║
║                                                        ▼                                                            ║
║  ┌───────────────────────────────────────── GATEWAY TIER ────────────────────────────────────────────┐             ║
║  │                                                                                                    │             ║
║  │  ┌──────────────────────────────────────────────────────────────────────────────────────────────┐ │             ║
║  │  │                                   NGINX REVERSE PROXY                                         │ │             ║
║  │  │  • SSL/TLS Termination (Let's Encrypt)  • Rate Limiting (100 req/min)                        │ │             ║
║  │  │  • Load Balancing (Round Robin)         • Gzip/Brotli Compression                           │ │             ║
║  │  │  • WebSocket Upgrade Support            • Security Headers (CSP, HSTS)                       │ │             ║
║  │  │  • Static File Caching (365 days)       • Request Buffering & Timeout                       │ │             ║
║  │  └──────────────────────────────────────────────────────────────────────────────────────────────┘ │             ║
║  │                                                                                                    │             ║
║  │         │                                       │                                     │           │             ║
║  │         ▼                                       ▼                                     ▼           │             ║
║  │  ┌─────────────────┐                    ┌─────────────────┐                   ┌─────────────────┐ │             ║
║  │  │  Gunicorn       │                    │    Daphne       │                   │  Static Files   │ │             ║
║  │  │  REST API       │                    │   WebSockets    │                   │  CDN Ready      │ │             ║
║  │  │  Port: 8000     │                    │   Port: 8001    │                   │  Port: 80/443   │ │             ║
║  │  │  Workers: 4     │                    │   Workers: 2    │                   │  Cache: 1 year  │ │             ║
║  │  └─────────────────┘                    └─────────────────┘                   └─────────────────┘ │             ║
║  └────────────────────────────────────────────────────────────────────────────────────────────────────┘             ║
║                                                        │                                                            ║
║                                                        ▼                                                            ║
║  ┌──────────────────────────────────────── APPLICATION TIER ─────────────────────────────────────────┐             ║
║  │                                                                                                    │             ║
║  │  ┌─────────────────────────────────── DJANGO BACKEND ────────────────────────────────────────────┐│             ║
║  │  │                                                                                                ││             ║
║  │  │  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐       ││             ║
║  │  │  │   AUTH MODULE    │  │   VAULT SERVICE  │  │ SECURITY SERVICE │  │   FHE SERVICE    │       ││             ║
║  │  │  │                  │  │                  │  │                  │  │                  │       ││             ║
║  │  │  │ • JWT Tokens     │  │ • CRUD Ops       │  │ • Breach Monitor │  │ • Concrete-Py    │       ││             ║
║  │  │  │ • WebAuthn/FIDO2 │  │ • Backup/Restore │  │ • Device Trust   │  │ • TenSEAL SEAL   │       ││             ║
║  │  │  │ • OAuth 2.0      │  │ • Sync Engine    │  │ • Login Tracking │  │ • FHE Router     │       ││             ║
║  │  │  │ • MFA (TOTP/Push)│  │ • Folder Mgmt    │  │ • Alert System   │  │ • Adaptive Depth │       ││             ║
║  │  │  │ • Kyber Crypto   │  │ • Shared Folders │  │ • Dark Web Scan  │  │ • Computation    │       ││             ║
║  │  │  │ • Recovery Flows │  │ • Import/Export  │  │ • Audit Logging  │  │   Cache (Redis)  │       ││             ║
║  │  │  └────────┬─────────┘  └────────┬─────────┘  └────────┬─────────┘  └────────┬─────────┘       ││             ║
║  │  │           │                     │                     │                     │                 ││             ║
║  │  │  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐       ││             ║
║  │  │  │ BEHAVIORAL       │  │   ML SECURITY    │  │   BLOCKCHAIN     │  │  EMAIL MASKING   │       ││             ║
║  │  │  │ RECOVERY         │  │                  │  │   ANCHORING      │  │                  │       ││             ║
║  │  │  │                  │  │ • LSTM Strength  │  │                  │  │ • SimpleLogin    │       ││             ║
║  │  │  │ • 247-dim DNA    │  │ • CNN-LSTM Threat│  │ • Merkle Trees   │  │ • AnonAddy       │       ││             ║
║  │  │  │ • Trust Scoring  │  │ • Isolation For. │  │ • Web3.py        │  │ • Alias Creation │       ││             ║
║  │  │  │ • Temporal Chal. │  │ • BERT Breach    │  │ • Arbitrum L2    │  │ • Activity Track │       ││             ║
║  │  │  │ • Guardian Mesh  │  │ • Siamese Similar│  │ • ZK Proofs      │  │ • Provider Mgmt  │       ││             ║
║  │  │  └──────────────────┘  └──────────────────┘  └──────────────────┘  └──────────────────┘       ││             ║
║  │  │                                                                                                ││             ║
║  │  │  ┌────────────────────────────────────────────────────────────────────────────────────────────┐││             ║
║  │  │  │                               MIDDLEWARE STACK                                              │││             ║
║  │  │  │  • VaultCompressionMiddleware (Gzip/Brotli)  • SecurityHeadersMiddleware (CSP, HSTS)      │││             ║
║  │  │  │  • CacheControlMiddleware                    • PerformanceMiddleware (Timing)             │││             ║
║  │  │  │  • CORSMiddleware                            • RateLimitMiddleware                        │││             ║
║  │  │  └────────────────────────────────────────────────────────────────────────────────────────────┘││             ║
║  │  └────────────────────────────────────────────────────────────────────────────────────────────────┘│             ║
║  │                                                                                                    │             ║
║  │  ┌─────────────────────────────────── BACKGROUND WORKERS ────────────────────────────────────────┐│             ║
║  │  │                                                                                                ││             ║
║  │  │  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐       ││             ║
║  │  │  │ CELERY WORKER 1  │  │ CELERY WORKER 2  │  │   CELERY BEAT    │  │  CHANNELS WORKER │       ││             ║
║  │  │  │                  │  │                  │  │   (Scheduler)    │  │                  │       ││             ║
║  │  │  │ • Email Tasks    │  │ • ML Inference   │  │                  │  │ • Breach Alerts  │       ││             ║
║  │  │  │ • Export Prep    │  │ • Breach Check   │  │ • Hourly Cleanup │  │ • Real-time Sync │       ││             ║
║  │  │  │ • Audit Process  │  │ • Stats Compute  │  │ • Daily Audits   │  │ • Live Updates   │       ││             ║
║  │  │  │ • Cache Warming  │  │ • Blockchain Tx  │  │ • Weekly Purge   │  │ • Notifications  │       ││             ║
║  │  │  └──────────────────┘  └──────────────────┘  └──────────────────┘  └──────────────────┘       ││             ║
║  │  └────────────────────────────────────────────────────────────────────────────────────────────────┘│             ║
║  └────────────────────────────────────────────────────────────────────────────────────────────────────┘             ║
║                                                        │                                                            ║
║                                                        ▼                                                            ║
║  ┌───────────────────────────────────────── DATA TIER ───────────────────────────────────────────────┐             ║
║  │                                                                                                    │             ║
║  │  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐           │             ║
║  │  │   POSTGRESQL     │  │     REDIS        │  │   ELASTICSEARCH  │  │   BLOCKCHAIN     │           │             ║
║  │  │   (Primary DB)   │  │  (Cache/Broker)  │  │   (Optional)     │  │   (Arbitrum L2)  │           │             ║
║  │  │                  │  │                  │  │                  │  │                  │           │             ║
║  │  │ • User Accounts  │  │ • Session Cache  │  │ • Full-text      │  │ • Commitment     │           │             ║
║  │  │ • Encrypted Vault│  │ • Rate Limiting  │  │   Search         │  │   Anchors        │           │             ║
║  │  │ • Kyber Keys     │  │ • Celery Broker  │  │ • Audit Logs     │  │ • Merkle Roots   │           │             ║
║  │  │ • FHE Keys/Cache │  │ • Real-time Pub  │  │ • ML Vector      │  │ • ZK Proofs      │           │             ║
║  │  │ • Behavioral DNA │  │ • L1/L2 Cache    │  │   Store (pgvec)  │  │ • Verification   │           │             ║
║  │  │ • Audit Logs     │  │ • FHE Result     │  │                  │  │                  │           │             ║
║  │  │ • Recovery Data  │  │   Cache          │  │                  │  │                  │           │             ║
║  │  └──────────────────┘  └──────────────────┘  └──────────────────┘  └──────────────────┘           │             ║
║  │                                                                                                    │             ║
║  └────────────────────────────────────────────────────────────────────────────────────────────────────┘             ║
║                                                                                                                    ║
╚══════════════════════════════════════════════════════════════════════════════════════════════════════════════════╝
```

### Component Communication Matrix

```
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                           COMPONENT COMMUNICATION PROTOCOLS                               │
├────────────────────┬─────────────────────┬───────────────────┬─────────────────────────┤
│      Source        │      Target         │    Protocol       │      Purpose            │
├────────────────────┼─────────────────────┼───────────────────┼─────────────────────────┤
│ Web App            │ NGINX Gateway       │ HTTPS/TLS 1.3     │ API requests            │
│ Web App            │ Daphne              │ WSS               │ Real-time breach alerts │
│ NGINX              │ Gunicorn            │ HTTP (internal)   │ REST API proxy          │
│ NGINX              │ Daphne              │ WebSocket         │ WS proxy                │
│ Django             │ PostgreSQL          │ TCP/5432          │ Data persistence        │
│ Django             │ Redis               │ TCP/6379          │ Cache/Celery broker     │
│ Celery Worker      │ Redis               │ AMQP              │ Task queue              │
│ Celery Worker      │ PostgreSQL          │ TCP/5432          │ Task results            │
│ Django             │ Arbitrum RPC        │ HTTPS/JSON-RPC    │ Blockchain anchoring    │
│ FHE Service        │ Redis               │ TCP/6379          │ Computation cache       │
│ ML Service         │ TensorFlow Serving  │ gRPC (optional)   │ Model inference         │
│ Channels           │ Redis               │ TCP/6379          │ Channel layer           │
└────────────────────┴─────────────────────┴───────────────────┴─────────────────────────┘
```

### Data Flow Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        DATA FLOW DIAGRAM                             │
└─────────────────────────────────────────────────────────────────────┘

   USER                    CLIENT                    SERVER                DB
    │                        │                         │                    │
    │  Enter Password        │                         │                    │
    │───────────────────────>│                         │                    │
    │                        │                         │                    │
    │                        │  Argon2id KDF           │                    │
    │                        │  (64MB, 3 iter)         │                    │
    │                        │─────────────────┐       │                    │
    │                        │                 │       │                    │
    │                        │<────────────────┘       │                    │
    │                        │  256-bit Key            │                    │
    │                        │                         │                    │
    │                        │  AES-GCM-256 Encrypt    │                    │
    │                        │─────────────────┐       │                    │
    │                        │                 │       │                    │
    │                        │<────────────────┘       │                    │
    │                        │  Encrypted Blob         │                    │
    │                        │                         │                    │
    │                        │  HTTPS POST (JWT)       │                    │
    │                        │────────────────────────>│                    │
    │                        │                         │                    │
    │                        │                         │  Store Blob       │
    │                        │                         │───────────────────>│
    │                        │                         │                    │
    │                        │                         │<───────────────────│
    │                        │                         │  OK                │
    │                        │                         │                    │
    │                        │<────────────────────────│                    │
    │                        │  Success Response       │                    │
    │                        │                         │                    │
    │<───────────────────────│                         │                    │
    │  Confirmation          │                         │                    │
    │                        │                         │                    │

    ✓ Server NEVER sees plaintext
    ✓ Keys derived client-side only
    ✓ Zero-knowledge architecture
```

---

## 🔐 Authentication Flow Diagrams

### Complete Authentication State Machine

```
┌─────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                              AUTHENTICATION STATE MACHINE                                            │
├─────────────────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                                      │
│                                      ┌─────────────┐                                                │
│                                      │   START     │                                                │
│                                      └──────┬──────┘                                                │
│                                             │                                                        │
│                     ┌───────────────────────┼───────────────────────┐                               │
│                     ▼                       ▼                       ▼                               │
│            ┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐                      │
│            │ Password + MFA  │     │    WebAuthn     │     │   OAuth 2.0 /   │                      │
│            │     Flow        │     │   (Passkey)     │     │   OIDC (SSO)    │                      │
│            └────────┬────────┘     └────────┬────────┘     └────────┬────────┘                      │
│                     │                       │                       │                                │
│                     │                       │              ┌────────┴────────┐                       │
│                     │                       │              ▼                 ▼                       │
│                     │                       │     ┌─────────────┐   ┌─────────────┐                 │
│                     │                       │     │OAuth 2.0    │   │OpenID       │                 │
│                     │                       │     │(Google/     │   │Connect      │                 │
│                     │                       │     │GitHub/Apple)│   │(Okta/Azure) │                 │
│                     │                       │     └──────┬──────┘   └──────┬──────┘                 │
│                     │                       │            │                 │                        │
│                     ▼                       ▼            ▼                 ▼                        │
│            ┌──────────────────────────────────────────────────────────────────┐                     │
│            │                    IDENTITY VERIFICATION                          │                     │
│            │                                                                   │                     │
│            │  ┌────────────┐ ┌────────────┐ ┌────────────┐ ┌────────────┐     │                     │
│            │  │  Verify    │ │  Verify    │ │  Verify    │ │  Validate  │     │                     │
│            │  │ Credentials│ │ Signature  │ │ OAuth Token│ │  ID Token  │     │                     │
│            │  │ (Argon2id) │ │ (WebAuthn) │ │ (Access)   │ │  (JWKS)    │     │                     │
│            │  └────────────┘ └────────────┘ └────────────┘ └────────────┘     │                     │
│            └───────────────────────────┬──────────────────────────────────────┘                     │
│                                              │                                                       │
│                                              ▼                                                       │
│                  ┌─────────────────────────────────────────────────────────┐                        │
│                  │                  MFA CHECK                               │                        │
│                  │                                                          │                        │
│                  │    Is MFA required for this user/device?                │                        │
│                  │                                                          │                        │
│                  │         ┌─────────┐         ┌─────────┐                 │                        │
│                  │         │   YES   │         │   NO    │                 │                        │
│                  │         └────┬────┘         └────┬────┘                 │                        │
│                  └──────────────┼──────────────────┼───────────────────────┘                        │
│                                 │                  │                                                 │
│                                 ▼                  │                                                 │
│                  ┌─────────────────────────────────┴───────────────────────┐                        │
│                  │                 MFA VERIFICATION                         │                        │
│                  │                                                          │                        │
│                  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐   │                        │
│                  │  │   TOTP   │ │   SMS    │ │   Push   │ │ Biometric│   │                        │
│                  │  │  6-digit │ │   Code   │ │  Notif   │ │Face/Voice│   │                        │
│                  │  └──────────┘ └──────────┘ └──────────┘ └──────────┘   │                        │
│                  └───────────────────────────┬─────────────────────────────┘                        │
│                                              │                                                       │
│                                              ▼                                                       │
│                  ┌─────────────────────────────────────────────────────────┐                        │
│                  │               DEVICE TRUST CHECK                         │                        │
│                  │                                                          │                        │
│                  │    ┌────────────────────────────────────────────┐       │                        │
│                  │    │  Is this device trusted?                   │       │                        │
│                  │    │                                            │       │                        │
│                  │    │  Check: Device ID, Fingerprint, Location   │       │                        │
│                  │    │  Risk Score, Behavioral Pattern            │       │                        │
│                  │    └────────────────────────────────────────────┘       │                        │
│                  │                                                          │                        │
│                  │         ┌─────────┐              ┌───────────┐          │                        │
│                  │         │ Trusted │              │ Untrusted │          │                        │
│                  │         └────┬────┘              └─────┬─────┘          │                        │
│                  │              │                         │                │                        │
│                  │              │                         ▼                │                        │
│                  │              │         ┌────────────────────────┐       │                        │
│                  │              │         │ Send Security Alert    │       │                        │
│                  │              │         │ Request Device Trust   │       │                        │
│                  │              │         └────────────────────────┘       │                        │
│                  └──────────────┼──────────────────────┬───────────────────┘                        │
│                                 │                      │                                             │
│                                 ▼                      ▼                                             │
│                  ┌─────────────────────────────────────────────────────────┐                        │
│                  │                    SESSION CREATION                      │                        │
│                  │                                                          │                        │
│                  │    ┌────────────────────────────────────────────────┐   │                        │
│                  │    │  Generate JWT Tokens                           │   │                        │
│                  │    │  • Access Token  (15 min TTL)                  │   │                        │
│                  │    │  • Refresh Token (7 days TTL)                  │   │                        │
│                  │    │  • Device binding                              │   │                        │
│                  │    └────────────────────────────────────────────────┘   │                        │
│                  │                                                          │                        │
│                  │    ┌────────────────────────────────────────────────┐   │                        │
│                  │    │  Create Audit Log Entry                        │   │                        │
│                  │    │  • IP Address, User Agent                      │   │                        │
│                  │    │  • Device Fingerprint                          │   │                        │
│                  │    │  • Geolocation                                 │   │                        │
│                  │    └────────────────────────────────────────────────┘   │                        │
│                  └───────────────────────────┬─────────────────────────────┘                        │
│                                              │                                                       │
│                                              ▼                                                       │
│                                      ┌─────────────┐                                                │
│                                      │ AUTHENTICATED│                                                │
│                                      │   SESSION   │                                                │
│                                      └─────────────┘                                                │
│                                                                                                      │
└─────────────────────────────────────────────────────────────────────────────────────────────────────┘
```

### OAuth 2.0 + Social Login Flow

```
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                              OAUTH 2.0 SOCIAL LOGIN FLOW                                 │
├─────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                          │
│    USER              CLIENT              BACKEND           OAUTH PROVIDER               │
│     │                  │                    │                    │                       │
│     │  Click "Login    │                    │                    │                       │
│     │  with Google"    │                    │                    │                       │
│     │─────────────────>│                    │                    │                       │
│     │                  │                    │                    │                       │
│     │                  │  GET /auth/oauth/  │                    │                       │
│     │                  │  google/?action=   │                    │                       │
│     │                  │  redirect          │                    │                       │
│     │                  │───────────────────>│                    │                       │
│     │                  │                    │                    │                       │
│     │                  │                    │  Generate state,   │                       │
│     │                  │                    │  PKCE verifier     │                       │
│     │                  │                    │────────┐           │                       │
│     │                  │                    │<───────┘           │                       │
│     │                  │                    │                    │                       │
│     │                  │<───────────────────│                    │                       │
│     │                  │  302 Redirect to   │                    │                       │
│     │                  │  Google OAuth URL  │                    │                       │
│     │                  │                    │                    │                       │
│     │<─────────────────│                    │                    │                       │
│     │  Redirect to Google                   │                    │                       │
│     │                                       │                    │                       │
│     │─────────────────────────────────────────────────────────>│                       │
│     │  Login with Google credentials                            │                       │
│     │                                       │                    │                       │
│     │<─────────────────────────────────────────────────────────│                       │
│     │  Authorization Code + State           │                    │                       │
│     │                                       │                    │                       │
│     │─────────────────>│                    │                    │                       │
│     │  Callback URL    │                    │                    │                       │
│     │  with code+state │                    │                    │                       │
│     │                  │                    │                    │                       │
│     │                  │  POST /oauth/google│                    │                       │
│     │                  │  {code, state}     │                    │                       │
│     │                  │───────────────────>│                    │                       │
│     │                  │                    │                    │                       │
│     │                  │                    │  Verify state      │                       │
│     │                  │                    │────────┐           │                       │
│     │                  │                    │<───────┘           │                       │
│     │                  │                    │                    │                       │
│     │                  │                    │  Exchange code     │                       │
│     │                  │                    │  for tokens        │                       │
│     │                  │                    │───────────────────>│                       │
│     │                  │                    │                    │                       │
│     │                  │                    │<───────────────────│                       │
│     │                  │                    │  Access Token +    │                       │
│     │                  │                    │  ID Token          │                       │
│     │                  │                    │                    │                       │
│     │                  │                    │  Fetch user info   │                       │
│     │                  │                    │───────────────────>│                       │
│     │                  │                    │<───────────────────│                       │
│     │                  │                    │  {email, name,     │                       │
│     │                  │                    │   picture}         │                       │
│     │                  │                    │                    │                       │
│     │                  │                    │  Create/Link User  │                       │
│     │                  │                    │  Generate JWT      │                       │
│     │                  │                    │────────┐           │                       │
│     │                  │                    │<───────┘           │                       │
│     │                  │                    │                    │                       │
│     │                  │<───────────────────│                    │                       │
│     │                  │  {access_token,    │                    │                       │
│     │                  │   refresh_token,   │                    │                       │
│     │                  │   user_info}       │                    │                       │
│     │                  │                    │                    │                       │
│     │<─────────────────│                    │                    │                       │
│     │  Authenticated!   │                    │                    │                       │
│     │                  │                    │                    │                       │
│                                                                                          │
│  SUPPORTED PROVIDERS:                                                                   │
│  ┌────────┐ ┌────────┐ ┌────────┐ ┌──────────┐                                         │
│  │ Google │ │ GitHub │ │ Apple  │ │Microsoft │                                         │
│  │  ✓     │ │   ✓    │ │   ✓    │ │ (coming) │                                         │
│  └────────┘ └────────┘ └────────┘ └──────────┘                                         │
│                                                                                          │
└─────────────────────────────────────────────────────────────────────────────────────────┘
```

### OpenID Connect (OIDC) Enterprise SSO Flow

SecureVault v2.4 introduces full **OpenID Connect (OIDC)** support for enterprise Single Sign-On (SSO) integration.

```
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                           OPENID CONNECT (OIDC) AUTHENTICATION FLOW                      │
├─────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                          │
│    USER              CLIENT              BACKEND           OIDC PROVIDER                │
│     │                  │                    │              (Okta/Azure AD)              │
│     │  Click "Login    │                    │                    │                       │
│     │  with SSO"       │                    │                    │                       │
│     │─────────────────>│                    │                    │                       │
│     │                  │                    │                    │                       │
│     │                  │  GET /oidc/        │                    │                       │
│     │                  │  providers/        │                    │                       │
│     │                  │───────────────────>│                    │                       │
│     │                  │                    │                    │                       │
│     │                  │<───────────────────│                    │                       │
│     │                  │  List of OIDC      │                    │                       │
│     │                  │  providers         │                    │                       │
│     │                  │                    │                    │                       │
│     │  Select provider │                    │                    │                       │
│     │─────────────────>│                    │                    │                       │
│     │                  │                    │                    │                       │
│     │                  │  POST /oidc/       │                    │                       │
│     │                  │  authorize/        │                    │                       │
│     │                  │───────────────────>│                    │                       │
│     │                  │                    │                    │                       │
│     │                  │                    │  Discover OIDC     │                       │
│     │                  │                    │  endpoints         │                       │
│     │                  │                    │───────────────────>│                       │
│     │                  │                    │<───────────────────│                       │
│     │                  │                    │  /.well-known/     │                       │
│     │                  │                    │  openid-configuration                      │
│     │                  │                    │                    │                       │
│     │                  │                    │  Generate:         │                       │
│     │                  │                    │  • state           │                       │
│     │                  │                    │  • nonce           │                       │
│     │                  │                    │  • PKCE verifier   │                       │
│     │                  │                    │────────┐           │                       │
│     │                  │                    │<───────┘           │                       │
│     │                  │                    │                    │                       │
│     │                  │<───────────────────│                    │                       │
│     │                  │  302 Redirect to   │                    │                       │
│     │                  │  OIDC Provider     │                    │                       │
│     │                  │                    │                    │                       │
│     │<─────────────────│                    │                    │                       │
│     │  Redirect to Okta/Azure AD           │                    │                       │
│     │                                       │                    │                       │
│     │─────────────────────────────────────────────────────────>│                       │
│     │  Login with enterprise credentials                        │                       │
│     │                                       │                    │                       │
│     │<─────────────────────────────────────────────────────────│                       │
│     │  Authorization Code + State           │                    │                       │
│     │                                       │                    │                       │
│     │─────────────────>│                    │                    │                       │
│     │  Callback URL    │                    │                    │                       │
│     │  with code+state │                    │                    │                       │
│     │                  │                    │                    │                       │
│     │                  │  POST /oidc/       │                    │                       │
│     │                  │  callback/         │                    │                       │
│     │                  │───────────────────>│                    │                       │
│     │                  │                    │                    │                       │
│     │                  │                    │  Verify state      │                       │
│     │                  │                    │  & nonce           │                       │
│     │                  │                    │────────┐           │                       │
│     │                  │                    │<───────┘           │                       │
│     │                  │                    │                    │                       │
│     │                  │                    │  Exchange code     │                       │
│     │                  │                    │  for tokens        │                       │
│     │                  │                    │───────────────────>│                       │
│     │                  │                    │<───────────────────│                       │
│     │                  │                    │  • access_token    │                       │
│     │                  │                    │  • id_token (JWT)  │                       │
│     │                  │                    │  • refresh_token   │                       │
│     │                  │                    │                    │                       │
│     │                  │                    │  Validate ID Token │                       │
│     │                  │                    │  • Fetch JWKS      │                       │
│     │                  │                    │  • Verify signature│                       │
│     │                  │                    │  • Check claims    │                       │
│     │                  │                    │  • Validate nonce  │                       │
│     │                  │                    │────────┐           │                       │
│     │                  │                    │<───────┘           │                       │
│     │                  │                    │                    │                       │
│     │                  │                    │  Create/Link User  │                       │
│     │                  │                    │  Generate JWT      │                       │
│     │                  │                    │────────┐           │                       │
│     │                  │                    │<───────┘           │                       │
│     │                  │                    │                    │                       │
│     │                  │<───────────────────│                    │                       │
│     │                  │  {access_token,    │                    │                       │
│     │                  │   refresh_token,   │                    │                       │
│     │                  │   user_info}       │                    │                       │
│     │                  │                    │                    │                       │
│     │<─────────────────│                    │                    │                       │
│     │  Authenticated!   │                    │                    │                       │
│                                                                                          │
│  SUPPORTED OIDC PROVIDERS:                                                              │
│  ┌────────┐ ┌────────┐ ┌────────┐ ┌──────────┐ ┌──────────┐                            │
│  │ Okta   │ │Azure AD│ │ Auth0  │ │  Google  │ │ Keycloak │                            │
│  │   ✓    │ │   ✓    │ │   ✓    │ │    ✓     │ │    ✓     │                            │
│  └────────┘ └────────┘ └────────┘ └──────────┘ └──────────┘                            │
│                                                                                          │
│  KEY FEATURES:                                                                          │
│  • Auto-discovery via .well-known/openid-configuration                                  │
│  • ID Token validation with JWKS                                                        │
│  • Nonce validation for replay attack protection                                        │
│  • PKCE (Proof Key for Code Exchange) support                                           │
│  • Standard claims extraction (sub, email, name, etc.)                                  │
│  • Automatic user provisioning and linking                                              │
│                                                                                          │
└─────────────────────────────────────────────────────────────────────────────────────────┘
```

#### OIDC Configuration

Configure OIDC providers via environment variables:

```bash
# OIDC Provider Configuration
OIDC_RP_CLIENT_ID=your-client-id
OIDC_RP_CLIENT_SECRET=your-client-secret
OIDC_OP_BASE_URL=https://your-provider.com  # e.g., https://accounts.google.com
OIDC_VERIFY_SSL=True
OIDC_USE_NONCE=True

# Optional: Override discovery endpoints
OIDC_OP_JWKS_ENDPOINT=https://your-provider.com/.well-known/jwks.json
OIDC_OP_USER_ENDPOINT=https://your-provider.com/userinfo
```

#### OIDC API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/auth/oidc/.well-known/openid-configuration/` | GET | OIDC Discovery document |
| `/api/auth/oidc/.well-known/jwks.json` | GET | JSON Web Key Set |
| `/api/auth/oidc/providers/` | GET | List configured providers |
| `/api/auth/oidc/authorize/` | POST | Start OIDC auth flow |
| `/api/auth/oidc/callback/` | GET | Handle OIDC callback |
| `/api/auth/oidc/userinfo/` | GET | Get authenticated user info |

### WebAuthn/Passkey Authentication Flow

```
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                           WEBAUTHN PASSKEY AUTHENTICATION FLOW                           │
├─────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                          │
│  ╔═══════════════════════════════════════════════════════════════════════════════════╗  │
│  ║                            REGISTRATION PHASE                                      ║  │
│  ╚═══════════════════════════════════════════════════════════════════════════════════╝  │
│                                                                                          │
│    USER           BROWSER         CLIENT (JS)         SERVER           AUTHENTICATOR    │
│     │                │                │                  │                   │          │
│     │  Click         │                │                  │                   │          │
│     │  "Add Passkey" │                │                  │                   │          │
│     │────────────────────────────────>│                  │                   │          │
│     │                │                │                  │                   │          │
│     │                │                │  POST /register/ │                   │          │
│     │                │                │  begin/          │                   │          │
│     │                │                │─────────────────>│                   │          │
│     │                │                │                  │                   │          │
│     │                │                │                  │  Generate:        │          │
│     │                │                │                  │  • Challenge      │          │
│     │                │                │                  │  • User handle    │          │
│     │                │                │                  │  • RP info        │          │
│     │                │                │                  │────────┐          │          │
│     │                │                │                  │<───────┘          │          │
│     │                │                │                  │                   │          │
│     │                │                │<─────────────────│                   │          │
│     │                │                │  {publicKey:     │                   │          │
│     │                │                │   options}       │                   │          │
│     │                │                │                  │                   │          │
│     │                │  navigator.    │                  │                   │          │
│     │                │  credentials.  │                  │                   │          │
│     │                │  create()      │                  │                   │          │
│     │                │<───────────────│                  │                   │          │
│     │                │                │                  │                   │          │
│     │                │────────────────────────────────────────────────────>│          │
│     │                │  Create credential request                           │          │
│     │                │                │                  │                   │          │
│     │<───────────────────────────────────────────────────────────────────────│          │
│     │  Biometric/PIN prompt                                                 │          │
│     │                │                │                  │                   │          │
│     │────────────────────────────────────────────────────────────────────>│          │
│     │  User verifies identity (Face ID / Touch ID / PIN)                   │          │
│     │                │                │                  │                   │          │
│     │                │                │                  │  Generate keypair │          │
│     │                │                │                  │  Sign challenge   │          │
│     │                │                │                  │<──────────────────│          │
│     │                │                │                  │                   │          │
│     │                │<───────────────────────────────────────────────────────│          │
│     │                │  PublicKeyCredential {id, rawId, attestationObject}  │          │
│     │                │                │                  │                   │          │
│     │                │───────────────>│                  │                   │          │
│     │                │                │                  │                   │          │
│     │                │                │  POST /register/ │                   │          │
│     │                │                │  complete/       │                   │          │
│     │                │                │  {credential}    │                   │          │
│     │                │                │─────────────────>│                   │          │
│     │                │                │                  │                   │          │
│     │                │                │                  │  Verify attestation│          │
│     │                │                │                  │  Store public key │          │
│     │                │                │                  │  Store credential │          │
│     │                │                │                  │────────┐          │          │
│     │                │                │                  │<───────┘          │          │
│     │                │                │                  │                   │          │
│     │                │                │<─────────────────│                   │          │
│     │                │                │  {success: true, │                   │          │
│     │                │                │   passkey_id}    │                   │          │
│     │                │                │                  │                   │          │
│     │<────────────────────────────────│                  │                   │          │
│     │  "Passkey registered!"          │                  │                   │          │
│                                                                                          │
│  ╔═══════════════════════════════════════════════════════════════════════════════════╗  │
│  ║                            AUTHENTICATION PHASE                                    ║  │
│  ╚═══════════════════════════════════════════════════════════════════════════════════╝  │
│                                                                                          │
│     │                │                │                  │                   │          │
│     │  Click "Login  │                │                  │                   │          │
│     │  with Passkey" │                │                  │                   │          │
│     │────────────────────────────────>│                  │                   │          │
│     │                │                │                  │                   │          │
│     │                │                │  POST /auth/     │                   │          │
│     │                │                │  begin/          │                   │          │
│     │                │                │─────────────────>│                   │          │
│     │                │                │                  │                   │          │
│     │                │                │                  │  Generate challenge│          │
│     │                │                │                  │  Get allowed creds │          │
│     │                │                │                  │────────┐          │          │
│     │                │                │                  │<───────┘          │          │
│     │                │                │                  │                   │          │
│     │                │                │<─────────────────│                   │          │
│     │                │                │  {challenge,     │                   │          │
│     │                │                │   allowCreds}    │                   │          │
│     │                │                │                  │                   │          │
│     │                │  navigator.    │                  │                   │          │
│     │                │  credentials.  │                  │                   │          │
│     │                │  get()         │                  │                   │          │
│     │                │<───────────────│                  │                   │          │
│     │                │                │                  │                   │          │
│     │                │────────────────────────────────────────────────────>│          │
│     │                │  Get credential request                              │          │
│     │                │                │                  │                   │          │
│     │<───────────────────────────────────────────────────────────────────────│          │
│     │  Biometric/PIN prompt                                                 │          │
│     │                │                │                  │                   │          │
│     │────────────────────────────────────────────────────────────────────>│          │
│     │  User verifies identity                                               │          │
│     │                │                │                  │                   │          │
│     │                │                │                  │  Sign challenge   │          │
│     │                │                │                  │  with private key │          │
│     │                │                │                  │<──────────────────│          │
│     │                │                │                  │                   │          │
│     │                │<───────────────────────────────────────────────────────│          │
│     │                │  PublicKeyCredential {authenticatorData, signature}  │          │
│     │                │                │                  │                   │          │
│     │                │───────────────>│                  │                   │          │
│     │                │                │                  │                   │          │
│     │                │                │  POST /auth/     │                   │          │
│     │                │                │  complete/       │                   │          │
│     │                │                │  {credential}    │                   │          │
│     │                │                │─────────────────>│                   │          │
│     │                │                │                  │                   │          │
│     │                │                │                  │  Verify signature │          │
│     │                │                │                  │  with stored pubkey│          │
│     │                │                │                  │  Update sign count│          │
│     │                │                │                  │  Generate JWT     │          │
│     │                │                │                  │────────┐          │          │
│     │                │                │                  │<───────┘          │          │
│     │                │                │                  │                   │          │
│     │                │                │<─────────────────│                   │          │
│     │                │                │  {access_token,  │                   │          │
│     │                │                │   refresh_token} │                   │          │
│     │                │                │                  │                   │          │
│     │<────────────────────────────────│                  │                   │          │
│     │  Authenticated! (Passwordless)  │                  │                   │          │
│                                                                                          │
└─────────────────────────────────────────────────────────────────────────────────────────┘
```

### Authorization & Permission Flow

```
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                              AUTHORIZATION & PERMISSION FLOW                             │
├─────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                          │
│    ┌────────────────────────────────────────────────────────────────────────────────┐   │
│    │                         INCOMING REQUEST                                        │   │
│    │  Authorization: Bearer <access_token>                                          │   │
│    │  X-Device-Fingerprint: <device_id>                                             │   │
│    │  X-Request-ID: <uuid>                                                          │   │
│    └────────────────────────────────────────────────────────────────────────────────┘   │
│                                            │                                             │
│                                            ▼                                             │
│    ┌────────────────────────────────────────────────────────────────────────────────┐   │
│    │                       JWT TOKEN VALIDATION                                      │   │
│    │  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐                 │   │
│    │  │ Verify Signature│  │ Check Expiry    │  │ Validate Claims │                 │   │
│    │  │ (HS256/RS256)   │  │ (exp < now?)    │  │ (iss, aud, sub) │                 │   │
│    │  └────────┬────────┘  └────────┬────────┘  └────────┬────────┘                 │   │
│    │           │                    │                    │                           │   │
│    │           └────────────────────┼────────────────────┘                           │   │
│    │                                │                                                 │   │
│    │                    ┌───────────┴───────────┐                                    │   │
│    │                    │ OIDC Token?           │                                    │   │
│    │                    │ (Check JWKS endpoint) │                                    │   │
│    │                    └───────────────────────┘                                    │   │
│    └────────────────────────────────────────────────────────────────────────────────┘   │
│                                            │                                             │
│                                            ▼                                             │
│    ┌────────────────────────────────────────────────────────────────────────────────┐   │
│    │                       PERMISSION CHECK LAYERS                                   │   │
│    │                                                                                 │   │
│    │  ┌─────────────────────────────────────────────────────────────────────────┐  │   │
│    │  │ Layer 1: Authentication Status                                           │  │   │
│    │  │  • User authenticated?  • Session valid?  • Device trusted?              │  │   │
│    │  └─────────────────────────────────────────────────────────────────────────┘  │   │
│    │                                    │                                           │   │
│    │                                    ▼                                           │   │
│    │  ┌─────────────────────────────────────────────────────────────────────────┐  │   │
│    │  │ Layer 2: Role-Based Access Control (RBAC)                                │  │   │
│    │  │  • User Role: [user, admin, enterprise_admin]                            │  │   │
│    │  │  • Resource Permission: [read, write, delete, share]                     │  │   │
│    │  └─────────────────────────────────────────────────────────────────────────┘  │   │
│    │                                    │                                           │   │
│    │                                    ▼                                           │   │
│    │  ┌─────────────────────────────────────────────────────────────────────────┐  │   │
│    │  │ Layer 3: Resource Ownership                                              │  │   │
│    │  │  • Vault Item: user.id == item.user_id                                   │  │   │
│    │  │  • Shared Folder: user in folder.members                                 │  │   │
│    │  │  • Emergency Access: approved_contacts                                   │  │   │
│    │  └─────────────────────────────────────────────────────────────────────────┘  │   │
│    │                                    │                                           │   │
│    │                                    ▼                                           │   │
│    │  ┌─────────────────────────────────────────────────────────────────────────┐  │   │
│    │  │ Layer 4: Adaptive Security Checks                                        │  │   │
│    │  │  • Risk Score Assessment  • Behavioral Analysis  • IP/Geo Verification   │  │   │
│    │  │  • Rate Limiting          • Anomaly Detection    • MFA Step-up Required? │  │   │
│    │  └─────────────────────────────────────────────────────────────────────────┘  │   │
│    └────────────────────────────────────────────────────────────────────────────────┘   │
│                                            │                                             │
│                              ┌─────────────┴─────────────┐                              │
│                              ▼                           ▼                              │
│                     ┌───────────────┐           ┌───────────────┐                       │
│                     │   AUTHORIZED  │           │   DENIED      │                       │
│                     │   (200 OK)    │           │  (401/403)    │                       │
│                     └───────────────┘           └───────────────┘                       │
│                                                                                          │
│    ┌────────────────────────────────────────────────────────────────────────────────┐   │
│    │                         AUDIT LOG ENTRY                                         │   │
│    │  • User ID    • Resource    • Action    • Result    • Timestamp    • IP        │   │
│    │  • Device     • Risk Score  • MFA Used  • OIDC Provider (if SSO)               │   │
│    └────────────────────────────────────────────────────────────────────────────────┘   │
│                                                                                          │
│  PERMISSION MATRIX:                                                                     │
│  ┌──────────────────┬────────┬────────┬────────┬────────┬────────────────────────────┐ │
│  │ Resource         │ Owner  │ Shared │ Admin  │ OIDC   │ Emergency                  │ │
│  ├──────────────────┼────────┼────────┼────────┼────────┼────────────────────────────┤ │
│  │ Vault Items      │ CRUD   │ R      │ CRUD   │ CRUD   │ R (after waiting period)   │ │
│  │ Folders          │ CRUD   │ R/W*   │ CRUD   │ CRUD   │ R                          │ │
│  │ Passkeys         │ CRUD   │ -      │ R/D    │ CRUD   │ -                          │ │
│  │ Recovery Keys    │ C/R    │ -      │ R      │ C/R    │ -                          │ │
│  │ Security Settings│ CRUD   │ -      │ CRUD   │ CRUD   │ -                          │ │
│  │ Shared Folders   │ CRUD   │ R/W*   │ CRUD   │ CRUD   │ R                          │ │
│  └──────────────────┴────────┴────────┴────────┴────────┴────────────────────────────┘ │
│  * R/W based on member role (viewer/editor)                                             │
│                                                                                          │
└─────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 📊 Data Flow Diagrams

### Complete Vault Data Flow

```
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                              VAULT DATA FLOW DIAGRAM                                     │
├─────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                          │
│  ┌────────────────────────────────────────────────────────────────────────────────────┐ │
│  │                              CREATE/UPDATE VAULT ITEM                               │ │
│  └────────────────────────────────────────────────────────────────────────────────────┘ │
│                                                                                          │
│    ┌─────────┐      ┌──────────────────────────────────────────────────────────────┐   │
│    │  USER   │      │                        CLIENT BROWSER                         │   │
│    │ INPUT   │      │                                                               │   │
│    │         │      │  ┌────────────────┐     ┌────────────────┐    ┌────────────┐ │   │
│    │ • Title │ ──── │  │ Form Input     │────>│ SecureVault    │───>│ Argon2id   │ │   │
│    │ • User  │      │  │ Validation     │     │ Crypto         │    │ KDF        │ │   │
│    │ • Pass  │      │  │                │     │                │    │            │ │   │
│    │ • URL   │      │  │ XSS Prevention │     │ • masterPass   │    │ Derive     │ │   │
│    │ • Notes │      │  │ Input Sanitize │     │ • salt (server)│    │ 256-bit key│ │   │
│    └─────────┘      │  └────────────────┘     └────────────────┘    └─────┬──────┘ │   │
│                     │                                                      │        │   │
│                     │                                                      ▼        │   │
│                     │                                             ┌────────────────┐│   │
│                     │                                             │  AES-256-GCM   ││   │
│                     │                                             │  Encryption    ││   │
│                     │                                             │                ││   │
│                     │                                             │ • 12-byte IV   ││   │
│                     │                                             │ • 128-bit tag  ││   │
│                     │                                             │ • Ciphertext   ││   │
│                     │                                             └───────┬────────┘│   │
│                     │                                                     │         │   │
│                     │  ┌────────────────────────────────────────────────────────┐   │   │
│                     │  │                    ENCRYPTED PACKAGE                    │   │   │
│                     │  │  {                                                     │   │   │
│                     │  │    "v": "2.0",                                         │   │   │
│                     │  │    "alg": "AES-256-GCM-ARGON2ID",                      │   │   │
│                     │  │    "nonce": "base64(12-bytes)",                        │   │   │
│                     │  │    "ct": "base64(ciphertext+authtag)",                 │   │   │
│                     │  │    "compressed": true,                                 │   │   │
│                     │  │    "ts": 1699999999999                                 │   │   │
│                     │  │  }                                                     │   │   │
│                     │  └────────────────────────────────────────────────────────┘   │   │
│                     └───────────────────────────────────────────┬───────────────────┘   │
│                                                                 │                       │
│                                                    HTTPS POST   │                       │
│                                                    (TLS 1.3)    ▼                       │
│                                                                                          │
│  ┌────────────────────────────────────────────────────────────────────────────────────┐ │
│  │                                    DJANGO BACKEND                                   │ │
│  │                                                                                     │ │
│  │  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐                │ │
│  │  │  API Gateway    │    │  Authentication  │    │  Vault Service  │                │ │
│  │  │                 │    │                  │    │                 │                │ │
│  │  │  • JWT Verify   │───>│  • User lookup   │───>│  • Validate     │                │ │
│  │  │  • Rate limit   │    │  • Permission    │    │  • Store blob   │                │ │
│  │  │  • CORS         │    │  • Audit log     │    │  • Version      │                │ │
│  │  └─────────────────┘    └─────────────────┘    └────────┬────────┘                │ │
│  │                                                          │                         │ │
│  │                                                          ▼                         │ │
│  │                                               ┌─────────────────┐                  │ │
│  │                                               │   PostgreSQL    │                  │ │
│  │                                               │                 │                  │ │
│  │                                               │ EncryptedVault  │                  │ │
│  │                                               │ Item:           │                  │ │
│  │                                               │ • id (UUID)     │                  │ │
│  │                                               │ • user_id (FK)  │                  │ │
│  │                                               │ • encrypted_data│ ◄── OPAQUE BLOB │ │
│  │                                               │ • item_type     │                  │ │
│  │                                               │ • folder_id     │                  │ │
│  │                                               │ • crypto_version│                  │ │
│  │                                               │ • timestamps    │                  │ │
│  │                                               └─────────────────┘                  │ │
│  └────────────────────────────────────────────────────────────────────────────────────┘ │
│                                                                                          │
│                          ✓ Server NEVER sees plaintext password                         │
│                          ✓ Server stores encrypted blob only                            │
│                          ✓ Decryption key never leaves client                           │
│                                                                                          │
└─────────────────────────────────────────────────────────────────────────────────────────┘
```

### Post-Quantum Encryption Data Flow (Kyber-768)

```
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                     CRYSTALS-KYBER HYBRID ENCRYPTION DATA FLOW                           │
├─────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                          │
│    ┌───────────────────────────────────────────────────────────────────────────────┐    │
│    │                           KEY GENERATION PHASE                                 │    │
│    └───────────────────────────────────────────────────────────────────────────────┘    │
│                                                                                          │
│    ┌─────────────────────────┐                      ┌─────────────────────────┐         │
│    │      KYBER-768          │                      │        X25519           │         │
│    │   (Post-Quantum KEM)    │                      │   (Classical ECDH)      │         │
│    │                         │                      │                         │         │
│    │  ┌─────────────────┐    │                      │  ┌─────────────────┐    │         │
│    │  │ KeyGen()        │    │                      │  │ KeyGen()        │    │         │
│    │  │                 │    │                      │  │                 │    │         │
│    │  │ pk: 1184 bytes  │    │                      │  │ pk: 32 bytes    │    │         │
│    │  │ sk: 2400 bytes  │    │                      │  │ sk: 32 bytes    │    │         │
│    │  └─────────────────┘    │                      │  └─────────────────┘    │         │
│    └───────────┬─────────────┘                      └───────────┬─────────────┘         │
│                │                                                │                       │
│                └──────────────────┬─────────────────────────────┘                       │
│                                   │                                                     │
│                                   ▼                                                     │
│                     ┌─────────────────────────────┐                                     │
│                     │    HYBRID PUBLIC KEY        │                                     │
│                     │                             │                                     │
│                     │  {                          │                                     │
│                     │    kyber: pk_kyber,         │                                     │
│                     │    x25519: pk_x25519        │                                     │
│                     │  }                          │                                     │
│                     │                             │                                     │
│                     │  Stored in: KyberKeyPair    │                                     │
│                     │  model with UUID primary key│                                     │
│                     └─────────────────────────────┘                                     │
│                                                                                          │
│    ┌───────────────────────────────────────────────────────────────────────────────┐    │
│    │                           ENCRYPTION PHASE                                     │    │
│    └───────────────────────────────────────────────────────────────────────────────┘    │
│                                                                                          │
│       PLAINTEXT                                                                          │
│          │                                                                               │
│          ▼                                                                               │
│    ┌─────────────────────────────────────────────────────────────────────────────────┐  │
│    │                                                                                  │  │
│    │  ┌─────────────────────┐              ┌─────────────────────┐                   │  │
│    │  │  Kyber.Encaps()     │              │  X25519.DH()        │                   │  │
│    │  │                     │              │                     │                   │  │
│    │  │  Input: pk_kyber    │              │  Input: pk_x25519   │                   │  │
│    │  │  Output:            │              │  Output:            │                   │  │
│    │  │   • ct: 1088 bytes  │              │   • ephemeral pk    │                   │  │
│    │  │   • ss: 32 bytes    │              │   • ss: 32 bytes    │                   │  │
│    │  └──────────┬──────────┘              └──────────┬──────────┘                   │  │
│    │             │                                    │                              │  │
│    │             │    ┌───────────────────────────────┘                              │  │
│    │             │    │                                                              │  │
│    │             ▼    ▼                                                              │  │
│    │  ┌─────────────────────────────────────────────────────────────────────────┐   │  │
│    │  │                     COMBINE SHARED SECRETS                               │   │  │
│    │  │                                                                          │   │  │
│    │  │   combined_ss = HKDF-SHA256(kyber_ss || x25519_ss, salt, info)          │   │  │
│    │  │                                                                          │   │  │
│    │  │   Output: 256-bit combined key                                          │   │  │
│    │  └─────────────────────────────────────────────────────────────────────────┘   │  │
│    │                                           │                                     │  │
│    │                                           ▼                                     │  │
│    │                              ┌─────────────────────────────┐                    │  │
│    │                              │      AES-256-GCM            │                    │  │
│    │                              │                             │                    │  │
│    │    PLAINTEXT ───────────────>│  Encrypt(plaintext,         │                    │  │
│    │                              │          combined_key,      │                    │  │
│    │                              │          nonce)             │                    │  │
│    │                              │                             │                    │  │
│    │                              │  Output: ciphertext + tag   │                    │  │
│    │                              └─────────────────────────────┘                    │  │
│    │                                                                                  │  │
│    └──────────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                          │
│    ┌───────────────────────────────────────────────────────────────────────────────┐    │
│    │                           STORED DATA STRUCTURE                                │    │
│    └───────────────────────────────────────────────────────────────────────────────┘    │
│                                                                                          │
│    ┌─────────────────────────────────────────────────────────────────────────────────┐  │
│    │  KyberEncryptedPassword model:                                                   │  │
│    │                                                                                  │  │
│    │  ┌─────────────────────┬────────────────────────────────────────────────────┐   │  │
│    │  │ Field               │ Description                                        │   │  │
│    │  ├─────────────────────┼────────────────────────────────────────────────────┤   │  │
│    │  │ id                  │ UUID primary key                                   │   │  │
│    │  │ user_id             │ Foreign key to User                                │   │  │
│    │  │ keypair_id          │ Foreign key to KyberKeyPair                        │   │  │
│    │  │ service_name        │ Service identifier (not encrypted)                 │   │  │
│    │  │ kyber_ciphertext    │ Kyber KEM ciphertext (1088 bytes)                  │   │  │
│    │  │ aes_ciphertext      │ AES-256-GCM encrypted data                         │   │  │
│    │  │ nonce               │ AES-GCM nonce (12 bytes)                           │   │  │
│    │  │ ephemeral_public_key│ X25519 ephemeral key (32 bytes)                    │   │  │
│    │  │ algorithm           │ "Kyber768-AES256-GCM"                              │   │  │
│    │  │ encryption_version  │ Encryption scheme version                          │   │  │
│    │  │ created_at          │ Timestamp                                          │   │  │
│    │  └─────────────────────┴────────────────────────────────────────────────────┘   │  │
│    └─────────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                          │
└─────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 🔒 Zero-Knowledge Security Architecture

SecureVault implements a **true zero-knowledge architecture** where sensitive data is encrypted client-side before any transmission. The server only stores and retrieves encrypted blobs.

### Security Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                      CLIENT (Browser)                            │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │  Master Password → Argon2id → Encryption Key                ││
│  │       │                            │                        ││
│  │       ▼                            ▼                        ││
│  │  Auth Hash (sent)          Encrypt Data (local)             ││
│  └─────────────────────────────────────────────────────────────┘│
└──────────────────────────┬──────────────────────────────────────┘
                           │ (Only encrypted data + auth hash)
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                      SERVER (Django)                             │
│  • Stores encrypted blobs only                                  │
│  • Verifies auth hash (double-hashed)                          │
│  • Never sees plaintext passwords                              │
│  • Caches non-sensitive metadata                               │
└─────────────────────────────────────────────────────────────────┘
```

### Key Security Principles

| Principle | Implementation |
|-----------|----------------|
| **Master Password Never Leaves Client** | Argon2id derives encryption key locally; auth hash sent for verification |
| **Double-Hashing for Auth** | Client hashes password, server hashes the hash again |
| **Client-Side Encryption** | AES-256-GCM with WebCrypto API before any API call |
| **Encrypted Blob Storage** | Server stores opaque ciphertext + non-sensitive metadata |
| **Client-Side Decryption** | All decryption happens in browser memory only |
| **Session Auto-Lock** | Automatic key clearing after configurable timeout |
| **Secure Memory Clearing** | Keys wiped from memory on lock/logout |
| **Adaptive Password is Zero-Knowledge** | The adaptive/typing-pattern feature sends only a client-keyed HMAC fingerprint + coarse features (length bucket, timings) and masked previews; the raw password never leaves the device, and the server rejects any plaintext field. Suggestions are generated client-side from a downloaded preference model. |

### Authentication Flow (Zero-Knowledge)

```mermaid
sequenceDiagram
    participant U as User
    participant C as Client (Browser)
    participant S as Server

    U->>C: Enter master password
    
    Note over C: Key Derivation (Client)
    C->>C: salt = fetch from server
    C->>C: encryptionKey = Argon2id(password, salt)
    C->>C: authHash = Argon2id(password + ":auth", salt)
    
    C->>S: POST /verify_auth/ {auth_hash}
    Note over S: Server verifies hash of hash
    S->>S: storedHash = SHA256(authHash)
    S->>S: Compare with database
    S->>C: {valid: true}
    
    Note over C: Session Established
    C->>C: Store encryptionKey in memory
    C->>C: Clear password from memory
    
    Note over U,S: Password NEVER sent to server!
```

---

## 📐 Entity Relationship Diagrams

### Complete Database ER Diagram

```
┌─────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                    SECUREVAULT DATABASE SCHEMA (ER DIAGRAM)                                      │
├─────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                                                  │
│  ╔══════════════════════════════════════════════════════════════════════════════════════════════════════════╗   │
│  ║                                         CORE USER & AUTH DOMAIN                                           ║   │
│  ╚══════════════════════════════════════════════════════════════════════════════════════════════════════════╝   │
│                                                                                                                  │
│   ┌────────────────────────┐         ┌────────────────────────┐         ┌────────────────────────┐             │
│   │         User           │         │      TwoFactorAuth     │         │       UserSalt         │             │
│   │  (django.auth.User)    │         │                        │         │                        │             │
│   ├────────────────────────┤         ├────────────────────────┤         ├────────────────────────┤             │
│   │ PK  id            INT  │◄────┐   │ PK  id            INT  │         │ PK  id            INT  │             │
│   │     username      VAR  │     │   │ FK  user_id       INT  │────────►│ FK  user_id       INT  │────────┐    │
│   │     email         VAR  │     │   │     is_enabled    BOOL │         │     salt          BIN  │        │    │
│   │     password      VAR  │     │   │     mfa_type      VAR  │         │     auth_hash     BIN  │        │    │
│   │     first_name    VAR  │     │   │     secret_key    VAR  │         │     created_at    TS   │        │    │
│   │     last_name     VAR  │     │   │     backup_codes  TEXT │         └────────────────────────┘        │    │
│   │     is_active     BOOL │     │   │     authy_id      VAR  │                                            │    │
│   │     date_joined   TS   │     │   │     phone_number  VAR  │                                            │    │
│   │     last_login    TS   │     │   │     last_used     TS   │                                            │    │
│   └─────────┬──────────────┘     │   └────────────────────────┘                                            │    │
│             │                    │                                                                          │    │
│             │                    │   ┌────────────────────────┐         ┌────────────────────────┐         │    │
│             │                    │   │      UserPasskey       │         │      RecoveryKey       │         │    │
│             │                    │   │                        │         │                        │         │    │
│             │                    │   ├────────────────────────┤         ├────────────────────────┤         │    │
│             │                    └───│ FK  user_id       INT  │────────►│ FK  user_id       INT  │─────────┘    │
│             │                        │     credential_id BIN  │ (unique)│     encrypted_vault TEXT│             │
│             │                        │     public_key    BIN  │         │     salt          VAR  │             │
│             │                        │     sign_count    INT  │         │     method        VAR  │             │
│             │                        │     rp_id         VAR  │         │     created_at    TS   │             │
│             │                        │     device_type   VAR  │         └────────────────────────┘             │
│             │                        │     created_at    TS   │                                                 │
│             │                        │     last_used_at  TS   │                                                 │
│             │                        └────────────────────────┘                                                 │
│             │                                                                                                   │
│             │                                                                                                   │
│  ╔══════════╧═══════════════════════════════════════════════════════════════════════════════════════════════╗   │
│  ║                                         VAULT & ENCRYPTION DOMAIN                                          ║   │
│  ╚══════════════════════════════════════════════════════════════════════════════════════════════════════════╝   │
│             │                                                                                                   │
│             │                    ┌────────────────────────────┐                                                 │
│             │                    │       VaultFolder          │                                                 │
│             │                    │                            │                                                 │
│             │                    ├────────────────────────────┤                                                 │
│             ├───────────────────►│ PK  id              INT    │◄─────────┐                                      │
│             │                    │ FK  user_id         INT    │          │                                      │
│             │                    │ FK  parent_id       INT    │──────────┘ (self-ref)                           │
│             │                    │     name            VAR    │                                                 │
│             │                    │     description     TEXT   │                                                 │
│             │                    │     color           VAR    │                                                 │
│             │                    │     icon            VAR    │                                                 │
│             │                    │     created_at      TS     │                                                 │
│             │                    └───────────────┬────────────┘                                                 │
│             │                                    │                                                              │
│             │                                    │                                                              │
│             │    ┌───────────────────────────────┴───────────────────────────────┐                              │
│             │    │                                                               │                              │
│             │    ▼                                                               ▼                              │
│   ┌─────────┴────────────────────┐                             ┌────────────────────────────────────┐          │
│   │    EncryptedVaultItem        │                             │        KyberEncryptedPassword      │          │
│   │                              │                             │                                    │          │
│   ├──────────────────────────────┤                             ├────────────────────────────────────┤          │
│   │ PK  id              UUID     │                             │ PK  id                  UUID       │          │
│   │ FK  user_id         INT      │◄────────────────────────────│ FK  user_id             INT        │          │
│   │ FK  folder_id       INT      │                             │ FK  keypair_id          UUID       │──────┐   │
│   │     item_id         VAR      │ (unique)                    │     service_name        VAR        │      │   │
│   │     item_type       VAR      │                             │     username            VAR        │      │   │
│   │     encrypted_data  TEXT     │ ◄── OPAQUE BLOB             │     url                 URL        │      │   │
│   │     crypto_version  INT      │                             │     kyber_ciphertext    BIN        │ ◄── KEM │
│   │     crypto_metadata JSON     │                             │     aes_ciphertext      BIN        │ ◄── ENC │
│   │     pqc_wrapped_key BIN      │                             │     nonce               BIN        │      │   │
│   │     fhe_password    BIN      │                             │     ephemeral_public_key BIN       │      │   │
│   │     encrypted_domain_hash BIN│                             │     encryption_version  INT        │      │   │
│   │     cached_strength_score BIN│                             │     algorithm           VAR        │      │   │
│   │     tags            JSON     │                             │     is_favorite         BOOL       │      │   │
│   │     favorite        BOOL     │                             │     is_deleted          BOOL       │      │   │
│   │     deleted         BOOL     │                             │     created_at          TS         │      │   │
│   │     created_at      TS       │                             │     last_accessed       TS         │      │   │
│   │     updated_at      TS       │                             └────────────────────────────────────┘      │   │
│   └──────────────────────────────┘                                                                         │   │
│                                                                                                            │   │
│                                                                                                            │   │
│  ╔═══════════════════════════════════════════════════════════════════════════════════════════════════════╗ │   │
│  ║                                    KYBER POST-QUANTUM CRYPTO DOMAIN                                    ║ │   │
│  ╚═══════════════════════════════════════════════════════════════════════════════════════════════════════╝ │   │
│                                                                                                            │   │
│   ┌────────────────────────────────────┐                      ┌────────────────────────────────────┐       │   │
│   │          KyberKeyPair              │                      │          KyberSession              │       │   │
│   │                                    │                      │                                    │       │   │
│   ├────────────────────────────────────┤                      ├────────────────────────────────────┤       │   │
│   │ PK  id                UUID         │◄─────────────────────│ PK  id                UUID         │       │   │
│   │ FK  user_id           INT          │                      │ FK  user_id           INT          │       │   │
│   │     public_key        BIN (1184B)  │                      │ FK  keypair_id        UUID         │───────┘   │
│   │     private_key       BIN (2400B)  │                      │     session_id        VAR          │ (unique)  │
│   │     key_version       INT          │                      │     ciphertext        BIN          │           │
│   │     algorithm         VAR          │                      │     encrypted_shared_secret BIN    │           │
│   │     security_level    INT          │                      │     ip_address        INET         │           │
│   │     is_active         BOOL         │                      │     user_agent        TEXT         │           │
│   │     is_compromised    BOOL         │                      │     is_active         BOOL         │           │
│   │     x25519_public_key BIN (32B)    │                      │     created_at        TS           │           │
│   │     x25519_private_key BIN (32B)   │                      │     expires_at        TS           │           │
│   │     encryption_count  INT          │                      └────────────────────────────────────┘           │
│   │     decryption_count  INT          │                                                                       │
│   │     created_at        TS           │                                                                       │
│   │     last_used         TS           │                                                                       │
│   │     expires_at        TS           │                                                                       │
│   └────────────────────────────────────┘                                                                       │
│                                                                                                                 │
│                                                                                                                 │
│  ╔═══════════════════════════════════════════════════════════════════════════════════════════════════════════╗ │
│  ║                                    BEHAVIORAL RECOVERY DOMAIN                                              ║ │
│  ╚═══════════════════════════════════════════════════════════════════════════════════════════════════════════╝ │
│                                                                                                                 │
│   ┌──────────────────────────────┐        ┌──────────────────────────────┐        ┌─────────────────────────┐  │
│   │   BehavioralCommitment       │        │  BehavioralRecoveryAttempt   │        │   BehavioralChallenge   │  │
│   │                              │        │                              │        │                         │  │
│   ├──────────────────────────────┤        ├──────────────────────────────┤        ├─────────────────────────┤  │
│   │ PK  id              INT      │        │ PK  id              INT      │◄───────│ FK  recovery_attempt_id │  │
│   │ FK  user_id         INT      │        │ FK  user_id         INT      │        │ PK  id              INT │  │
│   │     commitment_id   UUID     │unique  │     attempt_id      UUID     │unique  │     challenge_id    UUID│  │
│   │     encrypted_embedding BIN  │        │     current_stage   VAR      │        │     challenge_type  VAR │  │
│   │     challenge_type  VAR      │        │     samples_collected INT    │        │     challenge_data  JSON│  │
│   │     unlock_conditions JSON   │        │     challenges_completed INT │        │     user_response   JSON│  │
│   │     is_active       BOOL     │        │     similarity_scores JSON   │        │     similarity_score FLT│  │
│   │     samples_used    INT      │        │     overall_similarity FLT   │        │     passed          BOOL│  │
│   │     kyber_public_key BIN     │        │     status          VAR      │        │     attempt_number  INT │  │
│   │     kyber_ciphertext BIN     │        │     ip_address      INET     │        │     created_at      TS  │  │
│   │     is_quantum_protected BOOL│        │     device_fingerprint VAR   │        │     completed_at    TS  │  │
│   │     blockchain_hash VAR      │        │     started_at      TS       │        └─────────────────────────┘  │
│   │     blockchain_anchored BOOL │        │     completed_at    TS       │                                     │
│   │     creation_timestamp TS    │        └──────────────────────────────┘                                     │
│   └──────────────────────────────┘                                                                              │
│                                                                                                                 │
│                                                                                                                 │
│  ╔═══════════════════════════════════════════════════════════════════════════════════════════════════════════╗ │
│  ║                                      FHE & SECURITY DOMAIN                                                 ║ │
│  ╚═══════════════════════════════════════════════════════════════════════════════════════════════════════════╝ │
│                                                                                                                 │
│   ┌──────────────────────────────┐        ┌──────────────────────────────┐        ┌─────────────────────────┐  │
│   │       FHEKeyStore            │        │     FHEComputationCache      │        │     FHEOperationLog     │  │
│   │                              │        │                              │        │                         │  │
│   ├──────────────────────────────┤        ├──────────────────────────────┤        ├─────────────────────────┤  │
│   │ PK  id              UUID     │        │ PK  id              UUID     │        │ PK  id              UUID│  │
│   │ FK  user_id         INT      │        │ FK  user_id         INT      │        │ FK  user_id         INT │  │
│   │     key_type        VAR      │        │     operation_type  VAR      │        │     operation_type  VAR │  │
│   │     encrypted_key_data BIN   │        │     input_hash      VAR      │idx     │     encryption_tier VAR │  │
│   │     key_size_bits   INT      │        │     encrypted_result BIN     │        │     status          VAR │  │
│   │     polynomial_mod_deg INT   │        │     computation_time_ms INT  │        │     total_time_ms   INT │  │
│   │     security_level  INT      │        │     circuit_depth   INT      │        │     cache_hit       BOOL│  │
│   │     is_active       BOOL     │        │     hit_count       INT      │        │     error_message   TEXT│  │
│   │     created_at      TS       │        │     expires_at      TS       │        │     created_at      TS  │  │
│   │     expires_at      TS       │        │     created_at      TS       │        └─────────────────────────┘  │
│   └──────────────────────────────┘        └──────────────────────────────┘                                     │
│                                                                                                                 │
│   ┌──────────────────────────────┐        ┌──────────────────────────────┐        ┌─────────────────────────┐  │
│   │       UserDevice             │        │       LoginAttempt           │        │     SecurityAlert       │  │
│   │                              │        │                              │        │                         │  │
│   ├──────────────────────────────┤        ├──────────────────────────────┤        ├─────────────────────────┤  │
│   │ PK  id              INT      │        │ PK  id              INT      │        │ PK  id              INT │  │
│   │ FK  user_id         INT      │        │ FK  user_id         INT      │        │ FK  user_id         INT │  │
│   │     device_id       UUID     │unique  │ FK  device_id       INT      │        │     alert_type      VAR │  │
│   │     device_name     VAR      │        │     username_attempted VAR   │        │     severity        VAR │  │
│   │     device_type     VAR      │        │     ip_address      INET     │        │     title           VAR │  │
│   │     fingerprint     VAR      │unique  │     status          VAR      │        │     message         TEXT│  │
│   │     browser         VAR      │        │     failure_reason  VAR      │        │     data            JSON│  │
│   │     os              VAR      │        │     is_suspicious   BOOL     │        │     is_read         BOOL│  │
│   │     ip_address      INET     │        │     threat_score    INT      │        │     is_resolved     BOOL│  │
│   │     is_trusted      BOOL     │        │     timestamp       TS       │        │     created_at      TS  │  │
│   │     last_seen       TS       │        └──────────────────────────────┘        └─────────────────────────┘  │
│   └──────────────────────────────┘                                                                              │
│                                                                                                                 │
│                                                                                                                 │
│  ╔═══════════════════════════════════════════════════════════════════════════════════════════════════════════╗ │
│  ║                                   OIDC (OpenID Connect) DOMAIN                                            ║ │
│  ╚═══════════════════════════════════════════════════════════════════════════════════════════════════════════╝ │
│                                                                                                                 │
│   ┌──────────────────────────────┐        ┌──────────────────────────────┐        ┌─────────────────────────┐  │
│   │       OIDCProvider           │        │       OIDCSession            │        │    OIDCUserMapping      │  │
│   ├──────────────────────────────┤        ├──────────────────────────────┤        ├─────────────────────────┤  │
│   │ PK  id              UUID     │        │ PK  id              UUID     │        │ PK  id              INT │  │
│   │     name            VAR      │unique  │ FK  user_id         INT      │        │ FK  user_id         INT │  │
│   │     client_id       VAR      │        │ FK  provider_id     UUID     │        │ FK  provider_id     UUID│  │
│   │     client_secret   VAR      │        │     state           VAR      │        │     oidc_subject    VAR │  │
│   │     discovery_url   VAR      │        │     nonce           VAR      │        │     oidc_email      VAR │  │
│   │     authorization_ep VAR     │        │     pkce_verifier   VAR      │        │     oidc_name       VAR │  │
│   │     token_endpoint  VAR      │        │     id_token        TEXT     │        │     linked_at       TS  │  │
│   │     userinfo_ep     VAR      │        │     access_token    TEXT     │        │     last_login      TS  │  │
│   │     jwks_uri        VAR      │        │     refresh_token   TEXT     │        │     is_primary      BOOL│  │
│   │     issuer          VAR      │        │     token_expires   TS       │        └─────────────────────────┘  │
│   │     scopes          JSON     │        │     created_at      TS       │                                     │
│   │     is_active       BOOL     │        │     status          VAR      │                                     │
│   │     created_at      TS       │        └──────────────────────────────┘                                     │
│   └──────────────────────────────┘                                                                              │
│                                                                                                                 │
│   OIDC: OIDCProvider → OIDCSession → OIDCUserMapping → USER (Okta, Azure AD, Auth0, Google, Keycloak)          │
│                                                                                                                 │
│                                                                                                                 │
│  ╔═══════════════════════════════════════════════════════════════════════════════════════════════════════════╗ │
│  ║                                       RELATIONSHIPS LEGEND                                                 ║ │
│  ╠═══════════════════════════════════════════════════════════════════════════════════════════════════════════╣ │
│  ║                                                                                                            ║ │
│  ║   ───────►  One-to-Many (FK)     ◄──────►  One-to-One     ────┐    Self-referencing                       ║ │
│  ║                                                            ───┘                                            ║ │
│  ║                                                                                                            ║ │
│  ║   PK = Primary Key    FK = Foreign Key    TS = Timestamp    BIN = Binary    VAR = VARCHAR                 ║ │
│  ║   UUID = UUID type    BOOL = Boolean      INT = Integer     TEXT = Text     JSON = JSON type              ║ │
│  ║                                                                                                            ║ │
│  ╚═══════════════════════════════════════════════════════════════════════════════════════════════════════════╝ │
│                                                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘
```

### Simplified ER Diagram (Core Relationships)

```mermaid
erDiagram
    USER ||--o{ ENCRYPTEDVAULTITEM : owns
    USER ||--o{ KYBERKEYAPAIR : has
    USER ||--o{ USERPASSKEY : has
    USER ||--|| TWOFACTORAUTH : has
    USER ||--|| USERSALT : has
    USER ||--|| RECOVERYKEY : has
    USER ||--o{ BEHAVIORALCOMMITMENT : creates
    USER ||--o{ BEHAVIORALRECOVERYATTEMPT : initiates
    USER ||--o{ USERDEVICE : uses
    USER ||--o{ LOGINATTEMPT : makes
    USER ||--o{ SECURITYALERT : receives
    USER ||--o{ FHEKEYSTORE : owns
    
    VAULTFOLDER ||--o{ ENCRYPTEDVAULTITEM : contains
    VAULTFOLDER ||--o{ VAULTFOLDER : parent_of
    
    KYBERKEYPAIR ||--o{ KYBERENCRYPTEDPASSWORD : encrypts
    KYBERKEYPAIR ||--o{ KYBERSESSION : has
    
    BEHAVIORALRECOVERYATTEMPT ||--o{ BEHAVIORALCHALLENGE : includes
    BEHAVIORALRECOVERYATTEMPT ||--|| RECOVERYFEEDBACK : receives
    
    OIDCPROVIDER ||--o{ OIDCSESSION : authenticates
    OIDCSESSION ||--|| USER : authenticates
    USER ||--o{ OIDCUSERMAPPING : linked_via
    OIDCPROVIDER ||--o{ OIDCUSERMAPPING : provides
    
    USER {
        int id PK
        string username
        string email
        string password
        boolean is_active
    }
    
    ENCRYPTEDVAULTITEM {
        uuid id PK
        int user_id FK
        int folder_id FK
        string item_type
        text encrypted_data
        int crypto_version
    }
    
    KYBERKEYPAIR {
        uuid id PK
        int user_id FK
        binary public_key
        binary private_key
        int key_version
        boolean is_active
    }
    
    BEHAVIORALCOMMITMENT {
        int id PK
        int user_id FK
        uuid commitment_id
        binary encrypted_embedding
        string challenge_type
        boolean blockchain_anchored
    }
```

---

## 🔧 Technology Stack

### Backend Technologies

| Technology | Version | Purpose |
|------------|---------|---------|
| Python | 3.13 | Primary language |
| Django | 4.2.27 | Web framework (LTS) |
| Django REST Framework | 3.16+ | REST API |
| Django Channels | 4.0+ | WebSocket support |
| Celery | 5.5+ | Background tasks |
| Redis | 7.0+ | Cache & message broker |
| PostgreSQL | 15+ | Primary database |
| TensorFlow/Keras | 2.13+ | ML models |
| Transformers | 4.35+ | NLP models |
| Web3.py | 7.0+ | Blockchain interaction |
| mozilla-django-oidc | 4.0+ | OpenID Connect integration |
| Concrete-Python | 2.5+ | Lightweight FHE operations (optional) |
| TenSEAL | 0.3.14+ | Batch FHE operations (optional) |

### Frontend Technologies

| Technology | Version | Purpose |
|------------|---------|---------|
| React | 18.2.0 | UI framework |
| Vite | 5.1.4 | Build tool |
| TensorFlow.js | 3.21.0 | Client-side ML |
| @stablelib/x25519 | 2.0.1 | X25519 ECDH |
| Argon2-browser | 1.18.0 | Client-side KDF |
| CryptoJS | 4.2.0 | Cryptographic operations |
| tsparticles | 3.9.1 | UI animations |
| React Router | 7.5.2 | Client routing |

### 📦 Complete Frontend Dependencies (package.json)

SecureVault's frontend uses a carefully curated set of libraries for security, performance, and user experience.

---

#### 🔐 Core Cryptography & Security Libraries

| Package | Version | Category | Description |
|---------|---------|----------|-------------|
| **argon2-browser** | ^1.18.0 | 🔐 KDF | Memory-hard key derivation function (Argon2id) compiled to WebAssembly. Winner of the Password Hashing Competition (PHC). Used for deriving encryption keys from master passwords with adaptive parameters (32-128MB memory based on device capability). |
| **crypto-js** | ^4.2.0 | 🔐 Encryption | JavaScript library of cryptographic standards including AES-256-CBC, SHA-256, HMAC, PBKDF2. Used as fallback when WebCrypto API is unavailable. Provides legacy encryption compatibility. |
| **@noble/curves** | ^1.6.0 | 🔐 ECC | Audited, zero-dependency implementation of elliptic curve cryptography. Provides P-384 (secp384r1), Ed25519 for hybrid ECDH key exchange alongside Kyber for defense-in-depth. |
| **@noble/hashes** | ^1.5.0 | 🔐 Hashing | Audited cryptographic hash functions including SHA-256, SHA-512, HKDF, HMAC. Used for key derivation, message authentication, and combining shared secrets. |
| **@stablelib/random** | ^1.0.2 | 🔐 RNG | Cryptographically secure random number generation. Provides cross-platform entropy for key generation, nonces, and IVs. |
| **@stablelib/sha256** | ^2.0.1 | 🔐 Hashing | Optimized SHA-256 implementation. Used in HKDF operations to combine Kyber and X25519 shared secrets. |
| **@stablelib/x25519** | ^2.0.1 | 🔐 ECDH | Curve25519 elliptic curve Diffie-Hellman key agreement. Provides fast, secure key exchange as the classical fallback alongside post-quantum Kyber. |

---

#### 🛡️ Post-Quantum Cryptography (PQC) Libraries

| Package | Version | Category | Description |
|---------|---------|----------|-------------|
| **crystals-kyber-js** | ^2.5.0 | 🛡️ PQC | Pure JavaScript implementation of CRYSTALS-Kyber-768 (NIST Level 3). Provides quantum-resistant key encapsulation mechanism. Primary PQC library with full WebAssembly acceleration. |
| **mlkem** | ^2.5.0 | 🛡️ PQC | ML-KEM (Module-Lattice Key Encapsulation Mechanism) - the standardized name for Kyber post NIST finalization. Alternative implementation with optimized performance characteristics. |
| **pqc-kyber** | ^0.7.0 | 🛡️ PQC | Another Kyber implementation providing redundancy for post-quantum operations. Used as fallback if primary libraries fail to initialize. All three Kyber libraries enable robust PQC with multiple fallback options. |

---

#### 🤖 Machine Learning & AI Libraries

| Package | Version | Category | Description |
|---------|---------|----------|-------------|
| **@tensorflow/tfjs** | ^3.21.0 | 🤖 ML Core | TensorFlow.js core library for client-side machine learning. Powers real-time password strength prediction, anomaly detection, and behavioral biometrics analysis directly in the browser. |
| **@tensorflow/tfjs-core** | ^3.21.0 | 🤖 ML Core | Core TensorFlow.js operations and tensor manipulation. Provides low-level ML primitives for custom model operations. |
| **@tensorflow/tfjs-backend-webgl** | ^3.21.0 | 🤖 ML Acceleration | WebGL backend for TensorFlow.js enabling GPU-accelerated inference. Provides 10-50x speedup for ML operations on capable devices. |
| **@tensorflow/tfjs-converter** | ^3.21.0 | 🤖 Model Loading | Converts TensorFlow SavedModels and Keras models to TensorFlow.js format. Enables loading pre-trained ML models for password analysis. |
| **@tensorflow-models/universal-sentence-encoder** | ^1.3.3 | 🤖 NLP | Universal Sentence Encoder for semantic text understanding. Used in behavioral profiling to analyze typing patterns and generate 247-dimensional embeddings. |

---

#### ⚛️ React Ecosystem

| Package | Version | Category | Description |
|---------|---------|----------|-------------|
| **react** | ^18.2.0 | ⚛️ Core | Core React library with concurrent features, automatic batching, and Suspense for data fetching. Foundation of SecureVault's component architecture. |
| **react-dom** | ^18.2.0 | ⚛️ DOM | React DOM renderer for web applications. Provides React 18's new root API (`createRoot`) for improved rendering performance. |
| **react-router-dom** | ^7.5.2 | ⚛️ Routing | Declarative routing for React applications. Handles client-side navigation, protected routes, and deep linking for vault items. |
| **react-hot-toast** | ^2.5.2 | ⚛️ Notifications | Lightweight, customizable toast notifications. Provides user feedback for security events, form validation, and system status. |
| **react-icons** | ^5.5.0 | ⚛️ Icons | Comprehensive icon library including Font Awesome, Material Design, Heroicons. Used throughout the UI for consistent iconography. |

---

#### 🎨 UI & Animation Libraries

| Package | Version | Category | Description |
|---------|---------|----------|-------------|
| **framer-motion** | ^12.9.1 | 🎨 Animation | Production-ready motion library for React. Powers smooth page transitions, micro-interactions, and gesture-based animations throughout the vault interface. |
| **styled-components** | ^6.1.17 | 🎨 CSS-in-JS | Visual primitives for component-age styling. Enables dynamic theming, scoped styles, and server-side rendering support. |
| **@tsparticles/react** | ^3.0.0 | 🎨 Effects | React wrapper for tsparticles. Provides interactive particle backgrounds for login/signup pages. |
| **@tsparticles/slim** | ^3.9.1 | 🎨 Effects | Lightweight tsparticles bundle with essential features. Creates visual effects without full library overhead (~60% smaller). |
| **lucide-react** | ^0.515.0 | 🎨 Icons | Beautiful, consistent icon library. Alternative to react-icons with better tree-shaking support. |
| **qrcode.react** | ^4.2.0 | 🎨 QR Codes | React component for generating QR codes. Used for TOTP setup, passkey enrollment, and secure credential sharing. |

---

#### 🔥 Firebase & Push Notifications

| Package | Version | Category | Description |
|---------|---------|----------|-------------|
| **firebase** | ^11.7.1 | 🔥 BaaS | Firebase SDK for web. Provides push notifications, real-time database sync, and analytics. Powers cross-device notifications and security alerts. |
| **react-firebase-hooks** | ^5.1.1 | 🔥 Firebase | React hooks for Firebase. Simplifies Firebase authentication state management and real-time data subscriptions. |

---

#### 📝 Form Management & Validation

| Package | Version | Category | Description |
|---------|---------|----------|-------------|
| **formik** | ^2.4.6 | 📝 Forms | Popular form library for React. Manages form state, validation, and submission for login, signup, vault item creation, and settings forms. |
| **yup** | ^1.6.1 | 📝 Validation | Schema validation library. Defines validation rules for email format, password strength requirements, and vault item fields. |

---

#### 🔧 Utilities & Data Processing

| Package | Version | Category | Description |
|---------|---------|----------|-------------|
| **axios** | ^1.8.4 | 🔧 HTTP | Promise-based HTTP client. Handles all API communication with the Django backend including JWT refresh, request interceptors, and error handling. |
| **date-fns** | ^2.30.0 | 🔧 Dates | Modern JavaScript date utility library. Formats timestamps, calculates relative times ("2 hours ago"), and handles password expiration dates. |
| **pako** | ^2.1.0 | 🔧 Compression | High-speed zlib port. Compresses vault data before encryption (>1KB) to reduce storage and network overhead. Provides gzip/deflate compression. |
| **path-browserify** | ^1.0.1 | 🔧 Polyfill | Node.js `path` module for browsers. Required for some cryptographic libraries that expect Node.js environment. |
| **web-vitals** | ^2.1.4 | 🔧 Performance | Library for measuring Core Web Vitals (LCP, FID, CLS). Tracks real user performance metrics for optimization. |

---

#### 🛠️ Device Fingerprinting & Security

| Package | Version | Category | Description |
|---------|---------|----------|-------------|
| **@fingerprintjs/fingerprintjs** | ^3.4.2 | 🛠️ Security | Browser fingerprinting library. Generates unique device identifiers for trusted device recognition, anomaly detection, and session binding. |

---

#### 🌐 Communication Protocols

| Package | Version | Category | Description |
|---------|---------|----------|-------------|
| **@grpc/grpc-js** | ^1.13.3 | 🌐 gRPC | Pure JavaScript gRPC client. Enables high-performance communication with backend services, particularly for blockchain operations and FHE computations. |

---

#### 🧪 Development Dependencies

| Package | Version | Category | Description |
|---------|---------|----------|-------------|
| **vite** | ^5.1.4 | 🧪 Build | Next-generation frontend build tool. Provides instant dev server startup, HMR (Hot Module Replacement), and optimized production builds with tree-shaking. |
| **@vitejs/plugin-react** | ^4.2.1 | 🧪 Build | Official React plugin for Vite. Enables Fast Refresh, automatic JSX runtime, and React-specific optimizations. |
| **@vitejs/plugin-legacy** | ^5.3.1 | 🧪 Build | Legacy browser support plugin. Generates polyfills for older browsers while maintaining modern code for capable browsers. |
| **vite-plugin-wasm** | ^3.5.0 | 🧪 Build | WebAssembly support for Vite. Required for Argon2 and Kyber WASM modules to work correctly in dev and production. |
| **vite-plugin-top-level-await** | ^1.6.0 | 🧪 Build | Enables top-level await in modules. Required for async WASM initialization in cryptographic libraries. |
| **vitest** | ^1.3.1 | 🧪 Testing | Vite-native unit testing framework. Runs tests with same config as dev server, providing fast test execution. |
| **@vitest/ui** | ^1.3.1 | 🧪 Testing | Visual UI for Vitest. Provides interactive test runner with filtering, debugging, and coverage visualization. |
| **@testing-library/react** | ^16.3.0 | 🧪 Testing | React testing utilities. Enables testing components as users interact with them (by role, label, text). |
| **@testing-library/jest-dom** | ^6.6.3 | 🧪 Testing | Custom Jest matchers for DOM testing. Extends expect with toBeInTheDocument, toHaveStyle, toBeVisible, etc. |
| **@testing-library/user-event** | ^13.5.0 | 🧪 Testing | Simulates user interactions. Provides realistic click, type, and keyboard event simulation for integration tests. |
| **jsdom** | ^24.0.0 | 🧪 Testing | JavaScript DOM implementation. Provides browser-like environment for Node.js testing without a real browser. |

---

#### 📊 Frontend Dependency Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                       FRONTEND DEPENDENCY ARCHITECTURE                               │
├─────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                      │
│  ┌─────────────────────────────────────────────────────────────────────────────┐   │
│  │                           CORE LAYER                                         │   │
│  │  ┌────────────┐  ┌────────────┐  ┌────────────┐  ┌────────────────────────┐ │   │
│  │  │   react    │  │ react-dom  │  │   axios    │  │  react-router-dom      │ │   │
│  │  │  (18.2.0)  │  │  (18.2.0)  │  │  (1.8.4)   │  │     (7.5.2)            │ │   │
│  │  └────────────┘  └────────────┘  └────────────┘  └────────────────────────┘ │   │
│  └─────────────────────────────────────────────────────────────────────────────┘   │
│                                       │                                             │
│           ┌───────────────────────────┼───────────────────────────┐                │
│           │                           │                           │                │
│           ▼                           ▼                           ▼                │
│  ┌─────────────────────┐  ┌─────────────────────┐  ┌─────────────────────┐        │
│  │   🔐 CRYPTO LAYER   │  │   🤖 ML LAYER       │  │   🎨 UI LAYER       │        │
│  ├─────────────────────┤  ├─────────────────────┤  ├─────────────────────┤        │
│  │ • argon2-browser    │  │ • @tensorflow/tfjs  │  │ • framer-motion     │        │
│  │ • crypto-js         │  │ • tfjs-core         │  │ • styled-components │        │
│  │ • @noble/curves     │  │ • tfjs-backend-webgl│  │ • @tsparticles      │        │
│  │ • @noble/hashes     │  │ • tfjs-converter    │  │ • lucide-react      │        │
│  │ • @stablelib/x25519 │  │ • universal-encoder │  │ • react-icons       │        │
│  │ • @stablelib/sha256 │  │                     │  │ • qrcode.react      │        │
│  │ • @stablelib/random │  │                     │  │ • react-hot-toast   │        │
│  └─────────────────────┘  └─────────────────────┘  └─────────────────────┘        │
│           │                                                                        │
│           ▼                                                                        │
│  ┌─────────────────────────────────────────────────────────────────────────────┐   │
│  │                        🛡️ POST-QUANTUM LAYER                                │   │
│  ├─────────────────────────────────────────────────────────────────────────────┤   │
│  │  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐          │   │
│  │  │ crystals-kyber-js│  │      mlkem       │  │    pqc-kyber     │          │   │
│  │  │     (2.5.0)      │  │     (2.5.0)      │  │     (0.7.0)      │          │   │
│  │  │  [Primary PQC]   │  │  [NIST ML-KEM]   │  │   [Fallback]     │          │   │
│  │  └──────────────────┘  └──────────────────┘  └──────────────────┘          │   │
│  └─────────────────────────────────────────────────────────────────────────────┘   │
│                                                                                      │
│  ┌─────────────────────────────────────────────────────────────────────────────┐   │
│  │                           UTILITY LAYER                                      │   │
│  ├─────────────────────────────────────────────────────────────────────────────┤   │
│  │ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌────────────────────┐ │   │
│  │ │  formik  │ │   yup    │ │ date-fns │ │   pako   │ │ @fingerprintjs     │ │   │
│  │ │ (2.4.6)  │ │ (1.6.1)  │ │ (2.30.0) │ │ (2.1.0)  │ │ (3.4.2)            │ │   │
│  │ │  Forms   │ │Validation│ │  Dates   │ │Compress  │ │ Device ID          │ │   │
│  │ └──────────┘ └──────────┘ └──────────┘ └──────────┘ └────────────────────┘ │   │
│  └─────────────────────────────────────────────────────────────────────────────┘   │
│                                                                                      │
│  ┌─────────────────────────────────────────────────────────────────────────────┐   │
│  │                          BUILD LAYER (Dev)                                   │   │
│  ├─────────────────────────────────────────────────────────────────────────────┤   │
│  │ ┌──────────┐ ┌─────────────────┐ ┌──────────────────┐ ┌───────────────────┐│   │
│  │ │  vite    │ │ @vitejs/react   │ │ vite-plugin-wasm │ │ vitest + jsdom    ││   │
│  │ │ (5.1.4)  │ │ (4.2.1)         │ │ (3.5.0)          │ │ (testing)         ││   │
│  │ └──────────┘ └─────────────────┘ └──────────────────┘ └───────────────────┘│   │
│  └─────────────────────────────────────────────────────────────────────────────┘   │
│                                                                                      │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

---

#### 📈 Dependency Statistics

| Metric | Value |
|--------|-------|
| **Total Production Dependencies** | 37 packages |
| **Total Dev Dependencies** | 12 packages |
| **Crypto/Security Packages** | 10 packages |
| **Post-Quantum (PQC) Packages** | 3 packages |
| **ML/AI Packages** | 5 packages |
| **UI/Animation Packages** | 7 packages |
| **React Ecosystem Packages** | 5 packages |
| **Estimated Bundle Size (gzipped)** | ~450KB core + lazy-loaded |

---

### DevOps & Infrastructure

| Technology | Purpose |
|------------|---------|
| Docker | Containerization |
| Kubernetes | Orchestration |
| GitHub Actions | CI/CD pipeline |
| Nginx | Reverse proxy & load balancer |
| Gunicorn | WSGI server |
| Daphne | ASGI server (WebSockets) |
| Trivy | Security scanning |

### 📦 Complete Backend Dependencies (requirements.txt)

#### Core Django Framework

| Package | Version | Description |
|---------|---------|-------------|
| Django | 4.2.27 | High-level Python web framework (LTS) |
| djangorestframework | 3.16.1 | Powerful toolkit for building Web APIs |
| djangorestframework-simplejwt | 5.2.2 | JWT authentication for Django REST Framework |
| asgiref | 3.8.1 | ASGI specs, helper code, and adapters |

#### Django Extensions & Tools

| Package | Version | Description |
|---------|---------|-------------|
| django-extensions | 4.1 | Collection of custom extensions for Django |
| django-cors-headers | 4.0.0 | Django app for handling CORS headers |
| django-storages | 1.13.2 | Custom storage backends for Django |
| django-timezone-field | 7.1 | Timezone field for Django models |
| drf-yasg | 1.21.10 | Swagger/OpenAPI 2.0 documentation generator |

#### Authentication & OAuth 2.0 / OpenID Connect

| Package | Version | Description |
|---------|---------|-------------|
| django-allauth | 65.12.0 | Authentication, registration, account management |
| dj-rest-auth | 7.0.1 | REST API endpoints for authentication |
| python3-openid | 3.2.0 | Python 3 port of python-openid |
| oauthlib | 3.2.2 | OAuth request-signing logic |
| requests-oauthlib | 2.0.0 | OAuthlib integration with Requests |
| mozilla-django-oidc | 4.0.0+ | OpenID Connect authentication for Django |

#### Cryptography & Security

| Package | Version | Description |
|---------|---------|-------------|
| cryptography | 44.0.2 | Cryptographic primitives and recipes |
| argon2-cffi | 21.3.0 | Argon2 password hashing (winner of PHC) |
| argon2-cffi-bindings | 21.2.0 | Low-level bindings for Argon2 |
| pyOpenSSL | 25.0.0 | Python wrapper around OpenSSL |
| pycryptodome | 3.20.0+ | Self-contained cryptographic library |
| ecdsa | 0.19.1 | ECDSA signature implementation |
| pyotp | 2.9.0 | Python One-Time Password Library (TOTP/HOTP) |

#### JWT & Tokens

| Package | Version | Description |
|---------|---------|-------------|
| PyJWT | 2.10.1 | JSON Web Token implementation |
| python-jose | 3.4.0 | JavaScript Object Signing and Encryption (JOSE) |

#### Celery & Task Queue

| Package | Version | Description |
|---------|---------|-------------|
| celery | 5.5.1 | Distributed task queue |
| django-celery-beat | 2.8.0 | Database-backed periodic tasks |
| django-celery-results | 2.6.0 | Celery result backends for Django |
| amqp | 5.3.1 | AMQP client for Python |
| billiard | 4.2.1 | Python multiprocessing fork |
| kombu | 5.5.3 | Messaging library for Python |
| vine | 5.1.0 | Promise/callback chain implementation |
| redis | 5.2.1 | Python client for Redis |

#### Database

| Package | Version | Description |
|---------|---------|-------------|
| psycopg2-binary | 2.9.10 | PostgreSQL database adapter |
| sqlparse | 0.5.3 | SQL parser for Python |

#### HTTP & Networking

| Package | Version | Description |
|---------|---------|-------------|
| requests | 2.32.3 | HTTP library for Python |
| certifi | 2025.1.31 | Root certificates for SSL verification |
| charset-normalizer | 3.4.1 | Character encoding detection |
| idna | 3.10 | Internationalized Domain Names support |
| urllib3 | 1.26.20 | HTTP client for Python |
| dnspython | 2.7.0 | DNS toolkit for Python |

#### AWS & Cloud Storage

| Package | Version | Description |
|---------|---------|-------------|
| boto3 | 1.26.76 | AWS SDK for Python |
| botocore | 1.29.165 | Low-level AWS SDK interface |
| s3transfer | 0.6.2 | Amazon S3 transfer manager |
| jmespath | 1.0.1 | JSON Matching Expressions |
| google-cloud-storage | 2.5.0 | Google Cloud Storage client |

#### Firebase & Push Notifications

| Package | Version | Description |
|---------|---------|-------------|
| firebase-admin | 5.3.0 | Firebase Admin Python SDK |
| django-push-notifications | 3.0.0 | Push notifications for Django |
| pyfcm | 1.5.4 | Firebase Cloud Messaging client |

#### Django Channels & WebSockets

| Package | Version | Description |
|---------|---------|-------------|
| channels | 4.0.0+ | Async support for Django (WebSockets) |
| channels-redis | 4.1.0+ | Redis channel layer for Django Channels |
| daphne | 4.0.0+ | HTTP/WebSocket protocol server (ASGI) |

#### GeoIP & Device Detection

| Package | Version | Description |
|---------|---------|-------------|
| geoip2 | 4.7.0 | MaxMind GeoIP2 database reader |
| django-ipware | 4.0.2 | IP address detection for Django |
| user-agents | 2.2.0 | User agent string parser |

#### Machine Learning & Data Science

| Package | Version | Description |
|---------|---------|-------------|
| numpy | 1.24.0+ | Numerical computing library |
| pandas | 2.0.0+ | Data analysis library |
| scikit-learn | 1.3.0+ | Machine learning library |
| joblib | 1.3.0+ | Lightweight pipelining in Python |
| tensorflow | 2.13.0+ | Deep learning framework |
| torch | 2.1.0+ | PyTorch deep learning framework |
| transformers | 4.35.0+ | State-of-the-art NLP models |

#### Advanced Security Features

| Package | Version | Description |
|---------|---------|-------------|
| web3 | 7.0.0+ | Ethereum blockchain interaction |
| eth-account | 0.13.0+ | Ethereum account management |
| secretsharing | 0.2.6+ | Shamir's Secret Sharing implementation |
| liboqs-python | 0.10.0+ | Post-quantum cryptography (optional, Linux) |
| concrete-python | 2.5.0+ | Fully Homomorphic Encryption (optional) |
| tenseal | 0.3.14+ | Tensor operations on encrypted data (optional) |

#### Notifications & Communication

| Package | Version | Description |
|---------|---------|-------------|
| twilio | 8.0.0+ | Twilio API for SMS/Voice |
| sendgrid | 6.11.0+ | SendGrid email delivery |
| authy | 2.2.6 | Twilio Authy 2FA integration |

#### Production & Deployment

| Package | Version | Description |
|---------|---------|-------------|
| gunicorn | 21.2.0+ | Python WSGI HTTP server |
| uvicorn | 0.24.0+ | ASGI server with uvloop |
| whitenoise | 6.6.0+ | Static file serving |
| django-redis | 5.4.0+ | Redis cache backend for Django |
| hiredis | 2.3.2+ | High performance Redis client |
| sentry-sdk | 1.40.0+ | Error tracking and monitoring |
| psutil | 5.9.0+ | System monitoring utilities |

#### Security & Rate Limiting

| Package | Version | Description |
|---------|---------|-------------|
| django-ratelimit | 4.1.0+ | Rate limiting for Django views |
| django-defender | 0.9.7+ | Brute-force attack prevention |
| django-health-check | 3.18.0+ | Health check endpoints |
| safety | 2.3.0+ | Dependency vulnerability scanner |
| pip-audit | 2.6.0+ | Security auditing for pip packages |

---

## 📁 Project Structure

```
Password_manager/
├── 📁 .github/
│   └── 📁 workflows/
│       └── 📄 ci.yml                    # CI/CD pipeline configuration
├── 📁 contracts/                        # Solidity smart contracts
│   ├── 📁 contracts/
│   │   └── 📄 BehavioralCommitmentAnchor.sol
│   ├── 📁 scripts/                      # Deployment scripts
│   ├── 📁 test/                         # Contract tests
│   ├── 📄 hardhat.config.js             # Hardhat configuration
│   └── 📄 package.json
├── 📁 docker/                           # Docker configurations
│   ├── 📁 backend/
│   │   ├── 📄 Dockerfile                # Backend production image
│   │   └── 📄 entrypoint.sh             # Container entrypoint
│   ├── 📁 frontend/
│   │   ├── 📄 Dockerfile                # Frontend production image
│   │   ├── 📄 Dockerfile.dev            # Frontend development image
│   │   ├── 📄 nginx.conf                # Nginx config for frontend
│   │   └── 📄 entrypoint.sh             # Runtime config injection
│   ├── 📁 nginx/
│   │   └── 📄 nginx.conf                # Main reverse proxy config
│   ├── 📄 docker-compose.yml            # Production compose
│   ├── 📄 docker-compose.dev.yml        # Development compose
│   └── 📄 env.example                   # Environment template
├── 📁 k8s/                              # Kubernetes manifests
│   ├── 📄 namespace.yaml                # K8s namespace
│   ├── 📄 configmap.yaml                # Application config
│   ├── 📄 secrets.yaml                  # Sensitive credentials
│   ├── 📄 deployment.yaml               # All deployments
│   ├── 📄 ingress.yaml                  # Ingress with SSL
│   └── 📄 hpa.yaml                      # Horizontal pod autoscaler
├── 📁 desktop/                          # Electron desktop app
│   ├── 📄 main.js                       # Electron main process
│   ├── 📁 src/                          # Desktop source code
│   └── 📄 package.json
├── 📁 mobile/                           # React Native mobile app
│   ├── 📄 App.js                        # Mobile entry point
│   ├── 📁 src/                          # Mobile source code
│   └── 📄 package.json
├── 📁 browser-extension/                # Browser extension
│   ├── 📄 manifest.json                 # Extension manifest
│   ├── 📁 src/                          # Extension source code
│   └── 📄 package.json
├── 📁 frontend/                         # React web application
│   ├── 📁 src/
│   │   ├── 📁 Components/               # React components
│   │   │   ├── 📁 auth/                 # Authentication components
│   │   │   ├── 📁 animations/           # UI animations
│   │   │   ├── 📁 recovery/             # Recovery flow components
│   │   │   └── 📁 sharedfolders/        # Shared folders UI
│   │   ├── 📁 services/                 # Frontend services
│   │   │   ├── 📄 api.js                # API client
│   │   │   ├── 📄 cryptoService.js      # Client-side encryption
│   │   │   ├── 📄 xchachaEncryption.js  # XChaCha20 encryption
│   │   │   ├── 📄 eccService.js         # ECC operations
│   │   │   ├── 📄 oauthService.js       # OAuth social login
│   │   │   ├── 📄 oidcService.js        # OpenID Connect (OIDC) ⭐ NEW
│   │   │   ├── 📄 mfaService.js         # Multi-factor authentication
│   │   │   ├── 📁 quantum/              # Post-quantum crypto
│   │   │   │   └── 📄 kyberService.js   # Kyber-768 implementation
│   │   │   ├── 📁 fhe/                  # Fully Homomorphic Encryption
│   │   │   │   ├── 📄 fheService.js     # FHE client service (WASM)
│   │   │   │   ├── 📄 fheKeys.js        # FHE key management (IndexedDB)
│   │   │   │   └── 📄 index.js          # FHE module exports
│   │   │   ├── 📁 behavioralCapture/    # Behavioral biometrics
│   │   │   └── 📁 blockchain/           # Web3 integration
│   │   ├── 📁 ml/                       # Client-side ML
│   │   │   └── 📁 behavioralDNA/        # Behavioral DNA models
│   │   ├── 📁 contexts/                 # React contexts
│   │   ├── 📁 hooks/                    # Custom hooks
│   │   └── 📁 utils/                    # Utility functions
│   ├── 📄 vite.config.js                # Vite configuration
│   └── 📄 package.json
├── 📁 password_manager/                 # Django backend
│   ├── 📁 password_manager/             # Django project settings
│   │   ├── 📄 settings.py               # Main settings
│   │   ├── 📄 urls.py                   # Root URL config
│   │   ├── 📄 asgi.py                   # ASGI config
│   │   ├── 📄 wsgi.py                   # WSGI config
│   │   └── 📄 throttling.py             # Rate limiting
│   ├── 📁 api/                          # API app
│   │   ├── 📄 health.py                 # Health check endpoints
│   │   └── 📄 urls.py                   # API URL routing
│   ├── 📁 auth_module/                  # Authentication
│   │   ├── 📄 views.py                  # Auth views
│   │   ├── 📄 passkey_views.py          # WebAuthn endpoints
│   │   ├── 📄 oauth_views.py            # OAuth endpoints
│   │   ├── 📄 oidc_views.py             # OpenID Connect (OIDC) endpoints ⭐ NEW
│   │   ├── 📄 mfa_views.py              # MFA endpoints
│   │   ├── 📄 kyber_views.py            # Post-quantum crypto endpoints
│   │   ├── 📄 passkey_primary_recovery_views.py  # Primary recovery
│   │   ├── 📄 quantum_recovery_views.py # Quantum recovery
│   │   └── 📁 services/                 # Auth services
│   │       ├── 📄 oidc_service.py       # OIDC service (discovery, JWKS) ⭐ NEW
│   │       ├── 📄 quantum_crypto_service.py
│   │       ├── 📄 kyber_crypto.py
│   │       ├── 📄 kyber_cache.py        # Kyber key caching
│   │       ├── 📄 kyber_monitor.py      # Kyber performance monitoring
│   │       └── 📄 passkey_primary_recovery_service.py
│   ├── 📁 vault/                        # Vault management
│   │   ├── 📁 views/                    # Vault views
│   │   └── 📄 urls.py                   # Vault URLs
│   ├── 📁 security/                     # Security features
│   │   ├── 📄 views.py                  # Security endpoints
│   │   └── 📁 api/                      # Security APIs
│   ├── 📁 ml_security/                  # ML security models
│   │   ├── 📄 views.py                  # ML endpoints
│   │   └── 📁 ml_models/                # Trained models
│   ├── 📁 ml_dark_web/                  # Dark web monitoring
│   │   ├── 📁 ml_services.py            # ML services
│   │   └── 📄 routing.py                # WebSocket routing
│   ├── 📁 behavioral_recovery/          # Behavioral recovery
│   │   ├── 📄 views.py                  # Recovery endpoints
│   │   ├── 📄 models.py                 # Recovery models
│   │   └── 📁 services/                 # Recovery services
│   ├── 📁 blockchain/                   # Blockchain integration
│   │   ├── 📄 views.py                  # Blockchain endpoints
│   │   └── 📁 services/                 # Blockchain services
│   ├── 📁 fhe_service/                  # FHE (Fully Homomorphic Encryption)
│   │   ├── 📄 views.py                  # FHE API endpoints
│   │   ├── 📄 models.py                 # FHE models (cache, keystore, logs)
│   │   ├── 📄 urls.py                   # FHE URL routing
│   │   └── 📁 services/                 # FHE services
│   │       ├── 📄 concrete_service.py   # Concrete-Python operations
│   │       ├── 📄 seal_service.py       # TenSEAL batch operations
│   │       ├── 📄 fhe_router.py         # Intelligent operation routing
│   │       ├── 📄 fhe_cache.py          # Redis computation cache
│   │       └── 📄 adaptive_manager.py   # Circuit depth management
│   ├── 📁 shared/                       # Shared utilities
│   │   ├── 📄 performance_views.py      # Performance monitoring
│   │   └── 📁 crypto/                   # Server crypto utilities
│   ├── 📁 analytics/                    # Analytics
│   ├── 📁 ab_testing/                   # A/B testing
│   ├── 📁 email_masking/                # Email alias service
│   └── 📄 requirements.txt              # Python dependencies
├── 📁 tests/                            # Test suite
│   ├── 📁 behavioral_recovery/
│   ├── 📁 functional/
│   └── 📄 run_all_tests.py
├── 📁 scripts/                          # Utility scripts
├── 📁 docs/                             # Documentation
└── 📄 README.md                         # This file
```

---

## 📂 Detailed Project Files Structure

### Complete Backend Structure (`password_manager/`)

```
password_manager/
├── 📁 password_manager/                    # Django Project Settings
│   ├── 📄 settings.py                      # Main settings (965 lines)
│   │   ├── DATABASES                       # PostgreSQL configuration
│   │   ├── CACHES                          # Redis cache backend
│   │   ├── CELERY_*                        # Celery configuration
│   │   ├── REST_FRAMEWORK                  # DRF settings
│   │   ├── SIMPLE_JWT                      # JWT token settings
│   │   ├── CORS_*                          # CORS configuration
│   │   └── CHANNEL_LAYERS                  # Django Channels config
│   ├── 📄 urls.py                          # Root URL routing (113 lines)
│   ├── 📄 asgi.py                          # ASGI config for WebSockets
│   ├── 📄 wsgi.py                          # WSGI config for Gunicorn
│   ├── 📄 compression_middleware.py        # Gzip/Brotli compression (320 lines)
│   │   ├── VaultCompressionMiddleware      # Response compression
│   │   ├── SecurityHeadersMiddleware       # CSP, HSTS headers
│   │   └── CacheControlMiddleware          # Cache headers
│   ├── 📄 throttling.py                    # Rate limiting (154 lines)
│   └── 📄 api_utils.py                     # API response utilities
│
├── 📁 auth_module/                         # Authentication Module
│   ├── 📄 views.py                         # Core auth endpoints (1403 lines)
│   │   ├── RegisterView                    # User registration
│   │   ├── LoginView                       # User login
│   │   └── LogoutView                      # User logout
│   ├── 📄 passkey_views.py                 # WebAuthn/FIDO2 (587 lines)
│   │   ├── PasskeyRegistrationView         # Register passkey
│   │   ├── PasskeyAuthenticationView       # Authenticate with passkey
│   │   └── PasskeyListView                 # List user's passkeys
│   ├── 📄 mfa_views.py                     # Multi-factor auth (790 lines)
│   │   ├── TOTPSetupView                   # TOTP setup
│   │   ├── BiometricSetupView              # Biometric enrollment
│   │   └── MFAVerifyView                   # Verify MFA code
│   ├── 📄 oauth_views.py                   # OAuth 2.0 (427 lines)
│   │   ├── GoogleOAuthView                 # Google login
│   │   ├── GitHubOAuthView                 # GitHub login
│   │   └── AppleOAuthView                  # Apple login
│   ├── 📄 kyber_views.py                   # Kyber API (async views)
│   │   ├── generate_keypair                # Async keypair generation
│   │   ├── encrypt_password                # Hybrid encryption
│   │   ├── decrypt_password                # Hybrid decryption
│   │   ├── batch_encrypt                   # Batch operations
│   │   └── get_kyber_metrics               # Performance metrics
│   ├── 📄 passkey_primary_recovery_views.py # Primary recovery (637 lines)
│   ├── 📄 quantum_recovery_views.py        # Social mesh recovery (1104 lines)
│   ├── 📄 models.py                        # Auth models (540 lines)
│   │   ├── KyberKeyPair                    # Kyber-768 keypairs
│   │   ├── KyberEncryptedPassword          # Kyber-encrypted data
│   │   ├── KyberSession                    # Session shared secrets
│   │   ├── TwoFactorAuth                   # 2FA settings
│   │   ├── UserSalt                        # User's key derivation salt
│   │   ├── UserPasskey                     # WebAuthn credentials
│   │   ├── RecoveryKey                     # Recovery key backup
│   │   └── PushAuth                        # Push notification auth
│   └── 📁 services/                        # Auth services
│       ├── 📄 kyber_crypto.py              # Kyber-768 implementation
│       ├── 📄 optimized_ntt.py             # NumPy-optimized NTT
│       │   ├── OptimizedNTT                # Main NTT class
│       │   ├── forward_ntt()               # Forward transform
│       │   ├── inverse_ntt()               # Inverse transform
│       │   └── multiply_ntt()              # Pointwise multiply
│       ├── 📄 parallel_kyber.py            # Parallel operations
│       │   └── ParallelKyberOperations     # ThreadPoolExecutor batch ops
│       ├── 📄 kyber_cache.py               # Hybrid caching (959 lines)
│       │   ├── L1: Memory (LRU)            # Hot keys
│       │   ├── L2: Redis                   # Distributed cache
│       │   └── L3: Database                # Persistent storage
│       ├── 📄 kyber_monitor.py             # Performance monitoring
│       ├── 📄 quantum_crypto_service.py    # PQC service
│       ├── 📄 passkey_primary_recovery_service.py
│       ├── 📄 challenge_generator.py       # Temporal challenges
│       └── 📄 trust_scorer.py              # Trust scoring algorithm
│
├── 📁 vault/                               # Vault Management
│   ├── 📁 views/
│   │   ├── 📄 crud_views.py                # Basic CRUD operations
│   │   ├── 📄 api_views.py                 # Enhanced API (309 lines)
│   │   │   ├── get_salt                    # User salt for KDF
│   │   │   ├── verify_auth                 # Zero-knowledge auth
│   │   │   └── statistics                  # Cached vault stats
│   │   ├── 📄 backup_views.py              # Backup/restore
│   │   ├── 📄 folder_views.py              # Folder management
│   │   └── 📄 shared_folder_views.py       # Shared folders (RBAC)
│   ├── 📁 models/
│   │   ├── 📄 vault_models.py              # EncryptedVaultItem
│   │   └── 📄 folder_models.py             # VaultFolder
│   ├── 📁 services/
│   │   ├── 📄 vault_optimization_service.py # Optimization (483 lines)
│   │   │   ├── VaultCacheManager           # Multi-level caching
│   │   │   ├── VaultQueryOptimizer         # Query optimization
│   │   │   ├── VaultCompression            # Gzip utilities
│   │   │   └── AuthHashService             # Zero-knowledge auth
│   │   └── 📄 __init__.py
│   └── 📄 tasks.py                         # Celery tasks (471 lines)
│       ├── process_audit_log               # Async audit logging
│       ├── warm_user_cache                 # Cache warming
│       ├── cleanup_deleted_items           # Purge soft-deleted
│       ├── check_breach_status             # HIBP API check
│       └── prepare_export                  # Encrypted export
│
├── 📁 fhe_service/                         # Fully Homomorphic Encryption
│   ├── 📄 views.py                         # FHE endpoints (663 lines)
│   │   ├── fhe_encrypt                     # Encrypt with FHE
│   │   ├── fhe_strength_check              # Password strength
│   │   ├── fhe_batch_strength              # Batch evaluation
│   │   └── fhe_search                      # Encrypted search
│   ├── 📄 models.py                        # FHE models (287 lines)
│   │   ├── FHEKeyStore                     # User FHE keys
│   │   ├── FHEComputationCacheModel        # Computation cache
│   │   ├── FHEOperationLog                 # Audit log
│   │   └── FHEMetrics                      # Aggregated metrics
│   └── 📁 services/
│       ├── 📄 concrete_service.py          # Concrete-Python ops
│       ├── 📄 seal_service.py              # TenSEAL SEAL ops
│       ├── 📄 fhe_router.py                # Tier routing
│       ├── 📄 fhe_cache.py                 # Redis cache
│       └── 📄 adaptive_manager.py          # Depth management
│
├── 📁 behavioral_recovery/                 # Behavioral Recovery System
│   ├── 📄 views.py                         # Recovery endpoints (726 lines)
│   ├── 📄 models.py                        # Recovery models (587 lines)
│   │   ├── BehavioralCommitment            # 247-dim DNA storage
│   │   ├── BehavioralRecoveryAttempt       # Recovery attempts
│   │   ├── BehavioralChallenge             # Individual challenges
│   │   ├── BehavioralProfileSnapshot       # Periodic snapshots
│   │   ├── RecoveryFeedback                # User feedback (Phase 2B.2)
│   │   └── RecoveryPerformanceMetric       # Performance metrics
│   ├── 📄 tasks.py                         # Celery tasks
│   └── 📁 services/
│       ├── 📄 recovery_orchestrator.py     # Flow orchestration
│       ├── 📄 behavioral_analyzer.py       # DNA analysis
│       └── 📄 guardian_service.py          # Guardian mesh
│
├── 📁 blockchain/                          # Blockchain Anchoring
│   ├── 📄 views.py                         # Blockchain endpoints (390 lines)
│   ├── 📄 models.py                        # Anchor models
│   └── 📁 services/
│       ├── 📄 blockchain_anchor_service.py # Web3.py + Merkle trees
│       ├── 📄 merkle_tree.py               # Merkle tree implementation
│       └── 📄 commitment_hasher.py         # SHA-256 hashing
│
├── 📁 ml_security/                         # Machine Learning Security
│   ├── 📄 views.py                         # ML endpoints
│   └── 📁 ml_models/
│       ├── 📄 password_strength_model.py   # LSTM password strength
│       ├── 📄 anomaly_detector.py          # Isolation Forest
│       ├── 📄 threat_analyzer.py           # CNN-LSTM threat analysis
│       └── 📄 behavioral_model.py          # Behavioral profiling
│
├── 📁 ml_dark_web/                         # Dark Web Monitoring
│   ├── 📄 ml_services.py                   # BERT breach detection
│   ├── 📄 consumers.py                     # WebSocket consumers
│   └── 📄 routing.py                       # WebSocket routing
│
├── 📁 security/                            # Security Features
│   ├── 📄 views.py                         # Security endpoints
│   ├── 📄 models.py                        # Security models (207 lines)
│   │   ├── UserDevice                      # Device tracking
│   │   ├── SocialMediaAccount              # Social account protection
│   │   ├── LoginAttempt                    # Login tracking
│   │   ├── SecurityAlert                   # Alert system
│   │   ├── UserNotificationSettings        # Notification prefs
│   │   └── AccountLockEvent                # Lock/unlock events
│   └── 📁 services/
│       ├── 📄 breach_monitor.py            # Breach monitoring
│       └── 📄 device_trust.py              # Device trust scoring
│
└── 📄 requirements.txt                     # 119 Python packages
```

### Complete Frontend Structure (`frontend/src/`)

```
frontend/src/
├── 📄 App.jsx                              # Main React app (1149 lines)
├── 📄 App.css                              # Global styles (638 lines)
├── 📄 main.jsx                             # React entry point
│
├── 📁 services/                            # Frontend Services
│   ├── 📄 api.js                           # API client (209 lines)
│   ├── 📄 cryptoService.js                 # AES-GCM encryption (454 lines)
│   ├── 📄 secureVaultCrypto.js             # WebCrypto API (717 lines) ⭐
│   │   ├── deriveKeyFromPassword()         # Argon2id KDF
│   │   ├── encrypt()                       # AES-256-GCM encrypt
│   │   ├── decrypt()                       # AES-256-GCM decrypt
│   │   ├── generatePassword()              # Secure random generator
│   │   └── clearMemory()                   # Secure memory wipe
│   ├── 📄 secureVaultService.js            # Zero-knowledge ops (709 lines) ⭐
│   │   ├── initialize()                    # Init with master password
│   │   ├── fetchAndDecryptItems()          # Fetch + decrypt
│   │   ├── encryptAndSave()                # Encrypt + save
│   │   └── verifyMasterPassword()          # Zero-knowledge verify
│   ├── 📄 xchachaEncryption.js             # XChaCha20-Poly1305 (413 lines)
│   ├── 📄 eccService.js                    # ECC operations (367 lines)
│   ├── 📁 quantum/
│   │   ├── 📄 kyberService.js              # Kyber-768 + X25519 (1232 lines)
│   │   │   ├── generateKeypair()           # Hybrid keypair gen
│   │   │   ├── hybridEncapsulate()         # KEM + DH
│   │   │   └── hybridDecapsulate()         # Decapsulation
│   │   └── 📄 index.js                     # Quantum exports
│   ├── 📁 fhe/
│   │   ├── 📄 fheService.js                # TFHE WASM client (681 lines)
│   │   │   ├── initialize()                # Load WASM module
│   │   │   ├── generateKeys()              # FHE keypair gen
│   │   │   ├── encryptPassword()           # FHE encrypt
│   │   │   └── checkStrength()             # Encrypted strength
│   │   ├── 📄 fheKeys.js                   # IndexedDB key storage (604 lines)
│   │   └── 📄 index.js
│   ├── 📁 behavioralCapture/
│   │   ├── 📄 BehavioralCaptureEngine.js   # 247-dim capture
│   │   ├── 📄 KeystrokeDynamics.js         # Typing patterns
│   │   ├── 📄 MouseBiometrics.js           # Mouse patterns
│   │   └── 📄 CognitivePatterns.js         # Cognitive analysis
│   ├── 📁 blockchain/
│   │   ├── 📄 web3Service.js               # Web3 integration
│   │   └── 📄 contractABI.json             # Smart contract ABI
│   ├── 📄 vaultService.js                  # Vault operations (438 lines)
│   ├── 📄 mfaService.js                    # MFA client (583 lines)
│   ├── 📄 oauthService.js                  # OAuth client (235 lines)
│   ├── 📄 mlSecurityService.js             # ML security (369 lines)
│   ├── 📄 darkWebService.js                # Dark web monitoring (115 lines)
│   ├── 📄 analyticsService.js              # Analytics (734 lines)
│   ├── 📄 preferencesService.js            # User preferences (809 lines)
│   ├── 📄 performanceMonitor.js            # Performance tracking (528 lines)
│   └── 📄 SecureBehavioralStorage.js       # Encrypted IndexedDB (373 lines)
│
├── 📁 hooks/                               # React Hooks
│   ├── 📄 useAuth.jsx                      # Authentication hook
│   ├── 📄 useSecureVault.js                # Vault operations (466 lines) ⭐
│   │   ├── initialize()                    # Init vault
│   │   ├── fetchItems()                    # Fetch + decrypt
│   │   ├── saveItem()                      # Encrypt + save
│   │   └── deleteItem()                    # Soft delete
│   ├── 📄 useKyber.js                      # Kyber WASM/Worker
│   ├── 📄 useBehavioralRecovery.js         # Recovery hook
│   ├── 📄 useBiometricReauth.js            # Biometric re-auth
│   ├── 📄 useBreachWebSocket.js            # Breach alerts
│   └── 📄 useSecureSession.js              # Session management
│
├── 📁 contexts/                            # React Contexts
│   ├── 📄 AuthContext.jsx                  # Authentication state
│   ├── 📄 VaultContext.jsx                 # Vault state
│   ├── 📄 BehavioralContext.jsx            # Behavioral profile
│   └── 📄 AccessibilityContext.jsx         # A11y settings
│
├── 📁 Components/
│   ├── 📁 auth/                            # Auth Components
│   │   ├── 📄 Login.jsx                    # Login form (174 lines)
│   │   ├── 📄 PasskeyAuth.jsx              # Passkey auth (308 lines)
│   │   ├── 📄 PasskeyRegistration.jsx      # Passkey setup (179 lines)
│   │   ├── 📄 BiometricAuth.jsx            # Biometric auth (413 lines)
│   │   ├── 📄 BiometricSetup.jsx           # Biometric enrollment (437 lines)
│   │   ├── 📄 TwoFactorSetup.jsx           # 2FA config (417 lines)
│   │   ├── 📄 RecoveryKeySetup.jsx         # Recovery key (434 lines)
│   │   ├── 📄 PasswordRecovery.jsx         # Password recovery (636 lines)
│   │   ├── 📄 PasskeyPrimaryRecoverySetup.jsx # Primary recovery (451 lines)
│   │   ├── 📄 PasskeyPrimaryRecoveryInitiate.jsx # Recovery start (517 lines)
│   │   ├── 📄 QuantumRecoverySetup.jsx     # Quantum recovery UI (696 lines)
│   │   ├── 📄 OAuthCallback.jsx            # OAuth callback (334 lines)
│   │   └── 📄 SocialLoginButtons.jsx       # Social login (98 lines)
│   │
│   ├── 📁 vault/                           # Vault Components
│   │   ├── 📄 VaultList.jsx                # Item list
│   │   ├── 📄 VaultItem.jsx                # Item display
│   │   ├── 📄 VaultItemDetail.jsx          # Item detail
│   │   └── 📄 VaultSearch.jsx              # Search functionality
│   │
│   ├── 📁 security/                        # Security Components
│   │   ├── 📄 PasswordGenerator.jsx        # Password generator
│   │   ├── 📄 PasswordStrengthMeter.jsx    # Strength meter
│   │   ├── 📄 PasswordStrengthMeterML.jsx  # ML-powered strength
│   │   ├── 📄 SessionMonitor.jsx           # Session monitoring
│   │   ├── 📄 AccountProtection.jsx        # Account protection
│   │   └── 📄 BiometricReauth.jsx          # Re-authentication
│   │
│   ├── 📁 sharedfolders/                   # Shared Folders
│   │   ├── 📄 SharedFoldersDashboard.jsx   # Dashboard (376 lines)
│   │   ├── 📄 CreateFolderModal.jsx        # Create folder (368 lines)
│   │   ├── 📄 FolderDetailsModal.jsx       # Folder details (590 lines)
│   │   └── 📄 InvitationsModal.jsx         # Invitations (427 lines)
│   │
│   ├── 📁 recovery/                        # Recovery Components
│   │   ├── 📁 behavioral/
│   │   │   ├── 📄 BehavioralRecoveryFlow.jsx
│   │   │   └── 📄 ChallengeDisplay.jsx
│   │   └── 📁 social/
│   │       └── 📄 SocialMeshRecovery.jsx
│   │
│   ├── 📁 admin/                           # Admin Components
│   │   ├── 📄 RecoveryDashboard.jsx        # Recovery admin
│   │   └── 📄 PerformanceMonitoring.jsx    # Performance admin
│   │
│   └── 📁 common/                          # Common Components
│       ├── 📄 Button.jsx
│       ├── 📄 Modal.jsx
│       ├── 📄 Input.jsx
│       ├── 📄 LoadingIndicator.jsx
│       └── 📄 ErrorBoundary.jsx
│
├── 📁 ml/                                  # Client-side ML
│   └── 📁 behavioralDNA/
│       ├── 📄 index.js                     # ML exports
│       ├── 📄 HybridModel.js               # Client/server switcher
│       ├── 📄 TransformerModel.js          # Behavioral transformer
│       └── 📄 BackendAPI.js                # Backend ML API client
│
├── 📁 utils/                               # Utilities
│   ├── 📄 kyber-wasm-loader.js             # Kyber WASM loader
│   ├── 📄 kyber-cache.js                   # IndexedDB cache
│   ├── 📄 deviceFingerprint.js             # Device fingerprinting
│   ├── 📄 errorHandler.js                  # Error handling
│   ├── 📄 NetworkQualityEstimator.js       # Network quality
│   └── 📄 OfflineQueueManager.js           # Offline queue
│
└── 📁 workers/                             # Web Workers
    └── 📄 kyber-worker.js                  # Background Kyber ops
```

### Docker & DevOps Structure

```
docker/
├── 📄 docker-compose.yml                   # Production compose (362 lines)
│   ├── backend                             # Django + Gunicorn
│   ├── frontend                            # Nginx + React
│   ├── postgres                            # PostgreSQL 15
│   ├── redis                               # Redis 7
│   ├── celery-worker                       # Celery workers
│   ├── celery-beat                         # Celery scheduler
│   └── daphne                              # WebSocket server
├── 📄 docker-compose.dev.yml               # Development compose
├── 📄 env.example                          # Environment template
├── 📁 backend/
│   ├── 📄 Dockerfile                       # Multi-stage build
│   └── 📄 entrypoint.sh                    # Migrations + startup
├── 📁 frontend/
│   ├── 📄 Dockerfile                       # Production build
│   ├── 📄 Dockerfile.dev                   # Development build
│   ├── 📄 nginx.conf                       # Nginx configuration
│   └── 📄 entrypoint.sh                    # Runtime env injection
└── 📁 nginx/
    └── 📄 nginx.conf                       # Reverse proxy config

k8s/
├── 📄 namespace.yaml                       # password-manager namespace
├── 📄 configmap.yaml                       # Application config
├── 📄 secrets.yaml                         # Sensitive credentials
├── 📄 deployment.yaml                      # All deployments (697 lines)
│   ├── backend-deployment                  # Django (replicas: 4)
│   ├── frontend-deployment                 # Nginx (replicas: 3)
│   ├── celery-worker-deployment            # Workers (replicas: 2)
│   ├── celery-beat-deployment              # Scheduler (replicas: 1)
│   └── daphne-deployment                   # WebSocket (replicas: 2)
├── 📄 ingress.yaml                         # nginx-ingress + SSL
└── 📄 hpa.yaml                             # Horizontal pod autoscalers

.github/workflows/
└── 📄 ci.yml                               # CI/CD pipeline (536 lines)
    ├── test                                # pytest + vitest
    ├── lint                                # flake8 + ESLint
    ├── security                            # bandit + safety + Trivy
    ├── build                               # Docker multi-arch
    ├── deploy-staging                      # Auto on develop
    └── deploy-production                   # Manual approval
```

---

## 🚀 Quick Start

### Prerequisites

- Python 3.13+
- Node.js 20+
- PostgreSQL 15+
- Redis 7+
- Docker & Docker Compose (optional)

### Option 1: Docker Compose (Recommended)

```bash
# Clone repository
git clone https://github.com/yourusername/Password_manager.git
cd Password_manager

# Copy environment file
cp docker/env.example docker/.env

# Edit .env with your settings
nano docker/.env

# Start all services
cd docker
docker-compose up -d

# Access the application
# Frontend: http://localhost:3000
# Backend API: http://localhost:8000
# API Docs: http://localhost:8000/docs/
```

### Option 2: Manual Setup

```bash
# Backend Setup
cd password_manager
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt

# Create .env file (IMPORTANT!)
cp env.example .env
# Edit .env and ensure DEBUG=True for development

python manage.py migrate
python manage.py runserver 8000

# Frontend Setup (new terminal)
cd frontend
npm install
npm run dev

# Access at http://localhost:5173
```

### ⚠️ Important Development Notes

| Setting | Development | Production |
|---------|-------------|------------|
| `DEBUG` | `True` | `False` |
| Rate Limiting (auth) | 30/minute | 3/minute |
| HTTPS Redirect | Disabled | Enabled |
| Error Details | Shown | Hidden |

**Common Issues & Solutions:**

1. **HTTPS Redirect Loops / SSL Errors**
   - Ensure `DEBUG=True` in `password_manager/.env`
   - This disables `SECURE_SSL_REDIRECT` which causes issues in development

2. **HTTP 429 Too Many Requests**
   - Rate limiting is automatically lenient in `DEBUG` mode
   - If hitting limits, restart the backend server

3. **WebSocket / ASGI Errors**
   - Use `python manage.py runserver` (WSGI) for development
   - Daphne (ASGI) is only needed for WebSocket features in production

4. **Login Form Not Submitting**
   - Clear browser cache and localStorage
   - Ensure both email and password fields are filled

### Test User Setup

```bash
# Create a test user for development
cd password_manager
python manage.py shell -c "
from django.contrib.auth.models import User
from auth_module.models import UserSalt
import os
u, _ = User.objects.get_or_create(username='testuser@gmail.com', defaults={'email': 'testuser@gmail.com'})
u.set_password('TestPass123!')
u.save()
if not UserSalt.objects.filter(user=u).exists():
    UserSalt.objects.create(user=u, salt=os.urandom(32), auth_hash=os.urandom(64))
print('Test user created: testuser@gmail.com / TestPass123!')
"
```

---

## 🔐 Encryption & Decryption Mechanisms

### Zero-Knowledge Architecture

SecureVault implements a **strict zero-knowledge architecture** where:

1. **All encryption/decryption happens client-side**
2. **Server never receives plaintext data or encryption keys**
3. **Master password never leaves the client**
4. **Only encrypted blobs are transmitted and stored**

### Encryption Flow Diagram

```mermaid
sequenceDiagram
    participant U as User
    participant C as Client (Browser)
    participant S as Server
    participant DB as Database

    U->>C: Enter password + data
    
    Note over C: Key Derivation
    C->>C: Argon2id(password, salt)
    C->>C: Generate 256-bit key
    
    Note over C: Encryption
    C->>C: Generate random IV (12 bytes)
    C->>C: AES-GCM-256 encrypt(data, key, iv)
    C->>C: Generate auth tag (128-bit)
    
    Note over C: Package encrypted data
    C->>C: {ciphertext, iv, tag, salt}
    
    C->>S: HTTPS POST encrypted blob
    S->>DB: Store encrypted blob
    DB->>S: OK
    S->>C: Success response
    C->>U: Confirmation
    
    Note over S: Server NEVER sees plaintext!
```

### Complete Encryption & Decryption Mechanisms

SecureVault implements a **multi-layer encryption architecture** with various algorithms for different security requirements:

```
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                          ENCRYPTION ALGORITHM HIERARCHY                                  │
├─────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                          │
│   Layer 1: Primary Vault Encryption                                                     │
│   ┌─────────────────────────────────────────────────────────────────────────────────┐  │
│   │  AES-256-GCM + Argon2id KDF                                                      │  │
│   │  • 256-bit key derived from master password                                      │  │
│   │  • 96-bit random nonce (IV) per encryption                                       │  │
│   │  • 128-bit authentication tag (integrity verification)                           │  │
│   │  • Compression: Gzip for data > 1KB                                              │  │
│   └─────────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                          │
│   Layer 2: Alternative Symmetric Encryption                                             │
│   ┌─────────────────────────────────────────────────────────────────────────────────┐  │
│   │  XChaCha20-Poly1305 AEAD                                                         │  │
│   │  • 256-bit key                                                                   │  │
│   │  • 192-bit extended nonce (safer for random generation)                          │  │
│   │  • 128-bit Poly1305 MAC                                                          │  │
│   │  • Used for: File encryption, large data, stream ciphers                         │  │
│   └─────────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                          │
│   Layer 3: Post-Quantum Key Encapsulation                                               │
│   ┌─────────────────────────────────────────────────────────────────────────────────┐  │
│   │  CRYSTALS-Kyber-768 (NIST Level 3) + X25519 Hybrid                               │  │
│   │  • Kyber: 1184-byte public key, 2400-byte private key                            │  │
│   │  • X25519: 32-byte keys (defense-in-depth)                                       │  │
│   │  • Combined 64-byte shared secret                                                │  │
│   │  • Quantum-resistant + classical security                                        │  │
│   └─────────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                          │
│   Layer 4: Elliptic Curve Cryptography (Key Exchange)                                   │
│   ┌─────────────────────────────────────────────────────────────────────────────────┐  │
│   │  Hybrid ECC: Curve25519 + P-384                                                  │  │
│   │  • Curve25519 (X25519): 32-byte keys, constant-time                              │  │
│   │  • P-384 (secp384r1): 48-byte keys, NIST approved                                │  │
│   │  • HKDF-SHA256 for key derivation                                                │  │
│   └─────────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                          │
│   Layer 5: Fully Homomorphic Encryption (Server-side Computation)                       │
│   ┌─────────────────────────────────────────────────────────────────────────────────┐  │
│   │  TFHE (WASM) / Concrete-Python / TenSEAL                                         │  │
│   │  • 2048-bit keys, 8192 polynomial degree                                         │  │
│   │  • 128-bit security level                                                        │  │
│   │  • Used for: Password strength check, encrypted search                           │  │
│   └─────────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                          │
└─────────────────────────────────────────────────────────────────────────────────────────┘
```

---

#### 1. AES-256-GCM (Primary Vault Encryption)

| Parameter | Value | Description |
|-----------|-------|-------------|
| **Algorithm** | AES-256-GCM | Galois/Counter Mode with 256-bit key |
| **Key Size** | 256 bits (32 bytes) | Maximum AES key length |
| **Nonce/IV** | 96 bits (12 bytes) | Random per encryption |
| **Auth Tag** | 128 bits (16 bytes) | Integrity verification |
| **Block Size** | 128 bits | Standard AES block |
| **KDF** | Argon2id | Memory-hard key derivation |

```javascript
// Frontend: secureVaultCrypto.js - AES-256-GCM Encryption
async encrypt(data, options = {}) {
  const { compress = true, additionalData = null } = options;

  // Convert data to bytes
  let dataToEncrypt = typeof data === 'string' ? data : JSON.stringify(data);

  // Optional compression for large data (>1KB)
  if (compress && dataToEncrypt.length > 1024) {
    const compressed = await this._compress(dataToEncrypt);
    if (compressed.length < dataToEncrypt.length * 0.9) {
      dataToEncrypt = compressed;
    }
  }

  const encoder = new TextEncoder();
  const plaintextBytes = encoder.encode(dataToEncrypt);

  // Generate random 12-byte nonce (96 bits for AES-GCM)
  const nonce = window.crypto.getRandomValues(new Uint8Array(12));

  // Prepare Additional Authenticated Data (AAD) if provided
  const aadBytes = additionalData 
    ? encoder.encode(JSON.stringify(additionalData))
    : undefined;

  // Encrypt with AES-256-GCM using WebCrypto API
  const encryptedBuffer = await window.crypto.subtle.encrypt(
    {
      name: 'AES-GCM',
      iv: nonce,
      tagLength: 128,       // 128-bit authentication tag
      additionalData: aadBytes
    },
    this.encryptionKey,     // 256-bit key derived from Argon2id
    plaintextBytes
  );

  // Return encrypted package
  return {
    v: '2.0',                               // Encryption version
    alg: 'AES-256-GCM-ARGON2ID',           // Algorithm identifier
    nonce: this._bytesToBase64(nonce),      // Base64-encoded nonce
    ct: this._bytesToBase64(new Uint8Array(encryptedBuffer)),  // Ciphertext
    compressed: compress && dataToEncrypt.length > 1024,
    ts: Date.now()                          // Timestamp
  };
}
```

```javascript
// Frontend: secureVaultCrypto.js - AES-256-GCM Decryption
async decrypt(encryptedPackage, options = {}) {
  const { additionalData = null } = options;

  // Handle legacy format
  if (typeof encryptedPackage === 'string') {
    encryptedPackage = JSON.parse(encryptedPackage);
  }

  // Extract nonce and ciphertext
  const nonce = this._base64ToBytes(encryptedPackage.nonce);
  const ciphertext = this._base64ToBytes(encryptedPackage.ct);

  // Prepare AAD if required
  const encoder = new TextEncoder();
  const aadBytes = additionalData 
    ? encoder.encode(JSON.stringify(additionalData))
    : undefined;

  // Decrypt with AES-GCM
  const decryptedBuffer = await window.crypto.subtle.decrypt(
    {
      name: 'AES-GCM',
      iv: nonce,
      tagLength: 128,
      additionalData: aadBytes
    },
    this.encryptionKey,
    ciphertext
  );

  const decoder = new TextDecoder();
  let decryptedData = decoder.decode(decryptedBuffer);

  // Decompress if needed
  if (encryptedPackage.compressed) {
    decryptedData = await this._decompress(decryptedData);
  }

  return JSON.parse(decryptedData);
}
```

---

#### 2. XChaCha20-Poly1305 (Alternative AEAD)

| Parameter | Value | Description |
|-----------|-------|-------------|
| **Algorithm** | XChaCha20-Poly1305 | Extended nonce ChaCha20 with Poly1305 MAC |
| **Key Size** | 256 bits (32 bytes) | ChaCha20 key length |
| **Nonce** | 192 bits (24 bytes) | Extended nonce (safer for random generation) |
| **MAC** | 128 bits (16 bytes) | Poly1305 authentication tag |
| **Use Case** | File encryption, streaming | Better random nonce safety |

```javascript
// Frontend: xchachaEncryption.js - XChaCha20-Poly1305 Encryption
async encrypt(keyBuffer, plaintext, associatedData = null) {
  // Convert plaintext to ArrayBuffer
  const plaintextBuffer = typeof plaintext === 'string'
    ? new TextEncoder().encode(plaintext)
    : plaintext;

  // Generate 12-byte nonce (falls back to AES-GCM in browser)
  const nonce = window.crypto.getRandomValues(new Uint8Array(12));

  // Import key for AES-GCM (browser fallback)
  const cryptoKey = await window.crypto.subtle.importKey(
    'raw',
    keyBuffer,
    { name: 'AES-GCM' },
    false,
    ['encrypt', 'decrypt']
  );

  // Encrypt data with 128-bit authentication tag
  const ciphertext = await window.crypto.subtle.encrypt(
    {
      name: 'AES-GCM',
      iv: nonce,
      tagLength: 128,
      additionalData: associatedData 
        ? new TextEncoder().encode(associatedData) 
        : undefined
    },
    cryptoKey,
    plaintextBuffer
  );

  return {
    ciphertext: this.arrayBufferToBase64(ciphertext),
    nonce: this.arrayBufferToBase64(nonce),
    algorithm: 'XChaCha20-Poly1305',     // Logical algorithm
    actualAlgorithm: 'AES-256-GCM',       // Browser implementation
    version: '1.0'
  };
}

// File Encryption with Streaming (64KB chunks)
async encryptFile(keyBuffer, file, progressCallback = null) {
  const CHUNK_SIZE = 64 * 1024;  // 64 KB chunks
  const chunks = [];
  const masterNonce = this.generateNonce(12);
  
  let offset = 0;
  let chunkNumber = 0;
  
  while (offset < file.size) {
    const chunk = file.slice(offset, offset + CHUNK_SIZE);
    const chunkBuffer = await chunk.arrayBuffer();
    
    // Derive chunk-specific nonce
    const chunkNonceExtra = new Uint8Array([chunkNumber]);
    const chunkNonce = new Uint8Array([...masterNonce, ...chunkNonceExtra]);
    
    // Encrypt chunk
    const encrypted = await this.encrypt(keyBuffer, chunkBuffer, null);
    chunks.push(encrypted);
    
    offset += CHUNK_SIZE;
    chunkNumber++;
    
    if (progressCallback) {
      progressCallback(Math.round((offset / file.size) * 100));
    }
  }
  
  return {
    chunks,
    masterNonce: this.arrayBufferToBase64(masterNonce),
    originalSize: file.size,
    chunkSize: CHUNK_SIZE,
    fileName: file.name,
    fileType: file.type
  };
}
```

---

#### 3. CRYSTALS-Kyber-768 (Post-Quantum KEM)

| Parameter | Value | Description |
|-----------|-------|-------------|
| **Algorithm** | CRYSTALS-Kyber-768 | NIST PQC Standard (FIPS 203) |
| **Security Level** | NIST Level 3 | ~AES-192 equivalent |
| **Public Key** | 1184 bytes | Kyber-768 public key |
| **Private Key** | 2400 bytes | Kyber-768 secret key |
| **Ciphertext** | 1088 bytes | Encapsulated ciphertext |
| **Shared Secret** | 32 bytes | Derived shared secret |
| **Hybrid Mode** | Kyber + X25519 | Defense in depth |

```javascript
// Frontend: kyberService.js - Hybrid Post-Quantum Key Generation
async generateHybridKeypair() {
  await this.ensureInitialized();

  // Generate Kyber-768 keypair
  let kyberKeypair = null;
  if (!this.useFallback && this.kyberModule) {
    const { publicKey, secretKey } = await this.kyberModule.keypair();
    kyberKeypair = {
      publicKey: new Uint8Array(publicKey),
      secretKey: new Uint8Array(secretKey)
    };
  }

  // Generate X25519 keypair (always available)
  const x25519Keypair = this._generateX25519Keypair();

  // Return hybrid keypair
  return {
    kyber: kyberKeypair,
    x25519: x25519Keypair,
    algorithm: this.useFallback ? 'X25519' : 'Kyber768+X25519',
    securityLevel: this.useFallback ? 'classical' : 'post-quantum',
    timestamp: Date.now()
  };
}

// Hybrid Encapsulation (KEM + ECDH)
async hybridEncapsulate(recipientPublicKeys) {
  await this.ensureInitialized();
  const startTime = performance.now();

  let kyberResult = null;
  let x25519Result = null;

  // Kyber-768 encapsulation
  if (!this.useFallback && this.kyberModule && recipientPublicKeys.kyber) {
    const { ciphertext, sharedSecret } = await this.kyberModule.encapsulate(
      recipientPublicKeys.kyber.publicKey
    );
    kyberResult = {
      ciphertext: new Uint8Array(ciphertext),
      sharedSecret: new Uint8Array(sharedSecret)
    };
  }

  // X25519 key agreement (always performed)
  if (recipientPublicKeys.x25519) {
    const ephemeralKeypair = this._generateX25519Keypair();
    const sharedSecret = x25519.scalarMult(
      ephemeralKeypair.secretKey,
      recipientPublicKeys.x25519.publicKey
    );
    x25519Result = {
      publicKey: ephemeralKeypair.publicKey,
      sharedSecret: sharedSecret
    };
  }

  // Combine shared secrets using HKDF-SHA256
  const combinedSecret = await this._combineSharedSecrets(
    kyberResult?.sharedSecret,
    x25519Result?.sharedSecret
  );

  // Update metrics
  const encapsulateTime = performance.now() - startTime;
  this.metrics.encapsulations++;
  this.metrics.averageEncapsulateTime = 
    (this.metrics.averageEncapsulateTime * (this.metrics.encapsulations - 1) + encapsulateTime) 
    / this.metrics.encapsulations;

  return {
    kyber: kyberResult ? { ciphertext: kyberResult.ciphertext } : null,
    x25519: x25519Result ? { publicKey: x25519Result.publicKey } : null,
    sharedSecret: combinedSecret,
    algorithm: kyberResult ? 'Kyber768+X25519' : 'X25519',
    timing: encapsulateTime
  };
}

// Hybrid Decapsulation
async hybridDecapsulate(encapsulatedData, ourPrivateKeys) {
  await this.ensureInitialized();

  let kyberSecret = null;
  let x25519Secret = null;

  // Kyber-768 decapsulation
  if (!this.useFallback && this.kyberModule && encapsulatedData.kyber && ourPrivateKeys.kyber) {
    const sharedSecret = await this.kyberModule.decapsulate(
      encapsulatedData.kyber.ciphertext,
      ourPrivateKeys.kyber.secretKey
    );
    kyberSecret = new Uint8Array(sharedSecret);
  }

  // X25519 key agreement
  if (encapsulatedData.x25519 && ourPrivateKeys.x25519) {
    x25519Secret = x25519.scalarMult(
      ourPrivateKeys.x25519.secretKey,
      encapsulatedData.x25519.publicKey
    );
  }

  // Combine shared secrets
  return await this._combineSharedSecrets(kyberSecret, x25519Secret);
}

// Combine Kyber + X25519 shared secrets using HKDF
async _combineSharedSecrets(kyberSecret, x25519Secret) {
  const combined = new Uint8Array(
    (kyberSecret?.length || 0) + (x25519Secret?.length || 0)
  );
  
  let offset = 0;
  if (kyberSecret) {
    combined.set(kyberSecret, offset);
    offset += kyberSecret.length;
  }
  if (x25519Secret) {
    combined.set(x25519Secret, offset);
  }

  // Derive final key using HKDF-SHA256
  const info = new TextEncoder().encode('SecureVault-Hybrid-KEM-v1');
  return hash(combined, { dkLen: 32 }); // 256-bit derived key
}
```

```python
# Backend: kyber_crypto.py - Production Kyber Implementation
class ProductionKyber:
    """
    Production-ready CRYSTALS-Kyber implementation.
    Uses liboqs-python or pqcrypto for real post-quantum cryptography.
    """
    
    # Key sizes for CRYSTALS-Kyber-768 (NIST Level 3)
    PUBLIC_KEY_SIZE = 1184
    PRIVATE_KEY_SIZE = 2400
    CIPHERTEXT_SIZE = 1088
    SHARED_SECRET_SIZE = 32
    
    def generate_keypair(self) -> Tuple[bytes, bytes]:
        """Generate CRYSTALS-Kyber-768 keypair."""
        if self.implementation == 'liboqs':
            kem = oqs.KeyEncapsulation("Kyber768")
            public_key = kem.generate_keypair()
            private_key = kem.export_secret_key()
            return public_key, private_key
        elif self.implementation == 'pqcrypto':
            return pqcrypto_kyber.generate_keypair()
    
    def encapsulate(self, public_key: bytes) -> Tuple[bytes, bytes]:
        """Encapsulate a shared secret using recipient's public key."""
        if self.implementation == 'liboqs':
            kem = oqs.KeyEncapsulation("Kyber768")
            ciphertext, shared_secret = kem.encap_secret(public_key)
            return ciphertext, shared_secret
        elif self.implementation == 'pqcrypto':
            return pqcrypto_kyber.encrypt(public_key)
    
    def decapsulate(self, ciphertext: bytes, private_key: bytes) -> bytes:
        """Decapsulate shared secret using private key."""
        if self.implementation == 'liboqs':
            kem = oqs.KeyEncapsulation("Kyber768", private_key)
            return kem.decap_secret(ciphertext)
        elif self.implementation == 'pqcrypto':
            return pqcrypto_kyber.decrypt(private_key, ciphertext)
```

---

#### 4. Hybrid Elliptic Curve Cryptography (ECC)

| Curve | Key Size | Use Case | Standard |
|-------|----------|----------|----------|
| **Curve25519 (X25519)** | 32 bytes | ECDH key agreement | djb/Bernstein |
| **P-384 (secp384r1)** | 48 bytes | ECDH key agreement | NIST FIPS 186-4 |
| **Ed25519** | 32 bytes | Digital signatures | EdDSA |

```javascript
// Frontend: eccService.js - Hybrid ECC Implementation
export class ECCService {
  constructor() {
    this.CURVE25519_KEY_SIZE = 32;  // bytes
    this.P384_KEY_SIZE = 48;         // bytes (384 bits)
  }

  // Generate hybrid keypair (both curves)
  generateHybridKeyPair() {
    const curve25519Pair = this.generateCurve25519KeyPair();
    const p384Pair = this.generateP384KeyPair();
    
    return {
      curve25519: curve25519Pair,
      p384: p384Pair,
      type: 'hybrid-ecdh',
      version: 2
    };
  }

  // Perform Curve25519 ECDH
  performCurve25519ECDH(privateKey, publicKey) {
    return x25519.getSharedSecret(privateKey, publicKey);
  }

  // Perform P-384 ECDH
  performP384ECDH(privateKey, publicKey) {
    return p384.getSharedSecret(privateKey, publicKey);
  }

  // Combine secrets from both curves using HKDF
  async deriveHybridSharedSecret(ourKeys, peerKeys, context = 'SecureVault-ECC-v2') {
    // Perform ECDH with both curves
    const secret1 = this.performCurve25519ECDH(
      ourKeys.curve25519.privateKey,
      peerKeys.curve25519
    );
    
    const secret2 = this.performP384ECDH(
      ourKeys.p384.privateKey,
      peerKeys.p384
    );

    // Combine secrets
    const combined = new Uint8Array(secret1.length + secret2.length);
    combined.set(secret1, 0);
    combined.set(secret2, secret1.length);

    // Derive final key using HKDF-SHA256
    const info = new TextEncoder().encode(context);
    return hkdf(sha256, combined, undefined, info, 32);
  }
}
```

---

#### 5. Fully Homomorphic Encryption (FHE)

| Parameter | Value | Description |
|-----------|-------|-------------|
| **Implementation** | TFHE (WASM) / Concrete-Python / TenSEAL | Multiple FHE backends |
| **Key Size** | 2048 bits | FHE encryption key |
| **Polynomial Degree** | 8192 | Lattice polynomial |
| **Security Level** | 128 bits | Post-quantum secure |
| **Use Cases** | Password strength check, encrypted search | Server-side computation |

```javascript
// Frontend: fheService.js - FHE Client Operations
class FHEService {
  constructor() {
    this.KEY_SIZE = 2048;
    this.POLYNOMIAL_DEGREE = 8192;
    this.SECURITY_LEVEL = 128;
  }

  // Initialize TFHE WASM module
  async initialize() {
    try {
      // Attempt to load TFHE WebAssembly module
      const tfhe = await loadTFHE();
      if (tfhe) {
        this._tfheModule = tfhe;
        this.wasmLoaded = true;
      }
      
      // Load or generate keys
      await this._initializeKeys();
      this.initialized = true;
      
      return true;
    } catch (error) {
      // Fall back to simulated FHE for development
      this.wasmLoaded = false;
      this.initialized = true;
      return true;
    }
  }

  // Encrypt password for FHE operations
  async encryptPassword(password, options = {}) {
    if (!this.initialized) await this.initialize();

    const { tier = EncryptionTier.HYBRID_FHE } = options;

    // For client-only tier, use local encryption
    if (tier === EncryptionTier.CLIENT_ONLY) {
      return this._clientOnlyEncrypt(password);
    }

    // For hybrid/full FHE, use backend service
    const response = await api.post(FHE_CONFIG.ENDPOINTS.ENCRYPT, {
      data: this._prepareForEncryption(password),
      tier: tier,
      operation: FHE_CONFIG.OPERATIONS.PASSWORD_SEARCH
    });

    return response.data;
  }

  // Check password strength on encrypted data
  async checkStrength(encryptedPassword) {
    const response = await api.post(FHE_CONFIG.ENDPOINTS.STRENGTH_CHECK, {
      encrypted_password: encryptedPassword,
      return_details: true
    });

    return {
      strength: response.data.strength_score,
      entropy: response.data.entropy,
      feedback: response.data.feedback,
      computation_time: response.data.computation_time_ms
    };
  }
}
```

```python
# Backend: fhe_service/services/concrete_service.py - FHE Server Operations
class ConcreteFHEService:
    """
    Lightweight FHE operations using Concrete-Python.
    Optimized for single-value operations like password strength.
    """
    
    def __init__(self):
        self.circuit = None
        self.initialized = False
    
    def encrypt_password(self, password: str) -> bytes:
        """Encrypt password for FHE operations."""
        # Convert password to numerical representation
        password_values = [ord(c) for c in password[:32]]
        
        # Encrypt using Concrete
        encrypted = self.circuit.encrypt(password_values)
        return encrypted
    
    def compute_strength_encrypted(self, encrypted_password: bytes) -> int:
        """
        Compute password strength on encrypted data.
        Server never sees the plaintext password!
        """
        # Run FHE circuit
        result = self.circuit.run(encrypted_password)
        
        # Decrypt result (strength score only)
        strength_score = self.circuit.decrypt(result)
        return strength_score
```

---

### Algorithm Comparison Matrix

| Algorithm | Key Size | Security | Quantum-Safe | Speed | Use Case |
|-----------|----------|----------|--------------|-------|----------|
| **AES-256-GCM** | 256-bit | 256-bit | ❌ No | ⚡ Very Fast | Primary vault encryption |
| **XChaCha20-Poly1305** | 256-bit | 256-bit | ❌ No | ⚡ Very Fast | File/stream encryption |
| **Kyber-768** | 1184/2400 bytes | NIST L3 | ✅ Yes | 🔵 Fast | Post-quantum KEM |
| **X25519** | 32 bytes | 128-bit | ❌ No | ⚡ Very Fast | Classical ECDH |
| **P-384** | 48 bytes | 192-bit | ❌ No | 🔵 Fast | Enterprise ECDH |
| **TFHE** | 2048-bit | 128-bit | ✅ Yes | 🔴 Slow | Encrypted computation |
| **Argon2id** | N/A | Memory-hard | ✅ Yes | 🔵 Configurable | Key derivation |

---

### Encrypted Data Package Format

```json
{
  "v": "2.0",                           // Encryption version
  "alg": "AES-256-GCM-ARGON2ID",       // Algorithm identifier
  "nonce": "base64(12-bytes)",          // Random nonce/IV
  "ct": "base64(ciphertext+tag)",       // Ciphertext with auth tag
  "compressed": true,                   // Compression flag
  "ts": 1699999999999,                  // Timestamp
  "aad": true,                          // Additional authenticated data flag
  "kdf": {                              // Key derivation parameters
    "type": "argon2id",
    "time": 4,
    "mem": 131072,
    "parallelism": 2
  }
}
```

### Key Derivation Function (Argon2id)

SecureVault uses **Argon2id** (PHC winner, OWASP 2024 recommended) with adaptive parameters based on device capability.

> **Note:** SecureVault has TWO crypto services with slightly different Argon2id parameters:
> - `secureVaultCrypto.js` (v2.0) - 64-byte hash with key splitting (recommended for new implementations)
> - `cryptoService.js` (legacy-compatible) - 32-byte hash, different memory parameters per tier

```
┌─────────────────────────────────────────────────────────────────────────────────────────────────┐
│                           ARGON2ID KEY DERIVATION (Adaptive)                                     │
├─────────────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                                  │
│    Master Password              User-Specific Salt                                              │
│           │                           │                                                          │
│           └───────────┬───────────────┘                                                          │
│                       │                                                                          │
│                       ▼                                                                          │
│    ┌─────────────────────────────────────────────────────────────────────────────────────────┐  │
│    │                              ARGON2ID v1.3                                               │  │
│    │                                                                                          │  │
│    │   ╔══════════════════════════════════════════════════════════════════════════════════╗  │  │
│    │   ║  secureVaultCrypto.js (v2.0) - Key Splitting Mode                                ║  │  │
│    │   ╠══════════════════════════════════════════════════════════════════════════════════╣  │  │
│    │   ║  High-End (8GB+ RAM, 4+ cores):                                                  ║  │  │
│    │   ║    Memory: 128 MB | Iterations: 4 | Parallelism: 4 | Hash: 64 bytes → split     ║  │  │
│    │   ║                                                                                  ║  │  │
│    │   ║  Mid-Range (4GB+ RAM, 2+ cores):                                                 ║  │  │
│    │   ║    Memory: 64 MB  | Iterations: 3 | Parallelism: 2 | Hash: 64 bytes → split     ║  │  │
│    │   ║                                                                                  ║  │  │
│    │   ║  Low-End (mobile, <4GB RAM):                                                     ║  │  │
│    │   ║    Memory: 32 MB  | Iterations: 2 | Parallelism: 1 | Hash: 64 bytes → split     ║  │  │
│    │   ╚══════════════════════════════════════════════════════════════════════════════════╝  │  │
│    │                                                                                          │  │
│    │   ┌──────────────────────────────────────────────────────────────────────────────────┐  │  │
│    │   │  cryptoService.js (Legacy-Compatible) - Single Key Mode                          │  │  │
│    │   ├──────────────────────────────────────────────────────────────────────────────────┤  │  │
│    │   │  High-End (8GB+ RAM, 4+ cores):                                                  │  │  │
│    │   │    Memory: 128 MB | Iterations: 4 | Parallelism: 2 | Hash: 32 bytes             │  │  │
│    │   │                                                                                  │  │  │
│    │   │  Mid-Range (4GB+ RAM, 2+ cores):                                                 │  │  │
│    │   │    Memory: 96 MB  | Iterations: 4 | Parallelism: 2 | Hash: 32 bytes             │  │  │
│    │   │                                                                                  │  │  │
│    │   │  Low-End (mobile, <4GB RAM):                                                     │  │  │
│    │   │    Memory: 64 MB  | Iterations: 3 | Parallelism: 1 | Hash: 32 bytes             │  │  │
│    │   │                                                                                  │  │  │
│    │   │  Legacy (v1 compatibility):                                                      │  │  │
│    │   │    Memory: 64 MB  | Iterations: 10 | Parallelism: 1 | Hash: 32 bytes            │  │  │
│    │   └──────────────────────────────────────────────────────────────────────────────────┘  │  │
│    │                                                                                          │  │
│    │   Fixed Parameters (Both Services):                                                     │  │
│    │     Type: Argon2id (hybrid: data-dependent + independent addressing)                    │  │
│    │     Version: 0x13 (v1.3)                                                                │  │
│    │     Salt Length: 16-32 bytes (depending on service)                                     │  │
│    │                                                                                          │  │
│    └──────────────────────────────┬───────────────────────────────────────────────────────────┘  │
│                                   │                                                              │
│           ┌───────────────────────┴───────────────────────┐                                     │
│           │                                               │                                     │
│           ▼                                               ▼                                     │
│    ┌─────────────────────────────────┐    ┌─────────────────────────────────┐                  │
│    │   secureVaultCrypto.js (v2.0)   │    │   cryptoService.js (Legacy)     │                  │
│    │                                 │    │                                 │                  │
│    │   64-byte derived hash          │    │   32-byte derived hash          │                  │
│    │   ├──────────┬──────────┤       │    │   │                             │                  │
│    │   ▼          ▼                  │    │   ▼                             │                  │
│    │ ┌──────────┐ ┌──────────┐       │    │ ┌──────────────────┐            │                  │
│    │ │Encryption│ │  Auth    │       │    │ │ Single AES-256   │            │                  │
│    │ │   Key    │ │   Key    │       │    │ │  Encryption Key  │            │                  │
│    │ │(32 bytes)│ │(32 bytes)│       │    │ │   (32 bytes)     │            │                  │
│    │ │ AES-GCM  │ │HMAC-SHA256│      │    │ │  AES-GCM/CBC     │            │                  │
│    │ └──────────┘ └──────────┘       │    │ └──────────────────┘            │                  │
│    └─────────────────────────────────┘    └─────────────────────────────────┘                  │
│                                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────────────────────┘
```

#### Parameter Comparison Table

| Service | Tier | Memory | Iterations | Parallelism | Hash Length | Key Split |
|---------|------|--------|------------|-------------|-------------|-----------|
| **secureVaultCrypto.js** | High | 128 MB | 4 | 4 | 64 bytes | ✅ Yes |
| **secureVaultCrypto.js** | Medium | 64 MB | 3 | 2 | 64 bytes | ✅ Yes |
| **secureVaultCrypto.js** | Low | 32 MB | 2 | 1 | 64 bytes | ✅ Yes |
| **cryptoService.js** | High | 128 MB | 4 | 2 | 32 bytes | ❌ No |
| **cryptoService.js** | Medium | 96 MB | 4 | 2 | 32 bytes | ❌ No |
| **cryptoService.js** | Low | 64 MB | 3 | 1 | 32 bytes | ❌ No |
| **cryptoService.js** | Legacy | 64 MB | 10 | 1 | 32 bytes | ❌ No |

---

### CryptoService.js - Complete Client-Side Encryption Service

`cryptoService.js` is the **primary encryption service** for SecureVault, implementing a zero-knowledge architecture where all cryptographic operations occur exclusively in the browser.

#### Service Overview

| Feature | Description |
|---------|-------------|
| **File** | `frontend/src/services/cryptoService.js` |
| **Size** | 454 lines |
| **Purpose** | Zero-knowledge client-side encryption |
| **Dependencies** | `crypto-js`, `pako`, `argon2-browser` |
| **Primary Encryption** | AES-256-GCM (WebCrypto) / AES-256-CBC (CryptoJS fallback) |
| **KDF** | Argon2id with PBKDF2-SHA256 fallback |
| **Compression** | Gzip via pako (for data > 1KB) |

#### Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        CryptoService.js Architecture                         │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │                       INITIALIZATION                                 │   │
│   │                                                                      │   │
│   │   new CryptoService(masterPassword)                                 │   │
│   │   │                                                                  │   │
│   │   ├─► Store master password in memory                               │   │
│   │   └─► Initialize SubtleCrypto API reference                         │   │
│   │                                                                      │   │
│   └─────────────────────────────────────────────────────────────────────┘   │
│                                    │                                         │
│                                    ▼                                         │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │                    DEVICE CAPABILITY DETECTION                       │   │
│   │                                                                      │   │
│   │   getDeviceCapabilities()                                            │   │
│   │   │                                                                  │   │
│   │   ├─► navigator.deviceMemory (RAM in GB)                            │   │
│   │   ├─► navigator.hardwareConcurrency (CPU cores)                     │   │
│   │   │                                                                  │   │
│   │   └─► Returns: 'high' | 'medium' | 'low'                            │   │
│   │       • high:   8GB+ RAM, 4+ cores                                  │   │
│   │       • medium: 4GB+ RAM, 2+ cores                                  │   │
│   │       • low:    <4GB RAM or <2 cores                                │   │
│   │                                                                      │   │
│   └─────────────────────────────────────────────────────────────────────┘   │
│                                    │                                         │
│                                    ▼                                         │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │                    KEY DERIVATION FLOW                               │   │
│   │                                                                      │   │
│   │   deriveKey(salt, cryptoVersion)                                    │   │
│   │   │                                                                  │   │
│   │   ├─► Primary: Argon2id (argon2-browser)                            │   │
│   │   │   • time:        3-4 iterations (adaptive)                      │   │
│   │   │   • mem:         64-128 MB (adaptive)                           │   │
│   │   │   • hashLen:     32 bytes                                       │   │
│   │   │   • parallelism: 1-2 (adaptive)                                 │   │
│   │   │   • type:        Argon2id                                       │   │
│   │   │                                                                  │   │
│   │   └─► Fallback: PBKDF2-HMAC-SHA256 (CryptoJS)                       │   │
│   │       • iterations:  600,000                                        │   │
│   │       • keySize:     256 bits                                       │   │
│   │                                                                      │   │
│   └─────────────────────────────────────────────────────────────────────┘   │
│                                    │                                         │
│                                    ▼                                         │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │                     ENCRYPTION METHODS                               │   │
│   │                                                                      │   │
│   │   encrypt(data, salt)          │    legacyEncrypt(data, key)        │   │
│   │   │                            │    │                                │   │
│   │   │ WebCrypto API (primary)    │    │ CryptoJS (fallback)           │   │
│   │   │ • AES-256-GCM              │    │ • AES-256-CBC                  │   │
│   │   │ • 12-byte random IV        │    │ • 16-byte random IV           │   │
│   │   │ • Hardware-accelerated     │    │ • PKCS7 padding               │   │
│   │   │                            │    │ • Optional gzip compression   │   │
│   │   │                            │    │                                │   │
│   │   └────────────────────────────┴────┘                                │   │
│   │                                                                      │   │
│   └─────────────────────────────────────────────────────────────────────┘   │
│                                    │                                         │
│                                    ▼                                         │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │                     DECRYPTION METHODS                               │   │
│   │                                                                      │   │
│   │   decrypt(encryptedData, key)                                       │   │
│   │   │                                                                  │   │
│   │   ├─► Parse JSON payload {iv, data, compressed, version}            │   │
│   │   ├─► AES-256-CBC decrypt with CryptoJS                             │   │
│   │   ├─► Decompress if compressed flag is true                         │   │
│   │   └─► Return parsed JSON object                                     │   │
│   │                                                                      │   │
│   └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

#### Complete API Reference

```javascript
/**
 * CryptoService - Zero-Knowledge Client-Side Encryption
 * 
 * ZERO-KNOWLEDGE SECURITY MODEL:
 * 1. All encryption/decryption happens exclusively in the browser
 * 2. The server never receives plaintext data or encryption keys
 * 3. The master password never leaves the client
 * 4. Only encrypted data is transmitted to and stored on the server
 * 5. Recovery keys provide an alternative decryption path
 */
export class CryptoService {
  constructor(masterPassword) {
    this.masterPassword = masterPassword;
    this.subtle = window.crypto.subtle;
  }
}
```

#### Method: Device Capability Detection

```javascript
// cryptoService.js - Device capability detection for adaptive Argon2id
getDeviceCapabilities() {
  // Check device RAM and CPU cores
  const memory = navigator.deviceMemory || 4;  // GB, default 4GB
  const cores = navigator.hardwareConcurrency || 1;
  
  // Categorize device capability
  if (memory >= 8 && cores >= 4) {
    return 'high';    // Desktop/high-end laptop
  } else if (memory >= 4 && cores >= 2) {
    return 'medium';  // Mid-range device
  } else {
    return 'low';     // Low-end mobile
  }
}
```

#### Method: Argon2id Parameters

```javascript
// cryptoService.js - Adaptive Argon2id parameters
getArgon2Params(deviceCapability = null) {
  const capability = deviceCapability || this.getDeviceCapabilities();
  
  const params = {
    high: {
      time: 4,           // 4 iterations
      mem: 131072,       // 128 MB memory
      parallelism: 2,    // 2 threads
      version: 2
    },
    medium: {
      time: 4,           // 4 iterations
      mem: 98304,        // 96 MB memory (NOTE: different from secureVaultCrypto!)
      parallelism: 2,    // 2 threads
      version: 2
    },
    low: {
      time: 3,           // 3 iterations
      mem: 65536,        // 64 MB memory
      parallelism: 1,    // 1 thread
      version: 2
    },
    legacy: {            // v1 backward compatibility
      time: 10,          // 10 iterations (higher for older params)
      mem: 65536,        // 64 MB memory
      parallelism: 1,    // 1 thread
      version: 1
    }
  };
  
  return params[capability] || params.medium;
}
```

#### Method: Key Derivation (Argon2id + PBKDF2 Fallback)

```javascript
// cryptoService.js - Key derivation with Argon2id
async deriveKey(salt, cryptoVersion = 2) {
  // SECURITY NOTE: Key derivation happens client-side for zero-knowledge
  try {
    const saltArr = typeof salt === 'string' 
      ? CryptoJS.enc.Base64.parse(salt).toString(CryptoJS.enc.Hex)
      : salt;
    
    // Get parameters based on crypto version and device capability
    const params = cryptoVersion === 1 
      ? this.getArgon2Params('legacy')
      : this.getArgon2Params();
    
    console.log(`Deriving key with Argon2id v${cryptoVersion}:`, {
      time: params.time,
      mem: `${params.mem / 1024} MB`,
      parallelism: params.parallelism
    });
    
    // Argon2id hash
    const result = await argon2.hash({
      pass: this.masterPassword,
      salt: saltArr,
      time: params.time,
      mem: params.mem,
      hashLen: 32,                      // 32 bytes (256 bits) for AES-256
      parallelism: params.parallelism,
      type: argon2.ArgonType.Argon2id   // Use Argon2id variant
    });

    // Return base64 encoded hash for AES encryption
    return CryptoJS.enc.Base64.stringify(CryptoJS.enc.Hex.parse(result.hashHex));
    
  } catch (error) {
    console.error('Argon2 key derivation failed, falling back to PBKDF2:', error);
    
    // Fallback to PBKDF2 with 600,000 iterations (OWASP minimum)
    const key = CryptoJS.PBKDF2(this.masterPassword, salt, {
      keySize: 256/32,      // 256 bits
      iterations: 600000,   // 600k iterations
      hasher: CryptoJS.algo.SHA256
    });
    return key.toString(CryptoJS.enc.Base64);
  }
}
```

#### Method: WebCrypto Encryption (Primary)

```javascript
// cryptoService.js - WebCrypto AES-256-GCM encryption
async encrypt(data, salt) {
  try {
    // Derive CryptoKey using PBKDF2 (WebCrypto native)
    const key = await this.getCryptoKey(salt);
    
    // Generate 12-byte random IV (96 bits for AES-GCM)
    const iv = window.crypto.getRandomValues(new Uint8Array(12));
    
    // Convert data to ArrayBuffer
    const encoder = new TextEncoder();
    const dataToEncrypt = encoder.encode(JSON.stringify(data));
    
    // Encrypt with AES-256-GCM (authenticated encryption)
    const encryptedData = await this.subtle.encrypt(
      { name: 'AES-GCM', iv },
      key,
      dataToEncrypt
    );
    
    // Package result
    const result = {
      iv: Array.from(iv).map(b => String.fromCharCode(b)).join(''),
      data: Array.from(new Uint8Array(encryptedData)).map(b => String.fromCharCode(b)).join(''),
      version: 'webcrypto-1',
      usingHardwareEncryption: navigator.credentials && !!navigator.credentials.preventSilentAccess
    };
    
    return btoa(JSON.stringify(result));
    
  } catch (error) {
    console.error('WebCrypto encryption failed, falling back to CryptoJS:', error);
    return this.legacyEncrypt(data, salt);
  }
}
```

#### Method: Legacy Encryption (CryptoJS Fallback)

```javascript
// cryptoService.js - CryptoJS AES-256-CBC encryption with compression
async legacyEncrypt(data, key) {
  // SECURITY NOTE: Encryption occurs client-side only
  
  let dataToEncrypt = data;
  let compressed = false;
  
  // Compress large data (>1KB) using gzip
  const jsonData = JSON.stringify(data);
  if (jsonData.length > 1024) {
    try {
      const compressedData = pako.deflate(jsonData);
      if (compressedData.length < jsonData.length) {
        dataToEncrypt = compressedData;
        compressed = true;
      }
    } catch (error) {
      console.warn('Compression failed, using uncompressed data', error);
    }
  }
  
  // Generate 16-byte random IV
  const iv = CryptoJS.lib.WordArray.random(16);
  
  // Encrypt with AES-256-CBC
  const dataToProcess = compressed 
    ? CryptoJS.lib.WordArray.create(dataToEncrypt)
    : JSON.stringify(dataToEncrypt);
  
  const encrypted = CryptoJS.AES.encrypt(dataToProcess, key, {
    iv: iv,
    mode: CryptoJS.mode.CBC,
    padding: CryptoJS.pad.Pkcs7
  });
  
  // Return JSON payload
  return JSON.stringify({
    iv: iv.toString(CryptoJS.enc.Base64),
    data: encrypted.toString(),
    compressed: compressed
  });
}
```

#### Method: Decryption

```javascript
// cryptoService.js - AES-256-CBC decryption with decompression
async decrypt(encryptedData, key) {
  // SECURITY NOTE: Decryption occurs client-side - server never sees plaintext
  try {
    const payload = JSON.parse(encryptedData);
    
    if (!payload.iv || !payload.data) {
      throw new Error('Invalid encrypted data format');
    }
    
    // Parse IV from Base64
    const iv = CryptoJS.enc.Base64.parse(payload.iv);
    
    // Decrypt data
    const decrypted = CryptoJS.AES.decrypt(payload.data, key, {
      iv: iv,
      mode: CryptoJS.mode.CBC,
      padding: CryptoJS.pad.Pkcs7
    });
    
    // Handle decompression if data was compressed
    if (payload.compressed) {
      const decryptedBytes = this.convertWordArrayToUint8Array(decrypted);
      const decompressed = pako.inflate(decryptedBytes);
      const jsonStr = new TextDecoder().decode(decompressed);
      return JSON.parse(jsonStr);
    } else {
      const decryptedStr = decrypted.toString(CryptoJS.enc.Utf8);
      if (!decryptedStr) {
        throw new Error('Decryption failed - invalid key or corrupted data');
      }
      return JSON.parse(decryptedStr);
    }
    
  } catch (error) {
    console.error('Decryption error:', error.message);
    throw new Error('Failed to decrypt data: ' + error.message);
  }
}
```

#### Method: Recovery Key Derivation

```javascript
// cryptoService.js - Derive key from recovery key (alternative decryption path)
async deriveKeyFromRecoveryKey(recoveryKey, salt, iterations = 10) {
  // SECURITY NOTE: Recovery key derivation also happens client-side
  // Recovery keys maintain zero-knowledge while providing backup access
  try {
    // Remove hyphens from recovery key
    const cleanRecoveryKey = recoveryKey.replace(/-/g, '');
    
    const saltArr = typeof salt === 'string' 
      ? CryptoJS.enc.Base64.parse(salt).toString(CryptoJS.enc.Hex)
      : salt;
    
    const result = await argon2.hash({
      pass: cleanRecoveryKey,
      salt: saltArr,
      time: iterations,    // Lower iterations for recovery keys
      mem: 65536,          // 64 MB memory
      hashLen: 32,         // 32 bytes output
      parallelism: 1,
      type: argon2.ArgonType.Argon2id
    });

    return CryptoJS.enc.Base64.stringify(CryptoJS.enc.Hex.parse(result.hashHex));
    
  } catch (error) {
    console.error('Argon2 recovery key derivation failed:', error);
    
    // Fallback to PBKDF2
    const key = CryptoJS.PBKDF2(
      recoveryKey.replace(/-/g, ''),
      salt, 
      {
        keySize: 256/32,
        iterations: 600000,
        hasher: CryptoJS.algo.SHA256
      }
    );
    return key.toString(CryptoJS.enc.Base64);
  }
}
```

#### Method: Secure Password Generation

```javascript
// cryptoService.js - Cryptographically secure password generation
generatePassword(length = 16, options = {
  uppercase: true,
  lowercase: true,
  numbers: true,
  symbols: true
}) {
  const chars = {
    uppercase: 'ABCDEFGHIJKLMNOPQRSTUVWXYZ',
    lowercase: 'abcdefghijklmnopqrstuvwxyz',
    numbers: '0123456789',
    symbols: '!@#$%^&*()_+~`|}{[]:;?><,./-='
  };
  
  let charset = '';
  if (options.uppercase) charset += chars.uppercase;
  if (options.lowercase) charset += chars.lowercase;
  if (options.numbers) charset += chars.numbers;
  if (options.symbols) charset += chars.symbols;
  
  if (charset === '') {
    charset = chars.lowercase + chars.numbers;
  }
  
  // Use Web Crypto API for cryptographically secure random values
  let password = '';
  const randomValues = new Uint32Array(length);
  window.crypto.getRandomValues(randomValues);
  
  for (let i = 0; i < length; i++) {
    password += charset[randomValues[i] % charset.length];
  }
  
  return password;
}
```

#### Method: Secure Memory Clearing

```javascript
// cryptoService.js - Securely clear sensitive data from memory
clearKeys() {
  // SECURITY NOTE: Clear sensitive data when no longer needed
  this.masterPassword = null;
  this.encryptionKey = null;
  
  // Overwrite memory with random data
  const buf = new Uint8Array(1024);
  crypto.getRandomValues(buf);
  
  // Force garbage collection if available
  if (global.gc) global.gc();
}
```

#### Encrypted Data Format

```json
// WebCrypto format (version: 'webcrypto-1')
{
  "iv": "binary-string-12-bytes",
  "data": "binary-string-ciphertext",
  "version": "webcrypto-1",
  "usingHardwareEncryption": true
}

// Legacy CryptoJS format
{
  "iv": "base64-16-bytes",
  "data": "base64-ciphertext",
  "compressed": true|false
}
```

---

#### Argon2id Parameters (Code)

```javascript
// Frontend: secureVaultCrypto.js - Adaptive Argon2id Parameters
const ARGON2_PARAMS = {
  high: {     // Desktop/high-end laptop (8GB+ RAM, 4+ cores)
    time: 4,           // 4 iterations
    mem: 131072,       // 128 MB memory
    parallelism: 4     // 4 threads
  },
  medium: {   // Mid-range device (4GB+ RAM, 2+ cores)
    time: 3,           // 3 iterations
    mem: 65536,        // 64 MB memory
    parallelism: 2     // 2 threads
  },
  low: {      // Low-end/mobile (<4GB RAM)
    time: 2,           // 2 iterations
    mem: 32768,        // 32 MB memory
    parallelism: 1     // 1 thread
  },
};

// Detect device capability
_detectDeviceCapability() {
  const memory = navigator.deviceMemory || 4;  // GB
  const cores = navigator.hardwareConcurrency || 2;

  if (memory >= 8 && cores >= 4) return 'high';
  if (memory >= 4 && cores >= 2) return 'medium';
  return 'low';
}

// Derive key from master password
async deriveKeyFromPassword(masterPassword, salt) {
  const saltBytes = typeof salt === 'string' 
    ? this._base64ToBytes(salt) 
    : salt;
  
  const params = ARGON2_PARAMS[this.deviceCapability];
  
  console.log(`[SecureCrypto] Deriving key with Argon2id (${this.deviceCapability}):`, {
    time: params.time,
    memory: `${params.mem / 1024}MB`,
    parallelism: params.parallelism
  });

  // Use Argon2id for key derivation
  const result = await argon2.hash({
    pass: masterPassword,
    salt: this._bytesToHex(saltBytes),
    time: params.time,
    mem: params.mem,
    hashLen: 64,          // 512 bits for split key
    parallelism: params.parallelism,
    type: argon2.ArgonType.Argon2id
  });

  // Split derived key into encryption key (256 bits) and auth key (256 bits)
  const keyMaterial = this._hexToBytes(result.hashHex);
  const encKeyBytes = keyMaterial.slice(0, 32);   // First 32 bytes
  const authKeyBytes = keyMaterial.slice(32, 64); // Last 32 bytes

  // Import as CryptoKey for AES-GCM
  this.encryptionKey = await window.crypto.subtle.importKey(
    'raw',
    encKeyBytes,
    { name: 'AES-GCM', length: 256 },
    false,  // Not extractable
    ['encrypt', 'decrypt']
  );

  // Store auth key for HMAC operations
  this.authKey = await window.crypto.subtle.importKey(
    'raw',
    authKeyBytes,
    { name: 'HMAC', hash: 'SHA-256' },
    false,
    ['sign', 'verify']
  );

  // Secure memory wipe
  this._secureWipe(keyMaterial);
  this._secureWipe(encKeyBytes);
  this._secureWipe(authKeyBytes);

  return this.encryptionKey;
}
```

```python
# Backend: vault/crypto.py - Argon2id Key Derivation
from argon2 import PasswordHasher, Type
import argon2

def derive_key_from_password(password, salt, time_cost=4, memory_cost=131072, parallelism=2, crypto_version=2):
    """
    Derive encryption key using Argon2id (OWASP 2024 recommended)
    
    Args:
        password: User's master password
        salt: Cryptographic salt (16+ bytes)
        time_cost: Number of iterations (v2 default: 4)
        memory_cost: Memory usage in KiB (v2 default: 131072 = 128 MB)
        parallelism: Parallelism factor (v2 default: 2)
        crypto_version: Crypto version (1 = legacy, 2 = enhanced)
        
    Returns:
        bytes: Base64-encoded derived key
    """
    # Legacy parameters for backward compatibility
    if crypto_version == 1:
        time_cost = 3
        memory_cost = 65536   # 64 MB
        parallelism = 1
    
    ph = PasswordHasher(
        time_cost=time_cost,
        memory_cost=memory_cost,
        parallelism=parallelism,
        hash_len=32,          # 32 bytes for AES-256
        salt_len=16,
        type=argon2.Type.ID   # Argon2id for balanced security
    )
    
    # Hash password with salt
    key = ph.hash(password + salt.hex())
    
    # Derive final key using SHA-256 for consistent output
    return base64.urlsafe_b64encode(hashlib.sha256(key.encode()).digest())
```

#### PBKDF2 Fallback (Legacy Support)

When Argon2id is not available (older browsers), PBKDF2-HMAC-SHA256 is used:

```javascript
// Fallback to PBKDF2 with 600,000 iterations
async legacyDeriveKey(salt) {
  const key = CryptoJS.PBKDF2(this.masterPassword, salt, {
    keySize: 256/32,      // 256 bits
    iterations: 600000,   // OWASP 2024 minimum
    hasher: CryptoJS.algo.SHA256
  });
  return key.toString(CryptoJS.enc.Base64);
}
```

### Decryption Flow

```mermaid
sequenceDiagram
    participant U as User
    participant C as Client
    participant S as Server
    participant DB as Database

    U->>C: Request vault item
    C->>S: GET /api/vault/items/{id}/
    S->>DB: Fetch encrypted blob
    DB->>S: {ciphertext, iv, tag, salt}
    S->>C: Return encrypted blob
    
    U->>C: Enter master password
    
    Note over C: Key Derivation
    C->>C: Argon2id(password, salt)
    
    Note over C: Decryption
    C->>C: Verify auth tag
    C->>C: AES-GCM-256 decrypt
    
    C->>U: Display plaintext
    
    Note over C: Plaintext only exists in browser memory
```

---

## 🔐 Client-Side Encryption

SecureVault v2.0 introduces an enhanced client-side encryption system using the **WebCrypto API** for hardware-accelerated cryptographic operations.

### Implementation Components

| Component | File | Purpose |
|-----------|------|---------|
| **SecureVaultCrypto** | `services/secureVaultCrypto.js` | Core encryption/decryption with WebCrypto API |
| **SecureVaultService** | `services/secureVaultService.js` | Zero-knowledge vault operations |
| **useSecureVault** | `hooks/useSecureVault.js` | React hook for vault integration |

### SecureVaultCrypto Features

```javascript
// Client-side implementation (secureVaultCrypto.js)
export class SecureVaultCrypto {
  // Adaptive Argon2id parameters based on device capability
  static ARGON2_PARAMS = {
    high: { time: 4, mem: 131072, parallelism: 4 }, // 128MB for high-end
    medium: { time: 3, mem: 65536, parallelism: 2 }, // 64MB for mid-range
    low: { time: 2, mem: 32768, parallelism: 1 },    // 32MB for mobile
  };

  // Key derivation with hardware acceleration
  async deriveKeyFromPassword(masterPassword, salt) {
    const result = await argon2.hash({
      pass: masterPassword,
      salt: saltBytes,
      time: params.time,
      mem: params.mem,
      hashLen: 64, // 512 bits split into encryption + auth keys
      parallelism: params.parallelism,
      type: argon2.ArgonType.Argon2id
    });
    
    // Import as WebCrypto CryptoKey for AES-GCM
    this.encryptionKey = await crypto.subtle.importKey(
      'raw', encKeyBytes, 
      { name: 'AES-GCM', length: 256 },
      false, ['encrypt', 'decrypt']
    );
  }

  // AES-256-GCM encryption with random nonce
  async encrypt(data, options = {}) {
    const nonce = crypto.getRandomValues(new Uint8Array(12));
    const encrypted = await crypto.subtle.encrypt(
      { name: 'AES-GCM', iv: nonce, tagLength: 128 },
      this.encryptionKey,
      plaintextBytes
    );
    
    return { v: '2.0', alg: 'AES-256-GCM-ARGON2ID', nonce, ct: encrypted };
  }
}
```

### Key Features Summary

| Feature | Implementation |
|---------|----------------|
| **Client-Side Encryption** | AES-256-GCM with WebCrypto API |
| **Key Derivation** | Argon2id with adaptive parameters (OWASP 2024) |
| **Zero-Knowledge Auth** | Auth hash verification (password never sent) |
| **Hardware Acceleration** | WebCrypto API uses native crypto hardware |
| **Batch Operations** | Parallel encrypt/decrypt with Promise.all |
| **Secure Password Generator** | Crypto-random values with character requirements |
| **Compression** | Gzip for large payloads (10-50% reduction) |
| **Session Management** | Auto-lock with configurable timeout |
| **Secure Memory Clearing** | Keys wiped on lock/logout |
| **Legacy Support** | Backward compatible with v1 format |

### Encryption Package Format

```json
{
  "v": "2.0",
  "alg": "AES-256-GCM-ARGON2ID",
  "nonce": "base64-encoded-12-bytes",
  "ct": "base64-encoded-ciphertext-with-auth-tag",
  "compressed": true,
  "ts": 1699999999999
}
```

---

## ⚡ CRYSTALS-Kyber Optimizations

SecureVault includes an **optimized CRYSTALS-Kyber implementation** with NumPy-accelerated Number Theoretic Transform (NTT) for post-quantum cryptographic operations.

### NTT Optimization Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    OPTIMIZED NTT PIPELINE (Kyber-768)                       │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    PRECOMPUTATION PHASE (Startup)                    │   │
│  │  ┌─────────────────┐  ┌─────────────────┐  ┌──────────────────────┐ │   │
│  │  │ Twiddle Factors │  │ Inverse Factors │  │ Bit-Reversal Table  │ │   │
│  │  │  @lru_cache(1)  │  │  @lru_cache(1)  │  │  @lru_cache(1)      │ │   │
│  │  └─────────────────┘  └─────────────────┘  └──────────────────────┘ │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    │                                        │
│                                    ▼                                        │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    RUNTIME NTT OPERATIONS                            │   │
│  │                                                                      │   │
│  │  Input Polynomial ──► Bit-Reversal ──► Cooley-Tukey FFT ──► NTT     │   │
│  │       (n=256)         (Vectorized)    (NumPy Butterfly)    Domain   │   │
│  │                                                                      │   │
│  │  NTT Domain ──► Gentleman-Sande ──► Bit-Reversal ──► Output         │   │
│  │                  (Inverse NTT)       × n⁻¹ mod q    Polynomial      │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Performance Benchmarks

| Operation | Naive Implementation | Optimized NTT | Speedup |
|-----------|---------------------|---------------|---------|
| **Forward NTT** | ~0.8ms | ~0.1ms | **8x** |
| **Inverse NTT** | ~0.9ms | ~0.12ms | **7.5x** |
| **Key Generation** | ~2ms | ~0.3ms | **6-7x** |
| **Encryption** | ~1.5ms | ~0.2ms | **7-8x** |
| **Batch (100 ops)** | ~150ms | ~15ms | **10x** |

### Kyber Parameters

```python
# CRYSTALS-Kyber-768 NTT Parameters
KYBER_N = 256       # Polynomial degree
KYBER_Q = 3329      # Modulus
KYBER_ZETA = 17     # Primitive 256th root of unity mod q

# Optimizations:
# - Precomputed twiddle factors (forward & inverse)
# - NumPy vectorized butterfly operations
# - Cached bit-reversal permutation
# - Montgomery reduction for modular arithmetic
```

### Implementation Example

```python
# Backend (optimized_ntt.py)
from auth_module.services.optimized_ntt import OptimizedNTT

ntt = OptimizedNTT()

# Forward NTT (polynomial → NTT domain)
ntt_form = ntt.forward_ntt(polynomial)

# Point-wise multiplication (O(n) in NTT domain vs O(n²) naive)
product_ntt = ntt.multiply_ntt(a_ntt, b_ntt)

# Inverse NTT (NTT domain → polynomial)
result = ntt.inverse_ntt(product_ntt)

# Performance metrics
metrics = ntt.get_metrics()
# {'forward_ntt_count': 1000, 'avg_forward_ntt_ms': 0.1, ...}
```

### Hybrid Caching System

```
┌─────────────────────────────────────────────────────────────────┐
│                    KYBER CACHE ARCHITECTURE                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌────────────────┐   ┌────────────────┐   ┌────────────────┐  │
│  │   L1: Memory   │   │   L2: Redis    │   │  L3: Database  │  │
│  │    (LRU)       │   │  (Distributed) │   │  (PostgreSQL)  │  │
│  │   TTL: 5min    │──►│   TTL: 1hr     │──►│  Persistent    │  │
│  │   ~1000 keys   │   │   Shared       │   │   Backup       │  │
│  └────────────────┘   └────────────────┘   └────────────────┘  │
│                                                                 │
│  Cached Items:                                                  │
│  • Public keys (user_id → public_key)                          │
│  • Session shared secrets (session_id → shared_secret)         │
│  • Key validation results (key_hash → is_valid)                │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🔐 Fully Homomorphic Encryption (FHE)

SecureVault implements **Fully Homomorphic Encryption** to enable server-side computations on encrypted data without ever decrypting it.

### FHE Architecture

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                         FHE ARCHITECTURE                                         │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │                           CLIENT (Browser)                               │   │
│  │  ┌─────────────────┐   ┌──────────────────┐   ┌──────────────────────┐  │   │
│  │  │ TFHE-rs WASM    │   │ Key Management   │   │ Simulated FHE        │  │   │
│  │  │ (WebAssembly)   │   │ (IndexedDB)      │   │ (Fallback Mode)      │  │   │
│  │  │                 │   │                  │   │                      │  │   │
│  │  │ • Key Gen       │   │ • Client Keys    │   │ • AES-GCM Encrypt    │  │   │
│  │  │ • Encrypt       │   │ • Public Keys    │   │ • Local Strength     │  │   │
│  │  │ • ZK Proofs     │   │ • Server Keys    │   │ • Cache Results      │  │   │
│  │  └────────┬────────┘   └────────┬─────────┘   └──────────┬───────────┘  │   │
│  │           │                     │                        │              │   │
│  └───────────┼─────────────────────┼────────────────────────┼──────────────┘   │
│              │                     │                        │                   │
│              └─────────────────────┼────────────────────────┘                   │
│                                    │                                            │
│                    HTTPS (Encrypted Ciphertext)                                │
│                                    │                                            │
│  ┌─────────────────────────────────▼────────────────────────────────────────┐  │
│  │                        FHE OPERATION ROUTER                              │  │
│  │  ┌─────────────────────────────────────────────────────────────────────┐ │  │
│  │  │                    Intelligent Tier Selection                       │ │  │
│  │  │                                                                     │ │  │
│  │  │   Budget        Operation        Data Size       Result             │ │  │
│  │  │   Latency  ───> Type      ───>   & Complexity ──> Tier Selection    │ │  │
│  │  │   Memory        Priority         Circuit Depth                      │ │  │
│  │  └─────────────────────────────────────────────────────────────────────┘ │  │
│  └───────────────┬─────────────────────┬────────────────────┬───────────────┘  │
│                  │                     │                    │                   │
│    ┌─────────────▼─────────┐  ┌───────▼────────┐  ┌───────▼──────────┐        │
│    │   TIER 1: CLIENT     │  │ TIER 2: HYBRID │  │ TIER 3: FULL FHE │        │
│    │   (~5ms latency)     │  │ (~50ms latency)│  │ (~500ms latency) │        │
│    ├──────────────────────┤  ├────────────────┤  ├──────────────────┤        │
│    │ • Local computation  │  │• Concrete-Py   │  │ • TenSEAL SEAL   │        │
│    │ • No server needed   │  │• Simple ops    │  │ • Complex ops    │        │
│    │ • Instant response   │  │• Integer arith │  │ • Batch SIMD     │        │
│    └──────────────────────┘  └────────────────┘  └──────────────────┘        │
│                                      │                    │                   │
│                    ┌─────────────────┴────────────────────┘                   │
│                    │                                                          │
│                    ▼                                                          │
│    ┌──────────────────────────────────────────────────────────────────────┐  │
│    │                     REDIS FHE COMPUTATION CACHE                      │  │
│    │  ┌────────────────────────────────────────────────────────────────┐  │  │
│    │  │  Operation Hash ──> Cached Result (TTL: 1 hour)                │  │  │
│    │  │  • Avoid redundant FHE computations                            │  │  │
│    │  │  • 10x performance improvement for repeated operations         │  │  │
│    │  └────────────────────────────────────────────────────────────────┘  │  │
│    └──────────────────────────────────────────────────────────────────────┘  │
│                                                                                │
└────────────────────────────────────────────────────────────────────────────────┘
```

### FHE Encryption Tiers

| Tier | Name | Latency | Use Case | Technology |
|------|------|---------|----------|------------|
| 1 | Client Only | ~5ms | Real-time typing feedback | Local JS |
| 2 | Hybrid FHE | ~50ms | Password strength check | Concrete-Python |
| 3 | Full FHE | ~500ms | Encrypted search, batch ops | TenSEAL (SEAL) |
| 4 | Cached FHE | ~1ms | Repeated operations | Redis cache |

### FHE Password Strength Flow

```mermaid
sequenceDiagram
    participant U as User
    participant C as Client (Browser)
    participant R as FHE Router
    participant F as FHE Service
    participant CA as Redis Cache

    U->>C: Type password
    
    Note over C: Client-side FHE encryption
    C->>C: Generate/load FHE keys from IndexedDB
    C->>C: Encrypt password with TFHE
    
    C->>R: POST /api/fhe/strength-check/
    Note right of C: {encrypted_password, budget, metadata}
    
    R->>CA: Check cache (operation hash)
    
    alt Cache Hit
        CA->>R: Return cached result
        R->>C: Encrypted strength score
    else Cache Miss
        R->>R: Evaluate computational budget
        R->>R: Select optimal tier
        
        alt Tier 2: Hybrid
            R->>F: Route to Concrete-Python
            F->>F: FHE strength computation
        else Tier 3: Full FHE
            R->>F: Route to TenSEAL
            F->>F: SIMD batch computation
        end
        
        F->>CA: Cache result
        F->>R: Return encrypted score
        R->>C: Encrypted strength score
    end
    
    C->>C: Decrypt result with client key
    C->>U: Display strength meter
    
    Note over C,F: Server NEVER sees plaintext password!
```

### FHE Key Management

```javascript
// Client-side FHE key generation (fheService.js)
async initialize() {
  // Load or generate TFHE keys
  const cachedKeys = await fheKeyManager.loadKeys();
  
  if (!cachedKeys) {
    // Generate new FHE keypair
    this.clientKey = await tfhe.TfheClientKey.generate();
    this.publicKey = await tfhe.TfhePublicKey.new(this.clientKey);
    this.serverKey = await tfhe.TfheCompressedServerKey.new(this.clientKey);
    
    // Cache in IndexedDB (encrypted with device key)
    await fheKeyManager.saveKeys({
      clientKey: this.clientKey,
      publicKey: this.publicKey,
      serverKey: this.serverKey,
      createdAt: Date.now(),
    });
  }
}
```

### FHE Integration with Vault

The vault model includes FHE-specific columns for encrypted operations:

```python
class EncryptedVaultItem(models.Model):
    # ... standard fields ...
    
    # FHE fields for server-side computation
    fhe_password = models.BinaryField(
        null=True,
        help_text="FHE encrypted password (SEAL CKKS ciphertext)"
    )
    encrypted_domain_hash = models.BinaryField(
        null=True,
        help_text="Encrypted domain hash for FHE search"
    )
    cached_strength_score = models.FloatField(
        null=True,
        help_text="Cached FHE-computed strength score"
    )
    fhe_last_computed = models.DateTimeField(
        null=True,
        help_text="Last FHE computation timestamp"
    )
```

---

## ⚙️ Backend Optimizations

SecureVault v2.0 includes comprehensive backend optimizations for performance and scalability.

### Optimization Components

| Component | File | Purpose |
|-----------|------|---------|
| **VaultCacheManager** | `vault_optimization_service.py` | Multi-level caching (L1 + L2) |
| **VaultQueryOptimizer** | `vault_optimization_service.py` | Query optimization with select_related |
| **VaultCompression** | `vault_optimization_service.py` | Gzip compression utilities |
| **AuthHashService** | `vault_optimization_service.py` | Zero-knowledge auth verification |
| **VaultCompressionMiddleware** | `compression_middleware.py` | Gzip/Brotli response compression |
| **Celery Tasks** | `vault/tasks.py` | Background processing |

### Multi-Level Caching

```python
# VaultCacheManager - L1 (Memory) + L2 (Redis/Django cache)
class VaultCacheManager:
    # Cache TTLs
    TTL_SALT = 300      # 5 minutes
    TTL_STATS = 60      # 1 minute
    TTL_FOLDERS = 300   # 5 minutes
    TTL_AUTH = 600      # 10 minutes
    
    # Cached (non-sensitive):
    # - User salt
    # - Item counts and statistics
    # - Folder structure
    # - Auth hash (double-hashed)
    
    # NOT cached (for security):
    # - Encrypted data blobs
    # - Authentication tokens
```

### Query Optimization

```python
# VaultQueryOptimizer - Optimized queries
def get_optimized_queryset(user, item_type=None, favorites_only=False):
    return EncryptedVaultItem.objects.filter(
        user=user,
        deleted=False
    ).select_related('folder')  # Reduces N+1 queries
     .only('id', 'item_id', 'item_type', ...)  # Selective fields
     .order_by('-updated_at')  # Uses index

def get_metadata_only_queryset(user):
    # Returns items WITHOUT encrypted_data for listing
    # Reduces payload size by ~90%
    return EncryptedVaultItem.objects.filter(
        user=user, deleted=False
    ).only('id', 'item_id', 'item_type', 'favorite', 
           'folder_id', 'created_at', 'updated_at')
```

### Response Compression Middleware

```python
# compression_middleware.py
class VaultCompressionMiddleware:
    MIN_SIZE_FOR_COMPRESSION = 1024  # Compress if > 1KB
    
    # Supports Brotli (better) and Gzip (fallback)
    # Automatically selects based on Accept-Encoding
    # Typical compression: 10-50% reduction
    
    COMPRESSIBLE_CONTENT_TYPES = [
        'application/json',
        'text/html',
        'text/plain',
        'application/javascript',
    ]
```

### Celery Background Tasks

| Task | Purpose | Schedule |
|------|---------|----------|
| `process_audit_log` | Async audit logging | On-demand |
| `warm_user_cache` | Pre-warm cache after login | On-demand |
| `invalidate_user_cache` | Clear cache on logout | On-demand |
| `cleanup_old_audit_logs` | Delete old logs | Daily 2 AM |
| `cleanup_deleted_items` | Purge soft-deleted items | Weekly Sunday 3 AM |
| `compute_user_statistics` | Generate vault stats | On-demand |
| `check_breach_status` | HIBP API check (k-anonymity) | Rate-limited |
| `prepare_export` | Prepare encrypted export | On-demand |

### Performance Improvements Summary

| Optimization | Before | After | Improvement |
|--------------|--------|-------|-------------|
| **Query Response** | ~200ms | ~20ms | **10x faster** |
| **API Payload Size** | 100KB | 55KB | **45% smaller** |
| **Cache Hit Rate** | 0% | ~85% | **Reduced DB load** |
| **List Items (metadata)** | ~500ms | ~50ms | **10x faster** |
| **Compression Ratio** | - | 10-50% | **Bandwidth savings** |

### Security Headers Middleware

```python
# SecurityHeadersMiddleware adds:
response['X-Content-Type-Options'] = 'nosniff'
response['X-Frame-Options'] = 'DENY'
response['X-XSS-Protection'] = '1; mode=block'
response['Referrer-Policy'] = 'strict-origin-when-cross-origin'
response['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
response['Permissions-Policy'] = 'geolocation=(), microphone=(), camera=()'
```

### Cache Control for Vault Endpoints

```python
# CacheControlMiddleware
NO_CACHE_PATHS = ['/api/vault/', '/api/auth/', '/api/kyber/']

# Sensitive endpoints get:
'Cache-Control': 'no-store, no-cache, must-revalidate, private'
'Pragma': 'no-cache'
'Expires': '0'

# Static files get:
'Cache-Control': 'public, max-age=31536000, immutable'
```

---

## 🔑 Authentication & Authorization

### Authentication Methods Supported

```
┌─────────────────────────────────────────────────────────────────────┐
│                    AUTHENTICATION METHODS                            │
├─────────────────┬──────────────────────┬────────────────────────────┤
│   PASSWORD      │      PASSKEY         │         OAUTH 2.0          │
│   + MFA         │    (WebAuthn)        │       (Social Login)       │
├─────────────────┼──────────────────────┼────────────────────────────┤
│ • Email + Pass  │ • FIDO2 Compliant    │ • Google                   │
│ • TOTP (6-dig)  │ • Biometric          │ • GitHub                   │
│ • SMS Code      │ • Hardware Key       │ • Apple                    │
│ • Email Code    │ • Cross-Platform     │ • Microsoft (coming)       │
│ • Push Notif    │ • Passwordless       │ • Auto-provision user      │
└─────────────────┴──────────────────────┴────────────────────────────┘
```

### JWT Authentication Flow

```mermaid
sequenceDiagram
    participant U as User
    participant C as Client
    participant A as Auth Server
    participant R as Resource Server

    U->>C: Login (email + password)
    C->>C: Hash password (Argon2id)
    C->>A: POST /api/auth/token/ {email, auth_hash}
    
    A->>A: Verify credentials
    A->>A: Check MFA requirement
    
    alt MFA Required
        A->>C: {requires_mfa: true, mfa_token}
        C->>U: Request MFA code
        U->>C: Enter TOTP code
        C->>A: POST /api/auth/mfa/verify/ {mfa_token, code}
        A->>A: Verify TOTP
    end
    
    A->>A: Generate JWT tokens
    A->>C: {access_token, refresh_token, expires_in}
    
    C->>C: Store tokens securely
    
    Note over C,R: Subsequent API Requests
    
    C->>R: GET /api/vault/items/ + Authorization: Bearer {access_token}
    R->>R: Verify JWT signature
    R->>R: Check token expiry
    R->>R: Extract user claims
    R->>C: Return protected resource
    
    Note over C,A: Token Refresh
    
    C->>A: POST /api/auth/token/refresh/ {refresh_token}
    A->>A: Verify refresh token
    A->>C: {access_token, expires_in}
```

### WebAuthn/Passkey Authentication Flow

```mermaid
sequenceDiagram
    participant U as User
    participant B as Browser
    participant S as Server
    participant A as Authenticator

    Note over U,A: Registration Flow
    
    U->>B: Click "Register Passkey"
    B->>S: POST /api/auth/passkey/register/begin/
    S->>S: Generate challenge
    S->>S: Create user handle
    S->>B: {challenge, rp, user, pubKeyCredParams}
    
    B->>A: navigator.credentials.create(options)
    A->>U: Biometric/PIN prompt
    U->>A: Verify identity
    A->>A: Generate key pair
    A->>B: PublicKeyCredential {id, rawId, attestationObject}
    
    B->>S: POST /api/auth/passkey/register/complete/
    S->>S: Verify attestation
    S->>S: Store public key + credential ID
    S->>B: {success: true, passkey_id}
    
    Note over U,A: Authentication Flow
    
    U->>B: Click "Login with Passkey"
    B->>S: POST /api/auth/passkey/authenticate/begin/
    S->>S: Generate challenge
    S->>B: {challenge, allowCredentials}
    
    B->>A: navigator.credentials.get(options)
    A->>U: Biometric/PIN prompt
    U->>A: Verify identity
    A->>A: Sign challenge with private key
    A->>B: PublicKeyCredential {authenticatorData, signature}
    
    B->>S: POST /api/auth/passkey/authenticate/complete/
    S->>S: Verify signature with stored public key
    S->>S: Generate JWT tokens
    S->>B: {access_token, refresh_token}
```

### Authorization (RBAC)

```
┌─────────────────────────────────────────────────────────────────────┐
│                    ROLE-BASED ACCESS CONTROL                         │
├─────────────────┬───────────────────────────────────────────────────┤
│      ROLE       │                  PERMISSIONS                       │
├─────────────────┼───────────────────────────────────────────────────┤
│  Owner          │ Full control: create, read, update, delete,       │
│                 │ share, manage members, transfer ownership         │
├─────────────────┼───────────────────────────────────────────────────┤
│  Admin          │ Manage: read, update, delete, share, add members  │
├─────────────────┼───────────────────────────────────────────────────┤
│  Member         │ Contribute: read, create, update own items        │
├─────────────────┼───────────────────────────────────────────────────┤
│  Viewer         │ Read-only: view items, no modifications           │
└─────────────────┴───────────────────────────────────────────────────┘
```

---

## 🔄 Passkey Recovery System

SecureVault implements a **two-tier passkey recovery system** that balances security with usability.

### Recovery System Architecture

```
┌─────────────────────────────────────────────────────────┐
│              USER LOSES PASSKEY                          │
└──────────────────────┬──────────────────────────────────┘
                       │
              ┌────────▼────────┐
              │  TRY PRIMARY    │
              │  RECOVERY       │──────────> Has Recovery Key?
              └────────┬────────┘                  │
                       │              ┌────────────┴────────────┐
                       │             YES                        NO
                       │              │                         │
                       ▼              │                         │
          ┌───────────────────┐       │                         │
          │ Enter Recovery    │<──────┘                         │
          │ Key & Decrypt     │                                 │
          └─────────┬─────────┘                                 │
                    │                                           │
               Success?─────────────> NO ───────────────────────┤
                  │                                             │
                 YES                                            │
                  │                                             ▼
                  │                  ┌─────────────────────────────────┐
                  │                  │    FALLBACK TO SOCIAL MESH      │
                  │                  │    (3-7 days verification)      │
                  │                  │                                 │
                  │                  │  ┌─────────────────────────┐    │
                  │                  │  │ Behavioral DNA Capture │    │
                  │                  │  │ (247 dimensions)        │    │
                  │                  │  └───────────┬─────────────┘    │
                  │                  │              │                  │
                  │                  │  ┌───────────▼─────────────┐    │
                  │                  │  │ Temporal Challenges     │    │
                  │                  │  │ (Distributed over days) │    │
                  │                  │  └───────────┬─────────────┘    │
                  │                  │              │                  │
                  │                  │  ┌───────────▼─────────────┐    │
                  │                  │  │ Guardian Approvals      │    │
                  │                  │  │ (Threshold: 3 of 5)     │    │
                  │                  │  └───────────┬─────────────┘    │
                  │                  │              │                  │
                  │                  │  ┌───────────▼─────────────┐    │
                  │                  │  │ Trust Score ≥ 0.85      │    │
                  │                  │  └───────────┬─────────────┘    │
                  │                  └──────────────┼──────────────────┘
                  │                                 │
                  └────────────────┬────────────────┘
                                   │
                          ┌────────▼────────┐
                          │    PASSKEY      │
                          │    RESTORED     │
                          └─────────────────┘
```

### Primary Recovery Flow (Instant)

```mermaid
sequenceDiagram
    participant U as User
    participant C as Client
    participant S as Server
    participant K as KeyStore

    Note over U,K: Setup Phase (During Account Creation)
    
    U->>C: Register passkey
    C->>C: Generate passkey keypair
    C->>S: Store public key
    
    U->>C: Enable primary recovery
    S->>S: Generate 24-char recovery key
    S->>S: Hash recovery key (Argon2id)
    
    C->>C: Encrypt passkey private material
    C->>C: Key = KDF(recovery_key)
    
    C->>S: Store encrypted backup
    S->>K: {encrypted_passkey, key_hash, metadata}
    S->>C: Display recovery key (ONE TIME ONLY!)
    C->>U: "Write down your recovery key"
    
    Note over U,K: Recovery Phase
    
    U->>C: Lost passkey, initiate recovery
    C->>S: POST /api/auth/passkey-recovery/initiate/
    S->>S: Verify user identity (email)
    S->>C: {backup_exists: true, challenge}
    
    U->>C: Enter recovery key
    C->>S: POST /api/auth/passkey-recovery/complete/
    S->>S: Verify recovery key hash
    S->>K: Fetch encrypted backup
    K->>S: {encrypted_passkey_data}
    
    C->>C: Derive decryption key
    C->>C: Decrypt passkey material
    C->>C: Re-register passkey
    
    C->>S: Store new passkey credential
    S->>C: {success: true, new_passkey_id}
    C->>U: "Passkey restored!"
```

### Social Mesh Recovery Flow (Fallback)

```mermaid
sequenceDiagram
    participant U as User
    participant C as Client
    participant S as Server
    participant G as Guardians
    participant B as Blockchain

    Note over U,B: Recovery Initiation
    
    U->>C: Initiate social mesh recovery
    C->>S: POST /api/behavioral-recovery/initiate/
    
    S->>S: Verify behavioral commitments exist
    S->>S: Create recovery attempt
    S->>B: Verify commitment on chain
    
    S->>C: {attempt_id, timeline, first_challenge}
    
    Note over U,B: Phase 1: Behavioral Verification (Days 1-3)
    
    loop Each Challenge (5 total)
        S->>C: Temporal challenge (randomized timing)
        C->>U: Display challenge
        
        Note over C: Capture behavioral biometrics
        C->>C: Keystroke dynamics
        C->>C: Mouse movement patterns
        C->>C: Cognitive patterns
        
        U->>C: Submit answer
        C->>S: {answer, behavioral_data}
        
        S->>S: Verify answer
        S->>S: Analyze behavioral match
        S->>S: Update trust score
    end
    
    Note over U,B: Phase 2: Guardian Verification (Days 3-7)
    
    S->>G: Send approval requests
    
    par Guardian 1
        G->>S: Approve + verification
    and Guardian 2
        G->>S: Approve + video call
    and Guardian 3
        G->>S: Approve
    end
    
    S->>S: Check threshold (3 of 5)
    
    Note over U,B: Phase 3: Secret Reconstruction
    
    S->>S: Calculate final trust score
    
    alt Trust Score ≥ 0.85
        S->>S: Collect recovery shards (Shamir SSS)
        S->>S: Reconstruct passkey secret
        S->>C: Return decrypted passkey material
        C->>C: Re-register passkey
        C->>U: "Passkey restored!"
    else Trust Score < 0.85
        S->>C: Recovery denied
        S->>S: Log security event
        S->>U: Alert: suspicious recovery attempt
    end
```

### Behavioral DNA Capture (247 Dimensions)

```
┌─────────────────────────────────────────────────────────────────────┐
│                    BEHAVIORAL DNA VECTORS                            │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  TYPING DYNAMICS (60 dimensions)                                    │
│  ├── Key press duration (down-up time)                              │
│  ├── Inter-key latency (key-to-key timing)                          │
│  ├── Typing rhythm and cadence patterns                             │
│  ├── Error correction patterns                                      │
│  ├── Shift key usage timing                                         │
│  ├── Backspace frequency and timing                                 │
│  └── Caps lock vs shift preference                                  │
│                                                                      │
│  MOUSE BIOMETRICS (50 dimensions)                                   │
│  ├── Velocity curves and acceleration                               │
│  ├── Movement trajectory characteristics                            │
│  ├── Click timing patterns                                          │
│  ├── Scroll wheel behavior                                          │
│  ├── Hover-before-click duration                                    │
│  ├── Mouse jitter patterns (micro-movements)                        │
│  └── Directional preference (diagonal vs cardinal)                  │
│                                                                      │
│  COGNITIVE PATTERNS (45 dimensions)                                 │
│  ├── Decision-making speed                                          │
│  ├── UI navigation sequences                                        │
│  ├── Feature usage frequency                                        │
│  ├── Time-of-day activity patterns                                  │
│  ├── Session duration preferences                                   │
│  └── Multi-tasking behavior                                         │
│                                                                      │
│  DEVICE INTERACTION (50 dimensions)                                 │
│  ├── Screen interaction patterns                                    │
│  ├── Swipe velocity and curve                                       │
│  ├── Device orientation preferences                                 │
│  ├── App switching patterns                                         │
│  └── Notification interaction timing                                │
│                                                                      │
│  SEMANTIC BEHAVIORS (42 dimensions)                                 │
│  ├── Password creation patterns                                     │
│  ├── Vault organization methodology                                 │
│  ├── Search query formulation style                                 │
│  ├── Entry editing patterns                                         │
│  └── Copy-paste behavior                                            │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 🔓 Master Password Recovery

### Recovery Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│               MASTER PASSWORD RECOVERY SYSTEM                        │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│   ┌─────────────────┐          ┌─────────────────────────────────┐  │
│   │  RECOVERY KEY   │          │     EMERGENCY ACCESS            │  │
│   │  (Primary)      │          │     (Trusted Contacts)          │  │
│   ├─────────────────┤          ├─────────────────────────────────┤  │
│   │ • 24-char key   │          │ • Designated trustees           │  │
│   │ • User-stored   │          │ • Waiting period (24-72h)       │  │
│   │ • Instant       │          │ • Owner can cancel              │  │
│   │ • One-time use  │          │ • Audit trail                   │  │
│   └────────┬────────┘          └───────────────┬─────────────────┘  │
│            │                                    │                    │
│            └────────────────┬───────────────────┘                    │
│                             │                                        │
│                    ┌────────▼────────┐                              │
│                    │  VAULT ACCESS   │                              │
│                    │  RESTORED       │                              │
│                    └─────────────────┘                              │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

### Recovery Key Flow

```mermaid
sequenceDiagram
    participant U as User
    participant C as Client
    participant S as Server
    participant V as Vault

    Note over U,V: Setup Phase
    
    U->>C: Enable recovery key
    C->>C: Generate recovery key (256-bit)
    C->>C: Derive vault key from master password
    C->>C: Re-encrypt vault key with recovery key
    
    C->>S: Store encrypted vault key backup
    S->>V: {user_id, encrypted_vault_key, recovery_key_hash}
    
    C->>U: Display recovery key (SAVE THIS!)
    
    Note over U,V: Recovery Phase
    
    U->>C: Forgot master password
    C->>S: POST /api/auth/validate-recovery-key/
    S->>S: Verify email ownership
    S->>C: {recovery_enabled: true}
    
    U->>C: Enter recovery key
    C->>S: POST /api/auth/reset-with-recovery-key/
    S->>S: Verify recovery key hash
    S->>V: Fetch encrypted vault key
    V->>S: {encrypted_vault_key}
    S->>C: Return encrypted vault key
    
    C->>C: Decrypt vault key with recovery key
    
    U->>C: Enter new master password
    C->>C: Re-encrypt vault key with new password
    C->>S: Update encrypted vault key
    
    C->>U: "Password reset successful!"
```

### Emergency Access Flow

```mermaid
sequenceDiagram
    participant O as Owner
    participant T as Trusted Contact
    participant S as Server
    participant V as Vault

    Note over O,V: Setup Phase
    
    O->>S: Add emergency contact
    S->>T: Send invitation email
    T->>S: Accept invitation
    S->>S: Store emergency contact relationship
    
    Note over O,V: Emergency Access Request
    
    T->>S: Request emergency access
    S->>S: Start waiting period timer
    S->>O: Send notification (email + push)
    
    Note over O,V: Waiting Period (24-72 hours)
    
    alt Owner Cancels
        O->>S: Cancel emergency access
        S->>T: Access denied notification
    else Waiting Period Expires
        S->>S: Auto-approve access
        S->>T: Access granted notification
        
        T->>S: GET /api/user/emergency-vault/{request_id}/
        S->>S: Verify access grant
        S->>V: Fetch vault items (read-only)
        V->>S: {encrypted_items}
        S->>T: Return vault data
        
        Note over T: Limited time access (24h default)
    end
```

---

## 🔌 API Documentation

### API Base URLs

```
Development:  http://localhost:8000/api/
Production:   https://api.securevault.com/api/
WebSocket:    wss://api.securevault.com/ws/
```

### Complete API Structure

```
/api/
├── auth/                              # Authentication (25+ endpoints)
│   ├── POST   register/               # User registration
│   ├── POST   login/                  # User login
│   ├── POST   logout/                 # User logout
│   ├── token/
│   │   ├── POST   /                   # Obtain JWT tokens
│   │   ├── POST   refresh/            # Refresh access token
│   │   └── POST   verify/             # Verify token validity
│   ├── passkey/
│   │   ├── POST   register/begin/     # Start passkey registration
│   │   ├── POST   register/complete/  # Complete passkey registration
│   │   ├── POST   authenticate/begin/ # Start passkey auth
│   │   └── POST   authenticate/complete/
│   ├── passkeys/
│   │   ├── GET    /                   # List user's passkeys
│   │   ├── DELETE {id}/               # Delete passkey
│   │   ├── PUT    {id}/rename/        # Rename passkey
│   │   └── GET    status/             # Passkey status
│   ├── oauth/
│   │   ├── GET    providers/          # List OAuth providers
│   │   ├── POST   google/             # Google OAuth
│   │   ├── POST   github/             # GitHub OAuth
│   │   └── POST   apple/              # Apple OAuth
│   ├── oidc/                          # OpenID Connect (Enterprise SSO) ⭐
│   │   ├── GET    .well-known/openid-configuration  # OIDC Discovery
│   │   ├── GET    .well-known/jwks.json             # JSON Web Key Set
│   │   ├── GET    providers/          # List OIDC providers (Okta/Azure/Auth0)
│   │   ├── POST   authorize/          # Initiate OIDC auth flow
│   │   ├── GET    callback/           # Handle OIDC callback
│   │   ├── POST   token/              # Exchange code for tokens
│   │   ├── GET    userinfo/           # Get authenticated user info
│   │   └── POST   validate-token/     # Validate ID token
│   ├── mfa/
│   │   ├── POST   biometric/face/register/
│   │   ├── POST   biometric/voice/register/
│   │   ├── POST   biometric/authenticate/
│   │   ├── POST   assess-risk/        # Adaptive MFA
│   │   ├── GET    factors/            # Available MFA factors
│   │   └── POST   verify/             # Verify MFA code
│   ├── passkey-recovery/
│   │   ├── POST   setup/              # Setup primary recovery
│   │   ├── GET    backups/            # List recovery backups
│   │   ├── POST   initiate/           # Start recovery
│   │   ├── POST   complete/           # Complete recovery
│   │   └── GET    status/             # Recovery status
│   ├── POST   setup-recovery-key/     # Setup master password recovery
│   ├── POST   validate-recovery-key/  # Validate recovery key
│   └── POST   reset-with-recovery-key/# Reset password
│
├── vault/                             # Vault Management (20+ endpoints)
│   ├── items/
│   │   ├── GET    /                   # List items (?metadata_only=true)
│   │   ├── POST   /                   # Create item (encrypted blob)
│   │   ├── GET    {id}/               # Get item
│   │   ├── PUT    {id}/               # Update item (encrypted blob)
│   │   └── DELETE {id}/               # Delete item
│   ├── GET    get_salt/               # Get user's salt for key derivation ⭐
│   ├── POST   verify_auth/            # Zero-knowledge auth hash verification ⭐
│   ├── GET    statistics/             # Cached vault statistics ⭐
│   ├── POST   sync/                   # Cross-device sync
│   ├── GET    search/                 # Search vault
│   ├── folders/
│   │   ├── GET    /                   # List folders
│   │   ├── POST   /                   # Create folder
│   │   ├── PUT    {id}/               # Update folder
│   │   └── DELETE {id}/               # Delete folder
│   ├── backups/
│   │   ├── POST   create_backup/      # Create backup
│   │   └── POST   restore_backup/{id}/# Restore backup
│   └── shared-folders/                # Shared folder endpoints
│
├── security/                          # Security Features (12+ endpoints)
│   ├── GET    dashboard/              # Security dashboard
│   ├── GET    score/                  # Security score
│   ├── devices/
│   │   ├── GET    /                   # List devices
│   │   ├── GET    {id}/               # Device details
│   │   ├── POST   {id}/trust/         # Trust device
│   │   └── POST   {id}/untrust/       # Untrust device
│   ├── dark-web/
│   │   ├── GET    /                   # Breach monitoring
│   │   └── POST   scan/               # Manual scan
│   ├── social-accounts/
│   │   ├── GET    /                   # List accounts
│   │   ├── POST   {id}/lock/          # Lock account
│   │   └── POST   {id}/unlock/        # Unlock account
│   ├── GET    health-check/           # Security health
│   └── GET    audit-log/              # Audit log
│
├── user/                              # User Management (10+ endpoints)
│   ├── GET    profile/                # Get profile
│   ├── PUT    profile/                # Update profile
│   ├── GET    preferences/            # Get preferences
│   ├── PUT    preferences/            # Update preferences
│   ├── GET    emergency-access/       # Emergency access settings
│   ├── emergency-contacts/
│   │   ├── GET    /                   # List contacts
│   │   ├── POST   /                   # Add contact
│   │   ├── PUT    {id}/               # Update contact
│   │   └── DELETE /                   # Remove contact
│   ├── POST   emergency-request/      # Request emergency access
│   └── GET    emergency-vault/{id}/   # Access emergency vault
│
├── ml-security/                       # ML Security (10 endpoints) ⭐
│   ├── password-strength/
│   │   ├── POST   predict/            # Predict strength (LSTM)
│   │   ├── POST   predict-fhe/        # FHE encrypted strength check
│   │   └── GET    history/            # Prediction history
│   ├── anomaly/
│   │   └── POST   detect/             # Detect anomaly (Isolation Forest)
│   ├── behavior/
│   │   ├── GET    profile/            # Get behavior profile
│   │   └── PUT    profile/update/     # Update profile
│   ├── threat/
│   │   ├── POST   analyze/            # Analyze threat (CNN-LSTM)
│   │   └── GET    history/            # Threat history
│   ├── POST   session/analyze/        # Batch session analysis
│   └── GET    models/info/            # ML model info
│
├── performance/                       # Performance Monitoring (16 endpoints)
│   ├── GET    summary/                # Performance summary
│   ├── GET    system-health/          # System health
│   ├── GET    endpoints/              # Endpoint performance
│   ├── GET    database/               # Database performance
│   ├── GET    errors/                 # Error summary
│   ├── alerts/
│   │   ├── GET    /                   # List alerts
│   │   ├── POST   {id}/acknowledge/   # Acknowledge alert
│   │   └── POST   {id}/resolve/       # Resolve alert
│   ├── GET    dependencies/           # Dependencies status
│   ├── GET    ml-predictions/         # ML predictions
│   ├── POST   optimize/               # Optimize performance
│   ├── POST   frontend/               # Frontend report
│   └── crypto/
│       ├── POST   generate-key/       # Generate encryption key
│       ├── POST   derive-key/         # Derive key
│       ├── POST   test/               # Test encryption
│       └── GET    info/               # Crypto info
│
├── behavioral-recovery/               # Behavioral Recovery (12 endpoints)
│   ├── POST   initiate/               # Initiate recovery
│   ├── GET    status/{id}/            # Recovery status
│   ├── POST   submit-challenge/       # Submit challenge answer
│   ├── POST   complete/               # Complete recovery
│   ├── POST   setup-commitments/      # Setup behavioral commitments
│   ├── GET    commitments/status/     # Commitment status
│   ├── GET    challenges/{id}/next/   # Get next challenge
│   ├── metrics/
│   │   ├── GET    dashboard/          # Metrics dashboard
│   │   └── GET    summary/            # Metrics summary
│   ├── POST   feedback/               # Submit feedback
│   └── ab-tests/
│       ├── GET    {name}/results/     # A/B test results
│       └── POST   create/             # Create experiments
│
├── blockchain/                        # Blockchain Integration (4 endpoints)
│   ├── GET    verify-commitment/{id}/ # Verify commitment on chain
│   ├── GET    anchor-status/          # Anchoring status
│   ├── POST   trigger-anchor/         # Manual anchor (admin)
│   └── GET    user-commitments/       # User's commitments
│
├── kyber/                             # CRYSTALS-Kyber API (6 endpoints) ⭐
│   ├── POST   keypair/                # Generate Kyber keypair (async)
│   ├── POST   encrypt/                # Hybrid Kyber encryption
│   ├── POST   decrypt/                # Hybrid Kyber decryption
│   ├── POST   batch/                  # Batch encryption operations
│   ├── GET    status/                 # Kyber algorithm status
│   └── GET    metrics/                # NTT performance metrics
│
├── fhe/                               # FHE Operations (8 endpoints) ⭐
│   ├── POST   encrypt/                # Encrypt data with FHE
│   ├── POST   strength-check/         # FHE password strength check
│   ├── POST   batch-strength/         # Batch strength evaluation
│   ├── POST   search/                 # Encrypted search
│   ├── keys/
│   │   ├── POST   generate/           # Generate FHE keys
│   │   └── GET    /                   # Get user's FHE keys
│   ├── GET    status/                 # FHE service status
│   └── GET    metrics/                # FHE operation metrics
│
├── analytics/                         # Analytics (3 endpoints)
│   ├── POST   events/                 # Track events
│   ├── GET    dashboard/              # Analytics dashboard
│   └── GET    journey/                # User journey
│
├── ab-testing/                        # A/B Testing (5 endpoints)
│   ├── GET    /                       # Get experiments & flags
│   ├── POST   metrics/                # Track metric
│   ├── GET    experiments/{name}/results/
│   └── user/
│       ├── GET    experiments/        # User experiments
│       └── GET    flags/              # User feature flags
│
├── email-masking/                     # Email Masking (7 endpoints)
│   ├── aliases/
│   │   ├── GET    /                   # List aliases
│   │   ├── POST   create/             # Create alias
│   │   ├── GET    {id}/               # Alias detail
│   │   ├── POST   {id}/toggle/        # Toggle alias
│   │   └── GET    {id}/activity/      # Alias activity
│   └── providers/
│       ├── GET    /                   # List providers
│       └── POST   configure/          # Configure provider
│
└── health/                            # Health Checks (3 endpoints)
    ├── GET    /                       # Health check
    ├── GET    /api/health/            # API health (Docker/K8s)
    └── GET    /ready/                 # Readiness check

WebSocket Endpoints:
└── /ws/breach-alerts/{user_id}/       # Real-time breach alerts
```

### Authentication Header

```http
Authorization: Bearer <access_token>
```

### Example API Requests

```bash
# Get JWT Token
curl -X POST http://localhost:8000/api/auth/token/ \
  -H "Content-Type: application/json" \
  -d '{"email": "user@example.com", "password": "secure_password"}'

# List Vault Items
curl http://localhost:8000/api/vault/items/ \
  -H "Authorization: Bearer <token>"

# Predict Password Strength
curl -X POST http://localhost:8000/api/ml-security/password-strength/predict/ \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"password": "MyP@ssw0rd123!"}'

# FHE Encrypted Strength Check (password never sent in plaintext)
curl -X POST http://localhost:8000/api/fhe/strength-check/ \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "encrypted_password": "<base64_fhe_ciphertext>",
    "password_length": 14,
    "budget": {"max_latency_ms": 1000, "min_accuracy": 0.9}
  }'

# Get FHE Service Status
curl http://localhost:8000/api/fhe/status/ \
  -H "Authorization: Bearer <token>"

# Zero-Knowledge Auth Verification
curl -X POST http://localhost:8000/api/vault/verify_auth/ \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"auth_hash": "<client-generated-argon2id-hash>"}'

# Get Vault Items (metadata only - faster)
curl http://localhost:8000/api/vault/?metadata_only=true \
  -H "Authorization: Bearer <token>"

# Generate Kyber Keypair
curl -X POST http://localhost:8000/api/kyber/keypair/ \
  -H "Authorization: Bearer <token>"

# Get Kyber Performance Metrics
curl http://localhost:8000/api/kyber/metrics/ \
  -H "Authorization: Bearer <token>"
```

---

## 🚀 Deployment

### Deployment Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                    PRODUCTION DEPLOYMENT                             │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────────────────┐  │
│  │   GitHub    │───>│  GitHub     │───>│   Container Registry    │  │
│  │   Push      │    │  Actions    │    │   (ghcr.io)             │  │
│  └─────────────┘    └─────────────┘    └───────────┬─────────────┘  │
│                                                     │                │
│                           ┌─────────────────────────┘                │
│                           │                                          │
│                           ▼                                          │
│         ┌─────────────────────────────────────────┐                 │
│         │         KUBERNETES CLUSTER              │                 │
│         │                                         │                 │
│         │  ┌───────────────────────────────────┐  │                 │
│         │  │           INGRESS                 │  │                 │
│         │  │   (nginx-ingress + cert-manager)  │  │                 │
│         │  │   SSL/TLS Termination             │  │                 │
│         │  └─────────────┬─────────────────────┘  │                 │
│         │                │                        │                 │
│         │    ┌───────────┼───────────┐           │                 │
│         │    │           │           │           │                 │
│         │    ▼           ▼           ▼           │                 │
│         │  ┌─────┐   ┌───────┐   ┌────────┐     │                 │
│         │  │Front│   │Backend│   │WebSocket│     │                 │
│         │  │ end │   │  API  │   │(Daphne)│     │                 │
│         │  │ x3  │   │  x4   │   │   x2   │     │                 │
│         │  └─────┘   └───────┘   └────────┘     │                 │
│         │                │                       │                 │
│         │    ┌───────────┼───────────┐          │                 │
│         │    │           │           │          │                 │
│         │    ▼           ▼           ▼          │                 │
│         │  ┌─────┐   ┌───────┐   ┌────────┐    │                 │
│         │  │Celery│   │ Redis │   │Postgres│    │                 │
│         │  │Worker│   │ x1    │   │  x1    │    │                 │
│         │  │ x2  │   └───────┘   └────────┘    │                 │
│         │  └─────┘                              │                 │
│         └─────────────────────────────────────────┘                 │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

### Docker Deployment

#### Full Stack Deployment (All Services)

```bash
# Production deployment (all services)
cd docker
cp env.example .env
# Edit .env with production values

# Start all services
docker-compose up -d

# View logs
docker-compose logs -f

# Scale services
docker-compose up -d --scale backend=4 --scale celery-worker=2
```

#### Backend-Only Deployment (Django API)

```bash
# Build backend image
docker build -t password-manager-backend:latest \
  -f docker/backend/Dockerfile .

# Run backend container
docker run -d \
  --name pm-backend \
  -p 8000:8000 \
  -e DEBUG=False \
  -e SECRET_KEY=your-secure-secret-key \
  -e DATABASE_URL=postgresql://user:pass@db-host:5432/dbname \
  -e REDIS_URL=redis://:password@redis-host:6379/0 \
  -e ALLOWED_HOSTS=api.yourdomain.com \
  -e CORS_ALLOWED_ORIGINS=https://yourdomain.com \
  -e OIDC_RP_CLIENT_ID=your-oidc-client-id \
  -e OIDC_RP_CLIENT_SECRET=your-oidc-secret \
  -e OIDC_OP_BASE_URL=https://accounts.google.com \
  password-manager-backend:latest

# Run WebSocket server (Daphne)
docker run -d \
  --name pm-websocket \
  -p 8001:8001 \
  -e DEBUG=False \
  -e SECRET_KEY=your-secure-secret-key \
  -e DATABASE_URL=postgresql://user:pass@db-host:5432/dbname \
  -e REDIS_URL=redis://:password@redis-host:6379/0 \
  password-manager-backend:latest \
  daphne -b 0.0.0.0 -p 8001 password_manager.asgi:application

# Run Celery worker
docker run -d \
  --name pm-celery-worker \
  -e DEBUG=False \
  -e SECRET_KEY=your-secure-secret-key \
  -e DATABASE_URL=postgresql://user:pass@db-host:5432/dbname \
  -e CELERY_BROKER_URL=redis://:password@redis-host:6379/0 \
  password-manager-backend:latest \
  celery -A password_manager worker -l info

# Health check
curl http://localhost:8000/api/health/
```

#### Frontend-Only Deployment (React + Nginx)

```bash
# Build frontend image (production)
docker build -t password-manager-frontend:latest \
  -f docker/frontend/Dockerfile \
  --build-arg VITE_API_BASE_URL=https://api.yourdomain.com \
  --build-arg VITE_WS_URL=wss://ws.yourdomain.com \
  --build-arg VITE_OIDC_ENABLED=true \
  .

# Run frontend container
docker run -d \
  --name pm-frontend \
  -p 80:80 \
  password-manager-frontend:latest

# For development (with hot reload)
docker build -t password-manager-frontend-dev:latest \
  -f docker/frontend/Dockerfile.dev .

docker run -d \
  --name pm-frontend-dev \
  -p 5173:5173 \
  -v $(pwd)/frontend/src:/app/src \
  -e VITE_API_URL=http://localhost:8000 \
  password-manager-frontend-dev:latest

# Health check
curl http://localhost/health
```

#### Docker Compose (Separate Profiles)

```yaml
# docker-compose.yml with profiles
version: '3.8'

services:
  # Backend profile
  backend:
    profiles: ["backend", "full"]
    build:
      context: .
      dockerfile: docker/backend/Dockerfile
    ports:
      - "8000:8000"
    environment:
      - OIDC_RP_CLIENT_ID=${OIDC_RP_CLIENT_ID}
      - OIDC_OP_BASE_URL=${OIDC_OP_BASE_URL}
    # ... other config

  # Frontend profile
  frontend:
    profiles: ["frontend", "full"]
    build:
      context: .
      dockerfile: docker/frontend/Dockerfile
    ports:
      - "80:80"
    # ... other config

# Usage:
# docker-compose --profile backend up -d    # Backend only
# docker-compose --profile frontend up -d   # Frontend only
# docker-compose --profile full up -d       # All services
```

#### Environment Variables for OIDC

```bash
# Required OIDC Configuration (add to .env)
OIDC_RP_CLIENT_ID=your-client-id           # From your IdP (Okta/Azure AD/Auth0)
OIDC_RP_CLIENT_SECRET=your-client-secret   # Keep secret!
OIDC_OP_BASE_URL=https://accounts.google.com  # OpenID Provider URL
OIDC_VERIFY_SSL=True                       # Always True in production
OIDC_USE_NONCE=True                        # Replay attack protection

# For Azure AD:
# OIDC_OP_BASE_URL=https://login.microsoftonline.com/{tenant-id}/v2.0

# For Okta:
# OIDC_OP_BASE_URL=https://{your-org}.okta.com

# For Auth0:
# OIDC_OP_BASE_URL=https://{your-tenant}.auth0.com
```

### FHE Configuration

```bash
# Environment variables for FHE (docker/env.example)
FHE_ENABLED=true                    # Enable/disable FHE operations
FHE_DEFAULT_TIER=hybrid             # Default tier: client_only, hybrid, full_fhe
FHE_MAX_LATENCY_MS=1000            # Max latency for FHE operations
FHE_CACHE_TTL=3600                 # Redis cache TTL for FHE results
VITE_FHE_ENABLED=true              # Frontend FHE toggle
```

### Kubernetes Deployment

```bash
# Create namespace
kubectl apply -f k8s/namespace.yaml

# Create secrets (edit secrets.yaml first!)
kubectl apply -f k8s/secrets.yaml

# Deploy all services
kubectl apply -f k8s/configmap.yaml
kubectl apply -f k8s/deployment.yaml
kubectl apply -f k8s/ingress.yaml
kubectl apply -f k8s/hpa.yaml

# Check status
kubectl get pods -n password-manager
kubectl get services -n password-manager
```

### CI/CD Pipeline

The GitHub Actions workflow (`.github/workflows/ci.yml`) includes:

1. **Testing Stage**
   - Backend tests (pytest + coverage)
   - Frontend tests (vitest)
   - Linting (flake8, ESLint)
   - Security scanning (bandit, safety)

2. **Build Stage**
   - Multi-arch Docker images (amd64, arm64)
   - Push to GitHub Container Registry

3. **Deploy Stage**
   - Staging deployment (automatic on develop branch)
   - Production deployment (manual approval)
   - Rollback capability

4. **Notifications**
   - Slack notifications on success/failure

---

## 📄 File Descriptions

### Backend Files (`password_manager/`)

| File | Description |
|------|-------------|
| `password_manager/settings.py` | Django settings (901 lines) - security configs, CORS, JWT, channels |
| `password_manager/urls.py` | Root URL routing - all API endpoints registered |
| `password_manager/asgi.py` | ASGI config for WebSocket support (Channels) |
| `password_manager/wsgi.py` | WSGI config for Gunicorn |
| `password_manager/throttling.py` | Rate limiting configurations |
| `password_manager/api_utils.py` | Standardized API response utilities |
| `auth_module/views.py` | Core auth endpoints (1403 lines) - register, login, logout |
| `auth_module/passkey_views.py` | WebAuthn/Passkey (587 lines) - FIDO2 implementation |
| `auth_module/mfa_views.py` | Multi-factor auth (790 lines) - TOTP, biometric, push |
| `auth_module/oauth_views.py` | OAuth 2.0 (427 lines) - Google, GitHub, Apple |
| `auth_module/oidc_views.py` | OpenID Connect (OIDC) - Enterprise SSO (Okta, Azure AD, Auth0) ⭐ |
| `auth_module/services/oidc_service.py` | OIDC service - Discovery, JWKS, Token validation ⭐ |
| `auth_module/passkey_primary_recovery_views.py` | Primary recovery (637 lines) |
| `auth_module/quantum_recovery_views.py` | Quantum recovery (1104 lines) - Social mesh |
| `auth_module/quantum_recovery_models.py` | Recovery models (536 lines) |
| `auth_module/quantum_recovery_tasks.py` | Celery tasks (476 lines) |
| `auth_module/services/quantum_crypto_service.py` | Post-quantum crypto service |
| `auth_module/services/kyber_crypto.py` | Kyber-768 implementation |
| `auth_module/services/optimized_ntt.py` | NumPy-optimized NTT (6-8x faster) - Cooley-Tukey FFT |
| `auth_module/services/parallel_kyber.py` | Parallel Kyber ops with ThreadPoolExecutor |
| `auth_module/services/kyber_cache.py` | Hybrid caching (L1 Memory + L2 Redis + L3 DB) |
| `auth_module/services/kyber_monitor.py` | Performance monitoring for Kyber operations |
| `auth_module/kyber_views.py` | Async Django API views for Kyber endpoints |
| `auth_module/services/passkey_primary_recovery_service.py` | Recovery key service |
| `auth_module/services/challenge_generator.py` | Temporal challenge generator |
| `auth_module/services/trust_scorer.py` | Trust scoring algorithm |
| `vault/views/crud_views.py` | Vault CRUD operations |
| `vault/views/api_views.py` | API views with metadata_only, verify_auth, statistics |
| `vault/services/vault_optimization_service.py` | VaultCacheManager, QueryOptimizer, AuthHashService |
| `vault/tasks.py` | Celery tasks (audit, cache, breach check, export) |
| `vault/views/backup_views.py` | Backup & restore functionality |
| `vault/views/folder_views.py` | Folder management |
| `vault/views/shared_folder_views.py` | Shared folders with RBAC |
| `security/views.py` | Security dashboard, device management |
| `security/api/darkWebEndpoints.py` | Dark web monitoring endpoints |
| `security/api/account_protection.py` | Social account protection |
| `ml_security/views.py` | ML security endpoints |
| `ml_security/ml_models/password_strength_model.py` | LSTM password strength |
| `ml_security/ml_models/anomaly_detector.py` | Isolation Forest anomaly detection |
| `ml_security/ml_models/threat_analyzer.py` | CNN-LSTM threat analysis |
| `ml_dark_web/ml_services.py` | BERT breach detection |
| `ml_dark_web/routing.py` | WebSocket routing for breach alerts |
| `behavioral_recovery/views.py` | Behavioral recovery endpoints (726 lines) |
| `behavioral_recovery/models.py` | Behavioral commitment models |
| `behavioral_recovery/services/recovery_orchestrator.py` | Recovery flow orchestration |
| `blockchain/views.py` | Blockchain anchoring endpoints (390 lines) |
| `blockchain/services/blockchain_anchor_service.py` | Merkle tree & Web3 integration |
| `fhe_service/views.py` | FHE API endpoints (663 lines) - encrypt, strength check, search |
| `fhe_service/models.py` | FHE models (287 lines) - keystore, cache, operation logs |
| `fhe_service/services/concrete_service.py` | Concrete-Python FHE operations |
| `fhe_service/services/seal_service.py` | TenSEAL batch SIMD operations |
| `fhe_service/services/fhe_router.py` | Intelligent tier routing (client/hybrid/full FHE) |
| `fhe_service/services/fhe_cache.py` | Redis-based FHE computation cache |
| `fhe_service/services/adaptive_manager.py` | Adaptive circuit depth management |
| `shared/performance_views.py` | Performance monitoring (426 lines) |
| `shared/performance_middleware.py` | Request timing middleware |
| `shared/crypto/` | Server-side cryptographic utilities |
| `analytics/views.py` | Event tracking & analytics |
| `ab_testing/views.py` | A/B testing experiments |
| `email_masking/views.py` | Email alias management |
| `user/views.py` | User profile & emergency access (586 lines) |
| `api/health.py` | Health check endpoints for Docker/K8s |
| `middleware.py` | Security middleware (CORS, headers) |
| `password_manager/compression_middleware.py` | VaultCompressionMiddleware (Gzip/Brotli), SecurityHeadersMiddleware |
| `requirements.txt` | Python dependencies (115+ packages) |

### Frontend Files (`frontend/src/`)

| File | Description |
|------|-------------|
| `App.jsx` | Main React application (1149 lines) - routing, providers |
| `App.css` | Global styles (638 lines) - themes, animations |
| `index.css` | Base CSS (59 lines) - CSS variables |
| `main.jsx` | React entry point (65 lines) |
| `services/api.js` | API client with JWT handling (209 lines) |
| `services/cryptoService.js` | Client-side AES-GCM encryption (454 lines) |
| `services/secureVaultCrypto.js` | **NEW** WebCrypto API encryption (717 lines) - Argon2id, AES-256-GCM |
| `services/secureVaultService.js` | **NEW** Zero-knowledge vault operations (709 lines) |
| `services/xchachaEncryption.js` | XChaCha20-Poly1305 encryption (413 lines) |
| `services/eccService.js` | ECC operations (367 lines) |
| `services/quantum/kyberService.js` | Kyber-768 + X25519 hybrid (1232 lines) |
| `services/quantum/index.js` | Quantum crypto exports |
| `services/fhe/fheService.js` | FHE client service (681 lines) - WASM TFHE, key gen, encryption |
| `services/fhe/fheKeys.js` | FHE key management (604 lines) - IndexedDB storage, rotation |
| `services/fhe/index.js` | FHE module exports |
| `services/vaultService.js` | Vault operations (438 lines) |
| `services/mfaService.js` | MFA client service (583 lines) |
| `services/oauthService.js` | OAuth client (235 lines) |
| `services/oidcService.js` | OpenID Connect service - Enterprise SSO (Okta, Azure AD, Auth0) ⭐ |
| `services/mlSecurityService.js` | ML security client (369 lines) |
| `services/darkWebService.js` | Dark web monitoring client (115 lines) |
| `services/analyticsService.js` | Analytics tracking (734 lines) |
| `services/abTestingService.js` | A/B testing client (639 lines) |
| `services/preferencesService.js` | User preferences (809 lines) |
| `services/performanceMonitor.js` | Frontend performance (528 lines) |
| `services/errorTracker.js` | Error tracking (475 lines) |
| `services/SecureBehavioralStorage.js` | Encrypted IndexedDB storage (373 lines) |
| `services/behavioralCapture/BehavioralCaptureEngine.js` | 247-dim behavioral capture |
| `services/blockchain/` | Web3 blockchain integration |
| `ml/behavioralDNA/index.js` | Behavioral DNA model exports |
| `ml/behavioralDNA/HybridModel.js` | Client/server behavioral switcher |
| `ml/behavioralDNA/BackendAPI.js` | Backend behavioral API client |
| `contexts/BehavioralContext.jsx` | Behavioral profile management |
| `hooks/useAuth.jsx` | Authentication hook |
| `hooks/useSecureVault.js` | **NEW** React hook for vault operations (466 lines) |
| `hooks/useKyber.js` | React hook for Kyber WASM/Web Worker integration |
| `utils/kyber-wasm-loader.js` | Kyber WebAssembly lazy loader |
| `utils/kyber-cache.js` | IndexedDB cache for Kyber keys |
| `workers/kyber-worker.js` | Web Worker for background Kyber ops |
| `Components/auth/Login.jsx` | Login component (174 lines) |
| `Components/auth/PasskeyAuth.jsx` | Passkey authentication (308 lines) |
| `Components/auth/PasskeyRegistration.jsx` | Passkey setup (179 lines) |
| `Components/auth/BiometricAuth.jsx` | Biometric auth (413 lines) |
| `Components/auth/BiometricSetup.jsx` | Biometric enrollment (437 lines) |
| `Components/auth/TwoFactorSetup.jsx` | 2FA configuration (417 lines) |
| `Components/auth/RecoveryKeySetup.jsx` | Recovery key setup (434 lines) |
| `Components/auth/PasswordRecovery.jsx` | Password recovery (636 lines) |
| `Components/auth/PasskeyPrimaryRecoverySetup.jsx` | Primary recovery setup (451 lines) |
| `Components/auth/PasskeyPrimaryRecoveryInitiate.jsx` | Recovery initiation (517 lines) |
| `Components/auth/QuantumRecoverySetup.jsx` | Quantum recovery UI (696 lines) |
| `Components/auth/OAuthCallback.jsx` | OAuth callback handler (334 lines) |
| `Components/auth/SocialLoginButtons.jsx` | Social login UI (98 lines) |
| `Components/sharedfolders/SharedFoldersDashboard.jsx` | Shared folders UI (376 lines) |
| `Components/sharedfolders/CreateFolderModal.jsx` | Create folder modal (368 lines) |
| `Components/sharedfolders/FolderDetailsModal.jsx` | Folder details (590 lines) |
| `Components/sharedfolders/InvitationsModal.jsx` | Invitation management (427 lines) |
| `Components/animations/ParticleBackground.jsx` | Particle animations |

### Mobile App Files (`mobile/`)

| File | Description |
|------|-------------|
| `App.js` | React Native entry point (43 lines) |
| `app.json` | Expo configuration (42 lines) |
| `package.json` | Mobile dependencies (58 packages) |
| `src/` | Mobile source code directory |
| `components/` | Reusable mobile components |
| `app/` | Expo Router app directory |
| `hooks/` | Custom React Native hooks |
| `constants/` | App constants and themes |
| `assets/` | Images, fonts, icons |

### Desktop App Files (`desktop/`)

| File | Description |
|------|-------------|
| `main.js` | Electron main process (557 lines) - window management, IPC |
| `package.json` | Desktop dependencies (78 lines) |
| `src/` | Desktop source code |
| `assets/` | Desktop icons and resources |

### Browser Extension Files (`browser-extension/`)

| File | Description |
|------|-------------|
| `manifest.json` | Extension manifest v3 (46 lines) |
| `webpack.config.js` | Build configuration (54 lines) |
| `package.json` | Extension dependencies (32 lines) |
| `src/` | Extension source code |
| `icons/` | Extension icons (16x16 to 128x128) |

### Smart Contract Files (`contracts/`)

| File | Description |
|------|-------------|
| `contracts/BehavioralCommitmentAnchor.sol` | Solidity contract for Merkle anchoring |
| `hardhat.config.js` | Hardhat configuration (48 lines) - Arbitrum Sepolia |
| `scripts/deploy.js` | Contract deployment script |
| `test/` | Contract test suite |
| `package.json` | Contract dependencies (23 lines) |

### DevOps Files (`docker/`, `k8s/`, `.github/`)

| File | Description |
|------|-------------|
| `docker/backend/Dockerfile` | Backend multi-stage build (115 lines) |
| `docker/backend/entrypoint.sh` | Container entrypoint with migrations |
| `docker/frontend/Dockerfile` | Frontend Nginx image (96 lines) |
| `docker/frontend/Dockerfile.dev` | Development image (27 lines) |
| `docker/frontend/nginx.conf` | Frontend Nginx configuration |
| `docker/frontend/entrypoint.sh` | Runtime env injection |
| `docker/nginx/nginx.conf` | Main reverse proxy config |
| `docker/docker-compose.yml` | Production stack (354 lines) |
| `docker/docker-compose.dev.yml` | Development stack (105 lines) |
| `docker/env.example` | Environment template (92 lines) |
| `k8s/namespace.yaml` | Kubernetes namespace (12 lines) |
| `k8s/configmap.yaml` | Application configuration (49 lines) |
| `k8s/secrets.yaml` | Sensitive credentials (57 lines) |
| `k8s/deployment.yaml` | All deployments (697 lines) |
| `k8s/ingress.yaml` | Ingress with SSL & WebSocket (178 lines) |
| `k8s/hpa.yaml` | Horizontal pod autoscalers (132 lines) |
| `.github/workflows/ci.yml` | CI/CD pipeline (536 lines) |

### Test Files (`tests/`)

| File | Description |
|------|-------------|
| `run_all_tests.py` | Test runner script (440 lines) |
| `fixtures.py` | Test fixtures (634 lines) |
| `utils.py` | Test utilities (665 lines) |
| `test_ml_apis.py` | ML API tests (232 lines) |
| `manual_security_tests.py` | Security tests (742 lines) |
| `behavioral_recovery/` | Behavioral recovery tests |
| `functional/` | Functional test suite |
| `fhe_service/test_concrete_service.py` | Concrete-Python FHE tests (287 lines) |
| `fhe_service/test_seal_service.py` | TenSEAL batch operations tests (375 lines) |
| `fhe_service/test_fhe_router.py` | FHE router tests (323 lines) |
| `fhe_service/test_fhe_cache.py` | Redis FHE cache tests (397 lines) |
| `fhe_service/benchmarks.py` | FHE performance benchmarks (355 lines) |
| `TESTING_GUIDE.md` | Testing documentation (873 lines) |
| `MANUAL_TESTING_GUIDE.md` | Manual test procedures (702 lines) |

### Utility Scripts (`scripts/`)

| File | Description |
|------|-------------|
| `setup_ml_training.bat` | Windows ML setup (78 lines) |
| `setup_ml_training.sh` | Linux/Mac ML setup (77 lines) |
| `setup_behavioral_recovery.bat` | Windows recovery setup |
| `setup_behavioral_recovery.sh` | Linux/Mac recovery setup |

---

## 📊 Implementation Summary (v2.3)

### Client-Side Encryption (Frontend)

| File | Features |
|------|----------|
| `secureVaultCrypto.js` | WebCrypto API for AES-256-GCM, Argon2id with adaptive parameters, hardware acceleration, secure memory clearing, batch operations, password generator |
| `secureVaultService.js` | Zero-knowledge vault ops, client-side encryption before API calls, local decryption cache with TTL, session management with auto-lock, import/export |
| `useSecureVault.js` | React hook for vault operations, state management, activity tracking for timeout, lazy decryption support |

### Backend Optimization (Django)

| File | Features |
|------|----------|
| `vault_optimization_service.py` | VaultCacheManager (L1 + L2), VaultQueryOptimizer (select_related), VaultCompression (Gzip), AuthHashService (zero-knowledge) |
| `vault/tasks.py` | Celery tasks: audit log processing, cache warming/cleanup, statistics computation, breach checking (HIBP API), export preparation |
| `vault/views/api_views.py` | `/verify_auth/` endpoint for zero-knowledge auth, `/statistics/` endpoint for cached vault stats |

### Compression & Caching

| File | Features |
|------|----------|
| `compression_middleware.py` | VaultCompressionMiddleware (Gzip/Brotli 10-50% reduction), SecurityHeadersMiddleware (CSP, HSTS), CacheControlMiddleware |
| `settings.py` | Compression middleware, Celery Beat schedule for vault maintenance, Redis cache backend |

### CRYSTALS-Kyber Optimizations

| File | Features |
|------|----------|
| `optimized_ntt.py` | NumPy-vectorized NTT (6-8x speedup), precomputed twiddle factors, Cooley-Tukey FFT, benchmark utilities |
| `parallel_kyber.py` | ThreadPoolExecutor for batch operations, async wrappers |
| `kyber_cache.py` | Hybrid caching (L1 Memory + L2 Redis + L3 DB), public key caching, session shared secrets |

### Performance Metrics

| Metric | Improvement |
|--------|-------------|
| NTT Transform | ~8x faster |
| Key Generation | ~6-7x faster |
| Encryption | ~7-8x faster |
| Batch Operations | ~10x faster |
| API Response | ~10x faster (with caching) |
| Payload Size | 45% smaller (compression) |
| Cache Hit Rate | ~85% |

---

## ⚙️ Backend Runtime Notes (Django & ML Security)

- **Timezone-aware metrics**: All performance and analytics timestamps now use Django's `timezone.now()`, eliminating naive-datetime warnings when `USE_TZ = True`.
- **Performance monitoring**: `shared/performance_middleware.py` records request and API metrics and may emit `SLOW REQUEST` warnings for genuinely slow endpoints.
- **ML warm-up**: The ML security module (`ml_security`) pre-loads and warms up core models at startup, so the very first call may log a slow request, but subsequent `/api/ml-security/...` requests should be much faster.

## 🤝 Contributing

We welcome contributions! Please see our [Contributing Guide](CONTRIBUTING.md) for details.

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

---

## 📜 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## 🙏 Acknowledgments

- [NIST](https://www.nist.gov/) for post-quantum cryptography standards
- [W3C WebAuthn](https://www.w3.org/TR/webauthn/) for passwordless authentication spec
- [Django](https://www.djangoproject.com/) and [React](https://reactjs.org/) communities
- All open-source contributors

---

<div align="center">

**Built with ❤️ for a more secure digital world**

[Report Bug](https://github.com/yourusername/Password_manager/issues) • [Request Feature](https://github.com/yourusername/Password_manager/issues) • [Documentation](https://docs.securevault.com)

</div>

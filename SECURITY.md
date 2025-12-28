# Security Policy

## 📦 Project
Password Manager Backend & ML Dark Web Monitoring Platform

## 🛡 Supported Versions
Only the **latest main branch** is supported.

| Component | Status |
|---------|-------|
| Django Backend | ✅ Supported |
| ML Dark Web Engine | ✅ Supported |
| Docker Production Image | ✅ Supported |
| Legacy Python (<3.12) | ❌ Not Supported |

---

## 🔐 Dependency Security

### Vulnerability Scanning
We use:
- `pip-audit`
- `safety`

Scans are required:
- Before production releases
- During CI/CD builds
- After dependency upgrades

---

## ⚠️ Accepted & Tracked Risks

### 1️⃣ `ecdsa` – CVE-2024-23342
- **Source:** Indirect dependency via `sendgrid`
- **Severity:** Low
- **Impact:** No direct cryptographic operations performed by application
- **Mitigation:** Monitored upstream, isolated usage
- **Status:** Accepted risk (no upstream fix available)

### 2️⃣ PyTorch packages (`torch`, `torchvision`)
- **Issue:** Cannot be audited via PyPI (CPU wheels)
- **Mitigation:** Installed from official PyTorch distribution
- **Status:** Accepted

---

## 🚨 Reporting a Vulnerability

Please report security issues privately.

**DO NOT** open public GitHub issues for vulnerabilities.

📧 Contact: `security@yourcompany.com`

Include:
- Description
- Reproduction steps
- Impact assessment
- Suggested mitigation (if known)

---

## 🔑 Cryptographic Standards

| Purpose | Library |
|------|--------|
| Password Hashing | Argon2 |
| JWT | PyJWT + SimpleJWT |
| Encryption | cryptography / pycryptodome |
| Post-Quantum (Docker) | liboqs / pqcrypto |
| TLS | OpenSSL (system) |

---

## 🧪 Security Testing

- Rate limiting enforced
- Brute-force protection enabled
- MFA supported
- Token rotation enforced
- HTTPS required in production

---

## 📜 Compliance Alignment
- OWASP ASVS (Level 2)
- OWASP Top 10
- NIST SP 800-53 (partial)
- SLSA Level 2 (dependencies)


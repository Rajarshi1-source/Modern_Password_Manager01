# Security Policy

## 📦 Project
Password Manager Backend & ML Dark Web Monitoring Platform

## 🛡 Supported Versions
Only the **latest main branch** is supported.

| Component | Status |
|---------|-------|
| Django Backend | ✅ Supported |
| ML Dark Web Engine | ✅ Supported |
| Docker Production Image (`docker/backend/Dockerfile`) | ✅ Supported |
| `password_manager/Dockerfile.prod` | ❌ Not Supported — nothing builds it and it has a recorded startup-blocking defect. Not the deployed image. |
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

### 3️⃣ `protobuf` – Recursion Depth DoS (CVE-2024-7254)
- **Source:** Direct dependency (`protobuf` <= 6.33.4)
- **Severity:** Medium (DoS)
- **Issue:** Recursion depth bypass in `google.protobuf.json_format.ParseDict()` allows stack exhaustion via deeply nested `Any` messages.
- **Mitigation:** Input validation on nested structures; monitored for upstream patch.
- **Status:** Accepted risk (Waiting for upstream patch)

### 4️⃣ `ecdsa` – Minerva Timing Attack (CVE-2024-23342)
- **Source:** Indirect dependency via `sendgrid`
- **Severity:** High (Potential Key Leak)
- **Issue:** `ecdsa.SigningKey.sign_digest()` is vulnerable to timing attacks on P-256 curve, potentially leaking nonces.
- **Mitigation:** We do not perform P-256 signing operations directly; dependency usage is limited to non-signing contexts or verified safe paths.
- **Status:** Accepted risk (Upstream considers side-channel out of scope)

### 5️⃣ `nltk` – Model-Artifact Path Traversal (CVE-2026-81726)
- **Source:** Declared in `requirements.txt` under "Security overrides for transitive dependencies" (`nltk>=3.9.4`), pinned `nltk==3.9.4` in `requirements-lock.txt`. The declaration exists only to raise the floor on a version a transitive dependency pulls in — it is not an imported dependency of this codebase.
- **Severity (upstream):** High — the GitHub advisory GHSA-8mgp-746c-j5xp classifies it High. Recorded as the advisory states it, not as this repository experiences it.
- **Severity (residual, this repository):** Medium — the affected model-artifact loaders are unreachable here (see Mitigation), so the arbitrary file read/write cannot be triggered by this codebase. The two lines are kept separate on purpose: collapsing them into one number silently overrides the advisory, and a reader comparing this file against the advisory has no way to tell a considered downgrade from a mistake.
- **CVSS:** 8.3 (CVSS v4.0), vector `CVSS:4.0/AV:N/AC:H/AT:N/PR:N/UI:N/VC:H/VI:L/VA:L/SC:N/SI:N/SA:N`, as published on the GitHub advisory. Recorded verbatim from the advisory, which is also where the High rating above comes from; the Medium below is this repository's own residual judgement and is not a restatement of this score.
- **Issue:** NLTK's model-artifact APIs bypass `pathsec` and can touch files outside their allowed roots. Tracked as PYSEC-2026-3740 / GHSA-8mgp-746c-j5xp.
- **Mitigation:** Unreachable in this codebase — `import nltk`, `from nltk` and `nltk.` return zero matches across `password_manager/`, so none of the affected loaders is ever called, with or without an attacker-controlled path.
- **Status:** Accepted risk (no upstream fix exists — the GHSA range is `introduced: 0` → `last_affected: 3.10.3`, i.e. every published release including the one CI resolves, and pip-audit reports `fix_versions: []`; pinning cannot help). Suppressed in `password_manager/pip-audit-ignores.txt` with a dated expiry, re-evaluated on each renewal.
- **Note:** The PYSEC record for this CVE lists `fixed: 3.10.3` while the GHSA alias does not; pip-audit follows the wider GHSA range. Reading only the PYSEC half would suggest the finding is already resolved and lead to removing a suppression CI still needs.

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


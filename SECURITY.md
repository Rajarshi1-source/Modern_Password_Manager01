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

### Docker Build Context
`.dockerignore` (repo root) and `frontend/.dockerignore` keep local files out of images: `.env` files, private keys, local databases, logs, and virtualenvs. Without them, `COPY password_manager/ .` would bake a developer's `password_manager/.env` into a locally built image, and `load_dotenv()` would load it. Each build context needs its own file, so a new context needs one too.

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
- **Status:** Accepted risk (Upstream considers side-channel out of scope). sendgrid uses ecdsa only to verify Event Webhook signatures with a public key, which holds no secret, and nothing here calls that helper. Suppression (PYSEC-2026-1325) renewed 2026-10-29 to 2026-12-28 in `password_manager/pip-audit-ignores.txt`.

### 5️⃣ `nltk` – Model-Artifact Path Traversal (CVE-2026-81726) — RESOLVED 2026-10-24
- **Advisory:** GHSA-8mgp-746c-j5xp / PYSEC-2026-3740, affecting every nltk release up to 3.10.3.
- **Resolution:** nltk 3.10.4 fixes it; every nltk floor and pin now names 3.10.4, and the suppression was removed from `password_manager/pip-audit-ignores.txt` instead of renewed. Verified with pip-audit (no suppressions) on python:3.12-slim against the `requirements.txt` CI audits.

### 6️⃣ `Twisted` – IMAP LIST Wildcard ReDoS (CVE-2026-106454) — RESOLVED 2026-11-01
- **Advisory:** GHSA-8pqf-f4m5-798g, `twisted.mail.imap4.wildcardToRegexp()` ReDoS (unreachable here: no IMAP service).
- **Resolution:** Twisted 26.10.0 (stable, 2026-10-30) fixes it; every Twisted floor and pin now names 26.10.0, and the suppression was removed from `password_manager/pip-audit-ignores.txt` instead of renewed. PyPI's vulnerability feed lists none for 26.10.0.

### 7️⃣ `Twisted` – 2026-10-23 batch — RESOLVED 2026-11-01
- **Advisories:** CVE-2026-115778 (conch telnet), CVE-2026-115774 (mail IMAP4), CVE-2026-115775 (words XML stream), CVE-2026-115776 (words IRC), CVE-2026-115877 (`twisted.web.http` bare CR/LF in header values, request smuggling) and CVE-2026-83813 (`twisted.names` DNS client accepts an answer from any source address).
- **Resolution:** Fixed in Twisted 26.10.0, the stable release after 26.10.0rc1; the same bump and removal as entry 6.

### 8️⃣ `filelock` – lock-file handling (fixed only in 4.2.1)
- **Source:** Indirect dependency (huggingface-hub, torch, transformers, safety). `safety` 3.8.1, the newest release, requires `filelock<4.0`, so 4.2.1 cannot be installed while `safety` is a runtime requirement.
- **Advisories:** CVE-2026-112940 (`ReadWriteLock` symlink following on Linux), CVE-2026-112913 (the same locks' SQLite side files on Windows), CVE-2026-112907 (soft-lock markers read by path on Windows); and a second batch on 2026-10-29: CVE-2026-112909, -112939, -112935, -112912, -112910, -112938, -112911, -112908, -112936 and -112915 (symlink, hard-link, marker and ACL attacks on lock files).
- **Mitigation:** No code here or in the installed packages uses `ReadWriteLock`; the soft-lock advisory is Windows-only, and the backend runs in Linux containers (huggingface-hub falls back to a soft lock only on filesystems without `flock`). Every advisory in the second batch needs another local account that can create or rename files in the lock's directory; the backend image runs a single non-root account, so there is none inside the container. The model cache (`MLDarkWebConfig.MODELS_DIR`) sits in the application tree. In k8s and `docker/docker-compose.yml` that is the image's own read-only copy, with the pinned model baked in and loaded offline; only the development `docker-compose.yml` bind-mounts it from the host, where only the checkout's owner should be able to write it.
- **Status:** Accepted risk with a short expiry (2026-11-23) in `password_manager/pip-audit-ignores.txt`. Fix by moving `safety` out of the runtime requirements into the CI job that runs it, then raising `filelock` to `>=4.2.1` in every requirements file.

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


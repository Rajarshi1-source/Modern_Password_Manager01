# Dependency Policy (SLSA-Aligned)

## 🎯 Objective
Ensure secure, reproducible, and auditable dependency management.

This project targets **SLSA Level 2** compliance.

---

## 🔗 Dependency Sources

| Type | Policy |
|----|-------|
| PyPI | Allowed |
| GitHub (source builds) | Docker only |
| Local wheels | ❌ Forbidden |
| Unpinned transitive deps | ❌ Forbidden |

---

## 📦 Dependency Classes

### 1️⃣ Runtime Dependencies
- Defined in `requirements-prod.txt`
- Must be pinned or constrained
- Must pass `pip check`

### 2️⃣ Development Dependencies
- Defined in `requirements-dev.txt`
- Never deployed to production

### 3️⃣ ML / Native Dependencies
- Torch, TensorFlow, liboqs
- Installed from official vendors
- Hash verification required in Docker

---

## 🔐 Security Controls

| Control | Required |
|------|--------|
| `pip-audit` | ✅ |
| `safety` | ✅ |
| Hash pinning (Docker) | ✅ |
| Manual CVE triage | ✅ |

---

## ⚠️ Vulnerability Handling

| Severity | Action |
|-------|--------|
| Critical | Immediate fix |
| High | Fix or mitigate |
| Medium | Fix when feasible |
| Low | Track & document |

Accepted risks must be documented in `SECURITY.md`.

---

## 🔄 Update Policy

- Monthly dependency review
- Quarterly lockfile refresh
- Emergency patching for critical CVEs

---

## 🧾 Audit Trail

Artifacts:
- `requirements-lock.txt`
- `pip-audit` reports
- Docker image digests

All builds must be reproducible.

---

## ✅ Compliance Targets

- OWASP Top 10
- NIST 800-53 (partial)
- SLSA Level 2
- SOC 2 readiness (dependency scope)


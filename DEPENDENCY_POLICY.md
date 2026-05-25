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

---

## 🔐 Post-quantum cryptography (liboqs)

### Pinned pairing

The C library and its Python wrapper are released independently and pair
by ABI, not by semver. Both halves MUST be pinned together. Drift breaks
at runtime, not at build time — the symptom is a `ctypes` mis-cast or a
silently truncated buffer in production, not a CI failure.

| Component | Pinned version | Commit SHA | Pinned in |
|---|---|---|---|
| liboqs (C library) | `0.11.0` | `6f30d7ef49ca590979d7a085cd662f00bb6855fe` | `docker/backend/Dockerfile` (`--branch 0.11.0`, asserted via `LIBOQS_COMMIT` ARG) |
| liboqs-python | `0.10.0` | `02198f9c3366cfafdea38a7830b82b9bd78bcb32` | `docker/backend/Dockerfile` (`--branch 0.10.0`, asserted via `LIBOQSPY_COMMIT` ARG) + `requirements-lock.txt` |

The Dockerfile clones by tag (fast, `--depth 1`) AND asserts the
resulting commit SHA matches the value above. If upstream ever
retargets a release tag, the build aborts loudly rather than silently
shipping a different commit.

When bumping either: bump both in the same PR, refresh BOTH the tag
**and** the SHA columns above (verify via `git ls-remote --tags`), run
the full
`security/services/lattice_crypto_engine.py` test suite against a freshly
built image, and confirm `oqs.oqs_version()` and `oqs.oqs_python_version()`
agree at container start.

### Minimal build

`OQS_MINIMAL_BUILD` is restricted to the algorithms that production code
actually instantiates — currently `KEM_kyber_512`, `KEM_kyber_768`, and
`KEM_kyber_1024`. Adding a new algorithm (e.g. Dilithium for signatures)
requires:

1. Extending the semicolon-separated `OQS_MINIMAL_BUILD` list in
   `docker/backend/Dockerfile`.
2. Confirming the algorithm appears on liboqs's constant-time list. Any
   algorithm whose reference implementation is NOT constant-time MUST NOT
   be added without a documented threat model.

### SIMD / runtime dispatch

Production images are compiled with `OQS_DIST_BUILD=ON` +
`OQS_OPT_TARGET=auto`. This produces a single .so that dispatches at
runtime via CPUID:

- **x86_64 with AVX2** → vectorised Kyber polynomial-multiplication path
  (>50% speedup on the dominant hot path versus the portable C build).
- **arm64 with NEON** → vectorised path.
- **Anything else** → constant-time portable fallback.

Production hosts SHOULD expose AVX2 (x86_64) or NEON (arm64). The
fallback is correct but slower; if a deploy target lacks both extensions,
document the choice as an accepted performance risk.

### Hybrid KEX (status)

The recommended posture for a password manager is hybrid lattice + classical
key exchange (e.g. Kyber768 ⊕ X25519), so a flaw in either primitive does
not compromise the session key. **This codebase currently uses Kyber768
alone** in `auth_module/services/kyber_crypto.py`,
`behavioral_recovery/services/quantum_crypto_service.py`, and
`security/services/lattice_crypto_engine.py` — no X25519 mixing layer is
present. A follow-up ticket is required to introduce the hybrid wrapper;
that work is out of scope for the dependency-pinning effort because it
requires browser/mobile changes and a key-derivation design review.

### Scope: optimisations stay in user space

Optimisations to the post-quantum stack MUST stay in user space.
Kernel modules, FPGA drivers, GPU offload (CUDA / ICICLE), and
performance-counter / PMU access patterns are out of scope for this
codebase. Those techniques expand the TCB to kernel ring 0, introduce
hardware-specific deploy requirements, and are designed for
datacenter-scale TLS termination — not a single-user password-manager
workload.

The accepted optimisation lever is liboqs's built-in SIMD dispatch
(see above). The resulting user-space speedup on the polynomial-
multiplication hot path is sufficient for our QPS profile.


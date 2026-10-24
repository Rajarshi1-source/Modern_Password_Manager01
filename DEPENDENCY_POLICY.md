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
| liboqs (C library) | `0.16.0` | `5a1a854b0dc9f2141bdc771c555ee60c37950183` | `docker/backend/Dockerfile` (`--branch 0.16.0`, asserted via `LIBOQS_COMMIT` ARG) |
| liboqs-python | `0.16.0.1` | `62385cd99ababa2a4875257232c68dccda256e3b` | `docker/backend/Dockerfile` (`--branch 0.16.0.1`, asserted via `LIBOQSPY_COMMIT` ARG) + `requirements-lock.txt` |

Upgraded from liboqs `0.11.0` / liboqs-python `0.10.0` on 2026-10-19, together with the
backend's move from round-3 Kyber768 to FIPS 203 ML-KEM-768 (see "Algorithms and stored
data" below). `0.16.0` was the latest liboqs release on that date (no `0.17.0` yet).

The `liboqs-python==0.16.0.1` line in `requirements-lock.txt` documents the image. It is
installable from PyPI, so the `Dependency Compatibility` workflow resolves it as written,
but the image does **not** install it from there: it is built from the pinned tag above.
Do not bump that one line on its own; it would make the lock disagree with the image and
break this pairing rule. `dependabot.yml` ignores the package for that reason.

The Dockerfile clones by tag (fast, `--depth 1`) AND asserts the
resulting commit SHA matches the value above. If upstream ever
retargets a release tag, the build aborts loudly rather than silently
shipping a different commit.

When bumping either: bump both in the same PR (the four `ARG`s at the top of the
Dockerfile), refresh BOTH the tag **and** the SHA columns above (verify via
`git ls-remote --tags`), check `gh api repos/open-quantum-safe/liboqs/security-advisories`
against the algorithms actually compiled in, and update `EXPECTED_KEMS` in
`docker/backend/oqs_smoke.py` if the algorithm list changes.

`docker/backend/oqs_smoke.py` runs at image build time, in the shipped venv: it fails the
build unless `oqs.oqs_version()` and `oqs.oqs_python_version()` equal the pinned tags, the
enabled KEMs are exactly the minimal-build list, each one round-trips, and Kyber768 and
ML-KEM-768 do not interoperate. CI builds the image but never runs it, so this step is
where a broken pairing has to fail. liboqs-python 0.16 reads its version from its own
package metadata, so the Dockerfile installs it with `--target` and copies the
`.dist-info` into the venv along with the package.

### No runtime installs

liboqs-python (0.10 through 0.16.0.1) reacts to a missing C library by running
`git clone` and a CMake build of liboqs at **import time**. Backend code must
therefore import the wrapper only through `shared/oqs_loader.import_oqs()`,
which refuses (ImportError, so the usual fail-closed path applies) unless the
library is already installed. `oqs_smoke.py` checks that the lookup the loader
uses (`ctypes.util.find_library`) finds liboqs in the shipped image.

KEM inputs are length-checked before they reach liboqs: the wrapper copies them
with `ctypes.create_string_buffer(value, length)`, which zero-pads a short value
silently, so a truncated key or ciphertext would otherwise produce a wrong
secret instead of an error.

### Minimal build

`OQS_MINIMAL_BUILD` is restricted to the algorithms that production code
actually instantiates — currently `KEM_ml_kem_512`, `KEM_ml_kem_768`,
`KEM_ml_kem_1024` (all new data), and `KEM_kyber_512`, `KEM_kyber_768`,
`KEM_kyber_1024` (legacy: decrypting data written before the ML-KEM migration,
and `LatticeCryptoEngine` configurations that name `kyber-*`). No signature
scheme is compiled in, which is why the LMS/XMSS advisories against `0.16.0`
(CVE-2026-104254, CVE-2026-104255; fixed in `0.17.0`) do not affect this
image. Adding a new algorithm (e.g. ML-DSA for signatures) requires:

1. Extending the semicolon-separated `OQS_MINIMAL_BUILD` list in
   `docker/backend/Dockerfile`, and `EXPECTED_KEMS` in
   `docker/backend/oqs_smoke.py`.
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

### Algorithms and stored data

FIPS 203 ML-KEM-768 and round-3 Kyber768 have identical key, ciphertext and
secret sizes but are **not interoperable** (FIPS 203 changed key derivation and
implicit rejection), and decapsulating with the wrong one returns a wrong secret
rather than raising. So the backend never infers the KEM from sizes: every
stored artefact records it, and decryption dispatches on that record.

| Artefact | New data | Pre-migration data |
|---|---|---|
| Passkey-primary recovery blob | `version: 3`, `kem: "ML-KEM-768"` (KEM bound into the private-key wrap AAD) | `version: 2`, which implies Kyber768 |
| Recovery shard (`encrypt_shard_hybrid`) | `algorithm: "ML-KEM-768-AES-256-GCM"` | `"Kyber-768-AES-256-GCM"` |
| `HybridKyberEncryption` blob (the `/api/kyber/*` encrypt endpoints and `KyberEncryptedPassword` that used it are retired and deleted) | `"ML-KEM-768-AES256-GCM"` | `"Kyber768-AES256-GCM"` (or no label) |
| `KyberKeyPair.algorithm` | `"ML-KEM-768"` | `"Kyber768"`; encryption to that key keeps using Kyber768 |
| Behavioral embedding, `BehavioralCommitment.encryption_algorithm` | `"ml-kem-768-aes256gcm"` | `"kyber768-aes256gcm"` |
| Cached public key (`kyber:kem-pubkey:<user>`) | `"<KEM>\|<base64>"` | old `kyber:pubkey:` entries are never read |

Kyber768 is legacy: `ProductionKyber` refuses to generate new Kyber768 keys,
while decapsulation of Kyber768 data and encapsulation to an existing Kyber768
public key (a stored `KyberKeyPair`) keep working. liboqs has said since `0.12.0` that Kyber may be removed; if a future
release does remove it, the remaining Kyber768 artefacts above must be re-created
(or re-wrapped) before that upgrade.

### Hybrid KEX (status)

The recommended posture for a password manager is hybrid lattice + classical
key exchange (e.g. ML-KEM-768 ⊕ X25519), so a flaw in either primitive does
not compromise the session key. **This codebase currently uses ML-KEM-768
alone** in `auth_module/services/kyber_crypto.py` and
`behavioral_recovery/services/quantum_crypto_service.py` (ML-KEM-1024 in
`security/services/lattice_crypto_engine.py`) — no X25519 mixing layer is
present.A follow-up ticket is required to introduce the hybrid wrapper;
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


# Post-quantum hybrid architecture review

Status: review, 2026-10-06. No application code was changed by this document.
Companion change: PR #526 (CI lock-file fixes, Dependabot guard).

This document answers three questions, in this order:

1. **What does upgrading liboqs / liboqs-python to the newest release break?**
2. **What does the codebase actually implement today** (Django backend and React
   frontend) for post-quantum and hybrid encryption?
3. **How does that compare with the proposed "ML-KEM-768 + X25519" architecture,
   and which parts of each should be kept?**

Every factual claim below was checked against a primary source (release notes,
repository trees at a tag, the package registries, the installed libraries run
locally, or the code itself). Section 8 lists what was **not** verified.

---

## 1. Summary

| # | Question | Answer |
|---|---|---|
| 1 | Does bumping to liboqs-python `0.16.0.1` (liboqs `0.16.0`) remove `Kyber768`? | **No.** At tag `0.16.0`, `OQS_ENABLE_KEM_KYBER` is `ON` by default and `kyber_512/768/1024` are enabled. The `0.12.0` notice ("last release to include Kyber") has not been carried out as of `0.16.0`. Kyber round 3 remains deprecated and could still be removed later. |
| 2 | What does the bump remove? | Dilithium (removed in liboqs `0.15.0`) and SPHINCS+ (removed in `0.16.0`). **Neither is used anywhere in this codebase.** |
| 3 | Is it safe to just bump the pin in `requirements-lock.txt` (the Copilot suggestion)? | **No, for process reasons, not algorithm reasons.** `DEPENDENCY_POLICY.md` requires the C library and the Python wrapper to move together, with refreshed commit SHAs, in one PR, validated against a freshly built image. The Docker image builds both from pinned git SHAs; the lock line only documents that. A lock-only bump recreates the "lock lies about what is installed" problem the Dockerfile already complains about. |
| 4 | Does the code have problems that exist regardless of any version bump? | **Yes, several, and one is serious:** `behavioral_recovery/services/quantum_crypto_service.py` does `from oqs import KEM`, which does not exist in any liboqs-python version, so that service runs its non-post-quantum fallback even in the Docker image, with only log warnings (the import-time one only when `DEBUG=False`; each fallback operation also logs "NOT QUANTUM-RESISTANT"). See section 3.3. |
| 5 | Does CI protect against a liboqs regression? | **No.** No test job installs the Python wrapper, so `import oqs` fails and the backend selects a *simulated* KEM (log warnings only; the import-time one appears only when `DEBUG=False`). A broken liboqs bump would pass CI. |
| 6 | Is the proposed architecture better than what exists? | **Parts of it are; the whole is not.** Its password handling (never send the master password; one Argon2id run split with HKDF) and its use of standardized ML-KEM are better than the current code. Its single `K_master`, session-level hybrid handshake and storage schema are weaker than, or redundant with, what exists. Section 6. |
| 7 | What is the most valuable post-quantum change? | **Not application-layer.** The master password reaches the server on every login; a recorded TLS session decrypted later reveals it directly. Stop sending it (and do not replace it with a replayable derived value), then enable hybrid post-quantum TLS at the edge. Sections 6-7. |

---

## 2. liboqs / liboqs-python upgrade impact

### 2.1 What the project pins today

| Component | Pin | Where |
|---|---|---|
| liboqs (C) | `0.11.0`, commit `6f30d7ef…` | `docker/backend/Dockerfile` (`LIBOQS_REF`, `LIBOQS_COMMIT`) |
| liboqs-python | `0.10.0`, commit `02198f9c…` | `docker/backend/Dockerfile` (`LIBOQSPY_REF`, `LIBOQSPY_COMMIT`) and a descriptive line in `requirements-lock.txt` |
| Compiled algorithms | `KEM_kyber_512;KEM_kyber_768;KEM_kyber_1024` only | `-DOQS_MINIMAL_BUILD` in the Dockerfile |

`liboqs-python==0.10.0` **does not exist on PyPI**. PyPI only publishes `0.16.0`
(2026-07-23) and `0.16.0.1` (2026-09-23). Earlier wrapper versions were installed
from git, which is what the Dockerfile does. That is why the new
`Dependency Compatibility` workflow could not resolve the lock file, and it is
the only reason the suggested "bump to 0.16.0.1" looked reasonable.

### 2.2 What changed between the pinned versions and the newest

liboqs (C library), from the project's release notes:

| Release | Date | Relevant change |
|---|---|---|
| 0.11.0 | 2024-09-27 | ML-KEM updated to the **final FIPS 203** versions; Kyber round 3 retained "for interoperability". |
| 0.12.0 | 2024-12-10 | ML-DSA final (FIPS 204). **Notice: "last release of liboqs to include Kyber."** Operation failures in the new signature API. |
| 0.13.0 | 2025-04-17 | Default ML-KEM becomes PQCP `mlkem-native`; deterministic keygen API; HQC disabled by default. |
| 0.14.0 | 2025-07-10 | CVE-2025-52473 (HQC secret-dependent branches); mlkem-native v1.0.0. Notice: last release with Dilithium. |
| 0.15.0 | 2025-11-14 | **Dilithium removed.** SLH-DSA added. Notice: SPHINCS+ removed in 0.16. |
| 0.16.0 | 2026-07-09 | **SPHINCS+ removed.** mldsa-native default. FrodoKEM symbol renames. Security fixes (uninitialized `encaps_derand` pointer, XMSS out-of-bounds read). Kyber **still present**; a codeowner for Kyber was added. |

liboqs-python:

| Release | Date | Relevant change |
|---|---|---|
| 0.10.0 | 2024-04-01 | Auto-installs liboqs at runtime when not found; NIST PRNG removed. |
| 0.12.0 | 2025-01-15 | Operation failures **raise `RuntimeError`** instead of returning `0`. |
| 0.14.0 | 2025-08-09 | Minimum Python 3.11 (per the changelog; PyPI metadata says `>=3.10`). `StatefulSignature`; ML-KEM seeded keygen. |
| 0.16.0 | 2026-07-23 | Tracks liboqs 0.16.0; `PYOQS_VERSION` override; Windows DLL lookup. |
| 0.16.0.1 | 2026-09-23 | **Security fix: command injection in the automatic liboqs installation.** ML-DSA external-mu. |

### 2.3 How the Kyber question was settled (and why it matters)

The `0.12.0` release notes say it is the last release to include Kyber. Taken
alone that suggests `Kyber768` disappears in `0.13+`, and an early reading in
this review concluded exactly that. **It was wrong.** The repository tree at
tag `0.16.0` shows `docs/algorithms/kem/kyber.md` and, in
`.CMake/alg_support.cmake`:

```
option(OQS_ENABLE_KEM_KYBER "Enable kyber algorithm family" ON)
cmake_dependent_option(OQS_ENABLE_KEM_kyber_512  "" ON ...)
cmake_dependent_option(OQS_ENABLE_KEM_kyber_768  "" ON ...)
cmake_dependent_option(OQS_ENABLE_KEM_kyber_1024 "" ON ...)
```

and its `0.16.0` notes add a codeowner for Kyber. **Lesson: a deprecation notice
is not a removal.** Treat it as risk that can materialize in any future release.

### 2.4 Impact on this codebase

| Area | Finding | Verdict |
|---|---|---|
| `oqs.KeyEncapsulation("Kyber768")` in `auth_module/services/kyber_crypto.py`, `security/services/lattice_crypto_engine.py` (`Kyber512/768/1024`) | Algorithm still enabled by default in 0.16.0. Method names used (`generate_keypair`, `export_secret_key`, `encap_secret`, `decap_secret`) are unchanged in `0.16.0.1`. | **Compatible.** |
| Dilithium / SPHINCS+ / Falcon | No call site in backend Python (searched `oqs.Signature`, the algorithm names, `ML-DSA`, `SLH-DSA`). | **Not affected.** |
| `from oqs import KEM` in `behavioral_recovery/services/quantum_crypto_service.py` | `oqs` exports `KeyEncapsulation` and `Signature`. There is no `KEM` at `0.10.0` (checked in `oqs/oqs.py`) and none in the `0.16.0.1` `__all__`. | **Broken today, with any version.** See F1. |
| Failure semantics (0.12.0: `RuntimeError`) | The wrappers do not check numeric return codes; exceptions already propagate. | Compatible. |
| Import-time auto-install | In 0.10.0+ a missing liboqs triggers a download + CMake build **at import** (`subprocess` calls). The test logs already show `Error installing liboqs … No oqs shared libraries found` appearing from this. `0.16.0.1` patches a command-injection bug in exactly this path. | Operational risk in CI/dev; **not** in the image (liboqs is preinstalled). |
| `OQS_MINIMAL_BUILD` list | Only Kyber is compiled. ML-KEM is **not** in the shipped binary even though liboqs 0.11.0 contains it. | Must be extended before any ML-KEM use (section 7). |
| Python version | Image and CI use 3.12. Wrapper needs ≥3.10/3.11. | Compatible. |
| Docker | Both refs and SHAs must change in the same PR (policy). Needs a real image build to validate; Docker was not available locally when this was written. | Unvalidated. |

**liboqs's own warning.** The `0.16.0` README states: *"WE DO NOT CURRENTLY RECOMMEND
RELYING ON THIS LIBRARY IN A PRODUCTION ENVIRONMENT OR TO PROTECT ANY SENSITIVE
DATA. This library is meant to help with research and prototyping,"* and
recommends hybrid constructions. A password manager should therefore treat
liboqs-derived protection as **defense in depth on top of classical crypto**, never
as the only layer. This contradicts the "modern standard for a 2026 password
manager" framing in the pasted summary; the project's own README is the authority.

### 2.5 Recommendation for the bump

Do **not** bump now. Do it as a deliberate, staged migration after the fixes in
section 7 (P0/P1), following `DEPENDENCY_POLICY.md`:

1. bump liboqs and liboqs-python **together**, refresh both SHAs and the policy table;
2. build the image and run the `lattice_crypto_engine` tests against it;
3. confirm `oqs.oqs_version()` and `oqs.oqs_python_version()` agree at container start;
4. only then change the lock line, and remove the Dependabot `ignore` entry.

Until then the lock line stays (it documents the image), the compatibility
workflow drops it before resolving (and prints that it did), and Dependabot is
told to leave it alone.

---

## 3. What the codebase implements today

### 3.1 Backend

| Component | File | What it is |
|---|---|---|
| `ProductionKyber` + `HybridEncryption` | `auth_module/services/kyber_crypto.py` | Kyber768 KEM (liboqs, else `pqcrypto`, else **simulated**) + HKDF-SHA256 (`info=b'kyber-hybrid-encryption-v1'`) + AES-256-GCM, 96-bit random nonce, optional AAD hash. A KEM-DEM construction; **no X25519**. |
| Kyber API | `auth_module/kyber_views.py`, `models.py` (`algorithm` default `'Kyber768'`, optional `x25519_*` columns) | Endpoints for keygen/encrypt/decrypt; the algorithm is stored per key, which is what makes a versioned migration possible. |
| Other Kyber users | `auth_module/services/quantum_crypto_service.py` (`pqcrypto.kem.kyber768`), `security/services/lattice_crypto_engine.py` (liboqs, `Kyber512/768/1024`) | Three independent Kyber consumers, three different code paths. |
| Behavioral recovery | `behavioral_recovery/services/quantum_crypto_service.py` | See F1–F3. |
| Account auth | `PASSWORD_HASHERS = [Argon2PasswordHasher]`; JWT (`rest_framework_simplejwt`) | Server-side Argon2 hashing of whatever password it receives. |
| Vault storage | `vault/models/vault_models.py` `EncryptedVaultItem`: `encrypted_data` (text blob), `crypto_version`, `crypto_metadata` | Versioned opaque blob. |

### 3.2 Frontend

| Component | File | What it is |
|---|---|---|
| Hybrid KEM | `services/quantum/kyberService.js` | **X25519 + Kyber768** (`@stablelib/x25519`). Combined key = 4-byte length header ‖ Kyber key ‖ X25519 key. Shared secret = `SHA-256(kyberSS ‖ x25519SS)`. |
| Library loader | same, `_loadKyberModule()`; `workers/kyber-worker.js`; `utils/kyber-wasm-loader.js` | Tries `pqc-kyber`, then `crystals-kyber-js`, then `mlkem`. See F4. |
| Vault crypto | `services/vaultEnvelope.js`, `sessionVaultCrypto.js` (v2 `svc-gcm-1`, v3 `svc-gcm-2`) | AES-GCM **DEK/KEK envelope**: random DEK wrapped under a KEK derived from the vault password, wrapped-DEK for OAuth users, decoy slots, recovery factors. |
| KDF | `services/cryptoService.js` | Argon2id (adaptive parameters, "128 MB on capable devices"), PBKDF2 fallback; a legacy CryptoJS AES-CBC path (own TODO: no integrity tag) |
| Login | `hooks/useAuth.jsx` | Posts `{username, password}` in both the cookie and token flows. |
| Signup | `App.jsx` | Posts **both** `password` and a PBKDF2-SHA256 `auth_hash` (310 000 iterations, salt `pwm-auth\|<email>`). |
| Tokens | `hooks/useAuth.jsx` | HttpOnly-cookie flow exists but is **opt-in** (`VITE_USE_COOKIE_AUTH`, default off). |
| CSP | `docker/frontend/security-headers.conf` | `script-src 'self' 'unsafe-eval'`; kept deliberately for WASM glue (FHE and Kyber). |
| TLS | `docker/nginx/nginx.conf` | `ssl_ecdh_curve` is commented out; image is `nginx:1.27-alpine`. **No hybrid post-quantum TLS.** |

### 3.3 Findings

**F1: `from oqs import KEM` disables post-quantum protection behind log-only warnings (backend).**
`behavioral_recovery/services/quantum_crypto_service.py` imports a name that does
not exist, inside `except (ImportError, Exception, SystemExit)`. The import fails,
`LIBOQS_AVAILABLE` becomes `False`, and the service uses `_fallback_*` (random
keys, AES-GCM) even in the Docker image. Nothing surfaces to the caller: the
import-time warning is logged only when `DEBUG=False`, and each `_fallback_*`
call logs "NOT QUANTUM-RESISTANT" in either mode. Its docstring says "in production
(Docker), liboqs is compiled and installed for real PQC". Severity: **high** (a
security claim that is not true), fix: one line plus a fail-closed check.

**F2: `decrypt_behavioral_embedding(..., private_key)` ignores `private_key`.** It
calls `self.kem.decap_secret(...)` on a service-wide `KEM` object; in liboqs-python
the secret key lives on the object (set at construction or by the last
`generate_keypair`). Latent while F1 hides it.

**F3: the "quantum-protected" behavioral commitment stores a key it throws away.**
`commitment_service.py` generates a Kyber keypair server-side, encrypts to it and
comments that the private key is "not stored". The frontend's `kyber_public_key`
sent to `setup-commitments` is not what the service encrypts to. The non-quantum
path records `encryption_algorithm='base64'`. Observed from the code; the intended
design was not confirmed.

**F4: the frontend library fallback chain does not work as written, and tests never
run a real KEM.**
- `pqc-kyber` (loaded first) is **round-3 Kyber**, last published **2023-08-15**,
  before FIPS 203 was finalized.
- `crystals-kyber-js` v2.x and `mlkem` v2.x implement **FIPS 203 ML-KEM**. Run
  locally: both export `MlKem768` and **neither exports `Kyber768`**, which is the
  name the loader looks for. Their branch never matches, so the "fallback to
  ML-KEM" documented in the code cannot happen.
- Net effect: a `pqc-kyber` failure (WASM did not load) leaves `kyberModule = null`
  and the service silently continues **X25519-only**, labelled "NOT
  quantum-resistant" in a console log only (`allowFallback = true`).
- If an ML-KEM library *were* picked up, its secrets would **not** match the
  backend's round-3 `Kyber768`. Observed: the real `pqc-kyber` WASM (run in Node
  with `--experimental-wasm-modules`) produced a round-3 ciphertext and secret key;
  `mlkem` 2.7.0 (`MlKem768.decap`) accepted them with **no error and returned a
  different 32-byte secret**. Same key and ciphertext sizes, silent divergence.
- `vitest.config.js` aliases `pqc-kyber` to `src/test/stubs/pqc-kyber.js`, a
  non-cryptographic XOR stub. No unit test runs a real KEM.
- The self-check in `_verifyImplementation` compares **sizes** (1184/2400/1088/32),
  which are identical for round-3 Kyber and ML-KEM, so it cannot tell them apart.

**F5: the frontend combiner is weaker than documented.** Doc comment says
"HKDF-SHA256"; the code is plain `SHA-256(kyberSS ‖ x25519SS)`: no domain
separation label, no binding to the ciphertexts or public keys. `HYBRID_SHARED_SECRET_SIZE`
is 64 but the hybrid path returns 32 bytes.

**F6: the two "hybrids" are different constructions and do not interoperate.**
Frontend: X25519 + Kyber with a 1220-byte combined public key. Backend: Kyber-only
KEM + AES-GCM expecting a raw 1184-byte key. Today they meet only where the
backend generates its own keys, so nothing breaks, but they cannot be wired
together without a deliberate protocol decision.

**F7: simulated KEM fallback and no CI coverage of the real path (backend).**
`ProductionKyber` falls back to `os.urandom`-based "SIMULATION" when neither
liboqs nor `pqcrypto` imports. `ci.yml` installs `liboqs-dev` best-effort
(C library only); no requirements file used by tests installs the Python wrapper
(`requirements.txt` has it commented out: "Installed from source in Docker"), so
the test suite runs against the simulation. Only `test_quantum_entanglement.py`
and a management command mention Kyber. **A regression in liboqs or in the real
path cannot fail CI today.**

**F8: the raw master password is sent to the server on every login.** Both login
flows post `password: credentials.password`; signup posts the password and an
`auth_hash`. The vault key is derived client-side from the same password, so the
server (or anyone who records TLS and later breaks it) sees the secret the vault
depends on. This is the largest gap against a zero-knowledge design, and the most
important *post-quantum* gap: a recorded session decrypted later by a quantum
adversary yields the password itself (section 7).

**F9: PBKDF2 for the auth hash while the vault uses Argon2id.** 310 000 iterations
of PBKDF2-SHA256 is GPU-friendly, and the salt is deterministic
(`pwm-auth|<email>`).

---

## 4. The proposed architecture

Summary of the plan under review: ephemeral X25519 + ML-KEM-768 handshake between
React and Django producing an `HKDF-SHA256` session key; client-side Argon2id
(m=64 MiB, t=3, p=4) split by HKDF into `K_auth` (sent) and `K_master` (kept);
PostgreSQL `BYTEA` columns for IV/ciphertext/tag; a custom Django backend that
re-hashes `K_auth`; multipart upload of encrypted items; in-memory non-extractable
key, 15-minute inactivity lock, and a clipboard-clearing hook.

### 4.1 Technical errors in the plan's code (verified)

| Snippet | Problem |
|---|---|
| `client_kem.encapsulate(pk)` (Django) | `liboqs-python` has `encap_secret` / `decap_secret`; there is **no `encapsulate`** in `0.16.0.1` (checked in `oqs/oqs.py`). It would raise `AttributeError`. The variable is also misnamed: the *server* encapsulates to the *client's* public key. |
| `status.HTTP_400_BAD_RECORD` | Not a DRF constant (`HTTP_400_BAD_REQUEST`). |
| `ForeignKey(..., related_index="vault_items")` | Not a field option (`related_name`). |
| `titleCiphertextBytes` in `vaultCryptoService.ts` | Undefined; the variable defined is `fullTitleBuffer`. `ReferenceError` at runtime. |
| `import { mlkem768 } from '@noble/post-quantum'` | The documented API is `ml_kem768` from `@noble/post-quantum/ml-kem.js`, with `keygen()`, `encapsulate(pk)`, `decapsulate(ct, sk)`. |
| `import { noble } from '@noble/curves/ed25519'` | Not the library's export shape (it exports named curves such as `x25519`). Not re-verified against the current docs. |
| `Buffer.from(hex, 'hex')` in the browser | `Buffer` is not available in a Vite browser build without a polyfill. |
| `sessionStorage.setItem('access_token', …)` | Script-readable token storage; this repository previously had to remove similar storage after CodeQL alert #1048. |

These are fixable, but they show the plan is an illustration, not a drop-in design.

### 4.2 Design review

- **What its hybrid session layer actually protects.** Vault items are already
  end-to-end AES-256-GCM under a client-held key, so a post-quantum session layer
  does not protect them further. What crosses TLS in a form that matters is the
  credential. The plan fixes that with `K_auth`, not with ML-KEM.
- **The session key is never used.** The plan says "TODO: store the session key"
  and then recommends *not* passing vault data through it: it adds a second
  transport layer on top of HTTPS without defining what it carries, the replay
  rules, or how it binds to the authenticated user. That is a large custom
  protocol surface for unclear benefit.
- **Combiner.** HKDF over `ss_classic ‖ ss_pqc` with an `info` label (and an empty
  salt, which RFC 5869 treats as zeros; equivalent between Python `None` and
  WebCrypto's empty salt) is sound and matches the TLS hybrid style. It does not bind
  ciphertexts/public keys the way X-Wing does. `@noble/post-quantum` ships
  `ml_kem768_x25519` (X-Wing) if a bound combiner is wanted.
- **`K_auth` is a bearer credential.** The plan sends `K_auth` to the server on every
  login and the server only re-hashes it. Anyone who captures it (for example from
  a TLS recording decrypted later) can **replay it to log in** until the password
  changes, and can also test password guesses offline by recomputing `K_auth`. The
  split protects `K_master` (so the vault stays undecryptable) and stops the server
  seeing the password, but it does **not** make login replay-resistant.
- **Salt = email + constant.** Deterministic and public; changing the email changes
  the keys, and it removes the per-user random salt that the current vault code uses.
- **Single `K_master`** encrypting every item directly: changing the master password
  means re-encrypting the whole vault, and there is no recovery path. The existing
  DEK/KEK envelope exists to avoid exactly that.
- **`@noble/post-quantum` is not independently audited.** Its README says so
  explicitly (internal self-audit at `0.6.1`, April 2026; a reproducibility study
  against `0.7.0`, "not a full audit"). Same caveat as liboqs's own warning.
- **CSP.** The plan's `script-src 'self'` would break the app's FHE WASM glue, which
  needs `'unsafe-eval'` (see `security-headers.conf`). Moving ML-KEM to pure
  TypeScript removes only the Kyber reason for it.

---

## 5. Side-by-side

| Area | Existing | Plan | Better |
|---|---|---|---|
| Master password handling | Raw password posted on every login; PBKDF2 `auth_hash` also sent at signup | Never sent; one Argon2id run split by HKDF into `K_auth` / `K_master` | **Plan**, with the `K_auth` replay caveat (section 4.2). The most valuable idea in it. |
| KDF parameters | Argon2id, adaptive memory (to 128 MB) + PBKDF2 fallback; versioned | Fixed m=64 MiB, t=3, p=4 (matches RFC 9106's second recommended profile) | **Existing** for adaptivity/versioning; plan for using one KDF. |
| Per-user salt | Per-user salt in the vault envelope | Email + constant | **Existing.** |
| Vault key management | DEK/KEK envelope, wrapped DEK, password rotation, OAuth path, decoy slots, recovery factors | Single `K_master` | **Existing.** |
| Item format | Versioned `svc-gcm-*` blob + `crypto_version` + `crypto_metadata` | `BYTEA` iv / ct / tag columns | **Existing** (algorithm agility); `BYTEA` saves ~33% storage but loses versioning. Encrypting the item *title* is a good idea worth checking against the current schema. |
| KEM algorithm | Round-3 Kyber768 (`pqc-kyber`, unmaintained since 2023-08); backend liboqs `Kyber768` | ML-KEM-768 (FIPS 203) | **Plan.** Standardized and maintained. |
| Hybrid combiner | `SHA-256(a ‖ b)`, no label (doc says HKDF) | HKDF-SHA256 with label | **Plan**; X-Wing better than both. |
| Where PQ is applied | App-layer KEM for recovery shards / backups wrapped under a public key (data stored long-term) | A session handshake carrying nothing defined | **Existing's placement is right**: long-lived stored ciphertext is where "harvest now, decrypt later" bites. The plan's layer is redundant with TLS. |
| Transport PQ | None | App-layer hybrid | **Neither**; hybrid TLS at the edge is simpler and covers all traffic (section 7). |
| Downgrade behavior | Silent X25519-only (frontend); simulation behind a log-only warning (backend) | Not addressed | **Neither.** Both need fail-closed in production. |
| Auth tokens | HttpOnly-cookie flow (opt-in) else script-readable storage | `sessionStorage` | **Existing**, if the cookie flow is enabled by default. |
| Memory hygiene | Some non-extractable keys, `lock()`, clipboard-clear setting, decoy handling; legacy `extractable: true` key in `cryptoService.js` | Non-extractable key, inactivity timer, clipboard clear after 30 s | Plan's checklist is good practice; verify each against the existing code (I did not find an inactivity-timeout implementation by keyword search). |
| Tests of the real PQ path | None in CI (F7) | Not discussed | Gap in both. |

---

## 6. Recommended direction

Keep the existing vault design. Adopt from the plan: **the credential split**, **ML-KEM**,
**an HKDF (preferably X-Wing) combiner**, and its **client hygiene checklist**. Do
not adopt: the application-layer session handshake, the single `K_master`, the
email-derived salt, or the `BYTEA`-only item format.

### Priority list

**P0: correctness and honesty (small changes, no new protocol)**

1. Fix `from oqs import KEM` → `KeyEncapsulation`, and make decapsulation use the
   supplied private key (`oqs.KeyEncapsulation(alg, secret_key)`).
2. Fail closed: in non-`DEBUG` builds, refuse to start (or refuse the operation) when
   neither liboqs nor `pqcrypto` loads, instead of the simulated KEM. Add a
   `REQUIRE_REAL_PQC` setting defaulting to on in production.
3. Frontend: when the Kyber module does not load, surface it (and block, or require
   explicit user consent) instead of silently continuing X25519-only. Verify the
   loaded family with a known-answer test, not key sizes.
4. Add a CI job that builds the real liboqs/wrapper (or uses the built image) and
   runs round-trip + known-answer tests, so a liboqs change can actually fail CI.

**P1: the part that moves the security needle**

5. Stop sending the raw master password. Derive `K_auth` and `K_master` from one
   Argon2id run client-side (plan, Part 1) with a **per-user random salt** served
   before login (not the plan's email salt). This removes the password from the wire
   and from the server, and keeps `K_master` (hence the vault) out of reach. Be
   explicit about what it does *not* do: a sent `K_auth` is a **replayable bearer
   credential**, so treat this as step one and choose the login protocol on purpose:
   - *Target:* an augmented PAKE such as **OPAQUE (RFC 9807, July 2025, CFRG,
     Informational)**, where neither the password nor a replayable verifier crosses
     the wire and the server never holds a password-equivalent. Needs a maintained
     JS client and Python server implementation (not evaluated here) and a
     registration migration for existing accounts.
   - *Interim, if a PAKE is out of scope:* send `K_auth` only over the hybrid-TLS
     channel (item 6), keep it server-side re-hashed with Argon2, rate-limit, and
     require the existing second factor (TOTP / passkey) so a captured `K_auth`
     alone is not enough. Whether the second factor is enforced on every login was
     not verified.
   - Migration for existing accounts: accept both forms for a window, then flag or
     rotate.
6. Hybrid post-quantum TLS at the edge. nginx's documentation describes
   `ssl_ecdh_curve X25519MLKEM768:X25519;` and notes OpenSSL **3.5+** is required;
   older builds ignore or reject the unknown group. The current image is
   `nginx:1.27-alpine`; check `nginx -V` of the image you will ship before relying
   on it. Current Chrome, Edge and Firefox negotiate this group by default.

**P2: algorithm migration (Kyber round 3 → ML-KEM)**

7. Extend `OQS_MINIMAL_BUILD` to include `KEM_ml_kem_768` (liboqs 0.11.0 already
   contains it; the current binary does not compile it).
8. Version everything stored: the key table already has an `algorithm` column; add
   `ML-KEM-768` as a new value and write a dual-decapsulation path. **Existing
   round-3 ciphertexts cannot be opened with ML-KEM**, so stored items must be
   re-wrapped (decrypt with Kyber, encrypt with ML-KEM) before Kyber is dropped.
9. Frontend: replace the three-library loader with one maintained ML-KEM library
   (`mlkem` v2 or `@noble/post-quantum`; both pure TypeScript, no WASM), and use an
   X-Wing or labeled-HKDF combiner. Cross-test it against the backend with ACVP /
   Wycheproof vectors.
10. Then perform the liboqs bump (section 2.5), per `DEPENDENCY_POLICY.md`.

**P3: decide**

11. Enable the HttpOnly cookie auth flow by default.
12. Do **not** build the plan's application-layer session handshake unless there is
    a concrete payload for it that TLS (with hybrid groups) does not already cover.

### Why this order

P0 makes existing claims true and testable. P1 removes the largest real exposure
(the password crossing the wire) and covers all traffic with one configuration
change. P2 is a data migration with compatibility risk and should happen once P0's
tests exist. The liboqs bump is last because it changes nothing the application
needs that ML-KEM migration does not, and it is the riskiest to validate.

---

## 7. Why "harvest now, decrypt later" points at the password first

An adversary recording TLS today and breaking its classical key exchange later reads
whatever was sent. In this application that includes the **master password** (F8).
The vault contents are AES-256-GCM under keys derived from that password; reading
the password makes the vault key derivable. So:

- the credential split (P1.5) keeps the password and `K_master` off the wire, so a
  later-decrypted recording no longer yields the vault key directly; the attacker
  would have to guess the password offline against an Argon2id-protected `K_auth`.
  Grover's algorithm gives only a quadratic reduction for unstructured search, and
  its practical benefit depends on the cost of the quantum oracle (here a full
  Argon2id evaluation) and on the search being serial; this document does not
  quantify that cost. **A recorded `K_auth`, however, is a
  replayable login credential** until it is rotated, which is why P1.5 recommends a
  PAKE and why hybrid TLS (next bullet) still matters. OPAQUE's key exchange is
  classical 3DH, so it removes the replayable secret but is **not** itself
  post-quantum; I did not find a standardized post-quantum aPAKE (not an exhaustive
  search);
- hybrid TLS (P1.6) protects everything else in transit, including session tokens
  and metadata, without any application protocol;
- application-layer ML-KEM matters for **data stored long-term under public-key
  wrapping** (recovery shards, backups), which is where the current Kyber code is
  already placed.

---

## 8. What was verified, and what was not

**Verified (source in parentheses):**

- liboqs release notes 0.10.1–0.16.0 (`gh api repos/open-quantum-safe/liboqs/releases`).
- Kyber still present and enabled by default at `0.16.0` (`.CMake/alg_support.cmake`,
  `docs/algorithms/kem/` at tags 0.11.0–0.16.0).
- liboqs-python versions and API (`oqs/__init__.py`, `oqs/oqs.py` at `0.10.0` and
  `0.16.0.1`; PyPI lists only `0.16.0`, `0.16.0.1`).
- liboqs production-use warning (`README.md` at `0.16.0`).
- npm registry metadata for `pqc-kyber`, `crystals-kyber-js`, `mlkem`,
  `@noble/post-quantum`; the installed `mlkem` / `crystals-kyber-js` 2.7.0 run
  locally (exports `MlKem768`, not `Kyber768`).
- The code citations above, read from the repository at this commit.
- CI evidence for the dependency bump (separate: PR #526).

**Not verified:**

- No liboqs was built or run locally, so the claim that `Kyber768` interoperates
  across liboqs 0.11 → 0.16 rests on the algorithm being unchanged and on liboqs's
  own known-answer tests, not on a test here. This is why P0.4 exists.
- The real `pqc-kyber` WASM was executed in Node (its `package.json` has only a
  `module` entry, so `require` fails but ESM import with the WASM flag works). That
  it loads **in a browser** is inferred (a production build does bundle
  `pqc_kyber_bg.wasm`), not observed.
- Whether the nginx image you deploy supports `X25519MLKEM768`; the Docker daemon
  was unavailable. Check `nginx -V` and test with a recent browser.
- Whether the server stores or ever uses the `auth_hash` sent at signup.
- Whether an inactivity auto-lock exists under a name my keyword search missed.
- `@noble/curves` export names used in the plan (flagged as such above).
- The `behavioral_recovery` design intent (F3).
- Maturity of OPAQUE libraries for this stack (JS client, Python server); whether
  the existing second factor is enforced on every login; and that no standardized
  post-quantum aPAKE exists (the search was not exhaustive).

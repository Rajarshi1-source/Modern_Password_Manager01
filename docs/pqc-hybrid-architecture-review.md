# Post-quantum hybrid architecture review

Status: review, 2026-10-06. No application code was changed by this document.
Companion change: PR #526 (CI lock-file fixes, Dependabot guard).

Update, 2026-10-07: **F1, F2 and the backend half of F7 are fixed** (branch
`fix/behavioral-recovery-real-pqc`; P0.1 and P0.2 below). That work and the
review below found five more problems (F10–F14), two of them high (F13: a recovery
path that cannot decrypt; F14: client-IP spoofing in lockout/allowlist checks,
pending an ingress check). Section 9 also records two ops gaps: k8s backups are
discarded, and alerts have no receiver. Section 9 reviews a second set of proposals (Playwright
memory/clipboard audits, a PQC nginx build, a compose stack, encrypted backups,
monitoring, key rotation, audit logging) against the code.

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
| 4 | Does the code have problems that exist regardless of any version bump? | **Yes, several.** The most serious one at review time was fixed on 2026-10-07 (F1, F2, F7 backend): `behavioral_recovery/services/quantum_crypto_service.py` **used to** do `from oqs import KEM`, which does not exist in any liboqs-python version, so it ran its non-post-quantum fallback even in the Docker image, with only log warnings. It now does `import oqs`, uses `oqs.KeyEncapsulation("Kyber768")`, and **refuses** the fallback (`ImproperlyConfigured`) unless `QUANTUM_CRYPTO['ALLOW_SIMULATION']` is true. **Still open:** F13 (`auth_module`'s recovery KEM is an unconditional simulation), F3/F10 (behavioral commitments cannot be verified), F14 and F12. See section 3.3. |
| 5 | Does CI protect against a liboqs regression? | **No.** No test job installs the Python wrapper, so `import oqs` fails and the backend selects a *simulated* KEM. Since 2026-10-07 production serving refuses that simulation, but `TESTING` still allows it (`ALLOW_SIMULATION`), so CI keeps running against it. A broken liboqs bump would pass CI. |
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
| `from oqs import KEM` in `behavioral_recovery/services/quantum_crypto_service.py` (**removed 2026-10-07**) | `oqs` exports `KeyEncapsulation` and `Signature`. There is no `KEM` at `0.10.0` (checked in `oqs/oqs.py`) and none in the `0.16.0.1` `__all__`, so the import was broken with any version. The service now uses `oqs.KeyEncapsulation`, which is compatible with both. | **Fixed.** See F1. |
| Failure semantics (0.12.0: `RuntimeError`) | The wrappers do not check numeric return codes; exceptions already propagate. | Compatible. |
| Import-time auto-install | In 0.10.0+ a missing liboqs triggers a download + CMake build **at import** (`subprocess` calls). The test logs already show `Error installing liboqs … No oqs shared libraries found` appearing from this, after which the wrapper **exits with `SystemExit`** (verified on `0.10.0`), not an ordinary exception: code that wraps `import oqs` must catch `SystemExit` as well as `ImportError`. `0.16.0.1` patches a command-injection bug in exactly this path. | Operational risk in CI/dev; **not** in the image (liboqs is preinstalled). |
| `OQS_MINIMAL_BUILD` list | Only Kyber is compiled. ML-KEM is **not** in the shipped binary even though liboqs 0.11.0 contains it. | Must be extended before any ML-KEM use (section 6, P2). |
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
section 6 (P0/P1), following `DEPENDENCY_POLICY.md`:

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
| Other Kyber users | `auth_module/services/quantum_crypto_service.py` (**unconditional simulation**: `pqcrypto` appears only in docstrings; corrected 2026-10-07, see F13), `security/services/lattice_crypto_engine.py` (liboqs, `Kyber512/768/1024`) | Three independent Kyber consumers, three different code paths. |
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
| CSP | `docker/frontend/security-headers.conf` | `script-src 'self' 'unsafe-eval'`; required by the FHE loader's `new Function(...)` dynamic import (`fheService.js`) and by Kyber's WASM glue. |
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
*Fixed 2026-10-07:* `import oqs` + `oqs.KeyEncapsulation("Kyber768")`. A test
loads the module against an `oqs` that exports only `KeyEncapsulation` and
`Signature` (the real API) and asserts `LIBOQS_AVAILABLE`.

**F2: `decrypt_behavioral_embedding(..., private_key)` ignores `private_key`.** It
calls `self.kem.decap_secret(...)` on a service-wide `KEM` object; in liboqs-python
the secret key lives on the object (set at construction or by the last
`generate_keypair`). Latent while F1 hides it.
*Fixed 2026-10-07:* no service-wide KEM; each operation builds its own
`KeyEncapsulation` (as a context manager, so the native secret is freed), and
decapsulation uses `KeyEncapsulation(alg, private_key)`, the same pattern as
`kyber_crypto.py`. Decryption now dispatches on the blob's own `algorithm` field,
so a stored `fallback-aes256gcm` blob is never fed to Kyber, nor the reverse.

**F3: the "quantum-protected" behavioral commitment stores a key it throws away.**
`commitment_service.py` generates a Kyber keypair server-side, encrypts to it and
comments that the private key is "not stored". The frontend's `kyber_public_key`
sent to `setup-commitments` is not what the service encrypts to. The non-quantum
path records `encryption_algorithm='base64'`. Observed from the code; the intended
design was not confirmed.
*Consequence (confirmed 2026-10-08, PR #553 review):* a quantum-mode commitment
stores `encrypted_embedding=b''`, and `RecoveryOrchestrator` passes exactly that
field to `verify_behavioral_similarity`, which raises `JSONDecodeError`. So
**behavioral recovery fails for every commitment created with quantum mode on.**
This predates the F1 fix. On the pre-fix code, run with liboqs unavailable (then
true everywhere, because of F1), `_encrypt_embedding` already returned the
quantum tuple, and `verify(b'')` raised `JSONDecodeError`. Fixing it needs F3's
key-custody decision (P0.2a): persist the private key, wrapped, and give the
recovery path the quantum blob and that key.

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
*Backend fail-closed fixed 2026-10-07.* Rather than add a new `REQUIRE_REAL_PQC`
flag, both `ProductionKyber`'s simulation and the behavioral-recovery fallback now
use the **existing** switch that `LatticeCryptoEngine` already fails closed on:
`QUANTUM_CRYPTO['ALLOW_SIMULATION']`. It is `DEBUG`, widened only for `TESTING` and
passive management commands (`settings/base.py`), so it is already False in
production serving, and one switch cannot drift from a second. A missing setting
counts as False. The check runs **per operation**, not at construction, because
`kyber_crypto.py` builds `production_kyber` / `hybrid_encryption` at import time; a
construction-time raise would stop the process from booting. A refused operation
raises `ImproperlyConfigured`. **Still open:** the CI half (P0.4); tests mock
`oqs`, so they prove which branch runs and which key is used, not that liboqs
produces correct output.

**F10: the behavioral-recovery fallback cannot decrypt what it encrypts.**
`_fallback_encrypt` derives its AES key from `HKDF(public_key)`, while
`_fallback_decrypt` uses `HKDF(private_key[:32])`. The two keys are unrelated
random bytes, so a fallback round trip always fails the GCM tag check. Since F1 made
the fallback the only path, no `quantum_encrypted_embedding` blob written so far can
be decrypted by `QuantumCryptoService`. Together with F3 (the Kyber private key is
discarded), **no quantum-mode commitment (fallback-AES or Kyber) can be decrypted
or verified**, because its `encrypted_embedding` is `b''`. This does **not** extend
to the whole store. Rows on the legacy `base64` path (`encryption_algorithm='base64'`)
remain readable through `CommitmentService._decrypt_embedding`. So do rows upgraded
by `tasks.async_migrate_commitments_to_quantum`, which copies `encrypted_embedding`
into `legacy_encrypted_embedding` but leaves `encrypted_embedding` itself in place.
A recovery or migration plan must keep those rows. Not fixed: after the F7
change the fallback runs only in DEBUG/tests. Decide F3's key custody first; the
fallback can then be fixed or deleted to match.

**F11: `CommitmentService` downgraded any quantum failure to plain base64.**
`_encrypt_embedding` caught every exception from the quantum path and stored
`base64(json(embedding))`, labelled `encryption_algorithm='base64'`. That is
encoding, not encryption. A fail-closed raise (F7) or a real liboqs error (now
reachable, F1) would have been converted into **unencrypted** storage.
*Fixed 2026-10-07:* when `ALLOW_SIMULATION` is False the error propagates; the
DEBUG behaviour is unchanged. *2026-10-08 (review of #553):* the base64 path
itself is now guarded, because it was also reachable when quantum was off from
the start (explicit `use_quantum=False`, or `__init__` swallowing an
initialization error). It is allowed only with `ALLOW_SIMULATION`.
`QUANTUM_CRYPTO_ENABLED=False` (documented in `env.example` for behavioral
commitments, but never read here before) now stops Kyber being used. It opts
out of PQC, **not of encryption**. There is no real classical encryption path,
so commitment writes are refused rather than stored as readable base64.
Reads and verification of existing rows are unaffected. (An intermediate commit
let the opt-out store labelled base64; reverted after review on 2026-10-10.)
`QUANTUM_FALLBACK_ENABLED` stays unwired on purpose: it defaults to `True`, so
honouring it would reopen the silent downgrade by default. Still open in DEBUG only: when the AES fallback
succeeds, `_create_commitment` and `tasks.py` still label the row
`kyber768-aes256gcm` / `is_quantum_protected=True`. They should read
`QuantumCryptoService.is_quantum_protected(blob)` instead of hard-coding it.

**F12: the "Clear Clipboard Automatically" setting is not wired to anything.**
`preferencesService.js` defaults `clearClipboard: true, clipboardTimeout: 30`, and
`Components/settings/SecuritySettings.jsx` renders the toggle and the timeout. No
other code reads either key. The main copy action
(`Components/vault/VaultItemDetail.jsx`, `handleCopy`) calls
`navigator.clipboard.writeText(text)` and never clears it. Only
`SealedAutofillFrame.jsx` clears, on its own fixed 20 s timer. This is the same
kind of problem as F1: the UI advertises a protection that the code does not
provide. Fix it in the frontend with the Playwright test in section 9.1.

**F13: `auth_module/services/quantum_crypto_service.py` is a simulation everywhere,
and its decapsulation returns a random secret.** Section 3.1 originally said it used
`pqcrypto.kem.kyber768`. It does not: `pqcrypto` appears only in docstrings
("In production, use: …"). `generate_kyber_keypair`, `kyber_encapsulate` and
`kyber_decapsulate` each return fresh `os.urandom` bytes, in every environment and
regardless of any setting. Decapsulation therefore never reproduces the
encapsulated secret. Observed: `encrypt_shard_hybrid` → `decrypt_shard_hybrid`
fails with `InvalidTag`. Consumers:
- `quantum_recovery_views.py` encrypts recovery shards with it;
- `passkey_primary_recovery_service.py` encapsulates via `Kyber.encapsulate` (l. 98)
  and later decapsulates via `Kyber.decapsulate` (l. 180) with a private key
  "derived from the recovery key". Kyber keygen cannot be derived that way, so even
  a real KEM would not match. That decrypt cannot succeed as written.

Severity: **high, functional as well as security**. A recovery path that cannot
recover is worse than none, because users rely on it. Not fixed here; it needs its
own PR (route through `kyber_crypto.ProductionKyber`, which has the F7 guard, and
redesign where the recovery-side Kyber private key comes from). Existing stored
shards and recovery blobs cannot be migrated: their secrets were never
reconstructible.

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
- **CSP.** The plan's `script-src 'self'` would block the FHE loader's `new Function(...)`
  dynamic import and Kyber's WASM glue, which both require `'unsafe-eval'` (see
  `docker/frontend/security-headers.conf`). Moving ML-KEM to pure TypeScript removes
  only Kyber's requirement; the FHE loader still needs it.

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
| Transport PQ | None | App-layer hybrid | **Neither**; hybrid TLS at the edge is simpler and covers all traffic from clients that negotiate the hybrid group (sections 6-7). |
| Downgrade behavior | Silent X25519-only (frontend); simulation behind a log-only warning (backend) | Not addressed | **Neither.** Both need fail-closed in production. |
| Auth tokens | HttpOnly-cookie flow (opt-in) else script-readable storage | `sessionStorage` | **Existing**, if the cookie flow is enabled by default. |
| Memory hygiene | Some non-extractable keys, `lock()`, inactivity auto-lock (`VaultContext.jsx`, default 5 min), clipboard-clear *setting* that nothing reads (F12), decoy handling; legacy `extractable: true` key in `cryptoService.js` | Non-extractable key, inactivity timer, clipboard clear after 30 s | Plan's checklist is good practice. Auto-lock exists; clipboard clearing does not (F12). |
| Tests of the real PQ path | None in CI (F7) | Not discussed | Gap in both. |

---

## 6. Recommended direction

Keep the existing vault design. Adopt from the plan: **the credential split**, **ML-KEM**,
**an HKDF (preferably X-Wing) combiner**, and its **client hygiene checklist**. Do
not adopt: the application-layer session handshake, the single `K_master`, the
email-derived salt, or the `BYTEA`-only item format.

### Priority list

**P0: correctness and honesty (small changes, no new protocol)**

1. ~~Fix `from oqs import KEM` → `KeyEncapsulation`, and make decapsulation use the
   supplied private key (`oqs.KeyEncapsulation(alg, secret_key)`).~~ **Done
   2026-10-07** (F1, F2).
2. ~~Fail closed: in non-`DEBUG` builds, refuse to start (or refuse the operation) when
   neither liboqs nor `pqcrypto` loads, instead of the simulated KEM. Add a
   `REQUIRE_REAL_PQC` setting defaulting to on in production.~~ **Done 2026-10-07**
   for `kyber_crypto.py` and `behavioral_recovery`, refusing the operation, using the
   existing `QUANTUM_CRYPTO['ALLOW_SIMULATION']` rather than a new flag (F7). Also
   closed the base64 downgrade that would have absorbed the refusal (F11).
   This does **not** cover `auth_module/services/quantum_crypto_service.py`. It is
   not a `pqcrypto` path but an unconditional simulation (F13), with no
   `ALLOW_SIMULATION` check at all. It was left unchanged and is still unresolved;
   see item 2b.
2a. Decide F3's key custody (where the behavioral-commitment private key lives), then
   fix or delete the broken fallback (F10) and the DEBUG mislabelling (F11).
2b. Replace the unconditional simulation in `auth_module/services/quantum_crypto_service.py`
   (F13) with `ProductionKyber`, and redesign passkey-primary recovery's Kyber key
   custody. Highest functional priority in this list: recovery cannot work today.
2c. Wire the clipboard-clear setting (F12).
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
   - *Interim, if a PAKE is out of scope:* send `K_auth` over hybrid-TLS
     connections (item 6; a client that falls back to plain X25519 gets no
     post-quantum protection), keep it server-side re-hashed with Argon2, rate-limit, and
     require the existing second factor (TOTP / passkey) so a captured `K_auth`
     alone is not enough. Whether the second factor is enforced on every login was
     not verified.
   - Migration for existing accounts: accept both forms for a window, then flag or
     rotate.
6. Hybrid post-quantum TLS at the edge. nginx's documentation describes
   `ssl_ecdh_curve X25519MLKEM768:X25519;` and notes OpenSSL **3.5+** is required;
   older builds ignore or reject the unknown group. The current image is
   `nginx:1.27-alpine`; check `nginx -V` of the image you will ship before relying
   on it. Current Chrome, Edge and Firefox negotiate this group by default. With
   `X25519MLKEM768:X25519`, a client that does not offer the hybrid group still
   connects using classical X25519 alone, so post-quantum key exchange applies only
   to connections that negotiate `X25519MLKEM768`. Listing only the hybrid group
   would refuse such clients (a support-policy decision; not tested here).

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
(the password crossing the wire) and, for clients that negotiate the hybrid
group, covers all traffic with one configuration change. P2 is a data migration with compatibility risk and should happen once P0's
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
  and metadata, without any application protocol, on connections that negotiate
  the hybrid group (a client that falls back to X25519 gets classical key exchange only);
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
- ~~Whether an inactivity auto-lock exists under a name my keyword search missed.~~
  It does: `frontend/src/contexts/VaultContext.jsx` (`DEFAULT_AUTO_LOCK_TIMEOUT = 5`
  minutes, `checkInactivity`), and every lock path goes through `handleLockVault`
  (2026-10-07).
- `@noble/curves` export names used in the plan (flagged as such above).
- The `behavioral_recovery` design intent (F3).
- Maturity of OPAQUE libraries for this stack (JS client, Python server); whether
  the existing second factor is enforced on every login; and that no standardized
  post-quantum aPAKE exists (the search was not exhaustive).
- F10, F13 were **run**, not inferred: each round trip, executed with the real
  methods, fails with `InvalidTag` (2026-10-07).

---

## 9. Second proposal set: infrastructure and client hygiene (2026-10-07)

A second pasted plan proposes Playwright "memory zeroization" audits, an nginx
built against an OQS OpenSSL fork, a production compose stack, GnuPG-encrypted
`pg_dump` backups with a restore drill, Prometheus/Grafana alerting, multi-region
HA with a chaos script, logrotate, a vault integrity command, full-vault key
rotation and a `SecurityAuditEvent` model. Each part was compared with what is in
the repository. As with section 4, the snippets are illustrations, not drop-in code.

### 9.1 Verdicts

| Proposal | What exists today | Verdict |
|---|---|---|
| **Playwright security audits** | `frontend/playwright.config.js` (`testDir: ./e2e`, `@playwright/test ^1.58.1`, 19 specs, `test:e2e:ci`). Auto-lock exists (`VaultContext.jsx`). Clipboard clearing does **not** (F12). | **Adopt, adapted.** Add `frontend/e2e/vault_hygiene.spec.js`: (a) copy a password, then assert the clipboard is cleared after `clipboardTimeout`; this **fails today** and should land with the F12 fix; (b) idle past `autoLockTimeout`, then assert the vault locks. Use `page.clock` (Playwright ≥1.45) instead of the plan's 30 s real `waitForTimeout`s. Do **not** add a `window.VaultMemoryStore` / `executeLockdownTestTrigger` hook: a global that exposes the key in a production bundle is the leak the test claims to check for. Assert on behaviour instead (locked UI, decrypt refused). JavaScript cannot prove memory zeroization; the test can only show that a reference was dropped. Grant clipboard permissions per test (Chromium only), not in the shared config. Do not copy `fullyParallel: false` / `workers: 1` globally: CI already runs one worker. |
| **PQC nginx via OQS OpenSSL fork** | `docker/nginx/nginx.conf`: TLS block commented out; `nginx:1.27-alpine`. k8s edge is **ingress-nginx** (`k8s/ingress.yaml`, TLSv1.3 only, cert-manager). | **Reject the build; keep P1.6.** Errors: `ssl_curves` is not an nginx directive (`ssl_ecdh_curve`); the Dockerfile's `git clone` lines have no `RUN` and truncated URLs; linking `-loqs` into nginx is unnecessary. The standalone OQS OpenSSL fork has been superseded by `oqs-provider` for OpenSSL 3, and OpenSSL **3.5** implements ML-KEM and the `X25519MLKEM768` group natively, so no custom compile is needed. Use an nginx image built on OpenSSL ≥3.5 and check `nginx -V`. In k8s, set `ssl-ecdh-curve: "X25519MLKEM768:X25519"` in the ingress-nginx controller ConfigMap, provided its OpenSSL supports it (not verified). The plan's verification line is also wrong: `s_client`'s "Peer signature type" reports the **signature** algorithm, not the key-exchange group. Its `script-src 'self'` CSP would break the FHE loader (section 4.2). |
| **Production compose stack** | Two compose files (root and `docker/`). The root one mounts `./nginx/...`, which does not exist at the repo root (`docker/nginx/` does). k8s is the production target. | **Reject.** `CMD-SHEEP`; a `DATABASE_URL` that embeds a secrets-file *path* as a password; `core.settings.production` (the module is `password_manager.settings`); `postgres:16` / `python:3.11` (repo: PostgreSQL 17, Python 3.12); `pip install liboqs-python==0.16.0.1` without the C library, which triggers the import-time auto-install that 0.16.0.1 patched for command injection and breaks `DEPENDENCY_POLICY.md` (section 2.4). Separately, decide which compose file is canonical and fix or delete the root one's nginx mounts. |
| **Encrypted backups + restore drill** | k8s `db-backup` CronJob (`k8s/cronjobs.yaml`) runs `manage.py db_backup --output /backups`. **`/backups` is an `emptyDir`**, deleted when the pod exits, and `allow-maintenance` (`k8s/network-policy.yaml`) permits egress to Postgres only. **No backup survives.** The dump is an unencrypted gzipped `dumpdata` JSON, built in memory (`StringIO`) under a 512 Mi limit. | **Adopt the goal; the existing gap is the priority.** Write to durable storage (a PVC, or object storage with a matching egress rule), encrypt **to a public key** (`age` or GPG asymmetric) so the cluster never holds the decryption key, stream instead of buffering, and alert on time since the last *success*. Errors in the plan's scripts: `pg_dump -F c \| gzip` double-compresses; the drill restores a custom-format dump with `psql`, which cannot read it (`pg_restore`); the drill runs `docker run` from inside a container, which needs the host Docker socket (root on the host); GnuPG ≥2.1 batch mode with `--passphrase-file` generally needs `--pinentry-mode loopback`; `--cipher-algo` is ignored on decrypt; the drill queries a `users` table (Django: `auth_user`); writing plaintext to host disk and then `dd`-overwriting it does not reliably erase it on SSD/CoW storage, so stream the restore instead. |
| **Prometheus / Grafana alerting** | `k8s/monitoring/` has Prometheus, Grafana and Alertmanager. `alertmanager-config.yaml`'s only receiver, `default`, has **no** integrations: **alerts fire into nothing.** | **Adopt via Alertmanager, not Grafana provisioning.** Add a real receiver (secret-mounted), then the backup rules. Use `vault_backup_last_success_timestamp`: the plan stamps the timestamp on failure too, so its "stalled" alert would measure attempts, not successes. The plan's Grafana provisioning file does not match the notification-policy schema (it nests `policies` under alert-rule `groups`/`folder`; not run here). It also inlines a PagerDuty routing key, which belongs in a secret. |
| **logrotate in the backup container** | n/a (k8s logs go to stdout). | **Reject** for k8s. As written it also fails: busybox `crond -c` takes a **directory**, not a file; logrotate's trailing `# …` comments after directives are not valid syntax (logrotate(8); not run here). |
| **Multi-region HA + chaos script** | Single-region k8s. | **Defer.** The script stops one local container and polls a URL, so it does not exercise GSLB/DNS failover. CockroachDB is not a drop-in for this codebase's PostgreSQL-specific queries. Out of scope for a PQC plan. |
| **`audit_vault_integrity` command** | `EncryptedVaultItem` has **no** `title_iv` / `payload_iv` / `payload_tag` / `payload_ciphertext`. It stores a versioned `encrypted_data` blob, `crypto_version`, `crypto_metadata`. | **Adapt later (low).** A structural check per `crypto_version` (parse the `svc-gcm-*` envelope; 12-byte IV, 16-byte tag; size ceiling) without decrypting is useful. Raise `CommandError` instead of `sys.exit`, and log item IDs, never owner emails. |
| **Full-vault re-encryption key rotation** | `sessionVaultCryptoV3.changeMasterPassword` **re-wraps the same DEK** under a new KEK (O(1), no item rewrite); `rewrapMasterPasswordFromRecovery`; wrapped-DEK rotation endpoint. | **Reject.** It is a regression from the envelope design (section 5). It also posts `new_auth_hash` to `set_password` (F8's replayable-credential problem) and reads the token from `sessionStorage` (section 4.1). Its `beforeunload` warning protects a non-atomic client loop that the envelope design avoids needing. |
| **`SecurityAuditEvent` model + JSON log** | `security` logger with a file handler (`settings/base.py`); `vault.AuditLog`, `RecoveryAuditLog` (×2), `SocialRecoveryAuditLog`, `password_archaeology.SecurityEvent`. | **Reject the new model**; log password and DEK changes to the existing `security` logger and audit tables. Its `_get_client_ip` trusts the first `X-Forwarded-For` hop. **So does this codebase**, see F14. `failure_reason=str(e)` writes internal errors into a user-visible audit row. |

**F14: client IP is taken from the client-controlled first `X-Forwarded-For`
hop, including for security decisions.** Found while checking the audit-model
proposal. There is no shared, proxy-aware helper. At least eight copies
(`auth_module/utils.py`, `auth_module/recovery_throttling.py`, `middleware.py`,
`auth_module/views.py`, `cognitive_auth/views.py`, …) return
`X-Forwarded-For.split(',')[0]`. Two of them make security decisions:
`ProgressiveLockoutThrottle.get_cache_key` (recovery lockout bucket) and
`middleware.py` `_is_ip_allowed` (`ALLOWED_IP_RANGES`). If the edge forwards a
client-supplied `X-Forwarded-For` unchanged, a client can get a fresh lockout bucket
per request, or claim an allowlisted address. **Exploitability depends on the
ingress-nginx forwarded-header settings, which were not verified.**
`k8s/ingress.yaml` sets neither `use-forwarded-headers` nor
`compute-full-forwarded-for`, and DRF's `NUM_PROXIES` is unset. Fix: one helper
that takes the hop a configured number of trusted proxies back from the right (or
`REMOTE_ADDR` behind a single trusted proxy), used everywhere. Not PQC; its own PR.

### 9.2 Resulting priorities (added to section 6)

- **P0 (ops, not PQC, but most urgent here):** make the k8s backup durable and
  encrypted, and give Alertmanager a receiver. Today there is neither a retained
  backup nor a delivered alert.
- **P0.2b / P0.2c:** F13 (recovery cannot decrypt) and F12 (clipboard clear), the
  latter with the Playwright test above.
- **F14:** confirm the ingress forwarded-header behaviour first. If a
  client-supplied `X-Forwarded-For` reaches Django, this is a P0 lockout and
  allowlist bypass.
- **P1.6** (hybrid TLS) stands, implemented with stock OpenSSL ≥3.5 at the ingress
  rather than a custom nginx build.
- Everything else in 9.1 is "reject" or "defer" as listed.

### 9.3 Not verified in this section

- The OpenSSL version inside the ingress-nginx controller and any nginx image you
  would ship (no image was pulled or run).
- logrotate inline-comment parsing, the Grafana provisioning schema, and GnuPG
  loopback behaviour were taken from their documentation, not run.
- Whether any out-of-repo process (for example a node-level agent) copies the
  `emptyDir` before the backup pod exits. Nothing in the repository does.

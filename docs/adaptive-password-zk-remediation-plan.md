# Adaptive Password — Zero-Knowledge Remediation Plan

Status: **PLAN ONLY — no code changed yet.** Every file path, serializer field,
and service method referenced below was read from the current tree.

## 0. Why

`README.md` makes an unconditional guarantee:

> "Built with a zero-knowledge architecture, your data is encrypted client-side…
> even we cannot access your passwords." (L53) · "Server NEVER sees plaintext
> password" (L1052) · "encrypted client-side before any transmission. The server
> only stores and retrieves encrypted blobs." (L1170)

The adaptive-password feature breaks this. Three endpoints POST **raw plaintext**:

| Endpoint | Raw field(s) sent | Server use today |
|---|---|---|
| `POST /api/security/adaptive/record-session/` | `password` | `hash_password_prefix(password)` (keyed, server key) + `password_length` |
| `POST /api/security/adaptive/suggest/` | `password` | generate substitutions + masked previews (needs the characters) |
| `POST /api/security/adaptive/apply/` | `original_password`, `adapted_password` | store adaptation record |

"Hashed server-side, never stored" ≠ zero-knowledge: the plaintext is present in
server RAM and is exposed to TLS terminators, request/error logs, stack traces,
APM traces, heap/crash dumps, a compromised host, and insiders. This is the real
defect behind the PR #315 CodeRabbit nit.

**Goal:** the server must NEVER receive raw password material from the adaptive
feature, while preserving its value (timing-based learning + memorability
suggestions). Bring it in line with the vault, which already does Argon2id +
AES-GCM client-side (`cryptoService.js`).

## 1. The ZK invariant we will enforce

No adaptive request body, query param, log line, or stored column may contain raw
password characters **or any value from which the password can be feasibly
recovered** (this explicitly excludes bare/unkeyed hashes such as the existing
`getPasswordHashPrefix` = `SHA-256(password)` in `hooks/useTypingPatternCapture.js`,
which is offline-guessable).

Allowed across the wire (all consented):
- bucketized inter-key **timings** and relative **error positions** (already privacy-bucketized);
- a **client-keyed fingerprint** (opaque to the server);
- a coarse **length bucket** (not exact length);
- aggregate **substitution-class** usage/preferences (e.g. "user tends to map `o→0`"), optionally local-DP-noised;
- **masked previews** computed client-side (`ab***yz`).

Enforced by: (a) a frontend "no plaintext on the wire" contract test, and (b) a
backend serializer that **rejects** any legacy `password`/`original_password`/
`adapted_password` field (fail-closed).

## 2. Threat model

- **Server:** honest-but-curious and potentially compromised (logs, proxies,
  memory, insiders, breach). Must be assumable-hostile.
- **Client:** trusted — it already holds the master-derived key and performs vault
  crypto.
- **TLS** protects transit only; the server terminates it and sees plaintext, so
  TLS does not satisfy ZK. Hence all password-touching computation moves client-side.

## 3. Target architecture

Move **client-side** (never leaves the device):
- fingerprint derivation (HMAC), feature extraction, **candidate substitution
  generation**, suggestion ranking, preview generation, adapted-password construction.

Keep **server-side**:
- the RL / preference **learning** (trained only on aggregate, non-reversible
  signals: timings, error histograms, substitution-class acceptances);
- storage of session/adaptation records keyed by **fingerprint**;
- export of a compact per-user **preference model** the client downloads and applies.

New exchange that makes suggestions ZK: instead of POSTing the password to
`/suggest/`, the client `GET`s the learned **preference model** and generates +
ranks the suggestion **locally** from the in-memory password.

### Crypto design (fingerprint)
- `fpKey = Argon2id(masterPassword, salt = perUserSalt, domain="adaptive-fp")`
  — derived **once** per unlocked session, cached in memory, never transmitted.
  Reuse `cryptoService.deriveKey` machinery (argon2-browser already a dep).
- `fingerprint(pw) = base64url( HMAC_SHA256(fpKey, "adaptive-pw|" + pw) )[:24]`
  — **deterministic** (same pw → same fp, enables dedup/correlation), **keyed**
  (opaque + not offline-guessable by the server), **domain-separated**.
- `length_bucket = floor(len(pw) / 4)` (exact length is a strong fingerprinting
  signal; send a bucket).
- `char_classes = { lower, upper, digit, symbol }` counts (optional, coarse,
  local-DP-noised if desired).

`perUserSalt` is a **non-secret** random salt minted per user and stored
server-side; the client fetches it once (it only seeds key derivation and is
useless without the master password). Carry a `fp_key_version` so master-password
rotation can re-base fingerprints intentionally.

## 4. New wire contracts (v2; carry `schema_version: 2`)

**record-session v2** (no password):
```jsonc
{ "schema_version": 2, "password_fingerprint": "…", "length_bucket": 3,
  "keystroke_timings": [..], "backspace_positions": [..],
  "device_type": "desktop", "input_method": "keyboard",
  "substitution_classes_used": [ { "from": "o", "to": "0" } ] }   // optional
```

**suggest v2** — preferred path is a model pull, not a POST:
```jsonc
GET /api/security/adaptive/preference-model/
→ { "model_version": 7, "substitution_weights": { "o": {"0":0.8,…}, … },
    "memorability_params": { … } }
```
Client then runs `generateCandidates(pw)` → `rankSuggestions(candidates, model)`
→ `maskPreview(pw)` locally and renders the suggestion. **No password leaves the
client.** (Optional constrained fallback documented in §10 if a server-scored
path is ever required — it would send only `{fingerprint, candidate_classes,
length_bucket}`, never the password; use only if local ranking proves insufficient.)

**apply v2** (no passwords):
```jsonc
{ "schema_version": 2, "original_fingerprint": "…", "adapted_fingerprint": "…",
  "substitutions": [ { "from": "o", "to": "0", "confidence": 0.9 } ],
  "memorability_improvement": 0.15,
  "previews": { "original_masked": "ab***yz", "adapted_masked": "a0***yz" } }  // optional
```

## 5. Frontend changes

**`src/services/cryptoService.js`** — add:
- `deriveFingerprintKey(perUserSalt)` → Argon2id, cached on the instance.
- `passwordFingerprint(password, perUserSalt)` → derive/load the cached fp key, then WebCrypto `importKey('raw', fpKey, {name:'HMAC',hash:'SHA-256'})` + `sign` → base64url prefix.

**`src/services/adaptive/adaptiveFeatures.js`** (new, pure, unit-testable):
- `extractFeatures(password)` → `{ length_bucket, char_classes }` (no raw chars).
- `generateCandidates(password)` → `[{ position, original_char, suggested_char, reason }]` — **client-only**, from the leetspeak map (port `LEET_MAP` from the backend service §6).
- `rankSuggestions(candidates, preferenceModel)` → selected substitutions + confidence.
- `applySubstitutions(password, subs)` → `adaptedPassword` (client-only).
- `maskPreview(password)` → first 2 + `***` + last 2.

**`src/Components/security/TypingPatternCapture.jsx`** (`useTypingPattern.capturePattern`):
- Replace the pattern object `{ password, … }` (line ~160) with
  `{ password_fingerprint: await fingerprint(password), length_bucket, keystroke_timings, backspace_positions, device_type, input_method }`. **Remove the raw `password` field** and the misleading `// Will be hashed before sending` comment.

**`adaptivePasswordService`** (in `TypingPatternCapture.jsx`):
- `record`: POST v2 payload.
- `suggestAdaptation(password)`: fetch `/preference-model/`, run
  `generateCandidates` + `rankSuggestions` + `maskPreview` locally, return the
  suggestion object — **no password POST**.
- `applyAdaptation`: compute the adapted password locally; POST fingerprints +
  classes + masked previews.

**`src/hooks/useTypingPatternCapture.js`**: drop the bare-SHA-256
`getPasswordHashPrefix`; if a fingerprint is needed here, use the keyed one.

Consumers (`AdaptivePasswordSuggestion`, `TypingProfileCard`) keep their current
prop shapes (previews/fields unchanged) — the suggestion is just produced locally now.

## 6. Backend changes

**`security/serializers/adaptive_serializers.py`**:
- `TypingSessionInputSerializer`: remove `password`; add
  `password_fingerprint` (CharField, validated charset/length), `length_bucket`
  (IntegerField ≥ 0), optional `substitution_classes_used`.
- `ApplyAdaptationSerializer`: remove `original_password`/`adapted_password`;
  add `original_fingerprint`, `adapted_fingerprint`; keep `substitutions`
  (class-level `from`/`to` only); optional masked `previews`.
- New `PreferenceModelSerializer` for the export endpoint.
- Add a shared `validate()` that **rejects** any of `password`,
  `original_password`, `adapted_password` (defense-in-depth, returns 422).

**`security/api/adaptive_password_views.py`**:
- `record_typing_session`: read fingerprint + features; drop `password` handling.
- `suggest_adaptation`: deprecate (return `410`/redirect) in favor of new
  `preference_model` GET view; move suggestion generation to the client.
- `apply_adaptation`: read fingerprints + classes; drop raw passwords.
- New `preference_model(GET)` view → `service.export_preference_model(user)`.

**`security/services/adaptive_password_service.py`**:
- `record_typing_session(fingerprint, length_bucket, …)` — store keyed by
  fingerprint; update RL from aggregate signals; drop `hash_password_prefix(password)`
  ingestion (client now supplies the keyed fp).
- New `export_preference_model(user)` → `{ substitution_weights, memorability_params, model_version }` (no password data).
- `apply_adaptation(original_fingerprint, adapted_fingerprint, substitution_classes, …)`.
- The password-dependent generation/preview helpers move to the client; the
  server keeps only the learning. `LEET_MAP`/reverse maps are ported to the
  frontend `adaptiveFeatures.js` (shared source of truth documented).

**Models** (`security/models/…`; confirm exact module for `TypingSession`,
`PasswordAdaptation`, `UserTypingProfile`):
- `TypingSession`: store `password_fingerprint` + `length_bucket`; ensure no
  column can hold raw or server-hashed-from-raw password. Migration.
- `PasswordAdaptation`: store `original_fingerprint`/`adapted_fingerprint` and
  **masked** previews only. Migration.

## 7. Compatibility, versioning, migration

- Payloads carry `schema_version: 2`. The server accepts **v2 only** and returns
  a clear `400 "client upgrade required"` for v1 — it must **never** silently
  accept plaintext again.
- Feature is already behind enable/consent; gate the cutover with
  `ADAPTIVE_ZK_V2` flag for a clean rollback.
- DB migration: drop/rename any column that held server-side password-derived
  values; behavioral data may simply be re-collected (no backfill needed). Audit
  existing rows for any stored raw/derived password material and null it.
- Master-password rotation re-bases `fpKey` → fingerprints change → correlation
  resets. Document; store `fp_key_version`.

## 8. Testing strategy

- **Leak / contract tests (highest priority — the correct version of the #315 nit):**
  - Frontend: intercept `axios`; for every adaptive call, assert the serialized
    body contains **no** raw password and **no** substring of it.
  - Backend: serializer test asserts payloads containing `password` /
    `original_password` / `adapted_password` are **rejected**; a logging test
    asserts request bodies never surface plaintext.
- **Unit:** `cryptoService.passwordFingerprint` determinism + keyed-ness
  (same pw→same fp; different key→different fp; `fp ≠ SHA256(pw)`).
  `adaptiveFeatures` candidate/rank/apply/mask.
- **Contract:** record/suggest(model-pull)/apply v2 round-trips.
- **Property:** preview masking never reveals more than first-2/last-2;
  fingerprint length/charset invariants.
- **e2e (Playwright):** enable → type → record → suggest (client) → apply →
  rollback, with **network assertions** that no body carries plaintext.
- Update existing adaptive tests (incl. `frontend/src/__tests__/adaptive_password.test.tsx`)
  to v2.

## 9. Rollout — phased PRs

1. **PR-1 (fe crypto):** `cryptoService` HMAC fingerprint + key derivation + unit tests. No behavior change.
2. **PR-2 (fe features):** `adaptiveFeatures.js` (candidate/rank/apply/mask) + unit tests.
3. **PR-3 (be v2 schema):** serializers/models/migration + reject-plaintext validator + `preference_model` endpoint + tests. Behind `ADAPTIVE_ZK_V2`.
4. **PR-4 (wire it):** switch `adaptivePasswordService` + `capturePattern` to v2; suggestions generated client-side; remove raw password. Flip the flag. Leak + e2e tests.
5. **PR-5 (cleanup + docs):** delete dead server-side suggestion/preview paths; update the README ZK section to state adaptive is ZK; remove the misleading frontend comment.

## 10. Risks / open questions

- **Suggestion quality on aggregate-only signals.** The RL no longer sees the
  password, only timings + substitution-class acceptances. Validate suggestion
  quality A/B before/after. If insufficient, the constrained fallback (§4) sends
  only `{fingerprint, candidate_classes, length_bucket}` — still no password.
- **Substitution-class leakage.** `from→to` reveals general habits (e.g. `o→0`),
  not the password. Consented + aggregate; port `add_noise_to_substitutions`
  (already in the service) to the client for local DP if we want stronger guarantees.
- **Exact length.** Always send the bucket, never exact length.
- **Master-password change** invalidates fingerprints (correlation reset) —
  acceptable; documented.
- **Performance.** Argon2id for `fpKey` is heavy — derive once per session and
  cache; per-capture HMAC is cheap.

## 11. Acceptance criteria

- No adaptive endpoint accepts or requires a raw password (serializer-enforced;
  legacy fields rejected with 4xx).
- Frontend + backend leak tests green: plaintext never on the wire or in logs.
- Suggest + apply work end-to-end with client-side generation; feature parity validated.
- README ZK guarantee now holds for adaptive (docs updated to say so explicitly).
- All existing + new tests green; `npm run build` green.

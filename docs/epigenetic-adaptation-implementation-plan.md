# 🧬 Epigenetic Password Adaptation — Implementation Plan

Status: **Phases 1-3 SHIPPED** — see §1.6 (Phase 1, PR #465), §4.5 (Phase 2)
and §5.6 (Phase 3) for what actually landed and where it deviates from this
plan. §0 and the body of §1 below are the **pre-Phase-1 baseline**: every path,
line number, field and symbol in them was read from the tree at `main` =
`0b7ee24`, *before* implementation, and describes the gaps that motivated the
plan — not the current state. Likewise the bodies of §4 and §5 are the
pre-implementation designs; §4.5 and §5.6 record where the shipped code
diverges from them, and win on any conflict. Phases 4-5 are still plan-only.

Companion to `docs/adaptive-password-zk-remediation-plan.md` (the ZK cutover,
already executed). This plan covers what that one deliberately left open.

---

## 0. Verification — what already exists

**The feature is not new.** `settings/base.py:1799` literally titles its config
block `EPIGENETIC PASSWORD ADAPTATION CONFIGURATION`, and the requested
capability ships today as the **Adaptive Password** feature. Roughly 70% is
built, and the parts that are built are good.

### 0.1 Present and working

| Layer | Artifact | Assessment |
|---|---|---|
| Models | `security/models/core.py:954-1410` — `AdaptivePasswordConfig`, `TypingSession`, `PasswordAdaptation`, `UserTypingProfile`, `AdaptationFeedback` | Complete. Migrations `0019_adaptive_zk_v2_fields` / `0020_..._drop_legacy_columns` already removed the plaintext-derived columns. |
| Service | `security/services/adaptive_password_service.py` (777 L) | `record_typing_session_v2`, `export_preference_model`, `apply_adaptation_v2`, `rollback_adaptation`, `delete_all_data`. Row-locked, atomic, partial-unique-constrained rollback chain. |
| Privacy | `PrivacyGuard` (same file, L87-326) | Real DP: pydp `BoundedMean` with a numpy-Laplace fallback that uses rejection sampling to stay in-bounds; composition-theorem budget accounting. |
| Serializers | `security/serializers/adaptive_serializers.py:337-483` | `RejectPlaintextMixin` → **HTTP 422** on any `password` / `original_password` / `adapted_password`, checked in `to_internal_value` so it fires *before* field validation. `SchemaVersionMixin` pins v2, no silent v1 fallback. Substitutions restricted to single-char `{from,to,confidence}` with unknown-key rejection. |
| API | `security/urls.py:163-192` — 15 endpoints; `/adaptive/suggest/` returns **410 Gone** | Complete. |
| Client crypto | `frontend/src/services/cryptoService.js:220-309` | `deriveFingerprintKey` (Argon2id, **deliberately no PBKDF2 fallback** — fails closed rather than emitting a divergent fingerprint), `passwordFingerprint` → 144-bit base64url HMAC-SHA256, non-extractable key, domain-separated by `:adaptive-fp`. |
| Client engine | `frontend/src/services/adaptive/adaptiveFeatures.js` | Pure, side-effect-free: `extractFeatures`, `generateCandidates`, `rankSuggestions`, `applySubstitutions`, `maskPreview`. |
| Client UI | `TypingPatternCapture.jsx` (+ inline `adaptivePasswordService`), `AdaptivePasswordSuggestion.jsx`, `TypingProfileCard.jsx`, `hooks/useTypingPatternCapture.js` | Built — but see §0.2 D1: **not mounted anywhere.** |
| Admin | `security/admin_adaptive.py` (413 L) | Complete. |
| Tests | `test_adaptive_password.py` (938 L), `test_adaptive_zk_v2.py` (424 L), `adaptive_password.test.tsx`, `adaptiveZkLeak.test.jsx`, `adaptiveFeatures.test.js`, `cryptoService.fingerprint.test.js`, `e2e/adaptive_password.spec.ts` | Substantial, with real leak/contract tests. |

### 0.2 Gaps — the actual work

**A. Zero-knowledge blockers**

- **A1 — No per-user fingerprint salt exists anywhere.**
  `cryptoService.deriveFingerprintKey(perUserSalt)` (`cryptoService.js:230`)
  throws without one. There is **no model field, no endpoint, and no client
  store** for it in the entire repo — `grep` for `fingerprint_salt|adaptive_salt|
  fp_salt` returns only the remediation plan's own prose and an unrelated
  `PREDICTIVE_FINGERPRINT_SALT`. The remediation plan §3 specified it; it was
  never built. **The ZK feature cannot execute at all in its current state.**
- **A2 — `fp_key_version` missing.** Remediation plan §7 required it so master-password
  rotation re-bases fingerprints intentionally. Absent from models, API and client.
- **A3 — `mobile/src/services/AdaptivePasswordApi.js` is still v1.** `suggestAdaptation`
  (L75-82) POSTs raw `password`; `applyAdaptation` (L87-95) POSTs raw
  `original_password` + `adapted_password`. The backend now rejects both (410 /
  422), but the plaintext still leaves the device and lands in mobile logs and
  any intermediary. `mobile/src/screens/AdaptivePasswordScreen.js:27` imports it.
  Neither is registered in a navigator, so it is dormant — but it is live code.

**B. The headline claims are not implemented**

- **B1 — "Uses reinforcement learning": there is no RL.**
  `security/tasks/adaptive_tasks.py:139-209` computes per-substitution rewards
  and then **logs them**. Line 198 says so outright: *"In a full implementation,
  this would update a persistent RL model."* No bandit, no policy, no model table.
- **B2 — The learning loop is open at both ends.**
  `apply_adaptation_v2` never touches `UserTypingProfile` — accepting a
  suggestion teaches the model nothing. And `capturePattern`
  (`TypingPatternCapture.jsx:165-174`) never sends `substitution_classes_used`
  or `success`, so `_record_substitution_classes` (service L447) is unreachable
  from the real client path. Net effect: `export_preference_model` can only ever
  return the static leetspeak baseline (0.6 primary / 0.4 secondary, service
  L541-545). **Nothing personalizes.**
- **B3 — "Learn from your typing errors": errors are collected but never read.**
  `UserTypingProfile.error_prone_positions` is written and decayed
  (service L498-507) and is **not consulted by any suggestion path**.
  `rankSuggestions` scores purely on substitution-class weights.
- **B4 — "Optimize memorability": there is no memorability model.**
  `export_preference_model` returns `memorability_params` hard-coded
  (service L580-589) and **the client never reads them** — `adaptiveFeatures.js`
  has no memorability function at all. `suggestAdaptation`
  (`TypingPatternCapture.jsx:361-364`) fabricates
  `min(0.3, confidence*0.15 + count*0.03)`. And `apply_adaptation_v2` writes
  `memorability_score_before/after = None` (L692-693), so
  `get_evolution_stats`'s `average_memorability_improvement`
  (`adaptive_password_views.py:376-385`) is **always 0**.
- **B5 — "Gradually morph": no cadence is enforced.**
  `AdaptivePasswordConfig.should_suggest_adaptation()` (`core.py:1026`) is
  referenced **only in tests**. `auto_suggest_enabled`,
  `auto_apply_high_confidence`, `AUTO_APPLY_THRESHOLD` and
  `MIN_SESSIONS_FOR_SUGGESTION` are stored and admin-displayed but never acted on.
- **B6 — Dead model fields.** `rhythm_signature`, `common_error_types`,
  `wpm_variance`, `attempt_number` are modelled and admin-surfaced, never written.

**C. A security-correctness defect in the concept**

- **C1 — "Harder for attackers" is false as implemented.**
  The only transform is canonical leetspeak (`LEET_MAP`,
  `adaptiveFeatures.js:31-41`) — exactly what hashcat's `best64`/`leetspeak`
  rules and zxcvbn's l33t matcher already model. `password → p@ssw0rd` *lowers*
  guess-resistance. There is **no strength guard anywhere**: not in
  `rankSuggestions`, not in `applySubstitutions`, not in the serializer, not in
  the service.
  This repo already knows the attack: `frontend/src/services/predictive/clientPatternEngine.js`
  ships `normalizeLeet()` + `hasDictionaryBase()` precisely to de-leet a password
  before dictionary-matching it. The adaptive feature is generating the pattern
  that its own sibling module de-obfuscates.
- **C2 — Nothing rotates the actual credential.** `applyAdaptation` returns
  `adaptedPassword` in memory (`TypingPatternCapture.jsx:429`) and the caller is
  on its own; there is no wiring into the vault update path.

**D. Not shipped**

- **D1 — Zero UI surface.** `App.jsx` is 2106 lines with ~60 routes and **no
  adaptive route, import, or nav link**. The three components and the hook are
  orphaned — outside their own files, the only references in the whole repo are
  from test files.
- **D2 — A permanently-failing e2e spec.** `frontend/e2e/adaptive_password.spec.ts`
  is collected by `playwright.config.js` (`testDir: './e2e'`), carries no skip
  markers, and drives `[data-testid="adaptive-password-tab"]`, which does not
  exist. It is dormant rather than red only because Playwright is not wired into
  CI (`grep -i 'playwright|e2e' .github/workflows` → no matches).
- **D3 — No Celery beats.** `celery.py:79` has a `beat_schedule`; none of
  `aggregate_typing_profiles`, `cleanup_expired_adaptations`,
  `update_rl_model_from_feedback` appear in it. The backend tests for all three
  are `assertTrue(callable(...))` only (`test_adaptive_password.py:925-941`) —
  they assert nothing about behaviour.
- **D4 — The feature flag is inert.** `ADAPTIVE_PASSWORD['ENABLED']`
  (`settings/base.py:1804`) is read by no view. `/adaptive/enable/` works with
  the flag off.

**E. Name collision — do not touch**

`security/services/epigenetic_service.py`, `EpigeneticEvolutionCard.jsx`,
`GeneticEvolutionLog`, `DNAConnection` belong to a **different premium feature**:
DNA/biological-age password evolution via the Humanity.health API. Same word,
unrelated code. Nothing in this plan modifies it.

---

## 1. Zero-knowledge compatibility

**Verdict: compatible, and already architected correctly.** The v2 design is ZK-sound.

The server may hold, and this plan keeps it to: keyed HMAC fingerprints (opaque),
coarse length buckets, bucketized inter-key timings, error positions,
substitution *classes*, client-masked previews, and accept/reject/rollback/rating
events. It never receives password characters. `RejectPlaintextMixin` enforces
this fail-closed at the serializer, independent of any flag.

Three consequences that shape every phase below:

1. **All password-touching computation stays client-side.** The memorability
   scorer and the strength gate must live in `adaptiveFeatures.js`, not in the
   service. The server learns *parameters*; the client applies them.
2. **The reward signal must be derived from the fingerprint chain, not the
   password.** This is the key enabling insight for the RL work: because
   `PasswordAdaptation` links `original_fingerprint → adapted_fingerprint` and
   `TypingSession` is keyed by fingerprint, the server can measure *"did this
   user's error rate and entry time actually improve after this adaptation"* —
   a genuine behavioural reward — **without ever knowing either password.**
3. **The strength gate is necessarily client-only.** The server cannot verify it.
   That is acceptable: the server never applies anything, it only records. A
   client that records a weakening adaptation harms only itself. Document as an
   accepted asymmetry.

**One residual property to document (not a blocker):** fingerprints are only as
strong as the master password. An adversary who obtains the master password can
brute-force `fingerprint(pw)` over a candidate dictionary, since HMAC is fast.
Under the stated threat model (hostile server, master password never transmitted)
this is out of scope — but it argues for keeping the 144-bit truncation and for
not storing more fingerprints than necessary.

---

## 2. Decisions taken

| # | Decision | Rationale |
|---|---|---|
| D-1 | **Full productionization** | Close the learning loop, add the safety gate, ship the UI, schedule the beats. |
| D-2 | **Delete the mobile v1 client** (`AdaptivePasswordApi.js`, `AdaptivePasswordScreen.js`) | No navigator imports them, so nothing breaks. Porting to ZK v2 needs an Argon2 binding for React Native — its own project. Removing the plaintext path now is strictly better than guarding it. |
| D-3 | **Add a zxcvbn strength gate, keep leetspeak** | Makes the "harder for attackers" claim true instead of retracting it. Lazy-loaded so the main bundle is unaffected. |

---

## 3. Phase 1 — Unblock (the feature currently cannot run)

**Goal:** a real user can enable the feature and have a fingerprint computed.

### 1.1 Per-user fingerprint salt — backend

`security/models/core.py`, on `AdaptivePasswordConfig` (after L995):

```python
fingerprint_salt = models.CharField(
    max_length=64, blank=True, default='',
    help_text="Non-secret per-user salt seeding the client fingerprint KDF. "
              "Useless without the master password (never transmitted).")
fp_key_version = models.PositiveIntegerField(
    default=1,
    help_text="Bumped on master-password rotation so fingerprint eras never mix.")
```

Add the same `fp_key_version` (PositiveIntegerField, default 1, indexed with
`user`) to **`TypingSession`** and **`PasswordAdaptation`**, so rows from
different key eras are never correlated as if they were the same password.

- Mint the salt in `enable_adaptive_passwords` (`adaptive_password_views.py:72`)
  via `secrets.token_hex(16)` — **only when blank**, so re-enabling never
  silently invalidates an existing profile.
- Return `fingerprint_salt` + `fp_key_version` from `get_adaptive_config`
  (L144-154).
- Filter every read path (`export_preference_model`, `get_adaptation_history`,
  `get_evolution_stats`, `get_typing_profile`) by the config's **current**
  `fp_key_version`.
- New migration. Data migration: backfill a salt for existing enabled configs.
  *(Shipped as `0024_adaptive_fingerprint_key_era.py` — the number in this plan
  was a placeholder written before implementation; `0021`–`0023` were taken by
  unrelated migrations that landed on `main` first.)*

**Rotation endpoint:** `POST /adaptive/rotate-fingerprint-key/` → new salt,
`fp_key_version += 1`. Old rows are retained but excluded from learning. Hook it
into the existing master-password-change flow.

> **Verified during implementation (pre-Phase-1 note, now resolved):** the
> salt-in-`/config/` exposure was checked against the actual key derivation —
> `_deriveFingerprintKeyBits` (`cryptoService.js:269`) composes
> `` `${perUserSalt}:adaptive-fp` `` as the Argon2id *salt* with
> `this.masterPassword` as the *password*. Inverting a fingerprint therefore
> requires the master password, which the server never has. The salt alone is
> inert. This matched remediation plan §3, confirmed by re-deriving it at
> implementation time rather than trusting this paragraph — the confirmation
> is now recorded as a code comment on `AdaptivePasswordConfig.fingerprint_salt`
> in `security/models/core.py`.

### 1.2 Wire the salt through the client

- `adaptivePasswordService.getConfig()` (`TypingPatternCapture.jsx:300`) already
  hits `/adaptive/config/`; capture `fingerprint_salt` + `fp_key_version`.
- Add `adaptivePasswordService.makeFingerprinter(salt)` returning
  `(pw) => cryptoService.passwordFingerprint(pw, salt)`, so every call site
  (`capturePattern`, `applyAdaptation`, `useTypingPatternCapture.endCapture`)
  takes the same injected function.
- Send `fp_key_version` in the v2 payloads; add it to
  `TypingSessionInputV2Serializer` and `ApplyAdaptationV2Serializer` (integer,
  required, must equal the server's current version → else 409 "key era
  mismatch, re-derive"). This is the fail-closed guard against a stale client
  poisoning a fresh profile.

### 1.3 Enforce the feature flag

Add `@require_adaptive_enabled` (503 + `{"code": "feature_disabled"}`) to
`adaptive_password_views.py`, reading `ADAPTIVE_PASSWORD['ENABLED']`.

**Exempt three of the 16 views**, not all of them: `disable_adaptive_passwords`,
`delete_adaptive_data` (erasure), and `export_adaptive_data` (portability).
Opting out and exercising GDPR rights must survive an operator flipping the
kill switch off — a disabled deployment is not a reason to make a user's data
unreachable. The other 13, including `suggest_adaptation` and
`get_feedback_for_adaptation`, stay gated: for `/adaptive/suggest/`
specifically, the flag check runs first, so a disabled deployment returns 503
there too, not the 410 it returns when enabled.

### 1.4 Delete the mobile v1 plaintext client (D-2)

- Delete `mobile/src/services/AdaptivePasswordApi.js` and
  `mobile/src/screens/AdaptivePasswordScreen.js`.
- `grep -rn "AdaptivePasswordApi\|AdaptivePasswordScreen" mobile/` first to
  confirm no navigator registers them (current tree: only self-references).
- Add a CI guard regardless — a `rg` step failing on
  `original_password|adapted_password` under `mobile/` and `frontend/src/`,
  so the v1 shape can never reappear.

### 1.5 Tests

- Serializer: `fp_key_version` mismatch → 409; missing → 400.
- Salt is minted once and stable across repeated `/enable/` calls.
- Rotation bumps the version and excludes prior-era rows from
  `export_preference_model`.
- Flag off → the 13 gated endpoints 503; `disable`/`data`/`export` still
  200 (GDPR endpoints are deliberately not gated — see §1.3).
- **Leak test extension:** assert `/adaptive/config/` never returns anything
  password-derived, only the salt and version.

### 1.6 As shipped — status and deviations

**Status: SHIPPED.** [PR #465](https://github.com/Rajarshi1-source/Modern_Password_Manager01/pull/465),
branch `feat/adaptive-zk-phase1-fingerprint-salt`. Two commits:
`7119bad` (initial implementation) and `d6e0e89` (review-fix round, below).

**Deviation from §1.1's read-path list.** This plan named
`export_preference_model` and `get_typing_profile` as era-filtered targets.
Re-derived at implementation time rather than taken on faith: both read
`UserTypingProfile`, which holds behavioural aggregates (WPM, error-prone
positions, substitution-class preferences) that describe the *user*, not any
particular password — they stay valid across a rotation, and filtering them
would be meaningless. **Only the two fingerprint-keyed tables
(`TypingSession`, `PasswordAdaptation`) are era-scoped** — via
`get_adaptation_history`, `get_evolution_stats`, the `apply_adaptation_v2`
chain-parent lookup, and `rollback_adaptation`. Documented in the service's
`export_preference_model` docstring. Any later phase that reads
`UserTypingProfile` should follow this precedent, not §1.1's original wording.

**Review-fix round (`d6e0e89`), on CodeRabbit findings against `7119bad`:**

- `rollback_adaptation` (pre-existing code — not introduced by this PR, only
  touched to add the era filter) mutated two `PasswordAdaptation` rows as
  independent `.save()` calls with no transaction. A failure between them left
  the chain with no active row at all, and reactivating the parent could raise
  an unhandled `IntegrityError` against the era-scoped
  `uniq_active_original_fp_per_user` constraint. Fixed to mirror
  `apply_adaptation_v2`'s existing `transaction.atomic()` +
  `select_for_update()` + `IntegrityError`-guard pattern in the same file.
- `scripts/check-adaptive-zk-client.sh`'s `grep ... || true` collapsed "no
  matches" (exit 1, clean) and a genuine scan failure (exit 2+: bad pattern,
  unreadable file, wrong directory) into the same "OK" result for this CI
  security gate — a fail-open bug in a check whose entire purpose is failing
  closed. **CodeRabbit's own proposed rewrite for this
  (`if ! hits=$(...); then grep_status=$?; ...`) was itself broken**: `!`
  collapses the underlying command's exit code to a plain 0/1, so
  `grep_status` inside the `then` branch was never grep's real status —
  applying it as given made the guard report "grep failed" on every normal,
  clean run. Caught only by testing the exact proposed pattern against an
  actual clean tree before adopting it, not by reading it. Fixed by reading `$?`
  directly after the assignment (`hits="$(...)"; grep_status=$?`), which bash
  preserves correctly. See [[darkprotocol-tor-phase3]] — "a reviewer's
  suggested remedy for a real gap can itself be wrong; verify the fix's own
  mechanism" is now a repeated pattern across two unrelated features.
- A second CodeRabbit suggestion (assert `onError` was called on
  `TypingPatternCapture`) rested on a premise that's false for this codebase:
  the `TypingPatternCapture` *component* (as opposed to the
  `useTypingPattern`/`useTypingPatternCapture` hooks) does not accept or
  forward an `onError` prop at all — it always wires the hook's `onError` to
  its own internal `setState`. Applying the suggested assertion literally
  produces a test that can never pass. Fixed by asserting on the one side
  effect the catch block actually produces unconditionally on that component:
  `console.error`.
- Also fixed: a test-constant reference bug (two payload builders in
  `test_adaptive_zk_v2.py` hardcoded `fp_key_version: 1` instead of the class's
  `FP_KEY_VERSION`, so changing the constant would break every test in the
  class with a 409 — exactly the trap the class's own docstring warns about);
  a coverage gap (`/adaptive/rollback/` missing from the flag-gating test
  matrix, despite being decorated with `@require_adaptive_enabled`); and a
  weak assertion in `test_era_is_stamped_from_the_server_not_the_payload`,
  hardened with response-status checks and a `refresh_from_db()` comparison —
  though it's documented in that test that the serializer's 409-on-mismatch
  means payload and config are necessarily equal at request time, so the test
  still cannot fully distinguish "stamped from payload" from "stamped from
  config" without mocking, which was judged disproportionate for what
  CodeRabbit itself labeled a trivial finding.
- **Declined, with reasons recorded in the commit:** batching the migration's
  salt-backfill loop with `bulk_update` (CodeRabbit's own "Low value" label;
  `AdaptivePasswordConfig` is bounded by feature opt-in, not the full user
  base, and it's a one-time deploy-time backfill). The failing "Dependency
  Vulnerability Scan" CI check (expired pip-audit suppressions,
  `PYSEC-2025-183`/`PYSEC-2024-277`) — confirmed via `git diff --stat` that
  this PR touches zero dependency/ignore files; the failure predates it and is
  out of scope. (Superseded once the entries actually crossed their
  `2026-08-01` expiry and started hard-failing the PR's own merge gate — see
  the fifth PR #466 review-fix round below, where renewing them became this
  PR's own scope rather than a pre-existing, unrelated failure.)

**A pre-existing lesson, reconfirmed, not a new bug:** during the *initial*
implementation (`7119bad`), a shared mutable class-level `dict` used as
serializer `context` in `test_adaptive_zk_v2.py` leaked state between tests —
one test's mutation of the dict silently broke two unrelated tests. Fixed
before that commit landed (each serializer now gets a fresh `dict` via a
`_context()` helper) — recorded here because it's the same class of failure
as the CodeRabbit-suggested-fix bug above: **a test (or a fix) that merely
looks right has to be run, not just read**, whether the code was written by
this agent or suggested by a review tool.

**Second review-fix round, on the automatic CodeRabbit pass against `d6e0e89`
(the diff between `7119bad` and `20278fb`):** one actionable finding —
`check-adaptive-zk-client.sh`'s empty-`CLIENT_DIRS` branch (`exit 0` when none
of `frontend/src`/`mobile`/`desktop/src`/`browser-extension/src` exist) was
the *same bug class* as the grep-error fail-open from the first round, just at
the directory-discovery step instead of the scan step: if every candidate
directory were renamed or removed (adversarially or by accident), the guard
would report a clean pass having scanned nothing. Fixed by hard-requiring
`frontend/src` — the actual client for this feature, always present in a real
checkout of this repo (no sparse-checkout in CI) — and treating its absence as
a hard error; the other three directories stay best-effort. This closes the
guard's blind-spot pattern for a second time: **the "no work to do, exit 0"
branch is exactly where a fail-closed security gate needs the most scrutiny,
not the least** — it's the one path with no positive evidence backing the
success it reports. Verified against all four states (clean tree, planted
violation, clean again, and a simulated checkout with `frontend/src` itself
removed) before committing.

**Third review-fix round, on a full CodeRabbit pass against the diff between
`0b7ee24` (base) and `457633e`.** Four findings, all verified against current
code before any change:

- **Migration correctness (real, not hypothetical for this project).**
  `backfill_fingerprint_salts` queried/wrote through the default manager
  instead of `schema_editor.connection.alias`. This project actually has
  `DATABASE_ROUTERS = ['shared.db_router.PrimaryReplicaRouter']` configured
  (confirmed by reading `settings/base.py` and `shared/db_router.py`), which
  routes reads to a `replica` database whenever one is configured — so without
  `.using(alias)`, the migration's read could look at a different connection
  than the one actually being migrated. Fixed with `.using(db)` +
  `bulk_update(..., batch_size=500)`. The paired `drop_fingerprint_salts`
  reverse function was also confirmed dead: Django reverses a migration's
  `operations` bottom-to-top, so `RunPython`'s `reverse_code` (last in forward
  order) runs *before* `AddField`'s own reverse — `RemoveField`, which drops
  the column outright — meaning whatever the blanking function did is
  immediately discarded regardless. **Verified empirically, not just by
  reasoning**: migrated forward on a throwaway sqlite DB, set a salt, migrated
  back to `0023`, confirmed the column itself is gone either way. Replaced with
  `migrations.RunPython.noop`. Re-verified the fixed migration end-to-end
  afterward (forward backfill on a pre-existing raw-SQL-inserted row, reverse,
  re-forward) — all three steps correct.
- **Doc-vs-code drift (real).** The plan's header still said "PLAN ONLY — no
  code changed" after three shipped commits; §1.3 said `@require_adaptive_enabled`
  covers "all 15 views" when it actually exempts 3 (disable/erasure/export, by
  design — GDPR rights survive the kill switch); and a "Verify before
  implementing... time rather than trusting this paragraph" callout was still
  phrased as a pending action after the verification had already happened and
  been folded into a code comment. All three fixed with minimal, targeted edits
  rather than rewriting the historical sections (§0 and most of §1 are
  correctly framed as the pre-Phase-1 baseline once the header says so).
- **A genuine TOCTOU race, the highest-severity finding of the three rounds so
  far.** The view reads the current `fp_key_version` and the serializer
  compares the client's claimed value against it (409 on mismatch) — but the
  *service* then did its own **independent, unlocked** re-read of the config
  and stamped from *that*, discarding the already-validated value entirely.
  If `rotate_fingerprint_key` commits in the gap between the two reads, a row
  gets stamped with the new era while its fingerprint was actually derived
  under the old salt. Fixed by threading the validated `fp_key_version` through
  to both `record_typing_session_v2` and `apply_adaptation_v2` as
  `expected_fp_key_version`, re-checked against the service's own fresh
  config read (still needed for the opt-in gate) — a divergence returns a new
  `fp_key_era_changed` error, mapped to 409 by both views via a shared
  `_service_error_response` helper, telling the client to re-fetch and retry
  rather than silently writing an unreproducible row. **Considered and
  rejected** a simpler alternative (stamp with the validated value directly,
  no re-check) — semantically defensible since the fingerprint genuinely was
  derived under that era regardless of what the config says by write time —
  but rejected for consistency with this feature's established "fail closed on
  an unverified state" posture (same reasoning as `FingerprintKeyVersionMixin`'s
  missing-context handling). Per this project's own repeated lesson about race
  tests needing the actual interleaving, not a race-and-hope: the four new
  tests reproduce the race *deterministically*, not by attempting real
  concurrency — two call the service directly with a mismatched
  `expected_fp_key_version` against the DB's actual value, two mock
  `_current_fp_key_version` at the view layer to make the serializer validate
  against a stale reading while the DB has already moved on. **Verified the
  tests can fail**: neutralized both guards (`if False:` in place of the
  comparison) and confirmed all four tests failed before restoring the real
  code — caught and fixed one bug in my own first draft of these tests in the
  process (a config left at its default era-1 value, so the "mismatch" I
  intended to create didn't exist; the test passed for the wrong reason until
  the mutation check exposed it).

Verified after this round: 1013 passed / 6 skipped (security backend suite,
+5 from the 5 new tests — 4 for the race, 1 for the None-default backward-compat
case), Django `check` clean, `makemigrations --check` clean.

**Fourth review-fix round, on a CodeRabbit pass against the diff between
`457633e` and `3ebd725` (i.e. reviewing the third round's own fix).** Two
findings — one applied, one declined after tracing it through the actual
current code rather than the general heuristic behind it.

- **Applied: bound the salt-backfill's memory use.** The third round's own fix
  already added `bulk_update(..., batch_size=500)`, but `batch_size` on
  `bulk_update` only bounds how many rows go into each SQL statement — it does
  nothing about how many model instances are held in memory *before* the first
  UPDATE, and the code built that full list up front via
  `list(Config.objects.using(db).filter(...))`. Fixed by iterating the
  queryset with `.iterator(chunk_size=500)` and flushing a bounded buffer via
  `bulk_update` as it fills, so peak memory is O(batch) instead of O(rows).
  Verified end-to-end on a throwaway sqlite DB with 1203 pre-existing rows
  (deliberately > 2 batch boundaries): every row got a unique 32-char hex
  salt, and the reverse/re-forward cycle from the prior round's test still
  passes unchanged.
- **Declined: locking `AdaptivePasswordConfig` with `select_for_update()` in
  `record_typing_session_v2`, `apply_adaptation_v2`, and `rollback_adaptation`.**
  The claim was that the config read isn't locked against the write, so a
  rotation committing in between "permits stale-era rows or rollback-chain
  changes." Traced all three call sites against the exact current code
  (line-by-line, not from memory) before deciding: in every one, `config` is
  fetched **exactly once**, and that same in-memory `config.fp_key_version` is
  reused for both the check (the third round's `expected_fp_key_version` fix)
  and every subsequent read/write — there is no second database read that
  could observe an intervening rotation. Since Postgres/MySQL both give
  READ COMMITTED MVCC snapshots per statement (no torn reads), and the
  rotation endpoint's own `select_for_update()` only blocks *other*
  `select_for_update()` callers (not plain reads), the two possible outcomes
  of a genuinely concurrent rotation are: the read happens before the
  rotation commits (uses the pre-rotation era, which is *correct* — the
  fingerprint really was derived under it) or after (uses the post-rotation
  era, also correct, or caught by the mismatch check if it disagrees with what
  the view validated). Could not construct a scenario where the current code
  produces an inconsistent stamp or a corrupted chain. Concluded the suggested
  lock would add real contention on `record_typing_session_v2` — a
  per-keystroke-session hot path — against `rotate_fingerprint_key` and
  against itself under concurrent devices, without closing a gap that exists.
  This is the *pattern*, not the same finding, as trap 3/6's "verify the fix's
  own mechanism" — here the reviewer's general heuristic ("reads before writes
  should be locked") didn't survive contact with what the actual code does
  with the value it reads.

Verified after this round: 110 passed / 10 subtests (adaptive test files),
Django `check` clean, `makemigrations --check` clean.

**Fifth review-fix round, on a full CodeRabbit re-review (base `0b7ee24` against
`d9ddc67`, i.e. the whole PR to date).** Six findings — two applied, one
partially applied (documentation only), three declined, each verified against
current code first.

- **Applied: `enable_adaptive_passwords` never validated `suggestion_frequency_days`
  / `differential_privacy_epsilon`.** Confirmed real: the view copies both
  straight from the request body into `update_or_create()`, which writes to
  the DB with no `full_clean()` — nothing stopped a caller posting `epsilon=99`
  or `frequency_days=-5`. Fixed with inline range validation (1-365 /
  0.1-1.0, matching the model's own `help_text`) returning 400 on an
  out-of-range or non-numeric value. **Note on severity, corrected from the
  original claim**: the finding's justification said this "governs the noise
  applied to this user's own data" and "makes `should_suggest_adaptation`
  return true on every check" — traced both claims against the actual code
  before accepting them, and neither currently holds. `AdaptivePasswordService.__init__`
  constructs `PrivacyGuard()` with **no arguments**, so DP noise always uses
  the hardcoded 0.5 default — the stored `differential_privacy_epsilon` is
  presently dead data, never read by the noise path. `should_suggest_adaptation()`
  has no callers anywhere outside tests (already documented in §0.2 as gap
  B5). Fixed anyway, as data-hygiene/defense-in-depth: both fields will
  matter the moment Phase 3/5 wires them up, and a garbage value already
  sitting in the DB from an unvalidated `/enable/` call would become a live
  landmine at that point with no additional review.
- **Applied: N+1 query in `get_adaptation_history`.** `can_rollback()` reads
  `self.previous_adaptation` (a FK) on every row where `status == 'active'`
  (Python's `and` short-circuits the check before it for other statuses), and
  the queryset didn't `select_related` it — up to 20 extra per-row SELECTs.
  Fixed with `.select_related('previous_adaptation')`. Verified the fix
  matters, not just applied it: built two independent two-generation chains
  (a first-generation row has `previous_adaptation_id IS NULL`, which Django
  resolves without a query, so the regression only shows up on *chained*
  active rows) and asserted via `CaptureQueriesContext` that query count
  doesn't grow between one chain and two. Mutation-checked: temporarily
  stripped `select_related`, confirmed the query count actually diverged
  (5 → 6), restored the real code.
- **Declined: `check-adaptive-zk-client.sh`'s doc reference.** Claimed the
  script points to a nonexistent `docs/adaptive-password-zk-remediation-plan.md`.
  Checked — the file exists (14.5KB, predates this PR) and is the correct
  reference for that specific message: it's the ZK-architecture rationale doc
  (why raw passwords must never cross the wire), which is more relevant to a
  plaintext-violation error than the Phase 1 implementation plan or the
  user-facing API doc would be. The reviewer's own proposed verification
  script (`fd -a '...' . || true`) was itself phrased as a check for whether
  the file exists — running it would have shown the answer before the finding
  was posted.
- **Declined: `test_ensure_is_idempotent` should `refresh_from_db()` to prove
  persistence.** `ensure_fingerprint_salt()`'s own docstring states "Does NOT
  save — the caller decides the transaction boundary" — a deliberate contract
  that `/enable/` and `/config/`'s self-heal path rely on (they call
  `ensure_fingerprint_salt()` then `.save(update_fields=[...])` themselves,
  under a lock). Verified empirically rather than just reading the docstring:
  called the method once, then `refresh_from_db()` with no intervening
  `.save()` — the salt reverted to `''`, so the suggested assertion
  (`config.fingerprint_salt == first`) would fail against the current,
  *correct* implementation. Applying it verbatim would have broken a passing
  test testing the right thing; persistence-through-the-API is already
  covered by `test_config_returns_salt_and_era`, which is the correct layer
  for that property.
- **Documentation only, not a code bug: off-by-one in the view count.** The
  plan's §1.3/§1.5 said "15 views... 12 gated." Recounted directly from
  `urls.py` (16 `path('adaptive...)` entries) and the view decorators (13
  `@require_adaptive_enabled`, 3 exempt) — `get_feedback_for_adaptation` had
  been missed in the original count. Both counts corrected in §1.3 and §1.5;
  the round-3 log entry a few paragraphs above (which correctly reported what
  round 3 believed *at the time*) is left as an honest historical record
  rather than retroactively edited.
- **Documentation only: two stale-status fixes.** The acceptance-criteria list
  (§9 item 1) still said "fails today — A1" for the exact blocker Phase 1
  shipped; marked met. `ADAPTIVE_PASSWORD.md` called `update_rl_model_from_feedback`
  "the weekly" task — confirmed via `celery.py`'s `beat_schedule` that no
  entry exists for it yet (a Phase 5 item, §7); reworded to say so explicitly
  rather than implying it already runs on a schedule.

Verified after this round: 1018 passed / 6 skipped (+5), 27 subtests (+10),
Django `check` clean, `makemigrations --check` clean.

**Sixth review-fix round, on a full CodeRabbit re-review (base `0b7ee24`
against `5c04ab8`).** Four findings — two applied to the plan doc, one
applied to the CI guard (a genuine, present-day gap, not just the hypothetical
the finding described), one declined after direct verification.

- **Applied: the CI guard's inclusion list missed a real client directory.**
  `check-adaptive-zk-client.sh` scanned `frontend/src` + `mobile`/`desktop/src`/
  `browser-extension/src` (if present). Checked whether the finding's
  "renamed directory" scenario had *already* happened rather than treating it
  as hypothetical: it had — `shared/` is a real top-level directory with real
  JS files, and `frontend/src/services/webSecureStorage.js` imports
  `shared/crypto/secure_storage` directly, so `shared/` genuinely ships in the
  client bundle and was never scanned. Fixed by switching to an exclusion
  list (scan every top-level directory except known non-client ones), which
  fails in the safe direction if it goes stale (an unlisted new directory
  gets scanned, not silently skipped) — the opposite of the inclusion list's
  failure mode. **First attempt regressed on performance**: recursing from
  the repo root with `--exclude-dir` measured in the minutes on this checkout
  (timed out at 2 minutes) — Windows/MSYS pays real `opendir()` cost walking
  into the `node_modules` trees under `contracts/`, `mobile/`, `frontend/`
  even though their *contents* are excluded, and `canny/` (the Python venv)
  alone carries ~98k files including ~178 unrelated JS/TS files from
  third-party package internals. Fixed by pruning at the top level
  (excluding whole trees before grep ever opens them) instead — measured at
  ~0.4-0.8s. Verified against six states before committing: clean tree,
  planted violation under `shared/` (the actual gap), clean again, planted
  violation under `frontend/src` (original coverage preserved), clean again,
  and `frontend/src` missing (the round-2 hard-fail still works).
- **Applied: two doc-only corrections, both confirmed real before fixing.**
  §9 acceptance criterion 1 said "a user can enable the feature end-to-end...
  met... covered by `FingerprintSaltProvisioningTests`" — that test is
  backend-only and can't prove the client actually builds a matching
  fingerprint, and D1 (no adaptive UI mounted until Phase 5) is still open;
  narrowed the claim to what's actually proven (the A1 salt-blocker, backed
  by both the backend test and `cryptoService.fingerprint.test.js`) and noted
  what "end-to-end" would still require. The Phase 3 (not yet implemented)
  behavioural-reward design compared `TypingSession` rows by fingerprint value
  alone, with no `fp_key_version` filter — inconsistent with every other
  fingerprint-keyed query already shipped in Phase 1, all of which era-scope.
  Added the filter to the design; noted honestly that a genuine cross-era
  collision isn't practically reachable (144-bit HMAC under an
  independently-rotated key), so this is consistency/defense-in-depth for a
  future implementer, not a live gap in current (unimplemented) code.
- **Declined: the `ADAPTIVE_PASSWORD.md` `/enable/` example "doesn't match
  the API."** Claim: `enable()` returns the raw POST response, not
  `fingerprint_salt`/`fp_key_version` — those "come from `getConfig()`."
  Read `enable_adaptive_passwords`'s actual response body fresh (not from
  memory): it returns `{success, enabled, created, consent_given_at,
  fingerprint_salt, fp_key_version}` directly — both fields Phase 1 added in
  round 1. The doc's example destructures exactly those two fields from
  `adaptivePasswordService.enable()`'s return value, which is `response.data`
  verbatim. The example is correct as written; no change made.

Verified after this round: script re-verified (six states, see above); no
Python/JS files touched, so no test-suite re-run was needed.

**Seventh review-fix round, on a full CodeRabbit re-review (base `0b7ee24`
against `5959c40`).** One finding, applied.

- **Applied: the "after rotation" doc example never rebuilt the fingerprinter.**
  §2b showed `rotateFingerprintKey()` returning the new salt/era, then stopped
  at a comment ("Rebuild the fingerprinter... from here on") instead of
  actually calling `makeFingerprinter(...)` — unlike §1's example, which does
  show the call. Verified the finding's stated risk mechanism before accepting
  it, since it's the whole justification: the backend's era check only
  compares the `fp_key_version` **number** the client claims against what's
  stored; it has no cryptographic way to verify a fingerprint **string** was
  actually derived under that era's salt (confirmed exhaustively in rounds 3-4
  — this is this feature's known, documented trust model, not a new gap). So a
  developer following the example literally, still holding the pre-rotation
  `fingerprint` closure from §1, could send it alongside the new
  `fp_key_version` and have the server accept and store an era-2 row that no
  era-2-aware client — including that same developer's own future code — could
  ever reproduce. Fixed by matching §1's established pattern exactly: show the
  actual `makeFingerprinter(cryptoService, fingerprint_salt)` call, and state
  explicitly not to keep using the old closure.

Verified after this round: docs-only change; no Python/JS files touched, so no
test-suite re-run was needed.

---

## 4. Phase 2 — Make the adaptation safe (C1)

**Goal:** an adaptation can never reduce guess-resistance.

### 2.1 Add zxcvbn, lazily

`frontend/package.json` → `@zxcvbn-ts/core` + `@zxcvbn-ts/language-common`
(actively maintained, tree-shakeable, ESM — better fit for the Vite 7 build than
the unmaintained `zxcvbn` 4.x). **Vite stays on 7** per project policy.

Load via `await import(...)` inside the gate so it never enters the main chunk.

### 2.2 `filterByStrength` in `adaptiveFeatures.js`

```js
export async function filterByStrength(password, subs, { estimator } = {})
```

Returns `{ subs, originalGuessesLog10, adaptedGuessesLog10, rejected: [...] }`.

Rules, in order:

1. Compute `guesses_log10` for the original and for
   `applySubstitutions(password, subs)`.
2. **Strict non-regression:** if `adapted < original`, drop the
   lowest-confidence substitution and re-test; iterate until non-regressing or
   the set is empty.
3. **De-leet check (the specific attack):** if the adapted password's zxcvbn
   match sequence contains a `l33t`-flagged dictionary match that the original's
   did not, reject that substitution outright — it has handed the attacker a
   known rule.
4. Return `has_suggestion: false` if nothing survives. **This is a valid and
   expected outcome** and the UI must present it as such, not as an error.

### 2.3 Wire it in

- `adaptivePasswordService.suggestAdaptation` (`TypingPatternCapture.jsx:346`):
  insert the gate between `rankSuggestions` and `applySubstitutions`.
- Surface `Δ guesses_log10` in `AdaptivePasswordSuggestion.jsx` — the user should
  see that strength held or improved, not just a memorability claim.

### 2.4 Tests

- Property test: for a corpus of ~200 generated passwords, **no** returned
  adaptation ever lowers `guesses_log10`. This is the acceptance criterion for C1.
- Regression: `password` yields no suggestion (every leet variant de-leets to the
  same dictionary hit).
- The gate is exercised without network access (pure function, injected estimator).

### 2.5 As shipped — status and deviations

**Status: SHIPPED — code-complete and tested, not yet reachable by a user.**
Branch `feat/adaptive-phase2-3-strength-gate-bandit`. The gate itself runs
today via direct client/service calls and the test suite — `suggestAdaptation`
is a **client-side function** (in `adaptivePasswordService`), not an API
endpoint; the actual `/adaptive/suggest/` route is the old, deprecated one and
returns HTTP 410 Gone (§0.1). No route mounts the adaptive client anywhere in
the app yet (gap D1, Phase 5) — "SHIPPED" here means the code and its tests
landed on `main`, not that it currently protects a real user's password.

**Dependency: `@zxcvbn-ts/core` 4 + `@zxcvbn-ts/language-common` 4**, not the
3.x this section assumed. v4's `ZxcvbnFactory` is an *instance* rather than
3.x's `zxcvbn()` + `zxcvbnOptions` module singletons, so configuring it cannot
be disturbed by another feature mutating shared global options, and its
compressed dictionaries are smaller (measured: 1.3 MB vs 1.9 MB on disk). Both
majors were installed and driven before choosing. Vite stays on 7 per project
policy; the install is additive and did not move any existing dependency.

**The two rules are applied to a fixed point, not in the numbered sequence
above.** Every rejection changes the adapted password and therefore the other
rule's input, so running each rule once can leave a regression standing. Each
pass drops at least one substitution, so the loop is bounded by the input size;
exceeding that bound raises rather than returning a stale reading.

**The de-leet rule is the one that closes C1 — the non-regression rule cannot.**
Measured against the real estimator, `password` scores `guesses_log10 = 0.477`
and `p@ssw0rd` scores `0.954`: zxcvbn **credits** the leet variant, because the
l33t matcher's extra guess multiplier outweighs anything it takes away. A gate
built only on rule 1 would therefore wave through the canonical attack this
feature was accused of enabling. That measurement is now a test
(`credits p@ssw0rd over password — proving rule 1 alone cannot close C1`).
The original §2.2 wording implied rule 1 did the security work and rule 3 was a
narrow extra check; it is the other way round.

**Attribution.** A rejection is attributed to a substitution when its
`position` falls inside a leet-flagged dictionary match's `[i, j]` span in the
*adapted* password. This also rejects a substitution that extends a leet match
the original already had, which is the conservative reading and the intended
one.

**Survival rate, measured before building UI around it** (the §8 risk row):
over a deterministic 200-password corpus, **~25% of passwords keep at least one
substitution** and **~24% of individual substitutions survive** (136 of 575),
with **zero** strength violations. Not low enough to force the "safer transform
family" pivot, but low enough that `has_suggestion: false` is a *common*
outcome — the UI presents it as "no change needed", never as an error, and
`suggestAdaptation` returns a reason string for it. (First measured with a
hand-rolled LCG corpus generator that overflowed `Number.MAX_SAFE_INTEGER` on
its very first multiplication — caught in review, see §4.6 — and re-measured
with a correct generator; the survival rate barely moved, which is itself
evidence the earlier corpus, while technically corrupted, wasn't degenerate.)

**Bundle cost, measured** (the other §8 risk row): a probe build of an entry
that actually calls the gate emits three chunks — 5.9 kB for the adaptive
engine, and **31.6 kB + 427.7 kB (≈222 kB gzipped) of zxcvbn behind the dynamic
`import()`**. Nothing zxcvbn-related lands in the entry chunk. Worth recording
honestly: the *production* build cannot show this yet, because gap D1 means no
route imports the adaptive client, so Rollup drops the whole module — verified
by grepping `dist/` for the module's own strings and finding none. The
production number becomes real when Phase 5 mounts the UI.

**Fail-closed.** If the estimator cannot be loaded or throws, `filterByStrength`
propagates and `suggestAdaptation` returns `has_suggestion: false` with
`strength_gate_error: true`. An ungated suggestion is the defect, so "could not
measure" must never be mistaken for "measured and safe". A failed dynamic
import is deliberately *not* cached, or one offline moment would disable the
feature until reload.

**Only counts leave the gate.** `suggestAdaptation` surfaces `rejected_count`
and the distinct reason codes, not the rejected substitutions themselves —
those carry password positions and nothing downstream needs them.

**Two tests were wrong on first run**, and only running them showed it: a
fixture used `position: 8` for a character at position 7, which sent the
scripted estimator down its fallback branch so the test passed for the wrong
reason; and a caching assertion compared two promises returned by an `async`
function, which can never be identical. Both rules were then mutation-checked —
neutralizing de-leet fails 3 tests including the `password` regression;
neutralizing non-regression fails 3 including the 200-password property — so
neither holds vacuously.

**Pre-existing leak/contract tests now inject a neutral estimator.** Their
fixtures (`Sup3rSecret-Passw0rd!`, `MySecret123!`) keep *nothing* against the
real estimator, which would have turned them red; they are about what crosses
the wire, not about the gate, so the gate still runs but has no reason to
reject.

### 2.6 First review-fix round (PR #466), on CodeRabbit/Greptile/Codex findings

Two Phase 2 review findings, both verified before fixing.

- **Grammar bug in the strength panel, and an overclaimed reason.**
  `AdaptivePasswordSuggestion.jsx`'s `rejected_count` message read "1 weaker
  substitution were dropped" for the singular case (subject-verb
  disagreement), and unconditionally called every rejection "weaker" — true
  for a non-regression rejection, not accurate for a de-leet one (which can
  reject a substitution whose raw `guesses_log10` went *up*, per §2.5). Fixed
  the grammar and reworded to "removed to keep this password strong", which
  is accurate for both rejection reasons without claiming a specific
  mechanism.
- **LCG precision loss silently corrupted the 200-password property-test
  corpus.** The hand-rolled generator did `seed * 1103515245`, and for the
  fixed seed `20260805` that product is `22358107193472225` — already past
  `Number.MAX_SAFE_INTEGER` (confirmed by computing the exact product via
  `BigInt` and diffing against the `Number` result: the double came out
  `...3472224`, off by one on the very first multiplication, before any
  accumulation). Fixed by reusing the already-defined, hoisted `seededRng`
  xorshift32 helper instead. Re-measured the corpus stats afterward rather
  than assuming they were unaffected: survival moved from 143/576 (24.8%) to
  136/575 (23.7%) individual substitutions, ~25% of passwords either way,
  still zero strength violations — close enough that the earlier corpus,
  while genuinely corrupted, wasn't measuring something degenerate, but the
  precise numbers in §2.5 above are now the corrected ones.

---

## 5. Phase 3 — Close the learning loop with a real bandit (B1, B2)

**Goal:** replace the logging stub with a persistent, defensible RL policy that
is fed by real signals.

### 3.1 New model — `SubstitutionPolicyArm`

New file `security/models/adaptive_policy.py`:

| Field | Type | Note |
|---|---|---|
| `user` | FK | |
| `from_char` / `to_char` | Char(1) | the arm — one of the 15 `COMMON_SUBSTITUTIONS` pairs |
| `alpha` / `beta` | Float, default 1.0 | Beta posterior over "this class helps this user" |
| `pulls` | Int | |
| `fp_key_version` | Int | arms do not survive a key rotation's correlation reset |
| `last_updated_at` | DateTime | |

Unique together `(user, from_char, to_char, fp_key_version)`.

Plus `GlobalSubstitutionPrior` (same arms, no user) for cold start, aggregated
across users **only where `allow_centralized_training=True`**, DP-noised through
the existing `PrivacyGuard`.

**Algorithm: Beta-Bernoulli Thompson sampling.** Chosen over a contextual method
deliberately — at this data scale (a user produces tens of adaptations, not
thousands) a contextual model would overfit, and Thompson sampling gives
principled exploration with two floats per arm. Time-decay both parameters by
γ=0.98 per update window so the policy tracks drift, which is what "co-evolves
with you" actually means.

### 3.2 The reward function — all four signals are ZK-safe

Rewrite `update_rl_model_from_feedback` (`adaptive_tasks.py:139`) to *persist*.
Reuse its existing reward shaping (L167-184) as the explicit-feedback term:

| Signal | Source | Weight |
|---|---|---|
| Explicit rating | `AdaptationFeedback.rating` → 1.0 / 0.5 / 0.0, plus +0.2/+0.2/+0.1 for the three improvement booleans, capped at 1.0 | 0.4 |
| Acceptance | `PasswordAdaptation.status == 'active'` | 0.2 |
| Rollback | `status == 'rolled_back'` → hard 0 | 0.2 |
| **Behavioural** | mean `error_count` and `total_time_ms` of `TypingSession` rows on `adapted_fingerprint` vs. those on `original_fingerprint`, **both filtered to the adaptation's own `fp_key_version`** | 0.2 |

The behavioural term is the one that makes this real rather than a satisfaction
survey, and it is **fully zero-knowledge** — it joins two fingerprints, never a
password. Require ≥3 sessions on each side before it contributes; otherwise
renormalize the other weights.

Scope both `TypingSession` predicates by `fp_key_version` (matching the
`PasswordAdaptation` row's own era), not by fingerprint value alone. Every
other fingerprint-keyed query already shipped in Phase 1 — the
`apply_adaptation_v2` chain-parent lookup, `rollback_adaptation`,
`get_adaptation_history`, `get_evolution_stats` — does this; the reward query
should follow the same pattern rather than being the one exception. A genuine
cross-era fingerprint collision is not practically reachable (144-bit HMAC
output under an independently-rotated key per era), so this is consistency and
defense-in-depth rather than a live exploit path — but Phase 1's own
`fp_key_version` columns on `TypingSession`/`PasswordAdaptation` exist
specifically so a query never has to rely on that improbability.

Update: `alpha += r`, `beta += (1 - r)`.

### 3.3 Close both ends of the loop (B2)

- **`apply_adaptation_v2`** (`adaptive_password_service.py:597`): after creating
  the record, pull the arm for each applied class and credit an immediate partial
  acceptance reward. Inside the existing `transaction.atomic()` block.
- **`rollback_adaptation`** (L721): it already decays
  `substitution_confidence` by ×0.5 (L762-765) — additionally apply the hard-zero
  reward to the arm. Keep both writers consistent.
- **`capturePattern`** (`TypingPatternCapture.jsx:165-174`): actually send
  `substitution_classes_used` (derived client-side by running `REVERSE_LEET_MAP`
  over the password) and an explicit `success` flag. Without this,
  `_record_substitution_classes` stays dead code and `success` keeps falling back
  to the "no backspaces" heuristic the service's own docstring (L397-399) warns
  against.

### 3.4 `export_preference_model` reads the policy

Replace the static baseline (`adaptive_password_service.py:541-545`) with
posterior means `alpha / (alpha + beta)`, falling back to the global prior, then
to the leetspeak baseline for a genuinely cold user. Also export the raw
`{alpha, beta}` under an `exploration` key so the **client** Thompson-samples —
keeping exploration on-device and the endpoint deterministic and cacheable.

### 3.5 Tests

- Bandit convergence: simulate 200 rounds where `o→0` always rewards and `a→4`
  never does; assert the exported weight for `o→0` exceeds `a→4` and that both
  posteriors are calibrated.
- **Verify the test can fail:** temporarily neutralize the update and confirm the
  convergence assertion breaks. A learning test that holds against a no-op policy
  proves nothing.
- Rollback drives the arm's posterior down.
- The behavioural term is computed from fingerprints only — assert the query set
  touches no password-bearing column.
- Decay: an arm untouched for N windows relaxes toward the prior.

### 3.6 As shipped — status and deviations

**Status: SHIPPED — code-complete and tested, not yet reachable by a user**
(same caveat as §2.5: gap D1 means no route mounts the adaptive client yet).
Branch `feat/adaptive-phase2-3-strength-gate-bandit`. New files: `security/models/adaptive_policy.py`,
`security/services/adaptive_policy_service.py`,
`security/tests/test_adaptive_policy_bandit.py`; migrations `0025` (the two
models, pure schema — no `RunPython`, so none of Phase 1's DB-routing concern
applies) and `0026` (see idempotency below).

**Decay is applied toward the prior, not multiplicatively.** §3.1 said "decay
both parameters by γ=0.98", which read literally is `alpha *= 0.98` — that
walks both parameters toward 0, which is not a valid Beta and makes the
posterior mean numerically meaningless as an arm goes cold. Shipped as
`alpha ← 1 + (alpha − 1)·γ`. Same intent (an untouched arm relaxes to "no
opinion"), and it keeps `alpha, beta ≥ 1` by construction. It also bounds
growth without an arbitrary cap: with reward ≤ 1 per update the excess
converges on `1/(1−γ) = 50`, so an arm stays responsive instead of ossifying.
Both properties are tested.

**`acceptance` and `rollback` are separate components, not one status term.**
They answer different questions — "did the user take it up" and "did the user
actively undo it" — and a rolled-back adaptation is worse evidence than one
merely never accepted.

**Missing components are dropped and the remaining weights renormalized**, so a
partially-observed adaptation is not implicitly scored 0 on what was never
measured. With no feedback and too few sessions, an active adaptation scores
1.0, not 0.4.

**Idempotency was added, and is not optional.** §3.2 kept the original task's
"feedback from the last week" window. Celery retries tasks, and a re-run over
the same window would credit the same feedback twice — silently skewing a
posterior with evidence observed once. Migration `0026` adds
`AdaptationFeedback.policy_reward_applied_at`; the task selects on
`IS NULL` instead of a rolling window, claims each row under
`select_for_update()`, and commits the credit and the stamp together. Selecting
on "not yet applied" rather than on a date range also means a skipped or failed
beat catches up next run instead of dropping that week's data permanently. The
task is batched (`batch_size=500`) and one failing row is logged and left
unstamped rather than aborting the run.

**`credit_arms` takes a row lock, unlike the config reads Phase 1's round 4
declined to lock.** That declined lock was for a value fetched once and reused,
where nothing re-read; this is a genuine read-modify-write (read `alpha`, decay
it, add the reward, write it back), so two unlocked concurrent credits would
lose one outright. Different situation, opposite conclusion — recorded here
because the earlier decision could otherwise look inconsistent.

**Resolution order gained a level.** §3.4 said arm → global prior → baseline.
Shipped as **arm → `UserTypingProfile` usage confidence → global prior →
baseline**: the profile signal is user-specific and the global prior is not, so
letting the population overrule something already observed about this user
would be backwards. The export reports which level answered each class under
`weight_sources`.

**Global prior privacy.** Aggregation is restricted at the query to users with
`allow_centralized_training=True`, and each user contributes their arm's
**posterior mean** — already bounded to [0, 1] — which is what makes the
Laplace sensitivity exactly 1.0 rather than the ~50 an unclipped `alpha` would
imply. On top of the DP noise there is a k-anonymity floor
(`MIN_CONTRIBUTING_USERS = 5`); below it no row is published at all. Arms with
`pulls = 0` are excluded: a flat Beta(1,1) has mean 0.5 by construction and
would look like a real contribution while dragging every class toward "no
opinion".

**Client-side Thompson sampling shipped as specified.** `exploration` carries
the raw `{alpha, beta}`; `rankSuggestions` gained `{ explore, rng }` and draws
a Beta sample (Marsaglia-Tsang gamma with a bounded rejection loop) to *rank*,
while still reporting the posterior **mean** as `confidence` — showing the user
a random draw would make the same suggestion look differently confident on each
refresh. A class the server published no posterior for is scored at its mean
rather than an implicit Beta(1,1), which would let unknown classes outrank ones
the user has actually rewarded. `minConfidence` filters on the reported
confidence, not the draw, so a user-facing floor cannot be satisfied by a lucky
sample.

**The mutation check runs as a test, not by hand.** Neutralizing `apply_reward`
makes the convergence assertion fail. One detail is load-bearing and is
commented in the test: the neutralized stub still increments `pulls`, because
`pulls` is what makes the export read the arm at all — leave it at 0 and the
export falls back to the static baseline, where `o→0` (0.6) already beats
`a→4` (0.4), so `good > bad` would pass against a policy that learned nothing.

**A test expectation was wrong on first run**, in the same class as Phase 2's:
`test_enough_consenting_users_publish_a_prior` asserted a global mean > 0.8
from contributors who had rewarded the class *once* — one credit only moves an
arm from Beta(1,1) to Beta(2,1), a mean of 0.667, aggregating to ~0.639. The
implementation was right; the fixture was not confident enough to be the
population the assertion described.

**Known limitation, documented rather than hidden.**
`detectSubstitutionClasses` runs `REVERSE_LEET_MAP` over the password exactly
as §3.3 specified, so a symbol used as ordinary punctuation is indistinguishable
from the same symbol used as leetspeak — a password ending in `!` is reported
as using `i → !`. Resolving it needs the un-leeted word, i.e. a dictionary
lookup, and pulling zxcvbn's dictionaries into the per-session capture path is
not worth it. The cost is a little signal quality for the bandit, not a leak:
the class is reported either way.

**`success` is omitted, not defaulted.** `capturePattern(password, { success })`
only sends the key when the caller actually knows. Absence means "fall back to
the service's heuristic"; an invented `false` would train the bandit that a
successful entry failed.

### 3.7 First review-fix round (PR #466), on CodeRabbit/Greptile/Codex findings

Six findings applied, four declined with reasons recorded below, each verified
against current code (and in three cases, against the project's own defaults)
before deciding.

- **A genuine k-anonymity bypass, the most significant finding of this
  round.** `rebuild_global_priors` counted `SubstitutionPolicyArm` **rows**
  toward the `MIN_CONTRIBUTING_USERS` floor, not distinct users. Arms are
  era-scoped (`unique_together (user, from_char, to_char, fp_key_version)`),
  so a single user who rotates their fingerprint key holds one arm per era for
  the same class — rotate six times and that one person clears a floor of
  five alone. Verified by writing the reviewer's proposed test first and
  confirming it failed against the actual current code (one user, six eras,
  `classes_written` came back `1` where it should be `0`) before touching the
  aggregation — not just trusting the report. Fixed by keeping only the most
  recently updated arm per `(user, class)` before aggregating. This also
  matters for the Laplace calibration: `add_laplace_noise(sensitivity=1.0)`
  assumes exactly one bounded contribution per user, which multiple arms per
  user would have violated regardless of the anonymity floor.
- **A prior-rebuild failure discarded a batch's own stats.**
  `update_rl_model_from_feedback` called `rebuild_global_priors` outside any
  `try`/`except`. Every feedback row's credit had already committed by that
  point (each in its own transaction), so nothing was lost at the database
  level — but an uncaught exception there raised past the `logger.info`
  summary and the function's return value, so an operator watching the task
  result would see a bare failure instead of "142 rows credited, then the
  prior rebuild broke." Wrapped to match the per-row loop's own established
  rule that one failure must not discard an otherwise-successful run. Added a
  test that patches `rebuild_global_priors` to raise and asserts
  `processed`/`arms_updated` still come back correct; mutation-checked by
  reverting the wrap and confirming the test fails.
- **Dead code, not a bug: an explicit `last_updated_at` in `update_or_create`
  defaults.** `GlobalSubstitutionPrior.last_updated_at` is `auto_now=True`,
  so Django overwrites whatever is passed at `.save()` time unconditionally —
  the explicit `timezone.now()` never reached the database. Removed; the
  `timezone` import became unused as a result and was removed too.
- **Both new admin classes were missing `has_delete_permission`.** Read-only
  was the stated intent (`has_add_permission`/`has_change_permission` both
  already returned `False`), but neither disabled delete. Deleting an arm is
  not recoverable the way a prior is (a prior rebuilds from arms next run; an
  arm's source feedback rows are already stamped as applied, so nothing would
  ever re-derive it). Added `has_delete_permission` returning `False` to both.
  Also added `list_select_related = ('user',)` to
  `SubstitutionPolicyArmAdmin` — `user` is in `list_display`, so every
  changelist row was issuing its own query for the username.
- **Thompson sampling treated a malformed posterior as a usable one.**
  `rankSuggestions` checked `posterior` for truthiness only. A published
  `exploration` entry with a missing or non-numeric `alpha`/`beta` is a
  truthy object, so it reached `sampleBeta`, which has its own internal
  fallback to Beta(1,1) for exactly that case (by design, for a *genuinely
  absent* posterior). The result: a malformed entry got the same "0.5-centred
  random score that can outrank a class the user actually rewarded" outcome
  the surrounding code's own comment says is ruled out for a missing
  posterior — just reached through a different path. Fixed by gating on
  `typeof alpha === 'number' && alpha > 0` (same for `beta`) before treating a
  posterior as usable; anything else now falls back to the deterministic
  `confidence`, same as "no posterior published." Added a deterministic test
  (30 fixed seeds, malformed entry never wins) and mutation-checked it —
  reverting the gate makes the test fail on the very first assertion.
- **Unbounded substitution-class list length.** Neither
  `ApplyAdaptationV2Serializer.substitutions` nor
  `TypingSessionInputV2Serializer.substitution_classes_used` had a
  `max_length`, so one request could create an open-ended number of
  `SubstitutionPolicyArm` rows. The finding's own suggested remedy — restrict
  values to a `COMMON_SUBSTITUTIONS` allowlist — was **not** applied: it
  directly contradicts an intentional, already-tested design decision from
  this same PR (`policy_weights` deliberately lets a user's own evidence for a
  class outside the baseline enter their model;
  `test_policy_weights_keeps_a_class_the_baseline_never_had` asserts exactly
  that). Applied the proportionate fix instead: a shared
  `MAX_SUBSTITUTION_CLASSES = 32` bound in `_validate_substitution_classes`
  (generous headroom above the baseline's 14 distinct pairs, not a tight fit
  around it), which closes the open-ended-row-creation concern without
  reversing the tested design. Added tests for both serializers at and past
  the cap, and one confirming an out-of-baseline class still validates.

Four findings declined, each for a concrete reason discovered by tracing the
suggestion against actual code or the project's own runtime defaults, not by
disagreement on principle:

- **Declined (empirically, not just judged low-value): wiring
  `PrivacyGuard.verify_privacy_budget` into `rebuild_global_priors` before
  publishing.** The suggested guard, `verify_privacy_budget(2 *
  classes_above_floor)`, was checked against this project's own default
  `PrivacyGuard()` before adopting it: `epsilon=0.5, delta=1e-5` computes
  `total_epsilon ≈ 2.4` for a **single** operation, already past the method's
  own `> 1.0` "exceeded" threshold. Every call with these defaults returns
  `False`. Wiring the suggested check in as a hard gate would not have capped
  publication — it would have silently disabled the entire global-prior
  feature on every run, which is a far worse outcome than the gap it was
  meant to close and would not have been caught by any existing test (none of
  them assert the function *keeps working* under repeated calls with default
  parameters). This is the same "run the reviewer's suggested fix, don't just
  read it" discipline this project has needed before — here applied to a
  suggestion whose failure mode would have been silent.
- **Declined: restrict `apply`/`record-session` substitution classes to a
  `COMMON_SUBSTITUTIONS` allowlist.** See the applied length-cap fix above —
  this specific remedy was reversed in favor of the proportionate one because
  it conflicts with a design decision this same PR deliberately made and
  tested.
- **Declined: stamp pre-existing `AdaptationFeedback` rows with
  `policy_reward_applied_at` in migration 0026, so only future feedback moves
  the policy.** Backwards from the intended behavior: nothing credited
  historical feedback before Phase 3 existed (there was no persistent policy
  to credit it into), so the first real run crediting the full backlog once
  is the correct, intended outcome, not a bug — matching
  `test_the_task_picks_up_feedback_a_missed_beat_left_behind`'s design intent
  that unprocessed feedback should always eventually be credited, however old.
  Stamping it away would silently discard real, never-before-used signal.
- **Declined, both "Trivial / Low value" per the report itself:** a
  PostgreSQL-partial-index optimization for migration 0026's pending-feedback
  index (no measurable load exists yet — gap D1 keeps the whole feature
  unmounted) and adding `help_text` to `GlobalSubstitutionPrior.from_char`/
  `to_char` (would need its own migration for a field Django tracks purely
  for admin/introspection display, zero runtime effect). Neither is a defect;
  both deferred to avoid an unforced migration and an unforced query-plan
  change for no current benefit.

**Also investigated, confirmed out of scope: the failing "Dependency
Vulnerability Scan" CI check.** Same two advisories as Phase 1 round 1
(`PYSEC-2025-183`, `PYSEC-2024-277`), now further past their `2026-08-01`
suppression-expiry date. Confirmed via the actual job log rather than assumed:
the failure is pip-audit (Python), and this PR's only dependency-file changes
are to `frontend/package.json`/`package-lock.json` (the `@zxcvbn-ts/*`
additions from Phase 2) — zero Python dependency or suppression-list files are
touched. Renewing an expired suppression needs a fresh threat assessment per
the check's own error message, which is a security decision outside this
review-fix round's scope, not a merge-blocking regression this PR introduced.

Verified after this round: 164 passed across the four adaptive backend test
files (bandit, zk_v2, fingerprint-key-era, adaptive_password), 587 passed
frontend (58 files), Django `check` clean, `makemigrations --check` clean (no
model fields changed, so no new migration), `npm run build` green on Vite 7,
ESLint clean on every touched file, ZK client CI guard green.

**Second review-fix round (PR #466), on a re-review of the first round's own
fix.** One finding, applied and mutation-checked; two documentation-only
wording fixes alongside it.

- **Applied: `Infinity` passed the `typeof`-based posterior gate the first
  round added.** `typeof Infinity === 'number'` and `Infinity > 0` are both
  `true`, so `hasUsablePosterior`'s original `typeof x === 'number' && x > 0`
  check treated an `Infinity` `alpha`/`beta` as usable. Verified the actual
  consequence empirically rather than reasoning about it in the abstract:
  `sampleBeta(Infinity, 2, rng)` was run across ten different seeds and
  returned `NaN` every time — `gammaSample`'s `d = shape - 1/3` becomes
  `Infinity`, and the eventual `x / (x + y)` becomes `Infinity / Infinity`.
  A `NaN` score is worse than merely wrong: `NaN > existing.score` and
  `existing.score > NaN` are both always `false`, so a `NaN`-scored candidate
  processed *first* for a position can never be dethroned by a legitimately
  scored competitor — it wins by iteration-order accident, not confidence.
  Fixed by swapping `typeof x === 'number'` for `Number.isFinite(x)`, which
  excludes `Infinity`/`-Infinity`/`NaN` in one check. Added a deterministic
  regression test exploiting `LEET_MAP.a = ['@', '4']` (two candidates
  compete for the *same* position, so the outcome doesn't depend on the final
  sort's `NaN`-comparator behavior) and mutation-checked it: reverting to the
  pre-fix `typeof` gate makes the test fail with `'@'` (the malformed,
  first-generated candidate) selected instead of `'4'` (the legitimately
  strong one), on every one of 30 fixed seeds.
- **Documentation only: the §2.6 heading overclaimed its own scope**
  ("Two findings against the Phase 2 test file") when one of the two findings
  was about `AdaptivePasswordSuggestion.jsx`, not a test file. Reworded to
  "Two Phase 2 review findings."
- **Documentation only: "Status: SHIPPED" in both §2.5 and §3.6 could read as
  claiming the code protects a running user**, when gap D1 (no route mounts
  the adaptive client) means neither the strength gate nor the bandit is
  reachable outside tests and direct API calls yet. The finding was posted
  against §2.5 only; applied the same clarifying caveat to §3.6 too, since
  both sections use identical wording for the identical gap and fixing one
  while leaving the other would just relocate the ambiguity. Also added the
  same caveat to acceptance-criteria items 2 and 3 (§9), matching the pattern
  item 1 already used for the A1 blocker.

Verified after this round: adaptiveFeatures.test.js green (68 tests, +1),
ESLint clean. Docs-only changes elsewhere needed no test re-run.

**Third review-fix round (PR #466), full CodeRabbit re-review.** Two
production-code findings applied and mutation-checked, four documentation
wording clarifications, one nitpick applied, four declined. Also: a
"Backend Tests" CI check turned red on this round's first push — investigated
and confirmed unrelated to this PR before touching anything.

- **Applied: `credit_adaptation_best_effort` only caught `IntegrityError`,
  not `credit_arms`' own lock-contention failures.** `credit_arms` takes
  `select_for_update()` on `SubstitutionPolicyArm`; under real contention that
  can raise `OperationalError` (lock-wait timeout, detected deadlock), not
  just `IntegrityError`. Verified the two are genuinely unrelated in Django's
  hierarchy before fixing — `issubclass(OperationalError, IntegrityError)` is
  `False`, both are direct siblings under `DatabaseError` — so the original
  handler's scope was a real gap, not a stylistic nit: a lock timeout would
  have propagated straight into the caller's password-apply/rollback
  transaction, exactly the outcome this function's own docstring says it
  exists to prevent. Fixed by catching `DatabaseError`. Added a test that
  injects `OperationalError` and asserts the password change still commits;
  mutation-checked by reverting to the narrow catch and confirming the new
  test fails with the `OperationalError` propagating uncaught, exactly as
  predicted.
- **Applied: the weekly task's row lock could lock joined tables it never
  writes.** `AdaptationFeedback.objects.select_for_update().select_related(
  'adaptation', 'adaptation__user')` — without `of=(...)`, Postgres applies
  `FOR UPDATE` to every table in the join, including `auth_user` via
  `adaptation__user`, for a background batch job that writes only the
  feedback row. Verified `of=('self',)` is safe before applying: read
  Django's actual `SQLCompiler.get_select_for_update_of_arguments` source to
  confirm `'self'` is the documented literal for the query's base table; the
  `adaptation`/`adaptation__user` FKs are both non-nullable, so
  `select_related` already uses plain `INNER JOIN`s for them regardless;
  confirmed `has_select_for_update` is `False` on SQLite (this project's local
  test backend), so the whole clause is silently a no-op there and the change
  needed verifying by reading Postgres-path source, not just running the
  local suite. Full `WeeklyTaskTests` class re-run twice (once via a stale
  background job, once fresh) after the change: 7/7 both times.
- **Applied: a docstring's own stated numbers were wrong.** `_relative_improvement`
  claimed "0.0 means it at least doubled." Computed the actual formula at
  `before=1, after=2` (an exact doubling): `0.5 + 0.5*((1-2)/2) = 0.25`, not
  `0.0`. `0.0` is only approached asymptotically as the ratio grows without
  bound (`≈0.005` at 100x). Corrected the docstring to state the real
  behaviour rather than the aspirational one.
- **Applied, but not as literally suggested: the "usually ranks the strong
  arm first, but not always" test's upper bound was vacuous.** `expect(
  strongFirst).toBeLessThanOrEqual(runs)` can never fail — `strongFirst` is a
  count that cannot exceed the loop bound `runs` by construction, so the
  assertion carries no information regardless of whether exploration is
  broken. The literal suggested fix (`toBeLessThan(runs)`) was checked against
  the test's *actual* seed range before applying, per this project's standing
  rule about testing a suggested fix rather than reading it: with the test's
  existing `EXPLORING_MODEL` (`Beta(40, 2)` vs `Beta(2, 40)`), the strong arm
  won **200 of 200** seeds — tightening the bound as suggested would have
  broken the test immediately. Widened the check to 20,000 direct samples of
  the two distributions: **zero** crossovers. These two Beta parameterizations
  are too concentrated and too far apart to ever overlap in a realistic
  sample; the test's own name ("but not always") was not actually true for
  its chosen parameters. Fixed properly rather than papering over it: added a
  new, deliberately *local* model (`Beta(8, 4)` vs `Beta(4, 8)`, not touching
  the shared `EXPLORING_MODEL` used by five other tests) chosen by measuring
  several candidate parameterizations until one produced a realistic mix
  (182/200 strong-arm wins over this exact seed range — comfortably above the
  existing `>70%` floor, genuinely below 100%). Mutation-checked: forcing
  `hasUsablePosterior` to always be `false` (exploration disabled) makes the
  tightened assertion fail exactly as expected (`200 to be less than 200`).
- **Applied, low-risk: `test_evidence_is_bounded_so_an_arm_stays_responsive`
  hardcoded `0.98` instead of importing `DEFAULT_DECAY`.** A future change to
  the decay constant would previously fail this test on a bare arithmetic
  mismatch instead of pointing at the actual constant. Imported and rewrote
  the assertion in terms of `PRIOR_ALPHA + 1 / (1 - DEFAULT_DECAY)`.
- **Declined, both re-raising round-1 nitpicks the report itself already
  labeled "Trivial / Low value":** a Postgres partial index for the
  `AdaptationFeedback.Meta.indexes` pending-scan entry (same reasoning as
  round 1 — no measurable load exists while gap D1 keeps the feature
  unmounted, and it would need its own migration for a query-plan change with
  no current traffic to justify it), and replacing `short_description`
  attribute assignments with `@admin.display(...)` decorators on the two
  bandit admin classes (functionally identical, pure style, already declined
  once for the same reason).
- **Declined: streaming `rebuild_global_priors`' arm aggregation to avoid
  holding one model instance per `(user, class)` pair in memory.** The
  concern (100k users × 10 classes ⇒ 1M retained instances) is real in the
  abstract, but the feature currently has zero real users (gap D1), and the
  suggested refactor would have to faithfully reproduce the exact
  one-contribution-per-user dedup logic this same round's own k-anonymity fix
  (round 1) just added and tested — reimplementing that as a streaming
  group-by *now*, with no live scale problem to justify the added complexity
  and re-verification burden, is exactly the premature-abstraction trade this
  project's own working practice avoids. Revisit if/when Phase 5 ships real
  traffic through this path.
- **Declined: caching `GlobalSubstitutionPrior.objects.all()`'s read inside
  `policy_weights` (used by `/preference-model/`).** Same "no measurable load
  yet" reasoning, plus an added risk the finding's own proposed sketch doesn't
  fully resolve: a cache with a fixed TTL can serve a stale prior for up to
  that TTL after `rebuild_global_priors` runs, and getting the invalidation
  wrong is a worse failure mode (silently stale personalization data) than
  the uncached read it would replace, for a code path nothing calls yet.
- **Investigated, confirmed unrelated: "CI/CD Pipeline / Backend Tests" went
  red on this round's first push.** Fetched the actual job log rather than
  assuming a connection to this PR's changes. Findings: (1) the job runs
  against a **real Postgres 15 container** (`postgresql`, not this project's
  local SQLite test default), a backend this PR's local `canny`-venv runs
  never exercise; (2) of 203 total errors, **zero** were in any
  `test_adaptive_*` file — every adaptive test outcome was `PASSED`; (3) all
  203 errors were `ERROR at setup of ...` across a dozen unrelated modules
  (`bug_bounty`, `personality_auth`, `zk_proofs`, `auth_module`, and others),
  every one tracing to the identical
  `AttributeError: type object 'PytestDjangoTestCase' has no attribute
  '_pre_setup_ran_eagerly'` inside `pytest_asyncio`'s bridge into
  `pytest_django` internals — a dependency-version-compatibility break
  affecting only `async` test fixtures, none of which this feature's tests
  use; (4) most conclusively, the two commits immediately preceding this
  round on **this same branch** (`2faa9b2`, `157bfbc`) both had this exact
  check green, and the diff between the last green run and the first red one
  touched only `adaptiveFeatures.js` (an `Infinity`-gate fix) and two docs
  files — nothing that touches dependency pins, async fixtures, or any of the
  203 failing modules. Confirmed out of scope: environment/dependency drift
  between CI runs, not a regression introduced by this PR's code.
- **Noted, not fixed: `isort --check-only` fails on every adaptive file this
  PR touches.** Confirmed non-fatal — `ci.yml`'s invocation is
  `isort --check-only --diff . || true`, so it cannot be what failed the
  Backend Tests job. Confirmed pre-existing and repo-wide, not specific to
  this PR's files: the same failure hits files this PR has never touched
  (`fhe_service/services/adaptive_manager.py`,
  `auth_module/migrations/0002_...py`). Running `isort` locally on the touched
  files would reorder import blocks that predate this PR's own diff — a
  larger, less-surgical change than the actual review findings called for.
  Left alone.

Verified after this round: 46 passed / 7 subtests in
`test_adaptive_policy_bandit.py` (+2 vs. round 1: the new `OperationalError`
best-effort test and the multi-era k-anonymity test), full frontend suite
green (588 tests, 58 files — the local test count is unchanged from round 2
since round 3's frontend changes fixed existing tests rather than adding new
ones), Django `check` clean, `makemigrations --check` clean (no model fields
changed), ESLint clean on every touched file.

**Fourth review-fix round (PR #466), full CodeRabbit re-review.** Two Major
findings applied and mutation-checked — both genuine gaps in the bandit's
privacy guarantees, not stylistic issues. One finding declined after direct
empirical verification found it factually wrong about the shipped code's
behaviour. Two `Number.isFinite` gaps applied (same class of bug as round 2,
found in two more call sites). Three doc wording fixes. One query-scoping
nitpick applied; five declined.

- **Applied, the most significant finding of this round:
  `rebuild_global_priors` never retracted a published class.** The function
  only ever wrote or updated `GlobalSubstitutionPrior` rows — nothing deleted
  one. Verified the consequence is real and reachable via the ordinary path
  (not just full GDPR deletion): toggling `allow_centralized_training=False`
  on `/config/` removes a user from `consenting_user_ids` on the very next
  run, and if that user was one of exactly `MIN_CONTRIBUTING_USERS`
  contributors, the class silently stops clearing the floor while its stale
  row keeps being served by `policy_weights` as `global_prior` — the one path
  where a user's data shapes someone else's suggestions, and their withdrawal
  never reached it. Fixed by tracking `published_classes` each run and
  deleting every `GlobalSubstitutionPrior` row outside that set (including
  every row, in the degenerate case where nothing clears the floor at all —
  privacy-first means failing closed on publication, not leaving stale data
  indefinitely just because the current run couldn't confirm it). Four new
  tests, including the exact scenario CodeRabbit proposed (publish, withdraw
  consent, confirm retraction) plus a negative control (a still-qualifying
  class survives an unrelated run) and the degenerate "nothing qualifies"
  case. Mutation-checked: disabling retraction makes both retraction-asserting
  tests fail on their `classes_retracted` assertion specifically (confirmed
  after initially misreading a truncated terminal capture as a different,
  unrelated assertion — corrected by re-running with output redirected to a
  file instead of piped through `tail`, which is now the standing practice for
  any mutation-check output long enough to risk truncation).
- **Applied: the per-user DP epsilon never reached `rebuild_global_priors`.**
  `adaptive_tasks.py` called `rebuild_global_priors(PrivacyGuard())` with no
  epsilon, so the aggregation always ran at the class default (0.5) regardless
  of what any individual contributing user configured via
  `differential_privacy_epsilon`. This is the one path where a user's data
  crosses into shaping another user's output, so a user who chose a stricter
  (lower) epsilon did not consent to their contribution being folded in under
  a weaker one. Implemented more precisely than the literal suggestion (which
  would have queried `AdaptivePasswordConfig` broadly for every
  enabled+consenting user): scoped the `Min(differential_privacy_epsilon)`
  aggregate to the exact set of users who actually contribute an arm *this
  run* (already materialized in `latest_by_user_and_class`), computed inside
  `rebuild_global_priors` itself rather than in the caller — so a consenting
  user who has never touched the feature cannot make an unrelated class's
  epsilon stricter than it needs to be, and `adaptive_tasks.py` needed no
  changes at all. `PrivacyGuard.epsilon` is a plain instance attribute read at
  call time by `add_laplace_noise` (confirmed by reading every reference to it
  in the class), so overriding it before the noise-adding loop is sufficient.
  Two new tests (strictest epsilon wins over the caller's default; a
  non-contributing consenting user's stricter epsilon does not leak into an
  unrelated class's noise). Mutation-checked: disabling the override makes the
  strictest-epsilon test fail on `dp_epsilon` (0.5 instead of 0.1).
  **This fix broke nine pre-existing assertions** in tests built around
  `PrivacyGuard(epsilon=100.0)` for negligible-noise testing of the
  aggregation math — the override silently downgraded their contributors to
  the unconfigured default (0.5), reintroducing real noise into tests that
  were specifically designed to have none. Fixed by extending `_contributors`
  with a `dp_epsilon` parameter and threading a matching epsilon through every
  affected test's contributors, not just the guard. Two of the new retraction
  tests had a second, independent problem surfaced during this process: they
  used exactly `MIN_CONTRIBUTING_USERS` contributors, which makes "does this
  class still publish" a coin flip on the *sign* of the Laplace noise alone —
  landing exactly at an integer floor means any negative draw, however tiny,
  crosses the boundary, independent of how small the noise scale is (confirmed
  by direct computation, not just observed as flaky: `P(noise < 0) = 0.5` for
  any symmetric distribution regardless of scale). Fixed by padding the
  "should publish" side of these tests well above the floor and, where a test
  needed to demonstrate a *drop below* the floor, doing so with a multi-user
  margin (8 down to 4) rather than the single-user, exactly-at-the-boundary
  version that shipped first.
- **Declined, after direct empirical verification found the finding
  factually wrong about the shipped code:** "the gate rejects only *new*
  leet-flagged matches, preserving pre-existing ones." This contradicts what
  round 1 already documented about the same code (§2.5's "Attribution" note)
  after its own investigation, and — because a claim about production
  behaviour is worth re-verifying rather than trusting either doc against the
  other — was checked directly against the running gate rather than taken on
  faith from either source. Constructed `c0rrect` (already zxcvbn-l33t-matched
  at `[0, 6]` in its unmodified form, confirmed via `loadDefaultEstimator`
  before touching `filterByStrength` at all) and ran it through the real
  pipeline: the `e→3` substitution at position 4 — squarely inside that
  *pre-existing* span — is rejected as `de_leet`, identical to how a
  genuinely new match would be rejected. The implementation does not compare
  against the original's match sequence at all; it rejects any surviving
  substitution whose position falls inside *any* leet-flagged span of the
  *adapted* result, new or inherited. Left `ADAPTIVE_PASSWORD.md`'s wording
  unchanged (it already says "no leet-flagged dictionary match" without
  qualifying "new," which is the accurate description).
- **Applied: two more `Number.isFinite` gaps, same defect class as round 2's
  `hasUsablePosterior` fix, found in call sites that fix didn't cover.**
  `sampleBeta` itself still used `typeof x === 'number'` internally — round
  2's fix protects `rankSuggestions`' own call site, but `sampleBeta` is
  exported and callable directly, and its own contract ("valid probability
  for garbage input") wasn't actually met for `Infinity`. Verified before
  fixing: `sampleBeta(Infinity, 2)` returns `NaN` directly, and
  `sampleBeta(2, Infinity)` returns `0` (a false-confident answer, not an
  error). `AdaptivePasswordSuggestion.jsx`'s `hasStrengthReading` gate had the
  identical pattern for `guesses_log10_before`/`after`, where `typeof NaN ===
  'number'` would let a NaN reading through and render literally "NaN" in the
  UI. Both fixed with `Number.isFinite`. Extended the existing degenerate-
  parameter test for `sampleBeta` with `Infinity`/`-Infinity` cases (not a new
  test — the existing one already existed for exactly this purpose and simply
  hadn't been extended to the value that mattered) and mutation-checked it.
- **Applied, doc wording:** the reachability description near
  `suggestAdaptation` called it "the API endpoints Phase 1 shipped," but
  `suggestAdaptation` is a **client-side function** in `adaptivePasswordService`,
  not an API endpoint — the actual `/adaptive/suggest/` route is the old,
  deprecated one and returns 410 Gone. Reworded to state plainly that the gate
  runs today via direct client/service calls and the test suite.
- **Applied, low-risk query scoping:** `policy_weights` read
  `GlobalSubstitutionPrior.objects.all()` unconditionally on every
  `/preference-model/` call, though only classes in `known_classes` (the
  baseline, the user's own overrides, and their arms) can ever be looked up
  from the result. Reordered `known_classes`' construction ahead of the query
  and filtered with a superset `from_char__in`/`to_char__in` pair — safe
  specifically because the per-class loop only ever reads
  `globals_by_class.get((from_char, to_char))` for a class already being
  iterated from `known_classes`, so an over-fetched row is simply never looked
  up.
- **Declined, all explicitly labeled "Trivial" by the report itself, or
  matching an already-declined round-1/round-3 item:** `@admin.display`
  decorators (pure style, declined twice already); streaming
  `latest_by_user_and_class`'s aggregation to bound memory (same round-3
  reasoning — zero real users behind gap D1, and the suggested refactor would
  have to faithfully reproduce the one-contribution-per-user dedup this same
  round's own retraction fix already tests, for no live scale problem);
  `AddIndexConcurrently` for migration 0026 (the table is empty behind gap D1 —
  nothing to lock); splitting the task's `skipped` counter into
  `already_claimed`/`failed` (genuinely useful once an operator is watching
  this task, but nothing schedules it yet — gap D3 — so there is no current
  consumer to serve); backfilling `policy_reward_applied_at` on historical
  rows (same round-3 reasoning — crediting the full backlog once is the
  intended behaviour for a policy that never existed before Phase 3, not a bug
  to suppress).

Verified after this round: 170 passed / 27 subtests across the four adaptive
backend test files (+6 vs. round 3: four new retraction tests, two new
epsilon-scoping tests), full frontend suite green (588 tests, 58 files —
local count unchanged, since this round's frontend changes extended an
existing test rather than adding new ones), Django `check` clean,
`makemigrations --check` clean (no model fields changed), ESLint clean on
every touched file. Both new production-code fixes mutation-checked
independently, each restored from a clean backup and re-verified before
moving to the next.

**Fifth review-fix round (PR #466), on CodeRabbit's follow-up review of round
4's own new code, plus two CI checks investigated directly from the PR's
failing-checks list rather than from a bot comment.**

- **Applied: the two epsilon-scoping tests round 4 added were themselves
  flaky, and CodeRabbit's mechanism was correct.** Both call
  `rebuild_global_priors` with a real, unseeded `PrivacyGuard`, whose
  `add_laplace_noise` draws `np.random.laplace(0, sensitivity/epsilon)`.
  Verified the exact failure probabilities from the Laplace CDF rather than
  trusting the review's numbers outright: `P(noise < -margin) =
  0.5*exp(-margin/scale)` gives `0.5*exp(-10/10) ≈ 18.4%` for
  `test_the_strictest_contributing_users_epsilon_is_honoured` (epsilon=0.1,
  scale=10, 10-user margin above the k=5 floor) and `0.5*exp(-5/2) ≈ 4.1%`
  for `test_a_non_contributing_consenting_users_epsilon_does_not_leak_in`
  (epsilon=0.5, scale=2, 5-user margin) — both real, CI-relevant flake rates.
  Padding the contributor population further, which round 4 had already
  tried, cannot fix this: the Laplace tail probability is set by `scale =
  sensitivity / epsilon`, not by `n`, so no amount of padding shrinks it.
  Fixed by patching `PrivacyGuard.add_laplace_noise` to the identity function
  for the duration of these two tests (`patch.object`) — they test epsilon
  SELECTION, not noise magnitude, so removing the noise removes the flake
  without weakening what the test asserts. Mutation-checked by reverting the
  round-4 epsilon-override line itself (`privacy_guard.epsilon =
  strictest_epsilon` → `pass`) with the noise still patched out:
  `test_the_strictest_contributing_users_epsilon_is_honoured` failed exactly
  as expected (`0.5 != 0.1`), proving the patched test still catches the
  actual bug it exists to catch, not just the noise.
- **Investigated, confirmed not caused by this PR: the failing "CI/CD
  Pipeline / Backend Tests" check.** Fetched the actual job log rather than
  assuming. Of 1676 passed / 203 errors, **zero** were in
  `test_adaptive_policy_bandit.py` or `test_adaptive_zk_v2.py` — both files
  passed in full (51 and 38 tests respectively) in that exact run. Every
  error was the same `AttributeError: type object 'PytestDjangoTestCase' has
  no attribute '_pre_setup_ran_eagerly'` first diagnosed in round 2 (trap
  18), this time cascading through ten unrelated apps (`bug_bounty`,
  `circadian_totp`, `decentralized_identity`, `fhe_sharing`, `mesh_deaddrop`,
  `ml_dark_web`, `password_reputation`, `personality_auth`, `stegano_vault`,
  `zk_proofs`), first appearing in `ambient_auth`'s async fixture setup after
  a ~50-second stall. Confirmed not this PR's diff: `git diff main...HEAD
  --stat` touches zero conftest, settings, or dependency files, and none of
  the ten affected apps share any code path with the adaptive feature. Left
  un-fixed, same discipline as trap 18: bisectability to this PR's own diff,
  not "is something red," decides whether it's this PR's bug to fix.
- **Applied: renewed the two expired pip-audit suppressions, reversing the
  "confirmed out of scope" stance recorded in the third and fourth rounds
  above.** That stance was correct when written — the entries hadn't crossed
  their `2026-08-01` expiry yet, and the manifest's own policy requires "a
  fresh threat assessment" to renew, which a round that didn't own that
  assessment correctly declined to do. Both have now actually expired and
  the "Dependency Vulnerability Scan" check hard-fails, blocking this PR's
  own merge — making the fresh assessment this round's problem, not
  background noise. Did the assessment rather than reflexively bumping
  dates: web-verified `PYSEC-2025-183` (PyJWT) is still disputed upstream
  with no fixing release (`jpadilla/pyjwt#1168`), and `PYSEC-2024-277`
  (joblib) is still disputed on the same "deserializes only trusted,
  self-authored cache content" grounds already recorded in the manifest —
  `joblib==1.5.2`, the exact version `requirements-lock.txt` pins as of this
  review round, remains flagged because the finding is inherent to the
  pickle-based design, not a version gap (the round-6 section below records
  `joblib==1.5.3` from that round's own `pip-audit-report.json` — CI resolves
  the looser `joblib>=1.3.0` in `requirements.txt`/`requirements-ml.txt`
  rather than the lock file's exact pin, so the two version numbers
  describing "current" a round apart are not a typo, just two different
  requirements files with different constraints). Checked git history
  (`git log --follow -p`) before renewing:
  both entries were added once, in `c8e1a6e`, and never renewed since — this
  is the FIRST renewal for each, not the second, so the manifest's own
  "after two renewals without a fix, file a tracking issue" threshold does
  not apply yet. Bumped to `2026-09-28` (PyJWT) and `2026-10-03` (joblib),
  both within the policy's 60-day cap and staggered against the file's other
  entries. (This round's own "disputed, no fixing release" framing for both
  IDs turned out to be imprecise once the ACTUAL pip-audit output was read
  rather than only the advisories' text — see the sixth round below, which
  removed both entries entirely rather than renewing them again.)

Verified after this round: 89 passed / 7 subtests across
`test_adaptive_policy_bandit.py` + `test_adaptive_zk_v2.py` (count unchanged
— this round fixed test *reliability*, not test *count*), re-confirmed clean
after reverting the mutation-check backup, Django `check` clean. Frontend
untouched this round, so no frontend re-run was needed.

**Sixth review-fix round (PR #466), a full CodeRabbit re-review on round 5's
own commit, plus a CI failure that only became visible once round 5 fixed
the check that was gating it.**

- **Applied, and the actual root cause of the still-failing "Dependency
  Vulnerability Scan" check: three brand-new `cryptography` CVEs, not the
  two IDs round 5 renewed.** Round 5's fix worked exactly as intended — the
  scan's own `pip-audit-report.json` from this round confirms zero vulns for
  `pyjwt==2.13.0` and `joblib==1.5.3` — but that expiry pre-check had been
  short-circuiting the job before pip-audit itself ever ran (`sys.exit(3)` on
  the validation step), so nothing downstream was visible until round 5
  unblocked it. With the gate passing, pip-audit ran for the first time in
  this investigation and surfaced three real, unsuppressed findings against
  `cryptography==48.0.1`: `PYSEC-2026-3552` (Bleichenbacher oracle in
  `pkcs7_decrypt_der/_pem/_smime`), `PYSEC-2026-3553` (exponential-blowup DoS
  in x509 chain validation via duplicate self-signed certs), and
  `PYSEC-2026-3554` (wildcard SAN escapes a name-constrained sub-CA, same
  `x509.verification` module). Assessed reachability before suppressing
  rather than reflexively adding entries: grepped the whole codebase for
  `pkcs7_decrypt` and for any `cryptography.x509`/`x509.verification` import
  — zero matches for either. Everything this app actually uses the library
  for (AESGCM/ChaCha20Poly1305 AEAD, Fernet, HKDF, Scrypt, Ed25519/X25519/EC)
  is untouched by any of the three. Added threat-assessed suppressions for
  all three rather than upgrading `cryptography` — a core dependency used by
  most of the app's crypto services and by `pyjwt`/`fido2`/`pyopenssl`
  transitively, so a version bump is a repo-wide regression risk far outside
  this PR's "adaptive password feature" scope, and with zero reachable
  vulnerable code paths there is nothing an upgrade would actually protect
  here.
- **Applied, correcting round 5's own imprecise framing rather than renewing
  it again:** removed the `PYSEC-2025-183` (PyJWT) and `PYSEC-2024-277`
  (joblib) suppressions entirely instead of keeping them. CodeRabbit's
  re-review caught what round 5 got right in outcome but wrong in mechanism.
  For PyJWT, round 5's report read "PyJWT==2.13.0 (our pin) reports zero
  vulns" from `pip-audit-report.json` and reasoned "no fixing release" —
  but the actual reason pip-audit reports zero vulns is that OSV's affected
  range for this advisory tops out at 2.10.1, and our pin (2.13.0) is
  outside it entirely, not that PyJWT shipped a release that "fixes" a
  disputed design choice. For joblib, round 5's framing ("still disputed
  upstream... no fix version exists") was superseded by a fact round 5
  hadn't checked: OSV shows `PYSEC-2024-277` was formally **withdrawn** on
  2026-06-09 as a confirmed false positive (`joblib/joblib#1588`), not
  merely disputed-but-standing. A withdrawn/out-of-range advisory that
  pip-audit doesn't even report needs no suppression entry at all — keeping
  one is not wrong, but it's dead weight that reads as "this is still an
  active, live risk we're accepting," which neither ID is.
- **Applied: `rebuild_global_priors`'s failure fallback in
  `adaptive_tasks.py` returned a differently-shaped dict than its success
  path.** The success path returns `classes_written`/`classes_skipped`/
  `classes_retracted`; the `except Exception` fallback supplied only the
  first two plus `prior_rebuild_failed`. Any consumer reading
  `result['classes_retracted']` unconditionally — exactly the shape every
  other caller in this codebase already assumes, per the round-4 retraction
  work — would `KeyError` specifically on the failure path, the one where an
  operator most needs the dict to be readable. Added the missing key with
  value `0` and extended the existing failure-path test
  (`test_a_failing_prior_rebuild_does_not_discard_the_credited_batch`) to
  assert it.
- **Applied: `update_rl_model_from_feedback`'s per-row `except Exception`
  could swallow a Celery soft-time-limit interruption.** Verified this is
  reachable, not hypothetical, before fixing: `password_manager/celery.py`
  sets `task_soft_time_limit=300` / `task_time_limit=600` as app-wide
  defaults, and this task carries no per-task override, so it genuinely runs
  under a 5-minute soft limit. `SoftTimeLimitExceeded` is a plain `Exception`
  subclass (confirmed via `celery.exceptions`), so the existing broad handler
  would catch it, log it as "one bad row," and let the loop continue — past
  the soft deadline's intended graceful-wind-down point, all the way to the
  **uncatchable** 10-minute hard limit, which then `SIGKILL`s the worker
  mid-batch instead. Fixed by re-raising `SoftTimeLimitExceeded` and `Retry`
  (Celery's own control-flow exceptions) before the generic handler, so
  worker-level interruptions propagate instead of being misfiled as
  row-level failures.
- **Applied: the per-(user, class) aggregation dictionary in
  `rebuild_global_priors` retained a full `SubstitutionPolicyArm` ORM
  instance per key, when only two scalar values are ever read back from
  it.** `arms.iterator(chunk_size=1000)` bounds the DB cursor, but the
  dictionary — not the iterator — sets this task's peak memory, growing with
  the whole consenting population regardless of chunk size. Changed the
  dict's values from model instances to `(last_updated_at, posterior_mean)`
  tuples; `contributing_user_ids` below reads only the dict's keys, so it is
  unaffected. Declined the review's alternative "dedupe in SQL with
  `.distinct(*fields)`" option: PostgreSQL-only, and this project's existing
  streaming/memory nitpicks in this exact function have been declined twice
  before (rounds 3 and 4) on "zero real users behind gap D1" grounds — the
  tuple change gets the actual memory win from the review at effectively
  zero added complexity, without reopening a query-shape change that was
  already twice judged disproportionate to current scale.
- **Declined, all explicitly labeled "Trivial"/"Low value" by the report
  itself:** `help_text` on `SubstitutionPolicyArm`'s sibling model's
  `from_char`/`to_char` columns (cosmetic, would generate a no-op
  `AlterField` migration for zero runtime effect); a partial index on
  `AdaptationFeedback.policy_reward_applied_at` (same round-3/4 reasoning —
  the table is empty behind gap D1, nothing to optimize for yet);
  `@admin.display` decorators over `short_description` assignment (pure
  style, declined three times now — the surrounding admin module, largely
  pre-dating this PR, uses `short_description` assignment consistently
  throughout, and converting only the two new methods would make this PR's
  code the odd one out against its own file).

Verified after this round: 89 passed / 7 subtests across
`test_adaptive_policy_bandit.py` + `test_adaptive_zk_v2.py` (unchanged —
this round's test change only extended an existing assertion), Django
`check` clean, `makemigrations --check` clean (no model fields changed).
Frontend untouched this round.

**Seventh review-fix round (PR #466), a full CodeRabbit re-review of round
6's own commit, triggered manually (`@coderabbitai full review`) rather than
landing automatically.**

- **Confirmed, not re-fixed: "Dependency Vulnerability Scan" is green.**
  `gh pr checks 466` after round 6 shows the check passing — round 6's fix
  held. The only CI failure remaining is "Backend Tests," re-verified via
  the actual job log to be the byte-for-byte same result as round 5's own
  investigation: 1676 passed, 203 errors, all still the identical
  `_pre_setup_ran_eagerly` cascade through the same ten unrelated apps
  (`password_reputation`, `personality_auth`, `stegano_vault`, etc.), and
  all 89 adaptive-feature tests (51 + 38) passing in full. Re-confirming an
  already-diagnosed unrelated flake on every round rather than assuming the
  earlier diagnosis still holds — same discipline as trap 18, now exercised
  a third time (rounds 5, 6, 7) with an identical result each time.
- **Applied: `suggestAdaptation generates the suggestion client-side` in
  `adaptive_password.test.tsx` relied on an unstated assumption.**
  `suggestAdaptation` defaults to `explore: true` (confirmed in
  `TypingPatternCapture.jsx`), which enables Thompson sampling over the
  preference model's `exploration` table when one is present. The test's
  mocked model has no `exploration` key at all today, so the sampling path
  is a no-op purely by fixture accident, not by the test's own design —
  verified by reading `rankSuggestions`' guard (`explore ? preferenceModel
  && preferenceModel.exploration : null`) rather than assuming. Pinned
  `explore: false` explicitly, at zero behavioral cost today (re-ran the
  file: all 25 tests still pass, same assertions, same outcome) and
  removing a latent trap for whoever adds an `exploration` table to this
  fixture later without realizing this specific test would then become
  seed-dependent.
- **Applied: clarified an internal inconsistency in round 5's own text**,
  not a code change. Round 5 called `joblib==1.5.2` "the current pin";
  round 6's own section two paragraphs below it recorded
  `joblib==1.5.3` from that round's `pip-audit-report.json`. Both numbers
  are correct, just for different things: `requirements-lock.txt` pins
  `joblib==1.5.2` exactly, but CI actually resolves the looser
  `joblib>=1.3.0` in `requirements.txt`/`requirements-ml.txt`, which is
  where 1.5.3 came from. Reworded round 5's text to name the lock file
  specifically and point at this explanation, rather than leaving two
  unreconciled "current" version numbers a few paragraphs apart.
- **Declined, with a stronger reason than "trivial": a `CheckConstraint`
  requiring `alpha > 0`/`beta > 0` on both bandit models would work AGAINST
  an already-documented design choice in the same file, not just add
  unforced ceremony.** `SubstitutionPolicyArm.posterior_mean` already
  guards a zero-or-negative denominator with an explicit comment: "a row
  edited by hand in the admin, or restored from an older schema, should
  degrade to 'no opinion' rather than raise." A DB-level `CheckConstraint`
  would make exactly that scenario — a hand-edited or legacy row with a
  non-positive `alpha`/`beta` — impossible to save at all, contradicting
  the graceful-degradation behavior the model's own docstring commits to.
  Separately, both write paths are mathematically guaranteed positive by
  construction anyway: `_decay_toward_prior` keeps `SubstitutionPolicyArm`'s
  parameters `>= 1` (verified by reading the decay formula, not assumed),
  and `GlobalSubstitutionPrior`'s `alpha`/`beta` are `PRIOR_ALPHA/BETA +
  GLOBAL_PRIOR_STRENGTH * mean` with `mean` clamped to `[0, 1]` by
  `_clamp01` before use. Matches this project's own stated code
  philosophy — validate at system boundaries, trust internal invariants —
  applied here to a constraint that would additionally undo a documented
  fallback.
- **Declined, the fourth review pass to flag the same
  `AdaptationFeedback.policy_reward_applied_at` index in some form (rounds
  3, 4, 6, and now 7 — partial index, then partial+`AddIndexConcurrently`,
  now also a composite `(policy_reward_applied_at, created_at)` variant in
  `core.py`):** all three of this round's specific proposals share the same
  underlying non-problem as the previous three rounds' proposals — the
  table is empty behind gap D1 (nothing schedules the weekly task that
  would populate or query it yet), so there is no query plan, lock
  contention, or backlog-size problem for any of partial/concurrent/
  composite to solve today. Noting the repeat count explicitly here so a
  future round doesn't re-litigate this from zero a fifth time without
  first checking whether gap D1 has actually closed.
- **Declined again, third time: `@admin.display` over `short_description`**
  — same reasoning as rounds 4 and 6 (the surrounding, largely pre-existing
  admin module uses `short_description` assignment consistently; converting
  only the two newest methods would make this PR's own code the
  inconsistent one).

Verified after this round: 25 passed in `adaptive_password.test.tsx`
(frontend, the only test file touched), Backend Tests re-confirmed
unrelated via job log (no local backend re-run needed — no backend code
changed this round).

**Eighth review-fix round (PR #466), full CodeRabbit re-review of round 7's
own commit.**

- **Applied, a new Django-CVE wave against the pinned framework itself, same
  shape as round 6's cryptography wave.** Six new CVEs against
  `django==5.1.15` (our pin): `CVE-2026-48587`, `CVE-2026-8404`,
  `CVE-2026-48588` (Vary-header/Cache-Control cache-poisoning bugs in
  `UpdateCacheMiddleware`/`cache_page`/`vary_on_headers`), `CVE-2026-6873`
  (`get_signed_cookie` non-injective salt derivation), `CVE-2026-53877`
  (`django.contrib.gis.gdal.GDALRaster` buffer over-read), `CVE-2026-53878`
  (`DomainNameValidator` newline injection). All six fixes require Django
  5.2.15+/6.0.6+ or 5.2.16+/6.0.7+ — a MINOR version upgrade of the
  framework the entire app runs on, far outside this PR's own scope.
  Verified all six unreachable rather than assumed: zero
  `django.middleware.cache`/`cache_page`/`vary_on_headers`/
  `patch_vary_headers` usage anywhere; zero `get_signed_cookie` calls; zero
  `DomainNameValidator` usage; and for the GIS CVE specifically,
  `django.contrib.gis` is commented OUT of `INSTALLED_APPS` entirely, with
  the only `django.contrib.gis` import anywhere in the codebase being the
  unrelated `geoip2.GeoIP2` submodule, never `gdal.GDALRaster`. Added six
  threat-assessed suppressions rather than treating "Django itself has CVEs"
  as license to attempt a framework upgrade inside an unrelated feature PR.
- **Applied: `rankSuggestions` applied its `minConfidence` floor to the
  per-position WINNER after Thompson sampling had already picked it, not to
  each candidate before the pick.** A low-confidence sibling could win its
  position on a lucky exploration draw and then get filtered out by the
  confidence floor, dropping the whole position even though a
  higher-confidence sibling at the same position had satisfied the floor
  all along. In deterministic mode (`explore: false`, the default) this is
  provably a no-op — `score === confidence` there, so the position's winner
  IS its highest-confidence candidate, and pre- vs post-filtering are
  equivalent — the bug only exists on the `explore: true` path. Fixed by
  moving the filter before the per-position reduction. Added the exact
  regression case CodeRabbit specified (`a: { '@': 0.9, 4: 0.1 }`, `'4'`'s
  posterior tuned to win the draw almost every time) across 30 seeds, and
  mutation-checked by reverting to the old post-reduction filter: the new
  test failed immediately (`expected [] to have a length of 1`), confirming
  it catches the real bug.
- **Applied: `rebuild_global_priors`'s publish loop and its retraction step
  were not one transaction.** Each `update_or_create` auto-committed
  individually, and the retraction `delete()` ran as its own statement
  after the loop. A process death mid-loop (OOM, SIGKILL, worker eviction)
  would leave some classes freshly published and others untouched, AND skip
  the retraction entirely (it only runs after the loop completes) — the
  exact half-updated, never-retracted state the function's own retraction
  comment already exists to prevent. Wrapped the publish loop and retraction
  in one `transaction.atomic()` block: the whole run now commits or rolls
  back together, and a rollback is cheap to retry (the next scheduled run
  recomputes from the same underlying arms). Verified the caller
  (`update_rl_model_from_feedback`) does not already wrap this call in its
  own atomic block before nesting — it doesn't; each feedback row's credit
  already commits independently, per that function's own docstring, so
  nesting here does not change any existing commit boundary.
- **Applied: `scriptedEstimator`'s silent fallback for an unlisted password
  could make a table-exhaustive test pass for the wrong reason** — the exact
  hazard a NEIGHBORING test's own comment already warns about by hand (an
  off-by-one position "silently sends the scripted estimator down its
  fallback branch and the test passes for the wrong reason"). Added an
  opt-in `'strict'` fallback mode that throws on an unlisted password
  instead of returning a strong-and-clean reading, and applied it to that
  exact test (`leaves a substitution outside the leet match span alone`)
  after tracing `filterByStrength`'s actual query sequence to confirm all
  three table entries are the only forms it ever queries for this specific
  test — `'strict'` is provably safe there, not just probably.
- **Confirmed, not re-fixed: Backend Tests is the identical unrelated flake
  for the FOURTH consecutive round** (1676 passed, 203 errors, all 89
  adaptive tests passing, same `_pre_setup_ran_eagerly` cascade). An
  in-repo `grep` for the "ast-grep rule model-help-text" CodeRabbit cited as
  the reason to add `help_text` found no such rule or config file anywhere
  in this repository — the claim doesn't survive verification, so it
  carries no more weight than the same nitpick's prior, already-declined
  appearances.

Declined:

- `help_text` on `GlobalSubstitutionPrior.from_char`/`to_char` — a second
  appearance of the round-6 nitpick, same reasoning (cosmetic, a no-op
  `AlterField` migration for zero runtime effect), plus this round's
  specific "ast-grep rule" citation did not check out (see above).
- The `AdaptationFeedback.policy_reward_applied_at` index, a FIFTH time
  (rounds 3, 4, 6, 7, 8) in yet another variant (composite this time), and
  the historical-backfill question a THIRD time (rounds 3 and 4 already
  reasoned through this: crediting the full backlog once is the intended
  behaviour for a policy that never existed before Phase 3). Both still
  against the same table, still empty behind gap D1.
- Splitting the task's `skipped` counter into `already_claimed`/failed — a
  SECOND appearance of a nitpick declined all the way back before round 4
  (same reasoning: `update_rl_model_from_feedback` still has no
  `beat_schedule` entry — confirmed still true, not assumed — so there is
  still no operator consuming this counter to split it for).
- `@admin.display` over `short_description` — a fourth decline, same
  reasoning as rounds 4, 6, and 7.

Verified after this round: 69 passed in `adaptiveFeatures.test.js`
(frontend, +1 new test, mutation-checked), 89 passed / 7 subtests across
`test_adaptive_policy_bandit.py` + `test_adaptive_zk_v2.py` (backend,
unchanged count — this round's backend change was a transaction boundary,
not new coverage), Django `check` clean.

**Ninth review-fix round (PR #466), full CodeRabbit re-review of round 8's
own commit.**

- **Applied, a genuine unbounded-growth gap: nothing capped how many
  `SubstitutionPolicyArm` rows one user could accumulate across many
  requests over time.** `adaptive_serializers.MAX_SUBSTITUTION_CLASSES`
  (from round 1) bounds how many NEW classes one `/apply/` request may
  introduce (32), but `from`/`to` are single Unicode characters — not
  restricted to a small leet alphabet — so the reachable space per request
  is not naturally small, and nothing stopped an authenticated user from
  repeating requests with new distinct pairs indefinitely. Confirmed this
  is live-reachable, not gap-D1-gated: `/apply/` requires only
  `IsAuthenticated` + `@require_adaptive_enabled` (self-service opt-in, no
  UI needed to call the API directly) and carries no throttle class.
  Confirmed the read-side cost too: `policy_weights` loads
  `SubstitutionPolicyArm.objects.filter(user=user, fp_key_version=...)` in
  full, unfiltered, on every `/preference-model/` call. Added
  `MAX_ARMS_PER_USER_ERA = 200` and a check in `credit_arms`: a NEW class is
  skipped once an era is at the ceiling, but an already-existing arm keeps
  being credited normally — the era doesn't freeze once full. Two new
  tests, one for each half of that behavior, the ceiling-stops-creation one
  mutation-checked (disabling the check made it fail exactly as expected:
  `1 != 0`).
- **Investigated, declined: a claim that `SchemaVersionMixin` could reject
  an older deployed client's payload.** Checked `git log`/`git diff
  main...HEAD` before touching anything: `SchemaVersionMixin` and
  `ZK_SCHEMA_VERSION` predate this PR entirely (from PR #318's ZK v2 schema
  work), and this PR's diff touches zero lines of that mechanism — it only
  added two NEW fields to the v2 serializer (`success`,
  `substitution_classes_used`), both already `required=False`. The finding
  conflated "this PR added optional fields, correctly" with "a pre-existing,
  deliberately strict version gate is a compatibility risk" — two unrelated
  claims. The review's own investigation script runs (visible in its
  comment) never landed on a concrete mechanism, only a hedged "verify X";
  nothing to verify turned up a bug this PR introduced or could fix without
  redesigning a schema-versioning contract several PRs old.
- **Confirmed, not re-fixed: Backend Tests is the identical unrelated flake
  for the FIFTH consecutive round** (1676 passed, 203 errors, all 89
  adaptive tests passing — re-verified from the actual job log, not
  assumed from the last four rounds' results).

Declined:

- A composite `(policy_reward_applied_at, created_at)` index — a SIXTH
  appearance (rounds 3, 4, 6, 7, 8, 9) of the same still-empty-table
  nitpick.
- Splitting `skipped` into a separate `failed` counter — a THIRD appearance;
  `update_rl_model_from_feedback` still has no `beat_schedule` entry
  (checked again, not assumed), so there is still no operator consuming
  this counter to split it for.
- `@admin.display` over `short_description` — a FIFTH decline, same
  reasoning as rounds 4, 6, 7, and 8.
- An axios timeout on `suggestAdaptation`'s `/preference-model/` GET.
  Deferred to its own follow-up PR, on three verified grounds (the first
  pass recorded only the weakest of them, "consistent with a file-wide
  pattern"; re-derived properly on challenge):
  1. **It cannot fail open, structurally.** The `await axios.get(...)` is
     the *first* statement in `suggestAdaptation`, before
     `filterByStrength`. A hang never returns and a rejection propagates
     out — either way **no suggestion object is produced at all**, so
     there is no path where a failed model fetch yields an *ungated*
     suggestion. The Phase 2 C1 guarantee sits downstream of this fetch
     and does not depend on the timeout.
  2. **It is not a ZK surface.** The GET carries no body and no params;
     no password material is in the request, so a timeout has no bearing
     on the zero-knowledge property either. This is a stability/UX issue,
     not a security one, and is described that way in the follow-up.
  3. **It is pre-existing and unreachable today.** Verified on `main`
     directly (`git show main:…` — the identical untimed line is at
     line 410 there), and it appears as a *context* line, not a `+`, in
     this PR's diff. Gap D1 still holds: the only reference to
     `suggestAdaptation` outside its defining file and tests is a code
     comment, so no user can reach it yet.

  The follow-up is scoped wider than the review suggested, and that is
  what makes it a separate PR rather than a one-line patch here:
  `frontend/src/services/api.js` already builds a configured client with
  `timeout: 30000` *and* an HTTPS-enforcement interceptor, and
  `TypingPatternCapture.jsx` bypasses it by importing bare `axios` for
  **all 13** of its calls. The correct fix is migrating the file to that
  client (and retargeting the several tests that mock `axios` directly),
  not adding `{ timeout }` to the single call this PR happened to touch.
  Should land before Phase 5 mounts the UI.

Verified after this round: 91 passed / 7 subtests across
`test_adaptive_policy_bandit.py` + `test_adaptive_zk_v2.py` (+2 new tests),
Django `check` clean, `makemigrations --check` clean (no model fields
changed — the new ceiling is enforced in Python, not the schema). Frontend
untouched this round.

---

## 6. Phase 4 — Memorability and error signals (B3, B4)

### 4.1 Client-side memorability scorer

`adaptiveFeatures.js` gains the missing consumer of `memorability_params`:

```js
export function scoreMemorability(password, memorabilityParams)
```

Scores the four documented features — length fit against
`optimal_length_min/max`, repeated-pattern presence, character-class variety,
pronounceability (vowel/consonant alternation ratio) — combined by the exported
`weights`. Pure; password never leaves the function.

Then replace the fabricated formula (`TypingPatternCapture.jsx:361-364`) with
`scoreMemorability(adapted) - scoreMemorability(original)`, and pass the real
values through `apply_adaptation_v2` into `memorability_score_before/after`
(currently hard-`None`, L692-693) — which also makes `get_evolution_stats`'s
`average_memorability_improvement` stop being permanently 0.

### 4.2 Learn the memorability params (server side, aggregate only)

In `export_preference_model`:

- `optimal_length_min/max` ← the user's own `length_bucket` distribution weighted
  by per-bucket `success_rate` (derived entirely from `TypingSession` aggregates).
- The four `weights` ← EMA nudged by `AdaptationFeedback.memorability_improved`,
  attributed to whichever feature each accepted adaptation moved most. EMA, not a
  regression — the sample size does not support anything heavier.

### 4.3 Feed typing errors into ranking (B3 — the "learn from your typing errors" claim)

- Export `error_prone_positions` (already stored, `core.py:1262`) in the
  preference model.
- `rankSuggestions` gains an `errorPositions` option: **boost** candidates at or
  adjacent to high-error positions (this is where the user actually stumbles) and
  **penalize** introducing an unfamiliar character at a low-error position.
- ZK-safe: positions already cross the wire; the *join* to characters happens
  only on the client.

### 4.4 Populate the dead fields (B6)

`_update_typing_profile` (`adaptive_password_service.py:478`) additionally writes
`wpm_variance` (Welford, online), `rhythm_signature` (normalized timing-bucket
vector), and `common_error_types` (classified from `backspace_positions` adjacency
— `adjacent_key` vs `transposition` vs `other`). These are already modelled,
admin-surfaced, and DP-covered by the existing `PrivacyGuard`.

### 4.5 Tests

- `scoreMemorability` is monotone in each feature, holding the others fixed.
- Error-position boosting changes the ranking on a fixture where it should, and
  does not on one where it should not.
- `average_memorability_improvement` is non-zero after an accepted adaptation
  (direct regression test for the always-0 bug).

---

## 7. Phase 5 — Ship it (D1-D4, B5, C2)

### 5.1 Mount the UI

- New `frontend/src/Components/security/AdaptivePasswordDashboard.jsx`,
  composing the three existing orphaned components plus a consent panel.
- `App.jsx`: lazy import + `<Route path="/security/adaptive" …>` + a nav link
  alongside the other `/security/*` entries (L1709-1720). Follow the existing
  lazy + `<Suspense>` pattern exactly.
- Add the `data-testid` hooks the e2e spec already expects —
  `settings-menu`, `security-settings`, `adaptive-password-tab` (D2).

### 5.2 Enforce the suggestion cadence (B5)

- Surface `should_suggest_adaptation()` (`core.py:1026`, currently test-only) via
  `/adaptive/config/`, gated on `auto_suggest_enabled`.
- Client checks it on vault unlock; only then does it pull the preference model
  and offer a suggestion. **This is what makes the password "gradually morph"
  rather than nag.**
- Honour `auto_apply_high_confidence` + `AUTO_APPLY_THRESHOLD` (0.9) — and note
  in the UI that auto-apply still passes the Phase 2 strength gate. The gate is
  never bypassed, including on the auto path.

### 5.3 Wire adaptation into the vault (C2)

On accept, `applyAdaptation` must call the existing vault credential-update path
with the locally-computed `adaptedPassword` (currently just returned at
`TypingPatternCapture.jsx:429`). Re-encrypt client-side as the vault already
does — the new password is never transmitted in the clear.

**Ordering matters:** update the vault entry **first**, then POST the adaptation
record. If the record write fails, the user still has a working credential and a
missing analytics row; the reverse ordering loses the password.

### 5.4 Schedule the Celery beats (D3)

Add to `celery.py:79`'s `beat_schedule`:

| Task | Schedule |
|---|---|
| `security.tasks.aggregate_typing_profiles` | hourly, `crontab(minute=15)` |
| `security.tasks.cleanup_expired_adaptations` | daily, `crontab(hour=4, minute=15)` |
| `security.tasks.update_rl_model_from_feedback` | weekly, `crontab(day_of_week=1, hour=4, minute=45)` — matches the existing `RL_MODEL_UPDATE_INTERVAL_DAYS: 7` |

Off-peak and offset from the 2:00/3:30 jobs already in that schedule. Route
`security.tasks.*` to a queue consistent with the existing routing table (L44-51).

Replace the three `assertTrue(callable(...))` placeholders
(`test_adaptive_password.py:925-941`) with tests that actually run each task
against fixtures and assert its return payload.

### 5.5 Docs

- `password_manager/docs/ADAPTIVE_PASSWORD.md`: document the salt/rotation flow,
  the bandit, the strength gate, and the new endpoints. Its current
  "Suggestions are RL-powered" line (L127) becomes true at Phase 3 — **do not
  update it before then.**
- `README.md:1206` already states the ZK property correctly; extend it with the
  strength-gate guarantee.
- Note the accepted asymmetry from §1.3 (client-only gate) and the residual
  property from §1 (fingerprint strength is bounded by master-password strength).

---

## 8. Sequencing and risk

```text
Phase 1 (unblock) ──┬── Phase 2 (safety gate) ──┐
                    │                            ├── Phase 5 (ship)
                    └── Phase 3 (bandit) ── Phase 4 (memorability/errors) ──┘
```

Phase 1 is a hard prerequisite for everything — the feature does not currently
run. Phases 2 and 3 are independent and can proceed in parallel. Phase 5 must
come last: **shipping the UI before Phase 2 would expose users to adaptations
that measurably weaken their passwords.**

| Risk | Mitigation |
|---|---|
| Strength gate rejects nearly everything, leaving the feature inert | **Measured, Phase 2:** ~25% of passwords keep at least one substitution over a 200-password corpus (§4.5). Workable, so the "safer transform family" option (appending learned syllables, case-shifts at low-error positions) was not needed — but `has_suggestion: false` is common enough that the UI must treat it as a normal outcome. |
| Bandit starves on sparse data | Global DP prior for cold start; Thompson sampling explores by construction; ≥3-session floor on the behavioural term. **Shipped as specified**, plus a k-anonymity floor of 5 contributors on the global prior (§5.6). |
| Salt exposure misjudged | **Shipped, Phase 1 (§1.1):** the salt is genuinely non-secret — `AdaptivePasswordConfig.fingerprint_salt`'s own `help_text` states it, and it is useless to an attacker without the master password, which is never transmitted. Serving it over `/adaptive/config/` leaks nothing. Fingerprint-era isolation (`fp_key_version`) is enforced end-to-end: stamped from the server's own config (never the client's claim), scoped on every fingerprint-keyed read path, and bumped on rotation so eras never correlate. Residual property, not a blocker (§1): fingerprint strength is bounded by master-password strength, since HMAC is fast to brute-force offline given the master password — out of scope under this feature's threat model (hostile server, master password never transmitted). |
| zxcvbn bundle cost | **Measured, Phase 2:** ≈460 kB raw / 222 kB gzipped, entirely behind the dynamic `import()`; nothing zxcvbn-related in the entry chunk (§4.5). Not yet visible in the production build because gap D1 keeps the whole adaptive module unreachable and Rollup drops it. |
| Key rotation orphans learning | Intended — a correlation reset. Make it explicit in the UI, not a silent data loss. |

## 9. Acceptance criteria

1. The A1 blocker (no salt existed anywhere, so `deriveFingerprintKey` threw
   unconditionally) is resolved server-side and client-side — **met**, Phase 1
   §1.6; covered by `FingerprintSaltProvisioningTests` (backend salt
   provisioning) and `cryptoService.fingerprint.test.js` (client HMAC
   derivation). This is *not* the same claim as "a user can enable the feature
   end-to-end": that still needs D1 (no adaptive UI is mounted until Phase 5)
   and a cross-stack test connecting a real backend response to a real client
   derivation — a backend-only test can't prove that. Re-word this item to
   "end-to-end" only once D1/D2 ship.
2. No adaptation ever lowers `guesses_log10`, proven by property test over a
   corpus (C1) — **met**, Phase 2 §4.5; 200 deterministic passwords, each
   survivor re-measured independently of the number the gate reported about
   itself, and both gate rules mutation-checked. Scope of the claim: this is a
   *client-side* guarantee. The server never sees a password and so cannot
   verify it; that asymmetry is deliberate and documented in §1.3. Same D1
   caveat as item 1: "met" means the code and its tests exist, not that any
   real user's password is passing through this gate yet — nothing calls
   `suggestAdaptation` until Phase 5 mounts the UI.
3. The exported preference model demonstrably diverges from the static baseline
   after feedback, and the convergence test fails when the policy update is
   neutralized (B1, B2) — **met**, Phase 3 §5.6. `ConvergenceTests` drives 200
   rounds where `o→0` always rewards and `a→4` never does, asserts the exported
   weights (0.98 / 0.02) differ from the baseline (0.6 / 0.4), and a companion
   test neutralizes `apply_reward` and asserts the ordering assertion then
   fails. B2 is closed at both ends: `apply_adaptation_v2` credits an
   acceptance reward, `rollback_adaptation` a hard zero, and the client now
   sends `substitution_classes_used` and, when the outcome is actually known,
   an explicit `success` — omitted intentionally otherwise, so
   `capturePattern` falls back to the service's own heuristic rather than
   guessing. Same D1 caveat:
   the policy learns correctly once fed, but nothing feeds it from a real
   session until Phase 5.
4. `average_memorability_improvement` is non-zero after an accepted adaptation (B4).
5. Error-prone positions measurably change suggestion ranking (B3).
6. `/security/adaptive` is reachable and the e2e spec passes rather than being dormant (D1, D2).
7. Leak tests stay green — frontend, backend, and e2e network assertions.
8. No file under `mobile/` or `frontend/src/` references `original_password` / `adapted_password`, enforced in CI (A3).
9. Backend suite green under the `canny` venv with `DEBUG=True`; `npm run build` green on Vite 7.

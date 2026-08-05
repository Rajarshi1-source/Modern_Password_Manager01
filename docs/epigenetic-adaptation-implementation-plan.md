# 🧬 Epigenetic Password Adaptation — Implementation Plan

Status: **Phase 1 SHIPPED** — see §1.6 for what actually landed (PR #465) and
where it deviates from this plan. §0 and the body of §1 below are the
**pre-Phase-1 baseline**: every path, line number, field and symbol in them
was read from the tree at `main` = `0b7ee24`, *before* implementation, and
describes the gaps that motivated the plan — not the current state. Phases
2-5 are still plan-only.

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

**Exempt three of the 15 views**, not all of them: `disable_adaptive_passwords`,
`delete_adaptive_data` (erasure), and `export_adaptive_data` (portability).
Opting out and exercising GDPR rights must survive an operator flipping the
kill switch off — a disabled deployment is not a reason to make a user's data
unreachable. The other 12, including `suggest_adaptation`, stay gated: for
`/adaptive/suggest/` specifically, the flag check runs first, so a disabled
deployment returns 503 there too, not the 410 it returns when enabled.

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
- Flag off → the 12 gated endpoints 503; `disable`/`data`/`export` still
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
  out of scope.

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
| **Behavioural** | mean `error_count` and `total_time_ms` of `TypingSession` rows on `adapted_fingerprint` vs. those on `original_fingerprint` | 0.2 |

The behavioural term is the one that makes this real rather than a satisfaction
survey, and it is **fully zero-knowledge** — it joins two fingerprints, never a
password. Require ≥3 sessions on each side before it contributes; otherwise
renormalize the other weights.

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
| Strength gate rejects nearly everything, leaving the feature inert | Measure the survival rate over a password corpus **before** building UI around it. If it is very low, that is evidence for the "safer transform family" option (appending learned syllables, case-shifts at low-error positions) rather than a reason to relax the gate. |
| Bandit starves on sparse data | Global DP prior for cold start; Thompson sampling explores by construction; ≥3-session floor on the behavioural term. |
| Salt exposure misjudged | Re-derive the argument from `cryptoService.js:269` at implementation time; do not rely on §1.1's summary. |
| zxcvbn bundle cost | Dynamic `import()`, measured against the current bundle before merge. |
| Key rotation orphans learning | Intended — a correlation reset. Make it explicit in the UI, not a silent data loss. |

## 9. Acceptance criteria

1. A user can enable the feature end-to-end and a fingerprint is computed (fails today — A1).
2. No adaptation ever lowers `guesses_log10`, proven by property test over a corpus (C1).
3. The exported preference model demonstrably diverges from the static baseline after feedback, and the convergence test fails when the policy update is neutralized (B1, B2).
4. `average_memorability_improvement` is non-zero after an accepted adaptation (B4).
5. Error-prone positions measurably change suggestion ranking (B3).
6. `/security/adaptive` is reachable and the e2e spec passes rather than being dormant (D1, D2).
7. Leak tests stay green — frontend, backend, and e2e network assertions.
8. No file under `mobile/` or `frontend/src/` references `original_password` / `adapted_password`, enforced in CI (A3).
9. Backend suite green under the `canny` venv with `DEBUG=True`; `npm run build` green on Vite 7.

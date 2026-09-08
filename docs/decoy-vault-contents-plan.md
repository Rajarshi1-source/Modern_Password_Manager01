# Plan — Give the decoy session a believable vault

Closes the one limitation `VaultDuressSetup.jsx` states in its own UI copy and
that `docs/vault-unlock-envelope-integration-plan.md` §7.3 deferred as "product
work": a decoy unlock currently renders an **empty** vault, which is better
than the real list failing to decrypt row by row but is still not a
*believable* vault.

**Status: implemented.** §1–§6 describe what shipped, not just what was
drafted; where the built design differs from the first draft the reason is
recorded inline (§1.1, §2.1, §5).

**Scope: one PR, three commits.**

1. `feat(vault)` — the decoy vault itself (the subject of this plan, §1–§8).
2. `fix(ci)` — the two CodeRabbit findings still open on PR #489 (§9).
3. `fix(test)` — the six `test_layered_recovery.py` failures, whose real
   mechanism turns out not to be the one recorded last session (§10).

---

## 0. Where the limitation actually comes from

Read the code, not the summary. Three facts fix the shape of any fix:

| Fact | Evidence |
|---|---|
| `/api/vault/` returns **one** item list per account; the server has no idea which slot unlocked the session | `frontend/src/contexts/VaultContext.jsx:152` — a plain `GET /api/vault/`, no slot parameter, and none is possible |
| The server **must** stay that way | `docs/adaptive-password-zk-remediation-plan.md` §1–2; the ZK invariant forbids the server learning which slot a session belongs to. §22.1 of the envelope plan records a fix that was rejected for exactly this |
| The display gate already exists and returns `[]` | `frontend/src/App.jsx:96` `useDisplaySafeItems` |

So the decoy's contents can only ever be **client-side and device-local** —
the same posture the envelope itself already has (`unlockEnvelopeStore.js`
"STORAGE": `vaultUnlockEnvelope:<userId>` in `localStorage`, no server copy,
no cross-device sync). This plan does not change that posture, and
cross-device decoy stays out of scope for the reason §7.2 of the envelope plan
gives.

---

## 1. The store

New module: `frontend/src/services/hiddenVault/decoyVaultStore.js`.

```text
localStorage key:  vaultLocalCache:<userId>
value:             base64( 12-byte IV || AES-GCM ciphertext )
plaintext:         JSON, then NUL-padded to exactly PLAINTEXT_LEN bytes
key:               the DECOY DEK (envelope slot 1)
```

Plaintext shape:

```json
{ "v": "dvc-1", "rows": [ { "id", "item_id", "item_type", "encrypted_data", "favorite", "created_at" } ] }
```

`encrypted_data` is a **normal `sessionVaultCrypto` v2 envelope**
(`{v,iv,ct,salt}`) sealed under the same decoy DEK, carrying the same
`salt` the decoy slot stamps. That is deliberate double encryption and it buys
the property this whole feature depends on: **a decoy row is byte-shaped
exactly like a server row**, so every consumer above the store —
`VaultItemsSection`, `VaultDashboard`, `decryptEnvelope`, `keyForSalt`'s
matching-salt fast path — works on it unmodified. No display code learns that
decoy rows exist.

### 1.1 One store, not a seed plus an overlay

The decoy slot has ~15.8 KB spare (`TIER_SLOT_PAYLOAD_LEN[TIER0_32K] = 16000`
against a ~150-byte payload) and putting the items there is tempting. It does
not work for the *mutable* half: re-encoding the envelope requires **both**
passwords (`unlockEnvelopeStore.setDecoySlot`, and `encode()`'s contract that
the outer salt and both nonces must be fresh), and a decoy session by
definition does not have the real one. A seed-in-slot design would therefore
need a second mutable store layered over it anyway. One store does both jobs.

### 1.2 Indistinguishability — the part that is easy to get wrong

A `localStorage` key that appears **only when a decoy is configured** *is* the
oracle this feature exists to remove: a coercer with devtools reads the
feature's existence off the key list, and no amount of ciphertext strength
helps. Two rules, both non-negotiable:

- **`provision()` writes the blob for every account**, decoy or not: an empty
  container sealed under a throwaway key that is generated, used and dropped,
  so nothing can ever decrypt it and it is observationally random. This is the
  same trick `hiddenVaultEnvelope.encode()` already uses for an unconfigured
  decoy slot (`keyFor`, quoted in `provision`'s own docstring) — so the
  precedent and its rationale are already in this codebase; we are extending
  it, not inventing it.
- **The blob is a constant length.** The plaintext is padded to `PLAINTEXT_LEN`
  before encryption, so ciphertext length is fixed and the number of items —
  and whether there are any — never leaks. `provision`'s filler is written at
  exactly the same length, and the test asserts the two against each other
  rather than each against itself.

The key name is deliberately not `vaultDecoyItems`. It is a local cache; that
is a true description and it names nothing.

### 1.3 Capacity

`PLAINTEXT_LEN = 12000`. A row costs roughly `260 + 1.4 × |plaintext item|`
bytes, so ~12–20 typical credentials fit. Overflow is a **caller-facing error
at seed time**, never a silent truncation: `DecoyCapacityError`, surfaced in
`VaultDuressSetup` as "Those entries do not fit. Remove one and try again." A
decoy-session add that would overflow is refused with the existing
byte-identical `DECOY_WRITE_REFUSAL` string, because in a decoy session the
message reaches a coercer's screen and must stay indistinguishable from an
ordinary save failure.

---

## 2. Key handling

The decoy DEK never leaves the hidden-vault modules, matching the discipline
`unlockEnvelopeStore` already documents ("callers never see decoy key
material").

| Moment | Session | How the store gets a key |
|---|---|---|
| `provision()` | real | throwaway `crypto.getRandomValues` key, discarded |
| Seed / edit contents | real | `unlockEnvelopeStore.open({ password: decoyPassword })` → raw decoy DEK, used and dropped |
| Decoy-session write | decoy | the **session key itself** — it *is* the decoy DEK, non-extractable |

For the third row we need primitives `encryptItem` cannot provide, because
`encryptItem` must keep refusing (a decoy-session write reaching `/api/vault/`
permanently corrupts a row in the one shared list — `sessionVaultCrypto.js`
explains why there is no salt choice that fixes it). Three shipped, all in
`sessionVaultCrypto` beside `encryptItem`:

| Primitive | Refuses iff |
|---|---|
| `encryptItem` | `sessionIsDecoy` |
| `encryptDecoyItem` | `!sessionIsDecoy` |
| `encryptDecoyContainer` / `decryptDecoyContainer` | `!sessionIsDecoy` |

Exact opposites on one flag, written next to each other, so neither can be
widened without the other becoming visibly wrong. This is the choke-point rule
from envelope-plan §33.1 — the gate goes where the key is, not in each caller.

### 2.1 `sealItem` is shared, not copied

`encryptItem` and `encryptDecoyItem` both delegate to a private `sealItem`.
A decoy row has to be byte-shaped exactly like a server row or the display
path stops treating the two identically, which is the entire basis of §1's
design; two copies of the envelope-building code would be two things to keep
in sync, and the drift would be invisible until a decoy row failed to render.
`sessionVaultCrypto.decoyPrimitives.test.js` asserts the two envelopes agree
on version, salt and field set rather than merely both "looking like"
envelopes.

---

## 3. Reads

`useDisplaySafeItems` (`App.jsx:96`) is already the single display choke point
and stays the only one. It changes from "empty in a decoy session" to "the
decoy list in a decoy session":

```js
const isDecoy = sessionVaultCrypto.isDecoySession();
const decoyRows = useDecoyRows(isDecoy);           // [] until loaded
return useMemo(() => (isDecoy ? decoyRows : items || []), [isDecoy, decoyRows, items]);
```

Rules this must hold, each one a bug this codebase has already paid for:

1. **`refreshItems()` keeps running unchanged in a decoy session.** The real
   `GET /api/vault/` must still happen, with the same timing and the same
   response size, or the decoy is distinguishable by traffic analysis alone
   (`vault-unlock-envelope-integration-plan.md` §21.1). Its result is fetched,
   held in `items`, and simply not displayed.
2. **Failure to load the decoy rows renders `[]`, never `items`.** The
   fallback direction is the current shipped behaviour; falling back to the
   real list would be strictly worse than what we started with.
3. **The rows load from the live decoy flag, not from a cached copy of it.**
   Envelope-plan §29.1/§30.1/§31.1 were three consecutive rounds of one bug:
   a cached or adjacent signal standing in for the live fact. Read
   `isDecoySession()` at render, key the loader off the session generation.

---

## 4. Writes

Four mutations route to the store in a decoy session instead of `axios`:
`addItem`, `updateItem`, `deleteItem`, `toggleFavorite`. Each keeps its
existing shape — same `setItems` update, same `setError`, same return value —
so the UI cannot tell the two paths apart.

`createBackup`, `getBackups`, `restoreBackup` keep their current refusals
(`VaultContext.jsx:1104/1144/1168`). They are server-side operations on the
real account and a decoy session must not reach them; that gate was hardened
only last PR and this one does not touch it.

**A note that must not be lost, because it is the residual hole:** a real
write POSTs, a decoy write does not. A passive network observer can therefore
still distinguish the two. This is *pre-existing* — the current refusal also
makes no request — and it is not fixable here, because the only way to emit a
matching POST is to write decoy ciphertext into the shared server list, which
is the exact corruption `encryptItem`'s refusal exists to prevent. Recorded in
§8 and in `SECURITY.md`, not silently carried.

---

## 5. Seeding — `VaultDuressSetup`

A second form on the existing page, below decoy setup: **Decoy vault
contents.** Fields per row (site, username, password, notes), three empty rows
by default, add/remove, plus a live "N of ~15 entries" capacity hint.

Submitting takes **both passwords**. The decoy one is structural — the store
is keyed by the decoy DEK and opening slot 1 is the only way to reach it,
which has the useful consequence that contents can be edited later without
re-running `setDecoySlot`, so the duress token is never regenerated and never
needs re-registering.

The **real** one is a security gate, and the first draft of this plan omitted
it. Without it this form is a password classifier: a coercer with an
authenticated session types the password they were handed, and the
success/failure split tells them whether it was the decoy — precisely the
disclosure the feature exists to prevent. It is the same argument §22 of the
envelope plan makes for the recovery form, and the same one §24.1 records
having got wrong once. Past that gate the messages may be specific, because
the operator has already demonstrated the real credential.

The seeding entry point is `unlockEnvelopeStore.seedDecoyContents`, not a
method on the store: it opens slot 1 and hands the key straight to
`decoyVaultStore.seedWithKey`, so no component ever holds decoy key material
(the discipline `setDecoySlot` already follows) and the module dependency runs
one way only, with no import cycle.

We do **not** auto-generate filler credentials. What is plausible depends
entirely on who the user is and who is coercing them; a generator would
produce a recognisable signature across every install of this app, which is
the opposite of the goal. The UI says so.

The header comment's LIMITATION block and the on-screen notice both get
rewritten — narrowed to what is still true (device-local, no cross-device
decoy, write traffic distinguishable), not deleted.

---

## 6. Tests

Vitest, following the existing `*.decoySession.test.jsx` naming:

- `decoyVaultStore.test.js` — round-trip; constant ciphertext length across
  0/1/12 rows *and* against `provision`'s random filler (the indistinguishability
  property, asserted directly); capacity error; corrupt-blob → `[]`, no throw;
  wrong key → `[]`.
- `sessionVaultCrypto.decoyPrimitives.test.js` — the mirrored predicates: each
  primitive refuses in the other's session, a locked vault reports locked
  rather than leaking decoy state, both await guards drop their result when the
  session changes mid-call, and `DECOY_WRITE_REFUSAL` is sourced from the
  module, never re-typed as a literal (envelope-plan §39.3 / §40.1: a copied
  literal makes the assertion compare the mock to itself).
- `unlockEnvelopeStore.test.js` (extended) — `provision` writes the blob for an
  account with no decoy; seeding leaves the envelope byte-identical so the
  duress token survives; the real password is refused rather than sealing
  contents no decoy session could open.
- `VaultContext.decoySession.test.jsx` (extended) — delete/favourite in a decoy
  session mutate the store, make **zero** requests, and leave the real list
  untouched; a store failure surfaces the shared refusal string.
- `VaultDashboardRoute` / `VaultItemsSection` `.decoySession.test.jsx`
  (extended) — both display surfaces render the decoy rows and decrypt the
  decoy ciphertext, never the real one; an unconfigured or unreadable store
  renders empty rather than falling back to the real list.
- `VaultDuressSetup.test.jsx` (extended) — only filled entries are seeded, the
  real-password gate refuses, a capacity refusal names nothing, a mid-submit
  lock withholds the success message, and the form is absent in a decoy session
  and while locked.

Negative controls assert on the **returned value**, not on which branch ran
(§34.1).

---

## 7. Risks

| Risk | Handling |
|---|---|
| Padding bug leaks item count | Length asserted in tests against the `provision` filler, not just self-consistently |
| A new display surface bypasses `useDisplaySafeItems` | Same exposure as today; the hook's comment already carries the rule |
| Decoy write overflows capacity mid-coercion | Refused with the byte-identical generic string; never truncates |
| `localStorage` unavailable | Same accepted degradation as `hasEnvelope` — decoy renders empty, i.e. today's behaviour |
| Real session ever writes the store | Impossible by predicate: `encryptForDecoyStore` refuses outside a decoy session |

---

## 8. What is still not solved

Stated here so the next reader does not have to rediscover it:

1. **Write traffic is distinguishable** (§4). Pre-existing, unfixable without
   breaking the shared item list.
2. **Cross-device.** The decoy vault is device-local, like the envelope.
   Unlocking a decoy on a second device shows an empty vault.
3. **Backups.** `createBackup` still refuses in a decoy session.
4. **Password-login users.** Still out of scope; they never see
   `VaultUnlockModal` (envelope-plan §7.1).

---

## 9. Commit 2 — the two open CodeRabbit findings on PR #489

### 9.1 Python support floor (`password_manager/README.md:532`)

`SECURITY.md:14` declares Python `<3.12` unsupported. Everything that actually
runs says otherwise: `README.md` and `GEOIP_SETUP.md` say 3.10+, six workflows
pin `3.11`, and all four `docker/backend/Dockerfile` stages are
`python:3.11-slim-bookworm` — including a hardcoded
`/usr/local/lib/python3.11/site-packages/oqs` copy at line 230, which is a
*path*, so a base-image bump without it silently breaks the liboqs stage.

Resolution: **raise the runtime to 3.12** rather than lower the policy. 3.11 is
in security-fix-only maintenance; matching the config to the weaker claim moves
in the wrong direction for a password manager. Django 5.1/5.2 and DRF 3.17.2
both support 3.12.

Files: `.github/workflows/{backend-ci,ci,security-multi-scanner,security-sbom,security,stackhawk}.yml`,
`docker/backend/Dockerfile` (4 `FROM`s, the site-packages path, and the comment
at `ci.yml:536` that names the base image), `password_manager/README.md`,
`password_manager/GEOIP_SETUP.md`.

The Dockerfile change is the one only CI can fully verify; the `Build Docker
Image` job is the gate.

### 9.2 `nltk` advisory severity (`SECURITY.md:62`)

GHSA-8mgp-746c-j5xp is **High** upstream. The entry records Medium without
saying that is a *local residual* judgement, which reads as a contradiction of
the advisory. Split the two: upstream severity High; residual Medium, because
the affected loaders are unreachable (`import nltk` / `from nltk` / `nltk.`
return zero matches under `password_manager/`, already verified in the
`Mitigation` line). No CVSS number is asserted, because the advisory publishes
none — CodeRabbit's own web check confirmed that, and the current entry does
not actually claim 8.3, so this is a wording fix, not a retraction.

`DEPENDENCY_POLICY.md:59` requires every accepted risk to carry a `SECURITY.md`
entry; this edits an existing one, so no new cross-reference is needed.

---

## 10. Commit 3 — `test_layered_recovery.py`

**Correcting last session's diagnosis.** It was reported as test-order
pollution, on the evidence that `test_post_creates_factor` passes alone and
fails in the full run. That evidence was real but the conclusion was too
vague to act on. Running the file by itself reproduces all six failures in
3m33s, and the traceback names the mechanism outright:

```
rest_framework.exceptions.Throttled: Request was throttled. Expected available in 3598 seconds.
```

- `RecoveryThrottle` (`auth_module/recovery_throttling.py:19`) is `3/hour`,
  scoped by cache key `throttle_recovery_<ViewClass>_<user.id>`.
- Under `TESTING`, `settings/base.py:2689` clears
  `DEFAULT_THROTTLE_CLASSES` — but these views set `throttle_classes`
  **explicitly** (`wrapped_dek_view.py:60`, `recovery_factor_view.py:59/339/447`,
  `time_locked_view.py:188/…`), so the setting never applies to them.
- `CACHES` under `TESTING` is `LocMemCache`, which is process-global and is
  never cleared between tests. Nothing in `conftest.py` clears it.
- Locally the DB is SQLite, whose PK sequence rolls back with each test's
  transaction, so every test's `user` fixture gets **the same `user.id`** and
  therefore the same throttle key. The 4th request in a class is refused.

That last point is also why CI is green rather than hiding a failure:
PostgreSQL sequences are non-transactional, so `nextval` does not roll back and
each CI test gets a fresh `user.id` and a fresh throttle bucket. The
Postgres-backed jobs are honestly passing — but on an accident of sequence
semantics, not on isolation.

**Fix:** an autouse fixture in `password_manager/conftest.py` clearing every
configured cache before and after each test. This targets the class, not the
six symptoms: the same latent trap sits under `RecoveryInitiateThrottle` and
`RecoveryCompleteThrottle`, which key on **IP** (`get_ident`) — constant at
`127.0.0.1` for every test on every backend, so those would eventually bite CI
too, Postgres or not.

Before/after both, so a test that seeds the cache cannot leak forward and a
mid-run failure cannot leave state behind.

**Verification:** the file goes 6 failed / 12 passed → 18 passed; then the
`auth_module` and `security` suites; then the full backend suite, compared
failure-for-failure against the pre-change baseline recorded last session
(2056 passed / 7 failed / 13 skipped) to prove the fixture regresses nothing.

### 10.1 Separately worth knowing

`.github/workflows/backend-ci.yml:227` runs `pytest … -x` with
`continue-on-error: true`, so that job's green tick means "the step ran", not
"the tests passed". `ci.yml`'s `Backend Tests` job has neither flag and is the
one actually gating. Not changed here — flipping a `continue-on-error` is its
own PR with its own fallout — but recorded so no future session reads
`backend-ci`'s tick as evidence again.

---

## 11. Related

- `docs/vault-unlock-envelope-integration-plan.md` §7.3 — the deferral this closes
- `docs/privacy-features-gap-remediation-plan.md` §4.2 — origin of the duress work
- `docs/adaptive-password-zk-remediation-plan.md` §1–2 — the ZK invariant that rules out a server-side decoy
- `password_manager/hidden_vault/SPEC.md` — blob format and slot semantics

---

## 12. Review round 1 (PR #503, 2026-09-08) — Codex + CodeRabbit

Two bots reviewed the same diff. Every finding below was verified against the
source before acting; the ones declined are recorded with the reason, because
"the bot said so" is not evidence and neither is "the bot is wrong".

**No CI check was failing when this round started** — the SBOM break from the
Python bump had already been fixed, and the full matrix settled with zero
failures. These are correctness findings, not red builds.

### 12.1 The envelope version — the one that made the feature not work

`seedWithKey` hand-wrote `v: 'v2'` into each row's `encrypted_data`.
`sessionVaultCrypto.decryptItem` accepts **only** `PAYLOAD_VERSION`, which is
`'svc-gcm-1'`, and returns `{_legacyPlaintext: true}` for anything else. So
every SEEDED row rendered as a "legacy plaintext — re-save to encrypt" warning,
while rows added later through `encryptDecoyItem` decrypted correctly: a decoy
vault that was half warning banners is worse than the empty one it replaced.

This is §39.3's copied-literal trap, in a module written to avoid it, and the
test suite missed it for the §34.1 reason: `decoyVaultStore.test.js` decrypted
the row with raw WebCrypto, which is exactly the check that cannot notice a
wrong version string. `PAYLOAD_VERSION` is now exported and imported, and a new
test runs a seeded row through the real `decryptItem` and asserts
`_legacyPlaintext` is absent — an assertion on the returned VALUE, not on which
branch ran.

**The rule, stated so the next module inherits it:** a value two modules must
agree on byte-for-byte cannot be a literal in both, and a test that verifies
the producer without the consumer verifies nothing about the pair.

### 12.2 Three gaps in "the decoy behaves like a real vault"

- **`decryptItem` could not find a decoy row.** It looks up `items`, which in a
  decoy session deliberately holds the REAL list (fetched for traffic analysis,
  never displayed), so every click on a decoy row threw "Item not found". It
  now falls back to the store in a decoy session.
- **The canonical Add form never reached the decoy path.** `App.jsx`'s
  "Add New Password" `handleSubmit` calls `encryptEnvelope` and `axios.post`
  directly — it renders OUTSIDE `VaultProvider`, so it cannot use `addItem` at
  all. Only VaultContext's copy had a decoy branch, so the screen a coercer is
  most likely to be sitting in front of still visibly failed. Both now call one
  shared `decoyVaultStore.addRowForSession`.
- **Seeded entries rendered as "Untitled".** The setup form stored `site`; the
  vault's display surfaces read `data.name` and `data.website`. Contents the
  user wrote to look plausible rendered unlike every real entry.

**One shape underneath all three: the feature was verified against the modules
it touched, not against the screens a user reaches.** Grep for the CONSUMER of
every field and every id before calling a display path done.

### 12.3 Two indistinguishability holes

- **The contents blob was only created by `provision()`**, which an existing
  user with an envelope never runs again — their unlocks go straight to
  `open()`. For them the key would first appear when they SEEDED contents,
  making its presence in `localStorage` the exact "a decoy exists" oracle the
  always-present fixed-length design denies. `open()` now backfills it after a
  successful decode (so a wrong-password probe writes nothing).
- **`handleSeedContents` had no submit-time session gate**, while both sibling
  handlers on the same screen do. A form already on screen when the session
  flipped could still be submitted, and would answer "Incorrect vault
  password." to a coercer who had just watched that password unlock the vault.
  §38.2's rule restated: the boundary must never check less than the render
  gate — and this is now the third handler on this one screen to need it.

### 12.4 Three data-integrity findings

- **Changing the decoy password orphaned the contents.** `setDecoySlot` mints a
  fresh decoy DEK on every run and did not touch the container, so the next
  decoy unlock silently opened empty. Migration is impossible from there (it
  needs the OLD decoy password, which that function is never given), so the
  container is re-keyed to an empty one under the new DEK and `setDecoySlot`
  returns `contentsReset` for the UI to say so.
- **The decoy edit spread the whole `item` over the row**, so a caller passing
  `favorite: undefined` cleared the flag (`stripDisplayFlags` drops undefined).
  The real path deliberately PATCHes `encrypted_data` alone for exactly this
  reason; the decoy branch now matches it.
- **Concurrent mutations could discard each other.** Each did its own
  load-modify-save, and `favoriteInFlightRef` only serializes per item id.
  Serialization now lives in `decoyVaultStore.mutate` — at the store, so every
  caller inherits it, rather than in the one caller that noticed.

Also: `seedWithKey` discarded `writeRaw`'s boolean, so a `localStorage`
rejection reported success for contents that were never stored.

### 12.5 CI and docs

- **`Dockerfile.prod` is now the one file deliberately NOT on the 3.12 floor**,
  and reverting it is the fix, not an exception grudgingly made: its runtime is
  `gcr.io/distroless/python3-debian12`, whose interpreter is Debian 12's 3.11.
  A 3.12 builder produces a `/venv` with 3.12 paths and 3.12-ABI extension
  wheels that the 3.11 runtime cannot load — and no CI job builds this file, so
  nothing would have caught it. **A version bump's blast radius includes every
  image whose interpreter it does not own.**
- **`safety==2.3.5` removed from two installs.** In `ci.yml` it was installed
  *after* `requirements.txt` (which pins `safety>=3.8.1` and `packaging==25.0`);
  2.3.5 requires `packaging<22`, so pip downgraded packaging inside the very
  environment the tests then ran in. In `backend-ci.yml`'s lint job it was never
  invoked at all. The two `pipx install` uses are left alone: pipx isolates them
  in their own venv and they are demonstrably green on 3.12 in this PR's runs.
- **`SECURITY.md` now records CVSS v4.0 8.3 with its vector.** The previous
  entry said "none asserted", which was wrong — verified by fetching the
  advisory rather than taking either bot's word, which also caught that the
  vector is `AT:N`, not the `AT:P` one of the review comments quoted.
- Deployment guides now name the releases that actually carry `python3.12`
  (Ubuntu 24.04+/Debian 13+) instead of a generic "Ubuntu/Debian".

### 12.6 Declined

Nothing was declined outright this round. The `pipx`-isolated Safety installs
are the only finding not acted on, and the reason is above rather than a
disagreement about the underlying fact: Safety 2.3.5 genuinely does not claim
3.12 support, but pipx removes the dependency conflict that made it a problem,
and changing the pin risks Safety 3.x's authentication requirements on a
currently-green job — a trade to make deliberately, not inside a review round.

Frontend suite after this round: **79 files, 907 tests, all passing**; eslint
clean. No backend Python changed, so the backend suites from §10 stand.

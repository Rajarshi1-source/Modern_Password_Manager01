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

---

## 13. Review round 2 (PR #503, 2026-09-08) — CodeRabbit

**No CI check was failing.** The PR read "All checks have passed" — 34
successful, 7 skipped, 1 neutral — before and after this round. Everything
below is a correctness finding.

Each claim was checked against the source, and three were checked against the
live CI logs rather than reasoned about, which changed the answer twice.

### 13.1 A silent, signed, EMPTY SBOM (the one that mattered)

`.github/workflows/ci-sbom.yml` — a file this PR never touched — ran
`cyclonedx-py -r -i ... > sbom.python.cyclonedx.json || true` on the legacy 1.x
CLI. Reading the log for commit `31a144d`: it died with
`ImportError: cannot import name 'appdirs' from 'pkg_resources.extern'`, the
redirect had already created a **zero-byte file**, `|| true` swallowed the exit
code, and the job uploaded that empty file alongside the cosign-signed image
SBOM. Green job, empty artifact, asserting something untrue about the
dependency tree.

This is the same defect §12.5 fixed in `security-sbom.yml`, in a sibling that
round did not sweep. **The rule I already had and did not apply: fixing a bug
class in one file is not fixing the class — grep every sibling in the SAME
round.** There were three `cyclonedx-py` call sites; I fixed one.

Now on the 7.x line the repo's own `requirements-lock.txt` already pins
(`cyclonedx-bom==7.2.1`), with `|| true` gone and a verify step that fails on an
empty file *or* a zero-component document.

**`security.yml` is deliberately left on the 1.x CLI.** Its log shows a real
3705-byte SBOM: it works because it pins `setuptools<81`, which still vendors
the module 1.x imports. It also has its own verify step, so it fails loudly
rather than silently. That evidence also corrects §12.5's wording — the trigger
is the SETUPTOOLS version, not Python 3.12.

### 13.2 Two real defects in this PR's own code

- **Decoy row ids could collide.** `addRowForSession` used `d${Date.now()}`.
  `mutate` serializes writes but does nothing about the clock, so two appends
  inside one millisecond shared an id — and `deleteItem`/`toggleFavorite` match
  by id, so one delete would have removed both rows. Now carries a random
  suffix.
- **The backfill could overwrite a seed.** `writeUnconfigured` checked the key
  was absent, then did key generation and AES-GCM work, then wrote
  unconditionally. A seed landing in that window was replaced by filler nothing
  can decrypt, and the next decoy unlock would render empty. It now re-checks
  immediately before writing — the same compare-before-write shape `provision`
  already uses across its Argon2 awaits.

The interleaving test for the second one was **verified to fail without the
fix**. It first passed for the wrong reason: raced unsynchronised, the
backfill's crypto is shorter, so it usually finished first and the seed landed
on top regardless. It now holds the backfill inside its own AES-GCM call until
the seed has committed (§38.4 — synchronise on the thing being timed).

### 13.3 Test isolation

`conftest.py` wrapped `caches[alias].clear()` in `except Exception: pass`. A
swallowed failure leaves an alias uncleared while the suite still reports
green — silently restoring the exact leakage §10 added the fixture to prevent.
The guard is gone; under `TESTING` both aliases are LocMemCache and cannot
fail, and a future alias that can is a configuration problem worth failing on.

### 13.4 Documentation that had become false

- **`README.md` claimed "CI, Docker and the deployed image all run 3.12".**
  My own sentence, and untrue since §12.5 pinned `Dockerfile.prod` back to
  3.11. Now states the exception explicitly.
- **The Debian claim was wrong.** Both guides said `python3.12` is in the
  default repositories on "Debian 13+". Checking `packages.debian.org/trixie`
  directly: **not available in this suite.** Debian ships no `python3.12`
  package in any current release (bookworm has 3.11, trixie has 3.13), and
  deadsnakes is Ubuntu-only. Both guides now say Ubuntu 24.04+ only and point
  Debian users at pyenv, a source build, or the backend container.

### 13.5 Declined, with the evidence

- **"Run Safety on 3.11 instead of 3.12."** Checked the live log: Safety 2.3.5
  runs fine on 3.12 — it prints its banner and emits only a `pkg_resources`
  deprecation warning. The support matrix does not list 3.12; the tool works.
  No change for a hypothetical.
- **"Remove `|| true` from `security.yml`'s safety and pip-audit steps."**
  That is a policy change, not a bug fix, and it would turn a green gate red
  immediately — this repository carries 309 open Dependabot advisories on
  `main`. pip-audit is *already* properly gated in
  `security-multi-scanner.yml`, with the dated `pip-audit-ignores.txt` expiry
  manifest and a pre-check that fails on stale suppressions. Duplicating that
  gate without the suppression mechanism would block every PR on findings the
  project has already triaged. Worth doing deliberately, in its own PR, with
  the manifest wired in.
- **`Dockerfile.prod`'s entrypoint.** The finding is almost certainly right:
  the distroless runtime supplies its own `ENTRYPOINT`, so `CMD ["daphne", …]`
  becomes arguments to the interpreter and Python looks for a *file* named
  `daphne`; separately the copied venv's interpreter symlink points at a path
  the runtime image does not have. Not changed, because nothing here can
  verify a change — **no CI job builds this file** (only docs reference it) and
  the local Docker engine is erroring, so any "fix" would be reasoning
  presented as a result. The failure modes are now written into the file so
  nobody deploys it believing it works; it needs its own PR with a build-and-run
  smoke test.

Frontend after this round: **79 files, 910 tests, all passing**; eslint clean.
Backend: `test_layered_recovery.py` 18 passed, confirming the conftest fixture
still isolates without the swallowed exception.

---

## 14. Review round 3 (PR #503, 2026-09-12) — CodeRabbit

**No CI check was failing.** "All checks have passed" — 34 successful, 7
skipped, 1 neutral. Correctness findings only.

Most of this round was a **re-post of round 2**, several comments literally
marked *Outdated* by the bot itself. Per the rule in the envelope plan's §35.1,
re-posted findings are checked against the answer already in this document
before anything is touched. Three things were genuinely new.

### 14.1 A cross-tab stale write (real, and the only new code defect)

`saveForSession` encrypted, then wrote, without comparing against what was
stored. Within one tab that is covered: `mutate` brackets its awaits with
session-generation checks, `encryptDecoyContainer` guards its own await, and
there is no await between it returning and `writeRaw`.

**Across tabs it was not covered, because the generation counter is module
state and a second tab has its own.** Tab A holds a decoy session and starts a
mutation; tab B holds a real session and rotates the decoy password, which
mints a fresh DEK and re-keys the container (`setDecoySlot` → `resetForNewKey`).
Tab A cannot see any of that, so its in-flight write lands on top of the
rotation carrying old-DEK ciphertext — and the *new* decoy password then opens
a vault nothing can decrypt.

Fixed with a compare-and-swap on the stored bytes: `mutate` snapshots the raw
value it decoded from and `saveForSession` refuses if storage has moved.
Comparing bytes is what crosses the tab boundary, and it is the idiom
`provision` and `setDecoySlot` already use on the envelope itself. Only
`mutate` carries the snapshot — adding it to `seedWithKey`/`resetForNewKey`
would make a legitimate rotation refuse whenever a decoy tab wrote
concurrently, which is backwards.

Verified to fail without the fix.

### 14.2 A flaky test I introduced in round 2

Adding the rotation test exposed that §13's backfill test was **not
deterministic**: it held "the first `subtle.encrypt` call", but the seed it
races also encrypts, so when the seed's call arrived first the latch held the
*seed* and the test deadlocked on its own await. Measured: 1 failure in 3 runs.

Both tests now arm the latch for one specific operation and `waitFor` that
operation to actually be inside its encryption before the interleaving is
triggered. Five consecutive clean runs.

**"Hold the first call" is a race, not an ordering** — the §38.4 lesson one
level deeper: synchronising on *a* call is not synchronising on *the* call.

### 14.3 Documentation contradictions, including one of my own siblings

- **The deployment guide's production section was the sibling I missed.** Round
  2 fixed the Quick Start block's Python note and left the Production block's
  identical `apt-get install python3.12` untouched — **in the same file**. That
  is the sibling-sweep rule failing twice in three rounds, the second time
  inside a single document.
- **README vs. SECURITY.md vs. the Dockerfile disagreed about the production
  image.** The resolution is a fact worth stating plainly rather than a wording
  tweak: every workflow builds `docker/backend/Dockerfile` and that is what
  Kubernetes deploys; `password_manager/Dockerfile.prod` is built by **nothing**
  and carries a recorded startup-blocking defect. SECURITY.md's support row now
  names the file it means, and lists `Dockerfile.prod` as unsupported. The
  README no longer presents it as a "production exception".

### 14.4 Declined — the Safety pin, for the third time in three rounds

Each round has proposed a different remedy for `safety==2.3.5` on Python 3.12:
first "use 3.11", now "pin `safety==3.8.1` to match the repo". The stated harm
this time is that "its unguarded installation can stop each job before the scan
runs". **That is measurably false** — the `security.yml` log shows Safety
installing and running on 3.12, printing its banner and a full report.

The proposed replacement is not clearly better: `safety check` is deprecated
upstream (the 3.x CLI prints *"will be unsupported beyond 1 May 2024"*,
verified locally against safety 3.7.0 in the project venv), and all three call
sites are wrapped in `|| true` / `continue-on-error`. Swapping a working tool
for a deprecated code path behind a swallow is how working scan output becomes
silently empty output — the exact failure §13.1 was about.

The real remedy is migrating to `safety scan` with a `SAFETY_API_KEY` secret,
which is an infrastructure change needing a credential, not a review-round
edit. Recorded here as a standing item so the fourth round does not re-litigate
it from scratch.

Frontend after this round: **79 files, 911 tests**, five consecutive clean runs
of the concurrency suite; eslint 0 errors. No backend source changed.

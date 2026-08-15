# Vault v2 Salt Portability — Implementation Plan

Status as of 2026-08-15. Branch `fix/vault-v2-salt-portability`.

Originally drafted as "PLAN C — v2 key derivation: device-local salt and no
verifier", the third of three independent follow-ups. The other two shipped
first and are **merged**:

| Plan | Branch | PR | State |
|------|--------|----|-------|
| A | `feat/adaptive-delta-aware-memorability-weights` | #477 | Merged 2026-08-12 |
| B | `fix/vault-v3-unlock-degraded-mode` | #478 | Merged 2026-08-14 |
| **C** | **`fix/vault-v2-salt-portability`** | **this one** | In progress |

**Round-1 review-fix (PR #480, CodeRabbit, 2026-08-15):** 3 actionable findings,
all verified against the shipped code before any change and confirmed real —
none were re-raises of already-declined items:
1. Session-generation guard added to `initSessionKeyFromPassword`,
   `setupVaultPassword`, `unlockWithVaultPassword` (§4 Step 1b) — closes a
   real logout/account-switch race that Step 1's password retention made
   newly possible.
2. `App.jsx`'s separate auto-unlock `useEffect` (`:1137-1145`) brought in
   line with `handleSubmit`'s already-fixed OR-of-both-keys locked check
   (§4 Step 2 addendum).
3. Two documentation nitpicks fixed in place: the foreign-salt-only cache
   description (§4 Step 1) and reproducible mutation-check commands (§5).
   Plus one documentation addition requested as "Major": the `sessionPassword`
   security-trade-off note (§4 Step 1).

**Round-2 review-fix (PR #480, CodeRabbit, 2026-08-16):** 3 actionable
findings, all independently verified against the round-1 code (not assumed
correct because CodeRabbit said so) before any change:
1. **Real bug, confirmed and fixed:** `setupVaultPassword`'s
   `localStorage.setItem` ran *before* the round-1 generation check, so it
   was unguarded — a stale (superseded) call could still persist its own
   wrapped-DEK record, and if it happened to finish writing *after* the
   newer, winning call, it would silently overwrite the newer password's
   record with the older one's. Reproduced empirically before fixing (a
   scratch mutation test showed the placeholder `wrapped` value from the
   stale call landing in `localStorage` over the real newer record), fixed by
   moving the `localStorage.setItem` after the check (§4 Step 1b), and locked
   in with a new permanent regression test — see §5.
2. **Real gap, confirmed and fixed (narrowly):** `login()` (`useAuth.jsx`)
   sets `isAuthenticated` true *before* `handleLogin` (`App.jsx`) reaches the
   v2/v3 key bootstrap — confirmed by reading both files, not taken on faith.
   The auto-unlock `useEffect` (`:1137-1145`) fires on that early
   `isAuthenticated` flip, can see both keys still absent, and open
   `VaultUnlockModal` — and nothing was closing it again once the keys
   actually finished establishing a few hundred ms later, for what could be
   *every* password login, not just the failure-mode edge case round-1's
   note described. Fixed with a single targeted line in `handleLogin`,
   immediately after the v2/v3 bootstrap block: close the modal if either
   layer is now ready (§4 Step 2 addendum, updated). This is deliberately
   **not** the full reactive-state rewrite CodeRabbit's longer suggestion
   described (exposing key readiness through React state with an ordering
   guarantee) — the targeted close call resolves the concrete "stuck open"
   failure mode CodeRabbit demonstrated without that larger, riskier change.
   No new test added for this one — see the reasoning already on record in
   §4 Step 2 addendum for why an `App.jsx`-level test harness is out of scope
   here; unchanged by this round.
3. **Documentation fix (Minor):** `vaultEnvelope.js`'s header comment claimed
   v2 items are readable only on the device that wrote them — true before
   round-1's Step 1, false after it for path (A) (password-login; `keyForSalt`
   now recovers foreign-salt items on any device). The device-local limit is
   real only for path (B) (OAuth's wrapped-DEK fallback, which has no
   password to re-derive from). Corrected.
4. **Nitpick, addressed:** Step 3's salt-minting/logging behavior had no
   dedicated test coverage. Added two — see §5. Did **not** expand Step 3's
   actual behavior beyond what round-1 shipped (a log line, not the
   distinct-signal UI the original plan sketched and round-1 explicitly
   declined as disproportionate) — the nitpick asked for coverage of what's
   implemented, not a scope increase, and the auto-generated "fix" prompt
   attached to it oversold the ask relative to its own title.

---

## 1. The bug

`getOrCreateUserSalt` (`frontend/src/services/sessionVaultCrypto.js:61-70`)
reads `localStorage['vaultKeySalt:<userId>']` and, when absent, mints a fresh
random salt and persists it. **The salt is never sent to the server.**

The v2 session key is `PBKDF2(masterPassword, thatSalt)`. So:

> Items written on device A are undecryptable on device B, and undecryptable on
> device A after clearing site data — **even with the correct master password.**

The failure is silent and per-item: `decryptItem` throws, the caller catches,
and the UI renders a card titled "Decryption failed". This is **data loss**, not
merely the missing verifier the original framing led with. Adding a verifier
*alone* would make it look worse, not better — a user typing the correct
password on a new device would be told "incorrect password".

### The recovery material is already in the stored data

`encryptItem` writes `salt: sessionSaltB64` into **every** envelope
(`sessionVaultCrypto.js:265-270`), so each item carries, server-side, the salt
it was encrypted under. But `decryptItem` **ignores `parsed.salt`** and decrypts
with the module-level `sessionKey` derived from the *localStorage* salt
(`:305-315`).

Nothing is lost. It is unread.

---

## 2. Correction to the original framing (verified against the code)

The original plan's §4 posed "reconsider whether to fix v2 at all, or finish the
v3 migration" as an open, expensive either/or — "the two paths lead to very
different amounts of work". Scanning the code shows that framing is out of date
on both halves.

**The v3 migration is already ~90% complete.** Verified:

- `legacyVaultMigration.migrateLegacyUserToWrappedDEK` enrolls a user on
  `NOT_ENROLLED` and runs a full per-item rewrite (`legacyVaultMigration.js:250`).
- `migrateRemainingV2Items` runs an opportunistic sweep on **every** login once
  v3 is unlocked (`App.jsx:1428`), paginated, single-flight, with an
  `updated_at` optimistic-concurrency precondition.
- `decryptEnvelope` already falls back v2→v3 (`vaultEnvelope.js:24-35`).

The **only** code still writing v2 is:

- `vaultEnvelope.encryptEnvelope` (`vaultEnvelope.js:46-48`) — used by
  `VaultContext.addItem` (`:618`) and `VaultContext.updateItem` (`:703`).
- `App.handleSubmit` (`App.jsx:1178`) — the /vault add form, which calls
  `sessionVaultCrypto.encryptItem` directly rather than through the envelope
  helper.

So "finish the v3 migration" is not a large project. It is **two call sites**.

**But the two paths are complementary, not alternatives** — this is the load-
bearing observation, and it is why this PR does both:

- The sweep **decrypts with v2** (`legacyVaultMigration.js:150`). v2 decryption
  needs the device-local salt. So the sweep *cannot* migrate device A's items
  when run on device B. **Flipping the write path alone permanently strands
  every item already written on another device.**
- Conversely, salt-aware decryption alone leaves v2 as the live write path, so
  every new item keeps re-creating the problem.

Neither half fixes the bug on its own. Ordered together, they do.

### `App.jsx:1303-1305`'s comment is false

> "The legacy v2 session key above stays live so any items still encrypted under
> svc-gcm-1 keep decrypting; **new items go through v3.**"

New items do **not** go through v3. Both write paths above are v2. The comment
has been wrong since it was written. Corrected in this PR.

---

## 3. Decision (step-4 gate)

**Ship both, ordered — salt-aware v2 decrypt first, then flip the write path to
v3.** Confirmed with the repo owner before implementation, per the original
plan's "decide this before building step 1" instruction.

Dropped from scope: the standalone **verifier** (original step 3). Once decrypt
is salt-aware and writes are v3, a verifier's remaining job is to distinguish
"wrong password" from "unknown salt" — but there is no longer an unknown-salt
failure mode to confuse it with, and v3's `verifyMasterPassword`
(`sessionVaultCryptoV3.js:469`) already answers that question authoritatively
against a server-stored blob. Adding a second, weaker, device-local verifier
would be a strict downgrade. See §7.

---

## 4. Changes

### Step 1 — Make v2 decryption salt-aware

`frontend/src/services/sessionVaultCrypto.js`

- Retain the master password in module scope at
  `initSessionKeyFromPassword` time, alongside the existing `sessionKey` /
  `sessionSaltB64`. **Lifetime is unchanged in kind** — the module already holds
  a key derived from it for the whole session and already clears both in
  `clearSessionKey`; the password joins that same lifecycle and is cleared in
  the same place.

  **Security trade-off, stated explicitly** (raised in PR #480 review): unlike
  `sessionKey` (a derived, non-extractable `CryptoKey`), `sessionPassword` is
  *raw authentication material* held in a plain JS variable for as long as the
  session lasts. This is accepted, not accidental — it is what makes
  cross-device foreign-salt re-derivation possible at all (§ recovery
  material). The cleanup boundaries that bound its lifetime are: **logout**
  (`App.jsx`'s `handleLogout` calls `sessionVaultCrypto.clearSessionKey()`),
  **vault lock** (any caller of `clearSessionKey()`), and **user-switch**,
  which is just a second `initSessionKeyFromPassword` call — verified below
  that a re-init immediately discards the old password (Step 1's
  `sessionGeneration` guard makes this atomic against races too, see the new
  "Session-generation guard" subsection). No new cleanup path was added
  because none was missing: `clearSessionKey` already nulled every session
  variable that existed before this PR; `sessionPassword` was simply added to
  that same, already-correct list.
- Add `Map<saltB64, CryptoKey>` memoizing derived keys — **for foreign salts
  only**. An envelope whose salt is absent or equal to `sessionSaltB64` is
  answered directly from `sessionKey` and never touches this map; it is not
  seeded with the session salt at init. Derivation cost is therefore one
  session-key derivation at init, plus exactly one further derivation per
  *distinct foreign salt* subsequently encountered (memoized as an in-flight
  promise, so N items sharing one foreign salt still cost one derivation, not
  N). *(Corrected from an earlier draft of this section, which described the
  map as seeded with the session salt — CodeRabbit PR #480 review, round 1:
  the shipped code never does this; `keyForSalt`'s fast path returns
  `sessionKey` directly and only populates `foreignSaltKeys` on a genuine
  cache miss for a non-session salt.)*
- In `decryptItem`, when `parsed.salt` is present and differs from
  `sessionSaltB64`, resolve a key for *that* salt from the cache (deriving
  lazily via the existing `deriveDirectKey` on first encounter) and decrypt with
  it. Absent/equal salt keeps the current fast path exactly.
- `clearSessionKey` clears the password and the cache.

### Step 1b — Session-generation guard (round-1 review addition)

Not in the original plan; added in PR #480 review round 1 after CodeRabbit
correctly identified a race that Step 1's password retention made newly
possible: `initSessionKeyFromPassword`, `setupVaultPassword`, and
`unlockWithVaultPassword` each `await` a PBKDF2/Argon-class derivation
(~100 ms) before committing `sessionKey`/`sessionSaltB64`/`sessionPassword`.
If `clearSessionKey()` (logout) ran while one of those was still pending, the
stale call's continuation would commit anyway a moment later — **resurrecting
a session the user just logged out of**. The same unguarded-commit shape also
let an *older* call clobber a *newer* one on a fast account switch, whichever
happened to resolve last.

Fix: a single module-level `sessionGeneration` counter. `clearSessionKey`
increments it; each of the three functions above captures
`const generation = ++sessionGeneration` before its first await and only
commits session state if `generation === sessionGeneration` when the
derivation resolves — otherwise it throws
`'Vault session initialization was superseded by a newer request.'` instead of
committing. `unlockWithVaultPassword`'s check sits **after** its own
unwrap-failure `catch` (which throws `'Incorrect vault password.'`), so a
superseded-guard rejection can never be mislabeled as a wrong-password one.
`setupVaultPassword`'s `localStorage.setItem` (persisting the wrapped-DEK
record) stays **unguarded** — deliberately: the persisted record is valid
regardless of which in-memory commit wins, and a later `unlockWithVaultPassword`
call can still open it.

`keyForSalt` (the foreign-salt derivation inside `decryptItem`) is **not**
guarded the same way and does not need to be: it never writes module-level
session state, only returns a value to the one `decryptItem` call that is
already awaiting it. A stale return there is an ordinary "caller moved on"
situation, not a session-resurrection risk.

Tests: `sessionVaultCrypto.salt.test.js`, describe block
`"session-generation guard against stale async commits"` — one test stalls
`crypto.subtle.deriveKey` via a controllable mock, clears the session
mid-flight, and asserts the stale call rejects with `/superseded/i` and
`hasSessionKey()` stays `false`; a second stalls an *older* call, lets a
*newer* one complete normally, and asserts the newer session's own encrypted
item still decrypts after the stale older call finally resolves and rejects.

Deliberately **not** re-deriving per decrypt call: PBKDF2 at 310 000 iterations
is ~100 ms; a 200-item vault spanning three devices would otherwise add ~20 s to
a list render. The memo makes it three derivations total.

Wrapped-DEK (OAuth) path is untouched: `unlockWithVaultPassword` installs a DEK,
not a password-derived key, and has no password to memoize. Items written under
it carry that path's own salt and continue to decrypt via the session key.

### Step 2 — Route new writes through v3

`frontend/src/services/vaultEnvelope.js`

- `encryptEnvelope` prefers `sessionVaultCryptoV3.encryptItem` when
  `sessionVaultCryptoV3.hasSessionKey()`, falling back to v2 otherwise (OAuth
  sessions, v3 unlock failed, degraded mode from PR #478).
- The fallback matters: PR #478 established that a v3 desync leaves the vault
  *usable* via v2. Hard-failing writes when v3 is down would undo that.

`frontend/src/App.jsx`

- `handleSubmit` (`:1178`) goes through `encryptEnvelope` instead of calling
  `sessionVaultCrypto.encryptItem` directly — removing the second, divergent
  write path rather than teaching it the same trick.
- Its lock gate (`:1171`) must accept a v3-only session; today it checks
  `sessionVaultCrypto.hasSessionKey()` alone, which would wrongly show the
  vault-unlock prompt to a v3-ready user.
- Correct the false comment at `:1303-1305` (§2).
- **Round-1 review addition:** a *second*, separate `useEffect` (`:1137-1145`)
  auto-opens `VaultUnlockModal` whenever `isAuthenticated`/`user?.id`/
  `user?.email` change, and — before this fix — checked
  `sessionVaultCrypto.hasSessionKey()` alone, same as `handleSubmit` used to.
  CodeRabbit (PR #480 review, round 1) correctly flagged that fixing
  `handleSubmit`'s gate without fixing this parallel one leaves them
  inconsistent: a fully-usable v3-only session (v2 init failed or hasn't run
  this login, v3 succeeded) would save items fine via `handleSubmit`, yet this
  effect would still open — or leave open — the "your vault is locked" modal
  over it. Fixed with the identical OR-of-both-keys condition, so both gates
  agree on what "locked" means.

  **Deliberately not fixed in this PR:** the effect still does not *re-run* to
  auto-dismiss the modal if a key becomes available asynchronously after it
  already fired (its deps are React state/props, not the module-level
  `sessionKey`/`sessionDEK` variables, which are not reactive). That is a
  pre-existing timing gap in the effect, not something this PR's write-path
  change introduced, and closing it would mean either polling or converting
  session-key presence into React state — a materially larger, riskier change
  than "keep this effect's locked-check consistent with `handleSubmit`'s."
  Left as a known limitation; not tracked further here since it predates this
  plan's scope.

  **Test coverage note:** CodeRabbit also asked for a regression test
  asserting the modal doesn't stay open for a v3-only session. No test file
  for `App.jsx` exists anywhere in this codebase (verified — none of its
  effects, including this one, have ever had dedicated test coverage); adding
  the scaffolding needed for one (mocking `useAuth`, routing, `VaultUnlockModal`,
  etc.) to cover a single `useEffect` condition would be a disproportionately
  large addition for a one-line consistency fix, and out of step with "keep
  changes minimal." The two service-level test files already added exercise
  the actual OR-of-both-keys logic this fix uses (`vaultEnvelope.test.js`'s
  v3-preferred/v2-fallback tests share the same predicate shape). Not covered
  by an automated test; flagged here so it is not silently forgotten.

### Step 3 — Stop silent minting

`getOrCreateUserSalt` gains a caller-facing distinction between "first ever use"
(mint, correct) and "salt absent but this account has items" (do not silently
mint a salt guaranteed to mismatch). With step 1 in place this is no longer a
data-loss path — stranded items now decrypt via their own envelope salt — so
this reduces to a diagnostic signal rather than the recoverable-state UI the
original plan called for.

---

## 5. Tests

`frontend/src/services/__tests__/sessionVaultCrypto.salt.test.js` (new)

- **The portability regression:** an envelope carrying a *different* salt than
  the current session decrypts correctly.
- Same-salt envelopes still decrypt (no regression to the fast path).
- A genuinely wrong password still fails, for both the session salt and a
  foreign salt.
- Per-salt derivation is memoized — N items sharing a foreign salt derive once.
- `clearSessionKey` drops the cache and the retained password.
- Legacy/plaintext and malformed envelopes keep returning `_legacyPlaintext`.

`frontend/src/services/__tests__/vaultEnvelope.test.js` (extend)

- `encryptEnvelope` uses v3 when a v3 session key is present.
- Falls back to v2 when it is not.

`frontend/src/contexts/__tests__/` — the existing add/update harness already
mocks `encryptEnvelope`, so those tests stay valid unchanged; that is the point
of routing `App.handleSubmit` through the same helper.

**Round-1 review addition:** `sessionVaultCrypto.salt.test.js` also covers the
session-generation guard (§4, Step 1b) — one test stalls a pending
`initSessionKeyFromPassword` derivation, clears the session mid-flight, and
asserts the stale call rejects (`/superseded/i`) without resurrecting the
cleared session; a second asserts a newer call's session survives an older,
still-pending call resolving after it.

**Round-2 review addition:** three more tests in the same file.
- `setupVaultPassword`'s own localStorage-ordering bug (§4 Step 1b, round-2
  fix 1) — stalls a first call's `wrapKey`, lets a second (different-password)
  call complete and persist, then releases the stale first call and asserts
  `localStorage` still holds the *second* call's record, not the first's. This
  test is the direct regression check for the bug; it was confirmed to fail
  against the pre-fix ordering before the fix landed (the stale call's
  placeholder `wrapped` bytes were observed overwriting the real record), and
  passes now.
- Two tests for Step 3's minting log (§4 Step 3): a brand-new `userId` logs
  once via `console.info` matching `/minted a new device-local vault salt/i`;
  a second call for the same `userId` (salt already exists) does not log
  again.

**Mutation checks** (per the recurring lesson from PRs #454/#475 — a test that
passes against the broken code proves nothing). Each entry below is
independently reproducible: apply the described edit, run the named command,
confirm exactly the named test(s) fail (and nothing else), then revert.

1. **Foreign-salt decrypt.** In `sessionVaultCrypto.js`'s `decryptItem`, replace
   `const key = await keyForSalt(parsed.salt);` with the old unconditional
   `if (!sessionKey) throw new Error(...); const key = sessionKey;` (i.e. drop
   the `keyForSalt` call entirely).
   ```bash
   cd frontend && npx vitest run src/services/__tests__/sessionVaultCrypto.salt.test.js
   ```
   Expected failures (3): `decrypts an envelope written under a different
   (foreign) salt, given the correct password`, `derives a foreign salt key
   once and reuses it across concurrently-decrypted items`, `does not
   resurrect a stale cached foreign-salt key after clearSessionKey + re-init
   with a different password`. The other 9 tests in that file stay green
   (they don't exercise the foreign-salt path). Revert the edit; re-run to
   confirm all 12 pass again.

2. **v3-preferred writes.** In `vaultEnvelope.js`'s `encryptEnvelope`, replace
   the body with the old unconditional `return sessionVaultCrypto.encryptItem(data);`
   (drop the `sessionVaultCryptoV3.hasSessionKey()` branch).
   ```bash
   cd frontend && npx vitest run src/services/__tests__/vaultEnvelope.test.js
   ```
   Expected failure (1): `encryptEnvelope > prefers v3 when a v3 session key
   is present`. The `falls back to v2` test stays green (v2-always trivially
   satisfies "falls back to v2"). Revert; re-run to confirm all 7 pass again
   (the file also covers `decryptEnvelope`, untouched by this mutation).

3. **Session-generation guard.** In `sessionVaultCrypto.js`, delete the
   `const generation = ++sessionGeneration;` line and the following
   `if (generation !== sessionGeneration) { throw ...; }` block from
   `initSessionKeyFromPassword` (the other two guarded functions can be left
   alone — this one mutation is sufficient to demonstrate the check matters).
   ```bash
   cd frontend && npx vitest run src/services/__tests__/sessionVaultCrypto.salt.test.js -t "generation guard"
   ```
   Expected failures (2, both in describe block `session-generation guard
   against stale async commits`): `does not resurrect a session cleared while
   initSessionKeyFromPassword was still deriving`, `lets a newer
   initSessionKeyFromPassword call win when an older one is still pending`.
   Revert; re-run (without `-t`) to confirm all 12 pass again.

4. **`setupVaultPassword` persistence ordering (round-2 addition).** In
   `sessionVaultCrypto.js`, move the `localStorage.setItem(...)` call in
   `setupVaultPassword` back to *before* the `if (generation !== ...)` check
   (i.e. revert to the pre-round-2 ordering).
   ```bash
   cd frontend && npx vitest run src/services/__tests__/sessionVaultCrypto.salt.test.js -t "does not let a stale setupVaultPassword"
   ```
   Expected failure (1): `does not let a stale setupVaultPassword call
   overwrite a newer one's persisted record`. Revert; re-run (without `-t`)
   to confirm all 15 pass again.

All four were performed and confirmed during PR #480 development (round 1 and
round 2 review-fix passes); the commands above reproduce them exactly.

---

## 6. Verification

```bash
cd frontend && npx vitest run src/services/__tests__/sessionVaultCrypto.salt.test.js src/services/__tests__/vaultEnvelope.test.js src/contexts/__tests__/
```

Then ESLint on touched files, and the full frontend suite once at the end.

Backend is untouched — no migrations, no Django changes.

---

## 7. Out of scope

- **A standalone v2 verifier.** Superseded; see §3.
- **Retiring v2.** Still needed for OAuth sessions (no master password) and as
  the PR #478 degraded-mode fallback. This PR makes v2 read-portable and stops
  it taking new writes; removing it is a later step gated on the wrapped-DEK
  flow covering the OAuth path.
- **Server-side salt storage.** The envelope already carries the salt per item,
  which is strictly better than a per-user server salt — it survives salt
  rotation. No API change is needed and none is made.
- Anything in Plans A and B (shipped — see the table at the top).

---

## 8. Risk

Highest-risk of the three plans: it touches the live encryption path for every
vault item. Mitigations actually in force:

- Step 1 is **purely additive to the read path** — the unknown-salt branch only
  runs where today's code throws. No currently-working decrypt changes behaviour.
- Step 2's v2 fallback means a v3 outage degrades to today's behaviour rather
  than to a write failure.
- Both mutation checks above must be demonstrated failing before merge.
- Shipped alone, never alongside Plan A or B (both already merged regardless).

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
- Add `Map<saltB64, CryptoKey>` memoizing derived keys per salt. Seed it with
  the session salt at init.
- In `decryptItem`, when `parsed.salt` is present and differs from
  `sessionSaltB64`, resolve a key for *that* salt from the cache (deriving
  lazily via the existing `deriveDirectKey` on first encounter) and decrypt with
  it. Absent/equal salt keeps the current fast path exactly.
- `clearSessionKey` clears the password and the cache.

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

**Mutation checks** (per the recurring lesson from PRs #454/#475 — a test that
passes against the broken code proves nothing):

1. Restore `decryptItem`'s unconditional use of `sessionKey` → the foreign-salt
   test must fail.
2. Force `encryptEnvelope` back to v2-always → the v3-preference test must fail.

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

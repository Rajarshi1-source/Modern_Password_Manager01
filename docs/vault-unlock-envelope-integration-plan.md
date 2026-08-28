# Plan — Wire the two-slot envelope into `VaultUnlockModal` (§4.2 carry-over)

**Implemented in PR #489, then hardened across twelve review rounds
(§9–§20) — read all twelve before relying on §3's original design as the
literal shipped behavior. §11.5 in particular is a real data-corruption fix,
not a cosmetic one; §16.1, §18.1, and §20.2 extend it to the mutation and
display paths it originally missed (§18.1 is the one that reaches
`restoreBackup`, which can wipe the whole vault); §20.1 is a security
justification written in §12.2 that turned out to be wrong, and is worth
reading as a caution about scoping a threat model to "who is supposed to be
on this screen"; §13 records a bot misattribution caught before acting on
it; §19.6 names the failure mode that has produced most findings since round
9 — internal contradictions between two places stating the same fact — and
the rule for avoiding it.**

**§0 below is the PRE-IMPLEMENTATION baseline** — the verdict table records
what was true when this plan was written, which is why it still lists
`VaultUnlockModal` as "Not integrated". PR #489 is what changed that. Read
§9–§16 for the shipped state; do not read §0 as current status.

Deferred from PR #486 (`docs/privacy-features-gap-remediation-plan.md` §4.2,
§5 "Not delivered"). PR #486 shipped the backend and the service layer; the
main unlock modal was left on the single-password path because provisioning
the two-slot blob "deserves its own PR". This is that PR.

**Scope: one PR.** No dependency on the onion-transport work
(`docs/onion-sync-transport-phases-2-4-plan.md`); the two can land in either
order.

---

## 0. Verdict table — the PRE-IMPLEMENTATION baseline, verified by reading the code

| Piece | State | Evidence |
|---|---|---|
| Two-slot envelope format | **Complete and correct** | `frontend/src/services/hiddenVault/hiddenVaultEnvelope.js` — `encode`/`decode`, Argon2id per slot, fixed-size framing |
| `DuressSignal` model + endpoints | **Complete** | `password_manager/security/models/duress_models.py:741`; `duress/signal/register/`, `duress/signal/` |
| Client duress service | **Complete** | `frontend/src/services/duressSignalService.js` — `generateSignalToken`, `registerSignalToken`, `reportUnlock`, `reportUnlockForSlot` |
| A production caller for all of the above | **Exists, but only for stego images** | `frontend/src/Components/security/StegoVaultDashboard.jsx:228-269` (provision), `:371` (report) |
| `VaultUnlockModal` | **Not integrated** — single password, no slots, no duress | `frontend/src/Components/auth/VaultUnlockModal.jsx` (168 lines) |
| Legacy server-side compare scoped away from master passwords | **Done in #486** | `verify_password_or_duress` / `check_for_duress_code` docstrings |

So the gap is exactly one thing: **the envelope has no caller on the primary
unlock path.** Same shape as the gap #486 closed for `proxyVaultOperation` —
rails built, nothing riding them.

---

## 1. What `VaultUnlockModal` actually is (correcting a mis-scoping in §4.2)

§4.2 calls this "the main unlock modal". Read the file: it is **not** the
master-password login path. It is the **OAuth wrapped-DEK** modal.

```text
frontend/src/Components/auth/VaultUnlockModal.jsx:17-22
  mode = userId && sessionVaultCrypto.hasWrappedKey(userId) ? 'unlock' : 'setup'
```

It is rendered from `frontend/src/App.jsx:2053`, gated on
`isAuthenticated && showVaultUnlock` — an authenticated user with no in-memory
session key, typical of a social login that carries no master password.
Password-login users go through `sessionVaultCrypto.initSessionKeyFromPassword`
and never see this modal.

**Consequence for scope, stated up front:** integrating the envelope here gives
duress unlock to *OAuth / vault-password* users. Password-login users are a
second, larger surface (it touches `useAuth` and the login form) and are
explicitly **out of scope** — see §7. The #486 §6 acceptance criterion
("Duress password opens the decoy vault from the main unlock modal") is
satisfied for this modal; §7 records what remains so the checkbox is not read
as more than it is.

---

## 2. The constraint §5 worried about is smaller than it looked

PR `#486` §5 deferred this because it "needs the two-slot blob to be
provisioned at vault setup — a migration path for existing vaults". Verified
against the code, that migration is **device-local, not server-side**:

```text
frontend/src/services/sessionVaultCrypto.js:43-44
  const USER_SALT_STORAGE_KEY   = 'vaultKeySalt';
  const WRAPPED_DEK_STORAGE_KEY = 'vaultWrappedDEK';
```

`setupVaultPassword` writes `vaultWrappedDEK:<userId>` to **localStorage**;
`unlockWithVaultPassword` reads it back from there. Nothing about this record
lives on the server. So:

- There is **no server-side blob to migrate** — no model, no Django migration,
  no cross-device backfill.
- A user on a device with no wrapped key already lands in `setup` mode. That
  path provisions the envelope from scratch — free.
- A user on a device that *has* a wrapped key needs an **upgrade-on-unlock**
  step (§3.4). That is the entire migration.

This is a real reduction in scope versus what PR `#486` §5 assumed, and it is
why this fits in one PR.

---

## 3. Implementation

Modular-monolith placement: one new frontend service beside its peers
(`frontend/src/services/hiddenVault/`), a small additive API on
`sessionVaultCrypto`, and edits to two components. **No backend changes** —
`duress/signal/register/` and `duress/signal/` already do everything needed.

### 3.1 Slot payload format

Both slots carry the same shape so the JSON never betrays which slot is which
(and the envelope pads both to `slotPayloadLen(tier)` anyway, so lengths are
equal by construction):

```json
{ "v": "hv-slot-1", "dek": "<base64 32-byte raw DEK>", "salt": "<base64 16-byte>" }
```

The **decoy** slot additionally carries `"__duress_signal": "<44-char token>"`.
The real slot never does — the rule `StegoVaultDashboard.jsx` already follows,
and the one `reportUnlockForSlot` already depends on
(`duressSignalService.js:165-171`).

Carrying the raw DEK rather than a second wrapped-DEK record avoids stacking a
PBKDF2-310k KEK derivation on top of Argon2id for no security gain: the
envelope slot is already Argon2id + AES-GCM-256 with a per-slot domain tag
(`deriveSlotKey`, `hiddenVaultEnvelope.js:148`).

### 3.2 New service: `frontend/src/services/hiddenVault/unlockEnvelopeStore.js`

Owns storage and lifecycle of the per-user envelope. Storage key
`vaultUnlockEnvelope:<userId>` in localStorage, base64-encoded blob —
deliberately alongside `vaultWrappedDEK:<userId>`, because it is the same class
of device-local secret material and inherits the same threat model.

```text
export const hasEnvelope(userId): boolean
export const loadEnvelope(userId): Uint8Array | null
export const saveEnvelope(userId, blob: Uint8Array): void
export const clearEnvelope(userId): void

// Provision at setup: real slot only. The decoy slot gets a throwaway random
// key (encode() already does this — see below), so the blob is byte-wise
// indistinguishable from one that has a decoy configured.
export async function provision({ userId, vaultPassword, dekBytes, saltB64 }): Promise<void>

// Add or replace the decoy slot. Re-encodes the whole blob because the outer
// salt and both nonces must be fresh; requires BOTH passwords, since the real
// slot must be re-sealed and only the real password can open it first.
export async function setDecoySlot({ userId, vaultPassword, decoyPassword }): Promise<{ duressToken: string }>

// Try a password against both slots. Wraps decode() and unpacks the winning
// slot's JSON payload (parseSlotPayload) into its individual fields, rather
// than returning the raw payload object.
export async function open({ userId, password }): Promise<{ slotIndex, dekBytes, saltB64, duressToken }>
```

**Verified property this design leans on:** `encode()` gives an unpopulated slot
a *throwaway random key* rather than leaving it empty —

```text
hiddenVaultEnvelope.js:281-283
  async function keyFor(password, slotIndex) {
    if (password == null) return randomBytes(KEY_LEN); // throwaway
```

— and then encrypts a full-length framed plaintext under it. So slot 1 of a
no-decoy blob is real AES-GCM ciphertext of the correct length. An adversary
holding the blob cannot distinguish "no decoy configured" from "decoy
configured, I do not have the password". That is what makes §3.4's default
(envelope always provisioned, decoy optional) safe rather than a tell.

### 3.3 Additive API on `sessionVaultCrypto`

Today `unlockWithVaultPassword(vaultPassword, userId)` couples three things:
read localStorage → derive KEK → install DEK. The envelope path needs only the
third. Add one export; change nothing existing:

```js
/**
 * Install a raw 32-byte DEK as the session key. Used by the envelope unlock
 * path, where the DEK arrives already decrypted from a slot payload rather
 * than from a wrapped record.
 */
export const installRawDek = async (dekBytes, saltB64, userId) => { ... }
```

It must replicate the tail of `unlockWithVaultPassword` exactly — including the
`sessionGeneration` staleness check (`sessionVaultCrypto.js:326-329`), setting
`sessionSaltB64`, clearing `sessionPassword`, and `foreignSaltKeys.clear()`.
Skipping the generation check would reintroduce the write-race that round 2 of
PR `#486` fixed in `setupVaultPassword`.

### 3.4 `VaultUnlockModal` changes

Three modes instead of two; the third is invisible to the user.

**`setup`** (no wrapped key, no envelope):
1. Existing validation unchanged (≥12 chars, confirm match).
2. `sessionVaultCrypto.setupVaultPassword(password, userId)` — unchanged, so
   the legacy record still exists and `hasWrappedKey` stays truthful.
3. Export the freshly created DEK and call `unlockEnvelopeStore.provision(...)`.
   The DEK is `extractable: true` (`sessionVaultCrypto.js:246`), so this needs
   no change to key generation.
4. `duressSignalService.reportUnlock(getAccessToken(), null)` — noise, because
   §3.5 requires the report to fire on **every** unlock, including the first.

**`unlock` with an envelope present** (the new primary path):
1. `unlockEnvelopeStore.open({ userId, password })`.
2. On `WrongPasswordError` → the existing "Incorrect vault password." error.
   **The string must be identical for a wrong password and for every other
   failure from which a slot could be inferred.**
3. On success → `sessionVaultCrypto.installRawDek(dekBytes, saltB64, userId)`.
4. `duressSignalService.reportUnlockForSlot(getAccessToken(), slotIndex, { __duress_signal: duressToken })`
   — **fire-and-forget, not awaited**, exactly as `StegoVaultDashboard.jsx:371`
   does. Awaiting it would make a duress unlock measurably slower than a normal
   one wherever the token path and the noise path differ in server-side cost —
   the timing tell §3.5 exists to prevent.
5. `onUnlocked?.()` — unchanged, so `App.jsx`'s `vault:updated` dispatch still
   fires.

**`upgrade`** (wrapped key present, no envelope — the migration):
Runs inside the normal `unlock` submit, invisibly.
1. `sessionVaultCrypto.unlockWithVaultPassword(password, userId)` as today.
2. On success, export the now-live DEK and call
   `unlockEnvelopeStore.provision(...)`, then continue as `unlock` would.
3. If provisioning throws, **swallow it and proceed** — the user has
   successfully unlocked, and failing their login over an opportunistic upgrade
   is a worse outcome than retrying next time. Log once.

### 3.5 Indistinguishability rules (non-negotiable)

Mirrors `HeartbeatVerify.jsx`, which already refuses to branch its message on
the duress flag, and the discipline recorded in `duressSignalService.js`'s
module docstring.

1. **Same endpoint, same body size, every unlock.** `reportUnlock` already
   posts a 44-char base64 value in both cases, and the endpoint answers 204 for
   match, no-match, malformed and error alike (#486 §5).
2. **No UI branch.** Success text, spinner text, and modal-close timing are
   byte-identical for slot 0 and slot 1.
3. **No timing branch.** `decode()` already derives *both* slot keys and
   attempts *both* decryptions unconditionally
   (`hiddenVaultEnvelope.js:391-408`), so KDF cost does not depend on which slot
   wins. Do not "optimise" that by short-circuiting on first success — it would
   leak the slot through wall-clock time. Add a comment at the call site saying
   so, and one above the attempts loop in `hiddenVaultEnvelope.js` itself.
4. **No logging branch.** No `console.*` may mention slots or duress.

### 3.6 Where the decoy password is set

Not in `VaultUnlockModal`. Adding a "decoy password" field to the unlock modal
would advertise the feature to anyone who coerces the user into opening the
app. `StegoVaultDashboard.jsx:447` links to `/security/duress`, but that route
does not exist — a dead link, pre-dating this PR, for an unrelated (stego
image) decoy mechanism. Build a new, dedicated route instead:
**`/security/vault-duress`**, wired into `App.jsx`'s route table and the
sidebar (`Sidebar.jsx`, "Advanced Security" section, next to Dark Protocol) —
this is the canonical route; do not reuse or repoint the dead
`/security/duress` link:

1. User enters the current vault password plus a new decoy password.
2. `unlockEnvelopeStore.setDecoySlot(...)` generates the fresh decoy DEK
   internally and re-encodes the envelope — the caller never supplies one
   (see §15.6).
3. `registerSignalToken(getAccessToken(), duressToken)` — **after** the
   re-encoded blob is persisted, never before. Round 4 of #486 (§10.3) fixed
   exactly this ordering bug in `StegoVaultDashboard.onEmbed`: registering a
   token for a vault that then fails to save leaves a live alarm with nothing
   able to fire it.
4. Registration deactivates any previous signal server-side (#486 §8.3), so
   re-running this is idempotent from the user's point of view.

### 3.7 Performance — measure before shipping

`decode()` runs Argon2id **twice** at `time=3, mem=65536 KiB, par=1`
(`hiddenVaultEnvelope.js:32-34`). On a mid-range laptop that is roughly
0.2–0.5 s per slot; on a low-end phone browser it can exceed 1 s per slot. That
is a visible regression on a modal OAuth users hit every session.

Required in this PR: record measured p50/p95 on one desktop and one mobile
browser in the PR description. If p95 exceeds ~1.5 s total, move `decode()`
into a Web Worker **in this PR** rather than deferring it — a three-second
unlock is the kind of thing that gets a security feature switched off. Do
**not** lower the Argon2 parameters to hit the number; they are the entire
security margin of the decoy.

**Status: still outstanding — a sixth CodeRabbit review round correctly
flagged this checklist as unchecked, and a live measurement was attempted
and blocked, not skipped.** A standalone Vite entry importing
`hiddenVaultEnvelope.js` directly (bypassing the full app, since no backend
was available to authenticate through the real `VaultUnlockModal` flow) hit
a real, reproducible Vite dependency-resolution failure: `argon2-browser`
ships as a UMD bundle; this project's `vite.config.js` both lists it in
`optimizeDeps.include` (pre-bundle the bare specifier) AND aliases the bare
specifier to `argon2-browser/dist/argon2-bundled.min.js` (a different,
un-prebundled path) for a WASM-loading fix. For any module graph OUTSIDE
the app's main entry — which has presumably already resolved and cached
this correctly during normal dev-server startup — those two directives
resolve inconsistently and the alias target's CJS/UMD wrapper never gets
Vite's ESM interop applied, so `import argon2 from 'argon2-browser'`
resolves to a module with no `default` export and throws before any
Argon2id call runs. This is worth fixing in its own right before anyone
next attempts this measurement the same way: either drop the redundant
`optimizeDeps.include` entry (the alias alone should be sufficient) or add
`optimizeDeps.include: ['argon2-browser/dist/argon2-bundled.min.js']`
instead. **This blocker is specific to a standalone/isolated module entry,
not to the shipped app** — production and the normal dev server already
serve real users through this exact code path today, so it says nothing
about the correctness of what shipped, only about how to measure it in
isolation. The actual measurement — real Argon2id timing on real hardware,
through the real `VaultUnlockModal` UI with a running backend and an
authenticated session — remains genuinely undone and is not a number this
plan should guess at.

---

## 4. Tests

**Unit — `frontend/src/services/hiddenVault/__tests__/unlockEnvelopeStore.test.js` (new, vitest)**
- Real password → `slotIndex === 0` and the real DEK.
- Decoy password → `slotIndex === 1` and the decoy DEK plus `__duress_signal`.
- Wrong password → `WrongPasswordError`.
- `provision()` with no decoy: the blob is exactly `tierBytes(tier)` long, and
  `open()` never returns slot 1 for the real password or for an arbitrary
  test password — every attempt against the unconfigured slot rejects with
  `WrongPasswordError`, the identical error a wrong password against a
  *configured* decoy produces, never a different error class or a crash —
  the no-tell property from §3.2.
- `setDecoySlot()` preserves the real slot: after adding a decoy, the original
  vault password still returns slot 0 with an unchanged DEK.
- localStorage round-trip (base64 encode/decode) is lossless.

**Component — `frontend/src/Components/auth/__tests__/VaultUnlockModal.test.jsx` (new)**
- `setup` provisions an envelope and calls `reportUnlock` with `null`.
- `unlock` on slot 0 installs the DEK and calls `reportUnlockForSlot(_, 0, _)`.
- `unlock` on slot 1 installs the decoy DEK and calls
  `reportUnlockForSlot(_, 1, _)`.
- **Indistinguishability, scoped to `VaultUnlockModal` itself:** the
  component's OWN rendered output after a slot-0 unlock and after a slot-1
  unlock is identical — same success/error copy, same timing-relevant
  markup, no duress-conditional class name or attribute. Assert on the
  serialized container, not on hand-picked strings — a hand-picked assertion
  will not catch the next person who adds one. This claim stops at the
  modal's own DOM: it does NOT extend to what the app renders next. Since
  §20, every display surface (`VaultItemsSection` and `VaultDashboardRoute`,
  both via `useDisplaySafeItems`) renders an EMPTY vault during a decoy
  session rather than the real list — which removes the "every row fails to
  decrypt" tell that earlier rounds recorded here, but does NOT make the
  post-unlock view believable: an empty vault is still wrong for an account
  the coercer knows is not empty. That remaining gap is §7's product work
  and is out of scope here; do not read this bullet as claiming it is
  solved.
- **Upgrade path:** a user with `vaultWrappedDEK` and no envelope unlocks
  successfully *and* has an envelope afterwards.
- **Upgrade failure is non-fatal:** stub `provision` to throw; the unlock still
  succeeds and `onUnlocked` still fires.

**Contract — extend the existing "no plaintext on the wire" test**
- No request body on the unlock path contains the master or decoy password. The
  only outbound request is `POST /api/security/duress/signal/` carrying a single
  44-char base64 `signal` field.

**Backend — `password_manager/security/tests/`**
- Endpoint behaviour is already covered by #486's `DuressSignalAPITests`. Add
  one regression guard at the seam this PR creates: a report carrying a
  registered token creates a `DuressEvent` and triggers alarms; a report
  carrying noise creates neither. #486 tested the endpoint; this asserts the
  *client's* chosen token reaches it.

**e2e**
- Out of scope: there is one spec file (`e2e/dark_protocol.spec.js`) and no
  OAuth fixture. Recorded here rather than silently skipped.

---

## 5. Acceptance criteria

- [x] Vault password opens slot 0; decoy password opens slot 1; both install a
      working session DEK and the vault renders — `unlockEnvelopeStore.test.js`
      ("the real password opens slot 0 with the exact DEK it was given",
      "the decoy password opens slot 1 with a fresh DEK and a duress token")
      plus `VaultUnlockModal.test.jsx` ("slot 0 (real) installs the DEK...",
      "slot 1 (decoy) installs the decoy DEK...", both asserting
      `installRawDek` was called with the right DEK/salt AND that `onUnlocked`
      fired — the documented trigger (§3.4 step 5) for `App.jsx`'s
      `vault:updated` dispatch, i.e. the vault rendering.
- [x] No master or decoy password appears in any request body on the unlock
      path (contract test) — `duressSignalService.test.js`'s
      `reportUnlock` test asserts `Object.keys(body)` is exactly `['signal']`
      (no `password`/`master_password` key), and this is the ONLY network
      request the unlock path makes: `unlockEnvelopeStore.open()` and
      `sessionVaultCrypto.installRawDek()`/`unlockWithVaultPassword()` are
      pure local crypto/localStorage, no network calls of their own.
- [x] Slot-0 and slot-1 unlocks are indistinguishable, verified precisely —
      not by one test proving all of it, but by matching each guarantee to
      the test that actually covers it: **endpoint and request byte length**
      are `duressSignalService`'s own contract (fixed 44-char base64 for
      both a real token and noise, one hardcoded URL —
      `duressSignalService.test.js`), unrelated to which slot decoded;
      **rendered DOM and console output** are `VaultUnlockModal`'s own
      (`VaultUnlockModal.test.jsx`'s indistinguishability test, hardened in
      round 6 to also assert log-output equality, not just DOM). Explicitly
      NOT the vault dashboard rendered after unlock — see §7 and the
      duress-setup screen's own limitation notice for why that is a
      separate, unsolved problem.
- [x] A decoy unlock creates a `DuressEvent`; a normal unlock does not —
      combined coverage: `VaultUnlockModal.test.jsx` proves the client sends
      the real duress token for slot 1 and `null` for slot 0
      (`reportUnlockForSlot` assertions in both slot tests); #486's
      `test_duress_signal.py` (32 tests, still passing) proves the endpoint
      creates a `DuressEvent` for a matching signal and none for noise.
- [x] An existing OAuth user with a wrapped DEK and no envelope is upgraded
      transparently on their next unlock, and a failed upgrade does not block
      the unlock — `VaultUnlockModal.test.jsx` ("unlocks via the legacy path
      and transparently provisions an envelope with the same DEK", "a failed
      upgrade does not fail the unlock").
- [x] Slot 1 of a no-decoy blob is indistinguishable from a configured one —
      `unlockEnvelopeStore.test.js` ("produces a blob of exactly the fixed
      tier size", "a no-decoy blob rejects an arbitrary password with
      `WrongPasswordError`, not a crash" — see §4's no-tell test above).
- [ ] Measured unlock p50/p95 recorded in the PR description; a Web Worker
      landed in this PR if p95 > ~1.5 s. **Still genuinely outstanding** —
      see §3.7's own status note; kept unchecked deliberately, not an
      oversight.
- [x] Argon2 parameters unchanged from the `hiddenVaultEnvelope.js` defaults —
      verified directly: `DEFAULT_KDF_TIME = 3`, `DEFAULT_KDF_MEMORY_KIB =
      65536`, `DEFAULT_KDF_PARALLELISM = 1` in `hiddenVaultEnvelope.js` match
      §3.7's stated values exactly, and both `provision()` and
      `setDecoySlot()` use them as their unmodified defaults.

---

## 6. Risks

| Risk | Mitigation |
|---|---|
| Double Argon2id makes unlock feel broken on low-end devices | §3.7 — measure, Worker if needed, never weaken params |
| Losing OR corrupting `vaultUnlockEnvelope:<userId>` locks the user out | It never becomes the only copy: `setupVaultPassword`'s wrapped record is still written and `unlockWithVaultPassword` still works. For a user who ALREADY has that legacy wrapped record, a MISSING envelope always fell back to the legacy path (`upgrade` mode) — a user with neither record goes to `setup` instead, which provisions an envelope from scratch (§0's verdict table / §3.4). A PRESENT-but-corrupt envelope (bad base64, truncated write, `MalformedBlobError`) did NOT originally fall back — `hasEnvelope()` only checks for a value, not that it decodes. **Fixed in §9.1**: `runEnvelopeUnlockWithFallback()` now falls back to `upgrade` mode on any non-`WrongPasswordError` open failure, which also self-heals by re-provisioning a fresh envelope |
| A future contributor short-circuits `decode()` for speed | Comment at the call site and above the attempts loop, plus the DOM-equality test |
| Decoy DEK encrypts nothing, so the decoy vault looks empty and unconvincing | Out of scope here — populating a believable decoy is a product decision (§7). An empty decoy still beats no decoy, but UI copy must not claim it is convincing. **Also fixed in §10.3**: the setup screen's own copy previously claimed the opposite (an empty, indistinguishable decoy) directly contradicting its own limitation notice two paragraphs below — corrected to describe only what is actually true |
| Registering the signal token before the blob is saved | §3.6 step 3 ordering — the #486 §10.3 lesson (of the ORIGIN plan, `privacy-features-gap-remediation-plan.md` — not this plan's own §10). That ordering only prevents an orphaned token from a FAILED save; it does not by itself recover from registration failing AFTER a successful save. **Fixed in §9.2, then hardened in §12.2**: §9.2's in-memory retry did not survive a remount (reload, navigation) — recovery now re-derives the token on demand by re-opening the envelope with the decoy password, never holding it in state or storage, so it works regardless of how long ago the failure was |
| `installRawDek` drifts from `unlockWithVaultPassword`'s tail | Keep them adjacent in the file with a cross-reference comment; the generation-check assertion is part of the unit tests. **Extended in §10.1**: the drift risk was not hypothetical — `installRawDek`'s OWN generation bump ran too late to catch a race that started before it was even called, since its slow sibling (`unlockEnvelopeStore.open()`) lives in a different module and has no way to participate in the in-module bump-before/check-after pattern by itself |
| A user sets the decoy password equal to the real vault password | `VaultDuressSetup.jsx`'s form already rejected this client-side, but `unlockEnvelopeStore.setDecoySlot()` itself did not — any other caller could bypass it and silently create an inert decoy (both slots decrypt under the one shared password, and `decode()` always resolves ties to slot 0, so the "decoy" password would just open the real vault). **Fixed in §10.4**: rejected in the service layer too, before any decode/re-encode work |
| A decoy session's writes permanently corrupt a row in the real vault | The most serious risk found across all three review rounds. The decoy slot reuses the real slot's device salt (§3.2), so a v2 item written while a decoy DEK is installed is encrypted under that DEK but stamped with the real salt — `keyForSalt`'s matching-salt fast path later hands the REAL session's DEK to decrypt it, an unrecoverable AES-GCM failure. **Fixed in §11.5**: `sessionVaultCrypto.encryptItem` refuses to write for the lifetime of any session `installRawDek` marked as decoy (`isDecoySession()`); this is a write-time gate, not a salt change, because OAuth/envelope sessions have no password to re-derive a foreign-salt key from in the first place |
| A malformed-but-valid-base64 slot payload skips the corrupt-envelope fallback | `parseSlotPayload` used to accept any base64 `dek`; a wrong-length one only failed later, in `installRawDek`, outside the window §9.1's fallback tags as `envelopeUnusable`. **Fixed in §11.6**: length-checked inside `parseSlotPayload` itself, so the failure happens where the existing fallback already catches it |

---

## 7. Explicitly out of scope (and why)

1. **Password-login users.** They never see `VaultUnlockModal`; duress for them
   means changing `initSessionKeyFromPassword` and the login form. Larger
   surface, different failure modes, its own PR.
2. **Cross-device decoy.** The envelope is device-local because the wrapped DEK
   it sits beside already is. Making the decoy follow the user needs a
   server-side opaque blob — plausible via the `sessionVaultCryptoV3`
   server-wrapped-DEK machinery, but that is a storage design with its own
   migration, not a bolt-on.
3. **Populating a believable decoy vault.** Product work.
4. **Removing `verify_password_or_duress`.** #486 scoped it to short duress
   codes and documented the constraint; deleting it is separate.

---

## 8. Related

- `docs/privacy-features-gap-remediation-plan.md` §2, §4.2, §5 — origin
- `password_manager/hidden_vault/SPEC.md` — blob format and slot semantics
- `docs/adaptive-password-zk-remediation-plan.md` §1-2 — the ZK invariant
- `docs/onion-sync-transport-phases-2-4-plan.md` — the other #486 carry-over

---

## 9. Implementation status — PR #489 CodeRabbit review fixes (2026-08-25)

§3 above describes the design as originally written. Two gaps CodeRabbit
found in the actual PR #489 diff were real (verified against the code, not
taken on the bot's word) and are now fixed. Recorded here so this plan stays
the accurate description of what shipped, not just what was drafted.

### 9.1 §3.4 `unlock` mode had no fallback for a corrupt (not just missing) envelope

`hasEnvelope(userId)` (`unlockEnvelopeStore.js`) only checks that
`localStorage` HAS a value for the key — it never attempts to decode it. §6's
risk table already covered a MISSING envelope (falls back to `upgrade` mode,
by construction, since `internalMode` is only `'envelope'` when
`hasEnvelope()` is true). It did not cover a PRESENT but corrupt one: a
truncated `localStorage` write, or any other bit-level corruption, still
makes `hasEnvelope()` return `true`, permanently selecting `internalMode:
'envelope'` — and then `unlockEnvelopeStore.open()` throws something that is
NOT `WrongPasswordError` (a raw `DOMException` from `atob()` on invalid
base64, or `MalformedBlobError` from a bad magic/version/tier), which
`VaultUnlockModal.jsx` had no branch for. The user was stuck seeing a
confusing technical error message with no way back into a vault the legacy
wrapped-DEK record could still open.

**Fix:** `VaultUnlockModal.jsx` adds `runEnvelopeUnlockWithFallback()`. On any
`open()` failure other than `WrongPasswordError`, if
`sessionVaultCrypto.hasWrappedKey(userId)` is true, it runs `runUpgrade()`
instead of surfacing the raw error — which also re-provisions a fresh
envelope on success, self-healing the corruption rather than just routing
around it once. A genuine `WrongPasswordError` (the envelope decoded fine;
neither slot's password matched) is explicitly excluded from the fallback —
that must stay a normal retry, not a route into the legacy path. 4 new tests
in `VaultUnlockModal.test.jsx` cover invalid base64, `MalformedBlobError`,
the no-fallback-on-wrong-password case, and the no-wrapped-key dead end.

### 9.2 §3.6 decoy setup had no recovery when registration failed AFTER a successful save

§3.6 step 3's ordering (save the envelope, register the token only after)
correctly prevents orphaning a token when the SAVE fails. It does not, by
itself, handle the token being orphaned when the SAVE succeeds and the
SUBSEQUENT `registerSignalToken()` call fails (a transient network error,
the server being down). In that case the decoy password was already live —
the envelope was saved — but the alarm behind it was never registered
server-side, so a real decoy unlock under duress would silently fail to
raise it. The user saw a generic setup-failed error with no indication that
part of the operation had actually already taken effect. A naive "just try
again" retry made it worse: resubmitting calls `setDecoySlot()` again, which
mints an entirely new random token via `generateSignalToken()`, permanently
orphaning the first one rather than recovering it.

**Fix:** `VaultDuressSetup.jsx` extracts `finishRegistration(token)` and adds
`pendingDuressToken` state. On a registration failure, the exact token
`setDecoySlot()` returned is retained (not discarded), the error message
says explicitly that the alarm is not yet active, and a "Finish registration"
button appears that calls `registerSignalToken` again with that SAME
token — never re-running `setDecoySlot`. New test file
`VaultDuressSetup.test.jsx` (5 tests; none existed before this fix) covers
the full success path, the registration-failure-retains-token path, retry
success, a failed retry staying retriable, and the wrong-password path not
touching any of this.

### 9.3 Eight unrelated doc-accuracy fixes, same review round

The same CodeRabbit run also found 8 issues in
`docs/onion-sync-transport-phases-2-4-plan.md` (§4.1 Phases 2-4, still
unimplemented). Those are corrected directly in that document, not
duplicated here — see its own text for the SocksPort/control-port/exit-path/
electron-builder-macro/TOR_PROXY-allowlist/getCapabilities-sequencing fixes.

---

## 10. Implementation status — second CodeRabbit review round (2026-08-25)

A second `@coderabbitai full review` on the same PR (after §9's fixes were
pushed) found 4 more issues — one of them the most serious found on this PR
so far. Verified against current code before fixing, same discipline as §9.

### 10.1 A session change during `unlockEnvelopeStore.open()` could resurrect a stale session

`open()` runs two Argon2id derivations before resolving — §3.7 already notes
this can take over a second combined. `runEnvelopeUnlock()` then called
`sessionVaultCrypto.installRawDek(dekBytes, saltB64, userId)` with no
generation token. `installRawDek` bumped `sessionGeneration` **itself**,
*after* `open()` had already fully resolved — which means it had no way to
know whether a logout (`clearSessionKey()`) or a newer unlock had already
moved the session on *during* the window `open()` was pending. Every other
session-establishing function in `sessionVaultCrypto.js`
(`initSessionKeyFromPassword`, `setupVaultPassword`, `unlockWithVaultPassword`)
avoids exactly this by capturing `generation = ++sessionGeneration` BEFORE
its OWN slow step — but that pattern only works when the slow step is
inside the same function/module. `unlockEnvelopeStore.open()` is not; it
lives in a different module entirely, so `installRawDek` bumping its own
counter at the point it happens to be *called* — rather than at the point
the caller's slow work *started* — left a real gap: a stale `open()` result
could resolve after a genuine logout and still get installed as the live
session, with `onUnlocked?.()` firing on top of it.

**Fix:** `sessionVaultCrypto.js` adds `reserveSessionGeneration()`, an
exported one-liner (`() => ++sessionGeneration`) callers use to capture a
token BEFORE their own slow out-of-module step. `installRawDek` gains an
optional 4th parameter, `expectedGeneration`; when supplied, it is checked
against the live counter before any work happens, closing the gap the
internal-only bump could not. `VaultUnlockModal.jsx`'s `runEnvelopeUnlock`
now calls `reserveSessionGeneration()` immediately, before `await
unlockEnvelopeStore.open(...)`, and passes the token through.

This interacted with §9.1's fallback logic too: a stale-generation error
from `installRawDek` is NOT an envelope-corruption error (the envelope
decoded fine — the problem is purely session timing), so it must never
trigger `runEnvelopeUnlockWithFallback`'s legacy-path fallback. Running
`runUpgrade()` on top of an already-superseded session would just install a
SECOND, equally-discarded session rather than correctly abandoning the
attempt. The fallback logic changed from a fragile string comparison
(`err.message === 'Incorrect vault password.'`) to an explicit
`err.envelopeUnusable` tag set only on failures from `open()` itself, never
on failures from `installRawDek` — so the two failure classes can never be
confused regardless of what either error's message text happens to say.

2 new tests in `VaultUnlockModal.test.jsx`: a superseded-session error
propagates without triggering the fallback (asserting
`unlockWithVaultPassword` and `reportUnlockForSlot` are both never called),
and the generation token is reserved before `open()` is called, not after.

### 10.2 A decoy password equal to the real vault password silently makes the decoy inert

`hiddenVaultEnvelope`'s `deriveSlotKey` bakes the slot index into the salt
(a domain tag), so the same password string normally derives two DIFFERENT
keys for slot 0 vs slot 1 — that domain separation is precisely what makes
the real and decoy passwords independent. But if the two password STRINGS
are also textually identical, `decode()` derives k0 and k1 from that ONE
shared input, and BOTH slots decrypt successfully. `decode()`'s attempt loop
resolves ties to the FIRST match — slot 0, the real vault (kept
constant-time on purpose, see the loop's own comment) — so a user who
configured "a decoy password" that happened to equal their real one would
have it silently open the REAL vault, every time, with no alarm, and no
indication anything was wrong. `VaultDuressSetup.jsx`'s form already
rejected `decoyPassword === vaultPassword` client-side, but
`unlockEnvelopeStore.setDecoySlot()` — the actual service function — did
not, so any other caller (a future UI, a script, a test) could bypass the
one place this was enforced.

**Fix:** `setDecoySlot()` now rejects `decoyPassword === vaultPassword`
itself, before any decode or re-encode work, mirroring the "enforce in the
service layer, not just the form" discipline `duressSignalService.js`
already follows elsewhere in this codebase. New regression test in
`unlockEnvelopeStore.test.js` asserts both the rejection and that the
stored envelope is byte-unchanged afterward.

### 10.3 The decoy-setup screen's own intro copy contradicted its own limitation notice two paragraphs later

`VaultDuressSetup.jsx` claimed a decoy unlock "opens a separate, empty decoy
vault" and that "the app behaves identically either way, so there is
nothing on screen to give it away" — while the `noticeStyle` box directly
below it correctly stated the actual, verified behavior: a decoy unlock
shows the real vault's item list with each entry failing to decrypt, not an
empty or curated one (see the known limitation already recorded in §7 of
THIS plan and its own risk-table row above). The two paragraphs flatly
disagreed with each other. Fixed by rewriting the intro to only claim what
is actually true and tested — the unlock REQUEST is indistinguishable (same
endpoint and byte length: `duressSignalService.test.js`'s own contract
tests; same rendered output and console output: `VaultUnlockModal.test.jsx`'s
indistinguishability test, §9.1) — while pointing the reader at the
limitation notice for what appears on screen afterward, rather than
asserting something the very next paragraph disproves. No test added at the
time of THIS fix — it was a copy-only change and CodeRabbit's own finding
did not ask for coverage here, unlike the other
three.

### 10.4 `docs/onion-sync-transport-phases-2-4-plan.md`: A.5's own fix from §9.3 had introduced a NEW, worse bug

The prior round's A.5 fix (§9.3, "getCapabilities stays on the clearnet
service, always") solved the chicken-and-egg problem it targeted but broke
something else in the process: `isOnionSyncAvailable()` gates on
`vault_proxy.available`, which the server computes as `anonymity_active AND
request_is_onion_ingress` — true only when THAT SPECIFIC request arrived
over the onion listener. Once `getCapabilities` always goes out over
clearnet (§9.3's own fix), `request_is_onion_ingress` for that call is
structurally always false, so `vault_proxy.available` is always false, so
desktop would never attempt the onion path at all — Phase 2 would ship a
sidecar nothing ever uses. Root cause: `vault_proxy.available` is the right
gate ONLY when the capabilities call and the eventual data call are
guaranteed to travel the same transport, which is true for Phase 1 (a
Tor-Browser user's own page load is what makes the capabilities call arrive
over onion) and false for any client that is a separate process making its
own per-call transport decision — desktop AND mobile alike.

Fixed directly in that document (still doc-only, Phase 2-4 remains
unimplemented): `isOnionSyncAvailable()` now branches on whether a
non-web transport is selected for the current platform. When one is,
it checks `anonymity.available && Boolean(anonymity.onion_address)` — a
deployment-level signal that does not require this particular clearnet
request to have arrived over onion — with the real per-request
verification happening where it actually can, at the `proxyVaultOperation`
call itself. When none is (plain web), the original `vault_proxy.available`
check is unchanged. B.3 (mobile) point 1 updated with a cross-reference:
porting the PRE-this-fix web gate to mobile would have carried the same bug
forward, since mobile has the identical separate-process shape. See that
document's own A.5 and B.3 for the full text.

### 10.5 `docs/onion-sync-transport-phases-2-4-plan.md`: neither of B.3's proposed SOCKS5 libraries actually provides HTTP-over-SOCKS5

A separate, unrelated finding in the same document: B.3 point 5 offered
NetCipher's `StrongOkHttpClientBuilder` or `react-native-tcp-socket` as
alternatives for Android SOCKS5 routing. Neither works alone — verified
against each project's own documentation, not assumed from the bot's
restatement: NetCipher's builder hardcodes `supportsSocksProxy()` to
`false` (a limitation of NetCipher's own convenience wrapper, not of OkHttp
itself), and `react-native-tcp-socket` is a raw TCP/TLS socket library with
no HTTP client on top of it. Fixed directly in that document: the
corrected approach bypasses NetCipher's builder and uses OkHttp's native
`java.net.Proxy` SOCKS support directly (`.proxy(new Proxy(Proxy.Type.SOCKS,
...))`) behind a small custom native module — a real, complete stack, not
two incomplete ones presented as alternatives.

### 10.6 `docs/onion-sync-transport-phases-2-4-plan.md`: PR C's unlinkability claim contradicted its own qualification two sections later

§C.2 point 5 already said correctly that the server can still correlate
issuance batch size, redemption timing, and sync payload size. §C.5's
acceptance criterion then asserted, unqualified, "the server cannot link a
redemption to an issuance" — the two statements do not agree. Fixed by
bounding both to the same explicit claim: cryptographic unlinkability
under the stated threat model, given the listed observable metadata — never
an absolute "cannot be linked." Applies equally to any future UI copy for
this feature: the Phase 1 discipline of never claiming more than the
architecture backs (see `onionSyncService.js`'s own docstring) extends to
this primitive too.

---

## 11. Implementation status — third CodeRabbit review round (2026-08-25)

A third `@coderabbitai full review` found 7 more issues. Verified against
current code before fixing. One of these (11.5) is a genuine security-severity
fix — permanent data corruption of the real vault, not merely a UX gap.

### 11.1 `docs/onion-sync-transport-phases-2-4-plan.md`: the onion origin was specified as `https://`, but the onion listener is plaintext

`backend-onion` in `docker-compose.yml` runs plain `daphne -b 0.0.0.0 -p 8443
...` — no `-e ssl:...`, no certificate. An `https://<addr>.onion` request
would fail its TLS handshake before reaching the app. Fixed to `http://`,
with an explanation of why this is correct rather than a workaround: Tor's
own onion-service circuit already provides end-to-end encryption and the
`.onion` address is itself self-authenticating, so plaintext HTTP over a
genuine onion circuit is the normal pattern for hidden services — layering
HTTPS on top would need an explicit, separately-tested TLS terminator to
mean anything, not just a changed URL scheme.

### 11.2 `docs/privacy-features-gap-remediation-plan.md`: the ORIGIN plan's own Phase 2/3 summary still described the pre-hardening design

Two sentences in the origin plan (written before the detailed carry-over
plans existed) directly contradicted the later, reviewed design:
Phase 2 said "expose a SOCKS5 proxy to the renderer" — the detailed plan's
A.4 explicitly rejects this ("The renderer must not gain network
privileges. Keep the fetch in the main process.") for the same reason a
compromised renderer with raw SOCKS5 access could reach anything on the
circuit, not just `vault_sync`. Phase 3 said "iOS via an embedded Tor
library" — the detailed plan's B.2 defers iOS entirely (no Orbot
equivalent, App Store review risk). Both fixed with a superseded-by note
pointing at the detailed plan, rather than silently rewriting history.

### 11.3 `docs/vault-unlock-envelope-integration-plan.md` (this file): markdownlint MD040/MD018, plus a self-inflicted MD022 defect found while fixing them

The specific findings (missing fence languages at 4 blocks; bare `#486` at
the start of two wrapped lines, read by MD018 as a malformed heading) were
fixed as asked. While verifying with `markdownlint-cli2` directly rather
than trusting the fix by inspection alone, a separate, unflagged defect
turned up: seven section headings from §9 and this file's own §10 had been
authored as two adjacent `###` lines instead of one heading line-wrapped as
plain text (e.g. `### 9.1 ... (not just missing)` immediately followed by
`### envelope` as a SEPARATE heading) — a real authoring mistake from
writing those sections in the two previous rounds, not something CodeRabbit
flagged this time. Left in place, every markdown heading-extraction tool
(including this repository's own table-of-contents tooling, if it has any)
would show these as broken, truncated entries. Joined all seven into single
heading lines.

### 11.4 `docs/vault-unlock-envelope-integration-plan.md` §3.6: the plan described a route that was never the one actually built

§3.6 said the decoy-password settings screen belongs at "the existing
duress settings area (route `/security/duress`, which
`StegoVaultDashboard.jsx:447` already links to)". Verified against
`App.jsx` and `Sidebar.jsx`: the ACTUAL implementation is
`/security/vault-duress`, a new route built from scratch — because, as
recorded already in this repo's own implementation history,
`/security/duress` is a dead link (pre-dating this PR, for an unrelated
stego-image decoy mechanism) with no page behind it. The plan text had
simply never been updated to match what was actually built. Fixed to
describe the real route and state plainly that `/security/duress` is a
dead link, not something to repoint.

### 11.5 `frontend/src/services/hiddenVault/unlockEnvelopeStore.js`: a decoy-session write permanently corrupts a row in the REAL vault — the most serious finding across all three rounds

`setDecoySlot()` stamps the decoy slot with the SAME device salt as the
real slot (`realSaltB64` — reused deliberately, per that code's own
comment, since there was no reason at the time to think it needed to
differ). Traced forward, not just at the point CodeRabbit flagged: when a
decoy session is active (`installRawDek` installed the decoy DEK), the
existing v2 write path (`VaultContext`'s `addItem`/`updateItem`, both
routed through `encryptEnvelope` → `sessionVaultCrypto.encryptItem` for any
OAuth/envelope session, since those never carry a v3 key) has no gate
beyond "is there a session key" — so a new item added during a decoy
session gets encrypted under the DECOY DEK while `encryptItem` stamps it
with `sessionSaltB64`, which is the REAL slot's salt. When the REAL session
later encounters that item, `keyForSalt`'s matching-salt fast path hands it
the REAL DEK — an AES-GCM authentication failure, because the item was
never encrypted with that key. The item becomes **permanently unreadable**,
a garbage row injected into the ONE shared, server-side item list, with no
way to recover it (the decoy DEK that could decrypt it is never persisted
anywhere outside that already-superseded decoy envelope).

This is materially worse than the already-disclosed, accepted limitation
(§7, and the duress-setup screen's own notice) that a decoy unlock shows
the real item list with existing entries failing to decrypt — that
limitation is about *visibility*, this bug is about *silent, irreversible
data loss* triggered by ordinary use of the app while in a decoy session,
whether by the coerced user or a coercer probing what the app can do.
Changing the decoy slot's salt alone would NOT have fixed it: OAuth/envelope
sessions never set `sessionPassword` (see that field's own comment), so
`keyForSalt` already falls through to `sessionKey` for ANY foreign salt in
this session shape — the failure is structural, not a salt-choice bug, and
the actual fix has to stop the write, not relabel it.

**Fix:** `sessionVaultCrypto.js` adds a `sessionIsDecoy` flag, set by a new
optional 5th parameter on `installRawDek(dekBytes, saltB64, userId,
expectedGeneration, isDecoy)`, exported as `isDecoySession()`, and reset by
`clearSessionKey()`. `encryptItem()` refuses to write — throwing before any
crypto runs — whenever `sessionIsDecoy` is true. `VaultUnlockModal.jsx`'s
`runEnvelopeUnlock` passes `slotIndex !== 0` as `isDecoy` when installing
the DEK, so this engages automatically the moment a decoy unlock succeeds,
with no separate wiring needed elsewhere. New test file
`sessionVaultCrypto.decoySession.test.js` (8 tests, real WebCrypto/
localStorage, no mocks) covers the flag's lifecycle, the write refusal, that
a real session is unaffected, and — using real encrypt/decrypt round trips
rather than just asserting the throw — that the salt collision this fix
prevents is a genuine, reproducible corruption, not a hypothetical one.

**Deliberately not attempted:** giving reads a friendlier "you're in a
decoy session" indicator, or making the write-refusal message
indistinguishable from an unrelated save failure. Both are product/UX
decisions belonging with the "believable decoy contents" work §7 already
defers; this fix's scope is stopping the corruption, not polishing what a
decoy session feels like to use.

### 11.6 `frontend/src/services/hiddenVault/unlockEnvelopeStore.js`: `parseSlotPayload` didn't validate the decoded DEK's length

A payload whose `dek` field was valid base64 but decoded to something other
than 32 bytes passed `parseSlotPayload` unchanged, and only failed later, in
`sessionVaultCrypto.installRawDek`'s own length guard — which runs AFTER
`unlockEnvelopeStore.open()` has already returned successfully.
`VaultUnlockModal.jsx`'s `runEnvelopeUnlock` only tags failures thrown
*from* `open()` itself as `envelopeUnusable` (§10.1's fix), so this failure
silently skipped the legacy wrapped-DEK fallback and left the user stuck,
despite this being exactly the "stored envelope is corrupt" case that
fallback exists to handle. Fixed: `parseSlotPayload` now checks
`dekBytes.byteLength === 32` itself and throws `MalformedSlotPayloadError`
for anything else, so the failure happens inside `open()`'s call stack
where the existing fallback logic already catches it — no change needed to
`VaultUnlockModal.jsx` at all. New regression test hand-crafts a payload
with a 16-byte `dek` via `encode()`/`jsonToBytes()` directly (bypassing
`provision()`'s own input guard on purpose) and asserts `open()` rejects
with `MalformedSlotPayloadError`.

### 11.7 The DOM-indistinguishability claim (§3.5, §5) was broader than what is actually true or tested

"Rendered DOM after a slot-0 unlock and after a slot-1 unlock is identical"
reads as an app-wide claim, but it is only true — and only tested — for
`VaultUnlockModal`'s OWN rendered output. The vault dashboard the app
renders next is NOT identical between the two cases (§7's own disclosed
limitation: a decoy session shows the real item list with each entry
failing to decrypt). Narrowed both the test-guidance bullet and the
acceptance criterion to explicitly scope the claim to `VaultUnlockModal`
itself and cross-reference the limitation for everything downstream of it,
so a future reader cannot mistake "the modal looks the same" for "the app
looks the same."

---

## 12. Implementation status — fourth CodeRabbit review round (2026-08-25/26)

A fourth `@coderabbitai full review` found 2 more issues. Both verified
against current code before fixing.

### 12.1 `docs/onion-sync-transport-phases-2-4-plan.md` §9 "Cross-cutting rules" still stated the blanket rule §10.4 had already corrected

§10.4 (round 2) fixed A.5's design to gate desktop/mobile availability on
`anonymity.available && onion_address` rather than `vault_proxy.available`
— but the summary in §9 ("Cross-cutting rules for all three PRs"), a
separate section restating the same fact for quick reference, was never
updated to match. It still said, unqualified, "Gate on
`vault_proxy.available`, never on `anonymity.available`" — exactly the
blanket rule that would make desktop/mobile's onion transport never engage,
which §10.4 already established and fixed IN A.5 itself. A reader who only
skimmed §9 rather than the detailed sections would rebuild the broken
version. Fixed by making §9 point 3 platform-specific, matching A.5's
actual design, with a cross-reference rather than a second copy of the
full argument.

**Lesson applied from memory ([[feedback-verify-bot-review-findings]]):**
this is the SAME class of miss as §10.4 itself, one level up — fixing a
design section but not the summary restating it. When a fact is stated in
more than one place in the same document, fixing it in one place requires
searching the whole document for every other restatement, not just the
place review flagged.

### 12.2 `frontend/src/Components/security/VaultDuressSetup.jsx`: the pending-registration retry did not survive a remount

Round 2 (§9.2) fixed the immediate case — a registration failure right
after `setDecoySlot()` succeeds — by holding the failed token in
`pendingDuressToken` React state so a "Finish registration" button could
retry with the exact same token. CodeRabbit correctly identified what that
fix did not cover: if the user reloaded the page, navigated away, or the
tab was closed before retrying, `pendingDuressToken` was gone. The decoy
slot on disk still held the unregistered token — nothing was lost at the
data layer — but the UI had no way back to it short of reconfiguring the
decoy slot from scratch (which mints a brand-new token via
`generateSignalToken()` and orphans the first one, the exact failure mode
§9.2 exists to prevent). The bot's own suggested remedy explicitly ruled
out storing the token as plaintext device state, which rules out simply
persisting `pendingDuressToken` to `localStorage`.

**Fix:** replaced the state-held retry with a standing "Recover
unregistered alarm" form, always present on the page (not conditionally
rendered on failed-attempt state), that re-derives the token on demand:
the user re-enters their decoy password, `unlockEnvelopeStore.open()`
re-opens the existing envelope with it — the same call a real decoy unlock
makes — and the returned `duressToken` is registered immediately. Nothing
about this depends on component state surviving anything; it re-reads the
token from the one place it durably lives, the envelope itself, every
time it runs. `pendingDuressToken` state, `handleRetryRegistration`, and
the conditionally-rendered "Finish registration" button are all removed —
this is a strictly simpler mechanism than what it replaces, not an
additive one, and it never holds the raw token in memory for longer than
the single `await` before registering it.

Rewrote `VaultDuressSetup.test.jsx` (8 tests) to match: the recovery form
is present unconditionally (not gated on a prior failure), recovery
re-opens the envelope rather than reusing retained state, a fresh
component instance with zero prior render history can still recover
(the direct test of "survives a remount"), and two new distinct error
paths — a wrong decoy password, and a password that happens to open the
real slot instead (deliberately explicit here, unlike `VaultUnlockModal`'s
unlock path, because this settings screen already presupposes the user
knows about and is managing the duress feature; telling them which slot
they opened is not a signal that helps a coercer on a screen a coercer
would have no reason to be shown in the first place).

---

## 13. Implementation status — fifth CodeRabbit review round (2026-08-26)

A fifth `@coderabbitai full review` found 6 issues, none in this file's own
content — all 6 are corrections to `docs/onion-sync-transport-phases-2-4-plan.md`
(still fully unimplemented, so zero code-regression risk). Recorded here
too, briefly, so the full review history for PR #489 stays in one place
rather than split silently across documents.

**One of the six is itself a verification catch worth recording explicitly:**
two of the bot's comments were anchored — by GitHub's own line numbers — on
lines 530–533 and 546–553 of THIS file, but their body text discussed
anonymous-credential design, `clearnet_ingress_refused`, and
`VAULT_OPERATION_ROUTES` route-scoping — none of which appears anywhere in
this document (`grep` for any of those terms in this file returns nothing).
That content genuinely exists, but in the OTHER carry-over plan's §C.3/§C.4
(PR C, anonymous credentials). CodeRabbit's own diagnostic scripts (visible
in its review comments) had searched both files while investigating, and
the two findings landed misattributed to this file's line numbers instead
of their actual location. Applying the fix here — inserting anonymous-
credential content into the middle of THIS file's unrelated §10.2/§10.3 —
would have corrupted this document for no reason. Verified the substance of
both findings was still real and valid, then applied them at their actual
location instead. This is precisely the discipline
[[feedback-verify-bot-review-findings]] already asks for, extended one step
further: verify not just WHETHER a finding is correct, but WHERE it actually
applies, before touching anything.

The four genuinely-file-correct findings, and the two redirected ones, all
fixed directly in `docs/onion-sync-transport-phases-2-4-plan.md`:

1. **A.4's `TOR_PROXY` handler needed an explicit payload-shape constraint,
   not just an operation allowlist.** `operation === 'vault_sync'`
   legitimately passes the existing allowlist, but nothing previously said
   the `payload` itself must be rejected if it carries a destination-like
   field (`url`, `host`, `proxy`, `origin`). Without that, a compromised
   renderer could ride the allowed channel and smuggle a destination
   override through the payload instead of through `operation`. Fixed:
   payload is sync data only, validated before dispatch, with a test for a
   payload carrying a clearnet-looking `url` field.
2. **A.5's fix only checked the DEPLOYMENT's Tor daemon, never THIS
   device's own local sidecar.** `anonymity.available && onion_address`
   tells you the server has Tor up; it says nothing about whether `torSidecar`
   on this machine has actually finished bootstrapping (or has crashed).
   Gating on the deployment fact alone would report "available" while the
   local SOCKS5 listener isn't actually listening yet, and
   `proxyVaultOperation` would fail with a raw connection error instead of a
   clean "unavailable." Fixed: `isOnionSyncAvailable()` now requires BOTH
   the deployment fact AND `torSidecar.getStatus()` reporting ready, with
   tests for the bootstrapping and stopped/crashed states specifically.
3. **A.7's (and B.3's mobile equivalent) integration-test guidance still
   used `vault_proxy.available === true` as the desktop/mobile success
   signal** — exactly the field A.5's own fix established can never be true
   for either platform's clearnet-issued capabilities call. Fixed to assert
   at the request level instead: onion-routed `vault_sync` succeeds,
   clearnet-routed `vault_sync` is refused with `clearnet_ingress_refused`
   (403), and `anonymity.onion_address` is asserted separately as the
   bootstrap signal it actually is.
4. **B.3's mobile OkHttp client never inherited A.4's redirect hardening.**
   Desktop's Axios client got `maxRedirects: 0` (or origin-validated
   redirects) specifically to stop a malicious response from redirecting the
   client to a clearnet endpoint. When B.3 was rewritten in round 3 to use
   OkHttp's native SOCKS support, this requirement was never carried over —
   OkHttp's default redirect behavior is not safe here either. Fixed with
   the OkHttp equivalent (`followRedirects(false)`/origin validation) and a
   test asserting a clearnet redirect target is rejected.
5. **(Redirected from this file) PR C's "require onion ingress in the
   credential case" phrasing invited implementing the clearnet-refusal check
   as conditional on the credential branch.** The check is already
   endpoint-wide and unconditional in the real, shipped
   `dark_protocol_service.py` — this PR does not add it, and it must not
   become scoped to only one permission class on any future refactor. Fixed
   the wording to say so explicitly, plus added tests for JWT-only,
   credential-only, and mixed-authentication requests over clearnet, all
   refused identically.
6. **(Redirected from this file) PR C.4 had no test that a credential is
   confined to `vault_sync` alone**, despite C.2 point 3 already requiring
   exactly that ("authorise nothing else — it must not be usable to read or
   enumerate the vault"). Fixed by adding an explicit negative-route-scope
   test bullet covering every other entry in `VAULT_OPERATION_ROUTES`.

## 14. Implementation status — sixth CodeRabbit review round (2026-08-26)

A sixth `@coderabbitai full review` found 7 issues: 1 in this repo's shipped
code, and 6 doc-only corrections split across this file,
`docs/onion-sync-transport-phases-2-4-plan.md` (still fully unimplemented,
so zero code-regression risk), and `docs/privacy-features-gap-remediation-plan.md`.
Recorded here too, briefly, so the full review history for PR #489 stays in
one place rather than split silently across documents.

1. **`frontend/src/services/sessionVaultCrypto.js`: `sessionIsDecoy` was
   only ever reset to `false` by `installRawDek` and `clearSessionKey`, never
   by the three OTHER functions that also establish a session key
   (`initSessionKeyFromPassword`, `setupVaultPassword`,
   `unlockWithVaultPassword`).** None of these three ever install a decoy
   DEK, so this was fail-closed rather than a security hole — but a stale
   `true` left over from an earlier decoy session that never went through
   `clearSessionKey()` would make `encryptItem()`'s decoy write-refusal (the
   round-3 fix, §11.5) misfire against a session that is now genuinely real,
   silently blocking legitimate vault writes. Fixed by resetting
   `sessionIsDecoy = false` next to each function's own `sessionKey`
   assignment, and added 3 new tests
   (`sessionVaultCrypto.decoySession.test.js`) covering exactly this: a
   stale decoy flag does not survive into a session established without
   `installRawDek`.
2. **§3.7's performance checklist item ("measure `decode()` p50/p95 in a
   real browser before shipping") was still unchecked, correctly** — this
   round's finding was that it remained outstanding, not that it was
   mis-stated. A real measurement attempt was made (a minimal Vite-served
   harness importing `hiddenVaultEnvelope.js` directly) and hit a genuine,
   reproducible tooling blocker: `argon2-browser` resolves inconsistently
   between `vite.config.js`'s `optimizeDeps.include` and `resolve.alias`
   entries for a fresh, isolated module graph outside the main app's entry
   point, producing a UMD/ESM interop `SyntaxError`. Confirmed this is a
   tooling artifact (the shipped app's own existing entry point is
   unaffected) rather than a defect in the reviewed code, and documented the
   blocker plus its actual fix (drop the redundant `optimizeDeps.include`
   entry, or point it at the same aliased path) in §3.7 itself, so the next
   attempt doesn't repeat the investigation. The measurement itself is still
   not done.
3. **§5's and §10.3's "indistinguishable" acceptance claims still credited
   one general description to the specific tests that verify each part.**
   Reworded both to attribute precisely: endpoint and request byte length
   are `duressSignalService.test.js`'s own contract tests; rendered DOM
   *and* console output are `VaultUnlockModal.test.jsx`'s indistinguishability
   test. The DOM half was already covered (§11.7); the console-output half
   was not, so a new assertion was added to that same test
   (`vi.spyOn(console, 'log'/'warn'/'error')` around both a slot-0 and a
   slot-1 unlock, asserting the captured call arrays are equal) rather than
   just narrowing the prose to match existing coverage.
4. **`docs/onion-sync-transport-phases-2-4-plan.md` A.3: neither the
   bootstrap-gating nor the bounded-restart bullets said who actually calls
   them, or what happens if Tor's child process fails outright.** Fixed with
   two additions: a startup deadline (~60s) that rejects — never hangs — on
   child-process failure, with cleanup that doesn't mask the original error;
   and an explicit single lifecycle owner (the desktop main process, driven
   by privacy-mode setting changes: starts on `prefer_onion`/`require_onion`,
   stops on `off`), since a start/stop policy with no named owner is not
   actually implementable as stated.
5. **`docs/onion-sync-transport-phases-2-4-plan.md` B.3: the `http://<addr>.onion`
   guidance didn't account for Android's platform-level cleartext-traffic
   block.** API 28+ blocks cleartext HTTP by default, and OkHttp (B.3's own
   transport) honors that policy — so the plaintext onion listener would be
   silently blocked by the OS before OkHttp's own SOCKS5 routing ever runs.
   Fixed by cross-referencing this constraint from A.3 and adding the actual
   fix to B.3: a domain-scoped Network Security Configuration exception
   (`cleartextTrafficPermitted="true"` scoped to the exact onion hostname,
   never granted globally), with a test requirement on an API 28+ target
   with no global cleartext exception.
6. **`docs/onion-sync-transport-phases-2-4-plan.md` A.4: nothing specified
   how a desktop/mobile request reaches `/vault-proxy/`'s `IsAuthenticated`
   requirement at all.** The web client already sends this via
   `darkProtocolService.js`'s `authHeader()`, but the desktop/mobile
   transport design never carried that requirement over — as written, a
   correctly payload-validated (§13 point 1) request would still be rejected
   for having no bearer token. Fixed by specifying
   `proxyVaultOperation(operation, payload, authToken)` with the auth token
   as its own explicitly-named parameter, kept separate from `payload` so it
   can't be confused with — or smuggled through — the destination-field
   defense already in place there.
7. **`docs/privacy-features-gap-remediation-plan.md`'s Phase 2 summary still
   described the payload defense as an operation allowlist alone**, without
   the payload-shape check §13 point 1 had already added to the detailed
   design doc. Same class of gap as §12.1 (a summary restating a
   since-corrected design in less precise terms) — fixed by extending the
   parenthetical to name the payload-shape check and cross-reference A.4.

Verified via `gh api repos/Rajarshi1-source/Modern_Password_Manager01/pulls/489/comments`
(date-filtered to this round) that only CodeRabbit posted; no Codex or
Greptile activity this round. Targeted tests
(`sessionVaultCrypto.decoySession.test.js`, `sessionVaultCrypto.salt.test.js`,
`VaultUnlockModal.test.jsx` — 42 tests) and `eslint` all pass; markdownlint
(MD040/MD018) clean on all three touched doc files.

## 15. Implementation status — seventh CodeRabbit review round (2026-08-26)

A `@coderabbitai full review` requested after §14's fixes found 6 more
issues, all in `docs/onion-sync-transport-phases-2-4-plan.md` (still fully
unimplemented — Phases 2-4 have no code yet, so this remains doc-only, zero
regression risk) except one nitpick in this file. Verified each against
current code before fixing, same discipline as §9-14.

### 15.1 A.4/B.3: the `vault_sync` payload defense was a denylist of destination-looking names, not an enforceable schema

§13 point 1 (round 5) added "reject a payload containing `url`/`host`/
`proxy`/`origin`," but that is a denylist — it says nothing about allowed
fields, types, or nested structure, so a field the denylist did not name
(or a nested object carrying one) would pass straight through. Verified
what "sync data" actually means by reading the real contract end to end:
`frontend/src/contexts/VaultContext.jsx`'s `syncData` object (`last_sync`,
`items[]`, `deleted_items[]`) is posted to `/vault/sync/`, validated
server-side by `password_manager/vault/serializer.py`'s `SyncSerializer`
(exactly those three top-level fields) and `VaultItemSerializer` (`item_id`,
`encrypted_data`, `item_type`, `favorite`, `folder_id`, `tags`, plus
server-assigned `id`/`created_at`/`updated_at`). Fixed by replacing the
denylist with an allowlist mirroring those two serializers exactly — any
top-level or nested key outside that list is refused outright, closing the
gap for a field name no one has thought to denylist yet, not just the four
named so far. Same fix mirrored in `docs/privacy-features-gap-remediation-plan.md`'s
Phase 2 summary, which had described the same defense in the same
under-specified terms.

### 15.2 A.4: nothing said how `onionTransport.js`, in the main process, ever learns the onion address at all

A.4 said the `.onion` origin comes from `capabilities.anonymity.onion_address`
"fetched over clearnet on the first call," cross-referencing A.5 for which
service makes that call — but A.5's `getCapabilities()` call lives in the
**renderer's** clearnet service, and the `TOR_PROXY` IPC channel (by the
payload-shape defense in §13/§15.1) carries sync data and `authToken` only,
never a destination. There was no path left for the main process to receive
this value at all. Fixed by having `onionTransport.js` make its own,
independent clearnet fetch to the same capabilities endpoint, authenticated
with the same forwarded `authToken` it uses for the `vault_sync` POST, and
cache the resolved address for the session — explicitly documented as a
separate fetch from A.5's renderer-side one, not a shared value, so the two
are never conflated again. Validation of the resolved value as a well-formed
`.onion` hostname before dial, and the empty-cache-first-call test, are both
specified alongside it.

### 15.3 A.5: the availability check could read a bootstrap snapshot instead of awaiting it, making A.3's own promise unreachable

A.3 says the sidecar's first subsequent `proxyVaultOperation` call awaits
its readiness — but `prefer_onion`/`require_onion` decide whether to call
`proxyVaultOperation` at all based on `isOnionSyncAvailable()`, which A.5
specifies as a synchronous read of `torSidecar.getStatus()`. A snapshot
taken mid-bootstrap (which is exactly when a first sync after a mode change
is most likely to run) reads as "not ready," so `prefer_onion` silently
falls back to clearnet and `require_onion` fails closed during perfectly
normal startup — A.3's await is never reached, because the availability
gate upstream already returned false. Fixed by specifying that the
mode-change handler exposes its in-flight `start()` promise, and the
availability check awaits that promise (bounded by A.3's own ~60s deadline)
before reading `getStatus()`, with concurrent callers sharing the same
in-flight promise rather than each starting a second sidecar.

### 15.4 B.3: the Android cleartext exception named a runtime value a packaged config file cannot hold

B.3's Network Security Configuration fix (round 6, §14 point 5) scoped the
cleartext exception to "the exact `.onion` hostname" — but that hostname
comes from `capabilities.anonymity.onion_address` at runtime, per B.3's own
no-hardcoding rule, while Android's Network Security Configuration is
packaged into the APK at build time and cannot be altered after install
(confirmed against Android's own documentation: domain-config entries are
static and cannot change at runtime). An exact-hostname `<domain>` entry
therefore cannot name a value the app does not learn until its first
network call. Fixed by reframing the packaged hostname as a build-time
deployment constant (injected via a Gradle-generated resource value when
the APK is built for a given backend, the same way a backend URL is
typically parameterized per build flavor) rather than a runtime-discovered
one, with a runtime check that `capabilities.anonymity.onion_address`
matches the compiled-in value exactly before attempting the request — a
mismatch is treated as unavailable, never as grounds to widen the exception
or attempt a request Android will block anyway.

### 15.5 §9 "Cross-cutting rules" point 3 still omitted device-local transport readiness that A.5 itself requires

The same class of miss as §12.1: A.5 gates desktop/mobile availability on
`anonymity.available && onion_address` **and** that platform's own local
sidecar/Orbot readiness (added in round 5, §13 point 2) — but §9 point 3's
summary of the same rule, last touched in §12.1, only ever named the first
two conditions. A reader relying on the summary alone would rebuild the
version A.5 already found and fixed to be incomplete. Fixed by adding the
local-readiness clause to §9 point 3 itself, cross-referencing A.5 rather
than restating its full argument a second time.

### 15.6 `unlockEnvelopeStore.js` (this file, §3.2): the documented `setDecoySlot` signature carried a parameter the shipped function never had

§3.2 documented `setDecoySlot({ userId, vaultPassword, decoyPassword,
decoyDek })` — but the actual implementation (`unlockEnvelopeStore.js:232`)
generates the decoy DEK internally
(`window.crypto.getRandomValues(new Uint8Array(32))`) and never accepts one
from the caller; a caller passing `decoyDek` would have it silently
ignored. Fixed by removing the parameter from the documented signature so
it matches what shipped.

Verified via `gh api repos/Rajarshi1-source/Modern_Password_Manager01/pulls/489/comments`
(date-filtered to this round) that only CodeRabbit posted this round.
Doc-only changes; no code touched, so no test suite run beyond the
markdownlint check already required by this repo's convention for
doc-only PRs.

## 16. Implementation status — eighth CodeRabbit review round (2026-08-26)

An eighth `@coderabbitai full review` found 7 distinct issues, organized into
four numbered sections below (§16.1–§16.4; the last bundles four related
stale-reference corrections rather than being one finding): **2 in shipped
code** (the first code findings since round 6), 1 allowlist gap, and 4
status/cross-reference corrections. One of the two shipped-code findings was
accepted in part and declined in part, for a reason recorded below rather
than silently dropped.

### 16.1 §11.5's decoy write-gate missed the two mutation paths that never encrypt — Major, and the same "built the guard, forgot a caller" pattern this PR family keeps hitting

§11.5 (round 3) stopped a decoy session from corrupting the real vault by
refusing inside `sessionVaultCrypto.encryptItem()`. That covers
`VaultContext.addItem` and `updateItem`, since both call `encryptEnvelope`
→ `encryptItem` before writing. It does **not** cover the two mutation
paths that legitimately never encrypt anything, verified by reading each
end to end:

- **`VaultContext.deleteItem`** calls `vaultService.deleteVaultItem(itemId)`
  directly and sends no ciphertext at all, so it never reaches the gate. In
  a decoy session this would issue a real `DELETE` against the one shared,
  server-side item list — **destroying a genuine item irreversibly**. That
  is strictly worse than the corruption §11.5 was written to prevent: a
  corrupt row at least still exists.
- **`VaultContext.toggleFavorite`** deliberately bypasses the re-encrypt
  path (its own comment explains why: `favorite` is non-secret metadata and
  the item may be lazy-loaded with no decrypted payload available), issuing
  a metadata-only `PATCH`. Lower severity, but still a real mutation of a
  real item's persisted state from a session that is not the real user's,
  and it applies an optimistic local flip before the request.

**Fix:** both now check `sessionVaultCrypto.isDecoySession()` **before the
request and before any optimistic state change**, mirroring the
`hasVaultSessionKey()` guard pattern `addItem`/`updateItem` already use in
the same file — no new mechanism, just the existing one applied where it was
missing. New test file
`frontend/src/contexts/__tests__/VaultContext.decoySession.test.jsx`
(6 tests) asserts, for each path: no service call is made, no state change
is applied, a real session is unaffected, and the surfaced message stays
generic. **Negative-controlled before being trusted** (the discipline
[[feedback-verify-bot-review-findings]] and PR #488's own round-4 lesson
already established): disabling both guards makes 4 of the 6 fail, and the
2 that still pass are exactly the two "a real session still works" cases
that must not depend on the guard. Restoration verified byte-identical
against a pre-edit copy, not by eye.

Deliberately **not** extended to reads: this fix's scope is the mutation
paths §11.5 was already about. A believable decoy experience remains §7's
deferred product work.

> **Superseded in part by §18.1 (round 10).** This paragraph originally also
> excluded "backup/restore, or folder/tag operations" from the gate. That was
> wrong for backup/restore, and wrong in a way worth recording rather than
> quietly editing away: it excluded them by CATEGORY NAME rather than by what
> they actually do. `restoreBackup` is an item-mutation path — the server's
> `_restore_from_items` can `filter(user=request.user).delete()` and then
> batch `update_or_create` — so it belonged inside this fix's own stated
> scope all along. See §18.1.

### 16.2 The decoy write-refusal message named the duress feature to anyone watching the screen — accepted; the suggested console log was declined

`encryptItem`'s refusal threw `'Vault is in a decoy session: new items
cannot be saved.'`, and `VaultContext` surfaces `error.message` verbatim via
`setError`. So a coercer standing over the user during a duress unlock could
read the existence of the duress feature off a single failed save — which
defeats the entire point of the decoy, and is a different failure from the
one §11.5 explicitly deferred ("making the write-refusal message
indistinguishable from an unrelated save failure" was deferred as UX
polish; *actively naming the feature* is an information leak, and fixing it
is a one-line change). **Fixed:** the message is now `'Failed to save item.
Please try again.'` — wording an ordinary failure could equally produce, and
consistent with `VaultContext`'s own existing fallback strings. The two new
guards in §16.1 use the same generic style for the same reason.

**Declined, deliberately: the other half of the suggestion, "log the
decoy-specific reason to the console."** That directly contradicts this
plan's own §3.5 rule 4 ("**No logging branch.** No `console.*` may mention
slots or duress"), which is a reviewed, deliberate decision, and round 6
(§14 point 3) went as far as adding a console-output-equality assertion to
`VaultUnlockModal.test.jsx` to enforce it. Logging the reason would not
remove the tell — it would move it from the UI to devtools, where a coercer
sophisticated enough to look is exactly the coercer this feature is trying
to survive. The refusal needs no log to be debuggable: `isDecoySession()` is
already exported and is what the tests assert on.

The existing test that pinned `/decoy session/i` was updated to assert the
**gate** fired (via `isDecoySession()`) rather than the message text — pinning
the old wording would have re-pinned exactly the string that must not leak —
plus a new test asserting the message matches the generic form exactly and
contains no `decoy`/`duress`/`slot` wording.

### 16.3 The `vault_sync` payload allowlist omitted `expected_sync_version`, which the sync view really does accept

Round 7 (§15.1) derived the allowlist from `SyncSerializer`'s declared
fields. Verified this round that the sync view reads one more field straight
off `request.data`, **outside** the serializer entirely
(`password_manager/vault/views/crud_views.py:373`): `expected_sync_version`,
an optional integer used for optimistic concurrency against the locked
`UserSalt.sync_version` row, returning 409 on mismatch. No client sends it
today, so nothing is broken right now — but the first concurrency-aware
client to start sending it would be rejected at the IPC boundary, and the
failure would look like a transport bug rather than a stale allowlist.
Added to the allowlist in `docs/onion-sync-transport-phases-2-4-plan.md`
with the reasoning inline. It is a plain integer with no destination
semantics, so admitting it costs nothing the schema protects. **Lesson: a
serializer's declared fields are not automatically the endpoint's full
accepted input — check the view body for direct `request.data` reads
before treating the serializer as the complete contract.**

### 16.4 Three stale cross-references and one stale status claim

- This file's opening summary still said "five review rounds (§9–§13)" after
  §14 and §15 had been appended. Updated to §9–§16.
- §0's verdict table still listed `VaultUnlockModal` as "Not integrated" —
  true when written, false since this PR shipped. Rather than rewriting the
  historical verdicts (which would destroy the baseline the rest of the plan
  argues against), §0 is now explicitly **labelled** the pre-implementation
  baseline, in its own heading and in a note at the top of the file.
- §3.6 step 2 still said "Client generates a fresh decoy DEK", contradicting
  §15.6's own correction one round earlier — the same one-place-fixed,
  other-place-missed pattern as §12.1 and §15.5. Fixed to say the service
  generates it internally.
- `docs/privacy-features-gap-remediation-plan.md`'s summary paragraph
  referred to "§13" and "§9 through §13" without naming which document those
  sections live in — and the bare `§N` numbers refer to THIS file while the
  surrounding sentence was describing findings in the onion-sync plan.
  Clarified by naming the document explicitly, stating that every bare `§N`
  in that paragraph refers to this file, and extending the range to §15.

Targeted tests only, per the standing preference recorded in
[[feedback_targeted_testing]]: the 7 files covering the changed paths
(`VaultContext.decoySession.test.jsx`, `VaultContext.addItem/updateItem/lock`,
`sessionVaultCrypto.decoySession.test.js`, `VaultUnlockModal.test.jsx`,
`unlockEnvelopeStore.test.js`) — 59 tests, all passing, including the
console-equality assertion from §14 that the message change could plausibly
have broken. `eslint` clean on all four changed files (0 errors; the 8
warnings are pre-existing and none fall on a changed line). The full
frontend suite is CI's job, not this change's.

## 17. Implementation status — ninth CodeRabbit review round (2026-08-27)

A ninth `@coderabbitai full review` found 9 issues: 1 nitpick in shipped
code, and 8 actionable findings split across this file, `docs/onion-sync-transport-phases-2-4-plan.md`
(still fully unimplemented, so zero code-regression risk for those two), and
`frontend/src/Components/layout/Sidebar.jsx`. Verified each against current
code before fixing, same discipline as every prior round.

### 17.1 `frontend/src/services/sessionVaultCrypto.js`: `unlockWithVaultPassword` and `exportWrappedDekRaw` duplicated the entire wrapped-record-unwrap step

Confirmed by reading both functions in full: record load, JSON parse,
version check, KEK derivation, and the `unwrapKey` call (algorithm, key
length, and the canonical "Incorrect vault password." error) were
byte-identical between the two, differing only in the `extractable` flag
passed to `unwrapKey` — exactly the duplication `exportWrappedDekRaw`'s own
comment already flagged as a "keep these two in sync by hand" risk.

**Fix, scoped carefully to avoid a subtler regression the full suggested
extraction would have introduced:** only the KEK-derive-and-unwrap step
(the part with real crypto parameters, where a silent drift would be a
security bug) was extracted into a new private `unwrapDek(vaultPassword,
record, extractable)`. The record-loading/parsing/version-check lines stay
duplicated deliberately. Reason: `unlockWithVaultPassword` reserves
`sessionGeneration` **after** its synchronous validation completes but
**before** the slow KEK/unwrap step — capturing generation any earlier
would mean a call that fails on a corrupt record (synchronously, before
ever reaching this line) still advances the counter, which could
spuriously invalidate a genuinely-in-flight concurrent call that reserved
its own generation just before it. Folding the synchronous validation into
the shared helper would have made preserving that exact ordering
impossible from the outside. The extracted helper never touches
`sessionGeneration` at all, so this risk does not apply to it.

New test file `sessionVaultCrypto.exportWrappedDekRaw.test.js` (3 tests,
real WebCrypto/localStorage, no mocks): both functions recover the
identical DEK from the same wrapped record, both reject a wrong password
with the identical message, and `exportWrappedDekRaw` still touches no
session state. **Negative-controlled**: swapping the two `extractable`
arguments (making `exportWrappedDekRaw` request a non-extractable key)
made 2 of the 3 new tests fail with a real `InvalidAccessException` from
WebCrypto itself, not a mock; restoration verified byte-identical against
a pre-edit backup.

### 17.2 `docs/onion-sync-transport-phases-2-4-plan.md` A.3: the sidecar lifecycle-owner design had no path for the renderer's mode to actually reach the main process

A.3 makes the desktop main process the sole owner of
`torSidecar.start()`/`stop()`, driven by "the privacy-mode setting" — but
`getSyncPrivacyMode()`/`setSyncPrivacyMode()` (`onionSyncService.js`) are
renderer-local `localStorage` reads/writes, and Electron's main process has
no access to the renderer's `localStorage` without an explicit bridge.
Nothing in the design said how a live mode change, or the mode already
persisted from a previous session, would ever reach the main process at
all. Fixed with two additive steps: `setSyncPrivacyMode()` also calls the
existing `TOR_START`/`TOR_STOP` IPC channels when running under Electron
(making `start()`/`stop()` idempotent, so a redundant call from a
non-off-to-non-off change is harmless); and the renderer calls the same
step once, unconditionally, on startup using whatever mode is currently
persisted — closing the "user relaunches with `require_onion` already set"
gap. Test guidance added for both: startup with a persisted non-off mode,
and the `prefer_onion` → `off` transition through this same handoff.

### 17.3 `docs/onion-sync-transport-phases-2-4-plan.md` C.3: `IsAuthenticated OR HasAnonymousCredential` accepted a request presenting both

A request carrying a valid JWT alongside a valid anonymous credential would
pass the OR'd permission check on the JWT alone, and dispatch is
`request.user`-scoped — so the server could link that specific credential
redemption to a real user identity, defeating C.5's own acceptance
criterion that onion-routed sync "carries no JWT and no user identifier"
for exactly the requests where it matters most. Fixed by requiring EXACTLY
ONE authentication mode before dispatch, at the same point the
unconditional onion-ingress check already lives (and for the identical
reason: a boundary that must not depend on which permission class happens
to evaluate first) — additive to the existing OR, not a replacement for
it. Added a C.4 test bullet for the mixed-credential-over-onion case,
distinct from the existing clearnet-refusal bullet (which already covers
"both credentials, over clearnet" but never asserted anything about a
mixed request that reaches the onion-ingress check successfully).

### 17.4 This file's round-count claims had drifted from its own section numbers, in three places

- The opening summary said "seven CodeRabbit review rounds (§9–§16)" —
  §9 through §16 is eight sections, not seven. Fixed to state the count
  that will be true once this section is added: nine rounds, §9–§17.
- §14 said it found 8 issues (1 code + 7 doc-only) but its own numbered
  list has exactly 7 entries (1 code + 6 doc-only). Corrected the prose to
  match the list that was already there.
- §16 said it found 6 issues while its own four numbered subsections
  describe 2 code issues + 1 allowlist issue + 4 bundled status/cross-reference
  corrections (§16.4 alone bundles four) — 7 distinct findings, not 6.
  Corrected to state the count explicitly as 7, organized into 4 numbered
  sections, naming why the two numbers differ (§16.4 bundles four related
  corrections under one heading) rather than leaving the mismatch for the
  next round to catch.

`docs/privacy-features-gap-remediation-plan.md`'s own summary paragraph
inherited §14's miscount (it said "20 more issues" for rounds five through
seven, which was `6 + 8 + 6` using §14's WRONG count of 8) — corrected
there too, to the accurate `6 + 7 + 6 + 7 + 9 = 35` across rounds five
through nine, and its `§9 through §15` cross-reference extended to `§9
through §17`. **Lesson, extending §12.1's own: a summary that cites a
per-round count doesn't just need updating when a round is APPENDED — it
needs re-checking when an EARLIER round's own stated count turns out to
have been wrong, since the summary already baked in the mistake.**

### 17.5 §3.2/§3.4: `open()`'s documented return shape didn't match what shipped, and the flow steps that followed it compounded the mismatch

§3.2 declared `open({ userId, password }): Promise<{ slotIndex, payload }>`.
The actual shipped function (`unlockEnvelopeStore.js:320`) returns `{
slotIndex, dekBytes, saltB64, duressToken }` — it unpacks the slot's JSON
payload via `parseSlotPayload` before returning, never exposing a raw
`payload` object at all. §3.4's own flow steps then compounded this by
describing calls that only make sense under the STALE shape
(`installRawDek(payload.dek, payload.salt, userId)`,
`reportUnlockForSlot(..., slotIndex, payload)`) rather than the real one.
Verified against `VaultUnlockModal.jsx`'s actual call site
(`sessionVaultCrypto.installRawDek(dekBytes, saltB64, ...)`,
`reportUnlockForSlot(getAccessToken?.(), slotIndex, { __duress_signal:
duressToken })`) before fixing, rather than guessing which side was
correct. Fixed §3.2's declared signature and §3.4's two flow-step
descriptions to match the shipped shape exactly.

### 17.6 §4: the no-decoy test description read as if slot 1 successfully decrypts

"`provision()` with no decoy: ... slot 1 decrypts under no known password"
is ambiguous — it can be misread as a successful decryption under some
condition, when the actual, tested property is the opposite: `open()`
**rejects** every attempt against an unconfigured slot 1, with the
identical `WrongPasswordError` a wrong password against a *configured*
decoy produces. Verified against the real test
(`unlockEnvelopeStore.test.js`: "a no-decoy blob rejects an arbitrary
password with `WrongPasswordError`, not a crash") before rewording, rather
than guessing at the intended meaning. Reworded as an explicit negative
assertion.

### 17.7 §5: the acceptance checklist had drifted out of sync with tests that already passed

Six of eight checklist items were unchecked despite being genuinely covered
by existing, currently-passing tests — verified by running the actual
targeted suites (`unlockEnvelopeStore.test.js`, `VaultUnlockModal.test.jsx`,
`duressSignalService.test.js`, and #486's `test_duress_signal.py`, 49 + 32
tests, all passing) and matching each criterion to the specific test that
covers it, the same discipline the existing (already-checked)
indistinguishability item already modeled. Checked: vault/decoy unlock +
DEK install + vault renders (via `onUnlocked` firing — §3.4 step 5's own
documented trigger for `App.jsx`'s `vault:updated` dispatch); no password
in any unlock-path request body (`duressSignalService.test.js`'s
`reportUnlock` body-shape assertion — verified this is the ONLY network
call the unlock path makes, since `open()`/`installRawDek()`/
`unlockWithVaultPassword()` are pure local crypto); `DuressEvent`
created-on-decoy/not-on-normal (combined client + #486 server coverage);
OAuth upgrade transparent + failed-upgrade non-fatal; slot 1 of a no-decoy
blob indistinguishable; and Argon2 parameters unchanged (verified directly:
`DEFAULT_KDF_TIME`/`_MEMORY_KIB`/`_PARALLELISM` in `hiddenVaultEnvelope.js`
still match §3.7's stated values). **Left deliberately unchecked**: the
p50/p95 performance measurement — §3.7's own status note already explains
why it remains genuinely undone, and checking it would have been the exact
mistake this finding warns against, in the other direction.

### 17.8 Risk table: the missing-envelope recovery claim was stated as unconditional when it only applies to one of two cases

"A MISSING envelope always fell back to the legacy path (`upgrade` mode)"
is only true for a user who already has a legacy `vaultWrappedDEK` record.
Verified against `VaultUnlockModal.jsx`'s actual mode-selection logic
(lines 44-52): a user with NEITHER `hasEnvelope()` NOR `hasWrappedKey()`
takes the `setup` branch instead, not `upgrade` — provisioning a fresh
envelope from scratch, per §0's own verdict table and §3.4. Scoped the
claim to the case it actually describes, and named the `setup` branch for
the other case rather than leaving it implied.

### 17.9 `frontend/src/Components/layout/Sidebar.jsx`: the new Vault Duress nav link had no accessible name when the sidebar is collapsed

`NavItemText` is `display: none` while `collapsed` is true (removed from
the accessibility tree, not just visually hidden), and the link's only
other child is a decorative icon (`<FaMask />`) with no text alternative —
so a collapsed sidebar left this link with no accessible name at all for
screen-reader users. `NavItem` is `styled(NavLink)`, which forwards
arbitrary props straight to the underlying `<a>`, confirmed before adding
one. Fixed with `aria-label="Vault Duress"` on this one `NavItem`.
**Deliberately not applied to the sidebar's other nav items** — every one
of them shares the identical `NavItemText`/`display:none` pattern and so
has the same latent gap, but none of them were touched by this PR; fixing
pre-existing, out-of-diff items on this PR's own initiative would be the
exact scope creep [[privacy-features-gap-plan]]'s PR #488 round-4 lesson
already warns against. Left as a separate, real, awareness item for
whoever next touches the sidebar broadly.

Verified via `gh api repos/Rajarshi1-source/Modern_Password_Manager01/pulls/489/comments`
(date-filtered to this round) that only CodeRabbit posted this round.
Targeted tests: `sessionVaultCrypto.exportWrappedDekRaw.test.js` (new, 3
tests) plus `sessionVaultCrypto.decoySession.test.js`,
`sessionVaultCrypto.salt.test.js`, and `VaultUnlockModal.test.jsx` — 46
tests, all passing, plus the backend `test_duress_signal.py` (32 passed, 1
environment-gated skip) run in support of §17.7's checklist verification.
`eslint` clean on all three changed frontend files (0 errors; pre-existing
warnings unrelated to any changed line). `markdownlint` (MD018/MD022/MD040
— the rules this repo's history actually enforces; MD013/MD025/MD031/MD060
are pre-existing, unenforced style choices, not this PR's concern) clean on
all three touched doc files.

## 18. Implementation status — tenth CodeRabbit review round (2026-08-27)

A tenth `@coderabbitai full review` found 9 issues: **2 in shipped code**, 6
in `docs/onion-sync-transport-phases-2-4-plan.md` and
`docs/privacy-features-gap-remediation-plan.md`, and 1 repeat of a prior
round's finding that had been fixed at the wrong level. Verified each against
current code before fixing, same discipline as every prior round. Notably,
**both code findings are cases where an EARLIER round of this same PR drew a
scope boundary in the wrong place** — recorded as such rather than presented
as new discoveries.

### 18.1 The decoy write-gate still missed `restoreBackup`, which can wipe the real vault — §16.1's own scoping note was the cause

§16.1 (round 8) extended §11.5's decoy gate to `deleteItem` and
`toggleFavorite`, then explicitly excluded "reads, backup/restore, or
folder/tag operations" as out of scope. Traced what `restoreBackup` actually
does before accepting or rejecting this finding, rather than re-reading the
scoping sentence: `VaultContext.restoreBackup` POSTs to
`/vault/restore_backup/<id>/`, which reaches `backup_views.py`'s
`_restore_from_items` — and that function, when `clear_existing` is set, runs
`EncryptedVaultItem.objects.filter(user=request.user).delete()` and then
`update_or_create` for every item in the payload. **On `request.user`: the
REAL user.** So a decoy session could wipe and overwrite the real vault
irreversibly — the same class as the `deleteItem` gap §16.1 itself was
written to close, with a strictly larger blast radius (the whole vault, not
one row).

The root cause is worth stating plainly because it is a reasoning error, not
an oversight: §16.1 excluded these paths **by category name** ("backup/
restore") rather than by what they do. `restoreBackup` IS an item-mutation
path; it simply does not go through `addItem`/`updateItem`. The rule already
recorded in memory from that very round — "if it does not encrypt (a delete,
a metadata-only PATCH, **a bulk operation**), it needs its own explicit
guard" — names bulk operations explicitly, and then §16.1's own prose
excluded the one bulk operation in the codebase.

**Fix:** both `createBackup` and `restoreBackup` now check
`sessionVaultCrypto.isDecoySession()` before their request, with the same
generic non-revealing message the other guards use (§16.2). `restoreBackup`'s
guard also runs before the `refreshItems()` that would otherwise reload an
overwritten list. `createBackup` is guarded too, at lower severity and for
consistency rather than destructiveness: `create_backup` snapshots the real
user's items into a new server-side `VaultBackup` row, so it is still a real
write from a session that is not the real user's. `getBackups` is deliberately
**left unguarded** — it is a read, and reads remain out of scope by the same
§11.5 boundary that has held since round 3.

3 new tests in `VaultContext.decoySession.test.jsx`: restore makes no request
and triggers no refresh (asserted by pinning the GET count, not by "never
called", since mount already performs one), create makes no request, and a
real session still does both. Negative-controlled together with §18.2:
disabling all four guards fails 11 of the file's 34 tests.

### 18.2 `parseSlotPayload` validated the DEK's length but not the duress token's, leaving a wire-length tell

§11.6 (round 3) added a `dekBytes.byteLength === 32` check to
`parseSlotPayload` for exactly the right reason — so a corrupt-envelope
failure lands inside `open()`'s call stack where `VaultUnlockModal`'s
`envelopeUnusable` fallback catches it. The `__duress_signal` field sitting
two lines below got no equivalent check: `typeof x === 'string' ? x : null`
accepted **any** string, of any length.

Traced the consequence rather than assuming one: `open()` returns that token
→ `VaultUnlockModal` passes it to `reportUnlockForSlot` → `reportUnlock`
sends `JSON.stringify({ signal })`. A present-but-wrong-length token
therefore changes the **request body's byte length**, which is precisely the
invariant §3.5 rule 1 exists to protect ("same endpoint, same body size,
every unlock") and which `duressSignalService.test.js` already asserts for
the real-vs-noise case. That is a genuine indistinguishability break.

**Severity, stated honestly rather than inherited from the review's framing:**
this is defense-in-depth, not a live exploitable bug. The slot payload lives
inside AES-GCM-authenticated ciphertext, so an attacker cannot tamper with it
without the password, and the only writer (`setDecoySlot`) always uses
`generateSignalToken()`, which is always 44 chars. The realistic trigger is a
future code change, which is exactly what a regression guard is for.

**Fix:** `parseSlotPayload` now rejects a PRESENT `__duress_signal` that is
not a string of exactly `SIGNAL_TOKEN_LENGTH` characters, throwing
`MalformedSlotPayloadError` — same error, same placement, same fallback
behaviour as the DEK check above it. `duressSignalService` gained an exported
`SIGNAL_TOKEN_LENGTH` (derived from its own `SIGNAL_BYTES`, not a literal
`44`) so the check cannot drift if the token size ever changes — the same
reasoning that already made `REPORT_TIMEOUT_MS` an export.

**Declined, deliberately: rejecting a MISSING token.** The review asked for
"missing, non-string, or non-44-character" to all be rejected. A missing
token is the one case that leaks nothing: `reportUnlock` then generates noise
at its correct full length, so the wire is unchanged. Throwing would instead
make a decoy password *fail to open the decoy vault* — under duress, in front
of a coercer — over a payload with no tell in it. That trade is strictly
worse for the threat model this feature serves, so a missing token still
yields `null`. 7 new tests in `unlockEnvelopeStore.test.js` cover both
halves: five malformed shapes rejected, and missing/well-formed accepted.

### 18.3 `docs/onion-sync-transport-phases-2-4-plan.md` A.3: the control-port test asserted the wrong thing, and "mode 0700" is POSIX-only

Two separate defects in adjacent bullets, both real:

- **The auth test.** A.3 asked for "a test asserting an unauthenticated
  control connection is rejected". `CookieAuthentication 1` does not refuse
  the TCP connection — Tor accepts it and then rejects control *commands*
  until a valid `AUTHENTICATE`, closing the connection on failure. The test
  as specified would fail against a correctly-configured Tor while never
  exercising the authorization check. Rewritten to: connect, issue a command
  (`GETINFO version`) with no prior `AUTHENTICATE`, assert an auth error or
  closure; then repeat with a deliberately wrong cookie.
- **The permissions.** "mode 0700" is a POSIX instruction, and this app
  ships a Windows target (`desktop/package.json` `build.win`) where
  `fs.chmod` is effectively a no-op and the directory inherits the parent's
  ACL — which on a shared machine can include other local users. Since the
  control-port **cookie file is the credential**, that is a real gap, not a
  cosmetic one. Now specifies an owner-only DACL with inheritance disabled on
  Windows alongside 0700 elsewhere, and requires the test to attempt access
  as a second local user on every shipped platform — a test that only checks
  POSIX mode bits passes on Windows while proving nothing.

### 18.4 A.3's `start()` idempotency wording contradicted A.5's await-readiness requirement — both written in round 9

§17.2 (round 9) specified `start()` as "a no-op returning current status"
when already bootstrapping. §17.3, in the same round, established that the
availability check must be able to **await** an in-flight bootstrap, because
a mid-bootstrap snapshot makes `prefer_onion` fall back to clearnet and
`require_onion` fail closed during normal startup. A status snapshot is
exactly what §17.3 rules out, so the two sections shipped contradicting each
other. Fixed: `start()` returns the SAME in-flight readiness promise while
bootstrapping, and is a genuine no-op only once it has settled. Test guidance
added for two concurrent first syncs from a stopped state sharing one promise.

**Lesson, and the second instance of this exact shape in two rounds:** round
9 fixed a stale count in one document that had already propagated into
another; this round found two sections of the SAME round contradicting each
other. When one round changes a design fact in more than one place, the
places must be diffed against each other before the round is called done —
not just each one checked against the finding that prompted it.

### 18.5 A.8's no-survivor acceptance criterion promised what A.3 already said was impossible

A.8 read "No `tor` process survives app quit, crash, or force-quit" —
unconditional. A.3's own exit-path bullet already states, correctly and at
length, that `process.on('exit')` cannot await anything, `app.exit()` skips
the quit handlers entirely, and SIGKILL runs no JS at all. A criterion that
contradicts its own design section is one nobody can honestly tick. Split
into two: a normal-quit criterion verifiable by observation, and a separate
criterion requiring a **named OS-level parent-lifetime mechanism per
platform** (Windows Job Object with `KILL_ON_JOB_CLOSE`; process-group kill /
`PR_SET_PDEATHSIG` / `kqueue NOTE_EXIT` on the Unix targets) verified by a
real parent-kill test rather than by calling `stop()`.

### 18.6 B.2 treated Orbot's SOCKS port as fixed at 9050

B.2 described "a stable SOCKS5 endpoint on `127.0.0.1:9050`". Verified
against Orbot's own documented behaviour: 9050 is the **default**, the port
is user-configurable, Orbot writes the configured value into the torrc it
generates, and `0` is the documented value for **disabling** the SOCKS
listener. A hardcoded 9050 would work on a default install and fail silently
for anyone who changed it — and would connect to *something else* entirely if
another process held that port. Fixed: discover the configured port from
Orbot's own status/binding surface, treat `0`/absent/unparseable as "onion
sync unavailable" rather than falling back to 9050, and verify the resolved
listener accepts a connection before reporting availability — the same
"confirm one real SOCKS5 connection" discipline A.3 already requires of the
desktop sidecar's ephemeral port. Tests required for a non-default port and
for port 0.

### 18.7 `docs/privacy-features-gap-remediation-plan.md`: a historical scope statement read as current status, and the Phase 2 summary could rebuild a fixed bug

- The "**Not delivered — deliberately out of scope for this PR**" paragraph
  describes PR #486's scope at merge time, but reads as present-tense status
  and lists §4.2 as undelivered — which PR #489 delivered. The same paragraph
  already had the right pattern for §4.4 ("since delivered in the PR #488
  follow-up"), so applied it to §4.2 as well and marked §4.1 as still open,
  rather than rewriting the historical statement and destroying the record of
  what #486 actually scoped.
- The Phase 2 summary said to route the sync request "through the `.onion`
  from `getCapabilities()`", which is the pre-§15.2 design: `onionTransport.js`
  resolves the address itself, in the main process, precisely so the IPC
  channel can carry no destination field. The summary also said nothing about
  availability gating, leaving an implementer who read only it free to gate on
  `vault_proxy.available` — structurally always `false` on desktop, the exact
  bug §10.4/§15.5 already fixed twice. Corrected both, with the gating rule
  stated inline rather than only cross-referenced.

Targeted tests only, per the standing preference recorded in
[[feedback_targeted_testing]]: the files covering the changed paths —
`unlockEnvelopeStore.test.js` and `VaultContext.decoySession.test.jsx`
(34 tests, 10 of them new this round), plus `VaultUnlockModal.test.jsx`,
`duressSignalService.test.js`, `sessionVaultCrypto.decoySession.test.js`,
`sessionVaultCrypto.exportWrappedDekRaw.test.js`,
`sessionVaultCrypto.salt.test.js`, `VaultDuressSetup.test.jsx`, and the three
sibling `VaultContext.*` suites that share the mocked module surface. Both
code fixes negative-controlled before being trusted (disabling all four decoy
guards plus the duress-length check fails 11 of 34 tests; restoration
verified byte-identical against pre-edit backups). `eslint` clean on the
changed files. `markdownlint` (MD018/MD022/MD040) clean on all three touched
doc files. The full frontend suite is CI's job, not this change's.

## 19. Implementation status — eleventh CodeRabbit review round (2026-08-27)

An eleventh `@coderabbitai full review` found 5 issues: 1 hardening gap in
shipped code and 4 in `docs/onion-sync-transport-phases-2-4-plan.md` (still
fully unimplemented). **Three of the four doc findings are internal
contradictions introduced by MY OWN earlier rounds of this same PR** — the
pattern §18.4 already flagged, now at its third and fourth instance. That is
no longer a coincidence and is recorded as such in §19.6.

### 19.1 `provision()` validated every argument except `saltB64`, and a missing one writes a permanently dead envelope

`provision()` guards `userId`, `vaultPassword`, and `dekBytes` (the last with
an explicit 32-byte length check, added in §11.6) but never checked
`saltB64`. Traced what a bad value actually does rather than filing it as a
generic missing-guard: `buildSlotPayload` places `salt: saltB64` into an
object it hands to `jsonToBytes`, and **`JSON.stringify` drops a key whose
value is `undefined` entirely**. So `provision({..., saltB64: undefined})`
writes a structurally valid, correctly-sized, successfully-encrypting blob
whose payload simply has no `salt` key — and `parseSlotPayload` requires
`typeof obj.salt === 'string'`, so **every subsequent `open()` fails with
`MalformedSlotPayloadError`, permanently**. The envelope is dead on arrival
and the failure surfaces far from the call that caused it.

**Severity, stated honestly:** a hardening gap, not a live bug. The only
production caller (`VaultUnlockModal.jsx`) always passes a real string from
`sessionVaultCrypto`. But this is the same shape as §11.6's own finding —
validate the field where a bad value is CREATED, not where it is later
discovered — and the guard is one line.

**Fix:** reject a non-string or empty `saltB64` at entry, so a bad envelope
is never written. 4 new parameterised tests in `unlockEnvelopeStore.test.js`
cover `undefined`/`null`/number/empty-string and additionally assert
`hasEnvelope()` is still `false` afterwards — proving nothing was persisted,
not merely that the call threw. Negative-controlled: disabling the guard
fails all 4.

### 19.2 C.3 asserted an ordering about the SHIPPED code that is factually false — and PR C's own design depended on it

An earlier draft of C.3 (mine, round 9) justified the onion-ingress check's
placement by claiming it "already runs endpoint-wide, unconditionally,
**before either permission class is even evaluated**." Verified against the
installed DRF source rather than reasoning about it: `APIView.dispatch()`
calls `self.initial(...)`, which calls `check_permissions()` at
`rest_framework/views.py:421`, and only afterwards invokes the handler at
`:512`. `DarkProtocolVaultProxyView.post()` is that handler, and it is what
calls `DarkProtocolService.proxy_vault_operation(...)` — so the ingress
check runs **strictly after** permission evaluation, not before.

This is harmless in the code as it exists today: the endpoint is
`IsAuthenticated`-only, the two checks are independent, and neither can mask
the other. But PR C is precisely where a false ordering assumption turns
into a real bug, because it adds a second permission class whose
interaction with the first is the whole point. Corrected the claim, kept the
requirement it was (badly) justifying: the ingress check stays on
`proxy_vault_operation`, ahead of and independent of vault dispatch, and
must never be moved or duplicated inside `HasAnonymousCredential` alone.

**Consequence for the mixed-credential rule (§17.3):** that rule said to put
the exactly-one-auth-mode check "before dispatch — same place as the
onion-ingress check," which inherits the same wrong premise and is too late
to be what it claims. A mixed request passes `IsAuthenticated` on its JWT
during `check_permissions()` and arrives at the handler with `request.user`
populated. Corrected to name a hook that genuinely precedes permission
evaluation: override `initial()` and run the check **before**
`super().initial(...)`. Noted that doing it at the top of `post()` would
also close the hole, but leaves the guarantee resting on every future
handler remembering to call it, where `initial()` is structural. Test all
four shapes: JWT only, credential only, both, neither.

### 19.3 An anonymous redemption would still carry `session_id`, a user-scoped handle

C.3's frontend bullet said the redemption happens in
`darkProtocolService.proxyVaultOperation` and left it there. But that
function's existing signature is `(operation, payload, sessionId)` and it
sends `session_id` in the body alongside `authHeader()`'s bearer token —
and the server resolves that value as `GarlicSession.objects.filter(
session_id=session_id, user=user, ...)` in `_record_operation_traffic`.
**It is user-scoped.** Stripping the `Authorization` header alone would
therefore not make the request anonymous: the accounting path re-links it to
an account identity by a different route, defeating the same C.5 criterion
the mixed-credential rule protects.

Fixed by defining the anonymous redemption request explicitly — credential,
`operation`, sync-data-only `payload`, and nothing else: no bearer token, no
`session_id`, no other account-scoped handle. Traffic accounting simply does
not occur for these requests, which needs no server change
(`_record_operation_traffic` already returns early on a falsy `session_id`)
and is the correct outcome anyway: inventing an "anonymous" accounting
handle would recreate the correlation under a new name. Requires a
**wire-level** test asserting on the serialized request rather than the
function's arguments, since what matters is what leaves the machine.

### 19.4 A.5's own test list contradicted A.5's own prose, three sections apart

§17.3 (round 9) established that `isOnionSyncAvailable()` must be able to
AWAIT an in-flight bootstrap, because a mid-bootstrap snapshot makes
`prefer_onion` fall back to clearnet and `require_onion` fail closed during
normal startup. A.5's test list, a few dozen lines below and untouched since
round 5, still required that the same function "returns `false` while the
sidecar is still bootstrapping (any percentage short of 100)." Those cannot
both hold.

Root cause: "still bootstrapping" was being treated as ONE state when it is
two, and the resolution is to distinguish them rather than pick a side:
- **A bootstrap is in flight** (a tracked `start()` promise exists): await
  it, bounded by A.3's ~60s deadline, and answer from the settled outcome.
- **No bootstrap is in flight** (never started, deliberately stopped, or the
  last attempt already failed — `lastError` set, restart budget spent):
  return `false` immediately, without awaiting and without starting one as a
  side effect. A crashed sidecar must not hang a caller for 60s waiting on a
  promise that will never exist.

Both branches now have their own test requirements.

### 19.5 B.3 point 6's blanket "No hardcoding" contradicted point 5's packaged-hostname requirement

§15.4 (round 7) established that Android's Network Security Configuration is
packaged at build time and cannot name a runtime-discovered hostname, so the
cleartext exception must use a build-time deployment constant. Point 6, four
lines below, still said "**Onion address** from
`capabilities.anonymity.onion_address`, same as desktop. No hardcoding." —
which reads as forbidding exactly what point 5 requires.

Fixed by splitting point 6 into the two genuinely different values it was
conflating: the **runtime request target** (always from capabilities, never
hardcoded — rule unchanged) and the **hostname baked into
`network_security_config.xml`** (necessarily a compile-time per-flavour
deployment parameter, the same kind of thing the clearnet backend URL
already is, with point 5's runtime match-check as the safeguard). Also noted
the failure modes at both extremes: a build shipping without the exception
has no working onion sync at all on API 28+, and a build that "avoids
hardcoding" by widening cleartext globally is strictly worse than either.

### 19.6 The recurring failure mode on this PR, now named

Four rounds running, the most substantive findings have not been new bugs in
new code — they have been **contradictions between two places that describe
the same fact**, introduced when an earlier round fixed one place and not
the other:

| Round | What contradicted what |
|---|---|
| 9 (§17.4) | A stale round-count in one document, already propagated into a second |
| 10 (§18.4) | `start()`'s "returns current status" vs. the await-readiness rule — both written in round 9 |
| 10 (§18.1) | A scope note excluding "backup/restore" vs. its own rule naming bulk operations |
| 11 (§19.2) | A claimed DRF ordering vs. the actual shipped code |
| 11 (§19.4) | A.5's prose vs. A.5's own test list |
| 11 (§19.5) | B.3 point 5 vs. B.3 point 6 |

The lesson recorded in round 10 — "when a round changes a design fact in
more than one place, diff those places against each other before calling the
round done" — was correct but under-applied: it was read as being about the
places a round EDITS, when the real requirement is to search for every place
that RESTATES the changed fact, including ones the round never touched.
§19.4 and §19.5 are both cases where the contradicting text had not been
edited in rounds, and was found only because a reviewer read the section
end-to-end. Practical rule going forward: after changing a design fact in
these plans, grep for its distinctive terms across all three documents and
read every hit, rather than trusting that the sections touched this round
are the only ones that state it.

Targeted tests only, per the standing preference recorded in
[[feedback_targeted_testing]]: `unlockEnvelopeStore.test.js` (29 tests, 4 new
this round) plus the suites sharing its module surface —
`VaultContext.decoySession.test.jsx`, `VaultUnlockModal.test.jsx`,
`duressSignalService.test.js`, `sessionVaultCrypto.decoySession.test.js`,
`sessionVaultCrypto.exportWrappedDekRaw.test.js`,
`sessionVaultCrypto.salt.test.js`, `VaultDuressSetup.test.jsx`, and the three
sibling `VaultContext.*` suites. The one code fix was negative-controlled
before being trusted (disabling the guard fails all 4 new tests; restoration
verified byte-identical against a pre-edit backup). `eslint` clean on the
changed files. `markdownlint` (MD018/MD022/MD040) clean on all touched doc
files. The full frontend suite is CI's job, not this change's.

## 20. Implementation status — twelfth CodeRabbit review round (2026-08-28)

A twelfth `@coderabbitai full review` found 4 issues: 1 in shipped code, and
3 in `docs/onion-sync-transport-phases-2-4-plan.md` (still fully
unimplemented). Confirmed via the GraphQL review-threads API, not just the
pasted transcript, that all 4 were genuinely unresolved (`isResolved: false`)
and distinct from three OTHER CodeRabbit batches posted the same day that
rounds 9–11 had already closed — this PR now gets multiple review batches
per day, so date/thread-id verification matters more than it did earlier.

### 20.1 A decoy session's own vault UI outed the decoy the moment it rendered

`VaultUnlockModal.jsx`'s `runEnvelopeUnlock` installs the decoy DEK and
completes the unlock normally; `onUnlocked` then lets the dashboard render.
`VaultItemsSection` (`App.jsx`) reads the one shared, server-side item list
from `useVault()` and calls `decryptEnvelope` on every row — with no
decoy-session gate of any kind. A decoy DEK cannot decrypt anything sealed
under the real DEK, so every row rendered `"Decryption failed"` (and logged
a decrypt error per item) within moments of a decoy unlock succeeding — the
single most visible possible tell that a duress unlock is fake, defeating
the indistinguishability §11.5's write-refusal and §19's request/DOM/console
work were all built to protect.

This is the same read-side limitation §11.5 already named and deliberately
deferred ("giving reads a friendlier indicator... belongs with the
'believable decoy contents' work §7 already defers"). What changed: §11.5's
own compat table (§4) already sets an achievable floor below full believable
content — **"an empty decoy still beats no decoy"** — and the shipped code
did not clear even that floor; it rendered visibly broken, not empty.
Closing that specific gap does not require the deferred product decision
(what a believable decoy contains), only that a decoy session stop
attempting real decryption at all.

**First attempt, rejected before being applied:** gating `VaultContext.jsx`'s
exposed `items` (the single value every consumer reads) to `[]` during a
decoy session. Rejected upon checking it against the EXISTING test suite
first, not just against the new requirement: `VaultContext.decoySession.test.jsx`
(§16, §18.1) asserts `result.current.items` still reflects the real,
untouched row after a blocked `deleteItem`/`toggleFavorite`/`restoreBackup`
call precisely to prove no optimistic mutation slipped through the write
gate — six passing tests that a shared-`items` gate would have broken to fix
an unrelated read-side issue. Generalizes
[[feedback_verify_bot_review_findings]] point 5 (trace a fix forward to
every caller) one step further: an existing, already-passing TEST SUITE is a
caller too, and is cheaper to check against than to discover has broken
after the fact.

**Fix actually applied**, scoped to the one component CodeRabbit's own
trace showed is unconditionally rendered right after unlock
(`App.jsx`'s dashboard route): `VaultItemsSection` now derives a local
`visibleItems = isDecoySession() ? [] : items` (memoized on `items`, so the
array reference used for both the decrypt effect and the render stays
stable across renders — an unmemoized version was caught by
`react-hooks/exhaustive-deps` during verification, since a fresh `[]`
literal every render would otherwise re-trigger the decrypt effect on every
render) and decrypts/renders that instead of the raw `items` from context.
`VaultContext`'s own exported `items` — and every OTHER consumer of it — is
untouched. A decoy session now renders the existing, already-styled
`"No passwords saved yet"` empty state instead of a wall of decrypt
failures, with no decrypt attempt and no error logged.

**Deliberately not attempted, same as §11.5:** populating the decoy with
believable fake entries. That is still the separate §7 product decision;
this fix's scope is "empty, not broken," matching the plan's own documented
floor, nothing more.

**Not yet extended to:** `AdaptivePasswordDashboard.jsx` and
`SecurityDashboard.jsx`, which also read `items`/`decryptItem` from the same
context and are reachable via in-app navigation, not just the initial
dashboard render. CodeRabbit's finding traced only the automatic
post-unlock path (`VaultItemsSection`); these two were not cited and are
noted here as a known follow-up rather than folded into this fix silently.
`VaultItem.jsx`/`VaultItemCard.jsx`/`VaultItemDetail.jsx` were checked and
are not currently reachable from any route or parent component, so are out
of scope, not merely unaddressed.

New test file `VaultItemsSection.decoySession.test.jsx` (2 tests): a decoy
session renders the empty-vault state and never calls `decryptEnvelope`; a
real session decrypts and renders normally. Required exporting
`VaultItemsSection` as a named export (it was previously module-private) —
the only way to test it without instantiating all of `App.jsx`'s routing and
auth machinery, which has no existing test harness at all. This is additive
only; `App`'s existing default export and all current behavior are
unchanged.

### 20.2 The Tor control endpoint was never actually specified

A.3's "Authenticated control port" bullet requires `CookieAuthentication 1`
but never says what the control endpoint itself IS: `ControlPort` or
`ControlSocket`, bound where, allocated how, or discoverable from where. A
plan that fully specifies authenticating a connection to an endpoint it
never defines cannot actually be implemented as written — and the gap is
exactly the kind that matters here, since `ControlSocket` (a Unix domain
socket) silently does not exist on Windows, which `desktop/package.json`'s
`build.win` target ships to. Fixed: `ControlPort auto` (loopback-bound,
ephemeral — the same treatment, and the same collision reasoning, `SocksPort
auto` already gets two paragraphs above), read back and validated
loopback-only the same way `socksPort` already is, and added to `start()`'s
return value and `getStatus()` as `controlPort`. New test requirement:
concurrent sidecar instances get distinct control ports, and a non-loopback
control endpoint is never configured or reported.

### 20.3 The main process's own clearnet capability fetch had no transport requirement at all

A.4 documents `onionTransport.js` making its own clearnet GET to the
capabilities endpoint, carrying the same bearer `authToken` used for the
eventual `vault_sync` POST — but the very next bullet after it is "use
`http://`, not `https://`" for the ONION request, and nothing distinguished
the two. An implementer skimming both bullets together could reasonably
conclude the same weak-transport posture applies to the clearnet fetch,
which would send a live bearer token in the clear. Fixed by stating
explicitly that this fetch must be HTTPS-only, must validate certificates,
and must refuse (not follow) a downgrade redirect to `http://`, using the
same redirect-hardening approach A.4 already requires for the `vault_sync`
request itself, with a cross-reference forward to the specific bullet the
`http://` exception belongs to and does not extend from.

### 20.4 Orbot's config plugin queried package visibility, never service identity

B.3 point 3 required Android 11+ `<queries>` visibility for
`org.torproject.android`, which only lets this app confirm SOME installed
package declares Orbot's action — not that the package IS Orbot. An
implicit, action-only bind can be satisfied by any locally installed app
declaring the same action, which could then hand back an attacker-controlled
port this app would trust as Orbot's own SOCKS proxy, sitting directly in
the path of `vault_sync` traffic. Fixed: bind with an explicit
`setPackage("org.torproject.android")` target rather than an implicit
action-only intent, and verify the bound `ComponentName`'s package before
trusting anything it returns (including the discovered port point 5
already reads). New test requirement: a second, locally-installed app
declaring the same action must never be treated as Orbot, and an
already-occupied local port must be handled as "unavailable," not silently
connected to.

Verified via `gh api repos/Rajarshi1-source/Modern_Password_Manager01/pulls/489/comments`
(date-filtered) and the GraphQL `reviewThreads` API (resolution-filtered)
that only CodeRabbit posted this round and that all 4 threads were
genuinely open; no Codex or Greptile activity — Codex's last comment on this
PR is still the 2026-08-25 usage-limit notice, and Greptile remains absent
from every commenter list checked across all twelve rounds. Targeted tests:
new `VaultItemsSection.decoySession.test.jsx` (2 tests) plus the suites
sharing `sessionVaultCrypto`'s decoy-session surface —
`VaultContext.decoySession.test.jsx`, `VaultUnlockModal.test.jsx`,
`sessionVaultCrypto.decoySession.test.js` — 38 tests total, all passing.
`eslint` clean on `App.jsx` and the new test file (an initial version
tripped `react-hooks/exhaustive-deps`, fixed with `useMemo` before being
counted as clean — see §20.1). `markdownlint` (MD040/MD018) clean on the one
touched doc file. No change was needed in
`docs/privacy-features-gap-remediation-plan.md` this round: all 3 doc
findings are implementation detail nested under sections that document's own
Phase 2/3 summary already defers to ("See A.4 for the full schema and the
required tests"), not changes to a design fact the summary itself states.

## 20. Implementation status — thirteenth review round: Greptile + CodeRabbit (2026-08-28)

The first round on this PR with findings from TWO reviewers: Greptile raised
2 P1 security findings (and failed its own merge gate at confidence 1/5),
CodeRabbit raised 7. Both of Greptile's, and one of CodeRabbit's, are the
SAME class of defect this PR keeps producing — a guard applied to one path
and not its sibling (§19.6) — and one of them invalidates a security
justification I wrote myself two rounds earlier.

### 20.1 The duress recovery form was a password-classification oracle — Greptile P1, and my own round-10 reasoning was wrong

`VaultDuressSetup`'s "Recover unregistered alarm" form produced three
visibly distinct outcomes for a submitted password: the real vault password
got *"That opened the real vault, not the decoy slot"*, a valid decoy
password got a success message, and anything else got *"Incorrect decoy
password."* Anyone who can operate an authenticated session can therefore
type a password into this form and learn which of the three it is.

**Why this is severe, and why my earlier justification was wrong.** §12.2
introduced that specific wording with an explicit rationale, quoted from the
code comment: *"this settings screen already presupposes the user knows
about and is managing the duress feature, so telling them 'that opened the
real vault' is not a signal that helps a coercer."* That reasoning assumed
only the legitimate user ever reaches this screen. **It does not hold.**
Reaching `/security/vault-duress` requires only an AUTHENTICATED session —
and a coerced unlock produces exactly that, decoy or not. So a coercer who
has just forced an unlock can navigate here, type the password they were
handed, and be told by the application itself that it was a decoy. That is
precisely the disclosure the entire feature exists to prevent, delivered by
the one screen built to support it.

**Fix:** one outcome for all three password classes. `open()` is still
called (recovery genuinely needs the token from slot 1), but a
`WrongPasswordError` is no longer treated as an error at all — it is one of
the indistinguishable outcomes — and a real-slot open no longer gets its
own branch. The single message is worded to stay truthful in every case:
*"If that was your decoy password, its alarm is now registered..."*, plus an
explicit note that the message is the same whichever password was entered,
so the legitimate user is not misled into thinking it confirms anything.
The `catch` that remains handles only genuine operational faults
(registration request failed, envelope unreadable), which are unreachable
for a merely wrong or real password and say nothing about slots.

New test asserts the security property directly: decoy, real, and wrong
passwords all produce **byte-identical** rendered output, compared on the
serialized container rather than hand-picked strings, so a future
contributor reintroducing any branch fails it. Negative-controlled —
restoring the classifying branch fails 3 tests.

### 20.2 `/vault/dashboard` rendered the real vault during a decoy session — Greptile P1 and CodeRabbit, same finding

§19-era work added the decoy display gate to `VaultItemsSection`, the
`/vault` list. It did not add it to `VaultDashboardRoute`, which passes
`useVault().items` straight into `VaultDashboard`. A decoy session
navigating to `/vault/dashboard` therefore rendered the real inventory —
leaking real item metadata AND outing the decoy, since none of it decrypts
under the decoy DEK.

This is the third occurrence of the identical pattern (§16.1: gated
`encryptItem`, missed `deleteItem`/`toggleFavorite`; §18.1: missed
`restoreBackup`; now: gated one display surface, missed the other).

**Fix, deliberately structural rather than a second copy of the check:** a
shared `useDisplaySafeItems(items)` hook in `App.jsx`, used by BOTH
surfaces, carrying the rationale in one place and stating that any new
surface rendering `useVault().items` must go through it. Adding the gate
inline in `VaultDashboardRoute` would have fixed this instance while
leaving the next one exactly as likely.

CodeRabbit additionally caught a real defect in the ORIGINAL gate that the
copy would have propagated: `useMemo(..., [items])` omitted the decoy flag
from its dependency array, so a session flipping decoy state without
`items` changing identity would keep serving the memoized real list. The
shared hook reads the flag on every render (it is a module boolean — free)
and includes it in the deps.

`VaultDashboardRoute` is now exported for the same reason `VaultItemsSection`
already was: this gate needs a direct regression test. 3 new tests assert
the decoy case receives `[]` (and that no real identifier appears anywhere
in the props), the real case still receives the full list, and `undefined`
is still normalised to `[]`. Negative-controlled — and notably, breaking the
shared hook fails the tests for BOTH surfaces, which is the point of it
being shared.

### 20.3 `parseSlotPayload` let a raw `atob` DOMException escape as a second error contract

`fromB64` calls `atob`, which throws `InvalidCharacterError` (a
`DOMException`) for input that is not valid base64 — not this module's
`MalformedSlotPayloadError`. So "the stored payload is corrupt" left
`open()` as two different error types depending on HOW it was corrupt.

Impact is narrow but real. `VaultUnlockModal`'s fallback tags ANY
non-`WrongPasswordError` as `envelopeUnusable`, so its recovery path was
never broken — which is exactly why this could sit unnoticed. But
`VaultDuressSetup`'s recovery form surfaces `err.message` directly, so a
user would have seen a raw *"Failed to execute 'atob' on 'Window'..."*
string. Reachability is limited to a hand-crafted or externally corrupted
envelope, since `provision()`/`setDecoySlot()` only ever write `toB64`
output — this is hardening, in the same category as §19.1's `saltB64`
guard, not a live bug. Normalized to `MalformedSlotPayloadError`; the new
test asserts both the type AND that the message does not mention `atob`.

### 20.4 A.3's lifecycle contract omitted `controlPort` that A.3's own body requires

The `start()`/`getStatus()` signature block at the top of A.3 still read
`Promise<{ socksPort }>` / `{ state, bootstrapPercent, socksPort,
lastError }`, while the requirements below it — written one round earlier —
explicitly say to "add it to `start()`'s return value and `getStatus()` as
`controlPort`". Same self-contradiction pattern as §19.4/§19.5, in the same
section, one round later. Added `controlPort` to both, and specified what
the port fields hold when nothing is running (`null`, never a stale value
from a previous run that a caller could dial into nothing).

### 20.5 A single shared `DataDirectory` makes A.3's own concurrent-instance test impossible

A.3 says each sidecar gets its `DataDirectory` at
`PathUtils.getUserDataPath()/tor` — one fixed path — while also (again,
added one round earlier) requiring a test that starts **two sidecars
concurrently**. Tor takes an exclusive lock on a `lock` file inside its
`DataDirectory`, and a second process pointed at the same directory refuses
to start; distinct `ControlPort`/`SocksPort` values do not isolate it,
because the lock is on the directory. The two requirements cannot both be
satisfied.

Fixed to allocate a per-instance child directory
(`.../tor/<instanceId>`), keep that instance's control cookie inside it,
and clean it up on a successful `stop()`. Kept the owner-only permission
requirements (POSIX mode plus the Windows DACL) and noted that the
concurrency test has to run against the real bundled binary, since a mocked
test cannot exercise a lock the real Tor process takes.

### 20.6 The `vault_sync` item allowlist was wrong for the second consecutive round

§16.3 added `expected_sync_version` after finding the allowlist omitted a
field the endpoint really accepts. This round: it also omits `last_used_at`,
which appears in `VaultItemSerializer.fields` and NOT in its
`read_only_fields`, so it is genuinely writable (model:
`null=True, blank=True`, hence "or null"). No current producer sends it, so
nothing is broken today — but a serializer-shaped item would be rejected at
the IPC boundary for a field the server accepts, and the failure would look
like a transport bug.

Added, along with the observation that matters more than the field itself:
**the allowlist has now been wrong twice because it was derived by reading
the serializer rather than mechanically from `fields` minus
`read_only_fields`.** The plan now says to derive it that way.

### 20.7 The `require_onion` acceptance criterion contradicted A.5's await rule

A.8 said `require_onion` "fails closed on desktop when bootstrap has not
completed" — which covers the normal in-flight state that §19.4 established
must be AWAITED, not failed. As written it would make the first sync after
every launch fail during ordinary startup: the precise bug A.5's await
requirement exists to prevent. Narrowed to failure only when bootstrap
failed, hit the startup deadline, or was never started.

### 20.8 Two stale decoy-display claims found by applying §19.6's own rule

CodeRabbit flagged that `VaultDuressSetup`'s "Know the limits" notice still
described the pre-§20.2 behaviour ("shows your real vault's item list with
each entry failing to open"). Correct — and grepping for that claim per
§19.6's rule found a SECOND copy CodeRabbit did not flag, in the component's
own module docstring, plus a third in §4's live test guidance in this plan.
All three now describe the actual behaviour: a decoy session shows an EMPTY
vault. All three also keep the warning that empty is not the same as
believable — someone who knows the account is not empty may still find it
suspicious, and populating a plausible decoy remains §7's product work.

Historical changelog text in §10.3, §11.5, and §11.7 still describes the old
behaviour and is deliberately LEFT AS-IS: those sections are records of what
was true in those rounds, and rewriting them would destroy the audit trail
this document exists to keep. Only live guidance was corrected — the same
distinction applied in earlier rounds.

Targeted tests only, per [[feedback_targeted_testing]]: the 4 files covering
the changed paths (`VaultDuressSetup.test.jsx`,
`VaultDashboardRoute.decoySession.test.jsx` (new),
`VaultItemsSection.decoySession.test.jsx`, `unlockEnvelopeStore.test.js`) —
44 tests, plus the wider decoy/envelope suite as a regression sweep. All
three code fixes were negative-controlled before being trusted, and every
restoration verified byte-identical against a pre-edit backup. `eslint`
clean on the changed files; `markdownlint` (MD018/MD022/MD040) clean on all
touched docs.

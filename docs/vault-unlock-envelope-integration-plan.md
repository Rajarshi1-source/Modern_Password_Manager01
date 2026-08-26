# Plan — Wire the two-slot envelope into `VaultUnlockModal` (§4.2 carry-over)

**Implemented in PR #489, then hardened across four CodeRabbit review rounds
(§9, §10, §11, §12) — read all four before relying on §3's original design as
the literal shipped behavior. §11.5 in particular is a real data-corruption
fix, not a cosmetic one.**

Deferred from PR #486 (`docs/privacy-features-gap-remediation-plan.md` §4.2,
§5 "Not delivered"). PR #486 shipped the backend and the service layer; the
main unlock modal was left on the single-password path because provisioning
the two-slot blob "deserves its own PR". This is that PR.

**Scope: one PR.** No dependency on the onion-transport work
(`docs/onion-sync-transport-phases-2-4-plan.md`); the two can land in either
order.

---

## 0. Verdict table — what exists today, verified by reading the code

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
export async function setDecoySlot({ userId, vaultPassword, decoyPassword, decoyDek }): Promise<{ duressToken: string }>

// Try a password against both slots. Thin wrapper over decode() returning the
// parsed payload plus slotIndex.
export async function open({ userId, password }): Promise<{ slotIndex, payload }>
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
3. On success → `sessionVaultCrypto.installRawDek(payload.dek, payload.salt, userId)`.
4. `duressSignalService.reportUnlockForSlot(getAccessToken(), slotIndex, payload)`
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
2. Client generates a fresh decoy DEK and calls
   `unlockEnvelopeStore.setDecoySlot(...)`.
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

---

## 4. Tests

**Unit — `frontend/src/services/hiddenVault/__tests__/unlockEnvelopeStore.test.js` (new, vitest)**
- Real password → `slotIndex === 0` and the real DEK.
- Decoy password → `slotIndex === 1` and the decoy DEK plus `__duress_signal`.
- Wrong password → `WrongPasswordError`.
- `provision()` with no decoy: the blob is exactly `tierBytes(tier)` long, and
  slot 1 decrypts under no known password — the no-tell property from §3.2.
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
  modal's own DOM: it does NOT extend to the vault dashboard the app renders
  next, which — per §7 and the known limitation already recorded on the
  duress-setup screen — shows the real item list with each entry failing to
  decrypt under the decoy DEK. That is a materially different, larger
  problem (believable decoy contents) and is out of scope here; do not
  read this bullet as claiming it is solved.
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

- [ ] Vault password opens slot 0; decoy password opens slot 1; both install a
      working session DEK and the vault renders.
- [ ] No master or decoy password appears in any request body on the unlock
      path (contract test).
- [ ] Slot-0 and slot-1 unlocks are indistinguishable in endpoint, request byte
      length, log output, and `VaultUnlockModal`'s own rendered DOM
      (explicitly NOT the vault dashboard rendered after unlock — see §7 and
      the duress-setup screen's own limitation notice for why that is a
      separate, unsolved problem).
- [ ] A decoy unlock creates a `DuressEvent`; a normal unlock does not.
- [ ] An existing OAuth user with a wrapped DEK and no envelope is upgraded
      transparently on their next unlock, and a failed upgrade does not block
      the unlock.
- [ ] Slot 1 of a no-decoy blob is indistinguishable from a configured one.
- [ ] Measured unlock p50/p95 recorded in the PR description; a Web Worker
      landed in this PR if p95 > ~1.5 s.
- [ ] Argon2 parameters unchanged from the `hiddenVaultEnvelope.js` defaults.

---

## 6. Risks

| Risk | Mitigation |
|---|---|
| Double Argon2id makes unlock feel broken on low-end devices | §3.7 — measure, Worker if needed, never weaken params |
| Losing OR corrupting `vaultUnlockEnvelope:<userId>` locks the user out | It never becomes the only copy: `setupVaultPassword`'s wrapped record is still written and `unlockWithVaultPassword` still works. A MISSING envelope always fell back to the legacy path (`upgrade` mode). A PRESENT-but-corrupt one (bad base64, truncated write, `MalformedBlobError`) did NOT originally — `hasEnvelope()` only checks for a value, not that it decodes. **Fixed in §9.1**: `runEnvelopeUnlockWithFallback()` now falls back to `upgrade` mode on any non-`WrongPasswordError` open failure, which also self-heals by re-provisioning a fresh envelope |
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
is actually true and tested — the unlock REQUEST is indistinguishable
(same endpoint, shape, and timing; verified by the DOM-equality test in
§9.1's own test suite) — while pointing the reader at the limitation notice
for what appears on screen afterward, rather than asserting something the
very next paragraph disproves. No test added — this was a copy-only fix and
CodeRabbit's own finding did not ask for coverage here, unlike the other
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

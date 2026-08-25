# Plan — Wire the two-slot envelope into `VaultUnlockModal` (§4.2 carry-over)

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

```
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

#486 §5 deferred this because it "needs the two-slot blob to be provisioned at
vault setup — a migration path for existing vaults". Verified against the code,
that migration is **device-local, not server-side**:

```
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

This is a real reduction in scope versus what #486 §5 assumed, and it is why
this fits in one PR.

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

```
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

```
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
#486 fixed in `setupVaultPassword`.

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
app. It belongs in the existing duress settings area (route `/security/duress`,
which `StegoVaultDashboard.jsx:447` already links to):

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
- **Indistinguishability:** rendered DOM after a slot-0 unlock and after a
  slot-1 unlock is identical. Assert on the serialized container, not on
  hand-picked strings — a hand-picked assertion will not catch the next person
  who adds a duress-conditional class name.
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
      length, rendered DOM, and log output.
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
| Losing `vaultUnlockEnvelope:<userId>` locks the user out | It never becomes the only copy: `setupVaultPassword`'s wrapped record is still written and `unlockWithVaultPassword` still works. Envelope-missing falls back to the legacy path — that IS `upgrade` mode |
| A future contributor short-circuits `decode()` for speed | Comment at the call site and above the attempts loop, plus the DOM-equality test |
| Decoy DEK encrypts nothing, so the decoy vault looks empty and unconvincing | Out of scope here — populating a believable decoy is a product decision (§7). An empty decoy still beats no decoy, but UI copy must not claim it is convincing |
| Registering the signal token before the blob is saved | §3.6 step 3 ordering — the #486 §10.3 lesson |
| `installRawDek` drifts from `unlockWithVaultPassword`'s tail | Keep them adjacent in the file with a cross-reference comment; the generation-check assertion is part of the unit tests |

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

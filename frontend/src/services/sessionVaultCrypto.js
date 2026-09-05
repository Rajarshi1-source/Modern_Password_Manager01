/**
 * sessionVaultCrypto - In-memory AES-GCM encryption for vault items during a session
 *
 * Purpose: replace plaintext `JSON.stringify(...)` storage in the "Add Password"
 * form with real client-side encryption. The master password never leaves the
 * client and the derived CryptoKey lives only in module memory (cleared on
 * logout / tab close).
 *
 * Two init paths:
 *   (A) `initSessionKeyFromPassword(password, userId)` - password-login users.
 *       Derives the session DEK directly from the master password + per-user
 *       salt via PBKDF2.
 *
 *   (B) Wrapped-DEK flow for OAuth users (no master password available):
 *       `setupVaultPassword(vaultPassword, userId)` creates a random DEK and
 *       stores a copy of it wrapped with a KEK derived from `vaultPassword`.
 *       On subsequent sessions `unlockWithVaultPassword(vaultPassword, userId)`
 *       unwraps the DEK back into module memory. `hasWrappedKey(userId)` tells
 *       the UI whether to show a setup or an unlock prompt.
 *
 *       (C) `../hiddenVault/unlockEnvelopeStore.js` layers a two-slot duress
 *       envelope on top of this same DEK — see its own header comment and
 *       docs/vault-unlock-envelope-integration-plan.md. `installRawDek`,
 *       `exportSessionDekRaw`, and `exportWrappedDekRaw` below exist only to
 *       move that DEK's raw bytes into and out of that envelope; they are not
 *       a third independent key.
 *
 * Item payload format (JSON string):
 *   { v: 'svc-gcm-1', iv: base64, ct: base64, salt: base64 }
 *
 * Cross-device portability: the per-user salt is device-local (localStorage,
 * never sent to the server), so path (A)'s session key only opens items sealed
 * on THIS device. `decryptItem` therefore keys off the envelope's OWN `salt`
 * field rather than the session salt, re-deriving (and memoizing) a key per
 * distinct salt it encounters — see `keyForSalt`. Without this, items written
 * on another device, or on this one before site data was cleared, render as
 * "Decryption failed" despite a correct master password.
 *
 * Write path: v2 no longer takes new writes when v3 is available —
 * `vaultEnvelope.encryptEnvelope` prefers `sessionVaultCryptoV3`, whose DEK is
 * server-wrapped and has no salt-portability problem at all. v2 `encryptItem`
 * remains the fallback for OAuth sessions and for v3-degraded logins.
 *
 * Backward compatibility: `decryptItem` detects legacy plaintext JSON payloads
 * (no `v` field) and returns them as-is so existing vault rows still render.
 */

const PBKDF2_ITERATIONS = 310000;
const PAYLOAD_VERSION = 'svc-gcm-1';
const WRAPPED_VERSION = 'svc-wrap-1';
const USER_SALT_STORAGE_KEY = 'vaultKeySalt';
const WRAPPED_DEK_STORAGE_KEY = 'vaultWrappedDEK';

let sessionKey = null;
let sessionSaltB64 = null;
// True only when `installRawDek` installed the DECOY slot's DEK (path C).
// `encryptItem` refuses to write while this is set -- see its own comment.
// Without this, a new item added during a decoy session would be encrypted
// under the decoy DEK but stamped with the REAL slot's salt (setDecoySlot
// reuses it, see unlockEnvelopeStore.js), and the real session would later
// try to open it with the REAL DEK because `keyForSalt` fast-paths on a
// matching salt -- an AES-GCM auth failure that permanently corrupts a row
// in the one shared, server-side item list. Every OTHER session-establishing
// function (`initSessionKeyFromPassword`, `setupVaultPassword`,
// `unlockWithVaultPassword`, `clearSessionKey`) explicitly resets this to
// `false` next to its own `sessionKey` assignment, so a stale `true` from an
// earlier decoy session can never survive into a later real one that
// installs a session key WITHOUT going through `installRawDek` again.
let sessionIsDecoy = false;
// Retained ONLY for path (A) (direct derivation), so `decryptItem` can derive a
// key for an envelope written under a DIFFERENT salt than this device's -- see
// `keyForSalt`. This does not widen the master password's blast radius: the
// module already held `sessionKey`, derived from this exact password, for the
// whole session, and both are dropped together in `clearSessionKey`. Path (B)
// (wrapped DEK) never sets this -- it has no password to retain.
let sessionPassword = null;
// Memoized foreign-salt keys: `saltB64 -> Promise<CryptoKey>`.
//
// Promises, not resolved keys, on purpose. `decryptItem` is called concurrently
// (App.jsx maps the vault list through `Promise.all`), so caching only the
// settled key would let N items sharing one foreign salt each kick off their own
// PBKDF2 run before the first finished -- N * 310 000 iterations instead of one.
//
// Never holds `sessionSaltB64`; that case short-circuits to `sessionKey`.
const foreignSaltKeys = new Map();

// Bumped by `clearSessionKey` and by every async session-establishing call
// (`initSessionKeyFromPassword`, `setupVaultPassword`, `unlockWithVaultPassword`)
// before their first await. Each such call captures its own value and only
// commits `sessionKey`/`sessionSaltB64`/`sessionPassword` if the generation is
// still current when its derivation resolves. Without this, a `clearSessionKey()`
// (logout) that lands while one of those derivations is still in flight would
// have its result silently overwritten a moment later by the stale call --
// resurrecting a session the user just logged out of. The same guard also
// makes a newer call always win over an older one that is still resolving
// (e.g. a fast account switch), rather than whichever happens to settle last.
let sessionGeneration = 0;

const toB64 = (bytes) => {
  let binary = '';
  const arr = bytes instanceof Uint8Array ? bytes : new Uint8Array(bytes);
  for (let i = 0; i < arr.byteLength; i++) {
    binary += String.fromCharCode(arr[i]);
  }
  return btoa(binary);
};

const fromB64 = (b64) => {
  const binary = atob(b64);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) {
    bytes[i] = binary.charCodeAt(i);
  }
  return bytes;
};

const saltStorageKey = (userId) =>
  userId ? `${USER_SALT_STORAGE_KEY}:${userId}` : USER_SALT_STORAGE_KEY;

const wrappedStorageKey = (userId) =>
  userId ? `${WRAPPED_DEK_STORAGE_KEY}:${userId}` : WRAPPED_DEK_STORAGE_KEY;

/**
 * Read this device's per-user salt, minting one on first use.
 *
 * Minting is correct for a genuinely new device and unavoidable for path (A)
 * (there is nothing server-side to fetch). What it is NOT is a signal that the
 * user has no data: a returning user whose site data was cleared takes the same
 * branch, and every item they already own was sealed under the salt that just
 * disappeared.
 *
 * That used to be silent data loss. It no longer is — `decryptItem` recovers
 * those items from each envelope's own `salt` field (see `keyForSalt`) — so the
 * mint is now a recoverable event rather than a terminal one. It is still worth
 * a log line: it is the fingerprint of a cleared/new device, and a mint that
 * appears on a device the user has been using is the one shape here that would
 * indicate something genuinely wrong (evicted localStorage, a changed userId
 * key). Without this, the only evidence was a vault full of items that quietly
 * needed re-derivation.
 */
export const getOrCreateUserSalt = (userId) => {
  const storageKey = saltStorageKey(userId);
  let salt = localStorage.getItem(storageKey);
  if (!salt) {
    const raw = window.crypto.getRandomValues(new Uint8Array(16));
    salt = toB64(raw);
    localStorage.setItem(storageKey, salt);
    // eslint-disable-next-line no-console
    console.info(
      'sessionVaultCrypto: minted a new device-local vault salt. Existing items '
      + 'sealed under a previous salt stay readable — they are re-derived from '
      + 'each envelope\'s own salt.',
    );
  }
  return salt;
};

const deriveDirectKey = async (password, saltB64) => {
  const enc = new TextEncoder();
  const keyMaterial = await window.crypto.subtle.importKey(
    'raw',
    enc.encode(password),
    { name: 'PBKDF2' },
    false,
    ['deriveKey']
  );
  return window.crypto.subtle.deriveKey(
    {
      name: 'PBKDF2',
      salt: fromB64(saltB64),
      iterations: PBKDF2_ITERATIONS,
      hash: 'SHA-256',
    },
    keyMaterial,
    { name: 'AES-GCM', length: 256 },
    false,
    ['encrypt', 'decrypt']
  );
};

// Derive a KEK (extractable: false, usages: wrapKey/unwrapKey) for wrapping
// the random DEK under the user's vault password.
const deriveKEK = async (password, saltB64) => {
  const enc = new TextEncoder();
  const keyMaterial = await window.crypto.subtle.importKey(
    'raw',
    enc.encode(password),
    { name: 'PBKDF2' },
    false,
    ['deriveKey']
  );
  return window.crypto.subtle.deriveKey(
    {
      name: 'PBKDF2',
      salt: fromB64(saltB64),
      iterations: PBKDF2_ITERATIONS,
      hash: 'SHA-256',
    },
    keyMaterial,
    { name: 'AES-GCM', length: 256 },
    false,
    ['wrapKey', 'unwrapKey']
  );
};

// ----------------------------------------------------------------------------
// Path (A): password-login users — direct derivation from the master password.
// ----------------------------------------------------------------------------

/**
 * Initialize the session vault key from the master password.
 * Must be called after successful password-based login/signup.
 */
export const initSessionKeyFromPassword = async (password, userId) => {
  if (!password) throw new Error('initSessionKeyFromPassword: password required');
  const generation = ++sessionGeneration;
  const saltB64 = getOrCreateUserSalt(userId);
  const key = await deriveDirectKey(password, saltB64);
  if (generation !== sessionGeneration) {
    // Superseded by `clearSessionKey()` or a newer init while this was
    // pending -- see `sessionGeneration`. Do not resurrect/clobber.
    throw new Error('Vault session initialization was superseded by a newer request.');
  }
  // Assign only after the derivation resolves, so a failed init leaves the
  // previous session state intact rather than half-replaced.
  sessionSaltB64 = saltB64;
  sessionKey = key;
  sessionPassword = password;
  // Path (A) never installs a decoy DEK -- clear a stale flag from a PRIOR
  // decoy session that never went through clearSessionKey(), so a genuine
  // real session installed after one doesn't inherit encryptItem's write
  // refusal. See sessionIsDecoy's own comment.
  sessionIsDecoy = false;
  // A re-init (different account, or the same one after a password change)
  // invalidates every memoized key -- they were derived from the OLD password.
  foreignSaltKeys.clear();
};

// ----------------------------------------------------------------------------
// Path (B): wrapped-DEK flow for OAuth users.
// ----------------------------------------------------------------------------

/**
 * Returns true if a wrapped DEK already exists for `userId`. The UI uses this
 * to decide between a "set up a vault password" flow and an "unlock vault"
 * flow on subsequent logins.
 */
export const hasWrappedKey = (userId) => {
  if (!userId) return false;
  return localStorage.getItem(wrappedStorageKey(userId)) !== null;
};

/**
 * First-time setup for an OAuth account: generates a fresh random DEK,
 * wraps it under a KEK derived from `vaultPassword`, persists the wrapped
 * DEK in localStorage, and installs the DEK as the current session key.
 */
export const setupVaultPassword = async (vaultPassword, userId) => {
  if (!vaultPassword || vaultPassword.length < 8) {
    throw new Error('Vault password must be at least 8 characters.');
  }
  if (!userId) throw new Error('setupVaultPassword: userId required');

  const generation = ++sessionGeneration;
  const saltB64 = getOrCreateUserSalt(userId);
  const kek = await deriveKEK(vaultPassword, saltB64);

  // Generate a random DEK. Extractable so we can wrap it now, but it never
  // leaves this module in cleartext after this function returns.
  const dek = await window.crypto.subtle.generateKey(
    { name: 'AES-GCM', length: 256 },
    true,
    ['encrypt', 'decrypt']
  );

  const iv = window.crypto.getRandomValues(new Uint8Array(12));
  const wrapped = await window.crypto.subtle.wrapKey('raw', dek, kek, {
    name: 'AES-GCM',
    iv,
  });

  const record = {
    v: WRAPPED_VERSION,
    iv: toB64(iv),
    wrapped: toB64(new Uint8Array(wrapped)),
    salt: saltB64,
  };

  if (generation !== sessionGeneration) {
    // See `initSessionKeyFromPassword`. Checked BEFORE the localStorage
    // write (moved here in review round 2): persisting unconditionally let a
    // stale call's record win the write race against a NEWER, already-
    // completed setupVaultPassword call whenever the stale one happened to
    // finish writing last -- overwriting the newer password's record with
    // the older one's. The user would then be locked out with the password
    // they just set, because the persisted blob no longer matched it.
    throw new Error('Vault session initialization was superseded by a newer request.');
  }
  localStorage.setItem(wrappedStorageKey(userId), JSON.stringify(record));
  sessionSaltB64 = saltB64;
  sessionKey = dek;
  // Path (B) installs a DEK, not a password-derived key: there is nothing to
  // derive foreign-salt keys FROM, so drop any path-(A) leftovers rather than
  // letting `keyForSalt` derive with a password that doesn't match this session.
  sessionPassword = null;
  // See initSessionKeyFromPassword -- this is the freshly-generated REAL DEK,
  // never a decoy one, so any stale flag from an earlier decoy session must
  // not survive into it.
  sessionIsDecoy = false;
  foreignSaltKeys.clear();
};

/**
 * Derive the KEK from `vaultPassword` and unwrap `record`'s wrapped DEK.
 * Shared by `unlockWithVaultPassword` (needs a non-extractable key, since it
 * becomes the live session key) and `exportWrappedDekRaw` (needs the same
 * DEK as extractable raw bytes) below -- `extractable` is the only thing
 * that differs between the two callers, so the unwrap parameters
 * (algorithm, key length, the canonical wrong-password error) can no longer
 * drift out of sync between them the way a hand-maintained "keep these two
 * in sync" comment could not actually guarantee.
 */
const unwrapDek = async (vaultPassword, record, extractable) => {
  const kek = await deriveKEK(vaultPassword, record.salt);
  try {
    return await window.crypto.subtle.unwrapKey(
      'raw',
      fromB64(record.wrapped),
      kek,
      { name: 'AES-GCM', iv: fromB64(record.iv) },
      { name: 'AES-GCM', length: 256 },
      extractable,
      ['encrypt', 'decrypt']
    );
  } catch {
    // AES-GCM unwrap failure is the canonical "wrong password" signal, for
    // both callers.
    throw new Error('Incorrect vault password.');
  }
};

/**
 * Load and validate the path (B) wrapped-DEK record for `userId`.
 *
 * Shared by `unlockWithVaultPassword` and `exportWrappedDekRaw`, which read
 * the SAME record: one copy of the storage key, the parse, and the version
 * check, so a later record-format change cannot be applied to one caller and
 * forgotten in the other. Purely synchronous — callers that reserve a session
 * generation must still do so AFTER this returns and BEFORE any await, which
 * is the ordering `unlockWithVaultPassword` documents below.
 */
const loadWrappedRecord = (userId, fnName) => {
  if (!userId) throw new Error(`${fnName}: userId required`);
  const raw = localStorage.getItem(wrappedStorageKey(userId));
  if (!raw) throw new Error('No vault key has been set up for this account.');

  let record;
  try {
    record = JSON.parse(raw);
  } catch {
    throw new Error('Vault key record is corrupt. Please reset the vault.');
  }
  if (!record || record.v !== WRAPPED_VERSION) {
    throw new Error('Unsupported vault key record version.');
  }
  return record;
};

/**
 * Unlock an existing wrapped DEK using the user's vault password. Installs
 * the unwrapped DEK as the current session key. Throws if the password is
 * wrong or the stored record is missing/corrupt.
 */
export const unlockWithVaultPassword = async (vaultPassword, userId) => {
  const record = loadWrappedRecord(userId, 'unlockWithVaultPassword');

  // Reserved AFTER the synchronous validation above (so a record that fails
  // to even parse never bumps this) and BEFORE the slow unwrap step below --
  // see initSessionKeyFromPassword for why the position matters.
  const generation = ++sessionGeneration;
  const dek = await unwrapDek(vaultPassword, record, false);
  if (generation !== sessionGeneration) {
    // See `initSessionKeyFromPassword`.
    throw new Error('Vault session initialization was superseded by a newer request.');
  }
  sessionSaltB64 = record.salt;
  sessionKey = dek;
  // See `setupVaultPassword` — path (B) has no password to memoize against.
  sessionPassword = null;
  // See initSessionKeyFromPassword -- this is the legacy wrapped-DEK record's
  // REAL key, never a decoy one.
  sessionIsDecoy = false;
  foreignSaltKeys.clear();
};

/**
 * Remove the wrapped DEK for `userId`. Destructive: items encrypted under
 * the old DEK become unreadable. Intended for "reset vault" flows.
 */
export const clearWrappedKey = (userId) => {
  if (!userId) return;
  localStorage.removeItem(wrappedStorageKey(userId));
};

/**
 * Re-derive the path (B) wrapped DEK as EXTRACTABLE raw bytes, without
 * installing it as the session key.
 *
 * `unlockWithVaultPassword` above unwraps the same record but deliberately
 * installs a NON-extractable key (`extractable: false` in its `unwrapKey`
 * call) -- raw key material should not be exportable for the lifetime of a
 * normal session. Provisioning the hidden-vault envelope
 * (docs/vault-unlock-envelope-integration-plan.md §3.4 "upgrade" path) needs
 * the opposite for one instant: the raw bytes, so the SAME DEK this record
 * already protects can also be sealed into envelope slot 0. Rather than
 * weaken `unlockWithVaultPassword`'s key for every caller, this does a
 * second, independent unwrap via the shared `unwrapDek` helper above with
 * `extractable: true` -- the unwrap parameters themselves can no longer
 * drift between the two callers, since there is only one copy of them.
 *
 * Does NOT touch module session state (`sessionKey` etc.) -- call
 * `unlockWithVaultPassword` separately to actually unlock the session; this
 * is a side channel for provisioning only.
 */
export const exportWrappedDekRaw = async (vaultPassword, userId) => {
  const record = loadWrappedRecord(userId, 'exportWrappedDekRaw');

  const dek = await unwrapDek(vaultPassword, record, true);
  const rawDek = await window.crypto.subtle.exportKey('raw', dek);
  return { dekBytes: new Uint8Array(rawDek), saltB64: record.salt };
};

/**
 * Export the CURRENT in-memory session DEK as raw bytes, if it is
 * extractable.
 *
 * Only the fresh DEK `setupVaultPassword` just generated is extractable --
 * `unlockWithVaultPassword` and `installRawDek` (below) both install
 * NON-extractable keys, keeping raw key material out of reach for the
 * lifetime of a normal session. So this is meant to be called immediately
 * after `setupVaultPassword` resolves, to seed the hidden-vault envelope
 * with the SAME key it just created — not as a general-purpose export. It
 * throws for any other session shape rather than silently returning nothing.
 */
export const exportSessionDekRaw = async () => {
  if (!sessionKey) {
    throw new Error('exportSessionDekRaw: no session key installed');
  }
  let raw;
  try {
    raw = await window.crypto.subtle.exportKey('raw', sessionKey);
  } catch {
    throw new Error('exportSessionDekRaw: current session key is not extractable.');
  }
  return new Uint8Array(raw);
};

/**
 * Reserve a session-generation token before starting a slow OUT-OF-MODULE
 * async operation that will eventually call `installRawDek` — e.g.
 * `unlockEnvelopeStore.open()`'s two Argon2id derivations
 * (docs/vault-unlock-envelope-integration-plan.md §3.7 notes these can run
 * over a second combined).
 *
 * Every other session-establishing function in this module captures
 * `generation = ++sessionGeneration` BEFORE its own slow step and checks it
 * after, so a `clearSessionKey()` (logout) or a newer call that lands mid-
 * flight is detected rather than silently overwritten -- see
 * `initSessionKeyFromPassword`. That pattern only works when the slow step
 * is INSIDE this module. `unlockEnvelopeStore.open()` is not, so
 * `installRawDek` bumping its own generation internally would be blind to
 * anything that happened during the caller's `open()` await -- a logout or a
 * newer unlock landing in that window would go undetected, and the stale
 * result would resurrect a session nobody is in anymore. Call this BEFORE
 * the slow external step and pass the result to `installRawDek` as
 * `expectedGeneration` to close that gap.
 */
export const reserveSessionGeneration = () => ++sessionGeneration;

/**
 * Read the current session generation WITHOUT reserving one.
 *
 * For callers that need to detect whether the session changed under them but
 * are NOT installing a session of their own -- e.g. `VaultDuressSetup`, whose
 * `setDecoySlot()` call runs three Argon2 derivations during which the vault
 * can lock (`clearSessionKey()` bumps this counter) or be re-unlocked with the
 * DECOY password. Capture before the slow step, compare after.
 *
 * Deliberately separate from `reserveSessionGeneration()`: that one
 * INCREMENTS, which is correct for a caller about to install a key but would
 * invalidate an unrelated in-flight unlock if used merely to observe. A bare
 * `hasSessionKey()` re-check is not equivalent either -- it answers true again
 * after a lock followed by any unlock, including a decoy one.
 */
export const currentSessionGeneration = () => sessionGeneration;

/**
 * Install a raw 32-byte DEK as the session key.
 *
 * Used by the hidden-vault envelope unlock path
 * (docs/vault-unlock-envelope-integration-plan.md §3.3), where the DEK
 * arrives already decrypted from an envelope slot rather than unwrapped from
 * the path (B) wrapped-DEK record. Mirrors `unlockWithVaultPassword`'s tail
 * exactly (generation check, salt, session state) — keep the two in sync;
 * see that function's comments for why each line here exists. The imported
 * key is non-extractable, matching `unlockWithVaultPassword`'s posture.
 *
 * @param {number|null} [expectedGeneration] - a token from
 *   `reserveSessionGeneration()`, captured by the caller BEFORE its own slow
 *   pre-processing (e.g. envelope decode). When supplied, validated against
 *   the live counter before any work happens here, catching a race that
 *   started before this function was even called. When omitted, falls back
 *   to the original self-contained behaviour (generation captured and
 *   checked entirely within this call) — used only by callers with no slow
 *   step of their own to protect.
 * @param {boolean} [isDecoy] - true when `dekBytes` came from the hidden-vault
 *   envelope's DECOY slot (unlockEnvelopeStore.open()'s `slotIndex === 1`).
 *   Sets `sessionIsDecoy`, which `encryptItem` refuses to write under — see
 *   that flag's own comment for why this must never be left to default true.
 */
export const installRawDek = async (dekBytes, saltB64, userId, expectedGeneration = null, isDecoy = false) => {
  if (!userId) throw new Error('installRawDek: userId required');
  if (!(dekBytes instanceof Uint8Array) || dekBytes.byteLength !== 32) {
    throw new Error('installRawDek: dekBytes must be a 32-byte Uint8Array');
  }
  if (expectedGeneration !== null && expectedGeneration !== sessionGeneration) {
    throw new Error('Vault session initialization was superseded by a newer request.');
  }

  const generation = expectedGeneration ?? ++sessionGeneration;
  const dek = await window.crypto.subtle.importKey(
    'raw',
    dekBytes,
    { name: 'AES-GCM', length: 256 },
    false,
    ['encrypt', 'decrypt']
  );
  if (generation !== sessionGeneration) {
    // See `initSessionKeyFromPassword`.
    throw new Error('Vault session initialization was superseded by a newer request.');
  }
  sessionSaltB64 = saltB64;
  sessionKey = dek;
  sessionIsDecoy = isDecoy;
  // See `setupVaultPassword` — path (B)/(C) have no password to memoize against.
  sessionPassword = null;
  foreignSaltKeys.clear();
};

// ----------------------------------------------------------------------------
// Session key + item encryption (shared by both paths).
// ----------------------------------------------------------------------------

export const hasSessionKey = () => sessionKey !== null;

/** True only for a session installed from the hidden-vault envelope's decoy slot. */
export const isDecoySession = () => sessionIsDecoy;

export const clearSessionKey = () => {
  // Invalidates any in-flight init/setup/unlock call -- see `sessionGeneration`.
  sessionGeneration += 1;
  sessionKey = null;
  sessionSaltB64 = null;
  sessionPassword = null;
  sessionIsDecoy = false;
  foreignSaltKeys.clear();
};

/**
 * Resolve the AES-GCM key that opens an envelope written under `saltB64`.
 *
 * The v2 salt is device-local: `getOrCreateUserSalt` mints it into
 * localStorage and never sends it to the server. So an item encrypted on
 * another device (or on this one before site data was cleared) was sealed
 * under a salt this device has never seen, and the session key cannot open
 * it — which is why such items rendered as "Decryption failed" even with the
 * correct master password.
 *
 * The fix needs no migration and no new server field, because `encryptItem`
 * has always stamped `salt: sessionSaltB64` into every envelope (see below).
 * The salt each item needs is already stored alongside it; it was simply
 * never read. Given the master password — retained by
 * `initSessionKeyFromPassword` for exactly this — the original key is
 * re-derivable on any device.
 *
 * @param {unknown} saltB64 The envelope's `salt` field.
 * @returns {Promise<CryptoKey>} The session key when `saltB64` is absent or
 *   matches this session's salt; otherwise a key derived for that salt.
 */
const keyForSalt = async (saltB64) => {
  if (!sessionKey) {
    throw new Error('Vault is locked: session encryption key is not initialized.');
  }
  // Fast path: the overwhelmingly common case (item written on this device),
  // plus pre-salt envelopes, which predate the field and can only ever have
  // been written under this device's salt anyway.
  if (typeof saltB64 !== 'string' || !saltB64 || saltB64 === sessionSaltB64) {
    return sessionKey;
  }
  // Foreign salt, but no password to derive from — path (B) wrapped-DEK
  // sessions. Fall through to the session key: it won't open the item, but
  // that is exactly today's behaviour and the caller already handles the throw.
  if (!sessionPassword) {
    return sessionKey;
  }
  let pending = foreignSaltKeys.get(saltB64);
  if (!pending) {
    pending = deriveDirectKey(sessionPassword, saltB64);
    foreignSaltKeys.set(saltB64, pending);
    // Don't let a transient WebCrypto failure poison the cache for the rest of
    // the session — a retry should be allowed to derive again. `.catch` here
    // only unregisters; the rejection still propagates to the awaiting caller
    // through `pending` itself.
    pending.catch(() => {
      if (foreignSaltKeys.get(saltB64) === pending) {
        foreignSaltKeys.delete(saltB64);
      }
    });
  }
  return pending;
};

/**
 * Encrypt a plain JS object into an `encrypted_data` string.
 * Throws if no session key is initialized — callers MUST handle this
 * (e.g. prompt the user to log in with password, or show an error).
 *
 * Also throws for a decoy session (`isDecoySession()`). setDecoySlot stamps
 * the decoy slot with the SAME salt as the real slot
 * (unlockEnvelopeStore.js), so a new item written here would be encrypted
 * under the decoy DEK but carry the real slot's salt — `keyForSalt`'s
 * matching-salt fast path would later hand the REAL session's DEK to
 * decrypt it, an AES-GCM failure that permanently corrupts a row in the one
 * shared, server-side item list. There is no salt this function could stamp
 * instead that fixes this: OAuth/envelope sessions never set
 * `sessionPassword` (see its own comment), so ANY foreign salt already falls
 * through to `sessionKey` in `keyForSalt` -- the failure is structural, not
 * a salt-choice bug, so refusing the write here is the actual fix.
 */
/**
 * The single refusal string every decoy-session write path must raise.
 *
 * Indistinguishability requires that EVERY refusal emit one byte-identical
 * message: `VaultContext` surfaces `error.message` straight to the screen, so
 * two different strings would tell a coercer which layer declined. That rule
 * was being held by copied literals in `encryptItem` below and in
 * `vaultEnvelope.encryptEnvelope`, which cannot enforce it -- editing one copy
 * silently breaks the property. Owned here, beside `sessionIsDecoy` itself.
 *
 * Deliberately generic and deliberately never logged: it must stay plausible
 * as an ordinary save failure, and per the plan's §3.5 rule 4 no `console.*`
 * may mention slots or duress, which would just move the tell to devtools.
 */
export const DECOY_WRITE_REFUSAL = 'Failed to save item. Please try again.';

export const encryptItem = async (obj) => {
  if (!sessionKey) {
    throw new Error('Vault is locked: session encryption key is not initialized.');
  }
  if (sessionIsDecoy) {
    // Deliberately generic, and deliberately NOT logged anywhere: this string
    // reaches the UI (VaultContext's `setError(error.message || ...)`), so a
    // coercer watching the screen during a duress unlock must not be able to
    // read the duress feature's existence off a failed save. It must stay
    // plausible as an ordinary save failure. Per the plan's §3.5 rule 4 ("no
    // `console.*` may mention slots or duress") the reason is not logged
    // either -- a console message would just move the same tell to devtools.
    throw new Error(DECOY_WRITE_REFUSAL);
  }
  const iv = window.crypto.getRandomValues(new Uint8Array(12));
  const plaintext = new TextEncoder().encode(JSON.stringify(obj));
  const ctBuf = await window.crypto.subtle.encrypt(
    { name: 'AES-GCM', iv },
    sessionKey,
    plaintext
  );
  return JSON.stringify({
    v: PAYLOAD_VERSION,
    iv: toB64(iv),
    ct: toB64(new Uint8Array(ctBuf)),
    salt: sessionSaltB64,
  });
};

/**
 * Decrypt an `encrypted_data` string back into the original object.
 *
 * Strict: anything whose envelope is not a `{v: PAYLOAD_VERSION, iv, ct}`
 * ciphertext object is treated as legacy / untrusted and surfaces a
 * `_legacyPlaintext` marker *without* copying any of its fields into the
 * decrypted view. Plaintext secrets stored server-side must never be
 * silently rendered as if they had been end-to-end encrypted.
 */
export const decryptItem = async (payloadStr) => {
  if (typeof payloadStr !== 'string' || payloadStr.length === 0) {
    return {};
  }
  let parsed;
  try {
    parsed = JSON.parse(payloadStr);
  } catch {
    return {};
  }

  if (!parsed || typeof parsed !== 'object') return {};

  if (
    parsed.v !== PAYLOAD_VERSION ||
    typeof parsed.iv !== 'string' ||
    typeof parsed.ct !== 'string'
  ) {
    // Legacy plaintext or otherwise untrusted payload: do NOT leak fields
    // through. The UI should render a migration/warning state instead.
    return { _legacyPlaintext: true };
  }

  // Captured BEFORE the two awaits below, which is where the session can
  // change out from under this call -- a foreign-salt `keyForSalt` derivation
  // is a ~100ms PBKDF2 run, easily long enough for `clearSessionKey()`
  // (logout) to land mid-flight. `keyForSalt` itself intentionally doesn't
  // guard against that (see its own comment: it never writes module state,
  // so a stale RETURN VALUE there was judged harmless) -- but that reasoning
  // stops at the module boundary. The stale-but-still-cryptographically-valid
  // key it returns can still successfully decrypt THIS envelope's ciphertext
  // and hand real plaintext back to whatever called `decryptItem` before
  // logout, which is a confidentiality problem `keyForSalt`'s own guard was
  // never meant to cover. Checked again after `subtle.decrypt` too: that
  // call is also async, and a logout landing during ITS gap is the same risk.
  const generation = sessionGeneration;

  // Decrypt under the salt the envelope was SEALED with, not this device's.
  // `keyForSalt` throws the locked-vault error when there is no session key.
  const key = await keyForSalt(parsed.salt);
  if (generation !== sessionGeneration) {
    throw new Error('Vault session changed while decrypting.');
  }

  const iv = fromB64(parsed.iv);
  const ct = fromB64(parsed.ct);
  const ptBuf = await window.crypto.subtle.decrypt(
    { name: 'AES-GCM', iv },
    key,
    ct
  );
  if (generation !== sessionGeneration) {
    throw new Error('Vault session changed while decrypting.');
  }
  const text = new TextDecoder().decode(ptBuf);
  return JSON.parse(text);
};

export default {
  initSessionKeyFromPassword,
  setupVaultPassword,
  unlockWithVaultPassword,
  hasWrappedKey,
  clearWrappedKey,
  exportWrappedDekRaw,
  exportSessionDekRaw,
  reserveSessionGeneration,
  currentSessionGeneration,
  DECOY_WRITE_REFUSAL,
  installRawDek,
  hasSessionKey,
  isDecoySession,
  clearSessionKey,
  encryptItem,
  decryptItem,
  getOrCreateUserSalt,
};

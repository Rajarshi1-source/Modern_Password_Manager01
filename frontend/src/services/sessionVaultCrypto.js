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
const getOrCreateUserSalt = (userId) => {
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
  const saltB64 = getOrCreateUserSalt(userId);
  const key = await deriveDirectKey(password, saltB64);
  // Assign only after the derivation resolves, so a failed init leaves the
  // previous session state intact rather than half-replaced.
  sessionSaltB64 = saltB64;
  sessionKey = key;
  sessionPassword = password;
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
  localStorage.setItem(wrappedStorageKey(userId), JSON.stringify(record));

  sessionSaltB64 = saltB64;
  sessionKey = dek;
  // Path (B) installs a DEK, not a password-derived key: there is nothing to
  // derive foreign-salt keys FROM, so drop any path-(A) leftovers rather than
  // letting `keyForSalt` derive with a password that doesn't match this session.
  sessionPassword = null;
  foreignSaltKeys.clear();
};

/**
 * Unlock an existing wrapped DEK using the user's vault password. Installs
 * the unwrapped DEK as the current session key. Throws if the password is
 * wrong or the stored record is missing/corrupt.
 */
export const unlockWithVaultPassword = async (vaultPassword, userId) => {
  if (!userId) throw new Error('unlockWithVaultPassword: userId required');
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

  const kek = await deriveKEK(vaultPassword, record.salt);

  try {
    const dek = await window.crypto.subtle.unwrapKey(
      'raw',
      fromB64(record.wrapped),
      kek,
      { name: 'AES-GCM', iv: fromB64(record.iv) },
      { name: 'AES-GCM', length: 256 },
      false,
      ['encrypt', 'decrypt']
    );
    sessionSaltB64 = record.salt;
    sessionKey = dek;
    // See `setupVaultPassword` — path (B) has no password to memoize against.
    sessionPassword = null;
    foreignSaltKeys.clear();
  } catch {
    // AES-GCM unwrap failure is the canonical "wrong password" signal.
    throw new Error('Incorrect vault password.');
  }
};

/**
 * Remove the wrapped DEK for `userId`. Destructive: items encrypted under
 * the old DEK become unreadable. Intended for "reset vault" flows.
 */
export const clearWrappedKey = (userId) => {
  if (!userId) return;
  localStorage.removeItem(wrappedStorageKey(userId));
};

// ----------------------------------------------------------------------------
// Session key + item encryption (shared by both paths).
// ----------------------------------------------------------------------------

export const hasSessionKey = () => sessionKey !== null;

export const clearSessionKey = () => {
  sessionKey = null;
  sessionSaltB64 = null;
  sessionPassword = null;
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
 */
export const encryptItem = async (obj) => {
  if (!sessionKey) {
    throw new Error('Vault is locked: session encryption key is not initialized.');
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

  // Decrypt under the salt the envelope was SEALED with, not this device's.
  // `keyForSalt` throws the locked-vault error when there is no session key.
  const key = await keyForSalt(parsed.salt);

  const iv = fromB64(parsed.iv);
  const ct = fromB64(parsed.ct);
  const ptBuf = await window.crypto.subtle.decrypt(
    { name: 'AES-GCM', iv },
    key,
    ct
  );
  const text = new TextDecoder().decode(ptBuf);
  return JSON.parse(text);
};

export default {
  initSessionKeyFromPassword,
  setupVaultPassword,
  unlockWithVaultPassword,
  hasWrappedKey,
  clearWrappedKey,
  hasSessionKey,
  clearSessionKey,
  encryptItem,
  decryptItem,
};

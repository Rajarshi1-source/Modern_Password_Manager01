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

const getOrCreateUserSalt = (userId) => {
  const storageKey = saltStorageKey(userId);
  let salt = localStorage.getItem(storageKey);
  if (!salt) {
    const raw = window.crypto.getRandomValues(new Uint8Array(16));
    salt = toB64(raw);
    localStorage.setItem(storageKey, salt);
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
  sessionSaltB64 = saltB64;
  sessionKey = await deriveDirectKey(password, saltB64);
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

  if (!sessionKey) {
    throw new Error('Vault is locked: session encryption key is not initialized.');
  }

  const iv = fromB64(parsed.iv);
  const ct = fromB64(parsed.ct);
  const ptBuf = await window.crypto.subtle.decrypt(
    { name: 'AES-GCM', iv },
    sessionKey,
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

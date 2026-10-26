/**
 * loginVerifier.js — what the browser sends to sign in instead of the
 * master password.
 *
 *   salt     = SHA-256("pwm-login-verifier-v1|" + lower(trim(username)))
 *   verifier = base64(Argon2id(masterPassword, salt, t=3, m=64 MiB, p=2, 32 bytes))
 *
 * The verifier is sent as the `password` of the sign-in endpoints and is
 * stored server-side as the Django password (hashed again there). It is a
 * different value from every vault KEK: those are derived with random
 * salts kept in their wrapped-DEK envelopes, and this salt is
 * domain-separated by its prefix. The master password itself never
 * leaves the browser. Server side: `auth_module/login_verifier.py`.
 *
 * The salt comes from the username, so sign-in needs no extra request
 * that could reveal whether an account exists.
 *
 * Migration: an account created before the verifier still signs in with
 * its master password. When a verifier sign-in fails and this browser has
 * never signed the account in with a verifier, `signInWithVerifier`
 * retries once with the old password as `legacy_password`; the server
 * checks it once and switches the account to the verifier.
 */
import * as argon2 from 'argon2-browser';

export const LOGIN_VERIFIER_SCHEME = 'lv1';
const SALT_PREFIX = 'pwm-login-verifier-v1|';
// Same OWASP-aligned Argon2id cost as the vault KEK (sessionVaultCryptoV3).
const KDF = { t: 3, m: 65536, p: 2 };
const MIGRATED_KEY_PREFIX = 'pwm.lv1.';

const toHex = (a) => Array.from(a, (b) => b.toString(16).padStart(2, '0')).join('');
const toB64 = (a) => {
  let s = '';
  for (let i = 0; i < a.byteLength; i++) s += String.fromCharCode(a[i]);
  return btoa(s);
};

export const normalizeUsername = (username) => String(username || '').trim().toLowerCase();

async function sha256(text) {
  const digest = await window.crypto.subtle.digest('SHA-256', new TextEncoder().encode(text));
  return new Uint8Array(digest);
}

/**
 * Derive the login verifier for `username` from `masterPassword`.
 * @returns {Promise<string>} base64 of 32 bytes
 */
export async function deriveLoginVerifier(masterPassword, username) {
  if (!masterPassword || !normalizeUsername(username)) {
    throw new Error('masterPassword and username are required.');
  }
  const salt = await sha256(SALT_PREFIX + normalizeUsername(username));
  const result = await argon2.hash({
    pass: masterPassword,
    salt: toHex(salt),
    type: argon2.ArgonType.Argon2id,
    time: KDF.t,
    mem: KDF.m,
    parallelism: KDF.p,
    hashLen: 32,
  });
  return toB64(result.hash);
}

// The marker is keyed by a hash of the username, so local storage does not
// list which accounts signed in here. It is a convenience only: without it
// the worst case is one extra request carrying the old password.
async function migratedKey(username) {
  return MIGRATED_KEY_PREFIX + toHex(await sha256(SALT_PREFIX + normalizeUsername(username))).slice(0, 32);
}

async function isKnownMigrated(username) {
  try {
    return window.localStorage.getItem(await migratedKey(username)) === '1';
  } catch {
    return false;
  }
}

async function rememberMigrated(username) {
  try {
    window.localStorage.setItem(await migratedKey(username), '1');
  } catch { /* storage unavailable: the fallback below still works */ }
}

const isCredentialRejection = (err) => [400, 401].includes(err?.response?.status);

/**
 * Sign in with the verifier, switching a legacy account over if needed.
 *
 * @param {(body: {username: string, password: string, legacy_password?: string}) => Promise<T>} post
 *   Sends one sign-in request with this body; rejects on failure.
 * @returns {Promise<T>}
 * @template T
 */
export async function signInWithVerifier(post, { username, masterPassword }) {
  const verifier = await deriveLoginVerifier(masterPassword, username);
  try {
    const result = await post({ username, password: verifier });
    await rememberMigrated(username);
    return result;
  } catch (err) {
    if (!isCredentialRejection(err) || (await isKnownMigrated(username))) throw err;
  }
  // One retry carrying the old password, for an account that has not been
  // switched yet. The server ignores it for an account that has.
  const result = await post({ username, password: verifier, legacy_password: masterPassword });
  await rememberMigrated(username);
  return result;
}

/**
 * The PBKDF2-SHA256 master-password check kept in `UserSalt.auth_hash`
 * (registration, change_master, email reset). Salted with the account
 * email so the same password always gives the same hash.
 * @returns {Promise<string>} base64
 */
export async function deriveAuthHash(masterPassword, email) {
  const encoder = new TextEncoder();
  const keyMaterial = await window.crypto.subtle.importKey(
    'raw', encoder.encode(masterPassword), { name: 'PBKDF2' }, false, ['deriveBits'],
  );
  const bits = await window.crypto.subtle.deriveBits(
    {
      name: 'PBKDF2',
      salt: encoder.encode(`pwm-auth|${String(email).toLowerCase()}`),
      iterations: 310000,
      hash: 'SHA-256',
    },
    keyMaterial,
    256,
  );
  return toB64(new Uint8Array(bits));
}

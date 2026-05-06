/**
 * sessionVaultCryptoV3.js — wrapped-DEK crypto for the Layered Recovery Mesh.
 *
 *   1. A random 256-bit DEK is generated at enrollment and persists
 *      across master-password rotations.
 *   2. The DEK is wrapped under a KEK derived from the master password
 *      via Argon2id; only the resulting envelope (ciphertext) is sent
 *      to the server.
 *   3. Login = fetch wrapped blob, derive KEK, unwrap DEK in-memory.
 *   4. Master-password change = re-wrap the SAME DEK under a new KEK.
 *      Vault items are untouched.
 *   5. Recovery factors = wrap the DEK under additional KEKs (recovery
 *      key, social-mesh seed, time-lock seed). Recovery uses any of
 *      those KEKs to retrieve the DEK.
 *
 * ZK invariant: master password, recovery key, and unwrapped DEK never
 * leave the browser. Only the envelope (with `wrapped`, `iv`, `salt`)
 * is ever sent to the server.
 *
 * Lives ALONGSIDE the existing v2 `sessionVaultCrypto.js`. Unit 15
 * wires the live signup/login path through here.
 */
import * as argon2 from 'argon2-browser';
import axios from 'axios';

const BLOB_VERSION = 'wdek-1';
const PAYLOAD_VERSION = 'svc-gcm-2';
// OWASP-2024-aligned interactive Argon2id params (matches the medium
// preset in `secureVaultCrypto.js`).
const DEFAULT_KDF = { t: 3, m: 65536, p: 2 };

const WRAPPED_DEK_URL = '/api/auth/vault/wrapped-dek/';
// Anonymous post-recovery rotation endpoint. The recovery pages run
// while the user is NOT yet authenticated (they forgot the master
// password), so they cannot PUT to the IsAuthenticated WRAPPED_DEK_URL.
// This endpoint accepts (username, factor_type, dek_id, blob) and
// authorizes the rotation through possession of dek_id obtained via
// the `recovery-factors/lookup/` endpoint.
const WRAPPED_DEK_RECOVER_ROTATE_URL = '/api/auth/vault/wrapped-dek/recover-rotate/';
const RECOVERY_FACTORS_URL = '/api/auth/vault/recovery-factors/';

let sessionDEK = null; // CryptoKey, non-extractable
let sessionDEKId = null; // UUID string from server

// ─── Encoding helpers ───────────────────────────────────────────────
const toB64 = (b) => {
  const a = b instanceof Uint8Array ? b : new Uint8Array(b);
  let s = '';
  for (let i = 0; i < a.byteLength; i++) s += String.fromCharCode(a[i]);
  return btoa(s);
};
const fromB64 = (s) => {
  const bin = atob(s);
  const out = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i);
  return out;
};
const randomBytes = (n) => window.crypto.getRandomValues(new Uint8Array(n));
const toHex = (a) => Array.from(a, (b) => b.toString(16).padStart(2, '0')).join('');

// ─── KEK derivation (Argon2id) ─────────────────────────────────────
async function deriveKEK(secret, saltBytes, params = DEFAULT_KDF) {
  const result = await argon2.hash({
    pass: secret,
    salt: toHex(saltBytes),
    type: argon2.ArgonType.Argon2id,
    time: params.t,
    mem: params.m,
    parallelism: params.p,
    hashLen: 32,
  });
  return window.crypto.subtle.importKey(
    'raw',
    result.hash,
    { name: 'AES-GCM', length: 256 },
    false,
    ['wrapKey', 'unwrapKey'],
  );
}

// ─── Wrap / unwrap a DEK under a KEK ───────────────────────────────
async function wrapDEK(dekExtractable, kek, params, saltBytes) {
  const iv = randomBytes(12);
  const wrapped = await window.crypto.subtle.wrapKey(
    'raw',
    dekExtractable,
    kek,
    { name: 'AES-GCM', iv },
  );
  return {
    v: BLOB_VERSION,
    kdf: 'argon2id',
    kdf_params: params,
    salt: toB64(saltBytes),
    iv: toB64(iv),
    wrapped: toB64(new Uint8Array(wrapped)),
  };
}

async function unwrapDEK(blob, secret, { extractable = false } = {}) {
  if (!blob || blob.v !== BLOB_VERSION) {
    throw new Error('Unsupported wrapped-DEK version.');
  }
  const saltBytes = fromB64(blob.salt);
  const kek = await deriveKEK(secret, saltBytes, blob.kdf_params || DEFAULT_KDF);
  try {
    return await window.crypto.subtle.unwrapKey(
      'raw',
      fromB64(blob.wrapped),
      kek,
      { name: 'AES-GCM', iv: fromB64(blob.iv) },
      { name: 'AES-GCM', length: 256 },
      extractable,
      ['encrypt', 'decrypt'],
    );
  } catch {
    // Wrong secret, wrong salt, or corrupted blob — AES-GCM raises the
    // same OperationError. Generic message by design.
    throw new Error('Incorrect password or corrupted vault key.');
  }
}

async function reimportNonExtractable(extractableKey) {
  const raw = await window.crypto.subtle.exportKey('raw', extractableKey);
  return window.crypto.subtle.importKey(
    'raw',
    raw,
    { name: 'AES-GCM', length: 256 },
    false,
    ['encrypt', 'decrypt'],
  );
}

// ─── Public API: enrollment / login / change-password ─────────────

export async function enrollWithMasterPassword(masterPassword) {
  const dek = await window.crypto.subtle.generateKey(
    { name: 'AES-GCM', length: 256 },
    true, // extractable for wrapKey
    ['encrypt', 'decrypt'],
  );
  const saltBytes = randomBytes(16);
  const kek = await deriveKEK(masterPassword, saltBytes);
  const blob = await wrapDEK(dek, kek, DEFAULT_KDF, saltBytes);
  const { data } = await axios.put(WRAPPED_DEK_URL, { blob });
  // Re-import as non-extractable; nothing references the original
  // extractable handle after this point.
  sessionDEK = await reimportNonExtractable(dek);
  sessionDEKId = data.dek_id;
  return { dekId: sessionDEKId };
}

export async function unlockWithMasterPassword(masterPassword) {
  const { data } = await axios.get(WRAPPED_DEK_URL);
  if (!data.enrolled) {
    throw new Error('NOT_ENROLLED');
  }
  sessionDEK = await unwrapDEK(data.blob, masterPassword, { extractable: false });
  sessionDEKId = data.dek_id;
  return { dekId: sessionDEKId };
}

export async function changeMasterPassword(oldPassword, newPassword) {
  if (!sessionDEK) throw new Error('Vault is locked.');
  const { data } = await axios.get(WRAPPED_DEK_URL);
  const dekX = await unwrapDEK(data.blob, oldPassword, { extractable: true });
  const saltBytes = randomBytes(16);
  const kek = await deriveKEK(newPassword, saltBytes);
  const blob = await wrapDEK(dekX, kek, DEFAULT_KDF, saltBytes);
  await axios.put(WRAPPED_DEK_URL, { blob, dek_id: sessionDEKId });
}

// ─── Public API: recovery factor enroll / use ─────────────────────

/**
 * Wrap the current DEK under a KEK derived from `secret` and POST it as
 * a new RecoveryWrappedDEK row. `masterPassword` is required because
 * we need an extractable handle on the DEK for wrapKey, and the session
 * DEK is non-extractable by design.
 */
export async function enrollRecoveryFactor({ factorType, secret, meta = {}, masterPassword }) {
  if (!sessionDEKId) throw new Error('Vault is locked.');
  const { data } = await axios.get(WRAPPED_DEK_URL);
  const dekX = await unwrapDEK(data.blob, masterPassword, { extractable: true });
  const saltBytes = randomBytes(16);
  const kek = await deriveKEK(secret, saltBytes);
  const blob = await wrapDEK(dekX, kek, DEFAULT_KDF, saltBytes);
  await axios.post(RECOVERY_FACTORS_URL, {
    factor_type: factorType,
    dek_id: sessionDEKId,
    blob,
    meta,
  });
}

/**
 * Build (but do NOT POST) a recovery-factor envelope wrapping the
 * current DEK under a KEK derived from `secret`. Returns the envelope
 * plus the current `dekId` so the caller can include both in a
 * higher-level bundle write (e.g. the atomic time-locked
 * enroll-bundle endpoint, which writes the wdek row and the Shamir
 * server half in one transaction).
 *
 * Same crypto as `enrollRecoveryFactor`; the only difference is the
 * server-side POST is the caller's responsibility.
 *
 * @param {object} args
 * @param {string} args.secret         - The recovery secret (key/seed).
 * @param {string} args.masterPassword - Needed to derive an extractable DEK.
 * @returns {Promise<{blob: object, dekId: string}>}
 */
export async function buildRecoveryFactorEnvelope({ secret, masterPassword }) {
  if (!sessionDEKId) throw new Error('Vault is locked.');
  const { data } = await axios.get(WRAPPED_DEK_URL);
  const dekX = await unwrapDEK(data.blob, masterPassword, { extractable: true });
  const saltBytes = randomBytes(16);
  const kek = await deriveKEK(secret, saltBytes);
  const blob = await wrapDEK(dekX, kek, DEFAULT_KDF, saltBytes);
  return { blob, dekId: sessionDEKId };
}

/**
 * Recovery: install the DEK in the session by unwrapping a recovery
 * factor's blob with its corresponding secret. The recovery UI MUST
 * drive the user through `rewrapMasterPasswordFromRecovery` (or
 * `changeMasterPassword` in the rare case the user remembered the old
 * password) immediately after — recovery without setting a new master
 * password leaves the master-wrapped row pinned to the FORGOTTEN
 * password, which means the user is locked out again on next login.
 */
export async function unlockWithRecoveryFactor(blob, secret, dekId) {
  sessionDEK = await unwrapDEK(blob, secret, { extractable: false });
  sessionDEKId = dekId;
  return sessionDEK;
}

/**
 * Post-recovery master-password rotation.
 *
 * Used immediately after `unlockWithRecoveryFactor` when the user has
 * forgotten the old master password. We unwrap the DEK from the
 * recovery factor's blob (NOT the master-wrapped row, which is pinned
 * to the forgotten password — `changeMasterPassword` cannot handle
 * this case because it tries to unwrap the master row with the
 * recovery secret, which always fails), then wrap that same DEK under
 * a fresh KEK derived from the new master password and POST it to the
 * anonymous recover-rotate endpoint — keeping `dek_id` stable so the
 * user's other recovery factors are not orphaned.
 *
 * Why this can't use the standard WRAPPED_DEK_URL PUT: that endpoint
 * is `IsAuthenticated`, but the recovery pages run BEFORE the user is
 * authenticated (they're recovering precisely because they can't log
 * in). The anonymous WRAPPED_DEK_RECOVER_ROTATE_URL accepts
 * (username, factor_type, dek_id, blob) and authorizes the rotation
 * through possession of `dek_id`, which is only obtainable via a
 * successful `recovery-factors/lookup/` call.
 *
 * The session DEK is also re-installed (non-extractable) so the user
 * can use the vault immediately without a separate unlock step.
 *
 * @param {object} args
 * @param {object} args.factorBlob   - Recovery-factor envelope ({v:'wdek-1', ...}).
 * @param {string} args.recoverySecret - The secret that unwraps factorBlob
 *   (recovery key, hex-encoded recovery seed, hex-encoded time seed, etc.).
 * @param {string} args.newPassword  - The new master password to set.
 * @param {string} args.dekId        - Stable DEK identity (from listRecoveryFactors).
 * @param {string} args.username     - Account being recovered (used to address
 *   the rotation server-side; recovery pages are anonymous).
 * @param {('recovery_key'|'social_mesh'|'time_locked'|'passkey')} args.factorType
 *   The factor used to unwrap (lets the server confirm a real factor
 *   of this type exists and audit the rotation against it).
 * @returns {Promise<{dekId: string}>}
 */
export async function rewrapMasterPasswordFromRecovery({
  factorBlob,
  recoverySecret,
  newPassword,
  dekId,
  username,
  factorType,
}) {
  if (!factorBlob || !recoverySecret || !newPassword || !dekId || !username || !factorType) {
    throw new Error(
      'factorBlob, recoverySecret, newPassword, dekId, username, and factorType are required.',
    );
  }
  // Unwrap the DEK from the recovery factor as EXTRACTABLE so we can
  // re-wrap it under the new KEK. The extractable handle goes out of
  // scope at function exit; the only persistent reference is the
  // non-extractable session key we re-import below.
  const dekX = await unwrapDEK(factorBlob, recoverySecret, { extractable: true });

  const saltBytes = randomBytes(16);
  const kek = await deriveKEK(newPassword, saltBytes);
  const blob = await wrapDEK(dekX, kek, DEFAULT_KDF, saltBytes);

  await axios.post(WRAPPED_DEK_RECOVER_ROTATE_URL, {
    username,
    factor_type: factorType,
    dek_id: dekId,
    blob,
  });

  // Install the same DEK as the live session key, non-extractable.
  sessionDEK = await reimportNonExtractable(dekX);
  sessionDEKId = dekId;
  return { dekId };
}

// ─── Public API: item encryption ───────────────────────────────────

export const hasSessionKey = () => sessionDEK !== null;
export const clearSessionKey = () => {
  sessionDEK = null;
  sessionDEKId = null;
};

export async function encryptItem(obj) {
  if (!sessionDEK) throw new Error('Vault is locked.');
  const iv = randomBytes(12);
  const ct = await window.crypto.subtle.encrypt(
    { name: 'AES-GCM', iv },
    sessionDEK,
    new TextEncoder().encode(JSON.stringify(obj)),
  );
  return JSON.stringify({
    v: PAYLOAD_VERSION,
    iv: toB64(iv),
    ct: toB64(new Uint8Array(ct)),
    dek_id: sessionDEKId,
  });
}

export async function decryptItem(payloadStr) {
  if (typeof payloadStr !== 'string' || !payloadStr) return {};
  let parsed;
  try {
    parsed = JSON.parse(payloadStr);
  } catch {
    return {};
  }
  // Anything older than svc-gcm-2 is treated as legacy/untrusted —
  // do NOT leak fields; the legacy migration helper will re-encrypt.
  if (
    !parsed ||
    parsed.v !== PAYLOAD_VERSION ||
    typeof parsed.iv !== 'string' ||
    typeof parsed.ct !== 'string'
  ) {
    return { _legacyPlaintext: true };
  }
  if (parsed.dek_id && sessionDEKId && parsed.dek_id !== sessionDEKId) {
    return { _staleDek: true };
  }
  if (!sessionDEK) throw new Error('Vault is locked.');
  const buf = await window.crypto.subtle.decrypt(
    { name: 'AES-GCM', iv: fromB64(parsed.iv) },
    sessionDEK,
    fromB64(parsed.ct),
  );
  return JSON.parse(new TextDecoder().decode(buf));
}

export default {
  enrollWithMasterPassword,
  unlockWithMasterPassword,
  changeMasterPassword,
  enrollRecoveryFactor,
  buildRecoveryFactorEnvelope,
  unlockWithRecoveryFactor,
  rewrapMasterPasswordFromRecovery,
  hasSessionKey,
  clearSessionKey,
  encryptItem,
  decryptItem,
};

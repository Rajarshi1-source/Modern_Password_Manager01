/**
 * PRE (Umbral) Key Registration / Recovery Service.
 *
 * Responsibilities:
 *   - Generate a fresh Umbral keypair the first time a user opens the
 *     Homomorphic Sharing dashboard.
 *   - Upload the PUBLIC material to the backend key registry.
 *   - Persist the SECRET material locally, wrapped by
 *     `SecureVaultCrypto` (AES-GCM under the master key) when the
 *     vault is unlocked; otherwise fall back to best-effort
 *     session storage.
 *
 * Callers should prefer `ensureUmbralIdentity()` which returns
 * `{ ready, publicKeys, rawSecrets }` — it will transparently reuse
 * existing local keys or trigger first-time enrollment.
 *
 * The secret-key store is deliberately lightweight: the PRE feature
 * MUST degrade gracefully when the user hasn't unlocked their vault.
 */

import preClient, { isPreAvailable, UmbralUnavailableError } from './preClient';
import { registerUmbralPublicKey } from './fheSharingService';
import { getSecureVaultCrypto } from '../secureVaultCrypto';

const STORAGE_KEY = 'fhe:pre:umbral_identity_v1';
const LEGACY_STORAGE_KEY = 'fhe:pre:umbral_identity';

function _getLocalStorage() {
  try {
    return window.localStorage;
  } catch (_err) {
    return null;
  }
}

function _bytesToB64(bytes) {
  let bin = '';
  for (let i = 0; i < bytes.length; i += 1) bin += String.fromCharCode(bytes[i]);
  return btoa(bin);
}

function _b64ToBytes(s) {
  const bin = atob(s);
  const out = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i += 1) out[i] = bin.charCodeAt(i);
  return out;
}

async function _persistIdentity(identity) {
  const ls = _getLocalStorage();
  if (!ls) return false;

  const secretBlob = {
    sk: _bytesToB64(identity.secret.sk),
    signerSk: _bytesToB64(identity.secret.signerSk),
  };

  let serialized = {
    version: 1,
    wrapped: false,
    publicKeys: identity.public,
    payload: secretBlob,
  };

  try {
    const crypto = getSecureVaultCrypto();
    if (crypto?.initialized) {
      const wrapped = await crypto.encrypt(JSON.stringify(secretBlob), {
        associatedData: 'fhe:pre:umbral_identity_v1',
      });
      serialized = {
        version: 1,
        wrapped: true,
        publicKeys: identity.public,
        payload: wrapped,
      };
    }
  } catch (err) {
    // If encryption fails, we still persist plaintext rather than
    // silently lose the key — the user's UI would otherwise enrol a
    // fresh keypair next visit and all existing shares to them would
    // become undecryptable.
    console.warn('[PRE] Failed to wrap umbral secret under master key:', err);
  }

  try {
    ls.setItem(STORAGE_KEY, JSON.stringify(serialized));
    return true;
  } catch (err) {
    console.warn('[PRE] Failed to persist umbral identity:', err);
    return false;
  }
}

async function _loadIdentity() {
  const ls = _getLocalStorage();
  if (!ls) return null;
  const raw = ls.getItem(STORAGE_KEY) || ls.getItem(LEGACY_STORAGE_KEY);
  if (!raw) return null;

  let parsed;
  try {
    parsed = JSON.parse(raw);
  } catch (_err) {
    return null;
  }

  let secretBlob = parsed.payload;
  if (parsed.wrapped) {
    try {
      const crypto = getSecureVaultCrypto();
      if (!crypto?.initialized) return { ...parsed, locked: true };
      const plain = await crypto.decrypt(parsed.payload, {
        associatedData: 'fhe:pre:umbral_identity_v1',
      });
      secretBlob = JSON.parse(plain);
    } catch (err) {
      console.warn('[PRE] Failed to unwrap umbral identity:', err);
      return { ...parsed, locked: true };
    }
  }

  return {
    publicKeys: parsed.publicKeys,
    rawSecrets: {
      sk: _b64ToBytes(secretBlob.sk),
      signerSk: _b64ToBytes(secretBlob.signerSk),
    },
    wrapped: !!parsed.wrapped,
    locked: false,
  };
}

/**
 * Ensure the current user has an Umbral identity both locally and
 * registered with the backend. Returns:
 *
 *   - `{ ready: true, publicKeys, rawSecrets }` — everything loaded,
 *     recipient flows can proceed.
 *   - `{ ready: false, reason: 'pre_unavailable' }` — WASM missing.
 *   - `{ ready: false, reason: 'locked', publicKeys }` — identity
 *     exists on disk but the vault is still locked, so the SK can't
 *     be unwrapped; recipient flow must wait for unlock.
 */
export async function ensureUmbralIdentity(options = {}) {
  if (!(await isPreAvailable())) {
    return { ready: false, reason: 'pre_unavailable' };
  }

  const existing = await _loadIdentity();
  if (existing && existing.locked) {
    return {
      ready: false,
      reason: 'locked',
      publicKeys: existing.publicKeys,
    };
  }
  if (existing && existing.rawSecrets) {
    return {
      ready: true,
      publicKeys: existing.publicKeys,
      rawSecrets: existing.rawSecrets,
      wrapped: existing.wrapped,
    };
  }

  if (options.autoEnroll === false) {
    return { ready: false, reason: 'not_enrolled' };
  }

  let identity;
  try {
    identity = await preClient.generateKeyPair();
  } catch (err) {
    if (err instanceof UmbralUnavailableError) {
      return { ready: false, reason: 'pre_unavailable' };
    }
    throw err;
  }
  await _persistIdentity(identity);

  try {
    await registerUmbralPublicKey({
      umbralPublicKey: identity.public.umbralPublicKey,
      umbralVerifyingKey: identity.public.umbralVerifyingKey,
      umbralSignerPublicKey: identity.public.umbralSignerPublicKey,
    });
  } catch (err) {
    console.warn(
      '[PRE] Failed to register umbral public key with server; '
      + 'will retry next visit:', err,
    );
  }

  return {
    ready: true,
    publicKeys: identity.public,
    rawSecrets: identity.secret,
    wrapped: false,
    freshlyEnrolled: true,
  };
}

/**
 * Force-rotate the Umbral identity. After calling this, all existing
 * umbral-v1 shares TO this user become undecryptable (intentional —
 * use for incident response).
 */
export async function rotateUmbralIdentity() {
  const ls = _getLocalStorage();
  if (ls) {
    ls.removeItem(STORAGE_KEY);
    ls.removeItem(LEGACY_STORAGE_KEY);
  }
  return ensureUmbralIdentity({ autoEnroll: true });
}

export default {
  ensureUmbralIdentity,
  rotateUmbralIdentity,
};

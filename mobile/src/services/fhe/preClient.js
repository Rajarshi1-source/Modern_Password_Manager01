/**
 * Mobile Umbral PRE client (JS half).
 *
 * The actual cryptography is delegated to a native module
 * (`react-native-fhe-autofill`) that wraps the platform's preferred
 * umbral implementation:
 *
 *   - Android: `com.cockroachdb.umbral.UmbralJni` bindings against
 *     the Rust `umbral-pre` crate (compiled to `.so` via `jni` /
 *     NDK).  The JNI layer is invoked from the Kotlin
 *     `FheAutofillModule`.
 *   - iOS: a Swift wrapper around the same Rust crate, exposed
 *     through `FheAutofillModule.swift`.
 *
 * If the native module is absent (for example during the Expo
 * managed workflow before a dev-client rebuild), this file falls
 * back to a pure-JS implementation pulled in dynamically, mirroring
 * `frontend/src/services/fhe/preClient.js`.  The pure-JS path will
 * load `@nucypher/umbral-pre` if available.
 */

import { NativeModules, Platform } from 'react-native';

const NativeFheAutofill = NativeModules?.FheAutofill || null;

export class UmbralUnavailableError extends Error {
  constructor(message = 'Umbral is not available on this device') {
    super(message);
    this.name = 'UmbralUnavailableError';
  }
}

let _jsUmbral = null;
async function _loadJsUmbral() {
  if (_jsUmbral) return _jsUmbral;
  try {
    const name = ['@nucypher', 'umbral-pre'].join('/');
    const mod = await import(/* @vite-ignore */ name);
    _jsUmbral = mod && mod.SecretKey ? mod : mod.default;
    if (!_jsUmbral || !_jsUmbral.SecretKey) throw new Error('umbral-pre shape unexpected');
    return _jsUmbral;
  } catch (err) {
    throw new UmbralUnavailableError(err?.message || String(err));
  }
}

export async function isAvailable() {
  if (NativeFheAutofill?.isUmbralAvailable) {
    try {
      return !!(await NativeFheAutofill.isUmbralAvailable());
    } catch (_e) {
      // fall through to JS fallback probe
    }
  }
  try { await _loadJsUmbral(); return true; } catch (_e) { return false; }
}

/**
 * Returns `{ secret: { sk, signerSk }, public: { umbralPublicKey, umbralVerifyingKey, umbralSignerPublicKey } }`.
 * Secret fields are base64url strings on all platforms so the
 * react-native bridge doesn't have to round-trip binary buffers.
 */
export async function generateKeyPair() {
  if (NativeFheAutofill?.generateKeyPair) {
    const pair = await NativeFheAutofill.generateKeyPair();
    return pair;
  }
  const umbral = await _loadJsUmbral();
  const sk = umbral.SecretKey.random();
  const signerSk = umbral.SecretKey.random();
  const signer = new umbral.Signer(signerSk);
  const bytesToB64Url = (b) => {
    let s = '';
    for (let i = 0; i < b.length; i += 1) s += String.fromCharCode(b[i]);
    return btoa(s).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
  };
  return {
    secret: {
      sk: bytesToB64Url(sk.toSecretBytes()),
      signerSk: bytesToB64Url(signerSk.toSecretBytes()),
    },
    public: {
      umbralPublicKey: bytesToB64Url(sk.publicKey().toBytes()),
      umbralVerifyingKey: bytesToB64Url(signerSk.publicKey().toBytes()),
      umbralSignerPublicKey: bytesToB64Url(signer.verifyingKey().toBytes()),
    },
  };
}

/**
 * Decrypt a PRE payload and return the plaintext as a utf-8 string.
 * On Android/iOS, the native layer writes the plaintext into the
 * platform autofill framework *without* returning it to the JS
 * thread when `options.sealedAutofill` is true.  In that case the
 * return value is `{ autofilled: true, domain }`.
 */
export async function decryptReencrypted(payload, options = {}) {
  if (NativeFheAutofill?.decryptReencrypted) {
    return NativeFheAutofill.decryptReencrypted(payload, options || {});
  }
  const umbral = await _loadJsUmbral();
  const b64ToBytes = (s) => {
    const c = s.replace(/-/g, '+').replace(/_/g, '/');
    const pad = c.length % 4 === 0 ? '' : '='.repeat(4 - (c.length % 4));
    const bin = atob(c + pad);
    const out = new Uint8Array(bin.length);
    for (let i = 0; i < bin.length; i += 1) out[i] = bin.charCodeAt(i);
    return out;
  };
  const sk = umbral.SecretKey.fromBytes(b64ToBytes(payload.recipientSk));
  const delegatingPk = umbral.PublicKey.fromBytes(b64ToBytes(payload.delegatingPk));
  const verifyingPk = umbral.PublicKey.fromBytes(b64ToBytes(payload.verifyingPk));
  const capsule = umbral.Capsule.fromBytes(b64ToBytes(payload.capsule));
  const cfrag = umbral.CapsuleFrag.fromBytes(b64ToBytes(payload.cfrag));
  const verified = cfrag.verify(capsule, verifyingPk, delegatingPk, sk.publicKey());
  const ciphertext = b64ToBytes(payload.ciphertext);
  const plain = umbral.decryptReencrypted(sk, delegatingPk, capsule, [verified], ciphertext);
  return { plaintext: new TextDecoder().decode(plain) };
}

/**
 * Open the platform's autofill settings screen so the user can
 * enable this app as their autofill provider.
 */
export async function openAutofillSettings() {
  if (Platform.OS !== 'android') {
    throw new Error('openAutofillSettings is Android-only today.');
  }
  if (!NativeFheAutofill?.openSystemAutofillSettings) {
    throw new Error('Native module not installed (expo-dev-client rebuild required).');
  }
  return NativeFheAutofill.openSystemAutofillSettings();
}

export async function isSystemAutofillEnabled() {
  if (!NativeFheAutofill?.isSystemAutofillEnabled) return false;
  return !!(await NativeFheAutofill.isSystemAutofillEnabled());
}

export default {
  isAvailable,
  generateKeyPair,
  decryptReencrypted,
  openAutofillSettings,
  isSystemAutofillEnabled,
  UmbralUnavailableError,
};

/**
 * Proxy Re-Encryption (PRE) client — Umbral wrapper for the web.
 *
 * Responsibilities:
 *   - Generate the user's Umbral keypair locally.
 *   - Encrypt the password with `pk_O` to produce (capsule, ciphertext).
 *   - Build the re-encryption delegation kfrag targeted at pk_R.
 *   - Decrypt (capsule, cfrag, ciphertext) client-side for autofill.
 *
 * Design:
 *   - Lazy-loads `@nucypher/umbral-pre` (WASM) — the dependency is optional.
 *   - If the module isn't installed, we export stub methods that throw
 *     `UmbralUnavailableError`. This keeps the rest of the UI importable
 *     in environments where the WASM blob isn't shipped.
 *   - Secret keys are serialized and handed back to the caller to store
 *     (encrypted under the master key via `secureVaultCrypto`).
 *
 * See password_manager/fhe_sharing/SPEC.md.
 */

let _umbral = null;
let _loadPromise = null;

export class UmbralUnavailableError extends Error {
  constructor(message = 'Umbral WASM module not available') {
    super(message);
    this.name = 'UmbralUnavailableError';
  }
}

async function loadUmbral() {
  if (_umbral) return _umbral;
  if (_loadPromise) return _loadPromise;
  _loadPromise = (async () => {
    try {
      // Specifier is constructed at runtime so bundlers don't try to
      // statically resolve the optional peer dependency.
      const moduleName = ['@nucypher', 'umbral-pre'].join('/');
      const mod = await import(/* @vite-ignore */ moduleName);
      _umbral = mod && mod.SecretKey ? mod : mod.default;
      if (!_umbral || !_umbral.SecretKey) {
        throw new Error('umbral-pre module shape unexpected');
      }
      return _umbral;
    } catch (err) {
      _umbral = null;
      throw new UmbralUnavailableError(err?.message || String(err));
    }
  })();
  return _loadPromise;
}

// ---------------------------------------------------------------------------
// Base64url helpers (byte-exact with backend Python `base64.urlsafe_b64encode`)
// ---------------------------------------------------------------------------

function bytesToBase64Url(bytes) {
  let bin = '';
  for (let i = 0; i < bytes.length; i += 1) bin += String.fromCharCode(bytes[i]);
  return btoa(bin).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
}

function base64UrlToBytes(s) {
  const cleaned = s.replace(/-/g, '+').replace(/_/g, '/');
  const pad = cleaned.length % 4 === 0 ? '' : '='.repeat(4 - (cleaned.length % 4));
  const bin = atob(cleaned + pad);
  const out = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i += 1) out[i] = bin.charCodeAt(i);
  return out;
}

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

/**
 * @returns {Promise<boolean>}  true if the Umbral WASM is usable.
 */
export async function isPreAvailable() {
  try {
    await loadUmbral();
    return true;
  } catch (_err) {
    return false;
  }
}

/**
 * Generate a fresh Umbral keypair + signer.
 * Returns the public material encoded as base64url so it's safe to
 * upload directly to `/api/fhe-sharing/keys/register/`.
 *
 * The secret material is returned as raw `Uint8Array`s so the caller
 * can encrypt it under the master key before persisting.
 */
export async function generateKeyPair() {
  const umbral = await loadUmbral();
  const sk = umbral.SecretKey.random();
  const pk = sk.publicKey();

  const signerSk = umbral.SecretKey.random();
  const signer = new umbral.Signer(signerSk);
  const verifyingPk = signerSk.publicKey();

  return {
    secret: {
      sk: sk.toSecretBytes(),
      signerSk: signerSk.toSecretBytes(),
    },
    public: {
      umbralPublicKey: bytesToBase64Url(pk.toBytes()),
      umbralVerifyingKey: bytesToBase64Url(verifyingPk.toBytes()),
      umbralSignerPublicKey: bytesToBase64Url(signer.verifyingKey().toBytes()),
    },
  };
}

/**
 * Client-side encryption.
 * @param {string} publicKeyB64  owner's Umbral public key (base64url).
 * @param {Uint8Array|string} message  plaintext message (string is UTF-8 encoded).
 * @returns {{capsule: string, ciphertext: string}}  both base64url-encoded.
 */
export async function encryptFor(publicKeyB64, message) {
  const umbral = await loadUmbral();
  const pk = umbral.PublicKey.fromBytes(base64UrlToBytes(publicKeyB64));
  const plaintext = typeof message === 'string'
    ? new TextEncoder().encode(message)
    : message;
  const { capsule, ciphertext } = umbral.encrypt(pk, plaintext);
  return {
    capsule: bytesToBase64Url(capsule.toBytes()),
    ciphertext: bytesToBase64Url(ciphertext),
  };
}

/**
 * Generate a single re-encryption kfrag from owner -> recipient.
 *
 * @param {Object} args
 * @param {Uint8Array} args.ownerSkBytes     owner's secret key bytes
 * @param {Uint8Array} args.signerSkBytes    owner's signing secret key bytes
 * @param {string} args.recipientPkB64       recipient's umbral public key (base64url)
 * @returns {string}  base64url-encoded kfrag bytes.
 */
export async function generateKfrag({ ownerSkBytes, signerSkBytes, recipientPkB64 }) {
  const umbral = await loadUmbral();
  const ownerSk = umbral.SecretKey.fromBytes(ownerSkBytes);
  const signerSk = umbral.SecretKey.fromBytes(signerSkBytes);
  const signer = new umbral.Signer(signerSk);
  const recipientPk = umbral.PublicKey.fromBytes(base64UrlToBytes(recipientPkB64));

  const kfrags = umbral.generateKFrags(
    ownerSk,
    recipientPk,
    signer,
    /* threshold */ 1,
    /* shares */ 1,
    /* signDelegatingKey */ true,
    /* signReceivingKey */ true,
  );
  return bytesToBase64Url(kfrags[0].toBytes());
}

/**
 * Recipient-side decryption.  Combines (capsule, cfrag, ciphertext) into
 * plaintext. The returned value is a `Uint8Array`; the caller decodes
 * UTF-8 if the original message was a string.
 */
export async function decryptReencrypted({
  recipientSkBytes,
  delegatingPkB64,
  verifyingPkB64,
  capsuleB64,
  cfragB64,
  ciphertextB64,
}) {
  const umbral = await loadUmbral();
  const sk = umbral.SecretKey.fromBytes(recipientSkBytes);
  const delegatingPk = umbral.PublicKey.fromBytes(base64UrlToBytes(delegatingPkB64));
  const verifyingPk = umbral.PublicKey.fromBytes(base64UrlToBytes(verifyingPkB64));
  const capsule = umbral.Capsule.fromBytes(base64UrlToBytes(capsuleB64));
  const cfragRaw = umbral.CapsuleFrag.fromBytes(base64UrlToBytes(cfragB64));
  const ciphertext = base64UrlToBytes(ciphertextB64);

  // Verify integrity before decrypt.
  const verifiedCfrag = cfragRaw.verify(
    capsule,
    verifyingPk,
    delegatingPk,
    sk.publicKey(),
  );

  return umbral.decryptReencrypted(
    sk,
    delegatingPk,
    capsule,
    [verifiedCfrag],
    ciphertext,
  );
}

// Re-export base64 helpers so components can avoid reimplementing them.
export const preB64 = {
  encode: bytesToBase64Url,
  decode: base64UrlToBytes,
};

const preClient = {
  isPreAvailable,
  generateKeyPair,
  encryptFor,
  generateKfrag,
  decryptReencrypted,
  UmbralUnavailableError,
  b64: preB64,
};

export default preClient;

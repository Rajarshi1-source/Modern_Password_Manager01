/**
 * Extension-side Umbral PRE client.
 *
 * Mirrors the behaviour of `frontend/src/services/fhe/preClient.js` but
 * lives inside the extension bundle so neither the content script nor
 * the service worker touches the dashboard's JS context.
 *
 * Uses dynamic import with a runtime-built specifier so the bundler
 * treats the dependency as optional: builds without
 * ``@nucypher/umbral-pre`` installed still succeed.
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
      const name = ['@nucypher', 'umbral-pre'].join('/');
      const mod = await import(/* webpackIgnore: true */ name);
      _umbral = mod && mod.SecretKey ? mod : mod.default;
      if (!_umbral || !_umbral.SecretKey) {
        throw new Error('umbral-pre shape unexpected');
      }
      return _umbral;
    } catch (err) {
      _umbral = null;
      throw new UmbralUnavailableError(err?.message || String(err));
    }
  })();
  return _loadPromise;
}

function bytesToB64Url(b) {
  let s = '';
  for (let i = 0; i < b.length; i += 1) s += String.fromCharCode(b[i]);
  return btoa(s).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
}

function b64UrlToBytes(s) {
  const c = s.replace(/-/g, '+').replace(/_/g, '/');
  const pad = c.length % 4 === 0 ? '' : '='.repeat(4 - (c.length % 4));
  const bin = atob(c + pad);
  const out = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i += 1) out[i] = bin.charCodeAt(i);
  return out;
}

export async function isAvailable() {
  try { await loadUmbral(); return true; } catch (_e) { return false; }
}

export async function generateKeyPair() {
  const umbral = await loadUmbral();
  const sk = umbral.SecretKey.random();
  const signerSk = umbral.SecretKey.random();
  const signer = new umbral.Signer(signerSk);
  return {
    secret: { sk: sk.toSecretBytes(), signerSk: signerSk.toSecretBytes() },
    public: {
      umbralPublicKey: bytesToB64Url(sk.publicKey().toBytes()),
      umbralVerifyingKey: bytesToB64Url(signerSk.publicKey().toBytes()),
      umbralSignerPublicKey: bytesToB64Url(signer.verifyingKey().toBytes()),
    },
  };
}

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
  const delegatingPk = umbral.PublicKey.fromBytes(b64UrlToBytes(delegatingPkB64));
  const verifyingPk = umbral.PublicKey.fromBytes(b64UrlToBytes(verifyingPkB64));
  const capsule = umbral.Capsule.fromBytes(b64UrlToBytes(capsuleB64));
  const cfragRaw = umbral.CapsuleFrag.fromBytes(b64UrlToBytes(cfragB64));
  const ciphertext = b64UrlToBytes(ciphertextB64);
  const verified = cfragRaw.verify(capsule, verifyingPk, delegatingPk, sk.publicKey());
  return umbral.decryptReencrypted(sk, delegatingPk, capsule, [verified], ciphertext);
}

export const b64 = { encode: bytesToB64Url, decode: b64UrlToBytes };

export default { isAvailable, generateKeyPair, decryptReencrypted, b64, UmbralUnavailableError };

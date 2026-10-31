/**
 * Hybrid X25519 + ML-KEM-768 sealing for client-to-client key transport.
 *
 * Used to move recovery shares between devices (owner -> guardian ->
 * requester) through a server that must not be able to open them. The
 * sealed value stays safe while EITHER X25519 or ML-KEM-768 holds:
 *
 *   key = HKDF-SHA256(ikm  = ss_mlkem || ss_x25519,
 *                     salt = "",
 *                     info = "pwm-hybrid-kem-v1" || mlkem_ct || x25519_eph
 *                            || recipient_x25519 || SHA-256(recipient_mlkem))
 *
 * Both shared secrets and both ciphertexts go into the KDF, so neither
 * component can be swapped or replayed on its own. The derived key seals the
 * plaintext with AES-256-GCM; `context` is the AAD.
 *
 * Wire formats (mirrored by password_manager/shared/sealed_shares.py, which
 * only checks shapes; the server holds no key that opens a sealed value):
 *
 *   public key  = x25519_public (32) || ml_kem_768_ek (1184)
 *   secret key  = x25519_secret (32) || ml_kem_768_dk (2400)
 *   sealed      = 0x01 || x25519_eph (32) || mlkem_ct (1088) || nonce (12)
 *                 || AES-GCM ciphertext and tag
 *
 * There is no fallback: if ML-KEM is unavailable, sealing fails.
 */
import { x25519 } from '@noble/curves/ed25519';
import { hkdf } from '@noble/hashes/hkdf';
import { sha256 } from '@noble/hashes/sha256';
import { createMlKem768 } from 'mlkem';

export const HYBRID_KEM_ALGORITHM = 'X25519MLKEM768-HKDF-SHA256-AES256GCM-v1';

const X25519_SIZE = 32;
const MLKEM_PK_SIZE = 1184;
const MLKEM_SK_SIZE = 2400;
const MLKEM_CT_SIZE = 1088;
const NONCE_SIZE = 12;
const VERSION = 1;

export const HYBRID_PUBLIC_KEY_SIZE = X25519_SIZE + MLKEM_PK_SIZE;
export const HYBRID_SECRET_KEY_SIZE = X25519_SIZE + MLKEM_SK_SIZE;
const HEADER_SIZE = 1 + X25519_SIZE + MLKEM_CT_SIZE + NONCE_SIZE;

const INFO_LABEL = new TextEncoder().encode('pwm-hybrid-kem-v1');

let mlkemPromise = null;
function mlkem() {
  // Forget a failed start so a later call retries: a cached rejection would
  // fail every seal and open on the page, and recoverSeed would read that as
  // guardians sending bad shares.
  if (!mlkemPromise) {
    mlkemPromise = createMlKem768().catch((err) => {
      mlkemPromise = null;
      throw err;
    });
  }
  return mlkemPromise;
}

function concat(...parts) {
  const out = new Uint8Array(parts.reduce((n, p) => n + p.length, 0));
  let offset = 0;
  for (const p of parts) {
    out.set(p, offset);
    offset += p.length;
  }
  return out;
}

function requireBytes(value, size, name) {
  if (!(value instanceof Uint8Array) || value.length !== size) {
    throw new Error(`${name} must be ${size} bytes`);
  }
}

function x25519Shared(secret, publicKey) {
  const shared = x25519.getSharedSecret(secret, publicKey);
  // A low-order X25519 point gives an all-zero secret; refuse it.
  if (shared.every((b) => b === 0)) throw new Error('invalid X25519 public key');
  return shared;
}

function deriveKey(ssMlkem, ssX25519, mlkemCt, x25519Eph, recipientPublicKey) {
  const info = concat(
    INFO_LABEL,
    mlkemCt,
    x25519Eph,
    recipientPublicKey.subarray(0, X25519_SIZE),
    sha256(recipientPublicKey.subarray(X25519_SIZE)),
  );
  return hkdf(sha256, concat(ssMlkem, ssX25519), new Uint8Array(0), info, 32);
}

async function aesKey(raw) {
  return crypto.subtle.importKey('raw', raw, { name: 'AES-GCM' }, false, ['encrypt', 'decrypt']);
}

/** @returns {Promise<{publicKey: Uint8Array, secretKey: Uint8Array}>} */
export async function generateHybridKeyPair() {
  const kem = await mlkem();
  const [mlkemPk, mlkemSk] = kem.generateKeyPair();
  const xSecret = x25519.utils.randomPrivateKey();
  return {
    publicKey: concat(x25519.getPublicKey(xSecret), mlkemPk),
    secretKey: concat(xSecret, mlkemSk),
  };
}

/**
 * Seal `plaintext` to a hybrid public key.
 * @param {Uint8Array} recipientPublicKey
 * @param {Uint8Array} plaintext
 * @param {string} context  bound as AES-GCM AAD; the opener must pass the same
 * @returns {Promise<Uint8Array>}
 */
export async function sealToHybridKey(recipientPublicKey, plaintext, context) {
  requireBytes(recipientPublicKey, HYBRID_PUBLIC_KEY_SIZE, 'recipient public key');
  const kem = await mlkem();
  const [mlkemCt, ssMlkem] = kem.encap(recipientPublicKey.subarray(X25519_SIZE));
  const ephSecret = x25519.utils.randomPrivateKey();
  const ephPublic = x25519.getPublicKey(ephSecret);
  const ssX25519 = x25519Shared(ephSecret, recipientPublicKey.subarray(0, X25519_SIZE));
  const key = deriveKey(ssMlkem, ssX25519, mlkemCt, ephPublic, recipientPublicKey);
  const nonce = crypto.getRandomValues(new Uint8Array(NONCE_SIZE));
  const ct = new Uint8Array(await crypto.subtle.encrypt(
    { name: 'AES-GCM', iv: nonce, additionalData: new TextEncoder().encode(context) },
    await aesKey(key),
    plaintext,
  ));
  return concat(new Uint8Array([VERSION]), ephPublic, mlkemCt, nonce, ct);
}

/**
 * Open a value sealed with {@link sealToHybridKey}. Throws on any mismatch
 * (wrong key, wrong context, altered bytes).
 * @param {Uint8Array} secretKey
 * @param {Uint8Array} publicKey  the recipient's own public key
 * @param {Uint8Array} sealed
 * @param {string} context
 * @returns {Promise<Uint8Array>}
 */
export async function openSealed(secretKey, publicKey, sealed, context) {
  requireBytes(secretKey, HYBRID_SECRET_KEY_SIZE, 'secret key');
  requireBytes(publicKey, HYBRID_PUBLIC_KEY_SIZE, 'public key');
  if (!(sealed instanceof Uint8Array) || sealed.length <= HEADER_SIZE + 16 || sealed[0] !== VERSION) {
    throw new Error('not a sealed value');
  }
  let offset = 1;
  const ephPublic = sealed.subarray(offset, (offset += X25519_SIZE));
  const mlkemCt = sealed.subarray(offset, (offset += MLKEM_CT_SIZE));
  const nonce = sealed.subarray(offset, (offset += NONCE_SIZE));
  const ct = sealed.subarray(offset);

  const kem = await mlkem();
  const ssMlkem = kem.decap(mlkemCt, secretKey.subarray(X25519_SIZE));
  const ssX25519 = x25519Shared(secretKey.subarray(0, X25519_SIZE), ephPublic);
  const key = deriveKey(ssMlkem, ssX25519, mlkemCt, ephPublic, publicKey);
  return new Uint8Array(await crypto.subtle.decrypt(
    { name: 'AES-GCM', iv: nonce, additionalData: new TextEncoder().encode(context) },
    await aesKey(key),
    ct,
  ));
}

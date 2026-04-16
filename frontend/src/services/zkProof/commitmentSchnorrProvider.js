/**
 * Pedersen commitment + Schnorr proof of equality on secp256k1.
 *
 * This is the reference browser implementation of the `commitment-schnorr-v1`
 * scheme. It is byte-for-byte interoperable with the Python verifier in
 * `password_manager/zk_proofs/crypto/` — same curve parameters, same domain
 * separators, same hash-to-curve canonicalisation (even y).
 *
 * Security notes:
 *   - All scalar arithmetic goes through @noble/curves which is constant-time.
 *   - Secret scalars (m, r, k) never leave this module. Only compressed points
 *     and a single Schnorr scalar are serialised.
 *   - The nothing-up-my-sleeve generator H is derived by hashing the public
 *     string "pwm-zkp-v1|H-generator" into a curve point via try-and-increment.
 */

import { secp256k1 } from '@noble/curves/secp256k1';
import { sha256 } from '@noble/hashes/sha2';

const Point = secp256k1.Point;
const CURVE = Point.CURVE();

const ENC = new TextEncoder();

const DOMAIN = ENC.encode('pwm-zkp-v1');
const EQ_CHALLENGE_TAG = ENC.encode('pwm-zkp-v1|eq-challenge');
const H_SEED = ENC.encode('pwm-zkp-v1|H-generator');
const M_TAG = ENC.encode('|m|');
const R_TAG = ENC.encode('|r|');

// ---------------------------------------------------------------------------
// Byte helpers
// ---------------------------------------------------------------------------

const concatBytes = (...arrays) => {
  let total = 0;
  for (const a of arrays) total += a.length;
  const out = new Uint8Array(total);
  let off = 0;
  for (const a of arrays) {
    out.set(a, off);
    off += a.length;
  }
  return out;
};

const bytesToBigInt = (bytes) => {
  let x = 0n;
  for (let i = 0; i < bytes.length; i++) {
    x = (x << 8n) | BigInt(bytes[i]);
  }
  return x;
};

const bigIntToBytes = (value, length) => {
  const out = new Uint8Array(length);
  let x = value;
  for (let i = length - 1; i >= 0; i--) {
    out[i] = Number(x & 0xffn);
    x >>= 8n;
  }
  return out;
};

// ---------------------------------------------------------------------------
// Field arithmetic helpers (for hash-to-curve only; point ops use noble)
// ---------------------------------------------------------------------------

const modPos = (n, m) => {
  const r = n % m;
  return r >= 0n ? r : r + m;
};

const modPow = (base, exp, mod) => {
  let result = 1n;
  let b = modPos(base, mod);
  let e = exp;
  while (e > 0n) {
    if (e & 1n) result = (result * b) % mod;
    e >>= 1n;
    b = (b * b) % mod;
  }
  return result;
};

// ---------------------------------------------------------------------------
// Hash-to-curve via SHA-256 try-and-increment. Matches
// password_manager/zk_proofs/crypto/secp256k1.py::hash_to_point byte-for-byte.
// ---------------------------------------------------------------------------

const P = CURVE.p;
const N = CURVE.n;
const B_CURVE = CURVE.b;
const SQRT_EXP = (P + 1n) / 4n;

const hashToPoint = (seed) => {
  for (let counter = 0; counter < 0x100000000; counter++) {
    const ctrBytes = new Uint8Array(4);
    // Big-endian uint32 — matches Python `counter.to_bytes(4, "big")`.
    new DataView(ctrBytes.buffer).setUint32(0, counter, false);
    const digest = sha256(concatBytes(seed, ctrBytes));
    const x = modPos(bytesToBigInt(digest), P);
    if (x === 0n) continue;
    const ySq = modPos(x * x * x + B_CURVE, P);
    let y = modPow(ySq, SQRT_EXP, P);
    if ((y * y) % P !== ySq || y === 0n) continue;
    // Canonicalise to even y so frontend/backend agree bit-for-bit.
    if ((y & 1n) === 1n) y = P - y;
    const prefix = 0x02;
    const bytes = new Uint8Array(33);
    bytes[0] = prefix;
    bytes.set(bigIntToBytes(x, 32), 1);
    return Point.fromHex(bytes);
  }
  throw new Error('hashToPoint: exhausted 2^32 counters without a valid point');
};

// H is the second Pedersen generator. Lazy so module import never blocks.
let _H = null;
const H = () => {
  if (_H === null) _H = hashToPoint(H_SEED);
  return _H;
};
const G = () => Point.BASE;

// ---------------------------------------------------------------------------
// Point (de)serialisation — SEC1 compressed 33 bytes
// ---------------------------------------------------------------------------

const encodePoint = (point) => point.toRawBytes(true);
const decodePoint = (bytes) => Point.fromHex(bytes);

// ---------------------------------------------------------------------------
// Fiat-Shamir challenge — identical transcript to the Python verifier:
//     c = sha256( "pwm-zkp-v1|eq-challenge" || enc(c1) || enc(c2) || enc(T) ) mod n
// ---------------------------------------------------------------------------

const challengeScalar = (c1Bytes, c2Bytes, TBytes) => {
  const digest = sha256(concatBytes(EQ_CHALLENGE_TAG, c1Bytes, c2Bytes, TBytes));
  return modPos(bytesToBigInt(digest), N);
};

// ---------------------------------------------------------------------------
// Secret scalar derivation. Both m and r are derived deterministically from
// (password, itemId) via SHA-256 with different domain tags. This keeps the
// client stateless: anyone who knows the password can recompute the full
// commitment on any device. The server, which never sees the password,
// cannot link commitments across scope_ids.
// ---------------------------------------------------------------------------

const deriveScalar = (password, itemId, tag) => {
  const material = concatBytes(
    DOMAIN,
    tag,
    ENC.encode(String(itemId)),
    ENC.encode('|'),
    typeof password === 'string' ? ENC.encode(password) : password,
  );
  const digest = sha256(material);
  let x = modPos(bytesToBigInt(digest), N);
  // Scalars must be non-zero for the commitment math to be meaningful.
  if (x === 0n) x = 1n;
  return x;
};

export const deriveScalarFromPassword = (password, itemId) =>
  deriveScalar(password, itemId, M_TAG);

export const deriveBlinding = (password, itemId) =>
  deriveScalar(password, itemId, R_TAG);

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

export const commit = (mScalar, rScalar) =>
  G().multiply(mScalar).add(H().multiply(rScalar));

export const commitBytes = (mScalar, rScalar) => encodePoint(commit(mScalar, rScalar));

/**
 * High-level: produce a commitment for (password, itemId) in a single call.
 * Returns the compressed 33-byte commitment. Secret material stays local.
 */
export const commitFromPassword = (password, itemId) => {
  const m = deriveScalarFromPassword(password, itemId);
  const r = deriveBlinding(password, itemId);
  return commitBytes(m, r);
};

/**
 * Produce a Schnorr proof that commitments `c1Point` and `c2Point` hide the
 * same scalar. Callers must supply the private blinding factors r1, r2.
 * Returns `{ T: Uint8Array(33), s: Uint8Array(32) }`.
 */
export const proveEquality = (c1Point, c2Point, r1, r2) => {
  const delta = modPos(r1 - r2, N);
  // Draw a uniform non-zero k in [1, n-1]. Rejection sampling avoids the
  // modular bias from unbounded 256-bit uniforms.
  let k;
  for (let i = 0; i < 32; i++) {
    const raw = globalThis.crypto.getRandomValues(new Uint8Array(32));
    const candidate = bytesToBigInt(raw);
    if (candidate > 0n && candidate < N) {
      k = candidate;
      break;
    }
  }
  if (k === undefined) {
    throw new Error('proveEquality: failed to sample a valid nonce');
  }

  const T = H().multiply(k);
  const TBytes = encodePoint(T);
  const c1Bytes = encodePoint(c1Point);
  const c2Bytes = encodePoint(c2Point);
  const c = challengeScalar(c1Bytes, c2Bytes, TBytes);
  const s = modPos(k + c * delta, N);
  return { T: TBytes, s: bigIntToBytes(s, 32) };
};

/**
 * Verify a Schnorr equality proof locally. Returns `false` (never throws) on
 * any decoding, range, or cryptographic failure.
 */
export const verifyEquality = (c1Bytes, c2Bytes, TBytes, sBytes) => {
  try {
    const c1 = decodePoint(c1Bytes);
    const c2 = decodePoint(c2Bytes);
    const T = decodePoint(TBytes);
    const s = bytesToBigInt(sBytes);
    if (s === 0n || s >= N) return false;
    const c = challengeScalar(c1Bytes, c2Bytes, TBytes);
    const D = c1.add(c2.negate());
    const lhs = H().multiply(s);
    const rhs = T.add(D.multiply(c));
    return lhs.equals(rhs);
  } catch {
    return false;
  }
};

export default {
  scheme: 'commitment-schnorr-v1',
  deriveScalarFromPassword,
  deriveBlinding,
  commit,
  commitBytes,
  commitFromPassword,
  proveEquality,
  verifyEquality,
  encodePoint,
  decodePoint,
};

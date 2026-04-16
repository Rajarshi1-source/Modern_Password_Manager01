/**
 * Reputation-network crypto helpers (Phase 2a).
 *
 * Mirrors `password_reputation/providers/commitment_claim.py` exactly so the
 * binding_hash the client produces round-trips through the backend verifier.
 * Reuses the Pedersen commitment machinery from the existing
 * `commitment-schnorr-v1` ZK provider — a reputation proof is nothing more
 * than "here is a Pedersen commitment to a secret, and here is the entropy I
 * claim it has, bound to my user id".
 *
 * Entropy estimation uses the `zxcvbn`-style bits formula where available,
 * but we keep it dependency-free by falling back to a conservative
 * character-class estimator. The *server* does not trust this number; it
 * clamps to [MIN_ENTROPY_BITS, MAX_ENTROPY_BITS] and rate-limits.
 */

import { sha256 } from '@noble/hashes/sha2';

import commitmentSchnorrProvider from '../zkProof/commitmentSchnorrProvider';

const ENC = new TextEncoder();
const BINDING_DOMAIN = ENC.encode('pwm-reputation-v1|binding');

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

const u32be = (n) => {
  const x = Number(n) >>> 0;
  return new Uint8Array([(x >>> 24) & 0xff, (x >>> 16) & 0xff, (x >>> 8) & 0xff, x & 0xff]);
};

const u64be = (n) => {
  const v = BigInt(n);
  const out = new Uint8Array(8);
  for (let i = 7; i >= 0; i--) {
    out[i] = Number((v >> BigInt((7 - i) * 8)) & 0xffn);
  }
  return out;
};

/**
 * SHA-256(DOMAIN || len(C)|C || claim_bits || user_id) — must stay in sync
 * with `password_reputation.providers.commitment_claim._binding_hash`.
 */
export const computeBindingHash = ({ commitment, claimedBits, userId }) => {
  if (!(commitment instanceof Uint8Array)) {
    throw new Error('computeBindingHash: commitment must be Uint8Array.');
  }
  const payload = concatBytes(
    BINDING_DOMAIN,
    u32be(commitment.length),
    commitment,
    u32be(claimedBits),
    u64be(userId),
  );
  return sha256(payload);
};

/**
 * Produce a Pedersen commitment to the plaintext password scoped to
 * ``scopeId`` (which should be distinct from the zk_proofs commitment scope
 * so a reputation proof doesn't leak into the vault-item ZK namespace).
 */
export const commitmentForReputation = (password, scopeId) =>
  commitmentSchnorrProvider.commitFromPassword(password, `reputation:${scopeId}`);

/**
 * Dependency-free entropy estimator. Good enough to bucket passwords; the
 * server clamps + rate-limits regardless of what we send.
 *
 *   - log2(pool^length) with a small penalty for short passwords.
 */
export const estimateEntropyBits = (password) => {
  if (!password) return 0;
  let pool = 0;
  if (/[a-z]/.test(password)) pool += 26;
  if (/[A-Z]/.test(password)) pool += 26;
  if (/[0-9]/.test(password)) pool += 10;
  if (/[^a-zA-Z0-9]/.test(password)) pool += 32;
  if (pool === 0) pool = 1;
  const raw = password.length * Math.log2(pool);
  const lengthPenalty = password.length < 12 ? 4 : 0;
  return Math.max(0, Math.floor(raw - lengthPenalty));
};

export default {
  computeBindingHash,
  commitmentForReputation,
  estimateEntropyBits,
};

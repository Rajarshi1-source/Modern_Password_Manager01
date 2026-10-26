/**
 * Client side of guardian and social recovery.
 *
 *   Owner:     splits the recovery seed, seals each share to a guardian's
 *              hybrid public key, and sends only sealed shares, a proof
 *              digest per share and a seed check to the server.
 *   Guardian:  opens its sealed share on its own device, proves it can
 *              (share proof) when accepting, and on approval re-seals the
 *              share to the requester's one-time public key.
 *   Requester: opens the re-sealed shares, recombines the seed and checks it
 *              against the seed check before using it.
 *
 * The server stores and relays opaque values only (see
 * password_manager/shared/sealed_shares.py for the formats).
 */
import { hmac } from '@noble/hashes/hmac';
import { sha256 } from '@noble/hashes/sha256';
import {
  generateHybridKeyPair,
  openSealed,
  sealToHybridKey,
} from '../quantum/hybridKem';
import { combineShares, splitSecret } from './shamirGf256';

export const GUARDIAN_CONTEXT = 'pwm-recovery-share-v1|guardian';
export const REQUESTER_CONTEXT = 'pwm-recovery-share-v1|requester';

const encoder = new TextEncoder();

export function toB64(bytes) {
  let s = '';
  for (const b of bytes) s += String.fromCharCode(b);
  return btoa(s);
}

export function fromB64(value) {
  const s = atob(value);
  const out = new Uint8Array(s.length);
  for (let i = 0; i < s.length; i++) out[i] = s.charCodeAt(i);
  return out;
}

function concat(a, b) {
  const out = new Uint8Array(a.length + b.length);
  out.set(a);
  out.set(b, a.length);
  return out;
}

function equal(a, b) {
  if (a.length !== b.length) return false;
  let diff = 0;
  for (let i = 0; i < a.length; i++) diff |= a[i] ^ b[i];
  return diff === 0;
}

/** SHA-256("pwm-recovery-seed-check-v1|" || seed) */
export function seedCheck(seed) {
  return sha256(concat(encoder.encode('pwm-recovery-seed-check-v1|'), seed));
}

/** HMAC-SHA256(share, "pwm-recovery-share-proof-v1|" || SHA-256(public key)) */
export function shareProof(share, holderPublicKey) {
  return hmac(sha256, share, concat(
    encoder.encode('pwm-recovery-share-proof-v1|'), sha256(holderPublicKey),
  ));
}

/**
 * Owner: split `seed` and seal one share per guardian.
 * @param {{seed: Uint8Array, threshold: number, guardianPublicKeys: string[]}} args
 *   guardianPublicKeys are base64 hybrid public keys from the guardians' devices
 * @returns {Promise<{secretCheck: string, shares: Array<{shareIndex: number,
 *   sealedShare: string, shareProofHash: string}>}>}
 */
export async function sealSeedForGuardians({ seed, threshold, guardianPublicKeys }) {
  const shares = splitSecret(seed, guardianPublicKeys.length, threshold);
  try {
    const sealed = await Promise.all(shares.map(async (share, i) => {
      const publicKey = fromB64(guardianPublicKeys[i]);
      return {
        shareIndex: share[0],
        sealedShare: toB64(await sealToHybridKey(publicKey, share, GUARDIAN_CONTEXT)),
        shareProofHash: toB64(sha256(shareProof(share, publicKey))),
      };
    }));
    return { secretCheck: toB64(seedCheck(seed)), shares: sealed };
  } finally {
    shares.forEach((s) => s.fill(0));
  }
}

/**
 * Short fingerprint of a public key for checking it out of band.
 *
 * The server relays the requester's one-time key to guardians, so a
 * dishonest server could substitute its own key and collect the re-sealed
 * shares. The requester reads this fingerprint to each guardian over another
 * channel (phone, in person); the guardian re-seals only if it matches.
 * 80 bits of SHA-256, as five groups of four hex digits.
 */
export function keyFingerprint(publicKeyB64) {
  const digest = sha256(concat(encoder.encode('pwm-recovery-key-fingerprint-v1|'), fromB64(publicKeyB64)));
  const hex = Array.from(digest.subarray(0, 10), (b) => b.toString(16).padStart(2, '0')).join('');
  return hex.toUpperCase().match(/.{4}/g).join('-');
}

function normalizeFingerprint(value) {
  return String(value || '').toUpperCase().replace(/[^0-9A-F]/g, '');
}

/** Guardian or requester: a new hybrid key pair, base64-encoded. */
export async function newHolderKeyPair() {
  const { publicKey, secretKey } = await generateHybridKeyPair();
  return { publicKey: toB64(publicKey), secretKey: toB64(secretKey) };
}

/**
 * Guardian: open the sealed share and compute the proof sent on acceptance.
 * @returns {Promise<string>} base64 share proof
 */
export async function proveShareHolding({ keyPair, sealedShare }) {
  const publicKey = fromB64(keyPair.publicKey);
  const share = await openSealed(
    fromB64(keyPair.secretKey), publicKey, fromB64(sealedShare), GUARDIAN_CONTEXT,
  );
  try {
    return toB64(shareProof(share, publicKey));
  } finally {
    share.fill(0);
  }
}

/**
 * Guardian: open the sealed share and re-seal it to the requester's key.
 * Refuses unless `confirmedFingerprint` (what the requester read out over
 * another channel) matches the key the server handed over.
 * @returns {Promise<string>} base64 re-sealed share
 */
export async function resealShareForRequester({
  keyPair, sealedShare, requesterPublicKey, confirmedFingerprint,
}) {
  if (normalizeFingerprint(confirmedFingerprint)
      !== normalizeFingerprint(keyFingerprint(requesterPublicKey))) {
    throw new Error("the requester's key fingerprint does not match");
  }
  const share = await openSealed(
    fromB64(keyPair.secretKey), fromB64(keyPair.publicKey), fromB64(sealedShare),
    GUARDIAN_CONTEXT,
  );
  try {
    return toB64(await sealToHybridKey(fromB64(requesterPublicKey), share, REQUESTER_CONTEXT));
  } finally {
    share.fill(0);
  }
}

/**
 * Requester: open re-sealed shares and recombine the seed. Throws unless the
 * result matches `secretCheck`.
 * @returns {Promise<Uint8Array>} the recovery seed
 */
export async function recoverSeed({ keyPair, sealedShares, threshold, secretCheck }) {
  const secretKey = fromB64(keyPair.secretKey);
  const publicKey = fromB64(keyPair.publicKey);
  const shares = await Promise.all(sealedShares.map(
    (s) => openSealed(secretKey, publicKey, fromB64(s), REQUESTER_CONTEXT),
  ));
  try {
    if (shares.length < threshold) {
      throw new Error(`need ${threshold} shares, have ${shares.length}`);
    }
    const seed = combineShares(shares.slice(0, threshold));
    if (!equal(seedCheck(seed), fromB64(secretCheck))) {
      seed.fill(0);
      throw new Error('the recovered seed does not match; a share is wrong');
    }
    return seed;
  } finally {
    shares.forEach((s) => s.fill(0));
    secretKey.fill(0);
  }
}

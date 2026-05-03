/**
 * Shamir 2-of-2 secret split via XOR (one-time-pad construction).
 *
 * The textbook simplest correct 2-of-2 split: pick a uniformly random
 * `halfA` of the same length as the secret; set `halfB = secret XOR
 * halfA`. Either share alone is uniformly random and reveals NOTHING
 * about the secret. Combined via XOR they reconstruct the secret.
 *
 * (Full Shamir over GF(256) is unnecessary here — for a 2-of-2 split,
 * a degree-1 polynomial reduces to one-time-pad on each byte.)
 *
 * Used by Tier 3 (self-time-locked) recovery: one share lives offline
 * in a `.dlrec` file the user downloads; the other is stored
 * server-side, opaque, and only released after the time-lock delay.
 */

export function split2of2(secretBytes) {
  if (!(secretBytes instanceof Uint8Array)) {
    throw new TypeError('secretBytes must be a Uint8Array');
  }
  const halfA = window.crypto.getRandomValues(new Uint8Array(secretBytes.length));
  const halfB = new Uint8Array(secretBytes.length);
  for (let i = 0; i < secretBytes.length; i++) {
    halfB[i] = secretBytes[i] ^ halfA[i];
  }
  return { halfA, halfB };
}

export function combine2of2(halfA, halfB) {
  if (!(halfA instanceof Uint8Array) || !(halfB instanceof Uint8Array)) {
    throw new TypeError('shares must be Uint8Array');
  }
  if (halfA.length !== halfB.length) {
    throw new Error('share length mismatch');
  }
  const out = new Uint8Array(halfA.length);
  for (let i = 0; i < halfA.length; i++) {
    out[i] = halfA[i] ^ halfB[i];
  }
  return out;
}

const _b64Encode = (a) => {
  let s = '';
  for (let i = 0; i < a.byteLength; i++) s += String.fromCharCode(a[i]);
  return btoa(s);
};
const _b64Decode = (s) => {
  const bin = atob(s);
  const out = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i);
  return out;
};

export const _b64 = { encode: _b64Encode, decode: _b64Decode };

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

/**
 * Split a secret into two Shamir 2-of-2 shares via the XOR one-time-
 * pad construction. `halfA` is uniformly random (CSPRNG); `halfB` is
 * `secret XOR halfA`. Each share alone is information-theoretically
 * useless — a uniformly random byte string with no statistical
 * dependence on the secret.
 *
 * @param {Uint8Array} secretBytes - The secret to split.
 * @returns {{halfA: Uint8Array, halfB: Uint8Array}}
 * @throws {TypeError} if `secretBytes` is not a Uint8Array.
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

/**
 * Reconstruct the secret from two `split2of2` shares. The operation
 * is commutative — order doesn't matter — but both shares must have
 * the same length.
 *
 * @param {Uint8Array} halfA
 * @param {Uint8Array} halfB
 * @returns {Uint8Array}
 * @throws {TypeError} if either share is not a Uint8Array.
 * @throws {Error} if the shares have different lengths.
 */
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

/**
 * Base64 encode a `Uint8Array` (or array-buffer-like) to a string
 * suitable for transport in JSON. Sibling of `_b64Decode`.
 *
 * @param {Uint8Array | ArrayBufferLike} a
 * @returns {string}
 */
const _b64Encode = (a) => {
  let s = '';
  for (let i = 0; i < a.byteLength; i++) s += String.fromCharCode(a[i]);
  return btoa(s);
};

/**
 * Decode a base64 string back into a `Uint8Array`. Sibling of
 * `_b64Encode`.
 *
 * @param {string} s
 * @returns {Uint8Array}
 */
const _b64Decode = (s) => {
  const bin = atob(s);
  const out = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i);
  return out;
};

/**
 * Base64 helpers grouped under a single export so consumers can use
 * `_b64.encode` / `_b64.decode` without importing each individually.
 */
export const _b64 = { encode: _b64Encode, decode: _b64Decode };

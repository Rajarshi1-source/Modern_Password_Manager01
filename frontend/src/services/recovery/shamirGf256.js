/**
 * Shamir secret sharing over GF(2^8), byte by byte, on the client.
 *
 * Each share is `index (1 byte, 1..255) || one byte per secret byte`. Fewer
 * than `threshold` shares reveal nothing about the secret. Used for the
 * guardian and social recovery seed (see sealedShareRecovery.js); the server
 * never receives a share in the clear.
 */

// GF(2^8) with the AES polynomial x^8 + x^4 + x^3 + x + 1, generator 3.
const EXP = new Uint8Array(510);
const LOG = new Uint8Array(256);
(() => {
  let x = 1;
  for (let i = 0; i < 255; i++) {
    EXP[i] = x;
    LOG[x] = i;
    x ^= (x << 1) ^ (x & 0x80 ? 0x11b : 0);
  }
  for (let i = 255; i < 510; i++) EXP[i] = EXP[i - 255];
})();

function mul(a, b) {
  return a === 0 || b === 0 ? 0 : EXP[LOG[a] + LOG[b]];
}

function div(a, b) {
  if (b === 0) throw new Error('division by zero');
  return a === 0 ? 0 : EXP[LOG[a] + 255 - LOG[b]];
}

/**
 * @param {Uint8Array} secret
 * @param {number} total      number of shares, 2..255
 * @param {number} threshold  shares needed to recombine, 2..total
 * @returns {Uint8Array[]}    shares with indexes 1..total
 */
export function splitSecret(secret, total, threshold) {
  if (!(secret instanceof Uint8Array) || secret.length === 0) {
    throw new TypeError('secret must be a non-empty Uint8Array');
  }
  if (!Number.isInteger(total) || !Number.isInteger(threshold)
      || threshold < 2 || threshold > total || total > 255) {
    throw new RangeError('need 2 <= threshold <= total <= 255');
  }
  const shares = Array.from({ length: total }, (_, i) => {
    const share = new Uint8Array(secret.length + 1);
    share[0] = i + 1;
    return share;
  });
  const coefficients = new Uint8Array(threshold - 1);
  for (let byte = 0; byte < secret.length; byte++) {
    crypto.getRandomValues(coefficients);
    for (const share of shares) {
      const x = share[0];
      // Horner: secret + c1*x + c2*x^2 + ...
      let y = 0;
      for (let k = coefficients.length - 1; k >= 0; k--) y = mul(y ^ coefficients[k], x);
      share[byte + 1] = y ^ secret[byte];
    }
  }
  coefficients.fill(0);
  return shares;
}

/**
 * Recombine shares by Lagrange interpolation at x = 0. Any `threshold`
 * shares give the secret; fewer give an unrelated value, so check the
 * result against a commitment (sealedShareRecovery.js does).
 * @param {Uint8Array[]} shares
 * @returns {Uint8Array}
 */
export function combineShares(shares) {
  if (!Array.isArray(shares) || shares.length < 2) throw new Error('need at least two shares');
  const length = shares[0].length;
  const xs = shares.map((s) => s[0]);
  if (shares.some((s) => s.length !== length) || xs.some((x) => x === 0)
      || new Set(xs).size !== xs.length) {
    throw new Error('shares are malformed or repeated');
  }
  const secret = new Uint8Array(length - 1);
  for (let byte = 0; byte < secret.length; byte++) {
    let acc = 0;
    for (let i = 0; i < shares.length; i++) {
      let basis = 1;
      for (let j = 0; j < shares.length; j++) {
        if (i !== j) basis = mul(basis, div(xs[j], xs[j] ^ xs[i]));
      }
      acc ^= mul(shares[i][byte + 1], basis);
    }
    secret[byte] = acc;
  }
  return secret;
}

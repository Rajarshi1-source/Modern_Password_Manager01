/**
 * Hex encoding helpers shared across the layered-recovery UI.
 *
 * Lives here rather than inside each component so the encoding format
 * cannot drift between enroll and recover sites — both must produce
 * the same hex form of a recovery seed for the Argon2 KDF input to
 * match.
 */

/**
 * Render a `Uint8Array` (or any indexable byte sequence) as a
 * lowercase hex string with no separators.
 *
 * @param {Uint8Array} bytes
 * @returns {string} 2*bytes.length lowercase hex characters.
 */
export function bytesToHex(bytes) {
  return Array.from(bytes, (b) => b.toString(16).padStart(2, '0')).join('');
}

/**
 * Parse a hex string (even length, no separators) into bytes.
 *
 * @param {string} hex
 * @returns {Uint8Array}
 * @throws {Error} on odd length or a non-hex character.
 */
export function hexToBytes(hex) {
  if (typeof hex !== 'string' || hex.length % 2 !== 0 || !/^[0-9a-fA-F]*$/.test(hex)) {
    throw new Error('not a hex string');
  }
  const out = new Uint8Array(hex.length / 2);
  for (let i = 0; i < out.length; i++) out[i] = parseInt(hex.slice(2 * i, 2 * i + 2), 16);
  return out;
}

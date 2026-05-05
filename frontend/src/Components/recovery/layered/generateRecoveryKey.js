/**
 * Generate a 26-character user-facing recovery key.
 *
 * Alphabet excludes I, O, 0, 1 (transcription footguns). Formatted in
 * groups of four with hyphens for readability:
 *   ABCD-EFGH-JKLM-NPQR-STUV-WXYZ-23
 *
 * Built from `crypto.getRandomValues` — never leaves the browser.
 *
 * **Unbiased sampling.** We use rejection sampling rather than
 * `byte % ALPHABET.length`. With ALPHABET.length == 32 the modulo
 * mapping happens to be exact (256 % 32 == 0) so no bias is introduced
 * for the current alphabet — but CodeQL flags any modulo on a CSPRNG
 * byte as a potential bias source, and a future change to the alphabet
 * (say, adding one extra character to make 33) would silently produce
 * a biased key with the modulo approach. Rejection sampling is robust
 * against that future regression: bytes that fall in the trailing
 * partial range (>= 256 - (256 mod alphabet)) are discarded and re-
 * sampled, so every output character is uniformly distributed.
 */
const ALPHABET = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789';
const KEY_LENGTH = 26;

export function generateRecoveryKey() {
  const alphabetLength = ALPHABET.length;
  // Largest multiple of `alphabetLength` that fits in a byte. Bytes
  // at or above this threshold are rejected to avoid modulo bias.
  // For the current 32-char alphabet this threshold is 256, so no
  // byte is rejected; for any other alphabet size the rejection
  // window protects uniformity.
  const maxUnbiased = 256 - (256 % alphabetLength);

  let out = '';
  let i = 0;
  while (i < KEY_LENGTH) {
    const byte = window.crypto.getRandomValues(new Uint8Array(1))[0];
    if (byte >= maxUnbiased) continue;
    if (i && i % 4 === 0) out += '-';
    out += ALPHABET[byte % alphabetLength];
    i++;
  }
  return out;
}

/**
 * Normalize user input back to canonical formatted form. Accepts the
 * 26-character key with or without hyphens, with mixed case and spaces.
 * Returns the canonical formatted key, or null if not exactly 26
 * alphabet characters after normalization.
 */
export function normalizeRecoveryKey(input) {
  if (typeof input !== 'string') return null;
  const compact = input.replace(/[\s-]/g, '').toUpperCase();
  if (compact.length !== 26) return null;
  for (const ch of compact) {
    if (!ALPHABET.includes(ch)) return null;
  }
  let out = '';
  for (let i = 0; i < 26; i++) {
    if (i && i % 4 === 0) out += '-';
    out += compact[i];
  }
  return out;
}

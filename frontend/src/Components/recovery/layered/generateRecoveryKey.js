/**
 * Generate a 26-character user-facing recovery key.
 *
 * Alphabet excludes I, O, 0, 1 (transcription footguns). Formatted in
 * groups of four with hyphens for readability:
 *   ABCD-EFGH-JKLM-NPQR-STUV-WXYZ-23
 *
 * Built from `crypto.getRandomValues` — never leaves the browser.
 */
const ALPHABET = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789';

export function generateRecoveryKey() {
  const bytes = window.crypto.getRandomValues(new Uint8Array(26));
  let out = '';
  for (let i = 0; i < 26; i++) {
    if (i && i % 4 === 0) out += '-';
    out += ALPHABET[bytes[i] % ALPHABET.length];
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

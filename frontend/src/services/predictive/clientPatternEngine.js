/**
 * Client-Side Password Pattern Engine (Zero-Knowledge)
 * =====================================================
 *
 * A faithful browser port of the *structural* parts of the server's
 * `pattern_analysis_engine.py`. It runs over the decrypted vault in the
 * browser and produces an irreversible structural fingerprint:
 *
 *   - char-class sequence ("ULLLLDDDD")  — never the actual characters
 *   - length + length bucket
 *   - Shannon-entropy band               — never the exact password
 *   - boolean habit flags (dictionary base / keyboard / dates / leet)
 *   - a structure hash = SHA-256(charClassSeq:lengthBucket)
 *
 * INVARIANT: the output NEVER contains the password or any detected
 * dictionary word. Only the booleans and the aggregate shape leave the
 * device. This is what makes the predictive-expiration feature compatible
 * with the zero-knowledge model.
 *
 * The constants below intentionally mirror the Python engine so the client
 * fingerprint and any server-side reference computation agree.
 */

// Common leet-speak substitutions (mirrors PatternAnalysisEngine.LEET_MAPPINGS).
const LEET_MAPPINGS = {
  a: ['@', '4'],
  e: ['3'],
  i: ['1', '!'],
  o: ['0'],
  s: ['$', '5'],
  t: ['7'],
  l: ['1'],
  b: ['8'],
  g: ['9'],
};

// Reverse map for detection / normalisation (Map avoids computed-key access).
const REVERSE_LEET = new Map();
for (const [letter, subs] of Object.entries(LEET_MAPPINGS)) {
  for (const sub of subs) {
    REVERSE_LEET.set(sub, letter);
  }
}

const KEYBOARD_PATTERNS = [
  'qwerty', 'qwertyuiop', 'asdf', 'asdfgh', 'zxcvbn',
  '123456', '12345678', '1234567890',
  'qazwsx', 'qweasd', '1qaz2wsx',
  'password', 'pass', 'passwd',
];

const COMMON_BASE_WORDS = [
  'password', 'letmein', 'welcome', 'monkey', 'dragon',
  'master', 'login', 'admin', 'princess', 'sunshine',
  'shadow', 'football', 'baseball', 'soccer', 'hockey',
  'summer', 'winter', 'spring', 'autumn', 'love',
  'hello', 'secret', 'access', 'trustno', 'computer',
];

const DATE_PATTERNS = [
  /\d{4}$/,            // Year at end (2024)
  /\d{2}\d{2}\d{2,4}/, // MMDDYY or MMDDYYYY
  /\d{4}\d{2}\d{2}/,   // YYYYMMDD
  /19\d{2}/,           // 19XX
  /20\d{2}/,           // 20XX
];

/** Classify a single character into U / L / D / S. */
export function classifyChar(ch) {
  if (ch >= 'a' && ch <= 'z') return 'L';
  if (ch >= 'A' && ch <= 'Z') return 'U';
  if (ch >= '0' && ch <= '9') return 'D';
  // Unicode letters: treat by case where possible, else symbol.
  if (ch.toLowerCase() !== ch.toUpperCase()) {
    return ch === ch.toLowerCase() ? 'L' : 'U';
  }
  return 'S';
}

/** Build the char-class sequence, e.g. "ULLLLDDDD". */
export function charClassSequence(password) {
  let seq = '';
  for (const ch of password) seq += classifyChar(ch);
  return seq;
}

/** Length bucket (mirrors PatternAnalysisEngine._get_length_bucket). */
export function lengthBucket(length) {
  if (length <= 6) return 'very_short';
  if (length <= 8) return 'short';
  if (length <= 12) return 'medium';
  if (length <= 16) return 'long';
  return 'very_long';
}

/** Shannon entropy scaled by length, in bits (mirrors _calculate_entropy). */
export function entropyBits(password) {
  if (!password) return 0;
  const freq = new Map();
  for (const ch of password) freq.set(ch, (freq.get(ch) || 0) + 1);
  const length = password.length;
  let entropy = 0;
  for (const count of freq.values()) {
    const p = count / length;
    entropy -= p * Math.log2(p);
  }
  return entropy * length;
}

/**
 * Map entropy bits onto a coarse band. The thresholds are chosen so the
 * band's server-side representative estimate lands in the same risk bucket
 * the plaintext path would (server risk math keys off <30 and <50 bits).
 */
export function entropyBand(bits) {
  if (bits < 28) return 'very_low';
  if (bits < 50) return 'low';
  if (bits < 70) return 'medium';
  if (bits < 90) return 'high';
  return 'very_high';
}

/** Convert leet characters back to letters for dictionary matching. */
function normalizeLeet(text) {
  let out = '';
  for (const ch of text) out += REVERSE_LEET.get(ch) || ch;
  return out;
}

/** Whether the password is built on a common dictionary base word. */
export function hasDictionaryBase(password) {
  const lower = password.toLowerCase();
  const normalized = normalizeLeet(lower);
  return COMMON_BASE_WORDS.some(
    (word) => lower.includes(word) || normalized.includes(word)
  );
}

/** Whether the password contains a keyboard-walk pattern. */
export function hasKeyboardPattern(password) {
  const lower = password.toLowerCase();
  return KEYBOARD_PATTERNS.some((p) => lower.includes(p));
}

/** Whether the password contains a date-like pattern. */
export function hasDatePattern(password) {
  return DATE_PATTERNS.some((re) => re.test(password));
}

/** Whether the password uses leet-speak substitutions. */
export function hasLeet(password) {
  for (const ch of password) {
    if (REVERSE_LEET.has(ch)) return true;
  }
  return false;
}

/** SHA-256(charClassSeq:lengthBucket) as a hex string (matches the server). */
export async function structureHash(seq, bucket) {
  const data = new TextEncoder().encode(`${seq}:${bucket}`);
  const digest = await crypto.subtle.digest('SHA-256', data);
  return Array.from(new Uint8Array(digest))
    .map((b) => b.toString(16).padStart(2, '0'))
    .join('');
}

/**
 * Compute the full zero-knowledge fingerprint for a single password.
 *
 * @param {string} password - the plaintext password (stays in the browser)
 * @returns {Promise<Object>} irreversible structural fingerprint — contains
 *   NO password and NO dictionary words.
 */
export async function computeFingerprint(password) {
  const pw = password || '';
  const seq = charClassSequence(pw);
  const bucket = lengthBucket(pw.length);
  const bits = entropyBits(pw);

  return {
    char_class_sequence: seq,
    length: pw.length,
    length_bucket: bucket,
    entropy_band: entropyBand(bits),
    structure_hash: await structureHash(seq, bucket),
    has_dictionary_base: hasDictionaryBase(pw),
    has_keyboard_pattern: hasKeyboardPattern(pw),
    has_date_pattern: hasDatePattern(pw),
    has_leet: hasLeet(pw),
  };
}

export default {
  classifyChar,
  charClassSequence,
  lengthBucket,
  entropyBits,
  entropyBand,
  hasDictionaryBase,
  hasKeyboardPattern,
  hasDatePattern,
  hasLeet,
  structureHash,
  computeFingerprint,
};

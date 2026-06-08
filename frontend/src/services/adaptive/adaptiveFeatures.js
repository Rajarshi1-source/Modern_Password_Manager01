/**
 * Adaptive-password feature engine (client-side, pure, zero-knowledge).
 * =====================================================================
 *
 * PR-2 of docs/adaptive-password-zk-remediation-plan.md.
 *
 * Everything that needs to *see the raw password* lives here, on the client,
 * and never leaves the device:
 *   - feature extraction (coarse, non-reversible signals only),
 *   - candidate substitution generation (from the leetspeak map),
 *   - suggestion ranking against a server-exported preference model,
 *   - adapted-password construction,
 *   - masked previews.
 *
 * These functions are intentionally **pure** (no I/O, no module state) so they
 * are trivially unit-testable and can be wired into `adaptivePasswordService`
 * in PR-4 without behaviour surprises. The server only ever receives the
 * fingerprint (see cryptoService.passwordFingerprint), coarse features, masked
 * previews, and substitution *classes* — never the password itself.
 */

/**
 * Leetspeak substitution map — the single client-side source of truth, ported
 * from `COMMON_SUBSTITUTIONS` in
 * `security/services/adaptive_password_service.py`. Keys are lowercase letters;
 * values are ordered by how "natural"/common the substitution is (primary
 * first). Kept in sync with the backend; documented as shared.
 *
 * @type {Readonly<Record<string, string[]>>}
 */
export const LEET_MAP = Object.freeze({
  a: ['@', '4'],
  e: ['3'],
  i: ['1', '!'],
  o: ['0'],
  s: ['$', '5'],
  l: ['1', '|'],
  t: ['7', '+'],
  b: ['8'],
  g: ['9'],
});

/**
 * Reverse leetspeak map (substituted char → original letter), mirroring
 * `REVERSE_SUBSTITUTIONS` in the backend service. Useful for detecting
 * substitutions a user already applied.
 *
 * @type {Readonly<Record<string, string>>}
 */
export const REVERSE_LEET_MAP = Object.freeze(
  Object.fromEntries(
    (() => {
      // Build via a Map so the first writer wins (matching the backend's
      // hand-authored reverse table, where e.g. '1' resolves to 'i', not 'l').
      const reverse = new Map();
      for (const [letter, subs] of Object.entries(LEET_MAP)) {
        for (const sub of subs) {
          if (!reverse.has(sub)) reverse.set(sub, letter);
        }
      }
      return reverse;
    })(),
  ),
);

// Internal Map mirror of LEET_MAP for hot-path lookups by character. Using a
// Map (rather than `LEET_MAP[char]`) keeps lookups out of the object-injection
// lint sink and decouples reads from the exported, user-visible object.
const LEET_LOOKUP = new Map(Object.entries(LEET_MAP));

/**
 * Confidence used for a candidate the preference model has no opinion about.
 * Keeps the feature useful before any model is learned, while letting real
 * learned weights (typically tuned away from 0.5) rank above or below it.
 *
 * @type {number}
 */
export const DEFAULT_CONFIDENCE = 0.5;

/**
 * Assert that `value` is a string; password-handling helpers are strict so a
 * caller never silently fingerprints/masks a non-string (e.g. `undefined`).
 *
 * @param {unknown} value - The value to check.
 * @param {string} fnName - Caller name, for the error message.
 * @returns {string} The validated string.
 * @private
 */
function assertString(value, fnName) {
  if (typeof value !== 'string') {
    throw new TypeError(`${fnName} requires a string password`);
  }
  return value;
}

/**
 * Clamp a number into the inclusive [0, 1] range (confidences/weights).
 *
 * @param {number} n - The value to clamp.
 * @returns {number} `n` constrained to [0, 1].
 * @private
 */
function clamp01(n) {
  if (typeof n !== 'number' || Number.isNaN(n)) return 0;
  return Math.min(1, Math.max(0, n));
}

/**
 * Extract coarse, non-reversible features from a password.
 *
 * The password cannot be reconstructed from the result: only a length *bucket*
 * (not exact length) and per-class character *counts* are returned.
 *
 * @param {string} password - The plaintext password (stays on the client).
 * @returns {{ length_bucket: number, char_classes: { lower: number, upper: number, digit: number, symbol: number } }}
 *   Bucketized length (`floor(len / 4)`) and character-class counts.
 */
export function extractFeatures(password) {
  assertString(password, 'extractFeatures');
  const charClasses = { lower: 0, upper: 0, digit: 0, symbol: 0 };
  for (const ch of password.split('')) {
    if (ch >= 'a' && ch <= 'z') charClasses.lower += 1;
    else if (ch >= 'A' && ch <= 'Z') charClasses.upper += 1;
    else if (ch >= '0' && ch <= '9') charClasses.digit += 1;
    else charClasses.symbol += 1;
  }
  return {
    length_bucket: Math.floor(password.length / 4),
    char_classes: charClasses,
  };
}

/**
 * Generate every candidate leetspeak substitution available in a password.
 *
 * Pure and deterministic: for each position whose (lowercased) character has
 * entries in {@link LEET_MAP}, one candidate is emitted per possible
 * substitution. Ranking/selection is the job of {@link rankSuggestions}.
 *
 * @param {string} password - The plaintext password (stays on the client).
 * @returns {Array<{ position: number, original_char: string, suggested_char: string, reason: string }>}
 *   Candidate substitutions in left-to-right, map-order.
 */
export function generateCandidates(password) {
  assertString(password, 'generateCandidates');
  const candidates = [];
  for (const [position, originalChar] of password.split('').entries()) {
    const lower = originalChar.toLowerCase();
    const subs = LEET_LOOKUP.get(lower);
    if (!subs) continue;
    for (const suggestedChar of subs) {
      candidates.push({
        position,
        original_char: originalChar,
        suggested_char: suggestedChar,
        reason: `Common substitution: ${lower} → ${suggestedChar}`,
      });
    }
  }
  return candidates;
}

/**
 * Look up a substitution weight in a preference model.
 *
 * @param {object|null|undefined} model - Preference model (see {@link rankSuggestions}).
 * @param {string} fromChar - Lowercased original character.
 * @param {string} toChar - Candidate substituted character.
 * @returns {number|undefined} The learned weight, or `undefined` if absent.
 * @private
 */
function lookupWeight(model, fromChar, toChar) {
  const weights = model && model.substitution_weights;
  if (!weights || !Object.hasOwn(weights, fromChar)) return undefined;
  // Keys are our own substitution classes (own enumerable props, guarded by
  // Object.hasOwn above); the model is server-exported data, never code.
  // eslint-disable-next-line security/detect-object-injection
  const row = weights[fromChar];
  if (!row || !Object.hasOwn(row, toChar)) return undefined;
  // eslint-disable-next-line security/detect-object-injection
  const w = row[toChar];
  return typeof w === 'number' ? w : undefined;
}

/**
 * Rank candidate substitutions against a learned preference model and select
 * the best one per position.
 *
 * Each candidate is scored by the model's weight for its `from → to` class;
 * candidates the model has no opinion on fall back to {@link DEFAULT_CONFIDENCE}
 * so the feature still works before any model is learned. At most one
 * substitution is kept per position (the highest-confidence one), results are
 * sorted by confidence (descending, then position ascending for stability), and
 * capped at `maxSuggestions`.
 *
 * @param {Array<{ position: number, original_char: string, suggested_char: string, reason?: string }>} candidates
 *   Candidates, typically from {@link generateCandidates}.
 * @param {{ substitution_weights?: Record<string, Record<string, number>>, model_version?: number }|null} [preferenceModel=null]
 *   Server-exported preference model (no password data); `null` uses defaults.
 * @param {{ maxSuggestions?: number, minConfidence?: number }} [options={}]
 *   `maxSuggestions` caps the result size (default 3); `minConfidence` drops
 *   weak candidates (default 0).
 * @returns {Array<{ position: number, original_char: string, suggested_char: string, confidence: number, reason: string }>}
 *   The selected, ranked substitutions.
 */
export function rankSuggestions(candidates, preferenceModel = null, options = {}) {
  if (!Array.isArray(candidates)) {
    throw new TypeError('rankSuggestions requires an array of candidates');
  }
  const { maxSuggestions = 3, minConfidence = 0 } = options;

  const bestByPosition = new Map();
  for (const candidate of candidates) {
    const fromKey = String(candidate.original_char).toLowerCase();
    const weight = lookupWeight(preferenceModel, fromKey, candidate.suggested_char);
    const confidence = clamp01(weight === undefined ? DEFAULT_CONFIDENCE : weight);
    const scored = {
      position: candidate.position,
      original_char: candidate.original_char,
      suggested_char: candidate.suggested_char,
      confidence,
      reason: candidate.reason || `Substitution ${fromKey} → ${candidate.suggested_char}`,
    };
    const existing = bestByPosition.get(candidate.position);
    if (!existing || scored.confidence > existing.confidence) {
      bestByPosition.set(candidate.position, scored);
    }
  }

  return Array.from(bestByPosition.values())
    .filter((s) => s.confidence >= minConfidence)
    .sort((a, b) => b.confidence - a.confidence || a.position - b.position)
    .slice(0, Math.max(0, maxSuggestions));
}

/**
 * Apply selected substitutions to a password, producing the adapted password.
 *
 * Pure (does not mutate inputs). Substitutions are addressed by `position`
 * (UTF-16 code-unit index, matching {@link generateCandidates}); out-of-range
 * positions are ignored.
 *
 * @param {string} password - The original plaintext password (stays on client).
 * @param {Array<{ position: number, suggested_char: string }>} subs - Substitutions to apply.
 * @returns {string} The adapted password.
 */
export function applySubstitutions(password, subs) {
  assertString(password, 'applySubstitutions');
  if (!Array.isArray(subs)) {
    throw new TypeError('applySubstitutions requires an array of substitutions');
  }
  const chars = password.split('');
  // Collect overrides in a Map (position → char) so we never write to an array
  // slot by an externally-supplied index directly.
  const overrides = new Map();
  for (const sub of subs) {
    const { position, suggested_char: suggestedChar } = sub;
    if (Number.isInteger(position) && position >= 0 && position < chars.length) {
      overrides.set(position, String(suggestedChar));
    }
  }
  return chars.map((ch, i) => (overrides.has(i) ? overrides.get(i) : ch)).join('');
}

/**
 * Produce a privacy-safe masked preview of a password.
 *
 * Reveals at most the first two and last two characters (`ab***yz`); passwords
 * of four characters or fewer are fully masked so the preview never discloses
 * the whole secret. The middle is a fixed `***` (it does **not** encode the
 * exact length).
 *
 * @param {string} password - The plaintext password (stays on the client).
 * @returns {string} The masked preview (empty string for an empty password).
 */
export function maskPreview(password) {
  assertString(password, 'maskPreview');
  if (password.length === 0) return '';
  if (password.length <= 4) return '*'.repeat(password.length);
  return `${password.slice(0, 2)}***${password.slice(-2)}`;
}

export default {
  LEET_MAP,
  REVERSE_LEET_MAP,
  DEFAULT_CONFIDENCE,
  extractFeatures,
  generateCandidates,
  rankSuggestions,
  applySubstitutions,
  maskPreview,
};

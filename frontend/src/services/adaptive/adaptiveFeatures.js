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
 * Read a `{from: {to: value}}` table entry, guarding prototype pollution.
 *
 * @param {object|null|undefined} table - Two-level table from the server model.
 * @param {string} fromChar - Lowercased original character.
 * @param {string} toChar - Candidate substituted character.
 * @returns {unknown} The entry, or `undefined` if absent.
 * @private
 */
function lookupNested(table, fromChar, toChar) {
  if (!table || !Object.hasOwn(table, fromChar)) return undefined;
  // Keys are our own substitution classes (own enumerable props, guarded by
  // Object.hasOwn above); the model is server-exported data, never code.
  // eslint-disable-next-line security/detect-object-injection
  const row = table[fromChar];
  if (!row || !Object.hasOwn(row, toChar)) return undefined;
  // eslint-disable-next-line security/detect-object-injection
  return row[toChar];
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
  const w = lookupNested(model && model.substitution_weights, fromChar, toChar);
  return typeof w === 'number' ? w : undefined;
}

// =============================================================================
// Thompson sampling (Phase 3 — plan §3.4)
// =============================================================================
//
// The server exports the raw Beta posteriors under `exploration` and the
// client draws the sample. That split is deliberate: exploration has to be
// random to work, and a server that returned a fresh random draw per request
// could never be cached or reasoned about. Here the randomness is local, the
// endpoint stays deterministic, and the injectable `rng` makes the whole thing
// testable.

/**
 * Uniform in the OPEN interval (0, 1).
 *
 * Uses `crypto.getRandomValues` when available. Endpoints matter: a 0 would
 * make `Math.log(u)` in the gamma sampler `-Infinity`, and a 1 would make
 * `u ** (1 / shape)` degenerate.
 *
 * @returns {number} A uniform sample in (0, 1).
 * @private
 */
function defaultRng() {
  const webcrypto = globalThis.crypto;
  if (webcrypto && typeof webcrypto.getRandomValues === 'function') {
    const buffer = new Uint32Array(1);
    webcrypto.getRandomValues(buffer);
    // (x + 0.5) / 2^32 lands strictly inside (0, 1) for every uint32.
    return (buffer[0] + 0.5) / 4294967296;
  }
  // Math.random() can return exactly 0; nudge it off the endpoint.
  return Math.min(1 - Number.EPSILON, Math.max(Number.EPSILON, Math.random()));
}

/**
 * Standard normal variate (Box-Muller).
 *
 * @param {() => number} rng - Uniform (0, 1) source.
 * @returns {number} A standard normal sample.
 * @private
 */
function normalSample(rng) {
  return Math.sqrt(-2 * Math.log(rng())) * Math.cos(2 * Math.PI * rng());
}

/** Iteration ceiling for the gamma sampler's rejection loop. @private */
const GAMMA_MAX_ITERATIONS = 1000;

/**
 * Gamma(shape, 1) variate via Marsaglia-Tsang.
 *
 * @param {number} shape - Shape parameter (> 0).
 * @param {() => number} rng - Uniform (0, 1) source.
 * @returns {number} A gamma sample.
 * @private
 */
function gammaSample(shape, rng) {
  if (shape < 1) {
    // Boost into the shape >= 1 regime: G(a) == G(a + 1) * U^(1/a).
    return gammaSample(shape + 1, rng) * rng() ** (1 / shape);
  }

  const d = shape - 1 / 3;
  const c = 1 / Math.sqrt(9 * d);

  for (let i = 0; i < GAMMA_MAX_ITERATIONS; i += 1) {
    let x;
    let v;
    do {
      x = normalSample(rng);
      v = 1 + c * x;
    } while (v <= 0);
    v *= v * v;
    const u = rng();
    if (u < 1 - 0.0331 * x * x * x * x) return d * v;
    if (Math.log(u) < 0.5 * x * x + d * (1 - v + Math.log(v))) return d * v;
  }

  // Marsaglia-Tsang accepts in ~1 iteration on average, so this is unreachable
  // in practice — but an unbounded loop inside a password-entry code path is
  // not something to leave to "in practice". Fall back to the distribution's
  // mean, which degrades exploration to exploitation rather than hanging.
  return d;
}

/**
 * Draw from Beta(alpha, beta).
 *
 * Exported for tests; `rankSuggestions` is the intended caller.
 *
 * @param {number} alpha - Beta alpha (> 0).
 * @param {number} beta - Beta beta (> 0).
 * @param {() => number} [rng=defaultRng] - Uniform (0, 1) source.
 * @returns {number} A sample in [0, 1].
 */
export function sampleBeta(alpha, beta, rng = defaultRng) {
  // Number.isFinite, not typeof: `typeof Infinity === 'number'` is true, so a
  // bare typeof check lets Infinity/-Infinity through. gammaSample(Infinity)
  // returns Infinity, and Infinity / (Infinity + finite) or
  // finite / (finite + Infinity) is NaN or 0 depending on which side is
  // infinite — neither is a valid probability, and both would silently
  // corrupt a caller that isn't rankSuggestions' own already-gated call site
  // (this function is exported and part of the public contract on its own).
  const a = Number.isFinite(alpha) && alpha > 0 ? alpha : 1;
  const b = Number.isFinite(beta) && beta > 0 ? beta : 1;
  const x = gammaSample(a, rng);
  const y = gammaSample(b, rng);
  const total = x + y;
  // Both gammas underflowing to 0 is possible for tiny shapes; 0.5 is the
  // "no opinion" answer, matching a Beta(1, 1) mean.
  return total > 0 ? x / total : 0.5;
}

/**
 * Detect the leetspeak substitution *classes* already present in a password.
 *
 * Used to populate `substitution_classes_used` on a recorded typing session,
 * which is what teaches the server which classes this user actually reaches
 * for. Before Phase 3 the client never sent this, so the service's
 * `_record_substitution_classes` was unreachable from the real client path
 * (plan §0.2 gap B2).
 *
 * Zero-knowledge scope: the result is a set of character *classes* — never a
 * position, never surrounding context, never the password. It does reveal that
 * the password contains, say, a `0`; that is the coarse signal the v2 wire
 * contract explicitly allows for this field, and the whole feature is opt-in.
 *
 * Known limitation: a symbol used as ordinary punctuation is indistinguishable
 * from the same symbol used as leetspeak. A password ending in `!` is reported
 * as using the `i → !` class whether or not the user meant it that way.
 * Resolving it would need the un-leeted word, i.e. a dictionary lookup, and
 * pulling zxcvbn's dictionaries into the per-session capture path is not worth
 * it — the cost is a little signal quality for the bandit, not a leak (the
 * class is reported either way).
 *
 * @param {string} password - The plaintext password (stays on the client).
 * @returns {Array<{ from: string, to: string }>} Distinct classes, ordered by
 *   first appearance.
 */
export function detectSubstitutionClasses(password) {
  assertString(password, 'detectSubstitutionClasses');
  const seen = new Set();
  const classes = [];
  for (const ch of password) {
    const from = Object.hasOwn(REVERSE_LEET_MAP, ch)
      // eslint-disable-next-line security/detect-object-injection
      ? REVERSE_LEET_MAP[ch]
      : undefined;
    if (!from) continue;
    const key = `${from}->${ch}`;
    if (seen.has(key)) continue;
    seen.add(key);
    classes.push({ from, to: ch });
  }
  return classes;
}

// =============================================================================
// Error-position ranking (Phase 4 — plan §4.3 / gap B3)
// =============================================================================
//
// `UserTypingProfile.error_prone_positions` has been written and decayed since
// the feature's first version and read by nothing (gap B3): the product claim
// "learns from your typing errors" was false. The join that makes it useful --
// position -> which CHARACTER sits there -- can only happen on the client,
// because the server never sees the password. The positions themselves already
// cross the wire (they are in /adaptive/profile/ today), so exporting them in
// the preference model adds no new server-side knowledge.

/**
 * How much a fully error-prone (or fully error-free) position moves a
 * candidate's ranking score, in the same [0, 1] units as a confidence or a
 * Thompson draw. Deliberately smaller than the gap between a learned weight
 * (0.9) and the default (0.5), so error data tilts ties rather than
 * overpowering an actually-learned preference.
 *
 * @type {number}
 */
export const ERROR_POSITION_WEIGHT = 0.15;

/**
 * Weight applied to a neighbouring position's error rate.
 *
 * A stumble recorded at position p is evidence about the *transition* into p,
 * so p-1 and p+1 are partially implicated -- but only partially, or a single
 * hot position would smear across the whole password.
 *
 * @type {number}
 * @private
 */
const ADJACENT_ERROR_WEIGHT = 0.5;

/**
 * Error affinity of a position: how much this user stumbles at or next to it.
 *
 * @param {Map<number, number>} rates - position → error rate in [0, 1].
 * @param {number} position - Candidate position (index into the password).
 * @returns {number} Affinity in [0, 1].
 * @private
 */
function errorAffinity(rates, position) {
  const at = rates.get(position) ?? 0;
  const before = rates.get(position - 1) ?? 0;
  const after = rates.get(position + 1) ?? 0;
  return Math.min(1, Math.max(at, ADJACENT_ERROR_WEIGHT * Math.max(before, after)));
}

/**
 * Matches a canonical non-negative integer string: `'0'`, or a leading
 * nonzero digit followed by any digits (`'12'`, `'100'`). Rejects `''` and
 * `' '` (both of which `Number()` coerces to `0`, not "invalid"), leading
 * zeros (`'01'`), decimals, and signs.
 *
 * @type {RegExp}
 * @private
 */
const CANONICAL_INTEGER_KEY = /^(?:0|[1-9]\d*)$/u;

/**
 * Normalize the server's `error_prone_positions` map into a numeric Map.
 *
 * The wire shape is `{ "3": 0.4, "7": 0.15 }` — JSON object keys are always
 * strings. Entries that are not a finite number, or not a non-negative integer
 * position, are dropped rather than coerced: a malformed entry silently read as
 * position 0 would boost whatever sits at the start of every password (the same
 * "don't default malformed data into a plausible-looking value" principle
 * `leetMatchSpans` applies to estimator output). The key check runs BEFORE
 * `Number(key)`, not after: `Number('')` and `Number(' ')` both equal `0`,
 * so checking only the parsed number can't distinguish a deliberate `"0"`
 * key from an empty/whitespace one — both would otherwise silently boost
 * position 0. A negative rate is dropped outright, not clamped into the map:
 * `clamp01` would store it as a real `0` entry, which is different from no
 * entry at all — `rankSuggestions` uses `errorRates.size > 0` to decide
 * whether ANY real error data exists, and a stored-but-clamped bad entry
 * would incorrectly flip that on, activating a uniform penalty tilt across
 * every position that has no real data of its own.
 *
 * @param {Record<string, number>|null|undefined} errorPositions - Wire map.
 * @returns {Map<number, number>} Cleaned position → rate map (possibly empty).
 * @private
 */
function normalizeErrorPositions(errorPositions) {
  const rates = new Map();
  if (!errorPositions || typeof errorPositions !== 'object') return rates;
  for (const [key, value] of Object.entries(errorPositions)) {
    if (!CANONICAL_INTEGER_KEY.test(key)) continue;
    const position = Number(key);
    // Number.isFinite, not typeof: `typeof Infinity === 'number'` is true and
    // an Infinity rate would clamp to 1 and pin every ranking to that position.
    if (!Number.isFinite(value) || value < 0) continue;
    rates.set(position, clamp01(value));
  }
  return rates;
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
 * When `explore` is set and the model carries Phase 3's `exploration` table,
 * a candidate is *ranked* by a Thompson sample from its Beta posterior instead
 * of by the posterior mean. The reported `confidence` stays the mean — that is
 * the number the UI shows the user, and showing them a random draw would make
 * the same suggestion look differently confident on every refresh.
 *
 * @param {Array<{ position: number, original_char: string, suggested_char: string, reason?: string }>} candidates
 *   Candidates, typically from {@link generateCandidates}.
 * When `errorPositions` is supplied (Phase 4, plan §4.3), the ranking score is
 * additionally tilted by where this user actually stumbles: **boosted** at or
 * next to a high-error position (adapting the character they keep fumbling is
 * the change most likely to help) and **penalized** at a position they never
 * miss (swapping in an unfamiliar character there trades a fluent keystroke for
 * a new one). Like Thompson sampling, this moves the ranking only — the
 * reported `confidence` is untouched, because that is the number shown to the
 * user and it must mean "how much the model likes this class", not "how this
 * class happened to rank in this password".
 *
 * @param {Array<{ position: number, original_char: string, suggested_char: string, reason?: string }>} candidates
 *   Candidates, typically from {@link generateCandidates}.
 * @param {{ substitution_weights?: Record<string, Record<string, number>>, exploration?: Record<string, Record<string, {alpha: number, beta: number}>>, error_prone_positions?: Record<string, number>, model_version?: number }|null} [preferenceModel=null]
 *   Server-exported preference model (no password data); `null` uses defaults.
 * @param {{ maxSuggestions?: number, minConfidence?: number, explore?: boolean, rng?: () => number, errorPositions?: Record<string, number> }} [options={}]
 *   `maxSuggestions` caps the result size (default 3); `minConfidence` drops
 *   weak candidates (default 0); `explore` enables Thompson sampling (default
 *   false, so ranking stays deterministic unless a caller opts in); `rng`
 *   injects a uniform (0, 1) source for reproducible tests; `errorPositions`
 *   overrides the model's own `error_prone_positions` table.
 * @returns {Array<{ position: number, original_char: string, suggested_char: string, confidence: number, reason: string }>}
 *   The selected, ranked substitutions.
 */
export function rankSuggestions(candidates, preferenceModel = null, options = {}) {
  if (!Array.isArray(candidates)) {
    throw new TypeError('rankSuggestions requires an array of candidates');
  }
  const {
    maxSuggestions = 3, minConfidence = 0, explore = false, rng = defaultRng,
    errorPositions,
  } = options;
  const exploration = explore ? (preferenceModel && preferenceModel.exploration) : null;
  const errorRates = normalizeErrorPositions(
    errorPositions !== undefined
      ? errorPositions
      : (preferenceModel && preferenceModel.error_prone_positions),
  );
  // An empty table is a genuine no-op, not "every position is error-free".
  // Applying the -ERROR_POSITION_WEIGHT floor uniformly would not reorder
  // anything (it shifts every score equally), but it would make the "no error
  // data" and "measured zero everywhere" cases indistinguishable to a reader
  // and to any future code that inspects the score.
  const useErrorTilt = errorRates.size > 0;

  const bestByPosition = new Map();
  for (const candidate of candidates) {
    const fromKey = String(candidate.original_char).toLowerCase();
    const weight = lookupWeight(preferenceModel, fromKey, candidate.suggested_char);
    const confidence = clamp01(weight === undefined ? DEFAULT_CONFIDENCE : weight);

    // Ranking score: a Thompson draw when exploring and a posterior is
    // published for this exact class, otherwise the mean. A class the server
    // has no posterior for is not silently explored at Beta(1, 1) — that would
    // give unknown classes a 0.5-centred random score and let them outrank
    // classes the user has actually rewarded. The same reasoning applies to a
    // posterior entry that IS present but malformed (missing/non-numeric
    // alpha or beta): sampleBeta's own internal fallback would silently
    // produce that same undesirable Beta(1,1) draw, so a malformed entry has
    // to be treated as absent here, not left to fall through to that fallback.
    const posterior = exploration
      ? lookupNested(exploration, fromKey, candidate.suggested_char)
      : undefined;
    const hasUsablePosterior = posterior
      && Number.isFinite(posterior.alpha) && posterior.alpha > 0
      && Number.isFinite(posterior.beta) && posterior.beta > 0;
    const baseScore = hasUsablePosterior
      ? sampleBeta(posterior.alpha, posterior.beta, rng)
      : confidence;

    // Signed tilt: +ERROR_POSITION_WEIGHT at a position this user always
    // stumbles on, -ERROR_POSITION_WEIGHT at one they never miss. Deliberately
    // NOT clamped back into [0, 1]: the score is only ever compared against
    // other scores, and clamping would flatten exactly the extremes this term
    // exists to separate.
    const score = useErrorTilt
      ? baseScore + ERROR_POSITION_WEIGHT * (2 * errorAffinity(errorRates, candidate.position) - 1)
      : baseScore;

    // minConfidence is a floor on the *reported* confidence, not on the
    // exploration draw: a user-facing "don't show me anything below 0.5"
    // setting must not be satisfiable by a lucky sample. Applied here, before
    // the per-position winner is picked, not after: filtering post-reduction
    // would let a low-confidence candidate win its position on a lucky
    // Thompson draw and then drop that position entirely, even when a
    // sibling candidate at the same position had confidence >= minConfidence
    // all along.
    if (confidence < minConfidence) {
      continue;
    }

    const scored = {
      position: candidate.position,
      original_char: candidate.original_char,
      suggested_char: candidate.suggested_char,
      confidence,
      score,
      reason: candidate.reason || `Substitution ${fromKey} → ${candidate.suggested_char}`,
    };
    const existing = bestByPosition.get(candidate.position);
    if (!existing || scored.score > existing.score) {
      bestByPosition.set(candidate.position, scored);
    }
  }

  return Array.from(bestByPosition.values())
    .sort((a, b) => b.score - a.score || a.position - b.position)
    // `score` is internal ranking state — it is a random draw when exploring,
    // so exposing it would put a number in the suggestion object that changes
    // between identical calls.
    .map(({ score: _score, ...suggestion }) => suggestion)
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

// =============================================================================
// Memorability scorer (Phase 4 — plan §4.1 / gap B4)
// =============================================================================
//
// `export_preference_model` has shipped `memorability_params` since the
// feature's first version with NO consumer anywhere (gap B4), and
// `suggestAdaptation` fabricated its "% easier to remember" from the
// confidence and the substitution count -- a formula that is positive by
// construction and therefore measures nothing.
//
// Everything below is pure and client-side: scoring needs the raw password,
// which the server never has. Direction matters and is stated per feature,
// because two of the four move OPPOSITE to guess-resistance. That is not a
// conflict to resolve here: the Phase 2 strength gate is a hard filter applied
// independently, and memorability is never allowed to buy a weaker password
// (see `filterByStrength` -- it runs on the ranked set regardless of score).

/** Default memorability params, used when the server sends none. @private */
const DEFAULT_MEMORABILITY_PARAMS = Object.freeze({
  optimal_length_min: 12,
  optimal_length_max: 16,
  weights: Object.freeze({
    length: 0.2, patterns: 0.3, variety: 0.2, pronounceable: 0.3,
  }),
});

/** The four feature names, in a fixed order. @type {ReadonlyArray<string>} */
export const MEMORABILITY_FEATURES = Object.freeze([
  'length', 'patterns', 'variety', 'pronounceable',
]);

/** Characters treated as vowels for the pronounceability ratio. @private */
const VOWELS = new Set(['a', 'e', 'i', 'o', 'u', 'y']);

/**
 * Characters over which a length is considered "far" outside the optimal band.
 * A password 8 characters past the band scores 0 on length fit.
 * @private
 */
const LENGTH_DECAY_CHARS = 8;

/** Total number of character classes {@link extractFeatures} distinguishes. @private */
const CHAR_CLASS_COUNT = 4;

/**
 * Read the optimal length band + weights out of a server-supplied params blob.
 *
 * Anything missing, non-finite, or inconsistent (min > max, weights that do not
 * sum to a positive number) falls back to the defaults for that piece alone.
 * Failing closed here would be wrong: memorability is advisory, and a malformed
 * params blob must not make the whole suggestion path unavailable the way a
 * malformed strength reading rightly does.
 *
 * @param {object|null|undefined} params - `memorability_params` from the model.
 * @returns {{ min: number, max: number, weights: Record<string, number> }}
 * @private
 */
function normalizeMemorabilityParams(params) {
  const raw = params || {};
  let min = Number(raw.optimal_length_min);
  let max = Number(raw.optimal_length_max);
  if (!Number.isFinite(min) || !Number.isFinite(max) || min <= 0 || max < min) {
    min = DEFAULT_MEMORABILITY_PARAMS.optimal_length_min;
    max = DEFAULT_MEMORABILITY_PARAMS.optimal_length_max;
  }

  // All-or-nothing, matching the server's own `normalize_memorability_weights`
  // exactly (adaptive_password_service.py): a weights blob is accepted only
  // if every one of the four features is present with a finite, non-negative
  // number. The server never actually emits a partial blob over
  // `/preference-model/` (its own normalizer already rejects partial input
  // before publishing), so this mismatch was unreachable via that path — but
  // this function is also called directly by anything constructing a
  // `memorabilityParams` object by hand (tests, a future caller), and having
  // two normalizers silently define "partial" differently is a drift trap
  // regardless of today's reachability. Back-filling a missing weight with 0
  // and renormalizing over the rest, as a first version of this did, is a
  // DIFFERENT blend than "use the defaults" -- a half-learned model treated
  // as a complete one is a third thing neither side intended.
  const rawWeights = raw.weights || {};
  const weights = {};
  let total = 0;
  for (const name of MEMORABILITY_FEATURES) {
    if (!Object.hasOwn(rawWeights, name)) {
      return { min, max, weights: { ...DEFAULT_MEMORABILITY_PARAMS.weights } };
    }
    // eslint-disable-next-line security/detect-object-injection
    const value = Number(rawWeights[name]);
    // Number.isFinite, not typeof/truthiness: a weight of Infinity would make
    // the normalized combination NaN for every password, and a NaN weight
    // would poison the sum silently.
    if (!Number.isFinite(value) || value < 0) {
      return { min, max, weights: { ...DEFAULT_MEMORABILITY_PARAMS.weights } };
    }
    // eslint-disable-next-line security/detect-object-injection
    weights[name] = value;
    total += value;
  }
  if (total <= 0) {
    return { min, max, weights: { ...DEFAULT_MEMORABILITY_PARAMS.weights } };
  }
  for (const name of MEMORABILITY_FEATURES) {
    // eslint-disable-next-line security/detect-object-injection
    weights[name] /= total;
  }
  return { min, max, weights };
}

/**
 * Length fit against the user's learned optimal band.
 *
 * **Direction:** higher = more memorable. 1.0 anywhere inside the band, decaying
 * linearly to 0 over {@link LENGTH_DECAY_CHARS} characters on either side.
 *
 * Note this feature is *constant* under the substitution family this whole
 * feature implements: every substitution replaces one character with exactly
 * one other, so length never moves. It therefore contributes to the displayed
 * absolute score but never to the before/after Δ.
 *
 * @param {number} length - Password length.
 * @param {number} min - Optimal band lower bound.
 * @param {number} max - Optimal band upper bound.
 * @returns {number} Score in [0, 1].
 * @private
 */
function lengthFitScore(length, min, max) {
  if (length >= min && length <= max) return 1;
  const distance = length < min ? min - length : length - max;
  return clamp01(1 - distance / LENGTH_DECAY_CHARS);
}

/**
 * Repeated-pattern presence — the recall handles a password gives you.
 *
 * **Direction:** higher = more memorable. Measured as the fraction of positions
 * covered by either a run of identical characters or a bigram that occurs more
 * than once; both are structure a person can chunk and rehearse.
 *
 * @param {string} password - The plaintext password (stays on the client).
 * @returns {number} Score in [0, 1].
 * @private
 */
function patternScore(password) {
  if (password.length < 2) return 0;
  const chars = password.split('');
  const covered = new Set();

  // Single pass over adjacent pairs, carrying the previous character rather
  // than indexing back into `chars`. Equivalent to chars[i - 1], and keeps the
  // whole function clear of the object-injection lint sink.
  const bigramPositions = new Map();
  let previous = chars[0];
  for (const [index, current] of chars.entries()) {
    if (index === 0) continue;

    // Runs of identical characters ("aa", "111").
    if (current === previous) {
      covered.add(index - 1);
      covered.add(index);
    }

    // Bigrams, recorded by the position of their FIRST character.
    const bigram = `${previous}${current}`;
    const seen = bigramPositions.get(bigram);
    if (seen) seen.push(index - 1);
    else bigramPositions.set(bigram, [index - 1]);

    previous = current;
  }
  for (const positions of bigramPositions.values()) {
    if (positions.length < 2) continue;
    for (const i of positions) {
      covered.add(i);
      covered.add(i + 1);
    }
  }

  return covered.size / chars.length;
}

/**
 * Character-class variety.
 *
 * **Direction:** higher score = FEWER classes = more memorable. A password drawn
 * from one class is a word; one drawn from four is a string of exceptions, each
 * of which has to be recalled separately.
 *
 * This is the clearest place where memorability and guess-resistance genuinely
 * disagree, and the disagreement is resolved by keeping them separate rather
 * than by blending them: `filterByStrength` can veto any substitution, and no
 * memorability score can overrule it.
 *
 * @param {string} password - The plaintext password (stays on the client).
 * @returns {number} Score in [0, 1].
 * @private
 */
function varietyScore(password) {
  if (password.length === 0) return 1;
  const { char_classes: classes } = extractFeatures(password);
  const used = Object.values(classes).filter((n) => n > 0).length;
  return clamp01(1 - (used - 1) / (CHAR_CLASS_COUNT - 1));
}

/**
 * Pronounceability — vowel/consonant alternation over the alphabetic run.
 *
 * **Direction:** higher = more memorable. Computed over the *alphabetic*
 * characters only, in order: a password whose letters alternate vowel/consonant
 * can be said aloud, which is the strongest single predictor of recall.
 *
 * A password with fewer than two letters gets 0.5 — "no opinion" — rather than
 * 0: an all-digit PIN is not maximally unpronounceable, it is simply outside
 * what this feature measures.
 *
 * @param {string} password - The plaintext password (stays on the client).
 * @returns {number} Score in [0, 1].
 * @private
 */
function pronounceableScore(password) {
  const letters = password.toLowerCase().split('').filter((ch) => ch >= 'a' && ch <= 'z');
  if (letters.length < 2) return 0.5;
  let alternations = 0;
  let previousIsVowel = VOWELS.has(letters[0]);
  for (const [index, letter] of letters.entries()) {
    if (index === 0) continue;
    const isVowel = VOWELS.has(letter);
    if (isVowel !== previousIsVowel) alternations += 1;
    previousIsVowel = isVowel;
  }
  return alternations / (letters.length - 1);
}

/**
 * Compute the four memorability sub-scores for a password.
 *
 * Exported alongside {@link scoreMemorability} because the *attribution* half of
 * plan §4.2 needs to know which feature an adaptation moved most, and because
 * asserting the combiner is monotone in each feature requires seeing them
 * individually.
 *
 * @param {string} password - The plaintext password (stays on the client).
 * @param {object|null} [memorabilityParams=null] - `memorability_params` from
 *   the server-exported preference model.
 * @returns {{ length: number, patterns: number, variety: number, pronounceable: number }}
 *   Each sub-score in [0, 1]; higher always means "easier to remember".
 */
export function memorabilityFeatures(password, memorabilityParams = null) {
  assertString(password, 'memorabilityFeatures');
  const { min, max } = normalizeMemorabilityParams(memorabilityParams);
  return {
    length: lengthFitScore(password.length, min, max),
    patterns: patternScore(password),
    variety: varietyScore(password),
    pronounceable: pronounceableScore(password),
  };
}

/**
 * Score how memorable a password is, in [0, 1].
 *
 * The missing consumer of `memorability_params` (plan §4.1, gap B4). Pure: the
 * password is read here and nothing about it leaves the function — callers send
 * the server at most the resulting scalar.
 *
 * Honest scope, measured rather than asserted: because two of the four features
 * (variety, pronounceability) fall when a letter is replaced by a symbol or a
 * digit, a canonical leetspeak substitution usually scores *lower* here than the
 * original — e.g. `password` → `p@ssw0rd` moves variety 1.00 → 0.33 and
 * pronounceability 0.57 → 0.00. That negative reading is the correct one for
 * these four intrinsic features; the reason a user finds their own habitual
 * substitution easy is habit, which this feature models in the bandit posterior
 * (`confidence`), not here. The pre-Phase-4 formula hid this by being positive
 * by construction.
 *
 * @param {string} password - The plaintext password (stays on the client).
 * @param {object|null} [memorabilityParams=null] - `memorability_params` from
 *   the server-exported preference model; defaults are used when absent.
 * @returns {number} Weighted memorability score in [0, 1].
 */
export function scoreMemorability(password, memorabilityParams = null) {
  assertString(password, 'scoreMemorability');
  const { weights } = normalizeMemorabilityParams(memorabilityParams);
  const features = memorabilityFeatures(password, memorabilityParams);
  let score = 0;
  for (const name of MEMORABILITY_FEATURES) {
    // eslint-disable-next-line security/detect-object-injection
    score += weights[name] * features[name];
  }
  return clamp01(score);
}

/**
 * Identify which memorability feature an adaptation moved most.
 *
 * The server cannot compute this — it never sees either password — but plan
 * §4.2 needs it to attribute a user's "was this easier to remember?" feedback to
 * a feature before nudging that feature's weight. Sending the *name* of the
 * dominant feature (one of four fixed strings) rather than the delta vector
 * keeps the wire surface to a single categorical value.
 *
 * @param {string} original - The original password (stays on the client).
 * @param {string} adapted - The adapted password (stays on the client).
 * @param {object|null} [memorabilityParams=null] - Server memorability params.
 * @returns {string|null} The dominant feature name, or `null` when no feature
 *   moved at all (nothing to attribute).
 */
export function memorabilityDriver(original, adapted, memorabilityParams = null) {
  const before = memorabilityFeatures(original, memorabilityParams);
  const after = memorabilityFeatures(adapted, memorabilityParams);
  let driver = null;
  let largest = 0;
  for (const name of MEMORABILITY_FEATURES) {
    // eslint-disable-next-line security/detect-object-injection
    const delta = Math.abs(after[name] - before[name]);
    // Strict >: MEMORABILITY_FEATURES is a fixed order, so ties resolve to the
    // first-listed feature deterministically rather than by object key order.
    if (delta > largest) {
      largest = delta;
      driver = name;
    }
  }
  return driver;
}

// =============================================================================
// Strength gate (Phase 2 — plan §4 / gap C1)
// =============================================================================
//
// Leetspeak is exactly what hashcat's `best64`/`leetspeak` rules and zxcvbn's
// own l33t matcher already model, so an unguarded adaptation can hand an
// attacker a known rule. Everything below runs **client-side only** — the
// server never sees a password and therefore cannot verify this gate. That
// asymmetry is accepted and documented (plan §1.3): the server only records,
// so a client that records a weakening adaptation harms only itself.

/** Reason code: the substitution created a leet dictionary match. */
export const REJECT_DE_LEET = 'de_leet';

/** Reason code: the substitution set lowered `guesses_log10`. */
export const REJECT_STRENGTH_REGRESSION = 'strength_regression';

/**
 * Cached promise for the lazily-imported default estimator.
 *
 * zxcvbn's dictionaries are large, so they are pulled in via `import()` and
 * never enter the main chunk. Reset on failure so a transient chunk-load error
 * does not permanently disable the gate.
 *
 * @type {Promise<(password: string) => { guessesLog10: number, sequence: Array<object> }>|null}
 * @private
 */
let defaultEstimatorPromise = null;

/**
 * Read a binding from a dynamically-imported module, tolerating CJS interop.
 *
 * `@zxcvbn-ts/*` v4 ships `main` (CJS) + `module` (ESM) with no `exports` map.
 * Bundlers pick the ESM build and expose named bindings directly; a plain Node
 * ESM resolver picks the CJS build and puts everything on `default` instead.
 * Both shapes are handled so the same code works under Vite and under a raw
 * Node import (verified empirically against both — the difference is real, not
 * hypothetical).
 *
 * @param {object} mod - The imported module namespace.
 * @param {string} name - The binding to read.
 * @returns {unknown} The binding, from either shape.
 * @private
 */
function interopNamed(mod, name) {
  if (mod && Object.hasOwn(mod, name)) {
    // eslint-disable-next-line security/detect-object-injection
    return mod[name];
  }
  const fallback = mod && mod.default;
  if (fallback && Object.hasOwn(fallback, name)) {
    // eslint-disable-next-line security/detect-object-injection
    return fallback[name];
  }
  return undefined;
}

/**
 * Lazily build the default zxcvbn-backed strength estimator.
 *
 * Exported so a caller can warm the chunk ahead of time (e.g. when the adaptive
 * panel mounts) instead of paying the import cost inside the gate.
 *
 * @returns {Promise<(password: string) => { guessesLog10: number, sequence: Array<object> }>}
 *   An estimator over the common-language dictionaries.
 */
export async function loadDefaultEstimator() {
  if (defaultEstimatorPromise === null) {
    defaultEstimatorPromise = (async () => {
      const [core, common, en] = await Promise.all([
        import('@zxcvbn-ts/core'),
        import('@zxcvbn-ts/language-common'),
        import('@zxcvbn-ts/language-en'),
      ]);
      const ZxcvbnFactory = interopNamed(core, 'ZxcvbnFactory');
      const dictionary = interopNamed(common, 'dictionary');
      const graphs = interopNamed(common, 'adjacencyGraphs');
      const enDictionary = interopNamed(en, 'dictionary');
      if (typeof ZxcvbnFactory !== 'function' || !dictionary || !graphs || !enDictionary) {
        throw new Error('zxcvbn-ts loaded but did not expose the expected API.');
      }
      // language-common alone has no English word list (just breached
      // passwords + diceware + keyboard graphs), so an ordinary English word
      // with no leetspeak reads as near-random and scores far stronger than
      // it should -- measured: 'xylophone' alone goes from guesses_log10
      // 4.392 (recognized) to 7.955 (unmatched) without this merged in. That
      // is the same underestimation-of-guessability failure mode C1 exists
      // to close, just via a missing dictionary instead of a leetspeak match.
      const zxcvbn = new ZxcvbnFactory({
        dictionary: { ...dictionary, ...enDictionary },
        graphs,
      });
      return (password) => {
        const result = zxcvbn.check(password);
        return { guessesLog10: result.guessesLog10, sequence: result.sequence };
      };
    })().catch((error) => {
      // Do not cache a failure: a chunk that failed to load once (offline, CDN
      // hiccup) must be retryable, or the gate stays permanently unavailable
      // and — because callers fail closed — the feature stays permanently off.
      defaultEstimatorPromise = null;
      throw error;
    });
  }
  return defaultEstimatorPromise;
}

/**
 * Reset the cached default estimator. Test seam only.
 *
 * @returns {void}
 */
export function resetDefaultEstimator() {
  defaultEstimatorPromise = null;
}

/**
 * Collect the leet-flagged dictionary matches from a zxcvbn match sequence.
 *
 * @param {Array<object>|undefined} sequence - zxcvbn `result.sequence`.
 * @returns {Array<{ i: number, j: number }>} Index spans of l33t matches.
 * @private
 */
function leetMatchSpans(sequence) {
  if (!Array.isArray(sequence)) return [];
  return sequence
    // A match missing a valid i/j is dropped, not coerced to {i: 0, j: 0}:
    // that fake span would wrongly reject any substitution sitting at
    // position 0 for a match the estimator never actually reported there --
    // the same "don't default malformed data into a plausible-looking value"
    // principle normalizeEstimate below applies to the estimator reading
    // itself.
    .filter((match) => match && match.pattern === 'dictionary' && match.l33t === true
      && Number.isInteger(match.i) && Number.isInteger(match.j))
    .map((match) => ({ i: match.i, j: match.j }));
}

/**
 * Normalize an estimator result, rejecting anything unusable.
 *
 * A gate that silently treats a malformed estimator reading as "fine" would be
 * the same fail-open class of bug this gate exists to prevent, so an unusable
 * reading throws rather than defaulting.
 *
 * @param {unknown} raw - Whatever the estimator returned.
 * @param {string} label - Which password was measured, for the error message.
 * @returns {{ guessesLog10: number, sequence: Array<object> }} Normalized reading.
 * @private
 */
function normalizeEstimate(raw, label) {
  const guessesLog10 = raw && raw.guessesLog10;
  if (typeof guessesLog10 !== 'number' || !Number.isFinite(guessesLog10)) {
    throw new TypeError(
      `filterByStrength: estimator returned no finite guessesLog10 for the ${label} password.`,
    );
  }
  return { guessesLog10, sequence: (raw && raw.sequence) || [] };
}

/**
 * Drop every adaptation that would not strictly preserve guess-resistance.
 *
 * Two independent rules are enforced, because zxcvbn does **not** punish
 * leetspeak on its own — measured against the real estimator, `password`
 * scores `guesses_log10 ≈ 0.48` while `p@ssw0rd` scores `≈ 0.95`, i.e. the
 * naive non-regression test *passes* the canonical attack. Rule 2 is what
 * actually closes gap C1; rule 1 catches everything else.
 *
 *   1. **Strict non-regression** — the adapted password's `guesses_log10` must
 *      be `>=` the original's. On a regression the lowest-confidence
 *      substitution is dropped and the set re-tested.
 *   2. **De-leet** — a substitution that lands inside a leet-flagged dictionary
 *      match in the adapted password is rejected outright. That match is a rule
 *      an offline cracker already models, so the substitution has handed the
 *      attacker a shortcut regardless of what the guess count says.
 *
 * The two rules are applied to a **fixed point** rather than strictly in
 * sequence (a deviation from the plan's numbered ordering, which is written as
 * if each rule ran once): every rejection changes the adapted password, and so
 * changes the other rule's input. Each pass removes at least one substitution,
 * so the loop is bounded by `subs.length`.
 *
 * Fails closed: an estimator that throws or returns an unusable reading
 * propagates, so a caller can never mistake "could not measure" for "measured
 * and safe".
 *
 * @param {string} password - The original password (stays on the client).
 * @param {Array<{ position: number, original_char?: string, suggested_char: string, confidence?: number }>} subs
 *   Ranked substitutions, typically from {@link rankSuggestions}.
 * @param {{ estimator?: (password: string) => object|Promise<object> }} [options={}]
 *   `estimator` overrides the lazily-loaded zxcvbn default (used by tests and
 *   by callers that already hold an estimator).
 * @returns {Promise<{ subs: Array<object>, originalGuessesLog10: number, adaptedGuessesLog10: number, rejected: Array<object> }>}
 *   The surviving substitutions (possibly empty — a valid outcome, not an
 *   error), both guess counts, and every rejection with its reason code.
 */
export async function filterByStrength(password, subs, { estimator } = {}) {
  assertString(password, 'filterByStrength');
  if (!Array.isArray(subs)) {
    throw new TypeError('filterByStrength requires an array of substitutions');
  }

  const estimate = estimator || (await loadDefaultEstimator());
  const original = normalizeEstimate(await estimate(password), 'original');

  let surviving = subs.slice();
  const rejected = [];
  let adapted = original;

  // Every iteration either settles or removes at least one substitution, so
  // `subs.length + 1` passes is a hard upper bound. Asserting it rather than
  // silently falling out of a `for` bound keeps a future edit that breaks the
  // invariant loud instead of returning a stale reading.
  let passes = 0;
  for (;;) {
    if (surviving.length === 0) {
      adapted = original;
      break;
    }
    passes += 1;
    if (passes > subs.length + 1) {
      throw new Error('filterByStrength did not converge (substitution set never shrank).');
    }

    adapted = normalizeEstimate(
      await estimate(applySubstitutions(password, surviving)),
      'adapted',
    );

    // Rule 2 first: a substitution that created a leet dictionary match is
    // rejected on its own merits, not merely because the guess count moved.
    // Reusing `sub.position` (an index into the ORIGINAL password) against
    // spans measured in the ADAPTED one is only valid because every
    // substitution replaces exactly one character with exactly one other
    // (LEET_MAP's values are all single characters; applySubstitutions does
    // a 1:1 swap) -- positions never shift between original and adapted. A
    // multi-character substitution would break this and need the adapted
    // position computed explicitly instead.
    const spans = leetMatchSpans(adapted.sequence);
    const deLeetCulprits = surviving.filter((sub) =>
      spans.some((span) => sub.position >= span.i && sub.position <= span.j),
    );
    if (deLeetCulprits.length > 0) {
      for (const sub of deLeetCulprits) {
        rejected.push({ ...sub, rejected_because: REJECT_DE_LEET });
      }
      surviving = surviving.filter((sub) => !deLeetCulprits.includes(sub));
      continue;
    }

    // Rule 1: strict non-regression. Equal is acceptable; lower is not.
    if (adapted.guessesLog10 < original.guessesLog10) {
      const weakest = surviving.reduce((lowest, sub) =>
        (sub.confidence ?? 0) < (lowest.confidence ?? 0) ? sub : lowest,
      );
      rejected.push({ ...weakest, rejected_because: REJECT_STRENGTH_REGRESSION });
      surviving = surviving.filter((sub) => sub !== weakest);
      continue;
    }

    break;
  }

  return {
    subs: surviving,
    originalGuessesLog10: original.guessesLog10,
    adaptedGuessesLog10: surviving.length === 0
      ? original.guessesLog10
      : adapted.guessesLog10,
    rejected,
  };
}

export default {
  LEET_MAP,
  REVERSE_LEET_MAP,
  DEFAULT_CONFIDENCE,
  ERROR_POSITION_WEIGHT,
  MEMORABILITY_FEATURES,
  REJECT_DE_LEET,
  REJECT_STRENGTH_REGRESSION,
  memorabilityFeatures,
  scoreMemorability,
  memorabilityDriver,
  extractFeatures,
  generateCandidates,
  rankSuggestions,
  applySubstitutions,
  maskPreview,
  filterByStrength,
  loadDefaultEstimator,
  resetDefaultEstimator,
  sampleBeta,
  detectSubstitutionClasses,
};

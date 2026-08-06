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
 * @param {{ substitution_weights?: Record<string, Record<string, number>>, exploration?: Record<string, Record<string, {alpha: number, beta: number}>>, model_version?: number }|null} [preferenceModel=null]
 *   Server-exported preference model (no password data); `null` uses defaults.
 * @param {{ maxSuggestions?: number, minConfidence?: number, explore?: boolean, rng?: () => number }} [options={}]
 *   `maxSuggestions` caps the result size (default 3); `minConfidence` drops
 *   weak candidates (default 0); `explore` enables Thompson sampling (default
 *   false, so ranking stays deterministic unless a caller opts in); `rng`
 *   injects a uniform (0, 1) source for reproducible tests.
 * @returns {Array<{ position: number, original_char: string, suggested_char: string, confidence: number, reason: string }>}
 *   The selected, ranked substitutions.
 */
export function rankSuggestions(candidates, preferenceModel = null, options = {}) {
  if (!Array.isArray(candidates)) {
    throw new TypeError('rankSuggestions requires an array of candidates');
  }
  const {
    maxSuggestions = 3, minConfidence = 0, explore = false, rng = defaultRng,
  } = options;
  const exploration = explore ? (preferenceModel && preferenceModel.exploration) : null;

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
    const score = hasUsablePosterior
      ? sampleBeta(posterior.alpha, posterior.beta, rng)
      : confidence;

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
    // minConfidence is a floor on the *reported* confidence, not on the
    // exploration draw: a user-facing "don't show me anything below 0.5"
    // setting must not be satisfiable by a lucky sample.
    .filter((s) => s.confidence >= minConfidence)
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
      const [core, common] = await Promise.all([
        import('@zxcvbn-ts/core'),
        import('@zxcvbn-ts/language-common'),
      ]);
      const ZxcvbnFactory = interopNamed(core, 'ZxcvbnFactory');
      const dictionary = interopNamed(common, 'dictionary');
      const graphs = interopNamed(common, 'adjacencyGraphs');
      if (typeof ZxcvbnFactory !== 'function' || !dictionary || !graphs) {
        throw new Error('zxcvbn-ts loaded but did not expose the expected API.');
      }
      const zxcvbn = new ZxcvbnFactory({ dictionary: { ...dictionary }, graphs });
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
    .filter((match) => match && match.pattern === 'dictionary' && match.l33t === true)
    .map((match) => ({
      i: Number.isInteger(match.i) ? match.i : 0,
      j: Number.isInteger(match.j) ? match.j : 0,
    }));
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
  REJECT_DE_LEET,
  REJECT_STRENGTH_REGRESSION,
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

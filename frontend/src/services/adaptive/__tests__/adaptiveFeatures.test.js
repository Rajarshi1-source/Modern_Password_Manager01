/**
 * Unit + property tests for the client-side adaptive feature engine
 * (adaptiveFeatures.js) — PR-2 of docs/adaptive-password-zk-remediation-plan.md.
 *
 * The module is pure (no I/O), so these tests exercise the full
 * candidate → rank → apply → mask pipeline plus the zero-knowledge invariants:
 * features are coarse/non-reversible and previews never reveal more than the
 * first two / last two characters.
 */
import { describe, it, expect, vi } from 'vitest';
import {
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
} from '../adaptiveFeatures';

// A small preference model in the v2 wire shape (see plan §4): the server
// learns these weights from aggregate signals — never from the password.
const PREFERENCE_MODEL = {
  model_version: 7,
  substitution_weights: {
    o: { 0: 0.9 },
    a: { '@': 0.8, 4: 0.2 },
    e: { 3: 0.7 },
    s: { $: 0.1, 5: 0.6 },
  },
  memorability_params: {},
};

describe('LEET_MAP / REVERSE_LEET_MAP', () => {
  it('is frozen (shared source of truth, not mutable at runtime)', () => {
    expect(Object.isFrozen(LEET_MAP)).toBe(true);
    expect(() => {
      LEET_MAP.o = ['x'];
    }).toThrow();
  });

  it('mirrors the backend COMMON_SUBSTITUTIONS mapping', () => {
    expect(LEET_MAP.o).toEqual(['0']);
    expect(LEET_MAP.a).toEqual(['@', '4']);
    expect(LEET_MAP.s).toEqual(['$', '5']);
  });

  it('reverse map resolves substituted chars back to their letter', () => {
    expect(REVERSE_LEET_MAP['0']).toBe('o');
    expect(REVERSE_LEET_MAP['@']).toBe('a');
    expect(REVERSE_LEET_MAP['3']).toBe('e');
  });
});

describe('extractFeatures', () => {
  it('bucketizes length as floor(len / 4) (never exact length)', () => {
    expect(extractFeatures('').length_bucket).toBe(0);
    expect(extractFeatures('abc').length_bucket).toBe(0);
    expect(extractFeatures('abcd').length_bucket).toBe(1);
    expect(extractFeatures('abcdefghijk').length_bucket).toBe(2); // len 11
  });

  it('counts character classes', () => {
    const { char_classes } = extractFeatures('Ab1!cd');
    expect(char_classes).toEqual({ lower: 3, upper: 1, digit: 1, symbol: 1 });
  });

  it('treats whitespace and punctuation as symbols', () => {
    const { char_classes } = extractFeatures('a b.');
    expect(char_classes).toEqual({ lower: 2, upper: 0, digit: 0, symbol: 2 });
  });

  it('returns only coarse data — no raw characters', () => {
    const secret = 'Sup3rSecret!';
    const features = extractFeatures(secret);
    expect(JSON.stringify(features)).not.toContain('Secret');
    expect(Object.keys(features).sort()).toEqual(['char_classes', 'length_bucket']);
  });

  it('throws on a non-string input', () => {
    expect(() => extractFeatures(undefined)).toThrow(/string password/);
  });
});

describe('generateCandidates', () => {
  it('emits one candidate per available substitution, with positions', () => {
    // "oa" → o:[0], a:[@,4]  ⇒ 3 candidates
    const candidates = generateCandidates('oa');
    expect(candidates).toEqual([
      { position: 0, original_char: 'o', suggested_char: '0', reason: expect.any(String) },
      { position: 1, original_char: 'a', suggested_char: '@', reason: expect.any(String) },
      { position: 1, original_char: 'a', suggested_char: '4', reason: expect.any(String) },
    ]);
  });

  it('matches case-insensitively but preserves the original character', () => {
    const candidates = generateCandidates('O');
    expect(candidates).toHaveLength(1);
    expect(candidates[0]).toMatchObject({ position: 0, original_char: 'O', suggested_char: '0' });
  });

  it('returns nothing for a password with no mappable characters', () => {
    expect(generateCandidates('xyz789')).toEqual([]);
  });

  it('is deterministic', () => {
    expect(generateCandidates('password')).toEqual(generateCandidates('password'));
  });

  it('throws on a non-string input', () => {
    expect(() => generateCandidates(null)).toThrow(/string password/);
  });
});

describe('rankSuggestions', () => {
  it('scores candidates by the preference-model weights', () => {
    const ranked = rankSuggestions(generateCandidates('oa'), PREFERENCE_MODEL);
    const byPos = Object.fromEntries(ranked.map((r) => [r.position, r]));
    expect(byPos[0].confidence).toBe(0.9); // o→0
    // a has @:0.8 and 4:0.2 — the higher-weighted @ wins for that position.
    expect(byPos[1]).toMatchObject({ suggested_char: '@', confidence: 0.8 });
  });

  it('keeps at most one substitution per position (the strongest)', () => {
    const ranked = rankSuggestions(generateCandidates('aaa'), PREFERENCE_MODEL);
    const positions = ranked.map((r) => r.position);
    expect(new Set(positions).size).toBe(positions.length);
    expect(ranked.every((r) => r.suggested_char === '@')).toBe(true);
  });

  it('sorts by confidence descending (then position ascending)', () => {
    const ranked = rankSuggestions(generateCandidates('osa'), PREFERENCE_MODEL);
    const confidences = ranked.map((r) => r.confidence);
    const sorted = [...confidences].sort((a, b) => b - a);
    expect(confidences).toEqual(sorted);
    expect(confidences[0]).toBe(0.9); // o→0 is strongest
  });

  it('respects maxSuggestions', () => {
    const ranked = rankSuggestions(generateCandidates('oaes'), PREFERENCE_MODEL, { maxSuggestions: 2 });
    expect(ranked).toHaveLength(2);
  });

  it('drops candidates below minConfidence', () => {
    // s→$ is 0.1, s→5 is 0.6; with min 0.5 only the 5 survives for position s.
    const ranked = rankSuggestions(generateCandidates('s'), PREFERENCE_MODEL, { minConfidence: 0.5 });
    expect(ranked).toEqual([
      expect.objectContaining({ position: 0, suggested_char: '5', confidence: 0.6 }),
    ]);
  });

  it('falls back to DEFAULT_CONFIDENCE when no model is supplied', () => {
    const ranked = rankSuggestions(generateCandidates('o'));
    expect(ranked[0].confidence).toBe(DEFAULT_CONFIDENCE);
  });

  it('clamps out-of-range model weights into [0, 1]', () => {
    const ranked = rankSuggestions(generateCandidates('o'), {
      substitution_weights: { o: { 0: 5 } },
    });
    expect(ranked[0].confidence).toBe(1);
  });

  it('throws on a non-array input', () => {
    expect(() => rankSuggestions('nope')).toThrow(/array of candidates/);
  });
});

describe('applySubstitutions', () => {
  it('applies substitutions at the given positions', () => {
    const adapted = applySubstitutions('oasis', [
      { position: 0, suggested_char: '0' },
      { position: 1, suggested_char: '@' },
    ]);
    expect(adapted).toBe('0@sis');
  });

  it('ignores out-of-range and non-integer positions', () => {
    const adapted = applySubstitutions('abc', [
      { position: 99, suggested_char: 'Z' },
      { position: -1, suggested_char: 'Y' },
      { position: 1.5, suggested_char: 'X' },
    ]);
    expect(adapted).toBe('abc');
  });

  it('does not mutate the original password string identity', () => {
    const original = 'oo';
    const adapted = applySubstitutions(original, [{ position: 0, suggested_char: '0' }]);
    expect(original).toBe('oo');
    expect(adapted).toBe('0o');
  });

  it('throws on a non-string password', () => {
    expect(() => applySubstitutions(42, [])).toThrow(/string password/);
  });
});

describe('maskPreview', () => {
  it('reveals only first 2 + *** + last 2 for longer passwords', () => {
    expect(maskPreview('te5t1234')).toBe('te***34');
    expect(maskPreview('CorrectHorse')).toBe('Co***se');
  });

  it('fully masks passwords of 4 chars or fewer (no leakage on short input)', () => {
    expect(maskPreview('a')).toBe('*');
    expect(maskPreview('abcd')).toBe('****');
  });

  it('returns an empty string for an empty password', () => {
    expect(maskPreview('')).toBe('');
  });

  it('uses a fixed *** that does not encode the exact length', () => {
    expect(maskPreview('abcde')).toBe('ab***de');
    expect(maskPreview('abcdefghijklmnop')).toBe('ab***op');
  });

  // Property: a preview must never reveal more than the first 2 / last 2 chars.
  it('never reveals an interior character', () => {
    const samples = ['Password1!', 'aVeryLongSecretValue99', 'hunter2hunter2', 'mix3D_Up!'];
    for (const pw of samples) {
      const preview = maskPreview(pw);
      const allowed = pw.slice(0, 2) + pw.slice(-2);
      for (const ch of preview.replace(/\*/g, '')) {
        expect(allowed).toContain(ch);
      }
    }
  });
});

describe('end-to-end pipeline (candidate → rank → apply → mask)', () => {
  it('produces an adapted password and previews consistent with the suggestion UI', () => {
    const password = 'password';
    const candidates = generateCandidates(password);
    const subs = rankSuggestions(candidates, PREFERENCE_MODEL);
    const adapted = applySubstitutions(password, subs);

    // Every selected substitution is reflected in the adapted password.
    for (const sub of subs) {
      expect(adapted[sub.position]).toBe(sub.suggested_char);
    }
    // Same length, only mapped positions changed.
    expect(adapted).toHaveLength(password.length);

    // Shape consumed by AdaptivePasswordSuggestion.jsx.
    for (const sub of subs) {
      expect(sub).toEqual(
        expect.objectContaining({
          position: expect.any(Number),
          original_char: expect.any(String),
          suggested_char: expect.any(String),
          confidence: expect.any(Number),
          reason: expect.any(String),
        }),
      );
    }

    // 'password' adapts to 'p@5sw0rd' under this model; both previews keep the
    // last two ('rd') and reveal at most the first two characters.
    expect(maskPreview(password)).toBe('pa***rd');
    expect(maskPreview(adapted)).toBe('p@***rd');
  });

  it('never exposes the full raw password in features or previews', () => {
    const password = 'My$ecretPassw0rd';
    const features = extractFeatures(password);
    const preview = maskPreview(password);
    expect(JSON.stringify(features)).not.toContain(password);
    expect(preview).not.toContain(password);
    expect(preview.length).toBeLessThan(password.length);
  });
});

// =============================================================================
// Phase 2 — strength gate (plan §4, gap C1)
// =============================================================================

/**
 * Build a scripted estimator: an explicit password → reading table, so a unit
 * test states exactly the strength landscape it is testing rather than
 * depending on zxcvbn's real numbers. Unlisted passwords fall back to
 * `fallback`, which keeps each table down to the cases that matter.
 *
 * `fallback: 'strict'` opts into throwing on an unlisted password instead of
 * returning a strong-and-clean fallback reading. Use it for a table meant to
 * enumerate every adapted form the implementation should query: a table that
 * intends to be exhaustive but silently isn't (an off-by-one position, a
 * missed adapted-string variant) would otherwise fall through to the
 * fallback and pass for the wrong reason — the exact hazard the comment on
 * the de-leet span test below already warns about by hand.
 */
function scriptedEstimator(table, fallback = { guessesLog10: 10, sequence: [] }) {
  return vi.fn((password) => {
    // Keys are this test's own literals, guarded by Object.hasOwn.
    if (Object.hasOwn(table, password)) {
      // eslint-disable-next-line security/detect-object-injection
      return table[password];
    }
    if (fallback === 'strict') {
      throw new Error(`scriptedEstimator: unlisted password ${JSON.stringify(password)}`);
    }
    return fallback;
  });
}

/** A zxcvbn-shaped leet dictionary match spanning [i, j] inclusive. */
const leetMatch = (i, j) => ({ pattern: 'dictionary', l33t: true, i, j });

describe('filterByStrength — rule 1, strict non-regression', () => {
  it('keeps a substitution set that raises guesses_log10', async () => {
    const subs = [{ position: 1, original_char: 'b', suggested_char: '8', confidence: 0.9 }];
    const estimator = scriptedEstimator({
      abc: { guessesLog10: 5, sequence: [] },
      a8c: { guessesLog10: 6, sequence: [] },
    });

    const result = await filterByStrength('abc', subs, { estimator });

    expect(result.subs).toEqual(subs);
    expect(result.rejected).toEqual([]);
    expect(result.originalGuessesLog10).toBe(5);
    expect(result.adaptedGuessesLog10).toBe(6);
  });

  it('keeps a set that leaves guesses_log10 unchanged (>= is the bar)', async () => {
    const subs = [{ position: 1, original_char: 'b', suggested_char: '8', confidence: 0.9 }];
    const estimator = scriptedEstimator({
      abc: { guessesLog10: 5, sequence: [] },
      a8c: { guessesLog10: 5, sequence: [] },
    });

    const result = await filterByStrength('abc', subs, { estimator });

    expect(result.subs).toEqual(subs);
    expect(result.rejected).toEqual([]);
  });

  it('drops the lowest-confidence substitution and re-tests until non-regressing', async () => {
    const strong = { position: 0, original_char: 'a', suggested_char: '@', confidence: 0.9 };
    const weak = { position: 2, original_char: 'c', suggested_char: 'C', confidence: 0.1 };
    const estimator = scriptedEstimator({
      abc: { guessesLog10: 5, sequence: [] },
      // Both applied: weaker than the original, so the weak one must go first.
      '@bC': { guessesLog10: 4, sequence: [] },
      // Only the strong one applied: recovers.
      '@bc': { guessesLog10: 5.5, sequence: [] },
    });

    const result = await filterByStrength('abc', [strong, weak], { estimator });

    expect(result.subs).toEqual([strong]);
    expect(result.rejected).toEqual([
      { ...weak, rejected_because: REJECT_STRENGTH_REGRESSION },
    ]);
    expect(result.adaptedGuessesLog10).toBe(5.5);
  });

  it('returns an empty set — and the ORIGINAL reading — when nothing survives', async () => {
    const subs = [{ position: 0, original_char: 'a', suggested_char: '@', confidence: 0.5 }];
    const estimator = scriptedEstimator({
      abc: { guessesLog10: 5, sequence: [] },
      '@bc': { guessesLog10: 1, sequence: [] },
    });

    const result = await filterByStrength('abc', subs, { estimator });

    expect(result.subs).toEqual([]);
    // Reporting the rejected candidate's weak reading here would tell the UI a
    // password got weaker when in fact nothing changed.
    expect(result.adaptedGuessesLog10).toBe(5);
    expect(result.originalGuessesLog10).toBe(5);
    expect(result.rejected).toHaveLength(1);
  });
});

describe('filterByStrength — rule 2, de-leet', () => {
  it('rejects a substitution that lands inside a new leet dictionary match', async () => {
    const sub = { position: 1, original_char: 'o', suggested_char: '0', confidence: 0.9 };
    const estimator = scriptedEstimator({
      // The adapted form scores HIGHER, so rule 1 alone would let it through.
      // This is the exact shape of the real password -> p@ssw0rd case, where
      // zxcvbn credits the leet variations instead of punishing them.
      horse: { guessesLog10: 4, sequence: [] },
      h0rse: { guessesLog10: 4.5, sequence: [leetMatch(0, 4)] },
    });

    const result = await filterByStrength('horse', [sub], { estimator });

    expect(result.subs).toEqual([]);
    expect(result.rejected).toEqual([{ ...sub, rejected_because: REJECT_DE_LEET }]);
  });

  it('leaves a substitution outside the leet match span alone', async () => {
    // Indices of 'horse-abc': h0 o1 r2 s3 e4 -5 a6 b7 c8. The 'b' is at 7 —
    // an off-by-one here silently sends the scripted estimator down its
    // fallback branch and the test passes for the wrong reason.
    const inside = { position: 1, original_char: 'o', suggested_char: '0', confidence: 0.9 };
    const outside = { position: 7, original_char: 'b', suggested_char: '8', confidence: 0.8 };
    const estimator = scriptedEstimator({
      'horse-abc': { guessesLog10: 6, sequence: [] },
      // Both applied: the leet match covers only the first word.
      'h0rse-a8c': { guessesLog10: 6.5, sequence: [leetMatch(0, 4)] },
      // After dropping the culprit, no leet match remains.
      'horse-a8c': { guessesLog10: 6.4, sequence: [] },
    }, 'strict');

    const result = await filterByStrength('horse-abc', [inside, outside], { estimator });

    expect(result.subs).toEqual([outside]);
    expect(result.rejected).toEqual([{ ...inside, rejected_because: REJECT_DE_LEET }]);
    expect(result.adaptedGuessesLog10).toBe(6.4);
  });

  it('ignores non-leet dictionary matches (they are not something we created)', async () => {
    const sub = { position: 6, original_char: 'b', suggested_char: '8', confidence: 0.9 };
    const estimator = scriptedEstimator({
      horseXbc: { guessesLog10: 6, sequence: [] },
      horseX8c: {
        guessesLog10: 6.2,
        // A plain dictionary match spanning our position, but NOT l33t-flagged:
        // the word was already there and we did not obfuscate it.
        sequence: [{ pattern: 'dictionary', l33t: false, i: 0, j: 7 }],
      },
    });

    const result = await filterByStrength('horseXbc', [sub], { estimator });

    expect(result.subs).toEqual([sub]);
    expect(result.rejected).toEqual([]);
  });

  it('ignores a leet match missing i/j instead of treating it as a span at position 0', async () => {
    // A match object without a valid i/j used to default to {i: 0, j: 0},
    // which would wrongly reject ANY substitution at position 0 for a span
    // the estimator never actually reported.
    const sub = { position: 0, original_char: 'o', suggested_char: '0', confidence: 0.9 };
    const estimator = scriptedEstimator({
      horse: { guessesLog10: 4, sequence: [] },
      '0orse': {
        guessesLog10: 4.5,
        sequence: [{ pattern: 'dictionary', l33t: true }], // no i/j at all
      },
    }, 'strict');

    const result = await filterByStrength('horse', [sub], { estimator });

    expect(result.subs).toEqual([sub]);
    expect(result.rejected).toEqual([]);
  });
});

describe('filterByStrength — fail-closed contract', () => {
  it('propagates an estimator failure instead of passing substitutions through', async () => {
    const subs = [{ position: 0, original_char: 'a', suggested_char: '@', confidence: 0.5 }];
    const estimator = vi.fn(() => {
      throw new Error('chunk load failed');
    });

    await expect(filterByStrength('abc', subs, { estimator })).rejects.toThrow('chunk load failed');
  });

  it('rejects an estimator reading with no finite guessesLog10', async () => {
    const subs = [{ position: 0, original_char: 'a', suggested_char: '@', confidence: 0.5 }];
    const estimator = vi.fn(() => ({ sequence: [] }));

    await expect(filterByStrength('abc', subs, { estimator })).rejects.toThrow(/guessesLog10/);
  });

  it('accepts an async estimator', async () => {
    const subs = [{ position: 0, original_char: 'a', suggested_char: '@', confidence: 0.5 }];
    const estimator = vi.fn(async () => ({ guessesLog10: 7, sequence: [] }));

    const result = await filterByStrength('abc', subs, { estimator });

    expect(result.subs).toEqual(subs);
  });

  it('validates its arguments', async () => {
    await expect(filterByStrength(undefined, [])).rejects.toThrow(TypeError);
    await expect(filterByStrength('abc', 'not-an-array')).rejects.toThrow(TypeError);
  });

  it('handles an empty substitution set with a single estimator call', async () => {
    const estimator = scriptedEstimator({ abc: { guessesLog10: 5, sequence: [] } });

    const result = await filterByStrength('abc', [], { estimator });

    expect(result).toEqual({
      subs: [],
      originalGuessesLog10: 5,
      adaptedGuessesLog10: 5,
      rejected: [],
    });
    expect(estimator).toHaveBeenCalledTimes(1);
  });
});

describe('filterByStrength — against the real zxcvbn estimator', () => {
  // The default estimator is a lazily-imported LOCAL dependency: these tests
  // touch no network, and nothing here reaches for one. This block holds the
  // acceptance tests for gap C1.

  it('loads the bundled estimator once and reuses it', async () => {
    resetDefaultEstimator();
    // `loadDefaultEstimator` is `async`, so it necessarily returns a NEW
    // promise each call — comparing the promises would only test that. The
    // property that matters is that the expensive build ran once, which shows
    // up as the same estimator *function* being handed back.
    const [first, second] = await Promise.all([
      loadDefaultEstimator(),
      loadDefaultEstimator(),
    ]);
    expect(typeof first).toBe('function');
    expect(second).toBe(first);
    expect(await loadDefaultEstimator()).toBe(first);

    const reading = first('password');
    expect(reading.guessesLog10).toBeGreaterThan(0);
    expect(Array.isArray(reading.sequence)).toBe(true);
  }, 30000);

  it('does not cache a failed load, so the gate stays retryable', async () => {
    // Drive the real failure path: make the dynamic import throw, confirm both
    // the first and a *subsequent* call reject (a cached rejected promise would
    // leave the gate permanently unavailable, and callers fail closed — so the
    // whole feature would stay silently off until a page reload).
    // A factory that *throws* is caught and re-wrapped by vitest's own mock
    // machinery, which would make this assert on vitest's error rather than on
    // the loader's behaviour. Returning a namespace with the expected binding
    // missing drives the loader's own guard instead — same catch, same reset,
    // a message this test actually owns.
    vi.resetModules();
    vi.doMock('@zxcvbn-ts/core', () => ({ default: {} }));
    try {
      const mod = await import('../adaptiveFeatures');
      await expect(mod.loadDefaultEstimator()).rejects.toThrow(/did not expose the expected API/);
      await expect(mod.loadDefaultEstimator()).rejects.toThrow(/did not expose the expected API/);
    } finally {
      vi.doUnmock('@zxcvbn-ts/core');
      vi.resetModules();
    }

    // And the module under test is still usable afterwards.
    resetDefaultEstimator();
    expect(typeof (await loadDefaultEstimator())).toBe('function');
  }, 30000);

  it("yields no suggestion for 'password' — every leet variant de-leets to the same hit", async () => {
    const estimator = await loadDefaultEstimator();
    const subs = rankSuggestions(generateCandidates('password'), null);
    expect(subs.length).toBeGreaterThan(0);

    const result = await filterByStrength('password', subs, { estimator });

    expect(result.subs).toEqual([]);
    expect(result.rejected.every((r) => r.rejected_because === REJECT_DE_LEET)).toBe(true);
  }, 30000);

  it('credits p@ssw0rd over password — proving rule 1 alone cannot close C1', async () => {
    // The justification for the de-leet rule existing at all. zxcvbn scores the
    // leetspeak variant HIGHER, so a gate built only on non-regression would
    // wave through the canonical attack this feature was accused of enabling.
    const estimator = await loadDefaultEstimator();

    expect(estimator('p@ssw0rd').guessesLog10).toBeGreaterThan(
      estimator('password').guessesLog10,
    );
  }, 30000);

  it('never returns an adaptation that lowers guesses_log10 (property, 200 passwords)', async () => {
    const estimator = await loadDefaultEstimator();

    // Deterministic RNG: a property test that cannot be reproduced when it
    // fails is not much of a property test. Reuses the xorshift32 helper
    // defined below (hoisted, so usable here) rather than a hand-rolled LCG —
    // `seed * 1103515245` overflows Number.MAX_SAFE_INTEGER on the very first
    // multiplication (confirmed: the exact product is ...3472225, the double
    // computes ...3472224), which silently corrupted the corpus every prior
    // run of this test.
    const rnd = seededRng(20260805);
    const pick = (xs) => xs[Math.floor(rnd() * xs.length)];

    const words = ['sunshine', 'dragon', 'monkey', 'tiger', 'coffee', 'garden', 'silver',
      'rocket', 'purple', 'winter', 'orange', 'marble', 'pepper', 'shadow', 'forest',
      'castle', 'planet', 'falcon', 'copper', 'velvet'];
    const symbols = ['!', '#', '%', '&', '*', '-', '_', '?'];
    const alphabet = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789';

    const corpus = [];
    for (let i = 0; i < 200; i += 1) {
      if (i % 4 === 0) corpus.push(pick(words) + Math.floor(rnd() * 10000));
      else if (i % 4 === 1) corpus.push(pick(words) + pick(symbols) + pick(words));
      else if (i % 4 === 2) {
        let s = '';
        const n = 8 + Math.floor(rnd() * 8);
        for (let k = 0; k < n; k += 1) s += alphabet[Math.floor(rnd() * alphabet.length)];
        corpus.push(s);
      } else {
        corpus.push(
          pick(words).replace(/^./, (c) => c.toUpperCase())
          + pick(words) + pick(symbols) + Math.floor(rnd() * 100),
        );
      }
    }

    let examined = 0;
    let survived = 0;
    for (const password of corpus) {
      const ranked = rankSuggestions(generateCandidates(password), null);
      if (ranked.length === 0) continue;
      examined += 1;

      const result = await filterByStrength(password, ranked, { estimator });
      if (result.subs.length === 0) continue;
      survived += 1;

      // Re-measure independently rather than trusting the number the gate
      // reported about itself.
      const adapted = applySubstitutions(password, result.subs);
      expect(estimator(adapted).guessesLog10).toBeGreaterThanOrEqual(
        result.originalGuessesLog10,
      );
    }

    // Sanity floor. If the gate rejected everything the property above would
    // hold vacuously and prove nothing; the measured survival rate on this
    // corpus is ~25% of passwords (plan §4.5).
    expect(examined).toBeGreaterThan(150);
    expect(survived).toBeGreaterThan(0);
  }, 60000);
});

// =============================================================================
// Phase 3 — client-side bandit support (plan §5)
// =============================================================================

/**
 * Deterministic uniform (0, 1) source. A Thompson sampler tested with real
 * randomness gives a flaky test; tested with a fixed sequence it gives an
 * assertion about the sampler.
 */
function seededRng(seed = 1) {
  let state = seed >>> 0;
  return () => {
    // xorshift32, mapped into the open interval (0, 1).
    state ^= state << 13; state >>>= 0;
    state ^= state >>> 17;
    state ^= state << 5; state >>>= 0;
    return (state + 0.5) / 4294967296;
  };
}

describe('detectSubstitutionClasses', () => {
  it('reports the leet classes present, as classes only', () => {
    expect(detectSubstitutionClasses('p@ssw0rd')).toEqual([
      { from: 'a', to: '@' },
      { from: 'o', to: '0' },
    ]);
  });

  it('deduplicates repeats and preserves first-appearance order', () => {
    expect(detectSubstitutionClasses('0a0b@c@')).toEqual([
      { from: 'o', to: '0' },
      { from: 'a', to: '@' },
    ]);
  });

  it('returns nothing for a password with no substituted characters', () => {
    expect(detectSubstitutionClasses('Plainword')).toEqual([]);
  });

  it('never emits a position or any surrounding context', () => {
    const secret = 'Sup3rSecret-Passw0rd!';
    const classes = detectSubstitutionClasses(secret);
    expect(JSON.stringify(classes)).not.toContain('Secret');
    for (const entry of classes) {
      expect(Object.keys(entry).sort()).toEqual(['from', 'to']);
      expect(entry.from).toHaveLength(1);
      expect(entry.to).toHaveLength(1);
    }
  });

  it('throws on a non-string input', () => {
    expect(() => detectSubstitutionClasses(null)).toThrow(/string password/);
  });
});

describe('sampleBeta', () => {
  it('always lands in [0, 1]', () => {
    const rng = seededRng(7);
    for (let i = 0; i < 500; i += 1) {
      const x = sampleBeta(2, 5, rng);
      expect(x).toBeGreaterThanOrEqual(0);
      expect(x).toBeLessThanOrEqual(1);
    }
  });

  it('concentrates near the posterior mean as evidence accumulates', () => {
    const rng = seededRng(11);
    const draws = [];
    for (let i = 0; i < 400; i += 1) draws.push(sampleBeta(50, 2, rng));
    const mean = draws.reduce((a, b) => a + b, 0) / draws.length;
    // Beta(50, 2) has mean 50/52 ~= 0.96.
    expect(mean).toBeGreaterThan(0.9);
    expect(mean).toBeLessThanOrEqual(1);
  });

  it('separates a strong arm from a weak one on average', () => {
    const rng = seededRng(3);
    let strongWins = 0;
    for (let i = 0; i < 300; i += 1) {
      if (sampleBeta(40, 3, rng) > sampleBeta(3, 40, rng)) strongWins += 1;
    }
    expect(strongWins).toBeGreaterThan(280);
  });

  it('still explores: a flat prior does not always lose to a strong arm', () => {
    // This is the whole point of Thompson sampling — an arm with no evidence
    // has to win sometimes or the bandit never learns anything new.
    const rng = seededRng(5);
    let flatWins = 0;
    for (let i = 0; i < 400; i += 1) {
      if (sampleBeta(1, 1, rng) > sampleBeta(6, 3, rng)) flatWins += 1;
    }
    expect(flatWins).toBeGreaterThan(20);
    expect(flatWins).toBeLessThan(380);
  });

  it('handles degenerate parameters by falling back to the flat prior', () => {
    const rng = seededRng(13);
    // Infinity/-Infinity are deliberately included, not just NaN: this is
    // the exact gap a bare `typeof x === 'number'` check misses (it is true
    // for Infinity), and sampleBeta is exported and callable directly, not
    // just reached through rankSuggestions' own already-gated call site.
    for (const [a, b] of [
      [0, 1], [-1, 5], [NaN, 2], [2, undefined], [Infinity, 2], [2, Infinity],
      [-Infinity, 2], [Infinity, Infinity],
    ]) {
      const x = sampleBeta(a, b, rng);
      expect(Number.isFinite(x)).toBe(true);
      expect(x).toBeGreaterThanOrEqual(0);
      expect(x).toBeLessThanOrEqual(1);
    }
  });
});

describe('rankSuggestions — Thompson sampling', () => {
  const EXPLORING_MODEL = {
    model_version: 9,
    substitution_weights: { o: { 0: 0.95 }, a: { '@': 0.05, 4: 0.05 } },
    exploration: {
      o: { 0: { alpha: 40, beta: 2 } },
      a: { '@': { alpha: 2, beta: 40 }, 4: { alpha: 2, beta: 40 } },
    },
  };

  it('is deterministic by default (explore is opt-in)', () => {
    const candidates = generateCandidates('oa');
    const first = rankSuggestions(candidates, EXPLORING_MODEL);
    const second = rankSuggestions(candidates, EXPLORING_MODEL);
    expect(first).toEqual(second);
  });

  it('never exposes the internal ranking score', () => {
    const ranked = rankSuggestions(generateCandidates('oa'), EXPLORING_MODEL, {
      explore: true, rng: seededRng(2),
    });
    for (const sub of ranked) {
      expect(sub).not.toHaveProperty('score');
    }
  });

  it('reports the posterior MEAN as confidence, not the random draw', () => {
    // The user sees `confidence`; showing them a sample would make the same
    // suggestion look differently confident on every refresh.
    for (const seed of [1, 2, 3, 4, 5]) {
      const ranked = rankSuggestions(generateCandidates('o'), EXPLORING_MODEL, {
        explore: true, rng: seededRng(seed),
      });
      expect(ranked[0].confidence).toBe(0.95);
    }
  });

  it('usually ranks the strong arm first, but not always (that is exploration)', () => {
    // A DELIBERATELY LOCAL model, not EXPLORING_MODEL: that one uses
    // Beta(40, 2) vs Beta(2, 40), and sampling both 20,000 times empirically
    // never produced a single crossover (verified before writing this test,
    // not assumed) — those two distributions barely overlap, so the
    // "explore" side of the property this test is named for could never be
    // observed with them, no matter how many seeds were tried. Beta(8, 4) vs
    // Beta(4, 8) is close enough to overlap in practice (measured: 182/200
    // strong-arm wins over this exact seed range) while still being lopsided
    // enough that "usually" is the correct description.
    const model = {
      substitution_weights: { o: { 0: 0.8 }, a: { '@': 0.2, 4: 0.2 } },
      exploration: {
        o: { 0: { alpha: 8, beta: 4 } },
        a: { '@': { alpha: 4, beta: 8 }, 4: { alpha: 4, beta: 8 } },
      },
    };
    let strongFirst = 0;
    const runs = 200;
    for (let seed = 1; seed <= runs; seed += 1) {
      const ranked = rankSuggestions(generateCandidates('oa'), model, {
        explore: true, rng: seededRng(seed), maxSuggestions: 2,
      });
      if (ranked[0].suggested_char === '0') strongFirst += 1;
    }
    expect(strongFirst).toBeGreaterThan(runs * 0.7);
    // Strictly less than every run: the weak arm has to win at least once
    // for this test to actually exercise exploration rather than just
    // asserting a tautology about the sample count.
    expect(strongFirst).toBeLessThan(runs);
  });

  it('does not explore a class the server published no posterior for', () => {
    // A class with no posterior must not be scored from an implicit
    // Beta(1, 1): that would give unknown classes a 0.5-centred random score
    // and let them outrank classes the user has actually rewarded.
    const partial = {
      substitution_weights: { o: { 0: 0.95 }, e: { 3: 0.1 } },
      exploration: { o: { 0: { alpha: 40, beta: 2 } } },
    };
    for (let seed = 1; seed <= 50; seed += 1) {
      const ranked = rankSuggestions(generateCandidates('oe'), partial, {
        explore: true, rng: seededRng(seed), maxSuggestions: 2,
      });
      // 'e' has no posterior, so it is scored at its mean of 0.1 and can only
      // beat 'o' when 'o' draws below 0.1 — which Beta(40, 2) never does.
      expect(ranked[0].suggested_char).toBe('0');
    }
  });

  it('treats a malformed exploration entry as absent, not as an implicit flat prior', () => {
    // A posterior entry that IS present but has a non-numeric alpha/beta must
    // not fall through to sampleBeta's own internal Beta(1,1) fallback — that
    // is exactly the "unknown class gets a 0.5-centred random score" outcome
    // the previous test rules out for a MISSING posterior, and it must be
    // ruled out the same way for a malformed one.
    const malformed = {
      substitution_weights: { o: { 0: 0.95 }, a: { '@': 0.05 } },
      exploration: {
        o: { 0: { alpha: 40, beta: 2 } },
        // Missing beta entirely, and a non-numeric alpha — both shapes a
        // malformed or stale cached model could produce.
        a: { '@': { alpha: 'not-a-number' } },
      },
    };
    for (let seed = 1; seed <= 30; seed += 1) {
      const ranked = rankSuggestions(generateCandidates('oa'), malformed, {
        explore: true, rng: seededRng(seed), maxSuggestions: 2,
      });
      // 'a' has a malformed posterior and a low mean (0.05). Without the fix
      // it could win via an implicit Beta(1,1) draw roughly half the time;
      // with the fix it is scored at its mean and Beta(40, 2) never draws
      // below 0.05, so 'o' wins on every seed.
      expect(ranked[0].suggested_char).toBe('0');
    }
  });

  it('rejects a non-finite posterior parameter (Infinity), not just non-numeric ones', () => {
    // typeof Infinity === 'number', so a bare `typeof x === 'number'` gate (an
    // earlier version of this guard) treats Infinity as usable.
    // sampleBeta(Infinity, ...) reliably returns NaN (verified empirically,
    // not assumed), and NaN compares false in both directions against every
    // real number — so a NaN-scored candidate processed FIRST for a position
    // can never be dethroned by a legitimately scored competitor; it wins by
    // iteration-order accident, not confidence. LEET_MAP.a = ['@', '4'], so
    // both compete for the SAME position via generateCandidates('a'), and
    // '@' is generated first, which is what makes this deterministic rather
    // than seed-dependent.
    const model = {
      substitution_weights: { a: { '@': 0.05, 4: 0.05 } },
      exploration: {
        a: {
          '@': { alpha: Infinity, beta: 2 }, // malformed
          4: { alpha: 40, beta: 2 }, // strong, real posterior (mean ~0.95)
        },
      },
    };
    for (let seed = 1; seed <= 30; seed += 1) {
      const ranked = rankSuggestions(generateCandidates('a'), model, {
        explore: true, rng: seededRng(seed),
      });
      expect(ranked[0].suggested_char).toBe('4');
    }
  });

  it('applies minConfidence to the reported confidence, not to the draw', () => {
    // A user-facing "hide anything below 0.5" must not be satisfiable by a
    // lucky sample.
    for (let seed = 1; seed <= 50; seed += 1) {
      const ranked = rankSuggestions(generateCandidates('a'), EXPLORING_MODEL, {
        explore: true, rng: seededRng(seed), minConfidence: 0.5,
      });
      expect(ranked).toEqual([]);
    }
  });

  it('does not let a losing-confidence sibling drop a qualifying one from the same position', () => {
    // 'a' -> '@' and 'a' -> '4' compete for the SAME position. '@' has
    // confidence 0.9 (qualifies for minConfidence: 0.5); '4' has confidence
    // 0.1 (does not) but a strong posterior (mean ~0.95) that wins the
    // Thompson draw almost every time against '@'s weak one (mean ~0.05).
    // Filtering minConfidence AFTER picking the per-position winner would
    // let '4' win the position on its lucky draw, then get dropped by the
    // confidence floor -- taking '@' down with it even though '@' alone
    // already satisfied the floor. '@' must survive regardless of which way
    // any individual draw goes.
    const model = {
      substitution_weights: { a: { '@': 0.9, 4: 0.1 } },
      exploration: {
        a: { '@': { alpha: 2, beta: 40 }, 4: { alpha: 40, beta: 2 } },
      },
    };
    for (let seed = 1; seed <= 30; seed += 1) {
      const ranked = rankSuggestions(generateCandidates('a'), model, {
        explore: true, rng: seededRng(seed), minConfidence: 0.5,
      });
      expect(ranked).toHaveLength(1);
      expect(ranked[0].suggested_char).toBe('@');
    }
  });

  it('falls back to mean ranking when the model carries no exploration table', () => {
    const ranked = rankSuggestions(generateCandidates('oa'), PREFERENCE_MODEL, {
      explore: true, rng: seededRng(1),
    });
    expect(ranked[0].suggested_char).toBe('0');
    expect(ranked[0].confidence).toBe(0.9);
  });
});

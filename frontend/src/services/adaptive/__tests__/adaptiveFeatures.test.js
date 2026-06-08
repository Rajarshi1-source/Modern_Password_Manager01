/**
 * Unit + property tests for the client-side adaptive feature engine
 * (adaptiveFeatures.js) — PR-2 of docs/adaptive-password-zk-remediation-plan.md.
 *
 * The module is pure (no I/O), so these tests exercise the full
 * candidate → rank → apply → mask pipeline plus the zero-knowledge invariants:
 * features are coarse/non-reversible and previews never reveal more than the
 * first two / last two characters.
 */
import { describe, it, expect } from 'vitest';
import {
  LEET_MAP,
  REVERSE_LEET_MAP,
  DEFAULT_CONFIDENCE,
  extractFeatures,
  generateCandidates,
  rankSuggestions,
  applySubstitutions,
  maskPreview,
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

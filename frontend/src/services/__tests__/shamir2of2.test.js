import { describe, expect, it } from 'vitest';
import { split2of2, combine2of2 } from '../shamir2of2.js';

describe('shamir2of2', () => {
  it('round-trips secrets of various lengths', () => {
    for (const len of [1, 16, 32, 64, 128]) {
      const secret = window.crypto.getRandomValues(new Uint8Array(len));
      const { halfA, halfB } = split2of2(secret);
      expect(halfA.length).toBe(len);
      expect(halfB.length).toBe(len);
      const combined = combine2of2(halfA, halfB);
      expect(Array.from(combined)).toEqual(Array.from(secret));
    }
  });

  it('combines in either order', () => {
    const secret = window.crypto.getRandomValues(new Uint8Array(32));
    const { halfA, halfB } = split2of2(secret);
    expect(Array.from(combine2of2(halfA, halfB))).toEqual(Array.from(secret));
    expect(Array.from(combine2of2(halfB, halfA))).toEqual(Array.from(secret));
  });

  it('produces uniformly distributed shares (approximate sanity check)', () => {
    // Across many splits of an all-zero secret, halfA should look
    // uniformly random and halfB should equal halfA exactly.
    const N = 200;
    const lengths = new Set();
    for (let i = 0; i < N; i++) {
      const secret = new Uint8Array(16); // all zeros
      const { halfA, halfB } = split2of2(secret);
      // halfA XOR halfB == 0 -> halfB equals halfA byte-for-byte
      for (let j = 0; j < 16; j++) expect(halfB[j]).toBe(halfA[j]);
      // Hash-ish: convert to string to check we are not getting the
      // same share repeatedly (overwhelmingly improbable).
      lengths.add(Array.from(halfA).join(','));
    }
    expect(lengths.size).toBeGreaterThan(N / 2);
  });

  it('rejects mismatched share lengths', () => {
    const a = new Uint8Array(8);
    const b = new Uint8Array(16);
    expect(() => combine2of2(a, b)).toThrow();
  });

  it('rejects non-Uint8Array inputs', () => {
    expect(() => split2of2('not bytes')).toThrow();
    expect(() => combine2of2('a', 'b')).toThrow();
  });
});

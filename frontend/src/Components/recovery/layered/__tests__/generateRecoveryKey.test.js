import { describe, expect, it } from 'vitest';
import { generateRecoveryKey, normalizeRecoveryKey } from '../generateRecoveryKey';

const ALPHABET = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789';

describe('generateRecoveryKey', () => {
  it('produces a 26-letter key with hyphens every 4 chars', () => {
    const key = generateRecoveryKey();
    // 26 letters + hyphens between each group of 4 = 6 hyphens
    expect(key.length).toBe(26 + 6);
    expect(key.replace(/-/g, '').length).toBe(26);
    for (const ch of key.replace(/-/g, '')) {
      expect(ALPHABET).toContain(ch);
    }
    // Hyphen positions: index 4, 9, 14, 19, 24, 29
    expect(key[4]).toBe('-');
    expect(key[9]).toBe('-');
    expect(key[14]).toBe('-');
    expect(key[19]).toBe('-');
    expect(key[24]).toBe('-');
    expect(key[29]).toBe('-');
  });

  it('produces different keys on successive calls (overwhelmingly likely)', () => {
    const a = generateRecoveryKey();
    const b = generateRecoveryKey();
    expect(a).not.toBe(b);
  });
});

describe('normalizeRecoveryKey', () => {
  it('accepts the canonical form unchanged', () => {
    const k = generateRecoveryKey();
    expect(normalizeRecoveryKey(k)).toBe(k);
  });

  it('accepts unhyphenated, mixed-case, with whitespace', () => {
    const k = generateRecoveryKey();
    const ugly = k.replace(/-/g, '').toLowerCase().split('').join(' ');
    expect(normalizeRecoveryKey(ugly)).toBe(k);
  });

  it('rejects shorter or longer input', () => {
    expect(normalizeRecoveryKey('ABCD')).toBeNull();
    expect(normalizeRecoveryKey('A'.repeat(27))).toBeNull();
  });

  it('rejects characters outside the alphabet (no I/O/0/1)', () => {
    expect(normalizeRecoveryKey('I'.repeat(26))).toBeNull();
    expect(normalizeRecoveryKey('0'.repeat(26))).toBeNull();
  });

  it('rejects non-strings', () => {
    expect(normalizeRecoveryKey(undefined)).toBeNull();
    expect(normalizeRecoveryKey(null)).toBeNull();
    expect(normalizeRecoveryKey(12345)).toBeNull();
  });
});

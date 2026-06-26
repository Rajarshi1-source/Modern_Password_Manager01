import { describe, it, expect } from 'vitest';
import {
  classifyChar,
  charClassSequence,
  lengthBucket,
  entropyBand,
  hasDictionaryBase,
  hasKeyboardPattern,
  hasDatePattern,
  hasLeet,
  structureHash,
  computeFingerprint,
} from '../clientPatternEngine';

describe('clientPatternEngine — structural primitives', () => {
  it('classifies characters into U/L/D/S', () => {
    expect(classifyChar('a')).toBe('L');
    expect(classifyChar('Z')).toBe('U');
    expect(classifyChar('7')).toBe('D');
    expect(classifyChar('@')).toBe('S');
  });

  it('builds the char-class sequence', () => {
    expect(charClassSequence('Summer2024')).toBe('ULLLLLDDDD');
    expect(charClassSequence('P@ss1')).toBe('USLLD');
  });

  it('buckets length like the server', () => {
    expect(lengthBucket(6)).toBe('very_short');
    expect(lengthBucket(8)).toBe('short');
    expect(lengthBucket(12)).toBe('medium');
    expect(lengthBucket(16)).toBe('long');
    expect(lengthBucket(24)).toBe('very_long');
  });

  it('classifies entropy into ascending bands', () => {
    expect(entropyBand(10)).toBe('very_low');
    expect(entropyBand(40)).toBe('low');
    expect(entropyBand(95)).toBe('very_high');
  });

  it('detects habit flags', () => {
    expect(hasDictionaryBase('summer99')).toBe(true);
    expect(hasDictionaryBase('p@ssw0rd')).toBe(true); // leet-normalised
    expect(hasDictionaryBase('Xk2!mNp9@Qz')).toBe(false);
    expect(hasKeyboardPattern('qwerty123')).toBe(true);
    expect(hasDatePattern('login2024')).toBe(true);
    expect(hasLeet('p@ssw0rd')).toBe(true);
    expect(hasLeet('plainword')).toBe(false);
  });

  it('produces a 64-char hex structure hash', async () => {
    const h = await structureHash('ULLLLLDDDD', 'medium');
    expect(h).toMatch(/^[0-9a-f]{64}$/);
  });
});

describe('clientPatternEngine — computeFingerprint', () => {
  it('is deterministic for the same password', async () => {
    const a = await computeFingerprint('Summer2024');
    const b = await computeFingerprint('Summer2024');
    expect(a).toEqual(b);
  });

  it('NEVER leaks the password or dictionary words (ZK invariant)', async () => {
    const password = 'Summer2024';
    const fp = await computeFingerprint(password);
    const serialized = JSON.stringify(fp);

    // The plaintext and its dictionary base must not appear anywhere.
    expect(serialized.toLowerCase()).not.toContain('summer');
    expect(serialized).not.toContain(password);
    // The only string field describing content is the U/L/D/S sequence.
    expect(fp.char_class_sequence).toMatch(/^[ULDS]*$/);
    // No base-words field exists at all.
    expect(fp).not.toHaveProperty('detected_base_words');
    expect(Object.keys(fp).sort()).toEqual([
      'char_class_sequence',
      'entropy_band',
      'has_date_pattern',
      'has_dictionary_base',
      'has_keyboard_pattern',
      'has_leet',
      'length',
      'length_bucket',
      'structure_hash',
    ]);
  });

  it('captures the expected shape for a weak password', async () => {
    const fp = await computeFingerprint('Summer2024');
    expect(fp.char_class_sequence).toBe('ULLLLLDDDD');
    expect(fp.length).toBe(10);
    expect(fp.length_bucket).toBe('medium');
    expect(fp.has_dictionary_base).toBe(true);
    expect(fp.has_date_pattern).toBe(true);
  });
});

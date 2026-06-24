/**
 * Synesthesia mapping tests
 * =========================
 *
 * Verifies the core promise of the feature: the mapping is fully deterministic
 * (same input -> identical output), values stay in their expected ranges, and
 * the identicon is stable + symmetric.
 */

import { describe, it, expect } from 'vitest';
import {
  GLYPHS,
  charClass,
  charToColor,
  charToGlyph,
  charToNote,
  signatureGrid,
  passwordToSensoryMap,
} from '../synesthesia';

const PENTATONIC_LETTERS = ['C', 'D', 'E', 'G', 'A'];

describe('charClass', () => {
  it('classifies the four character classes', () => {
    expect(charClass('A')).toBe('upper');
    expect(charClass('z')).toBe('lower');
    expect(charClass('5')).toBe('digit');
    expect(charClass('!')).toBe('symbol');
  });
});

describe('determinism', () => {
  it('charToColor is stable across calls', () => {
    expect(charToColor('a')).toEqual(charToColor('a'));
    expect(charToColor('Q')).toEqual(charToColor('Q'));
  });

  it('passwordToSensoryMap returns identical output for identical input', () => {
    const a = passwordToSensoryMap('Tr0ub4dour&3');
    const b = passwordToSensoryMap('Tr0ub4dour&3');
    expect(a).toEqual(b);
  });

  it('identical characters map identically regardless of position', () => {
    const map = passwordToSensoryMap('aa');
    expect(map.chars[0].color).toEqual(map.chars[1].color);
    expect(map.chars[0].glyph).toEqual(map.chars[1].glyph);
    expect(map.chars[0].note).toEqual(map.chars[1].note);
    // ...but the positional index still differs.
    expect(map.chars[0].index).toBe(0);
    expect(map.chars[1].index).toBe(1);
  });
});

describe('ranges', () => {
  it('hue stays within [0, 360) for a wide spread of characters', () => {
    const sample = 'aA0!zZ9~ Mq#'.split('');
    for (const ch of sample) {
      const { h } = charToColor(ch);
      expect(h).toBeGreaterThanOrEqual(0);
      expect(h).toBeLessThan(360);
    }
  });

  it('glyph index is in range and resolves to a known glyph', () => {
    const sample = 'aA0!zZ9~ Mq#'.split('');
    for (const ch of sample) {
      const g = charToGlyph(ch);
      expect(g.index).toBeGreaterThanOrEqual(0);
      expect(g.index).toBeLessThan(GLYPHS.length);
      expect(GLYPHS).toContain(g.name);
    }
  });

  it('note resolves to a positive pentatonic frequency', () => {
    const sample = 'aA0! '.split('');
    for (const ch of sample) {
      const note = charToNote(ch);
      expect(note.freq).toBeGreaterThan(0);
      expect(PENTATONIC_LETTERS).toContain(note.name[0]);
    }
  });
});

describe('signatureGrid', () => {
  it('produces a 5x5 vertically symmetric grid', () => {
    const { cells, size } = signatureGrid('correct horse battery staple');
    expect(size).toBe(5);
    expect(cells).toHaveLength(5);
    for (const row of cells) {
      expect(row).toHaveLength(5);
      expect(row[0]).toBe(row[4]);
      expect(row[1]).toBe(row[3]);
    }
  });

  it('is stable for the same password', () => {
    expect(signatureGrid('hunter2')).toEqual(signatureGrid('hunter2'));
  });

  it('differs between different passwords', () => {
    const a = signatureGrid('abc');
    const b = signatureGrid('xyz');
    // Either the colour or the cell pattern must differ.
    expect(a.color === b.color && JSON.stringify(a.cells) === JSON.stringify(b.cells)).toBe(false);
  });
});

describe('empty input', () => {
  it('returns an empty, non-throwing map', () => {
    const map = passwordToSensoryMap('');
    expect(map.length).toBe(0);
    expect(map.chars).toEqual([]);
    expect(map.signature.cells.flat().every((c) => c === false)).toBe(true);
  });
});

/**
 * Synesthetic Password Visualization — deterministic mapping core
 * ===============================================================
 *
 * Pure, framework-free functions that turn a password into a stable
 * multi-sensory representation (colour + glyph + musical note per character,
 * plus an identicon-style "signature" grid).
 *
 * Design contract:
 * - Deterministic: the same input always yields the exact same output, so the
 *   brain can learn to recognise a password by its signature. No randomness.
 * - Position-independent per character: an identical character always maps to
 *   the same colour/glyph/note regardless of where it appears, which reinforces
 *   recognition.
 * - No side effects: nothing here persists, logs, transmits, or caches the
 *   password or anything derived from it. Callers must keep it that way — the
 *   visualisation is reversible and therefore as sensitive as the plaintext.
 *
 * The only dependency is sha256 from @noble/hashes (already used elsewhere in
 * this codebase, e.g. didService.js) — no new package is introduced.
 */

import { sha256 } from '@noble/hashes/sha256';

// Golden angle (degrees). Multiplying by code point and taking mod 360 spreads
// adjacent characters far apart on the colour wheel for maximum separation.
const GOLDEN_ANGLE = 137.508;

// Glyph vocabulary. Pairing a shape with each colour is what makes the
// visualisation colour-blind safe — never rely on hue alone. Keep this list
// stable; reordering it would change every existing signature.
export const GLYPHS = Object.freeze([
  'circle',
  'triangle',
  'square',
  'diamond',
  'wave',
  'hexagon',
  'star',
  'cross',
]);

// Major pentatonic scale (semitone offsets from the tonic). Any subset of these
// notes sounds consonant together, so every password "melody" is pleasant and
// never dissonant.
const PENTATONIC_SEMITONES = Object.freeze([0, 2, 4, 7, 9]);
const PENTATONIC_NAMES = Object.freeze(['C', 'D', 'E', 'G', 'A']);

// Tonic reference: C4 ≈ 261.63 Hz.
const C4_HZ = 261.63;

/**
 * Character class. Used to tint saturation/lightness and pick an octave so the
 * four classes feel distinct without changing the per-character hue.
 * @param {string} ch single character
 * @returns {'upper'|'lower'|'digit'|'symbol'}
 */
export function charClass(ch) {
  if (ch >= 'A' && ch <= 'Z') return 'upper';
  if (ch >= 'a' && ch <= 'z') return 'lower';
  if (ch >= '0' && ch <= '9') return 'digit';
  return 'symbol';
}

// Saturation/lightness per class (percentages). Chosen for readable contrast on
// both light and dark backgrounds.
const CLASS_SL = Object.freeze({
  upper: { s: 72, l: 55 },
  lower: { s: 68, l: 64 },
  digit: { s: 85, l: 50 },
  symbol: { s: 58, l: 46 },
});

// Octave offset per class (in octaves relative to C4), so each class sits in its
// own register when the melody plays.
const CLASS_OCTAVE = Object.freeze({
  digit: -1,
  lower: 0,
  upper: 1,
  symbol: 2,
});

/**
 * Map a single character to a deterministic colour.
 * @param {string} ch single character
 * @returns {{ h: number, s: number, l: number, css: string }}
 */
export function charToColor(ch) {
  const code = ch.codePointAt(0) ?? 0;
  const h = (code * GOLDEN_ANGLE) % 360;
  const { s, l } = CLASS_SL[charClass(ch)];
  return { h, s, l, css: `hsl(${h.toFixed(1)}, ${s}%, ${l}%)` };
}

/**
 * Map a single character to one of the GLYPHS.
 * @param {string} ch single character
 * @returns {{ index: number, name: string }}
 */
export function charToGlyph(ch) {
  const code = ch.codePointAt(0) ?? 0;
  const index = code % GLYPHS.length;
  return { index, name: GLYPHS[index] };
}

/**
 * Map a single character to a pentatonic note.
 * @param {string} ch single character
 * @returns {{ name: string, freq: number, octave: number }}
 */
export function charToNote(ch) {
  const code = ch.codePointAt(0) ?? 0;
  const step = code % PENTATONIC_SEMITONES.length;
  const octave = CLASS_OCTAVE[charClass(ch)];
  const semitone = PENTATONIC_SEMITONES[step] + 12 * octave;
  const freq = C4_HZ * Math.pow(2, semitone / 12);
  return {
    name: `${PENTATONIC_NAMES[step]}${4 + octave}`,
    freq: Math.round(freq * 100) / 100,
    octave: 4 + octave,
  };
}

// Identicon geometry: a SIZE×SIZE grid with vertical mirror symmetry, so only
// the left half (plus centre column) is derived from the hash and the rest is
// reflected — the classic "GitHub identicon" look.
const GRID = 5;

/**
 * Build a deterministic identicon-style signature from the whole password.
 * @param {string} password
 * @returns {{ cells: boolean[][], color: string, size: number }}
 *   cells is a GRID×GRID row-major boolean matrix (vertically symmetric);
 *   color is an rgb() string derived from the hash.
 */
export function signatureGrid(password) {
  const size = GRID;
  const empty = {
    cells: Array.from({ length: size }, () => Array.from({ length: size }, () => false)),
    color: 'rgb(148, 163, 184)', // neutral slate for the empty state
    size,
  };
  if (!password) return empty;

  const digest = sha256(new TextEncoder().encode(password)); // Uint8Array(32)

  // Base colour from the first three bytes.
  const color = `rgb(${digest[0]}, ${digest[1]}, ${digest[2]})`;

  const halfCols = Math.ceil(size / 2); // columns 0..2 for a 5-wide grid
  const cells = Array.from({ length: size }, () => Array(size).fill(false));
  let bit = 0;
  for (let row = 0; row < size; row += 1) {
    for (let col = 0; col < halfCols; col += 1) {
      // Use one byte per cell (32 bytes >> 15 cells needed); fill on even value.
      const byte = digest[(3 + bit) % digest.length];
      const on = (byte & 1) === 0;
      cells[row][col] = on;
      cells[row][size - 1 - col] = on; // mirror horizontally
      bit += 1;
    }
  }
  return { cells, color, size };
}

/**
 * Full sensory map for a password: per-character channels plus the signature.
 * This is the primary entry point for the UI.
 * @param {string} password
 * @returns {{
 *   chars: Array<{ index: number, class: string, color: ReturnType<typeof charToColor>, glyph: ReturnType<typeof charToGlyph>, note: ReturnType<typeof charToNote> }>,
 *   signature: ReturnType<typeof signatureGrid>,
 *   length: number
 * }}
 */
export function passwordToSensoryMap(password) {
  const source = password ? Array.from(password) : [];
  const chars = source.map((ch, index) => ({
    index,
    class: charClass(ch),
    color: charToColor(ch),
    glyph: charToGlyph(ch),
    note: charToNote(ch),
  }));
  return {
    chars,
    signature: signatureGrid(password),
    length: source.length,
  };
}

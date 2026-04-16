import { describe, it, expect } from 'vitest';
import provider, {
  commit,
  commitBytes,
  commitFromPassword,
  deriveScalarFromPassword,
  deriveBlinding,
  proveEquality,
  verifyEquality,
  encodePoint,
  decodePoint,
} from '../commitmentSchnorrProvider';
import { toBase64, fromBase64 } from '../index';
import vectors from '../__fixtures__/vectors.json';

const hexToBig = (h) => BigInt(h);

describe('commitmentSchnorrProvider / cross-language vectors', () => {
  it('produces the pinned Pedersen commitments for fixed scalars', () => {
    const m = hexToBig(vectors.m);
    const r1 = hexToBig(vectors.r1);
    const r2 = hexToBig(vectors.r2);
    const r3 = hexToBig(vectors.r3);

    expect(toBase64(commitBytes(m, r1))).toBe(vectors.c1_b64);
    expect(toBase64(commitBytes(m, r2))).toBe(vectors.c2_b64);
    expect(toBase64(commitBytes(m + 1n, r3))).toBe(vectors.c3_b64);
  });

  it('derives m and r from password/item matching the Python transcript', () => {
    const m = deriveScalarFromPassword(vectors.derive_password, vectors.derive_item);
    const r = deriveBlinding(vectors.derive_password, vectors.derive_item);
    expect(`0x${m.toString(16)}`).toBe(vectors.derive_m_hex);
    expect(`0x${r.toString(16)}`).toBe(vectors.derive_r_hex);
    expect(toBase64(commitFromPassword(vectors.derive_password, vectors.derive_item)))
      .toBe(vectors.derive_c_b64);
  });

  it('encodes/decodes compressed 33-byte points reversibly', () => {
    const point = commit(12345n, 67890n);
    const bytes = encodePoint(point);
    expect(bytes.length).toBe(33);
    const back = decodePoint(bytes);
    expect(back.equals(point)).toBe(true);
  });
});

describe('commitmentSchnorrProvider / Schnorr equality soundness', () => {
  it('accepts a proof produced by an honest prover', () => {
    const m = 0x9999n;
    const r1 = 0xAAAAn;
    const r2 = 0xBBBBn;
    const c1 = commit(m, r1);
    const c2 = commit(m, r2);
    const { T, s } = proveEquality(c1, c2, r1, r2);
    expect(verifyEquality(encodePoint(c1), encodePoint(c2), T, s)).toBe(true);
  });

  it('rejects a proof when commitments hide different scalars', () => {
    const r1 = 0xAAAAn;
    const r2 = 0xBBBBn;
    const c1 = commit(0x9999n, r1);
    const c2 = commit(0x9998n, r2);
    const { T, s } = proveEquality(c1, c2, r1, r2);
    expect(verifyEquality(encodePoint(c1), encodePoint(c2), T, s)).toBe(false);
  });

  it('rejects a proof replayed against a different commitment pair', () => {
    const m = 0x9999n;
    const r1 = 0xAAAAn;
    const r2 = 0xBBBBn;
    const r3 = 0xCCCCn;
    const c1 = commit(m, r1);
    const c2 = commit(m, r2);
    const c3 = commit(m, r3);
    const { T, s } = proveEquality(c1, c2, r1, r2);
    expect(verifyEquality(encodePoint(c1), encodePoint(c3), T, s)).toBe(false);
  });

  it('rejects a tampered s scalar', () => {
    const r1 = 0xAAAAn;
    const r2 = 0xBBBBn;
    const c1 = commit(0x9999n, r1);
    const c2 = commit(0x9999n, r2);
    const { T, s } = proveEquality(c1, c2, r1, r2);
    const tampered = new Uint8Array(s);
    tampered[31] ^= 0x01;
    expect(verifyEquality(encodePoint(c1), encodePoint(c2), T, tampered)).toBe(false);
  });

  it('rejects s = 0 and s >= n', () => {
    const r1 = 0xAAAAn;
    const r2 = 0xBBBBn;
    const c1 = commit(0x9999n, r1);
    const c2 = commit(0x9999n, r2);
    const { T } = proveEquality(c1, c2, r1, r2);
    expect(verifyEquality(encodePoint(c1), encodePoint(c2), T, new Uint8Array(32))).toBe(false);
  });

  it('never throws on malformed inputs — returns false instead', () => {
    expect(verifyEquality(new Uint8Array(5), new Uint8Array(5), new Uint8Array(5), new Uint8Array(5))).toBe(false);
    expect(verifyEquality(null, null, null, null)).toBe(false);
  });
});

describe('provider default export', () => {
  it('exposes the expected scheme name', () => {
    expect(provider.scheme).toBe('commitment-schnorr-v1');
  });

  it('toBase64/fromBase64 round-trip', () => {
    const bytes = new Uint8Array([1, 2, 3, 250, 251, 252]);
    expect(fromBase64(toBase64(bytes))).toEqual(bytes);
  });
});

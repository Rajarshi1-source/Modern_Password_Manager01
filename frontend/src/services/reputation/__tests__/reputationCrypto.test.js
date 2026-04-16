/**
 * Unit tests for the reputation crypto helpers.
 *
 * The binding_hash algorithm must stay byte-identical to the Python
 * implementation at `password_reputation/providers/commitment_claim.py`,
 * otherwise the server will always reject client-generated proofs.
 */

import { describe, expect, test } from 'vitest';

import {
  commitmentForReputation,
  computeBindingHash,
  estimateEntropyBits,
} from '../reputationCrypto';

const bytesToHex = (bytes) =>
  Array.from(bytes, (b) => b.toString(16).padStart(2, '0')).join('');

describe('computeBindingHash', () => {
  test('is deterministic for the same inputs', () => {
    const commitment = new Uint8Array(33).fill(0x42);
    const a = computeBindingHash({ commitment, claimedBits: 80, userId: 7 });
    const b = computeBindingHash({ commitment, claimedBits: 80, userId: 7 });
    expect(bytesToHex(a)).toBe(bytesToHex(b));
    expect(a).toHaveLength(32);
  });

  test('differs when any input differs', () => {
    const commitment = new Uint8Array(33).fill(0x42);
    const base = bytesToHex(computeBindingHash({ commitment, claimedBits: 80, userId: 7 }));
    expect(
      bytesToHex(computeBindingHash({ commitment, claimedBits: 81, userId: 7 })),
    ).not.toBe(base);
    expect(
      bytesToHex(computeBindingHash({ commitment, claimedBits: 80, userId: 8 })),
    ).not.toBe(base);
    const otherCommitment = new Uint8Array(33).fill(0x43);
    expect(
      bytesToHex(computeBindingHash({ commitment: otherCommitment, claimedBits: 80, userId: 7 })),
    ).not.toBe(base);
  });

  test('rejects non-Uint8Array commitment', () => {
    expect(() =>
      computeBindingHash({ commitment: 'hello', claimedBits: 80, userId: 1 }),
    ).toThrow(/Uint8Array/);
  });
});

describe('commitmentForReputation', () => {
  test('produces a 33-byte compressed secp256k1 point', () => {
    const c = commitmentForReputation('correct horse battery staple', 'vault-item-1');
    expect(c).toBeInstanceOf(Uint8Array);
    expect(c).toHaveLength(33);
    // Compressed points start with 0x02 or 0x03.
    expect([0x02, 0x03]).toContain(c[0]);
  });

  test('is deterministic for the same (password, scope)', () => {
    const c1 = commitmentForReputation('p@ssw0rd!', 'scope-A');
    const c2 = commitmentForReputation('p@ssw0rd!', 'scope-A');
    expect(bytesToHex(c1)).toBe(bytesToHex(c2));
  });

  test('differs for different scopes', () => {
    const c1 = commitmentForReputation('p@ssw0rd!', 'scope-A');
    const c2 = commitmentForReputation('p@ssw0rd!', 'scope-B');
    expect(bytesToHex(c1)).not.toBe(bytesToHex(c2));
  });
});

describe('estimateEntropyBits', () => {
  test('empty password → 0 bits', () => {
    expect(estimateEntropyBits('')).toBe(0);
  });

  test('penalises short passwords', () => {
    expect(estimateEntropyBits('abc')).toBeLessThan(estimateEntropyBits('abcdefghijkl'));
  });

  test('scales with character classes', () => {
    const lowerOnly = estimateEntropyBits('abcdefghijklmn');
    const mixed = estimateEntropyBits('Abcdefghijk1!2');
    expect(mixed).toBeGreaterThan(lowerOnly);
  });
});

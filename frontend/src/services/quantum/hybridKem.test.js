import { describe, expect, it } from 'vitest';
import {
  HYBRID_PUBLIC_KEY_SIZE,
  HYBRID_SECRET_KEY_SIZE,
  generateHybridKeyPair,
  openSealed,
  sealToHybridKey,
} from './hybridKem';

const CONTEXT = 'test-context';
const HEADER = 1 + 32 + 1088 + 12;

describe('hybrid X25519 + ML-KEM-768 sealing', () => {
  it('round-trips to the recipient only', async () => {
    const alice = await generateHybridKeyPair();
    const mallory = await generateHybridKeyPair();
    expect(alice.publicKey.length).toBe(HYBRID_PUBLIC_KEY_SIZE);
    expect(alice.secretKey.length).toBe(HYBRID_SECRET_KEY_SIZE);

    const message = new TextEncoder().encode('share bytes');
    const sealed = await sealToHybridKey(alice.publicKey, message, CONTEXT);
    expect(sealed.length).toBe(HEADER + message.length + 16);
    expect(sealed[0]).toBe(1);

    expect(Array.from(await openSealed(alice.secretKey, alice.publicKey, sealed, CONTEXT))).toEqual(Array.from(message));
    await expect(openSealed(mallory.secretKey, mallory.publicKey, sealed, CONTEXT)).rejects.toThrow();
    await expect(openSealed(alice.secretKey, alice.publicKey, sealed, 'other')).rejects.toThrow();
  });

  it('binds both ciphertexts: swapping either component breaks opening', async () => {
    const alice = await generateHybridKeyPair();
    const message = new Uint8Array(33).fill(7);
    const a = await sealToHybridKey(alice.publicKey, message, CONTEXT);
    const b = await sealToHybridKey(alice.publicKey, message, CONTEXT);

    const swapX25519 = a.slice();
    swapX25519.set(b.subarray(1, 33), 1);
    await expect(openSealed(alice.secretKey, alice.publicKey, swapX25519, CONTEXT)).rejects.toThrow();

    const swapMlkem = a.slice();
    swapMlkem.set(b.subarray(33, 33 + 1088), 33);
    await expect(openSealed(alice.secretKey, alice.publicKey, swapMlkem, CONTEXT)).rejects.toThrow();
  });

  it('needs both secret keys: a right X25519 key with a wrong ML-KEM key fails', async () => {
    const alice = await generateHybridKeyPair();
    const other = await generateHybridKeyPair();
    const sealed = await sealToHybridKey(alice.publicKey, new Uint8Array([1, 2, 3]), CONTEXT);
    const mixed = alice.secretKey.slice();
    mixed.set(other.secretKey.subarray(32), 32);
    await expect(openSealed(mixed, alice.publicKey, sealed, CONTEXT)).rejects.toThrow();
  });

  it('refuses malformed keys instead of falling back', async () => {
    await expect(sealToHybridKey(new Uint8Array(32), new Uint8Array(1), CONTEXT)).rejects.toThrow();
    const alice = await generateHybridKeyPair();
    const lowOrder = alice.publicKey.slice();
    lowOrder.fill(0, 0, 32);
    await expect(sealToHybridKey(lowOrder, new Uint8Array(1), CONTEXT)).rejects.toThrow();
  });
});

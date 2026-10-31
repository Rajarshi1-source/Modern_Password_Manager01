import { describe, expect, it, vi } from 'vitest';
import { generateHybridKeyPair, HYBRID_PUBLIC_KEY_SIZE } from './hybridKem';

// The first ML-KEM start fails (say, a wasm load error); later ones work.
// vi.mock is hoisted above the import, so hybridKem gets this module.
vi.mock('mlkem', async (importOriginal) => {
  const real = await importOriginal();
  let calls = 0;
  return {
    ...real,
    createMlKem768: vi.fn(() => {
      calls += 1;
      return calls === 1 ? Promise.reject(new Error('mlkem start failed')) : real.createMlKem768();
    }),
  };
});

describe('hybrid KEM start-up', () => {
  it('retries ML-KEM after a failed start instead of failing for good', async () => {
    await expect(generateHybridKeyPair()).rejects.toThrow('mlkem start failed');
    const { publicKey } = await generateHybridKeyPair();
    expect(publicKey).toHaveLength(HYBRID_PUBLIC_KEY_SIZE);
  });
});

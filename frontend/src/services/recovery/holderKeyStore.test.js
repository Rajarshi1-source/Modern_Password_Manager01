import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import {
  _setWrappingKeyBackendForTests,
  forgetRequesterKeyPair,
  getOrCreateGuardianPublicKey,
  loadGuardianKeyPair,
  loadRequesterKeyPair,
  newRequesterKeyPair,
  saveRequesterKeyPair,
} from './holderKeyStore';
import { proveShareHolding, sealSeedForGuardians } from './sealedShareRecovery';

// Stands in for IndexedDB, which jsdom lacks; holds the same non-extractable
// CryptoKey object IndexedDB would.
function memoryBackend() {
  const map = new Map();
  return {
    async get(id) { return map.get(id); },
    async add(id, value) {
      if (map.has(id)) throw new Error('exists');
      map.set(id, value);
    },
  };
}

describe('holderKeyStore', () => {
  beforeEach(() => {
    window.localStorage.clear();
    _setWrappingKeyBackendForTests(memoryBackend());
  });
  afterEach(() => _setWrappingKeyBackendForTests(null));

  it('never writes a secret key to localStorage in the clear', async () => {
    const publicKey = await getOrCreateGuardianPublicKey();
    const keyPair = await loadGuardianKeyPair();
    expect(keyPair.publicKey).toBe(publicKey);
    const stored = Object.values({ ...window.localStorage }).join('\n');
    expect(stored).not.toContain(keyPair.secretKey);
    expect(stored).not.toContain('"secretKey"');
  });

  it('gives concurrent first uses one key pair, and that pair opens its shares', async () => {
    const keys = await Promise.all([1, 2, 3, 4].map(() => getOrCreateGuardianPublicKey()));
    expect(new Set(keys).size).toBe(1);
    const setup = await sealSeedForGuardians({
      seed: new Uint8Array(32).fill(3), threshold: 2, guardianPublicKeys: [keys[0], keys[0]],
    });
    const proof = await proveShareHolding({
      keyPair: await loadGuardianKeyPair(), sealedShare: setup.shares[0].sealedShare,
    });
    expect(proof).toBeTruthy();
  });

  it('fails without storing anything when the wrapping key cannot be saved', async () => {
    _setWrappingKeyBackendForTests({
      async get() { return undefined; },
      async add() { throw new Error('QuotaExceededError'); },
    });
    await expect(getOrCreateGuardianPublicKey()).rejects.toThrow('QuotaExceededError');
    expect(window.localStorage.length).toBe(0);
  });

  it('keeps requester keys per request and forgets them', async () => {
    const keyPair = await newRequesterKeyPair();
    await saveRequesterKeyPair('req-1', keyPair);
    expect(await loadRequesterKeyPair('req-1')).toEqual(keyPair);
    expect(await loadRequesterKeyPair('req-2')).toBeNull();
    // A wrapped key copied to another request's slot does not open there.
    window.localStorage.setItem('pwm.recovery.requesterKeyPair.v2.req-2',
      window.localStorage.getItem('pwm.recovery.requesterKeyPair.v2.req-1'));
    await expect(loadRequesterKeyPair('req-2')).rejects.toThrow();
    forgetRequesterKeyPair('req-1');
    expect(await loadRequesterKeyPair('req-1')).toBeNull();
  });
});

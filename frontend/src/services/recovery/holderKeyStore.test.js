import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import {
  _setWrappingKeyBackendForTests,
  assertKeyStorageAvailable,
  forgetRequesterKeyPair,
  getOrCreateGuardianPublicKey,
  loadGuardianKeyPair,
  loadRequesterKeyPair,
  newRequesterKeyPair,
  replaceLostGuardianKey,
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
    clear() { map.clear(); },
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

  it('reports whether a requester key can be stored, leaving nothing behind', async () => {
    await expect(assertKeyStorageAvailable()).resolves.toBeUndefined();
    expect(window.localStorage.length).toBe(0);
    _setWrappingKeyBackendForTests({
      async get() { return undefined; },
      async add() { throw new Error('QuotaExceededError'); },
    });
    await expect(assertKeyStorageAvailable()).rejects.toThrow('QuotaExceededError');
  });

  it('explains that a browser without IndexedDB cannot store keys', async () => {
    _setWrappingKeyBackendForTests(null);
    await expect(getOrCreateGuardianPublicKey()).rejects.toMatchObject({
      name: 'KeyStorageError', message: expect.stringContaining('no IndexedDB'),
    });
    expect(window.localStorage.length).toBe(0);
  });

  it('does not hand out a guardian key whose wrapping key is gone', async () => {
    const backend = memoryBackend();
    _setWrappingKeyBackendForTests(backend);
    await getOrCreateGuardianPublicKey();
    const stored = { ...window.localStorage };
    // IndexedDB cleared, localStorage kept, this tab still open.
    backend.clear();
    const lost = { name: 'KeyStorageError', keyLost: true };
    await expect(getOrCreateGuardianPublicKey()).rejects.toMatchObject(lost);
    await expect(loadGuardianKeyPair()).rejects.toMatchObject(lost);
    expect({ ...window.localStorage }).toEqual(stored);
  });

  it('treats a stored value that is no longer base64 as a lost key', async () => {
    const original = await getOrCreateGuardianPublicKey();
    const name = 'pwm.recovery.guardianKeyPair.v2';
    const stored = JSON.parse(window.localStorage.getItem(name));
    window.localStorage.setItem(name, JSON.stringify({ ...stored, iv: '!not base64!' }));
    await expect(getOrCreateGuardianPublicKey()).rejects.toMatchObject({ keyLost: true });
    expect(await replaceLostGuardianKey()).not.toBe(original);
  });

  it.each([
    ['not JSON', 'not json'],
    ['missing its wrapped secret', '{"publicKey":"AAEC"}'],
  ])('keeps a damaged guardian record until it is replaced: %s', async (_, damaged) => {
    const name = 'pwm.recovery.guardianKeyPair.v2';
    window.localStorage.setItem(name, damaged);
    await expect(getOrCreateGuardianPublicKey()).rejects.toMatchObject({ keyLost: true });
    expect(window.localStorage.getItem(name)).toBe(damaged);
    const replacement = await replaceLostGuardianKey();
    expect((await loadGuardianKeyPair()).publicKey).toBe(replacement);
  });

  it('refuses a stored public key that is not the secret key\'s', async () => {
    const original = await getOrCreateGuardianPublicKey();
    const name = 'pwm.recovery.guardianKeyPair.v2';
    const stored = window.localStorage.getItem(name);
    const other = (await newRequesterKeyPair()).publicKey;
    const swapped = JSON.stringify({ ...JSON.parse(stored), publicKey: other });
    window.localStorage.setItem(name, swapped);
    const lost = { name: 'KeyStorageError', keyLost: true };
    await expect(getOrCreateGuardianPublicKey()).rejects.toMatchObject(lost);
    await expect(loadGuardianKeyPair()).rejects.toMatchObject(lost);
    expect(window.localStorage.getItem(name)).toBe(swapped);
    const replacement = await replaceLostGuardianKey();
    expect(replacement).not.toBe(other);
    expect(replacement).not.toBe(original);
  });

  it('tells a requester to start again, not to make a guardian key', async () => {
    const backend = memoryBackend();
    _setWrappingKeyBackendForTests(backend);
    await saveRequesterKeyPair('req-1', await newRequesterKeyPair());
    backend.clear();
    const err = await loadRequesterKeyPair('req-1').catch((e) => e);
    expect(err).toMatchObject({ name: 'KeyStorageError', keyLost: true });
    expect(err.message).toContain('Start recovery again');
    expect(err.message).not.toContain('guardian-key');
  });

  it('never advises clearing site data, which deletes wrapped vault keys', async () => {
    const backend = memoryBackend();
    _setWrappingKeyBackendForTests(backend);
    await getOrCreateGuardianPublicKey();
    backend.clear();
    const err = await getOrCreateGuardianPublicKey().catch((e) => e);
    expect(err.message).toContain('/recovery/guardian-key');
    expect(err.message).not.toMatch(/clear this site/i);
  });

  it('replaces only a guardian key that cannot be opened', async () => {
    const backend = memoryBackend();
    _setWrappingKeyBackendForTests(backend);
    const original = await getOrCreateGuardianPublicKey();
    expect(await replaceLostGuardianKey()).toBe(original);
    const blocked = new Error('blocked');
    const { get } = backend;
    backend.get = async () => { throw blocked; };
    await expect(replaceLostGuardianKey()).rejects.toBe(blocked);
    backend.get = get;
    expect(await getOrCreateGuardianPublicKey()).toBe(original);

    backend.clear();
    const replacement = await replaceLostGuardianKey();
    expect(replacement).not.toBe(original);
    expect(await getOrCreateGuardianPublicKey()).toBe(replacement);
    expect((await loadGuardianKeyPair()).publicKey).toBe(replacement);
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

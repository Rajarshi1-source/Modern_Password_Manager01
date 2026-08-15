import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

/**
 * Vault v2 salt portability (fix/vault-v2-salt-portability, see
 * docs/vault-v2-salt-portability-plan.md).
 *
 * `getOrCreateUserSalt` (sessionVaultCrypto.js) mints a per-user salt into
 * THIS device's localStorage and never sends it to the server. Before this
 * fix, `decryptItem` always decrypted with the session key derived from that
 * device-local salt — so an item written on a different device (or on this
 * one before site data was cleared) could never decrypt, even with the
 * correct master password, because its envelope was sealed under a salt this
 * device has never seen.
 *
 * The fix: every envelope already carries the salt it was sealed under
 * (`encryptItem` always has, unrelated to this bug). `decryptItem` now keys
 * off that field, deriving (and memoizing) a key per foreign salt on demand.
 *
 * No mocks: real WebCrypto (jsdom) and real localStorage, matching how
 * sessionVaultCryptoV3.test.js exercises the sibling v3 module.
 */
import {
  initSessionKeyFromPassword,
  encryptItem,
  decryptItem,
  clearSessionKey,
  hasSessionKey,
} from '../sessionVaultCrypto';

const saltStorageKey = (userId) => `vaultKeySalt:${userId}`;

// Polls (via macrotask ticks, not just microtasks) until `predicate()` is
// true. Used to wait for a stalled `deriveKey` mock's executor to actually
// run — it fires one macro/microtask tier deeper than the call site, after
// the real (unmocked) `importKey` call inside `deriveDirectKey` resolves.
const waitUntil = async (predicate, timeoutMs = 1000) => {
  const start = Date.now();
  while (!predicate()) {
    if (Date.now() - start > timeoutMs) {
      throw new Error('waitUntil: timed out waiting for condition');
    }
    await new Promise((resolve) => setTimeout(resolve, 0));
  }
};

beforeEach(() => {
  localStorage.clear();
  clearSessionKey();
});

afterEach(() => {
  clearSessionKey();
  localStorage.clear();
});

describe('sessionVaultCrypto — cross-device salt portability', () => {
  it('decrypts an envelope written under a different (foreign) salt, given the correct password', async () => {
    // "Device A": mints its own salt for this account, encrypts an item.
    await initSessionKeyFromPassword('correct horse battery staple', 'alice');
    const envelope = await encryptItem({ name: 'GitHub', password: 'p@ss' });
    clearSessionKey();

    // "Device B": same account, but no localStorage salt for it yet —
    // simulates a fresh browser, or this device after clearing site data.
    // Mints a DIFFERENT salt from device A's.
    localStorage.removeItem(saltStorageKey('alice'));
    await initSessionKeyFromPassword('correct horse battery staple', 'alice');

    // Before the fix this would derive with device B's salt, the AES-GCM tag
    // check would fail, and the item would render "Decryption failed"
    // despite the correct password.
    const decrypted = await decryptItem(envelope);
    expect(decrypted).toEqual({ name: 'GitHub', password: 'p@ss' });
  });

  it('keeps the same-salt fast path working (no regression)', async () => {
    await initSessionKeyFromPassword('pw', 'bob');
    const envelope = await encryptItem({ name: 'Same device' });
    const decrypted = await decryptItem(envelope);
    expect(decrypted).toEqual({ name: 'Same device' });
  });

  it('still rejects a genuinely wrong password against a foreign-salt envelope', async () => {
    await initSessionKeyFromPassword('right-password', 'carol');
    const envelope = await encryptItem({ secret: 'x' });
    clearSessionKey();

    localStorage.removeItem(saltStorageKey('carol'));
    await initSessionKeyFromPassword('WRONG-password', 'carol');

    await expect(decryptItem(envelope)).rejects.toThrow();
  });

  it('still rejects a wrong password against a same-salt envelope', async () => {
    await initSessionKeyFromPassword('right-password', 'dave');
    const envelope = await encryptItem({ secret: 'x' });
    clearSessionKey();
    // Same userId, salt still in localStorage — reads the SAME persisted salt.
    await initSessionKeyFromPassword('WRONG-password', 'dave');

    await expect(decryptItem(envelope)).rejects.toThrow();
  });

  it('derives a foreign salt key once and reuses it across concurrently-decrypted items', async () => {
    await initSessionKeyFromPassword('pw', 'erin');
    const envelopeA = await encryptItem({ n: 1 });
    const envelopeB = await encryptItem({ n: 2 });
    const envelopeC = await encryptItem({ n: 3 });
    clearSessionKey();

    localStorage.removeItem(saltStorageKey('erin'));
    await initSessionKeyFromPassword('pw', 'erin');

    const deriveKeySpy = vi.spyOn(window.crypto.subtle, 'deriveKey');

    // Mirrors how App.jsx decrypts the vault list: concurrently, via
    // Promise.all. Without memoization this would run PBKDF2 three times for
    // one shared foreign salt.
    const results = await Promise.all([
      decryptItem(envelopeA),
      decryptItem(envelopeB),
      decryptItem(envelopeC),
    ]);

    expect(results).toEqual([{ n: 1 }, { n: 2 }, { n: 3 }]);
    expect(deriveKeySpy).toHaveBeenCalledTimes(1);
    deriveKeySpy.mockRestore();
  });

  it('clearSessionKey drops the retained password and cache — decrypt then fails as locked', async () => {
    await initSessionKeyFromPassword('pw', 'frank');
    const envelope = await encryptItem({ secret: 'x' });
    clearSessionKey();

    await expect(decryptItem(envelope)).rejects.toThrow(/locked/i);
  });

  it('does not resurrect a stale cached foreign-salt key after clearSessionKey + re-init with a different password', async () => {
    await initSessionKeyFromPassword('pw', 'grace');
    const envelope = await encryptItem({ secret: 'x' });
    clearSessionKey();

    localStorage.removeItem(saltStorageKey('grace'));
    await initSessionKeyFromPassword('pw', 'grace');
    // Warm the foreign-salt cache once, with the CORRECT password.
    await expect(decryptItem(envelope)).resolves.toEqual({ secret: 'x' });

    clearSessionKey();
    // A different password now, same account. If the cache (or the retained
    // password) survived `clearSessionKey`, this would wrongly decrypt using
    // the old, correct-password-derived key instead of failing.
    await initSessionKeyFromPassword('a-different-password', 'grace');
    await expect(decryptItem(envelope)).rejects.toThrow();
  });
});

describe('sessionVaultCrypto — session-generation guard against stale async commits', () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('does not resurrect a session cleared while initSessionKeyFromPassword was still deriving', async () => {
    // Stall the PBKDF2 derivation so we can clear the session mid-flight and
    // control exactly when the stalled call resolves.
    let releaseDerive;
    vi.spyOn(window.crypto.subtle, 'deriveKey').mockImplementation(
      () => new Promise((resolve) => { releaseDerive = resolve; }),
    );

    const initPromise = initSessionKeyFromPassword('pw', 'ivy');
    // Wait for execution to actually reach the mocked `deriveKey` call (it's
    // one await deeper than this call site, behind the real `importKey`).
    await waitUntil(() => typeof releaseDerive === 'function');
    // The PBKDF2 call above is now suspended; nothing has committed yet.
    clearSessionKey();
    vi.restoreAllMocks();

    // Let the stalled (now-stale) derivation resolve.
    releaseDerive({});

    await expect(initPromise).rejects.toThrow(/superseded/i);
    // The commit must have been skipped entirely -- not just re-cleared.
    expect(hasSessionKey()).toBe(false);
  });

  it('lets a newer initSessionKeyFromPassword call win when an older one is still pending', async () => {
    let releaseFirstDerive;
    const deriveKeySpy = vi.spyOn(window.crypto.subtle, 'deriveKey').mockImplementationOnce(
      () => new Promise((resolve) => { releaseFirstDerive = resolve; }),
    );

    const firstInit = initSessionKeyFromPassword('old-account-password', 'judy');
    await waitUntil(() => typeof releaseFirstDerive === 'function');
    // `firstInit` is now suspended mid-derivation. A second call (e.g. a fast
    // account switch) starts and completes normally before the first resolves.
    deriveKeySpy.mockRestore();
    await initSessionKeyFromPassword('new-account-password', 'judy');
    const envelope = await encryptItem({ secret: 'newer session' });

    // Now let the stale first call's derivation resolve.
    releaseFirstDerive({});
    await expect(firstInit).rejects.toThrow(/superseded/i);

    // The newer session must still be the one in force.
    await expect(decryptItem(envelope)).resolves.toEqual({ secret: 'newer session' });
  });
});

describe('sessionVaultCrypto — legacy/malformed envelopes unaffected', () => {
  it('returns {} for non-JSON payloads', async () => {
    await initSessionKeyFromPassword('pw', 'heidi');
    expect(await decryptItem('not json')).toEqual({});
  });

  it('returns {_legacyPlaintext: true} for envelopes missing the v2 marker', async () => {
    await initSessionKeyFromPassword('pw', 'heidi');
    expect(await decryptItem(JSON.stringify({ foo: 'bar' }))).toEqual({ _legacyPlaintext: true });
  });

  it('returns {} for an empty string', async () => {
    expect(await decryptItem('')).toEqual({});
  });
});

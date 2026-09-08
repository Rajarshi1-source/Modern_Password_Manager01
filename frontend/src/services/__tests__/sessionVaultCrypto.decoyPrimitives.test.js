/**
 * The decoy primitives are a PARTITION of one flag, and that is the property
 * worth pinning.
 *
 *   encryptItem / decryptItem-side writes  refuse iff  sessionIsDecoy
 *   encryptDecoyItem / *DecoyContainer     refuse iff !sessionIsDecoy
 *
 * Neither half is safe alone. A decoy-session write reaching `/api/vault/`
 * permanently corrupts a row in the one shared item list (see `encryptItem`'s
 * own comment); a real-session write reaching the decoy container puts a
 * genuine secret under a key that a password handed over under duress opens.
 * These tests assert both directions, on the real module -- no mock of
 * `sessionVaultCrypto` itself, since the predicates ARE the subject.
 */
import { describe, test, expect, vi, beforeEach, afterEach } from 'vitest';
import { webcrypto } from 'node:crypto';

import * as svc from '../sessionVaultCrypto';
import { DECOY_WRITE_REFUSAL } from '../sessionVaultCrypto';

const SALT = 'c2FsdHNhbHRzYWx0c2E=';
const dek = () => new Uint8Array(32).fill(3);

beforeEach(() => {
  if (!globalThis.window) globalThis.window = globalThis;
  // jsdom exposes `crypto` as a getter-only property and ships no
  // `crypto.subtle`, so it has to be redefined rather than assigned.
  Object.defineProperty(window, 'crypto', { value: webcrypto, configurable: true, writable: true });
  localStorage.clear();
  svc.clearSessionKey();
});

afterEach(() => {
  svc.clearSessionKey();
  vi.restoreAllMocks();
});

const enterSession = ({ decoy }) => svc.installRawDek(dek(), SALT, 'user-1', null, decoy);

describe('a REAL session', () => {
  beforeEach(async () => { await enterSession({ decoy: false }); });

  test('encryptItem works and encryptDecoyItem refuses', async () => {
    await expect(svc.encryptItem({ a: 1 })).resolves.toEqual(expect.any(String));
    await expect(svc.encryptDecoyItem({ a: 1 })).rejects.toThrow(/not a decoy session/);
  });

  test('the decoy container primitives both refuse', async () => {
    await expect(svc.encryptDecoyContainer(new Uint8Array(16)))
      .rejects.toThrow(/not a decoy session/);
    await expect(svc.decryptDecoyContainer(new Uint8Array(12), new Uint8Array(32)))
      .rejects.toThrow(/not a decoy session/);
  });
});

describe('a DECOY session', () => {
  beforeEach(async () => { await enterSession({ decoy: true }); });

  test('encryptItem refuses with the shared string and encryptDecoyItem works', async () => {
    // Sourced from the module, never re-typed: a literal copy here would make
    // the assertion compare the test against itself (envelope plan §39.3/§40.1).
    await expect(svc.encryptItem({ a: 1 })).rejects.toThrow(DECOY_WRITE_REFUSAL);
    await expect(svc.encryptDecoyItem({ a: 1 })).resolves.toEqual(expect.any(String));
  });

  test('the refusal string names nothing', () => {
    expect(DECOY_WRITE_REFUSAL).not.toMatch(/decoy|duress|slot/i);
  });

  test('encryptDecoyItem produces the SAME envelope shape encryptItem does', async () => {
    const decoyEnvelope = JSON.parse(await svc.encryptDecoyItem({ a: 1 }));

    svc.clearSessionKey();
    await enterSession({ decoy: false });
    const realEnvelope = JSON.parse(await svc.encryptItem({ a: 1 }));

    // The whole display design rests on a decoy row being indistinguishable
    // from a server row at every layer above the store, so the two must agree
    // on version, salt and field set -- not merely both "look like" envelopes.
    expect(Object.keys(decoyEnvelope).sort()).toEqual(Object.keys(realEnvelope).sort());
    expect(decoyEnvelope.v).toBe(realEnvelope.v);
    expect(decoyEnvelope.salt).toBe(realEnvelope.salt);
  });

  test('the container round-trips under the session key', async () => {
    const plaintext = new TextEncoder().encode('{"v":"dvc-1","rows":[]}');
    const { iv, ct } = await svc.encryptDecoyContainer(plaintext);

    const out = await svc.decryptDecoyContainer(iv, ct);

    expect(new TextDecoder().decode(out)).toBe('{"v":"dvc-1","rows":[]}');
  });
});

describe('a LOCKED vault', () => {
  test('every decoy primitive reports locked, not "not a decoy session"', async () => {
    // Order matters: the locked check runs first, so a caller cannot learn
    // anything about decoy state from a locked vault.
    await expect(svc.encryptDecoyItem({ a: 1 })).rejects.toThrow(/Vault is locked/);
    await expect(svc.encryptDecoyContainer(new Uint8Array(16))).rejects.toThrow(/Vault is locked/);
    await expect(svc.decryptDecoyContainer(new Uint8Array(12), new Uint8Array(32)))
      .rejects.toThrow(/Vault is locked/);
  });
});

describe('the session-generation guard', () => {
  test('a lock landing during the encrypt await discards the result', async () => {
    await enterSession({ decoy: true });

    // Synchronise on the thing being timed: the lock has to land INSIDE the
    // subtle.encrypt await, so it is triggered from a stub standing in for it
    // rather than fired hopefully alongside (envelope plan §38.4).
    const realEncrypt = webcrypto.subtle.encrypt.bind(webcrypto.subtle);
    vi.spyOn(window.crypto.subtle, 'encrypt').mockImplementation(async (...args) => {
      const result = await realEncrypt(...args);
      svc.clearSessionKey();
      return result;
    });

    await expect(svc.encryptDecoyContainer(new Uint8Array(16)))
      .rejects.toThrow(/session changed/i);
  });

  test('a lock landing during the decrypt await discards the plaintext', async () => {
    await enterSession({ decoy: true });
    const plaintext = new TextEncoder().encode('secret');
    const { iv, ct } = await svc.encryptDecoyContainer(plaintext);

    const realDecrypt = webcrypto.subtle.decrypt.bind(webcrypto.subtle);
    vi.spyOn(window.crypto.subtle, 'decrypt').mockImplementation(async (...args) => {
      const result = await realDecrypt(...args);
      svc.clearSessionKey();
      return result;
    });

    // The plaintext IS recovered inside the call; the guard is what stops it
    // being handed back to a caller that no longer owns the session.
    await expect(svc.decryptDecoyContainer(iv, ct)).rejects.toThrow(/session changed/i);
  });
});

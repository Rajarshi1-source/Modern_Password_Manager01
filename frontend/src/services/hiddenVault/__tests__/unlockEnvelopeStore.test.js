/**
 * Unit tests for unlockEnvelopeStore — docs/vault-unlock-envelope-integration-plan.md §4.
 *
 * argon2-browser doesn't run cleanly under jsdom, so we mock it with the same
 * deterministic SHA-256 KDF stand-in used by sessionVaultCryptoV3.test.js and
 * cryptoService.fingerprint.test.js. The point of these tests is the store's
 * OWN contract (slot routing, payload shape, storage, the no-tell property) —
 * independent of which real KDF backs it.
 */
import { afterEach, beforeEach, describe, expect, test, vi } from 'vitest';

vi.mock('argon2-browser', () => {
  const hash = vi.fn(async ({ pass, salt }) => {
    const saltBytes = salt instanceof Uint8Array ? salt : new TextEncoder().encode(String(salt));
    const passBytes = new TextEncoder().encode(pass);
    const combined = new Uint8Array(passBytes.length + saltBytes.length);
    combined.set(passBytes, 0);
    combined.set(saltBytes, passBytes.length);
    const digest = await crypto.subtle.digest('SHA-256', combined);
    return { hash: new Uint8Array(digest) };
  });
  const ArgonType = { Argon2id: 2 };
  // hiddenVaultEnvelope.js does `import argon2 from 'argon2-browser'`
  // (default import), unlike cryptoService's `import * as argon2` -- so the
  // mock needs a `default` export too, not just named ones.
  return { ArgonType, hash, default: { ArgonType, hash } };
});

import {
  hasEnvelope,
  loadEnvelope,
  saveEnvelope,
  clearEnvelope,
  provision,
  setDecoySlot,
  open,
  MalformedSlotPayloadError,
} from '../unlockEnvelopeStore';
import { WrongPasswordError, TIERS, tierBytes } from '../hiddenVaultEnvelope';

const USER_ID = 'user-42';
const REAL_PASSWORD = 'correct horse battery staple';
const DECOY_PASSWORD = 'a totally different decoy phrase';
const DEK = new Uint8Array(32).map((_, i) => i + 1);
const SALT = 'ZGV2aWNlLXNhbHQtMTIzNDU2'; // arbitrary base64-looking device salt

beforeEach(() => {
  localStorage.clear();
});

afterEach(() => {
  localStorage.clear();
});

describe('storage helpers', () => {
  test('hasEnvelope/loadEnvelope are null/false before anything is saved', () => {
    expect(hasEnvelope(USER_ID)).toBe(false);
    expect(loadEnvelope(USER_ID)).toBeNull();
  });

  test('round-trips a blob through localStorage losslessly', () => {
    const blob = new Uint8Array([1, 2, 3, 250, 251, 252, 0, 255]);
    saveEnvelope(USER_ID, blob);

    expect(hasEnvelope(USER_ID)).toBe(true);
    expect(loadEnvelope(USER_ID)).toEqual(blob);
  });

  test('clearEnvelope removes the stored blob', () => {
    saveEnvelope(USER_ID, new Uint8Array([9, 9, 9]));
    clearEnvelope(USER_ID);

    expect(hasEnvelope(USER_ID)).toBe(false);
    expect(loadEnvelope(USER_ID)).toBeNull();
  });

  test('storage is namespaced per userId', () => {
    saveEnvelope('user-a', new Uint8Array([1]));
    expect(hasEnvelope('user-b')).toBe(false);
  });
});

describe('provision', () => {
  test('produces a blob of exactly the fixed tier size', async () => {
    await provision({ userId: USER_ID, vaultPassword: REAL_PASSWORD, dekBytes: DEK, saltB64: SALT });

    const blob = loadEnvelope(USER_ID);
    expect(blob.byteLength).toBe(tierBytes(TIERS.TIER0_32K));
  });

  test('the real password opens slot 0 with the exact DEK it was given', async () => {
    await provision({ userId: USER_ID, vaultPassword: REAL_PASSWORD, dekBytes: DEK, saltB64: SALT });

    const result = await open({ userId: USER_ID, password: REAL_PASSWORD });
    expect(result.slotIndex).toBe(0);
    expect(result.dekBytes).toEqual(DEK);
    expect(result.saltB64).toBe(SALT);
    expect(result.duressToken).toBeNull();
  });

  test('a no-decoy blob rejects an arbitrary password with WrongPasswordError, not a crash', async () => {
    await provision({ userId: USER_ID, vaultPassword: REAL_PASSWORD, dekBytes: DEK, saltB64: SALT });

    // This is the "no tell" property: slot 1 holds real ciphertext under a
    // throwaway key (see hiddenVaultEnvelope's keyFor), so an unconfigured
    // decoy fails the same way a wrong password against a configured one
    // would -- never a different error class, never a crash.
    await expect(open({ userId: USER_ID, password: 'anything else entirely' }))
      .rejects.toBeInstanceOf(WrongPasswordError);
  });

  test('rejects a dekBytes that is not a 32-byte Uint8Array', async () => {
    await expect(provision({
      userId: USER_ID,
      vaultPassword: REAL_PASSWORD,
      dekBytes: new Uint8Array(16),
      saltB64: SALT,
    })).rejects.toThrow(/32-byte/);
  });
});

describe('setDecoySlot', () => {
  const provisionReal = () =>
    provision({ userId: USER_ID, vaultPassword: REAL_PASSWORD, dekBytes: DEK, saltB64: SALT });

  test('throws if no envelope has been provisioned yet', async () => {
    await expect(setDecoySlot({
      userId: USER_ID,
      vaultPassword: REAL_PASSWORD,
      decoyPassword: DECOY_PASSWORD,
    })).rejects.toThrow(/no envelope/i);
  });

  test('the decoy password opens slot 1 with a fresh DEK and a duress token', async () => {
    await provisionReal();

    const { duressToken } = await setDecoySlot({
      userId: USER_ID,
      vaultPassword: REAL_PASSWORD,
      decoyPassword: DECOY_PASSWORD,
    });

    expect(typeof duressToken).toBe('string');
    expect(duressToken).toHaveLength(44); // base64 of 32 CSPRNG bytes, same shape duressSignalService expects

    const result = await open({ userId: USER_ID, password: DECOY_PASSWORD });
    expect(result.slotIndex).toBe(1);
    expect(result.duressToken).toBe(duressToken);
    expect(result.dekBytes).not.toEqual(DEK);
    expect(result.dekBytes).toHaveLength(32);
  });

  test('preserves the real slot unchanged after adding a decoy', async () => {
    await provisionReal();
    await setDecoySlot({ userId: USER_ID, vaultPassword: REAL_PASSWORD, decoyPassword: DECOY_PASSWORD });

    const real = await open({ userId: USER_ID, password: REAL_PASSWORD });
    expect(real.slotIndex).toBe(0);
    expect(real.dekBytes).toEqual(DEK);
    expect(real.duressToken).toBeNull();
  });

  test('the real slot never carries a duress token', async () => {
    await provisionReal();
    await setDecoySlot({ userId: USER_ID, vaultPassword: REAL_PASSWORD, decoyPassword: DECOY_PASSWORD });

    const real = await open({ userId: USER_ID, password: REAL_PASSWORD });
    expect(real.duressToken).toBeNull();
  });

  test('wrong current vault password is rejected before any re-encode', async () => {
    await provisionReal();

    await expect(setDecoySlot({
      userId: USER_ID,
      vaultPassword: 'not the real password',
      decoyPassword: DECOY_PASSWORD,
    })).rejects.toBeInstanceOf(WrongPasswordError);

    // The blob on disk must be untouched by the rejected attempt.
    const real = await open({ userId: USER_ID, password: REAL_PASSWORD });
    expect(real.dekBytes).toEqual(DEK);
  });

  test('produces a blob of the same fixed tier size as provision()', async () => {
    await provisionReal();
    await setDecoySlot({ userId: USER_ID, vaultPassword: REAL_PASSWORD, decoyPassword: DECOY_PASSWORD });

    expect(loadEnvelope(USER_ID).byteLength).toBe(tierBytes(TIERS.TIER0_32K));
  });
});

describe('open', () => {
  test('throws when no envelope has been provisioned', async () => {
    await expect(open({ userId: USER_ID, password: REAL_PASSWORD }))
      .rejects.toThrow(/no envelope/i);
  });
});

describe('MalformedSlotPayloadError', () => {
  test('is exported and descends from the hiddenVaultEnvelope error hierarchy', async () => {
    const { HiddenVaultError } = await import('../hiddenVaultEnvelope');
    expect(new MalformedSlotPayloadError()).toBeInstanceOf(HiddenVaultError);
  });
});

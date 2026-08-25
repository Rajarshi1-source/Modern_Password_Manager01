/**
 * Regression tests for the decoy-session write gate — CodeRabbit finding on
 * PR #489.
 *
 * `unlockEnvelopeStore.setDecoySlot()` stamps the decoy slot with the SAME
 * device salt as the real slot (there is no reason for the decoy's future
 * items to use a different one, per that file's own comment). But
 * `encryptItem` always stamps NEW items with `sessionSaltB64` — so a new
 * item written during a decoy session would be encrypted under the DECOY
 * DEK while carrying the REAL slot's salt. `keyForSalt`'s matching-salt fast
 * path would later hand the REAL session's DEK to decrypt it (OAuth/envelope
 * sessions never set `sessionPassword`, so there is no salt-based recovery
 * for this — see keyForSalt's own comment), an AES-GCM failure that
 * permanently corrupts a row in the one shared, server-side item list. The
 * fix refuses the write outright while `isDecoySession()` is true.
 *
 * No mocks: real WebCrypto (jsdom) and real localStorage, matching how
 * sessionVaultCrypto.salt.test.js exercises this same module.
 */
import { afterEach, beforeEach, describe, expect, test } from 'vitest';

import {
  installRawDek,
  isDecoySession,
  hasSessionKey,
  clearSessionKey,
  encryptItem,
  decryptItem,
} from '../sessionVaultCrypto';

const USER_ID = 'user-decoy-1';
const SALT = 'ZGV2aWNlLXNhbHQtMTIzNDU2';
const REAL_DEK = new Uint8Array(32).fill(1);
const DECOY_DEK = new Uint8Array(32).fill(2);

beforeEach(() => {
  localStorage.clear();
});

afterEach(() => {
  clearSessionKey();
  localStorage.clear();
});

describe('isDecoySession / installRawDek', () => {
  test('defaults to false for a real-slot install (isDecoy omitted)', async () => {
    await installRawDek(REAL_DEK, SALT, USER_ID);
    expect(hasSessionKey()).toBe(true);
    expect(isDecoySession()).toBe(false);
  });

  test('defaults to false for a real-slot install (isDecoy explicitly false)', async () => {
    await installRawDek(REAL_DEK, SALT, USER_ID, null, false);
    expect(isDecoySession()).toBe(false);
  });

  test('is true for a decoy-slot install', async () => {
    await installRawDek(DECOY_DEK, SALT, USER_ID, null, true);
    expect(hasSessionKey()).toBe(true);
    expect(isDecoySession()).toBe(true);
  });

  test('clearSessionKey resets it back to false', async () => {
    await installRawDek(DECOY_DEK, SALT, USER_ID, null, true);
    expect(isDecoySession()).toBe(true);

    clearSessionKey();

    expect(isDecoySession()).toBe(false);
    expect(hasSessionKey()).toBe(false);
  });

  test('a later real-slot install clears a previous decoy flag', async () => {
    await installRawDek(DECOY_DEK, SALT, USER_ID, null, true);
    expect(isDecoySession()).toBe(true);

    await installRawDek(REAL_DEK, SALT, USER_ID, null, false);

    expect(isDecoySession()).toBe(false);
  });
});

describe('encryptItem refuses to write during a decoy session', () => {
  test('throws for a decoy session, before touching WebCrypto', async () => {
    await installRawDek(DECOY_DEK, SALT, USER_ID, null, true);

    await expect(encryptItem({ title: 'anything' })).rejects.toThrow(/decoy session/i);
  });

  test('a real session (isDecoy false) can still write and read back its own item', async () => {
    await installRawDek(REAL_DEK, SALT, USER_ID, null, false);

    const envelope = await encryptItem({ title: 'gmail', password: 'hunter2' });
    const decrypted = await decryptItem(envelope);

    expect(decrypted).toEqual({ title: 'gmail', password: 'hunter2' });
  });

  test('the decoy DEK cannot decrypt an item written by the real session (proves this is a REAL corruption risk, not just a returned-error inconvenience)', async () => {
    await installRawDek(REAL_DEK, SALT, USER_ID, null, false);
    const envelope = await encryptItem({ secret: 'only the real DEK can read this' });

    clearSessionKey();
    await installRawDek(DECOY_DEK, SALT, USER_ID, null, true);

    // Reading is not gated (only writes are, per the fix's scope) -- and it
    // genuinely fails, confirming the salt collision is real: without the
    // write gate, a decoy-session write would be silently unreadable by the
    // real session in exactly the same way.
    await expect(decryptItem(envelope)).rejects.toThrow();
  });
});

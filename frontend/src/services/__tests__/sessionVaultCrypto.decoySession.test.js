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
  currentSessionGeneration,
  encryptItem,
  decryptItem,
  initSessionKeyFromPassword,
  setupVaultPassword,
  unlockWithVaultPassword,
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

describe('a stale decoy flag does not survive into a session established WITHOUT installRawDek', () => {
  // CodeRabbit nitpick: only installRawDek and clearSessionKey wrote
  // sessionIsDecoy. If a decoy session were replaced by
  // initSessionKeyFromPassword / setupVaultPassword / unlockWithVaultPassword
  // WITHOUT an intervening clearSessionKey(), the flag stayed true and
  // encryptItem refused writes for what is now a genuine real session
  // (fail-closed, but wrongly so). Each of these three now resets the flag
  // itself, next to its own sessionKey assignment.
  test('initSessionKeyFromPassword resets it', async () => {
    await installRawDek(DECOY_DEK, SALT, USER_ID, null, true);
    expect(isDecoySession()).toBe(true);

    await initSessionKeyFromPassword('a real master password', USER_ID);

    expect(isDecoySession()).toBe(false);
    await expect(encryptItem({ title: 'now writable' })).resolves.toBeTruthy();
  });

  test('setupVaultPassword resets it', async () => {
    await installRawDek(DECOY_DEK, SALT, USER_ID, null, true);
    expect(isDecoySession()).toBe(true);

    await setupVaultPassword('a fresh vault password', USER_ID);

    expect(isDecoySession()).toBe(false);
    await expect(encryptItem({ title: 'now writable' })).resolves.toBeTruthy();
  });

  test('unlockWithVaultPassword resets it', async () => {
    // Establish a real wrapped-DEK record to unlock, independent of the
    // decoy state under test below.
    await setupVaultPassword('the-real-vault-password', USER_ID);
    clearSessionKey();

    await installRawDek(DECOY_DEK, SALT, USER_ID, null, true);
    expect(isDecoySession()).toBe(true);

    await unlockWithVaultPassword('the-real-vault-password', USER_ID);

    expect(isDecoySession()).toBe(false);
    await expect(encryptItem({ title: 'now writable' })).resolves.toBeTruthy();
  });
});

describe('encryptItem refuses to write during a decoy session', () => {
  test('throws for a decoy session, before touching WebCrypto', async () => {
    await installRawDek(DECOY_DEK, SALT, USER_ID, null, true);

    // Assert the GATE fired via isDecoySession(), not via the message text --
    // the message is deliberately generic (it reaches the UI, where naming the
    // duress feature would tell a coercer it exists), so matching on
    // /decoy session/i here would pin exactly the wording that must not leak.
    expect(isDecoySession()).toBe(true);
    await expect(encryptItem({ title: 'anything' })).rejects.toThrow();
  });

  test('the refusal message never names the duress feature', async () => {
    await installRawDek(DECOY_DEK, SALT, USER_ID, null, true);

    // Indistinguishability (plan §3.5): this string is surfaced verbatim by
    // VaultContext's `setError(error.message || ...)`, so it must read as an
    // ordinary save failure. A regression that reintroduces "decoy"/"duress"
    // wording is a real information leak, not a cosmetic change.
    await expect(encryptItem({ title: 'anything' })).rejects.toThrow(
      /^Failed to save item\. Please try again\.$/
    );
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

describe('currentSessionGeneration -- the contract every await-window guard depends on', () => {
  // VaultUnlockModal (§36), VaultDuressSetup (§32) and VaultContext's decrypt
  // guard (§34) all decide "is this still the session that authorised me?" by
  // comparing this counter across an await. Each of those tests mocks the
  // accessor, so none of them proves the counter actually MOVES when the
  // session changes. Asserted here against the real module, once.

  test('clearSessionKey advances it -- so a lock invalidates an in-flight operation', async () => {
    await setupVaultPassword('a real vault password', USER_ID);
    const before = currentSessionGeneration();

    clearSessionKey();

    expect(currentSessionGeneration()).toBeGreaterThan(before);
  });

  test('installing a new session advances it -- so a NEWER unlock invalidates an older one', async () => {
    await setupVaultPassword('a real vault password', USER_ID);
    const before = currentSessionGeneration();

    // A decoy unlock is the case that matters most: `hasSessionKey()` answers
    // true again afterwards, so only the counter distinguishes it.
    await installRawDek(new Uint8Array(32).fill(3), SALT, USER_ID, null, true);

    expect(currentSessionGeneration()).toBeGreaterThan(before);
    expect(hasSessionKey()).toBe(true);
  });

  test('reading it does NOT advance it -- it observes, it does not reserve', async () => {
    await setupVaultPassword('a real vault password', USER_ID);

    const first = currentSessionGeneration();
    const second = currentSessionGeneration();

    expect(second).toBe(first);
  });
});

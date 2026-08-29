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
import { WrongPasswordError, TIERS, tierBytes, encode, jsonToBytes } from '../hiddenVaultEnvelope';

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

  test('normalizes an invalid stored base64 blob to MalformedSlotPayloadError, not a raw atob DOMException', () => {
    // hasEnvelope() only checks that a value EXISTS, so a corrupt stored blob
    // still renders VaultDuressSetup's forms -- which then surfaced a literal
    // "Failed to execute 'atob' on 'Window'" string to the user. Same
    // "stored data is corrupt" outcome as parseSlotPayload's dek decode, so
    // it gets the same error type.
    localStorage.setItem(`vaultUnlockEnvelope:${USER_ID}`, 'not!valid!base64!!');

    expect(hasEnvelope(USER_ID)).toBe(true);
    let err;
    try {
      loadEnvelope(USER_ID);
    } catch (e) {
      err = e;
    }
    expect(err).toBeInstanceOf(MalformedSlotPayloadError);
    expect(err.message).not.toMatch(/atob/i);
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

  test.each([
    ['undefined', undefined],
    ['null', null],
    ['a number', 12345],
    ['an empty string', ''],
  ])('rejects %s as saltB64 and writes nothing', async (_label, badSalt) => {
    // JSON.stringify drops an `undefined` value's key entirely, so a missing
    // salt would produce a payload with no `salt` key -- which parseSlotPayload
    // rejects on EVERY later open(), making the envelope permanently dead
    // while the real cause sits far away at provision time. Guarding at entry
    // means a bad envelope is never written in the first place.
    await expect(provision({
      userId: USER_ID,
      vaultPassword: REAL_PASSWORD,
      dekBytes: DEK,
      saltB64: badSalt,
    })).rejects.toThrow(/saltB64/);

    expect(hasEnvelope(USER_ID)).toBe(false);
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

  test('rejects a decoy password equal to the vault password before touching the envelope', async () => {
    await provisionReal();
    const before = loadEnvelope(USER_ID);

    // Regression: deriveSlotKey's domain separation gives slot 0 and slot 1
    // different keys from the SAME password string, so if vaultPassword and
    // decoyPassword were textually equal, decode() would derive both slot
    // keys from that one input and BOTH slots would decrypt -- landing on
    // slot 0 (the real vault) every time, making the "decoy" silently inert.
    await expect(setDecoySlot({
      userId: USER_ID,
      vaultPassword: REAL_PASSWORD,
      decoyPassword: REAL_PASSWORD,
    })).rejects.toThrow(/must differ/i);

    // Rejected before any decode/re-encode -- the stored blob is untouched.
    expect(loadEnvelope(USER_ID)).toEqual(before);
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

  test('rejects the DECOY password in the vaultPassword slot with the SAME error type as a garbage password', async () => {
    // Greptile P1 (§21.1): this used to throw a distinct Error whose message
    // named the slot, which VaultDuressSetup echoed -- so submitting a
    // candidate password to the setup form revealed whether it was the decoy.
    // Both outcomes are now WrongPasswordError, so no caller can tell them
    // apart by type, and the two must stay indistinguishable here.
    await provisionReal();
    await setDecoySlot({ userId: USER_ID, vaultPassword: REAL_PASSWORD, decoyPassword: DECOY_PASSWORD });

    const decoyErr = await setDecoySlot({
      userId: USER_ID, vaultPassword: DECOY_PASSWORD, decoyPassword: 'another decoy 12345',
    }).catch((e) => e);
    const garbageErr = await setDecoySlot({
      userId: USER_ID, vaultPassword: 'not any password at all', decoyPassword: 'another decoy 12345',
    }).catch((e) => e);

    expect(decoyErr).toBeInstanceOf(WrongPasswordError);
    expect(garbageErr).toBeInstanceOf(WrongPasswordError);
    expect(decoyErr.constructor).toBe(garbageErr.constructor);
    // Type parity alone is not enough: a caller that echoes `err.message`
    // would still distinguish them, which is how this leaked originally. The
    // messages must be byte-identical too.
    expect(decoyErr.message).toBe(garbageErr.message);
    // The shared message may say "slot" generically ("No slot decrypted...");
    // what it must never do is identify WHICH slot, or name the decoy.
    expect(decoyErr.message).not.toMatch(/decoy|real slot|slot 0|slot 1/i);

    // And the rejected attempt must not have re-sealed anything.
    const stillReal = await open({ userId: USER_ID, password: REAL_PASSWORD });
    expect(stillReal.slotIndex).toBe(0);
    expect(stillReal.dekBytes).toEqual(DEK);
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

  test('rejects a payload whose dek decodes to the wrong byte length as MalformedSlotPayloadError, not a silent short DEK', async () => {
    // Regression for a CodeRabbit finding on PR #489: parseSlotPayload used
    // to accept ANY base64 string for `dek`, so a valid-base64-but-wrong-
    // length value passed straight through and only failed later, in
    // sessionVaultCrypto.installRawDek -- OUTSIDE the window
    // VaultUnlockModal's runEnvelopeUnlock tags `envelopeUnusable` on. That
    // skipped the legacy wrapped-DEK fallback entirely. Hand-crafts the
    // malformed payload directly with encode()/jsonToBytes() (bypassing
    // provision()'s own dekBytes-length guard on purpose, since the point is
    // to prove parseSlotPayload itself now catches what a well-behaved
    // caller never would).
    const shortDekB64 = btoa(String.fromCharCode(...new Uint8Array(16).fill(9)));
    const malformedPayload = jsonToBytes({ v: 'hv-slot-1', dek: shortDekB64, salt: SALT });
    const blob = await encode({
      realPassword: REAL_PASSWORD,
      realPayload: malformedPayload,
      decoyPassword: null,
      decoyPayload: new Uint8Array(0),
      tier: TIERS.TIER0_32K,
    });
    saveEnvelope(USER_ID, blob);

    await expect(open({ userId: USER_ID, password: REAL_PASSWORD }))
      .rejects.toBeInstanceOf(MalformedSlotPayloadError);
  });

  test('rejects a dek that is not valid base64 as MalformedSlotPayloadError, not a raw atob DOMException', async () => {
    // `fromB64` calls atob(), which throws InvalidCharacterError (a
    // DOMException) rather than this module's own error type. That left two
    // different error contracts for the same "stored payload is corrupt"
    // outcome -- and VaultDuressSetup's recovery form surfaces `err.message`
    // directly, so the user would have seen a raw "Failed to execute 'atob'"
    // string. Normalized in parseSlotPayload so open() has ONE contract.
    const malformedPayload = jsonToBytes({
      v: 'hv-slot-1',
      dek: 'not!valid!base64!!',
      salt: SALT,
    });
    const blob = await encode({
      realPassword: REAL_PASSWORD,
      realPayload: malformedPayload,
      decoyPassword: null,
      decoyPayload: new Uint8Array(0),
      tier: TIERS.TIER0_32K,
    });
    saveEnvelope(USER_ID, blob);

    const err = await open({ userId: USER_ID, password: REAL_PASSWORD }).catch((e) => e);
    expect(err).toBeInstanceOf(MalformedSlotPayloadError);
    // The raw browser message must not reach a caller that surfaces it.
    expect(err.message).not.toMatch(/atob/i);
  });

  describe('__duress_signal validation', () => {
    // A decoy slot's token is sent VERBATIM as the request body
    // (duressSignalService.reportUnlock -> JSON.stringify({ signal })), and
    // the indistinguishability contract requires that body to be the same
    // size for a real token as for noise. A present-but-wrong-length token
    // would change the byte length on the wire -- the exact oracle the
    // feature denies -- so it must be rejected inside open()'s call stack,
    // where VaultUnlockModal's `envelopeUnusable` fallback catches it.
    const sealPayloadWithDuress = async (duressValue) => {
      const dekB64 = btoa(String.fromCharCode(...DEK));
      const payloadObj = { v: 'hv-slot-1', dek: dekB64, salt: SALT };
      if (duressValue !== undefined) payloadObj.__duress_signal = duressValue;
      const blob = await encode({
        realPassword: REAL_PASSWORD,
        realPayload: jsonToBytes(payloadObj),
        decoyPassword: null,
        decoyPayload: new Uint8Array(0),
        tier: TIERS.TIER0_32K,
      });
      saveEnvelope(USER_ID, blob);
    };

    test.each([
      ['too short', 'abc'],
      ['too long', 'a'.repeat(45)],
      ['a number', 12345],
      ['an object', { token: 'x' }],
      ['an empty string', ''],
    ])('rejects a %s duress signal as MalformedSlotPayloadError', async (_label, value) => {
      await sealPayloadWithDuress(value);

      await expect(open({ userId: USER_ID, password: REAL_PASSWORD }))
        .rejects.toBeInstanceOf(MalformedSlotPayloadError);
    });

    test('a MISSING duress signal is not an error -- it yields null so noise is sent at the correct length', async () => {
      // Deliberately NOT rejected: absent means "no alarm configured for this
      // slot", reportUnlock then generates full-length noise, so there is no
      // wire tell. Throwing here would make a decoy password unusable under
      // duress over a payload that leaks nothing.
      await sealPayloadWithDuress(undefined);

      const result = await open({ userId: USER_ID, password: REAL_PASSWORD });
      expect(result.duressToken).toBeNull();
    });

    test('a well-formed 44-char duress signal passes through unchanged', async () => {
      const token = 'a'.repeat(44);
      await sealPayloadWithDuress(token);

      const result = await open({ userId: USER_ID, password: REAL_PASSWORD });
      expect(result.duressToken).toBe(token);
    });
  });
});

describe('MalformedSlotPayloadError', () => {
  test('is exported and descends from the hiddenVaultEnvelope error hierarchy', async () => {
    const { HiddenVaultError } = await import('../hiddenVaultEnvelope');
    expect(new MalformedSlotPayloadError()).toBeInstanceOf(HiddenVaultError);
  });
});

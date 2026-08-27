/**
 * Round-trip regression test for the shared unwrap helper extracted from
 * `unlockWithVaultPassword` and `exportWrappedDekRaw` (CodeRabbit nitpick on
 * PR #489 — the two functions duplicated record-load/KEK-derive/unwrap logic
 * that a self-documented comment already flagged as a "keep these two in
 * sync by hand" risk).
 *
 * The two functions now share `_unwrapDek` for the KEK-derive-and-unwrap
 * step, differing only in the `extractable` flag each passes. This proves
 * that refactor didn't change either function's observable behavior: both
 * still recover the SAME DEK from the SAME wrapped record, and both still
 * throw the identical "Incorrect vault password." message on a wrong
 * password.
 *
 * No mocks: real WebCrypto (jsdom) and real localStorage, matching how
 * sessionVaultCrypto.decoySession.test.js exercises this same module.
 */
import { afterEach, beforeEach, describe, expect, test } from 'vitest';

import {
  setupVaultPassword,
  unlockWithVaultPassword,
  exportWrappedDekRaw,
  exportSessionDekRaw,
  hasSessionKey,
  clearSessionKey,
} from '../sessionVaultCrypto';

const USER_ID = 'user-export-raw-1';
const REAL_PASSWORD = 'the-real-vault-password';

beforeEach(() => {
  localStorage.clear();
});

afterEach(() => {
  clearSessionKey();
  localStorage.clear();
});

describe('exportWrappedDekRaw shares its unwrap step with unlockWithVaultPassword', () => {
  test('recovers the exact same DEK bytes that setupVaultPassword originally generated', async () => {
    await setupVaultPassword(REAL_PASSWORD, USER_ID);
    // setupVaultPassword's own fresh DEK is extractable (it must be, to seed
    // the hidden-vault envelope) -- unlockWithVaultPassword's is deliberately
    // NOT (see that function's own docstring), so the ground truth to compare
    // exportWrappedDekRaw against comes from here, not from re-exporting
    // after a later unlockWithVaultPassword call.
    const originalDek = await exportSessionDekRaw();
    clearSessionKey();

    const { dekBytes, saltB64 } = await exportWrappedDekRaw(REAL_PASSWORD, USER_ID);
    expect(dekBytes).toEqual(new Uint8Array(originalDek));
    expect(typeof saltB64).toBe('string');

    // unlockWithVaultPassword, called separately against the identical
    // record via the SAME shared unwrapDek helper, must also succeed --
    // proving the extractable:false path the refactor touched still works.
    await expect(unlockWithVaultPassword(REAL_PASSWORD, USER_ID)).resolves.toBeUndefined();
    expect(hasSessionKey()).toBe(true);
  });

  test('both functions reject a wrong password with the identical message', async () => {
    await setupVaultPassword(REAL_PASSWORD, USER_ID);
    clearSessionKey();

    await expect(exportWrappedDekRaw('wrong-password', USER_ID)).rejects.toThrow(
      'Incorrect vault password.'
    );
    await expect(unlockWithVaultPassword('wrong-password', USER_ID)).rejects.toThrow(
      'Incorrect vault password.'
    );
  });

  test('exportWrappedDekRaw does not touch session state', async () => {
    await setupVaultPassword(REAL_PASSWORD, USER_ID);
    clearSessionKey();

    await exportWrappedDekRaw(REAL_PASSWORD, USER_ID);

    // No session was installed by the export call -- confirmed by the fact
    // that exportSessionDekRaw (which reads the live session key) throws
    // rather than returning the exported bytes.
    await expect(exportSessionDekRaw()).rejects.toThrow();
  });
});

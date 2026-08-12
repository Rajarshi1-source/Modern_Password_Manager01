/**
 * Unit tests for `classifyV3UnlockError` — the decision logic behind
 * App.jsx's post-login handling of a `sessionVaultCryptoV3.
 * unlockWithMasterPassword` rejection.
 *
 * Before this classifier existed, EVERY rejection other than `NOT_ENROLLED`
 * fell into a bare `console.warn` — including a genuine desync between the
 * account password and the vault's wrapped key (`login()` above already
 * verified the password server-side, so this is not a typo), which silently
 * neutered the one real crypto gate the app has for v3-enrolled users. These
 * tests are the regression coverage for that: a desync must classify as
 * `'desync'`, not fall through to `'transient'` the way it used to.
 *
 * Deliberately NOT a full App.jsx render test: that component pulls in
 * PQC/FHE/blockchain/biometric providers unrelated to this classification,
 * so the logic was extracted into its own pure function specifically to
 * keep this coverage cheap and focused.
 */
import { describe, it, expect } from 'vitest';
import {
  classifyV3UnlockError,
  V3_UNLOCK_NOT_ENROLLED,
  V3_UNLOCK_DESYNC,
  V3_UNLOCK_TRANSIENT,
} from '../vaultV3UnlockClassifier';
import { DEK_UNWRAP_FAILURE_MESSAGE } from '../sessionVaultCryptoV3';

describe('classifyV3UnlockError', () => {
  it('classifies NOT_ENROLLED as not_enrolled', () => {
    expect(classifyV3UnlockError(new Error('NOT_ENROLLED'))).toBe(
      V3_UNLOCK_NOT_ENROLLED,
    );
  });

  it('classifies the real unwrapDEK failure message as desync', () => {
    // Reads the message from the crypto module's own export rather than a
    // hardcoded string, so this test breaks (not silently drifts) if the two
    // ever disagree.
    expect(classifyV3UnlockError(new Error(DEK_UNWRAP_FAILURE_MESSAGE))).toBe(
      V3_UNLOCK_DESYNC,
    );
  });

  it('classifies a network/5xx-shaped error as transient, not desync', () => {
    // The failure mode this distinction exists to prevent: a transient fetch
    // failure must NOT alarm the user the same way a genuine password/vault
    // desync does, since it self-heals on the next login.
    const networkError = new Error('Network Error');
    networkError.response = { status: 503 };
    expect(classifyV3UnlockError(networkError)).toBe(V3_UNLOCK_TRANSIENT);
  });

  it('classifies an unrelated Error as transient', () => {
    expect(classifyV3UnlockError(new Error('boom'))).toBe(V3_UNLOCK_TRANSIENT);
  });

  it('classifies a non-Error rejection as transient without throwing', () => {
    // Promise rejections are not guaranteed to be Error instances.
    expect(classifyV3UnlockError(undefined)).toBe(V3_UNLOCK_TRANSIENT);
    expect(classifyV3UnlockError(null)).toBe(V3_UNLOCK_TRANSIENT);
    expect(classifyV3UnlockError('a bare string rejection')).toBe(
      V3_UNLOCK_TRANSIENT,
    );
    expect(classifyV3UnlockError({})).toBe(V3_UNLOCK_TRANSIENT);
  });

  it('is not fooled by a message that merely CONTAINS the desync text', () => {
    // Exact match, not substring: a wrapped/rethrown error with extra
    // context should not be silently reclassified as the specific desync
    // case if it isn't actually that error.
    const wrapped = new Error(`Context: ${DEK_UNWRAP_FAILURE_MESSAGE} (retry 2)`);
    expect(classifyV3UnlockError(wrapped)).toBe(V3_UNLOCK_TRANSIENT);
  });
});

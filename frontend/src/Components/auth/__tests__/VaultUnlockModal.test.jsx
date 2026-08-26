/**
 * Unit tests for VaultUnlockModal's three internal unlock paths —
 * docs/vault-unlock-envelope-integration-plan.md §4 "Component" tests.
 *
 * Every dependency the component talks to is mocked so these assert wiring
 * and the indistinguishability contract, not the underlying crypto (that is
 * unlockEnvelopeStore.test.js's job).
 */
import React from 'react';
import { render, fireEvent, waitFor, cleanup } from '@testing-library/react';
import '@testing-library/jest-dom';
import { afterEach, beforeEach, describe, expect, test, vi } from 'vitest';

// hiddenVaultEnvelope.js imports argon2-browser at module scope; mock it so
// merely importing WrongPasswordError from it doesn't touch the WASM loader
// under jsdom (same reasoning as unlockEnvelopeStore.test.js).
vi.mock('argon2-browser', () => {
  const ArgonType = { Argon2id: 2 };
  const hash = vi.fn();
  return { ArgonType, hash, default: { ArgonType, hash } };
});

vi.mock('../../../services/sessionVaultCrypto', () => ({
  default: {
    hasWrappedKey: vi.fn(),
    setupVaultPassword: vi.fn(),
    unlockWithVaultPassword: vi.fn(),
    exportSessionDekRaw: vi.fn(),
    exportWrappedDekRaw: vi.fn(),
    reserveSessionGeneration: vi.fn(() => 1),
    installRawDek: vi.fn(),
    getOrCreateUserSalt: vi.fn(() => 'device-salt-b64'),
  },
}));

vi.mock('../../../services/hiddenVault/unlockEnvelopeStore', () => ({
  hasEnvelope: vi.fn(),
  open: vi.fn(),
  provision: vi.fn(),
}));

vi.mock('../../../services/duressSignalService', () => ({
  reportUnlock: vi.fn(),
  reportUnlockForSlot: vi.fn(),
}));

import VaultUnlockModal from '../VaultUnlockModal';
import sessionVaultCrypto from '../../../services/sessionVaultCrypto';
import * as unlockEnvelopeStore from '../../../services/hiddenVault/unlockEnvelopeStore';
import { reportUnlock, reportUnlockForSlot } from '../../../services/duressSignalService';
import { WrongPasswordError, MalformedBlobError } from '../../../services/hiddenVault/hiddenVaultEnvelope';

const USER_ID = 'user-1';
const TOKEN = 'jwt-token';
const getAccessToken = () => TOKEN;

const DEK = new Uint8Array(32).fill(7);

const renderModal = (props = {}) =>
  render(
    <VaultUnlockModal
      isOpen
      userId={USER_ID}
      getAccessToken={getAccessToken}
      onUnlocked={vi.fn()}
      onClose={vi.fn()}
      {...props}
    />
  );

const submitPassword = async (getByLabelText, getByRole, password, confirm = null) => {
  fireEvent.change(getByLabelText(/vault password/i, { selector: '#vault-password' }), {
    target: { value: password },
  });
  if (confirm !== null) {
    fireEvent.change(getByLabelText(/confirm vault password/i), { target: { value: confirm } });
  }
  fireEvent.click(getByRole('button', { name: /unlock|create vault password/i }));
};

beforeEach(() => {
  vi.clearAllMocks();
  sessionVaultCrypto.getOrCreateUserSalt.mockReturnValue('device-salt-b64');
});

afterEach(() => {
  cleanup();
});

describe('setup mode (no wrapped key, no envelope)', () => {
  beforeEach(() => {
    sessionVaultCrypto.hasWrappedKey.mockReturnValue(false);
    unlockEnvelopeStore.hasEnvelope.mockReturnValue(false);
  });

  test('creates the legacy record, provisions the envelope with the same DEK, and reports noise', async () => {
    sessionVaultCrypto.setupVaultPassword.mockResolvedValue(undefined);
    sessionVaultCrypto.exportSessionDekRaw.mockResolvedValue(DEK);
    unlockEnvelopeStore.provision.mockResolvedValue(undefined);
    const onUnlocked = vi.fn();

    const { getByLabelText, getByRole } = renderModal({ onUnlocked });
    await submitPassword(getByLabelText, getByRole, 'a very long vault password', 'a very long vault password');

    await waitFor(() => expect(onUnlocked).toHaveBeenCalled());

    expect(sessionVaultCrypto.setupVaultPassword).toHaveBeenCalledWith('a very long vault password', USER_ID);
    expect(unlockEnvelopeStore.provision).toHaveBeenCalledWith({
      userId: USER_ID,
      vaultPassword: 'a very long vault password',
      dekBytes: DEK,
      saltB64: 'device-salt-b64',
    });
    expect(reportUnlock).toHaveBeenCalledWith(TOKEN, null);
  });

  test('a failed envelope provisioning during setup does not block onUnlocked', async () => {
    sessionVaultCrypto.setupVaultPassword.mockResolvedValue(undefined);
    sessionVaultCrypto.exportSessionDekRaw.mockResolvedValue(DEK);
    unlockEnvelopeStore.provision.mockRejectedValue(new Error('disk full'));
    vi.spyOn(console, 'warn').mockImplementation(() => {});
    const onUnlocked = vi.fn();

    const { getByLabelText, getByRole } = renderModal({ onUnlocked });
    await submitPassword(getByLabelText, getByRole, 'a very long vault password', 'a very long vault password');

    await waitFor(() => expect(onUnlocked).toHaveBeenCalled());
    expect(reportUnlock).toHaveBeenCalledWith(TOKEN, null);
  });
});

describe('unlock mode — envelope already provisioned', () => {
  beforeEach(() => {
    unlockEnvelopeStore.hasEnvelope.mockReturnValue(true);
    sessionVaultCrypto.hasWrappedKey.mockReturnValue(true); // irrelevant once an envelope exists
  });

  test('slot 0 (real) installs the DEK and reports with slotIndex 0', async () => {
    unlockEnvelopeStore.open.mockResolvedValue({ slotIndex: 0, dekBytes: DEK, saltB64: 'salt-x', duressToken: null });
    const onUnlocked = vi.fn();

    const { getByLabelText, getByRole } = renderModal({ onUnlocked });
    await submitPassword(getByLabelText, getByRole, 'real-password');

    await waitFor(() => expect(onUnlocked).toHaveBeenCalled());
    expect(sessionVaultCrypto.installRawDek).toHaveBeenCalledWith(DEK, 'salt-x', USER_ID, 1, false);
    expect(reportUnlockForSlot).toHaveBeenCalledWith(TOKEN, 0, { __duress_signal: null });
    expect(sessionVaultCrypto.unlockWithVaultPassword).not.toHaveBeenCalled();
  });

  test('slot 1 (decoy) installs the decoy DEK, reports with slotIndex 1 and the real token, and marks the session as decoy', async () => {
    const decoyDek = new Uint8Array(32).fill(9);
    unlockEnvelopeStore.open.mockResolvedValue({
      slotIndex: 1,
      dekBytes: decoyDek,
      saltB64: 'salt-x',
      duressToken: 'the-real-duress-token',
    });
    const onUnlocked = vi.fn();

    const { getByLabelText, getByRole } = renderModal({ onUnlocked });
    await submitPassword(getByLabelText, getByRole, 'decoy-password');

    await waitFor(() => expect(onUnlocked).toHaveBeenCalled());
    expect(reportUnlockForSlot).toHaveBeenCalledWith(TOKEN, 1, { __duress_signal: 'the-real-duress-token' });
    // isDecoy=true is the flag sessionVaultCrypto uses to refuse writes for
    // this session (see sessionVaultCrypto.js's encryptItem) -- this is the
    // regression guard that it is actually threaded through from slotIndex.
    expect(sessionVaultCrypto.installRawDek).toHaveBeenCalledWith(decoyDek, 'salt-x', USER_ID, 1, true);
  });

  test('a wrong password surfaces the identical string regardless of the underlying error', async () => {
    unlockEnvelopeStore.open.mockRejectedValue(new WrongPasswordError('slot decode detail the UI must never show'));
    const onUnlocked = vi.fn();

    const { getByLabelText, getByRole, findByRole } = renderModal({ onUnlocked });
    await submitPassword(getByLabelText, getByRole, 'wrong-password');

    const alert = await findByRole('alert');
    expect(alert).toHaveTextContent('Incorrect vault password.');
    expect(onUnlocked).not.toHaveBeenCalled();
  });

  test('indistinguishability: rendered output and console output after a slot-0 and a slot-1 unlock are both identical', async () => {
    // Scope note (CodeRabbit, round 6): this test proves DOM equality and
    // log-output equality for VaultUnlockModal itself -- it does NOT prove
    // "same endpoint" or "same request byte length", since
    // reportUnlockForSlot is mocked here rather than making a real network
    // call. Those two guarantees are duressSignalService's own contract,
    // verified in duressSignalService.test.js (the fixed-length token/noise
    // assertions and the single hardcoded endpoint URL) -- see §5's
    // acceptance criterion for the precise split.
    const logSpyA = vi.spyOn(console, 'log').mockImplementation(() => {});
    const warnSpyA = vi.spyOn(console, 'warn').mockImplementation(() => {});
    const errorSpyA = vi.spyOn(console, 'error').mockImplementation(() => {});

    unlockEnvelopeStore.open.mockResolvedValueOnce({ slotIndex: 0, dekBytes: DEK, saltB64: 's', duressToken: null });
    const runA = renderModal({ onUnlocked: vi.fn() });
    await submitPassword(runA.getByLabelText, runA.getByRole, 'whatever-1');
    await waitFor(() => expect(sessionVaultCrypto.installRawDek).toHaveBeenCalledTimes(1));
    const htmlAfterReal = runA.container.innerHTML;
    const consoleCallsAfterReal = [...logSpyA.mock.calls, ...warnSpyA.mock.calls, ...errorSpyA.mock.calls];
    runA.unmount();
    vi.restoreAllMocks();

    const logSpyB = vi.spyOn(console, 'log').mockImplementation(() => {});
    const warnSpyB = vi.spyOn(console, 'warn').mockImplementation(() => {});
    const errorSpyB = vi.spyOn(console, 'error').mockImplementation(() => {});

    unlockEnvelopeStore.open.mockResolvedValueOnce({ slotIndex: 1, dekBytes: DEK, saltB64: 's', duressToken: 'tok' });
    const runB = renderModal({ onUnlocked: vi.fn() });
    await submitPassword(runB.getByLabelText, runB.getByRole, 'whatever-2');
    await waitFor(() => expect(sessionVaultCrypto.installRawDek).toHaveBeenCalledTimes(2));
    const htmlAfterDecoy = runB.container.innerHTML;
    const consoleCallsAfterDecoy = [...logSpyB.mock.calls, ...warnSpyB.mock.calls, ...errorSpyB.mock.calls];
    runB.unmount();

    expect(htmlAfterDecoy).toBe(htmlAfterReal);
    // Neither slot logs anything at all on a successful unlock -- and
    // critically, neither logs a DIFFERENT amount than the other, which is
    // the actual indistinguishability property (a slot-conditional debug
    // log would be exactly the kind of tell this asserts against).
    expect(consoleCallsAfterDecoy).toEqual(consoleCallsAfterReal);
  });
});

describe('unlock mode — stored envelope is unusable, falls back to the legacy path', () => {
  // Regression coverage for a CodeRabbit finding on PR #489: hasEnvelope()
  // only checks that localStorage HAS a value, not that it decodes. A
  // corrupt/truncated value previously selected internalMode: 'envelope' and
  // surfaced the raw decode error with no way back in, even though the
  // legacy wrapped-DEK record was perfectly usable.
  beforeEach(() => {
    unlockEnvelopeStore.hasEnvelope.mockReturnValue(true);
    sessionVaultCrypto.hasWrappedKey.mockReturnValue(true);
    sessionVaultCrypto.unlockWithVaultPassword.mockResolvedValue(undefined);
    sessionVaultCrypto.exportWrappedDekRaw.mockResolvedValue({ dekBytes: DEK, saltB64: 'legacy-salt' });
    unlockEnvelopeStore.provision.mockResolvedValue(undefined);
  });

  test('invalid base64 in the stored envelope falls back to the wrapped-DEK record', async () => {
    // Mirrors what atob() actually throws for a non-base64 string -- a
    // native DOMException, not a WrongPasswordError.
    unlockEnvelopeStore.open.mockRejectedValue(new DOMException('bad base64', 'InvalidCharacterError'));
    vi.spyOn(console, 'warn').mockImplementation(() => {});
    const onUnlocked = vi.fn();

    const { getByLabelText, getByRole } = renderModal({ onUnlocked });
    await submitPassword(getByLabelText, getByRole, 'legacy-password');

    await waitFor(() => expect(onUnlocked).toHaveBeenCalled());
    expect(sessionVaultCrypto.unlockWithVaultPassword).toHaveBeenCalledWith('legacy-password', USER_ID);
  });

  test('a structurally corrupt (MalformedBlobError) envelope falls back to the wrapped-DEK record', async () => {
    unlockEnvelopeStore.open.mockRejectedValue(new MalformedBlobError('bad magic'));
    vi.spyOn(console, 'warn').mockImplementation(() => {});
    const onUnlocked = vi.fn();

    const { getByLabelText, getByRole } = renderModal({ onUnlocked });
    await submitPassword(getByLabelText, getByRole, 'legacy-password');

    await waitFor(() => expect(onUnlocked).toHaveBeenCalled());
    expect(sessionVaultCrypto.unlockWithVaultPassword).toHaveBeenCalledWith('legacy-password', USER_ID);
    // The fallback also re-provisions a fresh envelope, self-healing the
    // corruption rather than leaving the bad blob in place for next time.
    expect(unlockEnvelopeStore.provision).toHaveBeenCalled();
  });

  test('a genuine wrong password does NOT fall back -- it is a normal retry', async () => {
    unlockEnvelopeStore.open.mockRejectedValue(new WrongPasswordError('no slot matched'));
    const onUnlocked = vi.fn();

    const { getByLabelText, getByRole, findByRole } = renderModal({ onUnlocked });
    await submitPassword(getByLabelText, getByRole, 'wrong-password');

    const alert = await findByRole('alert');
    expect(alert).toHaveTextContent('Incorrect vault password.');
    expect(onUnlocked).not.toHaveBeenCalled();
    expect(sessionVaultCrypto.unlockWithVaultPassword).not.toHaveBeenCalled();
  });

  test('with no wrapped key to fall back to, the original envelope error surfaces', async () => {
    sessionVaultCrypto.hasWrappedKey.mockReturnValue(false);
    unlockEnvelopeStore.open.mockRejectedValue(new MalformedBlobError('bad magic'));
    const onUnlocked = vi.fn();

    const { getByLabelText, getByRole, findByRole } = renderModal({ onUnlocked });
    await submitPassword(getByLabelText, getByRole, 'whatever');

    const alert = await findByRole('alert');
    expect(alert).toHaveTextContent('bad magic');
    expect(onUnlocked).not.toHaveBeenCalled();
    expect(sessionVaultCrypto.unlockWithVaultPassword).not.toHaveBeenCalled();
  });
});

describe('unlock mode — the session changes while open() is pending', () => {
  // Regression coverage for a CodeRabbit finding on PR #489:
  // unlockEnvelopeStore.open() runs two Argon2id derivations before
  // resolving; if a logout or a newer unlock lands during that window,
  // installRawDek must detect it (via the generation token
  // reserveSessionGeneration() captured BEFORE open() started) and refuse
  // to install a DEK for a session nobody is in anymore -- and that refusal
  // must propagate as-is, never get misread as "the envelope is corrupt"
  // and trigger the legacy fallback.
  beforeEach(() => {
    unlockEnvelopeStore.hasEnvelope.mockReturnValue(true);
    sessionVaultCrypto.hasWrappedKey.mockReturnValue(true);
  });

  test('a session superseded during open() propagates without falling back to the legacy path', async () => {
    unlockEnvelopeStore.open.mockResolvedValue({ slotIndex: 0, dekBytes: DEK, saltB64: 'salt-x', duressToken: null });
    // Simulates installRawDek's own stale-generation guard rejecting because
    // something else (a logout, a newer unlock) already moved the session
    // on by the time this call ran -- exactly the race reserveSessionGeneration
    // exists to catch, verified at the wiring level here since the counter's
    // own correctness is sessionVaultCrypto.salt.test.js's job.
    sessionVaultCrypto.installRawDek.mockRejectedValue(
      new Error('Vault session initialization was superseded by a newer request.')
    );
    const onUnlocked = vi.fn();

    const { getByLabelText, getByRole, findByRole } = renderModal({ onUnlocked });
    await submitPassword(getByLabelText, getByRole, 'real-password');

    const alert = await findByRole('alert');
    expect(alert).toHaveTextContent('superseded by a newer request');
    expect(onUnlocked).not.toHaveBeenCalled();
    // The critical assertion: this must NOT be treated as a corrupt
    // envelope. Falling back here would install a SECOND, equally stale
    // session on top of the first instead of correctly abandoning the
    // attempt.
    expect(sessionVaultCrypto.unlockWithVaultPassword).not.toHaveBeenCalled();
    expect(reportUnlockForSlot).not.toHaveBeenCalled();
  });

  test('reserves the generation token before calling open(), not after', async () => {
    const callOrder = [];
    sessionVaultCrypto.reserveSessionGeneration.mockImplementation(() => {
      callOrder.push('reserve');
      return 7;
    });
    unlockEnvelopeStore.open.mockImplementation(async () => {
      callOrder.push('open');
      return { slotIndex: 0, dekBytes: DEK, saltB64: 'salt-x', duressToken: null };
    });

    const { getByLabelText, getByRole } = renderModal({ onUnlocked: vi.fn() });
    await submitPassword(getByLabelText, getByRole, 'real-password');

    await waitFor(() => expect(sessionVaultCrypto.installRawDek).toHaveBeenCalled());
    expect(callOrder).toEqual(['reserve', 'open']);
    expect(sessionVaultCrypto.installRawDek).toHaveBeenCalledWith(DEK, 'salt-x', USER_ID, 7, false);
  });
});

describe('unlock mode — upgrade (wrapped key exists, no envelope yet)', () => {
  beforeEach(() => {
    unlockEnvelopeStore.hasEnvelope.mockReturnValue(false);
    sessionVaultCrypto.hasWrappedKey.mockReturnValue(true);
  });

  test('unlocks via the legacy path and transparently provisions an envelope with the same DEK', async () => {
    sessionVaultCrypto.unlockWithVaultPassword.mockResolvedValue(undefined);
    sessionVaultCrypto.exportWrappedDekRaw.mockResolvedValue({ dekBytes: DEK, saltB64: 'legacy-salt' });
    unlockEnvelopeStore.provision.mockResolvedValue(undefined);
    const onUnlocked = vi.fn();

    const { getByLabelText, getByRole } = renderModal({ onUnlocked });
    await submitPassword(getByLabelText, getByRole, 'legacy-password');

    await waitFor(() => expect(onUnlocked).toHaveBeenCalled());
    expect(sessionVaultCrypto.unlockWithVaultPassword).toHaveBeenCalledWith('legacy-password', USER_ID);
    expect(sessionVaultCrypto.exportWrappedDekRaw).toHaveBeenCalledWith('legacy-password', USER_ID);
    expect(unlockEnvelopeStore.provision).toHaveBeenCalledWith({
      userId: USER_ID,
      vaultPassword: 'legacy-password',
      dekBytes: DEK,
      saltB64: 'legacy-salt',
    });
    expect(reportUnlock).toHaveBeenCalledWith(TOKEN, null);
    // The upgrade path installs the session key via unlockWithVaultPassword
    // itself; installRawDek is the ENVELOPE path's mechanism and must not
    // also fire here.
    expect(sessionVaultCrypto.installRawDek).not.toHaveBeenCalled();
  });

  test('a failed upgrade does not fail the unlock', async () => {
    sessionVaultCrypto.unlockWithVaultPassword.mockResolvedValue(undefined);
    sessionVaultCrypto.exportWrappedDekRaw.mockRejectedValue(new Error('unwrap failed'));
    vi.spyOn(console, 'warn').mockImplementation(() => {});
    const onUnlocked = vi.fn();

    const { getByLabelText, getByRole } = renderModal({ onUnlocked });
    await submitPassword(getByLabelText, getByRole, 'legacy-password');

    await waitFor(() => expect(onUnlocked).toHaveBeenCalled());
    expect(unlockEnvelopeStore.provision).not.toHaveBeenCalled();
    expect(reportUnlock).toHaveBeenCalledWith(TOKEN, null);
  });

  test('a wrong password surfaces the identical string as the envelope path', async () => {
    sessionVaultCrypto.unlockWithVaultPassword.mockRejectedValue(new Error('Incorrect vault password.'));
    const onUnlocked = vi.fn();

    const { getByLabelText, getByRole, findByRole } = renderModal({ onUnlocked });
    await submitPassword(getByLabelText, getByRole, 'wrong-password');

    const alert = await findByRole('alert');
    expect(alert).toHaveTextContent('Incorrect vault password.');
    expect(onUnlocked).not.toHaveBeenCalled();
    expect(unlockEnvelopeStore.provision).not.toHaveBeenCalled();
  });
});

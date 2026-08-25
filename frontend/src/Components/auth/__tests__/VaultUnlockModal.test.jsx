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
import { WrongPasswordError } from '../../../services/hiddenVault/hiddenVaultEnvelope';

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
    expect(sessionVaultCrypto.installRawDek).toHaveBeenCalledWith(DEK, 'salt-x', USER_ID);
    expect(reportUnlockForSlot).toHaveBeenCalledWith(TOKEN, 0, { __duress_signal: null });
    expect(sessionVaultCrypto.unlockWithVaultPassword).not.toHaveBeenCalled();
  });

  test('slot 1 (decoy) installs the decoy DEK and reports with slotIndex 1 and the real token', async () => {
    unlockEnvelopeStore.open.mockResolvedValue({
      slotIndex: 1,
      dekBytes: new Uint8Array(32).fill(9),
      saltB64: 'salt-x',
      duressToken: 'the-real-duress-token',
    });
    const onUnlocked = vi.fn();

    const { getByLabelText, getByRole } = renderModal({ onUnlocked });
    await submitPassword(getByLabelText, getByRole, 'decoy-password');

    await waitFor(() => expect(onUnlocked).toHaveBeenCalled());
    expect(reportUnlockForSlot).toHaveBeenCalledWith(TOKEN, 1, { __duress_signal: 'the-real-duress-token' });
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

  test('indistinguishability: rendered output after a slot-0 and a slot-1 unlock is identical', async () => {
    unlockEnvelopeStore.open.mockResolvedValueOnce({ slotIndex: 0, dekBytes: DEK, saltB64: 's', duressToken: null });
    const runA = renderModal({ onUnlocked: vi.fn() });
    await submitPassword(runA.getByLabelText, runA.getByRole, 'whatever-1');
    await waitFor(() => expect(sessionVaultCrypto.installRawDek).toHaveBeenCalledTimes(1));
    const htmlAfterReal = runA.container.innerHTML;
    runA.unmount();

    unlockEnvelopeStore.open.mockResolvedValueOnce({ slotIndex: 1, dekBytes: DEK, saltB64: 's', duressToken: 'tok' });
    const runB = renderModal({ onUnlocked: vi.fn() });
    await submitPassword(runB.getByLabelText, runB.getByRole, 'whatever-2');
    await waitFor(() => expect(sessionVaultCrypto.installRawDek).toHaveBeenCalledTimes(2));
    const htmlAfterDecoy = runB.container.innerHTML;
    runB.unmount();

    expect(htmlAfterDecoy).toBe(htmlAfterReal);
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

/**
 * Targeted regression tests for VaultDuressSetup's alarm-registration recovery.
 *
 * setDecoySlot() persists the new decoy envelope BEFORE registerSignalToken()
 * runs (correct ordering, per the #486 §10.3 lesson) -- but if registration
 * then fails, the decoy password is already live while its alarm is not
 * registered anywhere. The original fix (round 2 on PR #489) held the failed
 * token in React state for an in-session "Finish registration" retry --
 * CodeRabbit's round-4 review correctly flagged that state as lost on any
 * remount (reload, navigation), leaving no way back in without reconfiguring
 * the decoy slot from scratch. The current design instead re-derives the
 * token on demand via a standing "Recover unregistered alarm" form that
 * re-opens the existing envelope with the decoy password -- the token is
 * never held in state or storage, so recovery works regardless of how much
 * time or how many remounts have passed.
 */
import React from 'react';
import { render, fireEvent, waitFor, cleanup } from '@testing-library/react';
import '@testing-library/jest-dom';
import { afterEach, beforeEach, expect, test, vi } from 'vitest';

// hiddenVaultEnvelope.js imports argon2-browser at module scope; mock it so
// merely importing WrongPasswordError from it doesn't touch the WASM loader
// under jsdom (same reasoning as VaultUnlockModal.test.jsx).
vi.mock('argon2-browser', () => {
  const ArgonType = { Argon2id: 2 };
  const hash = vi.fn();
  return { ArgonType, hash, default: { ArgonType, hash } };
});

vi.mock('../../../hooks/useAuth', () => ({
  useAuth: vi.fn(),
}));

vi.mock('../../../services/hiddenVault/unlockEnvelopeStore', () => ({
  hasEnvelope: vi.fn(),
  setDecoySlot: vi.fn(),
  open: vi.fn(),
}));

vi.mock('../../../services/duressSignalService', () => ({
  registerSignalToken: vi.fn(),
}));

import VaultDuressSetup from '../VaultDuressSetup';
import { useAuth } from '../../../hooks/useAuth';
import * as unlockEnvelopeStore from '../../../services/hiddenVault/unlockEnvelopeStore';
import { registerSignalToken } from '../../../services/duressSignalService';
import { WrongPasswordError } from '../../../services/hiddenVault/hiddenVaultEnvelope';

const USER_ID = 'user-1';
const TOKEN = 'jwt-token';
const DURESS_TOKEN = 'freshly-minted-duress-token';

const fillAndSubmit = (getByLabelText, getByRole, { vaultPassword = 'real-password', decoyPassword = 'a decoy password 12+', confirm } = {}) => {
  fireEvent.change(getByLabelText(/current vault password/i), { target: { value: vaultPassword } });
  fireEvent.change(getByLabelText(/new decoy password/i), { target: { value: decoyPassword } });
  fireEvent.change(getByLabelText(/confirm decoy password/i), { target: { value: confirm ?? decoyPassword } });
  fireEvent.click(getByRole('button', { name: /save decoy password/i }));
};

const submitRecovery = (getByLabelText, getByRole, password) => {
  fireEvent.change(getByLabelText(/decoy password/i, { selector: '#duress-recovery-password' }), {
    target: { value: password },
  });
  fireEvent.click(getByRole('button', { name: /recover unregistered alarm/i }));
};

beforeEach(() => {
  vi.clearAllMocks();
  useAuth.mockReturnValue({
    isAuthenticated: true,
    user: { id: USER_ID },
    getAccessToken: () => TOKEN,
  });
  unlockEnvelopeStore.hasEnvelope.mockReturnValue(true);
});

afterEach(() => {
  cleanup();
});

test('full success: registers the token and shows the success message', async () => {
  unlockEnvelopeStore.setDecoySlot.mockResolvedValue({ duressToken: DURESS_TOKEN });
  registerSignalToken.mockResolvedValue({ success: true });

  const { getByLabelText, getByRole, findByRole } = render(<VaultDuressSetup />);
  fillAndSubmit(getByLabelText, getByRole);

  const status = await findByRole('status');
  expect(status).toHaveTextContent('Decoy password saved.');
  expect(registerSignalToken).toHaveBeenCalledWith(TOKEN, DURESS_TOKEN);
});

test('registration failure points at the recovery section, and touches the envelope only once', async () => {
  unlockEnvelopeStore.setDecoySlot.mockResolvedValue({ duressToken: DURESS_TOKEN });
  registerSignalToken.mockRejectedValueOnce(new Error('network error'));

  const { getByLabelText, getByRole, findByRole } = render(<VaultDuressSetup />);
  fillAndSubmit(getByLabelText, getByRole);

  const alert = await findByRole('alert');
  expect(alert).toHaveTextContent(/could not be registered/i);
  expect(alert).toHaveTextContent(/recover unregistered alarm/i);
  expect(unlockEnvelopeStore.setDecoySlot).toHaveBeenCalledTimes(1);
});

test('the recovery form is present even before any failure, and survives independently of the setup form', async () => {
  const { getByRole } = render(<VaultDuressSetup />);
  expect(getByRole('button', { name: /recover unregistered alarm/i })).toBeInTheDocument();
});

test('recovery re-opens the envelope with the decoy password and registers the token it finds, without touching setDecoySlot', async () => {
  unlockEnvelopeStore.open.mockResolvedValue({ slotIndex: 1, duressToken: DURESS_TOKEN, dekBytes: new Uint8Array(32), saltB64: 's' });
  registerSignalToken.mockResolvedValue({ success: true });

  const { getByLabelText, getByRole, findByRole } = render(<VaultDuressSetup />);
  submitRecovery(getByLabelText, getByRole, 'my-decoy-password');

  const status = await findByRole('status');
  expect(status).toHaveTextContent(/alarm registered/i);
  expect(unlockEnvelopeStore.open).toHaveBeenCalledWith({ userId: USER_ID, password: 'my-decoy-password' });
  expect(registerSignalToken).toHaveBeenCalledWith(TOKEN, DURESS_TOKEN);
  // Recovery must never re-run setDecoySlot -- that would mint a brand-new
  // random token via generateSignalToken() and orphan whatever was already
  // registered or pending.
  expect(unlockEnvelopeStore.setDecoySlot).not.toHaveBeenCalled();
});

test('recovery survives a full remount (simulated by rendering a fresh instance with no prior state)', async () => {
  unlockEnvelopeStore.open.mockResolvedValue({ slotIndex: 1, duressToken: DURESS_TOKEN, dekBytes: new Uint8Array(32), saltB64: 's' });
  registerSignalToken.mockResolvedValue({ success: true });

  // A fresh render with zero component history -- nothing was carried over
  // from an earlier failed attempt, proving recovery does not depend on any
  // in-memory state from the session that saw the original failure.
  const { getByLabelText, getByRole, findByRole } = render(<VaultDuressSetup />);
  submitRecovery(getByLabelText, getByRole, 'my-decoy-password');

  await waitFor(() => expect(registerSignalToken).toHaveBeenCalledWith(TOKEN, DURESS_TOKEN));
  expect(await findByRole('status')).toHaveTextContent(/alarm registered/i);
});

test('recovery with the wrong decoy password shows a clear error and does not call registerSignalToken', async () => {
  unlockEnvelopeStore.open.mockRejectedValue(new WrongPasswordError('no slot matched'));

  const { getByLabelText, getByRole, findByRole } = render(<VaultDuressSetup />);
  submitRecovery(getByLabelText, getByRole, 'wrong-password');

  const alert = await findByRole('alert');
  expect(alert).toHaveTextContent('Incorrect decoy password.');
  expect(registerSignalToken).not.toHaveBeenCalled();
});

test('recovery with the REAL vault password (slot 0) is called out distinctly, not treated as success', async () => {
  unlockEnvelopeStore.open.mockResolvedValue({ slotIndex: 0, duressToken: null, dekBytes: new Uint8Array(32), saltB64: 's' });

  const { getByLabelText, getByRole, findByRole } = render(<VaultDuressSetup />);
  submitRecovery(getByLabelText, getByRole, 'real-password');

  const alert = await findByRole('alert');
  expect(alert).toHaveTextContent(/real vault, not the decoy slot/i);
  expect(registerSignalToken).not.toHaveBeenCalled();
});

test('a wrong vault password on the setup form does not touch recovery or registration', async () => {
  unlockEnvelopeStore.setDecoySlot.mockRejectedValue(new WrongPasswordError('no slot matched'));

  const { getByLabelText, getByRole, findByRole } = render(<VaultDuressSetup />);
  fillAndSubmit(getByLabelText, getByRole);

  const alert = await findByRole('alert');
  expect(alert).toHaveTextContent('Incorrect vault password.');
  expect(registerSignalToken).not.toHaveBeenCalled();
  expect(unlockEnvelopeStore.open).not.toHaveBeenCalled();
});

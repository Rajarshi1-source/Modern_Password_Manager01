/**
 * Targeted regression tests for VaultDuressSetup's orphaned-token recovery.
 *
 * CodeRabbit finding on PR #489: setDecoySlot() persists the new decoy
 * envelope BEFORE registerSignalToken() runs (correct ordering, per the
 * #486 §10.3 lesson) -- but if registration then fails, the decoy password
 * is already live while its alarm is not registered anywhere, and a plain
 * retry would mint a brand-new random token via setDecoySlot(), orphaning
 * the first one rather than recovering it. These tests assert the fix:
 * the failed token is retained and a dedicated retry re-sends the SAME
 * token without touching the envelope again.
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

test('full success: registers the token and shows the success message with no retry button', async () => {
  unlockEnvelopeStore.setDecoySlot.mockResolvedValue({ duressToken: DURESS_TOKEN });
  registerSignalToken.mockResolvedValue({ success: true });

  const { getByLabelText, getByRole, findByRole, queryByRole } = render(<VaultDuressSetup />);
  fillAndSubmit(getByLabelText, getByRole);

  const status = await findByRole('status');
  expect(status).toHaveTextContent('Decoy password saved.');
  expect(registerSignalToken).toHaveBeenCalledWith(TOKEN, DURESS_TOKEN);
  expect(queryByRole('button', { name: /finish registration/i })).not.toBeInTheDocument();
});

test('registration failure keeps the envelope change but surfaces a retry, not a dead-end error', async () => {
  unlockEnvelopeStore.setDecoySlot.mockResolvedValue({ duressToken: DURESS_TOKEN });
  registerSignalToken.mockRejectedValueOnce(new Error('network error'));

  const { getByLabelText, getByRole, findByRole } = render(<VaultDuressSetup />);
  fillAndSubmit(getByLabelText, getByRole);

  const alert = await findByRole('alert');
  expect(alert).toHaveTextContent(/could not be registered/i);
  expect(await findByRole('button', { name: /finish registration/i })).toBeInTheDocument();
  // The envelope was already re-encoded with the decoy slot -- exactly once,
  // never retried by this failure alone.
  expect(unlockEnvelopeStore.setDecoySlot).toHaveBeenCalledTimes(1);
});

test('retry re-sends the EXACT SAME token without touching the envelope again', async () => {
  unlockEnvelopeStore.setDecoySlot.mockResolvedValue({ duressToken: DURESS_TOKEN });
  registerSignalToken.mockRejectedValueOnce(new Error('network error'));
  registerSignalToken.mockResolvedValueOnce({ success: true });

  const { getByLabelText, getByRole, findByRole } = render(<VaultDuressSetup />);
  fillAndSubmit(getByLabelText, getByRole);
  await findByRole('button', { name: /finish registration/i });

  fireEvent.click(getByRole('button', { name: /finish registration/i }));

  const status = await findByRole('status');
  expect(status).toHaveTextContent('Decoy password saved.');
  expect(registerSignalToken).toHaveBeenCalledTimes(2);
  expect(registerSignalToken).toHaveBeenNthCalledWith(1, TOKEN, DURESS_TOKEN);
  expect(registerSignalToken).toHaveBeenNthCalledWith(2, TOKEN, DURESS_TOKEN);
  // setDecoySlot must never run a second time for a registration-only retry
  // -- re-running it would mint a DIFFERENT random token via
  // generateSignalToken() and silently orphan the one just recovered.
  expect(unlockEnvelopeStore.setDecoySlot).toHaveBeenCalledTimes(1);
});

test('a failed retry keeps the same token available for another attempt', async () => {
  unlockEnvelopeStore.setDecoySlot.mockResolvedValue({ duressToken: DURESS_TOKEN });
  registerSignalToken.mockRejectedValue(new Error('still down'));

  const { getByLabelText, getByRole, findByRole } = render(<VaultDuressSetup />);
  fillAndSubmit(getByLabelText, getByRole);
  await findByRole('button', { name: /finish registration/i });

  fireEvent.click(getByRole('button', { name: /finish registration/i }));

  await waitFor(() => expect(registerSignalToken).toHaveBeenCalledTimes(2));
  expect(await findByRole('button', { name: /finish registration/i })).toBeInTheDocument();
  expect(registerSignalToken).toHaveBeenNthCalledWith(2, TOKEN, DURESS_TOKEN);
});

test('a wrong vault password does not touch the retry path', async () => {
  unlockEnvelopeStore.setDecoySlot.mockRejectedValue(new WrongPasswordError('no slot matched'));

  const { getByLabelText, getByRole, findByRole, queryByRole } = render(<VaultDuressSetup />);
  fillAndSubmit(getByLabelText, getByRole);

  const alert = await findByRole('alert');
  expect(alert).toHaveTextContent('Incorrect vault password.');
  expect(queryByRole('button', { name: /finish registration/i })).not.toBeInTheDocument();
  expect(registerSignalToken).not.toHaveBeenCalled();
});

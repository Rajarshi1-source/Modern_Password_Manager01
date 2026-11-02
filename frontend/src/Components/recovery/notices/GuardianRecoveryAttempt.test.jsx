import React from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

const api = vi.hoisted(() => ({
  confirmRecovery: vi.fn(),
  recoveryProgress: vi.fn(),
  completeRecovery: vi.fn(),
}));
const keys = vi.hoisted(() => ({ loadRequesterKeyPair: vi.fn(), forgetRequesterKeyPair: vi.fn() }));

vi.mock('../../../services/api', () => ({
  default: {
    quantumRecovery: api,
    handleError: (err) => ({ error: err?.response?.data?.error }),
  },
}));
vi.mock('../../../services/recovery/holderKeyStore', () => keys);
const vault = vi.hoisted(() => ({ unlockWithRecoveryFactor: vi.fn() }));
const factors = vi.hoisted(() => ({ lookupRecoveryFactor: vi.fn() }));
const recoverSeed = vi.hoisted(() => vi.fn());
vi.mock('../../../services/sessionVaultCryptoV3', () => ({ default: vault }));
vi.mock('../../../services/recoveryFactorService', () => ({ default: factors }));
vi.mock('../../../services/quantum/hybridKem', () => ({
  ensureHybridKemReady: vi.fn(), generateHybridKeyPair: vi.fn(), openSealed: vi.fn(), sealToHybridKey: vi.fn(),
}));
vi.mock('../../../services/recovery/sealedShareRecovery', async (original) => ({
  ...(await original()), recoverSeed,
}));

import GuardianRecoveryAttempt from './GuardianRecoveryAttempt';
import { keyFingerprint, requesterToken, toB64 } from '../../../services/recovery/sealedShareRecovery';

const ATTEMPT_ID = '3f2b8c1e-7a4d-4e9b-8c21-5d6f7a8b9c0d';
const keyPair = { publicKey: toB64(new Uint8Array(1216).fill(7)), secretKey: toB64(new Uint8Array(64).fill(9)) };
const FINGERPRINT = keyFingerprint(keyPair.publicKey);
const LINK = `/recovery/guardian-attempt?attempt=${ATTEMPT_ID}&key=${FINGERPRINT}`;

const progress = (over = {}) => ({
  data: {
    status: 'guardian_approval', threshold: 2, guardians_asked: 3, approvals_received: 0, denials: 0,
    release_after: '2026-11-04T10:00:00Z', ready: false, ...over,
  },
});

const renderAt = (url) => render(
  <MemoryRouter initialEntries={[url]}>
    <GuardianRecoveryAttempt />
  </MemoryRouter>,
);

describe('GuardianRecoveryAttempt', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    keys.loadRequesterKeyPair.mockResolvedValue(keyPair);
    api.recoveryProgress.mockResolvedValue(progress());
  });

  it.each([
    `?attempt=abc-123&key=${FINGERPRINT}`,
    `?attempt=${ATTEMPT_ID.slice(0, -1)}&key=${FINGERPRINT}`,
    `?attempt=${ATTEMPT_ID}x&key=${FINGERPRINT}`,
    `?attempt=${ATTEMPT_ID}`,
    `?attempt=${ATTEMPT_ID}&key=nope`,
    '',
  ])('treats "%s" as an incomplete link and sends nothing', (query) => {
    renderAt(`/recovery/guardian-attempt${query}`);
    expect(screen.getByRole('alert').textContent).toMatch(/incomplete/);
    expect(api.recoveryProgress).not.toHaveBeenCalled();
  });

  it('on another browser says so, points at the cancel link, and sends nothing', async () => {
    keys.loadRequesterKeyPair.mockResolvedValue(null);
    renderAt(LINK);
    expect((await screen.findByTestId('guardian-recovery-other-device')).textContent).toMatch(/did not start/);
    expect(screen.getByTestId('guardian-recovery-attempt').textContent).toMatch(/cancel link/);
    expect(api.recoveryProgress).not.toHaveBeenCalled();
  });

  it('treats a stored key that is not the one in the link as no key', async () => {
    keys.loadRequesterKeyPair.mockResolvedValue({
      ...keyPair, publicKey: toB64(new Uint8Array(1216).fill(8)),
    });
    renderAt(LINK);
    await screen.findByTestId('guardian-recovery-other-device');
    expect(api.recoveryProgress).not.toHaveBeenCalled();
  });

  it('treats a stored key it cannot read as no key', async () => {
    keys.loadRequesterKeyPair.mockResolvedValue({ ...keyPair, publicKey: '%%not base64%%' });
    renderAt(LINK);
    await screen.findByTestId('guardian-recovery-other-device');
    expect(api.recoveryProgress).not.toHaveBeenCalled();
  });

  it('gives no date while the wait has no start', async () => {
    api.recoveryProgress.mockResolvedValue(progress({ release_after: null }));
    renderAt(LINK);
    const wait = await screen.findByTestId('guardian-recovery-wait');
    expect(wait.textContent).toMatch(/not on record/);
    expect(wait.textContent).not.toMatch(/1970|1969/);
  });

  it('offers to ask again only when the server says guardians were left unasked', async () => {
    renderAt(LINK);
    await screen.findByTestId('guardian-recovery-code');
    expect(screen.queryByRole('button', { name: /ask my guardians again/i })).toBeNull();
    api.recoveryProgress.mockResolvedValue(progress({ ask_again: true }));
    fireEvent.click(screen.getByTestId('guardian-recovery-check'));
    await screen.findByRole('button', { name: /ask my guardians again/i });
  });

  it('sends the device token, and asks guardians only when the person says so', async () => {
    api.recoveryProgress.mockResolvedValue(progress({ status: 'initiated', guardians_asked: 0 }));
    api.confirmRecovery.mockResolvedValue(progress());
    renderAt(LINK);
    const button = await screen.findByTestId('guardian-recovery-confirm');
    const body = { attempt_id: ATTEMPT_ID, requester_token: requesterToken(keyPair) };
    expect(api.recoveryProgress).toHaveBeenCalledWith(body);
    expect(api.confirmRecovery).not.toHaveBeenCalled();
    fireEvent.click(button);
    await screen.findByTestId('guardian-recovery-code');
    expect(api.confirmRecovery).toHaveBeenCalledWith(body);
  });

  it('shows the code to read out and the wait, and offers no recovery yet', async () => {
    api.recoveryProgress.mockResolvedValue(progress({ approvals_received: 2 }));
    renderAt(LINK);
    expect((await screen.findByTestId('guardian-recovery-code')).textContent).toBe(FINGERPRINT);
    expect(screen.getByTestId('guardian-recovery-wait')).toBeTruthy();
    expect(screen.getByTestId('guardian-recovery-progress').textContent).toMatch(/2 of 2/);
    expect(screen.queryByTestId('guardian-recovery-recover')).toBeNull();
  });

  it('asks for the username once it is ready', async () => {
    api.recoveryProgress.mockResolvedValue(progress({ approvals_received: 2, ready: true }));
    renderAt(LINK);
    await screen.findByTestId('guardian-recovery-recover');
    expect(api.completeRecovery).not.toHaveBeenCalled();
  });

  describe('recovering', () => {
    const submit = async (username) => {
      fireEvent.change(screen.getByTestId('guardian-recovery-username'), { target: { value: username } });
      fireEvent.click(screen.getByTestId('guardian-recovery-recover'));
    };

    beforeEach(() => {
      api.recoveryProgress.mockResolvedValue(progress({ approvals_received: 2, ready: true }));
      api.completeRecovery.mockResolvedValue({
        data: { sealed_shares: [{ sealed_share: 'a' }, { sealed_share: 'b' }], threshold: 2, secret_check: 'c' },
      });
      recoverSeed.mockImplementation(async () => new Uint8Array(32).fill(5));
      factors.lookupRecoveryFactor.mockResolvedValue({ blob: {}, dek_id: 'd' });
      vault.unlockWithRecoveryFactor.mockResolvedValue(undefined);
    });

    it('fetches the shares once when only the username was wrong', async () => {
      vault.unlockWithRecoveryFactor.mockRejectedValueOnce(new Error('unwrap'));
      renderAt(LINK);
      await screen.findByTestId('guardian-recovery-recover');

      await submit('typo');
      await waitFor(() => expect(screen.getByRole('alert').textContent).toMatch(/Check the username/));
      await submit('owner');

      await screen.findByTestId('guardian-recovery-new-password');
      expect(api.completeRecovery).toHaveBeenCalledTimes(1);
      expect(recoverSeed).toHaveBeenCalledTimes(1);
      expect(factors.lookupRecoveryFactor).toHaveBeenLastCalledWith('owner', 'social_mesh');
      const hex = '05'.repeat(32);
      expect(vault.unlockWithRecoveryFactor).toHaveBeenLastCalledWith({}, hex, 'd');
    });

    it('fetches the shares again when the fetch itself failed', async () => {
      api.completeRecovery.mockRejectedValueOnce({ response: { status: 500 } });
      renderAt(LINK);
      await screen.findByTestId('guardian-recovery-recover');

      await submit('owner');
      await screen.findByRole('alert');
      await submit('owner');

      await screen.findByTestId('guardian-recovery-new-password');
      expect(api.completeRecovery).toHaveBeenCalledTimes(2);
    });
  });

  it('stops on a cancelled recovery', async () => {
    api.recoveryProgress.mockResolvedValue(progress({ status: 'cancelled' }));
    renderAt(LINK);
    expect((await screen.findByTestId('guardian-recovery-stopped')).textContent).toMatch(/cancelled/);
    expect(screen.queryByTestId('guardian-recovery-code')).toBeNull();
  });

  it('explains a rate limit on a check', async () => {
    renderAt(LINK);
    const check = await screen.findByTestId('guardian-recovery-check');
    api.recoveryProgress.mockRejectedValue({
      response: { status: 429, data: { error: 'Too many requests', code: 'throttled' } },
    });
    fireEvent.click(check);
    await waitFor(() => expect(screen.getByRole('alert').textContent).toMatch(/Too many tries/));
  });

  it('gives the monthly limit its own reason', async () => {
    renderAt(LINK);
    const check = await screen.findByTestId('guardian-recovery-check');
    api.recoveryProgress.mockRejectedValue({
      response: { status: 429, data: { error: 'Too many recoveries this month; try again later' } },
    });
    fireEvent.click(check);
    await waitFor(() => expect(screen.getByRole('alert').textContent).toMatch(/this month/));
  });
});

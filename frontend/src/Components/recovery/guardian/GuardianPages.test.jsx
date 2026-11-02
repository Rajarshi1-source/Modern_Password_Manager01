import React from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';

const api = vi.hoisted(() => ({
  getRecoveryStatus: vi.fn(),
  setupRecovery: vi.fn(),
  initiateRecovery: vi.fn(),
  getGuardianShare: vi.fn(),
  approveRecovery: vi.fn(),
}));
const vault = vi.hoisted(() => ({ buildRecoveryFactorEnvelope: vi.fn() }));
const crypto = vi.hoisted(() => ({
  sealSeedForGuardians: vi.fn(),
  resealShareForRequester: vi.fn(),
  keyFingerprint: vi.fn(),
  requesterTokenHash: vi.fn(() => 'token-hash'),
}));
const keys = vi.hoisted(() => ({
  loadGuardianKeyPair: vi.fn(),
  assertKeyStorageAvailable: vi.fn(),
  newRequesterKeyPair: vi.fn(),
  saveRequesterKeyPair: vi.fn(),
}));

vi.mock('../../../services/api', () => ({
  default: { quantumRecovery: api, handleError: (err) => ({ error: err?.response?.data?.error }) },
}));
vi.mock('../../../services/sessionVaultCryptoV3', () => ({ default: vault }));
vi.mock('../../../services/quantum/hybridKem', () => ({ ensureHybridKemReady: vi.fn() }));
vi.mock('../../../services/recovery/sealedShareRecovery', () => crypto);
vi.mock('../../../services/recovery/holderKeyStore', () => keys);

import GuardianApprove from './GuardianApprove';
import GuardianRecoveryStart from './GuardianRecoveryStart';
import GuardianSetup from './GuardianSetup';

beforeEach(() => {
  vi.clearAllMocks();
  crypto.keyFingerprint.mockImplementation((key) => `FP-${key}`);
});

describe('GuardianApprove', () => {
  const open = () => render(
    <MemoryRouter initialEntries={['/recovery/guardian-approve/tok']}>
      <Routes><Route path="/recovery/guardian-approve/:token" element={<GuardianApprove />} /></Routes>
    </MemoryRouter>,
  );

  beforeEach(() => {
    api.getGuardianShare.mockResolvedValue({
      data: { sealed_share: 'sealed', requester_public_key: 'requester' },
    });
    keys.loadGuardianKeyPair.mockResolvedValue({ publicKey: 'g', secretKey: 's' });
  });

  it('sends nothing when the code does not match', async () => {
    crypto.resealShareForRequester.mockRejectedValue(new Error("the requester's key fingerprint does not match"));
    open();
    fireEvent.change(await screen.findByTestId('guardian-approve-code'), { target: { value: 'WRONG' } });
    fireEvent.click(screen.getByTestId('guardian-approve-submit'));
    await waitFor(() => expect(screen.getByRole('alert').textContent).toMatch(/does not match/));
    expect(api.approveRecovery).not.toHaveBeenCalled();
  });

  it('sends only the re-sealed share on approval', async () => {
    crypto.resealShareForRequester.mockResolvedValue('resealed');
    api.approveRecovery.mockResolvedValue({ data: {} });
    open();
    fireEvent.change(await screen.findByTestId('guardian-approve-code'), { target: { value: 'CODE' } });
    fireEvent.click(screen.getByTestId('guardian-approve-submit'));
    await screen.findByTestId('guardian-approve-result');
    expect(crypto.resealShareForRequester).toHaveBeenCalledWith(expect.objectContaining({
      confirmedFingerprint: 'CODE', requesterPublicKey: 'requester',
    }));
    expect(api.approveRecovery).toHaveBeenCalledWith({
      approval_token: 'tok', approved: true, resealed_share: 'resealed',
    });
  });

  it('can deny without opening the share', async () => {
    api.approveRecovery.mockResolvedValue({ data: {} });
    open();
    fireEvent.click(await screen.findByTestId('guardian-approve-deny'));
    await screen.findByTestId('guardian-approve-result');
    expect(crypto.resealShareForRequester).not.toHaveBeenCalled();
    expect(api.approveRecovery).toHaveBeenCalledWith({ approval_token: 'tok', approved: false });
  });

  it('shows why a closed request cannot be opened', async () => {
    api.getGuardianShare.mockRejectedValue({ response: { data: { error: 'This recovery is no longer open' } } });
    open();
    await waitFor(() => expect(screen.getByRole('alert').textContent).toMatch(/no longer open/));
  });
});

describe('GuardianSetup', () => {
  const fillGuardians = async () => {
    for (let i = 0; i < 3; i++) {
      fireEvent.change(await screen.findByTestId(`guardian-setup-email-${i}`), { target: { value: `g${i}@x.test` } });
      fireEvent.change(screen.getByTestId(`guardian-setup-key-${i}`), { target: { value: `key${i}` } });
    }
    fireEvent.change(screen.getByTestId('guardian-setup-master-password'), { target: { value: 'pw' } });
  };

  it('tells the owner when guardian recovery is already on', async () => {
    api.getRecoveryStatus.mockResolvedValue({ data: { recovery_configured: true, is_active: true } });
    render(<GuardianSetup />);
    expect((await screen.findByTestId('guardian-setup-existing')).textContent).toMatch(/is on/);
    expect(screen.queryByTestId('guardian-setup-submit')).toBeNull();
  });

  it('offers setup again when an invitation lapsed', async () => {
    api.getRecoveryStatus.mockResolvedValue({
      data: { recovery_configured: true, is_active: false, can_replace: true },
    });
    render(<GuardianSetup />);
    await screen.findByTestId('guardian-setup-submit');
  });

  it('refuses until every fingerprint is checked, and sends nothing', async () => {
    api.getRecoveryStatus.mockResolvedValue({ data: { recovery_configured: false } });
    render(<GuardianSetup />);
    await fillGuardians();
    fireEvent.click(screen.getByTestId('guardian-setup-submit'));
    await waitFor(() => expect(screen.getByRole('alert').textContent).toMatch(/fingerprint/));
    expect(crypto.sealSeedForGuardians).not.toHaveBeenCalled();
    expect(api.setupRecovery).not.toHaveBeenCalled();
  });

  it('wraps the vault key first, and a wrong password stops the setup', async () => {
    api.getRecoveryStatus.mockResolvedValue({ data: { recovery_configured: false } });
    crypto.sealSeedForGuardians.mockResolvedValue({ secretCheck: 'check', shares: [] });
    vault.buildRecoveryFactorEnvelope.mockRejectedValue(new Error('Wrong master password'));
    render(<GuardianSetup />);
    await fillGuardians();
    for (let i = 0; i < 3; i++) fireEvent.click(screen.getByTestId(`guardian-setup-fingerprint-checked-${i}`));
    fireEvent.click(screen.getByTestId('guardian-setup-submit'));
    await waitFor(() => expect(screen.getByRole('alert').textContent).toMatch(/Wrong master password/));
    expect(api.setupRecovery).not.toHaveBeenCalled();
  });

  it('sends the wrapped key and sealed values in one request, not the seed', async () => {
    api.getRecoveryStatus.mockResolvedValue({ data: { recovery_configured: false } });
    crypto.sealSeedForGuardians.mockResolvedValue({
      secretCheck: 'check',
      shares: [0, 1, 2].map((i) => ({ shareIndex: i + 1, sealedShare: `sealed${i}`, shareProofHash: `hash${i}` })),
    });
    vault.buildRecoveryFactorEnvelope.mockResolvedValue({ blob: { v: 'wdek-1' }, dekId: 'dek', authHash: 'proof' });
    api.setupRecovery.mockResolvedValue({ data: { shards_created: [] } });
    render(<GuardianSetup />);
    await fillGuardians();
    for (let i = 0; i < 3; i++) fireEvent.click(screen.getByTestId(`guardian-setup-fingerprint-checked-${i}`));
    fireEvent.click(screen.getByTestId('guardian-setup-submit'));
    await screen.findByTestId('guardian-setup-done');
    const body = api.setupRecovery.mock.calls[0][0];
    expect(Object.keys(body).sort()).toEqual(
      ['guardians', 'recovery_factor', 'secret_check', 'secret_type', 'threshold_shards']);
    expect(body.recovery_factor).toEqual({ dek_id: 'dek', blob: { v: 'wdek-1' }, auth_hash: 'proof' });
    expect(body.guardians[1]).toEqual({
      email: 'g1@x.test', requires_video: false, public_key: 'key1',
      share_index: 2, sealed_share: 'sealed1', share_proof_hash: 'hash1',
    });
  });
});

describe('GuardianRecoveryStart', () => {
  it('stores the key before asking, under its fingerprint, and sends only public values', async () => {
    const keyPair = { publicKey: 'pub', secretKey: 'secret' };
    keys.newRequesterKeyPair.mockResolvedValue(keyPair);
    api.initiateRecovery.mockResolvedValue({ data: { message: 'Check your email' } });
    render(<GuardianRecoveryStart />);
    fireEvent.change(screen.getByTestId('guardian-recovery-start-email'), { target: { value: 'me@x.test' } });
    fireEvent.click(screen.getByTestId('guardian-recovery-start-submit'));
    await screen.findByTestId('guardian-recovery-start-message');
    expect(keys.saveRequesterKeyPair).toHaveBeenCalledWith('FP-pub', keyPair);
    expect(keys.saveRequesterKeyPair.mock.invocationCallOrder[0])
      .toBeLessThan(api.initiateRecovery.mock.invocationCallOrder[0]);
    expect(api.initiateRecovery).toHaveBeenCalledWith({
      email: 'me@x.test', requester_public_key: 'pub', requester_token_hash: 'token-hash',
    });
  });

  it('does not ask the server when this browser cannot keep the key', async () => {
    keys.assertKeyStorageAvailable.mockRejectedValueOnce(new Error('no storage'));
    render(<GuardianRecoveryStart />);
    fireEvent.change(screen.getByTestId('guardian-recovery-start-email'), { target: { value: 'me@x.test' } });
    fireEvent.click(screen.getByTestId('guardian-recovery-start-submit'));
    await waitFor(() => expect(screen.getByRole('alert').textContent).toMatch(/no storage/));
    expect(api.initiateRecovery).not.toHaveBeenCalled();
  });
});

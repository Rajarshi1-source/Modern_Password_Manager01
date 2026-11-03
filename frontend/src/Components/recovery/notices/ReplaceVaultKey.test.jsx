import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import ReplaceVaultKey from './ReplaceVaultKey';
import RecoveryNotices from './RecoveryNotices';
import ApiService from '../../../services/api';
import { replaceVaultKey } from '../../../services/vaultEnvelope';

vi.mock('../../../services/api', () => ({
  default: {
    recoveryNotices: { list: vi.fn(), acknowledgeExposure: vi.fn() },
    handleError: vi.fn(),
  },
}));
vi.mock('../../../services/vaultEnvelope', () => ({ replaceVaultKey: vi.fn() }));

function submit(password = 'pw') {
  fireEvent.change(screen.getByLabelText('Master password'), { target: { value: password } });
  fireEvent.click(screen.getByRole('button', { name: 'Replace vault key' }));
}

describe('ReplaceVaultKey', () => {
  beforeEach(() => vi.clearAllMocks());

  it('says what happens to the recovery factors before anything is done', () => {
    render(<ReplaceVaultKey username="alice" />);
    expect(screen.getByTestId('replace-vault-key').textContent).toContain('every recovery factor is removed');
    expect(replaceVaultKey).not.toHaveBeenCalled();
  });

  it('replaces the key and tells the owner to sign in and enroll again', async () => {
    replaceVaultKey.mockResolvedValue({ dekId: 'new' });
    render(<ReplaceVaultKey username="alice" />);
    submit();
    const done = await screen.findByTestId('replace-vault-key-done');
    expect(replaceVaultKey).toHaveBeenCalledWith('pw', 'alice');
    expect(done.textContent).toContain('enroll new recovery factors');
  });

  it('shows a wrong password and clears the field', async () => {
    replaceVaultKey.mockRejectedValue(new Error('Incorrect password or corrupted vault key.'));
    render(<ReplaceVaultKey username="alice" />);
    submit();
    expect((await screen.findByRole('alert')).textContent).toContain('Incorrect password');
    expect(screen.getByLabelText('Master password').value).toBe('');
  });

  it('shows why the server refused', async () => {
    const err = new Error('Request failed');
    err.response = { status: 403 };
    replaceVaultKey.mockRejectedValue(err);
    ApiService.handleError.mockReturnValue({ error: 'Only after support unlocks the account.' });
    render(<ReplaceVaultKey username="alice" />);
    submit();
    expect((await screen.findByRole('alert')).textContent).toContain('support unlocks');
  });
});

describe('RecoveryNotices', () => {
  beforeEach(() => vi.clearAllMocks());

  const list = (data) => ApiService.recoveryNotices.list.mockResolvedValue({
    data: { notices: [], username: 'alice', vault_exposed_since: '2026-11-01T10:00:00Z', ...data },
  });

  it('offers the replacement while the warning is open', async () => {
    list({ vault_key_replaced_at: null });
    render(<RecoveryNotices />);
    expect(await screen.findByTestId('replace-vault-key')).toBeTruthy();
  });

  it('offers it again for an exposure newer than the last replacement', async () => {
    list({ vault_key_replaced_at: '2026-10-01T10:00:00Z' });
    render(<RecoveryNotices />);
    expect(await screen.findByTestId('replace-vault-key')).toBeTruthy();
  });

  it('warns that confirming the warning ends the offer', async () => {
    list({ vault_key_replaced_at: null });
    render(<RecoveryNotices />);
    await screen.findByTestId('replace-vault-key');
    expect(screen.getByTestId('vault-exposure-warning').textContent).toContain('can no longer be replaced');
  });

  it('says it is done once replaced for this exposure', async () => {
    list({ vault_key_replaced_at: '2026-11-02T10:00:00Z' });
    render(<RecoveryNotices />);
    await screen.findByTestId('vault-key-replaced');
    await waitFor(() => expect(screen.queryByTestId('replace-vault-key')).toBeNull());
  });
});

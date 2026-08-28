/**
 * VaultItemsSection (App.jsx) must not attempt to decrypt or render the real
 * vault's items during a decoy session -- a decoy DEK cannot decrypt them,
 * and rendering "Decryption failed" on every card would instantly out the
 * decoy to whoever forced the unlock. See
 * docs/vault-unlock-envelope-integration-plan.md's implementation-status log
 * (twelfth CodeRabbit review round) for the full finding this guards.
 */
import { describe, test, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';

const REAL_ITEM = { item_id: 'real-1', encrypted_data: 'CIPHERTEXT' };

const { mockIsDecoySession, mockDecryptEnvelope, mockUseVault } = vi.hoisted(() => ({
  mockIsDecoySession: vi.fn(() => false),
  mockDecryptEnvelope: vi.fn(async () => ({ name: 'Real Item' })),
  mockUseVault: vi.fn(() => ({
    items: [{ item_id: 'real-1', encrypted_data: 'CIPHERTEXT' }],
    loading: false,
    error: null,
  })),
}));

vi.mock('../services/sessionVaultCrypto', () => ({
  default: { isDecoySession: mockIsDecoySession },
}));

vi.mock('../services/vaultEnvelope', () => ({
  decryptEnvelope: (...args) => mockDecryptEnvelope(...args),
  encryptEnvelope: vi.fn(),
  hasVaultSessionKey: vi.fn(() => true),
}));

vi.mock('../contexts/VaultContext', () => ({
  useVault: () => mockUseVault(),
}));

import { VaultItemsSection } from '../App';

beforeEach(() => {
  vi.clearAllMocks();
  mockIsDecoySession.mockReturnValue(false);
  mockDecryptEnvelope.mockResolvedValue({ name: 'Real Item' });
  mockUseVault.mockReturnValue({ items: [REAL_ITEM], loading: false, error: null });
});

describe('VaultItemsSection during a decoy session', () => {
  test('renders the empty-vault state instead of attempting real decryption', async () => {
    mockIsDecoySession.mockReturnValue(true);
    render(<VaultItemsSection />);

    expect(await screen.findByTestId('empty-vault')).toBeInTheDocument();
    expect(screen.queryByTestId('vault-item')).not.toBeInTheDocument();
    expect(mockDecryptEnvelope).not.toHaveBeenCalled();
  });

  test('a real session still decrypts and renders the item normally', async () => {
    render(<VaultItemsSection />);

    await waitFor(() => expect(mockDecryptEnvelope).toHaveBeenCalledWith('CIPHERTEXT'));
    expect(await screen.findByText('Real Item')).toBeInTheDocument();
    expect(screen.queryByTestId('empty-vault')).not.toBeInTheDocument();
  });
});

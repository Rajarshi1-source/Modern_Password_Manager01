/**
 * VaultItemsSection (App.jsx) must not attempt to decrypt or render the real
 * vault's items during a decoy session -- a decoy DEK cannot decrypt them,
 * and rendering "Decryption failed" on every card would instantly out the
 * decoy to whoever forced the unlock. See
 * docs/vault-unlock-envelope-integration-plan.md's implementation-status log
 * (twelfth CodeRabbit review round) for the full finding this guards.
 *
 * What it renders INSTEAD changed with docs/decoy-vault-contents-plan.md: the
 * decoy vault's own rows, read from `decoyVaultStore`, which decrypt through
 * the ordinary `decryptEnvelope` path because they are shaped exactly like
 * server rows. An account with no decoy contents still falls back to the empty
 * state, which is what shipped before -- and is also the fallback for every
 * store failure.
 */
import { describe, test, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';

const REAL_ITEM = { item_id: 'real-1', encrypted_data: 'CIPHERTEXT' };
const DECOY_ROW = { id: 'd1', item_id: 'decoy-1', encrypted_data: 'DECOY_CIPHERTEXT' };

const {
  mockIsDecoySession, mockGeneration, mockDecryptEnvelope, mockUseVault, mockDecoyLoad,
} = vi.hoisted(() => ({
  mockIsDecoySession: vi.fn(() => false),
  mockGeneration: vi.fn(() => 1),
  mockDecryptEnvelope: vi.fn(async () => ({ name: 'Real Item' })),
  mockUseVault: vi.fn(() => ({
    items: [{ item_id: 'real-1', encrypted_data: 'CIPHERTEXT' }],
    loading: false,
    error: null,
  })),
  mockDecoyLoad: vi.fn(async () => []),
}));

vi.mock('../services/sessionVaultCrypto', () => ({
  default: {
    isDecoySession: mockIsDecoySession,
    currentSessionGeneration: mockGeneration,
  },
}));

vi.mock('../services/hiddenVault/decoyVaultStore', () => ({
  default: { loadForSession: mockDecoyLoad },
}));

vi.mock('../hooks/useAuth.jsx', () => ({
  useAuth: () => ({ user: { id: 1 }, isAuthenticated: true }),
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
  mockGeneration.mockReturnValue(1);
  // Re-armed here, not just cleared: see the note in the sibling
  // VaultDashboardRoute test -- `vi.clearAllMocks()` keeps implementations.
  mockDecoyLoad.mockResolvedValue([]);
  mockDecryptEnvelope.mockResolvedValue({ name: 'Real Item' });
  mockUseVault.mockReturnValue({ items: [REAL_ITEM], loading: false, error: null });
});

describe('VaultItemsSection during a decoy session', () => {
  test('with no decoy contents, renders the empty state and decrypts nothing real', async () => {
    mockIsDecoySession.mockReturnValue(true);
    render(<VaultItemsSection />);

    expect(await screen.findByTestId('empty-vault')).toBeInTheDocument();
    expect(screen.queryByTestId('vault-item')).not.toBeInTheDocument();
    expect(mockDecryptEnvelope).not.toHaveBeenCalled();
  });

  test('renders the decoy rows, and never decrypts the real ciphertext', async () => {
    mockIsDecoySession.mockReturnValue(true);
    mockDecoyLoad.mockResolvedValue([DECOY_ROW]);
    mockDecryptEnvelope.mockResolvedValue({ name: 'Decoy Entry' });

    render(<VaultItemsSection />);

    expect(await screen.findByText('Decoy Entry')).toBeInTheDocument();
    // Asserting the ARGUMENT, not merely that decryption happened: a check
    // that only counted calls would pass even if the real row were the one
    // being decrypted (envelope plan §34.1).
    expect(mockDecryptEnvelope).toHaveBeenCalledWith('DECOY_CIPHERTEXT');
    expect(mockDecryptEnvelope).not.toHaveBeenCalledWith('CIPHERTEXT');
    expect(screen.queryByTestId('empty-vault')).not.toBeInTheDocument();
  });

  test('a real session still decrypts and renders the item normally', async () => {
    render(<VaultItemsSection />);

    await waitFor(() => expect(mockDecryptEnvelope).toHaveBeenCalledWith('CIPHERTEXT'));
    expect(await screen.findByText('Real Item')).toBeInTheDocument();
    expect(screen.queryByTestId('empty-vault')).not.toBeInTheDocument();
  });
});

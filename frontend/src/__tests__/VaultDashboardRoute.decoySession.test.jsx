/**
 * VaultDashboardRoute (App.jsx) must not hand the real vault's items to
 * VaultDashboard during a decoy session.
 *
 * This is the sibling of the VaultItemsSection gate covered in
 * VaultItemsSection.decoySession.test.jsx. An earlier version gated ONLY that
 * section, leaving `/vault/dashboard` rendering the real inventory during a
 * decoy session -- which both leaks real item metadata and instantly outs the
 * decoy (a decoy DEK cannot decrypt any of it). Both surfaces now go through
 * the shared `useDisplaySafeItems` hook; these tests pin that, and exist
 * specifically so the next display surface added cannot quietly repeat the
 * "guarded one path, missed its sibling" pattern recorded in
 * docs/vault-unlock-envelope-integration-plan.md §19.6.
 */
import React, { Suspense } from 'react';
import { describe, test, expect, vi, beforeEach } from 'vitest';
import { render, waitFor } from '@testing-library/react';

const REAL_ITEM = { id: 42, item_id: 'real-1', encrypted_data: 'CIPHERTEXT' };

const { mockIsDecoySession, mockUseVault, mockVaultDashboard } = vi.hoisted(() => ({
  mockIsDecoySession: vi.fn(() => false),
  mockUseVault: vi.fn(),
  mockVaultDashboard: vi.fn(() => null),
}));

vi.mock('../services/sessionVaultCrypto', () => ({
  default: { isDecoySession: mockIsDecoySession },
}));

vi.mock('../contexts/VaultContext', () => ({
  useVault: () => mockUseVault(),
}));

// Capture exactly what the route hands the dashboard -- the assertion is
// about the props crossing that boundary, not about how the dashboard then
// chooses to render them.
vi.mock('../Components/dashboard/VaultDashboard', () => ({
  default: (props) => mockVaultDashboard(props),
}));

vi.mock('react-router-dom', async (importOriginal) => ({
  ...(await importOriginal()),
  useNavigate: () => vi.fn(),
}));

import { VaultDashboardRoute } from '../App';

beforeEach(() => {
  vi.clearAllMocks();
  mockIsDecoySession.mockReturnValue(false);
  mockVaultDashboard.mockReturnValue(null);
  mockUseVault.mockReturnValue({
    items: [REAL_ITEM],
    toggleFavorite: vi.fn(),
    updateItem: vi.fn(),
    deleteItem: vi.fn(),
    decryptItem: vi.fn(),
    canEdit: true,
  });
});

// VaultDashboard is lazy() in App.jsx, so the route suspends on first render;
// every assertion has to wait for that boundary to resolve.
const renderRoute = async () => {
  render(
    <Suspense fallback={null}>
      <VaultDashboardRoute />
    </Suspense>
  );
  await waitFor(() => expect(mockVaultDashboard).toHaveBeenCalled());
  return mockVaultDashboard.mock.calls[0][0];
};

describe('VaultDashboardRoute during a decoy session', () => {
  test('passes an empty item list to VaultDashboard, never the real one', async () => {
    mockIsDecoySession.mockReturnValue(true);

    const props = await renderRoute();

    expect(props.items).toEqual([]);
    // Belt and braces: no trace of the real row's identifiers crosses the
    // boundary, even nested somewhere else in the props.
    expect(JSON.stringify(props)).not.toContain('real-1');
  });

  test('a real session still receives the full item list', async () => {
    const props = await renderRoute();

    expect(props.items).toHaveLength(1);
    expect(props.items[0].item_id).toBe('real-1');
  });

  test('an undefined item list is normalised to an empty array, not passed through', async () => {
    // The route previously did `items={items || []}`; the shared hook has to
    // keep that normalisation or VaultDashboard receives undefined.
    mockUseVault.mockReturnValue({
      items: undefined,
      toggleFavorite: vi.fn(),
      updateItem: vi.fn(),
      deleteItem: vi.fn(),
      decryptItem: vi.fn(),
      canEdit: true,
    });

    const props = await renderRoute();

    expect(props.items).toEqual([]);
  });
});

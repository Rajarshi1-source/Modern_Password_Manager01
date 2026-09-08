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
const DECOY_ROW = { id: 'd1', item_id: 'decoy-1', encrypted_data: 'DECOY_CIPHERTEXT' };

const {
  mockIsDecoySession, mockGeneration, mockUseVault, mockVaultDashboard, mockDecoyLoad,
} = vi.hoisted(() => ({
  mockIsDecoySession: vi.fn(() => false),
  mockGeneration: vi.fn(() => 1),
  mockUseVault: vi.fn(),
  mockVaultDashboard: vi.fn(() => null),
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
  mockGeneration.mockReturnValue(1);
  // Reset the IMPLEMENTATION and not just the calls: `vi.clearAllMocks()`
  // leaves an earlier test's `mockResolvedValue` in place, so a mock encoding
  // a STATE has to be re-armed in the shared beforeEach or the file passes
  // under `-t` and fails as a whole.
  mockDecoyLoad.mockResolvedValue([]);
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
  test('passes the DECOY rows to VaultDashboard, never the real ones', async () => {
    mockIsDecoySession.mockReturnValue(true);
    mockDecoyLoad.mockResolvedValue([DECOY_ROW]);

    render(
      <Suspense fallback={null}>
        <VaultDashboardRoute />
      </Suspense>
    );
    // The rows arrive from an async store read, so the assertion has to wait
    // for the render that follows it rather than reading the first call.
    await waitFor(() => {
      const props = mockVaultDashboard.mock.calls.at(-1)[0];
      expect(props.items).toHaveLength(1);
      expect(props.items[0].item_id).toBe('decoy-1');
    });
    // Belt and braces: no trace of the real row's identifiers crosses the
    // boundary at ANY point, including the renders before the store resolved.
    const everyProp = JSON.stringify(mockVaultDashboard.mock.calls);
    expect(everyProp).not.toContain('real-1');
    // Full field match, not a substring of it: the decoy row's own
    // 'DECOY_CIPHERTEXT' ends in 'CIPHERTEXT', so a looser check passes or
    // fails for the wrong reason.
    expect(everyProp).not.toContain('"encrypted_data":"CIPHERTEXT"');
  });

  test('an unconfigured or unreadable decoy store renders empty, never the real list', async () => {
    // The fallback direction is load-bearing: [] is what shipped before decoy
    // contents existed, whereas falling back to the real list would be worse
    // than the problem this feature solves. `loadForSession` returns [] for
    // every failure, so this covers corruption and a wrong key too.
    mockIsDecoySession.mockReturnValue(true);
    mockDecoyLoad.mockResolvedValue([]);

    const props = await renderRoute();

    expect(props.items).toEqual([]);
    expect(JSON.stringify(mockVaultDashboard.mock.calls)).not.toContain('real-1');
  });

  test('the real item list is never even read from the decoy store', async () => {
    // A decoy session must still let VaultContext fetch /api/vault/ normally
    // (traffic analysis), so `items` stays populated -- it is only the DISPLAY
    // that is substituted. Pinning that the hook does not mutate `items`.
    mockIsDecoySession.mockReturnValue(true);
    mockDecoyLoad.mockResolvedValue([DECOY_ROW]);

    await renderRoute();

    expect(mockUseVault).toHaveBeenCalled();
    expect(mockDecoyLoad).toHaveBeenCalledWith(1);
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

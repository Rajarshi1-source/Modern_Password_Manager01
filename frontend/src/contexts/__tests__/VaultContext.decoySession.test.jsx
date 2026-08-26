import { describe, test, expect, vi, beforeEach } from 'vitest';
import { renderHook, act, waitFor } from '@testing-library/react';

/**
 * Decoy-session write gate on the mutation paths that never reach
 * `sessionVaultCrypto.encryptItem`.
 *
 * The envelope plan's §11.5 fix stops a decoy session from CORRUPTING a real
 * vault row by refusing inside `encryptItem` — which covers addItem/updateItem,
 * since both encrypt before writing. `deleteItem` and `toggleFavorite` do not:
 *   - `deleteItem` sends no ciphertext at all, so it never reaches that gate;
 *     an unguarded delete would destroy a genuine item in the one shared,
 *     server-side list, irreversibly.
 *   - `toggleFavorite` PATCHes non-secret metadata only, deliberately bypassing
 *     the re-encrypt path — but it still mutates a REAL item's persisted state.
 *
 * Both are now gated BEFORE the request and BEFORE any optimistic state change.
 * The surfaced messages are asserted to stay generic: they reach the UI, and a
 * message naming the duress feature would tell a coercer watching the screen
 * that it exists (plan §3.5).
 */
vi.mock('axios', () => ({
  default: {
    get: vi.fn(() => Promise.resolve({ data: { items: [] } })),
    post: vi.fn(() => Promise.resolve({ data: {} })),
    patch: vi.fn(() => Promise.resolve({ data: {} })),
    isCancel: () => false,
  },
}));

const { mockV2HasSessionKey, mockV3HasSessionKey, mockIsDecoySession } = vi.hoisted(() => ({
  mockV2HasSessionKey: vi.fn(() => true),
  mockV3HasSessionKey: vi.fn(() => false),
  mockIsDecoySession: vi.fn(() => false),
}));
vi.mock('../../services/sessionVaultCrypto', () => ({
  default: { hasSessionKey: mockV2HasSessionKey, isDecoySession: mockIsDecoySession },
}));
vi.mock('../../services/sessionVaultCryptoV3', () => ({
  default: { hasSessionKey: mockV3HasSessionKey },
}));
vi.mock('../../services/vaultEnvelope', () => ({
  encryptEnvelope: vi.fn(() => Promise.resolve('CIPHERTEXT')),
  decryptEnvelope: vi.fn(() => Promise.resolve({ name: 'x' })),
  hasVaultSessionKey: vi.fn(() => mockV2HasSessionKey() || mockV3HasSessionKey()),
}));
vi.mock('../../hooks/useAuth', () => ({
  useAuth: () => ({ isAuthenticated: true, user: { id: 1, email: 'u@e.com' } }),
}));
vi.mock('../../services/firebaseService', () => ({
  default: {
    initialize: vi.fn(), detachListeners: vi.fn(),
    listenForChanges: vi.fn(), syncItem: vi.fn(),
  },
}));
vi.mock('../../services/api', () => ({
  default: {
    get: vi.fn(() => Promise.resolve({ data: {} })),
    post: vi.fn(() => Promise.resolve({ data: {} })),
  },
}));

const { mockDeleteVaultItem, mockToggleFavorite } = vi.hoisted(() => ({
  mockDeleteVaultItem: vi.fn(() => Promise.resolve({ data: {} })),
  mockToggleFavorite: vi.fn(() => Promise.resolve({ data: {} })),
}));
vi.mock('../../services/vaultService', () => ({
  VaultService: class {
    checkInitialization() { return Promise.resolve({ initialized: false }); }
    clearKeys() {}
    deleteVaultItem(...args) { return mockDeleteVaultItem(...args); }
    toggleFavorite(...args) { return mockToggleFavorite(...args); }
  },
}));

import axios from 'axios';
import { VaultProvider, useVault } from '../VaultContext';

const wrapper = ({ children }) => <VaultProvider>{children}</VaultProvider>;

// One real row, so toggleFavorite finds a target and an optimistic flip is
// actually observable if the gate ever fails to fire.
const EXISTING_ITEM = {
  id: 42,
  item_id: 'real-1',
  item_type: 'password',
  encrypted_data: 'CIPHERTEXT',
  favorite: false,
};

const mountVault = async () => {
  const { result } = renderHook(() => useVault(), { wrapper });
  await waitFor(() => expect(axios.get).toHaveBeenCalled());
  await waitFor(() => expect(result.current.items).toHaveLength(1));
  return result;
};

beforeEach(() => {
  vi.clearAllMocks();
  mockV2HasSessionKey.mockReturnValue(true);
  mockV3HasSessionKey.mockReturnValue(false);
  mockIsDecoySession.mockReturnValue(false);
  axios.get.mockResolvedValue({ data: { items: [EXISTING_ITEM] } });
  mockDeleteVaultItem.mockResolvedValue({ data: {} });
  mockToggleFavorite.mockResolvedValue({ data: {} });
});

describe('VaultContext.deleteItem during a decoy session', () => {
  test('makes no request and leaves the item list untouched', async () => {
    mockIsDecoySession.mockReturnValue(true);
    const result = await mountVault();

    let caught;
    await act(async () => {
      caught = await result.current.deleteItem(42).catch((e) => e);
    });

    expect(caught).toBeInstanceOf(Error);
    expect(mockDeleteVaultItem).not.toHaveBeenCalled();
    // The real row must still be there -- no optimistic removal either.
    expect(result.current.items).toHaveLength(1);
    expect(result.current.items[0].id).toBe(42);
  });

  test('the surfaced message never names the duress feature', async () => {
    mockIsDecoySession.mockReturnValue(true);
    const result = await mountVault();

    let caught;
    await act(async () => {
      caught = await result.current.deleteItem(42).catch((e) => e);
    });

    expect(caught.message).toBe('Failed to delete item. Please try again.');
    expect(caught.message).not.toMatch(/decoy|duress|slot/i);
  });

  test('a real session still deletes normally', async () => {
    const result = await mountVault();

    await act(async () => {
      await result.current.deleteItem(42);
    });

    expect(mockDeleteVaultItem).toHaveBeenCalledWith(42);
    expect(result.current.items).toHaveLength(0);
  });
});

describe('VaultContext.toggleFavorite during a decoy session', () => {
  test('makes no request and applies no optimistic flip', async () => {
    mockIsDecoySession.mockReturnValue(true);
    const result = await mountVault();

    let caught;
    await act(async () => {
      caught = await result.current.toggleFavorite(42).catch((e) => e);
    });

    expect(caught).toBeInstanceOf(Error);
    expect(mockToggleFavorite).not.toHaveBeenCalled();
    // The gate runs BEFORE the optimistic setItems, so the flag is unchanged.
    expect(result.current.items[0].favorite).toBe(false);
  });

  test('the surfaced message never names the duress feature', async () => {
    mockIsDecoySession.mockReturnValue(true);
    const result = await mountVault();

    let caught;
    await act(async () => {
      caught = await result.current.toggleFavorite(42).catch((e) => e);
    });

    expect(caught.message).toBe('Failed to update favorite. Please try again.');
    expect(caught.message).not.toMatch(/decoy|duress|slot/i);
  });

  test('a real session still toggles normally', async () => {
    const result = await mountVault();

    await act(async () => {
      await result.current.toggleFavorite(42);
    });

    expect(mockToggleFavorite).toHaveBeenCalledWith(42, true);
    expect(result.current.items[0].favorite).toBe(true);
  });
});

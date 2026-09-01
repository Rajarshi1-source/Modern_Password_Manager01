import { describe, test, expect, vi, beforeEach } from 'vitest';
import { renderHook, act, waitFor } from '@testing-library/react';

/**
 * Queued sync work must never outlive the identity that created it.
 *
 * `syncVault` reads `pendingChangesRef`, not `pendingChanges` state, because it
 * runs from `setTimeout(() => syncVault(), 0)` and a state read there would be
 * stale. Clearing the STATE on an identity change therefore does not clear what
 * `syncVault` actually reads: the ref is refreshed by an effect on a later
 * commit, and a timer queued by the previous identity can fire inside that gap
 * and POST account A's ciphertext — and A's `deleted_items` ids, which the sync
 * endpoint applies as real deletions — into account B's vault, using B's
 * credentials.
 *
 * Two independent guards, tested separately here:
 *   - the identity effect drops the REF synchronously alongside the state, and
 *   - `syncVault` refuses any queue whose owner is not the identity now
 *     authenticated, which also covers logout, where the identity effect takes
 *     an early-return branch that clears nothing.
 */
vi.mock('axios', () => ({
  default: {
    get: vi.fn(() => Promise.resolve({ data: { items: [] } })),
    post: vi.fn(() => Promise.resolve({ data: {} })),
    patch: vi.fn(() => Promise.resolve({ data: {} })),
    isCancel: () => false,
  },
}));

const { mockV2HasSessionKey, mockIsDecoySession } = vi.hoisted(() => ({
  mockV2HasSessionKey: vi.fn(() => true),
  mockIsDecoySession: vi.fn(() => false),
}));
vi.mock('../../services/sessionVaultCrypto', () => ({
  default: { hasSessionKey: mockV2HasSessionKey, isDecoySession: mockIsDecoySession },
}));
vi.mock('../../services/sessionVaultCryptoV3', () => ({
  default: { hasSessionKey: vi.fn(() => false) },
}));
vi.mock('../../services/vaultEnvelope', () => ({
  encryptEnvelope: vi.fn(() => Promise.resolve('CIPHERTEXT')),
  decryptEnvelope: vi.fn(() => Promise.resolve({ name: 'x' })),
  hasVaultSessionKey: vi.fn(() => true),
}));

// Both halves of the auth state are controllable: the account-switch case needs
// a new user id, the logout case needs `isAuthenticated` to go false.
const { mockAuthState } = vi.hoisted(() => ({
  mockAuthState: vi.fn(() => ({ isAuthenticated: true, user: { id: 1, email: 'a@e.com' } })),
}));
vi.mock('../../hooks/useAuth', () => ({
  useAuth: () => mockAuthState(),
}));

vi.mock('../../services/firebaseService', () => ({
  default: {
    initialize: vi.fn(), detachListeners: vi.fn(),
    listenForChanges: vi.fn(), syncItem: vi.fn(),
  },
}));

const { mockOnionSyncVault } = vi.hoisted(() => ({
  mockOnionSyncVault: vi.fn(async () => ({
    data: { success: true, items: [] }, transport: 'clearnet', degraded: false,
  })),
}));
vi.mock('../../services/onionSyncService', () => ({
  default: { syncVault: mockOnionSyncVault },
  syncVault: mockOnionSyncVault,
}));

vi.mock('../../services/api', () => ({
  default: {
    get: vi.fn(() => Promise.resolve({ data: {} })),
    post: vi.fn(() => Promise.resolve({ data: {} })),
  },
}));

vi.mock('../../services/vaultService', () => ({
  VaultService: class {
    checkInitialization() { return Promise.resolve({ initialized: false }); }
    clearKeys() {}
  },
}));

import axios from 'axios';
import { VaultProvider, useVault } from '../VaultContext';

const wrapper = ({ children }) => <VaultProvider>{children}</VaultProvider>;

const USER_A = { isAuthenticated: true, user: { id: 1, email: 'a@e.com' } };
const USER_B = { isAuthenticated: true, user: { id: 2, email: 'b@e.com' } };
const LOGGED_OUT = { isAuthenticated: false, user: null };

beforeEach(() => {
  vi.clearAllMocks();
  mockV2HasSessionKey.mockReturnValue(true);
  mockIsDecoySession.mockReturnValue(false);
  mockAuthState.mockReturnValue(USER_A);
  axios.get.mockResolvedValue({ data: { items: [] } });
  axios.post.mockResolvedValue({
    data: { id: 7, item_id: 'a-item-1', favorite: false, created_at: 'T', updated_at: 'T' },
  });
});

/** Mounts as user A and leaves exactly one queued change owned by A. */
const mountAndQueueForA = async () => {
  const { result, rerender } = renderHook(() => useVault(), { wrapper });
  await waitFor(() => expect(axios.get).toHaveBeenCalled());

  await act(async () => {
    await result.current.addItem({ type: 'password', data: { name: 'A secret' } });
  });
  // The add itself must have gone out, so the queue below is genuinely A's.
  expect(axios.post).toHaveBeenCalled();
  return { result, rerender };
};

describe('VaultContext sync queue across an identity change', () => {
  test('a queue owned by A is not flushed after switching to B', async () => {
    const { result, rerender } = await mountAndQueueForA();

    mockAuthState.mockReturnValue(USER_B);
    await act(async () => { rerender(); });

    await act(async () => { await result.current.syncVault(); });

    expect(mockOnionSyncVault).not.toHaveBeenCalled();
  });

  test('a queue owned by A is not flushed after LOGOUT, which clears nothing', async () => {
    // The identity effect's `!isAuthenticated` branch returns early: it clears
    // items and the decrypted cache but neither the pendingChanges state nor
    // its ref. So this case is carried entirely by syncVault's owner guard,
    // and is the one that fails loudly if that guard is removed.
    const { result, rerender } = await mountAndQueueForA();

    mockAuthState.mockReturnValue(LOGGED_OUT);
    await act(async () => { rerender(); });

    await act(async () => { await result.current.syncVault(); });

    expect(mockOnionSyncVault).not.toHaveBeenCalled();
  });

  test('the same queue IS flushed while the owning identity is unchanged', async () => {
    // The negative half: the guards must not have made syncVault a no-op.
    const { result } = await mountAndQueueForA();

    await act(async () => { await result.current.syncVault(); });

    expect(mockOnionSyncVault).toHaveBeenCalledTimes(1);
    const [syncData] = mockOnionSyncVault.mock.calls[0];
    expect(syncData.items).toHaveLength(1);
  });
});

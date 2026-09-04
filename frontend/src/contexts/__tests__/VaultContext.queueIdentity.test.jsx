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

  test('a request STARTED by A and resolving after B signs in queues nothing', async () => {
    // The commit-time owner tag cannot save this case on its own: the late
    // append happens after the identity effect cleared the queue, so the tag
    // would label A's work as B-owned and syncVault's owner check would pass
    // it. The initiating identity has to be captured when the call starts.
    const { result, rerender } = renderHook(() => useVault(), { wrapper });
    await waitFor(() => expect(axios.get).toHaveBeenCalled());

    let resolvePost;
    axios.post.mockReturnValueOnce(new Promise((resolve) => { resolvePost = resolve; }));

    let addPromise;
    await act(async () => {
      addPromise = result.current.addItem({ type: 'password', data: { name: 'A secret' } });
    });

    // B signs in while A's POST is still in flight.
    mockAuthState.mockReturnValue(USER_B);
    await act(async () => { rerender(); });

    await act(async () => {
      resolvePost({ data: { id: 7, item_id: 'a-item-1', favorite: false } });
      await addPromise;
    });

    await act(async () => { await result.current.syncVault(); });

    expect(mockOnionSyncVault).not.toHaveBeenCalled();
  });

  test('a sync STARTED by A does not apply its response or clear the queue after B signs in', async () => {
    // The owner check runs BEFORE the request. If B signs in while A's sync is
    // in flight, applying A's response writes A's server state into B's list,
    // and the setPendingChanges([]) that follows discards work B queued since.
    const { result, rerender } = await mountAndQueueForA();

    let resolveSync;
    mockOnionSyncVault.mockReturnValueOnce(new Promise((r) => { resolveSync = r; }));

    let syncPromise;
    await act(async () => { syncPromise = result.current.syncVault(); });
    await waitFor(() => expect(mockOnionSyncVault).toHaveBeenCalled());

    mockAuthState.mockReturnValue(USER_B);
    await act(async () => { rerender(); });

    await act(async () => {
      resolveSync({
        data: { success: true, items: [{
          id: 99, item_id: 'a-server-item', item_type: 'password',
          encrypted_data: 'A-CIPHERTEXT', favorite: false,
        }], deleted_items: [] },
        transport: 'clearnet', degraded: false,
      });
      await syncPromise;
    });

    // A's server items must not land in B's list.
    expect(result.current.items.some((i) => i.item_id === 'a-server-item')).toBe(false);

  });

  test("A's late sync response does not wipe work B queued after the switch", async () => {
    // The SECOND half of the same guard. Asserting only that A's items are not
    // applied leaves a regression that still runs `setPendingChanges([])` in
    // the stale continuation -- which would silently discard whatever B has
    // queued since. A's OWN queue is not the thing at risk here: the identity
    // effect drops that legitimately (§29.1). B's is.
    const { result, rerender } = await mountAndQueueForA();

    let resolveSync;
    mockOnionSyncVault.mockReturnValueOnce(new Promise((r) => { resolveSync = r; }));
    let syncPromise;
    await act(async () => { syncPromise = result.current.syncVault(); });
    await waitFor(() => expect(mockOnionSyncVault).toHaveBeenCalled());

    // B signs in and queues work of their own while A's sync is still open.
    mockAuthState.mockReturnValue(USER_B);
    await act(async () => { rerender(); });
    axios.post.mockResolvedValue({
      data: { id: 8, item_id: 'b-item-1', favorite: false, created_at: 'T', updated_at: 'T' },
    });
    await act(async () => {
      await result.current.addItem({ type: 'password', data: { name: 'B secret' } });
    });

    // Now A's sync finally comes back.
    await act(async () => {
      resolveSync({
        data: { success: true, items: [], deleted_items: [] },
        transport: 'clearnet', degraded: false,
      });
      await syncPromise;
    });

    // B's queued item survived and is still flushable.
    mockOnionSyncVault.mockClear();
    await act(async () => { await result.current.syncVault(); });

    expect(mockOnionSyncVault).toHaveBeenCalledTimes(1);
    const [syncData] = mockOnionSyncVault.mock.calls[0];
    expect(syncData.items).toHaveLength(1);
    expect(syncData.items[0].item_id).toBe('b-item-1');
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

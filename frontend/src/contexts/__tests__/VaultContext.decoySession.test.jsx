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

const {
  mockV2HasSessionKey, mockV3HasSessionKey, mockIsDecoySession, mockEncryptDecoyItem,
} = vi.hoisted(() => ({
  mockV2HasSessionKey: vi.fn(() => true),
  mockV3HasSessionKey: vi.fn(() => false),
  mockIsDecoySession: vi.fn(() => false),
  // Stubbed because the real one needs a live session key; these tests are
  // about the ROUTING of a decoy write, not about the crypto itself (that is
  // covered in sessionVaultCrypto.decoyPrimitives.test.js).
  mockEncryptDecoyItem: vi.fn(async () => 'SEALED'),
}));
// Spread the REAL module rather than hand-listing what the context happens to
// call. Two reasons, both learned the hard way. A hand-written mock silently
// omits anything added later -- adding one `isDecoySession()` call site broke
// six unrelated tests in this suite. And `DECOY_WRITE_REFUSAL` must be the
// genuine exported constant: re-typing the literal here would make the
// assertions below compare the mock against itself, which is exactly the
// self-referential test the envelope plan's §39.3/§40.1 records.
vi.mock('../../services/sessionVaultCrypto', async (importOriginal) => {
  const actual = await importOriginal();
  return {
    ...actual,
    default: {
      ...actual.default,
      hasSessionKey: mockV2HasSessionKey,
      isDecoySession: mockIsDecoySession,
      encryptDecoyItem: mockEncryptDecoyItem,
    },
  };
});
// The decoy store is where a decoy-session mutation now LANDS. Mocked so these
// tests keep asserting the property they were written for -- that no request
// reaches the real vault -- independently of whether the store itself succeeds.
const { mockDecoyLoad, mockDecoySave, mockDecoyAddRow } = vi.hoisted(() => ({
  mockDecoyLoad: vi.fn(async () => []),
  mockDecoySave: vi.fn(async () => true),
  mockDecoyAddRow: vi.fn(async () => true),
}));
// `mutate` keeps the real module's read-modify-write SHAPE (load, apply the
// caller's mutator, save) rather than being a bare stub, so the assertions
// below can still inspect the rows actually handed to the store. Its
// serialization and session-generation binding are the real module's job and
// are covered in decoyVaultStore.test.js.
const mockDecoyMutate = vi.fn(async (userId, mutator) => {
  const rows = await mockDecoyLoad(userId);
  return mockDecoySave(userId, mutator(rows));
});
vi.mock('../../services/hiddenVault/decoyVaultStore', () => ({
  default: {
    loadForSession: mockDecoyLoad,
    saveForSession: mockDecoySave,
    mutate: (...args) => mockDecoyMutate(...args),
    addRowForSession: (...args) => mockDecoyAddRow(...args),
  },
  loadForSession: mockDecoyLoad,
  saveForSession: mockDecoySave,
}));
vi.mock('../../services/sessionVaultCryptoV3', () => ({
  default: { hasSessionKey: mockV3HasSessionKey },
}));
vi.mock('../../services/vaultEnvelope', () => ({
  encryptEnvelope: vi.fn(() => Promise.resolve('CIPHERTEXT')),
  decryptEnvelope: vi.fn(() => Promise.resolve({ name: 'x' })),
  hasVaultSessionKey: vi.fn(() => mockV2HasSessionKey() || mockV3HasSessionKey()),
}));
const { mockUseAuthUser } = vi.hoisted(() => ({
  mockUseAuthUser: vi.fn(() => ({ id: 1, email: 'u@e.com' })),
}));
vi.mock('../../hooks/useAuth', () => ({
  useAuth: () => ({ isAuthenticated: true, user: mockUseAuthUser() }),
}));
vi.mock('../../services/firebaseService', () => ({
  default: {
    initialize: vi.fn(), detachListeners: vi.fn(),
    listenForChanges: vi.fn(), syncItem: vi.fn(),
  },
}));
const { mockOnionSyncVault } = vi.hoisted(() => ({
  mockOnionSyncVault: vi.fn(async () => ({ data: {}, transport: 'clearnet', degraded: false })),
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
import api from '../../services/api';
import { DECOY_WRITE_REFUSAL } from '../../services/sessionVaultCrypto';
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
  const { result, rerender } = renderHook(() => useVault(), { wrapper });
  await waitFor(() => expect(axios.get).toHaveBeenCalled());
  await waitFor(() => expect(result.current.items).toHaveLength(1));
  return { result, rerender };
};

beforeEach(() => {
  vi.clearAllMocks();
  mockV2HasSessionKey.mockReturnValue(true);
  mockV3HasSessionKey.mockReturnValue(false);
  mockIsDecoySession.mockReturnValue(false);
  mockUseAuthUser.mockReturnValue({ id: 1, email: 'u@e.com' });
  axios.get.mockResolvedValue({ data: { items: [EXISTING_ITEM] } });
  mockDecoyLoad.mockResolvedValue([]);
  // Reset the IMPLEMENTATION, not just the call history: `vi.clearAllMocks()`
  // leaves a `mockResolvedValue(false)` set by an earlier test in place, so a
  // mock that encodes a STATE has to be re-armed here or the file passes under
  // `-t` and fails as a whole.
  mockDecoySave.mockResolvedValue(true);
  mockDecoyAddRow.mockResolvedValue(true);
  mockEncryptDecoyItem.mockResolvedValue('SEALED');
  mockDeleteVaultItem.mockResolvedValue({ data: {} });
  mockToggleFavorite.mockResolvedValue({ data: {} });
  api.post.mockResolvedValue({ data: { backup_id: 'b-1' } });
});

describe('VaultContext.deleteItem during a decoy session', () => {
  test('makes no request and leaves the REAL item list untouched', async () => {
    mockIsDecoySession.mockReturnValue(true);
    const { result } = await mountVault();

    await act(async () => {
      await result.current.deleteItem(42).catch((e) => e);
    });

    // The property under test is not "it throws" -- a decoy delete now
    // SUCCEEDS against the local store. What must never happen is a DELETE
    // against the one shared, server-side list, which would destroy a genuine
    // item irreversibly.
    expect(mockDeleteVaultItem).not.toHaveBeenCalled();
    // The real row must still be there -- no optimistic removal either.
    expect(result.current.items).toHaveLength(1);
    expect(result.current.items[0].id).toBe(42);
  });

  test('a store failure surfaces the shared refusal string, never a named one', async () => {
    mockIsDecoySession.mockReturnValue(true);
    mockDecoySave.mockResolvedValue(false);
    const { result } = await mountVault();

    let caught;
    await act(async () => {
      caught = await result.current.deleteItem(42).catch((e) => e);
    });

    // Compared against the module's own constant, not a copy of the literal.
    // Every decoy-session write failure must emit ONE byte-identical string:
    // it reaches the screen a coercer is watching, so two different messages
    // would tell them which layer declined.
    expect(caught.message).toBe(DECOY_WRITE_REFUSAL);
    expect(caught.message).not.toMatch(/decoy|duress|slot/i);
  });

  test('a working store removes the row locally and still sends no request', async () => {
    mockIsDecoySession.mockReturnValue(true);
    mockDecoyLoad.mockResolvedValue([
      { id: 'd1', item_id: 'decoy-1', encrypted_data: 'X' },
      { id: 'd2', item_id: 'decoy-2', encrypted_data: 'Y' },
    ]);
    const { result } = await mountVault();

    await act(async () => {
      await result.current.deleteItem('d1');
    });

    expect(mockDeleteVaultItem).not.toHaveBeenCalled();
    // Asserting the VALUE handed to the store, not merely that it was called:
    // a negative control that only checks which branch ran can pass for the
    // wrong reason (envelope plan §34.1).
    const [, savedRows] = mockDecoySave.mock.calls[0];
    expect(savedRows.map((r) => r.id)).toEqual(['d2']);
    // The REAL list is untouched -- a decoy delete must never reach it.
    expect(result.current.items).toHaveLength(1);
    expect(result.current.items[0].id).toBe(42);
  });

  test('a real session still deletes normally', async () => {
    const { result } = await mountVault();

    await act(async () => {
      await result.current.deleteItem(42);
    });

    expect(mockDeleteVaultItem).toHaveBeenCalledWith(42);
    expect(result.current.items).toHaveLength(0);
  });
});

describe('VaultContext.toggleFavorite during a decoy session', () => {
  test('makes no request and applies no optimistic flip to the REAL list', async () => {
    mockIsDecoySession.mockReturnValue(true);
    const { result } = await mountVault();

    await act(async () => {
      await result.current.toggleFavorite(42).catch((e) => e);
    });

    expect(mockToggleFavorite).not.toHaveBeenCalled();
    // The decoy branch returns before the optimistic setItems, so a real
    // item's flag is unchanged whether the store write succeeded or not.
    expect(result.current.items[0].favorite).toBe(false);
  });

  test('a store failure surfaces the shared refusal string, never a named one', async () => {
    mockIsDecoySession.mockReturnValue(true);
    mockDecoySave.mockResolvedValue(false);
    const { result } = await mountVault();

    let caught;
    await act(async () => {
      caught = await result.current.toggleFavorite(42).catch((e) => e);
    });

    // Byte-identical to deleteItem's above, and to encryptItem's, by
    // construction: all three read the same exported constant.
    expect(caught.message).toBe(DECOY_WRITE_REFUSAL);
    expect(caught.message).not.toMatch(/decoy|duress|slot/i);
  });

  test('an edit pins the generation it encrypted under', async () => {
    // updateItem encrypts, then queues the mutation. The store must be told
    // WHICH generation the ciphertext belongs to, or a lock plus a second
    // decoy unlock in the gap writes an unreadable row.
    mockIsDecoySession.mockReturnValue(true);
    const { result } = await mountVault();

    await act(async () => {
      await result.current.updateItem({ id: 'd1', data: { name: 'x' } }).catch(() => {});
    });

    // Third argument is the pinned generation, and it must be the value read
    // BEFORE encryptDecoyItem ran -- asserted as a real number rather than
    // merely "defined", since undefined would silently disable the guard.
    const [, , passedGeneration] = mockDecoyMutate.mock.calls[0];
    expect(typeof passedGeneration).toBe('number');
  });

  test('a working store flips the decoy row and still sends no PATCH', async () => {
    mockIsDecoySession.mockReturnValue(true);
    mockDecoyLoad.mockResolvedValue([{ id: 'd1', item_id: 'decoy-1', favorite: false }]);
    const { result } = await mountVault();

    await act(async () => {
      await result.current.toggleFavorite('d1');
    });

    expect(mockToggleFavorite).not.toHaveBeenCalled();
    const [, savedRows] = mockDecoySave.mock.calls[0];
    expect(savedRows[0].favorite).toBe(true);
    expect(result.current.items[0].favorite).toBe(false);
  });

  test('a real session still toggles normally', async () => {
    const { result } = await mountVault();

    await act(async () => {
      await result.current.toggleFavorite(42);
    });

    expect(mockToggleFavorite).toHaveBeenCalledWith(42, true);
    expect(result.current.items[0].favorite).toBe(true);
  });
});

describe('VaultContext backup paths during a decoy session', () => {
  test('restoreBackup makes no request and does not refresh the item list', async () => {
    mockIsDecoySession.mockReturnValue(true);
    const { result } = await mountVault();
    // Baseline: mountVault already did the initial GET. A refreshItems()
    // triggered by an unguarded restore would add another one, so pin the
    // count rather than asserting "never called".
    const getCallsBefore = axios.get.mock.calls.length;

    let caught;
    await act(async () => {
      caught = await result.current.restoreBackup('backup-1').catch((e) => e);
    });

    expect(caught).toBeInstanceOf(Error);
    // The server side of this call can wipe and overwrite the REAL vault
    // (backup_views.py `_restore_from_items`), so the request must not go out
    // at all -- this is the highest-blast-radius path the decoy flag guards.
    expect(api.post).not.toHaveBeenCalled();
    expect(axios.get.mock.calls.length).toBe(getCallsBefore);
    expect(caught.message).toBe('Failed to restore backup. Please try again.');
    expect(caught.message).not.toMatch(/decoy|duress|slot/i);
  });

  test('createBackup makes no request', async () => {
    mockIsDecoySession.mockReturnValue(true);
    const { result } = await mountVault();

    let caught;
    await act(async () => {
      caught = await result.current.createBackup().catch((e) => e);
    });

    expect(caught).toBeInstanceOf(Error);
    expect(api.post).not.toHaveBeenCalled();
    expect(caught.message).toBe('Failed to create backup. Please try again.');
    expect(caught.message).not.toMatch(/decoy|duress|slot/i);
  });

  test('getBackups returns an empty list and makes no request', async () => {
    // The DISPLAY half of the backup surface. getBackups is a read, so it was
    // left outside the write gate -- but BackupManager renders each row's
    // name, timestamp and item_count on mount, and a decoy session showing a
    // near-empty vault beside "247 items backed up" contradicts itself in
    // front of the coercer.
    mockIsDecoySession.mockReturnValue(true);
    api.get.mockResolvedValue({ data: [
      { id: 'b-1', name: 'Full vault', created_at: '2026-01-01', item_count: 247 },
    ] });
    const { result } = await mountVault();

    let backups;
    await act(async () => { backups = await result.current.getBackups(); });

    // Empty, not an error: a failure only on this screen would be its own
    // tell, whereas "no backups yet" is entirely ordinary.
    expect(backups).toEqual([]);
    expect(api.get).not.toHaveBeenCalledWith('/vault/backups/');
    // And nothing about the real vault reached the caller.
    expect(JSON.stringify(backups)).not.toMatch(/247|Full vault/);
  });

  test('a real session still lists backups', async () => {
    api.get.mockResolvedValue({ data: [{ id: 'b-1', name: 'Full vault', item_count: 247 }] });
    const { result } = await mountVault();

    let backups;
    await act(async () => { backups = await result.current.getBackups(); });

    expect(api.get).toHaveBeenCalledWith('/vault/backups/');
    expect(backups).toHaveLength(1);
  });

  test('a real session still creates and restores normally', async () => {
    const { result } = await mountVault();

    await act(async () => {
      await result.current.createBackup();
    });
    expect(api.post).toHaveBeenCalledWith(
      '/vault/create_backup/',
      expect.objectContaining({ name: expect.any(String) })
    );

    api.post.mockClear();
    await act(async () => {
      await result.current.restoreBackup('backup-1');
    });
    expect(api.post).toHaveBeenCalledWith('/vault/restore_backup/backup-1/');
  });
});

describe('VaultContext.syncVault during a decoy session', () => {
  // A distinct hole from the add/update/delete/favorite/backup gates. Those
  // stop a decoy session CREATING changes -- but handleLockVault does not
  // clear pendingChanges, so work queued in an earlier REAL session survives
  // lock -> decoy unlock and would be flushed from here, including
  // deleted_items, which the sync endpoint applies as real deletions.
  const queueOneChange = async (result) => {
    mockIsDecoySession.mockReturnValue(false);
    await act(async () => {
      await result.current.deleteItem(42);
    });
    expect(mockDeleteVaultItem).toHaveBeenCalled();
  };

  test('does not flush changes queued by an earlier real session', async () => {
    const { result } = await mountVault();
    // Queue a deletion as the REAL session would...
    await queueOneChange(result);

    // ...then the session becomes a decoy one (lock + decoy unlock), which
    // leaves pendingChanges untouched.
    mockIsDecoySession.mockReturnValue(true);
    mockOnionSyncVault.mockClear();

    await act(async () => {
      await result.current.syncVault();
    });

    expect(mockOnionSyncVault).not.toHaveBeenCalled();
  });

  test('a real session still flushes the same queued changes', async () => {
    const { result } = await mountVault();
    await queueOneChange(result);

    mockOnionSyncVault.mockClear();
    await act(async () => {
      await result.current.syncVault();
    });

    // Proves the gate is what stopped the sync above, not an empty queue.
    expect(mockOnionSyncVault).toHaveBeenCalled();
  });
});

describe('pendingChanges is scoped to the authenticated identity', () => {
  test('a queue built by user A is not flushed by user B', async () => {
    // The decoy gate deliberately PRESERVES the queue so the real session can
    // flush it later. That is only safe if the queue cannot outlive the
    // identity that built it: otherwise A's ciphertext would be POSTed into
    // B's vault and A's item_ids deleted from it. `items`/`decryptedItems`
    // were already cleared on an identity change; `pendingChanges` was not.
    const { result, rerender } = await mountVault();
    await act(async () => {
      await result.current.deleteItem(42);
    });
    expect(mockDeleteVaultItem).toHaveBeenCalled();

    // Switch identity: the provider's auth effect re-runs for a new user.id.
    mockUseAuthUser.mockReturnValue({ id: 2, email: 'b@e.com' });
    mockOnionSyncVault.mockClear();
    await act(async () => {
      rerender();
    });

    await act(async () => {
      await result.current.syncVault();
    });

    expect(mockOnionSyncVault).not.toHaveBeenCalled();
  });
});

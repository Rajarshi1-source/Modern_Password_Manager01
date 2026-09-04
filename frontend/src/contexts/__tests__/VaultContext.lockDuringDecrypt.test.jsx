import { describe, test, expect, vi, beforeEach } from 'vitest';
import { renderHook, act, waitFor } from '@testing-library/react';

/**
 * A vault lock must invalidate a decrypt that is already in flight.
 *
 * `decryptItem` awaits a real AES-GCM decrypt, then caches the plaintext into
 * `decryptedItems` and returns it. `lockVault()` can land inside that window —
 * it clears the session key and the item list, but nothing stopped the pending
 * continuation from writing the plaintext it already held into the cache. Since
 * `decryptItem` reads that cache before anything else, a later call kept
 * serving the secret from a locked vault.
 *
 * Two guards, tested separately:
 *   - the continuation compares the session generation captured before the
 *     await and refuses to cache or return plaintext when it moved, and
 *   - `handleLockVault` clears `decryptedItems` alongside `items`.
 */
vi.mock('axios', () => ({
  default: {
    get: vi.fn(() => Promise.resolve({ data: { items: [] } })),
    post: vi.fn(() => Promise.resolve({ data: {} })),
    patch: vi.fn(() => Promise.resolve({ data: {} })),
    isCancel: () => false,
  },
}));

const { mockHasSessionKey, mockIsDecoySession, mockGeneration, mockClearSessionKey } =
  vi.hoisted(() => ({
    mockHasSessionKey: vi.fn(() => true),
    mockIsDecoySession: vi.fn(() => false),
    mockGeneration: vi.fn(() => 5),
    mockClearSessionKey: vi.fn(),
  }));
vi.mock('../../services/sessionVaultCrypto', () => ({
  default: {
    hasSessionKey: mockHasSessionKey,
    isDecoySession: mockIsDecoySession,
    currentSessionGeneration: mockGeneration,
    clearSessionKey: mockClearSessionKey,
  },
}));
vi.mock('../../services/sessionVaultCryptoV3', () => ({
  default: { hasSessionKey: vi.fn(() => false), clearSessionKey: vi.fn() },
}));

const { mockDecryptEnvelope } = vi.hoisted(() => ({
  mockDecryptEnvelope: vi.fn(() => Promise.resolve({ name: 'x' })),
}));
vi.mock('../../services/vaultEnvelope', () => ({
  encryptEnvelope: vi.fn(() => Promise.resolve('CIPHERTEXT')),
  decryptEnvelope: mockDecryptEnvelope,
  hasVaultSessionKey: vi.fn(() => true),
}));

vi.mock('../../hooks/useAuth', () => ({
  useAuth: () => ({ isAuthenticated: true, user: { id: 1, email: 'a@e.com' } }),
}));
vi.mock('../../services/firebaseService', () => ({
  default: {
    initialize: vi.fn(), detachListeners: vi.fn(),
    listenForChanges: vi.fn(), syncItem: vi.fn(),
  },
}));
vi.mock('../../services/onionSyncService', () => ({
  default: { syncVault: vi.fn() },
  syncVault: vi.fn(),
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

const REAL_ITEM = {
  id: 42,
  item_id: 'real-item',
  item_type: 'password',
  encrypted_data: 'REAL-CIPHERTEXT',
  favorite: false,
};

beforeEach(() => {
  vi.clearAllMocks();
  mockHasSessionKey.mockReturnValue(true);
  mockIsDecoySession.mockReturnValue(false);
  mockGeneration.mockReturnValue(5);
  mockDecryptEnvelope.mockResolvedValue({ name: 'x' });
  axios.get.mockResolvedValue({ data: { items: [REAL_ITEM] } });
});

const mountWithItem = async () => {
  const { result } = renderHook(() => useVault(), { wrapper });
  await waitFor(() => expect(result.current.items).toHaveLength(1));
  return result;
};

describe('VaultContext.decryptItem across a vault lock', () => {
  test('a decrypt in flight when the vault locks returns no plaintext and caches none', async () => {
    let resolveDecrypt;
    mockDecryptEnvelope.mockReturnValue(new Promise((r) => { resolveDecrypt = r; }));

    const result = await mountWithItem();

    let pending;
    await act(async () => { pending = result.current.decryptItem('real-item'); });
    await waitFor(() => expect(mockDecryptEnvelope).toHaveBeenCalled());

    // The vault locks mid-decrypt: clearSessionKey() nulls the key AND bumps
    // the generation, which is what this continuation compares against.
    await act(async () => { result.current.lockVault(); });
    mockHasSessionKey.mockReturnValue(false);
    mockGeneration.mockReturnValue(6);

    let out;
    await act(async () => {
      resolveDecrypt({ name: 'REAL SECRET', password: 'hunter2' });
      out = await pending;
    });

    // No plaintext handed back...
    expect(out.data).toBeUndefined();
    expect(out._decryptionFailed).toBe(true);
    expect(JSON.stringify(out)).not.toMatch(/hunter2|REAL SECRET/);

    // ...and none cached. A second call cannot serve it from memory: the
    // cache lookup at the top of decryptItem is the first thing that would
    // return it, and here the call falls through to "Item not found" instead,
    // because the lock also emptied the list. Asserted as "never yields the
    // secret", which is the property that matters however it fails.
    mockDecryptEnvelope.mockClear();
    let second;
    await act(async () => {
      second = await result.current.decryptItem('real-item').catch((e) => e);
    });
    expect(second).toBeInstanceOf(Error);
    expect(JSON.stringify(second?.data ?? {})).not.toMatch(/hunter2|REAL SECRET/);
    expect(mockDecryptEnvelope).not.toHaveBeenCalled();
  });

  test('locking clears already-decrypted plaintext from the cache', async () => {
    mockDecryptEnvelope.mockResolvedValue({ name: 'REAL SECRET', password: 'hunter2' });
    const result = await mountWithItem();

    await act(async () => { await result.current.decryptItem('real-item'); });
    // Cached: a second call is served without re-decrypting.
    mockDecryptEnvelope.mockClear();
    await act(async () => { await result.current.decryptItem('real-item'); });
    expect(mockDecryptEnvelope).not.toHaveBeenCalled();

    await act(async () => { result.current.lockVault(); });

    // The cache went with the item list, so nothing is served from it.
    expect(result.current.items).toHaveLength(0);
    mockDecryptEnvelope.mockClear();
    let after;
    await act(async () => {
      after = await result.current.decryptItem('real-item').catch((e) => e);
    });
    // Asserted on the RETURNED VALUE, not on whether decryptEnvelope ran: the
    // cache lookup is the FIRST thing decryptItem does, so an uncleared cache
    // would return the secret without ever calling decryptEnvelope -- and a
    // "was not called" assertion would pass for the wrong reason. What must be
    // true is that no plaintext comes back.
    expect(after).toBeInstanceOf(Error);
    expect(JSON.stringify(after?.data ?? {})).not.toMatch(/hunter2|REAL SECRET/);
  });

  test('an unlocked, unchanged session still decrypts and caches normally', async () => {
    // The negative half: the guards must not have disabled on-demand decrypt.
    mockDecryptEnvelope.mockResolvedValue({ name: 'REAL SECRET' });
    const result = await mountWithItem();

    let out;
    await act(async () => { out = await result.current.decryptItem('real-item'); });

    expect(out.data).toEqual({ name: 'REAL SECRET' });
    expect(out._decrypted).toBe(true);
  });
});

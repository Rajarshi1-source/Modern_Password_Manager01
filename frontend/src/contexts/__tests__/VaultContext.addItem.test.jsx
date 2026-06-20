import { describe, test, expect, vi, beforeEach } from 'vitest';
import { renderHook, act, waitFor } from '@testing-library/react';

/**
 * PR G — VaultContext.addItem crypto consolidation.
 *
 * Pins the security contract of the add write path after retiring the dead
 * vaultService.saveVaultItem path:
 *   1. It encrypts via the shared sessionVaultCrypto envelope (encryptEnvelope).
 *   2. It POSTs ONLY the ciphertext to /api/vault/ — the plaintext `data`
 *      never leaves the browser.
 *   3. It is gated on a live session key (sessionVaultCrypto.hasSessionKey()).
 */
vi.mock('axios', () => ({
  default: {
    get: vi.fn(() => Promise.resolve({ data: { items: [] } })),
    post: vi.fn(() => Promise.resolve({ data: { id: 7, item_id: 'new-1', created_at: 'now', updated_at: 'now' } })),
    patch: vi.fn(() => Promise.resolve({ data: {} })),
    isCancel: () => false,
  },
}));
vi.mock('../../services/sessionVaultCrypto', () => ({
  default: { hasSessionKey: vi.fn(() => true) },
}));
vi.mock('../../services/vaultEnvelope', () => ({
  encryptEnvelope: vi.fn(() => Promise.resolve('CIPHERTEXT')),
  decryptEnvelope: vi.fn(() => Promise.resolve({ name: 'x' })),
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
  default: { get: vi.fn(() => Promise.resolve({ data: {} })), post: vi.fn(() => Promise.resolve({ data: {} })) },
}));
vi.mock('../../services/vaultService', () => ({
  VaultService: class {
    checkInitialization() { return Promise.resolve({ initialized: false }); }
    clearKeys() {}
  },
}));

import axios from 'axios';
import sessionVaultCrypto from '../../services/sessionVaultCrypto';
import { encryptEnvelope } from '../../services/vaultEnvelope';
import { VaultProvider, useVault } from '../VaultContext';

const wrapper = ({ children }) => <VaultProvider>{children}</VaultProvider>;

const ITEM = {
  item_id: 'new-1',
  type: 'password',
  favorite: false,
  data: { name: 'New', password: 'super-secret', website: 'x.com' },
};

beforeEach(() => {
  vi.clearAllMocks();
  sessionVaultCrypto.hasSessionKey.mockReturnValue(true);
  axios.post.mockResolvedValue({ data: { id: 7, item_id: 'new-1', created_at: 'now', updated_at: 'now' } });
  axios.get.mockResolvedValue({ data: { items: [] } });
  encryptEnvelope.mockResolvedValue('CIPHERTEXT');
});

describe('VaultContext.addItem (PR G)', () => {
  test('encrypts via encryptEnvelope and POSTs only ciphertext (never plaintext)', async () => {
    const { result } = renderHook(() => useVault(), { wrapper });
    await waitFor(() => expect(axios.get).toHaveBeenCalled()); // mount refresh settled

    await act(async () => {
      await result.current.addItem(ITEM);
    });

    expect(encryptEnvelope).toHaveBeenCalledWith(ITEM.data);
    expect(axios.post).toHaveBeenCalledTimes(1);
    const [url, payload] = axios.post.mock.calls[0];
    expect(url).toBe('/api/vault/');
    expect(payload).toEqual({
      item_type: 'password',
      item_id: 'new-1',
      encrypted_data: 'CIPHERTEXT',
      favorite: false,
    });
    // Critical: the plaintext secret must never be in the request body.
    expect(payload).not.toHaveProperty('data');
    expect(JSON.stringify(payload)).not.toContain('super-secret');
  });

  test('refuses to write (and never encrypts) when the vault is locked', async () => {
    sessionVaultCrypto.hasSessionKey.mockReturnValue(false);
    const { result } = renderHook(() => useVault(), { wrapper });
    await waitFor(() => expect(axios.get).toHaveBeenCalled());

    let caught;
    await act(async () => {
      caught = await result.current.addItem(ITEM).catch((e) => e);
    });

    expect(caught).toBeInstanceOf(Error);
    expect(caught.message).toMatch(/Unlock your vault/);
    expect(encryptEnvelope).not.toHaveBeenCalled();
    expect(axios.post).not.toHaveBeenCalled();
  });
});

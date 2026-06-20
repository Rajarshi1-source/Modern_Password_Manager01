import { describe, test, expect, vi, beforeEach } from 'vitest';
import { renderHook, act, waitFor } from '@testing-library/react';

/**
 * PR F — VaultContext.updateItem crypto unification.
 *
 * Pins the security contract of the dashboard's edit write path:
 *   1. It re-encrypts via the shared sessionVaultCrypto envelope (encryptEnvelope),
 *      NOT the dead vaultService.cryptoService.
 *   2. It PUTs ONLY the ciphertext to /api/vault/{id}/ — the plaintext `data`
 *      must never leave the browser.
 *   3. It is gated on a live session key (sessionVaultCrypto.hasSessionKey()).
 *
 * Every collaborator is mocked so no real WebCrypto/network is exercised.
 */
vi.mock('axios', () => ({
  default: {
    get: vi.fn(() => Promise.resolve({ data: { items: [] } })),
    patch: vi.fn(() => Promise.resolve({ data: { updated_at: '2026-06-19T00:00:00Z' } })),
    post: vi.fn(() => Promise.resolve({ data: {} })),
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
  id: 42,
  item_id: 'abc-123',
  type: 'password',
  favorite: false,
  data: { name: 'GitHub', password: 'super-secret', website: 'github.com' },
};

beforeEach(() => {
  vi.clearAllMocks();
  sessionVaultCrypto.hasSessionKey.mockReturnValue(true);
  axios.patch.mockResolvedValue({ data: { updated_at: '2026-06-19T00:00:00Z' } });
  axios.get.mockResolvedValue({ data: { items: [] } });
  encryptEnvelope.mockResolvedValue('CIPHERTEXT');
});

describe('VaultContext.updateItem (PR F)', () => {
  test('encrypts via encryptEnvelope and PATCHes only ciphertext (never plaintext)', async () => {
    const { result } = renderHook(() => useVault(), { wrapper });
    await waitFor(() => expect(axios.get).toHaveBeenCalled()); // mount refresh settled

    await act(async () => {
      await result.current.updateItem(ITEM);
    });

    expect(encryptEnvelope).toHaveBeenCalledWith(ITEM.data);
    expect(axios.patch).toHaveBeenCalledTimes(1);
    const [url, payload] = axios.patch.mock.calls[0];
    expect(url).toBe('/api/vault/42/');
    // Partial PATCH of ONLY the ciphertext — no `user` (would 400 on a full
    // PUT) and no `favorite` (owned by the metadata-only toggle).
    expect(payload).toEqual({ encrypted_data: 'CIPHERTEXT' });
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
      caught = await result.current.updateItem(ITEM).catch((e) => e);
    });

    expect(caught).toBeInstanceOf(Error);
    expect(caught.message).toMatch(/Unlock your vault/);
    expect(encryptEnvelope).not.toHaveBeenCalled();
    expect(axios.patch).not.toHaveBeenCalled();
  });
});

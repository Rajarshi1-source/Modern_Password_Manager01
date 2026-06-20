import { describe, test, expect, vi, beforeEach } from 'vitest';
import { renderHook, act, waitFor } from '@testing-library/react';

/**
 * PR G — vault lock clears the live session keys.
 *
 * After retiring the dead vaultService crypto path, vaultService.clearKeys()
 * is a no-op. handleLockVault must therefore clear the *real* session keys
 * (sessionVaultCrypto v2 + sessionVaultCryptoV3) so a manual/cross-tab lock
 * actually removes key material from memory, and the edit gate (canEdit) flips
 * to locked.
 */
vi.mock('axios', () => ({
  default: {
    get: vi.fn(() => Promise.resolve({ data: { items: [] } })),
    post: vi.fn(() => Promise.resolve({ data: {} })),
    patch: vi.fn(() => Promise.resolve({ data: {} })),
    isCancel: () => false,
  },
}));
vi.mock('../../services/sessionVaultCrypto', () => ({
  default: { hasSessionKey: vi.fn(() => true), clearSessionKey: vi.fn() },
}));
vi.mock('../../services/sessionVaultCryptoV3', () => ({
  default: { clearSessionKey: vi.fn() },
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

import sessionVaultCrypto from '../../services/sessionVaultCrypto';
import sessionVaultCryptoV3 from '../../services/sessionVaultCryptoV3';
import axios from 'axios';
import { VaultProvider, useVault } from '../VaultContext';

const wrapper = ({ children }) => <VaultProvider>{children}</VaultProvider>;

beforeEach(() => {
  vi.clearAllMocks();
  sessionVaultCrypto.hasSessionKey.mockReturnValue(true);
  axios.get.mockResolvedValue({ data: { items: [] } });
});

describe('VaultContext lock (PR G)', () => {
  test('lockVault clears both the v2 and v3 session keys and locks canEdit', async () => {
    const { result } = renderHook(() => useVault(), { wrapper });
    await waitFor(() => expect(axios.get).toHaveBeenCalled());
    // Unlocked to start (mocked hasSessionKey === true).
    expect(result.current.canEdit).toBe(true);

    act(() => {
      result.current.lockVault();
    });

    expect(sessionVaultCrypto.clearSessionKey).toHaveBeenCalledTimes(1);
    expect(sessionVaultCryptoV3.clearSessionKey).toHaveBeenCalledTimes(1);
    // Edit gate is locked after the keys are dropped.
    expect(result.current.canEdit).toBe(false);
  });
});

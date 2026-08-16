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
// Shared mock fns, hoisted above the `vi.mock` calls below so the
// `vaultEnvelope` mock's `hasVaultSessionKey` can delegate to the SAME
// `hasSessionKey` mocks the test body configures via
// `sessionVaultCrypto.hasSessionKey.mockReturnValue(...)` -- keeping the real
// module's "v2 OR v3" contract without duplicating mock state.
const { mockV2HasSessionKey, mockV3HasSessionKey } = vi.hoisted(() => ({
  mockV2HasSessionKey: vi.fn(() => true),
  mockV3HasSessionKey: vi.fn(() => false),
}));
vi.mock('../../services/sessionVaultCrypto', () => ({
  default: { hasSessionKey: mockV2HasSessionKey, clearSessionKey: vi.fn() },
}));
vi.mock('../../services/sessionVaultCryptoV3', () => ({
  default: { hasSessionKey: mockV3HasSessionKey, clearSessionKey: vi.fn() },
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
  // `vi.clearAllMocks()` clears call history but NOT configured return
  // values -- reset both explicitly so the v3-only test below can't leak
  // its `mockReturnValue(true)` into a later test that assumes v3 absent.
  sessionVaultCrypto.hasSessionKey.mockReturnValue(true);
  sessionVaultCryptoV3.hasSessionKey.mockReturnValue(false);
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

  test('canEdit is true for a v3-only session (v2 absent, v3 present)', async () => {
    // v2 init transiently failed at login, or v2 has been fully retired --
    // encryptEnvelope would still happily write via v3, so canEdit must not
    // report locked here.
    sessionVaultCrypto.hasSessionKey.mockReturnValue(false);
    sessionVaultCryptoV3.hasSessionKey.mockReturnValue(true);

    const { result } = renderHook(() => useVault(), { wrapper });
    await waitFor(() => expect(axios.get).toHaveBeenCalled());

    expect(result.current.canEdit).toBe(true);
  });
});

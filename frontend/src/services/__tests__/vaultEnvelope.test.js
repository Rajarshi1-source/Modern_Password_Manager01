import { describe, test, expect, vi, beforeEach } from 'vitest';

/**
 * PR E — vaultEnvelope helper.
 *
 * These tests pin the v2→v3 decrypt contract extracted (verbatim) from
 * App.jsx's VaultItemsSection.decryptOne, plus the encrypt delegation. Both
 * crypto layers are mocked so no real WebCrypto/session key is exercised.
 */
vi.mock('../sessionVaultCrypto', () => ({
  default: {
    decryptItem: vi.fn(),
    encryptItem: vi.fn(),
    hasSessionKey: vi.fn(),
  },
}));
vi.mock('../sessionVaultCryptoV3', () => ({
  default: {
    decryptItem: vi.fn(),
    hasSessionKey: vi.fn(),
  },
}));

import sessionVaultCrypto from '../sessionVaultCrypto';
import sessionVaultCryptoV3 from '../sessionVaultCryptoV3';
import { decryptEnvelope, encryptEnvelope } from '../vaultEnvelope';

beforeEach(() => {
  vi.clearAllMocks();
});

describe('decryptEnvelope', () => {
  test('returns the v2 result when v2 owns the envelope (no v3 fallback)', async () => {
    sessionVaultCrypto.decryptItem.mockResolvedValue({ name: 'GitHub', password: 'pw' });

    const out = await decryptEnvelope('v2-envelope');

    expect(out).toEqual({ name: 'GitHub', password: 'pw' });
    expect(sessionVaultCrypto.decryptItem).toHaveBeenCalledWith('v2-envelope');
    // v2 owned it, so the v3 layer must not be consulted at all.
    expect(sessionVaultCryptoV3.hasSessionKey).not.toHaveBeenCalled();
    expect(sessionVaultCryptoV3.decryptItem).not.toHaveBeenCalled();
  });

  test('falls back to v3 when v2 flags _legacyPlaintext and a v3 key is present', async () => {
    sessionVaultCrypto.decryptItem.mockResolvedValue({ _legacyPlaintext: true });
    sessionVaultCryptoV3.hasSessionKey.mockReturnValue(true);
    sessionVaultCryptoV3.decryptItem.mockResolvedValue({ name: 'Migrated', password: 'v3pw' });

    const out = await decryptEnvelope('v3-envelope');

    expect(out).toEqual({ name: 'Migrated', password: 'v3pw' });
    expect(sessionVaultCryptoV3.decryptItem).toHaveBeenCalledWith('v3-envelope');
  });

  test('keeps the v2 _legacyPlaintext result when the v3 fallback throws', async () => {
    const v2 = { _legacyPlaintext: true };
    sessionVaultCrypto.decryptItem.mockResolvedValue(v2);
    sessionVaultCryptoV3.hasSessionKey.mockReturnValue(true);
    sessionVaultCryptoV3.decryptItem.mockRejectedValue(new Error('v3 boom'));
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => {});

    const out = await decryptEnvelope('x');

    expect(out).toBe(v2);
    expect(warn).toHaveBeenCalled();
    warn.mockRestore();
  });

  test('does NOT call v3 when v2 is _legacyPlaintext but no v3 key is present', async () => {
    sessionVaultCrypto.decryptItem.mockResolvedValue({ _legacyPlaintext: true });
    sessionVaultCryptoV3.hasSessionKey.mockReturnValue(false);

    const out = await decryptEnvelope('x');

    expect(out).toEqual({ _legacyPlaintext: true });
    expect(sessionVaultCryptoV3.decryptItem).not.toHaveBeenCalled();
  });

  test('propagates when v2 decryption itself throws', async () => {
    sessionVaultCrypto.decryptItem.mockRejectedValue(new Error('tampered'));

    await expect(decryptEnvelope('x')).rejects.toThrow('tampered');
  });
});

describe('encryptEnvelope', () => {
  test('delegates to sessionVaultCrypto.encryptItem', async () => {
    sessionVaultCrypto.encryptItem.mockResolvedValue('sealed-envelope');
    const data = { name: 'New', password: 'secret' };

    const out = await encryptEnvelope(data);

    expect(out).toBe('sealed-envelope');
    expect(sessionVaultCrypto.encryptItem).toHaveBeenCalledWith(data);
    expect(sessionVaultCrypto.encryptItem).toHaveBeenCalledTimes(1);
  });
});

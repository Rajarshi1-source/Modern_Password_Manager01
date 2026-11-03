/**
 * The decoy guard on replacing the vault key: a decoy session never reaches the
 * real key, and answers a typed password as a wrong one, in about the same time.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import sessionVaultCrypto from '../sessionVaultCrypto';
import sessionVaultCryptoV3, { DEK_UNWRAP_FAILURE_MESSAGE } from '../sessionVaultCryptoV3';
import { replaceVaultKey } from '../vaultEnvelope';

vi.mock('argon2-browser', () => ({ ArgonType: { Argon2id: 2 }, hash: vi.fn() }));
vi.mock('axios', () => ({ default: { get: vi.fn(), put: vi.fn(), post: vi.fn() } }));

describe('replaceVaultKey', () => {
  beforeEach(() => vi.restoreAllMocks());

  it('passes through in a real session', async () => {
    vi.spyOn(sessionVaultCrypto, 'isDecoySession').mockReturnValue(false);
    const replace = vi.spyOn(sessionVaultCryptoV3, 'replaceVaultKey').mockResolvedValue({ dekId: 'new' });
    await expect(replaceVaultKey('pw', 'alice')).resolves.toEqual({ dekId: 'new' });
    expect(replace).toHaveBeenCalledWith('pw', 'alice');
  });

  it.each([[true], [false]])('refuses in a decoy session (typed password correct: %s)', async (correct) => {
    vi.spyOn(sessionVaultCrypto, 'isDecoySession').mockReturnValue(true);
    const replace = vi.spyOn(sessionVaultCryptoV3, 'replaceVaultKey');
    const verify = vi.spyOn(sessionVaultCryptoV3, 'verifyMasterPassword')
      .mockImplementation(async () => {
        if (!correct) throw new Error(DEK_UNWRAP_FAILURE_MESSAGE);
        return true;
      });
    await expect(replaceVaultKey('pw', 'alice')).rejects.toThrow(DEK_UNWRAP_FAILURE_MESSAGE);
    expect(verify).toHaveBeenCalledWith('pw'); // spends the derivation a wrong password would
    expect(replace).not.toHaveBeenCalled();
  });
});

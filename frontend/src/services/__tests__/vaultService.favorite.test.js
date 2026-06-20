import { describe, test, expect, vi } from 'vitest';
import { VaultService } from '../vaultService';

/**
 * PR A — favorite toggle.
 *
 * These tests pin the safety contract of VaultService.toggleFavorite:
 * it must issue a metadata-only PATCH to /vault/{id}/ carrying ONLY the
 * `favorite` flag, and never the encrypted payload. The axios instance is
 * stubbed so no network/encryption is exercised.
 */
describe('VaultService.toggleFavorite', () => {
  test('PATCHes /vault/{id}/ with only the favorite flag (no ciphertext)', async () => {
    const service = new VaultService();
    const patch = vi.fn().mockResolvedValue({ data: { id: 42, favorite: true } });
    service.api = { patch };

    await service.toggleFavorite(42, true);

    expect(patch).toHaveBeenCalledTimes(1);
    const [url, payload] = patch.mock.calls[0];
    expect(url).toBe('/vault/42/');
    expect(payload).toEqual({ favorite: true });
    // Critical: the secret payload is never part of a favorite toggle.
    expect(payload).not.toHaveProperty('encrypted_data');
    expect(payload).not.toHaveProperty('data');
  });

  test('can clear the favorite flag', async () => {
    const service = new VaultService();
    const patch = vi.fn().mockResolvedValue({ data: {} });
    service.api = { patch };

    await service.toggleFavorite('item-id-1', false);

    expect(patch).toHaveBeenCalledWith('/vault/item-id-1/', { favorite: false });
  });

  test('propagates an enhanced error when the PATCH fails (so the context can roll back)', async () => {
    const service = new VaultService();
    const apiError = new Error('Network down');
    apiError.errorData = { status: 503, code: 'service_unavailable' };
    service.api = { patch: vi.fn().mockRejectedValue(apiError) };

    await expect(service.toggleFavorite(7, true)).rejects.toThrow(/Failed to update favorite/);
  });
});

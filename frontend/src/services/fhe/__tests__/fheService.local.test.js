/**
 * fheService.local.test.js — strength checks run on the device.
 *
 * checkPasswordStrength / batchCheckStrength / encryptedSearch used to upload
 * client ciphertexts under field names the FHE views do not read, so every
 * call was a 400. The server cannot evaluate client ciphertexts and the only
 * field it would accept is the plaintext password, so these now compute
 * locally (or refuse) and must never touch the network.
 */

import { beforeEach, describe, expect, test, vi } from 'vitest';

vi.mock('../../api', () => ({
  api: { get: vi.fn(), post: vi.fn() },
}));

import { api } from '../../api';
import { fheService } from '../fheService';

const PASSWORD = 'Tr0ub4dor' + '&3';

describe('fheService strength checks are local', () => {
  beforeEach(() => {
    api.get.mockReset();
    api.post.mockReset();
  });

  test('checkPasswordStrength sends nothing and does not claim FHE', async () => {
    const result = await fheService.checkPasswordStrength(PASSWORD);
    expect(api.post).not.toHaveBeenCalled();
    expect(result.computedOn).toBe('client');
    expect(result.fheUsed).toBe(false);
    expect(result.tier).toBe('client_only');
    expect(result.score).toBeGreaterThan(0);
    expect(result.score).toBeLessThanOrEqual(100);
  });

  test('batchCheckStrength sends nothing and keeps input order', async () => {
    const results = await fheService.batchCheckStrength(['abc', PASSWORD]);
    expect(api.post).not.toHaveBeenCalled();
    expect(results.map(r => r.index)).toEqual([0, 1]);
    expect(results.map(r => r.passwordLength)).toEqual([3, PASSWORD.length]);
    expect(results.every(r => r.fheUsed === false)).toBe(true);
    expect(results[1].score).toBeGreaterThan(results[0].score);
  });

  test('encryptedSearch refuses without uploading the query', async () => {
    await expect(fheService.encryptedSearch('example.com')).rejects.toThrow(/not supported/);
    expect(api.post).not.toHaveBeenCalled();
  });
});

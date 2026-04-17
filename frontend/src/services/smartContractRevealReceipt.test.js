import { vi, describe, test, expect } from 'vitest';

vi.mock('./api', () => ({
  default: {
    get: (url) => Promise.resolve({ data: { ok: true, url, method: 'GET' } }),
    post: (url) => Promise.resolve({ data: { ok: true, url, method: 'POST' } }),
    patch: (url) => Promise.resolve({ data: { ok: true, url, method: 'PATCH' } }),
    delete: (url) => Promise.resolve({ data: { ok: true, url, method: 'DELETE' } }),
  },
}));

import smartContractService from './smartContractService';

describe('smartContractService reveal/receipt', () => {
  test('revealVault POSTs to the reveal endpoint', async () => {
    const res = await smartContractService.revealVault('abc-123');
    expect(res.data.url).toBe('/api/smart-contracts/vaults/abc-123/reveal/');
    expect(res.data.method).toBe('POST');
  });

  test('getReceipt GETs the receipt endpoint', async () => {
    const res = await smartContractService.getReceipt('abc-123');
    expect(res.data.url).toBe('/api/smart-contracts/vaults/abc-123/receipt/');
    expect(res.data.method).toBe('GET');
  });
});

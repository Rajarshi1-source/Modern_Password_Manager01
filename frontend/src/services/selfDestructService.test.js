import { vi, describe, test, expect } from 'vitest';

vi.mock('./api', () => ({
  default: {
    get: (url) => Promise.resolve({ data: { ok: true, url, method: 'GET' } }),
    post: (url, payload) => Promise.resolve({ data: { ok: true, url, payload, method: 'POST' } }),
    patch: (url, payload) => Promise.resolve({ data: { ok: true, url, payload, method: 'PATCH' } }),
    delete: (url) => Promise.resolve({ data: { ok: true, url, method: 'DELETE' } }),
  },
}));

import selfDestructService from './selfDestructService';

describe('selfDestructService', () => {
  test('listPolicies hits /api/self-destruct/policies/', async () => {
    const res = await selfDestructService.listPolicies();
    expect(res.data.url).toBe('/api/self-destruct/policies/');
  });

  test('createPolicy forwards payload', async () => {
    const res = await selfDestructService.createPolicy({ kinds: ['burn'] });
    expect(res.data.payload).toEqual({ kinds: ['burn'] });
    expect(res.data.method).toBe('POST');
  });

  test('revokePolicy uses POST to /revoke/', async () => {
    const res = await selfDestructService.revokePolicy('abc');
    expect(res.data.url).toBe('/api/self-destruct/policies/abc/revoke/');
    expect(res.data.method).toBe('POST');
  });

  test('listEvents goes to /events/', async () => {
    const res = await selfDestructService.listEvents();
    expect(res.data.url).toBe('/api/self-destruct/events/');
  });
});

import { vi, describe, test, expect, beforeEach } from 'vitest';

vi.mock('./api', () => {
  const calls = [];
  const mkResponse = (url, method) => {
    calls.push({ url, method });
    return Promise.resolve({ data: { ok: true, url, method } });
  };
  return {
    default: {
      get: (url) => mkResponse(url, 'GET'),
      post: (url) => mkResponse(url, 'POST'),
      patch: (url) => mkResponse(url, 'PATCH'),
      delete: (url) => mkResponse(url, 'DELETE'),
    },
    __calls: calls,
  };
});

import honeypotCredentialService from './honeypotCredentialService';

describe('honeypotCredentialService', () => {
  beforeEach(() => {
    // reset mock calls
  });

  test('list hits /api/honeypot/credentials/', async () => {
    const res = await honeypotCredentialService.list();
    expect(res.data.url).toBe('/api/honeypot/credentials/');
    expect(res.data.method).toBe('GET');
  });

  test('rotate hits the rotate sub-route', async () => {
    const res = await honeypotCredentialService.rotate('abc-123');
    expect(res.data.url).toBe('/api/honeypot/credentials/abc-123/rotate/');
    expect(res.data.method).toBe('POST');
  });

  test('reveal is a GET', async () => {
    const res = await honeypotCredentialService.reveal('abc-123');
    expect(res.data.method).toBe('GET');
    expect(res.data.url).toContain('/reveal/');
  });

  test('listEvents targets the events router', async () => {
    const res = await honeypotCredentialService.listEvents();
    expect(res.data.url).toBe('/api/honeypot/events/');
  });
});

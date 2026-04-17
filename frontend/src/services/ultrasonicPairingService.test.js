import { vi, describe, test, expect } from 'vitest';

vi.mock('./api', () => ({
  default: {
    get: (url) => Promise.resolve({ data: { ok: true, url, method: 'GET' } }),
    post: (url, payload) => Promise.resolve({ data: { ok: true, url, payload, method: 'POST' } }),
    patch: (url, payload) => Promise.resolve({ data: { ok: true, url, payload, method: 'PATCH' } }),
    delete: (url) => Promise.resolve({ data: { ok: true, url, method: 'DELETE' } }),
  },
}));

import ultrasonicPairingService, {
  abToB64, b64ToU8, shortAuthStringFromTag,
} from './ultrasonicPairingService';

describe('ultrasonicPairingService API surface', () => {
  test('initiate hits /api/ultrasonic/sessions/', async () => {
    const res = await ultrasonicPairingService.initiate({ pub_key: 'AA', purpose: 'item_share' });
    expect(res.data.url).toBe('/api/ultrasonic/sessions/');
    expect(res.data.payload.purpose).toBe('item_share');
  });

  test('claim hits /api/ultrasonic/sessions/claim/', async () => {
    const res = await ultrasonicPairingService.claim({ nonce: 'AA', pub_key: 'BB' });
    expect(res.data.url).toBe('/api/ultrasonic/sessions/claim/');
    expect(res.data.method).toBe('POST');
  });

  test('confirm builds session-scoped URL', async () => {
    const res = await ultrasonicPairingService.confirm('abc', { sas_hmac: 'CC' });
    expect(res.data.url).toBe('/api/ultrasonic/sessions/abc/confirm/');
  });

  test('delivered is a GET', async () => {
    const res = await ultrasonicPairingService.delivered('abc');
    expect(res.data.url).toBe('/api/ultrasonic/sessions/abc/delivered/');
    expect(res.data.method).toBe('GET');
  });
});

describe('b64 <-> u8 helpers', () => {
  test('round-trips a 6-byte buffer', () => {
    const bytes = new Uint8Array([0x00, 0x01, 0xff, 0x7f, 0x80, 0x55]);
    const b64 = abToB64(bytes.buffer);
    const back = b64ToU8(b64);
    expect(Array.from(back)).toEqual(Array.from(bytes));
  });
});

describe('shortAuthStringFromTag', () => {
  test('is deterministic and 6 digits', () => {
    const tag = new Uint8Array([1, 2, 3, 4, 5, 6, 7, 8, 9, 0, 11, 12, 13, 14, 15, 16]);
    const sas = shortAuthStringFromTag(tag);
    expect(sas).toMatch(/^\d{6}$/);
    const again = shortAuthStringFromTag(tag);
    expect(again).toBe(sas);
  });
});

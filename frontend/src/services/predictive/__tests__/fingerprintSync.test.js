import { describe, it, expect, vi } from 'vitest';

// The sync module imports submitFingerprints from the API service, which in
// turn pulls in the axios instance. Stub it so these unit tests stay pure.
vi.mock('../../predictiveExpirationService', () => ({
  submitFingerprints: vi.fn(async (fps) => ({ processed: fps.length, rules: [] })),
}));

import {
  deriveDomainClass,
  ageDays,
  buildFingerprintPayload,
  syncVaultFingerprints,
} from '../fingerprintSync';
import { submitFingerprints } from '../../predictiveExpirationService';

describe('fingerprintSync — deriveDomainClass', () => {
  it('maps known hosts to coarse classes', () => {
    expect(deriveDomainClass('https://chase.com/login')).toBe('finance');
    expect(deriveDomainClass('github.com')).toBe('technology');
    expect(deriveDomainClass('https://my.hospital.org')).toBe('healthcare');
  });

  it('returns "other" for unknown and "" for empty', () => {
    expect(deriveDomainClass('https://example.unknownsite.zzz')).toBe('other');
    expect(deriveDomainClass('')).toBe('');
    expect(deriveDomainClass(undefined)).toBe('');
  });

  it('matches on host boundaries, not arbitrary substrings', () => {
    // "annex.com" must NOT classify as social via the "x.com" keyword.
    expect(deriveDomainClass('https://annex.com')).toBe('other');
    // The real host still matches.
    expect(deriveDomainClass('https://x.com')).toBe('social');
  });

  it('only ever emits an allowed coarse class (never the exact host)', () => {
    const allowed = new Set([
      'finance', 'healthcare', 'technology', 'government', 'retail',
      'education', 'social', 'email', 'shopping', 'other', '',
    ]);
    expect(allowed.has(deriveDomainClass('https://secret-bank-internal.example/login'))).toBe(true);
  });
});

describe('fingerprintSync — ageDays', () => {
  it('computes whole-day age and never goes negative', () => {
    const tenDaysAgo = new Date(Date.now() - 10 * 86400 * 1000).toISOString();
    expect(ageDays(tenDaysAgo)).toBe(10);
    expect(ageDays(new Date(Date.now() + 86400 * 1000).toISOString())).toBe(0);
    expect(ageDays(null)).toBe(0);
  });
});

describe('fingerprintSync — buildFingerprintPayload', () => {
  it('skips non-password items and items without a password', async () => {
    expect(await buildFingerprintPayload({ item_type: 'note' })).toBeNull();
    expect(await buildFingerprintPayload({ item_type: 'password', data: {} })).toBeNull();
  });

  it('builds a ZK payload that never contains the password or exact URL', async () => {
    const item = {
      item_id: 'cred-42',
      item_type: 'password',
      created_at: new Date(Date.now() - 30 * 86400 * 1000).toISOString(),
      data: { password: 'Summer2024', url: 'https://chase.com/login' },
    };
    const payload = await buildFingerprintPayload(item);

    expect(payload.credential_id).toBe('cred-42');
    expect(payload.domain_class).toBe('finance');
    expect(payload.char_class_sequence).toBe('ULLLLLDDDD');

    const serialized = JSON.stringify(payload);
    expect(serialized).not.toContain('Summer2024');
    expect(serialized).not.toContain('chase.com');
    expect(serialized.toLowerCase()).not.toContain('summer');
  });

  it('measures age from a valid passwordChangedAt over created_at', async () => {
    const item = {
      item_id: 'cred-1',
      item_type: 'password',
      created_at: new Date(Date.now() - 300 * 86400 * 1000).toISOString(),
      data: {
        password: 'qwerty123',
        passwordChangedAt: new Date(Date.now() - 5 * 86400 * 1000).toISOString(),
      },
    };
    expect((await buildFingerprintPayload(item)).age_days).toBe(5);
  });

  it('falls back to created_at when passwordChangedAt is malformed', async () => {
    const item = {
      item_id: 'cred-2',
      item_type: 'password',
      created_at: new Date(Date.now() - 12 * 86400 * 1000).toISOString(),
      data: { password: 'qwerty123', passwordChangedAt: 'not-a-real-date' },
    };
    // Garbage timestamp must not score the password as freshly rotated (age 0).
    expect((await buildFingerprintPayload(item)).age_days).toBe(12);
  });
});

describe('fingerprintSync — syncVaultFingerprints', () => {
  it('uploads only password items and returns null when there is nothing', async () => {
    expect(await syncVaultFingerprints([])).toBeNull();
    expect(await syncVaultFingerprints([{ item_type: 'note' }])).toBeNull();

    const items = [
      { item_id: 'a', item_type: 'password', data: { password: 'qwerty123' } },
      { item_id: 'b', item_type: 'note', data: { text: 'hi' } },
    ];
    const res = await syncVaultFingerprints(items);
    expect(submitFingerprints).toHaveBeenCalledTimes(1);
    const sent = submitFingerprints.mock.calls[0][0];
    expect(sent).toHaveLength(1);
    expect(sent[0].credential_id).toBe('a');
    expect(res.processed).toBe(1);
  });

  it('chunks large vaults to the backend batch limit', async () => {
    submitFingerprints.mockClear();
    const items = Array.from({ length: 501 }, (_, i) => ({
      item_id: `c${i}`,
      item_type: 'password',
      data: { password: 'qwerty123' },
    }));

    const res = await syncVaultFingerprints(items);

    // 501 payloads -> two requests (500 + 1), none over the cap.
    expect(submitFingerprints).toHaveBeenCalledTimes(2);
    expect(submitFingerprints.mock.calls[0][0]).toHaveLength(500);
    expect(submitFingerprints.mock.calls[1][0]).toHaveLength(1);
    expect(res.processed).toBe(501);
  });
});

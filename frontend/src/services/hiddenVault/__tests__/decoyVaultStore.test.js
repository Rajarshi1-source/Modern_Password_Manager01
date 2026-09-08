/**
 * decoyVaultStore — the device-local decoy vault (docs/decoy-vault-contents-plan.md).
 *
 * The load-bearing property here is not round-tripping; it is that the stored
 * blob says NOTHING about whether a decoy is configured or how much it holds.
 * A `localStorage` key that appeared only once a decoy existed would let anyone
 * with devtools read the feature's existence straight off the key list, which
 * is the oracle the whole duress design exists to deny. So the length
 * assertions below compare a populated store against `writeUnconfigured`'s
 * output directly, rather than merely checking each is self-consistent.
 */
import { describe, test, expect, vi, beforeEach, afterEach } from 'vitest';
import { webcrypto } from 'node:crypto';

import * as decoyVaultStore from '../decoyVaultStore';
import { DecoyCapacityError } from '../decoyVaultStore';
import sessionVaultCrypto from '../../sessionVaultCrypto';

const USER = 'user-1';
const KEY = `vaultLocalCache:${USER}`;
const SALT = 'c2FsdHNhbHRzYWx0c2E=';

const dek = (fill) => new Uint8Array(32).fill(fill);

// The real WebCrypto, not a stub: these tests are about ciphertext LENGTH, and
// a stubbed AES-GCM would make every length assertion vacuous.
beforeEach(() => {
  if (!globalThis.window) globalThis.window = globalThis;
  // jsdom exposes `crypto` as a getter-only property and ships no
  // `crypto.subtle`, so it has to be redefined rather than assigned.
  Object.defineProperty(window, 'crypto', { value: webcrypto, configurable: true, writable: true });
  localStorage.clear();
  vi.restoreAllMocks();
});

afterEach(() => {
  localStorage.clear();
});

/** Put the module into a decoy session backed by `dekBytes`. */
const enterDecoySession = async (dekBytes) => {
  const key = await webcrypto.subtle.importKey(
    'raw', dekBytes, { name: 'AES-GCM', length: 256 }, false, ['encrypt', 'decrypt'],
  );
  vi.spyOn(sessionVaultCrypto, 'isDecoySession').mockReturnValue(true);
  vi.spyOn(sessionVaultCrypto, 'decryptDecoyContainer').mockImplementation(
    async (iv, ct) => new Uint8Array(await webcrypto.subtle.decrypt({ name: 'AES-GCM', iv }, key, ct)),
  );
  vi.spyOn(sessionVaultCrypto, 'encryptDecoyContainer').mockImplementation(async (plaintext) => {
    const iv = webcrypto.getRandomValues(new Uint8Array(12));
    const ct = await webcrypto.subtle.encrypt({ name: 'AES-GCM', iv }, key, plaintext);
    return { iv, ct: new Uint8Array(ct) };
  });
};

const ITEMS = [
  { site: 'mail.example.com', username: 'me@example.com', password: 'hunter2', notes: '' },
  { site: 'shop.example.net', username: 'me', password: 'correct horse', notes: 'old card' },
];

describe('indistinguishability', () => {
  test('an unconfigured store is the same length as a populated one', async () => {
    await decoyVaultStore.writeUnconfigured(USER);
    const unconfigured = localStorage.getItem(KEY);
    expect(unconfigured).not.toBeNull();

    localStorage.clear();
    await decoyVaultStore.seedWithKey({ userId: USER, dekBytes: dek(7), saltB64: SALT, items: ITEMS });
    const populated = localStorage.getItem(KEY);

    // The comparison that matters: a coercer reading localStorage sees two
    // values of identical length, so neither the presence of decoy contents
    // nor their size is legible.
    expect(populated.length).toBe(unconfigured.length);
  });

  test('the length does not vary with the number of entries', async () => {
    await decoyVaultStore.seedWithKey({ userId: USER, dekBytes: dek(7), saltB64: SALT, items: [] });
    const zero = localStorage.getItem(KEY).length;

    await decoyVaultStore.seedWithKey({ userId: USER, dekBytes: dek(7), saltB64: SALT, items: ITEMS });
    const two = localStorage.getItem(KEY).length;

    const many = Array.from({ length: 10 }, (_, i) => ({
      site: `s${i}.example.com`, username: `u${i}`, password: `p${i}`, notes: '',
    }));
    await decoyVaultStore.seedWithKey({ userId: USER, dekBytes: dek(7), saltB64: SALT, items: many });
    const ten = localStorage.getItem(KEY).length;

    expect(two).toBe(zero);
    expect(ten).toBe(zero);
  });

  test('writeUnconfigured never overwrites contents that already exist', async () => {
    await decoyVaultStore.seedWithKey({ userId: USER, dekBytes: dek(7), saltB64: SALT, items: ITEMS });
    const seeded = localStorage.getItem(KEY);

    // The corrupt-envelope self-heal reaches provision() on an account that may
    // already have decoy contents; clobbering them there would silently empty
    // the user's decoy vault.
    const wrote = await decoyVaultStore.writeUnconfigured(USER);

    expect(wrote).toBe(false);
    expect(localStorage.getItem(KEY)).toBe(seeded);
  });
});

describe('round trip', () => {
  test('seeded rows come back for a decoy session holding the same key', async () => {
    await decoyVaultStore.seedWithKey({ userId: USER, dekBytes: dek(7), saltB64: SALT, items: ITEMS });
    await enterDecoySession(dek(7));

    const rows = await decoyVaultStore.loadForSession(USER);

    expect(rows).toHaveLength(2);
    // Shaped exactly like a server row -- that is what lets every display
    // surface handle a decoy row without knowing it is one.
    expect(rows[0]).toMatchObject({ item_type: 'password', _lazyLoaded: true, _decrypted: false });
    expect(typeof rows[0].encrypted_data).toBe('string');
    const envelope = JSON.parse(rows[0].encrypted_data);
    expect(envelope).toMatchObject({ v: 'v2', salt: SALT });
    expect(envelope.iv).toEqual(expect.any(String));
    expect(envelope.ct).toEqual(expect.any(String));
  });

  test('the row ciphertext really is the item, under the decoy key', async () => {
    await decoyVaultStore.seedWithKey({ userId: USER, dekBytes: dek(7), saltB64: SALT, items: ITEMS });
    await enterDecoySession(dek(7));

    const rows = await decoyVaultStore.loadForSession(USER);
    const { iv, ct } = JSON.parse(rows[0].encrypted_data);
    const key = await webcrypto.subtle.importKey(
      'raw', dek(7), { name: 'AES-GCM', length: 256 }, false, ['decrypt'],
    );
    const b64 = (s) => Uint8Array.from(atob(s), (c) => c.charCodeAt(0));
    const plain = JSON.parse(new TextDecoder().decode(
      await webcrypto.subtle.decrypt({ name: 'AES-GCM', iv: b64(iv) }, key, b64(ct)),
    ));

    expect(plain).toEqual(ITEMS[0]);
  });

  test('created_at is spread out, not all stamped at one instant', async () => {
    await decoyVaultStore.seedWithKey({ userId: USER, dekBytes: dek(7), saltB64: SALT, items: ITEMS });
    await enterDecoySession(dek(7));

    const rows = await decoyVaultStore.loadForSession(USER);

    // A vault whose every entry was created in the same second is a tell to
    // anyone who glances at the dashboard's timestamps.
    expect(rows[0].created_at).not.toBe(rows[1].created_at);
  });

  test('saveForSession persists a mutated list, dropping render-only fields', async () => {
    await decoyVaultStore.seedWithKey({ userId: USER, dekBytes: dek(7), saltB64: SALT, items: ITEMS });
    await enterDecoySession(dek(7));
    const rows = await decoyVaultStore.loadForSession(USER);

    const saved = await decoyVaultStore.saveForSession(USER, [
      // `data` is decrypted plaintext a consumer may attach in memory; writing
      // it back would put a decoy secret into the container in the clear.
      { ...rows[0], favorite: true, data: { password: 'PLAINTEXT_LEAK' } },
    ]);
    expect(saved).toBe(true);

    expect(localStorage.getItem(KEY)).not.toContain('PLAINTEXT_LEAK');
    const reloaded = await decoyVaultStore.loadForSession(USER);
    expect(reloaded).toHaveLength(1);
    expect(reloaded[0].favorite).toBe(true);
    expect(reloaded[0].data).toBeUndefined();
  });
});

describe('failure modes all return an empty list', () => {
  test('no stored blob at all', async () => {
    await enterDecoySession(dek(7));
    expect(await decoyVaultStore.loadForSession(USER)).toEqual([]);
  });

  test('an unconfigured blob (throwaway key, undecryptable by anyone)', async () => {
    await decoyVaultStore.writeUnconfigured(USER);
    await enterDecoySession(dek(7));
    expect(await decoyVaultStore.loadForSession(USER)).toEqual([]);
  });

  test('the wrong key', async () => {
    await decoyVaultStore.seedWithKey({ userId: USER, dekBytes: dek(7), saltB64: SALT, items: ITEMS });
    await enterDecoySession(dek(9));
    expect(await decoyVaultStore.loadForSession(USER)).toEqual([]);
  });

  test('a corrupt blob', async () => {
    localStorage.setItem(KEY, 'not base64 at all!!');
    await enterDecoySession(dek(7));
    expect(await decoyVaultStore.loadForSession(USER)).toEqual([]);
  });

  test('a REAL session, even with a valid blob present', async () => {
    await decoyVaultStore.seedWithKey({ userId: USER, dekBytes: dek(7), saltB64: SALT, items: ITEMS });
    vi.spyOn(sessionVaultCrypto, 'isDecoySession').mockReturnValue(false);

    // Asserting the RETURNED VALUE, not that some slow path was skipped: a
    // negative control written the other way can pass for the wrong reason
    // (envelope plan §34.1).
    expect(await decoyVaultStore.loadForSession(USER)).toEqual([]);
    expect(await decoyVaultStore.saveForSession(USER, [{ id: 'd1' }])).toBe(false);
  });
});

describe('capacity', () => {
  const oversized = Array.from({ length: 200 }, (_, i) => ({
    site: `site-${i}.example.com`,
    username: `user-${i}@example.com`,
    password: 'x'.repeat(64),
    notes: 'y'.repeat(64),
  }));

  test('seeding too much raises DecoyCapacityError and stores nothing new', async () => {
    await decoyVaultStore.seedWithKey({ userId: USER, dekBytes: dek(7), saltB64: SALT, items: ITEMS });
    const before = localStorage.getItem(KEY);

    await expect(decoyVaultStore.seedWithKey({
      userId: USER, dekBytes: dek(7), saltB64: SALT, items: oversized,
    })).rejects.toBeInstanceOf(DecoyCapacityError);

    // Refused, never truncated: a truncated container decodes to nothing next
    // read, silently emptying the decoy vault mid-coercion.
    expect(localStorage.getItem(KEY)).toBe(before);
  });

  test('an oversized decoy-session save returns false rather than truncating', async () => {
    await decoyVaultStore.seedWithKey({ userId: USER, dekBytes: dek(7), saltB64: SALT, items: ITEMS });
    await enterDecoySession(dek(7));
    const before = localStorage.getItem(KEY);

    const rows = oversized.map((item, i) => ({
      id: `d${i}`, item_id: `item_${i}`, item_type: 'password',
      encrypted_data: JSON.stringify({ v: 'v2', iv: 'aaa', ct: 'z'.repeat(200), salt: SALT }),
      favorite: false, created_at: '2026-01-01T00:00:00.000Z',
    }));

    expect(await decoyVaultStore.saveForSession(USER, rows)).toBe(false);
    expect(localStorage.getItem(KEY)).toBe(before);
  });
});

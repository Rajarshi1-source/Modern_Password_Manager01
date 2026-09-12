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
import sessionVaultCrypto, { PAYLOAD_VERSION } from '../../sessionVaultCrypto';

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
    // The version comes from the shared constant. It was hard-coded 'v2' here
    // and in the module, so this assertion compared the copy against itself
    // and passed while `decryptItem` rejected every seeded row as legacy
    // plaintext -- the copied-literal trap, in a test written to catch it.
    expect(envelope).toMatchObject({ v: PAYLOAD_VERSION, salt: SALT });
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

  test('a seeded row decrypts through the real decryptItem path', async () => {
    // The assertion that actually matters, and the one this file was missing:
    // the earlier round-trip test decrypted the row with raw WebCrypto, which
    // is exactly the check that CANNOT notice a wrong envelope version. The
    // app reads these rows through sessionVaultCrypto, so the test must too.
    await decoyVaultStore.seedWithKey({ userId: USER, dekBytes: dek(7), saltB64: SALT, items: ITEMS });
    await enterDecoySession(dek(7));
    const rows = await decoyVaultStore.loadForSession(USER);

    // Real module, not the spied decoy helpers: installRawDek puts the same
    // key in as the session key, so decryptItem opens the row the way the
    // display path does.
    vi.restoreAllMocks();
    sessionVaultCrypto.clearSessionKey();
    await sessionVaultCrypto.installRawDek(dek(7), SALT, USER, null, true);

    const plain = await sessionVaultCrypto.decryptItem(rows[0].encrypted_data);

    expect(plain).toEqual(ITEMS[0]);
    // A wrong version does not throw -- it returns this marker, which renders
    // as a "legacy plaintext" warning banner instead of an entry. Asserting
    // its ABSENCE is what makes the check meaningful.
    expect(plain._legacyPlaintext).toBeUndefined();
    sessionVaultCrypto.clearSessionKey();
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

describe('concurrency', () => {
  test('a backfill that starts before a seed does not overwrite it', async () => {
    // The interleaving that matters: `open()` calls writeUnconfigured on every
    // unlock, and its key-generation plus AES-GCM work is a real await window.
    // A seed landing inside that window must survive -- otherwise the user
    // saves decoy contents and the next decoy unlock renders empty.
    // Synchronise on the await being timed rather than racing it and hoping:
    // the backfill is held INSIDE its own AES-GCM call until the seed has
    // finished writing, which is the ordering the re-check exists for. Racing
    // the two unsynchronised passes for the wrong reason -- the backfill's
    // crypto is shorter, so it usually finishes first and the seed lands on
    // top of it regardless of whether the re-check exists.
    const realEncrypt = webcrypto.subtle.encrypt.bind(webcrypto.subtle);
    let releaseBackfill;
    const held = new Promise((resolve) => { releaseBackfill = resolve; });
    // Armed for the BACKFILL's encrypt only, then disarmed. A "hold the first
    // call" latch is a race, not an ordering: the seed below also encrypts,
    // and when its call arrived first the latch held the SEED instead and the
    // test deadlocked on its own await. That made this test flaky ~1 run in 3.
    let armed = true;
    let backfillInsideEncrypt = false;
    vi.spyOn(window.crypto.subtle, 'encrypt').mockImplementation(async (...args) => {
      const out = await realEncrypt(...args);
      if (armed) {
        armed = false;
        backfillInsideEncrypt = true;
        await held;
      }
      return out;
    });

    const backfill = decoyVaultStore.writeUnconfigured(USER);
    // Synchronise on the backfill being inside its encryption before seeding,
    // so the interleaving under test is the one that actually happens.
    await vi.waitFor(() => expect(backfillInsideEncrypt).toBe(true));
    await decoyVaultStore.seedWithKey({ userId: USER, dekBytes: dek(7), saltB64: SALT, items: ITEMS });
    releaseBackfill();
    const wrote = await backfill;

    // Refused, because the key it checked for as absent is now present.
    expect(wrote).toBe(false);
    vi.restoreAllMocks();
    await enterDecoySession(dek(7));
    // The assertion that actually matters: the seeded CONTENTS are still
    // readable. A return value can be right for the wrong reason.
    expect(await decoyVaultStore.loadForSession(USER)).toHaveLength(2);
  });

  test('a stale mutation cannot overwrite a rotated container', async () => {
    // The cross-tab case. Tab A holds a decoy session and starts a mutation;
    // tab B holds a REAL session and rotates the decoy password, which mints a
    // fresh decoy DEK and re-keys the container. Tab A's session-generation
    // counter is module state -- it cannot see tab B at all -- so without a
    // compare-and-swap on the stored bytes, tab A's in-flight write lands on
    // top of the rotation with ciphertext sealed under the OLD dek, and the
    // new decoy password then opens a vault nothing can decrypt.
    await decoyVaultStore.seedWithKey({ userId: USER, dekBytes: dek(7), saltB64: SALT, items: ITEMS });
    await enterDecoySession(dek(7));

    const realEncrypt = webcrypto.subtle.encrypt.bind(webcrypto.subtle);
    let releaseMutation;
    const held = new Promise((resolve) => { releaseMutation = resolve; });
    // Armed for the MUTATION's encrypt only. A plain "hold the first call"
    // latch deadlocks here: `mutate` runs off a microtask queue, so the
    // rotation's own encrypt can be the first to arrive and then nothing can
    // release it.
    let armed = true;
    let mutationInsideEncrypt = false;
    vi.spyOn(window.crypto.subtle, 'encrypt').mockImplementation(async (...args) => {
      const out = await realEncrypt(...args);
      if (armed) {
        armed = false;
        mutationInsideEncrypt = true;
        await held;
      }
      return out;
    });

    const staleWrite = decoyVaultStore.mutate(USER, (rows) => [...rows, {
      id: 'dStale', item_id: 'stale', item_type: 'password',
      encrypted_data: 'X', favorite: false, created_at: new Date().toISOString(),
    }]);
    // Synchronise on the mutation actually being inside its encryption before
    // rotating -- otherwise the test races the thing it is trying to order.
    await vi.waitFor(() => expect(mutationInsideEncrypt).toBe(true));

    // The rotation lands while that mutation is held mid-encrypt.
    await decoyVaultStore.resetForNewKey(USER, dek(9));
    const rotated = localStorage.getItem(`vaultLocalCache:${USER}`);
    releaseMutation();

    expect(await staleWrite).toBe(false);
    vi.restoreAllMocks();
    // Byte-for-byte untouched: the rotation's container is what remains.
    expect(localStorage.getItem(`vaultLocalCache:${USER}`)).toBe(rotated);
  });

  test('two appends in the same millisecond get distinct ids', async () => {
    await decoyVaultStore.seedWithKey({ userId: USER, dekBytes: dek(7), saltB64: SALT, items: [] });
    await enterDecoySession(dek(7));
    vi.spyOn(sessionVaultCrypto, 'encryptDecoyItem').mockResolvedValue('SEALED');
    // Freeze the clock: a timestamp-only id repeats here, and both
    // deleteItem and toggleFavorite match rows by id -- one delete would
    // remove both rows.
    vi.spyOn(Date, 'now').mockReturnValue(1_700_000_000_000);

    await decoyVaultStore.addRowForSession(USER, { data: { name: 'one' } });
    await decoyVaultStore.addRowForSession(USER, { data: { name: 'two' } });

    const rows = await decoyVaultStore.loadForSession(USER);
    expect(rows).toHaveLength(2);
    expect(rows[0].id).not.toBe(rows[1].id);
    // `item_id` too, not just `id`: App.jsx keys the decrypted-payload map by
    // item_id (`Object.fromEntries([item_id, data])`) AND uses it as the React
    // list key, so a duplicate silently drops one row's plaintext.
    expect(rows[0].item_id).not.toBe(rows[1].item_id);
  });

  test('a queued add is refused when the session moved after encryption', async () => {
    await decoyVaultStore.seedWithKey({ userId: USER, dekBytes: dek(7), saltB64: SALT, items: [] });
    await enterDecoySession(dek(7));
    const before = localStorage.getItem(`vaultLocalCache:${USER}`);

    // encryptDecoyItem resolves under one generation; the counter then moves
    // before the queued mutation runs, exactly as a lock plus a second decoy
    // unlock would. Without the pin, ciphertext sealed under the old dek lands
    // in a container sealed under the new one and can never be read back.
    vi.spyOn(sessionVaultCrypto, 'encryptDecoyItem').mockImplementation(async () => {
      const sealed = 'SEALED-UNDER-OLD-DEK';
      sessionVaultCrypto.reserveSessionGeneration();
      return sealed;
    });

    const ok = await decoyVaultStore.addRowForSession(USER, { data: { name: 'x' } });

    expect(ok).toBe(false);
    expect(localStorage.getItem(`vaultLocalCache:${USER}`)).toBe(before);
  });

  test('mutate without an expected generation still runs', async () => {
    // delete/favourite encrypt nothing beforehand, so they pass no generation
    // and must not be caught by the new guard.
    await decoyVaultStore.seedWithKey({ userId: USER, dekBytes: dek(7), saltB64: SALT, items: ITEMS });
    await enterDecoySession(dek(7));

    const ok = await decoyVaultStore.mutate(USER, (rows) => rows.slice(1));

    expect(ok).toBe(true);
    expect(await decoyVaultStore.loadForSession(USER)).toHaveLength(1);
  });

  test('serialized mutations do not discard each other', async () => {
    await decoyVaultStore.seedWithKey({ userId: USER, dekBytes: dek(7), saltB64: SALT, items: ITEMS });
    await enterDecoySession(dek(7));

    // Two overlapping read-modify-writes on DIFFERENT rows. Unserialized, both
    // load the same snapshot and the second save discards the first --
    // `favoriteInFlightRef` only serializes per item id, so this is reachable
    // by toggling two rows.
    const [a, b] = await Promise.all([
      decoyVaultStore.mutate(USER, (rows) => rows.map((r, i) => (i === 0 ? { ...r, favorite: true } : r))),
      decoyVaultStore.mutate(USER, (rows) => rows.map((r, i) => (i === 1 ? { ...r, favorite: true } : r))),
    ]);

    expect(a).toBe(true);
    expect(b).toBe(true);
    const rows = await decoyVaultStore.loadForSession(USER);
    expect(rows.map((r) => r.favorite)).toEqual([true, true]);
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

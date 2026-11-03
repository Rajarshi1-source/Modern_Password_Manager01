/**
 * Replacing the vault key (`replaceVaultKey`) with real AES-GCM. argon2-browser
 * is mocked as in sessionVaultCryptoV3.verify.test.js. The point of these tests
 * is that nothing sealed under the old key becomes unreadable, across a sign-in,
 * a second replacement and a master-password change.
 */
import { describe, it, expect, beforeAll, beforeEach, vi } from 'vitest';
import axios from 'axios';

vi.mock('argon2-browser', () => ({
  ArgonType: { Argon2id: 2 },
  hash: vi.fn(async ({ pass, salt }) => {
    const enc = new TextEncoder().encode(`${pass}:${salt}`);
    const digest = await crypto.subtle.digest('SHA-256', enc);
    return { hash: new Uint8Array(digest) };
  }),
}));

vi.mock('axios', () => ({
  default: { get: vi.fn(), put: vi.fn(), post: vi.fn(), patch: vi.fn() },
}));

const PASSWORD = 'correct-horse-battery-staple';
const USERNAME = 'alice@example.com';
const FIRST_ID = '11111111-1111-4111-8111-111111111111';
const SECOND_ID = '22222222-2222-4222-8222-222222222222';
const THIRD_ID = '33333333-3333-4333-8333-333333333333';

let v3;
let server;

beforeAll(async () => {
  v3 = (await import('../sessionVaultCryptoV3')).default;
});

async function enroll() {
  vi.mocked(axios.put).mockResolvedValue({ data: { dek_id: FIRST_ID } });
  await v3.enrollWithMasterPassword(PASSWORD);
  server = { blob: vi.mocked(axios.put).mock.calls.at(-1)[1].blob, dek_id: FIRST_ID, retired_keys: [] };
}

// Does what VaultKeyReplaceView does to the row.
async function replace(newId) {
  vi.mocked(axios.post).mockResolvedValueOnce({ data: { dek_id: newId } });
  await v3.replaceVaultKey(PASSWORD, USERNAME);
  const sent = vi.mocked(axios.post).mock.calls.at(-1)[1];
  server = {
    blob: sent.blob,
    dek_id: newId,
    retired_keys: [...server.retired_keys, sent.retired_key],
  };
  return sent;
}

async function signIn() {
  vi.mocked(axios.get).mockResolvedValueOnce({ data: { enrolled: true, ...server } });
  await v3.unlockWithMasterPassword(PASSWORD);
}

describe('replaceVaultKey', () => {
  beforeEach(async () => {
    vi.clearAllMocks();
    v3.clearSessionKey();
    await enroll();
  });

  it('sends only ciphertext, and never the master password or a raw key', async () => {
    const sent = await replace(SECOND_ID);
    expect(Object.keys(sent).sort()).toEqual(['blob', 'dek_id', 'login_verifier', 'retired_key']);
    expect(sent.dek_id).toBe(FIRST_ID);
    expect(sent.retired_key.dek_id).toBe(FIRST_ID);
    expect(sent.retired_key.v).toBe('rdek-1');
    expect(JSON.stringify(sent)).not.toContain(PASSWORD);
  });

  it('wraps a different key from the one it replaces', async () => {
    const oldBlob = server.blob;
    await replace(SECOND_ID);
    expect(server.blob.wrapped).not.toBe(oldBlob.wrapped);
  });

  it('leaves the session locked, since the server ended it', async () => {
    await replace(SECOND_ID);
    expect(v3.hasSessionKey()).toBe(false);
  });

  it('opens the same master password after a sign-in', async () => {
    await replace(SECOND_ID);
    await signIn();
    expect(v3.hasSessionKey()).toBe(true);
    expect(v3.getSessionDEKId()).toBe(SECOND_ID);
  });

  it('keeps an item sealed under the old key readable', async () => {
    const sealed = await v3.encryptItem({ secret: 'old row' });
    await replace(SECOND_ID);
    await signIn();
    expect(v3.hasRetiredKeys()).toBe(true);
    expect(await v3.decryptItem(sealed)).toEqual({ secret: 'old row' });
  });

  it('seals new items under the new key', async () => {
    await replace(SECOND_ID);
    await signIn();
    const sealed = JSON.parse(await v3.encryptItem({ secret: 'new row' }));
    expect(sealed.dek_id).toBe(SECOND_ID);
  });

  it('reads through two replacements', async () => {
    const first = await v3.encryptItem({ secret: 'first' });
    await replace(SECOND_ID);
    await signIn();
    const second = await v3.encryptItem({ secret: 'second' });
    await replace(THIRD_ID);
    await signIn();
    expect(await v3.decryptItem(first)).toEqual({ secret: 'first' });
    expect(await v3.decryptItem(second)).toEqual({ secret: 'second' });
  });

  it('survives a master-password change after the replacement', async () => {
    const sealed = await v3.encryptItem({ secret: 'old row' });
    await replace(SECOND_ID);
    await signIn();
    vi.mocked(axios.get).mockResolvedValueOnce({ data: { enrolled: true, ...server } });
    vi.mocked(axios.put).mockResolvedValue({ data: { dek_id: SECOND_ID } });
    await v3.changeMasterPassword(PASSWORD, 'a-new-master-password');
    const blob = vi.mocked(axios.put).mock.calls.at(-1)[1].blob;
    v3.clearSessionKey();
    vi.mocked(axios.get).mockResolvedValueOnce({ data: { enrolled: true, ...server, blob } });
    await v3.unlockWithMasterPassword('a-new-master-password');
    expect(await v3.decryptItem(sealed)).toEqual({ secret: 'old row' });
  });

  it('changes nothing on a wrong password', async () => {
    await expect(v3.replaceVaultKey('wrong', USERNAME)).rejects.toThrow('Incorrect password');
    expect(axios.post).not.toHaveBeenCalled();
    expect(v3.hasSessionKey()).toBe(true);
  });

  it('keeps the session when the server refuses, so nothing is lost', async () => {
    const sealed = await v3.encryptItem({ secret: 'row' });
    vi.mocked(axios.post).mockRejectedValueOnce(new Error('403'));
    await expect(v3.replaceVaultKey(PASSWORD, USERNAME)).rejects.toThrow('403');
    expect(await v3.decryptItem(sealed)).toEqual({ secret: 'row' });
  });

  it('refuses on a locked vault', async () => {
    v3.clearSessionKey();
    await expect(v3.replaceVaultKey(PASSWORD, USERNAME)).rejects.toThrow('Vault is locked.');
  });

  it('reads as stale, not as an error, for a key it has no record of', async () => {
    const sealed = JSON.parse(await v3.encryptItem({ secret: 'row' }));
    sealed.dek_id = THIRD_ID;
    expect(await v3.decryptItem(JSON.stringify(sealed))).toEqual({ _staleDek: true });
  });

  it('reads as stale when a retired key entry is damaged', async () => {
    const sealed = await v3.encryptItem({ secret: 'row' });
    await replace(SECOND_ID);
    server.retired_keys[0] = { ...server.retired_keys[0], wrapped: btoa('x'.repeat(48)) };
    await signIn();
    expect(await v3.decryptItem(sealed)).toEqual({ _staleDek: true });
  });

  it('forgets retired keys on lock', async () => {
    const sealed = await v3.encryptItem({ secret: 'row' });
    await replace(SECOND_ID);
    await signIn();
    await v3.decryptItem(sealed);
    v3.clearSessionKey();
    expect(v3.hasRetiredKeys()).toBe(false);
    await expect(v3.decryptItem(sealed)).rejects.toThrow('Vault is locked.');
  });
});

describe('re-encrypting rows at sign-in', () => {
  let migrate;

  beforeAll(async () => {
    ({ migrateRemainingV2Items: migrate } = await import('../legacyVaultMigration'));
  });

  beforeEach(async () => {
    vi.clearAllMocks();
    v3.clearSessionKey();
    await enroll();
  });

  // Answers the vault list (empty) and the stale-row pages.
  function serve(pages) {
    let page = 0;
    vi.mocked(axios.get).mockImplementation(async (url) => {
      if (url === '/api/vault/') return { data: { results: [], next: null } };
      const data = pages[page];
      page += 1;
      return { data };
    });
  }

  it('moves a stale row to the current key and keeps its contents', async () => {
    const sealed = await v3.encryptItem({ secret: 'old row' });
    await replace(SECOND_ID);
    await signIn();
    serve([{ items: [{ id: 'a', updated_at: 't', encrypted_data: sealed }], next: null }]);
    vi.mocked(axios.post).mockResolvedValueOnce({ data: { rewritten: 1 } });
    const result = await migrate();
    expect(result.migratedCount).toBe(1);
    const row = vi.mocked(axios.post).mock.calls.at(-1)[1].items[0];
    expect(row.id).toBe('a');
    expect(row.updated_at).toBe('t');
    expect(JSON.parse(row.encrypted_data).dek_id).toBe(SECOND_ID);
    expect(await v3.decryptItem(row.encrypted_data)).toEqual({ secret: 'old row' });
  });

  it('leaves an unreadable row alone and carries on', async () => {
    const good = await v3.encryptItem({ secret: 'good' });
    await replace(SECOND_ID);
    await signIn();
    const damaged = JSON.stringify({ ...JSON.parse(good), ct: btoa('nope'.repeat(8)) });
    const unknown = JSON.stringify({ ...JSON.parse(good), dek_id: THIRD_ID });
    serve([{
      items: [
        { id: 'damaged', updated_at: 't', encrypted_data: damaged },
        { id: 'unknown', updated_at: 't', encrypted_data: unknown },
        { id: 'good', updated_at: 't', encrypted_data: good },
      ],
      next: null,
    }]);
    vi.mocked(axios.post).mockResolvedValueOnce({ data: { rewritten: 1 } });
    await migrate();
    const { items } = vi.mocked(axios.post).mock.calls.at(-1)[1];
    expect(items.map((i) => i.id)).toEqual(['good']);
  });

  it('never writes an empty item back over an envelope it cannot parse', async () => {
    await replace(SECOND_ID);
    await signIn();
    serve([{ items: [{ id: 'bad', updated_at: 't', encrypted_data: 'not json "v":"svc-gcm-2"' }], next: null }]);
    await migrate();
    expect(axios.post).toHaveBeenCalledTimes(1); // only the replacement itself
  });

  it('follows pages by cursor', async () => {
    await replace(SECOND_ID);
    await signIn();
    serve([{ items: [], next: 'cursor' }, { items: [], next: null }]);
    await migrate();
    const stale = vi.mocked(axios.get).mock.calls.filter(([url]) => url.endsWith('/stale-items/'));
    expect(stale.map(([, opts]) => opts.params)).toEqual([{}, { after: 'cursor' }]);
  });

  it('survives a throttled server, leaving the rest for the next sign-in', async () => {
    await replace(SECOND_ID);
    await signIn();
    vi.mocked(axios.get).mockImplementation(async (url) => {
      if (url === '/api/vault/') return { data: { results: [], next: null } };
      throw new Error('429');
    });
    await expect(migrate()).resolves.toEqual({ migratedCount: 0, totalCount: 0 });
  });

  it('asks nothing for an account that never replaced its key', async () => {
    serve([]);
    await migrate();
    expect(vi.mocked(axios.get).mock.calls.map(([url]) => url)).toEqual(['/api/vault/']);
  });
});

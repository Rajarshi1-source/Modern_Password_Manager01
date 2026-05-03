/**
 * Vitest unit tests for sessionVaultCryptoV3.
 *
 * argon2-browser does not run cleanly under jsdom, so we mock it with
 * a deterministic SHA-256 KDF stand-in. The point of these tests is to
 * verify call wiring (envelope shape, dek_id rotation guard, stale-DEK
 * handling, payload version gating) — the real Argon2 KDF is exercised
 * end-to-end in Playwright (Unit 14).
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

// Deterministic argon2 stand-in: hash(pass + ':' + salt) via SHA-256.
vi.mock('argon2-browser', () => ({
  ArgonType: { Argon2id: 2 },
  hash: vi.fn(async ({ pass, salt }) => {
    const enc = new TextEncoder().encode(`${pass}:${salt}`);
    const digest = await crypto.subtle.digest('SHA-256', enc);
    return { hash: new Uint8Array(digest) };
  }),
}));

// In-memory wrapped-DEK store, keyed by URL.
const serverState = { wrappedDek: null, dekId: null, factors: [] };

vi.mock('axios', () => {
  const get = vi.fn(async (url) => {
    if (url.endsWith('/vault/wrapped-dek/')) {
      if (!serverState.wrappedDek) return { data: { enrolled: false } };
      return { data: { enrolled: true, blob: serverState.wrappedDek, dek_id: serverState.dekId } };
    }
    return { data: null };
  });
  const put = vi.fn(async (url, body) => {
    if (url.endsWith('/vault/wrapped-dek/')) {
      if (serverState.wrappedDek && body.dek_id !== serverState.dekId) {
        const err = new Error('dek_id mismatch');
        err.response = { status: 409 };
        throw err;
      }
      serverState.wrappedDek = body.blob;
      if (!serverState.dekId) serverState.dekId = `dek-${Date.now()}`;
      return { data: { success: true, dek_id: serverState.dekId } };
    }
    return { data: null };
  });
  const post = vi.fn(async (url, body) => {
    if (url.endsWith('/vault/recovery-factors/')) {
      serverState.factors.push(body);
      return { data: { success: true, factor_id: serverState.factors.length } };
    }
    return { data: null };
  });
  return { default: { get, put, post } };
});

beforeEach(() => {
  serverState.wrappedDek = null;
  serverState.dekId = null;
  serverState.factors = [];
});

afterEach(async () => {
  const v3 = await import('../sessionVaultCryptoV3.js');
  v3.clearSessionKey();
});

describe('sessionVaultCryptoV3 — envelope shape', () => {
  it('writes a wdek-1 envelope with argon2id KDF params on enrollment', async () => {
    const v3 = await import('../sessionVaultCryptoV3.js');
    await v3.enrollWithMasterPassword('correct-horse-battery-staple');
    expect(serverState.wrappedDek).toBeTruthy();
    expect(serverState.wrappedDek.v).toBe('wdek-1');
    expect(serverState.wrappedDek.kdf).toBe('argon2id');
    expect(serverState.wrappedDek.kdf_params).toEqual({ t: 3, m: 65536, p: 2 });
    expect(typeof serverState.wrappedDek.salt).toBe('string');
    expect(typeof serverState.wrappedDek.iv).toBe('string');
    expect(typeof serverState.wrappedDek.wrapped).toBe('string');
  });
});

describe('sessionVaultCryptoV3 — unlock paths', () => {
  it('throws NOT_ENROLLED when server reports no enrollment', async () => {
    const v3 = await import('../sessionVaultCryptoV3.js');
    await expect(v3.unlockWithMasterPassword('anything')).rejects.toThrow('NOT_ENROLLED');
  });

  it('round-trips a vault item with the correct password', async () => {
    const v3 = await import('../sessionVaultCryptoV3.js');
    await v3.enrollWithMasterPassword('correct-horse-battery-staple');
    const ct = await v3.encryptItem({ title: 'gmail', password: 's3cret' });
    v3.clearSessionKey();
    await v3.unlockWithMasterPassword('correct-horse-battery-staple');
    const pt = await v3.decryptItem(ct);
    expect(pt).toEqual({ title: 'gmail', password: 's3cret' });
  });

  it('rejects the wrong password with a generic error', async () => {
    const v3 = await import('../sessionVaultCryptoV3.js');
    await v3.enrollWithMasterPassword('correct-horse-battery-staple');
    v3.clearSessionKey();
    await expect(v3.unlockWithMasterPassword('wrong-password'))
      .rejects.toThrow('Incorrect password or corrupted vault key.');
  });
});

describe('sessionVaultCryptoV3 — payload versioning', () => {
  it('returns _legacyPlaintext for non-svc-gcm-2 payloads', async () => {
    const v3 = await import('../sessionVaultCryptoV3.js');
    const result = await v3.decryptItem(JSON.stringify({ v: 'svc-gcm-1', iv: 'x', ct: 'y' }));
    expect(result).toEqual({ _legacyPlaintext: true });
  });

  it('returns _staleDek when payload dek_id mismatches session dek_id', async () => {
    const v3 = await import('../sessionVaultCryptoV3.js');
    await v3.enrollWithMasterPassword('pw');
    const stale = JSON.stringify({
      v: 'svc-gcm-2',
      iv: 'aXY=',
      ct: 'Y3Q=',
      dek_id: 'some-other-dek-id',
    });
    const result = await v3.decryptItem(stale);
    expect(result).toEqual({ _staleDek: true });
  });
});

describe('sessionVaultCryptoV3 — change-master-password', () => {
  it('keeps dek_id stable across rotation', async () => {
    const v3 = await import('../sessionVaultCryptoV3.js');
    const { dekId: idBefore } = await v3.enrollWithMasterPassword('old-pw');
    await v3.changeMasterPassword('old-pw', 'new-pw');
    expect(serverState.dekId).toBe(idBefore);
    // Items encrypted before rotation must still decrypt after rotation
    // — same DEK, just re-wrapped under the new KEK.
    v3.clearSessionKey();
    await v3.unlockWithMasterPassword('new-pw');
    expect(v3.hasSessionKey()).toBe(true);
  });
});

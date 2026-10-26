/**
 * Sign-in sends a login verifier derived from the master password, never
 * the master password itself, and the post-recovery rotation moves the
 * verifier together with the vault envelope.
 *
 * argon2-browser is replaced by a deterministic SHA-256 stand-in, as in
 * sessionVaultCryptoV3.test.js: these tests check wiring, not Argon2.
 */
import { beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('argon2-browser', () => ({
  ArgonType: { Argon2id: 2 },
  hash: vi.fn(async ({ pass, salt }) => {
    const enc = new TextEncoder().encode(`${pass}:${salt}`);
    return { hash: new Uint8Array(await crypto.subtle.digest('SHA-256', enc)) };
  }),
}));

const serverState = { wrappedDek: null, dekId: null, rotations: [] };
vi.mock('axios', () => {
  const get = vi.fn(async () => (serverState.wrappedDek
    ? { data: { enrolled: true, blob: serverState.wrappedDek, dek_id: serverState.dekId } }
    : { data: { enrolled: false } }));
  const put = vi.fn(async (url, body) => {
    serverState.wrappedDek = body.blob;
    serverState.dekId = serverState.dekId || 'dek-1';
    return { data: { success: true, dek_id: serverState.dekId } };
  });
  const post = vi.fn(async (url, body) => {
    if (url.endsWith('/recover-rotate/')) serverState.rotations.push(body);
    return { data: { success: true } };
  });
  return { default: { get, put, post } };
});

const MASTER = 'correct-horse-battery-staple';
const rejection = (status) => Object.assign(new Error('rejected'), { response: { status } });

beforeEach(() => {
  window.localStorage.clear();
  serverState.wrappedDek = null;
  serverState.dekId = null;
  serverState.rotations = [];
});

describe('deriveLoginVerifier', () => {
  it('is 32 bytes of base64, not the password, and bound to the account', async () => {
    const { deriveLoginVerifier } = await import('../loginVerifier.js');
    const v = await deriveLoginVerifier(MASTER, 'alice@example.com');
    expect(atob(v)).toHaveLength(32);
    expect(v).not.toContain(MASTER);
    expect(await deriveLoginVerifier(MASTER, ' Alice@Example.com ')).toBe(v);
    expect(await deriveLoginVerifier(MASTER, 'bob@example.com')).not.toBe(v);
    expect(await deriveLoginVerifier(`${MASTER}!`, 'alice@example.com')).not.toBe(v);
  });
});

describe('signInWithVerifier', () => {
  it('sends only the verifier when the account accepts it', async () => {
    const { signInWithVerifier, deriveLoginVerifier } = await import('../loginVerifier.js');
    const post = vi.fn(async () => ({ ok: true }));
    await signInWithVerifier(post, { username: 'alice@example.com', masterPassword: MASTER });
    expect(post).toHaveBeenCalledTimes(1);
    expect(post.mock.calls[0][0]).toEqual({
      username: 'alice@example.com',
      password: await deriveLoginVerifier(MASTER, 'alice@example.com'),
    });
  });

  it('retries once with the old password for an account not yet switched', async () => {
    const { signInWithVerifier } = await import('../loginVerifier.js');
    const post = vi.fn()
      .mockRejectedValueOnce(rejection(401))
      .mockResolvedValueOnce({ ok: true });
    await signInWithVerifier(post, { username: 'alice@example.com', masterPassword: MASTER });
    expect(post).toHaveBeenCalledTimes(2);
    expect(post.mock.calls[0][0]).not.toHaveProperty('legacy_password');
    expect(post.mock.calls[1][0].legacy_password).toBe(MASTER);
  });

  it('never sends the master password again once this browser saw the switch', async () => {
    const { signInWithVerifier } = await import('../loginVerifier.js');
    await signInWithVerifier(vi.fn(async () => ({})), { username: 'alice@example.com', masterPassword: MASTER });
    const post = vi.fn().mockRejectedValue(rejection(401));
    await expect(signInWithVerifier(post, { username: 'alice@example.com', masterPassword: 'typo' }))
      .rejects.toThrow();
    expect(post).toHaveBeenCalledTimes(1);
    expect(JSON.stringify(post.mock.calls)).not.toContain('typo');
  });

  it('does not retry on a server error', async () => {
    const { signInWithVerifier } = await import('../loginVerifier.js');
    const post = vi.fn().mockRejectedValue(rejection(500));
    await expect(signInWithVerifier(post, { username: 'a@example.com', masterPassword: MASTER })).rejects.toThrow();
    expect(post).toHaveBeenCalledTimes(1);
  });
});

describe('rewrapMasterPasswordFromRecovery', () => {
  it('rotates the login verifier with the envelope and never sends the new password', async () => {
    const v3 = await import('../sessionVaultCryptoV3.js');
    const { deriveLoginVerifier } = await import('../loginVerifier.js');
    await v3.enrollWithMasterPassword('forgotten-password');
    const factor = await v3.buildRecoveryFactorEnvelope({
      secret: 'RECOVERYKEY', masterPassword: 'forgotten-password',
    });
    v3.clearSessionKey();

    await v3.rewrapMasterPasswordFromRecovery({
      factorBlob: factor.blob,
      recoverySecret: 'RECOVERYKEY',
      newPassword: 'brand-new-master-password',
      dekId: factor.dekId,
      username: 'alice@example.com',
      factorType: 'recovery_key',
    });

    expect(serverState.rotations).toHaveLength(1);
    const body = serverState.rotations[0];
    expect(body.login_verifier).toBe(
      await deriveLoginVerifier('brand-new-master-password', 'alice@example.com'),
    );
    expect(atob(body.new_auth_hash)).toHaveLength(32);
    expect(JSON.stringify(body)).not.toContain('brand-new-master-password');
    expect(JSON.stringify(body)).not.toContain('RECOVERYKEY');
  });
});

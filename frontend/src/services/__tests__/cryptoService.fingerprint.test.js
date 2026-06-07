/**
 * Unit tests for the adaptive-password zero-knowledge fingerprint primitive
 * (cryptoService.passwordFingerprint / deriveFingerprintKey) — PR-1 of
 * docs/adaptive-password-zk-remediation-plan.md.
 *
 * argon2-browser doesn't run cleanly under jsdom, so we mock it with a
 * deterministic SHA-256 KDF stand-in (same approach as sessionVaultCryptoV3).
 * The point of these tests is the *fingerprint* contract — keyed, deterministic,
 * opaque, well-formed — which is independent of the specific KDF.
 */
import { describe, it, expect, beforeAll, beforeEach, vi } from 'vitest';
import * as argon2 from 'argon2-browser';
import { CryptoService } from '../cryptoService';

// Deterministic argon2 stand-in: hash(pass + ':' + salt) via SHA-256.
vi.mock('argon2-browser', () => ({
  ArgonType: { Argon2id: 2 },
  hash: vi.fn(async ({ pass, salt }) => {
    const enc = new TextEncoder().encode(`${pass}:${salt}`);
    const digest = await crypto.subtle.digest('SHA-256', enc);
    return { hash: new Uint8Array(digest) };
  }),
}));

const SALT = 'user-salt-abc';

// Helper: bare base64url SHA-256 of an arbitrary string (to prove the
// fingerprint is NOT a plain digest).
async function bareSha256B64Url(input) {
  const digest = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(input));
  const binary = Array.from(new Uint8Array(digest), (b) => String.fromCharCode(b)).join('');
  return btoa(binary).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
}

describe('cryptoService password fingerprint (ZK)', () => {
  beforeAll(() => {
    // Ensure WebCrypto is reachable via window.crypto.subtle (the service reads
    // it in its constructor); jsdom doesn't always alias it to the Node impl.
    if (!globalThis.window) globalThis.window = globalThis;
    if (!window.crypto || !window.crypto.subtle) {
      Object.defineProperty(window, 'crypto', { value: globalThis.crypto, configurable: true });
    }
  });

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('is deterministic for the same password + salt', async () => {
    const svc = new CryptoService('master-password');
    const a = await svc.passwordFingerprint('CorrectHorse1!', SALT);
    const b = await svc.passwordFingerprint('CorrectHorse1!', SALT);
    expect(a).toBe(b);
  });

  it('is keyed by the master password (different master → different fingerprint)', async () => {
    const a = await new CryptoService('master-A').passwordFingerprint('CorrectHorse1!', SALT);
    const b = await new CryptoService('master-B').passwordFingerprint('CorrectHorse1!', SALT);
    expect(a).not.toBe(b);
  });

  it('is keyed by the per-user salt (different salt → different fingerprint)', async () => {
    const svc = new CryptoService('master-password');
    const a = await svc.passwordFingerprint('CorrectHorse1!', 'salt-1');
    const b = await svc.passwordFingerprint('CorrectHorse1!', 'salt-2');
    expect(a).not.toBe(b);
  });

  it('distinguishes different passwords', async () => {
    const svc = new CryptoService('master-password');
    const a = await svc.passwordFingerprint('password-one', SALT);
    const b = await svc.passwordFingerprint('password-two', SALT);
    expect(a).not.toBe(b);
  });

  it('is NOT a bare hash of the password (keyed, not offline-guessable)', async () => {
    const svc = new CryptoService('master-password');
    const fp = await svc.passwordFingerprint('CorrectHorse1!', SALT);

    // A server holding only the fingerprint cannot reproduce it without the key:
    // it must differ from a plain digest of the password (with or without the
    // domain prefix).
    const barePlain = (await bareSha256B64Url('CorrectHorse1!')).slice(0, 24);
    const bareDomain = (await bareSha256B64Url('adaptive-pw|CorrectHorse1!')).slice(0, 24);
    expect(fp).not.toBe(barePlain);
    expect(fp).not.toBe(bareDomain);
  });

  it('returns a 24-char base64url token (no +/=)', async () => {
    const svc = new CryptoService('master-password');
    const fp = await svc.passwordFingerprint('CorrectHorse1!', SALT);
    expect(fp).toMatch(/^[A-Za-z0-9_-]{24}$/);
  });

  it('rejects an empty password and a missing salt', async () => {
    const svc = new CryptoService('master-password');
    await expect(svc.passwordFingerprint('', SALT)).rejects.toThrow(/non-empty password/);
    await expect(svc.passwordFingerprint('pw', '')).rejects.toThrow(/per-user salt/);
  });

  it('derives the fingerprint key once per salt (cached)', async () => {
    const svc = new CryptoService('master-password');
    await svc.passwordFingerprint('password-one', SALT);
    await svc.passwordFingerprint('password-two', SALT); // same salt → cache hit
    expect(argon2.hash).toHaveBeenCalledTimes(1);

    await svc.passwordFingerprint('password-one', 'another-salt'); // new salt → re-derive
    expect(argon2.hash).toHaveBeenCalledTimes(2);
  });

  it('never leaks the raw password through the fingerprint value', async () => {
    const svc = new CryptoService('master-password');
    const secret = 'Sup3rSecret-Passw0rd!';
    const fp = await svc.passwordFingerprint(secret, SALT);
    expect(fp).not.toContain(secret);
    expect(fp.length).toBe(24);
  });
});

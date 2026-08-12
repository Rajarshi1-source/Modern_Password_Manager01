/**
 * Unit tests for `sessionVaultCryptoV3.verifyMasterPassword` /
 * `canVerifyMasterPassword` — the verify-only primitive behind the adaptive
 * password feature's "check before you derive" guard.
 *
 * Why this exists: Argon2id has no "wrong password" outcome — it derives
 * different-but-well-formed key material from ANY input — so any feature that
 * re-asks for the master password and derives from it directly succeeds on a
 * typo. The AES-GCM unwrap exercised here is the actual check.
 *
 * argon2-browser doesn't run cleanly under jsdom, so it is mocked with a
 * deterministic SHA-256 KDF stand-in (the same approach already used by
 * cryptoService.fingerprint.test.js). The properties under test — right
 * password passes, wrong password throws, nothing is unlocked as a side
 * effect, the cache tracks rotations — are independent of the specific KDF.
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
  default: { get: vi.fn(), put: vi.fn(), post: vi.fn() },
}));

const RIGHT = 'correct-horse-battery-staple';
const WRONG = 'correct-horse-battery-stapl3';
const DEK_ID = '11111111-2222-3333-4444-555555555555';

let v3;

/**
 * Enroll once against a mocked server so a real wrapped-DEK envelope exists,
 * then hand back the blob the "server" would store. Uses the module's own
 * enrollment path rather than hand-rolling an envelope, so the test can never
 * drift from the real wrap format.
 */
async function enroll(password = RIGHT) {
  vi.mocked(axios.put).mockResolvedValue({ data: { dek_id: DEK_ID } });
  await v3.enrollWithMasterPassword(password);
  return vi.mocked(axios.put).mock.calls.at(-1)[1].blob;
}

describe('sessionVaultCryptoV3 master-password verification', () => {
  beforeAll(() => {
    if (!globalThis.window) globalThis.window = globalThis;
    if (!window.crypto || !window.crypto.subtle) {
      Object.defineProperty(window, 'crypto', {
        value: globalThis.crypto,
        configurable: true,
      });
    }
  });

  beforeEach(async () => {
    vi.clearAllMocks();
    // Fresh module instance per test: the blob cache is module-level state.
    vi.resetModules();
    v3 = await import('../sessionVaultCryptoV3');
  });

  it('cannot verify before any unlock or enrollment', () => {
    expect(v3.canVerifyMasterPassword()).toBe(false);
  });

  it('rejects with an actionable error when nothing is cached to check', async () => {
    await expect(v3.verifyMasterPassword(RIGHT)).rejects.toThrow(
      /sign out and back in/i,
    );
  });

  it('accepts the correct password after unlockWithMasterPassword', async () => {
    const blob = await enroll();
    vi.resetModules();
    v3 = await import('../sessionVaultCryptoV3');
    vi.mocked(axios.get).mockResolvedValue({
      data: { enrolled: true, blob, dek_id: DEK_ID },
    });

    await v3.unlockWithMasterPassword(RIGHT);

    expect(v3.canVerifyMasterPassword()).toBe(true);
    await expect(v3.verifyMasterPassword(RIGHT)).resolves.toBe(true);
  });

  it('rejects a wrong password', async () => {
    await enroll();
    await expect(v3.verifyMasterPassword(WRONG)).rejects.toThrow(
      /incorrect password/i,
    );
  });

  it('verifies without a network request', async () => {
    await enroll();
    vi.mocked(axios.get).mockClear();

    await v3.verifyMasterPassword(RIGHT);

    // The wrapped-DEK endpoint is throttled at 3/hour/user, a budget login
    // already spends one of. A verify-by-GET would starve the next login's
    // unlock, so this is a hard requirement, not an optimization.
    expect(axios.get).not.toHaveBeenCalled();
  });

  it('does not unlock or alter session state as a side effect', async () => {
    await enroll();
    const dekIdBefore = v3.getSessionDEKId();
    const hasKeyBefore = v3.hasSessionKey();

    await v3.verifyMasterPassword(RIGHT);
    await v3.verifyMasterPassword(WRONG).catch(() => {});

    expect(v3.getSessionDEKId()).toBe(dekIdBefore);
    expect(v3.hasSessionKey()).toBe(hasKeyBefore);
  });

  it('stops being able to verify after clearSessionKey', async () => {
    await enroll();
    expect(v3.canVerifyMasterPassword()).toBe(true);

    v3.clearSessionKey();

    expect(v3.canVerifyMasterPassword()).toBe(false);
    await expect(v3.verifyMasterPassword(RIGHT)).rejects.toThrow(
      /sign out and back in/i,
    );
  });

  it('tracks a master-password rotation instead of accepting the old one', async () => {
    // The stale-cache trap: if changeMasterPassword does not refresh the
    // cached envelope, verification keeps accepting the OLD password and
    // rejects the new one — worse than the unverified derivation this
    // primitive exists to prevent.
    const NEW = 'a-brand-new-master-password';
    await enroll(RIGHT);
    vi.mocked(axios.get).mockResolvedValue({
      data: {
        enrolled: true,
        blob: vi.mocked(axios.put).mock.calls.at(-1)[1].blob,
        dek_id: DEK_ID,
      },
    });
    vi.mocked(axios.put).mockResolvedValue({ data: { dek_id: DEK_ID } });

    await v3.changeMasterPassword(RIGHT, NEW);

    await expect(v3.verifyMasterPassword(NEW)).resolves.toBe(true);
    await expect(v3.verifyMasterPassword(RIGHT)).rejects.toThrow(
      /incorrect password/i,
    );
  });
});

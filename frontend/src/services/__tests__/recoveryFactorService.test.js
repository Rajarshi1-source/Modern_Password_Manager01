import { afterEach, describe, expect, it, vi } from 'vitest';

vi.mock('axios', () => ({
  default: {
    get: vi.fn(),
    put: vi.fn(),
    post: vi.fn(),
  },
}));

import axios from 'axios';
import {
  getWrappedDEK,
  putWrappedDEK,
  listRecoveryFactors,
  createRecoveryFactor,
  enrollTimeLock,
  initiateTimeLock,
  pollTimeLockRelease,
  acknowledgeCanary,
} from '../recoveryFactorService.js';

afterEach(() => {
  vi.clearAllMocks();
});

describe('recoveryFactorService — wrapped-DEK endpoints', () => {
  it('getWrappedDEK returns server payload as-is', async () => {
    axios.get.mockResolvedValueOnce({ data: { enrolled: true, blob: { v: 'wdek-1' }, dek_id: 'abc' } });
    const r = await getWrappedDEK();
    expect(axios.get).toHaveBeenCalledWith('/api/auth/vault/wrapped-dek/');
    expect(r).toEqual({ enrolled: true, blob: { v: 'wdek-1' }, dek_id: 'abc' });
  });

  it('putWrappedDEK omits dek_id when not provided', async () => {
    axios.put.mockResolvedValueOnce({ data: { success: true, dek_id: 'd' } });
    await putWrappedDEK({ v: 'wdek-1' });
    expect(axios.put).toHaveBeenCalledWith('/api/auth/vault/wrapped-dek/', { blob: { v: 'wdek-1' } });
  });

  it('putWrappedDEK includes dek_id when provided', async () => {
    axios.put.mockResolvedValueOnce({ data: { success: true, dek_id: 'd' } });
    await putWrappedDEK({ v: 'wdek-1' }, 'd');
    expect(axios.put).toHaveBeenCalledWith('/api/auth/vault/wrapped-dek/', {
      blob: { v: 'wdek-1' },
      dek_id: 'd',
    });
  });
});

describe('recoveryFactorService — recovery-factors endpoints', () => {
  it('listRecoveryFactors hits GET /recovery-factors/', async () => {
    axios.get.mockResolvedValueOnce({ data: [] });
    await listRecoveryFactors();
    expect(axios.get).toHaveBeenCalledWith('/api/auth/vault/recovery-factors/');
  });

  it('createRecoveryFactor sends snake_case body', async () => {
    axios.post.mockResolvedValueOnce({ data: { success: true, factor_id: 1 } });
    await createRecoveryFactor({ factorType: 'recovery_key', dekId: 'd', blob: { v: 'wdek-1' } });
    expect(axios.post).toHaveBeenCalledWith('/api/auth/vault/recovery-factors/', {
      factor_type: 'recovery_key',
      dek_id: 'd',
      blob: { v: 'wdek-1' },
      meta: {},
    });
  });
});

describe('recoveryFactorService — time-locked endpoints', () => {
  it('enrollTimeLock posts base64 server_half + half_metadata', async () => {
    axios.post.mockResolvedValueOnce({ data: { success: true, recovery_id: 1 } });
    await enrollTimeLock({ serverHalf: 'aGFsZg==', halfMetadata: { v: 'dlrec-1' } });
    expect(axios.post).toHaveBeenCalledWith('/api/auth/vault/time-locked/enroll/', {
      server_half: 'aGFsZg==',
      half_metadata: { v: 'dlrec-1' },
    });
  });

  it('initiateTimeLock posts username', async () => {
    axios.post.mockResolvedValueOnce({ data: { success: true } });
    await initiateTimeLock('alice');
    expect(axios.post).toHaveBeenCalledWith('/api/auth/vault/time-locked/initiate/', {
      username: 'alice',
    });
  });

  it('pollTimeLockRelease translates 403 → { ready: false, releaseAfter }', async () => {
    axios.post.mockRejectedValueOnce({ response: { status: 403, data: { release_after: '2026-05-10T00:00:00Z' } } });
    const r = await pollTimeLockRelease('alice');
    expect(r).toEqual({ ready: false, releaseAfter: '2026-05-10T00:00:00Z' });
  });

  it('pollTimeLockRelease returns { ready: true, ...data } on 200', async () => {
    axios.post.mockResolvedValueOnce({ data: { server_half: 'aGFsZg==', half_metadata: {} } });
    const r = await pollTimeLockRelease('alice');
    expect(r).toEqual({ ready: true, server_half: 'aGFsZg==', half_metadata: {} });
  });

  it('pollTimeLockRelease bubbles non-403 errors', async () => {
    axios.post.mockRejectedValueOnce({ response: { status: 500, data: {} } });
    await expect(pollTimeLockRelease('alice')).rejects.toBeTruthy();
  });

  it('acknowledgeCanary posts token', async () => {
    axios.post.mockResolvedValueOnce({ data: { success: true } });
    await acknowledgeCanary('xyz-token');
    expect(axios.post).toHaveBeenCalledWith('/api/auth/vault/time-locked/canary-ack/', {
      token: 'xyz-token',
    });
  });
});

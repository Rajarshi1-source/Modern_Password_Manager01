/**
 * recoveryFactorService.js — REST client for the layered-recovery API.
 *
 * Pure data-plumbing: all wrapping/unwrapping is done in
 * sessionVaultCryptoV3.js. This module only marshals JSON over HTTP.
 *
 * Endpoints:
 *   GET  /api/auth/vault/wrapped-dek/                  -> { enrolled, blob?, dek_id? }
 *   PUT  /api/auth/vault/wrapped-dek/                  -> { success, dek_id }
 *   GET  /api/auth/vault/recovery-factors/             -> [factor]
 *   POST /api/auth/vault/recovery-factors/             -> { success, factor_id }
 *   POST /api/auth/vault/time-locked/enroll/           -> { success, recovery_id }
 *   POST /api/auth/vault/time-locked/initiate/         -> { success, release_after? }
 *   POST /api/auth/vault/time-locked/release/          -> { ready, server_half?, half_metadata?, releaseAfter? }
 *   POST /api/auth/vault/time-locked/canary-ack/       -> { success }
 */
import axios from 'axios';

const BASE = '/api/auth/vault';

export async function getWrappedDEK() {
  const { data } = await axios.get(`${BASE}/wrapped-dek/`);
  return data;
}

export async function putWrappedDEK(blob, dekId) {
  const body = dekId ? { blob, dek_id: dekId } : { blob };
  const { data } = await axios.put(`${BASE}/wrapped-dek/`, body);
  return data;
}

export async function listRecoveryFactors() {
  const { data } = await axios.get(`${BASE}/recovery-factors/`);
  return data;
}

export async function createRecoveryFactor({ factorType, dekId, blob, meta = {} }) {
  const { data } = await axios.post(`${BASE}/recovery-factors/`, {
    factor_type: factorType,
    dek_id: dekId,
    blob,
    meta,
  });
  return data;
}

export async function enrollTimeLock({ serverHalf, halfMetadata = {} }) {
  const { data } = await axios.post(`${BASE}/time-locked/enroll/`, {
    server_half: serverHalf, // base64 string
    half_metadata: halfMetadata,
  });
  return data;
}

export async function initiateTimeLock(username) {
  const { data } = await axios.post(`${BASE}/time-locked/initiate/`, { username });
  return data;
}

/**
 * Polls for the server's Shamir half.
 *
 * The release endpoint can return 403 for two semantically distinct
 * reasons (see `TimeLockedReleaseView` in
 * `password_manager/auth_module/time_locked_view.py`):
 *
 *   1. Delay not elapsed — body is `{error, release_after}`. The
 *      caller should keep polling; we translate to
 *      `{ ready: false, releaseAfter }` so the countdown UI doesn't
 *      have to wrap every poll in try/catch.
 *
 *   2. Cancelled by canary acknowledgement — body is `{error}` (no
 *      `release_after`). The caller should STOP polling and surface
 *      the cancellation. We re-throw so the UI's catch block sees it.
 *
 * Any other 403 (auth/permission errors, throttling, CSRF, etc.) is
 * also re-thrown — it would be wrong to silently treat them as "still
 * waiting" and keep the user polling forever.
 *
 * Other status codes (5xx, network errors) bubble unchanged.
 */
export async function pollTimeLockRelease(username) {
  try {
    const { data } = await axios.post(`${BASE}/time-locked/release/`, { username });
    return { ready: true, ...data };
  } catch (err) {
    const body = err.response?.data;
    if (
      err.response?.status === 403 &&
      body &&
      typeof body.release_after === 'string'
    ) {
      // Specifically the "delay not elapsed" shape — keep polling.
      return { ready: false, releaseAfter: body.release_after };
    }
    // Anything else (cancelled-by-canary 403, real authz errors,
    // 5xx, etc.) bubbles to the caller.
    throw err;
  }
}

export async function acknowledgeCanary(token) {
  const { data } = await axios.post(`${BASE}/time-locked/canary-ack/`, { token });
  return data;
}

export default {
  getWrappedDEK,
  putWrappedDEK,
  listRecoveryFactors,
  createRecoveryFactor,
  enrollTimeLock,
  initiateTimeLock,
  pollTimeLockRelease,
  acknowledgeCanary,
};

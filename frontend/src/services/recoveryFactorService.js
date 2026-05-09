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

/**
 * Fetch the authenticated user's wrapped DEK envelope.
 *
 * @returns {Promise<{enrolled: boolean, blob?: object, dek_id?: string}>}
 *   - `enrolled: false` when the user has not yet provisioned a wrapped DEK.
 *   - When enrolled, `blob` is the opaque envelope (`{v: 'wdek-1', kdf,
 *     kdf_params, salt, iv, wrapped}`) and `dek_id` is the stable UUID
 *     that recovery factors were enrolled against.
 */
export async function getWrappedDEK() {
  const { data } = await axios.get(`${BASE}/wrapped-dek/`);
  return data;
}

/**
 * Create or rotate the wrapped DEK on the server.
 *
 * On first PUT (no existing row) `dekId` is omitted and the server mints
 * a new UUID. On subsequent PUTs (master-password rotation) `dekId` MUST
 * match the user's current `dek_id`; otherwise the server returns 409.
 * Refusing to clobber DEK identity is what protects existing recovery
 * factors from being silently orphaned.
 *
 * @param {object} blob   - Opaque envelope produced by sessionVaultCryptoV3.
 * @param {string} [dekId] - Existing dek_id when rotating; omit on first PUT.
 * @returns {Promise<{success: true, dek_id: string}>}
 */
export async function putWrappedDEK(blob, dekId) {
  const body = dekId ? { blob, dek_id: dekId } : { blob };
  const { data } = await axios.put(`${BASE}/wrapped-dek/`, body);
  return data;
}

/**
 * List the user's active recovery factors (recovery key / social mesh /
 * time-locked / passkey).
 *
 * @returns {Promise<Array<{id, factor_type, dek_id, created_at, last_used_at, meta}>>}
 *   Active factors only; revoked rows are filtered server-side.
 */
export async function listRecoveryFactors() {
  const { data } = await axios.get(`${BASE}/recovery-factors/`);
  return data;
}

/**
 * Enroll a new recovery factor (the wrapped DEK under a different KEK).
 *
 * @param {object} args
 * @param {('recovery_key'|'social_mesh'|'time_locked'|'passkey')} args.factorType
 *   Which factor type this row represents.
 * @param {string} args.dekId - Current dek_id (proof-of-DEK-possession).
 * @param {object} args.blob  - Wrapped envelope produced by sessionVaultCryptoV3.
 * @param {object} [args.meta] - Public, non-secret metadata about the factor.
 * @returns {Promise<{success: true, factor_id: number}>}
 */
export async function createRecoveryFactor({ factorType, dekId, blob, meta = {} }) {
  const { data } = await axios.post(`${BASE}/recovery-factors/`, {
    factor_type: factorType,
    dek_id: dekId,
    blob,
    meta,
  });
  return data;
}

/**
 * Persist the server's Shamir 2-of-2 half for tier-3 self-time-locked
 * recovery. The user keeps the matching half offline in a `.dlrec` file;
 * the server's half alone is information-theoretically useless without
 * the user's half.
 *
 * @param {object} args
 * @param {string} args.serverHalf - Base64-encoded opaque share bytes.
 * @param {object} [args.halfMetadata] - Public metadata (e.g. dlrec version).
 * @returns {Promise<{success: true, recovery_id: number}>}
 */
export async function enrollTimeLock({ serverHalf, halfMetadata = {} }) {
  const { data } = await axios.post(`${BASE}/time-locked/enroll/`, {
    server_half: serverHalf, // base64 string
    half_metadata: halfMetadata,
  });
  return data;
}

/**
 * Atomic single-call enrollment for tier-3 time-locked recovery.
 *
 * Combines what used to be two separate calls — `enrollTimeLock`
 * (server half) and `createRecoveryFactor({factorType:'time_locked'})`
 * (wdek row) — into one server-side transaction. Either both writes
 * commit or neither does, so a partial failure cannot leave the user
 * worse off than they started (the previous two-call flow was
 * destructive in either ordering for users who already had an
 * enrolled time-lock).
 *
 * The seed is still generated and Shamir-split locally; only the
 * server-side write coordination moves to one endpoint.
 *
 * @param {object} args
 * @param {string} args.serverHalf      - base64 of halfB
 * @param {object} [args.halfMetadata]  - public metadata (e.g. dlrec v)
 * @param {string} args.dekId           - current dek_id (proof-of-DEK)
 * @param {object} args.blob            - wdek-1 envelope wrapping the DEK
 * @param {object} [args.factorMeta]    - public metadata for the factor row
 * @returns {Promise<{success: true, recovery_id: number, factor_id: number}>}
 */
export async function enrollTimeLockBundle({
  serverHalf,
  halfMetadata = {},
  dekId,
  blob,
  factorMeta = {},
  authHash,
}) {
  const { data } = await axios.post(`${BASE}/time-locked/enroll-bundle/`, {
    server_half: serverHalf,
    half_metadata: halfMetadata,
    dek_id: dekId,
    blob,
    factor_meta: factorMeta,
    auth_hash: authHash,
  });
  return data;
}

/**
 * Anonymous lookup of a wrapped recovery factor by username + factor type.
 *
 * Used by the unauthenticated recovery pages: the user has forgotten
 * the master password and so cannot call the authenticated GET
 * `/recovery-factors/`, but the recovery flow still needs the wrapped
 * factor blob to feed the recovery secret into
 * `unlockWithRecoveryFactor`. The backend returns the same shape for
 * unknown usernames (a decoy `blob` + fresh `dek_id`), so an attacker
 * cannot use this endpoint to enumerate accounts.
 *
 * @param {string} username
 * @param {('recovery_key'|'social_mesh'|'time_locked'|'passkey')} factorType
 * @returns {Promise<{blob: object, dek_id: string}>}
 */
export async function lookupRecoveryFactor(username, factorType) {
  const { data } = await axios.post(`${BASE}/recovery-factors/lookup/`, {
    username,
    factor_type: factorType,
  });
  return data;
}

/**
 * Begin the tier-3 time-lock delay clock for a username.
 *
 * The endpoint returns the same uniform shape regardless of whether
 * the username exists or has an enrollment, so callers cannot use the
 * response to probe accounts. For unknown / un-enrolled accounts the
 * server synthesizes a decoy `release_after` indistinguishable from a
 * real one.
 *
 * @param {string} username
 * @returns {Promise<{success: true, release_after: string}>}
 */
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

/**
 * Acknowledge the opaque canary token from a recovery-alert email/SMS
 * to cancel an in-flight tier-3 recovery the legitimate user did not
 * initiate.
 *
 * The endpoint always returns `{success: true}` regardless of token
 * validity, so an attacker scraping random tokens cannot distinguish
 * "valid but already used" from "invalid". A real cancellation is
 * visible only via the subsequent `release` 403 (cancelled-by-canary)
 * and the audit log row.
 *
 * @param {string} token - Bearer canary token from the alert URL.
 * @returns {Promise<{success: true}>}
 */
export async function acknowledgeCanary(token) {
  const { data } = await axios.post(`${BASE}/time-locked/canary-ack/`, { token });
  return data;
}

export default {
  getWrappedDEK,
  putWrappedDEK,
  listRecoveryFactors,
  createRecoveryFactor,
  lookupRecoveryFactor,
  enrollTimeLock,
  enrollTimeLockBundle,
  initiateTimeLock,
  pollTimeLockRelease,
  acknowledgeCanary,
};

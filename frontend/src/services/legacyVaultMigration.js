/**
 * legacyVaultMigration.js — migration from the legacy direct-
 * derivation user (PBKDF2 session key in v2) to the wrapped-DEK
 * model (v3).
 *
 * Split into TWO entry points so the per-item rewrite is retryable
 * across logins:
 *
 *   * `migrateLegacyUserToWrappedDEK` — called once when v3
 *     `unlockWithMasterPassword` returns `NOT_ENROLLED`.
 *     Bootstraps the legacy session key, mints a v3 wrapped DEK,
 *     and runs the per-item rewrite once. Returns
 *     `{ migratedCount, totalCount, enrolled: true }` so the caller
 *     can skip the unconditional outer sweep on this login.
 *
 *   * `migrateRemainingV2Items` — called on every successful login
 *     once v3 is unlocked. Walks the vault (across all paginated
 *     pages), finds items still in the v2 envelope, and re-encrypts
 *     them under v3. No-op if nothing is left to migrate. The first
 *     per-account run does the bulk of the work; subsequent runs
 *     catch items that missed the first pass (network blip, PUT
 *     failure, etc.).
 *
 * ZK invariant: the master password and DEK never leave the
 * browser. Each rewrite is decrypt-with-old / encrypt-with-new /
 * PATCH, all client-side. The server only ever sees ciphertext.
 *
 * IMPORTANT — v2 key lifetime: we do NOT clear the v2 session key
 * here. The rest of the app currently still reads/writes items
 * through `sessionVaultCrypto` (v2); clearing the key mid-session
 * would immediately break vault access in the same browser tab
 * that just completed migration. The v2 key is dropped on
 * `handleLogout` (which already clears both v2 and v3 paths).
 * As more code paths migrate to v3, the eventual full retirement
 * of v2 can drop the key here too.
 *
 * Concurrency: a module-level in-flight Promise singleton ensures
 * that two near-simultaneous callers (e.g. two tabs, or a
 * double-fired login) share the same sweep rather than racing
 * decrypt-and-rewrite against each other on the same rows.
 */
import axios from 'axios';
import * as legacyV2 from './sessionVaultCrypto';
import sessionVaultCryptoV3 from './sessionVaultCryptoV3';

// Module-level single-flight guard. Subsequent calls to
// `migrateRemainingV2Items` while a sweep is already running
// (e.g. another tab, or a fast double-login) await the existing
// Promise instead of racing on the same items.
let inFlightSweep = null;

/**
 * Fetch ALL vault items across DRF's `LimitOffsetPagination`. The
 * settings configure PAGE_SIZE=100 so a single GET only returns the
 * first page; without pagination handling, anything beyond item 100
 * would silently miss migration on every login.
 *
 * @returns {Promise<Array<object>>}
 */
async function fetchAllVaultItems() {
  const out = [];
  let url = '/api/vault/';
  while (url) {
    // eslint-disable-next-line no-await-in-loop -- sequential by design
    const { data } = await axios.get(url);
    if (Array.isArray(data)) {
      out.push(...data);
      break; // Non-paginated response.
    }
    if (Array.isArray(data?.results)) {
      out.push(...data.results);
      url = data.next || null;
      continue;
    }
    break; // Unrecognised shape — stop and report what we have.
  }
  return out;
}

/**
 * Walk vault items and re-encrypt any that still live in the legacy
 * v2 envelope under the active v3 DEK. Safe to call on every login —
 * if nothing is left to migrate, this is a single GET + zero PATCHes.
 *
 * Items whose `encrypted_data` parses to a v3 (`svc-gcm-2`) envelope
 * are detected by `legacyV2.decryptItem` returning
 * `{_legacyPlaintext: true}` (the v2 decryptor treats any non-v2
 * envelope as legacy/unparseable) and skipped. `{_staleDek: true}`
 * is the analogous sentinel returned by v3's own decryptItem when
 * a payload's `dek_id` doesn't match the session DEK; if the v2
 * decryptor ever surfaces that shape we treat it the same way —
 * "leave it alone, it's not ours to migrate."
 *
 * Per-item failures (decrypt throw, encrypt throw, network PATCH
 * failure) are caught and logged but never abort the sweep — a
 * single bad row cannot block migration of the rest.
 *
 * @returns {Promise<{migratedCount: number, totalCount: number}>}
 */
export async function migrateRemainingV2Items() {
  // Coalesce concurrent calls onto a single in-flight Promise so we
  // can't double-rewrite the same items from two tabs.
  if (inFlightSweep) return inFlightSweep;
  inFlightSweep = (async () => {
    let list;
    try {
      list = await fetchAllVaultItems();
    } catch (err) {
      // eslint-disable-next-line no-console
      console.warn('legacyVaultMigration: could not list vault items:', err);
      return { migratedCount: 0, totalCount: 0 };
    }

    let migratedCount = 0;
    for (const item of list) {
      let plain;
      try {
        // eslint-disable-next-line no-await-in-loop -- sequential by design
        plain = await legacyV2.decryptItem(item.encrypted_data);
      } catch (err) {
        // eslint-disable-next-line no-console
        console.warn(`legacyVaultMigration: skipped item ${item.id}:`, err?.message);
        continue;
      }
      if (plain?._legacyPlaintext || plain?._staleDek) {
        // Already under v3 (or unparseable); leave it alone.
        continue;
      }
      // CRITICAL: encrypt + PATCH wrapped in a SINGLE try so a
      // failure in either step (e.g. a malformed plaintext that
      // crashes the v3 encryptor, or a transient PATCH 500) is
      // contained to the one item. Previously encryptItem lived
      // outside the try and a single rejection aborted the whole
      // sweep — contradicting the "Per-item failures don't abort
      // the whole pass" contract in the function docstring.
      try {
        // eslint-disable-next-line no-await-in-loop
        const reencrypted = await sessionVaultCryptoV3.encryptItem(plain);
        // PATCH (not PUT) so we only update encrypted_data; PUT
        // with `...item` would re-send writable fields like
        // item_type / folder_id / favorite / tags / last_used_at
        // with stale values, clobbering any concurrent edit made
        // from another tab or device between this client's GET
        // and PATCH.
        // eslint-disable-next-line no-await-in-loop
        await axios.patch(`/api/vault/${item.id}/`, {
          encrypted_data: reencrypted,
        });
        migratedCount += 1;
      } catch (err) {
        // eslint-disable-next-line no-console
        console.warn(`legacyVaultMigration: rewrite failed for ${item.id}:`, err);
      }
    }
    return { migratedCount, totalCount: list.length };
  })().finally(() => {
    inFlightSweep = null;
  });
  return inFlightSweep;
}

/**
 * First-time NOT_ENROLLED handler. Bootstraps the v2 session key,
 * mints a v3 wrapped DEK, then runs the per-item sweep once.
 *
 * Returns `{ enrolled: true, ...sweepResult }` so the caller can
 * skip the unconditional outer sweep on this login (the inner one
 * already ran). On any subsequent login, the unconditional sweep
 * runs alone and the first-time path is skipped because v3 unlock
 * succeeds.
 *
 * Fail-loud on missing init: if `legacyV2.initSessionKeyFromPassword`
 * is unavailable (export renamed/removed), we throw rather than
 * silently no-op. Without the v2 key, every subsequent
 * `legacyV2.decryptItem` call inside the sweep would throw and be
 * skipped, producing a "successful" migration that migrated zero
 * items — and `NOT_ENROLLED` would never fire again to retry.
 *
 * @param {string} masterPassword
 * @param {string} userIdOrEmail
 * @returns {Promise<{migratedCount: number, totalCount: number, enrolled: true}>}
 */
export async function migrateLegacyUserToWrappedDEK(masterPassword, userIdOrEmail) {
  if (typeof legacyV2.initSessionKeyFromPassword !== 'function') {
    throw new Error(
      'legacyVaultMigration: sessionVaultCrypto.initSessionKeyFromPassword '
      + 'is unavailable; cannot bootstrap v2 key for migration. App.jsx '
      + 'should fall back to v2-only operation for this session.',
    );
  }
  await legacyV2.initSessionKeyFromPassword(masterPassword, userIdOrEmail);

  // Mint a v3 wrapped DEK. The handleLogin caller catches errors
  // around the whole migration so we don't need a try/catch.
  await sessionVaultCryptoV3.enrollWithMasterPassword(masterPassword);

  // Re-encrypt every v2 item under the new DEK. We deliberately do
  // NOT clear the v2 session key after this — see module docstring.
  const sweepResult = await migrateRemainingV2Items();
  return { ...sweepResult, enrolled: true };
}

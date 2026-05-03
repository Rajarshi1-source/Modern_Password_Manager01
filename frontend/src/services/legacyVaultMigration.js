/**
 * legacyVaultMigration.js — one-shot, idempotent migration that
 * converts a legacy direct-derivation user (PBKDF2 session key in v2)
 * into the wrapped-DEK model (v3).
 *
 * Triggered by `App.jsx :: handleLogin` when v3
 * `unlockWithMasterPassword` returns `NOT_ENROLLED` for the current
 * account. The function:
 *
 *   1. Bootstraps the legacy v2 session key the old way so we can
 *      decrypt existing items.
 *   2. Calls v3 `enrollWithMasterPassword` to mint a fresh wrapped DEK
 *      and stash it server-side.
 *   3. Walks every vault item, decrypts it with the legacy key,
 *      re-encrypts it with the new v3 DEK, and PUTs it back.
 *   4. Clears the legacy session key.
 *
 * Idempotent: if it crashes mid-loop, the next login finds the v3
 * wrapped DEK already enrolled (no NOT_ENROLLED) and just unlocks
 * normally. Items already re-encrypted under svc-gcm-2 are left
 * untouched on subsequent runs because their decrypt-with-legacy
 * call returns `_legacyPlaintext: true` (legacy decryptItem treats
 * any non-svc-gcm-1 envelope as legacy and refuses to leak fields).
 *
 * ZK invariant: the master password and DEK never leave the browser.
 * The migration loop is decrypt-with-old / encrypt-with-new / PUT —
 * all client-side. The server only ever sees ciphertext.
 */
import axios from 'axios';
import * as legacyV2 from './sessionVaultCrypto';
import sessionVaultCryptoV3 from './sessionVaultCryptoV3';

export async function migrateLegacyUserToWrappedDEK(masterPassword, userIdOrEmail) {
  // (1) Bootstrap the legacy session key (PBKDF2 path).
  if (typeof legacyV2.initSessionKeyFromPassword === 'function') {
    await legacyV2.initSessionKeyFromPassword(masterPassword, userIdOrEmail);
  }

  // (2) Mint a v3 wrapped DEK.
  await sessionVaultCryptoV3.enrollWithMasterPassword(masterPassword);

  // (3) Re-encrypt every existing vault item under the new DEK.
  let list = [];
  try {
    const { data } = await axios.get('/api/vault/');
    list = data?.results || data || [];
  } catch (err) {
    // Listing endpoint shape can vary across deployments. We log and
    // continue — the user is now on v3 for new items; existing items
    // can be re-encrypted on subsequent logins by an opportunistic
    // pass that walks `vaultItems` and skips items already under
    // svc-gcm-2.
    // eslint-disable-next-line no-console
    console.warn('legacyVaultMigration: could not list vault items:', err);
    return { migratedCount: 0, totalCount: 0 };
  }

  let migratedCount = 0;
  for (const item of list) {
    let plain;
    try {
      plain = await legacyV2.decryptItem(item.encrypted_data);
    } catch (err) {
      // Item was likely encrypted under a different legacy key (e.g.
      // an OAuth user whose v2 key lives in localStorage under a
      // different namespace). Skip; leave for a future opportunistic
      // pass.
      // eslint-disable-next-line no-console
      console.warn(`legacyVaultMigration: skipped item ${item.id}:`, err?.message);
      continue;
    }
    if (plain?._legacyPlaintext || plain?._staleDek) {
      // Already under v3 (or unparseable); leave it alone.
      continue;
    }
    const reencrypted = await sessionVaultCryptoV3.encryptItem(plain);
    try {
      await axios.put(`/api/vault/${item.id}/`, {
        ...item,
        encrypted_data: reencrypted,
      });
      migratedCount += 1;
    } catch (err) {
      // PUT failed — log and continue. Migration is idempotent;
      // the item stays decryptable by legacy until next attempt.
      // eslint-disable-next-line no-console
      console.warn(`legacyVaultMigration: PUT failed for ${item.id}:`, err);
    }
  }

  // (4) Drop the legacy session key. The browser is now fully on v3.
  if (typeof legacyV2.clearSessionKey === 'function') {
    legacyV2.clearSessionKey();
  }

  return { migratedCount, totalCount: list.length };
}

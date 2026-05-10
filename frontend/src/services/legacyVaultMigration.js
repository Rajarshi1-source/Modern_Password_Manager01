/**
 * legacyVaultMigration.js — migration from the legacy direct-
 * derivation user (PBKDF2 session key in v2) to the wrapped-DEK
 * model (v3).
 *
 * Split into TWO functions so the per-item rewrite is retryable
 * across logins:
 *
 *   * `migrateLegacyUserToWrappedDEK` — called once when v3
 *     `unlockWithMasterPassword` returns `NOT_ENROLLED`. Bootstraps
 *     the legacy session key, mints a v3 wrapped DEK, and then
 *     delegates to the per-item pass.
 *
 *   * `migrateRemainingV2Items` — called on every successful login
 *     once v3 is unlocked. Walks the vault, finds items still in
 *     the v2 envelope, and re-encrypts them under v3. No-op if
 *     nothing is left to migrate. The first per-account run does
 *     the bulk of the work; subsequent runs catch items that
 *     missed the first pass (network blip, PUT failure, etc.).
 *
 * ZK invariant: the master password and DEK never leave the
 * browser. Each rewrite is decrypt-with-old / encrypt-with-new /
 * PUT, all client-side. The server only ever sees ciphertext.
 *
 * IMPORTANT — v2 key lifetime: we do NOT clear the v2 session key
 * here. The rest of the app currently still reads/writes items
 * through `sessionVaultCrypto` (v2); clearing the key mid-session
 * would immediately break vault access in the same browser tab
 * that just completed migration. The v2 key is dropped on
 * `handleLogout` (which already calls both clearSessionKey paths).
 * As more code paths migrate to v3, the eventual full retirement
 * of v2 can drop the key here too.
 */
import axios from 'axios';
import * as legacyV2 from './sessionVaultCrypto';
import sessionVaultCryptoV3 from './sessionVaultCryptoV3';

/**
 * Walk vault items and re-encrypt any that still live in the legacy
 * v2 envelope under the active v3 DEK. Safe to call on every login —
 * if nothing is left to migrate, this is a single GET + zero PUTs.
 *
 * Items whose `encrypted_data` parses to a v3 (`svc-gcm-2`) envelope
 * are detected by `legacyV2.decryptItem` returning
 * `{_legacyPlaintext: true}` (the v2 decryptor treats any non-v2
 * envelope as legacy/unparseable) and skipped. Items whose decrypt
 * raises (different legacy key namespace, etc.) are skipped with a
 * warning so a single bad row cannot block migration of the others.
 *
 * @returns {Promise<{migratedCount: number, totalCount: number}>}
 */
export async function migrateRemainingV2Items() {
  let list = [];
  try {
    const { data } = await axios.get('/api/vault/');
    list = data?.results || data || [];
  } catch (err) {
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
      // Per-item failures don't abort the whole pass. The next
      // login will sweep again — see App.jsx :: handleLogin where
      // this function is called unconditionally after v3 unlock.
      // eslint-disable-next-line no-console
      console.warn(`legacyVaultMigration: PUT failed for ${item.id}:`, err);
    }
  }
  return { migratedCount, totalCount: list.length };
}

/**
 * First-time NOT_ENROLLED handler. Bootstraps the v2 session key,
 * mints a v3 wrapped DEK, then delegates the per-item rewrite to
 * `migrateRemainingV2Items`. Idempotent: if it crashes mid-loop,
 * the next login finds the v3 wrapped DEK already enrolled (no
 * NOT_ENROLLED) and the unconditional `migrateRemainingV2Items`
 * pass picks up the remaining items.
 *
 * @param {string} masterPassword
 * @param {string} userIdOrEmail - identifier the v2 KDF salts against.
 * @returns {Promise<{migratedCount: number, totalCount: number}>}
 */
export async function migrateLegacyUserToWrappedDEK(masterPassword, userIdOrEmail) {
  // (1) Bootstrap the legacy session key (PBKDF2 path). Keep it
  //     alive for the rest of the session — see module docstring.
  if (typeof legacyV2.initSessionKeyFromPassword === 'function') {
    await legacyV2.initSessionKeyFromPassword(masterPassword, userIdOrEmail);
  }

  // (2) Mint a v3 wrapped DEK. The handleLogin caller catches
  //     errors here so we don't need a try/catch.
  await sessionVaultCryptoV3.enrollWithMasterPassword(masterPassword);

  // (3) Re-encrypt every v2 item under the new DEK. We deliberately
  //     do NOT clear the v2 session key after this — App.jsx may
  //     still hold v2-encrypted items in memory that need to round-
  //     trip through v2 before the next render cycle picks up the
  //     freshly-rewritten ciphertext.
  return migrateRemainingV2Items();
}

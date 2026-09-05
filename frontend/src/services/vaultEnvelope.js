import sessionVaultCrypto from './sessionVaultCrypto';
import sessionVaultCryptoV3 from './sessionVaultCryptoV3';

/**
 * Decrypt a vault item's `encrypted_data` envelope into its plaintext object.
 *
 * Single source of truth for the v2→v3 decrypt path. The logic is lifted
 * verbatim from App.jsx's `VaultItemsSection.decryptOne` so the /vault list and
 * (once PR F lands) VaultContext share one proven implementation:
 *
 *   1. Try sessionVaultCrypto (v2) first.
 *   2. v2 flags envelopes it doesn't own (including v3 `svc-gcm-2` rows) as
 *      `{ _legacyPlaintext: true }`. When that happens AND a v3 session key is
 *      present, retry with sessionVaultCryptoV3 (v3).
 *   3. If the v3 retry throws, keep the v2 `_legacyPlaintext` result so the UI
 *      can still render its migration/warning state.
 *
 * @param {string} encrypted_data The stored envelope string.
 * @returns {Promise<object>} The decrypted object, or `{ _legacyPlaintext: true }`
 *   for envelopes neither layer can open. Propagates (throws) if v2 decryption
 *   itself fails (e.g. tampered ciphertext / locked vault) — callers decide how
 *   to surface that.
 */
export async function decryptEnvelope(encrypted_data) {
  const v2Result = await sessionVaultCrypto.decryptItem(encrypted_data);
  // The v3 fallback is the READ-side mirror of the write-side hole fixed in
  // `encryptEnvelope` below: a decoy unlock installs its DEK on v2 only and
  // does not clear a live v3 key, and v3 has no concept of a decoy session.
  // A REAL item cannot be opened by the decoy DEK, so v2 returns the
  // `_legacyPlaintext` marker -- which is exactly the condition that triggers
  // this fallback, handing back the real plaintext v2 correctly refused.
  //
  // Skipping the fallback (rather than refusing outright) is deliberate: v2
  // still decrypts the DECOY slot's own items normally, which is what makes
  // the decoy vault believable. Only the escape hatch to the real key closes.
  if (
    v2Result && v2Result._legacyPlaintext
    && !sessionVaultCrypto.isDecoySession()
    && sessionVaultCryptoV3.hasSessionKey()
  ) {
    // The decoy check above runs BEFORE this await, and v3's decrypt is a real
    // AES-GCM operation -- so a decoy unlock landing inside the window passes
    // the check and still returns the REAL plaintext v2 refused. §34.2 closed
    // the branch and left its own await open, which is the §26/§32/§36 shape
    // one more time.
    //
    // Guarded HERE rather than at the callers because there are six of them
    // (App.jsx, ExportVault.jsx, and four in VaultContext) and exactly one --
    // VaultContext's on-demand `decryptItem` -- carries the §34.1 caller-side
    // generation guard. The other five, including the vault EXPORT path, have
    // none. This is the choke point every one of them crosses.
    //
    // Generation AND decoy are both re-read: the counter moves on any
    // lock/install (so it catches a decoy unlock, a logout, or a newer real
    // unlock), while `isDecoySession()` also covers the case where the counter
    // happened to be captured after the transition.
    const generation = sessionVaultCrypto.currentSessionGeneration();
    try {
      const v3Result = await sessionVaultCryptoV3.decryptItem(encrypted_data);
      if (
        sessionVaultCrypto.currentSessionGeneration() !== generation
        || sessionVaultCrypto.isDecoySession()
      ) {
        // Return the v2 marker, not a throw: it is exactly what this function
        // yields for a decoy session that never entered the fallback, so the
        // two are indistinguishable to every caller.
        return v2Result;
      }
      return v3Result;
    } catch (v3Err) {
      console.warn('v3 fallback failed; falling back to v2 legacy-plaintext result', v3Err);
      return v2Result;
    }
  }
  return v2Result;
}

/**
 * Encrypt a plaintext vault item object into an `encrypted_data` envelope.
 *
 * Prefers v3 (`svc-gcm-2`) and falls back to v2 (`svc-gcm-1`).
 *
 * v3 first, because v2's key is derived from a salt that lives in this device's
 * localStorage and is never sent to the server. For path (A) (password-login,
 * the common case) this is no longer a hard portability wall — `sessionVaultCrypto`'s
 * `keyForSalt` reads the envelope's OWN salt and re-derives on any device, given
 * the master password — but path (B) (OAuth's wrapped-DEK fallback) has no
 * password to re-derive from, so ITS items stay genuinely device-local. Either
 * way there is no reason to keep MAKING new v2 items when v3 is available: v3's
 * DEK is wrapped server-side, survives master-password rotation, and is the
 * format the login-time sweep in `legacyVaultMigration` rewrites everything into
 * anyway — writing v2 here just queued each new item for a rewrite on the next
 * login.
 *
 * The v2 fallback is not vestigial and must stay:
 *   * OAuth sessions have no master password, so no v3 DEK — path (B)'s
 *     wrapped DEK in `sessionVaultCrypto` is their only key.
 *   * PR #478's degraded mode deliberately keeps the vault USABLE through v2
 *     when the v3 wrapped-DEK unlock fails on a master-password desync.
 *     Hard-failing writes here would undo that.
 *
 * @param {object} data The plaintext item fields to encrypt.
 * @returns {Promise<string>} The serialized envelope (v3 when available).
 * @throws If the vault is locked on both layers.
 */
export async function encryptEnvelope(data) {
  // The decoy gate has to sit HERE, ahead of the v2/v3 choice, not only inside
  // `sessionVaultCrypto.encryptItem`.
  //
  // A decoy unlock installs its DEK through `installRawDek` on v2 ONLY --
  // `VaultUnlockModal` never touches `sessionVaultCryptoV3`, and
  // `installRawDek` does not clear it -- while `sessionIsDecoy` lives in v2.
  // v3 has no concept of a decoy session at all. So whenever a v3 key is still
  // live, the branch below picks v3 and the v2 gate is never consulted: a
  // decoy session could encrypt an add or edit for the REAL vault, which is
  // the row-corrupting write that gate exists to stop (see `sessionIsDecoy`'s
  // own comment in sessionVaultCrypto.js for why such a row is unrecoverable).
  //
  // Gating at the choke point rather than in each implementation is the point:
  // this function is the single place add/edit reaches either layer, so a
  // future third layer cannot reintroduce the bypass by simply not knowing
  // about decoys.
  //
  // The message is BYTE-IDENTICAL to the one `sessionVaultCrypto.encryptItem`
  // raises, and must stay so: `VaultContext` surfaces `error.message` to the
  // screen, so two different refusal strings would tell a coercer which layer
  // declined -- a new tell in the very guard added to remove one. Not logged,
  // for the same §3.5 reason that gate gives.
  if (sessionVaultCrypto.isDecoySession()) {
    throw new Error(sessionVaultCrypto.DECOY_WRITE_REFUSAL);
  }
  if (sessionVaultCryptoV3.hasSessionKey()) {
    return sessionVaultCryptoV3.encryptItem(data);
  }
  return sessionVaultCrypto.encryptItem(data);
}

/**
 * Whether either crypto layer has a live session key -- the single source of
 * truth for "is the vault usable," matching `encryptEnvelope`'s own
 * v3-preferred-else-v2 write rule above.
 *
 * Extracted in review round 10 after this exact OR-of-both-layers check had
 * drifted out of sync 4 separate times across `App.jsx` (3 inline copies) and
 * `VaultContext.jsx` (1 copy) — including a real bug (round 3) where
 * `VaultContext`'s copy lagged a v2-only check after `App.jsx`'s had already
 * been fixed. A single exported predicate next to the write rule it mirrors
 * makes that drift structurally harder to reintroduce.
 *
 * @returns {boolean}
 */
export const hasVaultSessionKey = () =>
  sessionVaultCrypto.hasSessionKey() || sessionVaultCryptoV3.hasSessionKey();

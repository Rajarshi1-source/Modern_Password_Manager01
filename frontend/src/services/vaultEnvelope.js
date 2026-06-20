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
  if (v2Result && v2Result._legacyPlaintext && sessionVaultCryptoV3.hasSessionKey()) {
    try {
      return await sessionVaultCryptoV3.decryptItem(encrypted_data);
    } catch (v3Err) {
      console.warn('v3 fallback failed; falling back to v2 legacy-plaintext result', v3Err);
      return v2Result;
    }
  }
  return v2Result;
}

/**
 * Encrypt a plaintext vault item object into a v2 `encrypted_data` envelope.
 *
 * Delegates to sessionVaultCrypto (v2) — the format the detail-route write path
 * already round-trips. Throws if the vault is locked (no session key).
 *
 * @param {object} data The plaintext item fields to encrypt.
 * @returns {Promise<string>} The serialized v2 envelope.
 */
export async function encryptEnvelope(data) {
  return sessionVaultCrypto.encryptItem(data);
}

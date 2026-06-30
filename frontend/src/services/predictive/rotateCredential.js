/**
 * Proactive Credential Rotation (Zero-Knowledge)
 * ==============================================
 *
 * Phase 3 of predictive expiration: when the dashboard flags a credential for
 * rotation, the *client* rotates it. The server can't and shouldn't mint
 * passwords (it holds no key), so the whole secret-touching flow runs here:
 *
 *   1. decrypt the vault item in the browser   (plaintext never leaves)
 *   2. generate a fresh strong password
 *   3. record the pending event server-side     (reason only — no password)
 *   4. re-encrypt + store via the vault         (only ciphertext is uploaded)
 *   5. re-sync the structural fingerprint       (server re-scores the NEW shape)
 *   6. confirm completion server-side           (no password is sent)
 *
 * The pending event is recorded BEFORE the irreversible local write so the
 * audit obligation always exists first; completion flips it pending → done.
 * The server-side `forceRotation` call is purely an audit/obligation record;
 * it carries no secret. This mirrors the ZK contract used by fingerprintSync.
 */

import { buildFingerprintPayload } from './fingerprintSync';
import {
  submitFingerprints,
  forceRotation,
  completeRotation,
} from '../predictiveExpirationService';
import { SecureVaultCrypto } from '../secureVaultCrypto';

// A rotated password should be strong by default; mirror the generator the
// vault UI uses (crypto.getRandomValues under the hood).
const DEFAULT_LENGTH = 20;

/** Generate a fresh strong password client-side. */
export function generateRotationPassword(length = DEFAULT_LENGTH) {
  const crypto = new SecureVaultCrypto();
  return crypto.generatePassword(length, {
    uppercase: true,
    lowercase: true,
    numbers: true,
    symbols: true,
    excludeAmbiguous: true,
  });
}

/**
 * Rotate a single credential end-to-end, client-side.
 *
 * @param {Object} vault - the VaultContext value (items, decryptItem, updateItem, canEdit)
 * @param {string} credentialId - the credential's item_id (what fingerprints use)
 * @param {Object} [options]
 * @param {string} [options.reason] - audit reason recorded with the event
 * @param {Function} [options.generatePassword] - override generator (tests)
 * @returns {Promise<{credentialId: string, event: Object, fingerprintSynced: boolean, completed: boolean}>}
 */
export async function rotateCredential(vault, credentialId, options = {}) {
  if (!vault || !credentialId) {
    throw new Error('rotateCredential requires a vault and a credentialId.');
  }
  // Re-encrypting needs a live session key; surface a clear, actionable error.
  if (!vault.canEdit) {
    throw new Error('Unlock your vault to rotate this password.');
  }

  const item = (vault.items || []).find(
    (i) => String(i.item_id) === String(credentialId)
  );
  if (!item) {
    throw new Error('This credential is not in your unlocked vault.');
  }

  // Decrypt to read the current fields. Plaintext stays in this browser.
  const decrypted = await vault.decryptItem(item.item_id);
  if (!decrypted || decrypted._decryptionFailed || !decrypted.data) {
    throw new Error('Could not decrypt this credential to rotate it.');
  }

  // 1. Fresh password (client-side only). The generator is injectable, so it
  //    may be async or return a non-string; resolve it and require a non-empty
  //    string before it ever reaches the encrypted payload / fingerprint sync.
  const generate = options.generatePassword || generateRotationPassword;
  const newPassword = await generate();
  if (typeof newPassword !== 'string' || newPassword.length === 0) {
    throw new Error('Failed to generate a new password.');
  }

  // Persist the rotation timestamp in the (encrypted) item data so age-based
  // scoring stays correct on every future full vault sync, not just the
  // immediate re-sync below. Only a coarse age_days is ever derived from it;
  // the timestamp itself stays client-side inside the encrypted payload.
  const rotatedItem = {
    ...decrypted,
    data: {
      ...decrypted.data,
      password: newPassword,
      passwordChangedAt: new Date().toISOString(),
    },
  };

  // 2. Record the rotation event server-side FIRST (reason only, no secret), so
  //    the pending obligation exists before the irreversible local write. If
  //    this fails we abort before touching the vault; if the local write later
  //    fails, the event legitimately stays pending. (Two-phase audit:
  //    pending here, completed in step 5.)
  const event = await forceRotation(credentialId, {
    reason: options.reason || 'Proactive rotation from predictive dashboard',
  });
  // Guard the rotation-event contract before the irreversible local write: a
  // malformed response with no event_id would otherwise persist the rotation
  // yet leave an uncompletable pending event (step 5 can't target it).
  if (!event?.event_id) {
    throw new Error('forceRotation must return an event_id.');
  }

  // 3. Re-encrypt + persist. updateItem encrypts item.data via the session key
  //    and PATCHes only the ciphertext — the plaintext is never sent.
  await vault.updateItem(rotatedItem);

  // 4. Re-sync the ZK fingerprint for the new shape. buildFingerprintPayload
  //    derives age from the persisted passwordChangedAt above, so the rotated
  //    password is scored as freshly created (age 0).
  let fingerprintSynced = false;
  try {
    const fp = await buildFingerprintPayload(rotatedItem);
    if (fp) {
      await submitFingerprints([fp]);
      fingerprintSynced = true;
    }
  } catch (err) {
    // A failed re-score must not undo a successful rotation — the next full
    // vault sync will pick up the new shape. Log and continue.
    console.warn('Post-rotation fingerprint sync failed; will re-sync later.', err);
  }

  // 5. Confirm completion: the rotation finished locally, so flip the event
  //    pending → completed. Best-effort — a failure here leaves the event
  //    pending (the rotation itself stands), so never fail the whole flow on it.
  let completed = false;
  try {
    await completeRotation(credentialId, event?.event_id);
    completed = true;
  } catch (err) {
    console.warn('Could not mark rotation complete; event stays pending.', err);
  }

  return { credentialId: String(credentialId), event, fingerprintSynced, completed };
}

export default { rotateCredential, generateRotationPassword };

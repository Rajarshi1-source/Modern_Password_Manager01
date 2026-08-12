/**
 * vaultV3UnlockClassifier.js
 *
 * Classifies what a `sessionVaultCryptoV3.unlockWithMasterPassword` rejection
 * means, so the login flow can react appropriately:
 *
 *   - not enrolled yet (first login on this account) -> run the legacy-to-v3
 *     migration, unchanged from before this module existed.
 *   - a genuine desync between the account password and the vault's wrapped
 *     key -- `unwrapDEK`'s AES-GCM failure, which only fires on a wrong KEK
 *     or a corrupted blob -- worth surfacing persistently, since it will not
 *     self-heal on retry.
 *   - anything else (a network error, a 5xx, a malformed response) -- worth
 *     logging, not worth alarming the user about, since `WRAPPED_DEK_URL` is
 *     re-fetched fresh next login and this is not a lasting problem.
 *
 * Pulled out of `App.jsx`'s `handleLogin` into its own pure, side-effect-free
 * function specifically so it is unit-testable without rendering that
 * component -- App.jsx pulls in PQC/FHE/blockchain/biometric providers well
 * outside this classification's own concern, and a full render harness for it
 * would be disproportionate to a three-way string comparison.
 */
import { DEK_UNWRAP_FAILURE_MESSAGE } from './sessionVaultCryptoV3';

export const V3_UNLOCK_NOT_ENROLLED = 'not_enrolled';
export const V3_UNLOCK_DESYNC = 'desync';
export const V3_UNLOCK_TRANSIENT = 'transient';

/**
 * @param {unknown} err - Whatever `unlockWithMasterPassword` rejected with.
 * @returns {'not_enrolled'|'desync'|'transient'}
 */
export function classifyV3UnlockError(err) {
  if (err?.message === 'NOT_ENROLLED') return V3_UNLOCK_NOT_ENROLLED;
  if (err?.message === DEK_UNWRAP_FAILURE_MESSAGE) return V3_UNLOCK_DESYNC;
  return V3_UNLOCK_TRANSIENT;
}

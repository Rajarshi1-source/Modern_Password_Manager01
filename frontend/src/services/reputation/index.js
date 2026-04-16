/**
 * Reputation-network service entry point.
 *
 * Combines the crypto helpers and the HTTP client so callers (the
 * ReputationDashboard, vault-save hooks that want to submit a proof
 * opportunistically, etc.) only need a single import.
 */

import reputationApi from './reputationApi';
import {
  commitmentForReputation,
  computeBindingHash,
  estimateEntropyBits,
} from './reputationCrypto';

/**
 * One-call helper: take a plaintext password + scope id + authenticated user
 * and submit a reputation proof. Returns the server's response as-is.
 *
 * @param {Object} args
 * @param {string} args.password        Plaintext password (never leaves client).
 * @param {string} args.scopeId         Opaque id (e.g. vault-item UUID).
 * @param {number|string} args.userId   Authenticated user's numeric id.
 * @param {number=} args.claimedBits    Entropy to claim (falls back to estimator).
 */
export const submitReputationProof = async ({
  password,
  scopeId,
  userId,
  claimedBits,
}) => {
  if (!password) throw new Error('submitReputationProof: password required.');
  if (!scopeId) throw new Error('submitReputationProof: scopeId required.');
  if (!userId && userId !== 0) {
    throw new Error('submitReputationProof: userId required for binding_hash.');
  }

  const commitment = commitmentForReputation(password, scopeId);
  const bits = claimedBits ?? estimateEntropyBits(password);
  const bindingHash = computeBindingHash({
    commitment,
    claimedBits: bits,
    userId,
  });

  return reputationApi.submitProof({
    scopeId,
    commitment,
    claimedEntropyBits: bits,
    bindingHash,
  });
};

export {
  reputationApi,
  commitmentForReputation,
  computeBindingHash,
  estimateEntropyBits,
};

export default {
  ...reputationApi,
  submitReputationProof,
  commitmentForReputation,
  computeBindingHash,
  estimateEntropyBits,
};

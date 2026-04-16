/**
 * Thin axios client for the `/api/reputation/` endpoints.
 *
 * No cryptography here — `reputationCrypto.js` builds the commitment and
 * binding_hash, this module just shuttles base64 blobs to the server.
 */

import api from '../api';

import { toBase64 } from '../zkProof';

const BASE = '/api/reputation';

export const submitProof = async ({
  scopeId,
  commitment,
  claimedEntropyBits,
  bindingHash,
  scheme = 'commitment-claim-v1',
}) => {
  const response = await api.post(`${BASE}/submit-proof/`, {
    scope_id: scopeId,
    commitment: toBase64(commitment),
    claimed_entropy_bits: claimedEntropyBits,
    binding_hash: toBase64(bindingHash),
    scheme,
  });
  return response.data;
};

export const getMyAccount = async () => {
  const response = await api.get(`${BASE}/me/`);
  return response.data;
};

export const getMyEvents = async (limit = 50) => {
  const response = await api.get(`${BASE}/events/`, { params: { limit } });
  return response.data;
};

export const getMyProofs = async () => {
  const response = await api.get(`${BASE}/proofs/`);
  return response.data;
};

export const getLeaderboard = async (limit = 20) => {
  const response = await api.get(`${BASE}/leaderboard/`, { params: { limit } });
  return response.data;
};

export const getRecentBatches = async () => {
  const response = await api.get(`${BASE}/batches/`);
  return response.data;
};

export const getConfig = async () => {
  const response = await api.get(`${BASE}/config/`);
  return response.data;
};

export default {
  submitProof,
  getMyAccount,
  getMyEvents,
  getMyProofs,
  getLeaderboard,
  getRecentBatches,
  getConfig,
};

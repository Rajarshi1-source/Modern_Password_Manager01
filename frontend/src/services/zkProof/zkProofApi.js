/**
 * Thin axios client for the `/api/zk/` endpoints exposed by the backend
 * `zk_proofs` Django app. All commitments and proof payloads are carried as
 * standard base64 strings matching the backend `Base64BytesField` format.
 */

import api from '../api';

const BASE = '/api/zk';

/**
 * POST a commitment. Idempotent per (scope_type, scope_id, scheme) — the server
 * `update_or_create`s on this key so re-posting replaces the stored commitment.
 */
export const registerCommitment = async ({
  scope_type,
  scope_id,
  commitment_b64,
  scheme = 'commitment-schnorr-v1',
}) => {
  const response = await api.post(`${BASE}/commit/`, {
    scope_type,
    scope_id,
    commitment: commitment_b64,
    scheme,
  });
  return response.data;
};

export const listCommitments = async ({ scope_type, scope_id } = {}) => {
  const params = new URLSearchParams();
  if (scope_type) params.append('scope_type', scope_type);
  if (scope_id) params.append('scope_id', scope_id);
  const qs = params.toString() ? `?${params.toString()}` : '';
  const response = await api.get(`${BASE}/commit/${qs}`);
  return response.data;
};

export const getCommitment = async (commitmentId) => {
  const response = await api.get(`${BASE}/commit/${commitmentId}/`);
  return response.data;
};

export const deleteCommitment = async (commitmentId) => {
  const response = await api.delete(`${BASE}/commit/${commitmentId}/`);
  return response.data;
};

/**
 * Submit an equality proof. Returns `{ verified, scheme, attempt_id, verified_at }`.
 * The server records a `ZKVerificationAttempt` for every call regardless of outcome.
 */
export const verifyEqualityApi = async ({
  commitment_a_id,
  commitment_b_id,
  proof_T_b64,
  proof_s_b64,
}) => {
  const response = await api.post(`${BASE}/verify-equality/`, {
    commitment_a_id,
    commitment_b_id,
    proof_T: proof_T_b64,
    proof_s: proof_s_b64,
  });
  return response.data;
};

export const listAttempts = async () => {
  const response = await api.get(`${BASE}/attempts/`);
  return response.data;
};

export const listSchemes = async () => {
  const response = await api.get(`${BASE}/schemes/`);
  return response.data;
};

export default {
  registerCommitment,
  listCommitments,
  getCommitment,
  deleteCommitment,
  verifyEqualityApi,
  listAttempts,
  listSchemes,
};

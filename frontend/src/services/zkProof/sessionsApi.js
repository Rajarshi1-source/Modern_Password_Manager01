/**
 * Thin axios client for the `/api/zk/sessions/` endpoints — multi-party
 * Zero-Knowledge verification ceremonies.
 *
 * Model recap:
 *   - Session owner publishes a reference ZKCommitment (one of their own).
 *   - Owner creates invites; each invite has a one-time ``invite_token``.
 *   - Invitee resolves the token (bound to their user), reconstructs a local
 *     commitment, produces a Schnorr equality proof, and posts it.
 *   - Server verifies against the reference and marks the participant slot
 *     verified / failed. Every attempt is logged via ZKVerificationAttempt.
 */

import api from '../api';

const BASE = '/api/zk/sessions';

export const listSessions = async () => {
  const response = await api.get(`${BASE}/`);
  return response.data;
};

export const getSession = async (sessionId) => {
  const response = await api.get(`${BASE}/${sessionId}/`);
  return response.data;
};

export const createSession = async ({
  reference_commitment_id,
  title = '',
  description = '',
  expires_in_hours = 24 * 7,
}) => {
  const response = await api.post(`${BASE}/`, {
    reference_commitment_id,
    title,
    description,
    expires_in_hours,
  });
  return response.data;
};

export const closeSession = async (sessionId) => {
  const response = await api.delete(`${BASE}/${sessionId}/`);
  return response.data;
};

export const inviteParticipant = async (sessionId, { invited_email = '', invited_label = '' } = {}) => {
  const response = await api.post(`${BASE}/${sessionId}/invite/`, {
    invited_email,
    invited_label,
  });
  return response.data;
};

export const revokeParticipant = async (sessionId, participantId) => {
  const response = await api.post(
    `${BASE}/${sessionId}/participants/${participantId}/revoke/`,
  );
  return response.data;
};

export const resolveInvite = async (token) => {
  const response = await api.get(`${BASE}/join/${token}/`);
  return response.data;
};

export const submitSessionProof = async ({
  invite_token,
  participant_commitment_id,
  proof_T_b64,
  proof_s_b64,
}) => {
  const response = await api.post(`${BASE}/submit-proof/`, {
    invite_token,
    participant_commitment_id,
    proof_T: proof_T_b64,
    proof_s: proof_s_b64,
  });
  return response.data;
};

export const listMyInvites = async () => {
  const response = await api.get(`${BASE}/my-invites/`);
  return response.data;
};

export default {
  listSessions,
  getSession,
  createSession,
  closeSession,
  inviteParticipant,
  revokeParticipant,
  resolveInvite,
  submitSessionProof,
  listMyInvites,
};

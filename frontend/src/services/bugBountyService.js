import { api as apiClient } from './api';

/**
 * Bug Bounty — Vault Self-Pentest service (Phase 1).
 *
 * Client for the continuous self-pentest harness: read the latest run + open
 * findings, trigger an on-demand run, and update a finding's triage status.
 */

const BASE_URL = '/api/bug-bounty';

/** Latest self-test run plus the user's open findings. */
export const getSelfTest = async () => {
  const response = await apiClient.get(`${BASE_URL}/self-test/`);
  return response.data;
};

/** Trigger an on-demand self-test; resolves with the completed run + findings. */
export const runSelfTest = async () => {
  const response = await apiClient.post(`${BASE_URL}/self-test/run/`);
  return response.data;
};

/**
 * Update a finding's triage status.
 * @param {string} id finding id
 * @param {'open'|'acknowledged'|'resolved'|'false_positive'} status
 */
export const updateFindingStatus = async (id, status) => {
  const response = await apiClient.patch(`${BASE_URL}/findings/${id}/`, { status });
  return response.data;
};

export default { getSelfTest, runSelfTest, updateFindingStatus };

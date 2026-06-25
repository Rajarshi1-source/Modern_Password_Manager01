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

/* ------------------------------------------------------------------ *
 * Phase 2 — bounty program / submissions / rewards
 * ------------------------------------------------------------------ */

/** Programs owned by the current user (management view). */
export const getPrograms = async () => {
  const response = await apiClient.get(`${BASE_URL}/programs/`);
  return response.data;
};

/** Active programs any researcher can submit to (across owners). */
export const getAvailablePrograms = async () => {
  const response = await apiClient.get(`${BASE_URL}/programs/available/`);
  return response.data;
};

/** Create a program. */
export const createProgram = async (payload) => {
  const response = await apiClient.post(`${BASE_URL}/programs/`, payload);
  return response.data;
};

/** Update a program (e.g. change status / scope / tiers). */
export const updateProgram = async (id, payload) => {
  const response = await apiClient.patch(`${BASE_URL}/programs/${id}/`, payload);
  return response.data;
};

/** Submissions visible to the user (as researcher or program owner). */
export const getSubmissions = async () => {
  const response = await apiClient.get(`${BASE_URL}/submissions/`);
  return response.data;
};

/** File a report against an active program. */
export const createSubmission = async (payload) => {
  const response = await apiClient.post(`${BASE_URL}/submissions/`, payload);
  return response.data;
};

/**
 * Owner-only: advance a submission through the triage state machine.
 * @param {string} id submission id
 * @param {{to_status: string, severity_assigned?: string, note?: string}} body
 */
export const transitionSubmission = async (id, body) => {
  const response = await apiClient.post(`${BASE_URL}/submissions/${id}/transition/`, body);
  return response.data;
};

/**
 * Owner-only: record a reward obligation on a resolved submission.
 * @param {string} id submission id
 * @param {{amount: string|number, currency?: string, adapter?: string, note?: string}} body
 */
export const rewardSubmission = async (id, body) => {
  const response = await apiClient.post(`${BASE_URL}/submissions/${id}/reward/`, body);
  return response.data;
};

/** Owner-only: settle an owed reward through its payout adapter (no money moves in-product). */
export const payReward = async (id) => {
  const response = await apiClient.post(`${BASE_URL}/rewards/${id}/pay/`);
  return response.data;
};

/** Owner-only: void an obligation that will not be paid. */
export const voidReward = async (id) => {
  const response = await apiClient.post(`${BASE_URL}/rewards/${id}/void/`);
  return response.data;
};

export default {
  getSelfTest,
  runSelfTest,
  updateFindingStatus,
  getPrograms,
  getAvailablePrograms,
  createProgram,
  updateProgram,
  getSubmissions,
  createSubmission,
  transitionSubmission,
  rewardSubmission,
  payReward,
  voidReward,
};

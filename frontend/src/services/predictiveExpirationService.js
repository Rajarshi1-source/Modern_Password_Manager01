/**
 * Predictive Expiration Security Service
 * ========================================
 * 
 * Frontend service for predictive password expiration API.
 */

import api from './api';

const PREDICTIVE_EXPIRATION_BASE = '/security/predictive-expiration';

/**
 * Get the predictive expiration dashboard overview
 * @returns {Promise} Dashboard data with risk summary, threats, and at-risk credentials
 */
export const getDashboard = async () => {
  const response = await api.get(`${PREDICTIVE_EXPIRATION_BASE}/dashboard/`);
  return response.data;
};

/**
 * Get list of credentials with their risk assessments
 * @param {Object} params - Query parameters
 * @param {string} [params.risk_level] - Filter by risk level (critical, high, medium, low, minimal)
 * @param {string} [params.domain] - Filter by domain
 * @param {boolean} [params.unacknowledged] - Only show unacknowledged risks
 * @returns {Promise} Paginated list of credential risks
 */
export const getCredentialRisks = async (params = {}) => {
  const response = await api.get(`${PREDICTIVE_EXPIRATION_BASE}/credentials/`, { params });
  return response.data;
};

/**
 * Get detailed risk analysis for a specific credential
 * @param {string} credentialId - UUID of the credential
 * @returns {Promise} Detailed risk assessment
 */
export const getCredentialRiskDetail = async (credentialId) => {
  const response = await api.get(`${PREDICTIVE_EXPIRATION_BASE}/credential/${credentialId}/risk/`);
  return response.data;
};

/**
 * Force password rotation for a credential
 * @param {string} credentialId - UUID of the credential
 * @param {Object} data - Rotation request data
 * @param {string} [data.reason] - Reason for rotation
 * @returns {Promise} Rotation event details
 */
export const forceRotation = async (credentialId, data = {}) => {
  const response = await api.post(`${PREDICTIVE_EXPIRATION_BASE}/credential/${credentialId}/rotate/`, data);
  return response.data;
};

/**
 * Acknowledge a risk warning for a credential
 * @param {string} credentialId - UUID of the credential
 * @returns {Promise} Acknowledgement confirmation
 */
export const acknowledgeRisk = async (credentialId) => {
  const response = await api.post(`${PREDICTIVE_EXPIRATION_BASE}/credential/${credentialId}/acknowledge/`);
  return response.data;
};

/**
 * Get list of active threats
 * @param {Object} params - Query parameters
 * @param {string} [params.threat_level] - Filter by threat level
 * @param {string} [params.actor_type] - Filter by actor type (apt, ransomware, etc.)
 * @param {string} [params.industry] - Filter by targeted industry
 * @returns {Promise} List of active threat actors
 */
export const getActiveThreats = async (params = {}) => {
  const response = await api.get(`${PREDICTIVE_EXPIRATION_BASE}/threats/`, { params });
  return response.data;
};

/**
 * Get threat landscape summary
 * @returns {Promise} High-level threat statistics
 */
export const getThreatSummary = async () => {
  const response = await api.get(`${PREDICTIVE_EXPIRATION_BASE}/threat-summary/`);
  return response.data;
};

/**
 * Get user's predictive expiration settings
 * @returns {Promise} Current settings
 */
export const getSettings = async () => {
  const response = await api.get(`${PREDICTIVE_EXPIRATION_BASE}/settings/`);
  return response.data;
};

/**
 * Update user's predictive expiration settings
 * @param {Object} settings - Settings to update
 * @returns {Promise} Updated settings
 */
export const updateSettings = async (settings) => {
  const response = await api.patch(`${PREDICTIVE_EXPIRATION_BASE}/settings/`, settings);
  return response.data;
};

/**
 * Get password rotation history
 * @param {Object} params - Query parameters
 * @param {string} [params.type] - Filter by rotation type
 * @param {string} [params.outcome] - Filter by outcome
 * @param {string} [params.start_date] - Start date filter
 * @param {string} [params.end_date] - End date filter
 * @returns {Promise} Paginated rotation history
 */
export const getRotationHistory = async (params = {}) => {
  const response = await api.get(`${PREDICTIVE_EXPIRATION_BASE}/history/`, { params });
  return response.data;
};

/**
 * Analyze a credential for risk
 * @param {Object} data - Credential data
 * @param {string} data.credential_id - UUID of the credential
 * @param {string} data.password - Password to analyze
 * @param {string} data.domain - Domain/service
 * @param {string} [data.created_at] - Credential creation date
 * @returns {Promise} Risk analysis results
 */
export const analyzeCredential = async (data) => {
  const response = await api.post(`${PREDICTIVE_EXPIRATION_BASE}/analyze/`, data);
  return response.data;
};

/**
 * Get user's password pattern profile
 * @returns {Promise} Pattern analysis profile
 */
export const getPatternProfile = async () => {
  const response = await api.get(`${PREDICTIVE_EXPIRATION_BASE}/pattern-profile/`);
  return response.data;
};

/**
 * Get industry threat levels
 * @returns {Promise} List of industries with threat levels
 */
export const getIndustryThreats = async () => {
  const response = await api.get(`${PREDICTIVE_EXPIRATION_BASE}/industries/`);
  return response.data;
};

// Export all functions as a named export
export const predictiveExpirationService = {
  getDashboard,
  getCredentialRisks,
  getCredentialRiskDetail,
  forceRotation,
  acknowledgeRisk,
  getActiveThreats,
  getThreatSummary,
  getSettings,
  updateSettings,
  getRotationHistory,
  analyzeCredential,
  getPatternProfile,
  getIndustryThreats,
};

export default predictiveExpirationService;

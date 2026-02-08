/**
 * Predictive Expiration Service (Mobile)
 * ========================================
 * 
 * React Native service for predictive password expiration API.
 */

import { apiClient } from './api';

const PREDICTIVE_EXPIRATION_BASE = '/security/predictive-expiration';

/**
 * Get the predictive expiration dashboard overview
 */
export const getDashboard = async () => {
  const response = await apiClient.get(`${PREDICTIVE_EXPIRATION_BASE}/dashboard/`);
  return response.data;
};

/**
 * Get list of credentials with their risk assessments
 */
export const getCredentialRisks = async (params = {}) => {
  const response = await apiClient.get(`${PREDICTIVE_EXPIRATION_BASE}/credentials/`, { params });
  return response.data;
};

/**
 * Get detailed risk analysis for a specific credential
 */
export const getCredentialRiskDetail = async (credentialId) => {
  const response = await apiClient.get(`${PREDICTIVE_EXPIRATION_BASE}/credential/${credentialId}/risk/`);
  return response.data;
};

/**
 * Force password rotation for a credential
 */
export const forceRotation = async (credentialId, reason = 'Manual rotation from mobile') => {
  const response = await apiClient.post(`${PREDICTIVE_EXPIRATION_BASE}/credential/${credentialId}/rotate/`, {
    reason,
  });
  return response.data;
};

/**
 * Acknowledge a risk warning for a credential
 */
export const acknowledgeRisk = async (credentialId) => {
  const response = await apiClient.post(`${PREDICTIVE_EXPIRATION_BASE}/credential/${credentialId}/acknowledge/`);
  return response.data;
};

/**
 * Get list of active threats
 */
export const getActiveThreats = async (params = {}) => {
  const response = await apiClient.get(`${PREDICTIVE_EXPIRATION_BASE}/threats/`, { params });
  return response.data;
};

/**
 * Get threat landscape summary
 */
export const getThreatSummary = async () => {
  const response = await apiClient.get(`${PREDICTIVE_EXPIRATION_BASE}/threat-summary/`);
  return response.data;
};

/**
 * Get user's predictive expiration settings
 */
export const getSettings = async () => {
  const response = await apiClient.get(`${PREDICTIVE_EXPIRATION_BASE}/settings/`);
  return response.data;
};

/**
 * Update user's predictive expiration settings
 */
export const updateSettings = async (settings) => {
  const response = await apiClient.patch(`${PREDICTIVE_EXPIRATION_BASE}/settings/`, settings);
  return response.data;
};

/**
 * Get password rotation history
 */
export const getRotationHistory = async (params = {}) => {
  const response = await apiClient.get(`${PREDICTIVE_EXPIRATION_BASE}/history/`, { params });
  return response.data;
};

/**
 * Analyze a credential for risk
 */
export const analyzeCredential = async (data) => {
  const response = await apiClient.post(`${PREDICTIVE_EXPIRATION_BASE}/analyze/`, data);
  return response.data;
};

/**
 * Get user's password pattern profile
 */
export const getPatternProfile = async () => {
  const response = await apiClient.get(`${PREDICTIVE_EXPIRATION_BASE}/pattern-profile/`);
  return response.data;
};

/**
 * Get industry threat levels
 */
export const getIndustryThreats = async () => {
  const response = await apiClient.get(`${PREDICTIVE_EXPIRATION_BASE}/industries/`);
  return response.data;
};

// Export all functions as named export
export const PredictiveExpirationService = {
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

export default PredictiveExpirationService;

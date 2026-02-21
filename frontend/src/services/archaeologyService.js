/**
 * Password Archaeology & Time Travel API Service
 * ================================================
 * Frontend service for interacting with the Password Archaeology API.
 */

import axios from 'axios';

const API_BASE = '/api/archaeology';

/**
 * Get auth headers from stored JWT token.
 */
function getAuthHeaders() {
  const token = localStorage.getItem('access_token');
  return token ? { Authorization: `Bearer ${token}` } : {};
}

/**
 * Create an axios instance with default config.
 */
const api = axios.create({
  baseURL: API_BASE,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Add auth header to every request
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// ===================================================================
// Dashboard
// ===================================================================

/**
 * Get aggregated dashboard summary.
 */
export async function getDashboard() {
  const response = await api.get('/dashboard/');
  return response.data;
}

// ===================================================================
// Timeline
// ===================================================================

/**
 * Get merged timeline of password changes and security events.
 * @param {Object} params - { date_from, date_to, vault_item_id, limit }
 */
export async function getTimeline(params = {}) {
  const response = await api.get('/timeline/', { params });
  return response.data;
}

// ===================================================================
// Strength Evolution
// ===================================================================

/**
 * Get strength evolution data for a specific credential.
 * @param {string} vaultItemId - UUID of the vault item
 * @param {Object} params - { date_from, date_to }
 */
export async function getStrengthEvolution(vaultItemId, params = {}) {
  const response = await api.get(`/strength-evolution/${vaultItemId}/`, { params });
  return response.data;
}

/**
 * Get overall strength evolution across all credentials.
 * @param {Object} params - { date_from, date_to, credential_domain }
 */
export async function getOverallStrength(params = {}) {
  const response = await api.get('/strength-evolution/overall/', { params });
  return response.data;
}

// ===================================================================
// Security Events
// ===================================================================

/**
 * List security events with optional filters.
 * @param {Object} params - { event_type, severity, resolved, limit }
 */
export async function getSecurityEvents(params = {}) {
  const response = await api.get('/security-events/', { params });
  return response.data;
}

// ===================================================================
// What-If Scenarios
// ===================================================================

/**
 * Run a "what if" scenario simulation.
 * @param {Object} data - { scenario_type, credential_domain, vault_item_id, params }
 */
export async function runWhatIfScenario(data) {
  const response = await api.post('/what-if/', data);
  return response.data;
}

/**
 * Get past what-if simulation history.
 */
export async function getWhatIfHistory() {
  const response = await api.get('/what-if/history/');
  return response.data;
}

// ===================================================================
// Time Machine
// ===================================================================

/**
 * Get account state at a specific point in time.
 * @param {string} timestamp - ISO 8601 timestamp
 */
export async function getTimeMachineSnapshot(timestamp) {
  const response = await api.get(`/time-machine/${timestamp}/`);
  return response.data;
}

// ===================================================================
// Achievements
// ===================================================================

/**
 * Get user's achievement records.
 */
export async function getAchievements() {
  const response = await api.get('/achievements/');
  return response.data;
}

/**
 * Mark an achievement as acknowledged.
 * @param {string} achievementId - UUID of the achievement
 */
export async function acknowledgeAchievement(achievementId) {
  const response = await api.patch(`/achievements/${achievementId}/acknowledge/`);
  return response.data;
}

// ===================================================================
// Security Score
// ===================================================================

/**
 * Get security score history for gamification charts.
 * @param {Object} params - { date_from, date_to }
 */
export async function getSecurityScore(params = {}) {
  const response = await api.get('/security-score/', { params });
  return response.data;
}

export default {
  getDashboard,
  getTimeline,
  getStrengthEvolution,
  getOverallStrength,
  getSecurityEvents,
  runWhatIfScenario,
  getWhatIfHistory,
  getTimeMachineSnapshot,
  getAchievements,
  acknowledgeAchievement,
  getSecurityScore,
};

/**
 * Honeypot Email Service
 * 
 * Service layer for honeypot email breach detection API interactions.
 * Handles CRUD operations, breach management, and activity monitoring.
 * 
 * @author Password Manager Team
 * @created 2026-02-01
 */

import api from './api';

const HONEYPOT_BASE = '/api/security/honeypot';

/**
 * Get honeypot configuration for current user
 */
export const getConfig = async () => {
  const response = await api.get(`${HONEYPOT_BASE}/config/`);
  return response.data;
};

/**
 * Update honeypot configuration
 */
export const updateConfig = async (config) => {
  const response = await api.put(`${HONEYPOT_BASE}/config/`, config);
  return response.data;
};

/**
 * Get all honeypots for current user
 */
export const getHoneypots = async (options = {}) => {
  const params = new URLSearchParams();
  if (options.status) params.append('status', options.status);
  if (options.includeInactive) params.append('include_inactive', 'true');
  
  const response = await api.get(`${HONEYPOT_BASE}/list/?${params}`);
  return response.data;
};

/**
 * Create a new honeypot
 */
export const createHoneypot = async (data) => {
  const response = await api.post(`${HONEYPOT_BASE}/list/`, data);
  return response.data;
};

/**
 * Get honeypot details
 */
export const getHoneypot = async (honeypotId) => {
  const response = await api.get(`${HONEYPOT_BASE}/${honeypotId}/`);
  return response.data;
};

/**
 * Update honeypot (notes, tags)
 */
export const updateHoneypot = async (honeypotId, data) => {
  const response = await api.patch(`${HONEYPOT_BASE}/${honeypotId}/`, data);
  return response.data;
};

/**
 * Delete a honeypot
 */
export const deleteHoneypot = async (honeypotId) => {
  const response = await api.delete(`${HONEYPOT_BASE}/${honeypotId}/`);
  return response.data;
};

/**
 * Test/check honeypot for activity
 */
export const testHoneypot = async (honeypotId) => {
  const response = await api.post(`${HONEYPOT_BASE}/${honeypotId}/test/`);
  return response.data;
};

/**
 * Bulk create honeypots
 */
export const bulkCreateHoneypots = async (services) => {
  const response = await api.post(`${HONEYPOT_BASE}/bulk-create/`, { services });
  return response.data;
};

/**
 * Check all honeypots for activity
 */
export const checkAllHoneypots = async () => {
  const response = await api.post(`${HONEYPOT_BASE}/check-all/`);
  return response.data;
};

// ============================================================================
// Breach Management
// ============================================================================

/**
 * Get all breach events
 */
export const getBreaches = async (options = {}) => {
  const params = new URLSearchParams();
  if (options.status) params.append('status', options.status);
  if (options.includeResolved) params.append('include_resolved', 'true');
  
  const response = await api.get(`${HONEYPOT_BASE}/breaches/?${params}`);
  return response.data;
};

/**
 * Get breach details with timeline
 */
export const getBreachTimeline = async (breachId) => {
  const response = await api.get(`${HONEYPOT_BASE}/breaches/${breachId}/`);
  return response.data;
};

/**
 * Update breach (acknowledge, add notes, change status)
 */
export const updateBreach = async (breachId, data) => {
  const response = await api.patch(`${HONEYPOT_BASE}/breaches/${breachId}/`, data);
  return response.data;
};

/**
 * Initiate credential rotation for a breach
 */
export const initiateRotation = async (breachId) => {
  const response = await api.post(`${HONEYPOT_BASE}/breaches/${breachId}/rotate/`);
  return response.data;
};

// ============================================================================
// Activity Monitoring
// ============================================================================

/**
 * Get activity logs
 */
export const getActivities = async (options = {}) => {
  const params = new URLSearchParams();
  if (options.honeypotId) params.append('honeypot_id', options.honeypotId);
  if (options.limit) params.append('limit', options.limit);
  
  const response = await api.get(`${HONEYPOT_BASE}/activities/?${params}`);
  return response.data;
};

// ============================================================================
// Statistics & Dashboard
// ============================================================================

/**
 * Get dashboard statistics
 */
export const getDashboardStats = async () => {
  const [config, honeypots, breaches] = await Promise.all([
    getConfig(),
    getHoneypots(),
    getBreaches()
  ]);
  
  const activeHoneypots = honeypots.honeypots?.filter(h => h.status === 'active') || [];
  const triggeredHoneypots = honeypots.honeypots?.filter(h => h.status === 'triggered') || [];
  const breachedHoneypots = honeypots.honeypots?.filter(h => h.breach_detected) || [];
  
  const unresolvedBreaches = breaches.breaches?.filter(
    b => !['resolved', 'false_positive'].includes(b.status)
  ) || [];
  
  return {
    config,
    totalHoneypots: honeypots.count || 0,
    activeHoneypots: activeHoneypots.length,
    triggeredHoneypots: triggeredHoneypots.length,
    breachedHoneypots: breachedHoneypots.length,
    totalBreaches: breaches.count || 0,
    unresolvedBreaches: unresolvedBreaches.length,
    criticalBreaches: breaches.breaches?.filter(b => b.severity === 'critical').length || 0,
    highBreaches: breaches.breaches?.filter(b => b.severity === 'high').length || 0,
    honeypots: honeypots.honeypots || [],
    breaches: breaches.breaches || []
  };
};

export default {
  getConfig,
  updateConfig,
  getHoneypots,
  createHoneypot,
  getHoneypot,
  updateHoneypot,
  deleteHoneypot,
  testHoneypot,
  bulkCreateHoneypots,
  checkAllHoneypots,
  getBreaches,
  getBreachTimeline,
  updateBreach,
  initiateRotation,
  getActivities,
  getDashboardStats
};

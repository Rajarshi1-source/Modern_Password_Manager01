/**
 * Honeypot Service for Mobile
 * 
 * Service layer for honeypot email breach detection API interactions.
 * Mobile implementation with React Native compatibility.
 * 
 * @author Password Manager Team
 * @created 2026-02-01
 */

import api from './api';

const HONEYPOT_BASE = '/api/security/honeypot';

class HoneypotService {
  /**
   * Get honeypot configuration for current user
   */
  async getConfig() {
    const response = await api.get(`${HONEYPOT_BASE}/config/`);
    return response.data;
  }

  /**
   * Update honeypot configuration
   */
  async updateConfig(config) {
    const response = await api.put(`${HONEYPOT_BASE}/config/`, config);
    return response.data;
  }

  /**
   * Get all honeypots for current user
   */
  async getHoneypots(options = {}) {
    const params = new URLSearchParams();
    if (options.status) params.append('status', options.status);
    if (options.includeInactive) params.append('include_inactive', 'true');
    
    const response = await api.get(`${HONEYPOT_BASE}/list/?${params}`);
    return response.data;
  }

  /**
   * Create a new honeypot
   */
  async createHoneypot(data) {
    const response = await api.post(`${HONEYPOT_BASE}/list/`, data);
    return response.data;
  }

  /**
   * Get honeypot details
   */
  async getHoneypot(honeypotId) {
    const response = await api.get(`${HONEYPOT_BASE}/${honeypotId}/`);
    return response.data;
  }

  /**
   * Update honeypot (notes, tags)
   */
  async updateHoneypot(honeypotId, data) {
    const response = await api.patch(`${HONEYPOT_BASE}/${honeypotId}/`, data);
    return response.data;
  }

  /**
   * Delete a honeypot
   */
  async deleteHoneypot(honeypotId) {
    const response = await api.delete(`${HONEYPOT_BASE}/${honeypotId}/`);
    return response.data;
  }

  /**
   * Test/check honeypot for activity
   */
  async testHoneypot(honeypotId) {
    const response = await api.post(`${HONEYPOT_BASE}/${honeypotId}/test/`);
    return response.data;
  }

  /**
   * Check all honeypots for activity
   */
  async checkAllHoneypots() {
    const response = await api.post(`${HONEYPOT_BASE}/check-all/`);
    return response.data;
  }

  /**
   * Get all breach events
   */
  async getBreaches(options = {}) {
    const params = new URLSearchParams();
    if (options.status) params.append('status', options.status);
    if (options.includeResolved) params.append('include_resolved', 'true');
    
    const response = await api.get(`${HONEYPOT_BASE}/breaches/?${params}`);
    return response.data;
  }

  /**
   * Get breach details with timeline
   */
  async getBreachTimeline(breachId) {
    const response = await api.get(`${HONEYPOT_BASE}/breaches/${breachId}/`);
    return response.data;
  }

  /**
   * Update breach (acknowledge, add notes, change status)
   */
  async updateBreach(breachId, data) {
    const response = await api.patch(`${HONEYPOT_BASE}/breaches/${breachId}/`, data);
    return response.data;
  }

  /**
   * Initiate credential rotation for a breach
   */
  async initiateRotation(breachId) {
    const response = await api.post(`${HONEYPOT_BASE}/breaches/${breachId}/rotate/`);
    return response.data;
  }

  /**
   * Get activity logs
   */
  async getActivities(options = {}) {
    const params = new URLSearchParams();
    if (options.honeypotId) params.append('honeypot_id', options.honeypotId);
    if (options.limit) params.append('limit', options.limit);
    
    const response = await api.get(`${HONEYPOT_BASE}/activities/?${params}`);
    return response.data;
  }

  /**
   * Get dashboard statistics
   */
  async getDashboardStats() {
    const [config, honeypots, breaches] = await Promise.all([
      this.getConfig(),
      this.getHoneypots(),
      this.getBreaches()
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
  }
}

export default new HoneypotService();

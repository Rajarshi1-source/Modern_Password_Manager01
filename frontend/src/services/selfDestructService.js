/**
 * Self-destruct policy client.
 *
 * Thin wrapper around /api/self-destruct/. Create one policy per vault
 * entry. The server enforces the rules on every retrieve; the UI side
 * only has to present lifetime counters and let the user revoke.
 */

import api from './api';

const BASE = '/api/self-destruct';

const selfDestructService = {
  listPolicies: () => api.get(`${BASE}/policies/`),
  createPolicy: (payload) => api.post(`${BASE}/policies/`, payload),
  getPolicy: (id) => api.get(`${BASE}/policies/${id}/`),
  updatePolicy: (id, payload) => api.patch(`${BASE}/policies/${id}/`, payload),
  revokePolicy: (id) => api.post(`${BASE}/policies/${id}/revoke/`),
  deletePolicy: (id) => api.delete(`${BASE}/policies/${id}/`),
  listEvents: () => api.get(`${BASE}/events/`),
};

export default selfDestructService;

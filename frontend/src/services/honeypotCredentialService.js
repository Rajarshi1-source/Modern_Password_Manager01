/**
 * Honeypot Credential Service
 *
 * Client for the /api/honeypot/ endpoints introduced by the
 * "Honeypot Passwords" feature. This is DISTINCT from the existing
 * honeypotService.js which targets email breach honeypots under
 * /api/security/honeypot/. Importing symbols from both is safe.
 */

import api from './api';

const BASE = '/api/honeypot';

const honeypotCredentialService = {
  list: () => api.get(`${BASE}/credentials/`),
  retrieve: (id) => api.get(`${BASE}/credentials/${id}/`),
  create: (payload) => api.post(`${BASE}/credentials/`, payload),
  update: (id, payload) => api.patch(`${BASE}/credentials/${id}/`, payload),
  remove: (id) => api.delete(`${BASE}/credentials/${id}/`),
  rotate: (id) => api.post(`${BASE}/credentials/${id}/rotate/`),
  reveal: (id) => api.get(`${BASE}/credentials/${id}/reveal/`),

  listEvents: () => api.get(`${BASE}/events/`),
  retrieveEvent: (id) => api.get(`${BASE}/events/${id}/`),

  listTemplates: () => api.get(`${BASE}/templates/`),
};

export default honeypotCredentialService;

/**
 * Heartbeat Authentication Service
 *
 * Thin client for /api/heartbeat/ endpoints. All HRV feature
 * extraction happens client-side in services/heartbeat/hrvFeatures.js
 * — this module only serialises the feature dict and posts it.
 *
 * NOTE: the verify endpoint ALWAYS returns 200 even on duress so an
 * on-looker cannot tell (by watching the network tab) whether the
 * user just triggered the decoy vault. The caller inspects
 * ``response.data.duress`` / ``response.data.vault`` instead.
 */

import api from './api';

const BASE = '/api/heartbeat';

const heartbeatService = {
  enroll: (features) => api.post(`${BASE}/enroll/`, { features }),
  verify: (features) => api.post(`${BASE}/verify/`, { features }),
  getProfile: () => api.get(`${BASE}/profile/`),
  resetProfile: () => api.post(`${BASE}/profile/reset/`),
};

export default heartbeatService;

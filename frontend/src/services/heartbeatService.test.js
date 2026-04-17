/**
 * heartbeatService.js unit tests.
 *
 * We mock the axios wrapper and assert every API method routes to
 * the right URL with the expected payload shape.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';

vi.mock('./api', () => ({
  default: {
    post: vi.fn(() => Promise.resolve({ data: {} })),
    get: vi.fn(() => Promise.resolve({ data: {} })),
  },
}));

import api from './api';
import heartbeatService from './heartbeatService';

describe('heartbeatService API surface', () => {
  beforeEach(() => {
    api.post.mockClear();
    api.get.mockClear();
  });

  it('enroll posts features to /api/heartbeat/enroll/', async () => {
    const features = { mean_hr: 72.1, rmssd: 40.2, sdnn: 55, pnn50: 0.2, lf_hf_ratio: 1.3 };
    await heartbeatService.enroll(features);
    expect(api.post).toHaveBeenCalledWith('/api/heartbeat/enroll/', { features });
  });

  it('verify posts features to /api/heartbeat/verify/', async () => {
    const features = { mean_hr: 80, rmssd: 25, sdnn: 44, pnn50: 0.1, lf_hf_ratio: 3.1 };
    await heartbeatService.verify(features);
    expect(api.post).toHaveBeenCalledWith('/api/heartbeat/verify/', { features });
  });

  it('getProfile GETs /api/heartbeat/profile/', async () => {
    await heartbeatService.getProfile();
    expect(api.get).toHaveBeenCalledWith('/api/heartbeat/profile/');
  });

  it('resetProfile POSTs /api/heartbeat/profile/reset/', async () => {
    await heartbeatService.resetProfile();
    expect(api.post).toHaveBeenCalledWith('/api/heartbeat/profile/reset/');
  });
});

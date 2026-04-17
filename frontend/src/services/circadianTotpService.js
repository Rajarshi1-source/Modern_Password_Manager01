/**
 * Circadian TOTP Service
 *
 * Thin axios client for the backend endpoints exposed under `/api/circadian/`.
 * Mirrors the shape of `mfaService.js` so it can be dropped into the existing
 * MFA flows.
 */

import axios from 'axios';

const API_BASE =
  import.meta.env.VITE_API_URL ||
  (import.meta.env.PROD ? 'https://api.securevault.com' : '');

const authHeaders = () => ({
  Authorization: `Bearer ${localStorage.getItem('token')}`,
  'Content-Type': 'application/json',
});

class CircadianTotpService {
  async getProfile() {
    const { data } = await axios.get(`${API_BASE}/api/circadian/profile/`, {
      headers: authHeaders(),
    });
    return data;
  }

  async recomputeCalibration() {
    const { data } = await axios.post(
      `${API_BASE}/api/circadian/calibration/recompute/`,
      {},
      { headers: authHeaders() }
    );
    return data;
  }

  async getWearableConnectUrl(provider) {
    const { data } = await axios.post(
      `${API_BASE}/api/circadian/wearables/${provider}/connect/`,
      {},
      { headers: authHeaders() }
    );
    return data;
  }

  async completeWearableCallback(provider, code, state) {
    const { data } = await axios.post(
      `${API_BASE}/api/circadian/wearables/${provider}/callback/`,
      { code, state },
      { headers: authHeaders() }
    );
    return data;
  }

  async pushObservations(provider, observations) {
    const { data } = await axios.post(
      `${API_BASE}/api/circadian/wearables/${provider}/ingest/`,
      { observations },
      { headers: authHeaders() }
    );
    return data;
  }

  async unlinkWearable(provider) {
    const { data } = await axios.post(
      `${API_BASE}/api/circadian/wearables/${provider}/unlink/`,
      {},
      { headers: authHeaders() }
    );
    return data;
  }

  async setupDevice(name = 'Circadian Authenticator') {
    const { data } = await axios.post(
      `${API_BASE}/api/circadian/device/setup/`,
      { name },
      { headers: authHeaders() }
    );
    return data;
  }

  async verifyDevice(deviceId, code) {
    const { data } = await axios.post(
      `${API_BASE}/api/circadian/device/verify/`,
      { device_id: deviceId, code },
      { headers: authHeaders() }
    );
    return data;
  }

  async listDevices() {
    const { data } = await axios.get(`${API_BASE}/api/circadian/device/list/`, {
      headers: authHeaders(),
    });
    return data;
  }

  async deleteDevice(deviceId) {
    const { data } = await axios.delete(
      `${API_BASE}/api/circadian/device/${deviceId}/`,
      { headers: authHeaders() }
    );
    return data;
  }

  async verifyCode(code, deviceId = null) {
    const payload = { code };
    if (deviceId) payload.device_id = deviceId;
    const { data } = await axios.post(
      `${API_BASE}/api/circadian/verify/`,
      payload,
      { headers: authHeaders(), validateStatus: () => true }
    );
    return data;
  }
}

const circadianTotpService = new CircadianTotpService();
export default circadianTotpService;

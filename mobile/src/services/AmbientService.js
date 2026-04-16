/**
 * AmbientService - Mobile
 *
 * Native-surface implementation of the Ambient Biometric Fusion
 * collector. Gathers:
 *   - Wi-Fi signature (salted LSH digest of BSSID set)
 *   - Bluetooth devices (salted LSH digest of MAC set)
 *   - Accelerometer motion class
 *   - Ambient audio fingerprint (salted LSH digest; no raw audio)
 *   - Network connection type (NetInfo)
 *   - Battery drain slope (react-native-device-info)
 *
 * Native capability modules are loaded lazily via dynamic require so
 * that the service degrades gracefully when a module is missing or a
 * permission is denied. Raw identifiers NEVER leave the device - only
 * a 128-bit locality-sensitive hash per group goes to the server.
 */

import { Platform, PermissionsAndroid } from 'react-native';
import AsyncStorage from '@react-native-async-storage/async-storage';
import {
  computeAmbientEmbedding,
  getOrCreateLocalSalt,
  sha256HexSync,
} from './ambient/ambientEmbedding';

const DEVICE_FP_KEY = 'ambient_device_fp_v1';
const ENABLED_KEY = 'ambient_service_enabled';
const API_BASE_KEY = 'ambient_api_base';
const DEFAULT_API_BASE = 'http://localhost:8000';

function safeRequire(name) {
  try {
    return require(name);
  } catch {
    return null;
  }
}

function bucketLight(lux) {
  if (lux == null || Number.isNaN(lux)) return 'unknown';
  if (lux < 5) return 'dark';
  if (lux < 50) return 'dim';
  if (lux < 500) return 'indoor';
  if (lux < 5000) return 'bright';
  return 'sunlight';
}

function classifyMotion(magnitudes) {
  if (!magnitudes || magnitudes.length === 0) return 'unknown';
  const mean = magnitudes.reduce((a, b) => a + b, 0) / magnitudes.length;
  const variance = magnitudes.reduce((a, b) => a + (b - mean) * (b - mean), 0) / magnitudes.length;
  if (variance < 0.05) return 'still';
  if (variance < 0.5) return 'handheld';
  if (variance < 3) return 'walking';
  return 'vehicle';
}

function bucketBatterySlope(slope) {
  if (slope == null || Number.isNaN(slope)) return 'unknown';
  if (slope >= 0) return 'charging';
  if (slope > -0.002) return 'idle';
  if (slope > -0.01) return 'active';
  return 'heavy';
}

class AmbientService {
  constructor() {
    this.localSalt = null;
    this.deviceFp = null;
    this.motionBuffer = [];
    this.motionSubscription = null;
  }

  async _ensureSaltAndFp() {
    if (!this.localSalt) this.localSalt = await getOrCreateLocalSalt();
    if (!this.deviceFp) {
      let stored = await AsyncStorage.getItem(DEVICE_FP_KEY);
      if (!stored || stored.length < 16) {
        stored = sha256HexSync(`${Date.now()}:${Math.random()}:${Platform.OS}`);
        await AsyncStorage.setItem(DEVICE_FP_KEY, stored);
      }
      this.deviceFp = stored;
    }
    return { localSalt: this.localSalt, deviceFp: this.deviceFp };
  }

  async requestPermissions() {
    const perms = {};
    if (Platform.OS === 'android') {
      try {
        perms.location = await PermissionsAndroid.request(
          PermissionsAndroid.PERMISSIONS.ACCESS_FINE_LOCATION,
          { title: 'Ambient Trust', message: 'Needed to read Wi-Fi/BLE neighborhood as a passive auth factor. Only hashed digests leave this device.', buttonPositive: 'Allow', buttonNegative: 'Deny' },
        );
        const btScan = PermissionsAndroid.PERMISSIONS.BLUETOOTH_SCAN;
        if (btScan) {
          perms.bluetooth = await PermissionsAndroid.request(btScan, {
            title: 'Ambient Trust', message: 'Scan nearby Bluetooth to detect trusted contexts.', buttonPositive: 'Allow', buttonNegative: 'Deny',
          });
        }
        const mic = PermissionsAndroid.PERMISSIONS.RECORD_AUDIO;
        if (mic) {
          perms.microphone = await PermissionsAndroid.request(mic, {
            title: 'Ambient Trust', message: 'Sample a short audio fingerprint (never stored, never uploaded as raw audio).', buttonPositive: 'Allow', buttonNegative: 'Deny',
          });
        }
      } catch { /* ignore */ }
    }
    return perms;
  }

  async _getWifiDigests() {
    const wifi = safeRequire('react-native-wifi-reborn');
    if (!wifi) return [];
    try {
      const list = await (wifi.default?.loadWifiList ? wifi.default.loadWifiList() : wifi.loadWifiList?.());
      const arr = typeof list === 'string' ? JSON.parse(list) : (list || []);
      const bssids = (arr || []).map((n) => n.BSSID || n.bssid).filter(Boolean).sort();
      if (bssids.length === 0) return [];
      return [sha256HexSync(bssids.join('|'))];
    } catch {
      return [];
    }
  }

  async _getBluetoothDigests() {
    const bleMod = safeRequire('react-native-ble-plx');
    if (!bleMod) return [];
    try {
      const { BleManager } = bleMod;
      if (!BleManager) return [];
      const manager = new BleManager();
      const devices = await new Promise((resolve) => {
        const seen = new Set();
        const timeout = setTimeout(() => {
          try { manager.stopDeviceScan(); } catch { /* ignore */ }
          resolve(Array.from(seen));
        }, 4000);
        try {
          manager.startDeviceScan(null, null, (err, device) => {
            if (err) { clearTimeout(timeout); resolve(Array.from(seen)); return; }
            if (device?.id) seen.add(device.id);
          });
        } catch {
          clearTimeout(timeout);
          resolve([]);
        }
      });
      try { manager.destroy(); } catch { /* ignore */ }
      const ids = (devices || []).sort();
      if (ids.length === 0) return [];
      return [sha256HexSync(ids.join('|'))];
    } catch {
      return [];
    }
  }

  async _getAudioDigest() {
    const recorder = safeRequire('react-native-audio-record');
    if (!recorder) return [];
    try {
      const AudioRecord = recorder.default || recorder;
      AudioRecord.init({ sampleRate: 8000, channels: 1, bitsPerSample: 16, audioSource: 6, wavFile: 'ambient.wav' });
      let digestAcc = '';
      const sub = AudioRecord.on('data', (chunk) => {
        try {
          if (chunk && chunk.length) digestAcc = sha256HexSync(digestAcc + chunk.slice(0, 64));
        } catch { /* ignore */ }
      });
      AudioRecord.start();
      await new Promise((r) => setTimeout(r, 1500));
      try { await AudioRecord.stop(); } catch { /* ignore */ }
      try { if (sub?.remove) sub.remove(); } catch { /* ignore */ }
      return digestAcc ? [digestAcc] : [];
    } catch {
      return [];
    }
  }

  async _getConnectionClass() {
    const netinfo = safeRequire('@react-native-community/netinfo');
    if (!netinfo) return { connection_class: 'unknown', effective_type: 'unknown' };
    try {
      const NetInfo = netinfo.default || netinfo;
      const state = await NetInfo.fetch();
      const type = String(state?.type || '').toLowerCase();
      const cellGen = state?.details?.cellularGeneration ? String(state.details.cellularGeneration).toLowerCase() : 'unknown';
      return {
        connection_class: ['wifi', 'cellular', 'ethernet', 'bluetooth'].includes(type) ? type : (type || 'unknown'),
        effective_type: cellGen,
      };
    } catch {
      return { connection_class: 'unknown', effective_type: 'unknown' };
    }
  }

  async _getMotionClass() {
    const sensors = safeRequire('react-native-sensors');
    if (!sensors) return 'unknown';
    try {
      const { accelerometer, setUpdateIntervalForType, SensorTypes } = sensors;
      if (setUpdateIntervalForType && SensorTypes) {
        setUpdateIntervalForType(SensorTypes.Accelerometer, 100);
      }
      const mags = [];
      await new Promise((resolve) => {
        const sub = accelerometer.subscribe(({ x, y, z }) => {
          const m = Math.sqrt(x * x + y * y + z * z) - 9.8;
          mags.push(Math.abs(m));
        });
        setTimeout(() => {
          try { sub.unsubscribe(); } catch { /* ignore */ }
          resolve();
        }, 1200);
      });
      return classifyMotion(mags);
    } catch {
      return 'unknown';
    }
  }

  async _getAmbientLightBucket() {
    const lightMod = safeRequire('react-native-ambient-light-sensor');
    if (!lightMod) return 'unknown';
    try {
      const LightSensor = lightMod.default || lightMod;
      if (typeof LightSensor.getLuminance === 'function') {
        const lux = await LightSensor.getLuminance();
        return bucketLight(Number(lux));
      }
    } catch { /* ignore */ }
    return 'unknown';
  }

  async _getBatterySlopeBucket() {
    const deviceInfoMod = safeRequire('react-native-device-info');
    if (!deviceInfoMod) return 'unknown';
    try {
      const DeviceInfo = deviceInfoMod.default || deviceInfoMod;
      const pct = await DeviceInfo.getBatteryLevel();
      const charging = typeof DeviceInfo.isBatteryCharging === 'function'
        ? await DeviceInfo.isBatteryCharging() : false;
      if (charging) return 'charging';
      const last = await AsyncStorage.getItem('ambient_battery_last_v1');
      const nowTs = Date.now();
      await AsyncStorage.setItem('ambient_battery_last_v1', JSON.stringify({ pct, ts: nowTs }));
      if (!last) return 'unknown';
      const parsed = JSON.parse(last);
      const dt = Math.max(1, (nowTs - parsed.ts) / 1000);
      const slope = (pct - parsed.pct) / dt;
      return bucketBatterySlope(slope);
    } catch {
      return 'unknown';
    }
  }

  /**
   * Capture a single ambient observation and return the payload that
   * the backend ingest endpoint expects.
   */
  async captureObservation() {
    const { localSalt, deviceFp } = await this._ensureSaltAndFp();

    const [
      wifiDigests,
      btDigests,
      audioDigests,
      motionClass,
      lightBucket,
      batteryBucket,
      connInfo,
    ] = await Promise.all([
      this._getWifiDigests(),
      this._getBluetoothDigests(),
      this._getAudioDigest(),
      this._getMotionClass(),
      this._getAmbientLightBucket(),
      this._getBatterySlopeBucket(),
      this._getConnectionClass(),
    ]);

    const hour = new Date().getHours();
    const coarseFeatures = {
      motion_class: motionClass,
      light_bucket: lightBucket,
      battery_drain_slope_bucket: batteryBucket,
      connection_class: connInfo.connection_class,
      effective_type: connInfo.effective_type,
      platform: Platform.OS,
      is_business_hours: hour >= 8 && hour < 19,
      tz_offset_min: -new Date().getTimezoneOffset(),
    };
    const sensitiveDigests = {
      wifi: wifiDigests,
      bluetooth: btDigests,
      audio: audioDigests,
    };

    const embed = computeAmbientEmbedding({ coarseFeatures, sensitiveDigests, localSalt });

    return {
      surface: 'mobile',
      schema_version: 1,
      device_fp: deviceFp,
      local_salt_version: 1,
      signal_availability: embed.signalAvailability,
      coarse_features: embed.coarseFeatures,
      embedding_digest: embed.embeddingDigest,
    };
  }

  async _getApiBase() {
    const stored = await AsyncStorage.getItem(API_BASE_KEY);
    return (typeof stored === 'string' && stored) ? stored : DEFAULT_API_BASE;
  }

  async _getAuthToken() {
    return (await AsyncStorage.getItem('auth_token')) || '';
  }

  async isEnabled() {
    const v = await AsyncStorage.getItem(ENABLED_KEY);
    return v !== 'false';
  }

  async setEnabled(enabled) {
    await AsyncStorage.setItem(ENABLED_KEY, enabled ? 'true' : 'false');
  }

  async ingestOnce() {
    if (!(await this.isEnabled())) return { skipped: true };
    const token = await this._getAuthToken();
    if (!token) return { skipped: true, reason: 'not authenticated' };
    const payload = await this.captureObservation();
    try {
      const resp = await fetch(`${await this._getApiBase()}/api/ambient/ingest/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify(payload),
      });
      if (!resp.ok) return { ok: false, status: resp.status };
      return { ok: true, data: await resp.json() };
    } catch (err) {
      return { ok: false, error: String(err) };
    }
  }

  async getContexts() {
    const token = await this._getAuthToken();
    if (!token) return [];
    try {
      const resp = await fetch(`${await this._getApiBase()}/api/ambient/contexts/`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!resp.ok) return [];
      return await resp.json();
    } catch { return []; }
  }

  async promoteContext(contextId, label) {
    const token = await this._getAuthToken();
    if (!token) throw new Error('not authenticated');
    const resp = await fetch(`${await this._getApiBase()}/api/ambient/contexts/${contextId}/promote/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
      body: JSON.stringify({ label }),
    });
    if (!resp.ok) throw new Error(`promote failed: ${resp.status}`);
    return resp.json();
  }
}

export const ambientService = new AmbientService();
export default ambientService;

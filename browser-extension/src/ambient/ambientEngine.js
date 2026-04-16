/**
 * Ambient engine for the MV3 service worker.
 *
 * Uses `chrome.alarms` to periodically snapshot extension-visible
 * ambient signals (network fingerprint, display topology, idle state,
 * connection class, time-of-day bucket) and POST an observation to the
 * backend `/api/ambient/ingest/` endpoint.
 *
 * Privacy: only salted SimHash digests and bucketed coarse features
 * ship. No raw IPs, no raw display resolutions, no URL history.
 */

import { computeAmbientEmbedding, getOrCreateLocalSalt } from './ambientEmbedding.js';
import { getNetworkDigests, getConnectionClass } from './networkFingerprint.js';
import { getDisplayDigest, getDisplayCountBucket } from './displayFingerprint.js';
import { getIdleState } from './idleSignal.js';

const ALARM_NAME = 'ambient-engine-tick';
const DEFAULT_PERIOD_MINUTES = 5;
const API_BASE = 'http://localhost:8000'; // overridden from storage at runtime
const DEVICE_FP_KEY = 'ambient_device_fp_v1';
const API_BASE_KEY = 'ambient_api_base';
const AUTH_TOKEN_KEY = 'auth_token';
const FEATURE_ENABLED_KEY = 'ambient_engine_enabled';

async function getDeviceFp() {
  const stored = await chrome.storage.local.get(DEVICE_FP_KEY);
  if (stored && typeof stored[DEVICE_FP_KEY] === 'string' && stored[DEVICE_FP_KEY].length >= 16) {
    return stored[DEVICE_FP_KEY];
  }
  const rand = new Uint8Array(16);
  crypto.getRandomValues(rand);
  const hex = Array.from(rand, (b) => b.toString(16).padStart(2, '0')).join('');
  try { await chrome.storage.local.set({ [DEVICE_FP_KEY]: hex }); } catch { /* ignore */ }
  return hex;
}

async function getApiBase() {
  const stored = await chrome.storage.local.get(API_BASE_KEY);
  return (stored && typeof stored[API_BASE_KEY] === 'string' && stored[API_BASE_KEY]) || API_BASE;
}

async function getAuthToken() {
  const stored = await chrome.storage.local.get(AUTH_TOKEN_KEY);
  return (stored && typeof stored[AUTH_TOKEN_KEY] === 'string') ? stored[AUTH_TOKEN_KEY] : '';
}

export async function snapshotAmbient() {
  const [networkDigests, displayDigest, idleState] = await Promise.all([
    getNetworkDigests(),
    getDisplayDigest(),
    getIdleState(60),
  ]);
  const { connection_class, effective_type } = getConnectionClass();

  const hour = new Date().getHours();
  const coarseFeatures = {
    connection_class,
    effective_type,
    display_presence_bucket: getDisplayCountBucket(displayDigest),
    idle_state: idleState,
    tz_offset_min: new Date().getTimezoneOffset() * -1,
    is_business_hours: hour >= 8 && hour < 19,
  };
  const sensitiveDigests = {
    network: networkDigests,
    display: displayDigest ? [displayDigest] : [],
  };

  const localSalt = await getOrCreateLocalSalt();
  return {
    ...(await computeAmbientEmbedding({ coarseFeatures, sensitiveDigests, localSalt })),
  };
}

async function postObservation() {
  const enabled = await chrome.storage.local.get(FEATURE_ENABLED_KEY);
  if (enabled && enabled[FEATURE_ENABLED_KEY] === false) return { skipped: true };

  const token = await getAuthToken();
  if (!token) return { skipped: true, reason: 'not authenticated' };

  const { coarseFeatures, embeddingDigest, signalAvailability } = await snapshotAmbient();
  const deviceFp = await getDeviceFp();
  const apiBase = await getApiBase();

  const body = {
    surface: 'extension',
    schema_version: 1,
    device_fp: deviceFp,
    local_salt_version: 1,
    signal_availability: signalAvailability,
    coarse_features: coarseFeatures,
    embedding_digest: embeddingDigest,
  };

  try {
    const resp = await fetch(`${apiBase}/api/ambient/ingest/`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify(body),
    });
    if (!resp.ok) {
      return { ok: false, status: resp.status };
    }
    return { ok: true, data: await resp.json() };
  } catch (err) {
    return { ok: false, error: String(err) };
  }
}

export function startAmbientEngine({ periodMinutes = DEFAULT_PERIOD_MINUTES } = {}) {
  try {
    chrome.alarms.create(ALARM_NAME, {
      periodInMinutes: periodMinutes,
      delayInMinutes: 1,
    });
  } catch { /* ignore */ }
  if (chrome.alarms && chrome.alarms.onAlarm && chrome.alarms.onAlarm.addListener) {
    chrome.alarms.onAlarm.addListener((alarm) => {
      if (alarm.name !== ALARM_NAME) return;
      postObservation().catch(() => { /* silent */ });
    });
  }
}

export function stopAmbientEngine() {
  try { chrome.alarms.clear(ALARM_NAME); } catch { /* ignore */ }
}

export { postObservation };

/**
 * Shared ambient embedding helper.
 *
 * Used by the web app, the browser extension, and the React Native
 * mobile app (via `mobile/src/services/ambient/ambientEmbedding.js`,
 * which imports from this module) to guarantee cross-surface digest
 * compatibility.
 *
 * Inputs:
 *   {
 *     coarseFeatures: { [k: string]: any },
 *     sensitiveDigests: { [group: string]: string[] },  // pre-hashed hex strings only
 *     localSalt: string,                                 // per-user, per-device
 *   }
 *
 * Output:
 *   {
 *     coarseFeatures: canonicalized copy,
 *     embeddingDigest: 128-bit hex LSH digest,
 *     signalAvailability: { [signal: string]: boolean },
 *   }
 *
 * We NEVER return raw signals. Callers must hash sensitive inputs
 * (BSSIDs, BLE MACs, audio samples) BEFORE calling this helper; this
 * helper only folds hex digests under the local salt.
 */

const DIGEST_BITS = 128;

function hasSubtle() {
  return typeof crypto !== 'undefined' && crypto && crypto.subtle;
}

async function hmacSha256(keyBytes, messageBytes) {
  if (hasSubtle()) {
    const key = await crypto.subtle.importKey(
      'raw',
      keyBytes,
      { name: 'HMAC', hash: 'SHA-256' },
      false,
      ['sign'],
    );
    const sig = await crypto.subtle.sign('HMAC', key, messageBytes);
    return new Uint8Array(sig);
  }
  // Tiny JS fallback (only used in environments without SubtleCrypto —
  // tests mostly). Imports are lazy to avoid pulling extra bytes into the
  // main bundle.
  const { hmac } = await import('@noble/hashes/hmac');
  const { sha256 } = await import('@noble/hashes/sha2');
  return hmac(sha256, keyBytes, messageBytes);
}

function toBytes(x) {
  if (x instanceof Uint8Array) return x;
  return new TextEncoder().encode(typeof x === 'string' ? x : JSON.stringify(x));
}

function toHex(bytes) {
  return Array.from(bytes, (b) => b.toString(16).padStart(2, '0')).join('');
}

/**
 * SimHash-style LSH over a multiset of tokens.
 *
 * For each token: HMAC-SHA-256(salt, token). Take the first
 * `DIGEST_BITS/8` bytes, convert to bits, map 1 -> +1 and 0 -> -1, then
 * sum component-wise. Final bit is `1` if sum > 0. This gives a digest
 * that's locality-sensitive (small token changes -> small Hamming
 * distance) while being deterministic and one-way.
 */
async function simhash(tokens, saltBytes) {
  const vector = new Array(DIGEST_BITS).fill(0);
  for (const token of tokens) {
    const sig = await hmacSha256(saltBytes, toBytes(token));
    for (let b = 0; b < DIGEST_BITS; b += 1) {
      const byte = sig[b >> 3];
      const bit = (byte >> (7 - (b & 7))) & 1;
      vector[b] += bit ? 1 : -1;
    }
  }
  const bits = new Uint8Array(DIGEST_BITS / 8);
  for (let b = 0; b < DIGEST_BITS; b += 1) {
    if (vector[b] > 0) {
      bits[b >> 3] |= 1 << (7 - (b & 7));
    }
  }
  return toHex(bits);
}

function canonicalizeCoarse(coarse) {
  if (!coarse || typeof coarse !== 'object') return {};
  const out = {};
  for (const k of Object.keys(coarse).sort()) {
    const v = coarse[k];
    if (v == null) continue;
    out[k] = v;
  }
  return out;
}

function tokensFromCoarse(coarse) {
  const tokens = [];
  for (const [k, v] of Object.entries(coarse)) {
    if (v == null) continue;
    if (typeof v === 'object') {
      tokens.push(`${k}:${JSON.stringify(v)}`);
    } else {
      tokens.push(`${k}:${String(v)}`);
    }
  }
  return tokens;
}

function tokensFromSensitiveDigests(sensitive) {
  const tokens = [];
  if (!sensitive || typeof sensitive !== 'object') return tokens;
  for (const [group, list] of Object.entries(sensitive)) {
    if (!Array.isArray(list)) continue;
    for (const d of list) {
      if (typeof d === 'string' && d.length > 0) {
        tokens.push(`${group}:${d}`);
      }
    }
  }
  return tokens;
}

function inferAvailability(coarse, sensitive) {
  const out = {};
  if ('light_bucket' in coarse && coarse.light_bucket && coarse.light_bucket !== 'unknown') {
    out.ambient_light = true;
  } else {
    out.ambient_light = false;
  }
  if ('motion_class' in coarse && coarse.motion_class && coarse.motion_class !== 'unknown') {
    out.accelerometer = true;
  } else {
    out.accelerometer = false;
  }
  if ('pointer_pressure_mean_bucket' in coarse && coarse.pointer_pressure_mean_bucket !== 'unknown') {
    out.pointer_pressure = true;
  } else {
    out.pointer_pressure = false;
  }
  if ('scroll_momentum_bucket' in coarse && coarse.scroll_momentum_bucket !== 'unknown') {
    out.scroll_momentum = true;
  } else {
    out.scroll_momentum = false;
  }
  if ('battery_drain_slope_bucket' in coarse && coarse.battery_drain_slope_bucket !== 'unknown') {
    out.battery_drain = true;
  } else {
    out.battery_drain = false;
  }
  if ('connection_class' in coarse && coarse.connection_class !== 'unknown') {
    out.network_class = true;
  } else {
    out.network_class = false;
  }
  if ('typing_cadence_stats' in coarse
      && coarse.typing_cadence_stats
      && typeof coarse.typing_cadence_stats === 'object') {
    out.typing_cadence = true;
  } else {
    out.typing_cadence = false;
  }
  out.wifi_signature = Boolean(sensitive && Array.isArray(sensitive.wifi) && sensitive.wifi.length > 0);
  out.bluetooth_devices = Boolean(sensitive && Array.isArray(sensitive.bluetooth) && sensitive.bluetooth.length > 0);
  out.ambient_audio = Boolean(sensitive && Array.isArray(sensitive.audio) && sensitive.audio.length > 0);
  out.geohash = Boolean(coarse.geohash_bucket);
  return out;
}

/**
 * Compute coarse features, availability, and LSH digest.
 */
export async function computeAmbientEmbedding({
  coarseFeatures = {},
  sensitiveDigests = {},
  localSalt = '',
} = {}) {
  const canonical = canonicalizeCoarse(coarseFeatures);
  const saltBytes = typeof localSalt === 'string' ? toBytes(localSalt) : new Uint8Array(0);
  const tokens = [
    ...tokensFromCoarse(canonical),
    ...tokensFromSensitiveDigests(sensitiveDigests),
  ];
  const digest = tokens.length > 0 ? await simhash(tokens, saltBytes) : '';
  return {
    coarseFeatures: canonical,
    embeddingDigest: digest,
    signalAvailability: inferAvailability(canonical, sensitiveDigests),
  };
}

/**
 * Get-or-create a per-user local salt stored in IndexedDB/localStorage.
 * Never shipped off-device. Rotatable — bumping the salt version forces
 * a fresh baseline on the backend.
 */
const SALT_STORAGE_KEY = 'ambient_auth_local_salt_v1';

export function getOrCreateLocalSalt() {
  if (typeof localStorage === 'undefined') {
    return 'ambient-auth-ephemeral-salt';
  }
  let s = null;
  try { s = localStorage.getItem(SALT_STORAGE_KEY); } catch { /* ignore */ }
  if (s && s.length >= 24) return s;
  const rand = new Uint8Array(32);
  if (typeof crypto !== 'undefined' && crypto.getRandomValues) {
    crypto.getRandomValues(rand);
  } else {
    for (let i = 0; i < rand.length; i += 1) {
      rand[i] = Math.floor(Math.random() * 256);
    }
  }
  const hex = toHex(rand);
  try { localStorage.setItem(SALT_STORAGE_KEY, hex); } catch { /* ignore */ }
  return hex;
}

export function rotateLocalSalt() {
  try { localStorage.removeItem(SALT_STORAGE_KEY); } catch { /* ignore */ }
  return getOrCreateLocalSalt();
}

export default {
  computeAmbientEmbedding,
  getOrCreateLocalSalt,
  rotateLocalSalt,
};

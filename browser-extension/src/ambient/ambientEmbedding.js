/**
 * Browser-extension copy of the shared ambient embedding helper.
 *
 * MUST produce byte-for-byte identical digests to
 * `frontend/src/services/ambient/ambientEmbedding.js` and
 * `mobile/src/services/ambient/ambientEmbedding.js` for the same inputs
 * and salt, so a user on the web app + extension + mobile ends up with
 * matching LSH digests whenever their environment is consistent.
 *
 * Algorithm (SimHash-style, 128-bit):
 *   1. Canonicalize coarse features (sort keys, drop nulls).
 *   2. Build tokens: [`${k}:${v}` for k,v in canonical] ++
 *      [`${group}:${digest}` for digest in sensitive[group]].
 *   3. For each token: HMAC-SHA-256(saltBytes, utf8(token)); take first
 *      16 bytes; map each bit to +1 or -1 and accumulate component-wise.
 *   4. Sign bit -> 1, negative -> 0, pack into 16 bytes, return as hex.
 */

const DIGEST_BITS = 128;

function toBytes(x) {
  if (x instanceof Uint8Array) return x;
  return new TextEncoder().encode(typeof x === 'string' ? x : JSON.stringify(x));
}

function toHex(bytes) {
  return Array.from(bytes, (b) => b.toString(16).padStart(2, '0')).join('');
}

async function hmacSha256(keyBytes, messageBytes) {
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
    if (vector[b] > 0) bits[b >> 3] |= 1 << (7 - (b & 7));
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
    if (typeof v === 'object') tokens.push(`${k}:${JSON.stringify(v)}`);
    else tokens.push(`${k}:${String(v)}`);
  }
  return tokens;
}

function tokensFromSensitive(sensitive) {
  const tokens = [];
  if (!sensitive || typeof sensitive !== 'object') return tokens;
  for (const [group, list] of Object.entries(sensitive)) {
    if (!Array.isArray(list)) continue;
    for (const d of list) {
      if (typeof d === 'string' && d.length > 0) tokens.push(`${group}:${d}`);
    }
  }
  return tokens;
}

function inferAvailability(coarse, sensitive) {
  const out = {};
  out.ambient_light = coarse.light_bucket && coarse.light_bucket !== 'unknown' ? true : false;
  out.accelerometer = coarse.motion_class && coarse.motion_class !== 'unknown' ? true : false;
  out.pointer_pressure = coarse.pointer_pressure_mean_bucket && coarse.pointer_pressure_mean_bucket !== 'unknown' ? true : false;
  out.scroll_momentum = coarse.scroll_momentum_bucket && coarse.scroll_momentum_bucket !== 'unknown' ? true : false;
  out.battery_drain = coarse.battery_drain_slope_bucket && coarse.battery_drain_slope_bucket !== 'unknown' ? true : false;
  out.network_class = coarse.connection_class && coarse.connection_class !== 'unknown' ? true : false;
  out.typing_cadence = Boolean(coarse.typing_cadence_stats && typeof coarse.typing_cadence_stats === 'object');
  out.wifi_signature = Boolean(sensitive?.wifi?.length);
  out.bluetooth_devices = Boolean(sensitive?.bluetooth?.length);
  out.ambient_audio = Boolean(sensitive?.audio?.length);
  out.geohash = Boolean(coarse.geohash_bucket);
  return out;
}

export async function computeAmbientEmbedding({
  coarseFeatures = {},
  sensitiveDigests = {},
  localSalt = '',
} = {}) {
  const canonical = canonicalizeCoarse(coarseFeatures);
  const saltBytes = typeof localSalt === 'string' ? toBytes(localSalt) : new Uint8Array(0);
  const tokens = [...tokensFromCoarse(canonical), ...tokensFromSensitive(sensitiveDigests)];
  const digest = tokens.length > 0 ? await simhash(tokens, saltBytes) : '';
  return {
    coarseFeatures: canonical,
    embeddingDigest: digest,
    signalAvailability: inferAvailability(canonical, sensitiveDigests),
  };
}

const SALT_STORAGE_KEY = 'ambient_auth_local_salt_v1';

export async function getOrCreateLocalSalt() {
  try {
    const stored = await chrome.storage.local.get(SALT_STORAGE_KEY);
    if (stored && typeof stored[SALT_STORAGE_KEY] === 'string' && stored[SALT_STORAGE_KEY].length >= 24) {
      return stored[SALT_STORAGE_KEY];
    }
  } catch { /* ignore */ }
  const rand = new Uint8Array(32);
  crypto.getRandomValues(rand);
  const hex = toHex(rand);
  try { await chrome.storage.local.set({ [SALT_STORAGE_KEY]: hex }); } catch { /* ignore */ }
  return hex;
}

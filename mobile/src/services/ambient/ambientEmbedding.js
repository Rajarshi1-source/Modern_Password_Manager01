/**
 * React-Native copy of the shared ambient embedding helper.
 *
 * MUST produce byte-for-byte identical digests to
 *   frontend/src/services/ambient/ambientEmbedding.js
 *   browser-extension/src/ambient/ambientEmbedding.js
 * for the same inputs and local salt.
 *
 * Uses `react-native-quick-crypto`'s HMAC-SHA-256 if available and
 * falls back to a pure-JS SHA-256 + HMAC implementation so the module
 * works on any RN runtime, including Expo Go.
 */

import AsyncStorage from '@react-native-async-storage/async-storage';

const DIGEST_BITS = 128;
const SALT_STORAGE_KEY = 'ambient_auth_local_salt_v1';

function utf8(s) {
  const out = [];
  for (let i = 0; i < s.length; i += 1) {
    let c = s.charCodeAt(i);
    if (c < 0x80) out.push(c);
    else if (c < 0x800) { out.push(0xc0 | (c >> 6)); out.push(0x80 | (c & 0x3f)); }
    else if (c < 0xd800 || c >= 0xe000) {
      out.push(0xe0 | (c >> 12)); out.push(0x80 | ((c >> 6) & 0x3f)); out.push(0x80 | (c & 0x3f));
    } else {
      i += 1;
      const cc = 0x10000 + (((c & 0x3ff) << 10) | (s.charCodeAt(i) & 0x3ff));
      out.push(0xf0 | (cc >> 18));
      out.push(0x80 | ((cc >> 12) & 0x3f));
      out.push(0x80 | ((cc >> 6) & 0x3f));
      out.push(0x80 | (cc & 0x3f));
    }
  }
  return new Uint8Array(out);
}

function toHex(bytes) {
  let s = '';
  for (let i = 0; i < bytes.length; i += 1) s += bytes[i].toString(16).padStart(2, '0');
  return s;
}

// Pure-JS SHA-256 (fallback)
const K = new Uint32Array([
  0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5,
  0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3, 0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174,
  0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc, 0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
  0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7, 0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967,
  0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13, 0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85,
  0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
  0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3,
  0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208, 0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2,
]);

function sha256Js(msg) {
  const H = new Uint32Array([
    0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a,
    0x510e527f, 0x9b05688c, 0x1f83d9ab, 0x5be0cd19,
  ]);
  const len = msg.length;
  const paddedLen = (((len + 9) + 63) & ~63);
  const padded = new Uint8Array(paddedLen);
  padded.set(msg);
  padded[len] = 0x80;
  const bitLen = len * 8;
  padded[paddedLen - 4] = (bitLen >>> 24) & 0xff;
  padded[paddedLen - 3] = (bitLen >>> 16) & 0xff;
  padded[paddedLen - 2] = (bitLen >>> 8) & 0xff;
  padded[paddedLen - 1] = bitLen & 0xff;

  const W = new Uint32Array(64);
  for (let chunk = 0; chunk < paddedLen; chunk += 64) {
    for (let i = 0; i < 16; i += 1) {
      const j = chunk + i * 4;
      W[i] = (padded[j] << 24) | (padded[j + 1] << 16) | (padded[j + 2] << 8) | padded[j + 3];
    }
    for (let i = 16; i < 64; i += 1) {
      const s0 = ((W[i - 15] >>> 7) | (W[i - 15] << 25)) ^ ((W[i - 15] >>> 18) | (W[i - 15] << 14)) ^ (W[i - 15] >>> 3);
      const s1 = ((W[i - 2] >>> 17) | (W[i - 2] << 15)) ^ ((W[i - 2] >>> 19) | (W[i - 2] << 13)) ^ (W[i - 2] >>> 10);
      W[i] = (W[i - 16] + s0 + W[i - 7] + s1) | 0;
    }
    let a = H[0], b = H[1], c = H[2], d = H[3];
    let e = H[4], f = H[5], g = H[6], h = H[7];
    for (let i = 0; i < 64; i += 1) {
      const S1 = ((e >>> 6) | (e << 26)) ^ ((e >>> 11) | (e << 21)) ^ ((e >>> 25) | (e << 7));
      const ch = (e & f) ^ (~e & g);
      const temp1 = (h + S1 + ch + K[i] + W[i]) | 0;
      const S0 = ((a >>> 2) | (a << 30)) ^ ((a >>> 13) | (a << 19)) ^ ((a >>> 22) | (a << 10));
      const mj = (a & b) ^ (a & c) ^ (b & c);
      const temp2 = (S0 + mj) | 0;
      h = g; g = f; f = e; e = (d + temp1) | 0;
      d = c; c = b; b = a; a = (temp1 + temp2) | 0;
    }
    H[0] = (H[0] + a) | 0; H[1] = (H[1] + b) | 0; H[2] = (H[2] + c) | 0; H[3] = (H[3] + d) | 0;
    H[4] = (H[4] + e) | 0; H[5] = (H[5] + f) | 0; H[6] = (H[6] + g) | 0; H[7] = (H[7] + h) | 0;
  }
  const out = new Uint8Array(32);
  for (let i = 0; i < 8; i += 1) {
    out[i * 4] = (H[i] >>> 24) & 0xff;
    out[i * 4 + 1] = (H[i] >>> 16) & 0xff;
    out[i * 4 + 2] = (H[i] >>> 8) & 0xff;
    out[i * 4 + 3] = H[i] & 0xff;
  }
  return out;
}

function hmacSha256Js(keyBytes, msg) {
  let key = keyBytes;
  if (key.length > 64) key = sha256Js(key);
  const padded = new Uint8Array(64);
  padded.set(key);
  const oKey = new Uint8Array(64);
  const iKey = new Uint8Array(64);
  for (let i = 0; i < 64; i += 1) {
    oKey[i] = padded[i] ^ 0x5c;
    iKey[i] = padded[i] ^ 0x36;
  }
  const inner = new Uint8Array(iKey.length + msg.length);
  inner.set(iKey); inner.set(msg, iKey.length);
  const innerHash = sha256Js(inner);
  const outer = new Uint8Array(oKey.length + innerHash.length);
  outer.set(oKey); outer.set(innerHash, oKey.length);
  return sha256Js(outer);
}

function simhash(tokens, saltBytes) {
  const vector = new Array(DIGEST_BITS).fill(0);
  for (const token of tokens) {
    const sig = hmacSha256Js(saltBytes, utf8(token));
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
  return {
    ambient_light: coarse.light_bucket && coarse.light_bucket !== 'unknown' ? true : false,
    accelerometer: coarse.motion_class && coarse.motion_class !== 'unknown' ? true : false,
    pointer_pressure: Boolean(coarse.pointer_pressure_mean_bucket && coarse.pointer_pressure_mean_bucket !== 'unknown'),
    scroll_momentum: Boolean(coarse.scroll_momentum_bucket && coarse.scroll_momentum_bucket !== 'unknown'),
    battery_drain: Boolean(coarse.battery_drain_slope_bucket && coarse.battery_drain_slope_bucket !== 'unknown'),
    network_class: Boolean(coarse.connection_class && coarse.connection_class !== 'unknown'),
    typing_cadence: Boolean(coarse.typing_cadence_stats && typeof coarse.typing_cadence_stats === 'object'),
    wifi_signature: Boolean(sensitive?.wifi?.length),
    bluetooth_devices: Boolean(sensitive?.bluetooth?.length),
    ambient_audio: Boolean(sensitive?.audio?.length),
    geohash: Boolean(coarse.geohash_bucket),
  };
}

export function computeAmbientEmbedding({
  coarseFeatures = {},
  sensitiveDigests = {},
  localSalt = '',
} = {}) {
  const canonical = canonicalizeCoarse(coarseFeatures);
  const saltBytes = typeof localSalt === 'string' ? utf8(localSalt) : new Uint8Array(0);
  const tokens = [...tokensFromCoarse(canonical), ...tokensFromSensitive(sensitiveDigests)];
  const digest = tokens.length > 0 ? simhash(tokens, saltBytes) : '';
  return {
    coarseFeatures: canonical,
    embeddingDigest: digest,
    signalAvailability: inferAvailability(canonical, sensitiveDigests),
  };
}

function randomHex(n) {
  let s = '';
  for (let i = 0; i < n; i += 1) {
    s += Math.floor(Math.random() * 256).toString(16).padStart(2, '0');
  }
  return s;
}

export async function getOrCreateLocalSalt() {
  try {
    const stored = await AsyncStorage.getItem(SALT_STORAGE_KEY);
    if (typeof stored === 'string' && stored.length >= 24) return stored;
  } catch { /* ignore */ }
  const hex = randomHex(32);
  try { await AsyncStorage.setItem(SALT_STORAGE_KEY, hex); } catch { /* ignore */ }
  return hex;
}

export async function rotateLocalSalt() {
  const hex = randomHex(32);
  try { await AsyncStorage.setItem(SALT_STORAGE_KEY, hex); } catch { /* ignore */ }
  return hex;
}

export function sha256HexSync(text) {
  return toHex(sha256Js(utf8(text)));
}

export function hmacSha256HexSync(keyText, msgText) {
  return toHex(hmacSha256Js(utf8(keyText), utf8(msgText)));
}

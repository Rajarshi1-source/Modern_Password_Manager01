/**
 * StegoVaultService - mobile surface.
 *
 * Mirrors the web and browser-extension stego module as closely as
 * React Native allows:
 *
 *   * Server-side CRUD (list / download / delete / store) goes through
 *     the existing ``/api/stego/`` endpoints via authService.
 *   * PNG decoding uses ``pako`` + ``buffer`` (pure JS, no native
 *     modules), so we can read raw pixel bytes and execute the same
 *     LSB permutation + slot framing as the Python / browser impls.
 *   * Argon2id key derivation is the one piece that cannot be done in
 *     pure JS with reasonable performance on RN. We use ``safeRequire``
 *     to look for ``react-native-argon2`` at runtime; if missing, we
 *     degrade gracefully and surface an actionable error instead of
 *     silently falling back to a weaker KDF.
 *
 * The file format is the exact byte-compatible ``HiddenVaultBlob v1``
 * described in ``password_manager/hidden_vault/SPEC.md``.
 */

import { Buffer } from 'buffer';
import pako from 'pako';

import authService from './authService';

// ---------------------------------------------------------------------------
// Constants (must match SPEC.md + envelope.py + web envelope)
// ---------------------------------------------------------------------------

const MAGIC = Buffer.from('HVBLOBv1', 'latin1');
const VERSION = 0x01;
const SLOT_COUNT = 2;
const KDF_ID_ARGON2ID = 0x01;

const OUTER_SALT_LEN = 16;
const NONCE_LEN = 12;
const GCM_TAG_LEN = 16;
const KEY_LEN = 32;
const HEADER_FIXED_LEN = 42;

const SLOT_FRAME_MAGIC = Buffer.from('HVS1', 'latin1');
const SLOT_FRAME_HEADER_LEN = 8;

const DOMAIN_TAG_PREFIX = Buffer.from('HVBLOBv1/slot', 'latin1');

export const TIERS = Object.freeze({
  TIER0_32K: 0,
  TIER1_128K: 1,
  TIER2_1M: 2,
});

const TIER_TOTAL_BYTES = { 0: 32 * 1024, 1: 128 * 1024, 2: 1024 * 1024 };
const TIER_SLOT_PAYLOAD_LEN = { 0: 16000, 1: 60000, 2: 490000 };

const PNG_SIGNATURE = Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]);
const PNG_HEADER_LEN = 4;
const BITS_PER_PIXEL = 3;

function safeRequire(name) {
  try {
    // eslint-disable-next-line global-require
    return require(name);
  } catch {
    return null;
  }
}

// ---------------------------------------------------------------------------
// PNG parsing (no libpng — we walk the chunks ourselves and rely on pako
// for the IDAT inflate). Handles only RGB / RGBA 8-bit depth which is
// what our web encoder produces.
// ---------------------------------------------------------------------------

function readU32BE(buf, off) {
  return (
    (buf[off] * 0x1000000) +
    ((buf[off + 1] << 16) | (buf[off + 2] << 8) | buf[off + 3])
  );
}

function assertIsPng(buf) {
  if (buf.length < 8) throw new Error('Too short to be a PNG.');
  for (let i = 0; i < 8; i += 1) {
    if (buf[i] !== PNG_SIGNATURE[i]) {
      throw new Error('Input bytes are not a PNG file.');
    }
  }
}

function decodePng(bytes) {
  const buf = Buffer.isBuffer(bytes) ? bytes : Buffer.from(bytes);
  assertIsPng(buf);

  let off = 8;
  let width = 0;
  let height = 0;
  let colorType = 0;
  let bitDepth = 0;
  const idat = [];
  while (off < buf.length) {
    const length = readU32BE(buf, off);
    const type = buf.slice(off + 4, off + 8).toString('latin1');
    const data = buf.slice(off + 8, off + 8 + length);
    if (type === 'IHDR') {
      width = readU32BE(data, 0);
      height = readU32BE(data, 4);
      bitDepth = data[8];
      colorType = data[9];
    } else if (type === 'IDAT') {
      idat.push(data);
    } else if (type === 'IEND') {
      break;
    }
    off += 8 + length + 4; // header + data + CRC
  }
  if (bitDepth !== 8) throw new Error(`Unsupported PNG bit depth: ${bitDepth}`);
  if (colorType !== 2 && colorType !== 6) {
    throw new Error(`Unsupported PNG color type: ${colorType}`);
  }
  const channels = colorType === 2 ? 3 : 4;
  const inflated = pako.inflate(Buffer.concat(idat));
  // Undo PNG scanline filters. Only the "None" (0) and "Sub" (1)
  // filters are common in our exports; we implement the full set.
  const rowBytes = width * channels;
  const pixels = new Uint8Array(width * height * 4); // RGBA out
  let inPos = 0;
  const prevRow = new Uint8Array(rowBytes);
  const currRow = new Uint8Array(rowBytes);
  for (let y = 0; y < height; y += 1) {
    const filter = inflated[inPos];
    inPos += 1;
    for (let x = 0; x < rowBytes; x += 1) {
      const raw = inflated[inPos + x];
      const left = x >= channels ? currRow[x - channels] : 0;
      const up = prevRow[x];
      const upLeft = x >= channels ? prevRow[x - channels] : 0;
      let recon;
      switch (filter) {
        case 0: recon = raw; break;
        case 1: recon = (raw + left) & 0xff; break;
        case 2: recon = (raw + up) & 0xff; break;
        case 3: recon = (raw + ((left + up) >> 1)) & 0xff; break;
        case 4: {
          const p = left + up - upLeft;
          const pa = Math.abs(p - left);
          const pb = Math.abs(p - up);
          const pc = Math.abs(p - upLeft);
          let paeth;
          if (pa <= pb && pa <= pc) paeth = left;
          else if (pb <= pc) paeth = up;
          else paeth = upLeft;
          recon = (raw + paeth) & 0xff;
          break;
        }
        default: throw new Error(`Unsupported PNG filter: ${filter}`);
      }
      currRow[x] = recon;
    }
    inPos += rowBytes;
    // Emit this row as RGBA.
    for (let x = 0; x < width; x += 1) {
      const srcOff = x * channels;
      const dstOff = (y * width + x) * 4;
      pixels[dstOff]     = currRow[srcOff];
      pixels[dstOff + 1] = currRow[srcOff + 1];
      pixels[dstOff + 2] = currRow[srcOff + 2];
      pixels[dstOff + 3] = channels === 4 ? currRow[srcOff + 3] : 0xff;
    }
    prevRow.set(currRow);
  }
  return { width, height, pixels };
}

// ---------------------------------------------------------------------------
// SHA-256 + DRBG + Fisher-Yates permutation (matches Python + web).
// ---------------------------------------------------------------------------

// Lightweight SHA-256 (RFC 6234). Accepts and returns Buffer/Uint8Array.
const K = new Uint32Array([
  0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1,
  0x923f82a4, 0xab1c5ed5, 0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3,
  0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174, 0xe49b69c1, 0xefbe4786,
  0x0fc19dc6, 0x240ca1cc, 0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
  0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7, 0xc6e00bf3, 0xd5a79147,
  0x06ca6351, 0x14292967, 0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13,
  0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85, 0xa2bfe8a1, 0xa81a664b,
  0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
  0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a,
  0x5b9cca4f, 0x682e6ff3, 0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208,
  0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2,
]);

function sha256(input) {
  const data = Buffer.from(input);
  const ml = data.length * 8;
  const withOne = Buffer.concat([data, Buffer.from([0x80])]);
  const padLen = (56 - (withOne.length % 64) + 64) % 64;
  const padded = Buffer.concat([withOne, Buffer.alloc(padLen), Buffer.alloc(8)]);
  padded.writeUInt32BE(Math.floor(ml / 0x100000000), padded.length - 8);
  padded.writeUInt32BE(ml >>> 0, padded.length - 4);

  const H = new Uint32Array([
    0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a,
    0x510e527f, 0x9b05688c, 0x1f83d9ab, 0x5be0cd19,
  ]);
  const W = new Uint32Array(64);
  for (let i = 0; i < padded.length; i += 64) {
    for (let t = 0; t < 16; t += 1) W[t] = padded.readUInt32BE(i + t * 4);
    for (let t = 16; t < 64; t += 1) {
      const s0 = ((W[t - 15] >>> 7) | (W[t - 15] << 25)) ^ ((W[t - 15] >>> 18) | (W[t - 15] << 14)) ^ (W[t - 15] >>> 3);
      const s1 = ((W[t - 2] >>> 17) | (W[t - 2] << 15)) ^ ((W[t - 2] >>> 19) | (W[t - 2] << 13)) ^ (W[t - 2] >>> 10);
      W[t] = (W[t - 16] + s0 + W[t - 7] + s1) >>> 0;
    }
    let [a, b, c, d, e, f, g, h] = H;
    for (let t = 0; t < 64; t += 1) {
      const S1 = ((e >>> 6) | (e << 26)) ^ ((e >>> 11) | (e << 21)) ^ ((e >>> 25) | (e << 7));
      const ch = (e & f) ^ (~e & g);
      const temp1 = (h + S1 + ch + K[t] + W[t]) >>> 0;
      const S0 = ((a >>> 2) | (a << 30)) ^ ((a >>> 13) | (a << 19)) ^ ((a >>> 22) | (a << 10));
      const mj = (a & b) ^ (a & c) ^ (b & c);
      const temp2 = (S0 + mj) >>> 0;
      h = g; g = f; f = e;
      e = (d + temp1) >>> 0;
      d = c; c = b; b = a;
      a = (temp1 + temp2) >>> 0;
    }
    H[0] = (H[0] + a) >>> 0; H[1] = (H[1] + b) >>> 0;
    H[2] = (H[2] + c) >>> 0; H[3] = (H[3] + d) >>> 0;
    H[4] = (H[4] + e) >>> 0; H[5] = (H[5] + f) >>> 0;
    H[6] = (H[6] + g) >>> 0; H[7] = (H[7] + h) >>> 0;
  }
  const out = Buffer.alloc(32);
  for (let i = 0; i < 8; i += 1) out.writeUInt32BE(H[i], i * 4);
  return out;
}

function counterBytesLE(n) {
  const b = Buffer.alloc(8);
  b.writeUInt32LE(n & 0xffffffff, 0);
  b.writeUInt32LE(Math.floor(n / 0x100000000) & 0xffffffff, 4);
  return b;
}

function permutation(numPixels, stegoKey) {
  const state = sha256(Buffer.concat([Buffer.from('png-lsb/v1|', 'latin1'), Buffer.from(stegoKey)]));
  let counter = 0;
  function randU32() {
    const blk = sha256(Buffer.concat([state, counterBytesLE(counter)]));
    counter += 1;
    return blk.readUInt32LE(0);
  }
  const out = new Uint32Array(numPixels);
  for (let i = 0; i < numPixels; i += 1) out[i] = i;
  for (let i = numPixels - 1; i > 0; i -= 1) {
    const j = randU32() % (i + 1);
    const tmp = out[i]; out[i] = out[j]; out[j] = tmp;
  }
  return out;
}

// ---------------------------------------------------------------------------
// PNG LSB extract (stego PNG -> blob bytes)
// ---------------------------------------------------------------------------

const DEFAULT_STEGO_KEY = Buffer.from('default-png-lsb-key', 'latin1');

export async function extractBlobFromPngBytes(pngBytes, stegoKey = DEFAULT_STEGO_KEY) {
  const { width, height, pixels } = decodePng(pngBytes);
  const numPixels = width * height;
  const order = permutation(numPixels, stegoKey);
  function readBit(bitIdx) {
    const pixelCursor = Math.floor(bitIdx / BITS_PER_PIXEL);
    const channelCursor = bitIdx % BITS_PER_PIXEL;
    if (pixelCursor >= numPixels) throw new Error('Ran out of cover while reading LSBs');
    return pixels[order[pixelCursor] * 4 + channelCursor] & 0x1;
  }
  const headerBits = new Uint8Array(PNG_HEADER_LEN * 8);
  for (let i = 0; i < headerBits.length; i += 1) headerBits[i] = readBit(i);
  const headerBytes = Buffer.alloc(PNG_HEADER_LEN);
  for (let i = 0; i < PNG_HEADER_LEN; i += 1) {
    let byte = 0;
    for (let b = 0; b < 8; b += 1) byte |= (headerBits[i * 8 + b] & 0x1) << (7 - b);
    headerBytes[i] = byte;
  }
  const length = headerBytes.readUInt32LE(0);
  const capacity = Math.floor((numPixels * BITS_PER_PIXEL) / 8) - PNG_HEADER_LEN;
  if (length === 0 || length > capacity) {
    throw new Error(`Invalid embedded length ${length} (capacity ${capacity}).`);
  }
  const payload = Buffer.alloc(length);
  for (let i = 0; i < length; i += 1) {
    let byte = 0;
    for (let b = 0; b < 8; b += 1) {
      byte |= (readBit(PNG_HEADER_LEN * 8 + i * 8 + b) & 0x1) << (7 - b);
    }
    payload[i] = byte;
  }
  return payload;
}

// ---------------------------------------------------------------------------
// HiddenVaultBlob v1 parsing + slot decryption
// ---------------------------------------------------------------------------

function parseBlobHeader(blob) {
  if (blob.length < HEADER_FIXED_LEN) throw new Error('blob too short');
  if (!blob.slice(0, 8).equals(MAGIC)) throw new Error('bad magic');
  if (blob[8] !== VERSION) throw new Error('unsupported version');
  if (blob[9] !== SLOT_COUNT) throw new Error('unsupported slot count');
  const tier = blob[10];
  if (!(tier in TIER_TOTAL_BYTES)) throw new Error('unknown tier');
  if (blob[11] !== KDF_ID_ARGON2ID) throw new Error('unsupported kdf id');
  const kdfTime = blob.readUInt32LE(12);
  const kdfMem = blob.readUInt32LE(16);
  const kdfPar = blob.readUInt32LE(20);
  const outerSalt = blob.slice(24, 24 + OUTER_SALT_LEN);
  const slotCtLen = blob.readUInt16LE(40);
  if (slotCtLen !== TIER_SLOT_PAYLOAD_LEN[tier]) {
    throw new Error('slot_ct_len does not match tier');
  }
  if (blob.length !== TIER_TOTAL_BYTES[tier]) {
    throw new Error('blob length does not match tier');
  }
  return { tier, kdfTime, kdfMem, kdfPar, outerSalt, slotCtLen };
}

async function deriveSlotKey({ password, outerSalt, slotIndex, kdfTime, kdfMem, kdfPar }) {
  const argon2 = safeRequire('react-native-argon2');
  if (!argon2) {
    throw new Error(
      'react-native-argon2 is not available. Install and link it to enable ' +
        'hidden-vault decryption on this device.',
    );
  }
  const salt = Buffer.concat([Buffer.from(outerSalt), DOMAIN_TAG_PREFIX, Buffer.from([slotIndex])]);
  // react-native-argon2 expects base64 salt.
  const saltB64 = salt.toString('base64');
  const raw = await argon2.default(password, saltB64, {
    iterations: kdfTime,
    memory: kdfMem,
    parallelism: kdfPar,
    hashLength: KEY_LEN,
    mode: 'argon2id',
  });
  if (!raw || !raw.rawHash) {
    throw new Error('Argon2id did not return a rawHash.');
  }
  return Buffer.from(raw.rawHash, 'hex');
}

async function aesGcmDecryptNative(key, nonce, ciphertext) {
  const aes = safeRequire('react-native-aes-gcm-crypto');
  if (!aes || !aes.default || !aes.default.decrypt) {
    throw new Error(
      'react-native-aes-gcm-crypto is not available. Install and link it to ' +
        'enable hidden-vault decryption on this device.',
    );
  }
  const tagStart = ciphertext.length - GCM_TAG_LEN;
  const body = ciphertext.slice(0, tagStart);
  const tag = ciphertext.slice(tagStart);
  const plaintextB64 = await aes.default.decrypt(
    body.toString('base64'),
    key.toString('base64'),
    nonce.toString('base64'),
    tag.toString('base64'),
    true,
  );
  return Buffer.from(plaintextB64, 'base64');
}

function unframePlaintext(frame) {
  if (frame.length < SLOT_FRAME_HEADER_LEN) return null;
  if (!frame.slice(0, 4).equals(SLOT_FRAME_MAGIC)) return null;
  const length = frame.readUInt32LE(4);
  if (length > frame.length - SLOT_FRAME_HEADER_LEN) return null;
  return frame.slice(8, 8 + length);
}

export async function decodeBlob(blobBytes, password) {
  const blob = Buffer.isBuffer(blobBytes) ? blobBytes : Buffer.from(blobBytes);
  const header = parseBlobHeader(blob);
  const s0Nonce = HEADER_FIXED_LEN;
  const s0Ct = s0Nonce + NONCE_LEN;
  const s1Nonce = s0Ct + header.slotCtLen;
  const s1Ct = s1Nonce + NONCE_LEN;
  const nonce0 = blob.slice(s0Nonce, s0Nonce + NONCE_LEN);
  const ct0 = blob.slice(s0Ct, s0Ct + header.slotCtLen);
  const nonce1 = blob.slice(s1Nonce, s1Nonce + NONCE_LEN);
  const ct1 = blob.slice(s1Ct, s1Ct + header.slotCtLen);

  const [k0, k1] = await Promise.all([
    deriveSlotKey({ password, outerSalt: header.outerSalt, slotIndex: 0, kdfTime: header.kdfTime, kdfMem: header.kdfMem, kdfPar: header.kdfPar }),
    deriveSlotKey({ password, outerSalt: header.outerSalt, slotIndex: 1, kdfTime: header.kdfTime, kdfMem: header.kdfMem, kdfPar: header.kdfPar }),
  ]);

  for (const [idx, key, nonce, ct] of [[0, k0, nonce0, ct0], [1, k1, nonce1, ct1]]) {
    try {
      const frame = await aesGcmDecryptNative(key, nonce, ct);
      const payload = unframePlaintext(frame);
      if (payload) return { slotIndex: idx, payload };
    } catch {
      // wrong password for this slot, try the other
    }
  }
  throw new Error('Wrong password.');
}

// ---------------------------------------------------------------------------
// Backend CRUD helpers
// ---------------------------------------------------------------------------

const API_BASE = 'http://localhost:8000';

async function authHeaders() {
  const token = (await authService.getAccessToken?.()) || '';
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export async function fetchConfig() {
  const resp = await fetch(`${API_BASE}/api/stego/config/`, { headers: await authHeaders() });
  if (!resp.ok) throw new Error(`config fetch failed: ${resp.status}`);
  return resp.json();
}

export async function listVaults() {
  const resp = await fetch(`${API_BASE}/api/stego/`, { headers: await authHeaders() });
  if (!resp.ok) throw new Error(`list failed: ${resp.status}`);
  return resp.json();
}

export async function downloadVault(vaultId) {
  const resp = await fetch(`${API_BASE}/api/stego/${vaultId}/`, { headers: await authHeaders() });
  if (!resp.ok) throw new Error(`download failed: ${resp.status}`);
  const ab = await resp.arrayBuffer();
  return Buffer.from(ab);
}

export async function unlockFromStegoBytes({ bytes, password, stegoKey = null }) {
  const blob = await extractBlobFromPngBytes(bytes, stegoKey || DEFAULT_STEGO_KEY);
  const { slotIndex, payload } = await decodeBlob(blob, password);
  let json = null;
  try { json = JSON.parse(payload.toString('utf8')); } catch { /* opaque bytes */ }
  return { slotIndex, payload, json };
}

export default {
  TIERS,
  fetchConfig,
  listVaults,
  downloadVault,
  unlockFromStegoBytes,
  extractBlobFromPngBytes,
  decodeBlob,
};

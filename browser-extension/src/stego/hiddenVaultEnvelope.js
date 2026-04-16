/**
 * HiddenVaultBlob v1 - browser implementation.
 *
 * Byte-compatible encode/decode of the cross-language blob format
 * documented in ``password_manager/hidden_vault/SPEC.md``.
 *
 * Uses:
 *  - ``argon2-browser`` for Argon2id key derivation (same parameters
 *    as the Python implementation so the same password + salt yield
 *    the same 32-byte slot key in both).
 *  - ``window.crypto.subtle`` for AES-256-GCM.
 *  - ``window.crypto.getRandomValues`` for nonces, salts, padding, and
 *    the throwaway key that fills the "unused" slot.
 *
 * Exported surface:
 *   * encode({ realPassword?, realPayload?, decoyPassword?, decoyPayload?, tier })
 *   * decode(blobBytes, password)
 *   * TIERS, tierBytes, slotPayloadLen
 */

import argon2 from 'argon2-browser';

// ---------------------------------------------------------------------------
// Constants (must match SPEC.md + envelope.py)
// ---------------------------------------------------------------------------

const MAGIC = new Uint8Array([0x48, 0x56, 0x42, 0x4c, 0x4f, 0x42, 0x76, 0x31]); // "HVBLOBv1"
const VERSION = 0x01;
const SLOT_COUNT = 2;
const KDF_ID_ARGON2ID = 0x01;

export const DEFAULT_KDF_TIME = 3;
export const DEFAULT_KDF_MEMORY_KIB = 65536;
export const DEFAULT_KDF_PARALLELISM = 1;

const OUTER_SALT_LEN = 16;
const NONCE_LEN = 12;
const GCM_TAG_LEN = 16;
const KEY_LEN = 32;

const HEADER_FIXED_LEN = 42;

const SLOT_FRAME_MAGIC = new Uint8Array([0x48, 0x56, 0x53, 0x31]); // "HVS1"
const SLOT_FRAME_HEADER_LEN = 8;

const DOMAIN_TAG_PREFIX = new Uint8Array([
  0x48, 0x56, 0x42, 0x4c, 0x4f, 0x42, 0x76, 0x31, 0x2f, 0x73, 0x6c, 0x6f, 0x74,
]); // "HVBLOBv1/slot"

export const TIERS = Object.freeze({
  TIER0_32K: 0,
  TIER1_128K: 1,
  TIER2_1M: 2,
});

const TIER_TOTAL_BYTES = {
  [TIERS.TIER0_32K]: 32 * 1024,
  [TIERS.TIER1_128K]: 128 * 1024,
  [TIERS.TIER2_1M]: 1024 * 1024,
};

const TIER_SLOT_PAYLOAD_LEN = {
  [TIERS.TIER0_32K]: 16000,
  [TIERS.TIER1_128K]: 60000,
  [TIERS.TIER2_1M]: 490000,
};

export function tierBytes(tier) {
  const v = TIER_TOTAL_BYTES[tier];
  if (v === undefined) throw new Error(`Unknown tier: ${tier}`);
  return v;
}

export function slotPayloadLen(tier) {
  const v = TIER_SLOT_PAYLOAD_LEN[tier];
  if (v === undefined) throw new Error(`Unknown tier: ${tier}`);
  return v;
}

// ---------------------------------------------------------------------------
// Errors
// ---------------------------------------------------------------------------

export class HiddenVaultError extends Error {}
export class WrongPasswordError extends HiddenVaultError {}
export class MalformedBlobError extends HiddenVaultError {}
export class PayloadTooLargeError extends HiddenVaultError {}

// ---------------------------------------------------------------------------
// Byte helpers
// ---------------------------------------------------------------------------

const textEncoder = new TextEncoder();

function concatBytes(...chunks) {
  const total = chunks.reduce((n, c) => n + c.length, 0);
  const out = new Uint8Array(total);
  let off = 0;
  for (const c of chunks) {
    out.set(c, off);
    off += c.length;
  }
  return out;
}

function u32leBytes(n) {
  const b = new Uint8Array(4);
  const dv = new DataView(b.buffer);
  dv.setUint32(0, n >>> 0, true);
  return b;
}

function u16leBytes(n) {
  const b = new Uint8Array(2);
  const dv = new DataView(b.buffer);
  dv.setUint16(0, n & 0xffff, true);
  return b;
}

function readU32le(bytes, offset) {
  const dv = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
  return dv.getUint32(offset, true);
}

function readU16le(bytes, offset) {
  const dv = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
  return dv.getUint16(offset, true);
}

function randomBytes(n) {
  const b = new Uint8Array(n);
  window.crypto.getRandomValues(b);
  return b;
}

function bytesEqual(a, b) {
  if (a.length !== b.length) return false;
  for (let i = 0; i < a.length; i += 1) {
    if (a[i] !== b[i]) return false;
  }
  return true;
}

// ---------------------------------------------------------------------------
// KDF + AES-GCM
// ---------------------------------------------------------------------------

async function deriveSlotKey({
  password,
  outerSalt,
  slotIndex,
  kdfTime,
  kdfMemKib,
  kdfPar,
}) {
  if (slotIndex !== 0 && slotIndex !== 1) {
    throw new Error('slotIndex must be 0 or 1');
  }
  const domainTag = concatBytes(DOMAIN_TAG_PREFIX, new Uint8Array([slotIndex]));
  const salt = concatBytes(outerSalt, domainTag);
  const result = await argon2.hash({
    pass: password,
    salt,
    type: argon2.ArgonType.Argon2id,
    time: kdfTime,
    mem: kdfMemKib,
    parallelism: kdfPar,
    hashLen: KEY_LEN,
  });
  return result.hash; // Uint8Array length 32
}

async function aesGcmEncrypt(key, nonce, plaintext) {
  const cryptoKey = await window.crypto.subtle.importKey(
    'raw',
    key,
    { name: 'AES-GCM' },
    false,
    ['encrypt'],
  );
  const ct = await window.crypto.subtle.encrypt(
    { name: 'AES-GCM', iv: nonce, tagLength: GCM_TAG_LEN * 8 },
    cryptoKey,
    plaintext,
  );
  return new Uint8Array(ct);
}

async function aesGcmDecrypt(key, nonce, ciphertext) {
  const cryptoKey = await window.crypto.subtle.importKey(
    'raw',
    key,
    { name: 'AES-GCM' },
    false,
    ['decrypt'],
  );
  const pt = await window.crypto.subtle.decrypt(
    { name: 'AES-GCM', iv: nonce, tagLength: GCM_TAG_LEN * 8 },
    cryptoKey,
    ciphertext,
  );
  return new Uint8Array(pt);
}

// ---------------------------------------------------------------------------
// Slot framing
// ---------------------------------------------------------------------------

function framePlaintext(payload, slotCtLen) {
  const bodyLen = slotCtLen - GCM_TAG_LEN;
  if (payload.length + SLOT_FRAME_HEADER_LEN > bodyLen) {
    throw new PayloadTooLargeError(
      `Payload (${payload.length}B) does not fit in slot body ` +
        `(${bodyLen - SLOT_FRAME_HEADER_LEN}B available).`,
    );
  }
  const out = new Uint8Array(bodyLen); // zero-initialized = zero padding
  out.set(SLOT_FRAME_MAGIC, 0);
  out.set(u32leBytes(payload.length), 4);
  out.set(payload, 8);
  return out;
}

function unframePlaintext(frame) {
  if (frame.length < SLOT_FRAME_HEADER_LEN) return null;
  if (!bytesEqual(frame.subarray(0, 4), SLOT_FRAME_MAGIC)) return null;
  const length = readU32le(frame, 4);
  if (length > frame.length - SLOT_FRAME_HEADER_LEN) return null;
  return frame.subarray(8, 8 + length);
}

// ---------------------------------------------------------------------------
// encode / decode
// ---------------------------------------------------------------------------

/**
 * Build a HiddenVaultBlob v1 opaque byte string.
 *
 * @param {{
 *   realPassword?: string,
 *   realPayload?: Uint8Array,
 *   decoyPassword?: string,
 *   decoyPayload?: Uint8Array,
 *   tier?: number,
 *   kdfTime?: number,
 *   kdfMemKib?: number,
 *   kdfPar?: number,
 * }} opts
 * @returns {Promise<Uint8Array>}
 */
export async function encode({
  realPassword = null,
  realPayload = new Uint8Array(0),
  decoyPassword = null,
  decoyPayload = new Uint8Array(0),
  tier = TIERS.TIER0_32K,
  kdfTime = DEFAULT_KDF_TIME,
  kdfMemKib = DEFAULT_KDF_MEMORY_KIB,
  kdfPar = DEFAULT_KDF_PARALLELISM,
} = {}) {
  if (realPassword == null && decoyPassword == null) {
    throw new Error('At least one of realPassword / decoyPassword is required.');
  }
  const totalBytes = tierBytes(tier);
  const ctLen = slotPayloadLen(tier);

  const outerSalt = randomBytes(OUTER_SALT_LEN);
  const header = concatBytes(
    MAGIC,
    new Uint8Array([VERSION, SLOT_COUNT, tier, KDF_ID_ARGON2ID]),
    u32leBytes(kdfTime),
    u32leBytes(kdfMemKib),
    u32leBytes(kdfPar),
    outerSalt,
    u16leBytes(ctLen),
  );
  if (header.length !== HEADER_FIXED_LEN) {
    throw new Error(`Internal error: header length ${header.length}`);
  }

  async function keyFor(password, slotIndex) {
    if (password == null) return randomBytes(KEY_LEN); // throwaway
    return deriveSlotKey({
      password,
      outerSalt,
      slotIndex,
      kdfTime,
      kdfMemKib,
      kdfPar,
    });
  }

  const [key0, key1] = await Promise.all([
    keyFor(realPassword, 0),
    keyFor(decoyPassword, 1),
  ]);

  const plaintext0 = framePlaintext(realPayload, ctLen);
  const plaintext1 = framePlaintext(decoyPayload, ctLen);

  const nonce0 = randomBytes(NONCE_LEN);
  const nonce1 = randomBytes(NONCE_LEN);

  const [ct0, ct1] = await Promise.all([
    aesGcmEncrypt(key0, nonce0, plaintext0),
    aesGcmEncrypt(key1, nonce1, plaintext1),
  ]);
  if (ct0.length !== ctLen || ct1.length !== ctLen) {
    throw new Error('Internal error: ciphertext length mismatch');
  }

  const assembled = concatBytes(header, nonce0, ct0, nonce1, ct1);
  const padLen = totalBytes - assembled.length;
  if (padLen < 0) {
    throw new Error(
      `Internal error: assembled length ${assembled.length} > tier ${totalBytes}`,
    );
  }
  const pad = randomBytes(padLen);
  const blob = concatBytes(assembled, pad);
  if (blob.length !== totalBytes) {
    throw new Error(`Internal error: blob length ${blob.length}`);
  }
  return blob;
}

function parseHeader(blob) {
  if (blob.length < HEADER_FIXED_LEN) {
    throw new MalformedBlobError('blob shorter than header length');
  }
  if (!bytesEqual(blob.subarray(0, 8), MAGIC)) {
    throw new MalformedBlobError('bad magic');
  }
  const version = blob[8];
  if (version !== VERSION) {
    throw new MalformedBlobError(`unsupported version: ${version}`);
  }
  const slotCount = blob[9];
  if (slotCount !== SLOT_COUNT) {
    throw new MalformedBlobError(`unsupported slot count: ${slotCount}`);
  }
  const tier = blob[10];
  if (TIER_TOTAL_BYTES[tier] === undefined) {
    throw new MalformedBlobError(`unknown tier: ${tier}`);
  }
  const kdfId = blob[11];
  if (kdfId !== KDF_ID_ARGON2ID) {
    throw new MalformedBlobError(`unsupported kdf id: ${kdfId}`);
  }
  const kdfTime = readU32le(blob, 12);
  const kdfMem = readU32le(blob, 16);
  const kdfPar = readU32le(blob, 20);
  const outerSalt = blob.subarray(24, 24 + OUTER_SALT_LEN);
  const slotCtLen = readU16le(blob, 40);
  if (slotCtLen !== TIER_SLOT_PAYLOAD_LEN[tier]) {
    throw new MalformedBlobError(
      `slot_ct_len=${slotCtLen} does not match tier expectation=${TIER_SLOT_PAYLOAD_LEN[tier]}`,
    );
  }
  if (blob.length !== TIER_TOTAL_BYTES[tier]) {
    throw new MalformedBlobError(
      `blob length ${blob.length} != tier total ${TIER_TOTAL_BYTES[tier]}`,
    );
  }
  return { version, slotCount, tier, kdfTime, kdfMem, kdfPar, outerSalt, slotCtLen };
}

function slotOffsets(slotCtLen) {
  const s0Nonce = HEADER_FIXED_LEN;
  const s0Ct = s0Nonce + NONCE_LEN;
  const s1Nonce = s0Ct + slotCtLen;
  const s1Ct = s1Nonce + NONCE_LEN;
  return { s0Nonce, s0Ct, s1Nonce, s1Ct };
}

/**
 * Try to unlock ``blob`` with ``password``. Attempts both slots.
 * Returns ``{ slotIndex, payload: Uint8Array }`` or throws
 * :class:`WrongPasswordError`.
 */
export async function decode(blob, password) {
  if (!(blob instanceof Uint8Array)) {
    throw new TypeError('blob must be Uint8Array');
  }
  const header = parseHeader(blob);
  const { s0Nonce, s0Ct, s1Nonce, s1Ct } = slotOffsets(header.slotCtLen);
  const nonce0 = blob.subarray(s0Nonce, s0Nonce + NONCE_LEN);
  const ct0 = blob.subarray(s0Ct, s0Ct + header.slotCtLen);
  const nonce1 = blob.subarray(s1Nonce, s1Nonce + NONCE_LEN);
  const ct1 = blob.subarray(s1Ct, s1Ct + header.slotCtLen);

  // Always derive both keys and always try both decryptions to keep
  // behaviour roughly constant-time between slots.
  const [k0, k1] = await Promise.all([
    deriveSlotKey({
      password,
      outerSalt: header.outerSalt,
      slotIndex: 0,
      kdfTime: header.kdfTime,
      kdfMemKib: header.kdfMem,
      kdfPar: header.kdfPar,
    }),
    deriveSlotKey({
      password,
      outerSalt: header.outerSalt,
      slotIndex: 1,
      kdfTime: header.kdfTime,
      kdfMemKib: header.kdfMem,
      kdfPar: header.kdfPar,
    }),
  ]);

  const attempts = [
    [0, k0, nonce0, ct0],
    [1, k1, nonce1, ct1],
  ];
  let winning = null;
  for (const [idx, key, nonce, ct] of attempts) {
    let frame;
    try {
      frame = await aesGcmDecrypt(key, nonce, ct);
    } catch {
      continue;
    }
    const payload = unframePlaintext(frame);
    if (payload === null) continue;
    if (winning === null) {
      // Clone subarray out of the decrypted buffer so the caller
      // keeps holding valid memory regardless of the inner buffer.
      winning = { slotIndex: idx, payload: new Uint8Array(payload) };
    }
  }
  if (winning === null) {
    throw new WrongPasswordError(
      'No slot decrypted successfully with the supplied password.',
    );
  }
  return winning;
}

// Small helper used by UI code.
export function jsonToBytes(obj) {
  return textEncoder.encode(JSON.stringify(obj));
}

export function bytesToJson(bytes) {
  try {
    return JSON.parse(new TextDecoder().decode(bytes));
  } catch {
    return null;
  }
}

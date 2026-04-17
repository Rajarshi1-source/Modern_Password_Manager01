/**
 * Ultrasonic Pairing Service
 *
 * Client for the /api/ultrasonic/ endpoints plus the Web Crypto
 * ECDH-P256 flow that binds both devices to the same session key.
 *
 * IMPORTANT: Private keys never leave the browser. Only the SEC1
 * uncompressed public key and the HMAC-SHA256(shared, "sas") check
 * code are transmitted.
 */

import api from './api';

const BASE = '/api/ultrasonic';

/* ---- base64 helpers (ArrayBuffer <-> b64) ---- */
export function abToB64(buffer) {
  const bytes = new Uint8Array(buffer);
  let binary = '';
  for (let i = 0; i < bytes.byteLength; i += 1) {
    binary += String.fromCharCode(bytes[i]);
  }
  return btoa(binary);
}

export function b64ToU8(b64) {
  const binary = atob(b64);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i += 1) bytes[i] = binary.charCodeAt(i);
  return bytes;
}

/* ---- ECDH P-256 ---- */

export async function generateEcdhKeyPair() {
  const keyPair = await window.crypto.subtle.generateKey(
    { name: 'ECDH', namedCurve: 'P-256' },
    true,
    ['deriveBits', 'deriveKey'],
  );
  const raw = await window.crypto.subtle.exportKey('raw', keyPair.publicKey);
  return { keyPair, publicKeyB64: abToB64(raw) };
}

export async function importRawEcdhPublicKey(b64) {
  return window.crypto.subtle.importKey(
    'raw',
    b64ToU8(b64).buffer,
    { name: 'ECDH', namedCurve: 'P-256' },
    true,
    [],
  );
}

export async function deriveSharedBits(privateKey, peerPublicKey) {
  const bits = await window.crypto.subtle.deriveBits(
    { name: 'ECDH', public: peerPublicKey },
    privateKey,
    256,
  );
  return new Uint8Array(bits);
}

export async function hmacSasCode(sharedBytes, label = 'sas') {
  const key = await window.crypto.subtle.importKey(
    'raw', sharedBytes, { name: 'HMAC', hash: 'SHA-256' }, false, ['sign'],
  );
  const tag = await window.crypto.subtle.sign(
    'HMAC', key,
    new TextEncoder().encode(label),
  );
  return new Uint8Array(tag);
}

/**
 * Turn an HMAC tag into a short 6-digit numeric SAS the user reads
 * out loud to verify the two devices agree.
 */
export function shortAuthStringFromTag(tagU8) {
  const view = new DataView(tagU8.buffer, tagU8.byteOffset, 4);
  const n = view.getUint32(0, false) % 1_000_000;
  return String(n).padStart(6, '0');
}

/* ---- API surface ---- */

const ultrasonicPairingService = {
  abToB64,
  b64ToU8,
  generateEcdhKeyPair,
  importRawEcdhPublicKey,
  deriveSharedBits,
  hmacSasCode,
  shortAuthStringFromTag,

  initiate: (payload) => api.post(`${BASE}/sessions/`, payload),
  claim: (payload) => api.post(`${BASE}/sessions/claim/`, payload),
  get: (sessionId) => api.get(`${BASE}/sessions/${sessionId}/`),
  confirm: (sessionId, payload) =>
    api.post(`${BASE}/sessions/${sessionId}/confirm/`, payload),
  share: (sessionId, payload) =>
    api.post(`${BASE}/sessions/${sessionId}/share/`, payload),
  delivered: (sessionId) =>
    api.get(`${BASE}/sessions/${sessionId}/delivered/`),
  enrollDevice: (sessionId, payload) =>
    api.post(`${BASE}/sessions/${sessionId}/enroll-device/`, payload),
};

export default ultrasonicPairingService;

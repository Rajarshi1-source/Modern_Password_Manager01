/**
 * WebAuthn base64url <-> ArrayBuffer helpers.
 *
 * The backend encodes the challenge and credential IDs with fido2's
 * `websafe_encode` (base64url: `-`/`_`, no padding) and decodes what the client
 * sends with `websafe_decode`. `window.atob()` only accepts *standard* base64, so
 * it throws `InvalidCharacterError` on the `-`/`_` characters — which broke ~71%
 * of passkey register/authenticate attempts (any challenge whose base64url
 * contained `-`/`_`). These helpers bridge the two encodings for the WebAuthn
 * calls, and are shared so the two auth components can't drift apart again.
 */

/**
 * Decode a base64url (or standard base64) string into an ArrayBuffer.
 * Normalizes `-`/`_` back to `+`/`/` and re-pads before decoding.
 *
 * @param {string} value base64url / base64 string
 * @returns {ArrayBuffer}
 */
export function base64urlToArrayBuffer(value) {
  const normalized = value.replace(/-/g, '+').replace(/_/g, '/');
  const padded = normalized + '='.repeat((4 - (normalized.length % 4)) % 4);
  const binary = atob(padded);
  // Uint8Array.from avoids an indexed write (keeps security/detect-object-injection quiet).
  return Uint8Array.from(binary, (ch) => ch.charCodeAt(0)).buffer;
}

/**
 * Encode an ArrayBuffer as an unpadded base64url string, matching the server's
 * fido2 `websafe_decode` convention (`-`/`_`, no padding).
 *
 * @param {ArrayBuffer} buffer
 * @returns {string} unpadded base64url
 */
export function arrayBufferToBase64url(buffer) {
  const binary = new Uint8Array(buffer).reduce(
    (acc, byte) => acc + String.fromCharCode(byte),
    ''
  );
  return btoa(binary)
    .replace(/\+/g, '-')
    .replace(/\//g, '_')
    .replace(/=+$/, '');
}

/**
 * Regression tests for the WebAuthn base64url helpers.
 *
 * The bug: the server encodes the challenge / credential IDs with fido2
 * websafe_encode (base64url), but the frontend decoded them with window.atob
 * (standard base64), which throws InvalidCharacterError on `-`/`_`. ~71% of
 * passkey register/authenticate attempts failed. These tests pin the fix.
 */
import { describe, it, expect } from 'vitest';
import { base64urlToArrayBuffer, arrayBufferToBase64url } from '../webauthnBase64';

const toBytes = (buffer) => Array.from(new Uint8Array(buffer));

describe('webauthnBase64', () => {
  it('decodes a base64url string containing - and _ (window.atob used to throw here)', () => {
    // bytes [0xfb,0xff,0xbf,0x3e,0x00] -> fido2 websafe_encode -> "-_-_PgA"
    expect(() => base64urlToArrayBuffer('-_-_PgA')).not.toThrow();
    expect(toBytes(base64urlToArrayBuffer('-_-_PgA'))).toEqual([0xfb, 0xff, 0xbf, 0x3e, 0x00]);
  });

  it('emits unpadded base64url (- and _, never + / =)', () => {
    // [0xfb,0xff,0xbf] -> standard base64 "+/+/" -> base64url "-_-_"
    const encoded = arrayBufferToBase64url(new Uint8Array([0xfb, 0xff, 0xbf]).buffer);
    expect(encoded).toBe('-_-_');
    expect(encoded).not.toMatch(/[+/=]/);
  });

  it('round-trips ArrayBuffer -> base64url -> ArrayBuffer', () => {
    const original = new Uint8Array([0xfb, 0xff, 0xbf, 0x3e, 0x00, 0x10, 0x2a]);
    const encoded = arrayBufferToBase64url(original.buffer);
    expect(encoded).not.toMatch(/[+/=]/);
    expect(toBytes(base64urlToArrayBuffer(encoded))).toEqual(Array.from(original));
  });

  it('still accepts standard base64 input (backward compatible)', () => {
    // "+/+/" (standard base64) decodes to the same [0xfb,0xff,0xbf]
    expect(toBytes(base64urlToArrayBuffer('+/+/'))).toEqual([0xfb, 0xff, 0xbf]);
  });
});

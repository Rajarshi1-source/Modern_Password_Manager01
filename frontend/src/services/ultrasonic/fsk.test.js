/**
 * FSK codec round-trip tests.
 *
 * Pure-math portion (encode -> decode) is exercised on synthetic PCM
 * at 48 kHz so we don't depend on OfflineAudioContext quirks across
 * jsdom / happy-dom / real browsers.
 */

import { describe, it, expect } from 'vitest';
import {
  buildFrameBits,
  encodeFrameToPcm,
  decodeFrameFromPcm,
  crc16Ccitt,
  bytesToBits,
  bitsToBytes,
} from './fsk';

describe('crc16Ccitt', () => {
  it('matches a known reference value for the empty/short cases', () => {
    expect(crc16Ccitt(new Uint8Array([]))).toBe(0xffff);
    // "123456789" CCITT-FALSE reference = 0x29B1
    const ref = new TextEncoder().encode('123456789');
    expect(crc16Ccitt(ref)).toBe(0x29b1);
  });
});

describe('bit/byte roundtrip', () => {
  it('round-trips arbitrary payloads', () => {
    const payload = new Uint8Array([0xde, 0xad, 0xbe, 0xef, 0x00, 0xff]);
    const bits = bytesToBits(payload);
    expect(bits.length).toBe(48);
    const back = bitsToBytes(bits);
    expect(Array.from(back)).toEqual(Array.from(payload));
  });
});

describe('FSK PCM round-trip', () => {
  it('decodes a 6-byte nonce back to its bytes over synthetic PCM', () => {
    const payload = new Uint8Array([0x12, 0x34, 0x56, 0x78, 0x9a, 0xbc]);
    const bits = buildFrameBits(payload);
    const sampleRate = 48000;
    const pcm = encodeFrameToPcm(bits, sampleRate);
    // Pad with silence to simulate a slightly-late mic start.
    const lead = Math.floor(sampleRate * 0.1);
    const padded = new Float32Array(pcm.length + lead);
    padded.set(pcm, lead);

    const decoded = decodeFrameFromPcm(padded, sampleRate, payload.length * 8);
    expect(decoded).not.toBeNull();
    expect(decoded.crcOk).toBe(true);
    expect(Array.from(decoded.payload)).toEqual(Array.from(payload));
  });

  it('survives moderate additive white noise', () => {
    const payload = new Uint8Array([0x01, 0x02, 0x03, 0x04, 0x05, 0x06]);
    const bits = buildFrameBits(payload);
    const sampleRate = 48000;
    const pcm = encodeFrameToPcm(bits, sampleRate);
    const noisy = new Float32Array(pcm.length);
    for (let i = 0; i < pcm.length; i += 1) {
      noisy[i] = pcm[i] + (Math.random() - 0.5) * 0.05;
    }
    const decoded = decodeFrameFromPcm(noisy, sampleRate, payload.length * 8);
    expect(decoded).not.toBeNull();
    expect(Array.from(decoded.payload)).toEqual(Array.from(payload));
  });
});

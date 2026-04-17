/**
 * Ultrasonic FSK (Frequency-Shift Keying) codec.
 *
 * Encodes a short payload (nonce) into an inaudible audio bitstream by
 * switching between two tones:
 *
 *   f0 = 18500 Hz  (bit = 0)
 *   f1 = 19500 Hz  (bit = 1)
 *
 * Each bit is emitted for ``SYMBOL_DURATION_S`` seconds. A 16-bit
 * preamble (0xAAAA = alternating 1/0) is prepended so the receiver can
 * lock the symbol clock, and a CRC-16 is appended for integrity.
 *
 * The codec is deliberately tiny — no modulation, no error-correction
 * codes, no dynamic symbol rate. It only needs to carry a 6-byte nonce
 * a few metres through open air once per pairing.
 */

export const FSK_F0 = 18500;
export const FSK_F1 = 19500;
export const SYMBOL_DURATION_S = 0.05; // 50 ms per bit
export const PREAMBLE_BITS = [
  1, 0, 1, 0, 1, 0, 1, 0, 1, 0, 1, 0, 1, 0, 1, 0,
];

/**
 * CRC-16/CCITT-FALSE — short, simple, catches single-bit flips.
 * Not meant as a MAC, only as an integrity check against FSK errors.
 */
export function crc16Ccitt(bytes) {
  let crc = 0xffff;
  for (let i = 0; i < bytes.length; i += 1) {
    crc ^= (bytes[i] & 0xff) << 8;
    for (let j = 0; j < 8; j += 1) {
      if (crc & 0x8000) {
        crc = ((crc << 1) ^ 0x1021) & 0xffff;
      } else {
        crc = (crc << 1) & 0xffff;
      }
    }
  }
  return crc & 0xffff;
}

/** Convert a Uint8Array to an array of single-bit MSB-first. */
export function bytesToBits(bytes) {
  const bits = [];
  for (let i = 0; i < bytes.length; i += 1) {
    for (let b = 7; b >= 0; b -= 1) {
      bits.push((bytes[i] >> b) & 1);
    }
  }
  return bits;
}

/** Inverse of ``bytesToBits``. */
export function bitsToBytes(bits) {
  const byteLen = Math.floor(bits.length / 8);
  const out = new Uint8Array(byteLen);
  for (let i = 0; i < byteLen; i += 1) {
    let byte = 0;
    for (let b = 0; b < 8; b += 1) {
      byte = (byte << 1) | (bits[i * 8 + b] & 1);
    }
    out[i] = byte;
  }
  return out;
}

/**
 * Build the full bit stream for a payload:
 *   [preamble | payload | CRC16(payload)]
 */
export function buildFrameBits(payload) {
  const crc = crc16Ccitt(payload);
  const withCrc = new Uint8Array(payload.length + 2);
  withCrc.set(payload, 0);
  withCrc[payload.length] = (crc >> 8) & 0xff;
  withCrc[payload.length + 1] = crc & 0xff;
  return [...PREAMBLE_BITS, ...bytesToBits(withCrc)];
}

/**
 * Render a frame into a PCM Float32Array at ``sampleRate`` Hz.
 * A short raised-cosine fade is applied at the start/end of each
 * symbol to suppress audible clicks at the boundary.
 */
export function encodeFrameToPcm(bits, sampleRate = 48000) {
  const samplesPerSymbol = Math.round(sampleRate * SYMBOL_DURATION_S);
  const total = bits.length * samplesPerSymbol;
  const out = new Float32Array(total);
  const rampSamples = Math.min(64, Math.floor(samplesPerSymbol * 0.1));

  for (let i = 0; i < bits.length; i += 1) {
    const freq = bits[i] === 1 ? FSK_F1 : FSK_F0;
    const base = i * samplesPerSymbol;
    for (let s = 0; s < samplesPerSymbol; s += 1) {
      const t = (base + s) / sampleRate;
      let gain = 0.5;
      if (s < rampSamples) {
        gain *= 0.5 - 0.5 * Math.cos((Math.PI * s) / rampSamples);
      } else if (s > samplesPerSymbol - rampSamples) {
        const d = samplesPerSymbol - s;
        gain *= 0.5 - 0.5 * Math.cos((Math.PI * d) / rampSamples);
      }
      out[base + s] = gain * Math.sin(2 * Math.PI * freq * t);
    }
  }
  return out;
}

/**
 * Goertzel-filter bin power at ``targetFreq`` over ``samples``.
 * Goertzel is O(N) per bin and far cheaper than a full FFT when we
 * only care about two frequencies.
 */
export function goertzelPower(samples, sampleRate, targetFreq) {
  const N = samples.length;
  const k = Math.round((N * targetFreq) / sampleRate);
  const omega = (2 * Math.PI * k) / N;
  const coeff = 2 * Math.cos(omega);
  let sPrev = 0;
  let sPrev2 = 0;
  for (let n = 0; n < N; n += 1) {
    const s = samples[n] + coeff * sPrev - sPrev2;
    sPrev2 = sPrev;
    sPrev = s;
  }
  return sPrev2 * sPrev2 + sPrev * sPrev - coeff * sPrev * sPrev2;
}

/**
 * Decode PCM Float32Array into a best-guess Uint8Array payload.
 *
 * Returns ``{payload, crcOk}`` or ``null`` if the preamble cannot be
 * located. The decoder does a sliding-window preamble search at
 * quarter-symbol resolution so the caller doesn't need sample-accurate
 * timing.
 */
export function decodeFrameFromPcm(samples, sampleRate, payloadBitLen) {
  const samplesPerSymbol = Math.round(sampleRate * SYMBOL_DURATION_S);
  const totalBits = PREAMBLE_BITS.length + payloadBitLen + 16;
  const need = totalBits * samplesPerSymbol;
  if (samples.length < need + samplesPerSymbol) return null;

  const step = Math.max(1, Math.floor(samplesPerSymbol / 4));
  let bestOffset = -1;
  let bestScore = -Infinity;

  for (let off = 0; off + need <= samples.length; off += step) {
    let score = 0;
    for (let i = 0; i < PREAMBLE_BITS.length; i += 1) {
      const start = off + i * samplesPerSymbol;
      const win = samples.subarray(start, start + samplesPerSymbol);
      const p0 = goertzelPower(win, sampleRate, FSK_F0);
      const p1 = goertzelPower(win, sampleRate, FSK_F1);
      const bit = p1 > p0 ? 1 : 0;
      if (bit === PREAMBLE_BITS[i]) score += Math.log1p(Math.max(p0, p1));
      else score -= Math.log1p(Math.max(p0, p1));
    }
    if (score > bestScore) {
      bestScore = score;
      bestOffset = off;
    }
  }

  if (bestOffset < 0 || bestScore <= 0) return null;

  const bits = new Array(payloadBitLen + 16);
  for (let i = 0; i < bits.length; i += 1) {
    const start = bestOffset + (PREAMBLE_BITS.length + i) * samplesPerSymbol;
    const win = samples.subarray(start, start + samplesPerSymbol);
    const p0 = goertzelPower(win, sampleRate, FSK_F0);
    const p1 = goertzelPower(win, sampleRate, FSK_F1);
    bits[i] = p1 > p0 ? 1 : 0;
  }

  const full = bitsToBytes(bits);
  if (full.length < 2) return null;
  const payload = full.slice(0, full.length - 2);
  const crcRx = (full[full.length - 2] << 8) | full[full.length - 1];
  const crcOk = crcRx === crc16Ccitt(payload);
  return { payload, crcOk, offset: bestOffset, score: bestScore };
}

export default {
  FSK_F0,
  FSK_F1,
  SYMBOL_DURATION_S,
  PREAMBLE_BITS,
  crc16Ccitt,
  bytesToBits,
  bitsToBytes,
  buildFrameBits,
  encodeFrameToPcm,
  decodeFrameFromPcm,
  goertzelPower,
};

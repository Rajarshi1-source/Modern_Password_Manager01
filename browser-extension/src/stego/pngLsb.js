/**
 * PNG LSB steganography - browser implementation.
 *
 * Byte-compatible with :mod:`stegano_vault.services.png_lsb_service`:
 * the same pseudo-random pixel permutation (SHA-256 counter DRBG seeded
 * with "png-lsb/v1|" + stegoKey), the same 3 bits/pixel scheme
 * (R/G/B LSBs, alpha untouched), and the same 4-byte LE length header.
 *
 * Unlike the Python side this implementation goes through the
 * browser ``<canvas>`` and does not re-optimise the PNG stream
 * afterwards. That's fine because our decoder works on the decoded
 * pixel data, not the compressed IDAT stream.
 */

const PNG_SIGNATURE = new Uint8Array([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]);
const HEADER_LEN = 4;
const BITS_PER_PIXEL = 3;

export class PngLsbError extends Error {}
export class NotAPngError extends PngLsbError {}
export class CoverTooSmallError extends PngLsbError {}

function assertIsPng(bytes) {
  if (bytes.length < 8) throw new NotAPngError('Too short to be a PNG.');
  for (let i = 0; i < 8; i += 1) {
    if (bytes[i] !== PNG_SIGNATURE[i]) {
      throw new NotAPngError(
        'Input bytes are not a PNG file. Lossy formats like JPEG ' +
          'would destroy the hidden payload and are refused.',
      );
    }
  }
}

// ---------------------------------------------------------------------------
// SHA-256 DRBG + Fisher-Yates permutation (matches Python)
// ---------------------------------------------------------------------------

async function sha256(bytes) {
  const buf = await window.crypto.subtle.digest('SHA-256', bytes);
  return new Uint8Array(buf);
}

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

function counterBytesLE(n) {
  const b = new Uint8Array(8);
  const dv = new DataView(b.buffer);
  // JS numbers safely represent up to 2^53, which is plenty for our counters.
  dv.setBigUint64(0, BigInt(n), true);
  return b;
}

async function permutation(numPixels, stegoKey) {
  const seedInput = concatBytes(new TextEncoder().encode('png-lsb/v1|'), stegoKey);
  const state = await sha256(seedInput);
  let counter = 0;

  async function randU32() {
    const blk = await sha256(concatBytes(state, counterBytesLE(counter)));
    counter += 1;
    return new DataView(blk.buffer, blk.byteOffset, 4).getUint32(0, true);
  }

  const out = new Uint32Array(numPixels);
  for (let i = 0; i < numPixels; i += 1) out[i] = i;
  for (let i = numPixels - 1; i > 0; i -= 1) {
    // eslint-disable-next-line no-await-in-loop
    const r = await randU32();
    const j = r % (i + 1);
    const tmp = out[i];
    out[i] = out[j];
    out[j] = tmp;
  }
  return out;
}

// ---------------------------------------------------------------------------
// Canvas helpers
// ---------------------------------------------------------------------------

async function bytesToImageData(coverBytes) {
  const blob = new Blob([coverBytes], { type: 'image/png' });
  const url = URL.createObjectURL(blob);
  try {
    const img = await new Promise((resolve, reject) => {
      const el = new Image();
      el.onload = () => resolve(el);
      el.onerror = reject;
      el.src = url;
    });
    const canvas = document.createElement('canvas');
    canvas.width = img.naturalWidth;
    canvas.height = img.naturalHeight;
    const ctx = canvas.getContext('2d');
    ctx.drawImage(img, 0, 0);
    return {
      imageData: ctx.getImageData(0, 0, canvas.width, canvas.height),
      canvas,
      ctx,
      width: canvas.width,
      height: canvas.height,
    };
  } finally {
    URL.revokeObjectURL(url);
  }
}

function canvasToPngBytes(canvas) {
  return new Promise((resolve, reject) => {
    canvas.toBlob(
      (blob) => {
        if (!blob) {
          reject(new PngLsbError('canvas.toBlob returned null'));
          return;
        }
        const fr = new FileReader();
        fr.onload = () => resolve(new Uint8Array(fr.result));
        fr.onerror = () => reject(new PngLsbError('FileReader failed'));
        fr.readAsArrayBuffer(blob);
      },
      'image/png',
    );
  });
}

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

function packBits(data) {
  const bits = new Uint8Array(data.length * 8);
  for (let i = 0; i < data.length; i += 1) {
    const byte = data[i];
    for (let b = 0; b < 8; b += 1) {
      bits[i * 8 + b] = (byte >> (7 - b)) & 0x1;
    }
  }
  return bits;
}

function unpackBits(bits) {
  if (bits.length % 8 !== 0) {
    throw new PngLsbError('bit stream length not a multiple of 8');
  }
  const out = new Uint8Array(bits.length / 8);
  for (let i = 0; i < bits.length; i += 1) {
    out[i >> 3] |= (bits[i] & 0x1) << (7 - (i % 8));
  }
  return out;
}

export async function pngCapacityBytes(coverBytes) {
  assertIsPng(coverBytes);
  const { width, height } = await bytesToImageData(coverBytes);
  return Math.max(0, Math.floor((width * height * BITS_PER_PIXEL) / 8) - HEADER_LEN);
}

export async function embedBlobInPng(coverBytes, blob, { stegoKey = new TextEncoder().encode('default-png-lsb-key') } = {}) {
  assertIsPng(coverBytes);
  if (!(blob instanceof Uint8Array)) throw new TypeError('blob must be Uint8Array');
  const { imageData, canvas, ctx, width, height } = await bytesToImageData(coverBytes);
  const numPixels = width * height;
  const capacity = Math.floor((numPixels * BITS_PER_PIXEL) / 8) - HEADER_LEN;
  if (blob.length > capacity) {
    throw new CoverTooSmallError(
      `Cover too small: need ${blob.length + HEADER_LEN} bytes of capacity, have ${capacity + HEADER_LEN}.`,
    );
  }

  const header = new Uint8Array(HEADER_LEN);
  new DataView(header.buffer).setUint32(0, blob.length >>> 0, true);
  const bits = packBits(concatBytes(header, blob));

  const order = await permutation(numPixels, stegoKey instanceof Uint8Array ? stegoKey : new TextEncoder().encode(String(stegoKey)));
  const data = imageData.data; // RGBA, length = numPixels * 4

  let bitIdx = 0;
  for (let orderIdx = 0; orderIdx < numPixels && bitIdx < bits.length; orderIdx += 1) {
    const pixelIdx = order[orderIdx];
    const base = pixelIdx * 4;
    if (bitIdx < bits.length) { data[base]     = (data[base]     & 0xfe) | bits[bitIdx++]; }
    if (bitIdx < bits.length) { data[base + 1] = (data[base + 1] & 0xfe) | bits[bitIdx++]; }
    if (bitIdx < bits.length) { data[base + 2] = (data[base + 2] & 0xfe) | bits[bitIdx++]; }
  }
  ctx.putImageData(imageData, 0, 0);
  return canvasToPngBytes(canvas);
}

export async function extractBlobFromPng(
  stegoBytes,
  { stegoKey = new TextEncoder().encode('default-png-lsb-key'), maxBlobBytes = 2 * 1024 * 1024 } = {},
) {
  assertIsPng(stegoBytes);
  const { imageData, width, height } = await bytesToImageData(stegoBytes);
  const numPixels = width * height;
  const order = await permutation(numPixels, stegoKey instanceof Uint8Array ? stegoKey : new TextEncoder().encode(String(stegoKey)));
  const data = imageData.data;

  const readBit = (bitIdx) => {
    const pixelCursor = Math.floor(bitIdx / BITS_PER_PIXEL);
    const channelCursor = bitIdx % BITS_PER_PIXEL;
    if (pixelCursor >= numPixels) {
      throw new PngLsbError('Ran out of cover while reading LSBs');
    }
    const base = order[pixelCursor] * 4;
    return data[base + channelCursor] & 0x1;
  };

  const headerBits = new Uint8Array(HEADER_LEN * 8);
  for (let i = 0; i < headerBits.length; i += 1) headerBits[i] = readBit(i);
  const headerBytes = unpackBits(headerBits);
  const length = new DataView(headerBytes.buffer).getUint32(0, true);
  const capacityBytes = Math.floor((numPixels * BITS_PER_PIXEL) / 8) - HEADER_LEN;
  if (length === 0 || length > maxBlobBytes || length > capacityBytes) {
    throw new PngLsbError(
      `Invalid embedded length ${length} (capacity ${capacityBytes}, max allowed ${maxBlobBytes}).`,
    );
  }
  const payloadBits = new Uint8Array(length * 8);
  for (let i = 0; i < payloadBits.length; i += 1) payloadBits[i] = readBit(HEADER_LEN * 8 + i);
  return unpackBits(payloadBits);
}

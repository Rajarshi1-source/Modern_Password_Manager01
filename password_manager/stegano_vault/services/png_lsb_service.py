"""
PNG LSB embed / extract service.

The blob is already opaque (encrypted client-side by the
``hidden_vault`` primitive), so this layer only cares about moving
bytes into and out of pixel data losslessly.

Design
------

* Use Pillow to decode PNG into an ``RGBA`` array.
* Use 3 bits / pixel (one LSB in each of R, G, B - leave A alone so
  transparency-aware renderers don't fiddle with it).
* Pixel write-order is a pseudo-random permutation keyed by a
  deterministic stego key derived from the blob header magic. This
  defeats trivial "scan the first N LSBs" steganalysis.
* A 4-byte length header ``LEN(uint32 LE)`` is written first, so the
  extractor knows exactly how many bytes to read back.
* Only lossless input / output formats are accepted. JPEG input /
  output is rejected explicitly because JPEG re-encoding would
  destroy the LSB payload.
"""

from __future__ import annotations

import hashlib
import io
import struct
from typing import Tuple

try:
    from PIL import Image
except Exception as exc:  # pragma: no cover
    raise RuntimeError(
        "stegano_vault.services.png_lsb_service requires Pillow. "
        "Install with 'pip install Pillow'."
    ) from exc


PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
HEADER_LEN = 4          # uint32 LE: length of embedded blob in bytes
BITS_PER_PIXEL = 3      # we use R, G, B LSBs; alpha is untouched


class PngLsbError(Exception):
    """Base error for PNG LSB service."""


class NotAPngError(PngLsbError):
    """Input was not a PNG (or is a lossy JPEG)."""


class CoverTooSmallError(PngLsbError):
    """Cover image does not have enough pixels for the blob."""


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _assert_is_png(data: bytes) -> None:
    if not data[:8] == PNG_SIGNATURE:
        raise NotAPngError(
            "Input bytes are not a PNG file. Lossy formats like JPEG "
            "would destroy the hidden payload and are refused."
        )


def _permutation(num_pixels: int, stego_key: bytes) -> list[int]:
    """
    Return a permutation of ``range(num_pixels)`` driven by
    ``stego_key``. Not cryptographically strong - this is only a
    steganalysis-resistance measure, not a privacy boundary. The
    plaintext is already AES-GCM encrypted upstream.
    """
    # Simple seeded Fisher-Yates with a SHA-256 DRBG.
    seed = hashlib.sha256(b"png-lsb/v1|" + stego_key).digest()
    state = seed
    counter = 0
    out = list(range(num_pixels))

    def _rand_u32() -> int:
        nonlocal state, counter
        block = hashlib.sha256(state + counter.to_bytes(8, "little")).digest()
        counter += 1
        return int.from_bytes(block[:4], "little")

    for i in range(num_pixels - 1, 0, -1):
        j = _rand_u32() % (i + 1)
        out[i], out[j] = out[j], out[i]
    return out


def _pack_bits(data: bytes) -> list[int]:
    """Expand bytes to a list of bits, MSB first per byte."""
    bits = []
    for byte in data:
        for shift in range(7, -1, -1):
            bits.append((byte >> shift) & 0x1)
    return bits


def _unpack_bits(bits: list[int]) -> bytes:
    """Inverse of :func:`_pack_bits`."""
    if len(bits) % 8 != 0:
        raise PngLsbError("bit stream length not a multiple of 8")
    out = bytearray(len(bits) // 8)
    for i, bit in enumerate(bits):
        out[i // 8] |= (bit & 0x1) << (7 - (i % 8))
    return bytes(out)


def png_capacity_bytes(cover_bytes: bytes) -> int:
    """
    Return how many payload bytes (excluding the 4-byte LEN header)
    can be hidden in ``cover_bytes`` at 3 bits/pixel.
    """
    _assert_is_png(cover_bytes)
    img = Image.open(io.BytesIO(cover_bytes))
    width, height = img.size
    total_bits = width * height * BITS_PER_PIXEL
    return max(0, total_bits // 8 - HEADER_LEN)


def compute_cover_hash(cover_bytes: bytes) -> str:
    """SHA-256 hex of the raw cover bytes (used for later re-encoding detection)."""
    return hashlib.sha256(cover_bytes).hexdigest()


# ---------------------------------------------------------------------------
# public API
# ---------------------------------------------------------------------------


def embed_blob_in_png(
    cover_bytes: bytes,
    blob: bytes,
    *,
    stego_key: bytes = b"default-png-lsb-key",
) -> bytes:
    """
    Return PNG bytes with ``blob`` LSB-embedded in the cover image's
    RGB channels using a keyed pixel permutation.

    Caller-visible contract:

    * Input cover must be PNG (NotAPngError otherwise).
    * If capacity is insufficient, raise CoverTooSmallError.
    * Output is a new PNG (lossless) - never a JPEG.
    """
    _assert_is_png(cover_bytes)
    if not isinstance(blob, (bytes, bytearray)):
        raise TypeError("blob must be bytes")

    img = Image.open(io.BytesIO(cover_bytes)).convert("RGBA")
    width, height = img.size
    num_pixels = width * height

    capacity = num_pixels * BITS_PER_PIXEL // 8 - HEADER_LEN
    if len(blob) > capacity:
        raise CoverTooSmallError(
            f"Cover too small: need {len(blob) + HEADER_LEN} bytes of "
            f"capacity, have {capacity + HEADER_LEN}."
        )

    header = struct.pack("<I", len(blob))
    bits = _pack_bits(header + bytes(blob))

    order = _permutation(num_pixels, stego_key)
    pixels = list(img.getdata())  # list of (r, g, b, a)

    bit_idx = 0
    for pixel_idx in order:
        if bit_idx >= len(bits):
            break
        r, g, b, a = pixels[pixel_idx]
        if bit_idx < len(bits):
            r = (r & ~1) | bits[bit_idx]; bit_idx += 1
        if bit_idx < len(bits):
            g = (g & ~1) | bits[bit_idx]; bit_idx += 1
        if bit_idx < len(bits):
            b = (b & ~1) | bits[bit_idx]; bit_idx += 1
        pixels[pixel_idx] = (r, g, b, a)

    img.putdata(pixels)
    buf = io.BytesIO()
    # Force PNG, optimize off so bytes are deterministic given input +
    # blob (the PNG filter heuristics Pillow picks are stable).
    img.save(buf, format="PNG", optimize=False)
    return buf.getvalue()


def extract_blob_from_png(
    stego_bytes: bytes,
    *,
    stego_key: bytes = b"default-png-lsb-key",
    max_blob_bytes: int = 2 * 1024 * 1024,
) -> bytes:
    """
    Inverse of :func:`embed_blob_in_png`.

    Reads the 4-byte length header first, then the blob bytes, both
    from the same keyed permutation of pixel LSBs. Raises PngLsbError
    if the length header is insane (> ``max_blob_bytes`` or > pixel
    capacity).
    """
    _assert_is_png(stego_bytes)
    img = Image.open(io.BytesIO(stego_bytes)).convert("RGBA")
    width, height = img.size
    num_pixels = width * height
    pixels = list(img.getdata())
    order = _permutation(num_pixels, stego_key)

    def _read_bits(n_bits: int, start_bit: int) -> Tuple[list[int], int]:
        bits_out: list[int] = []
        bi = start_bit
        # pixel progress is bi // 3, channel is bi % 3
        while len(bits_out) < n_bits:
            pixel_cursor = bi // BITS_PER_PIXEL
            channel_cursor = bi % BITS_PER_PIXEL
            if pixel_cursor >= num_pixels:
                raise PngLsbError("Ran out of cover while reading LSBs")
            px = pixels[order[pixel_cursor]]
            bits_out.append(px[channel_cursor] & 0x1)
            bi += 1
        return bits_out, bi

    header_bits, cursor = _read_bits(HEADER_LEN * 8, 0)
    header_bytes = _unpack_bits(header_bits)
    (length,) = struct.unpack("<I", header_bytes)
    capacity_bytes = num_pixels * BITS_PER_PIXEL // 8 - HEADER_LEN
    if length == 0 or length > max_blob_bytes or length > capacity_bytes:
        raise PngLsbError(
            f"Invalid embedded length {length} (capacity {capacity_bytes}, "
            f"max allowed {max_blob_bytes})."
        )
    payload_bits, _ = _read_bits(length * 8, cursor)
    return _unpack_bits(payload_bits)

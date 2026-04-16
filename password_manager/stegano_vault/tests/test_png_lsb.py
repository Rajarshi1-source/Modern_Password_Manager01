"""
Unit tests for :mod:`stegano_vault.services.png_lsb_service`.

Covers:
  * Round-trip of an arbitrary binary blob through a small synthetic
    PNG cover with the keyed pixel permutation.
  * Rejection of lossy formats (JPEG bytes).
  * Capacity calculation honouring the 4-byte length header.
  * Determinism: embedding with the same stego_key twice produces
    identical output.
"""

from __future__ import annotations

import io

import pytest
from PIL import Image

from stegano_vault.services import png_lsb_service as svc


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_cover(width: int = 64, height: int = 64) -> bytes:
    """Return raw PNG bytes of a deterministic RGBA cover image."""
    img = Image.new("RGBA", (width, height))
    pixels = []
    for y in range(height):
        for x in range(width):
            pixels.append(((x * 7) % 256, (y * 11) % 256, ((x + y) * 3) % 256, 255))
    img.putdata(pixels)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_roundtrip_small_blob():
    cover = _make_cover()
    blob = bytes(range(200))
    stego = svc.embed_blob_in_png(cover, blob)
    recovered = svc.extract_blob_from_png(stego)
    assert recovered == blob


def test_roundtrip_empty_blob_rejected():
    """Zero-length embedding is meaningless and should error at extract."""
    cover = _make_cover()
    with pytest.raises(svc.PngLsbError):
        # We specifically disallow length=0 via the extractor guard.
        # The embedder will still accept it, but extraction checks.
        svc.extract_blob_from_png(
            svc.embed_blob_in_png(cover, b"")
        )


def test_stego_key_affects_permutation():
    cover = _make_cover()
    blob = b"\x01\x02\x03\x04\x05" * 20
    a = svc.embed_blob_in_png(cover, blob, stego_key=b"key-a")
    b = svc.embed_blob_in_png(cover, blob, stego_key=b"key-b")
    assert a != b  # different orderings should change the bit placement
    # And each should only decode with the matching key.
    assert svc.extract_blob_from_png(a, stego_key=b"key-a") == blob
    assert svc.extract_blob_from_png(b, stego_key=b"key-b") == blob


def test_deterministic_with_same_key():
    cover = _make_cover()
    blob = b"stego-payload-bytes"
    a = svc.embed_blob_in_png(cover, blob, stego_key=b"deterministic")
    b = svc.embed_blob_in_png(cover, blob, stego_key=b"deterministic")
    assert a == b


def test_lossy_input_rejected():
    # Crafted JPEG SOI + EOI — enough to be recognised as JPEG by the
    # PIL-opening path (which the service refuses).
    jpeg_bytes = bytes.fromhex("ffd8ffe000104a46494600010100000100010000ffd9")
    with pytest.raises(svc.PngLsbError):
        svc.embed_blob_in_png(jpeg_bytes, b"payload")


def test_capacity_bytes():
    cover = _make_cover(32, 32)
    cap = svc.png_capacity_bytes(cover)
    # 32*32 pixels * 3 bits / 8 - 4 (length header) = 384 - 4 = 380
    assert cap == 380


def test_blob_too_big():
    cover = _make_cover(16, 16)
    cap = svc.png_capacity_bytes(cover)
    too_big = b"\x55" * (cap + 1)
    with pytest.raises(svc.PngLsbError):
        svc.embed_blob_in_png(cover, too_big)


def test_compute_cover_hash_is_deterministic():
    cover = _make_cover(8, 8)
    assert svc.compute_cover_hash(cover) == svc.compute_cover_hash(cover)
    assert len(svc.compute_cover_hash(cover)) == 64  # hex sha256

"""
Frame Decoding Helpers
=======================

Shared by the REST and WebSocket liveness paths so both decode client frames
identically and reject the same malformed input.
"""

import base64
from typing import Optional, Tuple

import numpy as np
from django.conf import settings

# Upper bound on a decoded frame, as a pixel count. Liveness frames come from a
# webcam canvas, so 1080p is already generous; the cap exists to stop a client
# forcing a huge allocation rather than to constrain real capture.
DEFAULT_MAX_FRAME_PIXELS = 1920 * 1080


def _max_frame_pixels() -> int:
    return getattr(settings, 'BIOMETRIC_LIVENESS', {}).get(
        'MAX_FRAME_PIXELS', DEFAULT_MAX_FRAME_PIXELS
    )


def decode_frame(
    frame_b64: str, width: int, height: int
) -> Tuple[Optional[np.ndarray], Optional[str]]:
    """
    Decode a base64 raw-pixel frame and reshape it to HxWxC, dropping alpha.

    Dimensions are required: a flat 1-D array yields no usable signal, and there
    is no safe default resolution -- a wrong guess just corrupts the reshape.

    Returns (frame, None) on success, or (None, message) where message is a
    client-safe literal. Errors are returned rather than raised so neither
    transport ever echoes exception text back to the client.
    """
    if width <= 0 or height <= 0:
        return None, 'Missing or invalid frame dimensions'
    if width * height > _max_frame_pixels():
        return None, 'Frame dimensions exceed maximum'

    # A non-string/bytes JSON value (number, list, object) is a client error, not
    # a 500 -- and len() below must not raise on it either.
    if not isinstance(frame_b64, (str, bytes)):
        return None, 'Invalid frame encoding'
    # Reject an oversized payload BEFORE b64decode allocates it. The largest
    # legitimate frame is RGBA (4 bytes/px) and base64 expands 3 bytes -> 4
    # chars; without this, the WS path (which has no message-size bound) lets a
    # client force an arbitrarily large decode.
    if len(frame_b64) > ((width * height * 4 + 2) // 3) * 4 + 4:
        return None, 'Frame payload too large'

    try:
        # binascii.Error subclasses ValueError, so this covers malformed base64;
        # TypeError is belt-and-braces for anything isinstance let through.
        frame_bytes = base64.b64decode(frame_b64, validate=True)
    except (ValueError, TypeError):
        return None, 'Invalid frame encoding'

    frame = np.frombuffer(frame_bytes, dtype=np.uint8)
    try:
        # .copy() so the RGB path returns a writable, C-contiguous array,
        # consistent with the RGBA branch below (np.frombuffer yields a read-only
        # buffer, and native vision detectors may preprocess the frame in place).
        return frame.reshape((height, width, 3)).copy(), None
    except ValueError:
        pass
    try:
        # Materialize the alpha-dropped RGB as a C-contiguous array: the sliced
        # view is non-contiguous, which native vision detectors may reject or
        # silently copy.
        return np.ascontiguousarray(frame.reshape((height, width, 4))[:, :, :3]), None
    except ValueError:
        return None, 'Frame dimensions do not match data'

"""
Frame Decoding Helpers
=======================

Shared by the REST and WebSocket liveness paths so both decode client frames
identically and reject the same malformed input.
"""

import base64
from typing import Optional, Tuple

import numpy as np


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

    try:
        # binascii.Error subclasses ValueError, so this covers malformed base64.
        frame_bytes = base64.b64decode(frame_b64, validate=True)
    except ValueError:
        return None, 'Invalid frame encoding'

    frame = np.frombuffer(frame_bytes, dtype=np.uint8)
    try:
        return frame.reshape((height, width, 3)), None
    except ValueError:
        pass
    try:
        return frame.reshape((height, width, 4))[:, :, :3], None
    except ValueError:
        return None, 'Frame dimensions do not match data'

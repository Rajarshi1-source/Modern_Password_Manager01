"""
Shared MediaPipe Tasks FaceLandmarker
======================================

Process-wide loader for the MediaPipe Tasks ``FaceLandmarker`` (the supported
replacement for the legacy ``mediapipe.python.solutions`` FaceMesh, which is
absent from current mediapipe wheels). One detector instance powers BOTH the
real gaze estimator (iris landmarks 468-477) and the real action-unit geometry
(facial landmarks + blendshapes).

Capability-gated: the landmarker loads ONLY when the ``face_landmarker.task``
model asset is configured (``BIOMETRIC_LIVENESS['FACE_LANDMARKER_MODEL']`` /
env ``LIVENESS_FACE_LANDMARKER_MODEL``) and actually present on disk. Without
it, ``get_face_landmarker()`` returns None and every landmark-based modality
stays unavailable and excluded from scoring -- never a fabricated signal.

Threading: the load is guarded by a double-checked lock, and after ONE failed
attempt the fast path returns without taking the lock -- so a permanently
absent model cannot serialize every frame on lock acquisition (the round-29
constraint: the lock must land WITH the real load so the fast path
short-circuits). Consequence: provisioning the model file requires a process
restart, the standard contract for process-wide ML resources. A single Tasks
detector is not thread-safe, so inference itself is serialized by its own lock.
"""

import logging
import os
import threading
from typing import Dict, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)

_LOAD_LOCK = threading.Lock()
_DETECT_LOCK = threading.Lock()
_LANDMARKER = None
_LOAD_ATTEMPTED = False


def _model_path() -> Optional[str]:
    """Configured path to the face_landmarker.task asset, or None."""
    from django.conf import settings
    config = getattr(settings, 'BIOMETRIC_LIVENESS', {})
    path = config.get('FACE_LANDMARKER_MODEL') or ''
    return path or None


def get_face_landmarker():
    """
    The shared FaceLandmarker instance, or None when the capability is absent.

    None when: mediapipe's Tasks API is not importable, no model asset is
    configured, the file is missing, or the load fails. All of those mean the
    landmark-based modalities (gaze, micro-expression) are genuinely
    unavailable -- callers must treat None as "hide and exclude", never
    substitute a placeholder.
    """
    global _LANDMARKER, _LOAD_ATTEMPTED
    if _LANDMARKER is not None or _LOAD_ATTEMPTED:
        return _LANDMARKER
    with _LOAD_LOCK:
        if _LANDMARKER is not None or _LOAD_ATTEMPTED:
            return _LANDMARKER
        _LOAD_ATTEMPTED = True
        path = _model_path()
        if not path:
            logger.info(
                "No FaceLandmarker model configured; landmark-based liveness "
                "modalities stay unavailable")
            return None
        if not os.path.isfile(path):
            logger.warning(
                f"FaceLandmarker model not found at {path}; landmark-based "
                "liveness modalities stay unavailable")
            return None
        try:
            from mediapipe.tasks.python import BaseOptions
            from mediapipe.tasks.python import vision
            options = vision.FaceLandmarkerOptions(
                base_options=BaseOptions(model_asset_path=path),
                output_face_blendshapes=True,
                num_faces=1,
                # IMAGE mode: frames arrive over REST and WS from multiple
                # transports, so a strictly monotonic video timestamp cannot be
                # guaranteed per detector instance.
                running_mode=vision.RunningMode.IMAGE,
            )
            _LANDMARKER = vision.FaceLandmarker.create_from_options(options)
            logger.info(f"FaceLandmarker loaded from {path}")
        except Exception:
            logger.exception(
                "FaceLandmarker load failed; landmark-based liveness "
                "modalities stay unavailable")
            _LANDMARKER = None
        return _LANDMARKER


def detect_face(
    frame_rgb: np.ndarray,
) -> Optional[Tuple[np.ndarray, Dict[str, float]]]:
    """
    Run the shared landmarker on an RGB frame.

    Returns ``(landmarks, blendshapes)`` -- landmarks as a (478, 3) array of
    normalized [x, y, z] coordinates (indices 468-477 are the iris ring), and
    blendshapes as {category_name: score} -- or None when no capability is
    loaded or no face is detected. Never fabricates either.
    """
    landmarker = get_face_landmarker()
    if landmarker is None:
        return None
    try:
        import mediapipe as mp
        image = mp.Image(
            image_format=mp.ImageFormat.SRGB,
            data=np.ascontiguousarray(frame_rgb, dtype=np.uint8),
        )
        # One shared Tasks detector is not thread-safe across sessions.
        with _DETECT_LOCK:
            result = landmarker.detect(image)
        if not result.face_landmarks:
            return None
        landmarks = np.array(
            [[p.x, p.y, p.z] for p in result.face_landmarks[0]])
        blendshapes: Dict[str, float] = {}
        if result.face_blendshapes:
            blendshapes = {
                b.category_name: float(b.score)
                for b in result.face_blendshapes[0]
            }
        return landmarks, blendshapes
    except Exception:
        logger.exception("FaceLandmarker inference failed")
        return None


def _reset_for_tests() -> None:
    """Clear the cached landmarker/attempt flag (test isolation only)."""
    global _LANDMARKER, _LOAD_ATTEMPTED
    with _LOAD_LOCK:
        _LANDMARKER = None
        _LOAD_ATTEMPTED = False

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
restart, the standard contract for process-wide ML resources.

Concurrency: a single Tasks detector is NOT thread-safe, but serializing every
session's inference behind one global mutex makes that detector the throughput
ceiling -- at 30fps with tens-of-ms per detect(), a handful of concurrent
verifications saturate it and the lock is held on request/worker threads. So we
keep a small POOL of independent detector instances and hand one to each
inference: a detector is still touched by exactly one thread at a time (the
guarantee that matters), while sessions run concurrently up to the pool size.
Each instance carries its own copy of the model weights, so the pool is sized
modestly and is configurable via ``LIVENESS_FACE_LANDMARKER_POOL``.
"""

import logging
import os
import queue
import threading
from typing import Dict, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)

_LOAD_LOCK = threading.Lock()
# Detectors available to borrow. Empty tuple => the capability is absent.
_POOL: 'queue.Queue' = queue.Queue()
_POOL_SIZE = 0
_LANDMARKER = None
_LOAD_ATTEMPTED = False

_DEFAULT_POOL_SIZE = 4
# Far longer than any real detect(); a backstop against a lost detector, not a
# tuning knob for contention.
_BORROW_TIMEOUT_S = 30


def _model_path() -> Optional[str]:
    """Configured path to the face_landmarker.task asset, or None."""
    from django.conf import settings
    config = getattr(settings, 'BIOMETRIC_LIVENESS', {})
    path = config.get('FACE_LANDMARKER_MODEL') or ''
    return path or None


def _pool_size() -> int:
    """How many detector instances to hold (>=1); each holds its own weights."""
    from django.conf import settings
    config = getattr(settings, 'BIOMETRIC_LIVENESS', {})
    try:
        return max(1, int(config.get('FACE_LANDMARKER_POOL', _DEFAULT_POOL_SIZE)))
    except (TypeError, ValueError):
        return _DEFAULT_POOL_SIZE


def _create_detector(path: str):
    """One configured FaceLandmarker instance, or None if construction fails."""
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
    return vision.FaceLandmarker.create_from_options(options)


def get_face_landmarker():
    """
    A representative FaceLandmarker, or None when the capability is absent.

    Used as the CAPABILITY PROBE (`is not None`) by the gaze estimator and the
    expression analyzer. Do not call detect() on the returned object -- it is
    also in the pool, and concurrent use of one Tasks detector is exactly what
    the pool exists to avoid. Run inference through detect_face().

    None when: mediapipe's Tasks API is not importable, no model asset is
    configured, the file is missing, or the load fails. All of those mean the
    landmark-based modalities (gaze, micro-expression) are genuinely
    unavailable -- callers must treat None as "hide and exclude", never
    substitute a placeholder.
    """
    global _LANDMARKER, _LOAD_ATTEMPTED, _POOL_SIZE
    if _LANDMARKER is not None or _LOAD_ATTEMPTED:
        return _LANDMARKER
    with _LOAD_LOCK:
        if _LANDMARKER is not None or _LOAD_ATTEMPTED:
            return _LANDMARKER
        try:
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
                wanted = _pool_size()
                detectors = [_create_detector(path)]
                # The first instance proves the capability. Additional ones are
                # pure throughput, so a failure part-way (e.g. memory pressure)
                # degrades the pool rather than the feature.
                for _ in range(wanted - 1):
                    try:
                        detectors.append(_create_detector(path))
                    except Exception:
                        logger.warning(
                            "FaceLandmarker pool stopped at %d/%d instances; "
                            "inference will be more serialized",
                            len(detectors), wanted, exc_info=True)
                        break
                for detector in detectors:
                    _POOL.put(detector)
                _POOL_SIZE = len(detectors)
                _LANDMARKER = detectors[0]
                logger.info(
                    f"FaceLandmarker loaded from {path} ({_POOL_SIZE} instances)")
            except Exception:
                logger.exception(
                    "FaceLandmarker load failed; landmark-based liveness "
                    "modalities stay unavailable")
                _LANDMARKER = None
            return _LANDMARKER
        finally:
            # Set the one-shot sentinel only AFTER the attempt resolves. Setting
            # it before the (hundreds-of-ms) create_from_options would make the
            # lock-free fast path return None to concurrent callers mid-load, so
            # gaze/expression would report unavailable on a process that does
            # have the model. Other threads instead block on _LOAD_LOCK until the
            # load finishes, then see the loaded model. The round-29 invariant
            # still holds: after this one-time attempt the fast path is lock-free
            # for both the loaded and permanently-absent cases.
            _LOAD_ATTEMPTED = True


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
    if get_face_landmarker() is None:
        return None
    try:
        import mediapipe as mp
        image = mp.Image(
            image_format=mp.ImageFormat.SRGB,
            data=np.ascontiguousarray(frame_rgb, dtype=np.uint8),
        )
        # Borrow a detector for the duration of this one detect() and put it
        # straight back. A Tasks detector is not thread-safe, so it must not be
        # shared concurrently -- but distinct instances can run in parallel, so
        # a busy pool blocks only until a peer finishes rather than behind every
        # inference in the process.
        #
        # The timeout should never fire: the pool is non-empty whenever the
        # capability check above passed, and every borrow is returned in a
        # finally. It exists so that a bug which loses a detector degrades to
        # "this frame has no landmarks" rather than parking a worker thread for
        # the life of the process.
        try:
            landmarker = _POOL.get(timeout=_BORROW_TIMEOUT_S)
        except queue.Empty:
            logger.error(
                "FaceLandmarker pool exhausted for %ss; skipping this frame",
                _BORROW_TIMEOUT_S)
            return None
        try:
            result = landmarker.detect(image)
        finally:
            _POOL.put(landmarker)
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
    """Clear the cached landmarker/pool/attempt flag (test isolation only)."""
    global _LANDMARKER, _LOAD_ATTEMPTED, _POOL, _POOL_SIZE
    with _LOAD_LOCK:
        _LANDMARKER = None
        _LOAD_ATTEMPTED = False
        _POOL = queue.Queue()
        _POOL_SIZE = 0

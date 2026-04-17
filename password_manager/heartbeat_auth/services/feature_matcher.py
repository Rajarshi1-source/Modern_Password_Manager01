"""HRV feature matcher.

Given a freshly uploaded feature vector and a stored per-user profile,
return a match score in [0, 1]. Internally this is a Mahalanobis-style
distance with a tiny ridge on the covariance for stability on the
early-enrollment case where the covariance matrix is rank-deficient.

The feature order is frozen in :data:`FEATURE_ORDER`; changing it
requires a baseline rebuild. Missing features in an incoming reading
are treated as ``mean[i]`` so they contribute zero to the distance —
this deliberately fails-open for absent features rather than crashing
enrollment on iOS where some signals can't be produced.
"""

from __future__ import annotations

import math
from typing import Dict, Iterable, List, Sequence, Tuple

try:
    import numpy as np  # type: ignore
except ImportError:  # pragma: no cover - numpy is a dep via ml_security
    np = None

FEATURE_ORDER: Tuple[str, ...] = (
    'mean_hr',
    'rmssd',
    'sdnn',
    'pnn50',
    'lf_hf_ratio',
)

RIDGE = 1e-3


def vector_from_features(features: Dict[str, float]) -> List[float]:
    """Project a feature dict onto the canonical FEATURE_ORDER."""
    out: List[float] = []
    for name in FEATURE_ORDER:
        v = features.get(name)
        try:
            out.append(float(v) if v is not None else float('nan'))
        except (TypeError, ValueError):
            out.append(float('nan'))
    return out


def _numpy_cov(samples: Sequence[Sequence[float]]) -> List[List[float]]:
    arr = np.asarray(samples, dtype=float)
    if arr.shape[0] < 2:
        n = arr.shape[1]
        return (np.eye(n) * 1.0).tolist()
    cov = np.cov(arr, rowvar=False)
    if cov.ndim == 0:
        cov = np.array([[float(cov)]])
    return cov.tolist()


def rolling_mean_cov(
    prev_mean: Sequence[float],
    prev_cov: Sequence[Sequence[float]],
    prev_count: int,
    new_vec: Sequence[float],
) -> Tuple[List[float], List[List[float]], int]:
    """Welford-style online update of mean and covariance.

    The covariance computed here is the *sample* covariance; during
    the first ``len(FEATURE_ORDER) + 1`` samples it is close to
    singular and the matcher adds a ridge on top to keep the inverse
    well-conditioned.
    """
    if np is None:
        raise RuntimeError('numpy is required for heartbeat feature matcher')

    n = prev_count + 1
    new_vec_np = np.asarray(new_vec, dtype=float)
    new_vec_np = np.where(np.isnan(new_vec_np), 0.0, new_vec_np)

    if prev_count == 0:
        mean = new_vec_np.copy()
        d = new_vec_np.shape[0]
        cov = np.eye(d) * 0.0
        return mean.tolist(), cov.tolist(), n

    prev_mean_np = np.asarray(prev_mean, dtype=float)
    prev_cov_np = np.asarray(prev_cov, dtype=float) if prev_cov else np.eye(new_vec_np.shape[0]) * 0.0
    delta = new_vec_np - prev_mean_np
    new_mean = prev_mean_np + delta / n
    # Recursive sample-covariance update.
    delta2 = new_vec_np - new_mean
    m2_prev = prev_cov_np * max(prev_count - 1, 0)
    m2_new = m2_prev + np.outer(delta, delta2)
    new_cov = m2_new / max(n - 1, 1)
    return new_mean.tolist(), new_cov.tolist(), n


def match(profile, features: Dict[str, float]) -> Dict[str, float]:
    """Return match metrics for ``features`` against ``profile``.

    Result shape::

        {
          'score': float in [0, 1],
          'distance': Mahalanobis distance (float),
          'per_feature_z': {name: z-score, ...},
        }

    Score = exp(-d^2 / 2), clipped to [0, 1].
    """
    if np is None:
        raise RuntimeError('numpy is required for heartbeat feature matcher')

    vec = np.asarray(vector_from_features(features), dtype=float)
    vec = np.where(np.isnan(vec), 0.0, vec)

    mean = np.asarray(profile.baseline_mean or [0.0] * len(FEATURE_ORDER), dtype=float)
    cov_raw = profile.baseline_cov or []
    cov = np.asarray(cov_raw, dtype=float) if cov_raw else np.eye(len(FEATURE_ORDER))
    if cov.shape != (len(FEATURE_ORDER), len(FEATURE_ORDER)):
        cov = np.eye(len(FEATURE_ORDER))

    cov_reg = cov + np.eye(cov.shape[0]) * RIDGE
    try:
        inv = np.linalg.inv(cov_reg)
    except np.linalg.LinAlgError:  # pragma: no cover
        inv = np.eye(cov.shape[0])

    diff = vec - mean
    distance_sq = float(diff @ inv @ diff)
    distance = math.sqrt(max(distance_sq, 0.0))
    score = math.exp(-distance_sq / 2.0)
    score = max(0.0, min(1.0, score))

    per_feature_z: Dict[str, float] = {}
    for i, name in enumerate(FEATURE_ORDER):
        sigma = math.sqrt(max(float(cov_reg[i, i]), 1e-9))
        per_feature_z[name] = float(diff[i] / sigma) if sigma else 0.0

    return {
        'score': score,
        'distance': distance,
        'per_feature_z': per_feature_z,
    }

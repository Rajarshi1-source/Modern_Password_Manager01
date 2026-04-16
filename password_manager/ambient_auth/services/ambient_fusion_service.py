"""
Ambient fusion service.

Pure-python, no numpy dependency, to keep the service dependency-light and
easy to test. All vector math is done on plain Python lists of floats.

Public API:
    ingest(user, payload)              -> FusionResult
    promote_context(user, observation_id, label) -> AmbientContext
    rename_context(user, context_id, label) -> AmbientContext
    delete_context(user, context_id) -> None
    reset_baseline(user)               -> None
    recompute_signal_reliability(user) -> dict[signal_key, weight]
    list_contexts(user)                -> list[AmbientContext]
    recent_observations(user, limit)   -> list[AmbientObservation]
    ensure_profile(user, device_fp)    -> AmbientProfile
    get_signal_configs(user)           -> dict[signal_key, dict]
    set_signal_config(user, signal_key, enabled, enabled_on_surfaces) -> AmbientSignalConfig

Wire protocol (payload from the three client surfaces):
    {
        "surface": "web" | "extension" | "mobile",
        "schema_version": 1,
        "device_fp": "<string>",
        "local_salt_version": 1,
        "signal_availability": {
            "ambient_light": true,
            "wifi_signature": false,
            ...
        },
        "coarse_features": {
            "light_bucket": "normal",
            "motion_class": "still",
            "battery_drain_slope_bucket": "slow",
            "connection_class": "wifi",
            "effective_type": "4g",
            "scroll_momentum_bucket": "low",
            "pointer_pressure_mean_bucket": "medium",
            "typing_cadence_stats": {...},
            "geohash_bucket": "9q8yy",
            "tz_offset_min": -480,
            "is_business_hours": true,
        },
        "embedding_digest": "<64-hex-chars or more>",
        "embedding_vector": [f1, f2, ..., f64]  # optional; if missing we derive from digest
    }
"""

from __future__ import annotations

import hashlib
import logging
import math
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from ..models import (
    AmbientContext,
    AmbientObservation,
    AmbientProfile,
    AmbientSignalConfig,
    SCHEMA_VERSION,
    SIGNAL_KEYS,
    SURFACE_CHOICES,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration (settings.AMBIENT_AUTH, all keys optional)
# ---------------------------------------------------------------------------

DEFAULT_EMBEDDING_DIM = 64
DEFAULT_CONTEXT_MATCH_RADIUS = 0.35  # cosine distance; lower = stricter
DEFAULT_CONTEXT_PROMOTE_MIN_SAMPLES = 3
DEFAULT_TRUST_HIGH = 0.85
DEFAULT_NOVELTY_HIGH = 0.70
DEFAULT_CENTROID_EMA_ALPHA = 0.15
DEFAULT_MAX_CONTEXTS_PER_PROFILE = 16

_SURFACE_VALUES = {s for s, _ in SURFACE_CHOICES}
_LABEL_RE = re.compile(r"^[\w\-\. ]{1,64}$")
_HEX_RE = re.compile(r"^[0-9a-fA-F]+$")


def _config() -> dict:
    return getattr(settings, "AMBIENT_AUTH", {}) or {}


def _embedding_dim() -> int:
    return int(_config().get("EMBEDDING_DIM", DEFAULT_EMBEDDING_DIM))


def _match_radius(override: Optional[float] = None) -> float:
    if override is not None:
        return float(override)
    return float(_config().get("CONTEXT_MATCH_RADIUS", DEFAULT_CONTEXT_MATCH_RADIUS))


def _promote_min_samples() -> int:
    return int(_config().get("CONTEXT_PROMOTE_MIN_SAMPLES", DEFAULT_CONTEXT_PROMOTE_MIN_SAMPLES))


def _trust_high() -> float:
    return float(_config().get("TRUST_HIGH", DEFAULT_TRUST_HIGH))


def _novelty_high() -> float:
    return float(_config().get("NOVELTY_HIGH", DEFAULT_NOVELTY_HIGH))


def _ema_alpha() -> float:
    return float(_config().get("CENTROID_EMA_ALPHA", DEFAULT_CENTROID_EMA_ALPHA))


def _max_contexts() -> int:
    return int(_config().get("MAX_CONTEXTS_PER_PROFILE", DEFAULT_MAX_CONTEXTS_PER_PROFILE))


def enabled() -> bool:
    """Master feature flag."""
    return bool(_config().get("ENABLED", True))


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------


@dataclass
class FusionResult:
    """Return value of ``ingest``. Safe to serialize straight to JSON."""

    observation: AmbientObservation
    profile: AmbientProfile
    matched_context: Optional[AmbientContext]
    trust_score: float
    novelty_score: float
    reasons: List[Dict[str, object]] = field(default_factory=list)
    mfa_recommendation: str = "no_change"  # "step_down" | "step_up" | "no_change"


# ---------------------------------------------------------------------------
# Math helpers (no numpy)
# ---------------------------------------------------------------------------


def _l2_norm(vec: Sequence[float]) -> float:
    return math.sqrt(sum(float(x) * float(x) for x in vec))


def _normalize(vec: Sequence[float]) -> List[float]:
    n = _l2_norm(vec)
    if n <= 0:
        return [0.0] * len(vec)
    return [float(x) / n for x in vec]


def _dot(a: Sequence[float], b: Sequence[float]) -> float:
    return sum(float(x) * float(y) for x, y in zip(a, b))


def _cosine_distance(a: Sequence[float], b: Sequence[float]) -> float:
    """Cosine distance in [0, 2]. 0 = identical direction, 2 = opposite."""
    na = _l2_norm(a)
    nb = _l2_norm(b)
    if na <= 0 or nb <= 0:
        return 1.0
    sim = _dot(a, b) / (na * nb)
    # Clamp to handle fp rounding.
    sim = max(-1.0, min(1.0, sim))
    return 1.0 - sim


def _derive_vector_from_digest(digest: str, dim: int) -> List[float]:
    """
    Deterministically expand a hex digest into a `dim`-length float vector
    in [-1, 1]. Used when the client does not ship an explicit embedding
    vector (only a digest). The same mapping must be used wherever else
    we compare digests to stored centroids.
    """
    if not digest:
        return [0.0] * dim
    # Use SHAKE-256 to get an arbitrary-length byte stream keyed by the digest.
    h = hashlib.shake_256(digest.encode("utf-8"))
    raw = h.digest(4 * dim)
    vec: List[float] = []
    for i in range(dim):
        chunk = raw[4 * i : 4 * (i + 1)]
        u = int.from_bytes(chunk, "big", signed=False)
        # Map to [-1, 1).
        vec.append((u / 2**31) - 1.0)
    return _normalize(vec)


def _coarse_feature_contributions(coarse: dict, dim: int) -> List[float]:
    """
    Hash each coarse feature key=value into the same `dim`-length float
    space and L2-normalize. Gives the server something structured to fuse
    with the opaque digest even when the client fails to ship an
    explicit vector.
    """
    vec = [0.0] * dim
    if not isinstance(coarse, dict):
        return vec
    for k, v in sorted(coarse.items()):
        token = f"{k}={v!s}".encode("utf-8")
        h = hashlib.sha256(token).digest()
        # Fold into `dim` float slots deterministically.
        for i, byte in enumerate(h):
            slot = i % dim
            # Center byte around 0.
            vec[slot] += (byte - 127.5) / 127.5
    return _normalize(vec)


def _build_embedding(payload: dict, dim: int) -> List[float]:
    """
    Combine the client-provided embedding (if any), the LSH digest
    expansion, and the hashed coarse features into a single normalized
    vector.
    """
    # 1) Client-provided vector (trusted shape, but still normalized).
    explicit = payload.get("embedding_vector")
    if isinstance(explicit, list) and len(explicit) >= 1:
        # Truncate or zero-pad to `dim`.
        trimmed = [float(x) for x in explicit[:dim]]
        if len(trimmed) < dim:
            trimmed.extend([0.0] * (dim - len(trimmed)))
        base = _normalize(trimmed)
    else:
        base = _derive_vector_from_digest(str(payload.get("embedding_digest", "")), dim)

    # 2) Coarse feature hash contribution.
    coarse_vec = _coarse_feature_contributions(payload.get("coarse_features", {}), dim)

    # 3) Weighted sum; the digest dominates (2/3) so the coarse hash acts
    #    as a tie-breaker rather than an override.
    fused = [
        (2.0 * b + 1.0 * c) / 3.0 for b, c in zip(base, coarse_vec)
    ]
    return _normalize(fused)


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def _validate_payload(payload: dict) -> None:
    """Reject malformed payloads & obvious privacy-policy violations."""
    if not isinstance(payload, dict):
        raise ValueError("Payload must be an object.")

    surface = payload.get("surface")
    if surface not in _SURFACE_VALUES:
        raise ValueError(f"Unknown surface: {surface!r}")

    schema = int(payload.get("schema_version", 0))
    if schema != SCHEMA_VERSION:
        raise ValueError(f"Unsupported schema_version: {schema}")

    device_fp = str(payload.get("device_fp", "")).strip()
    if not device_fp or len(device_fp) > 128:
        raise ValueError("device_fp missing or too long.")

    digest = str(payload.get("embedding_digest", "")).strip()
    if digest:
        if not _HEX_RE.match(digest) or len(digest) > 256:
            raise ValueError("embedding_digest must be hex, <=256 chars.")

    coarse = payload.get("coarse_features", {})
    if not isinstance(coarse, dict):
        raise ValueError("coarse_features must be an object.")

    # Privacy fence: reject payloads that try to smuggle raw sensitive signals.
    _reject_raw_sensitive(coarse)

    signal_availability = payload.get("signal_availability", {})
    if not isinstance(signal_availability, dict):
        raise ValueError("signal_availability must be an object.")


_SENSITIVE_KEY_SUBSTRINGS = (
    "bssid",
    "ssid_list",
    "wifi_list",
    "bluetooth_list",
    "ble_list",
    "audio_pcm",
    "audio_raw",
    "audio_samples",
    "mac_list",
    "mac_addresses",
)


def _reject_raw_sensitive(coarse: dict) -> None:
    """
    The Hybrid Privacy Policy forbids raw BSSIDs, raw BT MACs, or raw
    audio samples from ever reaching the server. Reject on sight — this
    is a hard contract violation.
    """
    for k, v in coarse.items():
        lk = str(k).lower()
        for needle in _SENSITIVE_KEY_SUBSTRINGS:
            if needle in lk:
                raise ValueError(
                    f"Privacy policy violation: coarse_features must not contain raw '{k}'."
                )
        # Lists of long hex/mac-looking strings are also forbidden in coarse features.
        if isinstance(v, list) and len(v) > 4:
            suspicious = sum(
                1 for x in v
                if isinstance(x, str)
                and len(x) >= 12
                and (":" in x or "-" in x or _HEX_RE.match(x.replace(":", "").replace("-", "")))
            )
            if suspicious >= 3:
                raise ValueError(
                    f"Privacy policy violation: coarse_features['{k}'] looks like raw BSSID/MAC list."
                )


# ---------------------------------------------------------------------------
# Profile/context persistence
# ---------------------------------------------------------------------------


def ensure_profile(user, device_fp: str, local_salt_version: int = 1) -> AmbientProfile:
    profile, _created = AmbientProfile.objects.get_or_create(
        user=user,
        device_fp=device_fp,
        local_salt_version=local_salt_version,
    )
    return profile


def _update_profile_centroid(profile: AmbientProfile, vector: List[float]) -> None:
    """EWMA update of the profile global centroid."""
    stored = profile.centroid_json or {}
    prev = stored.get("vector")
    dim = len(vector)
    if not isinstance(prev, list) or len(prev) != dim:
        new_vec = list(vector)
    else:
        alpha = _ema_alpha()
        new_vec = [
            (1.0 - alpha) * float(prev[i]) + alpha * float(vector[i])
            for i in range(dim)
        ]
    profile.centroid_json = {"vector": _normalize(new_vec), "dim": dim}


def _update_context_centroid(ctx: AmbientContext, vector: List[float]) -> None:
    stored = ctx.centroid_json or {}
    prev = stored.get("vector")
    dim = len(vector)
    if not isinstance(prev, list) or len(prev) != dim:
        new_vec = list(vector)
    else:
        alpha = _ema_alpha()
        new_vec = [
            (1.0 - alpha) * float(prev[i]) + alpha * float(vector[i])
            for i in range(dim)
        ]
    ctx.centroid_json = {"vector": _normalize(new_vec), "dim": dim}


def _best_context(profile: AmbientProfile, vector: List[float]):
    """Return (context, distance) for the nearest matching context, or (None, 1.0)."""
    best_ctx = None
    best_dist = 1.0
    for ctx in profile.contexts.all():
        stored = ctx.centroid_json or {}
        cent = stored.get("vector")
        if not isinstance(cent, list) or len(cent) != len(vector):
            continue
        d = _cosine_distance(vector, cent)
        if d < best_dist:
            best_dist = d
            best_ctx = ctx
    return best_ctx, best_dist


def _build_reasons(
    coarse: dict,
    availability: dict,
    matched_ctx: Optional[AmbientContext],
    distance: float,
    novelty: float,
) -> List[dict]:
    reasons: List[dict] = []

    if matched_ctx is not None:
        reasons.append(
            {
                "kind": "matched_context",
                "label": matched_ctx.label,
                "trusted": matched_ctx.is_trusted,
                "distance": round(float(distance), 4),
            }
        )
    elif novelty >= _novelty_high():
        reasons.append({"kind": "novel_context", "novelty": round(float(novelty), 4)})
    else:
        reasons.append({"kind": "no_known_context", "distance": round(float(distance), 4)})

    captured = [k for k, v in (availability or {}).items() if v]
    missing = [k for k, v in (availability or {}).items() if not v]
    if captured:
        reasons.append({"kind": "signals_captured", "signals": sorted(captured)})
    if missing:
        reasons.append({"kind": "signals_missing", "signals": sorted(missing)})

    if isinstance(coarse, dict):
        keep = {
            k: coarse[k]
            for k in (
                "light_bucket",
                "motion_class",
                "connection_class",
                "effective_type",
                "battery_drain_slope_bucket",
                "scroll_momentum_bucket",
                "pointer_pressure_mean_bucket",
                "geohash_bucket",
                "is_business_hours",
            )
            if k in coarse
        }
        if keep:
            reasons.append({"kind": "coarse_features", "features": keep})

    return reasons


def _mfa_recommendation(
    matched_ctx: Optional[AmbientContext],
    trust: float,
    novelty: float,
) -> str:
    if matched_ctx is not None and matched_ctx.is_trusted and trust >= _trust_high():
        return "step_down"
    if novelty >= _novelty_high():
        return "step_up"
    return "no_change"


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


@transaction.atomic
def ingest(user, payload: dict) -> FusionResult:
    """Validate + score + persist an ambient observation."""
    if not enabled():
        raise RuntimeError("Ambient auth is disabled in settings.AMBIENT_AUTH.ENABLED.")

    _validate_payload(payload)

    dim = _embedding_dim()
    vector = _build_embedding(payload, dim)

    profile = ensure_profile(
        user,
        device_fp=str(payload["device_fp"]),
        local_salt_version=int(payload.get("local_salt_version", 1)),
    )

    best_ctx, distance = _best_context(profile, vector)
    radius = _match_radius()

    if best_ctx is not None and distance <= radius:
        # Matched an existing cluster.
        trust = max(0.0, min(1.0, 1.0 - (distance / max(radius, 1e-6))))
        novelty = 0.0
        matched_context = best_ctx
        best_ctx.samples_used = int(best_ctx.samples_used) + 1
        best_ctx.last_matched_at = timezone.now()
        _update_context_centroid(best_ctx, vector)
        best_ctx.save()
    else:
        # Novel — attach to profile but do NOT auto-promote to a named
        # context. Users explicitly promote via promote_context().
        trust = 0.0
        # Novelty: saturate smoothly once distance exceeds the radius.
        if best_ctx is None:
            novelty = 1.0
        else:
            novelty = max(0.0, min(1.0, (distance - radius) / max(1.0 - radius, 1e-6)))
        matched_context = None

    # Global profile centroid always tracks.
    _update_profile_centroid(profile, vector)
    profile.samples_used = int(profile.samples_used) + 1
    profile.last_observation_at = timezone.now()
    profile.save()

    reasons = _build_reasons(
        payload.get("coarse_features", {}),
        payload.get("signal_availability", {}),
        matched_context,
        distance,
        novelty,
    )
    recommendation = _mfa_recommendation(matched_context, trust, novelty)

    observation = AmbientObservation.objects.create(
        user=user,
        profile=profile,
        matched_context=matched_context,
        surface=str(payload["surface"]),
        schema_version=SCHEMA_VERSION,
        signal_availability=payload.get("signal_availability", {}),
        coarse_features_json=payload.get("coarse_features", {}),
        embedding_digest=str(payload.get("embedding_digest", ""))[:256],
        trust_score=float(trust),
        novelty_score=float(novelty),
        reasons_json=reasons,
    )

    return FusionResult(
        observation=observation,
        profile=profile,
        matched_context=matched_context,
        trust_score=float(trust),
        novelty_score=float(novelty),
        reasons=reasons,
        mfa_recommendation=recommendation,
    )


# ---------------------------------------------------------------------------
# Context lifecycle
# ---------------------------------------------------------------------------


@transaction.atomic
def promote_context(user, observation_id, label: str) -> AmbientContext:
    """Promote an observation into a named context (trusted=True)."""
    if not _LABEL_RE.match(label or ""):
        raise ValueError("Label must be 1-64 chars of word / space / dash / dot.")

    try:
        obs = AmbientObservation.objects.select_related("profile").get(
            id=observation_id,
            user=user,
        )
    except AmbientObservation.DoesNotExist as exc:
        raise LookupError(f"Observation {observation_id} not found for user {user.id}.") from exc

    if obs.profile is None:
        raise ValueError("Observation has no profile to attach a context to.")

    if obs.profile.contexts.count() >= _max_contexts():
        raise ValueError(f"Max {_max_contexts()} contexts per profile reached.")

    dim = _embedding_dim()
    vector = _derive_vector_from_digest(obs.embedding_digest, dim)
    # Mix in the coarse features so promotion is consistent with ingest math.
    coarse_vec = _coarse_feature_contributions(obs.coarse_features_json or {}, dim)
    fused = _normalize([(2.0 * b + 1.0 * c) / 3.0 for b, c in zip(vector, coarse_vec)])

    ctx = AmbientContext.objects.create(
        profile=obs.profile,
        label=label.strip(),
        centroid_json={"vector": fused, "dim": dim},
        radius=_match_radius(),
        is_trusted=True,
        samples_used=1,
        last_matched_at=timezone.now(),
    )

    # Back-link the observation that seeded the context.
    obs.matched_context = ctx
    obs.save(update_fields=["matched_context"])

    return ctx


@transaction.atomic
def rename_context(user, context_id, label: str) -> AmbientContext:
    if not _LABEL_RE.match(label or ""):
        raise ValueError("Label must be 1-64 chars of word / space / dash / dot.")

    ctx = (
        AmbientContext.objects.select_related("profile")
        .filter(id=context_id, profile__user=user)
        .first()
    )
    if ctx is None:
        raise LookupError(f"Context {context_id} not found for user {user.id}.")
    ctx.label = label.strip()
    ctx.save(update_fields=["label", "updated_at"])
    return ctx


@transaction.atomic
def delete_context(user, context_id) -> None:
    ctx = (
        AmbientContext.objects.select_related("profile")
        .filter(id=context_id, profile__user=user)
        .first()
    )
    if ctx is None:
        raise LookupError(f"Context {context_id} not found for user {user.id}.")
    ctx.delete()


@transaction.atomic
def reset_baseline(user) -> None:
    """Nuke all ambient data for a user — privacy escape hatch."""
    AmbientObservation.objects.filter(user=user).delete()
    AmbientContext.objects.filter(profile__user=user).delete()
    AmbientProfile.objects.filter(user=user).delete()


def list_contexts(user):
    return AmbientContext.objects.filter(profile__user=user).order_by("-updated_at")


def recent_observations(user, limit: int = 50):
    limit = max(1, min(int(limit), 200))
    return (
        AmbientObservation.objects.filter(user=user)
        .select_related("matched_context", "profile")
        .order_by("-created_at")[:limit]
    )


# ---------------------------------------------------------------------------
# Signal config
# ---------------------------------------------------------------------------


def ensure_signal_configs(user) -> List[AmbientSignalConfig]:
    """Create any missing default config rows (all enabled by default, all surfaces)."""
    existing = {c.signal_key for c in AmbientSignalConfig.objects.filter(user=user)}
    created: List[AmbientSignalConfig] = []
    for key in SIGNAL_KEYS:
        if key in existing:
            continue
        created.append(
            AmbientSignalConfig.objects.create(
                user=user,
                signal_key=key,
                enabled=True,
                enabled_on_surfaces=list(_SURFACE_VALUES),
            )
        )
    return created


def get_signal_configs(user) -> Dict[str, dict]:
    ensure_signal_configs(user)
    out: Dict[str, dict] = {}
    for c in AmbientSignalConfig.objects.filter(user=user):
        out[c.signal_key] = {
            "enabled": bool(c.enabled),
            "enabled_on_surfaces": list(c.enabled_on_surfaces or []),
        }
    return out


@transaction.atomic
def set_signal_config(user, signal_key: str, *, enabled=None, enabled_on_surfaces=None):
    if signal_key not in SIGNAL_KEYS:
        raise ValueError(f"Unknown signal_key: {signal_key}")
    cfg, _ = AmbientSignalConfig.objects.get_or_create(
        user=user,
        signal_key=signal_key,
        defaults={"enabled": True, "enabled_on_surfaces": list(_SURFACE_VALUES)},
    )
    changed = []
    if enabled is not None:
        cfg.enabled = bool(enabled)
        changed.append("enabled")
    if enabled_on_surfaces is not None:
        surfaces = [s for s in enabled_on_surfaces if s in _SURFACE_VALUES]
        cfg.enabled_on_surfaces = surfaces
        changed.append("enabled_on_surfaces")
    if changed:
        cfg.save(update_fields=changed + ["updated_at"])
    return cfg


# ---------------------------------------------------------------------------
# Reliability recomputation (Celery task target)
# ---------------------------------------------------------------------------


def recompute_signal_reliability(user) -> Dict[str, float]:
    """
    Re-learn per-signal weights from observation history.

    Heuristic v1: a signal's reliability is the fraction of recent
    observations in which that signal was captured (available) AND
    contributed to a matched trusted context.
    """
    weights: Dict[str, float] = {k: 0.0 for k in SIGNAL_KEYS}
    counts: Dict[str, int] = {k: 0 for k in SIGNAL_KEYS}

    qs = (
        AmbientObservation.objects.filter(user=user)
        .select_related("matched_context")
        .order_by("-created_at")[:500]
    )
    for obs in qs:
        matched_trusted = bool(obs.matched_context and obs.matched_context.is_trusted)
        availability = obs.signal_availability or {}
        for key in SIGNAL_KEYS:
            if availability.get(key):
                counts[key] += 1
                if matched_trusted:
                    weights[key] += 1.0

    result: Dict[str, float] = {}
    for key in SIGNAL_KEYS:
        result[key] = round(weights[key] / counts[key], 4) if counts[key] > 0 else 0.5

    for profile in AmbientProfile.objects.filter(user=user):
        profile.signal_weights_json = result
        profile.save(update_fields=["signal_weights_json", "updated_at"])

    return result


# ---------------------------------------------------------------------------
# Cross-feature integration helpers
# ---------------------------------------------------------------------------


def latest_signal(user, max_age_seconds: int = 900) -> Optional[Dict[str, object]]:
    """
    Return a lightweight view of the user's most recent ambient
    observation for consumption by adaptive-MFA and ML-security pipelines.

    Returns ``None`` when ambient auth is disabled for the deployment,
    when the user has no ambient observations at all, or when the most
    recent observation is older than ``max_age_seconds``.
    """

    if not enabled():
        return None

    obs = (
        AmbientObservation.objects.filter(user=user)
        .select_related("matched_context")
        .order_by("-created_at")
        .first()
    )
    if obs is None:
        return None

    from django.utils import timezone as _tz

    age = (_tz.now() - obs.created_at).total_seconds()
    if age > max_age_seconds:
        return None

    stage = str(_config().get("ENFORCEMENT_STAGE", "collect")).lower()
    matched = obs.matched_context
    return {
        "observation_id": str(obs.id),
        "surface": obs.surface,
        "trust_score": float(obs.trust_score or 0.0),
        "novelty_score": float(obs.novelty_score or 0.0),
        "matched_context_id": str(matched.id) if matched else None,
        "matched_context_label": matched.label if matched else None,
        "matched_context_trusted": bool(matched.is_trusted) if matched else False,
        "linked_geofence_id": str(matched.linked_geofence_id) if (matched and matched.linked_geofence_id) else None,
        "reasons": list(obs.reasons_json or []),
        "age_seconds": age,
        "enforcement_stage": stage,
    }

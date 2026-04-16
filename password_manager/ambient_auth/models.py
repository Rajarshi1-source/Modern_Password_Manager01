"""
Data model for Ambient Biometric Fusion.

  * ``AmbientProfile`` — one row per ``(user, device_fp)`` baseline. Holds
    per-user/per-device embedding stats and per-signal reliability
    weights. Rebuilt from ``AmbientObservation`` if ever reset.
  * ``AmbientContext`` — a named recurring cluster ("Home", "Office")
    that the user has explicitly promoted (trusted) or auto-labelled.
  * ``AmbientObservation`` — append-only log of every ingest. Never
    stores raw sensitive signals; only bucketed coarse features and the
    opaque LSH digest.
  * ``AmbientSignalConfig`` — per-user, per-signal opt-in toggle.

All index names are <= 30 chars (Django E034 limit).
"""

from __future__ import annotations

import uuid

from django.conf import settings
from django.db import models


# ---------------------------------------------------------------------------
# Constants (shared with the fusion service & serializers)
# ---------------------------------------------------------------------------

SURFACE_WEB = "web"
SURFACE_EXTENSION = "extension"
SURFACE_MOBILE = "mobile"
SURFACE_CHOICES = [
    (SURFACE_WEB, "Web app"),
    (SURFACE_EXTENSION, "Browser extension"),
    (SURFACE_MOBILE, "React Native mobile"),
]

SIGNAL_KEYS = (
    "typing_cadence",
    "pointer_pressure",
    "scroll_momentum",
    "ambient_light",
    "ambient_audio",
    "wifi_signature",
    "bluetooth_devices",
    "accelerometer",
    "battery_drain",
    "network_class",
    "geohash",
)

SCHEMA_VERSION = 1


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class AmbientProfile(models.Model):
    """Per-(user, device_fp) ambient baseline."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="ambient_profiles",
    )
    device_fp = models.CharField(
        max_length=128,
        help_text="Stable device fingerprint (FingerprintJS visitorId or equivalent).",
    )
    local_salt_version = models.PositiveIntegerField(
        default=1,
        help_text="Bump when the client rotates its per-user LSH salt; forces new baseline.",
    )
    centroid_json = models.JSONField(
        default=dict,
        blank=True,
        help_text="Global centroid of all observations (64-d float vector + covariance).",
    )
    signal_weights_json = models.JSONField(
        default=dict,
        blank=True,
        help_text="Per-signal reliability weights in [0,1] learned from observation accuracy.",
    )
    samples_used = models.PositiveIntegerField(default=0)
    last_observation_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "device_fp", "local_salt_version"],
                name="amb_profile_unique_dev_salt",
            ),
        ]
        indexes = [
            models.Index(
                fields=["user", "-updated_at"],
                name="amb_profile_user_upd_idx",
            ),
        ]
        verbose_name = "Ambient profile"
        verbose_name_plural = "Ambient profiles"

    def __str__(self) -> str:  # pragma: no cover
        return f"AmbientProfile(user={self.user_id}, device_fp={self.device_fp[:8]}..., n={self.samples_used})"


class AmbientContext(models.Model):
    """Named recurring ambient cluster (e.g. "Home", "Office")."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    profile = models.ForeignKey(
        AmbientProfile,
        on_delete=models.CASCADE,
        related_name="contexts",
    )
    label = models.CharField(
        max_length=64,
        help_text="Human-readable label (user-provided or auto-generated).",
    )
    centroid_json = models.JSONField(
        default=dict,
        blank=True,
        help_text="64-d centroid for this cluster.",
    )
    radius = models.FloatField(
        default=0.35,
        help_text="Cosine distance threshold under which an observation counts as a match.",
    )
    is_trusted = models.BooleanField(
        default=False,
        help_text="Only trusted contexts grant MFA step-down. Must be explicitly promoted.",
    )
    samples_used = models.PositiveIntegerField(default=0)
    last_matched_at = models.DateTimeField(null=True, blank=True)
    linked_geofence = models.ForeignKey(
        "security.GeofenceZone",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ambient_contexts",
        help_text="Optional cross-link to a GeofenceZone. If the user is inside the linked zone, ambient trust may be treated as corroborated.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(
                fields=["profile", "-updated_at"],
                name="amb_ctx_profile_upd_idx",
            ),
            models.Index(
                fields=["is_trusted"],
                name="amb_ctx_trusted_idx",
            ),
        ]
        verbose_name = "Ambient context"
        verbose_name_plural = "Ambient contexts"

    def __str__(self) -> str:  # pragma: no cover
        trust = "trusted" if self.is_trusted else "untrusted"
        return f"AmbientContext({self.label}, {trust})"


class AmbientObservation(models.Model):
    """Append-only log of ambient observations (what the client posted)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="ambient_observations",
    )
    profile = models.ForeignKey(
        AmbientProfile,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="observations",
    )
    matched_context = models.ForeignKey(
        AmbientContext,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="observations",
    )
    surface = models.CharField(max_length=16, choices=SURFACE_CHOICES)
    schema_version = models.PositiveIntegerField(default=SCHEMA_VERSION)
    signal_availability = models.JSONField(
        default=dict,
        blank=True,
        help_text='Bitmap of which signals were captured, e.g. {"ambient_light": true, "wifi_signature": false}',
    )
    coarse_features_json = models.JSONField(
        default=dict,
        blank=True,
        help_text="Bucketed coarse features (light_bucket, motion_class, ...).",
    )
    embedding_digest = models.CharField(
        max_length=256,
        blank=True,
        default="",
        help_text="Opaque LSH digest (hex). Sensitive signals (BSSIDs, audio, BT) folded in here; never raw.",
    )
    trust_score = models.FloatField(default=0.0)
    novelty_score = models.FloatField(default=0.0)
    reasons_json = models.JSONField(
        default=list,
        blank=True,
        help_text="Structured explainability payload for the UX.",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(
                fields=["user", "-created_at"],
                name="amb_obs_user_created_idx",
            ),
            models.Index(
                fields=["profile", "-created_at"],
                name="amb_obs_profile_ctx_idx",
            ),
        ]
        verbose_name = "Ambient observation"
        verbose_name_plural = "Ambient observations"

    def __str__(self) -> str:  # pragma: no cover
        return f"AmbientObservation({self.id}, trust={self.trust_score:.2f}, nov={self.novelty_score:.2f})"


class AmbientSignalConfig(models.Model):
    """Per-user, per-signal toggle with per-surface granularity."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="ambient_signal_configs",
    )
    signal_key = models.CharField(
        max_length=32,
        help_text="One of ambient_auth.models.SIGNAL_KEYS.",
    )
    enabled = models.BooleanField(default=True)
    enabled_on_surfaces = models.JSONField(
        default=list,
        blank=True,
        help_text='List of surfaces on which this signal is enabled, e.g. ["web", "mobile"].',
    )
    updated_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "signal_key"],
                name="amb_signalcfg_unique",
            ),
        ]
        indexes = [
            models.Index(
                fields=["user", "signal_key"],
                name="amb_signalcfg_user_idx",
            ),
        ]
        verbose_name = "Ambient signal config"
        verbose_name_plural = "Ambient signal configs"

    def __str__(self) -> str:  # pragma: no cover
        state = "on" if self.enabled else "off"
        return f"AmbientSignalConfig(user={self.user_id}, {self.signal_key}={state})"

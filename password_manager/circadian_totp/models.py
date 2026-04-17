"""Database models for circadian-rhythm TOTP.

Models:
    CircadianProfile    - per-user circadian baseline derived from observations.
    SleepObservation    - individual sleep window ingested from a wearable
                          provider or manual entry.
    WearableLink        - encrypted OAuth credentials for a wearable provider.
    CircadianTOTPDevice - the per-user provisioned TOTP device keyed by
                          circadian phase.
"""

from __future__ import annotations

import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone


PROVIDER_CHOICES = (
    ("fitbit", "Fitbit"),
    ("apple_health", "Apple Health"),
    ("oura", "Oura"),
    ("google_fit", "Google Fit"),
    ("manual", "Manual / Self-Reported"),
)


CHRONOTYPE_CHOICES = (
    ("lark", "Early Bird (Lark)"),
    ("neutral", "Neutral"),
    ("owl", "Night Owl"),
)


class CircadianProfile(models.Model):
    """User's circadian baseline, refreshed on each new SleepObservation."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="circadian_profile",
    )
    chronotype = models.CharField(
        max_length=12, choices=CHRONOTYPE_CHOICES, default="neutral"
    )
    # Midpoint of sleep expressed as minutes past UTC midnight (0..1439).
    baseline_sleep_midpoint_minutes = models.IntegerField(default=180)  # 03:00 UTC
    phase_stddev_minutes = models.FloatField(default=30.0)
    phase_lock_minutes = models.IntegerField(
        default=20,
        help_text="Acceptable phase drift window during verification (minutes).",
    )
    sample_count = models.IntegerField(default=0)
    last_calibrated_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Circadian Profile"
        verbose_name_plural = "Circadian Profiles"

    def __str__(self) -> str:  # pragma: no cover - trivial
        return (
            f"CircadianProfile<{self.user_id}> "
            f"midpoint={self.baseline_sleep_midpoint_minutes}m "
            f"samples={self.sample_count}>"
        )


class SleepObservation(models.Model):
    """One sleep window ingested for a user.

    Only minimal metadata is stored - no raw biometric time-series. A SHA-256
    hash of the raw payload is kept for idempotency & audit purposes.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="circadian_observations",
    )
    provider = models.CharField(max_length=20, choices=PROVIDER_CHOICES)
    sleep_start = models.DateTimeField()
    sleep_end = models.DateTimeField()
    efficiency_score = models.FloatField(null=True, blank=True)
    raw_payload_hash = models.CharField(max_length=64, blank=True, default="")
    ingested_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-sleep_end"]
        indexes = [
            models.Index(fields=["user", "sleep_end"]),
            models.Index(fields=["user", "provider"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "provider", "sleep_start"],
                name="uniq_sleep_obs_per_provider",
            )
        ]

    def __str__(self) -> str:  # pragma: no cover - trivial
        return f"SleepObservation<{self.user_id} {self.provider} {self.sleep_end}>"

    @property
    def midpoint_minutes_utc(self) -> int:
        """Minutes past midnight UTC for the sleep midpoint."""
        duration = self.sleep_end - self.sleep_start
        mid = self.sleep_start + duration / 2
        return mid.hour * 60 + mid.minute


class WearableLink(models.Model):
    """Encrypted OAuth credentials for a wearable provider."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="wearable_links",
    )
    provider = models.CharField(max_length=20, choices=PROVIDER_CHOICES)
    external_user_id = models.CharField(max_length=128, blank=True, default="")
    oauth_access_token_encrypted = models.BinaryField(blank=True, default=b"")
    oauth_refresh_token_encrypted = models.BinaryField(blank=True, default=b"")
    scope = models.CharField(max_length=256, blank=True, default="")
    token_type = models.CharField(max_length=32, blank=True, default="Bearer")
    expires_at = models.DateTimeField(null=True, blank=True)
    last_synced_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "provider"], name="uniq_wearable_per_user"
            )
        ]

    def __str__(self) -> str:  # pragma: no cover - trivial
        return f"WearableLink<{self.user_id} {self.provider}>"

    def is_expired(self) -> bool:
        if self.expires_at is None:
            return False
        return timezone.now() >= self.expires_at


class CircadianTOTPDevice(models.Model):
    """A provisioned circadian-modulated TOTP device."""

    DRIFT_ALGORITHMS = (("xor_phase", "XOR Phase (v1)"),)

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="circadian_totp_devices",
    )
    name = models.CharField(max_length=64, default="Circadian Authenticator")
    secret_encrypted = models.BinaryField()
    digits = models.PositiveSmallIntegerField(default=6)
    step_seconds = models.PositiveIntegerField(default=30)
    drift_algorithm = models.CharField(
        max_length=32, choices=DRIFT_ALGORITHMS, default="xor_phase"
    )
    confirmed = models.BooleanField(default=False)
    last_verified_at = models.DateTimeField(null=True, blank=True)
    last_phase_used = models.IntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Circadian TOTP Device"
        verbose_name_plural = "Circadian TOTP Devices"
        indexes = [models.Index(fields=["user", "confirmed"])]

    def __str__(self) -> str:  # pragma: no cover - trivial
        state = "confirmed" if self.confirmed else "pending"
        return f"CircadianTOTPDevice<{self.user_id} {self.name} {state}>"

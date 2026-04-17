"""Models for Heartbeat / HRV authentication.

Schema notes:
    * One profile per user. The baseline mean + covariance are kept
      as JSON lists of floats so we can evolve the feature vector
      without a migration (``services.feature_matcher`` owns the
      canonical feature order).
    * Readings are kept (without raw R-R intervals by default) for
      nightly baseline recomputation. Wiping all readings via
      :func:`services.heartbeat_service.reset` also wipes the profile.
"""

from __future__ import annotations

import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone


class ProfileStatus(models.TextChoices):
    PENDING = 'pending', 'Enrollment in progress'
    ENROLLED = 'enrolled', 'Ready to verify'
    RESET = 'reset', 'Profile was wiped; needs re-enrollment'


class SessionType(models.TextChoices):
    ENROLL = 'enroll', 'Enrollment reading'
    VERIFY = 'verify', 'Verification reading'


class SessionStatus(models.TextChoices):
    PENDING = 'pending', 'Upload received, not scored yet'
    ALLOWED = 'allowed', 'Matched baseline'
    DENIED = 'denied', 'Below match threshold'
    DURESS = 'duress', 'Match OK but stress signature tripped'
    REJECTED = 'rejected', 'Reading quality too low'


class HeartbeatProfile(models.Model):
    """Per-user HRV baseline."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='heartbeat_profile',
        primary_key=True,
    )
    status = models.CharField(
        max_length=16,
        choices=ProfileStatus.choices,
        default=ProfileStatus.PENDING,
    )
    enrollment_count = models.PositiveIntegerField(default=0)

    # Baseline statistics over the feature vector defined in
    # services.feature_matcher.FEATURE_ORDER.
    baseline_mean = models.JSONField(default=list, blank=True)
    baseline_cov = models.JSONField(default=list, blank=True)

    # Cached scalar baselines used by the duress detector; these are
    # populated alongside baseline_mean but split out so the detector
    # can load them with one query rather than reparsing the vector.
    baseline_rmssd = models.FloatField(null=True, blank=True)
    baseline_sdnn = models.FloatField(null=True, blank=True)
    baseline_mean_hr = models.FloatField(null=True, blank=True)

    # Thresholds (overridable per-user for research).
    match_threshold = models.FloatField(
        default=0.75,
        help_text='Minimum match score in [0,1] to allow verification.',
    )
    duress_rmssd_sigma = models.FloatField(
        default=2.0,
        help_text='Duress trigger: RMSSD must drop this many sigmas below baseline.',
    )

    enrolled_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'heartbeat_profiles'
        verbose_name = 'Heartbeat profile'


class HeartbeatSession(models.Model):
    """One capture attempt (enroll or verify)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='heartbeat_sessions',
    )
    session_type = models.CharField(max_length=10, choices=SessionType.choices)
    status = models.CharField(
        max_length=12,
        choices=SessionStatus.choices,
        default=SessionStatus.PENDING,
    )
    match_score = models.FloatField(null=True, blank=True)
    duress_probability = models.FloatField(null=True, blank=True)
    duress_detected = models.BooleanField(default=False)
    created_at = models.DateTimeField(default=timezone.now)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'heartbeat_sessions'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'session_type']),
            models.Index(fields=['user', 'status']),
        ]


class HeartbeatReading(models.Model):
    """Per-capture feature vector + aggregates."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session = models.ForeignKey(
        HeartbeatSession,
        on_delete=models.CASCADE,
        related_name='readings',
    )
    features = models.JSONField(
        default=dict,
        help_text='Canonical feature dict (see services.feature_matcher.FEATURE_ORDER).',
    )
    rmssd = models.FloatField(null=True, blank=True)
    sdnn = models.FloatField(null=True, blank=True)
    mean_hr = models.FloatField(null=True, blank=True)
    lf_hf_ratio = models.FloatField(null=True, blank=True)
    pnn50 = models.FloatField(null=True, blank=True)
    rr_intervals = models.JSONField(
        default=list,
        blank=True,
        help_text='Optional raw R-R intervals (ms); empty for privacy-min uploads.',
    )
    capture_duration_s = models.FloatField(null=True, blank=True)
    frame_rate = models.FloatField(null=True, blank=True)
    captured_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = 'heartbeat_readings'
        ordering = ['-captured_at']


class HeartbeatEvent(models.Model):
    """Forensic log row for every verify/duress decision."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session = models.ForeignKey(
        HeartbeatSession,
        on_delete=models.CASCADE,
        related_name='events',
    )
    decision = models.CharField(
        max_length=12,
        help_text='allow|deny|duress|reject',
    )
    reason = models.CharField(max_length=64, blank=True, default='')
    ip = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        db_table = 'heartbeat_events'
        ordering = ['-created_at']

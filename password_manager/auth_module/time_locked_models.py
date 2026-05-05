"""
Tier 3 (Self-Time-Locked) recovery models for the Layered Recovery Mesh.

The user's vault DEK recovery seed (`time_seed`) is split with a Shamir
2-of-2 scheme at enrollment:

  - One share is encoded into a `.dlrec` file the user downloads and
    keeps offline.
  - The other share (`server_half`) is held server-side, opaque to the
    server. With Shamir 2-of-2, the server's share is one point on a
    degree-1 polynomial — it is information-theoretically useless
    without the user's local share. A full server-database breach
    therefore yields nothing on its own.

The server's only powers are:
  1. Refusing to release its share before `release_after`, enforcing the
     time-lock delay (default 7 days, modulated 3-14 by the trust-score
     modulator).
  2. Sending periodic canary alerts to the user's email/SMS during the
     delay window so a legitimate account-holder can cancel an attacker-
     initiated recovery via `canary_ack_token`.

Recovery flow:
  enroll  -> store server_half + half_metadata
  initiate-> set release_after, canary_state=ALERTING, send canary
  release -> if now < release_after: refuse + log 'too_early'
             if canary_state=ACKNOWLEDGED: refuse + log 'cancelled_by_canary'
             else: return server_half (one-shot), set canary_state=EXPIRED
  ack     -> sets canary_state=ACKNOWLEDGED, is_active=False (kills attempt)

Server never sees the master password, the DEK, or the reconstructed
`time_seed`. Reconstruction happens in the requesting client's browser.
"""
from django.contrib.auth.models import User
from django.db import models


class TimeLockedRecovery(models.Model):
    """One-active-row-per-user time-locked recovery enrollment.

    `server_half` is opaque Shamir share bytes. The server never inspects
    or 'validates' its mathematical content.
    """

    class CanaryState(models.TextChoices):
        QUIET = 'quiet', 'Quiet (no active recovery)'
        ALERTING = 'alerting', 'Alerting (delay running)'
        ACKNOWLEDGED = 'acknowledged', 'Legitimate user acknowledged'
        EXPIRED = 'expired', 'Released; one-shot consumed'

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='time_locked_recoveries',
    )
    server_half = models.BinaryField()
    half_metadata = models.JSONField(default=dict, blank=True)
    release_after = models.DateTimeField(null=True, blank=True)
    canary_state = models.CharField(
        max_length=16,
        choices=CanaryState.choices,
        default=CanaryState.QUIET,
    )
    last_canary_sent = models.DateTimeField(null=True, blank=True)
    canary_ack_token = models.CharField(max_length=64, blank=True, default='')
    initiated_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    enrolled_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = 'time_locked_recovery'
        # Explicit index names so model state matches the migration —
        # `makemigrations --check` would otherwise see Django's
        # auto-generated names diverge from the names we wrote into
        # 0012_time_locked_recovery.py and produce phantom
        # RemoveIndex/AddIndex diffs.
        indexes = [
            models.Index(fields=['user', 'is_active'], name='tlr_user_active_idx'),
            models.Index(fields=['canary_state', 'last_canary_sent'], name='tlr_canary_idx'),
        ]

    def __str__(self):
        return f'TimeLockedRecovery(user={self.user_id}, active={self.is_active})'


class ServerHalfReleaseLog(models.Model):
    """Append-only forensics log of every release attempt against a
    `TimeLockedRecovery` row. Used for ZK audit and anomaly review."""

    recovery = models.ForeignKey(
        TimeLockedRecovery,
        on_delete=models.CASCADE,
        related_name='release_log',
    )
    attempted_at = models.DateTimeField(auto_now_add=True)
    succeeded = models.BooleanField(default=False)
    refusal_reason = models.CharField(max_length=64, blank=True, default='')
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=255, blank=True, default='')

    class Meta:
        db_table = 'server_half_release_log'
        indexes = [
            models.Index(
                fields=['recovery', 'attempted_at'],
                name='shrl_recovery_attempted_idx',
            ),
        ]

    def __str__(self):
        outcome = 'OK' if self.succeeded else (self.refusal_reason or 'refused')
        return f'ServerHalfReleaseLog(recovery={self.recovery_id}, {outcome})'

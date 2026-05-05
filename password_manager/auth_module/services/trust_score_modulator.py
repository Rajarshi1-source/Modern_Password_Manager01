"""
Trust-score modulator for recovery timing.

This module never derives or unwraps any key. It only adjusts:
  - Tier 3 (time-locked) delay: 3 to 14 days
  - Tier 2 (social mesh) threshold: base +/- 1
based on the behavioral match score (float in [0.0, 1.0]).
"""
from __future__ import annotations

MIN_DELAY_DAYS = 3
MAX_DELAY_DAYS = 14
DEFAULT_DELAY_DAYS = 7

DEFAULT_CANARY_HOURS = 24
SUSPICIOUS_CANARY_HOURS = 6
ELEVATED_CANARY_HOURS = 12

HIGH_TRUST_THRESHOLD = 0.8
LOW_TRUST_THRESHOLD = 0.2
ELEVATED_TRUST_THRESHOLD = 0.5

# Absolute floor for any social-mesh threshold. Single-guardian
# configurations (threshold=1, total=1) are valid in the existing
# recovery flow (see quantum_recovery_views: it can set
# guardian_approvals_required = min(2, len(active_guardians)) which
# falls to 1 when only one active guardian exists), so the modulator
# must accept and pass them through untouched.
MIN_THRESHOLD = 1


def _coerce_score(behavioral_match_score):
    """Return a float score in [0.0, 1.0] or None if invalid/out-of-range."""
    if behavioral_match_score is None:
        return None
    try:
        s = float(behavioral_match_score)
    except (TypeError, ValueError):
        return None
    if not (0.0 <= s <= 1.0):
        return None
    return s


def compute_time_lock_delay_days(behavioral_match_score):
    """Map behavioral match score to a time-lock delay in days.

    Higher score -> shorter delay (down to MIN_DELAY_DAYS).
    Invalid/missing score -> DEFAULT_DELAY_DAYS.
    """
    s = _coerce_score(behavioral_match_score)
    if s is None:
        return DEFAULT_DELAY_DAYS
    delay = MAX_DELAY_DAYS - s * (MAX_DELAY_DAYS - MIN_DELAY_DAYS)
    # round() returns int when called without ndigits in Python 3;
    # the explicit int() cast is redundant (Ruff RUF046).
    return max(MIN_DELAY_DAYS, min(MAX_DELAY_DAYS, round(delay)))


def compute_social_mesh_threshold(base_threshold, total_guardians, behavioral_match_score):
    """Adjust the social-mesh approval threshold by +/- 1 based on score.

    Clamped to [MIN_THRESHOLD, total_guardians]. Raises ValueError on invalid args.

    Single-guardian configurations (base_threshold == total_guardians == 1)
    are valid and are returned unchanged: with only one guardian there is
    no headroom to modulate, and the recovery flow already allows this
    case via ``min(2, len(active_guardians))``.
    """
    if base_threshold < MIN_THRESHOLD or total_guardians < MIN_THRESHOLD:
        raise ValueError(
            f'threshold and total_guardians must each be >= {MIN_THRESHOLD}'
        )
    if base_threshold > total_guardians:
        raise ValueError('base_threshold cannot exceed total_guardians')

    target = base_threshold
    s = _coerce_score(behavioral_match_score)
    if s is not None:
        if s >= HIGH_TRUST_THRESHOLD:
            target = base_threshold - 1
        elif s <= LOW_TRUST_THRESHOLD:
            target = base_threshold + 1

    return max(MIN_THRESHOLD, min(total_guardians, target))


def canary_alert_frequency_hours(behavioral_match_score):
    """Return canary alert cadence in hours; lower score -> more frequent alerts."""
    s = _coerce_score(behavioral_match_score)
    if s is None:
        return DEFAULT_CANARY_HOURS
    if s <= LOW_TRUST_THRESHOLD:
        return SUSPICIOUS_CANARY_HOURS
    if s <= ELEVATED_TRUST_THRESHOLD:
        return ELEVATED_CANARY_HOURS
    return DEFAULT_CANARY_HOURS

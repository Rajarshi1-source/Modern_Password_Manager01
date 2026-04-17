"""High-level service for the heartbeat_auth HTTP surface.

All user-facing actions (enroll, verify, reset) go through this module.
Internally it delegates to :mod:`feature_matcher`, :mod:`duress_detector`
and :mod:`duress_bridge`.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from django.conf import settings
from django.utils import timezone

from ..models import (
    HeartbeatEvent,
    HeartbeatProfile,
    HeartbeatReading,
    HeartbeatSession,
    ProfileStatus,
    SessionStatus,
    SessionType,
)
from . import duress_bridge, duress_detector, feature_matcher

logger = logging.getLogger(__name__)

MIN_ENROLLMENTS = 5


def _get_profile(user) -> HeartbeatProfile:
    profile, _ = HeartbeatProfile.objects.get_or_create(user=user)
    return profile


def _ip_from(request) -> Optional[str]:
    if request is None:
        return None
    ip = request.META.get('HTTP_X_FORWARDED_FOR', '').split(',')[0].strip() \
        or request.META.get('REMOTE_ADDR')
    return ip or None


def _reading_from(session: HeartbeatSession, features: Dict[str, Any],
                  extras: Dict[str, Any]) -> HeartbeatReading:
    return HeartbeatReading.objects.create(
        session=session,
        features=dict(features or {}),
        rmssd=features.get('rmssd'),
        sdnn=features.get('sdnn'),
        mean_hr=features.get('mean_hr'),
        lf_hf_ratio=features.get('lf_hf_ratio'),
        pnn50=features.get('pnn50'),
        rr_intervals=extras.get('rr_intervals') or [],
        capture_duration_s=extras.get('capture_duration_s'),
        frame_rate=extras.get('frame_rate'),
    )


def enroll_reading(user, features: Dict[str, Any], extras: Optional[Dict[str, Any]] = None,
                   request=None) -> Dict[str, Any]:
    """Fold a new enrollment reading into the user's baseline.

    Returns a dict describing the profile state after the reading;
    flips ``status`` to ``enrolled`` once ``MIN_ENROLLMENTS`` readings
    have been accepted.
    """
    extras = extras or {}
    profile = _get_profile(user)

    session = HeartbeatSession.objects.create(
        user=user,
        session_type=SessionType.ENROLL,
        status=SessionStatus.PENDING,
    )
    _reading_from(session, features, extras)

    vec = feature_matcher.vector_from_features(features)
    new_mean, new_cov, new_count = feature_matcher.rolling_mean_cov(
        profile.baseline_mean or [0.0] * len(feature_matcher.FEATURE_ORDER),
        profile.baseline_cov or [],
        profile.enrollment_count,
        vec,
    )
    profile.baseline_mean = new_mean
    profile.baseline_cov = new_cov
    profile.enrollment_count = new_count
    profile.baseline_rmssd = features.get('rmssd') \
        if profile.baseline_rmssd is None \
        else (profile.baseline_rmssd * (new_count - 1) + (features.get('rmssd') or 0.0)) / new_count
    profile.baseline_sdnn = features.get('sdnn') \
        if profile.baseline_sdnn is None \
        else (profile.baseline_sdnn * (new_count - 1) + (features.get('sdnn') or 0.0)) / new_count
    profile.baseline_mean_hr = features.get('mean_hr') \
        if profile.baseline_mean_hr is None \
        else (profile.baseline_mean_hr * (new_count - 1) + (features.get('mean_hr') or 0.0)) / new_count

    if profile.enrollment_count >= MIN_ENROLLMENTS:
        profile.status = ProfileStatus.ENROLLED
        if profile.enrolled_at is None:
            profile.enrolled_at = timezone.now()
    else:
        profile.status = ProfileStatus.PENDING
    profile.save()

    session.status = SessionStatus.ALLOWED
    session.completed_at = timezone.now()
    session.save(update_fields=['status', 'completed_at'])
    HeartbeatEvent.objects.create(
        session=session, decision='allow', reason='enroll',
        ip=_ip_from(request),
    )

    return {
        'enrollment_count': profile.enrollment_count,
        'required': MIN_ENROLLMENTS,
        'status': profile.status,
    }


def verify_reading(user, features: Dict[str, Any], extras: Optional[Dict[str, Any]] = None,
                   request=None) -> Dict[str, Any]:
    """Score a verification reading and return ``allow``/``deny``/``duress``."""
    extras = extras or {}
    profile = _get_profile(user)

    session = HeartbeatSession.objects.create(
        user=user,
        session_type=SessionType.VERIFY,
        status=SessionStatus.PENDING,
    )
    _reading_from(session, features, extras)

    if profile.status != ProfileStatus.ENROLLED:
        session.status = SessionStatus.REJECTED
        session.completed_at = timezone.now()
        session.save(update_fields=['status', 'completed_at'])
        HeartbeatEvent.objects.create(
            session=session, decision='reject', reason='not_enrolled',
            ip=_ip_from(request),
        )
        return {
            'match': False,
            'score': 0.0,
            'duress': False,
            'decision': 'not_enrolled',
            'session_id': str(session.id),
        }

    match_info = feature_matcher.match(profile, features)
    score = match_info['score']

    duress_enabled = bool(getattr(settings, 'HEARTBEAT_DURESS_ENABLED', True))
    duress_info = {'duress': False, 'probability': 0.0}
    if duress_enabled and score >= profile.match_threshold:
        duress_info = duress_detector.detect(profile, features)

    decoy_payload = None
    if duress_info.get('duress'):
        decision = 'duress'
        session.status = SessionStatus.DURESS
        session.duress_detected = True
        session.duress_probability = duress_info.get('probability', 0.0)
        decoy_payload = duress_bridge.maybe_activate_duress(user, request=request,
                                                            probability=duress_info.get('probability', 0.0))
        HeartbeatEvent.objects.create(
            session=session, decision='duress', reason='hrv_stress',
            ip=_ip_from(request),
        )
    elif score >= profile.match_threshold:
        decision = 'allow'
        session.status = SessionStatus.ALLOWED
        HeartbeatEvent.objects.create(
            session=session, decision='allow', reason='match',
            ip=_ip_from(request),
        )
    else:
        decision = 'deny'
        session.status = SessionStatus.DENIED
        HeartbeatEvent.objects.create(
            session=session, decision='deny', reason='below_threshold',
            ip=_ip_from(request),
        )

    session.match_score = float(score)
    session.completed_at = timezone.now()
    session.save(update_fields=[
        'match_score', 'status', 'duress_detected',
        'duress_probability', 'completed_at',
    ])

    return {
        'match': decision in ('allow', 'duress'),
        'decision': decision,
        'score': float(score),
        'threshold': float(profile.match_threshold),
        'duress': bool(duress_info.get('duress')),
        'duress_probability': float(duress_info.get('probability', 0.0)),
        'decoy_vault': decoy_payload,
        'session_id': str(session.id),
    }


def get_profile_dict(user) -> Dict[str, Any]:
    profile = _get_profile(user)
    return {
        'status': profile.status,
        'enrollment_count': profile.enrollment_count,
        'required': MIN_ENROLLMENTS,
        'enrolled_at': profile.enrolled_at.isoformat() if profile.enrolled_at else None,
        'match_threshold': profile.match_threshold,
        'duress_rmssd_sigma': profile.duress_rmssd_sigma,
    }


def reset(user) -> None:
    """Wipe the profile and all readings. Requires re-enrollment."""
    HeartbeatSession.objects.filter(user=user).delete()
    try:
        profile = HeartbeatProfile.objects.get(user=user)
    except HeartbeatProfile.DoesNotExist:
        return
    profile.baseline_mean = []
    profile.baseline_cov = []
    profile.baseline_rmssd = None
    profile.baseline_sdnn = None
    profile.baseline_mean_hr = None
    profile.enrollment_count = 0
    profile.enrolled_at = None
    profile.status = ProfileStatus.RESET
    profile.save()

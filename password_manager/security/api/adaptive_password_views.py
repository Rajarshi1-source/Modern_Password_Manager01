"""
Adaptive Password API Views
===========================

REST API endpoints for adaptive password feature.

Endpoints:
- POST /adaptive/enable/
- POST /adaptive/record-session/
- POST /adaptive/suggest-adaptation/
- POST /adaptive/apply-adaptation/
- POST /adaptive/rollback/
- GET /adaptive/profile/
- GET /adaptive/history/
- DELETE /adaptive/data/
"""

from functools import wraps

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.conf import settings
from django.db import transaction
from django.utils import timezone

import logging

from ..services.adaptive_password_service import AdaptivePasswordService
from ..models import (
    AdaptivePasswordConfig,
    UserTypingProfile,
    TypingSession,
    PasswordAdaptation,
)
from ..serializers.adaptive_serializers import (
    TypingSessionInputV2Serializer,
    ApplyAdaptationV2Serializer,
    PreferenceModelSerializer,
)

logger = logging.getLogger(__name__)


# =============================================================================
# Feature flag
# =============================================================================

def require_adaptive_enabled(view_func):
    """Gate a view on ``settings.ADAPTIVE_PASSWORD['ENABLED']`` (503 when off).

    Until now the flag was defined but read by no view, so the deployment-level
    kill switch did nothing — ``/adaptive/enable/`` succeeded with the feature
    "disabled". Applied *inside* ``@api_view`` so the returned Response is still
    finalized by DRF's content negotiation.

    Fail-closed: a missing ``ADAPTIVE_PASSWORD`` block reads as disabled. The
    setting ships in ``settings/base.py``, so absence means someone stripped it
    deliberately and the safe reading of that is "off".
    """

    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if not getattr(settings, 'ADAPTIVE_PASSWORD', {}).get('ENABLED', False):
            return Response(
                {
                    'error': 'Adaptive passwords are disabled on this deployment.',
                    'code': 'feature_disabled',
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        return view_func(request, *args, **kwargs)

    return _wrapped


def _current_fp_key_version(user):
    """Return the user's current fingerprint key era, or ``None`` if unconfigured.

    ``None`` is a deliberate, distinct signal to
    :class:`FingerprintKeyVersionMixin`: it means "no config", which the
    service's opt-in gate reports as a 400. It is NOT the same as the context
    key being absent, which means "the view forgot" and fails closed with a 409.
    """
    return AdaptivePasswordConfig.objects.filter(user=user).values_list(
        'fp_key_version', flat=True
    ).first()


def _auto_apply_threshold():
    """Confidence a suggestion must clear before the client may auto-apply it.

    Read from ``settings.ADAPTIVE_PASSWORD['AUTO_APPLY_THRESHOLD']`` (0.9) —
    stored and admin-displayed since the feature's first version but, like
    ``auto_apply_high_confidence`` itself, never acted on (plan §0.2 gap B5).
    Published on ``/adaptive/config/`` so the client applies the deployment's
    threshold rather than a duplicated literal that could drift from it.

    Fail-safe rather than fail-closed: a missing or non-numeric setting reads as
    1.0, i.e. "nothing is confident enough to auto-apply". Defaulting to a low
    number here would silently auto-rotate credentials on a misconfigured
    deployment, which is the exact opposite of what an unset value should mean.
    """
    raw = getattr(settings, 'ADAPTIVE_PASSWORD', {}).get('AUTO_APPLY_THRESHOLD', 1.0)
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return 1.0
    if not 0.0 <= value <= 1.0:
        return 1.0
    return value


def _service_error_response(result):
    """Map a service-layer ``{'error': ...}`` dict to a status code.

    ``fp_key_era_changed`` (the TOCTOU close in ``record_typing_session_v2`` /
    ``apply_adaptation_v2``, for a rotation that commits between the
    serializer's era validation and the service's write) gets the same 409 as
    :class:`FingerprintKeyEraMismatch`, so the client's existing "409 → re-fetch
    config, re-derive, retry" handling covers this path too. Everything else
    (opt-in gate failures, not-found, etc.) stays 400, matching prior behavior.
    """
    code = status.HTTP_409_CONFLICT if result.get('code') == 'fp_key_era_changed' else status.HTTP_400_BAD_REQUEST
    return Response(result, status=code)


# =============================================================================
# Configuration Endpoints
# =============================================================================

@api_view(['POST'])
@permission_classes([IsAuthenticated])
@require_adaptive_enabled
def enable_adaptive_passwords(request):
    """
    Enable adaptive passwords for the user (opt-in).

    Returns the non-secret ``fingerprint_salt`` the client needs to derive its
    fingerprint key (see cryptoService.deriveFingerprintKey) plus the current
    ``fp_key_version``.

    Request body:
    {
        "consent": true,
        "consent_version": "1.0",
        "suggestion_frequency_days": 30,
        "allow_centralized_training": true,
        "allow_federated_learning": false
    }
    """
    user = request.user
    data = request.data

    # Require explicit consent
    if not data.get('consent'):
        return Response(
            {'error': 'Explicit consent required to enable adaptive passwords'},
            status=status.HTTP_400_BAD_REQUEST
        )

    # Bound the two numeric fields to the ranges documented on the model
    # (AdaptivePasswordConfig.suggestion_frequency_days / .differential_privacy_epsilon
    # help_text: 1-365 / 0.1-1.0). update_or_create() below writes straight to the
    # DB with no full_clean(), so nothing else stops a caller-supplied 0, a
    # negative number, or a 99 from being persisted.
    try:
        frequency_days = int(data.get('suggestion_frequency_days', 30))
        epsilon = float(data.get('differential_privacy_epsilon', 0.5))
    except (TypeError, ValueError):
        return Response(
            {'error': 'suggestion_frequency_days and differential_privacy_epsilon must be numeric'},
            status=status.HTTP_400_BAD_REQUEST,
        )
    if not 1 <= frequency_days <= 365 or not 0.1 <= epsilon <= 1.0:
        return Response(
            {
                'error': (
                    'suggestion_frequency_days must be 1-365 and '
                    'differential_privacy_epsilon must be 0.1-1.0'
                )
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    consent_fields = {
        'is_enabled': True,
        'consent_given_at': timezone.now(),
        'consent_version': data.get('consent_version', '1.0'),
        'suggestion_frequency_days': frequency_days,
        'allow_centralized_training': data.get('allow_centralized_training', True),
        'allow_federated_learning': data.get('allow_federated_learning', False),
        'differential_privacy_epsilon': epsilon,
    }

    with transaction.atomic():
        # `create_defaults` (Django 5.0+) mints the salt in the INSERT itself, so
        # a freshly created config is never observable without one.
        config, created = AdaptivePasswordConfig.objects.update_or_create(
            user=user,
            defaults=consent_fields,
            create_defaults={
                **consent_fields,
                'fingerprint_salt': AdaptivePasswordConfig.new_fingerprint_salt(),
            },
        )

        # An UPDATE path (re-enable, or a row created through the admin) may
        # still lack a salt. Mint it under a row lock: two concurrent /enable/
        # calls minting different salts would silently orphan every fingerprint
        # the losing client had already derived.
        if not config.fingerprint_salt:
            config = AdaptivePasswordConfig.objects.select_for_update().get(pk=config.pk)
            if not config.fingerprint_salt:
                config.ensure_fingerprint_salt()
                config.save(update_fields=['fingerprint_salt', 'updated_at'])

    # Initialize typing profile if needed
    UserTypingProfile.objects.get_or_create(
        user=user,
        defaults={
            'preferred_substitutions': {},
            'substitution_confidence': {},
            'error_prone_positions': {},
        }
    )

    logger.info(f"User {user.id} enabled adaptive passwords")

    return Response({
        'success': True,
        'enabled': True,
        'created': created,
        'consent_given_at': config.consent_given_at.isoformat(),
        # Non-secret: seeds the CLIENT-side Argon2id KDF whose password is the
        # master password, which the server never receives.
        'fingerprint_salt': config.fingerprint_salt,
        'fp_key_version': config.fp_key_version,
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def disable_adaptive_passwords(request):
    """
    Disable adaptive passwords and optionally delete data.

    Deliberately NOT behind @require_adaptive_enabled: opting out and erasing
    data are GDPR rights that must survive the deployment kill switch being
    flipped off. Same for /adaptive/data/ (erasure) and /adaptive/export/
    (portability). Everything on the active learning surface IS gated.

    Request body:
    {
        "delete_data": false
    }
    """
    user = request.user
    delete_data = request.data.get('delete_data', False)
    
    try:
        config = AdaptivePasswordConfig.objects.get(user=user)
        config.is_enabled = False
        config.save()
    except AdaptivePasswordConfig.DoesNotExist:
        pass
    
    result = {'success': True, 'enabled': False}
    
    if delete_data:
        service = AdaptivePasswordService(user)
        counts = service.delete_all_data()
        result['deleted'] = counts
    
    return Response(result)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@require_adaptive_enabled
def get_adaptive_config(request):
    """Get current adaptive password configuration.

    Also the client's source for ``fingerprint_salt`` + ``fp_key_version``,
    which it needs before it can compute any fingerprint at all.
    """
    user = request.user

    try:
        config = AdaptivePasswordConfig.objects.get(user=user)

        if not config.fingerprint_salt:
            # Self-heal: a config can reach this state through the Django admin
            # (security/admin_adaptive.py exposes is_enabled), which never runs
            # the /enable/ minting path. Lock the row so two concurrent reads
            # cannot mint two different salts.
            with transaction.atomic():
                config = AdaptivePasswordConfig.objects.select_for_update().get(
                    pk=config.pk
                )
                if not config.fingerprint_salt:
                    config.ensure_fingerprint_salt()
                    config.save(update_fields=['fingerprint_salt', 'updated_at'])
                    logger.info(
                        'Minted missing adaptive fingerprint salt for user %s', user.id
                    )

        return Response({
            'enabled': config.is_enabled,
            'fingerprint_salt': config.fingerprint_salt,
            'fp_key_version': config.fp_key_version,
            'consent_given_at': config.consent_given_at.isoformat() if config.consent_given_at else None,
            'consent_version': config.consent_version,
            'suggestion_frequency_days': config.suggestion_frequency_days,
            'last_suggestion_at': config.last_suggestion_at.isoformat() if config.last_suggestion_at else None,
            'allow_centralized_training': config.allow_centralized_training,
            'allow_federated_learning': config.allow_federated_learning,
            'differential_privacy_epsilon': config.differential_privacy_epsilon,
            'auto_suggest_enabled': config.auto_suggest_enabled,
            'auto_apply_high_confidence': config.auto_apply_high_confidence,
            'auto_apply_threshold': _auto_apply_threshold(),
            # Phase 5 (plan §5.2, gap B5): the cadence gate. `should_suggest_
            # adaptation()` has existed on the model since the feature's first
            # version and was referenced ONLY by tests, so "gradually morph"
            # was never enforced -- nothing stopped the client offering a
            # suggestion on every unlock. AND-ed with auto_suggest_enabled
            # here rather than left to the client to combine, so a client that
            # reads one field and not the other cannot nag a user who turned
            # suggestions off.
            'should_suggest': (
                config.auto_suggest_enabled and config.should_suggest_adaptation()
            ),
        })
    except AdaptivePasswordConfig.DoesNotExist:
        return Response({
            'enabled': False,
            'configured': False,
        })


# =============================================================================
# Typing Session Endpoints
# =============================================================================

@api_view(['POST'])
@permission_classes([IsAuthenticated])
@require_adaptive_enabled
def record_typing_session(request):
    """
    Record a typing session for pattern learning (zero-knowledge).

    PRIVACY: Only records timing patterns and error positions — never raw
    keystrokes or the actual password. The client sends a keyed fingerprint and
    coarse features; raw-password fields are rejected (422).
    {
        "schema_version": 2,
        "fp_key_version": 1,                 // must match the server's era (409)
        "password_fingerprint": "…",       // client-keyed, opaque to server
        "length_bucket": 3,                  // floor(len/4), not exact length
        "keystroke_timings": [120, 85, ...],
        "backspace_positions": [3, 7],
        "device_type": "desktop",
        "input_method": "keyboard",
        "substitution_classes_used": [{"from": "o", "to": "0"}]  // optional
    }
    """
    user = request.user

    serializer = TypingSessionInputV2Serializer(
        data=request.data,
        context={'fp_key_version': _current_fp_key_version(user)},
    )
    # PlaintextRejected → 422; FingerprintKeyEraMismatch → 409;
    # bad/missing schema_version or fields → 400.
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data
    service = AdaptivePasswordService(user)
    result = service.record_typing_session_v2(
        password_fingerprint=data['password_fingerprint'],
        length_bucket=data['length_bucket'],
        keystroke_timings=data['keystroke_timings'],
        backspace_positions=data.get('backspace_positions', []),
        device_type=data.get('device_type', 'desktop'),
        input_method=data.get('input_method', 'keyboard'),
        substitution_classes_used=data.get('substitution_classes_used') or [],
        success=data.get('success'),
        expected_fp_key_version=data['fp_key_version'],
    )
    if 'error' in result:
        return _service_error_response(result)
    return Response(result)


# =============================================================================
# Adaptation Endpoints
# =============================================================================

@api_view(['POST'])
@permission_classes([IsAuthenticated])
@require_adaptive_enabled
def suggest_adaptation(request):
    """
    Deprecated under zero-knowledge v2 (HTTP 410).

    Server-side suggestion (which required the raw password) has been removed.
    The client instead pulls GET /api/security/adaptive/preference-model/ and
    generates + ranks suggestions locally, so the password never leaves the
    device.
    """
    return Response(
        {
            'error': 'Server-side suggestion is disabled under zero-knowledge v2. '
                     'Fetch the preference model and generate suggestions '
                     'client-side.',
            'code': 'endpoint_deprecated',
            'preference_model': '/api/security/adaptive/preference-model/',
        },
        status=status.HTTP_410_GONE,
    )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@require_adaptive_enabled
def apply_adaptation(request):
    """
    Apply a password adaptation (zero-knowledge).

    Fingerprints + class-level substitutions + masked previews only — raw
    passwords are rejected (422).
    {
        "schema_version": 2,
        "fp_key_version": 1,
        "original_fingerprint": "…",
        "adapted_fingerprint": "…",
        "substitutions": [{"from": "o", "to": "0", "confidence": 0.9}],
        "previews": {"original_masked": "ab***yz", "adapted_masked": "a0***yz"},
        "memorability_improvement": -0.30,
        "memorability_score_before": 0.55,
        "memorability_score_after": 0.24,
        "memorability_driver": "variety"
    }

    The three memorability fields are Phase 4 additions and remain optional: a
    client that omits them records an adaptation exactly as before, with both
    scores left NULL and excluded from `average_memorability_improvement`.
    """
    user = request.user

    serializer = ApplyAdaptationV2Serializer(
        data=request.data,
        context={'fp_key_version': _current_fp_key_version(user)},
    )
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data
    service = AdaptivePasswordService(user)
    result = service.apply_adaptation_v2(
        original_fingerprint=data['original_fingerprint'],
        adapted_fingerprint=data['adapted_fingerprint'],
        substitution_classes=data['substitutions'],
        previews=data.get('previews'),
        memorability_improvement=data.get('memorability_improvement'),
        memorability_score_before=data.get('memorability_score_before'),
        memorability_score_after=data.get('memorability_score_after'),
        memorability_driver=data.get('memorability_driver'),
        expected_fp_key_version=data['fp_key_version'],
    )
    if 'error' in result:
        return _service_error_response(result)
    return Response(result)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@require_adaptive_enabled
def preference_model(request):
    """Export the per-user adaptive preference model (zero-knowledge).

    The client downloads this aggregate model and generates + ranks password
    suggestions locally, replacing the password-POSTing /suggest/ path. The
    response carries only non-reversible learning signals (substitution-class
    weights + memorability params) — never any password-derived data.
    """
    service = AdaptivePasswordService(request.user)
    model = service.export_preference_model()
    serializer = PreferenceModelSerializer(model)
    return Response(serializer.data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@require_adaptive_enabled
def rotate_fingerprint_key(request):
    """Re-base the client fingerprint key and open a new era.

    Call this when the master password changes: the fingerprint key is derived
    from it, so every fingerprint the client computes afterwards differs from
    the previous era's. Rotating explicitly makes that break visible (old rows
    are excluded from history/stats/rollback) instead of leaving the client
    writing fingerprints that silently never match anything.

    Destructive to correlation, so it requires an explicit acknowledgement —
    same shape as the `consent` gate on /adaptive/enable/.

    Request body:
    {
        "confirm": true
    }
    """
    user = request.user

    if not request.data.get('confirm'):
        return Response(
            {
                'error': (
                    'Rotating the fingerprint key resets adaptation history '
                    'correlation. Send {"confirm": true} to proceed.'
                ),
                'code': 'confirmation_required',
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        with transaction.atomic():
            config = AdaptivePasswordConfig.objects.select_for_update().get(user=user)
            new_version = config.rotate_fingerprint_key()
            config.save(
                update_fields=['fingerprint_salt', 'fp_key_version', 'updated_at']
            )
    except AdaptivePasswordConfig.DoesNotExist:
        return Response(
            {'error': 'Adaptive passwords not configured'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    logger.info(
        'User %s rotated the adaptive fingerprint key to era v%s',
        user.id, new_version,
    )

    return Response({
        'success': True,
        'fingerprint_salt': config.fingerprint_salt,
        'fp_key_version': new_version,
        'note': (
            'Re-derive the fingerprint key from the new salt. Prior-era typing '
            'sessions and adaptations are retained for audit but no longer '
            'contribute to history, stats or rollback.'
        ),
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@require_adaptive_enabled
def rollback_adaptation(request):
    """
    Rollback to previous password version.
    
    Request body:
    {
        "adaptation_id": "uuid-of-adaptation"
    }
    """
    user = request.user
    data = request.data
    
    if 'adaptation_id' not in data:
        return Response(
            {'error': 'adaptation_id is required'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    service = AdaptivePasswordService(user)
    result = service.rollback_adaptation(data['adaptation_id'])
    
    if 'error' in result:
        return Response(result, status=status.HTTP_400_BAD_REQUEST)
    
    return Response(result)


# =============================================================================
# Profile and History Endpoints
# =============================================================================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
@require_adaptive_enabled
def get_typing_profile(request):
    """Get user's aggregated typing profile."""
    user = request.user
    
    try:
        profile = UserTypingProfile.objects.get(user=user)
        return Response({
            'has_profile': True,
            'total_sessions': profile.total_sessions,
            'success_rate': profile.success_rate,
            'average_wpm': profile.average_wpm,
            'profile_confidence': profile.profile_confidence,
            'has_sufficient_data': profile.has_sufficient_data(),
            'top_substitutions': profile.get_top_substitutions(5),
            'error_prone_positions': dict(
                sorted(
                    profile.error_prone_positions.items(),
                    key=lambda x: x[1],
                    reverse=True
                )[:5]
            ),
            'last_session_at': profile.last_session_at.isoformat() if profile.last_session_at else None,
        })
    except UserTypingProfile.DoesNotExist:
        return Response({
            'has_profile': False,
        })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@require_adaptive_enabled
def get_adaptation_history(request):
    """Get user's password adaptation history."""
    user = request.user
    
    service = AdaptivePasswordService(user)
    history = service.get_adaptation_history()
    
    return Response({
        'count': len(history),
        'adaptations': history,
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@require_adaptive_enabled
def get_evolution_stats(request):
    """Get evolution statistics for the CURRENT fingerprint key era.

    Scoped like /adaptive/history/: counting rows from a superseded era would
    inflate the user's visible adaptation count with entries whose fingerprints
    no longer correspond to anything they can derive.
    """
    user = request.user

    fp_key_version = _current_fp_key_version(user)
    if fp_key_version is None:
        return Response({
            'active_adaptations': 0,
            'total_adaptations': 0,
            'average_memorability_improvement': 0,
            'total_typing_sessions': 0,
            'overall_success_rate': 0,
        })

    # Get adaptation stats
    adaptations = PasswordAdaptation.objects.filter(
        user=user, fp_key_version=fp_key_version
    )
    active_count = adaptations.filter(status='active').count()
    total_count = adaptations.count()
    
    # Calculate average memorability improvement
    accepted = adaptations.filter(status__in=['active', 'rolled_back'])
    if accepted.exists():
        improvements = [
            (a.memorability_score_after or 0) - (a.memorability_score_before or 0)
            for a in accepted
            if a.memorability_score_before is not None
        ]
        avg_improvement = sum(improvements) / len(improvements) if improvements else 0
    else:
        avg_improvement = 0
    
    # Get session stats
    sessions = TypingSession.objects.filter(user=user, fp_key_version=fp_key_version)
    session_count = sessions.count()
    if session_count > 0:
        success_rate = sessions.filter(success=True).count() / session_count
    else:
        success_rate = 0
    
    return Response({
        'active_adaptations': active_count,
        'total_adaptations': total_count,
        'average_memorability_improvement': avg_improvement,
        'total_typing_sessions': session_count,
        'overall_success_rate': success_rate,
    })


# =============================================================================
# Data Management Endpoints
# =============================================================================

@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_adaptive_data(request):
    """
    Delete all adaptive password data (GDPR compliance).
    
    This is permanent and cannot be undone.
    """
    user = request.user
    
    service = AdaptivePasswordService(user)
    counts = service.delete_all_data()
    
    logger.info(f"User {user.id} deleted all adaptive password data")
    
    return Response({
        'success': True,
        'deleted': counts,
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def export_adaptive_data(request):
    """
    Export all adaptive password data (GDPR data portability).
    
    Returns all user data in JSON format.
    """
    user = request.user
    
    # Get config
    try:
        config = AdaptivePasswordConfig.objects.get(user=user)
        config_data = {
            'is_enabled': config.is_enabled,
            'consent_given_at': config.consent_given_at.isoformat() if config.consent_given_at else None,
            'consent_version': config.consent_version,
            'suggestion_frequency_days': config.suggestion_frequency_days,
            'fp_key_version': config.fp_key_version,
        }
    except AdaptivePasswordConfig.DoesNotExist:
        config_data = None
    
    # Get profile
    try:
        profile = UserTypingProfile.objects.get(user=user)
        profile_data = {
            'total_sessions': profile.total_sessions,
            'success_rate': profile.success_rate,
            'average_wpm': profile.average_wpm,
            'preferred_substitutions': profile.preferred_substitutions,
            'error_prone_positions': profile.error_prone_positions,
            # Phase 4 fields (plan §4.2/§4.4): learned per-user memorability
            # weights and the three profile fields _update_typing_profile
            # populates. Omitting them would make this export stop being a
            # complete GDPR portability record the moment a user's first
            # feedback row lands and the weekly task nudges their weights.
            'memorability_weights': profile.memorability_weights,
            'wpm_variance': profile.wpm_variance,
            'common_error_types': profile.common_error_types,
            'rhythm_signature': profile.rhythm_signature,
        }
    except UserTypingProfile.DoesNotExist:
        profile_data = None
    
    # Get adaptations (limited info for privacy). Deliberately NOT era-scoped:
    # GDPR portability covers everything held about the user, including rows
    # from superseded fingerprint key eras that history/stats now hide.
    adaptations = PasswordAdaptation.objects.filter(user=user)
    adaptations_data = [
        {
            'id': str(a.id),
            'generation': a.adaptation_generation,
            'fp_key_version': a.fp_key_version,
            'type': a.adaptation_type,
            'status': a.status,
            'suggested_at': a.suggested_at.isoformat(),
            'memorability_improvement': (
                (a.memorability_score_after or 0) - (a.memorability_score_before or 0)
            ) if a.memorability_score_before else None,
            'memorability_driver': a.memorability_driver or None,
        }
        for a in adaptations
    ]
    
    return Response({
        'export_date': timezone.now().isoformat(),
        'user_id': user.id,
        'configuration': config_data,
        'typing_profile': profile_data,
        'adaptations': adaptations_data,
        'session_count': TypingSession.objects.filter(user=user).count(),
    })


# =============================================================================
# Feedback Endpoints
# =============================================================================

@api_view(['POST'])
@permission_classes([IsAuthenticated])
@require_adaptive_enabled
def submit_feedback(request):
    """
    Submit feedback for a password adaptation.
    
    Request body:
    {
        "adaptation_id": "uuid-of-adaptation",
        "rating": 4,  // 1-5
        "typing_accuracy_improved": true,
        "memorability_improved": true,
        "typing_speed_improved": null,
        "additional_feedback": "Optional text"
    }
    """
    from ..models import AdaptationFeedback
    
    user = request.user
    data = request.data
    
    # Validate required fields
    if 'adaptation_id' not in data:
        return Response(
            {'error': 'adaptation_id is required'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    if 'rating' not in data:
        return Response(
            {'error': 'rating is required (1-5)'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    rating = data['rating']
    try:
        rating = int(rating)
    except (TypeError, ValueError):
        return Response(
            {'error': 'rating must be an integer between 1 and 5'},
            status=status.HTTP_400_BAD_REQUEST
        )
    if rating < 1 or rating > 5:
        return Response(
            {'error': 'rating must be an integer between 1 and 5'},
            status=status.HTTP_400_BAD_REQUEST
        )

    def _to_bool(value):
        if value is None or value == '':
            return None
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.lower() in ('true', '1', 'yes', 'on')
        return bool(value)
    
    # Find the adaptation
    try:
        adaptation = PasswordAdaptation.objects.get(
            id=data['adaptation_id'],
            user=user
        )
    except PasswordAdaptation.DoesNotExist:
        return Response(
            {'error': 'Adaptation not found'},
            status=status.HTTP_404_NOT_FOUND
        )
    
    # Check if feedback already exists
    if AdaptationFeedback.objects.filter(adaptation=adaptation, user=user).exists():
        return Response(
            {'error': 'Feedback already submitted for this adaptation'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Count sessions since adaptation
    sessions_since = TypingSession.objects.filter(
        user=user,
        created_at__gte=adaptation.decided_at or adaptation.suggested_at
    ).count()
    
    # Create feedback
    feedback = AdaptationFeedback.objects.create(
        adaptation=adaptation,
        user=user,
        rating=rating,
        typing_accuracy_improved=_to_bool(data.get('typing_accuracy_improved')),
        memorability_improved=_to_bool(data.get('memorability_improved')),
        typing_speed_improved=_to_bool(data.get('typing_speed_improved')),
        additional_feedback=data.get('additional_feedback', ''),
        typing_sessions_since=sessions_since,
    )
    
    logger.info(f"User {user.id} submitted feedback for adaptation {adaptation.id}: {rating}/5")
    
    return Response({
        'success': True,
        'feedback_id': str(feedback.id),
        'rating': rating,
        'days_since_adaptation': feedback.days_since_adaptation,
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@require_adaptive_enabled
def get_feedback_for_adaptation(request, adaptation_id):
    """Get feedback for a specific adaptation."""
    from ..models import AdaptationFeedback
    
    user = request.user
    
    try:
        feedback = AdaptationFeedback.objects.get(
            adaptation_id=adaptation_id,
            user=user
        )
        return Response({
            'has_feedback': True,
            'rating': feedback.rating,
            'typing_accuracy_improved': feedback.typing_accuracy_improved,
            'memorability_improved': feedback.memorability_improved,
            'typing_speed_improved': feedback.typing_speed_improved,
            'additional_feedback': feedback.additional_feedback,
            'days_since_adaptation': feedback.days_since_adaptation,
            'created_at': feedback.created_at.isoformat(),
        })
    except AdaptationFeedback.DoesNotExist:
        return Response({
            'has_feedback': False,
        })


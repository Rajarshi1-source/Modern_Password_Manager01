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

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.utils import timezone
from django.conf import settings

import logging

from ..services.adaptive_password_service import AdaptivePasswordService
from ..models import (
    AdaptivePasswordConfig,
    UserTypingProfile,
    TypingSession,
    PasswordAdaptation,
)

logger = logging.getLogger(__name__)


# =============================================================================
# Configuration Endpoints
# =============================================================================

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def enable_adaptive_passwords(request):
    """
    Enable adaptive passwords for the user (opt-in).
    
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
    
    # Create or update config
    config, created = AdaptivePasswordConfig.objects.update_or_create(
        user=user,
        defaults={
            'is_enabled': True,
            'consent_given_at': timezone.now(),
            'consent_version': data.get('consent_version', '1.0'),
            'suggestion_frequency_days': data.get('suggestion_frequency_days', 30),
            'allow_centralized_training': data.get('allow_centralized_training', True),
            'allow_federated_learning': data.get('allow_federated_learning', False),
            'differential_privacy_epsilon': data.get('differential_privacy_epsilon', 0.5),
        }
    )
    
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
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def disable_adaptive_passwords(request):
    """
    Disable adaptive passwords and optionally delete data.
    
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
def get_adaptive_config(request):
    """Get current adaptive password configuration."""
    user = request.user
    
    try:
        config = AdaptivePasswordConfig.objects.get(user=user)
        return Response({
            'enabled': config.is_enabled,
            'consent_given_at': config.consent_given_at.isoformat() if config.consent_given_at else None,
            'consent_version': config.consent_version,
            'suggestion_frequency_days': config.suggestion_frequency_days,
            'last_suggestion_at': config.last_suggestion_at.isoformat() if config.last_suggestion_at else None,
            'allow_centralized_training': config.allow_centralized_training,
            'allow_federated_learning': config.allow_federated_learning,
            'differential_privacy_epsilon': config.differential_privacy_epsilon,
            'auto_suggest_enabled': config.auto_suggest_enabled,
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
def record_typing_session(request):
    """
    Record a typing session for pattern learning.
    
    PRIVACY: Only records timing patterns and error positions,
    never raw keystrokes or actual password.
    
    Request body:
    {
        "password": "actual_password",  // For hashing only, never stored
        "keystroke_timings": [120, 85, ...],  // Inter-key delays in ms
        "backspace_positions": [3, 7],  // Where errors occurred
        "device_type": "desktop",
        "input_method": "keyboard"
    }
    """
    user = request.user
    data = request.data
    
    # Validate required fields
    if 'password' not in data:
        return Response(
            {'error': 'Password required for session recording'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    if 'keystroke_timings' not in data:
        return Response(
            {'error': 'Keystroke timings required'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    service = AdaptivePasswordService(user)
    
    result = service.record_typing_session(
        password=data['password'],
        keystroke_timings=data['keystroke_timings'],
        backspace_positions=data.get('backspace_positions', []),
        device_type=data.get('device_type', 'desktop'),
        input_method=data.get('input_method', 'keyboard'),
    )
    
    if 'error' in result:
        return Response(result, status=status.HTTP_400_BAD_REQUEST)
    
    return Response(result)


# =============================================================================
# Adaptation Endpoints
# =============================================================================

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def suggest_adaptation(request):
    """
    Get password adaptation suggestion.
    
    Request body:
    {
        "password": "current_password",
        "force": false  // Force suggestion even if timing criteria not met
    }
    """
    user = request.user
    data = request.data
    
    if 'password' not in data:
        return Response(
            {'error': 'Password required for adaptation suggestion'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    service = AdaptivePasswordService(user)
    suggestion = service.suggest_adaptation(
        password=data['password'],
        force=data.get('force', False),
    )
    
    if suggestion is None:
        return Response({
            'has_suggestion': False,
            'reason': 'No improvement found or insufficient data',
        })
    
    return Response({
        'has_suggestion': True,
        'substitutions': [
            {
                'position': s.position,
                'original_char': s.original_char,
                'suggested_char': s.suggested_char,
                'confidence': s.confidence,
                'reason': s.reason,
            }
            for s in suggestion.substitutions
        ],
        'original_preview': suggestion.original_password_preview,
        'adapted_preview': suggestion.adapted_password_preview,
        'confidence_score': suggestion.confidence_score,
        'memorability_improvement': suggestion.memorability_improvement,
        'adaptation_type': suggestion.adaptation_type,
        'reason': suggestion.reason,
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def apply_adaptation(request):
    """
    Apply a password adaptation.
    
    Request body:
    {
        "original_password": "old_password",
        "adapted_password": "new_password",
        "substitutions": [
            {"position": 3, "from": "o", "to": "0", "confidence": 0.85}
        ]
    }
    """
    user = request.user
    data = request.data
    
    required_fields = ['original_password', 'adapted_password', 'substitutions']
    for field in required_fields:
        if field not in data:
            return Response(
                {'error': f'{field} is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    service = AdaptivePasswordService(user)
    result = service.apply_adaptation(
        original_password=data['original_password'],
        adapted_password=data['adapted_password'],
        substitutions=data['substitutions'],
    )
    
    if 'error' in result:
        return Response(result, status=status.HTTP_400_BAD_REQUEST)
    
    return Response(result)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
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
def get_evolution_stats(request):
    """Get overall evolution statistics for user."""
    user = request.user
    
    # Get adaptation stats
    adaptations = PasswordAdaptation.objects.filter(user=user)
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
    sessions = TypingSession.objects.filter(user=user)
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
        }
    except UserTypingProfile.DoesNotExist:
        profile_data = None
    
    # Get adaptations (limited info for privacy)
    adaptations = PasswordAdaptation.objects.filter(user=user)
    adaptations_data = [
        {
            'id': str(a.id),
            'generation': a.adaptation_generation,
            'type': a.adaptation_type,
            'status': a.status,
            'suggested_at': a.suggested_at.isoformat(),
            'memorability_improvement': (
                (a.memorability_score_after or 0) - (a.memorability_score_before or 0)
            ) if a.memorability_score_before else None,
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
    if not isinstance(rating, int) or rating < 1 or rating > 5:
        return Response(
            {'error': 'rating must be an integer between 1 and 5'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
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
        typing_accuracy_improved=data.get('typing_accuracy_improved'),
        memorability_improved=data.get('memorability_improved'),
        typing_speed_improved=data.get('typing_speed_improved'),
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


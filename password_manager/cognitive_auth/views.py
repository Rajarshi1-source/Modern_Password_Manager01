"""
Cognitive Auth API Views
========================

REST API endpoints for cognitive password verification testing.

@author Password Manager Team
@created 2026-02-07
"""

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.utils import timezone
from datetime import timedelta
import hashlib

from .models import (
    CognitiveProfile, CognitiveSession, CognitiveChallenge,
    ChallengeResponse, PasswordCreationSignature, CognitiveSettings
)
from .services import (
    ChallengeGenerator, ReactionTimeAnalyzer, ImplicitMemoryDetector,
    CognitiveProfileService
)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def start_verification_session(request):
    """
    Start a new cognitive verification session.
    
    POST /api/cognitive/challenge/start/
    
    Request body:
    {
        "password": "the_password_to_verify",
        "vault_item_id": "optional_uuid",
        "context": "login|high_security|recovery|periodic|suspicious",
        "difficulty": "easy|medium|hard"
    }
    """
    password = request.data.get('password')
    if not password:
        return Response(
            {'error': 'Password is required'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    vault_item_id = request.data.get('vault_item_id')
    context = request.data.get('context', 'login')
    difficulty = request.data.get('difficulty', 'medium')
    
    # Get user settings
    try:
        user_settings = CognitiveSettings.objects.get(user=request.user)
        enabled_types = user_settings.get_enabled_challenge_types()
    except CognitiveSettings.DoesNotExist:
        enabled_types = ['scrambled', 'stroop', 'priming', 'partial']
        user_settings = None
    
    # Create session
    session = CognitiveSession.objects.create(
        user=request.user,
        vault_item_id=vault_item_id,
        verification_context=context,
        expires_at=timezone.now() + timedelta(minutes=10),
        device_fingerprint=request.headers.get('X-Device-Fingerprint', ''),
        ip_address=get_client_ip(request),
        user_agent=request.META.get('HTTP_USER_AGENT', ''),
    )
    
    # Generate challenges
    generator = ChallengeGenerator(
        password,
        user_settings={'extended_time_limit': user_settings.extended_time_limit if user_settings else False}
    )
    
    challenges_data = generator.generate_session_challenges(
        challenge_types=enabled_types,
        difficulty=difficulty
    )
    
    # Create challenge records
    for cdata in challenges_data:
        CognitiveChallenge.objects.create(
            session=session,
            challenge_type=cdata['challenge_type'],
            difficulty=cdata['difficulty'],
            sequence_number=cdata['sequence_number'],
            challenge_data=cdata['challenge_data'],
            correct_answer_hash=cdata['correct_answer_hash'],
            time_limit_ms=cdata['time_limit_ms'],
            display_duration_ms=cdata['display_duration_ms'],
        )
    
    session.total_challenges = len(challenges_data)
    session.status = 'in_progress'
    session.started_at = timezone.now()
    session.save()
    
    # Get first challenge
    first_challenge = CognitiveChallenge.objects.filter(
        session=session,
        sequence_number=1
    ).first()
    
    if first_challenge:
        first_challenge.is_presented = True
        first_challenge.presented_at = timezone.now()
        first_challenge.save()
    
    return Response({
        'session_id': str(session.id),
        'total_challenges': session.total_challenges,
        'expires_at': session.expires_at.isoformat(),
        'websocket_url': f'/ws/cognitive/{session.id}/',
        'first_challenge': format_challenge_for_response(first_challenge) if first_challenge else None,
    }, status=status.HTTP_201_CREATED)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def submit_response(request):
    """
    Submit a response to a cognitive challenge.
    
    POST /api/cognitive/challenge/respond/
    
    Request body:
    {
        "session_id": "uuid",
        "challenge_id": "uuid",
        "response": "user_response",
        "client_timestamp": 1234567890123,
        "reaction_time_ms": 850,
        "first_keystroke_ms": 200,
        "total_input_duration_ms": 650,
        "hesitation_count": 0,
        "correction_count": 0
    }
    """
    session_id = request.data.get('session_id')
    challenge_id = request.data.get('challenge_id')
    response_value = request.data.get('response', '')
    
    try:
        session = CognitiveSession.objects.get(id=session_id, user=request.user)
    except CognitiveSession.DoesNotExist:
        return Response(
            {'error': 'Session not found'},
            status=status.HTTP_404_NOT_FOUND
        )
    
    if session.is_expired():
        session.status = 'expired'
        session.save()
        return Response(
            {'error': 'Session expired'},
            status=status.HTTP_410_GONE
        )
    
    try:
        challenge = CognitiveChallenge.objects.get(id=challenge_id, session=session)
    except CognitiveChallenge.DoesNotExist:
        return Response(
            {'error': 'Challenge not found'},
            status=status.HTTP_404_NOT_FOUND
        )
    
    # Check if already responded
    if hasattr(challenge, 'response'):
        return Response(
            {'error': 'Challenge already answered'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Verify response
    response_hash = hashlib.sha256(response_value.encode()).hexdigest()
    is_correct = response_hash == challenge.correct_answer_hash
    
    # Get timing data
    reaction_time_ms = request.data.get('reaction_time_ms', 0)
    
    # Analyze reaction time
    try:
        profile = CognitiveProfile.objects.get(user=request.user)
        baseline = {
            'mean': profile.baseline_reaction_time_mean,
            'std_dev': profile.baseline_reaction_time_std,
        }
    except CognitiveProfile.DoesNotExist:
        baseline = None
    
    analyzer = ReactionTimeAnalyzer(baseline)
    metrics = analyzer.analyze_single_response(
        reaction_time_ms,
        challenge.challenge_type,
        is_correct
    )
    
    # Create response record
    challenge_response = ChallengeResponse.objects.create(
        challenge=challenge,
        response_hash=response_hash,
        is_correct=is_correct,
        reaction_time_ms=reaction_time_ms,
        first_keystroke_ms=request.data.get('first_keystroke_ms'),
        total_input_duration_ms=request.data.get('total_input_duration_ms'),
        hesitation_count=request.data.get('hesitation_count', 0),
        correction_count=request.data.get('correction_count', 0),
        client_timestamp=request.data.get('client_timestamp', 0),
        z_score=metrics.z_score,
        is_anomalous=metrics.is_anomalous,
        confidence_score=metrics.confidence,
    )
    
    # Update session
    session.challenges_completed += 1
    if is_correct:
        session.challenges_passed += 1
    session.save()
    
    # Check if session is complete
    is_complete = session.challenges_completed >= session.total_challenges
    
    result = {
        'is_correct': is_correct,
        'reaction_time_ms': reaction_time_ms,
        'confidence': metrics.confidence,
        'is_anomalous': metrics.is_anomalous,
        'challenges_completed': session.challenges_completed,
        'challenges_passed': session.challenges_passed,
        'is_session_complete': is_complete,
    }
    
    if is_complete:
        # Finalize session
        session_result = finalize_session(session, request.user)
        result['session_result'] = session_result
    else:
        # Get next challenge
        next_challenge = CognitiveChallenge.objects.filter(
            session=session,
            sequence_number=challenge.sequence_number + 1
        ).first()
        
        if next_challenge:
            next_challenge.is_presented = True
            next_challenge.presented_at = timezone.now()
            next_challenge.save()
            result['next_challenge'] = format_challenge_for_response(next_challenge)
    
    return Response(result)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_profile(request):
    """
    Get user's cognitive profile.
    
    GET /api/cognitive/profile/
    """
    profile_service = CognitiveProfileService()
    summary = profile_service.get_profile_summary(request.user)
    
    return Response(summary)


@api_view(['PUT'])
@permission_classes([IsAuthenticated])
def update_settings(request):
    """
    Update cognitive verification settings.
    
    PUT /api/cognitive/settings/
    """
    settings_obj, created = CognitiveSettings.objects.get_or_create(
        user=request.user
    )
    
    # Update fields
    updatable_fields = [
        'enable_scrambled', 'enable_stroop', 'enable_priming', 'enable_partial',
        'preferred_difficulty', 'verify_on_login', 'verify_on_sensitive_actions',
        'periodic_verification_days', 'extended_time_limit', 'high_contrast_mode'
    ]
    
    for field in updatable_fields:
        if field in request.data:
            setattr(settings_obj, field, request.data[field])
    
    settings_obj.save()
    
    return Response({
        'message': 'Settings updated successfully',
        'settings': {
            'enable_scrambled': settings_obj.enable_scrambled,
            'enable_stroop': settings_obj.enable_stroop,
            'enable_priming': settings_obj.enable_priming,
            'enable_partial': settings_obj.enable_partial,
            'preferred_difficulty': settings_obj.preferred_difficulty,
            'verify_on_login': settings_obj.verify_on_login,
            'verify_on_sensitive_actions': settings_obj.verify_on_sensitive_actions,
            'periodic_verification_days': settings_obj.periodic_verification_days,
            'extended_time_limit': settings_obj.extended_time_limit,
            'high_contrast_mode': settings_obj.high_contrast_mode,
            'enabled_types': settings_obj.get_enabled_challenge_types(),
        }
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_settings(request):
    """
    Get cognitive verification settings.
    
    GET /api/cognitive/settings/
    """
    settings_obj, created = CognitiveSettings.objects.get_or_create(
        user=request.user
    )
    
    return Response({
        'enable_scrambled': settings_obj.enable_scrambled,
        'enable_stroop': settings_obj.enable_stroop,
        'enable_priming': settings_obj.enable_priming,
        'enable_partial': settings_obj.enable_partial,
        'preferred_difficulty': settings_obj.preferred_difficulty,
        'verify_on_login': settings_obj.verify_on_login,
        'verify_on_sensitive_actions': settings_obj.verify_on_sensitive_actions,
        'periodic_verification_days': settings_obj.periodic_verification_days,
        'extended_time_limit': settings_obj.extended_time_limit,
        'high_contrast_mode': settings_obj.high_contrast_mode,
        'enabled_types': settings_obj.get_enabled_challenge_types(),
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_history(request):
    """
    Get verification history.
    
    GET /api/cognitive/history/
    """
    limit = int(request.query_params.get('limit', 10))
    
    sessions = CognitiveSession.objects.filter(
        user=request.user
    ).order_by('-created_at')[:limit]
    
    history = []
    for session in sessions:
        history.append({
            'id': str(session.id),
            'context': session.verification_context,
            'status': session.status,
            'total_challenges': session.total_challenges,
            'challenges_passed': session.challenges_passed,
            'overall_score': session.overall_score,
            'creator_probability': session.creator_probability,
            'confidence': session.confidence,
            'created_at': session.created_at.isoformat(),
            'completed_at': session.completed_at.isoformat() if session.completed_at else None,
        })
    
    return Response({
        'sessions': history,
        'total': len(history),
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def start_calibration(request):
    """
    Start a calibration session to establish baseline.
    
    POST /api/cognitive/calibrate/
    """
    password = request.data.get('password')
    if not password:
        return Response(
            {'error': 'Password is required'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Reset profile for recalibration
    profile_service = CognitiveProfileService()
    profile = profile_service.reset_profile(request.user)
    
    # Create calibration session with extra challenges
    session = CognitiveSession.objects.create(
        user=request.user,
        verification_context='periodic',  # Calibration is like periodic
        expires_at=timezone.now() + timedelta(minutes=30),  # Longer for calibration
        device_fingerprint=request.headers.get('X-Device-Fingerprint', ''),
        ip_address=get_client_ip(request),
        user_agent=request.META.get('HTTP_USER_AGENT', ''),
    )
    
    # Generate more challenges for calibration
    generator = ChallengeGenerator(password)
    challenges_data = generator.generate_session_challenges(
        num_challenges=20,  # More for calibration
        difficulty='medium'
    )
    
    for cdata in challenges_data:
        CognitiveChallenge.objects.create(
            session=session,
            challenge_type=cdata['challenge_type'],
            difficulty=cdata['difficulty'],
            sequence_number=cdata['sequence_number'],
            challenge_data=cdata['challenge_data'],
            correct_answer_hash=cdata['correct_answer_hash'],
            time_limit_ms=cdata['time_limit_ms'],
            display_duration_ms=cdata['display_duration_ms'],
        )
    
    session.total_challenges = len(challenges_data)
    session.status = 'in_progress'
    session.started_at = timezone.now()
    session.save()
    
    first_challenge = CognitiveChallenge.objects.filter(
        session=session,
        sequence_number=1
    ).first()
    
    if first_challenge:
        first_challenge.is_presented = True
        first_challenge.presented_at = timezone.now()
        first_challenge.save()
    
    return Response({
        'session_id': str(session.id),
        'is_calibration': True,
        'total_challenges': session.total_challenges,
        'expires_at': session.expires_at.isoformat(),
        'websocket_url': f'/ws/cognitive/{session.id}/',
        'first_challenge': format_challenge_for_response(first_challenge) if first_challenge else None,
        'message': 'Calibration session started. Complete all challenges to establish your baseline.',
    }, status=status.HTTP_201_CREATED)


# Helper functions

def get_client_ip(request):
    """Extract client IP from request."""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        return x_forwarded_for.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')


def format_challenge_for_response(challenge):
    """Format challenge for API response (hide sensitive data)."""
    if not challenge:
        return None
    
    # Don't expose correct_answer_hash
    display_data = dict(challenge.challenge_data)
    
    return {
        'id': str(challenge.id),
        'type': challenge.challenge_type,
        'difficulty': challenge.difficulty,
        'sequence_number': challenge.sequence_number,
        'data': display_data,
        'time_limit_ms': challenge.time_limit_ms,
        'display_duration_ms': challenge.display_duration_ms,
    }


def finalize_session(session, user):
    """Finalize a completed verification session."""
    session.status = 'completed'
    session.completed_at = timezone.now()
    
    # Get all responses
    responses = []
    for challenge in session.challenges.all():
        if hasattr(challenge, 'response'):
            resp = challenge.response
            responses.append({
                'challenge_type': challenge.challenge_type,
                'reaction_time_ms': resp.reaction_time_ms,
                'is_correct': resp.is_correct,
                'hesitation_count': resp.hesitation_count,
                'correction_count': resp.correction_count,
            })
    
    # Analyze session
    analyzer = ReactionTimeAnalyzer()
    analysis = analyzer.analyze_session_responses(responses)
    
    # Detect implicit memory
    try:
        profile = CognitiveProfile.objects.get(user=user)
        profile_data = {
            'baseline_reaction_time_mean': profile.baseline_reaction_time_mean,
            'baseline_reaction_time_std': profile.baseline_reaction_time_std,
        }
    except CognitiveProfile.DoesNotExist:
        profile_data = None
    
    detector = ImplicitMemoryDetector(profile_data)
    detection = detector.detect({}, responses)
    
    # Update session with results
    session.overall_score = analysis.get('accuracy', 0)
    session.confidence = analysis.get('confidence', 0)
    session.creator_probability = detection.creator_probability
    
    if detection.is_creator and session.overall_score >= 0.7:
        session.status = 'passed'
    else:
        session.status = 'failed'
    
    session.save()
    
    # Update profile if passed
    if session.status == 'passed':
        profile_service = CognitiveProfileService()
        profile_service.update_profile_from_responses(user, responses, is_calibration=False)
    
    return {
        'status': session.status,
        'overall_score': session.overall_score,
        'creator_probability': detection.creator_probability,
        'confidence': session.confidence,
        'is_creator': detection.is_creator,
        'explanation': detection.explanation,
        'anomalies': detection.anomalies,
    }

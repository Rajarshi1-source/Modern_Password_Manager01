"""
REST API Views for Behavioral Recovery

Implements the behavioral biometric recovery flow endpoints
"""

from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.throttling import AnonRateThrottle
from rest_framework.response import Response
from rest_framework import status
from django.contrib.auth.models import User
from django.utils import timezone
import logging
import uuid

from .models import (
    BehavioralCommitment,
    BehavioralRecoveryAttempt,
    BehavioralChallenge,
    RecoveryAuditLog
)
from .serializers import (
    BehavioralRecoveryAttemptSerializer,
    BehavioralChallengeSerializer,
    RecoveryInitiateSerializer,
    ChallengeSubmitSerializer,
    RecoveryCompleteSerializer,
    CommitmentSetupSerializer
)
from .services import RecoveryOrchestrator, ChallengeGenerator, CommitmentService
from password_manager.api_utils import success_response, error_response

logger = logging.getLogger(__name__)


@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([AnonRateThrottle])
def initiate_recovery(request):
    """
    Initiate behavioral recovery process
    
    POST /api/behavioral-recovery/initiate/
    Body: { "email": "user@example.com" }
    
    Returns: {
        "attempt_id": "uuid",
        "timeline": {...},
        "first_challenge": {...}
    }
    """
    try:
        serializer = RecoveryInitiateSerializer(data=request.data)
        if not serializer.is_valid():
            return error_response(
                "Invalid request data",
                details=serializer.errors,
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        email = serializer.validated_data['email']
        
        # Find user by email
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            # Don't reveal whether user exists
            return error_response(
                "If an account exists with this email, recovery instructions will be sent",
                status_code=status.HTTP_200_OK
            )
        
        # Check if user has behavioral commitments set up
        commitments = BehavioralCommitment.objects.filter(user=user, is_active=True)
        if not commitments.exists():
            return error_response(
                "Behavioral recovery not set up for this account",
                code="no_commitments",
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        # Initialize recovery orchestrator
        orchestrator = RecoveryOrchestrator()
        recovery_attempt = orchestrator.initiate_recovery(user, request)
        
        # Generate first challenge
        challenge_gen = ChallengeGenerator()
        first_challenge = challenge_gen.generate_challenge(recovery_attempt, 'typing')
        
        # Log the initiation
        RecoveryAuditLog.objects.create(
            recovery_attempt=recovery_attempt,
            event_type='recovery_initiated',
            ip_address=request.META.get('REMOTE_ADDR'),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
            event_data={'email': email}
        )
        
        return success_response(
            data={
                'attempt_id': str(recovery_attempt.attempt_id),
                'timeline': {
                    'expected_days': 5,
                    'challenges_per_day': 4,
                    'total_challenges': recovery_attempt.challenges_total,
                    'expected_completion': recovery_attempt.expected_completion_date.isoformat()
                },
                'first_challenge': BehavioralChallengeSerializer(first_challenge).data
            },
            message="Behavioral recovery initiated. Complete the challenges over the next 5 days."
        )
        
    except Exception as e:
        logger.error(f"Error initiating recovery: {e}", exc_info=True)
        return error_response(
            "Failed to initiate recovery",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([AllowAny])
def get_recovery_status(request, attempt_id):
    """
    Get status of ongoing recovery attempt
    
    GET /api/behavioral-recovery/status/{attempt_id}/
    
    Returns: {
        "stage": "typing_challenge",
        "days_remaining": 3,
        "similarity_score": 0.85,
        "progress": {...}
    }
    """
    try:
        recovery_attempt = BehavioralRecoveryAttempt.objects.get(attempt_id=attempt_id)
        
        serializer = BehavioralRecoveryAttemptSerializer(recovery_attempt)
        
        # Calculate days remaining
        if recovery_attempt.expected_completion_date:
            days_remaining = (recovery_attempt.expected_completion_date - timezone.now()).days
        else:
            days_remaining = None
        
        return success_response(
            data={
                **serializer.data,
                'days_remaining': days_remaining,
                'progress_percentage': (recovery_attempt.challenges_completed / recovery_attempt.challenges_total * 100)
                    if recovery_attempt.challenges_total > 0 else 0
            }
        )
        
    except BehavioralRecoveryAttempt.DoesNotExist:
        return error_response(
            "Recovery attempt not found",
            code="not_found",
            status_code=status.HTTP_404_NOT_FOUND
        )
    except Exception as e:
        logger.error(f"Error getting recovery status: {e}", exc_info=True)
        return error_response(
            "Failed to retrieve recovery status",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([AllowAny])
def submit_challenge(request):
    """
    Submit behavioral challenge response
    
    POST /api/behavioral-recovery/submit-challenge/
    Body: {
        "attempt_id": "uuid",
        "challenge_id": "uuid",
        "behavioral_data": {...}
    }
    
    Returns: {
        "similarity_score": 0.92,
        "passed": true,
        "next_challenge": {...}
    }
    """
    try:
        serializer = ChallengeSubmitSerializer(data=request.data)
        if not serializer.is_valid():
            return error_response(
                "Invalid request data",
                details=serializer.errors,
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        attempt_id = serializer.validated_data['attempt_id']
        challenge_id = serializer.validated_data['challenge_id']
        behavioral_data = serializer.validated_data['behavioral_data']
        
        # Get recovery attempt and challenge
        try:
            recovery_attempt = BehavioralRecoveryAttempt.objects.get(attempt_id=attempt_id)
            challenge = BehavioralChallenge.objects.get(challenge_id=challenge_id)
        except (BehavioralRecoveryAttempt.DoesNotExist, BehavioralChallenge.DoesNotExist):
            return error_response(
                "Recovery attempt or challenge not found",
                status_code=status.HTTP_404_NOT_FOUND
            )
        
        # Use orchestrator to evaluate challenge
        orchestrator = RecoveryOrchestrator()
        result = orchestrator.evaluate_challenge(challenge, behavioral_data)
        
        # Generate next challenge if needed
        next_challenge = None
        if recovery_attempt.status == 'in_progress':
            challenge_gen = ChallengeGenerator()
            next_challenge = challenge_gen.get_next_challenge(recovery_attempt)
        
        return success_response(
            data={
                'similarity_score': result['similarity_score'],
                'passed': result['passed'],
                'overall_similarity': recovery_attempt.overall_similarity,
                'next_challenge': BehavioralChallengeSerializer(next_challenge).data if next_challenge else None,
                'challenges_remaining': recovery_attempt.challenges_total - recovery_attempt.challenges_completed
            },
            message="Challenge evaluated successfully"
        )
        
    except Exception as e:
        logger.error(f"Error submitting challenge: {e}", exc_info=True)
        return error_response(
            "Failed to submit challenge",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([AllowAny])
def complete_recovery(request):
    """
    Complete recovery and reset password
    
    POST /api/behavioral-recovery/complete/
    Body: {
        "attempt_id": "uuid",
        "new_password": "..."
    }
    
    Returns: { "success": true, "new_vault_encrypted": {...} }
    """
    try:
        serializer = RecoveryCompleteSerializer(data=request.data)
        if not serializer.is_valid():
            return error_response(
                "Invalid request data",
                details=serializer.errors,
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        attempt_id = serializer.validated_data['attempt_id']
        new_password = serializer.validated_data['new_password']
        
        # Get recovery attempt
        try:
            recovery_attempt = BehavioralRecoveryAttempt.objects.get(attempt_id=attempt_id)
        except BehavioralRecoveryAttempt.DoesNotExist:
            return error_response(
                "Recovery attempt not found",
                status_code=status.HTTP_404_NOT_FOUND
            )
        
        # Check if similarity threshold met
        if not recovery_attempt.overall_similarity or recovery_attempt.overall_similarity < 0.87:
            return error_response(
                f"Behavioral similarity too low ({recovery_attempt.overall_similarity:.2f}). Required: 0.87",
                code="low_similarity",
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        # Use orchestrator to complete recovery
        orchestrator = RecoveryOrchestrator()
        result = orchestrator.complete_recovery(recovery_attempt, new_password)
        
        # Log completion
        RecoveryAuditLog.objects.create(
            recovery_attempt=recovery_attempt,
            event_type='recovery_completed',
            ip_address=request.META.get('REMOTE_ADDR'),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
            event_data={'similarity_score': recovery_attempt.overall_similarity}
        )
        
        return success_response(
            data=result,
            message="Password recovery completed successfully"
        )
        
    except Exception as e:
        logger.error(f"Error completing recovery: {e}", exc_info=True)
        return error_response(
            "Failed to complete recovery",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def setup_commitments(request):
    """
    Set up behavioral commitments for future recovery
    
    POST /api/behavioral-recovery/setup-commitments/
    Body: { "behavioral_profile": {...} }
    
    Returns: { "commitments_created": 12 }
    """
    try:
        serializer = CommitmentSetupSerializer(data=request.data)
        if not serializer.is_valid():
            return error_response(
                "Invalid request data",
                details=serializer.errors,
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        behavioral_profile = serializer.validated_data['behavioral_profile']
        
        # Use commitment service to create commitments
        commitment_service = CommitmentService()
        commitments = commitment_service.create_commitments(request.user, behavioral_profile)
        
        return success_response(
            data={
                'commitments_created': len(commitments),
                'profile_quality': commitment_service.assess_profile_quality(behavioral_profile)
            },
            message="Behavioral commitments created successfully"
        )
        
    except Exception as e:
        logger.error(f"Error setting up commitments: {e}", exc_info=True)
        return error_response(
            "Failed to set up commitments",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_commitment_status(request):
    """
    Check if user has behavioral commitments set up
    
    GET /api/behavioral-recovery/commitments/status/
    
    Returns: {
        "has_commitments": true,
        "creation_date": "2025-01-01",
        "commitments_count": 12
    }
    """
    try:
        commitments = BehavioralCommitment.objects.filter(user=request.user, is_active=True)
        
        if commitments.exists():
            first_commitment = commitments.order_by('creation_timestamp').first()
            return success_response(
                data={
                    'has_commitments': True,
                    'creation_date': first_commitment.creation_timestamp.date().isoformat(),
                    'commitments_count': commitments.count(),
                    'ready_for_recovery': True
                }
            )
        else:
            return success_response(
                data={
                    'has_commitments': False,
                    'creation_date': None,
                    'commitments_count': 0,
                    'ready_for_recovery': False
                }
            )
            
    except Exception as e:
        logger.error(f"Error getting commitment status: {e}", exc_info=True)
        return error_response(
            "Failed to get commitment status",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([AllowAny])
def get_next_challenge(request, attempt_id):
    """
    Get next challenge for recovery attempt
    
    GET /api/behavioral-recovery/challenges/{attempt_id}/next/
    
    Returns: { "challenge": {...} }
    """
    try:
        recovery_attempt = BehavioralRecoveryAttempt.objects.get(attempt_id=attempt_id)
        
        challenge_gen = ChallengeGenerator()
        next_challenge = challenge_gen.get_next_challenge(recovery_attempt)
        
        if next_challenge:
            return success_response(
                data={'challenge': BehavioralChallengeSerializer(next_challenge).data}
            )
        else:
            return success_response(
                data={'challenge': None},
                message="No more challenges available"
            )
            
    except BehavioralRecoveryAttempt.DoesNotExist:
        return error_response(
            "Recovery attempt not found",
            status_code=status.HTTP_404_NOT_FOUND
        )
    except Exception as e:
        logger.error(f"Error getting next challenge: {e}", exc_info=True)
        return error_response(
            "Failed to get next challenge",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


# ============================================================================
# PHASE 2B.2: METRICS DASHBOARD API ENDPOINTS
# ============================================================================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def recovery_metrics_dashboard(request):
    """
    Get comprehensive recovery metrics for admin dashboard (Phase 2B.2)
    
    GET /api/behavioral-recovery/metrics/dashboard/
    Query params:
        - time_range_days: Number of days to analyze (default: 30)
    
    Returns: {
        "metrics": {...},
        "ab_tests": {...},
        "blockchain": {...},
        "trends": {...}
    }
    
    Permissions: Admin only
    """
    from rest_framework.permissions import IsAdminUser
    
    # Check if user is admin
    if not request.user.is_staff:
        return error_response(
            "Admin access required",
            status_code=status.HTTP_403_FORBIDDEN
        )
    
    try:
        from .analytics.recovery_metrics import RecoveryMetricsCollector
        from .ab_tests.recovery_experiments import get_experiment_results
        from blockchain.models import BlockchainAnchor
        
        # Get time range from query params
        time_range_days = int(request.GET.get('time_range_days', 30))
        
        # Collect metrics
        collector = RecoveryMetricsCollector(time_range_days=time_range_days)
        metrics = collector.get_dashboard_metrics()
        
        # Get A/B test results
        ab_tests = {}
        try:
            for exp_name in ['recovery_time_duration', 'similarity_threshold', 'challenge_frequency']:
                exp_results = get_experiment_results(exp_name)
                if exp_results:
                    ab_tests[exp_name] = exp_results
        except Exception as e:
            logger.warning(f"Could not fetch A/B test results: {e}")
        
        # Get blockchain stats
        blockchain_stats = {
            'total_anchors': BlockchainAnchor.objects.count(),
            'recent_anchors': BlockchainAnchor.objects.filter(
                timestamp__gte=timezone.now() - timezone.timedelta(days=time_range_days)
            ).count(),
            'testnet_anchors': BlockchainAnchor.objects.filter(network='testnet').count(),
            'mainnet_anchors': BlockchainAnchor.objects.filter(network='mainnet').count(),
        }
        
        # Get trending data
        trends = collector.get_trending_metrics(periods=7)
        
        logger.info(f"Admin {request.user.username} accessed metrics dashboard")
        
        return success_response(
            data={
                'metrics': metrics,
                'ab_tests': ab_tests,
                'blockchain': blockchain_stats,
                'trends': trends,
                'generated_at': timezone.now().isoformat()
            },
            message=f"Metrics collected for last {time_range_days} days"
        )
        
    except Exception as e:
        logger.error(f"Error fetching metrics dashboard: {e}", exc_info=True)
        return error_response(
            "Failed to fetch metrics",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def recovery_metrics_summary(request):
    """
    Get key metrics summary (lighter endpoint)
    
    GET /api/behavioral-recovery/metrics/summary/
    
    Returns: {
        "success_rate": 95.5,
        "false_positive_rate": 0.0,
        "nps_score": 42.3,
        "avg_recovery_time": 4.5
    }
    
    Permissions: Admin only
    """
    if not request.user.is_staff:
        return error_response(
            "Admin access required",
            status_code=status.HTTP_403_FORBIDDEN
        )
    
    try:
        from .analytics.recovery_metrics import RecoveryMetricsCollector
        
        collector = RecoveryMetricsCollector(time_range_days=30)
        
        summary = {
            'success_rate': collector.calculate_success_rate(),
            'false_positive_rate': collector.calculate_false_positive_rate(),
            'nps_score': collector.calculate_nps_score(),
            'avg_recovery_time': collector.calculate_avg_recovery_time(),
            'user_satisfaction': collector.calculate_user_satisfaction(),
            'blockchain_verification_rate': collector.calculate_blockchain_verification_rate()
        }
        
        return success_response(data=summary)
        
    except Exception as e:
        logger.error(f"Error fetching metrics summary: {e}", exc_info=True)
        return error_response(
            "Failed to fetch metrics summary",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([AllowAny])
def submit_recovery_feedback(request):
    """
    Submit user feedback after recovery (Phase 2B.2)
    
    POST /api/behavioral-recovery/feedback/
    Body: {
        "attempt_id": "uuid",
        "security_perception": 8,
        "ease_of_use": 9,
        "trust_level": 7,
        "time_perception": 3,
        "nps_rating": 9,
        "feedback_text": "Great experience!"
    }
    
    Returns: { "feedback_id": 123 }
    """
    try:
        from .models import RecoveryFeedback
        
        # Validate required fields
        attempt_id = request.data.get('attempt_id')
        if not attempt_id:
            return error_response("attempt_id is required", status_code=status.HTTP_400_BAD_REQUEST)
        
        # Get recovery attempt
        recovery_attempt = BehavioralRecoveryAttempt.objects.get(attempt_id=attempt_id)
        
        # Check if feedback already exists
        if hasattr(recovery_attempt, 'feedback'):
            return error_response(
                "Feedback already submitted for this recovery",
                status_code=status.HTTP_409_CONFLICT
            )
        
        # Create feedback
        feedback = RecoveryFeedback.objects.create(
            recovery_attempt=recovery_attempt,
            security_perception=request.data.get('security_perception'),
            ease_of_use=request.data.get('ease_of_use'),
            trust_level=request.data.get('trust_level'),
            time_perception=request.data.get('time_perception'),
            nps_rating=request.data.get('nps_rating'),
            feedback_text=request.data.get('feedback_text', '')
        )
        
        logger.info(f"Feedback submitted for recovery {attempt_id}")
        
        return success_response(
            data={'feedback_id': feedback.id},
            message="Thank you for your feedback!"
        )
        
    except BehavioralRecoveryAttempt.DoesNotExist:
        return error_response(
            "Recovery attempt not found",
            status_code=status.HTTP_404_NOT_FOUND
        )
    except Exception as e:
        logger.error(f"Error submitting feedback: {e}", exc_info=True)
        return error_response(
            "Failed to submit feedback",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_ab_test_results(request, experiment_name):
    """
    Get results for a specific A/B test experiment
    
    GET /api/behavioral-recovery/ab-tests/{experiment_name}/results/
    
    Returns: {
        "experiment": "recovery_time_duration",
        "is_active": true,
        "variants": [...]
    }
    
    Permissions: Admin only
    """
    if not request.user.is_staff:
        return error_response(
            "Admin access required",
            status_code=status.HTTP_403_FORBIDDEN
        )
    
    try:
        from .ab_tests.recovery_experiments import get_experiment_results
        
        results = get_experiment_results(experiment_name)
        
        if results:
            return success_response(data=results)
        else:
            return error_response(
                f"Experiment '{experiment_name}' not found",
                status_code=status.HTTP_404_NOT_FOUND
            )
        
    except Exception as e:
        logger.error(f"Error fetching A/B test results: {e}", exc_info=True)
        return error_response(
            "Failed to fetch A/B test results",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_recovery_experiments(request):
    """
    Initialize A/B testing experiments (Admin only, run once)
    
    POST /api/behavioral-recovery/ab-tests/create/
    
    Returns: {
        "created": ["recovery_time_duration", "similarity_threshold", "challenge_frequency"]
    }
    
    Permissions: Admin only
    """
    if not request.user.is_staff:
        return error_response(
            "Admin access required",
            status_code=status.HTTP_403_FORBIDDEN
        )
    
    try:
        from .ab_tests.recovery_experiments import create_recovery_experiments
        
        experiments = create_recovery_experiments()
        
        if experiments:
            return success_response(
                data={'created': list(experiments.keys())},
                message=f"Successfully created {len(experiments)} experiments"
            )
        else:
            return error_response(
                "A/B testing not available",
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE
            )
        
    except Exception as e:
        logger.error(f"Error creating experiments: {e}", exc_info=True)
        return error_response(
            f"Failed to create experiments: {str(e)}",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


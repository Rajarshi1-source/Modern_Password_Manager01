"""
Recovery Orchestrator (Phase 2B.2: A/B Testing Integration)

Manages the behavioral recovery flow with A/B testing support
"""

import logging
from datetime import timedelta
from django.utils import timezone
from django.contrib.auth.hashers import make_password
from ..models import (
    BehavioralRecoveryAttempt,
    BehavioralChallenge,
    RecoveryAuditLog
)
from .commitment_service import CommitmentService
from ..ab_tests.recovery_experiments import (
    get_experiment_variant,
    track_experiment_event,
    AB_TESTING_AVAILABLE
)

logger = logging.getLogger(__name__)


class RecoveryOrchestrator:
    """
    Orchestrates the behavioral recovery process with A/B testing support
    
    Manages:
    - Initiating recovery attempts
    - Evaluating challenges
    - Tracking progress
    - Completing recovery
    - A/B testing experiment assignment and tracking
    """
    
    # Default parameters (can be overridden by A/B tests)
    DEFAULT_RECOVERY_TIMELINE_DAYS = 5
    DEFAULT_CHALLENGES_PER_DAY = 4
    DEFAULT_SIMILARITY_THRESHOLD = 0.87
    
    def __init__(self, user=None):
        """
        Initialize orchestrator with optional A/B testing support
        
        Args:
            user: Django User object (for A/B test assignment)
        """
        self.commitment_service = CommitmentService()
        self.user = user
        self.ab_variants = {}
        
        # Load A/B test variants if user provided and A/B testing available
        if user and AB_TESTING_AVAILABLE:
            self._load_ab_variants()
    
    def _load_ab_variants(self):
        """Load A/B test variants for the user"""
        try:
            # Get variants for all active experiments
            experiments = [
                'recovery_time_duration',
                'similarity_threshold',
                'challenge_frequency'
            ]
            
            for exp_name in experiments:
                variant = get_experiment_variant(self.user.id, exp_name)
                if variant:
                    self.ab_variants[exp_name] = variant
                    logger.info(f"User {self.user.id} assigned to {exp_name}: {variant.name}")
            
        except Exception as e:
            logger.warning(f"Error loading A/B variants: {e}. Using defaults.")
    
    def get_recovery_timeline_days(self):
        """Get recovery timeline days (with A/B test override)"""
        variant = self.ab_variants.get('recovery_time_duration')
        if variant and variant.config.get('days'):
            return variant.config['days']
        return self.DEFAULT_RECOVERY_TIMELINE_DAYS
    
    def get_similarity_threshold(self):
        """Get similarity threshold (with A/B test override)"""
        variant = self.ab_variants.get('similarity_threshold')
        if variant and variant.config.get('threshold'):
            return variant.config['threshold']
        return self.DEFAULT_SIMILARITY_THRESHOLD
    
    def get_challenge_frequency(self):
        """
        Get challenge frequency configuration (with A/B test override)
        
        Returns:
            dict: {challenges_per_day, total_days}
        """
        variant = self.ab_variants.get('challenge_frequency')
        if variant and variant.config.get('challenges_per_day'):
            return {
                'challenges_per_day': variant.config['challenges_per_day'],
                'total_days': variant.config['total_days']
            }
        return {
            'challenges_per_day': self.DEFAULT_CHALLENGES_PER_DAY,
            'total_days': self.DEFAULT_RECOVERY_TIMELINE_DAYS
        }
    
    def initiate_recovery(self, user, request):
        """
        Start a new behavioral recovery attempt (with A/B testing support)
        
        Args:
            user: Django User object
            request: HTTP request object (for IP, user agent, etc.)
        
        Returns:
            BehavioralRecoveryAttempt object
        """
        logger.info(f"Initiating behavioral recovery for user: {user.username}")
        
        # Set user if not already set (for A/B testing)
        if not self.user:
            self.user = user
            if AB_TESTING_AVAILABLE:
                self._load_ab_variants()
        
        # Get A/B test parameters
        recovery_days = self.get_recovery_timeline_days()
        challenge_config = self.get_challenge_frequency()
        similarity_threshold = self.get_similarity_threshold()
        
        # Calculate expected completion date based on A/B test variant
        expected_completion = timezone.now() + timedelta(days=recovery_days)
        
        # Calculate total challenges based on experiment
        total_challenges = challenge_config['challenges_per_day'] * challenge_config['total_days']
        
        # Create recovery attempt with A/B test metadata
        recovery_attempt = BehavioralRecoveryAttempt.objects.create(
            user=user,
            current_stage='initiated',
            status='in_progress',
            expected_completion_date=expected_completion,
            challenges_total=total_challenges,
            ip_address=request.META.get('REMOTE_ADDR'),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
            contact_email=user.email,
            # Store A/B test variants in metadata
            metadata={
                'ab_tests': {
                    'recovery_timeline': self.ab_variants.get('recovery_time_duration', {}).get('name', 'default'),
                    'similarity_threshold': similarity_threshold,
                    'challenge_frequency': self.ab_variants.get('challenge_frequency', {}).get('name', 'default')
                },
                'recovery_config': {
                    'days': recovery_days,
                    'challenges_per_day': challenge_config['challenges_per_day'],
                    'total_challenges': total_challenges
                }
            }
        )
        
        # Track A/B test events
        if AB_TESTING_AVAILABLE:
            for exp_name, variant in self.ab_variants.items():
                track_experiment_event(
                    user_id=user.id,
                    experiment_name=exp_name,
                    variant_name=variant.name,
                    event_type='recovery_initiated',
                    metadata={'attempt_id': str(recovery_attempt.attempt_id)}
                )
        
        logger.info(f"Recovery attempt created: {recovery_attempt.attempt_id} (Timeline: {recovery_days} days, Challenges: {total_challenges})")
        return recovery_attempt
    
    def evaluate_challenge(self, challenge, behavioral_data):
        """
        Evaluate a behavioral challenge response
        
        Args:
            challenge: BehavioralChallenge object
            behavioral_data: Dict with captured behavioral response
        
        Returns:
            dict: Evaluation results
        """
        logger.info(f"Evaluating challenge: {challenge.challenge_id}")
        
        try:
            # Get recovery attempt
            recovery_attempt = challenge.recovery_attempt
            
            # Get user's stored behavioral commitment
            from ..models import BehavioralCommitment
            commitment = BehavioralCommitment.objects.filter(
                user=recovery_attempt.user,
                challenge_type=challenge.challenge_type,
                is_active=True
            ).first()
            
            if not commitment:
                raise ValueError(f"No behavioral commitment found for {challenge.challenge_type}")
            
            # Extract behavioral embedding from response
            # In production, this would use the Transformer model
            current_embedding = self._extract_embedding(behavioral_data)
            
            # Get similarity threshold (with A/B test override)
            similarity_threshold = self.get_similarity_threshold()
            
            # Verify similarity
            similarity_result = self.commitment_service.verify_behavioral_similarity(
                commitment.encrypted_embedding,
                current_embedding,
                threshold=similarity_threshold
            )
            
            # Update challenge
            challenge.user_response = behavioral_data
            challenge.similarity_score = similarity_result['similarity_score']
            challenge.passed = similarity_result['passed']
            challenge.completed_at = timezone.now()
            
            # Calculate time taken
            if challenge.created_at:
                time_taken = (challenge.completed_at - challenge.created_at).total_seconds()
                challenge.time_taken_seconds = int(time_taken)
            
            challenge.save()
            
            # Update recovery attempt progress
            recovery_attempt.challenges_completed += 1
            recovery_attempt.update_similarity_score(
                challenge.challenge_type,
                similarity_result['similarity_score']
            )
            
            # Update stage based on progress
            self._update_recovery_stage(recovery_attempt)
            
            # Log the evaluation
            RecoveryAuditLog.objects.create(
                recovery_attempt=recovery_attempt,
                event_type='challenge_completed' if similarity_result['passed'] else 'challenge_failed',
                event_data={
                    'challenge_type': challenge.challenge_type,
                    'similarity_score': similarity_result['similarity_score'],
                    'passed': similarity_result['passed']
                }
            )
            
            logger.info(f"Challenge evaluated - Similarity: {similarity_result['similarity_score']:.3f}")
            
            return {
                'similarity_score': similarity_result['similarity_score'],
                'passed': similarity_result['passed'],
                'threshold': similarity_result['threshold']
            }
            
        except Exception as e:
            logger.error(f"Error evaluating challenge: {e}", exc_info=True)
            
            # Log the error
            RecoveryAuditLog.objects.create(
                recovery_attempt=challenge.recovery_attempt,
                event_type='challenge_failed',
                event_data={'error': str(e)}
            )
            
            raise
    
    def complete_recovery(self, recovery_attempt, new_password):
        """
        Complete the recovery process and reset password (with A/B testing tracking)
        
        Args:
            recovery_attempt: BehavioralRecoveryAttempt object
            new_password: New master password
        
        Returns:
            dict: Completion results
        """
        logger.info(f"Completing recovery for attempt: {recovery_attempt.attempt_id}")
        
        try:
            # Get similarity threshold (with A/B test override)
            similarity_threshold = self.get_similarity_threshold()
            
            # Verify similarity threshold met
            if not recovery_attempt.overall_similarity or recovery_attempt.overall_similarity < similarity_threshold:
                raise ValueError(f"Similarity threshold not met: {recovery_attempt.overall_similarity} < {similarity_threshold}")
            
            # Update user password
            user = recovery_attempt.user
            user.password = make_password(new_password)
            user.save()
            
            # Mark recovery as completed
            recovery_attempt.status = 'completed'
            recovery_attempt.current_stage = 'completed'
            recovery_attempt.completed_at = timezone.now()
            recovery_attempt.save()
            
            # Track A/B test completion events
            if AB_TESTING_AVAILABLE and self.ab_variants:
                for exp_name, variant in self.ab_variants.items():
                    track_experiment_event(
                        user_id=user.id,
                        experiment_name=exp_name,
                        variant_name=variant.name,
                        event_type='recovery_completed',
                        metadata={
                            'attempt_id': str(recovery_attempt.attempt_id),
                            'completion_time_hours': (
                                recovery_attempt.completed_at - recovery_attempt.started_at
                            ).total_seconds() / 3600,
                            'similarity_score': recovery_attempt.overall_similarity
                        }
                    )
            
            logger.info(f"Password reset successful for user: {user.username}")
            
            return {
                'success': True,
                'user_id': user.id,
                'recovery_completed_at': recovery_attempt.completed_at.isoformat(),
                'ab_test_variants': {k: v.name for k, v in self.ab_variants.items()}
            }
            
        except Exception as e:
            logger.error(f"Error completing recovery: {e}", exc_info=True)
            
            # Mark recovery as failed
            recovery_attempt.status = 'failed'
            recovery_attempt.save()
            
            # Track A/B test failure events
            if AB_TESTING_AVAILABLE and self.ab_variants:
                user = recovery_attempt.user
                for exp_name, variant in self.ab_variants.items():
                    track_experiment_event(
                        user_id=user.id,
                        experiment_name=exp_name,
                        variant_name=variant.name,
                        event_type='recovery_failed',
                        metadata={
                            'attempt_id': str(recovery_attempt.attempt_id),
                            'error': str(e)
                        }
                    )
            
            raise
    
    def _update_recovery_stage(self, recovery_attempt):
        """
        Update the recovery stage based on progress
        
        Args:
            recovery_attempt: BehavioralRecoveryAttempt object
        """
        challenges_completed = recovery_attempt.challenges_completed
        
        if challenges_completed >= 20:
            recovery_attempt.current_stage = 'verification'
        elif challenges_completed >= 15:
            recovery_attempt.current_stage = 'navigation_challenge'
        elif challenges_completed >= 10:
            recovery_attempt.current_stage = 'cognitive_challenge'
        elif challenges_completed >= 5:
            recovery_attempt.current_stage = 'mouse_challenge'
        else:
            recovery_attempt.current_stage = 'typing_challenge'
        
        recovery_attempt.save()
    
    def _extract_embedding(self, behavioral_data):
        """
        Extract behavioral embedding from raw data
        
        In production, this would use the Transformer model to convert
        247-dimensional behavioral data into 128-dimensional embedding
        
        Args:
            behavioral_data: Dict with raw behavioral data
        
        Returns:
            List: 128-dimensional embedding
        """
        # Placeholder: In production, use actual Transformer model
        # For now, create a dummy 128-dim embedding
        import hashlib
        import json
        
        # Create deterministic hash-based embedding for testing
        data_str = json.dumps(behavioral_data, sort_keys=True)
        hash_obj = hashlib.sha512(data_str.encode())
        hash_bytes = hash_obj.digest()
        
        # Convert to 128 floats in range [0, 1]
        embedding = [float(b) / 255.0 for b in hash_bytes[:128]]
        
        return embedding


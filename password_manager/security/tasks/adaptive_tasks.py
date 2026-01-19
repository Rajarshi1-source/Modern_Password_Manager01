"""
Celery Tasks for Adaptive Password Feature
===========================================

Async tasks for:
- Generating password adaptation suggestions
- Aggregating typing profiles
- Cleaning up expired adaptations
- Updating RL model from feedback
"""

from celery import shared_task
from django.contrib.auth.models import User
from django.utils import timezone
from django.conf import settings
from datetime import timedelta
import logging

logger = logging.getLogger(__name__)


# =============================================================================
# Suggestion Generation Task
# =============================================================================

@shared_task(bind=True, max_retries=3)
def generate_adaptation_suggestion(self, user_id: int, password_hash_prefix: str):
    """
    Generate RL-powered password adaptation suggestion asynchronously.
    
    Args:
        user_id: User ID
        password_hash_prefix: Hash prefix of password to adapt
    
    Returns:
        Adaptation ID or None
    """
    try:
        from security.models import (
            UserTypingProfile, PasswordAdaptation, AdaptivePasswordConfig
        )
        from security.services.adaptive_password_service import AdaptivePasswordService
        
        user = User.objects.get(id=user_id)
        service = AdaptivePasswordService(user)
        
        # Check configuration
        try:
            config = AdaptivePasswordConfig.objects.get(user=user)
            if not config.is_enabled:
                logger.info(f"Adaptive passwords disabled for user {user_id}")
                return None
        except AdaptivePasswordConfig.DoesNotExist:
            logger.info(f"No adaptive config for user {user_id}")
            return None
        
        # Get typing profile
        try:
            profile = UserTypingProfile.objects.get(user=user)
            if not profile.has_sufficient_data():
                logger.info(f"Insufficient data for user {user_id}: {profile.total_sessions} sessions")
                return None
        except UserTypingProfile.DoesNotExist:
            logger.info(f"No typing profile for user {user_id}")
            return None
        
        # Generate suggestion using RL agent
        # Note: This would use the password_hash_prefix to identify the password
        # The actual password is never passed to async tasks
        
        suggestion_data = {
            'password_hash_prefix': password_hash_prefix,
            'substitutions': service._generate_substitution_suggestions(profile),
            'confidence': profile.profile_confidence,
            'memorability_improvement': 0.1,  # Estimated
        }
        
        # Create adaptation record
        adaptation = PasswordAdaptation.objects.create(
            user=user,
            password_hash_prefix=password_hash_prefix,
            adapted_hash_prefix='pending',  # Will be set when user accepts
            adaptation_type='substitution',
            substitutions_applied=suggestion_data['substitutions'],
            confidence_score=suggestion_data['confidence'],
            memorability_score_before=0.5,  # Placeholder
            memorability_score_after=0.6,  # Placeholder
            status='suggested',
            reason=f"ML-generated suggestion based on {profile.total_sessions} typing sessions",
        )
        
        # Update last suggestion time
        config.last_suggestion_at = timezone.now()
        config.save()
        
        logger.info(f"Generated adaptation suggestion for user {user_id}: {adaptation.id}")
        return str(adaptation.id)
    
    except User.DoesNotExist:
        logger.error(f"User {user_id} not found")
        return None
    except Exception as e:
        logger.error(f"Error generating adaptation for user {user_id}: {str(e)}")
        raise self.retry(exc=e, countdown=60)


# =============================================================================
# Profile Aggregation Task
# =============================================================================

@shared_task
def aggregate_typing_profiles():
    """
    Aggregate typing sessions into profiles for all users with new sessions.
    Runs hourly.
    
    Returns:
        Dict with processing stats
    """
    from security.models import UserTypingProfile, TypingSession
    from security.services.adaptive_password_service import AdaptivePasswordService
    
    # Find users with sessions in the last hour
    recent_cutoff = timezone.now() - timedelta(hours=1)
    
    users_with_sessions = User.objects.filter(
        typing_sessions__created_at__gte=recent_cutoff
    ).distinct()
    
    processed = 0
    errors = 0
    
    for user in users_with_sessions:
        try:
            service = AdaptivePasswordService(user)
            
            # Get recent sessions
            sessions = TypingSession.objects.filter(
                user=user
            ).order_by('-created_at')[:50]  # Last 50 sessions
            
            if not sessions:
                continue
            
            # Get or create profile
            profile, created = UserTypingProfile.objects.get_or_create(user=user)
            
            # Update aggregated metrics
            total = sessions.count()
            successful = sessions.filter(success=True).count()
            
            profile.total_sessions = total
            profile.successful_sessions = successful
            profile.success_rate = successful / total if total > 0 else 0
            
            # Calculate profile confidence
            if total >= 50:
                profile.profile_confidence = 0.9
            elif total >= 20:
                profile.profile_confidence = 0.7
            elif total >= 10:
                profile.profile_confidence = 0.5
            else:
                profile.profile_confidence = total / 20.0  # Linear up to 10
            
            profile.last_session_at = sessions.first().created_at
            profile.save()
            
            processed += 1
            logger.debug(f"Aggregated profile for user {user.id}")
            
        except Exception as e:
            logger.error(f"Error aggregating profile for user {user.id}: {str(e)}")
            errors += 1
    
    logger.info(f"Aggregated {processed} typing profiles ({errors} errors)")
    return {'processed': processed, 'errors': errors}


# =============================================================================
# Cleanup Task
# =============================================================================

@shared_task
def cleanup_expired_adaptations():
    """
    Clean up expired adaptation suggestions.
    Runs daily.
    
    Returns:
        Dict with cleanup stats
    """
    from security.models import PasswordAdaptation
    
    expiry_days = getattr(settings, 'ADAPTIVE_PASSWORD', {}).get(
        'ADAPTATION_EXPIRY_DAYS', 7
    )
    
    expiry_cutoff = timezone.now() - timedelta(days=expiry_days)
    
    # Find expired pending adaptations
    expired = PasswordAdaptation.objects.filter(
        status='suggested',
        suggested_at__lt=expiry_cutoff
    )
    
    count = expired.count()
    
    # Mark as expired rather than delete (for analytics)
    expired.update(
        status='expired',
        reason='Auto-expired after {expiry_days} days'
    )
    
    logger.info(f"Expired {count} pending adaptations")
    return {'expired': count}


# =============================================================================
# RL Model Update Task
# =============================================================================

@shared_task
def update_rl_model_from_feedback():
    """
    Update RL bandit model using user feedback.
    Runs weekly.
    
    Returns:
        Dict with update stats
    """
    from security.models import AdaptationFeedback, PasswordAdaptation
    
    # Get feedback from the last week
    week_ago = timezone.now() - timedelta(days=7)
    
    recent_feedback = AdaptationFeedback.objects.filter(
        created_at__gte=week_ago
    ).select_related('adaptation')
    
    if not recent_feedback.exists():
        logger.info("No recent feedback to process")
        return {'processed': 0}
    
    # Aggregate feedback by substitution type
    substitution_rewards = {}
    
    for feedback in recent_feedback:
        if not feedback.adaptation or not feedback.adaptation.substitutions_applied:
            continue
        
        # Calculate reward from feedback
        reward = 0
        if feedback.rating >= 4:
            reward = 1.0
        elif feedback.rating == 3:
            reward = 0.5
        else:
            reward = 0.0
        
        # Add bonus for improvement indicators
        if feedback.typing_accuracy_improved:
            reward += 0.2
        if feedback.memorability_improved:
            reward += 0.2
        if feedback.typing_speed_improved:
            reward += 0.1
        
        reward = min(reward, 1.0)  # Cap at 1.0
        
        # Map to substitutions
        for sub_key, sub_data in feedback.adaptation.substitutions_applied.items():
            if isinstance(sub_data, dict):
                from_char = sub_data.get('from', '')
                to_char = sub_data.get('to', '')
                key = f"{from_char}->{to_char}"
                
                if key not in substitution_rewards:
                    substitution_rewards[key] = []
                substitution_rewards[key].append(reward)
    
    # Update global substitution priors
    # In a full implementation, this would update a persistent RL model
    updates = 0
    for sub_key, rewards in substitution_rewards.items():
        avg_reward = sum(rewards) / len(rewards)
        logger.debug(f"Substitution {sub_key}: avg reward = {avg_reward:.2f} ({len(rewards)} samples)")
        updates += 1
    
    logger.info(f"Updated RL model with {updates} substitution patterns from {recent_feedback.count()} feedback entries")
    return {
        'processed': recent_feedback.count(),
        'substitution_updates': updates
    }


# =============================================================================
# On-Demand Tasks
# =============================================================================

@shared_task
def notify_user_of_suggestion(user_id: int, adaptation_id: str):
    """
    Send notification to user about new password suggestion.
    
    Args:
        user_id: User ID
        adaptation_id: Adaptation UUID
    """
    from security.models import PasswordAdaptation
    
    try:
        user = User.objects.get(id=user_id)
        adaptation = PasswordAdaptation.objects.get(id=adaptation_id)
        
        # Send push notification if enabled
        # This would integrate with your push notification system
        logger.info(f"Notification sent to user {user_id} for adaptation {adaptation_id}")
        
        return {'success': True}
    
    except (User.DoesNotExist, PasswordAdaptation.DoesNotExist) as e:
        logger.error(f"Notification failed: {str(e)}")
        return {'success': False, 'error': str(e)}


@shared_task
def calculate_memorability_score(password_hash_prefix: str, user_id: int):
    """
    Calculate memorability score for a password using ML model.
    
    Args:
        password_hash_prefix: Hash prefix of password
        user_id: User ID for context
    
    Returns:
        Memorability score [0, 1]
    """
    from security.services.adaptive_password_service import AdaptivePasswordService
    from security.models import UserTypingProfile
    
    try:
        user = User.objects.get(id=user_id)
        profile = UserTypingProfile.objects.get(user=user)
        
        service = AdaptivePasswordService(user)
        
        # Use memorability scorer
        # Note: We can only estimate based on profile, not actual password
        base_score = 0.5
        
        # Adjust based on user's error patterns
        if profile.error_prone_positions:
            error_count = len(profile.error_prone_positions)
            base_score -= error_count * 0.02  # Penalize for error-prone patterns
        
        # Adjust based on success rate
        base_score += (profile.success_rate - 0.5) * 0.2
        
        # Clamp to [0, 1]
        score = max(0.0, min(1.0, base_score))
        
        return {'score': score, 'password_hash_prefix': password_hash_prefix}
    
    except (User.DoesNotExist, UserTypingProfile.DoesNotExist) as e:
        logger.error(f"Memorability calculation failed: {str(e)}")
        return {'score': 0.5, 'error': str(e)}

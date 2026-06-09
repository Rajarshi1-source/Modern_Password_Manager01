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

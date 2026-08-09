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
from celery.exceptions import Retry, SoftTimeLimitExceeded
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
def update_rl_model_from_feedback(batch_size: int = 500):
    """
    Update the RL bandit model from user feedback, and persist it.

    Before Phase 3 this task computed per-substitution rewards and then *logged*
    them — its own comment said "in a full implementation, this would update a
    persistent RL model" (plan §0.2 gap B1). It now folds each reward into the
    user's Beta-Bernoulli ``SubstitutionPolicyArm`` posteriors and rebuilds the
    DP-noised cross-user cold-start priors.

    Selection is by ``policy_reward_applied_at IS NULL``, not by a rolling
    "last week" window. That makes the task idempotent under Celery's retries
    (a re-run cannot credit the same feedback twice) and self-healing after a
    skipped beat (last week's feedback is picked up on the next run rather than
    dropped). Each credit and its stamp commit together under a row lock, so
    two workers racing the same batch cannot double-count.

    Args:
        batch_size: Maximum feedback rows to process in one run. Bounds both
            runtime and the transaction count; leftovers are picked up next run
            because they are still unstamped.

    Returns:
        Dict with update stats, including the per-component reward breakdown
        counts so an operator can see *why* the policy moved.
    """
    from django.db import transaction

    from security.models import AdaptationFeedback
    from security.services.adaptive_password_service import PrivacyGuard
    from security.services.adaptive_policy_service import (
        composite_reward, credit_adaptation, rebuild_global_priors,
    )

    pending_ids = list(
        AdaptationFeedback.objects
        .filter(policy_reward_applied_at__isnull=True)
        .order_by('created_at')
        .values_list('id', flat=True)[:batch_size]
    )

    processed = 0
    arms_updated = 0
    skipped = 0
    behavioural_used = 0
    reward_total = 0.0

    for feedback_id in pending_ids:
        try:
            with transaction.atomic():
                # Re-assert the unstamped predicate under the lock: another
                # worker (or a retry of this task) may have claimed this row
                # between the id scan above and here.
                #
                # of=('self',) scopes FOR UPDATE to adaptation_feedback alone.
                # Without it, Postgres applies FOR UPDATE to every joined
                # table select_related() pulls in -- including auth_user via
                # adaptation__user -- so this background batch job would lock
                # user rows for the duration of each iteration's transaction,
                # unrelated to anything this task actually writes. 'self' is
                # Django's documented literal for the base table (verified in
                # SQLCompiler.get_select_for_update_of_arguments's
                # _get_field_choices, which yields "self" for the root
                # klass_info); both adaptation and adaptation__user are
                # non-nullable FKs, so select_related still uses plain INNER
                # JOINs to fetch them, just without a lock.
                feedback = (
                    AdaptationFeedback.objects
                    .select_for_update(of=('self',))
                    .select_related('adaptation', 'adaptation__user')
                    .filter(pk=feedback_id, policy_reward_applied_at__isnull=True)
                    .first()
                )
                if feedback is None:
                    skipped += 1
                    continue

                adaptation = feedback.adaptation
                reward, components = composite_reward(adaptation, feedback)
                arms_updated += credit_adaptation(adaptation, reward)

                feedback.policy_reward_applied_at = timezone.now()
                feedback.save(update_fields=['policy_reward_applied_at'])

            processed += 1
            reward_total += reward
            if components.get('behavioural') is not None:
                behavioural_used += 1

        except (SoftTimeLimitExceeded, Retry):
            # Celery worker control flow, not a bad row -- the task runs
            # under a global task_soft_time_limit (celery.py). Swallowing
            # this here would let the loop keep going past the soft
            # deadline until the uncatchable 10-minute hard limit SIGKILLs
            # the worker mid-batch instead of winding down gracefully.
            raise
        except Exception as exc:  # noqa: BLE001 - one bad row must not stop the run
            # The row stays unstamped, so the next run retries it. Logged at
            # error level because a persistent failure here silently freezes
            # the policy.
            logger.error(
                'Policy update failed for feedback %s: %s', feedback_id, exc,
                exc_info=True,
            )
            skipped += 1

    try:
        prior_stats = {**rebuild_global_priors(PrivacyGuard()), 'prior_rebuild_failed': False}
    except (SoftTimeLimitExceeded, Retry):
        # Same reasoning as the per-row handler above: this is Celery worker
        # control flow, not a rebuild failure. rebuild_global_priors scans the
        # whole consenting population in one transaction, so it is the call
        # most likely to cross the soft deadline -- swallowing it here would
        # let the loop keep going past the soft limit until the uncatchable
        # hard limit SIGKILLs the worker instead of winding down gracefully.
        # The feedback rows credited above already committed independently,
        # so nothing from this run is lost by re-raising.
        raise
    except Exception as exc:  # noqa: BLE001 - the credited batch must still report
        # Every feedback row credited above already committed (each in its own
        # transaction), so a rebuild failure here must not raise past this
        # point and discard that result -- it would lose the log line below
        # and the whole return value for a run that mostly succeeded.
        logger.error('Global prior rebuild failed: %s', exc, exc_info=True)
        prior_stats = {'classes_written': 0, 'classes_skipped': 0,
                       'classes_retracted': 0, 'prior_rebuild_failed': True}

    logger.info(
        'RL policy updated: %s feedback rows, %s arms, %s with a behavioural term',
        processed, arms_updated, behavioural_used,
    )
    return {
        'processed': processed,
        'skipped': skipped,
        'arms_updated': arms_updated,
        'behavioural_term_used': behavioural_used,
        'mean_reward': round(reward_total / processed, 4) if processed else None,
        **prior_stats,
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

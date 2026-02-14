"""
Predictive Intent Celery Tasks
==============================

Background tasks for AI-powered password prediction:
- Model training
- Expired prediction cleanup
- Morning credential preloading
- Usage pattern analysis

@author Password Manager Team
@created 2026-02-07
"""

import logging
from datetime import timedelta
from celery import shared_task
from django.utils import timezone
from django.contrib.auth.models import User
from django.db.models import Count, F
from django.db import models

logger = logging.getLogger(__name__)


# =============================================================================
# Model Training Tasks
# =============================================================================

@shared_task(name='ml_security.train_intent_model')
def train_intent_model():
    """
    Nightly task to retrain the intent prediction model.
    
    Collects feedback data and retrains to improve accuracy.
    """
    from ..ml_models.intent_predictor import get_intent_predictor
    from ..predictive_intent_models import (
        PasswordUsagePattern,
        PredictionFeedback,
    )
    
    logger.info("Starting intent model training task")
    
    try:
        # Get recent patterns with feedback
        cutoff = timezone.now() - timedelta(days=90)
        
        patterns = PasswordUsagePattern.objects.filter(
            access_time__gte=cutoff
        ).values(
            'vault_item_id', 'user_id', 'domain', 'domain_category',
            'day_of_week', 'hour_of_day', 'time_of_day',
            'previous_vault_item_id', 'access_method'
        )
        
        # Get feedback for outcome labeling
        feedback = PredictionFeedback.objects.filter(
            created_at__gte=cutoff,
            used_for_training=False
        ).select_related('prediction')
        
        # Prepare training data
        training_data = []
        for pattern in patterns:
            training_data.append({
                'features': pattern,
                'label': None  # Will be matched with feedback
            })
        
        # Match feedback to patterns
        feedback_map = {}
        for fb in feedback:
            key = (fb.prediction.user_id, fb.prediction.predicted_vault_item_id)
            feedback_map[key] = fb.was_correct
        
        for item in training_data:
            key = (item['features']['user_id'], item['features']['vault_item_id'])
            if key in feedback_map:
                item['label'] = feedback_map[key]
        
        # Filter to only labeled data
        labeled_data = [d for d in training_data if d['label'] is not None]
        
        if len(labeled_data) < 100:
            logger.info(f"Insufficient training data: {len(labeled_data)} samples")
            return {'status': 'skipped', 'reason': 'insufficient_data'}
        
        # Train model
        predictor = get_intent_predictor()
        metrics = predictor.train(labeled_data)
        
        # Mark feedback as used
        feedback.update(used_for_training=True)
        
        logger.info(f"Intent model trained: {metrics}")
        return {'status': 'success', 'metrics': metrics}
        
    except Exception as e:
        logger.error(f"Intent model training failed: {e}")
        return {'status': 'error', 'error': str(e)}


# =============================================================================
# Cleanup Tasks
# =============================================================================

@shared_task(name='ml_security.cleanup_expired_predictions')
def cleanup_expired_predictions():
    """
    Hourly task to remove expired predictions and preloaded credentials.
    
    Ensures no stale credential data remains in cache.
    """
    from ..predictive_intent_models import (
        IntentPrediction,
        PreloadedCredential,
        ContextSignal,
    )
    
    logger.info("Starting expired predictions cleanup")
    
    try:
        now = timezone.now()
        
        # Delete expired predictions (keep used ones for 7 days for analytics)
        expired_unused = IntentPrediction.objects.filter(
            expires_at__lt=now,
            was_used__isnull=True,
        )
        unused_count = expired_unused.count()
        expired_unused.delete()
        
        # Delete old used predictions (after 7 days)
        old_used = IntentPrediction.objects.filter(
            expires_at__lt=now - timedelta(days=7),
            was_used=True,
        )
        old_used_count = old_used.count()
        old_used.delete()
        
        # Delete expired preloaded credentials (critical - no stale creds)
        expired_preloads = PreloadedCredential.objects.filter(
            expires_at__lt=now
        )
        preload_count = expired_preloads.count()
        expired_preloads.delete()
        
        # Delete old context signals (older than 24 hours)
        old_signals = ContextSignal.objects.filter(
            timestamp__lt=now - timedelta(hours=24)
        )
        signal_count = old_signals.count()
        old_signals.delete()
        
        logger.info(
            f"Cleanup complete: {unused_count} unused predictions, "
            f"{old_used_count} old predictions, {preload_count} preloads, "
            f"{signal_count} signals removed"
        )
        
        return {
            'status': 'success',
            'deleted': {
                'unused_predictions': unused_count,
                'old_predictions': old_used_count,
                'preloaded_credentials': preload_count,
                'context_signals': signal_count,
            }
        }
        
    except Exception as e:
        logger.error(f"Cleanup task failed: {e}")
        return {'status': 'error', 'error': str(e)}


@shared_task(name='ml_security.cleanup_old_patterns')
def cleanup_old_patterns():
    """
    Daily task to remove patterns beyond user retention settings.
    """
    from ..predictive_intent_models import (
        PasswordUsagePattern,
        PredictiveIntentSettings,
    )
    
    logger.info("Starting pattern retention cleanup")
    
    try:
        deleted_count = 0
        
        # Get all users with custom retention settings
        settings = PredictiveIntentSettings.objects.all()
        
        for setting in settings:
            cutoff = timezone.now() - timedelta(days=setting.pattern_retention_days)
            count, _ = PasswordUsagePattern.objects.filter(
                user=setting.user,
                access_time__lt=cutoff
            ).delete()
            deleted_count += count
        
        # Default cleanup for users without settings (90 days)
        default_cutoff = timezone.now() - timedelta(days=90)
        users_with_settings = settings.values_list('user_id', flat=True)
        count, _ = PasswordUsagePattern.objects.filter(
            access_time__lt=default_cutoff
        ).exclude(user_id__in=users_with_settings).delete()
        deleted_count += count
        
        logger.info(f"Pattern cleanup: {deleted_count} patterns removed")
        return {'status': 'success', 'deleted': deleted_count}
        
    except Exception as e:
        logger.error(f"Pattern cleanup failed: {e}")
        return {'status': 'error', 'error': str(e)}


# =============================================================================
# Preloading Tasks
# =============================================================================

@shared_task(name='ml_security.preload_morning_credentials')
def preload_morning_credentials():
    """
    Early morning task to pre-cache likely morning logins.
    
    Runs at 6 AM to prepare credentials users typically access
    in the morning.
    """
    from ..services.predictive_intent_service import get_predictive_intent_service
    from ..predictive_intent_models import PasswordUsagePattern
    
    logger.info("Starting morning credential preload")
    
    try:
        service = get_predictive_intent_service()
        
        # Find users with morning patterns
        morning_hours = [6, 7, 8, 9]
        today = timezone.now().weekday()
        
        # Get users who typically access passwords in the morning
        active_users = PasswordUsagePattern.objects.filter(
            hour_of_day__in=morning_hours,
            day_of_week=today,
            access_time__gte=timezone.now() - timedelta(days=30)
        ).values('user_id').annotate(
            count=Count('id')
        ).filter(count__gte=5).order_by('-count')[:100]
        
        preload_count = 0
        for user_data in active_users:
            try:
                user = User.objects.get(id=user_data['user_id'])
                
                # Generate predictions for morning context
                context = {
                    'hour_of_day': 8,
                    'day_of_week': today,
                }
                
                predictions = service.get_predictions(user, context, max_predictions=3)
                preload_count += len(predictions)
                
            except User.DoesNotExist:
                continue
            except Exception as e:
                logger.warning(f"Failed to preload for user {user_data['user_id']}: {e}")
        
        logger.info(f"Morning preload: generated {preload_count} predictions")
        return {'status': 'success', 'predictions_generated': preload_count}
        
    except Exception as e:
        logger.error(f"Morning preload failed: {e}")
        return {'status': 'error', 'error': str(e)}


# =============================================================================
# Analysis Tasks
# =============================================================================

@shared_task(name='ml_security.analyze_usage_patterns')
def analyze_usage_patterns():
    """
    Daily task to analyze usage patterns and update statistics.
    """
    from ..predictive_intent_models import (
        PasswordUsagePattern,
        IntentPrediction,
        PredictionFeedback,
    )
    
    logger.info("Starting usage pattern analysis")
    
    try:
        now = timezone.now()
        week_ago = now - timedelta(days=7)
        month_ago = now - timedelta(days=30)
        
        # Calculate overall prediction accuracy
        total_predictions = IntentPrediction.objects.filter(
            predicted_at__gte=week_ago
        ).count()
        
        used_predictions = IntentPrediction.objects.filter(
            predicted_at__gte=week_ago,
            was_used=True
        ).count()
        
        accuracy = used_predictions / total_predictions if total_predictions > 0 else 0
        
        # Find top domains by usage
        top_domains = list(
            PasswordUsagePattern.objects.filter(
                access_time__gte=month_ago
            ).values('domain').annotate(
                count=Count('id')
            ).order_by('-count')[:20]
        )
        
        # Find peak usage hours
        peak_hours = list(
            PasswordUsagePattern.objects.filter(
                access_time__gte=month_ago
            ).values('hour_of_day').annotate(
                count=Count('id')
            ).order_by('-count')[:5]
        )
        
        # Calculate average time to use
        avg_time = PredictionFeedback.objects.filter(
            created_at__gte=week_ago,
            time_to_use_ms__isnull=False
        ).aggregate(
            avg_time=models.Avg('time_to_use_ms')
        )['avg_time'] or 0
        
        stats = {
            'week_accuracy': round(accuracy * 100, 2),
            'total_predictions': total_predictions,
            'used_predictions': used_predictions,
            'top_domains': top_domains[:10],
            'peak_hours': peak_hours,
            'avg_time_to_use_ms': round(avg_time, 0),
        }
        
        logger.info(f"Pattern analysis complete: {accuracy*100:.1f}% accuracy")
        return {'status': 'success', 'stats': stats}
        
    except Exception as e:
        logger.error(f"Pattern analysis failed: {e}")
        return {'status': 'error', 'error': str(e)}


# =============================================================================
# Scheduled Task Registration
# =============================================================================

def register_periodic_tasks(sender, **kwargs):
    """Register periodic tasks with Celery Beat."""
    from celery.schedules import crontab
    
    sender.add_periodic_task(
        crontab(hour=2, minute=0),
        train_intent_model.s(),
        name='Train intent model (2 AM)'
    )
    
    sender.add_periodic_task(
        60 * 60,  # Every hour
        cleanup_expired_predictions.s(),
        name='Cleanup expired predictions'
    )
    
    sender.add_periodic_task(
        crontab(hour=3, minute=0),
        cleanup_old_patterns.s(),
        name='Cleanup old patterns (3 AM)'
    )
    
    sender.add_periodic_task(
        crontab(hour=6, minute=0),
        preload_morning_credentials.s(),
        name='Preload morning credentials (6 AM)'
    )
    
    sender.add_periodic_task(
        crontab(hour=4, minute=0),
        analyze_usage_patterns.s(),
        name='Analyze usage patterns (4 AM)'
    )

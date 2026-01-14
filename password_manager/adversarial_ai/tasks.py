"""
Adversarial AI - Celery Background Tasks
=========================================

Background tasks for:
- Periodic threat model updates
- Batch password analysis
- Learning system aggregation
- Trending attack calculations
"""

import logging
from celery import shared_task
from django.utils import timezone
from django.contrib.auth import get_user_model

logger = logging.getLogger(__name__)
User = get_user_model()


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def run_adversarial_analysis(self, user_id: int, password_features: dict, save_result: bool = True):
    """
    Run full adversarial analysis in the background.
    
    Args:
        user_id: User ID for the analysis
        password_features: Password feature dictionary
        save_result: Whether to save the result to database
    
    Returns:
        Battle result dictionary
    """
    from .ai_engines.game_engine import GameEngine
    from .models import AdversarialBattle, UserDefenseProfile, DefenseRecommendation
    import hashlib
    
    try:
        logger.info(f"Starting adversarial analysis for user {user_id}")
        
        engine = GameEngine()
        result = engine.run_battle(password_features, user_id)
        
        if save_result:
            user = User.objects.get(id=user_id)
            
            # Create password hash for deduplication
            feature_str = f"{password_features.get('length', 0)}-{password_features.get('entropy', 0)}"
            password_hash = hashlib.sha256(feature_str.encode()).hexdigest()
            
            battle = AdversarialBattle.objects.create(
                user=user,
                password_hash=password_hash,
                password_entropy=password_features.get('entropy', 0),
                password_length=password_features.get('length', 0),
                attack_score=result.attack_score,
                defense_score=result.defense_score,
                estimated_crack_time_seconds=result.estimated_crack_time_seconds,
                outcome=result.outcome.value,
                attack_vectors_used=[r.attack_used for r in result.rounds],
                defense_strategies=[r.defense_applied for r in result.rounds],
                completed_at=timezone.now()
            )
            
            # Update user profile
            profile, _ = UserDefenseProfile.objects.get_or_create(user=user)
            profile.update_from_battle(battle)
            
            # Create recommendations
            for rec in result.recommendations[:3]:
                DefenseRecommendation.objects.create(
                    user=user,
                    battle=battle,
                    title=rec.title,
                    description=rec.description,
                    priority=rec.priority.value,
                    action_items=rec.action_items,
                    estimated_strength_improvement=rec.estimated_improvement
                )
            
            logger.info(f"Adversarial analysis completed for user {user_id}, battle ID: {battle.id}")
            
            return {
                'battle_id': battle.id,
                'outcome': result.outcome.value,
                'defense_score': result.defense_score,
                'attack_score': result.attack_score
            }
        
        return {
            'outcome': result.outcome.value,
            'defense_score': result.defense_score,
            'attack_score': result.attack_score
        }
        
    except User.DoesNotExist:
        logger.error(f"User {user_id} not found")
        raise
    except Exception as e:
        logger.error(f"Error in adversarial analysis: {e}")
        raise self.retry(exc=e)


@shared_task(bind=True, max_retries=2)
def update_threat_model(self):
    """
    Periodic task to update the threat model based on aggregated data.
    Should be run daily via Celery Beat.
    """
    from .ai_engines.learning_system import BreachLearningSystem
    
    try:
        logger.info("Starting threat model update")
        
        learning = BreachLearningSystem()
        result = learning.update_threat_model()
        
        logger.info(f"Threat model updated: {result}")
        
        return result
        
    except Exception as e:
        logger.error(f"Error updating threat model: {e}")
        raise self.retry(exc=e)


@shared_task(bind=True)
def calculate_trending_attacks(self):
    """
    Calculate and cache trending attack patterns.
    Should be run hourly via Celery Beat.
    """
    from .ai_engines.learning_system import BreachLearningSystem
    from django.core.cache import cache
    
    try:
        logger.info("Calculating trending attacks")
        
        learning = BreachLearningSystem()
        trends = learning.get_trending_attacks(limit=10)
        
        # Cache the results
        cache_data = [
            {
                'attack_type': t.attack_type,
                'direction': t.trend_direction,
                'velocity': t.velocity,
                'affected_count': t.affected_pattern_count,
                'defenses': t.recommended_defenses
            }
            for t in trends
        ]
        
        cache.set('adversarial_trending_attacks', cache_data, timeout=3600)
        
        logger.info(f"Cached {len(trends)} trending attacks")
        
        return {'cached_trends': len(trends)}
        
    except Exception as e:
        logger.error(f"Error calculating trending attacks: {e}")
        return {'error': str(e)}


@shared_task(bind=True)
def send_battle_notification(self, user_id: int, battle_id: int):
    """
    Send WebSocket notification for completed battle.
    """
    from channels.layers import get_channel_layer
    from asgiref.sync import async_to_sync
    from .models import AdversarialBattle
    
    try:
        battle = AdversarialBattle.objects.get(id=battle_id)
        channel_layer = get_channel_layer()
        
        async_to_sync(channel_layer.group_send)(
            f'adversarial_{user_id}',
            {
                'type': 'battle_update',
                'message': {
                    'battle_id': battle_id,
                    'outcome': battle.outcome,
                    'defense_score': battle.defense_score,
                    'attack_score': battle.attack_score,
                    'timestamp': timezone.now().isoformat()
                }
            }
        )
        
        logger.info(f"Sent battle notification to user {user_id}")
        
    except AdversarialBattle.DoesNotExist:
        logger.error(f"Battle {battle_id} not found")
    except Exception as e:
        logger.error(f"Error sending battle notification: {e}")


@shared_task(bind=True)
def batch_analyze_passwords(self, user_id: int, password_features_list: list):
    """
    Analyze multiple passwords in batch.
    
    Args:
        user_id: User ID
        password_features_list: List of password feature dictionaries
    
    Returns:
        List of analysis results
    """
    from .ai_engines.game_engine import GameEngine
    
    try:
        logger.info(f"Starting batch analysis for user {user_id}, {len(password_features_list)} passwords")
        
        engine = GameEngine()
        results = []
        
        for features in password_features_list:
            assessment = engine.get_quick_assessment(features)
            results.append(assessment)
        
        logger.info(f"Batch analysis completed: {len(results)} passwords analyzed")
        
        return {
            'user_id': user_id,
            'analyzed_count': len(results),
            'results': results
        }
        
    except Exception as e:
        logger.error(f"Error in batch analysis: {e}")
        raise


@shared_task(bind=True)
def cleanup_old_battles(self, days_to_keep: int = 90):
    """
    Clean up old battle records to manage database size.
    Should be run weekly via Celery Beat.
    
    Args:
        days_to_keep: Number of days of data to retain
    """
    from .models import AdversarialBattle
    from datetime import timedelta
    
    try:
        cutoff = timezone.now() - timedelta(days=days_to_keep)
        
        old_battles = AdversarialBattle.objects.filter(created_at__lt=cutoff)
        count = old_battles.count()
        
        if count > 0:
            old_battles.delete()
            logger.info(f"Cleaned up {count} old battle records")
        
        return {'deleted_count': count}
        
    except Exception as e:
        logger.error(f"Error cleaning up old battles: {e}")
        raise


@shared_task(bind=True)
def generate_user_insights(self, user_id: int):
    """
    Generate security insights for a user based on their battle history.
    """
    from .models import AdversarialBattle, UserDefenseProfile
    from django.db.models import Avg, Count
    
    try:
        user = User.objects.get(id=user_id)
        
        # Get battle statistics
        battles = AdversarialBattle.objects.filter(user=user)
        stats = battles.aggregate(
            avg_defense=Avg('defense_score'),
            avg_attack=Avg('attack_score'),
            total_battles=Count('id')
        )
        
        # Calculate win rate
        wins = battles.filter(outcome='defender_wins').count()
        total = stats['total_battles'] or 1
        win_rate = wins / total
        
        # Find common vulnerabilities
        from collections import Counter
        all_attacks = []
        for battle in battles:
            all_attacks.extend(battle.attack_vectors_used or [])
        
        common_attacks = Counter(all_attacks).most_common(3)
        
        # Update profile
        profile, _ = UserDefenseProfile.objects.get_or_create(user=user)
        profile.common_vulnerabilities = [a[0] for a in common_attacks]
        profile.historical_average_score = stats['avg_defense'] or 0.5
        profile.save()
        
        logger.info(f"Generated insights for user {user_id}")
        
        return {
            'user_id': user_id,
            'avg_defense_score': stats['avg_defense'],
            'win_rate': win_rate,
            'common_vulnerabilities': [a[0] for a in common_attacks]
        }
        
    except User.DoesNotExist:
        logger.error(f"User {user_id} not found")
        return {'error': 'User not found'}
    except Exception as e:
        logger.error(f"Error generating user insights: {e}")
        raise

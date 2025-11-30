"""
A/B Testing Experiments for Behavioral Recovery (Phase 2B.2)

Defines experiments to optimize recovery parameters:
1. Recovery timeline duration
2. Behavioral similarity threshold
3. Challenge frequency

Usage:
    from behavioral_recovery.ab_tests.recovery_experiments import create_recovery_experiments
    create_recovery_experiments()
"""

from django.utils import timezone
from django.conf import settings
import logging

# Check if ab_testing app exists
try:
    from ab_testing.models import Experiment
    AB_TESTING_AVAILABLE = True
except ImportError as e:
    AB_TESTING_AVAILABLE = False
    logging.warning(f"ab_testing app not found: {str(e)}. A/B testing experiments will be disabled.")

logger = logging.getLogger(__name__)


def create_recovery_experiments():
    """
    Setup A/B tests for behavioral recovery
    
    Creates 3 experiments:
    1. Recovery Time Duration (3 days vs 5 days vs 7 days)
    2. Behavioral Similarity Threshold (0.85 vs 0.87 vs 0.90)
    3. Challenge Frequency (1x/day for 5 days vs 2x/day for 3 days vs 3x/day for 2 days)
    
    Returns:
        dict: Created experiments or None if ab_testing not available
    """
    if not AB_TESTING_AVAILABLE:
        logger.error("Cannot create experiments: ab_testing app not available")
        return None
    
    created_experiments = {}
    
    try:
        # Experiment 1: Recovery Time Duration
        exp1, created = Experiment.objects.get_or_create(
            name='recovery_time_duration',
            defaults={
                'description': 'Test optimal recovery timeline duration',
                'type': 'multivariate',
                'status': 'running',
                'active': True,
                'start_date': timezone.now(),
                'primary_goal': 'recovery_completion_rate',
                'variants': [
                    {
                        'name': '3_days',
                        'weight': 33.3,
                        'config': {'days': 3, 'description': 'Fast track recovery (3 days)'}
                    },
                    {
                        'name': '5_days',
                        'weight': 33.3,
                        'config': {'days': 5, 'description': 'Standard recovery (5 days)'}
                    },
                    {
                        'name': '7_days',
                        'weight': 33.4,
                        'config': {'days': 7, 'description': 'Extended recovery (7 days)'}
                    }
                ]
            }
        )
        
        if created:
            logger.info(f"✅ Created experiment: {exp1.name} with 3 variants")
        else:
            logger.info(f"ℹ️ Experiment already exists: {exp1.name}")
        
        created_experiments['recovery_time_duration'] = exp1
        
        # Experiment 2: Behavioral Similarity Threshold
        exp2, created = Experiment.objects.get_or_create(
            name='similarity_threshold',
            defaults={
                'description': 'Optimize security vs usability tradeoff',
                'type': 'multivariate',
                'status': 'running',
                'active': True,
                'start_date': timezone.now(),
                'primary_goal': 'user_satisfaction_score',
                'variants': [
                    {
                        'name': 'threshold_085',
                        'weight': 33.3,
                        'config': {
                            'threshold': 0.85,
                            'description': 'Lenient threshold (85% similarity)'
                        }
                    },
                    {
                        'name': 'threshold_087',
                        'weight': 33.3,
                        'config': {
                            'threshold': 0.87,
                            'description': 'Balanced threshold (87% similarity)'
                        }
                    },
                    {
                        'name': 'threshold_090',
                        'weight': 33.4,
                        'config': {
                            'threshold': 0.90,
                            'description': 'Strict threshold (90% similarity)'
                        }
                    }
                ]
            }
        )
        
        if created:
            logger.info(f"✅ Created experiment: {exp2.name} with 3 variants")
        else:
            logger.info(f"ℹ️ Experiment already exists: {exp2.name}")
        
        created_experiments['similarity_threshold'] = exp2
        
        # Experiment 3: Challenge Frequency
        exp3, created = Experiment.objects.get_or_create(
            name='challenge_frequency',
            defaults={
                'description': 'Daily challenge optimization for user engagement',
                'type': 'multivariate',
                'status': 'running',
                'active': True,
                'start_date': timezone.now(),
                'primary_goal': 'average_recovery_time',
                'variants': [
                    {
                        'name': 'once_daily',
                        'weight': 33.3,
                        'config': {
                            'challenges_per_day': 1,
                            'total_days': 5,
                            'description': 'Leisurely pace (1 challenge/day for 5 days)'
                        }
                    },
                    {
                        'name': 'twice_daily',
                        'weight': 33.3,
                        'config': {
                            'challenges_per_day': 2,
                            'total_days': 3,
                            'description': 'Balanced pace (2 challenges/day for 3 days)'
                        }
                    },
                    {
                        'name': 'three_daily',
                        'weight': 33.4,
                        'config': {
                            'challenges_per_day': 3,
                            'total_days': 2,
                            'description': 'Fast pace (3 challenges/day for 2 days)'
                        }
                    }
                ]
            }
        )
        
        if created:
            logger.info(f"✅ Created experiment: {exp3.name} with 3 variants")
        else:
            logger.info(f"ℹ️ Experiment already exists: {exp3.name}")
        
        created_experiments['challenge_frequency'] = exp3
        
        logger.info(f"✅ Successfully created/verified {len(created_experiments)} experiments")
        return created_experiments
        
    except Exception as e:
        logger.error(f"❌ Error creating experiments: {e}", exc_info=True)
        raise


def get_experiment_variant(user_id, experiment_name):
    """
    Get assigned variant for a user in an experiment
    
    Args:
        user_id: User ID
        experiment_name: Name of the experiment
        
    Returns:
        Variant object or None
    """
    if not AB_TESTING_AVAILABLE:
        return None
    
    try:
        experiment = Experiment.objects.get(name=experiment_name, is_active=True)
        
        # Simple deterministic assignment based on user_id
        # In production, use a proper A/B testing service
        variant_index = user_id % 3
        variants = list(experiment.variants.all().order_by('name'))
        
        if variants:
            return variants[variant_index]
        
        return None
        
    except Experiment.DoesNotExist:
        logger.warning(f"Experiment not found: {experiment_name}")
        return None
    except Exception as e:
        logger.error(f"Error getting variant for experiment {experiment_name}: {e}")
        return None


def track_experiment_event(user_id, experiment_name, variant_name, event_type, metadata=None):
    """
    Track an event for an experiment
    
    Args:
        user_id: User ID
        experiment_name: Name of the experiment
        variant_name: Name of the variant
        event_type: Type of event (e.g., 'recovery_initiated', 'recovery_completed')
        metadata: Additional event data
    """
    if not AB_TESTING_AVAILABLE:
        return
    
    try:
        from ab_testing.models import ExperimentEvent
        
        ExperimentEvent.objects.create(
            experiment_name=experiment_name,
            variant_name=variant_name,
            user_id=user_id,
            event_type=event_type,
            metadata=metadata or {},
            timestamp=timezone.now()
        )
        
        logger.debug(f"Tracked event: {event_type} for {experiment_name}:{variant_name}")
        
    except Exception as e:
        logger.error(f"Error tracking experiment event: {e}")


def deactivate_experiment(experiment_name):
    """
    Deactivate an experiment
    
    Args:
        experiment_name: Name of the experiment to deactivate
    """
    if not AB_TESTING_AVAILABLE:
        return False
    
    try:
        experiment = Experiment.objects.get(name=experiment_name)
        experiment.is_active = False
        experiment.end_date = timezone.now()
        experiment.save()
        
        logger.info(f"✅ Deactivated experiment: {experiment_name}")
        return True
        
    except Experiment.DoesNotExist:
        logger.warning(f"Experiment not found: {experiment_name}")
        return False
    except Exception as e:
        logger.error(f"Error deactivating experiment: {e}")
        return False


def get_experiment_results(experiment_name):
    """
    Get results for an experiment
    
    Args:
        experiment_name: Name of the experiment
        
    Returns:
        Dictionary with results or None
    """
    if not AB_TESTING_AVAILABLE:
        return None
    
    try:
        experiment = Experiment.objects.get(name=experiment_name)
        variants = experiment.variants.all()
        
        results = {
            'experiment': experiment_name,
            'is_active': experiment.is_active,
            'start_date': experiment.start_date,
            'variants': []
        }
        
        for variant in variants:
            # In production, fetch actual metrics from ExperimentEvent
            variant_data = {
                'name': variant.name,
                'traffic_percentage': variant.traffic_percentage,
                'config': variant.config,
                # Placeholder for actual metrics
                'metrics': {
                    'total_users': 0,
                    'success_rate': 0.0,
                    'avg_completion_time': 0.0
                }
            }
            results['variants'].append(variant_data)
        
        return results
        
    except Experiment.DoesNotExist:
        logger.warning(f"Experiment not found: {experiment_name}")
        return None
    except Exception as e:
        logger.error(f"Error getting experiment results: {e}")
        return None


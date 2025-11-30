"""
A/B Testing API Views
====================

API endpoints for A/B testing and feature flags.
"""

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from django.utils import timezone
from django.db.models import Count, Q
from datetime import timedelta

from .models import (
    FeatureFlag,
    Experiment,
    ExperimentAssignment,
    ExperimentMetric,
    FeatureFlagUsage
)


@api_view(['GET'])
@permission_classes([AllowAny])
def get_experiments_and_flags(request):
    """
    Get active experiments and feature flags for a user
    
    GET /api/ab-testing/
    Query params:
        - userId: User ID (optional, uses request.user if authenticated)
        - cohort: User cohort (optional)
    """
    try:
        # Get user
        user = request.user if request.user.is_authenticated else None
        user_id = request.GET.get('userId') or (user.id if user else None)
        cohort = request.GET.get('cohort')
        
        # Get active feature flags
        feature_flags = {}
        for flag in FeatureFlag.objects.filter(enabled=True):
            is_enabled = flag.is_enabled_for_user(user)
            feature_flags[flag.name] = is_enabled
            
            # Track usage
            FeatureFlagUsage.objects.create(
                feature_flag=flag,
                user=user,
                was_enabled=is_enabled,
                context={
                    'cohort': cohort,
                    'url': request.META.get('HTTP_REFERER', '')
                }
            )
        
        # Get active experiments
        experiments = {}
        now = timezone.now()
        
        for exp in Experiment.objects.filter(
            active=True,
            status='running',
            start_date__lte=now
        ).filter(Q(end_date__isnull=True) | Q(end_date__gte=now)):
            
            # Check traffic allocation
            if exp.traffic_allocation < 1.0:
                # Use deterministic hash to decide if user is in experiment
                if user:
                    hash_val = hash(f"{user.id}_{exp.name}") % 100
                    if hash_val >= exp.traffic_allocation * 100:
                        continue
            
            # Get or create assignment
            if user:
                assignment, created = ExperimentAssignment.objects.get_or_create(
                    experiment=exp,
                    user=user,
                    defaults={'variant': assign_variant(exp, user.id)}
                )
            else:
                # For anonymous users, generate assignment (not persisted)
                anonymous_id = request.session.session_key or 'anon'
                assignment = type('obj', (object,), {
                    'variant': assign_variant(exp, anonymous_id)
                })()
            
            experiments[exp.name] = {
                'name': exp.name,
                'type': exp.type,
                'active': exp.active,
                'variants': exp.variants,
                'targeting': exp.targeting
            }
        
        return Response({
            'feature_flags': feature_flags,
            'experiments': experiments
        })
        
    except Exception as e:
        return Response({
            'status': 'error',
            'message': str(e)
        }, status=status.HTTP_400_BAD_REQUEST)


def assign_variant(experiment, user_identifier):
    """
    Assign a variant based on user identifier and experiment configuration
    """
    variants = experiment.variants or [
        {'name': 'control', 'weight': 0.5},
        {'name': 'treatment', 'weight': 0.5}
    ]
    
    # Hash user identifier to get deterministic assignment
    hash_val = hash(f"{user_identifier}_{experiment.name}")
    bucket = (hash_val % 10000) / 10000  # 0.0000 to 0.9999
    
    # Weighted assignment
    cumulative_weight = 0
    for variant in variants:
        cumulative_weight += variant.get('weight', 0)
        if bucket < cumulative_weight:
            return variant.get('name')
    
    # Fallback to last variant
    return variants[-1].get('name') if variants else 'control'


@api_view(['POST'])
@permission_classes([AllowAny])
def track_experiment_metric(request):
    """
    Track experiment metrics (exposures, outcomes, interactions)
    
    POST /api/ab-testing/metrics/
    Body: {
        "type": "exposure|outcome|interaction",
        "experiment": "experiment_name",
        "outcome": "outcome_name" (for outcomes),
        "interaction": "interaction_name" (for interactions),
        "variant": "variant_name",
        "value": 1,
        "properties": {...}
    }
    """
    try:
        data = request.data
        
        # Get user
        user = request.user if request.user.is_authenticated else None
        anonymous_id = data.get('anonymousId', '')
        
        # Get experiment
        experiment_name = data.get('experiment')
        experiment = Experiment.objects.get(name=experiment_name)
        
        # Create metric
        metric = ExperimentMetric.objects.create(
            experiment=experiment,
            variant=data.get('variant'),
            user=user,
            anonymous_id=anonymous_id,
            type=data.get('type'),
            name=data.get('outcome') or data.get('interaction') or data.get('experiment'),
            value=data.get('value', 1),
            properties=data.get('properties', {}),
            context=data.get('context', {}),
            timestamp=timezone.now()
        )
        
        return Response({
            'status': 'success',
            'metric_id': str(metric.id)
        }, status=status.HTTP_201_CREATED)
        
    except Experiment.DoesNotExist:
        return Response({
            'status': 'error',
            'message': 'Experiment not found'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({
            'status': 'error',
            'message': str(e)
        }, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_experiment_results(request, experiment_name):
    """
    Get results for a specific experiment
    
    GET /api/ab-testing/experiments/<experiment_name>/results/
    """
    try:
        experiment = Experiment.objects.get(name=experiment_name)
        
        # Get all variants
        variants = [v['name'] for v in experiment.variants]
        
        # Calculate metrics per variant
        results = {}
        for variant in variants:
            exposures = experiment.metrics.filter(variant=variant, type='exposure').count()
            outcomes = experiment.metrics.filter(variant=variant, type='outcome').count()
            
            conversion_rate = (outcomes / exposures * 100) if exposures > 0 else 0
            
            results[variant] = {
                'exposures': exposures,
                'outcomes': outcomes,
                'conversion_rate': conversion_rate,
                'interactions': experiment.metrics.filter(variant=variant, type='interaction').count()
            }
        
        return Response({
            'experiment': {
                'name': experiment.name,
                'type': experiment.type,
                'status': experiment.status,
                'start_date': experiment.start_date,
                'end_date': experiment.end_date,
                'winner': experiment.winner,
                'confidence': experiment.confidence
            },
            'results': results
        })
        
    except Experiment.DoesNotExist:
        return Response({
            'status': 'error',
            'message': 'Experiment not found'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({
            'status': 'error',
            'message': str(e)
        }, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_user_experiments(request):
    """
    Get all experiments and assignments for current user
    
    GET /api/ab-testing/user/experiments/
    """
    try:
        user = request.user
        
        assignments = ExperimentAssignment.objects.filter(user=user).select_related('experiment')
        
        return Response({
            'assignments': [{
                'experiment': a.experiment.name,
                'variant': a.variant,
                'assigned_at': a.assigned_at,
                'experiment_type': a.experiment.type,
                'experiment_status': a.experiment.status
            } for a in assignments]
        })
        
    except Exception as e:
        return Response({
            'status': 'error',
            'message': str(e)
        }, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_user_feature_flags(request):
    """
    Get all feature flags for current user
    
    GET /api/ab-testing/user/flags/
    """
    try:
        user = request.user
        
        flags = {}
        for flag in FeatureFlag.objects.all():
            flags[flag.name] = {
                'enabled': flag.is_enabled_for_user(user),
                'description': flag.description,
                'config': flag.config
            }
        
        return Response({
            'flags': flags
        })
        
    except Exception as e:
        return Response({
            'status': 'error',
            'message': str(e)
        }, status=status.HTTP_400_BAD_REQUEST)


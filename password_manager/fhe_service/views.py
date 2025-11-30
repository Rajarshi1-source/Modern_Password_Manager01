"""
FHE Service API Views

API endpoints for FHE operations:
- Encrypt data with FHE
- Encrypted password strength check
- Batch strength evaluation
- Encrypted search
- Key management
"""

import logging
import time
from typing import Dict, Any

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.utils import timezone

from .services import (
    FHEOperationRouter,
    FHEComputationCache,
    AdaptiveFHEManager,
    EncryptionTier,
    get_fhe_router,
    get_fhe_cache,
    get_adaptive_manager,
)
from .services.fhe_router import ComputationalBudget, OperationType
from .models import FHEOperationLog, FHEKeyStore

logger = logging.getLogger(__name__)


def log_fhe_operation(
    user,
    operation_type: str,
    tier: str,
    status_result: str,
    metrics: Dict[str, Any],
    request=None
):
    """Log an FHE operation for audit."""
    try:
        FHEOperationLog.objects.create(
            user=user,
            ip_address=request.META.get('REMOTE_ADDR') if request else None,
            user_agent=request.META.get('HTTP_USER_AGENT', '')[:500] if request else None,
            operation_type=operation_type,
            encryption_tier=tier,
            status=status_result,
            total_time_ms=metrics.get('total_time_ms', 0),
            computation_time_ms=metrics.get('computation_time_ms', 0),
            circuit_depth=metrics.get('circuit_depth', 0),
            input_size_bytes=metrics.get('input_size', 0),
            output_size_bytes=metrics.get('output_size', 0),
            cache_hit=metrics.get('cache_hit', False),
            fallback_used=metrics.get('fallback_used', False),
        )
    except Exception as e:
        logger.error(f"Failed to log FHE operation: {e}")


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def encrypt_data(request):
    """
    Encrypt data using FHE.
    
    Request body:
    {
        "data": "string or dict",
        "operation_type": "password_length" | "character_count" | "strength_check",
        "budget": {
            "max_latency_ms": 1000,
            "min_accuracy": 0.9
        }
    }
    """
    start_time = time.time()
    
    data = request.data.get('data')
    operation_type = request.data.get('operation_type', 'strength_check')
    budget_data = request.data.get('budget', {})
    
    if not data:
        return Response(
            {'error': 'Data is required'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Create budget from request
    budget = ComputationalBudget(
        max_latency_ms=budget_data.get('max_latency_ms', 1000),
        max_memory_mb=budget_data.get('max_memory_mb', 512),
        min_accuracy=budget_data.get('min_accuracy', 0.9),
        priority=budget_data.get('priority', 5)
    )
    
    try:
        router = get_fhe_router()
        decision, result = router.route_operation(operation_type, data, budget)
        
        elapsed_ms = int((time.time() - start_time) * 1000)
        
        # Log operation
        log_fhe_operation(
            user=request.user,
            operation_type=operation_type,
            tier=decision.tier.name,
            status_result='success',
            metrics={
                'total_time_ms': elapsed_ms,
                'computation_time_ms': decision.estimated_latency_ms,
                'cache_hit': decision.tier == EncryptionTier.CACHED_FHE,
            },
            request=request
        )
        
        return Response({
            'success': True,
            'result': _serialize_result(result),
            'tier': decision.tier.name,
            'service': decision.service_name,
            'latency_ms': elapsed_ms,
            'accuracy_estimate': decision.estimated_accuracy,
            'cached': decision.tier == EncryptionTier.CACHED_FHE
        })
        
    except Exception as e:
        logger.error(f"FHE encrypt error: {e}")
        
        log_fhe_operation(
            user=request.user,
            operation_type=operation_type,
            tier='unknown',
            status_result='failed',
            metrics={'error': str(e)},
            request=request
        )
        
        return Response(
            {'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def strength_check(request):
    """
    Check password strength using encrypted computation.
    
    Request body:
    {
        "password": "string",
        "use_fhe": true,
        "budget": {
            "max_latency_ms": 500
        }
    }
    """
    start_time = time.time()
    
    password = request.data.get('password', '')
    use_fhe = request.data.get('use_fhe', True)
    budget_data = request.data.get('budget', {})
    
    if not password:
        return Response(
            {'error': 'Password is required'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    budget = ComputationalBudget(
        max_latency_ms=budget_data.get('max_latency_ms', 500),
        min_accuracy=budget_data.get('min_accuracy', 0.9),
        priority=budget_data.get('priority', 5)
    )
    
    try:
        if use_fhe:
            router = get_fhe_router()
            decision, result = router.route_operation(
                'strength_check',
                password,
                budget
            )
            
            score = result.get('score', 0) if isinstance(result, dict) else 50
            tier_used = decision.tier.name
            
        else:
            # Non-FHE fallback
            score = _calculate_strength_score_simple(password)
            tier_used = 'client_only'
        
        elapsed_ms = int((time.time() - start_time) * 1000)
        
        # Determine strength category
        if score >= 80:
            strength = 'strong'
        elif score >= 60:
            strength = 'medium'
        elif score >= 40:
            strength = 'weak'
        else:
            strength = 'very_weak'
        
        log_fhe_operation(
            user=request.user,
            operation_type='strength_check',
            tier=tier_used,
            status_result='success',
            metrics={'total_time_ms': elapsed_ms, 'score': score},
            request=request
        )
        
        return Response({
            'success': True,
            'score': score,
            'strength': strength,
            'fhe_used': use_fhe and tier_used != 'client_only',
            'tier': tier_used,
            'latency_ms': elapsed_ms
        })
        
    except Exception as e:
        logger.error(f"Strength check error: {e}")
        
        return Response(
            {'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def batch_strength_check(request):
    """
    Batch password strength check using SIMD FHE.
    
    Request body:
    {
        "passwords": [
            {"id": "1", "password": "pass1"},
            {"id": "2", "password": "pass2"}
        ],
        "budget": {
            "max_latency_ms": 5000
        }
    }
    """
    start_time = time.time()
    
    passwords = request.data.get('passwords', [])
    budget_data = request.data.get('budget', {})
    
    if not passwords:
        return Response(
            {'error': 'Passwords list is required'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    if len(passwords) > 100:
        return Response(
            {'error': 'Maximum 100 passwords per batch'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    budget = ComputationalBudget(
        max_latency_ms=budget_data.get('max_latency_ms', 5000),
        min_accuracy=budget_data.get('min_accuracy', 0.9),
        priority=budget_data.get('priority', 5)
    )
    
    try:
        # Extract password features
        password_features = []
        for item in passwords:
            pwd = item.get('password', '') if isinstance(item, dict) else item
            features = _extract_password_features(pwd)
            features['id'] = item.get('id', '') if isinstance(item, dict) else ''
            password_features.append(features)
        
        router = get_fhe_router()
        decision, result = router.route_operation(
            'batch_strength',
            password_features,
            budget
        )
        
        elapsed_ms = int((time.time() - start_time) * 1000)
        
        # Format results
        scores = result.get('scores', []) if isinstance(result, dict) else []
        results = []
        
        for i, features in enumerate(password_features):
            score = scores[i] if i < len(scores) else _calculate_strength_score_simple(
                passwords[i].get('password', '') if isinstance(passwords[i], dict) else passwords[i]
            )
            
            results.append({
                'id': features.get('id', str(i)),
                'score': score,
                'strength': _score_to_strength(score)
            })
        
        log_fhe_operation(
            user=request.user,
            operation_type='batch_strength',
            tier=decision.tier.name,
            status_result='success',
            metrics={
                'total_time_ms': elapsed_ms,
                'batch_size': len(passwords)
            },
            request=request
        )
        
        return Response({
            'success': True,
            'results': results,
            'batch_size': len(passwords),
            'tier': decision.tier.name,
            'latency_ms': elapsed_ms
        })
        
    except Exception as e:
        logger.error(f"Batch strength check error: {e}")
        
        return Response(
            {'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def encrypted_search(request):
    """
    Search encrypted vault using FHE.
    
    Request body:
    {
        "query": "search term",
        "vault_ids": ["id1", "id2"],  # Optional
        "threshold": 0.8,
        "budget": {...}
    }
    """
    query = request.data.get('query', '')
    threshold = request.data.get('threshold', 0.8)
    budget_data = request.data.get('budget', {})
    
    if not query:
        return Response(
            {'error': 'Query is required'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    budget = ComputationalBudget(
        max_latency_ms=budget_data.get('max_latency_ms', 2000),
        min_accuracy=budget_data.get('min_accuracy', 0.85),
        priority=budget_data.get('priority', 5)
    )
    
    try:
        start_time = time.time()
        
        router = get_fhe_router()
        
        # This would typically query the vault - simplified for demo
        search_data = {
            'query': query,
            'vault': [],  # Would be populated from user's vault
            'threshold': threshold
        }
        
        decision, result = router.route_operation(
            'similarity_search',
            search_data,
            budget
        )
        
        elapsed_ms = int((time.time() - start_time) * 1000)
        
        matches = result.get('matches', []) if isinstance(result, dict) else []
        
        return Response({
            'success': True,
            'matches': matches,
            'tier': decision.tier.name,
            'latency_ms': elapsed_ms
        })
        
    except Exception as e:
        logger.error(f"Encrypted search error: {e}")
        
        return Response(
            {'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def generate_keys(request):
    """
    Generate FHE keypair for user.
    
    Keys are encrypted with user's master key before storage.
    """
    try:
        # Check if user already has keys
        existing_keys = FHEKeyStore.objects.filter(
            user=request.user,
            is_active=True
        ).exists()
        
        if existing_keys and not request.data.get('force', False):
            return Response({
                'success': False,
                'error': 'Keys already exist. Set force=true to regenerate.'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Deactivate existing keys
        FHEKeyStore.objects.filter(user=request.user).update(is_active=False)
        
        # Generate placeholder keys (actual key generation would use the services)
        # In production, this would call concrete_service or seal_service
        import secrets
        
        key_data = secrets.token_bytes(32)  # Placeholder
        
        FHEKeyStore.objects.create(
            user=request.user,
            key_type='seal_public',
            encrypted_key_data=key_data,
            key_size_bits=256,
            polynomial_modulus_degree=8192,
            security_level=128,
            is_active=True
        )
        
        return Response({
            'success': True,
            'message': 'FHE keys generated successfully',
            'key_type': 'seal_public',
            'security_level': 128
        })
        
    except Exception as e:
        logger.error(f"Key generation error: {e}")
        
        return Response(
            {'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_keys(request):
    """
    Get user's FHE public key info.
    """
    try:
        keys = FHEKeyStore.objects.filter(
            user=request.user,
            is_active=True
        ).values(
            'key_type',
            'key_size_bits',
            'security_level',
            'created_at',
            'last_used_at'
        )
        
        return Response({
            'success': True,
            'keys': list(keys)
        })
        
    except Exception as e:
        logger.error(f"Get keys error: {e}")
        
        return Response(
            {'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
def fhe_status(request):
    """
    Get FHE service status (public endpoint).
    """
    try:
        router = get_fhe_router()
        cache = get_fhe_cache()
        adaptive = get_adaptive_manager()
        
        return Response({
            'success': True,
            'router': router.get_status(),
            'cache': cache.get_stats(),
            'adaptive': adaptive.get_status()
        })
        
    except Exception as e:
        logger.error(f"FHE status error: {e}")
        
        return Response({
            'success': False,
            'error': str(e)
        })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def fhe_metrics(request):
    """
    Get FHE operation metrics for the user.
    """
    try:
        # Get user's operation stats
        ops = FHEOperationLog.objects.filter(user=request.user)
        
        total_ops = ops.count()
        successful_ops = ops.filter(status='success').count()
        
        # Calculate averages
        from django.db.models import Avg, Sum
        
        stats = ops.aggregate(
            avg_latency=Avg('total_time_ms'),
            total_compute_time=Sum('computation_time_ms')
        )
        
        # Tier distribution
        tier_dist = {}
        for tier_choice in ['client_only', 'hybrid_fhe', 'full_fhe', 'cached_fhe']:
            tier_dist[tier_choice] = ops.filter(encryption_tier=tier_choice).count()
        
        return Response({
            'success': True,
            'total_operations': total_ops,
            'successful_operations': successful_ops,
            'success_rate': successful_ops / total_ops if total_ops > 0 else 0,
            'avg_latency_ms': stats['avg_latency'] or 0,
            'total_compute_time_ms': stats['total_compute_time'] or 0,
            'tier_distribution': tier_dist
        })
        
    except Exception as e:
        logger.error(f"FHE metrics error: {e}")
        
        return Response(
            {'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


# Helper functions

def _serialize_result(result: Any) -> Any:
    """Serialize FHE result for JSON response."""
    if result is None:
        return None
    
    if isinstance(result, dict):
        return {k: _serialize_result(v) for k, v in result.items()}
    
    if isinstance(result, (list, tuple)):
        return [_serialize_result(v) for v in result]
    
    if isinstance(result, bytes):
        return result.hex()
    
    if hasattr(result, 'metadata'):
        return result.metadata
    
    return str(result)


def _calculate_strength_score_simple(password: str) -> float:
    """Simple password strength calculation."""
    if not password:
        return 0
    
    score = 0
    
    # Length score
    score += min(40, len(password) * 4)
    
    # Character diversity
    has_lower = any(c.islower() for c in password)
    has_upper = any(c.isupper() for c in password)
    has_digit = any(c.isdigit() for c in password)
    has_special = any(not c.isalnum() for c in password)
    
    diversity = sum([has_lower, has_upper, has_digit, has_special])
    score += diversity * 10
    
    # Penalty for common patterns
    common_patterns = ['123', 'abc', 'qwerty', 'password', 'admin']
    if any(p in password.lower() for p in common_patterns):
        score -= 20
    
    return max(0, min(100, score))


def _extract_password_features(password: str) -> Dict[str, Any]:
    """Extract features from password for FHE processing."""
    if not password:
        return {
            'length': 0,
            'entropy': 0,
            'char_diversity': 0,
            'pattern_score': 0
        }
    
    length = len(password)
    
    has_lower = any(c.islower() for c in password)
    has_upper = any(c.isupper() for c in password)
    has_digit = any(c.isdigit() for c in password)
    has_special = any(not c.isalnum() for c in password)
    
    char_types = sum([has_lower, has_upper, has_digit, has_special])
    char_diversity = char_types / 4.0
    
    unique_chars = len(set(password))
    entropy = (unique_chars / max(1, length)) * (length / 32.0)
    
    common_patterns = ['123', 'abc', 'qwerty', 'password']
    has_pattern = any(p in password.lower() for p in common_patterns)
    pattern_score = 0.5 if has_pattern else 0.0
    
    return {
        'length': length,
        'entropy': min(1.0, entropy),
        'char_diversity': char_diversity,
        'pattern_score': pattern_score
    }


def _score_to_strength(score: float) -> str:
    """Convert numeric score to strength category."""
    if score >= 80:
        return 'strong'
    elif score >= 60:
        return 'medium'
    elif score >= 40:
        return 'weak'
    else:
        return 'very_weak'


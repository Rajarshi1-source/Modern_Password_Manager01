"""
Adversarial AI - REST API Views
================================

API endpoints for adversarial password analysis:
- Password analysis
- Battle simulation
- Recommendations
- Trending attacks
"""

import logging
import hashlib
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from password_manager.api_utils import success_response, error_response
from .ai_engines.attacker_ai import AttackerAI
from .ai_engines.defender_ai import DefenderAI
from .ai_engines.game_engine import GameEngine
from .ai_engines.learning_system import BreachLearningSystem
from .models import (
    AdversarialBattle,
    DefenseRecommendation,
    UserDefenseProfile,
    AggregatedBreachPattern
)

logger = logging.getLogger(__name__)

# Initialize AI engines (singleton pattern)
_game_engine = None
_learning_system = None


def get_game_engine():
    global _game_engine
    if _game_engine is None:
        _game_engine = GameEngine()
    return _game_engine


def get_learning_system():
    global _learning_system
    if _learning_system is None:
        _learning_system = BreachLearningSystem()
    return _learning_system


# Initialize ML Security predictor (for feature extraction)
_password_predictor = None


def get_password_predictor():
    """Get or create PasswordStrengthPredictor for adversarial feature extraction."""
    global _password_predictor
    if _password_predictor is None:
        try:
            from ml_security.ml_models.password_strength import PasswordStrengthPredictor
            _password_predictor = PasswordStrengthPredictor()
            logger.info("Integrated with ml_security.PasswordStrengthPredictor")
        except ImportError:
            logger.warning("ml_security module not available, using manual feature extraction")
            _password_predictor = False  # Use False to indicate unavailable
    return _password_predictor if _password_predictor else None


# =============================================================================
# PASSWORD ANALYSIS
# =============================================================================

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def analyze_password(request):
    """
    Analyze password using adversarial AI.
    
    POST Data:
    {
        "features": {
            "length": int,
            "entropy": float,
            "has_upper": bool,
            "has_lower": bool,
            "has_digit": bool,
            "has_special": bool,
            "has_common_patterns": bool,
            "character_diversity": float,
            "guessability_score": float,
            "pattern_info": dict (optional)
        },
        "run_full_battle": bool (optional, default: false),
        "save_result": bool (optional, default: true)
    }
    
    Returns:
    {
        "success": true,
        "analysis": {...},
        "battle": {...} (if run_full_battle=true)
    }
    """
    try:
        features = request.data.get('features', {})
        run_full_battle = request.data.get('run_full_battle', False)
        save_result = request.data.get('save_result', True)
        
        if not features:
            return error_response("Password features are required", status.HTTP_400_BAD_REQUEST)
        
        engine = get_game_engine()
        
        if run_full_battle:
            # Run full adversarial battle
            result = engine.run_battle(features, request.user.id)
            
            # Save to database if requested
            if save_result:
                _save_battle_result(request.user, features, result)
            
            return success_response({
                'battle': {
                    'battle_id': result.battle_id,
                    'outcome': result.outcome.value,
                    'attack_score': result.attack_score,
                    'defense_score': result.defense_score,
                    'estimated_crack_time': result.estimated_crack_time_seconds,
                    'crack_time_human': result.crack_time_human,
                    'vulnerabilities': result.key_vulnerabilities,
                    'strengths': result.key_strengths,
                    'recommendations': [
                        {
                            'title': r.title,
                            'description': r.description,
                            'priority': r.priority.value,
                            'action_items': r.action_items,
                            'estimated_improvement': r.estimated_improvement
                        }
                        for r in result.recommendations
                    ],
                    'rounds': [
                        {
                            'round': r.round_number,
                            'attack': r.attack_used,
                            'attack_success': r.attack_success_prob,
                            'defense': r.defense_applied,
                            'winner': r.round_winner
                        }
                        for r in result.rounds
                    ]
                }
            })
        else:
            # Quick analysis only
            analysis = engine.get_quick_assessment(features)
            
            return success_response({
                'analysis': analysis
            })
    
    except Exception as e:
        logger.error(f"Error analyzing password: {e}")
        return error_response(str(e), status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def analyze_raw_password(request):
    """
    Analyze password using adversarial AI with ML-powered feature extraction.
    
    This endpoint integrates with ml_security.PasswordStrengthPredictor to 
    automatically extract features from the raw password.
    
    POST Data:
    {
        "password": str,  # The raw password to analyze
        "run_full_battle": bool (optional, default: false),
        "save_result": bool (optional, default: true)
    }
    
    Returns:
    {
        "success": true,
        "features": {...},  # Extracted features
        "analysis": {...},  # Quick analysis result
        "battle": {...}  # Full battle result (if run_full_battle=true)
    }
    """
    try:
        password = request.data.get('password', '')
        run_full_battle = request.data.get('run_full_battle', False)
        save_result = request.data.get('save_result', True)
        
        if not password:
            return error_response("Password is required", status.HTTP_400_BAD_REQUEST)
        
        # Get the PasswordStrengthPredictor for feature extraction
        predictor = get_password_predictor()
        
        if predictor:
            # Use ML-powered feature extraction
            features = predictor.get_adversarial_features(password)
            logger.debug("Using ML-powered feature extraction from PasswordStrengthPredictor")
        else:
            # Fallback to manual extraction
            features = _extract_features_manually(password)
            logger.debug("Using manual feature extraction (ml_security not available)")
        
        engine = get_game_engine()
        
        if run_full_battle:
            result = engine.run_battle(features, request.user.id)
            
            if save_result:
                _save_battle_result(request.user, features, result)
            
            return success_response({
                'features': features,
                'battle': {
                    'battle_id': result.battle_id,
                    'outcome': result.outcome.value,
                    'attack_score': result.attack_score,
                    'defense_score': result.defense_score,
                    'estimated_crack_time': result.estimated_crack_time_seconds,
                    'crack_time_human': result.crack_time_human,
                    'vulnerabilities': result.key_vulnerabilities,
                    'strengths': result.key_strengths,
                    'recommendations': [
                        {
                            'title': r.title,
                            'description': r.description,
                            'priority': r.priority.value,
                            'action_items': r.action_items,
                            'estimated_improvement': r.estimated_improvement
                        }
                        for r in result.recommendations
                    ],
                }
            })
        else:
            analysis = engine.get_quick_assessment(features)
            
            return success_response({
                'features': features,
                'analysis': analysis
            })
    
    except Exception as e:
        logger.error(f"Error analyzing raw password: {e}")
        return error_response(str(e), status.HTTP_500_INTERNAL_SERVER_ERROR)


def _extract_features_manually(password: str) -> dict:
    """
    Manual feature extraction fallback when ml_security is not available.
    """
    import re
    import math
    from collections import Counter
    
    # Calculate entropy
    def calc_entropy(pwd):
        if not pwd:
            return 0.0
        counter = Counter(pwd)
        length = len(pwd)
        entropy = 0.0
        for count in counter.values():
            probability = count / length
            if probability > 0:
                entropy -= probability * math.log2(probability)
        return entropy * length
    
    # Check common patterns
    patterns = [
        r'qwerty', r'asdf', r'zxcv', r'12345', r'password',
        r'(.)\1{2,}',  # Repeated chars
    ]
    has_common = any(re.search(p, password.lower()) for p in patterns)
    
    # Calculate diversity
    unique = len(set(password.lower()))
    diversity = unique / len(password) if password else 0
    
    return {
        'length': len(password),
        'entropy': calc_entropy(password),
        'has_upper': bool(re.search(r'[A-Z]', password)),
        'has_lower': bool(re.search(r'[a-z]', password)),
        'has_digit': bool(re.search(r'\d', password)),
        'has_special': bool(re.search(r'[^A-Za-z0-9]', password)),
        'has_common_patterns': has_common,
        'character_diversity': diversity,
        'guessability_score': 50,  # Default
        'pattern_info': {
            'keyboard_walk': bool(re.search(r'qwerty|asdf|zxcv', password.lower())),
            'date_pattern': bool(re.search(r'\d{4}$|19\d{2}|20\d{2}', password)),
            'repeated_chars': bool(re.search(r'(.)\1{2,}', password)),
        }
    }

def _save_battle_result(user, features, result):
    """Save battle result to database."""
    try:
        # Create password hash for deduplication
        feature_str = f"{features.get('length', 0)}-{features.get('entropy', 0)}"
        password_hash = hashlib.sha256(feature_str.encode()).hexdigest()
        
        battle = AdversarialBattle.objects.create(
            user=user,
            password_hash=password_hash,
            password_entropy=features.get('entropy', 0),
            password_length=features.get('length', 0),
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
        
        # Record to learning system
        learning = get_learning_system()
        learning.record_battle_result(features, {
            'attack_score': result.attack_score,
            'attack_vectors_used': [r.attack_used for r in result.rounds]
        })
        
        # Create recommendations if needed
        for rec in result.recommendations[:3]:  # Top 3
            DefenseRecommendation.objects.create(
                user=user,
                battle=battle,
                title=rec.title,
                description=rec.description,
                priority=rec.priority.value,
                action_items=rec.action_items,
                estimated_strength_improvement=rec.estimated_improvement
            )
        
        return battle
        
    except Exception as e:
        logger.error(f"Error saving battle result: {e}")
        return None


# =============================================================================
# RECOMMENDATIONS
# =============================================================================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_recommendations(request):
    """
    Get personalized defense recommendations for the user.
    
    Query Parameters:
    - limit: Number of recommendations to return (default: 10)
    - status: Filter by status (pending/viewed/applied/dismissed)
    
    Returns:
    {
        "success": true,
        "recommendations": [...]
    }
    """
    try:
        limit = int(request.query_params.get('limit', 10))
        status_filter = request.query_params.get('status', None)
        
        queryset = DefenseRecommendation.objects.filter(user=request.user)
        
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        recommendations = queryset.order_by('-priority', '-created_at')[:limit]
        
        return success_response({
            'recommendations': [
                {
                    'id': r.id,
                    'title': r.title,
                    'description': r.description,
                    'priority': r.priority,
                    'status': r.status,
                    'action_items': r.action_items,
                    'estimated_improvement': r.estimated_strength_improvement,
                    'created_at': r.created_at.isoformat()
                }
                for r in recommendations
            ]
        })
    
    except Exception as e:
        logger.error(f"Error getting recommendations: {e}")
        return error_response(str(e), status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def update_recommendation_status(request, recommendation_id):
    """
    Update recommendation status.
    
    POST Data:
    {
        "status": "viewed" | "applied" | "dismissed"
    }
    """
    try:
        new_status = request.data.get('status')
        
        if new_status not in ['viewed', 'applied', 'dismissed']:
            return error_response("Invalid status", status.HTTP_400_BAD_REQUEST)
        
        recommendation = DefenseRecommendation.objects.filter(
            id=recommendation_id,
            user=request.user
        ).first()
        
        if not recommendation:
            return error_response("Recommendation not found", status.HTTP_404_NOT_FOUND)
        
        recommendation.status = new_status
        
        if new_status == 'viewed':
            recommendation.viewed_at = timezone.now()
        elif new_status == 'applied':
            recommendation.applied_at = timezone.now()
            
            # Update user profile
            profile, _ = UserDefenseProfile.objects.get_or_create(user=request.user)
            profile.recommendations_applied += 1
            profile.save()
        
        recommendation.save()
        
        return success_response({
            'recommendation_id': recommendation_id,
            'new_status': new_status
        })
    
    except Exception as e:
        logger.error(f"Error updating recommendation: {e}")
        return error_response(str(e), status.HTTP_500_INTERNAL_SERVER_ERROR)


# =============================================================================
# BATTLE HISTORY
# =============================================================================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_battle_history(request):
    """
    Get user's adversarial battle history.
    
    Query Parameters:
    - limit: Number of battles to return (default: 20)
    - outcome: Filter by outcome (defender_wins/attacker_wins/draw)
    
    Returns:
    {
        "success": true,
        "battles": [...],
        "summary": {...}
    }
    """
    try:
        limit = int(request.query_params.get('limit', 20))
        outcome_filter = request.query_params.get('outcome', None)
        
        queryset = AdversarialBattle.objects.filter(user=request.user)
        
        if outcome_filter:
            queryset = queryset.filter(outcome=outcome_filter)
        
        battles = queryset.order_by('-created_at')[:limit]
        
        # Calculate summary stats
        all_battles = AdversarialBattle.objects.filter(user=request.user)
        total = all_battles.count()
        wins = all_battles.filter(outcome='defender_wins').count()
        losses = all_battles.filter(outcome='attacker_wins').count()
        
        return success_response({
            'battles': [
                {
                    'id': b.id,
                    'outcome': b.outcome,
                    'attack_score': b.attack_score,
                    'defense_score': b.defense_score,
                    'crack_time_seconds': b.estimated_crack_time_seconds,
                    'attack_vectors': b.attack_vectors_used,
                    'created_at': b.created_at.isoformat()
                }
                for b in battles
            ],
            'summary': {
                'total_battles': total,
                'defender_wins': wins,
                'attacker_wins': losses,
                'draws': total - wins - losses,
                'win_rate': wins / total if total > 0 else 0
            }
        })
    
    except Exception as e:
        logger.error(f"Error getting battle history: {e}")
        return error_response(str(e), status.HTTP_500_INTERNAL_SERVER_ERROR)


# =============================================================================
# TRENDING ATTACKS
# =============================================================================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_trending_attacks(request):
    """
    Get currently trending attack patterns.
    
    Query Parameters:
    - limit: Number of trends to return (default: 5)
    
    Returns:
    {
        "success": true,
        "trending": [...],
        "insights": {...}
    }
    """
    try:
        limit = int(request.query_params.get('limit', 5))
        
        learning = get_learning_system()
        trends = learning.get_trending_attacks(limit)
        insights = learning.get_aggregated_insights()
        
        return success_response({
            'trending': [
                {
                    'attack_type': t.attack_type,
                    'direction': t.trend_direction,
                    'velocity': t.velocity,
                    'affected_count': t.affected_pattern_count,
                    'recommended_defenses': t.recommended_defenses
                }
                for t in trends
            ],
            'insights': insights
        })
    
    except Exception as e:
        logger.error(f"Error getting trending attacks: {e}")
        return error_response(str(e), status.HTTP_500_INTERNAL_SERVER_ERROR)


# =============================================================================
# USER PROFILE
# =============================================================================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_defense_profile(request):
    """
    Get user's defense profile.
    
    Returns:
    {
        "success": true,
        "profile": {...}
    }
    """
    try:
        profile, created = UserDefenseProfile.objects.get_or_create(user=request.user)
        
        return success_response({
            'profile': {
                'overall_score': profile.overall_defense_score,
                'historical_average': profile.historical_average_score,
                'total_battles': profile.total_battles,
                'battles_won': profile.battles_won,
                'battles_lost': profile.battles_lost,
                'win_rate': profile.battles_won / profile.total_battles 
                    if profile.total_battles > 0 else 0,
                'common_vulnerabilities': profile.common_vulnerabilities,
                'strong_practices': profile.strong_practices,
                'recommendations_applied': profile.recommendations_applied,
                'improvement_rate': profile.improvement_rate,
                'last_battle': profile.last_battle_at.isoformat() 
                    if profile.last_battle_at else None
            },
            'is_new': created
        })
    
    except Exception as e:
        logger.error(f"Error getting defense profile: {e}")
        return error_response(str(e), status.HTTP_500_INTERNAL_SERVER_ERROR)

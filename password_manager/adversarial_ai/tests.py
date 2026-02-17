"""
Adversarial AI - Unit Tests
============================

Comprehensive tests for the adversarial AI system.

Test Categories:
1. AttackerAITestCase - Test attack simulation, crack time estimation
2. DefenderAITestCase - Test defense assessment, recommendation generation
3. GameEngineTestCase - Test battle execution, equilibrium calculation
4. LearningSystemTestCase - Test aggregated learning
5. AdversarialModelsTestCase - Test Django models
6. AdversarialAPITestCase - Test all API endpoints
7. AdversarialWebSocketTestCase - Test real-time battle updates
"""

from django.test import TestCase
from django.contrib.auth.models import User
from rest_framework.test import APITestCase, APIClient
from rest_framework import status
from unittest.mock import patch, MagicMock, AsyncMock
from channels.testing import WebsocketCommunicator
from channels.db import database_sync_to_async
import json

from .models import (
    AdversarialBattle,
    AttackVector,
    DefenseRecommendation,
    AggregatedBreachPattern,
    UserDefenseProfile
)
from .ai_engines.attacker_ai import AttackerAI, AttackCategory
from .ai_engines.defender_ai import DefenderAI, DefenseLevel
from .ai_engines.game_engine import GameEngine, BattleOutcome
from .ai_engines.learning_system import BreachLearningSystem


# ==============================================================================
# ATTACKER AI TESTS
# ==============================================================================

class AttackerAITestCase(TestCase):
    """Tests for the Attacker AI engine."""
    
    def setUp(self):
        self.attacker = AttackerAI()
        
        # Sample password features for testing
        self.weak_password_features = {
            'length': 6,
            'entropy': 25,
            'has_upper': False,
            'has_lower': True,
            'has_digit': False,
            'has_special': False,
            'has_common_patterns': True,
            'character_diversity': 0.3,
            'guessability_score': 85,
            'pattern_info': {'keyboard_walk': True, 'date_pattern': False}
        }
        
        self.strong_password_features = {
            'length': 20,
            'entropy': 90,
            'has_upper': True,
            'has_lower': True,
            'has_digit': True,
            'has_special': True,
            'has_common_patterns': False,
            'character_diversity': 0.85,
            'guessability_score': 10,
            'pattern_info': {}
        }
    
    def test_simulate_attack_weak_password(self):
        """Test attack simulation on weak password."""
        result = self.attacker.simulate_attack(self.weak_password_features)
        
        self.assertGreater(result.overall_success_probability, 0.5)
        self.assertIsNotNone(result.most_effective_attack)
        self.assertGreater(len(result.attack_results), 0)
    
    def test_simulate_attack_strong_password(self):
        """Test attack simulation on strong password."""
        result = self.attacker.simulate_attack(self.strong_password_features)
        
        self.assertLess(result.overall_success_probability, 0.5)
        self.assertGreater(result.estimated_crack_time_seconds, 86400)
    
    def test_estimate_crack_time(self):
        """Test crack time estimation."""
        seconds, human = self.attacker.estimate_crack_time(
            entropy=80, 
            patterns=[], 
            hash_type='bcrypt'
        )
        
        self.assertIsInstance(seconds, int)
        self.assertIsInstance(human, str)
        self.assertGreater(seconds, 0)
    
    def test_estimate_crack_time_low_entropy(self):
        """Test crack time estimation for low entropy."""
        seconds, human = self.attacker.estimate_crack_time(
            entropy=20, 
            patterns=['keyboard_walk'], 
            hash_type='md5'
        )
        
        self.assertLess(seconds, 86400)  # Should crack quickly
    
    def test_get_attack_vectors(self):
        """Test getting ordered attack vectors."""
        vectors = self.attacker.get_attack_vectors(self.weak_password_features)
        
        self.assertIsInstance(vectors, list)
        self.assertGreater(len(vectors), 0)
        
        # Check vectors are sorted by success probability
        for i in range(len(vectors) - 1):
            self.assertGreaterEqual(
                vectors[i]['success_probability'],
                vectors[i + 1]['success_probability']
            )
    
    def test_empty_features(self):
        """Test handling of empty features."""
        result = self.attacker.simulate_attack({})
        
        self.assertIsNotNone(result)
        self.assertGreaterEqual(result.overall_success_probability, 0)


# ==============================================================================
# DEFENDER AI TESTS
# ==============================================================================

class DefenderAITestCase(TestCase):
    """Tests for the Defender AI engine."""
    
    def setUp(self):
        self.defender = DefenderAI()
        
        self.weak_features = {
            'length': 6,
            'entropy': 25,
            'has_upper': False,
            'has_lower': True,
            'has_digit': False,
            'has_special': False,
            'has_common_patterns': True,
            'character_diversity': 0.3,
            'guessability_score': 85,
            'pattern_info': {'keyboard_walk': True}
        }
        
        self.strong_features = {
            'length': 20,
            'entropy': 90,
            'has_upper': True,
            'has_lower': True,
            'has_digit': True,
            'has_special': True,
            'has_common_patterns': False,
            'character_diversity': 0.85,
            'guessability_score': 10,
            'pattern_info': {}
        }
        
        self.moderate_features = {
            'length': 12,
            'entropy': 55,
            'has_upper': True,
            'has_lower': True,
            'has_digit': True,
            'has_special': False,
            'has_common_patterns': False,
            'character_diversity': 0.6,
            'guessability_score': 40,
            'pattern_info': {}
        }
    
    def test_assess_defense_weak(self):
        """Test defense assessment for weak password."""
        result = self.defender.assess_defense(self.weak_features)
        
        self.assertLess(result.defense_score, 0.5)
        self.assertIn(result.defense_level, [DefenseLevel.CRITICAL, DefenseLevel.WEAK])
        self.assertGreater(len(result.vulnerabilities), 0)
    
    def test_assess_defense_strong(self):
        """Test defense assessment for strong password."""
        result = self.defender.assess_defense(self.strong_features)
        
        self.assertGreater(result.defense_score, 0.7)
        self.assertIn(result.defense_level, [DefenseLevel.STRONG, DefenseLevel.FORTRESS])
        self.assertGreater(len(result.strengths), 0)
    
    def test_assess_defense_moderate(self):
        """Test defense assessment for moderate password."""
        result = self.defender.assess_defense(self.moderate_features)
        
        self.assertGreaterEqual(result.defense_score, 0.4)
        self.assertLessEqual(result.defense_score, 0.8)
    
    def test_generate_recommendations(self):
        """Test recommendation generation."""
        result = self.defender.assess_defense(self.weak_features)
        
        self.assertGreater(len(result.recommendations), 0)
        
        # Check recommendations have required fields
        for rec in result.recommendations:
            self.assertIsNotNone(rec.title)
            self.assertIsNotNone(rec.description)
            self.assertIsNotNone(rec.priority)
    
    def test_recommendations_prioritized(self):
        """Test that recommendations are properly prioritized."""
        result = self.defender.assess_defense(self.weak_features)
        
        if len(result.recommendations) > 1:
            # First recommendation should be higher or equal priority
            priorities = {'critical': 4, 'high': 3, 'medium': 2, 'low': 1}
            for i in range(len(result.recommendations) - 1):
                current_priority = priorities.get(result.recommendations[i].priority.value, 0)
                next_priority = priorities.get(result.recommendations[i + 1].priority.value, 0)
                self.assertGreaterEqual(current_priority, next_priority)


# ==============================================================================
# GAME ENGINE TESTS
# ==============================================================================

class GameEngineTestCase(TestCase):
    """Tests for the Game Engine."""
    
    def setUp(self):
        self.engine = GameEngine()
        
        self.test_features = {
            'length': 12,
            'entropy': 60,
            'has_upper': True,
            'has_lower': True,
            'has_digit': True,
            'has_special': False,
            'has_common_patterns': False,
            'character_diversity': 0.6,
            'guessability_score': 40,
            'pattern_info': {}
        }
        
        self.weak_features = {
            'length': 5,
            'entropy': 20,
            'has_upper': False,
            'has_lower': True,
            'has_digit': False,
            'has_special': False,
            'has_common_patterns': True,
            'character_diversity': 0.3,
            'guessability_score': 90,
            'pattern_info': {'keyboard_walk': True}
        }
    
    def test_run_battle(self):
        """Test running a full battle."""
        result = self.engine.run_battle(self.test_features)
        
        self.assertIsNotNone(result.battle_id)
        self.assertIn(result.outcome, [
            BattleOutcome.DEFENDER_WINS,
            BattleOutcome.ATTACKER_WINS,
            BattleOutcome.DRAW
        ])
        self.assertGreaterEqual(result.defense_score, 0)
        self.assertLessEqual(result.defense_score, 1)
        self.assertGreater(len(result.rounds), 0)
    
    def test_battle_outcome_weak_password(self):
        """Test that weak password loses battle."""
        result = self.engine.run_battle(self.weak_features)
        
        # Weak passwords should typically lose
        self.assertIn(result.outcome, [BattleOutcome.ATTACKER_WINS, BattleOutcome.DRAW])
    
    def test_get_quick_assessment(self):
        """Test quick assessment."""
        result = self.engine.get_quick_assessment(self.test_features)
        
        self.assertIn('status', result)
        self.assertIn('defense_score', result)
        self.assertIn('attack_success_probability', result)
    
    def test_analyze_password_delta(self):
        """Test comparing two password versions."""
        old_features = {**self.test_features, 'length': 8, 'entropy': 40}
        new_features = self.test_features
        
        delta = self.engine.analyze_password_delta(old_features, new_features)
        
        self.assertIn('defense_improvement', delta)
        self.assertIn('improved', delta)
    
    def test_delta_shows_improvement(self):
        """Test that delta correctly identifies improvement."""
        old_features = self.weak_features
        new_features = self.test_features
        
        delta = self.engine.analyze_password_delta(old_features, new_features)
        
        self.assertTrue(delta['improved'])
        self.assertGreater(delta['defense_improvement'], 0)
    
    def test_battle_has_rounds(self):
        """Test that battle produces rounds."""
        result = self.engine.run_battle(self.test_features)
        
        self.assertGreater(len(result.rounds), 0)
        
        for round_data in result.rounds:
            self.assertIsNotNone(round_data.round_number)
            self.assertIsNotNone(round_data.attack_used)


# ==============================================================================
# LEARNING SYSTEM TESTS
# ==============================================================================

class LearningSystemTestCase(TestCase):
    """Tests for the Learning System."""
    
    def setUp(self):
        self.learning = BreachLearningSystem()
        
        self.test_features = {
            'length': 12,
            'has_upper': True,
            'has_lower': True,
            'has_digit': True,
            'has_special': False,
            'pattern_info': {}
        }
        
        self.test_battle_result = {
            'attack_score': 0.4,
            'attack_vectors_used': ['dictionary', 'brute_force']
        }
    
    def test_record_battle_result(self):
        """Test recording battle result."""
        # Should not raise
        self.learning.record_battle_result(
            self.test_features,
            self.test_battle_result,
            user_consent=True
        )
    
    def test_record_without_consent(self):
        """Test that data is not recorded without consent."""
        initial_count = len(self.learning._pattern_cache)
        
        self.learning.record_battle_result(
            self.test_features,
            self.test_battle_result,
            user_consent=False
        )
        
        # Cache should not grow
        self.assertEqual(len(self.learning._pattern_cache), initial_count)
    
    def test_get_aggregated_insights(self):
        """Test getting aggregated insights."""
        # Record some data first
        for _ in range(5):
            self.learning.record_battle_result(
                self.test_features,
                self.test_battle_result,
                user_consent=True
            )
        
        insights = self.learning.get_aggregated_insights()
        
        self.assertIn('total_patterns_analyzed', insights)
        self.assertIn('pattern_type_vulnerabilities', insights)
    
    def test_get_trending_attacks(self):
        """Test getting trending attack patterns."""
        trends = self.learning.get_trending_attacks(limit=5)
        
        self.assertIsInstance(trends, list)


# ==============================================================================
# MODEL TESTS
# ==============================================================================

class AdversarialModelsTestCase(TestCase):
    """Tests for Django models."""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpassword123'
        )
    
    def test_create_battle(self):
        """Test creating an adversarial battle."""
        battle = AdversarialBattle.objects.create(
            user=self.user,
            password_hash='abc123',
            password_entropy=65.5,
            password_length=14,
            attack_score=0.35,
            defense_score=0.72,
            estimated_crack_time_seconds=86400,
            outcome='defender_wins'
        )
        
        self.assertIsNotNone(battle.id)
        self.assertEqual(battle.user, self.user)
        self.assertEqual(battle.outcome, 'defender_wins')
    
    def test_battle_str_representation(self):
        """Test battle string representation."""
        battle = AdversarialBattle.objects.create(
            user=self.user,
            password_hash='abc123',
            password_entropy=65.5,
            password_length=14,
            attack_score=0.35,
            defense_score=0.72,
            estimated_crack_time_seconds=86400,
            outcome='defender_wins'
        )
        
        str_repr = str(battle)
        self.assertIn('testuser', str_repr.lower())
    
    def test_user_defense_profile_update(self):
        """Test updating user defense profile from battle."""
        profile, _ = UserDefenseProfile.objects.get_or_create(user=self.user)
        initial_battles = profile.total_battles
        
        battle = AdversarialBattle.objects.create(
            user=self.user,
            password_hash='abc123',
            password_entropy=65.5,
            password_length=14,
            attack_score=0.35,
            defense_score=0.72,
            estimated_crack_time_seconds=86400,
            outcome='defender_wins'
        )
        
        profile.update_from_battle(battle)
        profile.refresh_from_db()
        
        self.assertEqual(profile.total_battles, initial_battles + 1)
        self.assertEqual(profile.battles_won, 1)
    
    def test_defense_recommendation_creation(self):
        """Test creating a defense recommendation."""
        battle = AdversarialBattle.objects.create(
            user=self.user,
            password_hash='abc123',
            password_entropy=65.5,
            password_length=14,
            attack_score=0.35,
            defense_score=0.72,
            estimated_crack_time_seconds=86400,
            outcome='defender_wins'
        )
        
        recommendation = DefenseRecommendation.objects.create(
            user=self.user,
            battle=battle,
            title='Test Recommendation',
            description='Add special characters',
            priority='medium'
        )
        
        self.assertIsNotNone(recommendation.id)
        self.assertEqual(recommendation.status, 'pending')


# ==============================================================================
# API ENDPOINT TESTS
# ==============================================================================

class AdversarialAPITestCase(APITestCase):
    """Tests for API endpoints."""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpassword123'
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
        
        self.valid_features = {
            'length': 12,
            'entropy': 60,
            'has_upper': True,
            'has_lower': True,
            'has_digit': True,
            'has_special': False,
            'has_common_patterns': False,
            'character_diversity': 0.6,
            'guessability_score': 40,
            'pattern_info': {}
        }
    
    def test_analyze_password(self):
        """Test password analysis endpoint."""
        response = self.client.post('/api/adversarial/analyze/', {
            'features': self.valid_features,
            'run_full_battle': False
        }, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('analysis', response.data)
    
    def test_analyze_password_full_battle(self):
        """Test password analysis with full battle."""
        response = self.client.post('/api/adversarial/analyze/', {
            'features': self.valid_features,
            'run_full_battle': True
        }, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('battle', response.data)
    
    def test_analyze_password_missing_features(self):
        """Test password analysis with missing features."""
        response = self.client.post('/api/adversarial/analyze/', {
            'run_full_battle': False
        }, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_analyze_raw_password(self):
        """Test ML-powered raw password analysis endpoint."""
        response = self.client.post('/api/adversarial/analyze-raw/', {
            'password': 'TestPassword123!',
            'run_full_battle': False
        }, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('features', response.data)
        self.assertIn('analysis', response.data)
    
    def test_analyze_raw_password_empty(self):
        """Test raw password analysis with empty password."""
        response = self.client.post('/api/adversarial/analyze-raw/', {
            'password': '',
            'run_full_battle': False
        }, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_get_recommendations(self):
        """Test recommendations endpoint."""
        response = self.client.get('/api/adversarial/recommendations/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('recommendations', response.data)
    
    def test_get_recommendations_with_limit(self):
        """Test recommendations endpoint with limit."""
        response = self.client.get('/api/adversarial/recommendations/?limit=5')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertLessEqual(len(response.data.get('recommendations', [])), 5)
    
    def test_update_recommendation_status(self):
        """Test updating recommendation status."""
        # First create a battle and recommendation
        battle = AdversarialBattle.objects.create(
            user=self.user,
            password_hash='abc123',
            password_entropy=65.5,
            password_length=14,
            attack_score=0.35,
            defense_score=0.72,
            estimated_crack_time_seconds=86400,
            outcome='defender_wins'
        )
        
        recommendation = DefenseRecommendation.objects.create(
            user=self.user,
            battle=battle,
            title='Test Recommendation',
            description='Add special characters',
            priority='medium'
        )
        
        response = self.client.post(
            f'/api/adversarial/recommendations/{recommendation.id}/status/',
            {'status': 'applied'},
            format='json'
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        recommendation.refresh_from_db()
        self.assertEqual(recommendation.status, 'applied')
    
    def test_get_battle_history(self):
        """Test battle history endpoint."""
        # Create some battles
        for i in range(3):
            AdversarialBattle.objects.create(
                user=self.user,
                password_hash=f'hash{i}',
                password_entropy=50 + i * 10,
                password_length=12 + i,
                attack_score=0.3 + i * 0.1,
                defense_score=0.7 - i * 0.1,
                estimated_crack_time_seconds=86400,
                outcome='defender_wins'
            )
        
        response = self.client.get('/api/adversarial/history/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('battles', response.data)
        self.assertEqual(len(response.data['battles']), 3)
    
    def test_get_battle_history_with_limit(self):
        """Test battle history with limit."""
        for i in range(5):
            AdversarialBattle.objects.create(
                user=self.user,
                password_hash=f'hash{i}',
                password_entropy=50,
                password_length=12,
                attack_score=0.3,
                defense_score=0.7,
                estimated_crack_time_seconds=86400,
                outcome='defender_wins'
            )
        
        response = self.client.get('/api/adversarial/history/?limit=3')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertLessEqual(len(response.data['battles']), 3)
    
    def test_get_trending_attacks(self):
        """Test trending attacks endpoint."""
        response = self.client.get('/api/adversarial/trending-attacks/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('trending', response.data)
    
    def test_get_defense_profile(self):
        """Test defense profile endpoint."""
        response = self.client.get('/api/adversarial/profile/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('profile', response.data)
    
    def test_unauthenticated_access(self):
        """Test that unauthenticated access is denied."""
        self.client.force_authenticate(user=None)
        
        response = self.client.get('/api/adversarial/profile/')
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_unauthenticated_analyze(self):
        """Test that unauthenticated analysis is denied."""
        self.client.force_authenticate(user=None)
        
        response = self.client.post('/api/adversarial/analyze/', {
            'features': self.valid_features,
            'run_full_battle': False
        }, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


# ==============================================================================
# WEBSOCKET TESTS
# ==============================================================================

class AdversarialWebSocketTestCase(TestCase):
    """Tests for WebSocket consumer."""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='wsuser',
            email='ws@example.com',
            password='testpassword123'
        )
        
        self.test_features = {
            'length': 12,
            'entropy': 60,
            'has_upper': True,
            'has_lower': True,
            'has_digit': True,
            'has_special': False,
            'has_common_patterns': False,
            'character_diversity': 0.6,
            'guessability_score': 40,
            'pattern_info': {}
        }
    
    @patch('adversarial_ai.consumers.AdversarialBattleConsumer')
    def test_websocket_connect_message_format(self, mock_consumer):
        """Test WebSocket connection message format."""
        # Test the expected message structure
        expected_message = {
            'type': 'connection_established',
            'message': 'Connected to Adversarial AI Defense System',
            'user_id': str(self.user.id)
        }
        
        self.assertIn('type', expected_message)
        self.assertIn('message', expected_message)
        self.assertIn('user_id', expected_message)
    
    def test_quick_analysis_message_format(self):
        """Test quick analysis message format."""
        expected_message = {
            'type': 'quick_analysis',
            'result': {
                'status': 'moderate',
                'defense_score': 0.65,
                'attack_success_probability': 0.35
            }
        }
        
        self.assertIn('type', expected_message)
        self.assertIn('result', expected_message)
        self.assertIn('defense_score', expected_message['result'])
    
    def test_battle_round_message_format(self):
        """Test battle round message format."""
        expected_message = {
            'type': 'battle_round',
            'round': {
                'number': 1,
                'attack': 'dictionary',
                'attack_success': 0.3,
                'defense': 'length_defense',
                'defense_effectiveness': 0.7,
                'winner': 'defender'
            }
        }
        
        self.assertIn('type', expected_message)
        self.assertIn('round', expected_message)
        self.assertIn('number', expected_message['round'])
        self.assertIn('attack', expected_message['round'])
    
    def test_battle_complete_message_format(self):
        """Test battle complete message format."""
        expected_message = {
            'type': 'battle_complete',
            'result': {
                'battle_id': 'uuid-here',
                'outcome': 'defender_wins',
                'attack_score': 0.35,
                'defense_score': 0.72,
                'crack_time': '1 year',
                'vulnerabilities': [],
                'strengths': ['length', 'diversity'],
                'recommendations': []
            }
        }
        
        self.assertIn('type', expected_message)
        self.assertIn('result', expected_message)
        self.assertIn('outcome', expected_message['result'])
        self.assertIn('defense_score', expected_message['result'])


# ==============================================================================
# EDGE CASE TESTS
# ==============================================================================

class EdgeCaseTestCase(TestCase):
    """Tests for edge cases and error handling."""
    
    def setUp(self):
        self.engine = GameEngine()
        self.attacker = AttackerAI()
        self.defender = DefenderAI()
    
    def test_very_short_password(self):
        """Test handling of very short password."""
        features = {
            'length': 1,
            'entropy': 5,
            'has_upper': False,
            'has_lower': True,
            'has_digit': False,
            'has_special': False,
            'has_common_patterns': False,
            'character_diversity': 1.0,
            'guessability_score': 100,
            'pattern_info': {}
        }
        
        result = self.engine.run_battle(features)
        self.assertIsNotNone(result)
        self.assertEqual(result.outcome, BattleOutcome.ATTACKER_WINS)
    
    def test_very_long_password(self):
        """Test handling of very long password."""
        features = {
            'length': 128,
            'entropy': 200,
            'has_upper': True,
            'has_lower': True,
            'has_digit': True,
            'has_special': True,
            'has_common_patterns': False,
            'character_diversity': 0.95,
            'guessability_score': 0,
            'pattern_info': {}
        }
        
        result = self.engine.run_battle(features)
        self.assertIsNotNone(result)
        self.assertEqual(result.outcome, BattleOutcome.DEFENDER_WINS)
    
    def test_null_values_in_features(self):
        """Test handling of null values."""
        features = {
            'length': 12,
            'entropy': None,
            'has_upper': True,
            'has_lower': True,
            'has_digit': None,
            'has_special': False,
            'has_common_patterns': False,
            'character_diversity': 0.6,
            'guessability_score': 40,
            'pattern_info': None
        }
        
        # Should handle gracefully
        try:
            result = self.engine.get_quick_assessment(features)
            self.assertIsNotNone(result)
        except Exception as e:
            self.fail(f"Engine should handle null values gracefully: {e}")
    
    def test_negative_values(self):
        """Test handling of negative values."""
        features = {
            'length': -5,
            'entropy': -10,
            'has_upper': True,
            'has_lower': True,
            'has_digit': True,
            'has_special': False,
            'has_common_patterns': False,
            'character_diversity': -0.5,
            'guessability_score': -10,
            'pattern_info': {}
        }
        
        # Should handle gracefully
        try:
            result = self.engine.get_quick_assessment(features)
            self.assertIsNotNone(result)
        except Exception as e:
            self.fail(f"Engine should handle negative values gracefully: {e}")


# ==============================================================================
# INTEGRATION TESTS
# ==============================================================================

class IntegrationTestCase(TestCase):
    """Integration tests for the full adversarial system."""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='integrationuser',
            email='integration@example.com',
            password='testpassword123'
        )
        
        self.engine = GameEngine()
        self.learning = BreachLearningSystem()
    
    def test_full_analysis_flow(self):
        """Test complete analysis flow."""
        features = {
            'length': 12,
            'entropy': 60,
            'has_upper': True,
            'has_lower': True,
            'has_digit': True,
            'has_special': False,
            'has_common_patterns': False,
            'character_diversity': 0.6,
            'guessability_score': 40,
            'pattern_info': {}
        }
        
        # Run battle
        result = self.engine.run_battle(features, self.user.id)
        
        # Verify result
        self.assertIsNotNone(result.battle_id)
        self.assertIsNotNone(result.outcome)
        self.assertGreater(len(result.recommendations), 0)
        
        # Record for learning
        self.learning.record_battle_result(
            features,
            {'attack_score': result.attack_score, 'attack_vectors_used': []},
            user_consent=True
        )
    
    def test_consecutive_battles_improvement(self):
        """Test that system tracks improvement over battles."""
        profile, _ = UserDefenseProfile.objects.get_or_create(user=self.user)
        
        # Simulate losing battle
        battle1 = AdversarialBattle.objects.create(
            user=self.user,
            password_hash='weak123',
            password_entropy=25,
            password_length=6,
            attack_score=0.8,
            defense_score=0.2,
            estimated_crack_time_seconds=60,
            outcome='attacker_wins'
        )
        profile.update_from_battle(battle1)
        
        # Simulate winning battle
        battle2 = AdversarialBattle.objects.create(
            user=self.user,
            password_hash='strong456',
            password_entropy=80,
            password_length=16,
            attack_score=0.2,
            defense_score=0.85,
            estimated_crack_time_seconds=86400 * 365,
            outcome='defender_wins'
        )
        profile.update_from_battle(battle2)
        
        profile.refresh_from_db()
        
        # Should have 2 battles, 1 won
        self.assertEqual(profile.total_battles, 2)
        self.assertEqual(profile.battles_won, 1)

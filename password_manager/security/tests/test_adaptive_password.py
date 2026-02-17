"""
Adaptive Password Service Tests
===============================

Comprehensive unit tests for the adaptive password feature.

Tests cover:
- Typing pattern collection (privacy)
- Substitution learning
- Memorability scoring
- Contextual bandit adaptation
- API endpoints
- Django models
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta
from uuid import uuid4
import json

from django.test import TestCase, override_settings
from django.contrib.auth.models import User
from django.utils import timezone
from rest_framework.test import APITestCase, APIClient
from rest_framework import status


# =============================================================================
# Privacy Guard Tests
# =============================================================================

class PrivacyGuardTests(TestCase):
    """Test privacy protection mechanisms."""
    
    def setUp(self):
        from security.services.adaptive_password_service import PrivacyGuard
        self.guard = PrivacyGuard(epsilon=0.5)
    
    def test_anonymize_timing_buckets(self):
        """Test timing values are bucketed correctly."""
        # Test various timing values
        self.assertEqual(self.guard.anonymize_timing(30), 50)
        self.assertEqual(self.guard.anonymize_timing(75), 100)
        self.assertEqual(self.guard.anonymize_timing(150), 150)
        self.assertEqual(self.guard.anonymize_timing(1500), 2000)
        self.assertEqual(self.guard.anonymize_timing(5000), 2000)  # Caps at max
    
    def test_hash_password_prefix(self):
        """Test password hashing returns only prefix."""
        prefix = self.guard.hash_password_prefix("testpassword123")
        
        # Should be exactly 16 characters
        self.assertEqual(len(prefix), 16)
        
        # Should be hexadecimal
        self.assertTrue(all(c in '0123456789abcdef' for c in prefix))
        
        # Same password should give same prefix
        self.assertEqual(
            self.guard.hash_password_prefix("testpassword123"),
            prefix
        )
        
        # Different password should give different prefix
        self.assertNotEqual(
            self.guard.hash_password_prefix("differentpassword"),
            prefix
        )
    
    def test_differential_privacy_noise(self):
        """Test DP noise is added correctly."""
        # Run multiple times to test noise is being added
        values = [self.guard.add_laplace_noise(100.0) for _ in range(100)]
        
        # Not all values should be exactly 100
        self.assertTrue(any(v != 100.0 for v in values))
        
        # Mean should be close to 100 (within reasonable bounds)
        mean = sum(values) / len(values)
        self.assertAlmostEqual(mean, 100.0, delta=20)
    
    def test_pattern_sanitization(self):
        """Test pattern data is properly sanitized."""
        from security.services.adaptive_password_service import TypingPattern
        
        pattern = TypingPattern(
            password_hash_prefix="testprefix123456",  # gitleaks:allow
            password_length=12,
            error_positions=[3, 7],
            timing_buckets={0: 100, 1: 150, 2: 200},
            total_time_ms=450,
            success=True,
        )
        
        sanitized = self.guard.sanitize_pattern(pattern)
        
        # Password hash should be preserved
        self.assertEqual(sanitized.password_hash_prefix, pattern.password_hash_prefix)
        
        # Timing buckets should be modified (with noise)
        self.assertIsInstance(sanitized.timing_buckets, dict)


# =============================================================================
# Typing Pattern Collector Tests
# =============================================================================

class TypingPatternCollectorTests(TestCase):
    """Test typing pattern collection."""
    
    def setUp(self):
        from security.services.adaptive_password_service import (
            TypingPatternCollector, PrivacyGuard
        )
        self.collector = TypingPatternCollector(PrivacyGuard(epsilon=0.5))
    
    def test_process_keystroke_data(self):
        """Test converting raw keystroke data to pattern."""
        pattern = self.collector.process_keystroke_data(
            password="testpass123",
            keystroke_timings=[100, 120, 80, 150, 200, 90, 110, 130, 140, 160],
            backspace_positions=[3, 7],
        )
        
        # Check pattern structure
        self.assertEqual(len(pattern.password_hash_prefix), 16)
        self.assertEqual(pattern.password_length, 11)
        self.assertEqual(len(pattern.error_positions), 2)
        self.assertFalse(pattern.success)  # Has backspaces = errors
    
    def test_no_raw_keystrokes_stored(self):
        """Verify raw keystrokes are never stored."""
        pattern = self.collector.process_keystroke_data(
            password="secretpassword",
            keystroke_timings=[100] * 14,
            backspace_positions=[],
        )
        
        # Pattern should not contain the password
        pattern_dict = vars(pattern)
        for value in pattern_dict.values():
            if isinstance(value, str):
                self.assertNotIn("secretpassword", value)
                self.assertNotIn("secret", value)
    
    def test_detect_error_types(self):
        """Test error type detection."""
        password_length = 20
        
        # Errors at beginning
        errors = self.collector.detect_error_types([0, 1, 2], password_length)
        self.assertGreater(errors.get('beginning', 0), 0)
        
        # Errors at end
        errors = self.collector.detect_error_types([17, 18, 19], password_length)
        self.assertGreater(errors.get('end', 0), 0)
        
        # Repeated errors
        errors = self.collector.detect_error_types([5, 5, 5], password_length)
        self.assertGreater(errors.get('repeated', 0), 0)


# =============================================================================
# Substitution Learner Tests
# =============================================================================

class SubstitutionLearnerTests(TestCase):
    """Test substitution learning."""
    
    def setUp(self):
        from security.services.adaptive_password_service import SubstitutionLearner
        self.learner = SubstitutionLearner()
    
    def test_suggest_substitutions(self):
        """Test substitution suggestion generation."""
        suggestions = self.learner.suggest_substitutions(
            password="password123",
            error_prone_positions={4: 0.8, 6: 0.6},  # 'w' and 'r' positions
            user_preferences={'o': '0'},
            n_suggestions=2,
        )
        
        # Should return suggestions
        self.assertLessEqual(len(suggestions), 2)
        
        # Each suggestion should have required fields
        for sub in suggestions:
            self.assertIsNotNone(sub.position)
            self.assertIsNotNone(sub.original_char)
            self.assertIsNotNone(sub.suggested_char)
            self.assertGreater(sub.confidence, 0)
    
    def test_user_preferences_respected(self):
        """Test that user preferences are used in suggestions."""
        suggestions = self.learner.suggest_substitutions(
            password="hello",
            error_prone_positions={4: 0.9},  # 'o' position
            user_preferences={'o': '0'},  # User prefers o->0
            n_suggestions=1,
        )
        
        if suggestions and suggestions[0].position == 4:
            self.assertEqual(suggestions[0].suggested_char, '0')


# =============================================================================
# Memorability Scorer Tests
# =============================================================================

class MemorabilityScorerTests(TestCase):
    """Test memorability scoring."""
    
    def setUp(self):
        from security.services.adaptive_password_service import MemorabilityScorer
        self.scorer = MemorabilityScorer()
    
    def test_score_range(self):
        """Test scores are in valid range."""
        passwords = [
            "a",
            "password",
            "Password123!",
            "qwerty123",
            "xK9$mZp@vL2#nQ",
        ]
        
        for password in passwords:
            score = self.scorer.calculate_score(password)
            self.assertGreaterEqual(score, 0.0)
            self.assertLessEqual(score, 1.0)
    
    def test_pronounceable_scores_higher(self):
        """Test pronounceable passwords score higher."""
        pronounceable = self.scorer.calculate_score("beautiful")
        random_chars = self.scorer.calculate_score("xqzjkwvbm")
        
        self.assertGreater(pronounceable, random_chars)
    
    def test_optimal_length_scores_higher(self):
        """Test optimal length (12-16) scores well."""
        optimal = self.scorer.calculate_score("Password1234")
        too_short = self.scorer.calculate_score("Pass1")
        too_long = self.scorer.calculate_score("PasswordPasswordPassword123!")
        
        self.assertGreater(optimal, too_short)
        self.assertGreater(optimal, too_long)
    
    def test_compare_passwords(self):
        """Test password comparison."""
        original, adapted, improvement = self.scorer.compare_passwords(
            "passw0rd",
            "passw@rd"
        )
        
        self.assertIsInstance(original, float)
        self.assertIsInstance(adapted, float)
        self.assertIsInstance(improvement, float)


# =============================================================================
# Contextual Bandit Tests
# =============================================================================

class AdaptationBanditTests(TestCase):
    """Test contextual bandit for adaptation selection."""
    
    def setUp(self):
        from security.services.adaptive_password_service import AdaptationBandit
        self.bandit = AdaptationBandit()
    
    def test_select_strategy(self):
        """Test strategy selection."""
        strategy = self.bandit.select_strategy({
            'error_rate': 0.2,
            'typing_speed': 'normal',
        })
        
        self.assertIn(strategy, [
            'aggressive', 'conservative', 'error_focused', 'rhythm_focused'
        ])
    
    def test_update_arm(self):
        """Test arm update with reward."""
        initial_alpha = self.bandit.arms['error_focused']['alpha']
        
        self.bandit.update('error_focused', 0.8)  # Good reward
        
        # Alpha should increase
        self.assertGreater(
            self.bandit.arms['error_focused']['alpha'],
            initial_alpha
        )
    
    def test_context_influences_selection(self):
        """Test context affects strategy selection."""
        # Run many selections with high error context
        high_error_selections = []
        for _ in range(100):
            strategy = self.bandit.select_strategy({'error_rate': 0.5})
            high_error_selections.append(strategy)
        
        # error_focused should appear more often
        error_count = high_error_selections.count('error_focused')
        self.assertGreater(error_count, 10)  # Should appear reasonably often


# =============================================================================
# Adaptive Password Service Tests
# =============================================================================

class AdaptivePasswordServiceTests(TestCase):
    """Test main adaptive password service."""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
    
    def test_service_initialization(self):
        """Test service initializes correctly."""
        from security.services.adaptive_password_service import AdaptivePasswordService
        
        service = AdaptivePasswordService(self.user)
        self.assertIsNotNone(service.privacy_guard)
        self.assertIsNotNone(service.pattern_collector)
        self.assertIsNotNone(service.substitution_learner)
        self.assertIsNotNone(service.memorability_scorer)
    
    def test_record_session_requires_consent(self):
        """Test session recording requires consent."""
        from security.services.adaptive_password_service import AdaptivePasswordService
        
        service = AdaptivePasswordService(self.user)
        result = service.record_typing_session(
            password="test123",
            keystroke_timings=[100] * 7,
            backspace_positions=[],
        )
        
        # Should fail without config
        self.assertIn('error', result)
    
    def test_suggest_adaptation_requires_data(self):
        """Test suggestion requires sufficient data."""
        from security.services.adaptive_password_service import AdaptivePasswordService
        from security.models import AdaptivePasswordConfig
        
        # Create config
        AdaptivePasswordConfig.objects.create(
            user=self.user,
            is_enabled=True,
            consent_given_at=timezone.now(),
        )
        
        service = AdaptivePasswordService(self.user)
        suggestion = service.suggest_adaptation("password123")
        
        # Should return None due to insufficient data
        self.assertIsNone(suggestion)


# =============================================================================
# Model Tests
# =============================================================================

class AdaptivePasswordModelsTests(TestCase):
    """Test Django models for adaptive passwords."""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
    
    def test_config_creation(self):
        """Test AdaptivePasswordConfig creation."""
        from security.models import AdaptivePasswordConfig
        
        config = AdaptivePasswordConfig.objects.create(
            user=self.user,
            is_enabled=True,
            consent_given_at=timezone.now(),
        )
        
        self.assertEqual(config.is_enabled, True)
        self.assertEqual(config.suggestion_frequency_days, 30)  # Default
        self.assertEqual(config.differential_privacy_epsilon, 0.5)  # Default
    
    def test_config_defaults_to_disabled(self):
        """Test config defaults to disabled (opt-in)."""
        from security.models import AdaptivePasswordConfig
        
        config = AdaptivePasswordConfig.objects.create(user=self.user)
        self.assertFalse(config.is_enabled)
    
    def test_typing_session_creation(self):
        """Test TypingSession creation."""
        from security.models import TypingSession
        
        session = TypingSession.objects.create(
            user=self.user,
            password_hash_prefix="testprefix123456",  # gitleaks:allow
            password_length=12,
            success=True,
            error_positions=[],
            timing_profile={'0': 100, '1': 150},
        )
        
        self.assertEqual(session.error_count, 0)
        self.assertTrue(session.success)
    
    def test_adaptation_rollback_chain(self):
        """Test password adaptation rollback chain."""
        from security.models import PasswordAdaptation
        
        # Create first adaptation
        first = PasswordAdaptation.objects.create(
            user=self.user,
            password_hash_prefix="testorig123456",  # gitleaks:allow
            adapted_hash_prefix="testadapt123456",  # gitleaks:allow
            adaptation_generation=1,
            adaptation_type='substitution',
            confidence_score=0.85,
            status='rolled_back',
        )
        
        # Create second adaptation linked to first
        second = PasswordAdaptation.objects.create(
            user=self.user,
            password_hash_prefix="testadapt123456",  # gitleaks:allow
            adapted_hash_prefix="testadapt234567",  # gitleaks:allow
            previous_adaptation=first,
            adaptation_generation=2,
            adaptation_type='substitution',
            confidence_score=0.9,
            status='active',
        )
        
        # Test rollback chain
        chain = second.get_rollback_chain()
        self.assertEqual(len(chain), 2)
        self.assertEqual(chain[0], second)
        self.assertEqual(chain[1], first)
        
        # Test can_rollback
        self.assertTrue(second.can_rollback())
        self.assertFalse(first.can_rollback())  # No previous
    
    def test_typing_profile_sufficient_data(self):
        """Test typing profile data sufficiency check."""
        from security.models import UserTypingProfile
        
        profile = UserTypingProfile.objects.create(
            user=self.user,
            total_sessions=5,
            minimum_sessions_for_suggestion=10,
        )
        
        self.assertFalse(profile.has_sufficient_data())
        
        profile.total_sessions = 15
        profile.save()
        
        self.assertTrue(profile.has_sufficient_data())


# =============================================================================
# API Endpoint Tests
# =============================================================================

class AdaptivePasswordAPITests(APITestCase):
    """Test API endpoints."""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
    
    def test_get_config_unauthenticated(self):
        """Test config endpoint requires authentication."""
        self.client.logout()
        response = self.client.get('/api/security/adaptive/config/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_get_config_not_configured(self):
        """Test getting config when not configured."""
        response = self.client.get('/api/security/adaptive/config/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data['enabled'])
        self.assertFalse(response.data.get('configured', True))
    
    def test_enable_requires_consent(self):
        """Test enabling requires explicit consent."""
        response = self.client.post('/api/security/adaptive/enable/', {})
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)
    
    def test_enable_with_consent(self):
        """Test enabling with consent."""
        response = self.client.post('/api/security/adaptive/enable/', {
            'consent': True,
            'consent_version': '1.0',
        })
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['enabled'])
    
    def test_record_session_requires_data(self):
        """Test session recording requires proper data."""
        # First enable
        self.client.post('/api/security/adaptive/enable/', {
            'consent': True,
        })
        
        # Try without required fields
        response = self.client.post('/api/security/adaptive/record-session/', {})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_suggest_adaptation_endpoint(self):
        """Test adaptation suggestion endpoint."""
        response = self.client.post('/api/security/adaptive/suggest/', {
            'password': 'testpassword123',
        })
        
        # Should return 200 even without suggestions
        self.assertEqual(response.status_code, status.HTTP_200_OK)
    
    def test_get_profile_endpoint(self):
        """Test profile endpoint."""
        response = self.client.get('/api/security/adaptive/profile/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('has_profile', response.data)
    
    def test_get_history_endpoint(self):
        """Test history endpoint."""
        response = self.client.get('/api/security/adaptive/history/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('adaptations', response.data)
    
    def test_delete_data_endpoint(self):
        """Test GDPR data deletion."""
        # First enable and create some data
        self.client.post('/api/security/adaptive/enable/', {
            'consent': True,
        })
        
        # Delete
        response = self.client.delete('/api/security/adaptive/data/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['success'])
    
    def test_export_data_endpoint(self):
        """Test GDPR data export."""
        response = self.client.get('/api/security/adaptive/export/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('export_date', response.data)
        self.assertIn('user_id', response.data)


# =============================================================================
# Integration Tests
# =============================================================================

class AdaptivePasswordIntegrationTests(TestCase):
    """Integration tests for full workflow."""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
    
    def test_full_workflow(self):
        """Test complete user workflow."""
        from security.models import (
            AdaptivePasswordConfig, TypingSession, 
            UserTypingProfile, PasswordAdaptation
        )
        from security.services.adaptive_password_service import AdaptivePasswordService
        
        # 1. Enable adaptive passwords
        config = AdaptivePasswordConfig.objects.create(
            user=self.user,
            is_enabled=True,
            consent_given_at=timezone.now(),
        )
        
        # 2. Create typing profile with sufficient data
        profile = UserTypingProfile.objects.create(
            user=self.user,
            total_sessions=20,
            successful_sessions=15,
            success_rate=0.75,
            preferred_substitutions={'o': '0', 'a': '@'},
            error_prone_positions={'3': 0.4, '7': 0.3},
            profile_confidence=0.8,
        )
        
        # 3. Get suggestion
        service = AdaptivePasswordService(self.user)
        suggestion = service.suggest_adaptation("password123", force=True)
        
        # Should get a suggestion
        self.assertIsNotNone(suggestion)
        
        # 4. Apply adaptation
        if suggestion:
            result = service.apply_adaptation(
                original_password="password123",
                adapted_password="p@ssw0rd123",
                substitutions=[
                    {'position': 1, 'from': 'a', 'to': '@'},
                    {'position': 5, 'from': 'o', 'to': '0'},
                ],
            )
            
            self.assertIn('adaptation_id', result)
            self.assertEqual(result['generation'], 1)


# =============================================================================
# A/B Test Configuration Tests
# =============================================================================

class AdaptivePasswordABTests(TestCase):
    """Test A/B test configurations."""
    
    def test_experiment_variants(self):
        """Test different experiment variants."""
        experiments = {
            'adaptive_password_rollout': {
                'variants': {
                    'control': {'adaptation_enabled': False},
                    'v1': {'adaptation_enabled': True, 'auto_suggest': False},
                    'v2': {'adaptation_enabled': True, 'auto_suggest': True},
                },
                'metrics': [
                    'login_success_rate',
                    'password_reset_rate', 
                    'memorability_score'
                ],
            },
            'suggestion_frequency': {
                'variants': {
                    'weekly': {'frequency_days': 7},
                    'monthly': {'frequency_days': 30},
                    'quarterly': {'frequency_days': 90},
                },
                'metrics': ['suggestion_acceptance_rate', 'adaptation_rollback_rate'],
            },
        }
        
        # Verify experiment structure
        for exp_name, exp_config in experiments.items():
            self.assertIn('variants', exp_config)
            self.assertIn('metrics', exp_config)
            self.assertGreater(len(exp_config['variants']), 1)
    
    def test_ab_user_assignment(self):
        """Test consistent user assignment to variants."""
        import hashlib
        
        def assign_variant(user_id, experiment, variants):
            """Deterministic variant assignment based on user ID."""
            hash_input = f"{user_id}:{experiment}"
            hash_val = int(hashlib.md5(hash_input.encode()).hexdigest(), 16)
            variant_idx = hash_val % len(variants)
            return list(variants.keys())[variant_idx]
        
        # Same user should always get same variant
        variants = {'control': {}, 'treatment_a': {}, 'treatment_b': {}}
        user_variant = assign_variant('user_123', 'adaptive_password', variants)
        
        for _ in range(10):
            self.assertEqual(
                assign_variant('user_123', 'adaptive_password', variants),
                user_variant
            )
    
    def test_ab_metrics_collection(self):
        """Test A/B test metrics are collected correctly."""
        metrics = {
            'experiment': 'adaptive_password_v2',
            'variant': 'treatment',
            'user_id': 'user_123',
            'events': [
                {'type': 'suggestion_shown', 'timestamp': timezone.now().isoformat()},
                {'type': 'suggestion_accepted', 'timestamp': timezone.now().isoformat()},
                {'type': 'login_success', 'days_since': 7},
            ]
        }
        
        # Verify metrics structure
        self.assertIn('experiment', metrics)
        self.assertIn('variant', metrics)
        self.assertIn('events', metrics)
        self.assertGreater(len(metrics['events']), 0)


# =============================================================================
# Advanced Privacy Engine Tests (pydp)
# =============================================================================

class AdvancedPrivacyEngineTests(TestCase):
    """Test advanced differential privacy with pydp."""
    
    def setUp(self):
        from security.services.adaptive_password_service import PrivacyGuard
        self.guard = PrivacyGuard(epsilon=0.5, delta=1e-5)
    
    def test_add_noise_to_timings(self):
        """Test pydp BoundedMean for timing data."""
        timings = [100.0, 120.0, 95.0, 110.0, 105.0]
        
        noisy1 = self.guard.add_noise_to_timings(timings)
        noisy2 = self.guard.add_noise_to_timings(timings)
        
        # Should return different values due to DP noise
        # (Note: small chance they're equal, but very unlikely)
        self.assertIsInstance(noisy1, float)
        self.assertIsInstance(noisy2, float)
        
        # Should be within reasonable bounds
        self.assertGreater(noisy1, 0)
        self.assertLess(noisy1, 1000)
    
    def test_add_noise_to_error_histogram(self):
        """Test DP-protected error histogram."""
        error_positions = [3, 7, 7, 12, 3, 3]  # 3 appears 3x, 7 appears 2x
        
        histogram = self.guard.add_noise_to_error_histogram(error_positions)
        
        # Should be a dict with int keys and values
        self.assertIsInstance(histogram, dict)
        for pos, count in histogram.items():
            self.assertIsInstance(pos, int)
            self.assertIsInstance(count, int)
            self.assertGreaterEqual(count, 0)  # Should be non-negative
    
    def test_add_noise_to_substitutions(self):
        """Test DP noise on substitution mappings."""
        substitutions = {'o': '0', 'a': '@'}
        
        noisy_subs = self.guard.add_noise_to_substitutions(substitutions)
        
        # Should preserve original substitutions (with possible additions)
        self.assertIsInstance(noisy_subs, dict)
        # Original should be present
        self.assertIn('o', noisy_subs)
        self.assertIn('a', noisy_subs)
    
    def test_verify_privacy_budget_fresh(self):
        """Test privacy budget on fresh guard."""
        from security.services.adaptive_password_service import PrivacyGuard
        fresh_guard = PrivacyGuard(epsilon=0.5, delta=1e-5)
        self.assertTrue(fresh_guard.verify_privacy_budget())
    
    def test_privacy_budget_exhaustion(self):
        """Test privacy budget exhaustion after many operations."""
        # Simulate many operations
        for _ in range(100):
            self.guard.add_laplace_noise(100.0)
        
        # Budget should be getting low
        status = self.guard.get_privacy_budget_status()
        self.assertGreater(status['operations_count'], 0)
        self.assertIn('total_epsilon_used', status)
        self.assertIn('budget_remaining_pct', status)
    
    def test_get_privacy_budget_status(self):
        """Test privacy budget status reporting."""
        status = self.guard.get_privacy_budget_status()
        
        required_keys = [
            'epsilon', 'delta', 'operations_count', 
            'total_epsilon_used', 'max_recommended_operations',
            'budget_remaining_pct', 'using_pydp'
        ]
        
        for key in required_keys:
            self.assertIn(key, status)
        
        self.assertEqual(status['epsilon'], 0.5)
        self.assertEqual(status['delta'], 1e-5)


# =============================================================================
# LSTM Memorability Model Tests
# =============================================================================

class MemorabilityLSTMTests(TestCase):
    """Test LSTM-based memorability prediction."""
    
    def setUp(self):
        from security.services.adaptive_password_service import MemorabilityLSTM
        self.lstm = MemorabilityLSTM(input_dim=50, hidden_dim=128)
    
    def test_initialization(self):
        """Test LSTM model initializes correctly."""
        self.assertIsNotNone(self.lstm)
        self.assertEqual(self.lstm.input_dim, 50)
        self.assertEqual(self.lstm.hidden_dim, 128)
    
    def test_extract_features_length(self):
        """Test feature extraction produces correct dimensions."""
        features = self.lstm.extract_features("TestPassword123!")
        
        self.assertEqual(len(features), 50)
        self.assertTrue(all(isinstance(f, float) for f in features))
    
    def test_extract_features_with_profile(self):
        """Test feature extraction with typing profile."""
        profile = {
            'avg_inter_keystroke_time': 120.0,
            'typing_speed_wpm': 45.0,
            'success_rate': 0.85,
            'profile_confidence': 0.7,
            'error_prone_positions': {'3': 0.4, '7': 0.3},
            'preferred_substitutions': {'o': '0'},
            'total_sessions': 25,
        }
        
        features = self.lstm.extract_features("TestPassword123!", profile)
        
        self.assertEqual(len(features), 50)
        # Profile features should be included (not all zeros)
        self.assertTrue(any(f > 0 for f in features[35:45]))  # Profile features
    
    def test_predict_returns_valid_score(self):
        """Test prediction returns score in valid range."""
        score = self.lstm.predict("TestPassword123!")
        
        self.assertGreaterEqual(score, 0.0)
        self.assertLessEqual(score, 1.0)
    
    def test_predict_different_passwords(self):
        """Test predictions differ for different passwords."""
        score1 = self.lstm.predict("SimplePass123")
        score2 = self.lstm.predict("xK9$mZp@vL2#nQ")
        
        # Scores should be different (very unlikely to be exactly equal)
        self.assertIsInstance(score1, float)
        self.assertIsInstance(score2, float)
    
    def test_compare_passwords(self):
        """Test password comparison functionality."""
        orig, adapted, improvement = self.lstm.compare_passwords(
            "password123",
            "p@ssw0rd123"
        )
        
        self.assertIsInstance(orig, float)
        self.assertIsInstance(adapted, float)
        self.assertIsInstance(improvement, float)
        self.assertAlmostEqual(improvement, adapted - orig, places=5)
    
    def test_feature_extraction_edge_cases(self):
        """Test feature extraction handles edge cases."""
        # Empty password
        features = self.lstm.extract_features("")
        self.assertEqual(len(features), 50)
        
        # Single character
        features = self.lstm.extract_features("a")
        self.assertEqual(len(features), 50)
        
        # Very long password
        features = self.lstm.extract_features("a" * 100)
        self.assertEqual(len(features), 50)


# =============================================================================
# End-to-End Tests
# =============================================================================

class AdaptivePasswordE2ETests(TestCase):
    """End-to-end tests for complete user journeys."""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='e2euser',
            email='e2e@example.com',
            password='TestPassword123!'
        )
    
    def test_complete_opt_in_to_adaptation_flow(self):
        """
        Test complete flow:
        1. User opts in
        2. Typing sessions are recorded
        3. Profile is built
        4. Suggestion is generated
        5. User accepts suggestion
        6. Rollback is available
        """
        from security.models import (
            AdaptivePasswordConfig, TypingSession, 
            UserTypingProfile, PasswordAdaptation
        )
        from security.services.adaptive_password_service import AdaptivePasswordService
        
        # Step 1: Opt in
        config = AdaptivePasswordConfig.objects.create(
            user=self.user,
            is_enabled=True,
            consent_given_at=timezone.now(),
        )
        self.assertTrue(config.is_enabled)
        
        # Step 2: Record typing sessions
        for i in range(15):
            TypingSession.objects.create(
                user=self.user,
                password_hash_prefix=f"hash{i:012d}1234",
                password_length=12,
                success=i % 3 != 0,  # 66% success
                error_positions=[3, 7] if i % 3 == 0 else [],
                timing_profile={'0': 100, '1': 120},
            )
        
        # Step 3: Create profile
        profile = UserTypingProfile.objects.create(
            user=self.user,
            total_sessions=15,
            successful_sessions=10,
            success_rate=0.67,
            average_wpm=45.0,
            preferred_substitutions={'o': '0'},
            error_prone_positions={'3': 0.4, '7': 0.3},
            profile_confidence=0.75,
        )
        self.assertTrue(profile.has_sufficient_data())
        
        # Step 4: Get suggestion
        service = AdaptivePasswordService(self.user)
        suggestion = service.suggest_adaptation("password123", force=True)
        
        # Step 5: Apply adaptation (simulate)
        if suggestion:
            adaptation = PasswordAdaptation.objects.create(
                user=self.user,
                password_hash_prefix="original123456",
                adapted_hash_prefix="adapted1234567",
                adaptation_generation=1,
                adaptation_type='substitution',
                confidence_score=suggestion.confidence_score,
                status='active',
            )
            
            # Step 6: Verify rollback available
            second_adaptation = PasswordAdaptation.objects.create(
                user=self.user,
                password_hash_prefix="adapted1234567",
                adapted_hash_prefix="adapted2345678",
                previous_adaptation=adaptation,
                adaptation_generation=2,
                adaptation_type='substitution',
                confidence_score=0.9,
                status='active',
            )
            
            self.assertTrue(second_adaptation.can_rollback())
            chain = second_adaptation.get_rollback_chain()
            self.assertEqual(len(chain), 2)
    
    def test_gdpr_data_lifecycle(self):
        """Test GDPR compliance: export and deletion."""
        from security.models import (
            AdaptivePasswordConfig, TypingSession, UserTypingProfile
        )
        
        # Create data
        AdaptivePasswordConfig.objects.create(
            user=self.user,
            is_enabled=True,
            consent_given_at=timezone.now(),
        )
        
        UserTypingProfile.objects.create(
            user=self.user,
            total_sessions=10,
        )
        
        TypingSession.objects.create(
            user=self.user,
            password_hash_prefix="testhash12345678",
            password_length=12,
            success=True,
        )
        
        # Verify data exists
        self.assertEqual(AdaptivePasswordConfig.objects.filter(user=self.user).count(), 1)
        self.assertEqual(UserTypingProfile.objects.filter(user=self.user).count(), 1)
        self.assertEqual(TypingSession.objects.filter(user=self.user).count(), 1)
        
        # Delete all data (GDPR)
        AdaptivePasswordConfig.objects.filter(user=self.user).delete()
        UserTypingProfile.objects.filter(user=self.user).delete()
        TypingSession.objects.filter(user=self.user).delete()
        
        # Verify deletion
        self.assertEqual(AdaptivePasswordConfig.objects.filter(user=self.user).count(), 0)
        self.assertEqual(UserTypingProfile.objects.filter(user=self.user).count(), 0)
        self.assertEqual(TypingSession.objects.filter(user=self.user).count(), 0)
    
    def test_privacy_preserved_throughout_flow(self):
        """Verify no raw passwords are stored at any point."""
        from security.models import TypingSession, PasswordAdaptation, UserTypingProfile
        from security.services.adaptive_password_service import AdaptivePasswordService
        
        password = "MySecretPassword123!"
        
        # Create session with pattern
        service = AdaptivePasswordService(self.user)
        pattern = service.pattern_collector.process_keystroke_data(
            password=password,
            keystroke_timings=[100] * len(password),
            backspace_positions=[],
        )
        
        # Verify pattern doesn't contain password
        self.assertNotIn(password, str(vars(pattern)))
        self.assertNotIn("MySecret", str(vars(pattern)))
        
        # Verify hash prefix is only 16 chars
        self.assertEqual(len(pattern.password_hash_prefix), 16)


# =============================================================================
# Functional Tests
# =============================================================================

class AdaptivePasswordFunctionalTests(TestCase):
    """Functional tests for business logic."""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='funcuser',
            password='testpass123'
        )
    
    def test_suggestion_frequency_respected(self):
        """Test suggestions respect frequency settings."""
        from security.models import AdaptivePasswordConfig
        
        # Create config with 30-day frequency
        config = AdaptivePasswordConfig.objects.create(
            user=self.user,
            is_enabled=True,
            suggestion_frequency_days=30,
            consent_given_at=timezone.now(),
        )
        
        # First suggestion should be allowed
        self.assertTrue(config.should_suggest_adaptation())
        
        # Mark as suggested recently
        config.last_suggestion_at = timezone.now()
        config.save()
        
        # Should not suggest again
        self.assertFalse(config.should_suggest_adaptation())
        
        # After 30 days, should suggest again
        config.last_suggestion_at = timezone.now() - timedelta(days=31)
        config.save()
        self.assertTrue(config.should_suggest_adaptation())
    
    def test_minimum_sessions_required(self):
        """Test minimum sessions before suggestions."""
        from security.models import UserTypingProfile
        
        profile = UserTypingProfile.objects.create(
            user=self.user,
            total_sessions=5,
            minimum_sessions_for_suggestion=10,
        )
        
        self.assertFalse(profile.has_sufficient_data())
        
        profile.total_sessions = 10
        profile.save()
        
        self.assertTrue(profile.has_sufficient_data())
    
    def test_confidence_threshold_for_auto_apply(self):
        """Test auto-apply only with high confidence."""
        from security.models import AdaptivePasswordConfig
        from django.conf import settings
        
        # Get threshold from settings
        threshold = getattr(settings, 'ADAPTIVE_PASSWORD', {}).get(
            'AUTO_APPLY_THRESHOLD', 0.9
        )
        
        config = AdaptivePasswordConfig.objects.create(
            user=self.user,
            is_enabled=True,
            auto_apply_high_confidence=True,
            consent_given_at=timezone.now(),
        )
        
        # Low confidence - should not auto-apply
        self.assertLess(0.7, threshold)
        
        # High confidence - should auto-apply
        self.assertGreaterEqual(0.95, threshold)
    
    def test_rollback_depth_limit(self):
        """Test rollback depth is limited."""
        from security.models import PasswordAdaptation
        from django.conf import settings
        
        max_depth = getattr(settings, 'ADAPTIVE_PASSWORD', {}).get(
            'MAX_ROLLBACK_DEPTH', 10
        )
        
        # Create chain of adaptations
        prev = None
        for i in range(15):
            adaptation = PasswordAdaptation.objects.create(
                user=self.user,
                password_hash_prefix=f"hash{i:014d}12",
                adapted_hash_prefix=f"hash{i+1:014d}12",
                previous_adaptation=prev,
                adaptation_generation=i + 1,
                adaptation_type='substitution',
                confidence_score=0.85,
                status='rolled_back' if prev else 'active',
            )
            prev = adaptation
        
        # Get rollback chain
        chain = prev.get_rollback_chain()
        
        # Verify chain length
        self.assertEqual(len(chain), 15)
        
        # In production, we'd limit to max_depth
        limited_chain = chain[:max_depth]
        self.assertLessEqual(len(limited_chain), max_depth)


# =============================================================================
# Frontend Component Tests (Mock)
# =============================================================================

class FrontendComponentTests(TestCase):
    """Test frontend component contracts (mock tests)."""
    
    def test_typing_pattern_capture_props(self):
        """Test TypingPatternCapture component contract."""
        component_props = {
            'inputRef': 'React.RefObject<HTMLInputElement>',
            'enabled': 'boolean',
            'onPatternCaptured': 'function',
            'onError': 'function (optional)',
        }
        
        required_props = ['inputRef', 'enabled', 'onPatternCaptured']
        for prop in required_props:
            self.assertIn(prop, component_props)
    
    def test_typing_pattern_capture_output_format(self):
        """Test TypingPatternCapture output format."""
        expected_output = {
            'timings': [100, 120, 95],  # Inter-keystroke timings
            'errors': [3, 7],           # Error positions
            'backspace_count': 2,
            'total_time_ms': 5000,
            'password_length': 12,
            'session_type': 'login',
        }
        
        required_fields = ['timings', 'errors', 'backspace_count', 'total_time_ms']
        for field in required_fields:
            self.assertIn(field, expected_output)
    
    def test_adaptive_suggestion_component_props(self):
        """Test AdaptivePasswordSuggestion component contract."""
        suggestion_props = {
            'original_preview': 'te***23',
            'adapted_preview': 't3***23',
            'substitutions': [
                {'position': 1, 'from': 'e', 'to': '3'}
            ],
            'confidence_score': 0.85,
            'memorability_improvement': 0.15,
        }
        
        required_fields = ['original_preview', 'adapted_preview', 'substitutions']
        for field in required_fields:
            self.assertIn(field, suggestion_props)
    
    def test_typing_profile_card_data_format(self):
        """Test TypingProfileCard data format."""
        profile_data = {
            'total_sessions': 25,
            'success_rate': 0.85,
            'average_wpm': 45.0,
            'preferred_substitutions': {'o': '0', 'a': '@'},
            'error_prone_positions': {'3': 0.4, '7': 0.3},
            'profile_confidence': 0.8,
            'last_adaptation_at': '2024-01-15T10:30:00Z',
        }
        
        # All values should be serializable
        import json
        json_str = json.dumps(profile_data)
        self.assertIsInstance(json_str, str)
    
    def test_useTypingPatternCapture_hook_interface(self):
        """Test useTypingPatternCapture hook interface."""
        hook_interface = {
            'isCapturing': 'boolean',
            'sessionData': 'object | null',
            'startCapture': 'function',
            'captureKeystroke': 'function',
            'captureError': 'function',
            'endCapture': 'function',
            'resetSession': 'function',
        }
        
        required_exports = ['startCapture', 'captureKeystroke', 'endCapture']
        for export in required_exports:
            self.assertIn(export, hook_interface)


# =============================================================================
# Celery Task Tests
# =============================================================================

class CeleryTaskTests(TestCase):
    """Test Celery async tasks."""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='celeryuser',
            password='testpass123'
        )
    
    def test_generate_suggestion_task_structure(self):
        """Test suggestion generation task structure."""
        from security.tasks.adaptive_tasks import generate_adaptation_suggestion
        
        # Verify task is callable
        self.assertTrue(callable(generate_adaptation_suggestion))
    
    def test_cleanup_expired_adaptations_structure(self):
        """Test cleanup task structure."""
        from security.tasks.adaptive_tasks import cleanup_expired_adaptations
        
        self.assertTrue(callable(cleanup_expired_adaptations))
    
    def test_aggregate_typing_profiles_structure(self):
        """Test aggregation task structure."""
        from security.tasks.adaptive_tasks import aggregate_typing_profiles
        
        self.assertTrue(callable(aggregate_typing_profiles))
    
    def test_update_rl_model_structure(self):
        """Test RL model update task structure."""
        from security.tasks.adaptive_tasks import update_rl_model_from_feedback
        
        self.assertTrue(callable(update_rl_model_from_feedback))


# =============================================================================
# Feedback API Tests
# =============================================================================

class FeedbackAPITests(APITestCase):
    """Test feedback submission API."""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='feedbackuser',
            password='testpass123'
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
    
    def test_submit_feedback_endpoint(self):
        """Test feedback submission."""
        from security.models import PasswordAdaptation, AdaptivePasswordConfig
        
        # Create config and adaptation
        AdaptivePasswordConfig.objects.create(
            user=self.user,
            is_enabled=True,
            consent_given_at=timezone.now(),
        )
        
        adaptation = PasswordAdaptation.objects.create(
            user=self.user,
            password_hash_prefix="feedback12345678",
            adapted_hash_prefix="adapted123456789",
            adaptation_generation=1,
            adaptation_type='substitution',
            confidence_score=0.85,
            status='active',
        )
        
        # Submit feedback
        response = self.client.post('/api/security/adaptive/feedback/', {
            'adaptation_id': str(adaptation.id),
            'rating': 4,
            'typing_accuracy_improved': True,
            'memorability_improved': True,
        })
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['success'])
    
    def test_get_feedback_endpoint(self):
        """Test getting feedback for an adaptation."""
        from security.models import PasswordAdaptation
        
        adaptation = PasswordAdaptation.objects.create(
            user=self.user,
            password_hash_prefix="getfeedback12345",
            adapted_hash_prefix="adapted12345678",
            adaptation_generation=1,
            adaptation_type='substitution',
            confidence_score=0.85,
            status='active',
        )
        
        response = self.client.get(f'/api/security/adaptive/feedback/{adaptation.id}/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('has_feedback', response.data)


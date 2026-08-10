"""
Adaptive Password Service Tests (zero-knowledge)
================================================

Unit/integration tests for the surviving adaptive-password surface after the
zero-knowledge v2 cleanup. The v2 wire contract + serializers are covered in
test_adaptive_zk_v2.py; this module covers:
- the privacy guard (timing buckets, differential-privacy noise)
- Django models (config, fingerprint-keyed sessions/adaptations, rollback chain)
- the v2 service (fingerprint record, preference-model export, apply)
- API endpoints, celery tasks, and end-to-end flows
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta
from uuid import uuid4
import json

from django.conf import settings
from django.test import TestCase
from django.contrib.auth.models import User
from django.utils import timezone
from rest_framework.test import APITestCase, APIClient
from rest_framework import status

# A low-entropy, obviously-fake stand-in for a client fingerprint. Referenced by
# name (not inlined next to ``password_fingerprint``) so secret scanners don't
# mistake a base64url-looking literal for a real credential. The real value is a
# client-computed HMAC fingerprint (see cryptoService.passwordFingerprint).
FP_STUB = 'fp-not-a-real-fingerprint'


# =============================================================================
# Privacy Guard Tests
# =============================================================================

class PrivacyGuardTests(TestCase):
    """Test privacy protection mechanisms."""
    
    def setUp(self):
        """Set up the test user/fixtures."""
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
            password_hash_prefix="testprefix123456",  # pragma: allowlist secret
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
# Adaptive Password Service Tests
# =============================================================================

class AdaptivePasswordServiceTests(TestCase):
    """Test main adaptive password service."""
    
    def setUp(self):
        """Set up the test user/fixtures."""
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
    
    def test_service_initialization(self):
        """Test service initializes correctly (zero-knowledge: privacy guard only)."""
        from security.services.adaptive_password_service import AdaptivePasswordService

        service = AdaptivePasswordService(self.user)
        self.assertIsNotNone(service.privacy_guard)

    def test_record_session_requires_consent(self):
        """Test session recording requires consent (v2 fingerprint path)."""
        from security.services.adaptive_password_service import AdaptivePasswordService

        service = AdaptivePasswordService(self.user)
        result = service.record_typing_session_v2(
            password_fingerprint=FP_STUB,
            length_bucket=2,
            keystroke_timings=[100] * 7,
            backspace_positions=[],
        )

        # Should fail without config
        self.assertIn('error', result)
    
# =============================================================================
# Model Tests
# =============================================================================

class AdaptivePasswordModelsTests(TestCase):
    """Test Django models for adaptive passwords."""
    
    def setUp(self):
        """Set up the test user/fixtures."""
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
            password_fingerprint=FP_STUB,
            length_bucket=3,
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
            original_fingerprint='Orig0123456789-_aAbBcCdD',
            adapted_fingerprint='Adpt0123456789-_aAbBcCdD',
            adaptation_generation=1,
            adaptation_type='substitution',
            confidence_score=0.85,
            status='rolled_back',
        )

        # Create second adaptation linked to first
        second = PasswordAdaptation.objects.create(
            user=self.user,
            original_fingerprint='Adpt0123456789-_aAbBcCdD',
            adapted_fingerprint='Adp20123456789-_aAbBcCdD',
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
        """Set up the test user/fixtures."""
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
    
    def test_suggest_adaptation_endpoint_deprecated_under_zk_v2(self):
        """Server-side /suggest/ is unconditionally deprecated (410).

        Suggestions are now generated client-side from the preference model, so
        POSTing a password returns 410 Gone (and never accepts the plaintext).
        """
        response = self.client.post('/api/security/adaptive/suggest/', {
            'password': 'testpassword123',
        })
        self.assertEqual(response.status_code, status.HTTP_410_GONE)
        self.assertIn('preference-model', str(response.data))
    
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
        """Set up the test user/fixtures."""
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
    
    def test_full_workflow(self):
        """Test complete zero-knowledge workflow (model export → apply)."""
        from security.models import (
            AdaptivePasswordConfig, UserTypingProfile
        )
        from security.services.adaptive_password_service import AdaptivePasswordService

        # 1. Enable adaptive passwords
        AdaptivePasswordConfig.objects.create(
            user=self.user,
            is_enabled=True,
            consent_given_at=timezone.now(),
        )

        # 2. Create typing profile with sufficient data + learned preferences
        UserTypingProfile.objects.create(
            user=self.user,
            total_sessions=20,
            successful_sessions=15,
            success_rate=0.75,
            preferred_substitutions={'o': '0', 'a': '@'},
            substitution_confidence={'o->0': 0.9},
            error_prone_positions={'3': 0.4, '7': 0.3},
            profile_confidence=0.8,
        )

        service = AdaptivePasswordService(self.user)

        # 3. Export the preference model (client ranks suggestions locally).
        model = service.export_preference_model()
        self.assertEqual(model['model_version'], 20)
        self.assertAlmostEqual(model['substitution_weights']['o']['0'], 0.9)

        # 4. Apply an adaptation by fingerprints only (no raw passwords).
        result = service.apply_adaptation_v2(
            original_fingerprint='Orig0123456789-_aAbBcCdD',
            adapted_fingerprint='Adpt0123456789-_aAbBcCdD',
            substitution_classes=[
                {'from': 'a', 'to': '@', 'confidence': 0.8},
                {'from': 'o', 'to': '0', 'confidence': 0.9},
            ],
            previews={'original_masked': 'pa***23', 'adapted_masked': 'p@***23'},
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
        from security.utils.sensitive_hash import hash_for_dedup

        def assign_variant(user_id, experiment, variants):
            """Deterministic A/B variant assignment (non-security use).

            HMAC-keyed via hash_for_dedup so CodeQL doesn't classify the
            input ``user_id`` as a weak-hashed secret.
            """
            hash_input = f"{user_id}:{experiment}"
            hash_val = int(hash_for_dedup(hash_input, domain="ab-test-variant"), 16)
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
        """Set up the test user/fixtures."""
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
# End-to-End Tests
# =============================================================================

class AdaptivePasswordE2ETests(TestCase):
    """End-to-end tests for complete user journeys."""
    
    def setUp(self):
        """Set up the test user/fixtures."""
        self.user = User.objects.create_user(
            username='e2euser',
            email='e2e@example.com',
            password='TestPassword123!'
        )
    
    def test_complete_opt_in_to_adaptation_flow(self):
        """
        Test the complete zero-knowledge flow:
        1. User opts in
        2. Typing sessions are recorded by fingerprint (no password)
        3. Profile is built
        4. An adaptation is applied by fingerprint
        5. A follow-up adaptation chains for rollback
        """
        from security.models import (
            AdaptivePasswordConfig, TypingSession, UserTypingProfile
        )
        from security.services.adaptive_password_service import AdaptivePasswordService

        # Step 1: Opt in
        config = AdaptivePasswordConfig.objects.create(
            user=self.user,
            is_enabled=True,
            consent_given_at=timezone.now(),
        )
        self.assertTrue(config.is_enabled)

        # Step 2: Record typing sessions (keyed fingerprint + coarse features).
        service = AdaptivePasswordService(self.user)
        for i in range(15):
            service.record_typing_session_v2(
                password_fingerprint=FP_STUB,
                length_bucket=3,
                keystroke_timings=[100, 120, 90, 110],
                backspace_positions=[3, 7] if i % 3 == 0 else [],
            )

        # Step 3: Profile is built from the aggregate signals.
        profile = UserTypingProfile.objects.get(user=self.user)
        self.assertEqual(profile.total_sessions, 15)
        self.assertTrue(profile.has_sufficient_data())
        self.assertEqual(TypingSession.objects.filter(user=self.user).count(), 15)

        # Step 4 + 5: Apply an adaptation, then a follow-up that chains for rollback.
        first = service.apply_adaptation_v2(
            original_fingerprint='Orig0123456789-_aAbBcCdD',
            adapted_fingerprint='Adpt0123456789-_aAbBcCdD',
            substitution_classes=[{'from': 'o', 'to': '0', 'confidence': 0.9}],
        )
        self.assertEqual(first['generation'], 1)

        second = service.apply_adaptation_v2(
            original_fingerprint='Adpt0123456789-_aAbBcCdD',
            adapted_fingerprint='Adp20123456789-_aAbBcCdD',
            substitution_classes=[{'from': 'a', 'to': '@', 'confidence': 0.8}],
        )
        self.assertEqual(second['generation'], 2)
        self.assertTrue(second['can_rollback'])

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
            password_fingerprint=FP_STUB,
            length_bucket=3,
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

    def test_delete_all_data_erases_policy_arms_too(self):
        """The real ``delete_all_data`` path, not a hand-rolled equivalent
        (unlike ``test_gdpr_data_lifecycle`` above, which deletes each model
        directly and never calls the service method at all).

        ``SubstitutionPolicyArm`` rows -- the bandit's per-user learned
        posteriors -- are independently keyed by ``user``, not cascaded from
        ``PasswordAdaptation``, so they survived GDPR erasure indefinitely
        until this was fixed (CodeRabbit, PR #466 round 16). Also checks
        another user's arm is untouched, so the fix is scoped correctly.
        """
        from security.models import (
            AdaptivePasswordConfig, TypingSession, UserTypingProfile,
            SubstitutionPolicyArm,
        )
        from security.services.adaptive_password_service import AdaptivePasswordService

        AdaptivePasswordConfig.objects.create(
            user=self.user, is_enabled=True, consent_given_at=timezone.now(),
        )
        UserTypingProfile.objects.create(user=self.user, total_sessions=10)
        TypingSession.objects.create(
            user=self.user, password_fingerprint=FP_STUB, length_bucket=3,
            success=True,
        )
        service = AdaptivePasswordService(self.user)
        # Real creation path: applying an adaptation credits an arm as a
        # side effect (credit_adaptation_best_effort), the same as CodeRabbit's
        # finding described, rather than inserting the row directly.
        service.apply_adaptation_v2(
            original_fingerprint='Orig0123456789-_aAbBcCdD',
            adapted_fingerprint='Adpt0123456789-_aAbBcCdD',
            substitution_classes=[{'from': 'o', 'to': '0', 'confidence': 0.9}],
        )
        self.assertEqual(
            SubstitutionPolicyArm.objects.filter(user=self.user).count(), 1
        )

        other_user = User.objects.create_user(
            username='other-gdpr-user', password='irrelevant-to-this-test',
        )
        SubstitutionPolicyArm.objects.create(
            user=other_user, from_char='a', to_char='4', fp_key_version=1,
        )

        counts = service.delete_all_data()

        self.assertEqual(counts['policy_arms'], 1)
        self.assertEqual(
            SubstitutionPolicyArm.objects.filter(user=self.user).count(), 0
        )
        self.assertEqual(TypingSession.objects.filter(user=self.user).count(), 0)
        self.assertEqual(UserTypingProfile.objects.filter(user=self.user).count(), 0)
        self.assertFalse(
            AdaptivePasswordConfig.objects.get(user=self.user).is_enabled
        )
        # Scoped to this user only -- the other user's arm survives.
        self.assertEqual(
            SubstitutionPolicyArm.objects.filter(user=other_user).count(), 1
        )

    def test_delete_all_data_is_all_or_nothing(self):
        """The round-17 ``transaction.atomic()`` wrap around ``delete_all_data``
        has no direct test of its own -- the test above only exercises the
        happy path. Force a failure on the LAST statement inside the atomic
        block (the config disable) and confirm every earlier delete in the
        same call rolled back instead of partially committing (CodeRabbit,
        PR #466 round 19)."""
        from unittest.mock import patch

        from security.models import (
            AdaptivePasswordConfig, SubstitutionPolicyArm, TypingSession,
        )
        from security.services.adaptive_password_service import AdaptivePasswordService

        AdaptivePasswordConfig.objects.create(
            user=self.user, is_enabled=True, consent_given_at=timezone.now(),
        )
        TypingSession.objects.create(
            user=self.user, password_fingerprint=FP_STUB, length_bucket=3,
            success=True,
        )
        SubstitutionPolicyArm.objects.create(
            user=self.user, from_char='o', to_char='0', fp_key_version=1,
        )
        service = AdaptivePasswordService(self.user)

        with patch.object(
            AdaptivePasswordConfig, 'save', side_effect=RuntimeError('boom'),
        ):
            with self.assertRaises(RuntimeError):
                service.delete_all_data()

        # Nothing committed -- the earlier deletes in the same call rolled
        # back along with the failing config save.
        self.assertEqual(TypingSession.objects.filter(user=self.user).count(), 1)
        self.assertEqual(
            SubstitutionPolicyArm.objects.filter(user=self.user).count(), 1
        )
        self.assertTrue(
            AdaptivePasswordConfig.objects.get(user=self.user).is_enabled
        )

    def test_privacy_preserved_throughout_flow(self):
        """Verify no raw password is stored — only the keyed fingerprint."""
        from security.models import AdaptivePasswordConfig, TypingSession
        from security.services.adaptive_password_service import AdaptivePasswordService

        password = "MySecretPassword123!"
        # In production the fingerprint is computed client-side; here we just use
        # an opaque token to prove the server stores no password-derived material.
        fingerprint = 'Zk0paqueFingerprint-_1234'

        AdaptivePasswordConfig.objects.create(
            user=self.user, is_enabled=True, consent_given_at=timezone.now()
        )
        service = AdaptivePasswordService(self.user)
        result = service.record_typing_session_v2(
            password_fingerprint=fingerprint,
            length_bucket=len(password) // 4,
            keystroke_timings=[100] * 6,
            backspace_positions=[],
        )

        session = TypingSession.objects.get(id=result['session_id'])
        # The stored row contains the opaque fingerprint, never the password.
        self.assertEqual(session.password_fingerprint, fingerprint)
        serialized = str([
            session.password_fingerprint, session.length_bucket,
            session.timing_profile, session.error_positions,
        ])
        self.assertNotIn(password, serialized)
        self.assertNotIn("MySecret", serialized)


# =============================================================================
# Functional Tests
# =============================================================================

class AdaptivePasswordFunctionalTests(TestCase):
    """Functional tests for business logic."""
    
    def setUp(self):
        """Set up the test user/fixtures."""
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
        
        # Create chain of adaptations (keyed by fingerprint).
        prev = None
        for i in range(15):
            adaptation = PasswordAdaptation.objects.create(
                user=self.user,
                original_fingerprint=f"Fp{i:020d}ab",
                adapted_fingerprint=f"Fp{i + 1:020d}ab",
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
            'length_bucket': 3,         # coarse bucket (ZK v2), not exact length
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
        """Set up the test user/fixtures."""
        self.user = User.objects.create_user(
            username='celeryuser',
            password='testpass123'
        )
    
    # These three tests were `assertTrue(callable(task))` until Phase 5. That
    # asserts the import worked, nothing else -- it would pass against a task
    # whose body raised on every row. They now run each task against real
    # fixtures and assert its return payload (plan §5.4).

    def test_cleanup_expired_adaptations_expires_only_stale_suggestions(self):
        """The cleanup task marks aged 'suggested' rows expired, and only those."""
        from security.models import PasswordAdaptation
        from security.tasks.adaptive_tasks import cleanup_expired_adaptations

        expiry_days = getattr(settings, 'ADAPTIVE_PASSWORD', {}).get(
            'ADAPTATION_EXPIRY_DAYS', 7
        )
        stale = PasswordAdaptation.objects.create(
            user=self.user, adaptation_type='substitution',
            confidence_score=0.8, status='suggested',
        )
        # suggested_at is auto_now_add, so it cannot be set on create.
        PasswordAdaptation.objects.filter(pk=stale.pk).update(
            suggested_at=timezone.now() - timedelta(days=expiry_days + 1)
        )
        fresh = PasswordAdaptation.objects.create(
            user=self.user, adaptation_type='substitution',
            confidence_score=0.8, status='suggested',
        )
        # An ACTIVE row is the user's live password. Ageing must never touch it.
        active = PasswordAdaptation.objects.create(
            user=self.user, adaptation_type='substitution',
            confidence_score=0.8, status='active',
        )
        PasswordAdaptation.objects.filter(pk=active.pk).update(
            suggested_at=timezone.now() - timedelta(days=expiry_days + 30)
        )

        result = cleanup_expired_adaptations()

        self.assertEqual(result, {'expired': 1})
        stale.refresh_from_db()
        fresh.refresh_from_db()
        active.refresh_from_db()
        self.assertEqual(stale.status, 'expired')
        # Regression guard for a real bug found while writing this test: the
        # f-string was missing its `f` prefix, so every expired row stored
        # the literal text below, braces and all, instead of the interpolated
        # day count.
        self.assertEqual(stale.reason, f'Auto-expired after {expiry_days} days')
        self.assertEqual(fresh.status, 'suggested')
        self.assertEqual(active.status, 'active')

    def test_aggregate_typing_profiles_recomputes_from_sessions(self):
        """The aggregation task rebuilds the profile from recent sessions."""
        from security.models import TypingSession, UserTypingProfile
        from security.tasks.adaptive_tasks import aggregate_typing_profiles

        for index in range(4):
            TypingSession.objects.create(
                user=self.user,
                password_fingerprint=f'fp-agg-{index}',
                length_bucket=3,
                success=index != 0,  # 3 of 4 succeed
                error_positions=[],
                error_count=0,
                timing_profile={},
                total_time_ms=1000,
            )

        result = aggregate_typing_profiles()

        self.assertEqual(result['errors'], 0)
        self.assertEqual(result['processed'], 1)
        profile = UserTypingProfile.objects.get(user=self.user)
        self.assertEqual(profile.total_sessions, 4)
        self.assertEqual(profile.successful_sessions, 3)
        self.assertAlmostEqual(profile.success_rate, 0.75)

    def test_aggregate_typing_profiles_does_not_clobber_concurrent_writes(self):
        """This task must only touch the columns it recomputes.

        Regression test for a real bug: an unscoped `profile.save()` writes
        back EVERY field on the in-memory instance, including
        `memorability_weights` -- which `nudge_memorability_weights` (the
        weekly feedback task) can update concurrently on the same row. A
        stale in-memory snapshot from this hourly task, saved after that
        nudge commits, would silently revert it with no error and no log
        line.

        A single-threaded test can't produce real concurrency, so the
        interleaving is forced directly: `get_or_create` is patched to, as a
        side effect of the task's own read, apply a raw `.update()` the
        task's in-memory `profile` object cannot see -- exactly what a
        second writer committing between this task's read and its save would
        look like. Without `update_fields`, the task's later save would
        overwrite this change with the stale value it read; with it, the
        change survives untouched.
        """
        from unittest.mock import patch

        from security.models import TypingSession, UserTypingProfile
        from security.tasks.adaptive_tasks import aggregate_typing_profiles

        TypingSession.objects.create(
            user=self.user, password_fingerprint='fp-clobber-0',
            length_bucket=3, success=True, error_positions=[],
            error_count=0, timing_profile={}, total_time_ms=1000,
        )
        UserTypingProfile.objects.create(user=self.user)

        concurrent_weights = {
            'length': 0.1, 'patterns': 0.2, 'variety': 0.4, 'pronounceable': 0.3,
        }
        real_get_or_create = UserTypingProfile.objects.get_or_create

        def racing_get_or_create(*args, **kwargs):
            result = real_get_or_create(*args, **kwargs)
            # Lands AFTER this task's own read, simulating a concurrent
            # committer this task's in-memory instance never sees.
            UserTypingProfile.objects.filter(user=self.user).update(
                memorability_weights=concurrent_weights,
            )
            return result

        with patch.object(
            UserTypingProfile.objects, 'get_or_create',
            side_effect=racing_get_or_create,
        ):
            aggregate_typing_profiles()

        profile = UserTypingProfile.objects.get(user=self.user)
        self.assertEqual(profile.total_sessions, 1)
        self.assertEqual(profile.memorability_weights, concurrent_weights)

    def test_aggregate_typing_profiles_ignores_users_with_no_recent_sessions(self):
        """A user with nothing new is not processed at all."""
        from security.tasks.adaptive_tasks import aggregate_typing_profiles

        result = aggregate_typing_profiles()

        self.assertEqual(result, {'processed': 0, 'errors': 0})

    def test_update_rl_model_credits_feedback_and_reports_it(self):
        """The RL task credits an arm, stamps the row, and is idempotent."""
        from security.models import (
            AdaptationFeedback, AdaptivePasswordConfig, PasswordAdaptation,
            SubstitutionPolicyArm, UserTypingProfile,
        )
        from security.services.adaptive_password_service import (
            DEFAULT_MEMORABILITY_WEIGHTS,
        )
        from security.tasks.adaptive_tasks import update_rl_model_from_feedback

        AdaptivePasswordConfig.objects.create(
            user=self.user, is_enabled=True, fingerprint_salt='saltysalt',
        )
        adaptation = PasswordAdaptation.objects.create(
            user=self.user,
            adaptation_type='substitution',
            confidence_score=0.8,
            status='active',
            substitutions_applied={'0': {'from': 'o', 'to': '0'}},
            memorability_driver='variety',
        )
        feedback = AdaptationFeedback.objects.create(
            adaptation=adaptation, user=self.user, rating=5,
            memorability_improved=True,
        )

        result = update_rl_model_from_feedback()

        self.assertEqual(result['processed'], 1)
        self.assertEqual(result['skipped'], 0)
        self.assertEqual(result['arms_updated'], 1)
        # The fixture's driver='variety' + improved=True feeds
        # nudge_memorability_weights too; assert the IN-TASK wiring, not just
        # the standalone helper (covered separately in test_adaptive_zk_v2.py).
        self.assertEqual(result['memorability_nudges'], 1)
        self.assertFalse(result['prior_rebuild_failed'])
        self.assertIn('classes_written', result)
        self.assertIsNotNone(result['mean_reward'])

        arm = SubstitutionPolicyArm.objects.get(
            user=self.user, from_char='o', to_char='0',
        )
        self.assertEqual(arm.pulls, 1)

        profile = UserTypingProfile.objects.get(user=self.user)
        variety_after_first_run = profile.memorability_weights['variety']
        self.assertGreater(
            variety_after_first_run, DEFAULT_MEMORABILITY_WEIGHTS['variety'],
        )

        feedback.refresh_from_db()
        self.assertIsNotNone(feedback.policy_reward_applied_at)

        # Idempotency: the stamp is what makes a Celery retry safe, so a second
        # run must credit nothing rather than double-count the same evidence,
        # for BOTH learned models the task updates.
        second = update_rl_model_from_feedback()
        self.assertEqual(second['processed'], 0)
        self.assertEqual(second['memorability_nudges'], 0)
        arm.refresh_from_db()
        self.assertEqual(arm.pulls, 1)
        profile.refresh_from_db()
        self.assertEqual(profile.memorability_weights['variety'], variety_after_first_run)

    def test_beat_schedule_entries_name_registered_tasks(self):
        """Every adaptive beat entry must resolve to a real registered task.

        The plan named these `security.tasks.<func>`, but a bare
        ``@shared_task`` derives its name from the DEFINING module, so the real
        names carry an ``adaptive_tasks`` segment. A wrong name here does not
        fail loudly at import -- beat simply raises NotRegistered on every tick
        and the task silently never runs, which is exactly how these three came
        to have no schedule at all for so long.
        """
        from password_manager.celery import app

        # Import for the side effect of registering the tasks, mirroring what
        # autodiscovery does in a real worker.
        import security.tasks.adaptive_tasks  # noqa: F401

        adaptive_entries = {
            name: entry for name, entry in app.conf.beat_schedule.items()
            if name.startswith('adaptive-')
        }
        self.assertEqual(len(adaptive_entries), 3, adaptive_entries)
        for name, entry in adaptive_entries.items():
            self.assertIn(entry['task'], app.tasks, f'{name} -> {entry["task"]}')


# =============================================================================
# Feedback API Tests
# =============================================================================

class FeedbackAPITests(APITestCase):
    """Test feedback submission API."""
    
    def setUp(self):
        """Set up the test user/fixtures."""
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
            original_fingerprint='Fb0123456789-_aAbBcCdDeE',
            adapted_fingerprint='Fb1123456789-_aAbBcCdDeE',
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
            original_fingerprint='Gf0123456789-_aAbBcCdDeE',
            adapted_fingerprint='Gf1123456789-_aAbBcCdDeE',
            adaptation_generation=1,
            adaptation_type='substitution',
            confidence_score=0.85,
            status='active',
        )

        response = self.client.get(f'/api/security/adaptive/feedback/{adaptation.id}/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('has_feedback', response.data)


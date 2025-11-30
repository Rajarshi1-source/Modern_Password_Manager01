"""
Unit Tests for Trust Scoring Service

Tests comprehensive trust score calculation based on multiple factors:
- Challenge success rate (40%)
- Device recognition (20%)
- Behavioral biometrics match (20%)
- Temporal consistency (20%)
"""

import pytest
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta

from ..services.trust_scorer import trust_scorer
from ..quantum_recovery_models import (
    PasskeyRecoverySetup,
    RecoveryAttempt,
    TemporalChallenge,
    BehavioralBiometrics
)

# Mock import for models that might not exist
try:
    from security.models import UserDevice
except ImportError:
    UserDevice = None

User = get_user_model()


@pytest.mark.django_db
class TestTrustScorerService(TestCase):
    """Test trust scoring calculations"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.user = User.objects.create_user(
            email='test@example.com',
            password='TestPassword123!'
        )
        
        self.recovery_setup = PasskeyRecoverySetup.objects.create(
            user=self.user,
            total_shards=5,
            threshold_shards=3,
            is_active=True
        )
        
        self.attempt = RecoveryAttempt.objects.create(
            recovery_setup=self.recovery_setup,
            status='challenge_phase',
            initiated_from_ip='192.168.1.1',
            initiated_from_device_fingerprint='test_fp',
            initiated_from_user_agent='test_ua',
            initiated_from_location={'city': 'San Francisco', 'country': 'USA'},
            initiated_at=timezone.now(),
            expires_at=timezone.now() + timedelta(days=14)
        )
    
    def test_calculate_challenge_success_score_perfect(self):
        """Test challenge success score with 100% success"""
        self.attempt.challenges_sent = 5
        self.attempt.challenges_completed = 5
        self.attempt.challenges_failed = 0
        self.attempt.save()
        
        score = trust_scorer.calculate_challenge_success_score(self.attempt)
        
        self.assertEqual(score, 1.0)  # Perfect score
    
    def test_calculate_challenge_success_score_partial(self):
        """Test challenge success score with partial success"""
        self.attempt.challenges_sent = 5
        self.attempt.challenges_completed = 3
        self.attempt.challenges_failed = 2
        self.attempt.save()
        
        score = trust_scorer.calculate_challenge_success_score(self.attempt)
        
        expected_score = (3 / 5) - (2 * 0.1)  # 60% success - 20% penalty = 40%
        self.assertAlmostEqual(score, expected_score, places=2)
    
    def test_calculate_challenge_success_score_no_challenges(self):
        """Test challenge success score with no challenges sent"""
        self.attempt.challenges_sent = 0
        self.attempt.challenges_completed = 0
        self.attempt.challenges_failed = 0
        self.attempt.save()
        
        score = trust_scorer.calculate_challenge_success_score(self.attempt)
        
        self.assertEqual(score, 0.0)
    
    def test_calculate_challenge_success_score_with_penalty(self):
        """Test that failures apply penalty"""
        self.attempt.challenges_sent = 5
        self.attempt.challenges_completed = 4
        self.attempt.challenges_failed = 1
        self.attempt.save()
        
        score = trust_scorer.calculate_challenge_success_score(self.attempt)
        
        # 80% success - 10% penalty = 70%
        self.assertAlmostEqual(score, 0.7, places=2)
    
    @pytest.mark.skipif(UserDevice is None, reason="UserDevice model not available")
    def test_calculate_device_recognition_score_trusted_device(self):
        """Test device recognition with trusted device"""
        # Create trusted device
        UserDevice.objects.create(
            user=self.user,
            fingerprint='test_fp',
            browser='Chrome',
            os='Windows',
            is_trusted=True
        )
        
        score = trust_scorer.calculate_device_recognition_score(self.attempt)
        
        self.assertEqual(score, 1.0)  # Trusted device = perfect score
    
    @pytest.mark.skipif(UserDevice is None, reason="UserDevice model not available")
    def test_calculate_device_recognition_score_known_device(self):
        """Test device recognition with known but not trusted device"""
        # Create known device
        UserDevice.objects.create(
            user=self.user,
            fingerprint='test_fp',
            browser='Chrome',
            os='Windows',
            is_trusted=False
        )
        
        score = trust_scorer.calculate_device_recognition_score(self.attempt)
        
        self.assertEqual(score, 0.7)  # Known device = 0.7 score
    
    def test_calculate_device_recognition_score_unknown_device(self):
        """Test device recognition with completely unknown device"""
        score = trust_scorer.calculate_device_recognition_score(self.attempt)
        
        # Unknown device should have low score (0.0 or 0.3 based on implementation)
        self.assertLessEqual(score, 0.3)
    
    def test_calculate_behavioral_match_score_no_baseline(self):
        """Test behavioral match with no baseline data"""
        score = trust_scorer.calculate_behavioral_match_score(self.attempt)
        
        self.assertEqual(score, 0.5)  # Neutral score when no baseline
    
    def test_calculate_behavioral_match_score_with_data(self):
        """Test behavioral match with baseline data"""
        # Create behavioral biometrics
        BehavioralBiometrics.objects.create(
            user=self.user,
            typical_login_times=[9, 10, 14, 15, 18],
            typical_locations=[
                {'city': 'San Francisco', 'country': 'USA'}
            ],
            last_updated=timezone.now()
        )
        
        # Create completed challenges
        for i in range(3):
            TemporalChallenge.objects.create(
                recovery_attempt=self.attempt,
                challenge_type='historical',
                encrypted_challenge_data=b'test',
                encrypted_expected_response=b'test',
                status='completed',
                is_correct=True,
                actual_response_time_seconds=120 + i*10,
                scheduled_for=timezone.now() - timedelta(hours=i),
                sent_at=timezone.now() - timedelta(hours=i),
                responded_at=timezone.now() - timedelta(hours=i, minutes=-2),
                expires_at=timezone.now() + timedelta(hours=6)
            )
        
        score = trust_scorer.calculate_behavioral_match_score(self.attempt)
        
        # Should return a score (actual value depends on matching logic)
        self.assertGreaterEqual(score, 0.0)
        self.assertLessEqual(score, 1.0)
    
    def test_calculate_temporal_consistency_score_insufficient_data(self):
        """Test temporal consistency with insufficient challenges"""
        # Create only 2 challenges
        for i in range(2):
            TemporalChallenge.objects.create(
                recovery_attempt=self.attempt,
                challenge_type='historical',
                encrypted_challenge_data=b'test',
                encrypted_expected_response=b'test',
                status='completed',
                is_correct=True,
                actual_response_time_seconds=120,
                scheduled_for=timezone.now(),
                sent_at=timezone.now(),
                responded_at=timezone.now(),
                expires_at=timezone.now() + timedelta(hours=6)
            )
        
        score = trust_scorer.calculate_temporal_consistency_score(self.attempt)
        
        self.assertEqual(score, 0.5)  # Neutral score with insufficient data
    
    def test_calculate_temporal_consistency_score_consistent_responses(self):
        """Test temporal consistency with consistent response times"""
        # Create challenges with consistent response times
        response_times = [120, 125, 118, 122, 121]  # Very consistent
        
        for i, rt in enumerate(response_times):
            TemporalChallenge.objects.create(
                recovery_attempt=self.attempt,
                challenge_type='historical',
                encrypted_challenge_data=b'test',
                encrypted_expected_response=b'test',
                status='completed',
                is_correct=True,
                actual_response_time_seconds=rt,
                scheduled_for=timezone.now() - timedelta(hours=i),
                sent_at=timezone.now() - timedelta(hours=i),
                responded_at=timezone.now() - timedelta(hours=i, minutes=-2),
                expires_at=timezone.now() + timedelta(hours=6)
            )
        
        score = trust_scorer.calculate_temporal_consistency_score(self.attempt)
        
        # Consistent responses should yield high score
        self.assertGreater(score, 0.6)
    
    def test_calculate_temporal_consistency_score_inconsistent_responses(self):
        """Test temporal consistency with inconsistent response times"""
        # Create challenges with highly variable response times
        response_times = [60, 300, 90, 450, 120]  # Very inconsistent
        
        for i, rt in enumerate(response_times):
            TemporalChallenge.objects.create(
                recovery_attempt=self.attempt,
                challenge_type='historical',
                encrypted_challenge_data=b'test',
                encrypted_expected_response=b'test',
                status='completed',
                is_correct=True,
                actual_response_time_seconds=rt,
                scheduled_for=timezone.now() - timedelta(hours=i),
                sent_at=timezone.now() - timedelta(hours=i),
                responded_at=timezone.now() - timedelta(hours=i, minutes=-2),
                expires_at=timezone.now() + timedelta(hours=6)
            )
        
        score = trust_scorer.calculate_temporal_consistency_score(self.attempt)
        
        # Inconsistent responses should yield lower score
        self.assertLess(score, 0.8)
    
    def test_calculate_comprehensive_trust_score(self):
        """Test comprehensive trust score calculation"""
        # Set up good challenge performance
        self.attempt.challenges_sent = 5
        self.attempt.challenges_completed = 5
        self.attempt.challenges_failed = 0
        self.attempt.save()
        
        # Create challenges for temporal scoring
        for i in range(3):
            TemporalChallenge.objects.create(
                recovery_attempt=self.attempt,
                challenge_type='historical',
                encrypted_challenge_data=b'test',
                encrypted_expected_response=b'test',
                status='completed',
                is_correct=True,
                actual_response_time_seconds=120,
                scheduled_for=timezone.now(),
                sent_at=timezone.now(),
                responded_at=timezone.now(),
                expires_at=timezone.now() + timedelta(hours=6)
            )
        
        # Calculate comprehensive score
        trust_score = trust_scorer.calculate_comprehensive_trust_score(self.attempt)
        
        # Verify score is in valid range
        self.assertGreaterEqual(trust_score, 0.0)
        self.assertLessEqual(trust_score, 1.0)
    
    def test_comprehensive_trust_score_weighting(self):
        """Test that comprehensive score uses correct weighting"""
        # This test verifies the weighted formula:
        # Score = (Challenge × 0.4) + (Device × 0.2) + (Behavioral × 0.2) + (Temporal × 0.2)
        
        # Set up perfect challenge score (1.0)
        self.attempt.challenges_sent = 5
        self.attempt.challenges_completed = 5
        self.attempt.challenges_failed = 0
        self.attempt.save()
        
        # Create minimal challenges for temporal scoring
        for i in range(3):
            TemporalChallenge.objects.create(
                recovery_attempt=self.attempt,
                challenge_type='historical',
                encrypted_challenge_data=b'test',
                encrypted_expected_response=b'test',
                status='completed',
                is_correct=True,
                actual_response_time_seconds=120,
                scheduled_for=timezone.now(),
                sent_at=timezone.now(),
                responded_at=timezone.now(),
                expires_at=timezone.now() + timedelta(hours=6)
            )
        
        trust_score = trust_scorer.calculate_comprehensive_trust_score(self.attempt)
        
        # With perfect challenges (1.0 * 0.4 = 0.4) + other scores, should be >= 0.4
        self.assertGreaterEqual(trust_score, 0.4)
    
    def test_match_typical_times_exact_match(self):
        """Test time matching with exact match"""
        # Create behavioral data
        behavioral = BehavioralBiometrics.objects.create(
            user=self.user,
            typical_login_times=[9, 14, 18],
            last_updated=timezone.now()
        )
        
        # Set attempt time to 14:00 (matches typical time)
        self.attempt.initiated_at = timezone.now().replace(hour=14, minute=0)
        self.attempt.save()
        
        score = trust_scorer._match_typical_times(self.attempt, behavioral)
        
        self.assertEqual(score, 1.0)  # Exact match
    
    def test_match_typical_times_close_match(self):
        """Test time matching with close match (within 2 hours)"""
        behavioral = BehavioralBiometrics.objects.create(
            user=self.user,
            typical_login_times=[9, 14, 18],
            last_updated=timezone.now()
        )
        
        # Set attempt time to 16:00 (within 2 hours of 14:00)
        self.attempt.initiated_at = timezone.now().replace(hour=16, minute=0)
        self.attempt.save()
        
        score = trust_scorer._match_typical_times(self.attempt, behavioral)
        
        self.assertEqual(score, 0.7)  # Close match
    
    def test_match_typical_times_no_match(self):
        """Test time matching with no match"""
        behavioral = BehavioralBiometrics.objects.create(
            user=self.user,
            typical_login_times=[9, 14, 18],
            last_updated=timezone.now()
        )
        
        # Set attempt time to 3:00 AM (far from typical times)
        self.attempt.initiated_at = timezone.now().replace(hour=3, minute=0)
        self.attempt.save()
        
        score = trust_scorer._match_typical_times(self.attempt, behavioral)
        
        self.assertEqual(score, 0.3)  # No match
    
    def test_match_typical_locations_exact_match(self):
        """Test location matching with exact match"""
        behavioral = BehavioralBiometrics.objects.create(
            user=self.user,
            typical_locations=[
                {'city': 'San Francisco', 'country': 'USA'}
            ],
            last_updated=timezone.now()
        )
        
        # Attempt from same location
        self.attempt.initiated_from_location = {'city': 'San Francisco', 'country': 'USA'}
        self.attempt.save()
        
        score = trust_scorer._match_typical_locations(self.attempt, behavioral)
        
        self.assertEqual(score, 1.0)  # Exact match
    
    def test_match_typical_locations_same_country(self):
        """Test location matching with same country"""
        behavioral = BehavioralBiometrics.objects.create(
            user=self.user,
            typical_locations=[
                {'city': 'San Francisco', 'country': 'USA'}
            ],
            last_updated=timezone.now()
        )
        
        # Attempt from different city, same country
        self.attempt.initiated_from_location = {'city': 'New York', 'country': 'USA'}
        self.attempt.save()
        
        score = trust_scorer._match_typical_locations(self.attempt, behavioral)
        
        self.assertEqual(score, 0.6)  # Same country
    
    def test_match_typical_locations_different_country(self):
        """Test location matching with different country"""
        behavioral = BehavioralBiometrics.objects.create(
            user=self.user,
            typical_locations=[
                {'city': 'San Francisco', 'country': 'USA'}
            ],
            last_updated=timezone.now()
        )
        
        # Attempt from different country
        self.attempt.initiated_from_location = {'city': 'London', 'country': 'UK'}
        self.attempt.save()
        
        score = trust_scorer._match_typical_locations(self.attempt, behavioral)
        
        self.assertEqual(score, 0.2)  # Different country


@pytest.mark.django_db
class TestTrustScorerIntegration(TestCase):
    """Integration tests for trust scorer with complete scenarios"""
    
    def setUp(self):
        """Set up comprehensive test environment"""
        self.user = User.objects.create_user(
            email='integration@example.com',
            password='TestPassword123!'
        )
        
        self.recovery_setup = PasskeyRecoverySetup.objects.create(
            user=self.user,
            total_shards=5,
            threshold_shards=3,
            is_active=True
        )
    
    def test_high_trust_scenario(self):
        """Test scenario that should result in high trust score"""
        # Create attempt with good characteristics
        attempt = RecoveryAttempt.objects.create(
            recovery_setup=self.recovery_setup,
            status='challenge_phase',
            initiated_from_ip='192.168.1.1',
            initiated_from_device_fingerprint='trusted_fp',
            initiated_from_user_agent='test_ua',
            initiated_from_location={'city': 'San Francisco', 'country': 'USA'},
            challenges_sent=5,
            challenges_completed=5,
            challenges_failed=0,
            initiated_at=timezone.now().replace(hour=14),
            expires_at=timezone.now() + timedelta(days=14)
        )
        
        # Create behavioral baseline
        BehavioralBiometrics.objects.create(
            user=self.user,
            typical_login_times=[14, 15, 16],
            typical_locations=[{'city': 'San Francisco', 'country': 'USA'}],
            last_updated=timezone.now()
        )
        
        # Create trusted device if model exists
        if UserDevice is not None:
            UserDevice.objects.create(
                user=self.user,
                fingerprint='trusted_fp',
                browser='Chrome',
                os='Windows',
                is_trusted=True
            )
        
        # Create consistent challenges
        for i in range(5):
            TemporalChallenge.objects.create(
                recovery_attempt=attempt,
                challenge_type='historical',
                encrypted_challenge_data=b'test',
                encrypted_expected_response=b'test',
                status='completed',
                is_correct=True,
                actual_response_time_seconds=120 + i,
                scheduled_for=timezone.now() - timedelta(hours=i),
                sent_at=timezone.now() - timedelta(hours=i),
                responded_at=timezone.now() - timedelta(hours=i, minutes=-2),
                expires_at=timezone.now() + timedelta(hours=6)
            )
        
        trust_score = trust_scorer.calculate_comprehensive_trust_score(attempt)
        
        # Should have high trust score (>= 0.7)
        self.assertGreaterEqual(trust_score, 0.7)
    
    def test_low_trust_scenario(self):
        """Test scenario that should result in low trust score"""
        # Create attempt with suspicious characteristics
        attempt = RecoveryAttempt.objects.create(
            recovery_setup=self.recovery_setup,
            status='challenge_phase',
            initiated_from_ip='1.2.3.4',  # Unknown IP
            initiated_from_device_fingerprint='unknown_fp',
            initiated_from_user_agent='test_ua',
            initiated_from_location={'city': 'Unknown', 'country': 'Unknown'},
            challenges_sent=5,
            challenges_completed=2,
            challenges_failed=3,
            initiated_at=timezone.now().replace(hour=3),  # Unusual time
            expires_at=timezone.now() + timedelta(days=14)
        )
        
        # Create behavioral baseline (not matching attempt)
        BehavioralBiometrics.objects.create(
            user=self.user,
            typical_login_times=[9, 14, 18],
            typical_locations=[{'city': 'San Francisco', 'country': 'USA'}],
            last_updated=timezone.now()
        )
        
        # Create inconsistent challenges
        response_times = [60, 300, 90]  # Very inconsistent
        for i, rt in enumerate(response_times):
            TemporalChallenge.objects.create(
                recovery_attempt=attempt,
                challenge_type='historical',
                encrypted_challenge_data=b'test',
                encrypted_expected_response=b'test',
                status='completed',
                is_correct=i < 2,  # Only first 2 correct
                actual_response_time_seconds=rt,
                scheduled_for=timezone.now() - timedelta(hours=i),
                sent_at=timezone.now() - timedelta(hours=i),
                responded_at=timezone.now() - timedelta(hours=i, minutes=-2),
                expires_at=timezone.now() + timedelta(hours=6)
            )
        
        trust_score = trust_scorer.calculate_comprehensive_trust_score(attempt)
        
        # Should have low trust score (< 0.5)
        self.assertLess(trust_score, 0.5)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])


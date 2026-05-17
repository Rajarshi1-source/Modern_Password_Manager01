"""
Unit tests for the trust-score modulator.

These tests cover pure-function behavior only; no database access required.
"""
from unittest import TestCase

from ..services.trust_score_modulator import (
    DEFAULT_CANARY_HOURS,
    DEFAULT_DELAY_DAYS,
    ELEVATED_CANARY_HOURS,
    MAX_DELAY_DAYS,
    MIN_DELAY_DAYS,
    MIN_THRESHOLD,
    SUSPICIOUS_CANARY_HOURS,
    canary_alert_frequency_hours,
    compute_social_mesh_threshold,
    compute_time_lock_delay_days,
)


class TestComputeTimeLockDelayDays(TestCase):
    def test_none_returns_default(self):
        self.assertEqual(compute_time_lock_delay_days(None), DEFAULT_DELAY_DAYS)

    def test_invalid_type_returns_default(self):
        self.assertEqual(compute_time_lock_delay_days('abc'), DEFAULT_DELAY_DAYS)
        self.assertEqual(compute_time_lock_delay_days(object()), DEFAULT_DELAY_DAYS)

    def test_out_of_range_returns_default(self):
        self.assertEqual(compute_time_lock_delay_days(-0.1), DEFAULT_DELAY_DAYS)
        self.assertEqual(compute_time_lock_delay_days(1.5), DEFAULT_DELAY_DAYS)

    def test_perfect_match_returns_min(self):
        self.assertEqual(compute_time_lock_delay_days(1.0), MIN_DELAY_DAYS)

    def test_zero_match_returns_max(self):
        self.assertEqual(compute_time_lock_delay_days(0.0), MAX_DELAY_DAYS)

    def test_midpoint_returns_middle(self):
        # 14 - 0.5 * 11 = 8.5 -> rounds to 8 (banker's rounding) or 9
        result = compute_time_lock_delay_days(0.5)
        self.assertIn(result, (8, 9))

    def test_returns_int(self):
        self.assertIsInstance(compute_time_lock_delay_days(0.7), int)

    def test_string_numeric_is_coerced(self):
        self.assertEqual(compute_time_lock_delay_days('1.0'), MIN_DELAY_DAYS)


class TestComputeSocialMeshThreshold(TestCase):
    def test_high_score_lowers_threshold(self):
        self.assertEqual(compute_social_mesh_threshold(3, 5, 0.9), 2)

    def test_low_score_raises_threshold(self):
        self.assertEqual(compute_social_mesh_threshold(3, 5, 0.1), 4)

    def test_mid_score_unchanged(self):
        self.assertEqual(compute_social_mesh_threshold(3, 5, 0.5), 3)

    def test_none_score_unchanged(self):
        self.assertEqual(compute_social_mesh_threshold(3, 5, None), 3)

    def test_invalid_score_unchanged(self):
        self.assertEqual(compute_social_mesh_threshold(3, 5, 'bad'), 3)
        self.assertEqual(compute_social_mesh_threshold(3, 5, 1.5), 3)

    def test_floor_at_min_threshold_with_high_score(self):
        self.assertEqual(
            compute_social_mesh_threshold(MIN_THRESHOLD, 5, 1.0), MIN_THRESHOLD,
        )

    def test_ceiling_at_total_guardians_with_low_score(self):
        self.assertEqual(compute_social_mesh_threshold(5, 5, 0.0), 5)

    def test_single_guardian_unchanged(self):
        # Existing recovery flow can produce (threshold=1, total=1)
        # via min(2, len(active_guardians)) when only one guardian is
        # active. The modulator must accept it and pass it through
        # untouched — there's no headroom to raise or lower.
        self.assertEqual(compute_social_mesh_threshold(1, 1, 0.5), 1)
        self.assertEqual(compute_social_mesh_threshold(1, 1, 0.0), 1)
        self.assertEqual(compute_social_mesh_threshold(1, 1, 1.0), 1)
        self.assertEqual(compute_social_mesh_threshold(1, 1, None), 1)

    def test_zero_threshold_raises(self):
        with self.assertRaises(ValueError):
            compute_social_mesh_threshold(0, 5, 0.5)

    def test_zero_guardians_raises(self):
        with self.assertRaises(ValueError):
            compute_social_mesh_threshold(3, 0, 0.5)

    def test_base_exceeds_total_raises(self):
        with self.assertRaises(ValueError):
            compute_social_mesh_threshold(6, 5, 0.5)

    def test_boundary_high_score_exact(self):
        self.assertEqual(compute_social_mesh_threshold(3, 5, 0.8), 2)

    def test_boundary_low_score_exact(self):
        self.assertEqual(compute_social_mesh_threshold(3, 5, 0.2), 4)


class TestCanaryAlertFrequencyHours(TestCase):
    def test_none_returns_default(self):
        self.assertEqual(canary_alert_frequency_hours(None), DEFAULT_CANARY_HOURS)

    def test_invalid_type_returns_default(self):
        self.assertEqual(canary_alert_frequency_hours('bad'), DEFAULT_CANARY_HOURS)

    def test_out_of_range_returns_default(self):
        self.assertEqual(canary_alert_frequency_hours(2.0), DEFAULT_CANARY_HOURS)
        self.assertEqual(canary_alert_frequency_hours(-1.0), DEFAULT_CANARY_HOURS)

    def test_low_score_high_frequency(self):
        self.assertEqual(canary_alert_frequency_hours(0.1), SUSPICIOUS_CANARY_HOURS)

    def test_mid_score_elevated_frequency(self):
        self.assertEqual(canary_alert_frequency_hours(0.4), ELEVATED_CANARY_HOURS)

    def test_high_score_default_frequency(self):
        self.assertEqual(canary_alert_frequency_hours(0.9), DEFAULT_CANARY_HOURS)

    def test_boundary_low(self):
        self.assertEqual(canary_alert_frequency_hours(0.2), SUSPICIOUS_CANARY_HOURS)

    def test_boundary_mid(self):
        self.assertEqual(canary_alert_frequency_hours(0.5), ELEVATED_CANARY_HOURS)

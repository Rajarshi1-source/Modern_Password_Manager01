"""Unit tests for the HRV feature matcher."""

from __future__ import annotations

import pytest

pytest.importorskip('numpy')

from django.contrib.auth import get_user_model
from django.test import TestCase

from heartbeat_auth.models import HeartbeatProfile, ProfileStatus
from heartbeat_auth.services import feature_matcher

User = get_user_model()


def _features(mean_hr=70, rmssd=45, sdnn=55, pnn50=0.25, lf_hf=1.5):
    return {
        'mean_hr': mean_hr,
        'rmssd': rmssd,
        'sdnn': sdnn,
        'pnn50': pnn50,
        'lf_hf_ratio': lf_hf,
    }


class FeatureMatcherTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email='hb@example.com', password='x' * 12)
        self.profile = HeartbeatProfile.objects.create(
            user=self.user,
            status=ProfileStatus.ENROLLED,
            baseline_mean=[70.0, 45.0, 55.0, 0.25, 1.5],
            baseline_cov=[
                [9.0, 0, 0, 0, 0],
                [0, 9.0, 0, 0, 0],
                [0, 0, 9.0, 0, 0],
                [0, 0, 0, 0.01, 0],
                [0, 0, 0, 0, 0.25],
            ],
            baseline_rmssd=45.0,
            baseline_sdnn=55.0,
            baseline_mean_hr=70.0,
        )

    def test_exact_match_score_near_one(self):
        out = feature_matcher.match(self.profile, _features())
        self.assertGreater(out['score'], 0.95)
        self.assertLess(out['distance'], 0.5)

    def test_far_sample_scores_low(self):
        out = feature_matcher.match(
            self.profile,
            _features(mean_hr=140, rmssd=5, sdnn=10, pnn50=0.02, lf_hf=8),
        )
        self.assertLess(out['score'], 0.2)

    def test_rolling_updates_grow_count(self):
        mean0 = [70.0, 45.0, 55.0, 0.25, 1.5]
        cov0 = [[0.0] * 5 for _ in range(5)]
        mean1, cov1, n1 = feature_matcher.rolling_mean_cov(
            mean0, cov0, 0, [72.0, 46.0, 56.0, 0.26, 1.6],
        )
        self.assertEqual(n1, 1)
        mean2, cov2, n2 = feature_matcher.rolling_mean_cov(
            mean1, cov1, 1, [74.0, 47.0, 57.0, 0.27, 1.7],
        )
        self.assertEqual(n2, 2)
        # Mean should be halfway between the two observations.
        self.assertAlmostEqual(mean2[0], 73.0, places=5)

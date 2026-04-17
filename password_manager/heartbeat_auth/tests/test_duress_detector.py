"""Unit tests for the HRV duress detector."""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import TestCase

from heartbeat_auth.models import HeartbeatProfile, ProfileStatus
from heartbeat_auth.services import duress_detector

User = get_user_model()


class DuressDetectorTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email='dd@example.com', password='x' * 12)
        self.profile = HeartbeatProfile.objects.create(
            user=self.user,
            status=ProfileStatus.ENROLLED,
            baseline_rmssd=45.0,
            baseline_sdnn=8.0,  # used as proxy sigma for rmssd (~18% of mean)
            baseline_mean_hr=70.0,
            duress_rmssd_sigma=2.0,
        )

    def test_calm_reading_not_duress(self):
        out = duress_detector.detect(self.profile, {
            'rmssd': 46.0, 'mean_hr': 72.0,
        })
        self.assertFalse(out['duress'])
        self.assertLess(out['probability'], 0.5)

    def test_stress_reading_flags_duress(self):
        # rmssd: 45 - 20 = 25, drop = 20/8 = 2.5σ
        # mean_hr: 70 + 25 = 95, rise = 25 / max(3.5, 2) = ~7σ
        out = duress_detector.detect(self.profile, {
            'rmssd': 25.0, 'mean_hr': 95.0,
        })
        self.assertTrue(out['duress'])
        self.assertGreaterEqual(out['probability'], 0.5)

    def test_rmssd_drop_without_hr_rise_is_not_duress(self):
        out = duress_detector.detect(self.profile, {
            'rmssd': 25.0, 'mean_hr': 68.0,
        })
        self.assertFalse(out['duress'])

    def test_missing_baseline_returns_false(self):
        empty = HeartbeatProfile.objects.create(
            user=User.objects.create_user(email='empty@example.com', password='x' * 12),
            status=ProfileStatus.PENDING,
        )
        out = duress_detector.detect(empty, {'rmssd': 10.0, 'mean_hr': 110.0})
        self.assertFalse(out['duress'])
        self.assertEqual(out['reason'], 'insufficient_baseline')

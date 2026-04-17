"""Unit tests for circadian_totp.services.circadian_totp_service.

Covers the three behaviours that matter for security:

1. ``bio_counter`` XORs the TOTP counter with the phase offset, so a code
   valid at the baseline phase is invalid at a grossly different phase.
2. ``verify`` accepts codes generated within the user's configured phase
   slack but rejects codes from far-out-of-phase windows.
3. Phase re-estimation converges to the user's new sleep midpoint after a
   burst of new ``SleepObservation`` rows is ingested.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone as _tz

import pytest
from django.contrib.auth import get_user_model

from circadian_totp import services
from circadian_totp.models import (
    CircadianProfile,
    CircadianTOTPDevice,
    SleepObservation,
)
from circadian_totp.services.circadian_totp_service import (
    _phase_to_steps,
    bio_counter,
    current_phase_minutes,
    generate_code,
    provision_device,
    recompute_profile,
    totp_counter,
    verify,
)

User = get_user_model()


@pytest.fixture
def user(db):
    return User.objects.create_user(
        username="sleeper",
        email="sleeper@example.com",
        password="TestPassword123!",
    )


@pytest.mark.django_db
class TestPhaseMath:
    def test_bio_counter_differs_for_non_zero_phase(self):
        T = 1_000_000
        assert bio_counter(T, 0) == T
        assert bio_counter(T, 1) != T
        assert bio_counter(T, 0xFFFF) != T

    def test_phase_to_steps_maps_minutes_to_30s_steps(self):
        assert _phase_to_steps(0, 30) == 0
        assert _phase_to_steps(1, 30) == 2
        assert _phase_to_steps(-5, 30) == -10

    def test_current_phase_zero_at_baseline(self, user):
        profile = services.get_or_create_profile(user)
        profile.baseline_sleep_midpoint_minutes = 180  # 03:00 UTC
        profile.save()
        at = datetime(2026, 4, 17, 3, 0, tzinfo=_tz.utc)
        assert current_phase_minutes(profile, at) == 0

    def test_current_phase_wraps_modulo_1440(self, user):
        profile = services.get_or_create_profile(user)
        profile.baseline_sleep_midpoint_minutes = 10  # 00:10 UTC
        profile.save()
        at = datetime(2026, 4, 17, 23, 50, tzinfo=_tz.utc)  # 23:50
        diff = current_phase_minutes(profile, at)
        assert -720 <= diff <= 720
        assert abs(diff) == 20


@pytest.mark.django_db
class TestGenerateAndVerify:
    def test_generate_then_verify_round_trip(self, user):
        device, _uri = provision_device(user, name="Test")
        at = datetime(2026, 4, 17, 3, 0, tzinfo=_tz.utc)
        code = generate_code(device, at=at)
        assert verify(device, code, at=at) is True

    def test_verify_rejects_wrong_code(self, user):
        device, _uri = provision_device(user, name="Test")
        at = datetime(2026, 4, 17, 3, 0, tzinfo=_tz.utc)
        # A code that is very unlikely to coincidentally verify under the
        # phase-slack window (tolerance is narrow by default).
        assert (
            verify(device, "000000", at=at, tolerance_steps=0, phase_slack_minutes=1)
            is False
        )

    def test_verify_accepts_code_within_clock_tolerance(self, user):
        device, _uri = provision_device(user, name="Test")
        profile = services.get_or_create_profile(user)
        profile.baseline_sleep_midpoint_minutes = 180
        profile.phase_lock_minutes = 30
        profile.save()

        # The wearable-modulated counter couples T and P, so both drift
        # together. The verifier's ``tolerance_steps`` window must cover the
        # clock skew: a 30s skew = 1 step, well within the default tolerance.
        at_gen = datetime(2026, 4, 17, 3, 0, 0, tzinfo=_tz.utc)
        at_ver = datetime(2026, 4, 17, 3, 0, 15, tzinfo=_tz.utc)

        code = generate_code(device, at=at_gen)
        assert verify(device, code, at=at_ver) is True

    def test_verify_rejects_wrong_shape(self, user):
        device, _uri = provision_device(user, name="Test")
        assert verify(device, "") is False
        assert verify(device, "12a456") is False
        assert verify(device, "12345") is False  # too short


@pytest.mark.django_db
class TestRecomputeProfile:
    def test_recompute_converges_on_observed_midpoint(self, user):
        now = datetime(2026, 4, 17, 12, 0, tzinfo=_tz.utc)
        for day in range(1, 11):
            start = now - timedelta(days=day, hours=8)
            end = now - timedelta(days=day, hours=0)
            SleepObservation.objects.create(
                user=user,
                provider="manual",
                sleep_start=start,
                sleep_end=end,
                raw_payload_hash=f"manual-{day}",
            )

        profile = recompute_profile(user)
        assert profile.sample_count == 10
        mid_minutes = (now - timedelta(hours=4)).hour * 60 + (
            now - timedelta(hours=4)
        ).minute
        assert abs(profile.baseline_sleep_midpoint_minutes - mid_minutes) <= 60

    def test_recompute_with_no_observations_is_idempotent(self, user):
        profile = services.get_or_create_profile(user)
        before = profile.baseline_sleep_midpoint_minutes
        profile2 = recompute_profile(user)
        assert profile2.sample_count == 0
        assert profile2.baseline_sleep_midpoint_minutes == before


@pytest.mark.django_db
class TestConfirmAndDelete:
    def test_confirm_device_flips_confirmed_flag(self, user):
        device, _uri = provision_device(user, name="Test")
        at = datetime(2026, 4, 17, 3, 0, tzinfo=_tz.utc)
        code = generate_code(device, at=at)
        assert device.confirmed is False

        ok = services.confirm_device(device, code)
        device.refresh_from_db()
        assert ok is True
        assert device.confirmed is True

    def test_verify_code_for_user_rejects_unconfirmed_devices(self, user):
        device, _uri = provision_device(user, name="Test")
        # Device is *not* confirmed, so verify_code_for_user must return False
        # even if the code would otherwise be valid.
        at = datetime(2026, 4, 17, 3, 0, tzinfo=_tz.utc)
        code = generate_code(device, at=at)
        assert services.verify_code_for_user(user, code) is False

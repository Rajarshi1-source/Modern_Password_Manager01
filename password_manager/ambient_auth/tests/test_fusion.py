"""Core fusion + privacy fence tests for the ambient_auth service layer."""

from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model

from ambient_auth.models import (
    AmbientContext,
    AmbientObservation,
    AmbientProfile,
    AmbientSignalConfig,
    SIGNAL_KEYS,
)
from ambient_auth.services import (
    ingest,
    latest_signal,
    list_contexts,
    promote_context,
    recompute_signal_reliability,
    rename_context,
    reset_baseline,
    set_signal_config,
)


pytestmark = pytest.mark.django_db


def _user(username="ambient-user"):
    User = get_user_model()
    return User.objects.create_user(username=username, password="pw1234!!")  # nosec: test fixture


def _payload(
    *,
    digest: str = "aa" * 16,
    surface: str = "web",
    device_fp: str = "fp-123",
    coarse=None,
    availability=None,
):
    return {
        "surface": surface,
        "schema_version": 1,
        "device_fp": device_fp,
        "local_salt_version": 1,
        "signal_availability": availability or {
            "ambient_light": True,
            "accelerometer": True,
            "network_class": True,
        },
        "coarse_features": coarse or {
            "light_bucket": "indoor",
            "motion_class": "still",
            "connection_class": "wifi",
            "is_business_hours": True,
        },
        "embedding_digest": digest,
    }


def test_ingest_creates_profile_and_observation():
    user = _user()
    result = ingest(user, _payload())
    assert isinstance(result.observation, AmbientObservation)
    assert AmbientProfile.objects.filter(user=user).count() == 1
    assert AmbientObservation.objects.filter(user=user).count() == 1
    # First observation is always novel.
    assert result.matched_context is None
    assert result.novelty_score > 0.0
    assert result.trust_score == 0.0


def test_promote_context_makes_future_observations_match():
    user = _user()
    first = ingest(user, _payload())
    ctx = promote_context(user, first.observation.id, label="Home")
    assert isinstance(ctx, AmbientContext)
    assert ctx.is_trusted is True

    # Same digest + coarse features should now match the promoted context.
    second = ingest(user, _payload())
    assert second.matched_context is not None
    assert second.matched_context.id == ctx.id
    assert second.trust_score >= 0.0
    assert second.novelty_score == 0.0


def test_reject_raw_bssid_smuggled_in_coarse_features():
    user = _user()
    bad = _payload(
        coarse={
            "light_bucket": "indoor",
            "wifi_bssids": [
                "AA:BB:CC:DD:EE:01",
                "AA:BB:CC:DD:EE:02",
                "AA:BB:CC:DD:EE:03",
                "AA:BB:CC:DD:EE:04",
                "AA:BB:CC:DD:EE:05",
            ],
        },
    )
    with pytest.raises(ValueError):
        ingest(user, bad)


def test_reject_raw_audio_samples():
    user = _user()
    bad = _payload(
        coarse={
            "audio_pcm": [0, 1, 2, 3, 4, 5, 6, 7, 8, 9],
            "light_bucket": "dark",
        },
    )
    with pytest.raises(ValueError):
        ingest(user, bad)


def test_unknown_surface_rejected():
    user = _user()
    with pytest.raises(ValueError):
        ingest(user, _payload(surface="robot"))


def test_reset_baseline_removes_everything():
    user = _user()
    result = ingest(user, _payload())
    promote_context(user, result.observation.id, label="Home")
    ingest(user, _payload())

    assert AmbientProfile.objects.filter(user=user).exists()
    assert AmbientContext.objects.filter(profile__user=user).exists()
    assert AmbientObservation.objects.filter(user=user).exists()

    reset_baseline(user)
    assert not AmbientProfile.objects.filter(user=user).exists()
    assert not AmbientContext.objects.filter(profile__user=user).exists()
    assert not AmbientObservation.objects.filter(user=user).exists()


def test_rename_context_updates_label():
    user = _user()
    r = ingest(user, _payload())
    ctx = promote_context(user, r.observation.id, label="Home")
    updated = rename_context(user, ctx.id, "Office")
    assert updated.label == "Office"


def test_list_contexts_returns_user_contexts_only():
    u1 = _user("a")
    u2 = _user("b")
    r1 = ingest(u1, _payload(device_fp="fp-a"))
    promote_context(u1, r1.observation.id, label="Home")
    r2 = ingest(u2, _payload(device_fp="fp-b"))
    promote_context(u2, r2.observation.id, label="Home")

    assert len(list(list_contexts(u1))) == 1
    assert len(list(list_contexts(u2))) == 1


def test_signal_config_defaults_and_toggle():
    user = _user()
    cfgs = {c.signal_key: c for c in AmbientSignalConfig.objects.filter(user=user)}
    # Defaults are created lazily; trigger creation by calling set_signal_config.
    set_signal_config(user, "ambient_light", enabled=False)
    fresh = AmbientSignalConfig.objects.get(user=user, signal_key="ambient_light")
    assert fresh.enabled is False


def test_recompute_signal_reliability_returns_weight_per_signal():
    user = _user()
    r = ingest(user, _payload())
    promote_context(user, r.observation.id, label="Home")
    ingest(user, _payload())  # matched, trusted
    weights = recompute_signal_reliability(user)
    for key in SIGNAL_KEYS:
        assert key in weights
        assert 0.0 <= weights[key] <= 1.0


def test_latest_signal_reflects_recent_observation():
    user = _user()
    r = ingest(user, _payload())
    sig = latest_signal(user)
    assert sig is not None
    assert sig["observation_id"] == str(r.observation.id)
    assert "trust_score" in sig
    assert "novelty_score" in sig


def test_latest_signal_none_for_fresh_user():
    user = _user()
    assert latest_signal(user) is None

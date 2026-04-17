"""Core algorithm: biological-clock-modulated TOTP.

Principle
---------
Standard TOTP uses a counter ``T = floor(epoch / step)``. We derive a
"biological counter" that XORs ``T`` with a phase offset ``P`` expressed as a
number of ``step_seconds`` units past the user's baseline sleep midpoint::

    bio_counter(T, P) = T XOR (P & 0xFFFF)

Verification iterates over a small time-tolerance window AND a phase-slack
window (``phase_lock_minutes``) so that legitimate drift of the user's
circadian rhythm does not lock them out.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import logging
import secrets
import statistics
import struct
import time as _time
from datetime import datetime, timedelta, timezone as _tz
from typing import Iterable, List, Optional, Tuple
from urllib.parse import quote

from django.conf import settings
from django.db import transaction
from django.utils import timezone as djtz

from ..crypto_utils import (
    decrypt_bytes,
    decrypt_string,
    encrypt_bytes,
    encrypt_string,
)
from ..models import (
    CircadianProfile,
    CircadianTOTPDevice,
    SleepObservation,
    WearableLink,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Profile maintenance
# ---------------------------------------------------------------------------


def get_or_create_profile(user) -> CircadianProfile:
    profile, _ = CircadianProfile.objects.get_or_create(user=user)
    return profile


def _chronotype_from_midpoint(midpoint_minutes: int) -> str:
    """Map a UTC sleep-midpoint (minutes past UTC midnight) to a chronotype.

    Rough mapping after accounting for typical UTC-offset behavior: we use the
    raw UTC value because assuming a local offset is unsafe; the bucket
    assignment is inherently coarse.
    """

    # Wrap around so the function works for midpoints right after midnight.
    m = midpoint_minutes % 1440
    if m < 180:  # 00:00 - 03:00 UTC
        return "lark"
    if m >= 360:  # after 06:00 UTC
        return "owl"
    return "neutral"


def recompute_profile(user, window_days: int = 14) -> CircadianProfile:
    """Re-estimate the user's sleep-midpoint baseline.

    Uses a rolling median + interquartile-range trimmed mean over the last
    ``window_days`` observations. Robust to the occasional late-night
    ``SleepObservation`` outlier.
    """

    profile = get_or_create_profile(user)
    cutoff = djtz.now() - timedelta(days=window_days)
    obs = list(
        SleepObservation.objects.filter(user=user, sleep_end__gte=cutoff).order_by(
            "-sleep_end"
        )[:50]
    )
    if not obs:
        return profile

    midpoints = [o.midpoint_minutes_utc for o in obs]
    midpoints_unwrapped = _unwrap_circular_minutes(midpoints)

    median = statistics.median(midpoints_unwrapped)
    # Tukey-biweight-style trimming: keep values within 1.5 * MAD of the median.
    mad = statistics.median(abs(x - median) for x in midpoints_unwrapped) or 1.0
    trimmed = [x for x in midpoints_unwrapped if abs(x - median) <= 2.5 * mad]
    if not trimmed:
        trimmed = midpoints_unwrapped

    mean = sum(trimmed) / len(trimmed)
    stddev = statistics.pstdev(trimmed) if len(trimmed) > 1 else 15.0

    profile.baseline_sleep_midpoint_minutes = int(round(mean)) % 1440
    profile.phase_stddev_minutes = float(stddev)
    # 2-sigma window clipped to a sensible range.
    profile.phase_lock_minutes = int(max(10, min(45, round(2 * stddev))))
    profile.sample_count = len(obs)
    profile.chronotype = _chronotype_from_midpoint(
        profile.baseline_sleep_midpoint_minutes
    )
    profile.last_calibrated_at = djtz.now()
    profile.save()
    return profile


def _unwrap_circular_minutes(values: Iterable[int]) -> List[float]:
    """Unwrap a sequence of minutes-past-midnight values so that a cluster
    crossing midnight (e.g. [23:55, 00:10, 00:30]) clusters numerically.
    """

    vals = list(values)
    if not vals:
        return []
    # Pick a reference near the median to minimize wrap distance.
    ref = sorted(vals)[len(vals) // 2]
    unwrapped: List[float] = []
    for v in vals:
        # Choose the representation within [ref-720, ref+720).
        candidates = [v, v + 1440, v - 1440]
        best = min(candidates, key=lambda x: abs(x - ref))
        unwrapped.append(float(best))
    return unwrapped


# ---------------------------------------------------------------------------
# Observation ingestion
# ---------------------------------------------------------------------------


def _hash_observation(provider: str, sleep_start, sleep_end) -> str:
    payload = f"{provider}|{sleep_start.isoformat()}|{sleep_end.isoformat()}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def ingest_sleep_observations(user, provider: str, observations: list) -> int:
    """Insert observations, skipping duplicates. Returns number of inserts."""

    if not observations:
        return 0
    created_count = 0
    for obs in observations:
        start = obs["sleep_start"]
        end = obs["sleep_end"]
        efficiency = obs.get("efficiency_score")
        digest = _hash_observation(provider, start, end)
        try:
            with transaction.atomic():
                _, created = SleepObservation.objects.get_or_create(
                    user=user,
                    provider=provider,
                    sleep_start=start,
                    defaults={
                        "sleep_end": end,
                        "efficiency_score": efficiency,
                        "raw_payload_hash": digest,
                    },
                )
                if created:
                    created_count += 1
        except Exception:  # pragma: no cover - defensive
            logger.exception(
                "Failed to persist sleep observation for user=%s provider=%s",
                getattr(user, "id", None),
                provider,
            )
    return created_count


# ---------------------------------------------------------------------------
# Counter + code primitives
# ---------------------------------------------------------------------------


def totp_counter(at: Optional[datetime] = None, step_seconds: int = 30) -> int:
    at = at or djtz.now()
    return int(at.timestamp()) // step_seconds


def bio_counter(T: int, P: int) -> int:
    """XOR the time counter with a 16-bit phase offset."""
    return int(T) ^ (int(P) & 0xFFFF)


def _hotp(secret_b32: str, counter: int, digits: int = 6) -> str:
    key = base64.b32decode(secret_b32.upper() + "=" * ((8 - len(secret_b32) % 8) % 8))
    msg = struct.pack(">Q", counter)
    digest = hmac.new(key, msg, hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    code_int = (
        ((digest[offset] & 0x7F) << 24)
        | ((digest[offset + 1] & 0xFF) << 16)
        | ((digest[offset + 2] & 0xFF) << 8)
        | (digest[offset + 3] & 0xFF)
    )
    return str(code_int % (10**digits)).rjust(digits, "0")


def current_phase_minutes(
    profile: CircadianProfile, at: Optional[datetime] = None
) -> int:
    """Minutes from the user's baseline sleep midpoint to ``at``.

    Returned as a signed integer in [-720, 720]. When a user's rhythm is
    perfectly aligned, ``at`` near the baseline midpoint returns ~0.
    """
    at = at or djtz.now()
    now_utc = at.astimezone(_tz.utc)
    mins = now_utc.hour * 60 + now_utc.minute
    diff = mins - profile.baseline_sleep_midpoint_minutes
    if diff > 720:
        diff -= 1440
    elif diff < -720:
        diff += 1440
    return diff


def _phase_to_steps(phase_minutes: int, step_seconds: int) -> int:
    return int(round(phase_minutes * 60 / step_seconds))


# ---------------------------------------------------------------------------
# Device provisioning + verification
# ---------------------------------------------------------------------------


def provision_device(
    user, name: str = "Circadian Authenticator"
) -> Tuple[CircadianTOTPDevice, str]:
    """Create a new (unconfirmed) device and return its provisioning URI."""
    get_or_create_profile(user)
    secret_b32 = _generate_base32_secret(20)
    device = CircadianTOTPDevice.objects.create(
        user=user,
        name=name,
        secret_encrypted=encrypt_string(secret_b32),
        confirmed=False,
    )
    uri = _otpauth_uri(
        secret_b32,
        label=f"{getattr(user, 'username', 'user')}",
        issuer=getattr(settings, "TOTP_ISSUER", "SecureVault Circadian"),
        digits=device.digits,
        period=device.step_seconds,
    )
    return device, uri


def _generate_base32_secret(num_bytes: int = 20) -> str:
    raw = secrets.token_bytes(num_bytes)
    return base64.b32encode(raw).decode("ascii").rstrip("=")


def _otpauth_uri(
    secret: str, label: str, issuer: str, digits: int = 6, period: int = 30
) -> str:
    # We emit a standard otpauth URI so generic authenticator apps can be
    # bootstrapped with the non-biological secret. Verification on the server
    # is the step that enforces the biological counter; this URI is still
    # useful as a fallback + for provisioning UX.
    label_esc = quote(f"{issuer}:{label}")
    issuer_esc = quote(issuer)
    return (
        f"otpauth://totp/{label_esc}?secret={secret}"
        f"&issuer={issuer_esc}&digits={digits}&period={period}"
    )


def generate_code(device: CircadianTOTPDevice, at: Optional[datetime] = None) -> str:
    profile = get_or_create_profile(device.user)
    at = at or djtz.now()
    T = totp_counter(at, device.step_seconds)
    phase = current_phase_minutes(profile, at)
    P = _phase_to_steps(phase, device.step_seconds)
    secret = decrypt_string(device.secret_encrypted)
    return _hotp(secret, bio_counter(T, P), digits=device.digits)


def _phase_window(slack_minutes: int, step_seconds: int) -> Iterable[int]:
    max_steps = max(1, int(round(slack_minutes * 60 / step_seconds)))
    return range(-max_steps, max_steps + 1)


def verify(
    device: CircadianTOTPDevice,
    code: str,
    at: Optional[datetime] = None,
    tolerance_steps: int = 2,
    phase_slack_minutes: Optional[int] = None,
) -> bool:
    """Verify a biological TOTP code within the allowed drift windows."""

    if not code or not code.isdigit() or len(code) != device.digits:
        return False
    profile = get_or_create_profile(device.user)
    slack = (
        phase_slack_minutes
        if phase_slack_minutes is not None
        else profile.phase_lock_minutes
    )
    at = at or djtz.now()
    T = totp_counter(at, device.step_seconds)
    phase = current_phase_minutes(profile, at)
    P_center = _phase_to_steps(phase, device.step_seconds)
    secret = decrypt_string(device.secret_encrypted)

    expected = str(code).rjust(device.digits, "0")
    for dt in range(-tolerance_steps, tolerance_steps + 1):
        for dp in _phase_window(slack, device.step_seconds):
            candidate = _hotp(
                secret, bio_counter(T + dt, P_center + dp), digits=device.digits
            )
            if hmac.compare_digest(candidate, expected):
                device.last_verified_at = djtz.now()
                device.last_phase_used = P_center + dp
                device.save(update_fields=["last_verified_at", "last_phase_used"])
                return True
    return False


def confirm_device(device: CircadianTOTPDevice, code: str) -> bool:
    """Verify a code and mark the device confirmed on success."""
    if verify(device, code):
        if not device.confirmed:
            device.confirmed = True
            device.save(update_fields=["confirmed"])
        return True
    return False


def verify_code_for_user(user, code: str, device_id: Optional[str] = None) -> bool:
    """Try every confirmed device for the user (or a specific one)."""
    qs = CircadianTOTPDevice.objects.filter(user=user, confirmed=True)
    if device_id:
        qs = qs.filter(id=device_id)
    for device in qs:
        if verify(device, code):
            return True
    return False


# ---------------------------------------------------------------------------
# Wearable OAuth orchestration (dispatches to adapters)
# ---------------------------------------------------------------------------


def _get_adapter(provider: str):
    from .wearable_adapters import get_adapter

    return get_adapter(provider)


def wearable_authorize_url(user, provider: str) -> Tuple[str, str]:
    adapter = _get_adapter(provider)
    return adapter.authorize_url(user)


def wearable_exchange_code(
    user, provider: str, code: str, state: str
) -> WearableLink:
    adapter = _get_adapter(provider)
    tokens = adapter.exchange_code(user, code, state)
    link, _ = WearableLink.objects.update_or_create(
        user=user,
        provider=provider,
        defaults={
            "oauth_access_token_encrypted": encrypt_string(tokens.get("access_token", "")),
            "oauth_refresh_token_encrypted": encrypt_string(
                tokens.get("refresh_token", "")
            ),
            "scope": tokens.get("scope", "") or "",
            "token_type": tokens.get("token_type", "Bearer") or "Bearer",
            "expires_at": tokens.get("expires_at"),
            "external_user_id": str(tokens.get("user_id", "") or ""),
        },
    )
    return link

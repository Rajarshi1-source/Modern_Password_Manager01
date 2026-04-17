"""Duress detector for HRV authentication.

Heart Rate Variability (HRV) drops sharply under acute stress: RMSSD
shrinks (parasympathetic withdrawal) and mean HR rises (sympathetic
activation). We flag the reading as "duress" when BOTH of those
signatures are present relative to the user's own baseline, so a
naturally-high-HR user isn't permanently stuck in duress mode.

This is authentication, not medical triage — the thresholds are
deliberately conservative to keep the false-duress rate low. We'd
rather allow an angry-but-not-coerced user into their real vault than
subject them to a decoy every time their heart rate is up.
"""

from __future__ import annotations

import math
from typing import Dict


def detect(profile, features: Dict[str, float]) -> Dict[str, float]:
    """Return duress probability + flag.

    Signals:
        * ``rmssd`` must be lower than ``baseline_rmssd - sigma * base_sd``
        * ``mean_hr`` must exceed ``baseline_mean_hr + 1 * base_sd``
    """
    rmssd = _as_float(features.get('rmssd'))
    mean_hr = _as_float(features.get('mean_hr'))

    base_rmssd = profile.baseline_rmssd
    base_hr = profile.baseline_mean_hr
    sigma = float(getattr(profile, 'duress_rmssd_sigma', 2.0) or 2.0)

    if None in (base_rmssd, base_hr) or rmssd is None or mean_hr is None:
        return {'duress': False, 'probability': 0.0, 'reason': 'insufficient_baseline'}

    # Estimate baseline SD from SDNN as a rough proxy if a dedicated
    # sigma is not stored. Falls back to 10% of the baseline value
    # when neither is known.
    sd_rmssd = _as_float(getattr(profile, 'baseline_sdnn', None)) or (base_rmssd * 0.1)
    sd_hr = max(float(base_hr) * 0.05, 2.0)

    rmssd_drop = (base_rmssd - rmssd) / max(sd_rmssd, 1e-6)
    hr_rise = (mean_hr - base_hr) / max(sd_hr, 1e-6)

    duress = rmssd_drop >= sigma and hr_rise >= 1.0
    # Logistic squashing so the probability is monotonic in how far
    # the reading is past threshold.
    proba = _sigmoid(0.5 * (rmssd_drop - sigma) + 0.5 * (hr_rise - 1.0))
    if not duress:
        proba = min(proba, 0.49)  # never report >=0.5 unless flagged
    return {
        'duress': bool(duress),
        'probability': float(max(0.0, min(1.0, proba))),
        'rmssd_sigma_drop': float(rmssd_drop),
        'hr_sigma_rise': float(hr_rise),
    }


def _as_float(value):
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _sigmoid(x: float) -> float:
    try:
        return 1.0 / (1.0 + math.exp(-x))
    except OverflowError:  # pragma: no cover
        return 0.0 if x < 0 else 1.0

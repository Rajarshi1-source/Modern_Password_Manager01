"""Mood context estimation for challenge presentation.

We don't *gate* auth on mood — that would be both discriminatory and easy
to game — but we surface a best-effort mood tag so the orchestrator can
pick easier questions when the user appears stressed or rushed, and so
auditors can see the signals that informed a challenge decision.

Signals considered:
* Hour of day in the user's timezone (late-night = slightly more stress).
* Recent ``authentication.models.LoginAttempt`` failures (when available).
* Typing cadence hints passed in via ``signals`` (keystroke latency
  standard deviation, backspace rate, etc.).

All signals are optional — the service degrades to :class:`MoodContext.UNKNOWN`
gracefully if the caller provides no data.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import Dict, Optional

from django.utils import timezone

from ..models import MoodContext


@dataclass
class MoodEstimate:
    context: str
    signals: Dict[str, float]


class MoodContextService:
    def estimate(
        self,
        user,
        *,
        typing_signals: Optional[Dict[str, float]] = None,
        recent_window_minutes: int = 30,
    ) -> MoodEstimate:
        signals: Dict[str, float] = {}

        now = timezone.now()
        hour = now.hour
        if hour < 6 or hour >= 23:
            signals['late_hour'] = 1.0

        failures = self._recent_auth_failures(user, recent_window_minutes)
        if failures is not None:
            signals['recent_auth_failures'] = float(failures)

        if typing_signals:
            for k, v in typing_signals.items():
                try:
                    signals[f"typing_{k}"] = float(v)
                except (TypeError, ValueError):
                    continue

        context = self._classify(signals)
        return MoodEstimate(context=context, signals=signals)

    # ------------------------------------------------------------------
    def _classify(self, signals: Dict[str, float]) -> str:
        failures = signals.get('recent_auth_failures', 0.0)
        if failures >= 3:
            return MoodContext.FRUSTRATED
        if failures >= 1 or signals.get('typing_backspace_rate', 0.0) > 0.25:
            return MoodContext.STRESSED
        if signals.get('typing_mean_latency_ms', 0.0) and signals['typing_mean_latency_ms'] < 120:
            return MoodContext.RUSHED
        if signals.get('late_hour'):
            return MoodContext.STRESSED
        if not signals:
            return MoodContext.UNKNOWN
        return MoodContext.CALM

    def _recent_auth_failures(self, user, window_minutes: int) -> Optional[int]:
        try:
            from authentication.models import LoginAttempt

            cutoff = timezone.now() - timedelta(minutes=window_minutes)
            return LoginAttempt.objects.filter(
                user=user, was_successful=False, created_at__gte=cutoff
            ).count()
        except Exception:
            return None

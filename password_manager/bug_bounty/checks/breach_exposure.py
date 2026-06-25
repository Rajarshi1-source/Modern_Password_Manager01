"""Check: the user's credentials appear in known breaches.

Reuses the existing ML dark-web monitoring results (``ml_dark_web.MLBreachMatch``)
rather than running a new scan — this is pure aggregation of a signal the
platform already maintains.
"""

from __future__ import annotations

import logging

from .base import BaseCheck, FindingResult

logger = logging.getLogger(__name__)

# MLBreachData.severity labels are stored upper-case.
_SEVERE_LABELS = ('CRITICAL', 'HIGH')


class BreachExposureCheck(BaseCheck):
    check_id = 'breach_exposure'
    title = 'Credentials found in known data breaches'

    def _collect(self, user):
        """Return (unresolved_count, has_severe_breach) or None if unavailable."""
        try:
            from ml_dark_web.models import MLBreachMatch
        except ImportError:  # app not installed → expected "signal unavailable"
            logger.debug('Breach signal unavailable for self-test', exc_info=True)
            return None
        # A real ORM/runtime error below is a bug — let it bubble to the service.
        qs = MLBreachMatch.objects.filter(user=user, resolved=False)
        count = qs.count()
        if not count:
            return 0, False
        # Explicit presence check, not lexicographic ordering of the text labels
        # (which would rank 'MEDIUM' above 'HIGH'/'CRITICAL').
        has_severe = qs.filter(breach__severity__in=_SEVERE_LABELS).exists()
        return count, has_severe

    def run(self, user):
        collected = self._collect(user)
        if not collected:
            return []
        count, has_severe = collected
        if not count:
            return []
        severity = 'critical' if has_severe else 'high'
        return [
            FindingResult(
                check_id=self.check_id,
                title=self.title,
                severity=severity,
                remediation=(
                    'Rotate the affected passwords immediately and stop reusing '
                    'them across sites. Review the breach alerts in the dark-web '
                    'monitoring dashboard and mark them resolved once rotated.'
                ),
                fingerprint='breach-exposure',
                evidence={'unresolved_matches': count, 'severe_breach_present': has_severe},
            )
        ]

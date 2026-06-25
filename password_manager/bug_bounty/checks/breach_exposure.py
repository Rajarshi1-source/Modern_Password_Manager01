"""Check: the user's credentials appear in known breaches.

Reuses the existing ML dark-web monitoring results (``ml_dark_web.MLBreachMatch``)
rather than running a new scan — this is pure aggregation of a signal the
platform already maintains.
"""

from __future__ import annotations

import logging

from .base import BaseCheck, FindingResult

logger = logging.getLogger(__name__)

_HIGH_SEVERITIES = {'high', 'critical'}


class BreachExposureCheck(BaseCheck):
    check_id = 'breach_exposure'
    title = 'Credentials found in known data breaches'

    def _collect(self, user):
        """Return (unresolved_count, worst_severity) or None if unavailable."""
        try:
            from ml_dark_web.models import MLBreachMatch
            qs = MLBreachMatch.objects.filter(user=user, resolved=False)
            count = qs.count()
            worst = None
            if count:
                worst = (
                    qs.order_by('-breach__severity')
                    .values_list('breach__severity', flat=True)
                    .first()
                )
            return count, worst
        except Exception:
            logger.debug('Breach signal unavailable for self-test', exc_info=True)
            return None

    def run(self, user):
        collected = self._collect(user)
        if not collected:
            return []
        count, worst = collected
        if not count:
            return []
        severity = 'critical' if (worst or '').lower() in _HIGH_SEVERITIES else 'high'
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
                evidence={'unresolved_matches': count, 'worst_severity': worst},
            )
        ]
